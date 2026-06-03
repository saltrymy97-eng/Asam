# services/sales_service.py – منطق أعمال المبيعات المُحسَّن
# يدعم: التحقق من المخزون، FIFO، تعدد العملات، ضريبة القيمة المضافة، القيد المحاسبي التلقائي

import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.vat_service import get_vat_rate
from services.currency_service import get_exchange_rate, get_base_currency
from services.fifo_service import consume_fifo, get_fifo_cost


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
    """إضافة عميل جديد"""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
        (name, phone, address)
    )
    customer_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(username=username, action="إضافة عميل", table_name="customers",
               new_value=f"العميل: {name}, الهاتف: {phone}")
    return customer_id


def get_products_for_sale():
    """جلب المنتجات المتاحة للبيع (الكمية > 0)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute(
        "SELECT id, name, selling_price, quantity FROM products WHERE quantity > 0 ORDER BY name"
    ).fetchall()
    conn.close()
    return [
        {"id": p["id"], "name": p["name"], "selling_price": p["selling_price"], "quantity": p["quantity"]}
        for p in products
    ]


def create_sale_invoice(customer_id, items, username="admin", currency_code="YER", exchange_rate=None):
    """
    إنشاء فاتورة مبيعات كاملة مع:
    - فحص المخزون
    - حساب تكلفة البضاعة المباعة FIFO
    - القيد المحاسبي قبل commit (ضمان التراجع الكامل)
    """
    if not items:
        return None, Decimal("0"), "يجب إضافة منتج واحد على الأقل"
    for item in items:
        if item["quantity"] <= 0:
            return None, Decimal("0"), "الكمية يجب أن تكون موجبة"
        price = item.get("unit_price") or item.get("unit_price_base") or 0
        if Decimal(str(price)) < 0:
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

        # 1. التحقق من المخزون وتجهيز بيانات FIFO
        product_prices = {}
        total_cogs = Decimal("0")  # إجمالي تكلفة البضاعة المباعة
        fifo_details = []  # تفاصيل استهلاك FIFO لكل منتج

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

            # حساب تكلفة FIFO لهذا المنتج
            qty = item["quantity"]
            fifo_cost = get_fifo_cost(item["product_id"], qty)
            if fifo_cost is None:
                raise Exception(f"لا توجد دفعات FIFO كافية للمنتج {item['product_id']}")
            
            total_cogs += fifo_cost
            fifo_details.append({
                "product_id": item["product_id"],
                "quantity": qty,
                "fifo_cost": fifo_cost
            })

            user_price = item.get("unit_price") or item.get("unit_price_base")
            if user_price is not None:
                base_price = _to_decimal(user_price)
            else:
                base_price = _to_decimal(row["selling_price"])
            product_prices[item["product_id"]] = base_price

        # 2. حساب المبالغ
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

        # 3. إدراج الفاتورة (بدون commit بعد)
        cur = conn.execute(
            """INSERT INTO invoices 
               (type, party_id, invoice_date, total, total_base, status, vat_rate, vat_amount, currency_code, exchange_rate)
               VALUES (?, ?, date('now'), ?, ?, 'completed', ?, ?, ?, ?)""",
            ("sale", customer_id, float(total_local), float(total_base), float(vat_rate),
             float(vat_amount_local), currency_code, float(exchange_rate))
        )
        invoice_id = cur.lastrowid

        # 4. إدراج بنود الفاتورة
        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = item["quantity"]
            local_unit_price = _quantize(base_price / exchange_rate)
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], qty, float(local_unit_price))
            )

        # 5. استهلاك دفعات FIFO وتحديث المخزون
        for detail in fifo_details:
            # استهلاك FIFO (ينشئ سجلات في fifo_consumptions ويحدث inventory_batches)
            consume_fifo(detail["product_id"], detail["quantity"], conn,
                        f"فاتورة مبيعات #{invoice_id}")

        # 6. خصم المخزون من جدول products
        for item in items:
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                (item["quantity"], item["product_id"], item["quantity"])
            )
            if conn.total_changes == 0:
                raise Exception(f"تعذر خصم المخزون للمنتج {item['product_id']} (تحديث متزامن)")
            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'out', ?, date('now'), ?)",
                (item["product_id"], item["quantity"], f"فاتورة مبيعات #{invoice_id}")
            )

        # 7. إنشاء القيد المحاسبي (قبل commit - هنا النقطة الحرجة)
        customer_name = "غير معروف"
        try:
            row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if row:
                customer_name = row["name"]
        except:
            pass

        from services.accounting_service import save_journal_entry

        lines = [
            {
                "account": customer_name,
                "debit": float(total_local),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            },
            {
                "account": "المبيعات",
                "debit": 0,
                "credit": float(subtotal_local),
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            }
        ]

        if float(vat_amount_local) > 0:
            lines.append({
                "account": "ضريبة القيمة المضافة المستحقة",
                "debit": 0,
                "credit": float(vat_amount_local),
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        # إضافة سطر تكلفة البضاعة المباعة (COGS)
        if float(total_cogs) > 0:
            lines.extend([
                {
                    "account": "تكلفة البضاعة المباعة",
                    "debit": float(total_cogs),
                    "credit": 0,
                    "currency_code": currency_code,
                    "exchange_rate": float(exchange_rate)
                },
                {
                    "account": "المخزون",
                    "debit": 0,
                    "credit": float(total_cogs),
                    "currency_code": currency_code,
                    "exchange_rate": float(exchange_rate)
                }
            ])

        entry_id, entry_error = save_journal_entry(
            description=f"فاتورة مبيعات #{invoice_id} - {customer_name}",
            lines=lines,
            entry_date=date.today().strftime("%Y-%m-%d")
        )

        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {entry_error}")

        # ✅ فقط بعد نجاح كل شيء: commit
        conn.commit()

        # تسجيل التدقيق
        log_action(
            username=username, action="فاتورة مبيعات", table_name="invoices",
            record_id=invoice_id,
            new_value=f"العميل: {customer_name}, الإجمالي: {float(total_local):,.2f} {currency_code}, "
                      f"تكلفة البضاعة: {float(total_cogs):,.2f}, الضريبة: {float(vat_amount_local):,.2f}"
        )

        return invoice_id, total_local, None

    except Exception as e:
        conn.rollback()
        return None, Decimal("0"), str(e)
    finally:
        conn.close()


def get_sale_invoices():
    """جلب فواتير المبيعات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, c.name AS customer, i.invoice_date, i.total, i.total_base,
               i.status, i.vat_rate, i.vat_amount, i.currency_code, i.exchange_rate
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id
        WHERE i.type = 'sale' ORDER BY i.id DESC
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
    """تفاصيل فاتورة المبيعات"""
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
