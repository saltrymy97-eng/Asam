# services/purchases_service.py – منطق أعمال المشتريات (v7.0)
# ✅ فحص الرصيد قبل الدفع للمورد
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.vat_service import get_vat_rate
from services.currency_service import get_exchange_rate, get_base_currency
from services.fifo_service import add_batch
from services.chart_service import get_functional_account


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _read_functional_account(conn, functional_type):
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


# ---------- الموردون ----------
def get_suppliers():
    conn = get_connection()
    try:
        suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
        return [dict(s) for s in suppliers]
    finally:
        close_connection(conn)


def get_all_suppliers():
    conn = get_connection()
    try:
        suppliers = conn.execute("SELECT * FROM suppliers ORDER BY id DESC").fetchall()
        return [dict(s) for s in suppliers]
    finally:
        close_connection(conn)


def add_supplier(name, phone, address, username="admin"):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)",
            (name, phone, address)
        )
        supplier_id = cur.lastrowid
        conn.commit()
        log_action(username=username, action="إضافة مورد", table_name="suppliers",
                   new_value=f"المورد: {name}, الهاتف: {phone}")
        return supplier_id
    finally:
        close_connection(conn)


def get_products_for_purchase():
    conn = get_connection()
    try:
        products = conn.execute(
            "SELECT id, name, purchase_price FROM products ORDER BY name"
        ).fetchall()
        return [
            {"id": p["id"], "name": p["name"], "purchase_price": p["purchase_price"]}
            for p in products
        ]
    finally:
        close_connection(conn)


# ============================================================
# 🎯 المرحلة 1: حفظ الفاتورة + القيد (بدون paid_amount)
# ============================================================
def _save_invoice_core(supplier_id, items, username, currency_code,
                       exchange_rate, paid_amount_dec, remaining_dec,
                       payment_method, payment_status, total_local, total_base,
                       subtotal_local, vat_amount_local, vat_rate):
    """
    حفظ الفاتورة + القيد المحاسبي.
    ✅ الفاتورة تُحفظ بحالة 'unpaid' (paid_amount=0، remaining=total)
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN")

        supplier_row = conn.execute(
            "SELECT id, name FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
        if not supplier_row:
            raise Exception("المورد غير موجود")
        supplier_name = supplier_row["name"]

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

        # ✅ إدراج الفاتورة — بدون paid_amount
        cur = conn.execute(
            """INSERT INTO invoices 
               (type, supplier_id, invoice_date, total, total_base, status, 
                vat_rate, vat_amount, currency_code, exchange_rate,
                paid_amount, remaining_amount, payment_status, payment_method)
               VALUES (?, ?, date('now'), ?, ?, 'completed', ?, ?, ?, ?,
                       0, ?, 'unpaid', NULL)""",
            ("purchase", supplier_id, float(total_local), float(total_base),
             float(vat_rate), float(vat_amount_local), currency_code,
             float(exchange_rate), float(total_local))
        )
        invoice_id = cur.lastrowid

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

        from services.accounting_service import save_journal_entry

        inventory_account = _read_functional_account(conn, "inventory")
        suppliers_account = _read_functional_account(conn, "accounts_payable")
        vat_account = _read_functional_account(conn, "purchase_tax")

        lines = []

        lines.append({
            "account": inventory_account,
            "debit": float(subtotal_local),
            "credit": 0,
            "currency_code": currency_code,
            "exchange_rate": float(exchange_rate)
        })

        if float(vat_amount_local) > 0:
            lines.append({
                "account": vat_account,
                "debit": float(vat_amount_local),
                "credit": 0,
                "currency_code": currency_code,
                "exchange_rate": float(exchange_rate)
            })

        lines.append({
            "account": suppliers_account,
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
        return invoice_id, supplier_name, None

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return None, None, str(e)
    finally:
        close_connection(conn)


# ============================================================
# 🎯 المرحلة 2: سند الصرف — مع فحص الرصيد
# ============================================================
def _save_payment_side(invoice_id, supplier_id, supplier_name,
                       paid_amount_dec, cash_account, username):
    """
    إنشاء السند + تحديث الفاتورة تلقائياً.
    ✅ فحص الرصيد قبل محاولة الدفع.
    """
    if paid_amount_dec <= 0 or not cash_account:
        return None, None

    # ============================================================
    # ✅ جديد: فحص الرصيد قبل استدعاء create_voucher
    # ============================================================
    try:
        from services.cash_service import check_sufficient_balance
        ok, balance_err = check_sufficient_balance(
            cash_account, float(paid_amount_dec)
        )
        if not ok:
            return None, f"الرصيد غير كافٍ — {balance_err}"
    except ImportError:
        pass  # إذا لم تكن الدالة موجودة، نتجاهل (الفحص داخل create_voucher)

    try:
        from services.receipts_service import create_voucher
        voucher_id, verr = create_voucher(
            voucher_type='payment',
            party_type='supplier',
            party_id=supplier_id,
            amount=float(paid_amount_dec),
            account=cash_account,
            invoice_id=invoice_id,
            reference=f"دفعة فاتورة مشتريات #{invoice_id}",
            notes="دفعة تلقائية عند إنشاء الفاتورة",
            created_by=username,
            auto_link=True,
            conn=None,
        )
        if verr:
            return None, f"فشل إنشاء سند الصرف: {verr}"
        return voucher_id, None
    except ImportError as ie:
        return None, f"مكتبة السندات مفقودة: {ie}"
    except Exception as e:
        return None, f"خطأ غير متوقع: {e}"


# ============================================================
# 🎯 الدالة الرئيسية
# ============================================================
def create_purchase_invoice(supplier_id, items, username="admin",
                             currency_code="YER", exchange_rate=None,
                             paid_amount=None, payment_method="credit",
                             cash_account=None):
    """إنشاء فاتورة مشتريات كاملة"""
    # ============ التحقق الأولي ============
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

    # ============ حساب المبالغ ============
    product_prices = {}
    for item in items:
        user_price = item.get("unit_price") or item.get("unit_price_base")
        if user_price is not None:
            product_prices[item["product_id"]] = _to_decimal(user_price)
        else:
            conn_tmp = get_connection()
            try:
                row = conn_tmp.execute(
                    "SELECT purchase_price FROM products WHERE id = ?",
                    (item["product_id"],)
                ).fetchone()
                if not row:
                    return None, Decimal("0"), f"المنتج {item['product_id']} غير موجود"
                product_prices[item["product_id"]] = _to_decimal(row["purchase_price"])
            finally:
                close_connection(conn_tmp)

    subtotal_local = Decimal("0")
    subtotal_base = Decimal("0")
    for item in items:
        base_price = product_prices[item["product_id"]]
        qty = Decimal(str(item["quantity"]))
        subtotal_base += base_price * qty
        local_unit_price = _quantize(base_price / exchange_rate)
        subtotal_local += local_unit_price * qty

    subtotal_local = _quantize(subtotal_local)
    vat_amount_local = _quantize(subtotal_local * vat_rate)
    total_local = _quantize(subtotal_local + vat_amount_local)

    subtotal_base = _quantize(subtotal_base)
    vat_amount_base = _quantize(subtotal_base * vat_rate)
    total_base = _quantize(subtotal_base + vat_amount_base)

    # ============ معالجة paid_amount ============
    if paid_amount is None:
        paid_amount_dec = Decimal("0")
    else:
        paid_amount_dec = _to_decimal(paid_amount)
        if paid_amount_dec < 0:
            return None, Decimal("0"), "المبلغ المدفوع لا يمكن أن يكون سالباً"
        if paid_amount_dec > total_local:
            return None, Decimal("0"), (
                f"المبلغ المدفوع ({paid_amount_dec}) أكبر من إجمالي الفاتورة ({total_local})"
            )

    remaining_dec = total_local - paid_amount_dec

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

    # ============ المرحلة 1: الفاتورة + القيد ============
    invoice_id, supplier_name, err = _save_invoice_core(
        supplier_id=supplier_id,
        items=items,
        username=username,
        currency_code=currency_code,
        exchange_rate=exchange_rate,
        paid_amount_dec=paid_amount_dec,
        remaining_dec=remaining_dec,
        payment_method=payment_method,
        payment_status=payment_status,
        total_local=total_local,
        total_base=total_base,
        subtotal_local=subtotal_local,
        vat_amount_local=vat_amount_local,
        vat_rate=vat_rate,
    )

    if err:
        return None, Decimal("0"), f"فشل حفظ الفاتورة: {err}"

    # ============ المرحلة 2: السند ============
    payment_note = None
    if paid_amount_dec > 0 and cash_account:
        voucher_id, perr = _save_payment_side(
            invoice_id=invoice_id,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            paid_amount_dec=paid_amount_dec,
            cash_account=cash_account,
            username=username,
        )
        if perr:
            payment_note = f"⚠️ السند لم يُنشأ — {perr}"
            _add_note_to_invoice(invoice_id, payment_note)

    # ============ تسجيل التدقيق ============
    try:
        log_action(
            username=username, action="فاتورة مشتريات", table_name="invoices",
            record_id=invoice_id,
            new_value=(
                f"المورد: {supplier_name}, الإجمالي: {float(total_local):,.2f} {currency_code}, "
                f"المدفوع: {float(paid_amount_dec):,.2f}, المتبقي: {float(remaining_dec):,.2f}"
            )
        )
    except Exception:
        pass

    if payment_note:
        return invoice_id, total_local, payment_note
    return invoice_id, total_local, None


# ============================================================
# مساعد: إضافة ملاحظة إلى فاتورة
# ============================================================
def _add_note_to_invoice(invoice_id, note):
    try:
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE invoices
                SET reference = COALESCE(reference, '') || ' | ' || ?
                WHERE id = ?
            """, (note, invoice_id))
            conn.commit()
        finally:
            close_connection(conn)
    except Exception as e:
        print(f"⚠️ فشل إضافة الملاحظة: {e}")


# ============================================================
# استعلامات القراءة
# ============================================================
def get_purchase_invoices():
    conn = get_connection()
    try:
        invoices = conn.execute("""
            SELECT i.id, s.name AS supplier, i.invoice_date, i.total, i.total_base,
                   i.status, i.vat_rate, i.vat_amount, i.currency_code, i.exchange_rate,
                   i.reference,
                   COALESCE(i.paid_amount, 0) AS paid_amount,
                   COALESCE(i.remaining_amount, i.total) AS remaining_amount,
                   COALESCE(i.payment_status, 'unpaid') AS payment_status,
                   i.payment_method
            FROM invoices i
            LEFT JOIN suppliers s ON i.supplier_id = s.id
            WHERE i.type = 'purchase' ORDER BY i.id DESC
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
            d["has_warning"] = bool(
                d.get("reference") and "⚠️" in d["reference"]
            )
            result.append(d)
        return result
    finally:
        close_connection(conn)


def get_invoice_details(invoice_id):
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


# ============================================================
# مساعد: إنشاء السند يدوياً
# ============================================================
def create_payment_voucher_for_invoice(invoice_id, username="admin"):
    conn = get_connection()
    try:
        inv = conn.execute("""
            SELECT id, supplier_id, total, paid_amount, remaining_amount, 
                   payment_status, currency_code
            FROM invoices
            WHERE id = ? AND type = 'purchase'
        """, (invoice_id,)).fetchone()
        if not inv:
            return None, "الفاتورة غير موجودة"

        inv = dict(inv)
        paid = float(inv.get("paid_amount") or 0)
        if paid <= 0:
            return None, "لا يوجد مبلغ مدفوع على هذه الفاتورة"

        supplier_id = inv["supplier_id"]

        row = conn.execute("""
            SELECT account_code FROM cash_accounts 
            WHERE is_active = 1 LIMIT 1
        """).fetchone()
        if not row or not row["account_code"]:
            return None, "لا يوجد صندوق نشط"

        cash_account = row["account_code"]
    finally:
        close_connection(conn)

    voucher_id, perr = _save_payment_side(
        invoice_id=invoice_id,
        supplier_id=supplier_id,
        supplier_name="",
        paid_amount_dec=Decimal(str(paid)),
        cash_account=cash_account,
        username=username,
    )

    if perr:
        return None, perr

    try:
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE invoices
                SET reference = REPLACE(COALESCE(reference, ''), 
                    (SELECT ' | ' || reference FROM invoices WHERE id=?), '')
                WHERE id = ?
            """, (invoice_id, invoice_id))
            conn.commit()
        finally:
            close_connection(conn)
    except Exception:
        pass

    return voucher_id, None
