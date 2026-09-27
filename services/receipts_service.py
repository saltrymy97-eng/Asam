# services/receipts_service.py – سندات القبض والصرف الاحترافية (v5.0)
# ✅ فحص الرصيد قبل سند الصرف
# ✅ متوافق مع Connection Registry
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.accounting_service import save_journal_entry
from services.chart_service import get_functional_account


# ============================================================
# إنشاء الجداول
# ============================================================
def create_vouchers_table(conn=None):
    """إنشاء جدول السندات إذا لم يكن موجوداً"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


def get_cash_accounts(conn=None):
    """جلب حسابات النقدية (المستوى الثاني تحت الأصول)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        accounts = conn.execute("""
            SELECT code, name FROM accounts
            WHERE parent_id = (SELECT id FROM accounts WHERE code = '1')
            ORDER BY code
        """).fetchall()
        if not accounts:
            return [{"code": "صندوق", "name": "صندوق"}, {"code": "بنك", "name": "بنك"}]
        return [{"code": a["code"], "name": a["name"]} for a in accounts]
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# ✅ الربط اليدوي وإدارة العلاقات
# ============================================================

def get_voucher_linked_amount(voucher_id, conn=None):
    """حساب المبلغ الإجمالي الذي تم ربطه من هذا السند"""
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
            close_connection(conn)


def get_unlinked_vouchers(party_type=None, party_id=None, limit=100, conn=None):
    """جلب السندات غير المربوطة بالكامل"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
            close_connection(conn)


def get_vouchers_by_party(party_type, party_id, limit=50, conn=None):
    """جلب جميع سندات طرف معين"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
            close_connection(conn)


def get_party_invoices_with_status(party_type, party_id, only_pending=True, conn=None):
    """جلب فواتير طرف معين مع حالتها الحالية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
            close_connection(conn)


def link_voucher_to_invoice(voucher_id, invoice_id, amount, conn=None):
    """ربط سند بفاتورة (يدوياً أو تلقائياً)"""
    if amount is None or float(amount) <= 0:
        return False, "المبلغ يجب أن يكون أكبر من صفر"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

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

        v_row = None
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

        payment_method = 'cash'
        if voucher_id and v_row:
            acc_code = v_row["account"]
            acc_row = conn.execute(
                "SELECT name FROM accounts WHERE code=?", (acc_code,)
            ).fetchone()
            acc_name = (acc_row["name"] if acc_row else "") or ""
            if "بنك" in acc_name:
                payment_method = 'bank'

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
            try: conn.rollback()
            except Exception: pass
        return False, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def unlink_voucher_from_invoice(payment_id, conn=None):
    """إلغاء ربط دفعة بفاتورة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

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

        conn.execute("DELETE FROM invoice_payments WHERE id=?", (payment_id,))

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
            try: conn.rollback()
            except Exception: pass
        return False, str(e)
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# الأرصدة والفواتير المعلقة
# ============================================================

def get_customers_with_balances(conn=None):
    """جلب العملاء مع رصيدهم المستحق"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        return result
    finally:
        if own_conn:
            close_connection(conn)


def get_suppliers_with_balances(conn=None):
    """جلب الموردين مع رصيدهم المستحق"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        return result
    finally:
        if own_conn:
            close_connection(conn)


def get_invoices_for_party(party_type, party_id):
    return get_party_invoices_with_status(party_type, party_id, only_pending=True)


# ============================================================
# ✅ إنشاء السندات — مع حماية الرصيد
# ============================================================
def create_voucher(voucher_type, party_type, party_id, amount, account,
                   invoice_id=None, reference="", notes="", created_by="admin",
                   voucher_date=None, auto_link=True, conn=None):
    """
    إنشاء سند قبض أو صرف — كل العمليات من نفس الاتصال.
    
    ✅ جديد: فحص الرصيد قبل سند الصرف (payment).
    """
    if voucher_date is None:
        voucher_date = date.today().strftime("%Y-%m-%d")

    if not amount or float(amount) <= 0:
        return None, "المبلغ يجب أن يكون أكبر من صفر"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # ============================================================
        # ✅ جديد: فحص الرصيد قبل سند الصرف
        # ============================================================
        if voucher_type == 'payment':
            from services.cash_service import check_sufficient_balance
            ok, err = check_sufficient_balance(account, float(amount), conn=conn)
            if not ok:
                if own_conn:
                    conn.rollback()
                return None, f"لا يمكن إنشاء سند الصرف: {err}"

        # إنشاء الجدول من نفس الاتصال
        try:
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
        except Exception:
            pass

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

        # 3. قراءة الحسابات الوظيفية من نفس الاتصال
        def _read_functional_account(functional_type):
            r = conn.execute(
                "SELECT code FROM accounts WHERE functional_type = ? AND is_active = 1 LIMIT 1",
                (functional_type,)
            ).fetchone()
            if r:
                return r["code"]
            return get_functional_account(functional_type)

        customers_account = _read_functional_account("accounts_receivable")
        suppliers_account = _read_functional_account("accounts_payable")

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

        # 4. ربط السند بالصندوق — من نفس الاتصال
        try:
            from services.cash_service import add_cash_transaction

            _rows = conn.execute(
                "SELECT * FROM cash_accounts WHERE is_active = 1 ORDER BY name"
            ).fetchall()
            cash_accounts = [dict(r) for r in _rows]

            row_acc = conn.execute("SELECT name FROM accounts WHERE code=?", (account,)).fetchone()
            acc_name = row_acc["name"] if row_acc else ""

            cash_row = conn.execute(
                "SELECT code FROM accounts WHERE functional_type = 'cash' AND is_active = 1 LIMIT 1"
            ).fetchone()
            cash_account_code = cash_row["code"] if cash_row else None

            is_cash = ("صندوق" in acc_name) or (account == cash_account_code)

            cash_acc = None
            if is_cash and cash_accounts:
                for ca in cash_accounts:
                    if ca.get('account_code') == account:
                        cash_acc = ca
                        break
                if cash_acc is None and cash_account_code:
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
                    conn=conn,
                    skip_balance_check=True  # ✅ تخطي الفحص (تم قبل الإدراج)
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
            try: conn.rollback()
            except Exception: pass
        return None, str(e)
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# العرض والتفاصيل
# ============================================================

def get_vouchers(limit=50):
    conn = get_connection()
    try:
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
        return [dict(v) for v in vouchers]
    finally:
        close_connection(conn)


def get_voucher_details(voucher_id):
    conn = get_connection()
    try:
        voucher = conn.execute("""
            SELECT v.*,
                   CASE WHEN v.party_type='customer' THEN c.name ELSE s.name END as party_name
            FROM vouchers v
            LEFT JOIN customers c ON v.party_type='customer' AND v.party_id = c.id
            LEFT JOIN suppliers s ON v.party_type='supplier' AND v.party_id = s.id
            WHERE v.id = ?
        """, (voucher_id,)).fetchone()

        if not voucher:
            return None

        voucher = dict(voucher)

        entry_id = voucher.get("journal_entry_id")
        if entry_id:
            lines = conn.execute(
                "SELECT account_name, debit, credit FROM journal_lines WHERE entry_id=?",
                (entry_id,)
            ).fetchall()
            voucher["lines"] = [dict(l) for l in lines]

        payments = conn.execute("""
            SELECT ip.*, i.type AS invoice_type, i.invoice_date AS invoice_date
            FROM invoice_payments ip
            LEFT JOIN invoices i ON ip.invoice_id = i.id
            WHERE ip.voucher_id = ?
            ORDER BY ip.id
        """, (voucher_id,)).fetchall()
        voucher["linked_payments"] = [dict(p) for p in payments]

        linked_total = sum(float(p["amount"] or 0) for p in voucher["linked_payments"])
        voucher["linked_amount"] = linked_total
        voucher["unlinked_amount"] = max(0.0, float(voucher["amount"] or 0) - linked_total)

        return voucher
    finally:
        close_connection(conn)
