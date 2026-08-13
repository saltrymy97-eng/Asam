# services/bank_service.py – منطق التعاملات البنكية (مع إدارة العمليات والقيود الآلية ودعم العملات)
import sqlite3
from datetime import date, datetime
import database
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry

def get_conn():
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    return conn

# ===================== إدارة الحسابات البنكية =====================

def create_bank_account(bank_name, account_number, account_name="", currency_code="YER", opening_balance=0.0, account_code=None):
    """إضافة حساب بنكي جديد مع ربطه بكود الحساب في شجرة الحسابات"""
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        # إذا لم يتم تحديد كود حساب، يتم استخدام الحساب الوظيفي الافتراضي للبنك
        final_account_code = account_code or get_functional_account("bank")
        
        conn.execute(
            """INSERT INTO bank_accounts (bank_name, account_number, account_name, currency_code, opening_balance, current_balance, account_code)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (bank_name, account_number, account_name, currency_code, opening_balance, opening_balance, final_account_code)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_bank_account(account_id, bank_name=None, account_number=None, account_name=None, currency_code=None, account_code=None, is_active=None):
    """تحديث بيانات حساب بنكي"""
    conn = get_conn()
    fields = []
    values = []
    if bank_name: fields.append("bank_name = ?"); values.append(bank_name)
    if account_number: fields.append("account_number = ?"); values.append(account_number)
    if account_name: fields.append("account_name = ?"); values.append(account_name)
    if currency_code: fields.append("currency_code = ?"); values.append(currency_code)
    if account_code: fields.append("account_code = ?"); values.append(account_code)
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

# ===================== الحركات البنكية والقيود الآلية =====================

def add_bank_transaction(bank_account_id, transaction_date, description, trans_type, amount, reference="", contra_account_code=None):
    """
    إضافة حركة بنكية مع إنشاء قيد محاسبي تلقائي وتحديث الرصيد (القيد إلزامي دائماً).
    """
    if trans_type not in ('deposit', 'withdrawal', 'transfer_in', 'transfer_out'):
        raise ValueError("نوع الحركة غير صالح")
    
    bank_acc = get_bank_account_by_id(bank_account_id)
    if not bank_acc:
        raise ValueError("الحساب البنكي غير موجود")
    
    bank_account_code = bank_acc.get('account_code') or get_functional_account("bank")
    currency = bank_acc.get('currency_code', 'YER')
    
    # ✅ الحل الاحترافي لسعر الصرف
    base_currency = get_base_currency()
    if currency == base_currency['code']:
        exchange_rate = 1.0
    else:
        exchange_rate = get_exchange_rate(currency, base_currency['code']) or 1.0
    
    # تحديد الحساب المقابل في القيد المحاسبي
    target_contra_code = contra_account_code or get_functional_account("cash")
    
    lines = []
    if trans_type in ('deposit', 'transfer_in'):
        # إيداع: البنك مدين، والحساب المقابل دائن
        lines.append({
            "account_name": bank_account_code,
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
        # سحب/تحويل للخارج: الحساب المقابل مدين، والبنك دائن
        lines.append({
            "account_name": target_contra_code,
            "debit": amount,
            "credit": 0.0,
            "currency_code": currency,
            "exchange_rate": exchange_rate
        })
        lines.append({
            "account_name": bank_account_code,
            "debit": 0.0,
            "credit": amount,
            "currency_code": currency,
            "exchange_rate": exchange_rate
        })
        
    # 🔧 التعديل الجديد: معالجة القيمة المرتجعة من save_journal_entry
    _journal_result = save_journal_entry(
        entry_date=transaction_date,
        description=f"{description} ({reference})".strip(),
        lines=lines
    )
    
    # التأكد من أن القيمة رقم وليس tuple
    if isinstance(_journal_result, tuple):
        journal_id = _journal_result[0]
    else:
        journal_id = _journal_result

    conn = get_conn()
    try:
        conn.execute("BEGIN")
        reconciled_flag = 1 if journal_id else 0
        conn.execute(
            """INSERT INTO bank_transactions (bank_account_id, transaction_date, description, type, amount, reference, reconciled, journal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (bank_account_id, transaction_date, description, trans_type, amount, reference, reconciled_flag, journal_id)
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

def transfer_between_banks(from_account_id, to_account_id, amount, transfer_date, description="تحويل بين حسابات بنكية", reference=""):
    """تحويل مالي بين حسابين بنكيين مع القيد المحاسبي المزدوج"""
    from_acc = get_bank_account_by_id(from_account_id)
    to_acc = get_bank_account_by_id(to_account_id)
    
    if not from_acc or not to_acc:
        raise ValueError("أحد الحسابات البنكية غير موجود")
    
    from_code = from_acc.get('account_code') or get_functional_account("bank")
    to_code = to_acc.get('account_code') or get_functional_account("bank")
    
    from_curr = from_acc.get('currency_code', 'YER')
    to_curr = to_acc.get('currency_code', 'YER')
    
    from_rate = get_exchange_rate(from_curr)
    to_rate = get_exchange_rate(to_curr)
    
    # القيمة بالعملة المحلية للطرف المحول منه
    base_amount = amount * from_rate
    # القيمة المحولة لحساب المستلم
    converted_to_amount = base_amount / to_rate if to_rate else amount

    # إنشاء قيد التحويل المباشر
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
        description=f"{description} من {from_acc['bank_name']} إلى {to_acc['bank_name']}",
        lines=lines
    )
    
    # تسجيل الحركتين في الجدول المصرفي
    add_bank_transaction(from_account_id, transfer_date, f"تحويل إلى {to_acc['bank_name']}", 'transfer_out', amount, reference)
    add_bank_transaction(to_account_id, transfer_date, f"تحويل من {from_acc['bank_name']}", 'transfer_in', converted_to_amount, reference)
    
    return journal_id

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
