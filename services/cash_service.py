# services/cash_service.py – وحدة الصندوق متعدد العملات والقيود الآلية (احترافي)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cash_account_id) REFERENCES cash_accounts(id)
        )
    """)
    conn.commit()
    conn.close()

# ========== إدارة حسابات الصندوق ==========

def create_cash_account(name, currency_code="YER", opening_balance=0.0, account_code=None):
    """إنشاء حساب صندوق جديد مع ربطه بشجرة الحسابات"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        final_account_code = account_code or get_functional_account("cash")
        conn.execute(
            """INSERT INTO cash_accounts (name, currency_code, opening_balance, current_balance, account_code) 
               VALUES (?, ?, ?, ?, ?)""",
            (name, currency_code, opening_balance, opening_balance, final_account_code)
        )
        conn.commit()
        return True, "تم إنشاء حساب الصندوق بنجاح"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_all_cash_accounts(active_only=True):
    """جلب جميع حسابات الصندوق"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM cash_accounts"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name"
    accounts = conn.execute(query).fetchall()
    conn.close()
    return [dict(a) for a in accounts]

def get_cash_account_by_id(account_id):
    """جلب حساب صندوق محدد"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    account = conn.execute("SELECT * FROM cash_accounts WHERE id=?", (account_id,)).fetchone()
    conn.close()
    return dict(account) if account else None

def update_cash_balance(account_id):
    """تحديث رصيد الصندوق بناءً على الحركات المسجلة"""
    conn = get_connection()
    try:
        deposits = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM cash_transactions WHERE cash_account_id=? AND type='deposit'",
            (account_id,)
        ).fetchone()[0]
        withdrawals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM cash_transactions WHERE cash_account_id=? AND type='withdrawal'",
            (account_id,)
        ).fetchone()[0]

        account = get_cash_account_by_id(account_id)
        if not account:
            return 0.0

        current_balance = account['opening_balance'] + deposits - withdrawals

        conn.execute("BEGIN")
        conn.execute("UPDATE cash_accounts SET current_balance=? WHERE id=?", (current_balance, account_id))
        conn.commit()
        return current_balance
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ========== حركات الصندوق والقيود الآلية ==========

def add_cash_transaction(cash_account_id, transaction_date, description, trans_type, amount, reference="", contra_account_code=None, create_journal=True, journal_line_id=None):
    """إضافة حركة صندوق (إيداع/سحب) مع إنشاء قيد محاسبي تلقائي وتحديث الرصيد"""
    if trans_type not in ('deposit', 'withdrawal'):
        return False, "نوع الحركة غير صالح"

    account = get_cash_account_by_id(cash_account_id)
    if not account:
        return False, "حساب الصندوق غير موجود"

    cash_code = account.get('account_code') or get_functional_account("cash")
    currency = account.get('currency_code', 'YER')
    exchange_rate = get_exchange_rate(currency)
    journal_id = None

    if create_journal:
        target_contra_code = contra_account_code or get_functional_account("bank")
        lines = []

        if trans_type == 'deposit':
            # إيداع: الصندوق مدين، والحساب المقابل دائن
            lines.append({
                "account_name": cash_code,
                "debit": amount,
                "credit": 0.0,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })
            lines.append({
                "account_name": target_contra_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })
        else:
            # سحب: الحساب المقابل مدين، والصندوق دائن
            lines.append({
                "account_name": target_contra_code,
                "debit": amount,
                "credit": 0.0,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })
            lines.append({
                "account_name": cash_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })

        journal_id = save_journal_entry(
            entry_date=transaction_date,
            description=f"{description} ({reference})".strip(),
            lines=lines
        )

    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO cash_transactions 
               (cash_account_id, transaction_date, description, type, amount, reference, journal_id, journal_line_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (cash_account_id, transaction_date, description, trans_type, amount, reference, journal_id, journal_line_id)
        )
        conn.commit()

        # تحديث الرصيد
        new_balance = update_cash_balance(cash_account_id)

        # تسجيل العملية في سجل التدقيق
        log_action(
            username="admin",
            action=f"{'إيداع' if trans_type == 'deposit' else 'سحب'} صندوق",
            table_name="cash_transactions",
            new_value=f"صندوق: {account['name']}, المبلغ: {amount:,.2f} {account['currency_code']}, الرصيد الجديد: {new_balance:,.2f}"
        )

        return True, f"تمت الحركة بنجاح. الرصيد الحالي: {new_balance:,.2f}"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def transfer_between_cashes(from_account_id, to_account_id, amount, transfer_date, description="تحويل بين الصناديق", reference=""):
    """تحويل مالي بين صندوقين أو بين صندوق وحساب آخر"""
    from_acc = get_cash_account_by_id(from_account_id)
    to_acc = get_cash_account_by_id(to_account_id)

    if not from_acc or not to_acc:
        return False, "أحد حسابات الصندوق غير موجود"

    from_code = from_acc.get('account_code') or get_functional_account("cash")
    to_code = to_acc.get('account_code') or get_functional_account("cash")

    from_curr = from_acc.get('currency_code', 'YER')
    to_curr = to_acc.get('currency_code', 'YER')

    from_rate = get_exchange_rate(from_curr)
    to_rate = get_exchange_rate(to_curr)

    base_amount = amount * from_rate
    converted_to_amount = base_amount / to_rate if to_rate else amount

    lines = [
        {
            "account_name": to_code,
            "debit": converted_to_amount,
            "credit": 0.0,
            "currency_code": to_curr,
            "exchange_rate": to_rate
        },
        {
            "account_name": from_code,
            "debit": 0.0,
            "credit": amount,
            "currency_code": from_curr,
            "exchange_rate": from_rate
        }
    ]

    journal_id = save_journal_entry(
        entry_date=transfer_date,
        description=f"{description} من {from_acc['name']} إلى {to_acc['name']}",
        lines=lines
    )

    add_cash_transaction(from_account_id, transfer_date, f"تحويل إلى {to_acc['name']}", 'withdrawal', amount, reference, create_journal=False)
    add_cash_transaction(to_account_id, transfer_date, f"تحويل من {from_acc['name']}", 'deposit', converted_to_amount, reference, create_journal=False)

    return True, f"تم التحويل بنجاح برقم قيد: {journal_id}"

def get_cash_transactions(cash_account_id=None, limit=50):
    """جلب حركات الصندوق"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
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
    conn.close()
    return [dict(r) for r in rows]

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
            except:
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
    conn.row_factory = sqlite3.Row
    account = get_cash_account_by_id(cash_account_id)
    if not account:
        return None, "الحساب غير موجود"

    balance_before = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN type='deposit' THEN amount ELSE -amount END), 0) FROM cash_transactions WHERE cash_account_id=? AND transaction_date < ?",
        (cash_account_id, from_date)
    ).fetchone()[0]
    opening = account['opening_balance'] + balance_before

    transactions = conn.execute(
        "SELECT * FROM cash_transactions WHERE cash_account_id=? AND transaction_date BETWEEN ? AND ? ORDER BY transaction_date, id",
        (cash_account_id, from_date, to_date)
    ).fetchall()

    period_movement = sum(t['amount'] if t['type']=='deposit' else -t['amount'] for t in transactions)
    closing = opening + period_movement

    conn.close()
    return {
        'account': account,
        'from_date': from_date,
        'to_date': to_date,
        'opening_balance': opening,
        'transactions': [dict(t) for t in transactions],
        'closing_balance': closing
    }, None
