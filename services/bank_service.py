# services/bank_service.py – منطق التعاملات البنكية (v2.0)
# ✅ Connection Registry + حماية الرصيد
import sqlite3
from datetime import date, datetime
from database import get_connection, close_connection
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


# ============================================================
# ✅ دالة الفحص (تستخدم من cash_service أيضاً)
# ============================================================
def check_bank_sufficient_balance(bank_account_id, amount, conn=None):
    """
    فحص كفاية رصيد البنك قبل السحب/التحويل.
    
    Returns:
        (True, None) أو (False, "رسالة الخطأ")
    """
    if bank_account_id is None:
        return False, "معرف الحساب البنكي مفقود"
    
    try:
        amount_float = float(amount)
    except (ValueError, TypeError):
        return False, "المبلغ غير صحيح"
    
    if amount_float <= 0:
        return False, "المبلغ يجب أن يكون أكبر من صفر"
    
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        row = conn.execute(
            "SELECT bank_name, current_balance FROM bank_accounts WHERE id = ? AND is_active = 1",
            (bank_account_id,)
        ).fetchone()
        
        if not row:
            return False, "الحساب البنكي غير موجود"
        
        current = float(row["current_balance"] or 0)
        if amount_float > current:
            return False, (
                f"الرصيد غير كافٍ في '{row['bank_name']}'. "
                f"المتاح: {current:,.2f}، المطلوب: {amount_float:,.2f}"
            )
        return True, None
    finally:
        if own_conn:
            close_connection(conn)


# ===================== إدارة الحسابات البنكية =====================

def create_bank_account(bank_name, account_number, account_name="",
                        currency_code="YER", opening_balance=0.0,
                        account_code=None, conn=None):
    """إضافة حساب بنكي جديد"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        if own_conn:
            conn.execute("BEGIN")
        
        final_account_code = account_code or get_functional_account("bank")
        
        conn.execute(
            """INSERT INTO bank_accounts 
               (bank_name, account_number, account_name, currency_code, 
                opening_balance, current_balance, account_code)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (bank_name, account_number, account_name, currency_code,
             opening_balance, opening_balance, final_account_code)
        )
        
        if own_conn:
            conn.commit()
        
        # ✅ قيد الرصيد الافتتاحي
        if opening_balance > 0:
            capital_account_code = get_functional_account("capital")
            lines = [
                {
                    "account": final_account_code,
                    "debit": opening_balance,
                    "credit": 0.0,
                    "currency_code": currency_code,
                    "exchange_rate": 1.0
                },
                {
                    "account": capital_account_code,
                    "debit": 0.0,
                    "credit": opening_balance,
                    "currency_code": currency_code,
                    "exchange_rate": 1.0
                }
            ]
            save_journal_entry(
                description=f"رصيد افتتاحي لحساب بنكي {bank_name} ({account_number})",
                lines=lines,
                entry_date=date.today().strftime("%Y-%m-%d"),
                conn=conn if not own_conn else None
            )
        
        return True
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


def update_bank_account(account_id, bank_name=None, account_number=None,
                        account_name=None, currency_code=None,
                        account_code=None, is_active=None, conn=None):
    """تحديث بيانات حساب بنكي"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    fields = []
    values = []
    if bank_name: fields.append("bank_name = ?"); values.append(bank_name)
    if account_number: fields.append("account_number = ?"); values.append(account_number)
    if account_name: fields.append("account_name = ?"); values.append(account_name)
    if currency_code: fields.append("currency_code = ?"); values.append(currency_code)
    if account_code: fields.append("account_code = ?"); values.append(account_code)
    if is_active is not None: fields.append("is_active = ?"); values.append(1 if is_active else 0)
    
    if not fields:
        if own_conn:
            close_connection(conn)
        return
    
    try:
        if own_conn:
            conn.execute("BEGIN")
        values.append(account_id)
        conn.execute(f"UPDATE bank_accounts SET {', '.join(fields)} WHERE id = ?", values)
        if own_conn:
            conn.commit()
    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_all_bank_accounts(active_only=True, conn=None):
    """جلب جميع الحسابات البنكية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        query = "SELECT * FROM bank_accounts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY bank_name"
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def get_bank_account_by_id(account_id, conn=None):
    """جلب حساب بنكي محدد"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT * FROM bank_accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own_conn:
            close_connection(conn)


def get_bank_account_by_code(account_code, conn=None):
    """جلب حساب بنكي بكود الحساب"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT * FROM bank_accounts WHERE account_code = ? AND is_active = 1",
            (account_code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own_conn:
            close_connection(conn)


def update_bank_balance(account_id, conn=None):
    """تحديث الرصيد الحالي للحساب"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        deposits = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions "
            "WHERE bank_account_id = ? AND type = 'deposit'",
            (account_id,)
        ).fetchone()[0]
        withdrawals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions "
            "WHERE bank_account_id = ? AND type = 'withdrawal'",
            (account_id,)
        ).fetchone()[0]
        transfers_in = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions "
            "WHERE bank_account_id = ? AND type = 'transfer_in'",
            (account_id,)
        ).fetchone()[0]
        transfers_out = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions "
            "WHERE bank_account_id = ? AND type = 'transfer_out'",
            (account_id,)
        ).fetchone()[0]
        
        account = get_bank_account_by_id(account_id, conn=conn)
        if not account:
            return 0.0
        
        current_balance = (
            account['opening_balance'] + deposits + transfers_in
            - withdrawals - transfers_out
        )
        
        conn.execute(
            "UPDATE bank_accounts SET current_balance = ? WHERE id = ?",
            (current_balance, account_id)
        )
        if own_conn:
            conn.commit()
        return current_balance
    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


# ===================== الحركات البنكية =====================

def add_bank_transaction(bank_account_id, transaction_date, description,
                         trans_type, amount, reference="",
                         contra_account_code=None, conn=None,
                         skip_balance_check=False):
    """
    إضافة حركة بنكية مع قيد تلقائي.
    
    ✅ جديد: فحص الرصيد قبل السحب/التحويل للخارج.
    """
    if trans_type not in ('deposit', 'withdrawal', 'transfer_in', 'transfer_out'):
        raise ValueError("نوع الحركة غير صالح")
    
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        if own_conn:
            conn.execute("BEGIN")
        
        bank_acc = get_bank_account_by_id(bank_account_id, conn=conn)
        if not bank_acc:
            raise ValueError("الحساب البنكي غير موجود")
        
        bank_account_code = bank_acc.get('account_code') or get_functional_account("bank")
        currency = bank_acc.get('currency_code', 'YER')
        
        # ✅ جديد: فحص الرصيد قبل السحب/التحويل للخارج
        if trans_type in ('withdrawal', 'transfer_out') and not skip_balance_check:
            ok, err = check_bank_sufficient_balance(bank_account_id, float(amount), conn=conn)
            if not ok:
                if own_conn:
                    conn.rollback()
                raise ValueError(err)
        
        # سعر الصرف
        base_currency = get_base_currency()
        if currency == base_currency['code']:
            exchange_rate = 1.0
        else:
            exchange_rate = get_exchange_rate(currency, base_currency['code']) or 1.0
        
        target_contra_code = contra_account_code or get_functional_account("cash")
        
        lines = []
        if trans_type in ('deposit', 'transfer_in'):
            lines.append({
                "account": bank_account_code,
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
                "account": bank_account_code,
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
                raise ValueError(f"فشل القيد: {jerr}")
        else:
            journal_id = _journal_result
        
        reconciled_flag = 1 if journal_id else 0
        conn.execute(
            """INSERT INTO bank_transactions 
               (bank_account_id, transaction_date, description, type, amount, 
                reference, reconciled, journal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (bank_account_id, transaction_date, description, trans_type,
             amount, reference, reconciled_flag, journal_id)
        )
        
        if own_conn:
            conn.commit()
        
        # تحديث الرصيد
        update_bank_balance(bank_account_id, conn=conn if not own_conn else None)
        
        return True
    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def transfer_between_banks(from_account_id, to_account_id, amount,
                            transfer_date, description="تحويل بين حسابات بنكية",
                            reference="", conn=None):
    """تحويل بين حسابين بنكيين — مع فحص الرصيد"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        if own_conn:
            conn.execute("BEGIN")
        
        from_acc = get_bank_account_by_id(from_account_id, conn=conn)
        to_acc = get_bank_account_by_id(to_account_id, conn=conn)
        
        if not from_acc or not to_acc:
            raise ValueError("أحد الحسابات البنكية غير موجود")
        
        # ✅ جديد: فحص الرصيد قبل التحويل
        ok, err = check_bank_sufficient_balance(from_account_id, float(amount), conn=conn)
        if not ok:
            if own_conn:
                conn.rollback()
            raise ValueError(err)
        
        from_code = from_acc.get('account_code') or get_functional_account("bank")
        to_code = to_acc.get('account_code') or get_functional_account("bank")
        
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
        
        _journal_result = save_journal_entry(
            entry_date=transfer_date,
            description=f"{description} من {from_acc['bank_name']} إلى {to_acc['bank_name']}",
            lines=lines,
            conn=conn
        )
        if isinstance(_journal_result, tuple):
            journal_id = _journal_result[0]
        else:
            journal_id = _journal_result
        
        # ✅ نسجل الحركتين — مع skip_balance_check (تم الفحص)
        add_bank_transaction(
            from_account_id, transfer_date,
            f"تحويل إلى {to_acc['bank_name']}", 'transfer_out',
            amount, reference, conn=conn, skip_balance_check=True
        )
        add_bank_transaction(
            to_account_id, transfer_date,
            f"تحويل من {from_acc['bank_name']}", 'transfer_in',
            converted_to_amount, reference, conn=conn
        )
        
        if own_conn:
            conn.commit()
        
        return journal_id
    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_bank_transactions(bank_account_id=None, limit=50, conn=None):
    """جلب الحركات البنكية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def reconcile_transaction(transaction_id, journal_line_id=None, conn=None):
    """تسوية حركة بنكية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
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
        if own_conn:
            conn.commit()
        return True
    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_unreconciled_transactions(bank_account_id, conn=None):
    """جلب الحركات غير المسواة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute(
            """SELECT * FROM bank_transactions
               WHERE bank_account_id = ? AND reconciled = 0
               ORDER BY transaction_date""",
            (bank_account_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


# ===================== المصالحة البنكية =====================

def create_bank_reconciliation(bank_account_id, reconciliation_date,
                                statement_balance, conn=None):
    """إنشاء تسوية بنكية جديدة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN")
        
        account = get_bank_account_by_id(bank_account_id, conn=conn)
        if not account:
            raise ValueError("الحساب البنكي غير موجود")
        
        book_balance = account['current_balance']
        difference = statement_balance - book_balance
        
        conn.execute(
            """INSERT INTO bank_reconciliations 
               (bank_account_id, reconciliation_date, statement_balance, 
                book_balance, difference, status)
               VALUES (?, ?, ?, ?, ?, 'completed')""",
            (bank_account_id, reconciliation_date, statement_balance,
             book_balance, difference)
        )
        if own_conn:
            conn.commit()
        return True, difference
    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_reconciliation_history(bank_account_id=None, conn=None):
    """جلب سجل المصالحات البنكية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


# ===================== ملخصات =====================

def get_bank_balance_summary(conn=None):
    """ملخص أرصدة جميع الحسابات البنكية النشطة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        accounts = get_all_bank_accounts(active_only=True, conn=conn)
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
                'bank_name': acc['bank_name'],
                'account_number': acc['account_number'],
                'currency': currency,
                'balance': balance,
                'balance_base': balance_base
            })
            total_balance_base += balance_base
        
        return summary, total_balance_base
    finally:
        if own_conn:
            close_connection(conn)
