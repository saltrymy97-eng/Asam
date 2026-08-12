# services/purchases_service.py – منطق أعمال المشتريات المُحسَّن (إصدار احترافي - حسابات وظيفية)
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.vat_service import get_vat_rate
from services.currency_service import get_exchange_rate, get_base_currency
from services.fifo_service import add_batch
from services.chart_service import get_functional_account


# ---------- دوال مساعدة ----------
def _quantize(value: Decimal) -> Decimal:
    """تقريب المبلغ إلى منزلتين عشريتين"""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_decimal(value) -> Decimal:
    """تحويل القيمة إلى Decimal مع معالجة None"""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


# ---------- الدوال الرئيسية ----------
def get_suppliers():
    """جلب الموردين (ID واسم فقط)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return [dict(s) for s in suppliers]


def get_all_suppliers():
    """جلب جميع بيانات الموردين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT * FROM suppliers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(s) for s in suppliers]


def add_supplier(name, phone, address, username="admin"):
    """إضافة مورد جديد"""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)",
        (name, phone, address)
    )
    supplier_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(username=username, action="إضافة مورد", table_name="suppliers",
               new_value=f"المورد: {name}, الهاتف: {phone}")
    return supplier_id


def get_products_for_purchase():
    """جلب جميع المنتجات للشراء"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute(
        "SELECT id, name, purchase_price FROM products ORDER BY name"
    ).fetchall()
    conn.close()
    return [
        {"id": p["id"], "name": p["name"], "purchase_price": p["purchase_price"]}
        for p in products
    ]


def create_purchase_invoice(supplier_id, items, username="admin", currency_code="YER", exchange_rate=None):
    """
    إنشاء فاتورة مشتريات كاملة مع:
    - فحص المورد والمنتجات
    - دعم العملات المتعددة
    - إضافة دفعات FIFO تلقائياً
    - القيد المحاسبي قبل commit
    """
    if not items:
        return None, Decimal("0"), "يجب إضافة منتج واحد على الأقل"
    for item in items:
        if item["quantity"] <= 0:
            return None, Decimal("0"), "الكمية يجب أن تكون موجبة"
        price = item.get("unit_price") or item.get("unit_price_base")
        if price is not None and Decimal(str(price)) < 0:
            return None, Decimal("0"), "سعر الوحدة يجب أن لا يكون سالباً"

    base_currency = get_base_currency()
    base_code = base_currency["code"]

    if currency_code == base_code:
        exchange_rate = Decimal("1")
    else:
        if exchange_rate is None:
            exchange_rate = get_exchange_rate(currency_code, base_code)
        if exchange_rate is None or exchange_rate <= 0:
            return None, Decimal("0"), f"سعر صرف العملة {currency_code} غير متوفر"
        exchange_rate = Decimal(str(exchange_rate))

    vat_rate = _to_decimal(get_vat_rate())

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")

        # 1. التحقق من وجود المورد
        supplier_row = conn.execute("SELECT id, name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not supplier_row:
            raise Exception("المورد غير موجود")
        supplier_name = supplier_row["name"]

        # 2. التحقق من المنتجات وتجهيز البيانات
        product_prices = {}
        for item in items:
            row = conn.execute(
                "SELECT id, purchase_price FROM products WHERE id = ?",
                (item["product_id"],)
            ).fetchone()
            if not row:
                raise Exception(f"المنتج {item['product_id']} غير موجود")

            user_price = item.get("unit_price") or item.get("unit_price_base")
            if user_price is not None:
                base_price = _to_decimal(user_price)
            else:
                base_price = _to_decimal(row["purchase_price"])
            product_prices[item["product_id"]] = base_price

        # 3. حساب المبالغ
        subtotal_local = Decimal("0")
        subtotal_base = Decimal("0")

        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = Decimal(str(item["quantity"]))
            line_total_base = base_price * qty
            local_unit_price = _quantize(base_price / exchange_rate)
            line_total_local = local_unit_price * qty

            subtotal_base += line_total_base
            subtotal_local += line_total_local

        subtotal_local = _quantize(subtotal_local)
        vat_amount_local = _quantize(subtotal_local * vat_rate)
        total_local = _quantize(subtotal_local + vat_amount_local)

        subtotal_base = _quantize(subtotal_base)
        vat_amount_base = _quantize(subtotal_base * vat_rate)
        total_base = _quantize(subtotal_base + vat_amount_base)

        # 4. إدراج الفاتورة (باستخدام supplier_id)
        cur = conn.execute(
            """INSERT INTO invoices 
               (type, supplier_id, invoice_date, total, total_base, status, vat_rate, vat_amount, currency_code, exchange_rate)
               VALUES (?, ?, date('now'), ?, ?, 'completed', ?, ?, ?, ?)""",
            ("purchase", supplier_id, float(total_local), float(total_base), float(vat_rate),
             float(vat_amount_local), currency_code, float(exchange_rate))
        )
        invoice_id = cur.lastrowid

        # 5. إدراج بنود الفاتورة وتحديث المخزون وإضافة دفعات FIFO
        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = item["quantity"]
            local_unit_price = _quantize(base_price / exchange_rate)

            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], qty, float(local_unit_price))
            )

            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (qty, item["product_id"])
            )

            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'in', ?, date('now'), ?)",
                (item["product_id"], qty, f"فاتورة مشتريات #{invoice_id}")
            )

            success, error = add_batch(
                product_id=item["product_id"],
                quantity=qty,
                unit_cost=float(base_price),
                batch_date=date.today().strftime("%Y-%m-%d"),
                reference=f"فاتورة مشتريات #{invoice_id}",
                conn=conn
            )
            if not success:
                raise Exception(f"فشل إضافة دفعة FIFO للمنتج {item['product_id']}: {error}")

        # 6. إنشاء القيد المحاسبي (قبل commit) - باستخدام الحسابات الوظيفية
        from services.accounting_service import save_journal_entry

        # ✅ استخدام الحسابات الوظيفية بدلاً من الأكواد الثابتة
        inventory_account = get_functional_account("inventory")
        suppliers_account = get_functional_account("suppliers")
        vat_account = get_functional_account("purchase_tax")

        lines = [
            {
                "account": inventory_account,      # المخزون (مدين)
                "debit": float(subtotal_local),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            }
        ]

        if float(vat_amount_local) > 0:
            lines.append({
                "account": vat_account,            # ضريبة القيمة المضافة المدخلة (مدين)
                "debit": float(vat_amount_local),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        lines.append({
            "account": suppliers_account,          # الموردون (دائن)
            "debit": 0,
            "credit": float(total_local),
            "currency_code": currency_code,
            "exchange_rate": float(exchange_rate)
        })

        entry_id, entry_error = save_journal_entry(
            description=f"فاتورة مشتريات #{invoice_id} - {supplier_name}",
            lines=lines,
            entry_date=date.today().strftime("%Y-%m-%d"),
            conn=conn
        )

        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {entry_error}")

        conn.commit()

        log_action(
            username=username, action="فاتورة مشتريات", table_name="invoices",
            record_id=invoice_id,
            new_value=f"المورد: {supplier_name}, الإجمالي: {float(total_local):,.2f} {currency_code}, "
                      f"الضريبة: {float(vat_amount_local):,.2f}"
        )

        return invoice_id, total_local, None

    except Exception as e:
        conn.rollback()
        return None, Decimal("0"), str(e)
    finally:
        conn.close()


def get_purchase_invoices():
    """جلب فواتير المشتريات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, s.name AS supplier, i.invoice_date, i.total, i.total_base,
               i.status, i.vat_rate, i.vat_amount, i.currency_code, i.exchange_rate
        FROM invoices i
        LEFT JOIN suppliers s ON i.supplier_id = s.id
        WHERE i.type = 'purchase' ORDER BY i.id DESC
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
    """تفاصيل فاتورة المشتريات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    details = conn.execute("""
        SELECT p.name, ii.quantity, ii.unit_price,
               (ii.quantity * ii.unit_price) AS total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    return [
        {"name": d["name"], "quantity": d["quantity"],
         "unit_price": _to_decimal(d["unit_price"]), "total": _to_decimal(d["total"])}
        for d in details
    ]
