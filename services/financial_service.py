# services/financial_service.py - منطق القوائم المالية (يبحث بالاسم والكود)
import sqlite3

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_balance(account_input):
    """جلب رصيد حساب محدد (يبحث بالكود أو الاسم)"""
    conn = get_conn()
    # البحث بالكود أو الاسم
    query = """
        SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance
        FROM journal_lines
        WHERE account_name = ? OR account_name = (SELECT name FROM accounts WHERE code = ?)
    """
    result = conn.execute(query, (account_input, account_input)).fetchone()
    conn.close()
    return result["balance"] if result else 0

def get_accounts_by_prefix(prefix):
    """جلب جميع الحسابات المستخدمة في القيود التي تبدأ كوداتها بالبادئة"""
    conn = get_conn()
    accounts = conn.execute("""
        SELECT DISTINCT jl.account_name as code,
               COALESCE(a.name, jl.account_name) as name,
               COALESCE(a.is_debit,
                  CASE
                    WHEN jl.account_name LIKE '1%' THEN 'debit'
                    WHEN jl.account_name LIKE '5%' THEN 'debit'
                    WHEN jl.account_name LIKE '4%' THEN 'credit'
                    WHEN jl.account_name LIKE '2%' THEN 'credit'
                    WHEN jl.account_name LIKE '3%' THEN 'credit'
                    ELSE 'debit'
                  END) as is_debit
        FROM journal_lines jl
        LEFT JOIN accounts a ON jl.account_name = a.code OR jl.account_name = a.name
        WHERE jl.account_name LIKE ? OR a.code LIKE ?
        ORDER BY jl.account_name
    """, (prefix + "%", prefix + "%")).fetchall()
    conn.close()
    return accounts

def get_income_statement():
    """توليد بيانات قائمة الدخل"""
    revenue_accounts = get_accounts_by_prefix("4")
    total_revenue = 0
    revenue_data = []
    for acc in revenue_accounts:
        balance = get_account_balance(acc["code"])
        amount = -balance if acc["is_debit"] == "credit" else balance
        total_revenue += amount
        revenue_data.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    expense_accounts = get_accounts_by_prefix("5")
    total_expenses = 0
    expense_data = []
    for acc in expense_accounts:
        balance = get_account_balance(acc["code"])
        amount = balance if acc["is_debit"] == "debit" else -balance
        total_expenses += amount
        expense_data.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    net_income = total_revenue - total_expenses
    return {
        "revenue": revenue_data,
        "total_revenue": total_revenue,
        "expenses": expense_data,
        "total_expenses": total_expenses,
        "net_income": net_income
    }

def get_balance_sheet():
    """توليد بيانات الميزانية العمومية"""
    asset_accounts = get_accounts_by_prefix("1")
    total_assets = 0
    asset_data = []
    for acc in asset_accounts:
        balance = get_account_balance(acc["code"])
        amount = balance if acc["is_debit"] == "debit" else -balance
        total_assets += amount
        asset_data.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    liability_accounts = get_accounts_by_prefix("2")
    total_liabilities = 0
    liability_data = []
    for acc in liability_accounts:
        balance = get_account_balance(acc["code"])
        amount = -balance if acc["is_debit"] == "credit" else balance
        total_liabilities += amount
        liability_data.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    equity_accounts = get_accounts_by_prefix("3")
    total_equity = 0
    equity_data = []
    for acc in equity_accounts:
        balance = get_account_balance(acc["code"])
        amount = -balance if acc["is_debit"] == "credit" else balance
        total_equity += amount
        equity_data.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    rev_total = sum(-get_account_balance(acc["code"]) if acc["is_debit"]=="credit" else get_account_balance(acc["code"]) for acc in get_accounts_by_prefix("4"))
    exp_total = sum(get_account_balance(acc["code"]) if acc["is_debit"]=="debit" else -get_account_balance(acc["code"]) for acc in get_accounts_by_prefix("5"))
    net = rev_total - exp_total
    total_equity += net
    equity_data.append({"code": "", "name": "صافي الدخل (أرباح محتجزة)", "amount": net})

    return {
        "assets": asset_data,
        "total_assets": total_assets,
        "liabilities": liability_data,
        "total_liabilities": total_liabilities,
        "equity": equity_data,
        "total_equity": total_equity,
        "total_liab_equity": total_liabilities + total_equity
    }
