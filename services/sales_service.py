# services/sales_service.py – منطق أعمال المبيعات (إصدار احترافي v3.0)
# ✅ متوافق مع Connection Registry + يدعم نقدي/آجل/جزئي
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.vat_service import get_vat_rate
from services.currency_service import get_exchange_rate, get_base_currency
from services.fifo_service import consume_fifo, get_fifo_cost
from services.chart_service import get_functional_account


# ---------- دوال مساعدة ----------
def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


# ============================================================
# ✅ مساعد: قراءة الحسابات الوظيفية من نفس الاتصال
# ============================================================
def _read_functional_account(conn, functional_type):
    """قراءة كود الحساب الوظيفي من نفس الاتصال (بدون get_functional_account)"""
    try:
        r = conn.execute(
            "SELECT code FROM accounts WHERE functional_type = ? AND is_active = 1 LIMIT 1",
            (functional_type,)
        ).fetchone()
        if r:
            return r["code"]
    except Exception:
        pass
    return get_functional_account(functional_type)


# ---------- العملاء ----------
def get_customers():
    """جلب العملاء (ID واسم فقط) للاختيار"""
    conn = get_connection()
    try:
        customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        return [dict(c) for c in customers]
    finally:
        close_connection(conn)


def get_all_customers():
    """جلب جميع بيانات العملاء"""
    conn = get_connection()
    try:
        customers = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
        return [dict(c) for c in customers]
    finally:
        close_connection(conn)


def add_customer(name, phone, address, username="admin"):
    """إضافة عميل جديد"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
            (name, phone, address)
        )
        customer_id = cur.lastrowid
        conn.commit()
        log_action(username=username, action="إضافة عميل", table_name="customers",
                   new_value=f"العميل: {name}, الهاتف: {phone}")
        return customer_id
    finally:
        close_connection(conn)


def get_products_for_sale():
    """جلب المنتجات المتاحة للبيع (الكمية > 0)"""
    conn = get_connection()
    try:
        products = conn.execute(
            "SELECT id, name, selling_price, quantity FROM products "
            "WHERE quantity > 0 ORDER BY name"
        ).fetchall()
        return [
            {"id": p["id"], "name": p["name"],
             "selling_price": p["selling_price"], "quantity": p["quantity"]}
            for p in products
        ]
    finally:
        close_connection(conn)


# ============================================================
# ✅ الدالة الرئيسية — create_sale_invoice
# ============================================================
def create_sale_invoice(customer_id, items, username="admin",
                        currency_code="YER", exchange_rate=None,
                        paid_amount=None, payment_method="credit",
                        cash_account=None):
    """إنشاء فاتورة مبيعات كاملة — كل العمليات من نفس الاتصال"""
    if not items:
        return None, Decimal("0"), "يجب إضافة منتج واحد على الأقل"

    for item in items:
        if item["quantity"] <= 0:
            return None, Decimal("0"), "الكمية يجب أن تكون موجبة"
        price = item.get("unit_price") or item.get("unit_price_base") or 0
        if Decimal(str(price)) < 0:
            return None, Decimal("0"), "سعر الوحدة يجب أن لا يكون سالباً"

    # تجميع الكميات
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
        conn.execute("BEGIN")

        # 1. التحقق من المخزون + حساب COGS
        product_prices = {}
        total_cogs = Decimal("0")
        fifo_details = []

        for product_id, total_qty in qty_by_product.items():
            row = conn.execute(
                "SELECT selling_price, quantity FROM products WHERE id = ?",
                (product_id,)
            ).fetchone()
            if not row:
                raise Exception(f"المنتج {product_id} غير موجود")

            available = row["quantity"]
            if available < total_qty:
                raise Exception(
                    f"المخزون غير كافٍ للمنتج '{product_id}'، المتاح: {available}، المطلوب: {total_qty}"
                )

            fifo_cost = get_fifo_cost(product_id, total_qty)
            if fifo_cost is None:
                raise Exception(f"لا توجد دفعات FIFO كافية للمنتج {product_id}")

            total_cogs += _to_decimal(fifo_cost)
            fifo_details.append({
                "product_id": product_id,
                "quantity": total_qty,
                "fifo_cost": fifo_cost
            })

        # تجهيز الأسعار
        for item in items:
            user_price = item.get("unit_price") or item.get("unit_price_base")
            if user_price is not None:
                product_prices[item["product_id"]] = _to_decimal(user_price)
            elif item["product_id"] not in product_prices:
                row = conn.execute(
                    "SELECT selling_price FROM products WHERE id = ?",
                    (item["product_id"],)
                ).fetchone()
                product_prices[item["product_id"]] = _to_decimal(row["selling_price"])

        # 2. حساب الإجماليات
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

        # 3. معالجة paid_amount
        if paid_amount is None:
            paid_amount_dec = Decimal("0")
        else:
            paid_amount_dec = _to_decimal(paid_amount)
            if paid_amount_dec < 0:
                raise Exception("المبلغ المدفوع لا يمكن أن يكون سالباً")
            if paid_amount_dec > total_local:
                raise Exception(
                    f"المبلغ المدفوع ({paid_amount_dec}) أكبر من إجمالي الفاتورة ({total_local})"
                )

        remaining_dec = total_local - paid_amount_dec

        # تحديد payment_method و payment_status
        if paid_amount_dec == 0:
            if payment_method in ('cash', 'bank', 'mixed'):
                payment_method = 'credit'
            payment_status = 'unpaid'
        elif remaining_dec == 0:
            if payment_method == 'credit':
                payment_method = 'cash'
            payment_status = 'paid'
        else:
            if payment_method in ('cash', 'bank', 'credit'):
                payment_method = 'mixed'
            payment_status = 'partial'

        # 4. إدراج الفاتورة
        cur = conn.execute(
            """INSERT INTO invoices 
               (type, customer_id, invoice_date, total, total_base, status, 
                vat_rate, vat_amount, currency_code, exchange_rate,
                paid_amount, remaining_amount, payment_status, payment_method)
               VALUES (?, ?, date('now'), ?, ?, 'completed', ?, ?, ?, ?,
                       ?, ?, ?, ?)""",
            ("sale", customer_id, float(total_local), float(total_base),
             float(vat_rate), float(vat_amount_local), currency_code,
             float(exchange_rate), float(paid_amount_dec),
             float(remaining_dec), payment_status, payment_method)
        )
        invoice_id = cur.lastrowid

        # 5. إدراج بنود الفاتورة
        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = item["quantity"]
            local_unit_price = _quantize(base_price / exchange_rate)
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], qty, float(local_unit_price))
            )

        # 6. استهلاك FIFO
        for detail in fifo_details:
            consume_fifo(detail["product_id"], detail["quantity"], conn,
                        f"فاتورة مبيعات #{invoice_id}")

        # 7. خصم المخزون
        for product_id, total_qty in qty_by_product.items():
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
                (total_qty, product_id, total_qty)
            )
            if conn.total_changes == 0:
                raise Exception(f"تعذر خصم المخزون للمنتج {product_id} (تحديث متزامن)")
            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) "
                "VALUES (?, 'out', ?, date('now'), ?)",
                (product_id, total_qty, f"فاتورة مبيعات #{invoice_id}")
            )

        # 8. جلب اسم العميل
        row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
        customer_name = row["name"] if row else "غير معروف"

        # 9. القيد المحاسبي — قراءة الحسابات من نفس الاتصال
        from services.accounting_service import save_journal_entry

        customers_account = _read_functional_account(conn, "accounts_receivable")
        sales_account = _read_functional_account(conn, "sales_revenue")
        vat_account = _read_functional_account(conn, "sales_tax")
        cogs_account = _read_functional_account(conn, "cogs")
        inventory_account = _read_functional_account(conn, "inventory")

        lines = []

        if paid_amount_dec > 0:
            if not cash_account:
                raise Exception("يجب تحديد حساب الصندوق/البنك عند وجود دفعة نقدية")
            lines.append({
                "account": cash_account,
                "debit": float(paid_amount_dec),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        if remaining_dec > 0:
            lines.append({
                "account": customers_account,
                "debit": float(remaining_dec),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        lines.append({
            "account": sales_account,
            "debit": 0,
            "credit": float(subtotal_local),
            "currency_code": currency_code,
            "exchange_rate": float(exchange_rate)
        })

        if float(vat_amount_local) > 0:
            lines.append({
                "account": vat_account,
                "debit": 0,
                "credit": float(vat_amount_local),
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        if float(total_cogs) > 0:
            lines.extend([
                {
                    "account": cogs_account,
                    "debit": float(total_cogs),
                    "credit": 0,
                    "currency_code": currency_code,
                    "exchange_rate": float(exchange_rate)
                },
                {
                    "account": inventory_account,
                    "debit": 0,
                    "credit": float(total_cogs),
                    "currency_code": currency_code,
                    "exchange_rate": float(exchange_rate)
                }
            ])

        entry_id, entry_error = save_journal_entry(
            description=f"فاتورة مبيعات #{invoice_id} - {customer_name}",
            lines=lines,
            entry_date=date.today().strftime("%Y-%m-%d"),
            conn=conn
        )

        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {entry_error}")

        # 10. سند القبض التلقائي
        voucher_id = None
        if paid_amount_dec > 0 and cash_account:
            try:
                from services.receipts_service import create_voucher
                voucher_id, verr = create_voucher(
                    voucher_type='receipt',
                    party_type='customer',
                    party_id=customer_id,
                    amount=float(paid_amount_dec),
                    account=cash_account,
                    invoice_id=invoice_id,
                    reference=f"دفعة فاتورة #{invoice_id}",
                    notes=f"دفعة تلقائية عند إنشاء الفاتورة",
                    created_by=username,
                    auto_link=True,
                    conn=conn
                )
                if verr:
                    raise Exception(f"فشل إنشاء سند القبض: {verr}")
            except ImportError as ie:
                print(f"⚠️ لم يتم إنشاء سند تلقائي: {ie}")

        conn.commit()

        log_action(
            username=username, action="فاتورة مبيعات", table_name="invoices",
            record_id=invoice_id,
            new_value=(
                f"العميل: {customer_name}, الإجمالي: {float(total_local):,.2f} {currency_code}, "
                f"المدفوع: {float(paid_amount_dec):,.2f}, المتبقي: {float(remaining_dec):,.2f}, "
                f"تكلفة البضاعة: {float(total_cogs):,.2f}, الضريبة: {float(vat_amount_local):,.2f}"
            )
        )

        return invoice_id, total_local, None

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return None, Decimal("0"), str(e)
    finally:
        close_connection(conn)


def get_sale_invoices():
    """جلب فواتير المبيعات"""
    conn = get_connection()
    try:
        invoices = conn.execute("""
            SELECT i.id, c.name AS customer, i.invoice_date, i.total, i.total_base,
                   i.status, i.vat_rate, i.vat_amount, i.currency_code, i.exchange_rate,
                   COALESCE(i.paid_amount, 0) AS paid_amount,
                   COALESCE(i.remaining_amount, i.total) AS remaining_amount,
                   COALESCE(i.payment_status, 'unpaid') AS payment_status,
                   i.payment_method
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE i.type = 'sale' ORDER BY i.id DESC
        """).fetchall()
        result = []
        for inv in invoices:
            d = dict(inv)
            d["total"] = _to_decimal(d["total"])
            d["total_base"] = _to_decimal(d["total_base"])
            d["vat_amount"] = _to_decimal(d["vat_amount"])
            d["exchange_rate"] = _to_decimal(d["exchange_rate"])
            d["paid_amount"] = _to_decimal(d["paid_amount"])
            d["remaining_amount"] = _to_decimal(d["remaining_amount"])
            result.append(d)
        return result
    finally:
        close_connection(conn)


def get_invoice_details(invoice_id):
    """تفاصيل فاتورة المبيعات"""
    conn = get_connection()
    try:
        details = conn.execute("""
            SELECT p.name, ii.quantity, ii.unit_price,
                   (ii.quantity * ii.unit_price) AS total
            FROM invoice_items ii
            JOIN products p ON ii.product_id = p.id
            WHERE ii.invoice_id = ?
        """, (invoice_id,)).fetchall()
        return [
            {"name": d["name"], "quantity": d["quantity"],
             "unit_price": _to_decimal(d["unit_price"]),
             "total": _to_decimal(d["total"])}
            for d in details
        ]
    finally:
        close_connection(conn)
