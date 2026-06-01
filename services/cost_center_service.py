import sqlite3
from datetime import datetime
import database

def get_connection():
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    return conn

# ===================== إدارة مراكز التكلفة =====================

def create_cost_center(code, name, parent_id=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cost_centers (code, name, parent_id, is_active) VALUES (?, ?, ?, 1)",
            (code, name, parent_id)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"الرمز {code} موجود مسبقاً")
    finally:
        conn.close()

def update_cost_center(center_id, code=None, name=None, parent_id=None, is_active=None):
    conn = get_connection()
    fields = []
    values = []
    if code: fields.append("code = ?"); values.append(code)
    if name: fields.append("name = ?"); values.append(name)
    if parent_id is not None: fields.append("parent_id = ?"); values.append(parent_id)
    if is_active is not None: fields.append("is_active = ?"); values.append(is_active)
    if not fields: return
    values.append(center_id)
    conn.execute(f"UPDATE cost_centers SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()

def delete_cost_center(center_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if cursor.execute("SELECT COUNT(*) as cnt FROM cost_centers WHERE parent_id = ?", (center_id,)).fetchone()['cnt'] > 0:
            raise ValueError("لا يمكن حذف المركز لأن لديه مراكز فرعية.")
        if cursor.execute("SELECT COUNT(*) as cnt FROM cost_center_allocations WHERE cost_center_id = ?", (center_id,)).fetchone()['cnt'] > 0:
            raise ValueError("لا يمكن حذف المركز لأن لديه توزيعات محاسبية.")
        cursor.execute("DELETE FROM cost_centers WHERE id = ?", (center_id,))
        conn.commit()
        return True
    except ValueError: raise
    except Exception as e: conn.rollback(); raise e
    finally: conn.close()

def get_all_cost_centers(active_only=True):
    conn = get_connection()
    query = "SELECT id, code, name, parent_id, is_active FROM cost_centers"
    if active_only: query += " WHERE is_active = 1"
    query += " ORDER BY code"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cost_center_tree():
    centers = get_all_cost_centers(active_only=False)
    if not centers: return []
    tree = {c['id']: {**c, 'children': []} for c in centers}
    roots = []
    for c in centers:
        if c['parent_id'] and c['parent_id'] in tree:
            tree[c['parent_id']]['children'].append(tree[c['id']])
        else: roots.append(tree[c['id']])
    return roots

def get_cost_center_by_id(center_id):
    conn = get_connection()
    row = conn.execute("SELECT id, code, name, parent_id, is_active FROM cost_centers WHERE id = ?", (center_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ... (باقي الدوال مثل التوزيعات ستظل كما هي، ثم نصل للتقارير) ...

# ===================== تقارير مراكز التكلفة (مُصححة بدون account_type) =====================

def _account_type_from_code(code):
    """تحديد نوع الحساب من أول رقم في الكود"""
    if not code: return 'unknown'
    first = code[0]
    if first == '1': return 'asset'
    elif first == '2': return 'liability'
    elif first == '3': return 'equity'
    elif first == '4': return 'revenue'
    elif first == '5': return 'expense'
    else: return 'unknown'

def get_cost_center_balance(center_id, from_date=None, to_date=None):
    conn = get_connection()
    query = """
        SELECT 
            COALESCE(SUM(CASE WHEN jl.debit > 0 THEN cca.amount ELSE 0 END),0) as total_debit,
            COALESCE(SUM(CASE WHEN jl.credit > 0 THEN cca.amount ELSE 0 END),0) as total_credit
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE cca.cost_center_id = ?
    """
    params = [center_id]
    if from_date: query += " AND je.date >= ?"; params.append(from_date)
    if to_date: query += " AND je.date <= ?"; params.append(to_date)
    res = conn.execute(query, params).fetchone()
    conn.close()
    if res:
        return {'total_debit': res['total_debit'] or 0, 'total_credit': res['total_credit'] or 0, 'net': (res['total_debit'] or 0) - (res['total_credit'] or 0)}
    return {'total_debit': 0, 'total_credit': 0, 'net': 0}

def get_cost_center_income_statement(center_id, from_date, to_date):
    """قائمة دخل تستخدم الكود لتصنيف الحسابات"""
    conn = get_connection()
    # نحضر السطور المجمعة حسب الحساب
    query = """
        SELECT 
            a.code as account_code, a.name as account_name,
            COALESCE(SUM(jl.debit),0) as total_debit,
            COALESCE(SUM(jl.credit),0) as total_credit
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN accounts a ON a.name = jl.account_name
        WHERE cca.cost_center_id = ? AND je.date BETWEEN ? AND ?
        GROUP BY a.code, a.name
        ORDER BY a.code
    """
    rows = conn.execute(query, (center_id, from_date, to_date)).fetchall()
    conn.close()
    
    income = 0.0
    expenses = 0.0
    details = []
    for r in rows:
        code = r['account_code'] or ''
        ac_type = _account_type_from_code(code)
        net = r['total_credit'] - r['total_debit'] if ac_type in ('revenue','equity','liability') else r['total_debit'] - r['total_credit']
        if ac_type == 'revenue':
            income += net
        elif ac_type == 'expense':
            expenses += net
        details.append({
            'account_code': code,
            'account_name': r['account_name'],
            'account_type': ac_type,
            'debit': r['total_debit'],
            'credit': r['total_credit'],
            'net': net
        })
    return {'income': income, 'expenses': expenses, 'net_profit': income - expenses, 'details': details}

def get_cost_center_trial_balance(center_id, from_date=None, to_date=None):
    conn = get_connection()
    query = """
        SELECT 
            a.code as account_code, a.name as account_name,
            COALESCE(SUM(jl.debit),0) as total_debit,
            COALESCE(SUM(jl.credit),0) as total_credit
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN accounts a ON a.name = jl.account_name
        WHERE cca.cost_center_id = ?
    """
    params = [center_id]
    if from_date: query += " AND je.date >= ?"; params.append(from_date)
    if to_date: query += " AND je.date <= ?"; params.append(to_date)
    query += " GROUP BY a.code, a.name ORDER BY a.code"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        ac_type = _account_type_from_code(r['account_code'] or '')
        balance = r['total_debit'] - r['total_credit'] if ac_type in ('asset','expense') else r['total_credit'] - r['total_debit']
        result.append({
            'account_code': r['account_code'],
            'account_name': r['account_name'],
            'account_type': ac_type,
            'total_debit': r['total_debit'],
            'total_credit': r['total_credit'],
            'balance': balance
        })
    return result

def get_all_centers_summary(from_date=None, to_date=None):
    conn = get_connection()
    query = """
        SELECT cc.id as center_id, cc.code as center_code, cc.name as center_name,
               COUNT(DISTINCT jl.id) as transaction_count,
               COALESCE(SUM(cca.amount),0) as total_allocated
        FROM cost_centers cc
        LEFT JOIN cost_center_allocations cca ON cc.id = cca.cost_center_id
        LEFT JOIN journal_lines jl ON cca.journal_line_id = jl.id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id
        WHERE cc.is_active = 1
    """
    params = []
    if from_date: query += " AND (je.date >= ? OR je.date IS NULL)"; params.append(from_date)
    if to_date: query += " AND (je.date <= ? OR je.date IS NULL)"; params.append(to_date)
    query += " GROUP BY cc.id, cc.code, cc.name ORDER BY total_allocated DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===================== موازنات (مُصححة) =====================
def set_budget(cost_center_id, account_id, fiscal_year, amount):
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO cost_center_budgets (cost_center_id, account_id, fiscal_year, budget_amount) 
                      VALUES (?,?,?,?) ON CONFLICT(cost_center_id, account_id, fiscal_year) DO UPDATE SET budget_amount = ?""",
                     (cost_center_id, account_id, fiscal_year, amount, amount))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback(); raise e
    finally: conn.close()

def get_budget_variance(cost_center_id, fiscal_year, as_of_month=None):
    conn = get_connection()
    date_cond = "strftime('%Y', je.date) = CAST(? AS TEXT)"
    params = [fiscal_year]
    if as_of_month:
        date_cond += " AND strftime('%m', je.date) <= ?"
        params.append(str(as_of_month).zfill(2))
    # نستخدم كود الحساب لتحديد الطبيعة
    query = f"""
        SELECT a.code as account_code, a.name as account_name, b.budget_amount,
               COALESCE(SUM(CASE WHEN SUBSTR(a.code,1,1) IN ('1','5') THEN jl.debit - jl.credit
                                  ELSE jl.credit - jl.debit END),0) as actual
        FROM cost_center_budgets b
        JOIN accounts a ON b.account_id = a.id
        LEFT JOIN cost_center_allocations cca ON cca.cost_center_id = b.cost_center_id
             AND cca.journal_line_id IN (
                 SELECT jl2.id FROM journal_lines jl2
                 JOIN journal_entries je2 ON jl2.entry_id = je2.id
                 WHERE {date_cond}
             )
        LEFT JOIN journal_lines jl ON jl.id = cca.journal_line_id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id
        WHERE b.cost_center_id = ? AND b.fiscal_year = ? AND b.budget_amount != 0
        GROUP BY a.code, a.name, b.budget_amount
        ORDER BY a.code
    """
    params.extend([cost_center_id, fiscal_year])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    total_budget = 0; total_actual = 0
    for r in rows:
        variance = r['actual'] - r['budget_amount']
        pct = (variance/r['budget_amount']*100) if r['budget_amount'] else 0
        ac_code = r['account_code'] or ''
        ac_type = _account_type_from_code(ac_code)
        result.append({
            'account_code': ac_code,
            'account_name': r['account_name'],
            'account_type': ac_type,
            'budget': r['budget_amount'],
            'actual': r['actual'],
            'variance': variance,
            'variance_pct': round(pct,2),
            'status': 'favourable' if ((ac_type in ('revenue','income') and variance>0) or (ac_type in ('expense','cost_of_sales') and variance<0)) else 'unfavourable'
        })
        total_budget += r['budget_amount']
        total_actual += r['actual']
    return {
        'details': result,
        'total_budget': total_budget,
        'total_actual': total_actual,
        'total_variance': total_actual - total_budget,
        'total_variance_pct': round((total_actual-total_budget)/total_budget*100,2) if total_budget else 0
    }

# ... (باقي الدوال: توزيعات، موازنات، إلخ)
