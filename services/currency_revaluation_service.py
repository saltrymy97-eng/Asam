# services/currency_revaluation_service.py – إعادة تقييم العملات (فروق أسعار الصرف)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate
from services.accounting_service import save_journal_entry

def create_revaluation_table():
    """إنشاء جدول إعادة التقييم إذا لم يكن موجوداً"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS currency_revaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_accounts_with_foreign_currency():
    """
    جلب الحسابات (عملاء/موردين) التي لها حركات بعملة غير العملة الأساسية.
    نعتمد على journal_lines: أي حساب لديه currency_code مختلف عن العملة الأساسية.
    """
    base = get_base_currency()
    base_code = base['code'] if base else 'YER'
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("""
        SELECT DISTINCT account_name, currency_code
        FROM journal_lines
        WHERE currency_code IS NOT NULL AND currency_code != ''
          AND currency_code != ?
        ORDER BY account_name
    """, (base_code,)).fetchall()
    conn.close()
    return [dict(a) for a in accounts]

def get_foreign_balance(account_name, currency_code):
    """
    حساب رصيد الحساب بالعملة الأجنبية (صافي debit - credit بالعملة الأصلية)
    وحساب القيمة المحلية المسجلة حالياً (باستخدام أسعار الصرف التاريخية)
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    # الرصيد بالعملة الأصلية
    row = conn.execute("""
        SELECT 
            COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as foreign_balance
        FROM journal_lines
        WHERE account_name = ? AND currency_code = ?
    """, (account_name, currency_code)).fetchone()
    
    foreign_balance = row['foreign_balance'] if row else 0.0
    
    # القيمة المحلية التاريخية (باستخدام أسعار الصرف الأصلية)
    row_local = conn.execute("""
        SELECT 
            COALESCE(SUM(debit * exchange_rate), 0) - COALESCE(SUM(credit * exchange_rate), 0) as local_value
        FROM journal_lines
        WHERE account_name = ? AND currency_code = ?
    """, (account_name, currency_code)).fetchone()
    
    old_local_value = row_local['local_value'] if row_local else 0.0
    
    conn.close()
    return foreign_balance, old_local_value

def perform_revaluation(account_name, currency_code, new_rate, revaluation_date, created_by="admin"):
    """
    تنفيذ إعادة تقييم لحساب معين بعملة أجنبية.
    - يحسب الفرق بين القيمة القديمة والجديدة.
    - ينشئ قيد تعديل (فروق عملة) إن وجد فرق.
    """
    create_revaluation_table()
    base = get_base_currency()
    base_code = base['code'] if base else 'YER'
    
    # جلب الرصيد والقيمة الحالية
    foreign_balance, old_local_value = get_foreign_balance(account_name, currency_code)
    
    # إذا كان الرصيد صفر، لا حاجة للتقييم
    if abs(foreign_balance) < 0.001:
        return None, f"رصيد الحساب {account_name} بالعملة {currency_code} يساوي صفر، لا حاجة لإعادة التقييم"
    
    # حساب القيمة الجديدة باستخدام السعر الجديد
    new_local_value = foreign_balance * new_rate
    difference = new_local_value - old_local_value
    
    # إذا كان الفرق طفيف جداً
    if abs(difference) < 0.01:
        return None, f"لا يوجد فرق جوهري لسعر صرف {currency_code} (الفرق أقل من 0.01)"
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        
        # القيد: إذا الفرق موجب (مكسب) أو سالب (خسارة)
        if difference > 0:
            # أصل (عميل) زادت قيمته: مدين العميل، دائن فروق عملة
            lines = [
                {"account": account_name, "debit": difference, "credit": 0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account": "فروق أسعار الصرف", "debit": 0, "credit": difference,
                 "currency_code": base_code, "exchange_rate": 1.0}
            ]
        else:
            # أصل (عميل) نقصت قيمته أو التزام (مورد) زاد: مدين فروق عملة، دائن الحساب
            lines = [
                {"account": "فروق أسعار الصرف", "debit": -difference, "credit": 0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account": account_name, "debit": 0, "credit": -difference,
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
        
        # تسجيل العملية في جدول revaluations
        conn.execute("""
            INSERT INTO currency_revaluations 
            (date, account_name, currency_code, old_rate, new_rate, foreign_balance, old_local_value, new_local_value, difference, journal_entry_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (revaluation_date, account_name, currency_code, 
              old_local_value/foreign_balance if foreign_balance != 0 else 0,
              new_rate, foreign_balance, old_local_value, new_local_value, difference,
              entry_id, created_by))
        
        conn.commit()
        
        log_action(username=created_by, action="إعادة تقييم عملة",
                  table_name="currency_revaluations", record_id=entry_id,
                  new_value=f"{account_name} {currency_code}: فرق {difference:,.2f}")
        
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
    history = conn.execute("""
        SELECT * FROM currency_revaluations
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(h) for h in history]
