# services/purchases_service.py – منطق أعمال المشتريات (إصدار احترافي v2.0)
# ✅ يدعم: الشراء النقدي الكامل + الآجل الكامل + الجزئي (دفعة + متبقي)
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


# ---------- الموردون ----------
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


# ============================================================
# ✅ الدالة الرئيسية — معدّلة لدعم نقدي/آجل/جزئي
# ============================================================
def create_purchase_invoice(supplier_id, items, username="admin",
                             currency_code="YER", exchange_rate=None,
                             paid_amount=None, payment_method="credit",
                             cash_account=None):
    """
    إنشاء فاتورة مشتريات كاملة مع دعم 3 سيناريوهات:
    
    1. نقدي كامل:  paid_amount = total  → payment_method='cash'
    2. آجل كامل:   paid_amount = 0      → payment_method='credit'
    3. جزئي:       0 < paid_amount < total → payment_method='mixed'
    
    Args:
        paid_amount:    المبلغ المدفوع للمورد فوراً (None = آجل كامل)
        payment_method: 'cash' | 'credit' | 'bank' | 'mixed'
        cash_account:   كود حساب الصندوق/البنك (مطلوب إذا فيه دفع)
    
    Returns:
        (invoice_id, total, None)         عند النجاح
        (None, Decimal("0"), "رسالة")      عند الفشل
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
        supplier_row = conn.execute(
            "SELECT id, name FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
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

        # 4. ✅ معالجة paid_amount
        if paid_amount is None:
            paid_amount_dec = Decimal("0")           # آجل كامل افتراضي
        else:
            paid_amount_dec = _to_decimal(paid_amount)
            if paid_amount_dec < 0:
                raise Exception("المبلغ المدفوع لا يمكن أن يكون سالباً")
            if paid_amount_dec > total_local:
                raise Exception(
                    f"المبلغ المدفوع ({paid_amount_dec}) أكبر من إجمالي الفاتورة ({total_local})"
                )

        remaining_dec = total_local - paid_amount_dec

        # تحديد payment_method و payment_status تلقائياً
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

        # 5. إدراج الفاتورة مع الحقول الجديدة
        cur = conn.execute(
            """INSERT INTO invoices 
               (type, supplier_id, invoice_date, total, total_base, status, 
                vat_rate, vat_amount, currency_code, exchange_rate,
                paid_amount, remaining_amount, payment_status, payment_method)
               VALUES (?, ?, date('now'), ?, ?, 'completed', ?, ?, ?, ?,
                       ?, ?, ?, ?)""",
            ("purchase", supplier_id, float(total_local), float(total_base),
             float(vat_rate), float(vat_amount_local), currency_code,
             float(exchange_rate), float(paid_amount_dec),
             float(remaining_dec), payment_status, payment_method)
        )
        invoice_id = cur.lastrowid

        # 6. إدراج بنود الفاتورة + تحديث المخزون + FIFO
        for item in items:
            base_price = product_prices[item["product_id"]]
            qty = item["quantity"]
            local_unit_price = _quantize(base_price / exchange_rate)

            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], qty, float(local_unit_price))
            )

            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (qty, item["product_id"])
            )

            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) "
                "VALUES (?, 'in', ?, date('now'), ?)",
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

        # 7. ✅ إنشاء القيد المحاسبي (3 سيناريوهات)
        from services.accounting_service import save_journal_entry

        inventory_account = get_functional_account("inventory")
        suppliers_account = get_functional_account("accounts_payable")
        vat_account = get_functional_account("purchase_tax")

        lines = []

        # ✅ المخزون مدين (كامل المبلغ قبل الضريبة)
        lines.append({
            "account": inventory_account,
            "debit": float(subtotal_local),
            "credit": 0,
            "currency_code": currency_code,
            "exchange_rate": float(exchange_rate)
        })

        # ✅ ضريبة المدخلات مدين
        if float(vat_amount_local) > 0:
            lines.append({
                "account": vat_account,
                "debit": float(vat_amount_local),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        # ✅ الجزء النقدي: الصندوق/البنك دائن (المورد قبض فوراً)
        if paid_amount_dec > 0:
            if not cash_account:
                raise Exception("يجب تحديد حساب الصندوق/البنك عند وجود دفعة نقدية")
            lines.append({
                "account": cash_account,
                "debit": 0,
                "credit": float(paid_amount_dec),
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        # ✅ الجزء الآجل: الموردون دائن
        if remaining_dec > 0:
            lines.append({
                "account": suppliers_account,
                "debit": 0,
                "credit": float(remaining_dec),
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

        # 8. ✅ إنشاء سند صرف تلقائي (إذا فيه دفعة للمورد)
        voucher_id = None
        if paid_amount_dec > 0 and cash_account:
            try:
                from services.receipts_service import create_voucher
                voucher_id, verr = create_voucher(
                    voucher_type='payment',        # ← سند صرف للمورد
                    party_type='supplier',
                    party_id=supplier_id,
                    amount=float(paid_amount_dec),
                    account=cash_account,
                    invoice_id=invoice_id,
                    reference=f"دفعة فاتورة مشتريات #{invoice_id}",
                    notes=f"دفعة تلقائية عند إنشاء الفاتورة",
                    created_by=username,
                    auto_link=True,     # ← ربط تلقائي بـ invoice_payments
                    conn=conn           # ← نفس المعاملة
                )
                if verr:
                    raise Exception(f"فشل إنشاء سند الصرف: {verr}")
            except ImportError as ie:
                print(f"⚠️ لم يتم إنشاء سند تلقائي: {ie}")

        conn.commit()

        log_action(
            username=username, action="فاتورة مشتريات", table_name="invoices",
            record_id=invoice_id,
            new_value=(
                f"المورد: {supplier_name}, الإجمالي: {float(total_local):,.2f} {currency_code}, "
                f"المدفوع: {float(paid_amount_dec):,.2f}, المتبقي: {float(remaining_dec):,.2f}, "
                f"الضريبة: {float(vat_amount_local):,.2f}"
            )
        )

        return invoice_id, total_local, None

    except Exception as e:
        conn.rollback()
        return None, Decimal("0"), str(e)
    finally:
        conn.close()


def get_purchase_invoices():
    """جلب فواتير المشتريات (مع حقول الدفع الجديدة)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, s.name AS supplier, i.invoice_date, i.total, i.total_base,
               i.status, i.vat_rate, i.vat_amount, i.currency_code, i.exchange_rate,
               COALESCE(i.paid_amount, 0) AS paid_amount,
               COALESCE(i.remaining_amount, i.total) AS remaining_amount,
               COALESCE(i.payment_status, 'unpaid') AS payment_status,
               i.payment_method
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
        d["paid_amount"] = _to_decimal(d["paid_amount"])
        d["remaining_amount"] = _to_decimal(d["remaining_amount"])
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
