# services/financial_service.py - القوائم المالية (مع مراكز التكلفة والعملات) - نسخة مصححة ونهائية
import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join("data", "erp.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_balance(account_code, cost_center_id=None):
    """
    رصيد حساب معين بالعملة الأساسية.
    إذا حُدد cost_center_id، يتم استخدام توزيعات المركز مع سعر صرف السطر الأصلي.
    """
    conn = get_conn()
    if cost_center_id:
        debit = conn.execute("""
            SELECT COALESCE(SUM(cca.amount * jl.exchange_rate), 0)
            FROM cost_center_allocations cca
            JOIN journal_lines jl ON cca.journal_line_id = jl.id
            WHERE jl.account_name = ? AND cca.cost_center_id = ? AND jl.debit > 0
        """, (account_code, cost_center_id)).fetchone()[0]
        credit = conn.execute("""
            SELECT COALESCE(SUM(cca.amount * jl.exchange_rate), 0)
            FROM cost_center_allocations cca
            JOIN journal_lines jl ON cca.journal_line_id = jl.id
            WHERE jl.account_name = ? AND cca.cost_center_id = ? AND jl.credit > 0
        """, (account_code, cost_center_id)).fetchone()[0]
    else:
        debit = conn.execute(
            "SELECT COALESCE(SUM(debit * exchange_rate), 0) FROM journal_lines WHERE account_name=?",
            (account_code,)
        ).fetchone()[0]
        credit = conn.execute(
            "SELECT COALESCE(SUM(credit * exchange_rate), 0) FROM journal_lines WHERE account_name=?",
            (account_code,)
        ).fetchone()[0]
    conn.close()
    return debit, credit

def get_all_active_accounts(cost_center_id=None):
    """
    جلب جميع الحسابات المستخدمة في القيود مع تصنيفها من شجرة الحسابات.
    """
    conn = get_conn()
    accounts = []
    
    if cost_center_id:
        rows = conn.execute("""
            SELECT DISTINCT jl.account_name as code
            FROM journal_lines jl
            JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
            WHERE cca.cost_center_id = ?
            ORDER BY jl.account_name
        """, (cost_center_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT DISTINCT account_name as code
            FROM journal_lines
            ORDER BY account_name
        """).fetchall()
    
    for row in rows:
        code = row["code"]
        # التعديل: البحث بالكود أو بالاسم ليشمل الحسابات النصية
        tree = conn.execute(
            "SELECT name, is_debit, account_type FROM accounts WHERE code=? OR name=?",
            (code, code)
        ).fetchone()
        accounts.append({
            "code": code,
            "name": tree["name"] if tree else code,
            "account_type": tree["account_type"] if tree else None,
            "is_debit": (tree["is_debit"] == "debit") if tree else None
        })
    
    conn.close()
    return accounts

def get_income_statement(cost_center_id=None):
    """قائمة الدخل (بالعملة الأساسية)"""
    all_accounts = get_all_active_accounts(cost_center_id)
    revenue_list = []
    total_revenue = 0
    expense_list = []
    total_expenses = 0

    for acc in all_accounts:
        code = acc["code"]
        atype = acc["account_type"]
        # تصنيف الحساب كإيراد أو مصروف بناءً على النوع أو البادئة
        is_revenue = False
        is_expense = False
        if atype in ("Revenue", "Expense"):
            is_revenue = (atype == "Revenue")
            is_expense = (atype == "Expense")
        elif code and code[0].isdigit():
            prefix = code[0]
            if prefix == "4":
                is_revenue = True
            elif prefix == "5":
                is_expense = True

        if not is_revenue and not is_expense:
            continue

        debit, credit = get_account_balance(code, cost_center_id)
        if is_revenue:
            amount = credit - debit
            if amount != 0:
                total_revenue += amount
                revenue_list.append({"code": code, "name": acc["name"], "amount": amount})
        else:  # expense
            amount = debit - credit
            if amount != 0:
                total_expenses += amount
                expense_list.append({"code": code, "name": acc["name"], "amount": amount})

    return {
        "revenue": revenue_list,
        "total_revenue": total_revenue,
        "expenses": expense_list,
        "total_expenses": total_expenses,
        "net_income": total_revenue - total_expenses
    }

def get_balance_sheet(cost_center_id=None):
    """الميزانية العمومية (بالعملة الأساسية) - تصنيف دقيق ومتوازن"""
    all_accounts = get_all_active_accounts(cost_center_id)
    asset_list = []
    total_assets = 0
    liability_list = []
    total_liabilities = 0
    equity_list = []
    total_equity = 0

    for acc in all_accounts:
        code = acc["code"]
        atype = acc["account_type"]
        # تحديد الفئة: أصل، خصم، حقوق ملكية، أو بنود قائمة الدخل (يتم تجاهلها هنا)
        category = None
        if atype in ("Asset", "Liability", "Equity"):
            category = atype
        elif code and code[0].isdigit():
            prefix = code[0]
            if prefix == "1":
                category = "Asset"
            elif prefix == "2":
                category = "Liability"
            elif prefix == "3":
                category = "Equity"
            # 4 و 5 تُعالج في قائمة الدخل
        else:
            # حساب غير رقمي (اسم عميل/مورد): نصنفه حسب الرصيد
            debit, credit = get_account_balance(code, cost_center_id)
            net = debit - credit
            if net > 0:
                category = "Asset"
            elif net < 0:
                category = "Liability"
            # إذا كان الصفر، لا نظهره

        if category is None:
            continue

        debit, credit = get_account_balance(code, cost_center_id)
        if category == "Asset":
            amount = debit - credit
            if amount != 0:
                total_assets += amount
                asset_list.append({"code": code, "name": acc["name"], "amount": amount})
        elif category == "Liability":
            amount = credit - debit
            if amount != 0:
                total_liabilities += amount
                liability_list.append({"code": code, "name": acc["name"], "amount": amount})
        elif category == "Equity":
            amount = credit - debit
            if amount != 0:
                total_equity += amount
                equity_list.append({"code": code, "name": acc["name"], "amount": amount})

    # إضافة صافي الدخل إلى حقوق الملكية
    income_stmt = get_income_statement(cost_center_id)
    net_income = income_stmt['net_income']
    total_equity += net_income
    equity_list.append({"code": "", "name": "صافي الدخل (أرباح محتجزة)", "amount": net_income})

    return {
        "assets": asset_list,
        "total_assets": total_assets,
        "liabilities": liability_list,
        "total_liabilities": total_liabilities,
        "equity": equity_list,
        "total_equity": total_equity,
        "total_liab_equity": total_liabilities + total_equity
    }
