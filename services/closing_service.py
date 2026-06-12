# services/closing_service.py – منطق قيد إغلاق الحسابات (مع دعم إقفال مراكز التكلفة)
import sqlite3
from database import get_connection
from services import cost_center_service as ccs
from services.audit_service import log_action

def get_account_balance(account_code):
    """جلب رصيد حساب محدد (عام)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    query = """
        SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance
        FROM journal_lines
        WHERE account_name = ?
    """
    result = conn.execute(query, (account_code,)).fetchone()
    conn.close()
    return result["balance"] if result else 0

def get_all_accounts_by_prefix(prefix):
    """جلب الحسابات حسب البادئة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute(
        "SELECT code, name, is_debit FROM accounts WHERE code LIKE ? ORDER BY code",
        (prefix + "%",)
    ).fetchall()
    conn.close()
    return accounts

def create_closing_entry(year, retained_earnings_code="32"):
    """
    إنشاء قيد إغلاق السنة المالية العامة (للشركة بالكامل) مع حماية العمليات.
    تُرجع (success, net_income, error_message)
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        conn.execute("BEGIN")
        
        # التأكد من عدم وجود قيد إغلاق مسبق لنفس السنة
        existing = conn.execute(
            "SELECT id FROM journal_entries WHERE description = ? AND date LIKE ?",
            (f"قيد إغلاق السنة المالية {year}", f"{year}%")
        ).fetchone()
        if existing:
            conn.rollback()
            conn.close()
            return False, 0, f"يوجد بالفعل قيد إغلاق للسنة {year}."
        
        # جمع أرصدة الإيرادات (4)
        revenue_accounts = get_all_accounts_by_prefix("4")
        total_revenue = 0
        revenue_details = []
        for acc in revenue_accounts:
            balance = get_account_balance(acc["code"])
            amount = -balance if acc["is_debit"] == "credit" else balance
            if amount != 0:
                total_revenue += amount
                revenue_details.append((acc["code"], acc["name"], amount))
        
        # جمع أرصدة المصروفات (5)
        expense_accounts = get_all_accounts_by_prefix("5")
        total_expense = 0
        expense_details = []
        for acc in expense_accounts:
            balance = get_account_balance(acc["code"])
            amount = balance if acc["is_debit"] == "debit" else -balance
            if amount != 0:
                total_expense += amount
                expense_details.append((acc["code"], acc["name"], amount))
        
        net_income = total_revenue - total_expense
        
        # إنشاء قيد اليومية
        desc = f"قيد إغلاق السنة المالية {year}"
        date_str = f"{year}-12-31"
        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (date_str, desc, f"إغلاق {year}")
        )
        entry_id = cur.lastrowid
        
        # إقفال الإيرادات (مدين) – مع exchange_rate و currency_code
        for code, name, amt in revenue_details:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, 0, 'YER', 1.0)",
                (entry_id, code, abs(amt))
            )
        
        # إقفال المصروفات (دائن) – مع exchange_rate و currency_code
        for code, name, amt in expense_details:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, 0, ?, 'YER', 1.0)",
                (entry_id, code, abs(amt))
            )
        
        # توجيه صافي الدخل إلى الأرباح المحتجزة (32) – مع exchange_rate و currency_code
        if net_income > 0:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, 0, ?, 'YER', 1.0)",
                (entry_id, retained_earnings_code, net_income)
            )
        elif net_income < 0:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, 0, 'YER', 1.0)",
                (entry_id, retained_earnings_code, -net_income)
            )
        
        conn.commit()

        # تسجيل العملية في سجل التدقيق
        log_action(
            username="admin",
            action="إغلاق سنة مالية",
            table_name="journal_entries",
            record_id=entry_id,
            new_value=f"إغلاق السنة المالية {year}, صافي الدخل: {net_income:,.2f}"
        )

        return True, net_income, None
        
    except Exception as e:
        conn.rollback()
        return False, 0, str(e)
    finally:
        conn.close()

def create_cost_center_closing_entry(year, cost_center_id, retained_earnings_code="32"):
    """
    إنشاء قيد إغلاق لمركز تكلفة محدد (لتصفير إيراداته ومصروفاته المخصصة).
    يعتمد على توزيعات مراكز التكلفة الفعلية لتحديد المبالغ، ويتم توزيع كل سطر
    على نفس المركز بنسبة 100%.
    تُرجع (success, net_income, error_message)
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    # التحقق من وجود المركز
    center = ccs.get_cost_center_by_id(cost_center_id)
    if not center:
        return False, 0, "مركز التكلفة غير موجود"
    
    try:
        conn.execute("BEGIN")
        
        desc = f"قيد إغلاق مركز تكلفة {center['code']} - {center['name']} للسنة {year}"
        # التأكد من عدم وجود قيد إغلاق سابق لنفس المركز والسنة
        existing = conn.execute(
            "SELECT id FROM journal_entries WHERE description = ?",
            (desc,)
        ).fetchone()
        if existing:
            conn.rollback()
            conn.close()
            return False, 0, f"يوجد بالفعل قيد إغلاق للمركز {center['code']} للسنة {year}."
        
        # استخدام دالة قائمة الدخل المخصصة للمركز للحصول على صافي الدخل والتفاصيل
        income_stmt = ccs.get_cost_center_income_statement(cost_center_id, f"{year}-01-01", f"{year}-12-31")
        net_income = income_stmt['net_profit']
        details = income_stmt['details']  # تحتوي على account_code, account_type, net, debit, credit
        
        # إنشاء قيد الإغلاق
        date_str = f"{year}-12-31"
        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (date_str, desc, f"إغلاق مركز {center['code']} - {year}")
        )
        entry_id = cur.lastrowid
        
        # سننشئ أسطر الإغلاق لكل حساب إيراد/مصروف له صافي غير صفري
        # وكل سطر نوزعه على نفس المركز بنسبة 100%
        line_ids = []
        for item in details:
            if item['net'] == 0:
                continue
            
            account_code = item['account_code']
            account_type = item['account_type']
            abs_net = abs(item['net'])
            
            # إيرادات: مدين لإغلاقها (طبيعتها دائنة) – مع exchange_rate و currency_code
            if account_type in ('revenue', 'income'):
                cur_line = conn.execute(
                    "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, 0, 'YER', 1.0)",
                    (entry_id, account_code, abs_net)
                )
            # مصروفات: دائن لإغلاقها (طبيعتها مدينة) – مع exchange_rate و currency_code
            elif account_type in ('expense', 'cost_of_sales'):
                cur_line = conn.execute(
                    "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, 0, ?, 'YER', 1.0)",
                    (entry_id, account_code, abs_net)
                )
            else:
                # حسابات أخرى لا نغلقها عادةً، لكن إذا وُجدت نضبطها بنفس المنطق مع exchange_rate
                if item['net'] > 0:
                    cur_line = conn.execute(
                        "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, 0, 'YER', 1.0)",
                        (entry_id, account_code, abs_net)
                    )
                else:
                    cur_line = conn.execute(
                        "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, 0, ?, 'YER', 1.0)",
                        (entry_id, account_code, abs_net)
                    )
            
            line_id = cur_line.lastrowid
            line_ids.append(line_id)
            
            # توزيع هذا السطر على المركز الحالي بنسبة 100%
            ccs.allocate_journal_line(line_id, [{
                'cost_center_id': cost_center_id,
                'amount': abs_net,
                'percentage': 100.0
            }])
        
        # إضافة سطر صافي الدخل إلى الأرباح المحتجزة وتوزيعه على المركز – مع exchange_rate و currency_code
        if net_income > 0:
            cur_line = conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, 0, ?, 'YER', 1.0)",
                (entry_id, retained_earnings_code, net_income)
            )
        elif net_income < 0:
            cur_line = conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, 0, 'YER', 1.0)",
                (entry_id, retained_earnings_code, -net_income)
            )
        if net_income != 0:
            line_id = cur_line.lastrowid
            ccs.allocate_journal_line(line_id, [{
                'cost_center_id': cost_center_id,
                'amount': abs(net_income),
                'percentage': 100.0
            }])
        
        conn.commit()

        # تسجيل العملية في سجل التدقيق
        log_action(
            username="admin",
            action="إغلاق سنة مالية (مركز تكلفة)",
            table_name="journal_entries",
            record_id=entry_id,
            new_value=f"إغلاق مركز {center['code']} - {center['name']} للسنة {year}, صافي الدخل: {net_income:,.2f}"
        )

        return True, net_income, None
        
    except Exception as e:
        conn.rollback()
        return False, 0, str(e)
    finally:
        conn.close()
