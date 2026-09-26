# services/receipts_service.py – سندات القبض والصرف الاحترافية
# v3.0 — ربط يدوي للفواتير + دفعات متعددة + إلغاء الربط + فحوصات سلامة
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.accounting_service import save_journal_entry
from services.chart_service import get_functional_account


# ============================================================
# إنشاء الجداول
# ============================================================
def create_vouchers_table():
    """إنشاء جدول السندات إذا لم يكن موجوداً"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            party_type TEXT NOT NULL,
            party_id INTEGER,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            invoice_id INTEGER,
            journal_entry_id INTEGER,
            reference TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_cash_accounts():
    """جلب حسابات النقدية (المستوى الثاني تحت الأصول)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("""
        SELECT code, name FROM accounts
        WHERE parent_id = (SELECT id FROM accounts WHERE code = '1')
        ORDER BY code
    """).fetchall()
    conn.close()
    if not accounts:
        return [{"code": "صندوق", "name": "صندوق"}, {"code": "بنك", "name": "بنك"}]
    return [{"code": a["code"], "name": a["name"]} for a in accounts]


# ============================================================
# ✅ دوال جديدة: الربط اليدوي وإدارة العلاقات
# ============================================================

def get_voucher_linked_amount(voucher_id, conn=None):
    """
    حساب المبلغ الإجمالي الذي تم ربطه من هذا السند (عبر invoice_payments).
    يُستخدم لفحص عدم تجاوز قيمة السند.
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM invoice_payments WHERE voucher_id = ?",
            (voucher_id,)
        ).fetchone()
        return float(row[0]) if row else 0.0
    finally:
        if own_conn:
            conn.close()


def get_unlinked_vouchers(party_type=None, party_id=None, limit=100, conn=None):
    """
    جلب السندات التي لم يتم ربطها بأي فاتورة (أو رُبط منها جزء فقط).
    
    Args:
        party_type: 'customer' أو 'supplier' (اختياري)
        party_id:   معرف الطرف (اختياري)
        limit:      الحد الأقصى للنتائج
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        sql = """
            SELECT v.*,
                   CASE WHEN v.party_type='customer' THEN c.name ELSE s.name END AS party_name,
                   COALESCE((
                       SELECT SUM(amount) FROM invoice_payments WHERE voucher_id = v.id
                   ), 0) AS linked_amount
            FROM vouchers v
            LEFT JOIN customers c ON v.party_type='customer' AND v.party_id = c.id
            LEFT JOIN suppliers s ON v.party_type='supplier' AND v.party_id = s.id
            WHERE v.amount > COALESCE((
                       SELECT SUM(amount) FROM invoice_payments WHERE voucher_id = v.id
                   ), 0) + 0.01
        """
        params = []
        if party_type:
            sql += " AND v.party_type = ?"
            params.append(party_type)
        if party_id:
            sql += " AND v.party_id = ?"
            params.append(party_id)
        sql += " ORDER BY v.date DESC, v.id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.close()


def get_vouchers_by_party(party_type, party_id, limit=50, conn=None):
    """جلب جميع سندات طرف معين (مربوطة أو غير مربوطة)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT v.*,
                   COALESCE((
                       SELECT SUM(amount) FROM invoice_payments WHERE voucher_id = v.id
                   ), 0) AS linked_amount
            FROM vouchers v
            WHERE v.party_type = ? AND v.party_id = ?
            ORDER BY v.date DESC, v.id DESC
            LIMIT ?
        """, (party_type, party_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.close()


def get_party_invoices_with_status(party_type, party_id, only_pending=True, conn=None):
    """
    جلب فواتير طرف معين مع حالتها الحالية (المدفوع/المتبقي/الحالة).
    
    Args:
        only_pending: إذا True → فقط الفواتير غير المدفوعة بالكامل
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        if party_type == 'customer':
            type_filter = 'sale'
            id_col = 'customer_id'
        else:
            type_filter = 'purchase'
            id_col = 'supplier_id'

        sql = f"""
            SELECT id, invoice_date, type, total,
                   COALESCE(paid_amount, 0) AS paid_amount,
                   COALESCE(remaining_amount, total) AS remaining_amount,
                   COALESCE(payment_status, 'unpaid') AS payment_status,
                   currency_code
            FROM invoices
            WHERE type = ? AND {id_col} = ? AND status = 'completed'
        """
        if only_pending:
            sql += " AND COALESCE(remaining_amount, total) > 0.01"
        sql += " ORDER BY invoice_date, id"

        rows = conn.execute(sql, (type_filter, party_id)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.close()


def link_voucher_to_invoice(voucher_id, invoice_id, amount, conn=None):
    """
    ربط سند بفاتورة (يدوياً أو تلقائياً).
    
    - تُدرج صفاً في invoice_payments
    - تُحدّث invoices.paid_amount و remaining_amount و payment_status
    - تفحص أن مجموع المربوط لا يتجاوز قيمة السند نفسه
    
    Args:
        voucher_id: معرف السند (يمكن None للدفعات اليدوية بلا سند)
        invoice_id: معرف الفاتورة
        amount:     المبلغ (يجب > 0)
        conn:       اتصال خارجي (للمعاملة الواحدة)
    
    Returns:
        (True, None)          عند النجاح
        (False, "رسالة")     عند الفشل
    """
    if amount is None or float(amount) <= 0:
        return False, "المبلغ يجب أن يكون أكبر من صفر"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # 1. التحقق من الفاتورة
        inv = conn.execute(
            "SELECT id, type, total, paid_amount, remaining_amount FROM invoices WHERE id=?",
            (invoice_id,)
        ).fetchone()
        if not inv:
            if own_conn: conn.rollback()
            return False, f"الفاتورة #{invoice_id} غير موجودة"

        inv = dict(inv) if not isinstance(inv, dict) else inv
        total = float(inv.get("total") or 0)
        paid = float(inv.get("paid_amount") or 0)
        remaining = total - paid

        if float(amount) > remaining + 0.01:
            if own_conn: conn.rollback()
            return False, (
                f"المبلغ المُدخل ({float(amount):,.2f}) أكبر من المتبقي "
                f"({remaining:,.2f}) على الفاتورة #{invoice_id}"
            )

        # 2. ✅ فحص السند إن وُجد: لا يتجاوز المبلغ المتبقي من السند
        if voucher_id:
            v_row = conn.execute(
                "SELECT id, amount, account FROM vouchers WHERE id=?",
                (voucher_id,)
            ).fetchone()
            if not v_row:
                if own_conn: conn.rollback()
                return False, f"السند #{voucher_id} غير موجود"

            v_amount = float(v_row["amount"] or 0)
            linked_row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM invoice_payments WHERE voucher_id=?",
                (voucher_id,)
            ).fetchone()
            linked = float(linked_row[0]) if linked_row else 0.0
            voucher_remaining = v_amount - linked

            if float(amount) > voucher_remaining + 0.01:
                if own_conn: conn.rollback()
                return False, (
                    f"المبلغ المُدخل ({float(amount):,.2f}) أكبر من المتبقي من السند "
                    f"({voucher_remaining:,.2f})"
                )

        # 3. تحديد طريقة الدفع من السند
        payment_method = 'cash'
        if voucher_id:
            acc_code = v_row["account"]
            acc_row = conn.execute(
                "SELECT name FROM accounts WHERE code=?", (acc_code,)
            ).fetchone()
            acc_name = (acc_row["name"] if acc_row else "") or ""
            if "بنك" in acc_name:
                payment_method = 'bank'

        # 4. إدراج في invoice_payments
        conn.execute("""
            INSERT INTO invoice_payments
                (invoice_id, voucher_id, amount, payment_date, payment_method,
                 currency_code, exchange_rate, notes, created_by)
            VALUES (?, ?, ?, ?, ?, 'YER', 1.0, ?, 'system')
        """, (
            invoice_id, voucher_id, float(amount),
            date.today().strftime("%Y-%m-%d"),
            payment_method,
            f"ربط بسند #{voucher_id}" if voucher_id else "دفعة يدوية"
        ))

        # 5. تحديث الفاتورة
        new_paid = paid + float(amount)
        new_remaining = max(0.0, total - new_paid)
        if new_remaining < 0.01:
            new_status = 'paid'
        elif new_paid > 0.01:
            new_status = 'partial'
        else:
            new_status = 'unpaid'

        conn.execute("""
            UPDATE invoices
            SET paid_amount = ?, remaining_amount = ?, payment_status = ?
            WHERE id = ?
        """, (new_paid, new_remaining, new_status, invoice_id))

        if own_conn:
            conn.commit()

        return True, None

    except Exception as e:
        if own_conn:
            conn.rollback()
        return False, str(e)
    finally:
        if own_conn:
            conn.close()


# ============================================================
# ✅ دالة جديدة: إلغاء ربط دفعة (unlink)
# ============================================================
def unlink_voucher_from_invoice(payment_id, conn=None):
    """
    إلغاء ربط دفعة بفاتورة (حذف صف من invoice_payments).
    يُستخدم لتصحيح الأخطاء دون حذف السند نفسه.
    
    Args:
        payment_id: معرف صف الدفعة في invoice_payments
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # 1. جلب معلومات الدفعة
        row = conn.execute(
            "SELECT invoice_id, voucher_id, amount FROM invoice_payments WHERE id=?",
            (payment_id,)
        ).fetchone()
        if not row:
            if own_conn: conn.rollback()
            return False, f"الدفعة #{payment_id} غير موجودة"

        row = dict(row) if not isinstance(row, dict) else row
        invoice_id = row["invoice_id"]
        amount = float(row["amount"] or 0)

        # 2. حذف الدفعة
        conn.execute("DELETE FROM invoice_payments WHERE id=?", (payment_id,))

        # 3. إعادة حساب حالة الفاتورة
        inv = conn.execute(
            "SELECT total, paid_amount FROM invoices WHERE id=?",
            (invoice_id,)
        ).fetchone()
        if inv:
            inv = dict(inv) if not isinstance(inv, dict) else inv
            total = float(inv.get("total") or 0)
            old_paid = float(inv.get("paid_amount") or 0)
            new_paid = max(0.0, old_paid - amount)
            new_remaining = max(0.0, total - new_paid)

            if new_remaining < 0.01:
                new_status = 'paid'
            elif new_paid > 0.01:
                new_status = 'partial'
            else:
                new_status = 'unpaid'

            conn.execute("""
                UPDATE invoices
                SET paid_amount = ?, remaining_amount = ?, payment_status = ?
                WHERE id = ?
            """, (new_paid, new_remaining, new_status, invoice_id))

        if own_conn:
            conn.commit()
        return True, None

    except Exception as e:
        if own_conn:
            conn.rollback()
        return False, str(e)
    finally:
        if own_conn:
            conn.close()


# ============================================================
# الأرصدة والفواتير المعلقة
# ============================================================

def get_customers_with_balances():
    """جلب العملاء مع رصيدهم المستحق"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
    result = []
    for c in customers:
        row = conn.execute("""
            SELECT COALESCE(SUM(remaining_amount), 0)
            FROM invoices
            WHERE type='sale' AND customer_id=? AND status='completed'
        """, (c["id"],)).fetchone()
        balance = row[0] if row else 0.0
        result.append({"id": c["id"], "name": c["name"], "balance": balance})
    conn.close()
    return result


def get_suppliers_with_balances():
    """جلب الموردين مع رصيدهم المستحق"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    result = []
    for s in suppliers:
        row = conn.execute("""
            SELECT COALESCE(SUM(remaining_amount), 0)
            FROM invoices
            WHERE type='purchase' AND supplier_id=? AND status='completed'
        """, (s["id"],)).fetchone()
        balance = row[0] if row else 0.0
        result.append({"id": s["id"], "name": s["name"], "balance": balance})
    conn.close()
    return result


def get_invoices_for_party(party_type, party_id):
    """جلب الفواتير المعلقة للطرف (للاختيار في الواجهة)"""
    return get_party_invoices_with_status(party_type, party_id, only_pending=True)


# ============================================================
# إنشاء السندات (كما هو بدون تغيير جوهري)
# ============================================================
def create_voucher(voucher_type, party_type, party_id, amount, account,
                   invoice_id=None, reference="", notes="", created_by="admin",
                   voucher_date=None, auto_link=True, conn=None):
    """إنشاء سند قبض أو صرف مع القيد المحاسبي والربط التلقائي بالفواتير"""
    if voucher_date is None:
        voucher_date = date.today().strftime("%Y-%m-%d")

    if not amount or float(amount) <= 0:
        return None, "المبلغ يجب أن يكون أكبر من صفر"

    create_vouchers_table()

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # 1. إدراج السند
        cur = conn.execute("""
            INSERT INTO vouchers (type, date, party_type, party_id, amount, account,
                                 invoice_id, reference, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (voucher_type, voucher_date, party_type, party_id, float(amount), account,
              invoice_id, reference, notes, created_by))
        voucher_id = cur.lastrowid

        # 2. جلب اسم الطرف
        if party_type == 'customer':
            row = conn.execute("SELECT name FROM customers WHERE id=?", (party_id,)).fetchone()
        else:
            row = conn.execute("SELECT name FROM suppliers WHERE id=?", (party_id,)).fetchone()
        party_name = row["name"] if row else "غير معروف"

        # 3. القيد المحاسبي
        customers_account = get_functional_account("accounts_receivable")
        suppliers_account = get_functional_account("accounts_payable")

        if voucher_type == 'receipt':
            lines = [
                {"account": account, "debit": float(amount), "credit": 0},
                {"account": customers_account, "debit": 0, "credit": float(amount)}
            ]
        else:
            lines = [
                {"account": suppliers_account, "debit": float(amount), "credit": 0},
                {"account": account, "debit": 0, "credit": float(amount)}
            ]

        desc = f"سند {'قبض' if voucher_type == 'receipt' else 'صرف'} #{voucher_id} - {party_name}"
        if invoice_id:
            desc += f" (فاتورة #{invoice_id})"

        entry_id, error = save_journal_entry(
            description=desc,
            lines=lines,
            entry_date=voucher_date,
            conn=conn
        )
        if error:
            raise Exception(f"فشل القيد المحاسبي: {error}")

        conn.execute("UPDATE vouchers SET journal_entry_id=? WHERE id=?",
                    (entry_id, voucher_id))

        # 4. ربط السند بالصندوق
        try:
            from services.cash_service import add_cash_transaction, get_all_cash_accounts
            cash_accounts = get_all_cash_accounts(active_only=True)

            row_acc = conn.execute("SELECT name FROM accounts WHERE code=?", (account,)).fetchone()
            acc_name = row_acc["name"] if row_acc else ""
            cash_account_code = get_functional_account("cash")
            is_cash = ("صندوق" in acc_name) or (account == cash_account_code)

            cash_acc = None
            if is_cash and cash_accounts:
                for ca in cash_accounts:
                    if ca.get('account_code') == account:
                        cash_acc = ca
                        break
                if cash_acc is None:
                    for ca in cash_accounts:
                        if ca.get('account_code') == cash_account_code:
                            cash_acc = ca
                            break
                if cash_acc is None:
                    cash_acc = cash_accounts[0]

            if cash_acc and float(amount) > 0:
                trans_type = "deposit" if voucher_type == "receipt" else "withdrawal"
                ok, msg = add_cash_transaction(
                    cash_acc['id'],
                    voucher_date,
                    f"سند {'قبض' if voucher_type == 'receipt' else 'صرف'} #{voucher_id} - {party_name}",
                    trans_type,
                    float(amount),
                    reference=f"voucher#{voucher_id}",
                    create_journal=False,
                    voucher_id=voucher_id,
                    conn=conn
                )
                if not ok:
                    print(f"⚠️ فشل ربط السند بالصندوق: {msg}")
        except Exception as e:
            print(f"⚠️ خطأ ربط السند بالصندوق: {e}")

        # 5. الربط التلقائي بالفاتورة
        if invoice_id and auto_link:
            ok, err = link_voucher_to_invoice(
                voucher_id=voucher_id,
                invoice_id=invoice_id,
                amount=float(amount),
                conn=conn
            )
            if not ok:
                raise Exception(f"فشل ربط السند بالفاتورة: {err}")

        if own_conn:
            conn.commit()

        log_action(
            username=created_by,
            action=f"سند {'قبض' if voucher_type == 'receipt' else 'صرف'}",
            table_name="vouchers",
            record_id=voucher_id,
            new_value=f"{party_name}, المبلغ: {float(amount):,.2f}, {account}"
        )

        return voucher_id, None

    except Exception as e:
        if own_conn:
            conn.rollback()
        return None, str(e)
    finally:
        if own_conn:
            conn.close()


# ============================================================
# العرض والتفاصيل
# ============================================================

def get_vouchers(limit=50):
    """سجل السندات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    vouchers = conn.execute("""
        SELECT v.*,
               CASE WHEN v.party_type='customer' THEN c.name ELSE s.name END as party_name,
               COALESCE((
                   SELECT SUM(amount) FROM invoice_payments WHERE voucher_id = v.id
               ), 0) AS linked_amount
        FROM vouchers v
        LEFT JOIN customers c ON v.party_type='customer' AND v.party_id = c.id
        LEFT JOIN suppliers s ON v.party_type='supplier' AND v.party_id = s.id
        ORDER BY v.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(v) for v in vouchers]


def get_voucher_details(voucher_id):
    """تفاصيل سند مع القيد + الدفعات المرتبطة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    voucher = conn.execute("""
        SELECT v.*,
               CASE WHEN v.party_type='customer' THEN c.name ELSE s.name END as party_name
        FROM vouchers v
        LEFT JOIN customers c ON v.party_type='customer' AND v.party_id = c.id
        LEFT JOIN suppliers s ON v.party_type='supplier' AND v.party_id = s.id
        WHERE v.id = ?
    """, (voucher_id,)).fetchone()

    if not voucher:
        conn.close()
        return None

    voucher = dict(voucher)

    # القيد
    entry_id = voucher.get("journal_entry_id")
    if entry_id:
        lines = conn.execute(
            "SELECT account_name, debit, credit FROM journal_lines WHERE entry_id=?",
            (entry_id,)
        ).fetchall()
        voucher["lines"] = [dict(l) for l in lines]

    # ✅ الدفعات المرتبطة (invoice_payments)
    payments = conn.execute("""
        SELECT ip.*, i.type AS invoice_type, i.invoice_date AS invoice_date
        FROM invoice_payments ip
        LEFT JOIN invoices i ON ip.invoice_id = i.id
        WHERE ip.voucher_id = ?
        ORDER BY ip.id
    """, (voucher_id,)).fetchall()
    voucher["linked_payments"] = [dict(p) for p in payments]

    # ✅ المبلغ المربوط والمتبقي من السند
    linked_total = sum(float(p["amount"] or 0) for p in voucher["linked_payments"])
    voucher["linked_amount"] = linked_total
    voucher["unlinked_amount"] = max(0.0, float(voucher["amount"] or 0) - linked_total)

    conn.close()
    return voucher
