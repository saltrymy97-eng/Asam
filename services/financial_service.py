# services/financial_service.py - منطق القوائم المالية (نظيف، بدون تشخيص)
import sqlite3

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_balance(account_code):
    """جلب رصيد حساب محدد"""
    conn = get_conn()
    debit = conn.execute("SELECT COALESCE(SUM(debit),0) FROM journal_lines WHERE account_name=?", (account_code,)).fetchone()[0]
    credit = conn.execute("SELECT COALESCE(SUM(credit),0) FROM journal_lines WHERE account_name=?", (account_code,)).fetchone()[0]
    conn.close()
    return debit, credit

def get_accounts_by_prefix(prefix):
    """جلب الحسابات المستخدمة في القيود"""
    conn = get_conn()
    accounts = conn.execute("""
        SELECT DISTINCT jl.account_name as code,
               COALESCE(a.name, jl.account_name) as name,
               COALESCE(a.is_debit,
                  CASE
                    WHEN jl.account_name LIKE '1%' THEN 'debit'
                    WHEN jl.account_name LIKE '5%' THEN 'debit'
                    ELSE 'credit'
                  END) as is_debit
        FROM journal_lines jl
        LEFT JOIN accounts a ON jl.account_name = a.code OR jl.account_name = a.name
        WHERE jl.account_name LIKE ?
        ORDER BY jl.account_name
    """, (prefix + "%",)).fetchall()
    conn.close()
    return accounts

def get_income_statement():
    """قائمة الدخل"""
    rev_accounts = get_accounts_by_prefix("4")
    revenue_list = []
    total_revenue = 0
    for acc in rev_accounts:
        debit, credit = get_account_balance(acc["code"])
        amount = credit - debit
        if amount != 0:
            total_revenue += amount
            revenue_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    exp_accounts = get_accounts_by_prefix("5")
    expense_list = []
    total_expenses = 0
    for acc in exp_accounts:
        debit, credit = get_account_balance(acc["code"])
        amount = debit - credit
        if amount != 0:
            total_expenses += amount
            expense_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    return {
        "revenue": revenue_list,
        "total_revenue": total_revenue,
        "expenses": expense_list,
        "total_expenses": total_expenses,
        "net_income": total_revenue - total_expenses
    }

def get_balance_sheet():
    """الميزانية العمومية"""
    asset_accounts = get_accounts_by_prefix("1")
    asset_list = []
    total_assets = 0
    for acc in asset_accounts:
        debit, credit = get_account_balance(acc["code"])
        amount = debit - credit
        if amount != 0:
            total_assets += amount
            asset_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    liab_accounts = get_accounts_by_prefix("2")
    liability_list = []
    total_liabilities = 0
    for acc in liab_accounts:
        debit, credit = get_account_balance(acc["code"])
        amount = credit - debit
        if amount != 0:
            total_liabilities += amount
            liability_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    eq_accounts = get_accounts_by_prefix("3")
    equity_list = []
    total_equity = 0
    for acc in eq_accounts:
        debit, credit = get_account_balance(acc["code"])
        amount = credit - debit
        if amount != 0:
            total_equity += amount
            equity_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    rev_debit = sum(get_account_balance(acc["code"])[0] for acc in get_accounts_by_prefix("4"))
    rev_credit = sum(get_account_balance(acc["code"])[1] for acc in get_accounts_by_prefix("4"))
    exp_debit = sum(get_account_balance(acc["code"])[0] for acc in get_accounts_by_prefix("5"))
    exp_credit = sum(get_account_balance(acc["code"])[1] for acc in get_accounts_by_prefix("5"))
    net = (rev_credit - rev_debit) - (exp_debit - exp_credit)
    total_equity += net
    equity_list.append({"code": "", "name": "صافي الدخل (أرباح محتجزة)", "amount": net})

    return {
        "assets": asset_list,
        "total_assets": total_assets,
        "liabilities": liability_list,
        "total_liabilities": total_liabilities,
        "equity": equity_list,
        "total_equity": total_equity,
        "total_liab_equity": total_liabilities + total_equity
    }
