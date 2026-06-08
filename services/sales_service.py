# services/sales_service.py – منطق أعمال المبيعات المُحسَّن (إصدار PostgreSQL)
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


def _row_to_dict(columns, row):
    """تحويل صف من قاعدة البيانات إلى قاموس"""
    if row is None:
        return None
    return {columns[i]: row[i] for i in range(len(columns))}


def _rows_to_dicts(columns, rows):
    """تحويل قائمة صفوف إلى قائمة قواميس"""
    return [_row_to_dict(columns, r) for r in rows]


# ---------- الدوال الرئيسية ----------
def get_customers():
    """جلب العملاء (ID واسم فقط) للاختيار"""
    conn = get_connection()
    rows = conn.run("SELECT id, name FROM customers ORDER BY name")
    conn.close()
    return [{"id": r[0], "name": r[1]} for r in rows]


def get_all_customers():
    """جلب جميع بيانات العملاء"""
    conn = get_connection()
    rows = conn.run("SELECT * FROM customers ORDER BY id DESC")
    conn.close()
    cols = ["id", "name", "phone", "address"]
    return _rows_to_dicts(cols, rows)


def add_customer(name, phone, address, username="admin"):
    """إضافة عميل جديد"""
    conn = get_connection()
    conn.run(
        "INSERT INTO customers (name, phone, address) VALUES (:name, :phone, :address)",
        name=name, phone=phone, address=address
    )
    # pg8000 لا يدعم lastrowid مباشرة، نستخدم استعلام منفصل
    rows = conn.run("SELECT id FROM customers WHERE name = :name ORDER BY id DESC LIMIT 1", name=name)
    customer_id = rows[0][0] if rows else 0
    conn.close()
    log_action(username=username, action="إضافة عميل", table_name="customers",
               new_value=f"العميل: {name}, الهاتف: {phone}")
    return customer_id


def get_products_for_sale():
    """جلب المنتجات المتاحة للبيع (الكمية > 0)"""
    conn = get_connection()
    rows = conn.run(
        "SELECT id, name, selling_price, quantity FROM products WHERE quantity > 0 ORDER BY name"
    )
    conn.close()
    return [
        {"id": r[0], "name": r[1], "selling_price": r[2], "quantity": r[3]}
        for r in rows
    ]


def create_sale_invoice(customer_id, items, username="admin", currency_code="YER", exchange_rate=None):
    """
    إنشاء فاتورة مبيعات كاملة مع:
    - تجميع الكميات حسب المنتج وفحص المخزون
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

    from collections import defaultdict
    qty_by_product = defaultdict(int)
    for item in items:
        qty_by_product[item["product_id"]] += item["quantity"]

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
    try:
        # 1. التحقق من المخزون لكل منتج
        product_prices = {}
        total_cogs = Decimal("0")
        fifo_details = []

        for product_id, total_qty in qty_by_product.items():
            rows = conn.run(
                "SELECT selling_price, quantity FROM products WHERE id = :pid", pid=product_id
            )
            if not rows:
                raise Exception(f"المنتج {product_id} غير موجود")
            
            available = rows[0][1]
            if available < total_qty:
                raise Exception(f"المخزون غير كافٍ للمنتج '{product_id}'، المتاح: {available}، المطلوب: {total_qty}")

            fifo_cost = get_fifo_cost(product_id, total_qty)
            if fifo_cost is None:
                raise Exception(f"لا توجد دفعات FIFO كافية للمنتج {product_id}")
            
            total_cogs += _to_decimal(fifo_cost)
            fifo_details.append({
                "product_id": product_id,
                "quantity": total_qty,
                "fifo_cost": fifo_cost
            })

        for item in items:
            user_price = item.get("unit_price") or item.get("unit_price_base")
            if user_price is not None:
                product_prices[item["product_id"]] = _to_decimal(user_price)
            elif item["product_id"] not in product_prices:
                rows = conn.run("SELECT selling_price FROM products WHERE id = :pid", pid=item["product_id"])
                product_prices[item["product_id"]] = _to_decimal(rows[0][0])

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

        # 3. إدراج الفاتورة
        conn.run(
            """INSERT INTO invoices 
               (type, customer_id, invoice_date, total, total_base, status, vat_rate, vat_amount, currency_code, exchange_rate)
               VALUES (:type, :cid, CURRENT_DATE, :total, :total_base, 'completed', :vat_rate, :vat_amount, :currency, :rate)""",
            type="sale", cid=customer_id, total=float(total_local), total_base=float(total_base),
            vat_rate=float(vat_rate), vat_amount=float(vat_amount_local), currency=currency_code,
            rate=float(exchange_rate)
        )
        rows = conn.run("SELECT id FROM invoices ORDER BY id DESC LIMIT 1")
        invoice_id = rows[0][0]

        # 4. إدراج بنود الفاتورة
        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = item["quantity"]
            local_unit_price = _quantize(base_price / exchange_rate)
            conn.run(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (:iid, :pid, :qty, :price)",
                iid=invoice_id, pid=item["product_id"], qty=qty, price=float(local_unit_price)
            )

        # 5. استهلاك دفعات FIFO
        for detail in fifo_details:
            consume_fifo(detail["product_id"], detail["quantity"], conn,
                        f"فاتورة مبيعات #{invoice_id}")

        # 6. خصم المخزون
        for product_id, total_qty in qty_by_product.items():
            conn.run(
                "UPDATE products SET quantity = quantity - :qty WHERE id = :pid AND quantity >= :qty",
                qty=total_qty, pid=product_id
            )
            conn.run(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (:pid, 'out', :qty, CURRENT_DATE, :ref)",
                pid=product_id, qty=total_qty, ref=f"فاتورة مبيعات #{invoice_id}"
            )

        # 7. إنشاء القيد المحاسبي
        customer_name = "غير معروف"
        try:
            rows = conn.run("SELECT name FROM customers WHERE id = :cid", cid=customer_id)
            if rows:
                customer_name = rows[0][0]
        except:
            pass

        from services.accounting_service import save_journal_entry

        lines = [
            {"account": customer_name, "debit": float(total_local), "credit": 0,
             "currency_code": currency_code, "exchange_rate": float(exchange_rate)},
            {"account": "المبيعات", "debit": 0, "credit": float(subtotal_local),
             "currency_code": currency_code, "exchange_rate": float(exchange_rate)}
        ]

        if float(vat_amount_local) > 0:
            lines.append({"account": "ضريبة القيمة المضافة المستحقة", "debit": 0,
                         "credit": float(vat_amount_local), "currency_code": currency_code,
                         "exchange_rate": float(exchange_rate)})

        if float(total_cogs) > 0:
            lines.extend([
                {"account": "تكلفة البضاعة المباعة", "debit": float(total_cogs), "credit": 0,
                 "currency_code": currency_code, "exchange_rate": float(exchange_rate)},
                {"account": "المخزون", "debit": 0, "credit": float(total_cogs),
                 "currency_code": currency_code, "exchange_rate": float(exchange_rate)}
            ])

        entry_id, entry_error = save_journal_entry(
            description=f"فاتورة مبيعات #{invoice_id} - {customer_name}",
            lines=lines,
            entry_date=date.today().strftime("%Y-%m-%d"),
            conn=conn
        )

        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {entry_error}")

        log_action(
            username=username, action="فاتورة مبيعات", table_name="invoices",
            record_id=invoice_id,
            new_value=f"العميل: {customer_name}, الإجمالي: {float(total_local):,.2f} {currency_code}, "
                      f"تكلفة البضاعة: {float(total_cogs):,.2f}, الضريبة: {float(vat_amount_local):,.2f}"
        )

        return invoice_id, total_local, None

    except Exception as e:
        try:
            conn.run("ROLLBACK")
        except:
            pass
        return None, Decimal("0"), str(e)
    finally:
        conn.close()


def get_sale_invoices():
    """جلب فواتير المبيعات"""
    conn = get_connection()
    rows = conn.run("""
        SELECT i.id, c.name AS customer, i.invoice_date, i.total, i.total_base,
               i.status, i.vat_rate, i.vat_amount, i.currency_code, i.exchange_rate
        FROM invoices i
        LEFT JOIN customers c ON i.customer_id = c.id
        WHERE i.type = 'sale' ORDER BY i.id DESC
    """)
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r[0], "customer": r[1], "invoice_date": r[2], "total": _to_decimal(r[3]),
            "total_base": _to_decimal(r[4]), "status": r[5], "vat_rate": r[6],
            "vat_amount": _to_decimal(r[7]), "currency_code": r[8], "exchange_rate": _to_decimal(r[9])
        })
    return result


def get_invoice_details(invoice_id):
    """تفاصيل فاتورة المبيعات"""
    conn = get_connection()
    rows = conn.run("""
        SELECT p.name, ii.quantity, ii.unit_price,
               (ii.quantity * ii.unit_price) AS total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = :iid
    """, iid=invoice_id)
    conn.close()
    return [
        {"name": r[0], "quantity": r[1], "unit_price": _to_decimal(r[2]), "total": _to_decimal(r[3])}
        for r in rows
    ]
