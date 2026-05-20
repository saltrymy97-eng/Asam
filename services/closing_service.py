# services/closing_service.py – منطق قيد إغلاق الحسابات (مع إدارة العمليات)
import sqlite3
from database import get_connection

def get_account_balance(account_code):
    """جلب رصيد حساب محدد"""
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

def create_closing_entry(year, retained_earnings_code="310000"):
    """
    إنشاء قيد إغلاق السنة المالية مع حماية العمليات.
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
        
        # إقفال الإيرادات (مدين)
        for code, name, amt in revenue_details:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, 0)",
                (entry_id, code, abs(amt))
            )
        
        # إقفال المصروفات (دائن)
        for code, name, amt in expense_details:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, 0, ?)",
                (entry_id, code, abs(amt))
            )
        
        # توجيه صافي الدخل إلى الأرباح المحتجزة
        if net_income > 0:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, 0, ?)",
                (entry_id, retained_earnings_code, net_income)
            )
        elif net_income < 0:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, 0)",
                (entry_id, retained_earnings_code, -net_income)
            )
        
        conn.commit()
        return True, net_income, None
        
    except Exception as e:
        conn.rollback()
        return False, 0, str(e)
    finally:
        conn.close()
