# services/currency_revaluation_service.py – إعادة تقييم العملات (فروق أسعار الصرف) ديناميكياً
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry

def create_revaluation_table():
    """إنشاء جدول إعادة التقييم إذا لم يكن موجوداً"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS currency_revaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                account_name TEXT NOT NULL,
                currency_code TEXT NOT NULL,
                old_rate REAL,
                new_rate REAL,
                foreign_balance REAL,
                old_local_value REAL,
                new_local_value REAL,
                difference REAL,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES chart_of_accounts(id)
            )
        """)
        conn.commit()
    finally:
        conn.close()

def get_accounts_with_foreign_currency():
    """
    جلب الحسابات (عملاء/موردين/بنوك) التي لها حركات بعملة غير العملة الأساسية.
    نعتمد على journal_entry_lines لربط الحساب مع رمز العملة.
    """
    base = get_base_currency()
    base_code = base['code'] if base else 'YER'
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        accounts = conn.execute("""
            SELECT DISTINCT 
                c.id as account_id, 
                c.name as account_name, 
                c.code as account_code,
                jl.currency_code
            FROM journal_entry_lines jl
            JOIN chart_of_accounts c ON jl.account_id = c.id
            WHERE jl.currency_code IS NOT NULL AND jl.currency_code != ''
              AND jl.currency_code != ?
            ORDER BY c.name
        """, (base_code,)).fetchall()
        return [dict(a) for a in accounts]
    finally:
        conn.close()

def get_foreign_balance(account_id, currency_code):
    """
    حساب رصيد الحساب بالعملة الأجنبية (صافي debit - credit بالعملة الأصلية)
    وحساب القيمة المحلية المسجلة حالياً (باستخدام أسعار الصرف التاريخية)
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # الرصيد بالعملة الأصلية والقيمة المحلية التاريخية
        row = conn.execute("""
            SELECT 
                COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as foreign_balance,
                COALESCE(SUM(debit * exchange_rate), 0) - COALESCE(SUM(credit * exchange_rate), 0) as local_value
            FROM journal_entry_lines
            WHERE account_id = ? AND currency_code = ?
        """, (account_id, currency_code)).fetchone()
        
        foreign_balance = row['foreign_balance'] if row else 0.0
        old_local_value = row['local_value'] if row else 0.0
        
        return foreign_balance, old_local_value
    finally:
        conn.close()

def perform_revaluation(account_id, currency_code, new_rate, revaluation_date, created_by="admin"):
    """
    تنفيذ إعادة تقييم لحساب معين بعملة أجنبية.
    - يحسب الفرق بين القيمة القديمة والجديدة.
    - ينشئ قيد تعديل (فروق عملة) باستخدام الحسابات الوظيفية.
    """
    create_revaluation_table()
    base = get_base_currency()
    base_code = base['code'] if base else 'YER'
    
    # 1. جلب الحساب الوظيفي لأرباح وخسائر فروق العملة
    fx_account_id = (
        get_functional_account("fx_gain_loss") or 
        get_functional_account("fx_gain") or 
        get_functional_account("other_income")
    )
    if not fx_account_id:
        return None, "حساب فروق العملة الوظيفي (fx_gain_loss) غير معرف في شجرة الحسابات"

    # 2. جلب بيانات الحساب والرصيد والقيمة الحالية
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        acc_info = conn.execute("SELECT id, name FROM chart_of_accounts WHERE id=?", (account_id,)).fetchone()
        if not acc_info:
            return None, "الحساب المحدد غير موجود في شجرة الحسابات"
        
        account_name = acc_info['name']
        foreign_balance, old_local_value = get_foreign_balance(account_id, currency_code)
        
        # إذا كان الرصيد صفر، لا حاجة للتقييم
        if abs(foreign_balance) < 0.001:
            return None, f"رصيد الحساب '{account_name}' بالعملة {currency_code} يساوي صفر، لا حاجة لإعادة التقييم"
        
        # حساب القيمة الجديدة باستخدام السعر الجديد
        new_local_value = round(foreign_balance * new_rate, 2)
        difference = round(new_local_value - old_local_value, 2)
        
        # إذا كان الفرق طفيف جداً
        if abs(difference) < 0.01:
            return None, f"لا يوجد فرق جوهري لسعر صرف {currency_code} (الفرق أقل من 0.01)"
        
        conn.execute("BEGIN")
        
        # 3. بناء القيد المحاسبي باستخدام account_id المباشر
        if difference > 0:
            # زيادة في أصل أو انخفاض التزام (مكسب): مدين الحساب، دائن فروق عملة
            lines = [
                {"account_id": account_id, "debit": difference, "credit": 0.0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account_id": fx_account_id, "debit": 0.0, "credit": difference,
                 "currency_code": base_code, "exchange_rate": 1.0}
            ]
        else:
            # انخفاض في أصل أو زيادة التزام (خسارة): مدين فروق عملة، دائن الحساب
            lines = [
                {"account_id": fx_account_id, "debit": abs(difference), "credit": 0.0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account_id": account_id, "debit": 0.0, "credit": abs(difference),
                 "currency_code": base_code, "exchange_rate": 1.0}
            ]
        
        desc = f"إعادة تقييم {account_name} - {currency_code} (سعر جديد: {new_rate})"
        entry_id, error = save_journal_entry(
            description=desc,
            lines=lines,
            entry_date=revaluation_date,
            conn=conn
        )
        if error:
            raise Exception(error)
        
        # 4. تسجيل العملية في جدول revaluations
        old_calculated_rate = old_local_value / foreign_balance if foreign_balance != 0 else 0
        conn.execute("""
            INSERT INTO currency_revaluations 
            (date, account_id, account_name, currency_code, old_rate, new_rate, foreign_balance, old_local_value, new_local_value, difference, journal_entry_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (revaluation_date, account_id, account_name, currency_code, 
              old_calculated_rate, new_rate, foreign_balance, old_local_value, 
              new_local_value, difference, entry_id, created_by))
        
        conn.commit()
        
        log_action(username=created_by, action="إعادة تقييم عملة",
                  table_name="currency_revaluations", record_id=entry_id,
                  new_value=f"{account_name} ({currency_code}): فرق {difference:,.2f}")
        
        return entry_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_revaluation_history(limit=50):
    """سجل عمليات إعادة التقييم"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        history = conn.execute("""
            SELECT * FROM currency_revaluations
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(h) for h in history]
    finally:
        conn.close()
