# services/financial_service.py - القوائم المالية (مع دعم مراكز التكلفة والحسابات الوظيفية والعملات)
import sqlite3
from database import get_connection
from services.chart_service import get_functional_account

def get_account_balance(account_code, cost_center_id=None, as_of_date=None, from_date=None, to_date=None):
    """
    رصيد حساب معين بالعملة الأساسية (محتسباً بسعر الصرف وقت القيد).
    دعم التصفية حسب مركز التكلفة أو نطاق زمني.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    params = [account_code]
    date_filter = ""
    if from_date:
        date_filter += " AND jl.entry_date >= ?"
        params.append(from_date)
    if to_date or as_of_date:
        target_date = to_date or as_of_date
        date_filter += " AND jl.entry_date <= ?"
        params.append(target_date)

    if cost_center_id:
        query = f"""
            SELECT 
                COALESCE(SUM(CASE WHEN jl.debit > 0 THEN cca.amount * COALESCE(jl.exchange_rate, 1.0) ELSE 0 END), 0) AS total_debit,
                COALESCE(SUM(CASE WHEN jl.credit > 0 THEN cca.amount * COALESCE(jl.exchange_rate, 1.0) ELSE 0 END), 0) AS total_credit
            FROM cost_center_allocations cca
            JOIN journal_lines jl ON cca.journal_line_id = jl.id
            WHERE jl.account_name = ? AND cca.cost_center_id = ? {date_filter}
        """
        params.insert(1, cost_center_id)
    else:
        query = f"""
            SELECT 
                COALESCE(SUM(debit * COALESCE(exchange_rate, 1.0)), 0) AS total_debit,
                COALESCE(SUM(credit * COALESCE(exchange_rate, 1.0)), 0) AS total_credit
            FROM journal_lines jl
            WHERE jl.account_name = ? {date_filter}
        """

    row = conn.execute(query, params).fetchone()
    conn.close()
    
    debit = row["total_debit"] if row else 0
    credit = row["total_credit"] if row else 0
    return debit, credit

def get_all_active_accounts(cost_center_id=None):
    """
    جلب جميع الحسابات المستخدمة في القيود مع تصنيفها من شجرة الحسابات.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    if cost_center_id:
        query = """
            SELECT DISTINCT jl.account_name AS code
            FROM journal_lines jl
            JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
            WHERE cca.cost_center_id = ?
            ORDER BY jl.account_name
        """
        rows = conn.execute(query, (cost_center_id,)).fetchall()
    else:
        query = """
            SELECT DISTINCT account_name AS code
            FROM journal_lines
            ORDER BY account_name
        """
        rows = conn.execute(query).fetchall()
    
    accounts = []
    for row in rows:
        code = row["code"]
        tree = conn.execute(
            "SELECT name, is_debit, account_type FROM accounts WHERE code = ? OR name = ?",
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

def get_income_statement(cost_center_id=None, from_date=None, to_date=None):
    """قائمة الدخل (بالعملة الأساسية)"""
    all_accounts = get_all_active_accounts(cost_center_id)
    revenue_list = []
    total_revenue = 0
    expense_list = []
    total_expenses = 0

    for acc in all_accounts:
        code = acc["code"]
        atype = acc["account_type"]
        
        is_revenue = False
        is_expense = False
        
        if atype in ("Revenue", "Expense", "income", "expense", "revenue"):
            is_revenue = (atype in ("Revenue", "income", "revenue"))
            is_expense = (atype in ("Expense", "expense"))
        elif code and code[0].isdigit():
            prefix = code[0]
            if prefix == "4":
                is_revenue = True
            elif prefix == "5":
                is_expense = True

        if not is_revenue and not is_expense:
            continue

        debit, credit = get_account_balance(code, cost_center_id=cost_center_id, from_date=from_date, to_date=to_date)
        
        if is_revenue:
            amount = credit - debit
            if amount != 0:
                total_revenue += amount
                revenue_list.append({"code": code, "name": acc["name"], "amount": amount})
        else:  # المصروفات
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

def get_balance_sheet(cost_center_id=None, as_of_date=None):
    """الميزانية العمومية (بالعملة الأساسية) - تصنيف دقيق ومتوازن اعتماداً على الحسابات الوظيفية"""
    all_accounts = get_all_active_accounts(cost_center_id)
    asset_list = []
    total_assets = 0
    liability_list = []
    total_liabilities = 0
    equity_list = []
    total_equity = 0

    retained_earnings_code = get_functional_account("retained_earnings")

    for acc in all_accounts:
        code = acc["code"]
        atype = acc["account_type"]
        
        category = None
        if atype in ("Asset", "Liability", "Equity", "asset", "liability", "equity"):
            if atype in ("Asset", "asset"):
                category = "Asset"
            elif atype in ("Liability", "liability"):
                category = "Liability"
            elif atype in ("Equity", "equity"):
                category = "Equity"
        elif code and code[0].isdigit():
            prefix = code[0]
            if prefix == "1":
                category = "Asset"
            elif prefix == "2":
                category = "Liability"
            elif prefix == "3":
                category = "Equity"
        else:
            # حساب غير رقمي (عميل / مورد): يصنف حسب الطبيعة
            debit, credit = get_account_balance(code, cost_center_id=cost_center_id, as_of_date=as_of_date)
            net = debit - credit
            if net > 0:
                category = "Asset"
            elif net < 0:
                category = "Liability"

        if category is None:
            continue

        debit, credit = get_account_balance(code, cost_center_id=cost_center_id, as_of_date=as_of_date)
        
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

    # احتساب صافي الدخل وإضافته إلى حقوق الملكية تحت كود الأرباح المحتجزة الوظيفي
    income_stmt = get_income_statement(cost_center_id=cost_center_id, to_date=as_of_date)
    net_income = income_stmt['net_income']
    total_equity += net_income
    
    # جلب اسم حساب الأرباح المحتجزة
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    retained_acc = conn.execute("SELECT name FROM accounts WHERE code = ?", (retained_earnings_code,)).fetchone()
    conn.close()
    retained_name = retained_acc["name"] if retained_acc else "الأرباح المحتجزة (صافي الدخل)"

    equity_list.append({
        "code": retained_earnings_code,
        "name": f"{retained_name} - الفترة الحالية",
        "amount": net_income
    })

    return {
        "assets": asset_list,
        "total_assets": total_assets,
        "liabilities": liability_list,
        "total_liabilities": total_liabilities,
        "equity": equity_list,
        "total_equity": total_equity,
        "total_liab_equity": total_liabilities + total_equity
    }
