# services/cash_service.py – وحدة الصندوق متعدد العملات (v3.0)
# ✅ متوافق مع Connection Registry — لا يُغلق الاتصال
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


# ============================================================
# ✅ مساعد: قراءة الحساب الوظيفي من نفس الاتصال (بدون اتصال جديد)
# ============================================================
def _read_functional_code(conn, functional_type):
    """قراءة كود الحساب الوظيفي من نفس الاتصال"""
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


def create_cash_tables():
    """إنشاء جداول الصندوق إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cash_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            currency_code TEXT NOT NULL DEFAULT 'YER',
            opening_balance REAL DEFAULT 0.0,
            current_balance REAL DEFAULT 0.0,
            account_code TEXT,
            is_active INTEGER DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cash_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash_account_id INTEGER NOT NULL,
            transaction_date TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL CHECK(type IN ('deposit','withdrawal')),
            amount REAL NOT NULL CHECK(amount > 0),
            reference TEXT,
            journal_id INTEGER,
            journal_line_id INTEGER,
            voucher_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cash_account_id) REFERENCES cash_accounts(id)
        )
    """)
    conn.commit()
    close_connection(conn)


# ========== إدارة حسابات الصندوق ==========

def create_cash_account(name, currency_code="YER", opening_balance=0.0, account_code=None):
    """إنشاء حساب صندوق جديد مع ربطه بشجرة الحسابات"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        # ✅ قراءة الحساب الوظيفي من نفس الاتصال
        if account_code:
            final_account_code = account_code
        else:
            final_account_code = _read_functional_code(conn, "cash")

        conn.execute(
            """INSERT INTO cash_accounts (name, currency_code, opening_balance, current_balance, account_code) 
               VALUES (?, ?, ?, ?, ?)""",
            (name, currency_code, opening_balance, opening_balance, final_account_code)
        )
        conn.commit()
        return True, "تم إنشاء حساب الصندوق بنجاح"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        close_connection(conn)


def get_all_cash_accounts(active_only=True, conn=None):
    """جلب جميع حسابات الصندوق (يدعم conn خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        query = "SELECT * FROM cash_accounts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        accounts = conn.execute(query).fetchall()
        return [dict(a) for a in accounts]
    finally:
        if own_conn:
            close_connection(conn)


def get_cash_account_by_id(account_id, conn=None):
    """جلب حساب صندوق محدد (يدعم conn خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        account = conn.execute(
            "SELECT * FROM cash_accounts WHERE id=?", (account_id,)
        ).fetchone()
        return dict(account) if account else None
    finally:
        if own_conn:
            close_connection(conn)


def update_cash_balance(account_id, conn=None):
    """تحديث رصيد الصندوق (يدعم conn خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        deposits = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM cash_transactions "
            "WHERE cash_account_id=? AND type='deposit'",
            (account_id,)
        ).fetchone()[0]
        withdrawals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM cash_transactions "
            "WHERE cash_account_id=? AND type='withdrawal'",
            (account_id,)
        ).fetchone()[0]

        account = get_cash_account_by_id(account_id, conn=conn)
        if not account:
            return 0.0

        current_balance = account['opening_balance'] + deposits - withdrawals

        conn.execute(
            "UPDATE cash_accounts SET current_balance=? WHERE id=?",
            (current_balance, account_id)
        )
        if own_conn:
            conn.commit()
        return current_balance
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


# ========== حركات الصندوق ==========

def add_cash_transaction(
    cash_account_id,
    transaction_date,
    description,
    trans_type,
    amount,
    reference="",
    contra_account_code=None,
    create_journal=True,
    journal_line_id=None,
    voucher_id=None,
    conn=None
):
    """إضافة حركة صندوق مع قيد محاسبي تلقائي"""
    if trans_type not in ('deposit', 'withdrawal'):
        return False, "نوع الحركة غير صالح"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        account = get_cash_account_by_id(cash_account_id, conn=conn)
        if not account:
            if own_conn:
                conn.rollback()
            return False, "حساب الصندوق غير موجود"

        cash_code = account.get('account_code') or _read_functional_code(conn, "cash")
        currency = account.get('currency_code', 'YER')

        base_currency = get_base_currency()
        if currency == base_currency['code']:
            exchange_rate = 1.0
        else:
            exchange_rate = get_exchange_rate(currency, base_currency['code']) or 1.0

        journal_id = None

        if create_journal:
            target_contra_code = contra_account_code or _read_functional_code(conn, "bank")
            lines = []

            if trans_type == 'deposit':
                lines.append({
                    "account": cash_code,
                    "debit": amount,
                    "credit": 0.0,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })
                lines.append({
                    "account": target_contra_code,
                    "debit": 0.0,
                    "credit": amount,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })
            else:
                lines.append({
                    "account": target_contra_code,
                    "debit": amount,
                    "credit": 0.0,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })
                lines.append({
                    "account": cash_code,
                    "debit": 0.0,
                    "credit": amount,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })

            _journal_result = save_journal_entry(
                entry_date=transaction_date,
                description=f"{description} ({reference})".strip(),
                lines=lines,
                conn=conn
            )

            if isinstance(_journal_result, tuple):
                journal_id, jerr = _journal_result[0], _journal_result[1] if len(_journal_result) > 1 else None
                if jerr:
                    if own_conn:
                        conn.rollback()
                    return False, f"فشل القيد المحاسبي: {jerr}"
            else:
                journal_id = _journal_result

        conn.execute(
            """INSERT INTO cash_transactions 
               (cash_account_id, transaction_date, description, type, amount, 
                reference, journal_id, journal_line_id, voucher_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cash_account_id, transaction_date, description, trans_type,
             amount, reference, journal_id, journal_line_id, voucher_id)
        )

        new_balance = update_cash_balance(cash_account_id, conn=conn)

        if own_conn:
            conn.commit()

        log_action(
            username="admin",
            action=f"{'إيداع' if trans_type == 'deposit' else 'سحب'} صندوق",
            table_name="cash_transactions",
            new_value=f"صندوق: {account['name']}, المبلغ: {amount:,.2f} {account['currency_code']}, "
                      f"الرصيد الجديد: {new_balance:,.2f}"
        )

        return True, f"تمت الحركة بنجاح. الرصيد الحالي: {new_balance:,.2f}"

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def transfer_between_cashes(from_account_id, to_account_id, amount, transfer_date,
                             description="تحويل بين الصناديق", reference=""):
    """تحويل بين صندوقين"""
    conn = get_connection()
    try:
        from_acc = get_cash_account_by_id(from_account_id, conn=conn)
        to_acc = get_cash_account_by_id(to_account_id, conn=conn)

        if not from_acc or not to_acc:
            return False, "أحد حسابات الصندوق غير موجود"

        from_code = from_acc.get('account_code') or _read_functional_code(conn, "cash")
        to_code = to_acc.get('account_code') or _read_functional_code(conn, "cash")

        from_curr = from_acc.get('currency_code', 'YER')
        to_curr = to_acc.get('currency_code', 'YER')

        from_rate = get_exchange_rate(from_curr)
        to_rate = get_exchange_rate(to_curr)

        base_amount = amount * from_rate
        converted_to_amount = base_amount / to_rate if to_rate else amount

        lines = [
            {
                "account": to_code,
                "debit": converted_to_amount,
                "credit": 0.0,
                "currency_code": to_curr,
                "exchange_rate": to_rate
            },
            {
                "account": from_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": from_curr,
                "exchange_rate": from_rate
            }
        ]

        result = save_journal_entry(
            entry_date=transfer_date,
            description=f"{description} من {from_acc['name']} إلى {to_acc['name']}",
            lines=lines,
            conn=conn
        )
        if isinstance(result, tuple):
            journal_id = result[0]
        else:
            journal_id = result

        add_cash_transaction(from_account_id, transfer_date, f"تحويل إلى {to_acc['name']}",
                             'withdrawal', amount, reference, create_journal=False,
                             conn=conn)
        add_cash_transaction(to_account_id, transfer_date, f"تحويل من {from_acc['name']}",
                             'deposit', converted_to_amount, reference, create_journal=False,
                             conn=conn)

        return True, f"تم التحويل بنجاح برقم قيد: {journal_id}"
    except Exception as e:
        return False, str(e)
    finally:
        close_connection(conn)


def get_cash_transactions(cash_account_id=None, limit=50):
    """جلب حركات الصندوق"""
    conn = get_connection()
    try:
        if cash_account_id:
            rows = conn.execute(
                """SELECT ct.*, ca.name as account_name, ca.currency_code 
                   FROM cash_transactions ct 
                   JOIN cash_accounts ca ON ct.cash_account_id = ca.id 
                   WHERE ct.cash_account_id = ? 
                   ORDER BY ct.transaction_date DESC, ct.id DESC LIMIT ?""",
                (cash_account_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ct.*, ca.name as account_name, ca.currency_code 
                   FROM cash_transactions ct 
                   JOIN cash_accounts ca ON ct.cash_account_id = ca.id 
                   ORDER BY ct.transaction_date DESC, ct.id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        close_connection(conn)


# ========== التقارير ==========

def get_cash_balance_summary():
    """ملخص أرصدة جميع صناديق النقدية"""
    accounts = get_all_cash_accounts(active_only=True)
    summary = []
    total_balance_base = 0.0
    base_currency = get_base_currency()
    base_code = base_currency['code'] if base_currency else 'YER'

    for acc in accounts:
        balance = acc['current_balance']
        currency = acc['currency_code']
        if currency != base_code:
            try:
                balance_base = convert_amount(balance, currency, base_code)
            except Exception:
                balance_base = balance
        else:
            balance_base = balance

        summary.append({
            'id': acc['id'],
            'name': acc['name'],
            'currency': currency,
            'balance': balance,
            'balance_base': balance_base
        })
        total_balance_base += balance_base

    return summary, total_balance_base


def get_cash_statement(cash_account_id, from_date, to_date):
    """كشف حساب الصندوق لفترة محددة"""
    conn = get_connection()
    try:
        account = get_cash_account_by_id(cash_account_id, conn=conn)
        if not account:
            return None, "الحساب غير موجود"

        balance_before = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN type='deposit' THEN amount ELSE -amount END), 0) "
            "FROM cash_transactions WHERE cash_account_id=? AND transaction_date < ?",
            (cash_account_id, from_date)
        ).fetchone()[0]
        opening = account['opening_balance'] + balance_before

        transactions = conn.execute(
            "SELECT * FROM cash_transactions WHERE cash_account_id=? AND transaction_date BETWEEN ? AND ? "
            "ORDER BY transaction_date, id",
            (cash_account_id, from_date, to_date)
        ).fetchall()

        period_movement = sum(t['amount'] if t['type'] == 'deposit' else -t['amount']
                              for t in transactions)
        closing = opening + period_movement

        return {
            'account': account,
            'from_date': from_date,
            'to_date': to_date,
            'opening_balance': opening,
            'transactions': [dict(t) for t in transactions],
            'closing_balance': closing
        }, None
    finally:
        close_connection(conn)
