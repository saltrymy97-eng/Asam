# services/bank_service.py – منطق التعاملات البنكية (مع إدارة العمليات ودعم العملات)
import sqlite3
from datetime import date, datetime
import database
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount

def get_conn():
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    return conn

# ===================== إدارة الحسابات البنكية =====================

def create_bank_account(bank_name, account_number, account_name="", currency_code="YER", opening_balance=0.0):
    """إضافة حساب بنكي جديد"""
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO bank_accounts (bank_name, account_number, account_name, currency_code, opening_balance, current_balance)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (bank_name, account_number, account_name, currency_code, opening_balance, opening_balance)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_bank_account(account_id, bank_name=None, account_number=None, account_name=None, currency_code=None, is_active=None):
    """تحديث بيانات حساب بنكي"""
    conn = get_conn()
    fields = []
    values = []
    if bank_name: fields.append("bank_name = ?"); values.append(bank_name)
    if account_number: fields.append("account_number = ?"); values.append(account_number)
    if account_name: fields.append("account_name = ?"); values.append(account_name)
    if currency_code: fields.append("currency_code = ?"); values.append(currency_code)
    if is_active is not None: fields.append("is_active = ?"); values.append(1 if is_active else 0)
    if not fields: return
    try:
        conn.execute("BEGIN")
        values.append(account_id)
        conn.execute(f"UPDATE bank_accounts SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_bank_accounts(active_only=True):
    """جلب جميع الحسابات البنكية"""
    conn = get_conn()
    query = "SELECT * FROM bank_accounts"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY bank_name"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_bank_account_by_id(account_id):
    """جلب حساب بنكي محدد"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM bank_accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_bank_balance(account_id):
    """تحديث الرصيد الحالي للحساب بناءً على الحركات المسجلة"""
    conn = get_conn()
    try:
        deposits = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE bank_account_id = ? AND type = 'deposit'",
            (account_id,)
        ).fetchone()[0]
        withdrawals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE bank_account_id = ? AND type = 'withdrawal'",
            (account_id,)
        ).fetchone()[0]
        transfers_in = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE bank_account_id = ? AND type = 'transfer_in'",
            (account_id,)
        ).fetchone()[0]
        transfers_out = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE bank_account_id = ? AND type = 'transfer_out'",
            (account_id,)
        ).fetchone()[0]
        
        account = get_bank_account_by_id(account_id)
        if not account:
            return 0.0
        
        current_balance = account['opening_balance'] + deposits + transfers_in - withdrawals - transfers_out
        
        conn.execute("BEGIN")
        conn.execute("UPDATE bank_accounts SET current_balance = ? WHERE id = ?", (current_balance, account_id))
        conn.commit()
        return current_balance
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ===================== الحركات البنكية =====================

def add_bank_transaction(bank_account_id, transaction_date, description, trans_type, amount, reference=""):
    """إضافة حركة بنكية (إيداع، سحب، تحويل) مع تحديث الرصيد"""
    if trans_type not in ('deposit', 'withdrawal', 'transfer_in', 'transfer_out'):
        raise ValueError("نوع الحركة غير صالح")
    
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO bank_transactions (bank_account_id, transaction_date, description, type, amount, reference)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (bank_account_id, transaction_date, description, trans_type, amount, reference)
        )
        conn.commit()
        
        # تحديث الرصيد بعد إضافة الحركة
        update_bank_balance(bank_account_id)
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_bank_transactions(bank_account_id=None, limit=50):
    """جلب الحركات البنكية (لحساب معين أو للكل)"""
    conn = get_conn()
    if bank_account_id:
        rows = conn.execute(
            """SELECT bt.*, ba.bank_name, ba.account_number
               FROM bank_transactions bt
               JOIN bank_accounts ba ON bt.bank_account_id = ba.id
               WHERE bt.bank_account_id = ?
               ORDER BY bt.transaction_date DESC, bt.id DESC
               LIMIT ?""",
            (bank_account_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT bt.*, ba.bank_name, ba.account_number
               FROM bank_transactions bt
               JOIN bank_accounts ba ON bt.bank_account_id = ba.id
               ORDER BY bt.transaction_date DESC, bt.id DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reconcile_transaction(transaction_id, journal_line_id=None):
    """تسوية حركة بنكية (ربطها بقيد محاسبي)"""
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        if journal_line_id:
            conn.execute(
                "UPDATE bank_transactions SET reconciled = 1, journal_line_id = ? WHERE id = ?",
                (journal_line_id, transaction_id)
            )
        else:
            conn.execute(
                "UPDATE bank_transactions SET reconciled = 1 WHERE id = ?",
                (transaction_id,)
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_unreconciled_transactions(bank_account_id):
    """جلب الحركات غير المسواة لحساب معين"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM bank_transactions
           WHERE bank_account_id = ? AND reconciled = 0
           ORDER BY transaction_date""",
        (bank_account_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===================== المصالحة البنكية =====================

def create_bank_reconciliation(bank_account_id, reconciliation_date, statement_balance):
    """إنشاء تسوية بنكية جديدة"""
    conn = get_conn()
    try:
        # حساب رصيد الدفاتر الحالي
        account = get_bank_account_by_id(bank_account_id)
        if not account:
            raise ValueError("الحساب البنكي غير موجود")
        
        book_balance = account['current_balance']
        difference = statement_balance - book_balance
        
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO bank_reconciliations (bank_account_id, reconciliation_date, statement_balance, book_balance, difference, status)
               VALUES (?, ?, ?, ?, ?, 'completed')""",
            (bank_account_id, reconciliation_date, statement_balance, book_balance, difference)
        )
        conn.commit()
        return True, difference
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_reconciliation_history(bank_account_id=None):
    """جلب سجل المصالحات البنكية"""
    conn = get_conn()
    if bank_account_id:
        rows = conn.execute(
            """SELECT br.*, ba.bank_name, ba.account_number
               FROM bank_reconciliations br
               JOIN bank_accounts ba ON br.bank_account_id = ba.id
               WHERE br.bank_account_id = ?
               ORDER BY br.reconciliation_date DESC""",
            (bank_account_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT br.*, ba.bank_name, ba.account_number
               FROM bank_reconciliations br
               JOIN bank_accounts ba ON br.bank_account_id = ba.id
               ORDER BY br.reconciliation_date DESC"""
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===================== دوال مساعدة =====================

def get_bank_balance_summary():
    """ملخص أرصدة جميع الحسابات البنكية النشطة"""
    accounts = get_all_bank_accounts(active_only=True)
    summary = []
    total_balance_base = 0.0
    base_currency = get_base_currency()
    base_code = base_currency['code'] if base_currency else 'YER'
    
    for acc in accounts:
        balance = acc['current_balance']
        currency = acc['currency_code']
        # تحويل إلى العملة الأساسية إذا لزم
        if currency != base_code:
            try:
                balance_base = convert_amount(balance, currency, base_code)
            except:
                balance_base = balance
        else:
            balance_base = balance
        
        summary.append({
            'bank_name': acc['bank_name'],
            'account_number': acc['account_number'],
            'currency': currency,
            'balance': balance,
            'balance_base': balance_base
        })
        total_balance_base += balance_base
    
    return summary, total_balance_base
