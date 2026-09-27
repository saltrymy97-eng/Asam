# services/expenses_service.py – منطق المصروفات (v2.0)
# ✅ Registry + فحص الرصيد + دعم البنك والصندوق
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


def create_expenses_table(conn=None):
    """إنشاء جدول المصروفات إذا لم يكن موجوداً"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                account_code TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                party_type TEXT,
                party_id INTEGER,
                party_name TEXT,
                invoice_ref TEXT,
                notes TEXT,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


def get_expense_categories():
    """جلب فئات المصروفات الشائعة"""
    return [
        {"code": "إيجار", "name": "إيجار"},
        {"code": "كهرباء", "name": "كهرباء"},
        {"code": "مياه", "name": "مياه"},
        {"code": "إنترنت", "name": "إنترنت"},
        {"code": "رواتب", "name": "رواتب"},
        {"code": "صيانة", "name": "صيانة"},
        {"code": "نقل", "name": "نقل"},
        {"code": "قرطاسية", "name": "قرطاسية"},
        {"code": "دعاية وإعلان", "name": "دعاية وإعلان"},
        {"code": "أخرى", "name": "أخرى"},
    ]


def get_payment_accounts(conn=None):
    """
    ✅ جلب كل الحسابات القابلة للدفع (صناديق + بنوك).
    يُرجع قائمة موحّدة للاستخدام في الواجهة.
    
    Returns:
        list of {id, code, name, type, balance, currency}
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        result = []
        
        # 1) الصناديق
        cash_rows = conn.execute("""
            SELECT id, name, currency_code, current_balance, account_code
            FROM cash_accounts
            WHERE is_active = 1
            ORDER BY name
        """).fetchall()
        
        for r in cash_rows:
            result.append({
                "id": r["id"],
                "code": r["account_code"],
                "name": r["name"],
                "type": "cash",
                "balance": float(r["current_balance"] or 0),
                "currency": r["currency_code"] or "YER",
            })
        
        # 2) البنوك
        try:
            bank_rows = conn.execute("""
                SELECT id, bank_name, account_number, currency_code, 
                       current_balance, account_code
                FROM bank_accounts
                WHERE is_active = 1
                ORDER BY bank_name
            """).fetchall()
            
            for r in bank_rows:
                display_name = f"{r['bank_name']} ({r['account_number']})"
                result.append({
                    "id": r["id"],
                    "code": r["account_code"],
                    "name": display_name,
                    "type": "bank",
                    "balance": float(r["current_balance"] or 0),
                    "currency": r["currency_code"] or "YER",
                })
        except Exception:
            pass  # bank_accounts قد لا يحتوي بعض الأعمدة
        
        return result
    finally:
        if own_conn:
            close_connection(conn)


def get_cash_accounts(conn=None):
    """(للتوافق مع الكود القديم) جلب حسابات النقدية والبنوك"""
    return get_payment_accounts(conn=conn)


def get_suppliers_for_expense(conn=None):
    """جلب الموردين للقائمة المنسدلة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        suppliers = conn.execute(
            "SELECT id, name FROM suppliers ORDER BY name"
        ).fetchall()
        return [dict(s) for s in suppliers]
    finally:
        if own_conn:
            close_connection(conn)


def create_expense(date_val, category, amount, account_code, payment_method,
                    party_type=None, party_id=None, invoice_ref=None, notes=None,
                    created_by="admin", conn=None):
    """
    تسجيل مصروف مع إنشاء قيد محاسبي متزن.
    
    Args:
        account_code:   كود حساب الصندوق/البنك (يُستخدم للخصم)
        payment_method: 'cash' | 'bank' | 'credit'
        party_type:     'supplier' أو None
        party_id:       معرف المورد
    
    Returns:
        (expense_id, None)          عند النجاح
        (None, "رسالة الخطأ")      عند الفشل
    """
    create_expenses_table(conn=conn)

    # ✅ التحقق من المبلغ
    if amount is None or float(amount) <= 0:
        return None, "المبلغ يجب أن يكون أكبر من الصفر"

    amount = float(amount)

    # ✅ التحقق من payment_method
    if payment_method not in ('cash', 'bank', 'credit'):
        return None, "طريقة الدفع يجب أن تكون cash أو bank أو credit"

    # ✅ فحص الرصيد قبل السحب (فقط إذا كان نقدي أو بنكي)
    if payment_method in ('cash', 'bank'):
        from services.cash_service import check_sufficient_balance
        ok, balance_err = check_sufficient_balance(account_code, amount, conn=conn)
        if not ok:
            return None, f"لا يمكن تسجيل المصروف: {balance_err}"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # 1. جلب اسم المورد إذا كان موجوداً
        party_name = None
        if party_type == 'supplier' and party_id:
            sup = conn.execute(
                "SELECT name FROM suppliers WHERE id=?", (party_id,)
            ).fetchone()
            party_name = sup['name'] if sup else None

        # 2. إدراج المصروف
        cur = conn.execute("""
            INSERT INTO expenses 
                (date, category, amount, account_code, payment_method,
                 party_type, party_id, party_name, invoice_ref, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_val, category, amount, account_code, payment_method,
              party_type, party_id, party_name, invoice_ref, notes, created_by))
        expense_id = cur.lastrowid

        # 3. الحسابات الوظيفية
        expense_account = get_functional_account("operating_expense")

        # ✅ تحديد حساب الدائن
        if payment_method == 'credit':
            if party_type == 'supplier' and party_id:
                # آجل: ذمم الموردين
                credit_account = get_functional_account("accounts_payable")
            else:
                # آجل بدون مورد: نستخدم حساب المصروف نفسه (يُعالج لاحقاً)
                credit_account = get_functional_account("accrued_expenses")
        else:
            # نقدي أو بنكي: نخصم من الصندوق/البنك مباشرة
            credit_account = account_code

        if not expense_account:
            if own_conn:
                conn.rollback()
            return None, "لم يتم العثور على حساب المصروفات الوظيفي (operating_expense)"

        if not credit_account:
            if own_conn:
                conn.rollback()
            return None, "لم يتم تحديد حساب الدائن"

        # 4. بناء سطور القيد
        lines = [
            {
                "account": expense_account,
                "debit": amount,
                "credit": 0.0,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
            {
                "account": credit_account,
                "debit": 0.0,
                "credit": amount,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
        ]

        # 5. إنشاء القيد
        entry_id, error = save_journal_entry(
            description=f"مصروف {category} - {date_val}",
            lines=lines,
            entry_date=date_val,
            conn=conn,
        )
        if error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {error}")

        # 6. تحديث سجل المصروف برقم القيد
        conn.execute(
            "UPDATE expenses SET journal_entry_id=? WHERE id=?",
            (entry_id, expense_id)
        )

        # 7. ✅ تسجيل حركة الصندوق/البنك (إذا نقدي/بنكي)
        if payment_method == 'cash':
            try:
                from services.cash_service import add_cash_transaction
                # نبحث عن الصندوق بكود الحساب
                acc_row = conn.execute(
                    "SELECT id FROM cash_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                    (account_code,)
                ).fetchone()
                if acc_row:
                    add_cash_transaction(
                        acc_row['id'],
                        date_val,
                        f"مصروف {category}",
                        'withdrawal',
                        amount,
                        reference=f"expense#{expense_id}",
                        create_journal=False,
                        conn=conn,
                        skip_balance_check=True,  # تم الفحص
                    )
            except Exception as e:
                print(f"⚠️ فشل تسجيل حركة الصندوق: {e}")

        elif payment_method == 'bank':
            try:
                from services.bank_service import add_bank_transaction
                acc_row = conn.execute(
                    "SELECT id FROM bank_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                    (account_code,)
                ).fetchone()
                if acc_row:
                    add_bank_transaction(
                        acc_row['id'],
                        date_val,
                        f"مصروف {category}",
                        'withdrawal',
                        amount,
                        reference=f"expense#{expense_id}",
                        conn=conn,
                        skip_balance_check=True,
                    )
            except Exception as e:
                print(f"⚠️ فشل تسجيل حركة البنك: {e}")

        if own_conn:
            conn.commit()

        log_action(
            username=created_by,
            action="تسجيل مصروف",
            table_name="expenses",
            record_id=expense_id,
            new_value=f"{category}: {amount:,.2f} ({payment_method})"
        )

        return expense_id, None

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def get_expenses(limit=50, conn=None):
    """جلب سجل المصروفات"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        expenses = conn.execute("""
            SELECT e.*, j.id as journal_id
            FROM expenses e
            LEFT JOIN journal_entries j ON e.journal_entry_id = j.id
            ORDER BY e.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(e) for e in expenses]
    finally:
        if own_conn:
            close_connection(conn)


def delete_expense(expense_id, conn=None):
    """حذف مصروف (مع حذف القيد المرتبط به)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN")
        
        row = conn.execute(
            "SELECT journal_entry_id FROM expenses WHERE id=?", (expense_id,)
        ).fetchone()
        entry_id = row[0] if row else None
        
        if entry_id:
            conn.execute("DELETE FROM journal_lines WHERE entry_id=?", (entry_id,))
            conn.execute("DELETE FROM journal_entries WHERE id=?", (entry_id,))
        
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        
        if own_conn:
            conn.commit()
        return True, None
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
