# services/financial_service.py - القوائم المالية (مع مراكز التكلفة والعملات)
import sqlite3

DB_PATH = "erp.db"

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
        # استخدام توزيعات المركز، مع ضرب المبلغ الموزع في سعر صرف السطر
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
        # إجمالي عام مع ضرب كل سطر في سعر صرفه
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

def get_accounts_by_prefix(prefix, cost_center_id=None):
    """جلب الحسابات المستخدمة في القيود (أو في توزيعات مركز معين)"""
    conn = get_conn()
    if cost_center_id:
        accounts = conn.execute("""
            SELECT DISTINCT jl.account_name as code
            FROM journal_lines jl
            JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
            WHERE jl.account_name LIKE ? AND cca.cost_center_id = ?
            ORDER BY jl.account_name
        """, (prefix + "%", cost_center_id)).fetchall()
    else:
        accounts = conn.execute("""
            SELECT DISTINCT jl.account_name as code
            FROM journal_lines jl
            WHERE jl.account_name LIKE ?
            ORDER BY jl.account_name
        """, (prefix + "%",)).fetchall()

    result = []
    for acc in accounts:
        code = acc["code"]
        name_row = conn.execute("SELECT name FROM accounts WHERE code=?", (code,)).fetchone()
        name = name_row["name"] if name_row else code
        result.append({"code": code, "name": name})
    conn.close()
    return result

def get_income_statement(cost_center_id=None):
    """قائمة الدخل (بالعملة الأساسية، مع فلترة اختيارية حسب مركز التكلفة)"""
    rev_accounts = get_accounts_by_prefix("4", cost_center_id)
    revenue_list = []
    total_revenue = 0
    for acc in rev_accounts:
        debit, credit = get_account_balance(acc["code"], cost_center_id)
        amount = credit - debit  # الإيرادات دائنة
        if amount != 0:
            total_revenue += amount
            revenue_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    exp_accounts = get_accounts_by_prefix("5", cost_center_id)
    expense_list = []
    total_expenses = 0
    for acc in exp_accounts:
        debit, credit = get_account_balance(acc["code"], cost_center_id)
        amount = debit - credit  # المصروفات مدينة
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

def get_balance_sheet(cost_center_id=None):
    """الميزانية العمومية (بالعملة الأساسية)"""
    # الأصول (1)
    asset_accounts = get_accounts_by_prefix("1", cost_center_id)
    asset_list = []
    total_assets = 0
    for acc in asset_accounts:
        debit, credit = get_account_balance(acc["code"], cost_center_id)
        amount = debit - credit
        if amount != 0:
            total_assets += amount
            asset_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    # الخصوم (2)
    liab_accounts = get_accounts_by_prefix("2", cost_center_id)
    liability_list = []
    total_liabilities = 0
    for acc in liab_accounts:
        debit, credit = get_account_balance(acc["code"], cost_center_id)
        amount = credit - debit  # الخصوم دائنة
        if amount != 0:
            total_liabilities += amount
            liability_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    # حقوق الملكية (3)
    eq_accounts = get_accounts_by_prefix("3", cost_center_id)
    equity_list = []
    total_equity = 0
    for acc in eq_accounts:
        debit, credit = get_account_balance(acc["code"], cost_center_id)
        amount = credit - debit
        if amount != 0:
            total_equity += amount
            equity_list.append({"code": acc["code"], "name": acc["name"], "amount": amount})

    # صافي الدخل
    if cost_center_id is None:
        # صافي الدخل العام من الإيرادات والمصروفات
        rev_accounts = get_accounts_by_prefix("4")
        exp_accounts = get_accounts_by_prefix("5")
        rev_debit = sum(get_account_balance(acc["code"])[0] for acc in rev_accounts)
        rev_credit = sum(get_account_balance(acc["code"])[1] for acc in rev_accounts)
        exp_debit = sum(get_account_balance(acc["code"])[0] for acc in exp_accounts)
        exp_credit = sum(get_account_balance(acc["code"])[1] for acc in exp_accounts)
        net_income = (rev_credit - rev_debit) - (exp_debit - exp_credit)
        total_equity += net_income
        equity_list.append({"code": "", "name": "صافي الدخل (أرباح محتجزة)", "amount": net_income})
    else:
        # صافي دخل المركز
        inc = get_income_statement(cost_center_id)
        net_income_center = inc['net_income']
        total_equity += net_income_center
        equity_list.append({"code": "", "name": "صافي الدخل للمركز", "amount": net_income_center})

    return {
        "assets": asset_list,
        "total_assets": total_assets,
        "liabilities": liability_list,
        "total_liabilities": total_liabilities,
        "equity": equity_list,
        "total_equity": total_equity,
        "total_liab_equity": total_liabilities + total_equity
    }
