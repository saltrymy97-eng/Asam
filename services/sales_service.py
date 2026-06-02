# services/sales_service.py – منطق أعمال المبيعات المُحسَّن
# يدعم: التحقق من المخزون، تعدد العملات بدقة مالية، تدقيق الإجراءات، ضريبة القيمة المضافة

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.vat_service import get_vat_rate
from services.currency_service import get_exchange_rate, get_base_currency


# ---------- دوال مساعدة ----------
def _quantize(value: Decimal) -> Decimal:
    """تقريب المبلغ إلى منزلتين عشريتين (لأغراض العرض والتخزين)"""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_decimal(value) -> Decimal:
    """تحويل القيمة إلى Decimal مع معالجة None"""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


# ---------- الدوال الرئيسية ----------
def get_customers():
    """جلب العملاء (ID واسم فقط) للاختيار"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
    conn.close()
    return [dict(c) for c in customers]


def get_all_customers():
    """جلب جميع بيانات العملاء"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(c) for c in customers]


def add_customer(name, phone, address, username="admin"):
    """إضافة عميل جديد، وتُرجع معرّف العميل"""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
        (name, phone, address)
    )
    customer_id = cur.lastrowid
    conn.commit()
    conn.close()

    log_action(
        username=username,
        action="إضافة عميل",
        table_name="customers",
        new_value=f"العميل: {name}, الهاتف: {phone}"
    )
    return customer_id


def get_products_for_sale():
    """
    جلب المنتجات المتاحة للبيع (الكمية > 0).
    يُعيد السعر الأساسي للبيع (بعملة الأساس)؛ التحويل للعملات الأخرى يتم لاحقاً.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute(
        "SELECT id, name, selling_price, quantity FROM products WHERE quantity > 0 ORDER BY name"
    ).fetchall()
    conn.close()
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "selling_price": p["selling_price"],
            "quantity": p["quantity"]
        }
        for p in products
    ]


def create_sale_invoice(customer_id, items, username="admin", currency_code="YER", exchange_rate=None):
    """
    إنشاء فاتورة مبيعات مع:
    - التحقق من المخزون
    - دعم العملات المتعددة (التحويل من عملة الأساس)
    - حسابات دقيقة باستخدام Decimal
    - تدقيق الإجراء

    :param customer_id: معرف العميل
    :param items: قائمة من dict تحتوي على المفاتيح product_id, quantity, unit_price (السعر الذي اختاره المستخدم)
    :param currency_code: رمز العملة المطلوبة للفاتورة (مثلاً USD)
    :param exchange_rate: سعر صرف العملة المطلوبة مقابل عملة الأساس (إذا لم يُعطَ يُحسَب تلقائياً)
    :return: (invoice_id, total_local, error_string)
    """
    # التحقق من المدخلات
    if not items:
        return None, Decimal("0"), "يجب إضافة منتج واحد على الأقل"
    for item in items:
        if item["quantity"] <= 0:
            return None, Decimal("0"), "الكمية يجب أن تكون موجبة"
        # دعم unit_price أو unit_price_base
        price = item.get("unit_price") or item.get("unit_price_base") or 0
        if Decimal(str(price)) < 0:
            return None, Decimal("0"), "سعر الوحدة يجب أن لا يكون سالباً"

    base_currency = get_base_currency()
    base_code = base_currency["code"]

    # إذا كانت العملة هي عملة الأساس، نجبر exchange_rate = 1
    if currency_code == base_code:
        exchange_rate = Decimal("1")
    else:
        if exchange_rate is None:
            exchange_rate = get_exchange_rate(currency_code, base_code)
        if exchange_rate is None or exchange_rate <= 0:
            return None, Decimal("0"), f"سعر صرف العملة {currency_code} غير متوفر"
        exchange_rate = Decimal(str(exchange_rate))

    # جلب نسبة الضريبة
    vat_rate = _to_decimal(get_vat_rate())

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")

        # 1. التحقق من المخزون وحجز الكميات (تحديث المنتجات فوراً لتجنب تزامن)
        product_prices = {}  # product_id -> Decimal selling_price_base
        for item in items:
            row = conn.execute(
                "SELECT selling_price, quantity FROM products WHERE id = ?",
                (item["product_id"],)
            ).fetchone()
            if not row:
                raise Exception(f"المنتج {item['product_id']} غير موجود")
            available = row["quantity"]
            if available < item["quantity"]:
                raise Exception(f"المخزون غير كافٍ للمنتج '{item['product_id']}'، المتاح: {available}")

            # استخدام السعر الذي أدخله المستخدم إن وُجد، وإلا سعر قاعدة البيانات
            user_price = item.get("unit_price") or item.get("unit_price_base")
            if user_price is not None:
                base_price = _to_decimal(user_price)
            else:
                base_price = _to_decimal(row["selling_price"])
            product_prices[item["product_id"]] = base_price

            # خصم المخزون مباشرة (Optimistic lock)
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                (item["quantity"], item["product_id"], item["quantity"])
            )
            if conn.total_changes == 0:
                raise Exception(f"تعذر خصم المخزون للمنتج {item['product_id']} (تحديث متزامن)")

        # 2. حساب المبالغ باستخدام Decimal
        subtotal_base = Decimal("0")
        subtotal_local = Decimal("0")

        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = Decimal(str(item["quantity"]))
            line_total_base = base_price * qty
            local_unit_price = base_price / exchange_rate
            local_unit_price = _quantize(local_unit_price)
            line_total_local = local_unit_price * qty
            line_total_base = _quantize(line_total_base)

            subtotal_base += line_total_base
            subtotal_local += line_total_local

        subtotal_local = _quantize(subtotal_local)
        vat_amount_local = _quantize(subtotal_local * vat_rate)
        total_local = _quantize(subtotal_local + vat_amount_local)

        subtotal_base = _quantize(subtotal_base)
        vat_amount_base = _quantize(subtotal_base * vat_rate)
        total_base = _quantize(subtotal_base + vat_amount_base)

        # 3. إدراج الفاتورة
        cur = conn.execute(
            """INSERT INTO invoices 
               (type, party_id, invoice_date, total, total_base, status, vat_rate, vat_amount, currency_code, exchange_rate)
               VALUES (?, ?, date('now'), ?, ?, 'completed', ?, ?, ?, ?)""",
            (
                "sale",
                customer_id,
                float(total_local),
                float(total_base),
                float(vat_rate),
                float(vat_amount_local),
                currency_code,
                float(exchange_rate)
            )
        )
        invoice_id = cur.lastrowid

        # 4. إدراج بنود الفاتورة (نخزن السعر المحلي الفعلي)
        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = item["quantity"]
            local_unit_price = _quantize(base_price / exchange_rate)
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], qty, float(local_unit_price))
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'out', ?, date('now'), ?)",
                (item["product_id"], qty, f"فاتورة مبيعات #{invoice_id}")
            )

        conn.commit()

        # تسجيل التدقيق
        customer_name = "غير معروف"
        try:
            row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if row:
                customer_name = row["name"]
        except:
            pass

        log_action(
            username=username,
            action="فاتورة مبيعات",
            table_name="invoices",
            record_id=invoice_id,
            new_value=(
                f"العميل: {customer_name}, "
                f"الإجمالي المحلي: {float(total_local):,.2f} {currency_code}, "
                f"الضريبة: {float(vat_amount_local):,.2f}, "
                f"سعر الصرف: {float(exchange_rate)}"
            )
        )

        return invoice_id, total_local, None

    except Exception as e:
        conn.rollback()
        return None, Decimal("0"), str(e)
    finally:
        conn.close()


def get_sale_invoices():
    """جلب فواتير المبيعات مع إجمالي العملة الأساس والمحلية"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id,
               c.name AS customer,
               i.invoice_date,
               i.total,
               i.total_base,
               i.status,
               i.vat_rate,
               i.vat_amount,
               i.currency_code,
               i.exchange_rate
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id
        WHERE i.type = 'sale'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    result = []
    for inv in invoices:
        d = dict(inv)
        d["total"] = _to_decimal(d["total"])
        d["total_base"] = _to_decimal(d["total_base"])
        d["vat_amount"] = _to_decimal(d["vat_amount"])
        d["exchange_rate"] = _to_decimal(d["exchange_rate"])
        result.append(d)
    return result


def get_invoice_details(invoice_id):
    """تفاصيل فاتورة المبيعات (المنتجات والأسعار والكميات)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    details = conn.execute("""
        SELECT p.name,
               ii.quantity,
               ii.unit_price,
               (ii.quantity * ii.unit_price) AS total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    return [
        {
            "name": d["name"],
            "quantity": d["quantity"],
            "unit_price": _to_decimal(d["unit_price"]),
            "total": _to_decimal(d["total"])
        }
        for d in details
    ]
