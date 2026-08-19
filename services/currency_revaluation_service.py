# services/currency_revaluation_service.py – إعادة تقييم العملات (فروق أسعار الصرف) ديناميكياً
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate
from services.accounting_service import save_journal_entry

def get_accounts_with_foreign_currency():
    """
    جلب الحسابات التي لها حركات بالعملات الأجنبية.
    (تم دعم الربط بـ account_id، أو تطابق الاسم account_name، أو كود الحساب account_code لضمان ظهور كافة الحسابات المسجلة)
    """
    base = get_base_currency()
    base_code = base['code'] if base else 'YER'
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        accounts = conn.execute("""
            SELECT DISTINCT 
                a.id as account_id, 
                a.name as account_name, 
                a.code as account_code,
                UPPER(TRIM(jl.currency_code)) as currency_code
            FROM journal_lines jl
            JOIN accounts a ON (
                jl.account_id = a.id OR 
                jl.account_name = a.name OR
                jl.account_name = a.code
            )
            WHERE jl.currency_code IS NOT NULL 
              AND TRIM(jl.currency_code) != ''
              AND UPPER(TRIM(jl.currency_code)) != UPPER(?)
            ORDER BY a.code
        """, (base_code,)).fetchall()
        return [dict(a) for a in accounts]
    except Exception as e:
        print(f"Error fetching foreign currency accounts: {e}")
        return []
    finally:
        conn.close()

def get_foreign_balance(account_id, currency_code):
    """حساب الرصيد الأجنبي والقيمة المحلية السابقة بدقة مع دعم مطابقة ID، الاسم، أو الكود"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # جلب اسم الحساب وكوده لضمان البحث الآمن وشمولية كافة الحركات المرتبطة
        acc = conn.execute("SELECT name, code FROM accounts WHERE id = ?", (account_id,)).fetchone()
        acc_name = acc['name'] if acc else ""
        acc_code = acc['code'] if acc else ""

        row = conn.execute("""
            SELECT 
                COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as foreign_balance,
                COALESCE(SUM(debit * exchange_rate), 0) - COALESCE(SUM(credit * exchange_rate), 0) as local_value
            FROM journal_lines
            WHERE (account_id = ? OR account_name = ? OR account_name = ?) 
              AND UPPER(TRIM(currency_code)) = UPPER(TRIM(?))
        """, (account_id, acc_name, acc_code, currency_code)).fetchone()
        
        foreign_balance = row['foreign_balance'] if row else 0.0
        old_local_value = row['local_value'] if row else 0.0
        
        return foreign_balance, old_local_value
    except Exception as e:
        print(f"Error calculating foreign balance: {e}")
        return 0.0, 0.0
    finally:
        conn.close()

def perform_revaluation(account_id, currency_code, new_rate, revaluation_date, created_by="admin"):
    """تنفيذ عملية إعادة التقييم وإنشاء القيود المحاسبية تلقائياً"""
    
    base = get_base_currency()
    base_code = base['code'] if base else 'YER'
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # 1. التحقق من الحساب
        acc_info = conn.execute("SELECT id, name FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc_info:
            return None, "الحساب المحدد غير موجود في شجرة الحسابات."
        account_name = acc_info['name']

        # 2. جلب حساب فروق العملة
        fx_acc = conn.execute("SELECT id, name FROM accounts WHERE functional_type = 'exchange_difference' LIMIT 1").fetchone()
        if not fx_acc:
            return None, "لم يتم العثور على حساب 'فروق أسعار الصرف'. تأكد من تحديد النوع الوظيفي (exchange_difference) في شجرة الحسابات."
        
        fx_account_id = fx_acc['id']
        fx_account_name = fx_acc['name']
        
        # 3. حساب الأرصدة
        foreign_balance, old_local_value = get_foreign_balance(account_id, currency_code)
        
        if abs(foreign_balance) < 0.001:
            return None, "الرصيد صفر، لا حاجة لإعادة التقييم."
        
        new_local_value = round(foreign_balance * new_rate, 2)
        difference = round(new_local_value - old_local_value, 2)
        
        if abs(difference) < 0.01:
            return None, f"لا يوجد فرق جوهري لسعر صرف {currency_code}."
        
        # 4. بناء أسطر القيد
        if difference > 0: # ربح
            lines = [
                {"account_id": account_id, "account_name": account_name, "debit": difference, "credit": 0.0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account_id": fx_account_id, "account_name": fx_account_name, "debit": 0.0, "credit": difference,
                 "currency_code": base_code, "exchange_rate": 1.0}
            ]
        else: # خسارة
            lines = [
                {"account_id": fx_account_id, "account_name": fx_account_name, "debit": abs(difference), "credit": 0.0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account_id": account_id, "account_name": account_name, "debit": 0.0, "credit": abs(difference),
                 "currency_code": base_code, "exchange_rate": 1.0}
            ]
        
        desc = f"إعادة تقييم {account_name} - {currency_code} (سعر: {new_rate:,.2f})"
        
        # 5. حفظ القيد
        journal_result = save_journal_entry(description=desc, lines=lines, entry_date=revaluation_date)
        
        if isinstance(journal_result, tuple):
            entry_id = journal_result[0]
            error_msg = journal_result[1] if len(journal_result) > 1 else None
            if error_msg:
                return None, f"فشل إنشاء القيد المحاسبي: {error_msg}"
        else:
            entry_id = journal_result
            
        if not entry_id:
            return None, "تعذر استخراج رقم القيد المحاسبي."

        old_calculated_rate = old_local_value / foreign_balance if foreign_balance != 0 else 0
        
        # 6. الحفظ في جدول التقييم
        conn.execute("""
            INSERT INTO currency_revaluations 
            (date, account_id, account_name, currency_code, old_rate, new_rate, foreign_balance, old_local_value, new_local_value, difference, journal_entry_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (revaluation_date, account_id, account_name, currency_code, 
              old_calculated_rate, new_rate, foreign_balance, old_local_value, 
              new_local_value, difference, entry_id, created_by))
        
        conn.commit()
        
        # 7. التدقيق
        log_action(username=created_by, action="إعادة تقييم عملة",
                  table_name="currency_revaluations", record_id=entry_id,
                  new_value=f"{account_name} ({currency_code}): فرق {difference:,.2f}")
        
        return entry_id, None

    except sqlite3.Error as db_err:
        conn.rollback()
        return None, f"خطأ قاعدة بيانات: {str(db_err)}"
    except Exception as e:
        conn.rollback()
        return None, f"خطأ غير متوقع: {str(e)}"
    finally:
        conn.close()

def get_revaluation_history(limit=50):
    """سجل عمليات إعادة التقييم المنجزة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        history = conn.execute("""
            SELECT * FROM currency_revaluations
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(h) for h in history]
    except Exception as e:
        print(f"Error fetching revaluation history: {e}")
        return []
    finally:
        conn.close()
