import sqlite3
from datetime import datetime
import database

def get_connection():
    return database.get_connection()

# ===================== إدارة مراكز التكلفة =====================

def create_cost_center(code, name, parent_id=None):
    """إضافة مركز تكلفة جديد (يدعم الشجرة)"""
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
    """تحديث بيانات مركز تكلفة"""
    conn = get_connection()
    fields = []
    values = []
    if code:
        fields.append("code = ?")
        values.append(code)
    if name:
        fields.append("name = ?")
        values.append(name)
    if parent_id is not None:
        fields.append("parent_id = ?")
        values.append(parent_id)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(is_active)
    if not fields:
        return
    values.append(center_id)
    conn.execute(f"UPDATE cost_centers SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()

def get_all_cost_centers(active_only=True):
    """جلب جميع مراكز التكلفة (مفيدة للـ dropdown)"""
    conn = get_connection()
    query = "SELECT id, code, name, parent_id, is_active FROM cost_centers"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY code"
    centers = conn.execute(query).fetchall()
    conn.close()
    return centers

def get_cost_center_tree():
    """جلب المراكز كهيكل شجري للعرض"""
    centers = get_all_cost_centers(active_only=False)
    # تحويل إلى dict مع children
    tree = {}
    for c in centers:
        tree[c['id']] = {**c, 'children': []}
    roots = []
    for c in centers:
        if c['parent_id'] and c['parent_id'] in tree:
            tree[c['parent_id']]['children'].append(tree[c['id']])
        else:
            roots.append(tree[c['id']])
    return roots

# ===================== توزيع القيود على المراكز =====================

def allocate_journal_line(journal_line_id, allocations):
    """
    توزيع مبلغ سطر قيد على مراكز تكلفة.
    allocations: قائمة من dict {cost_center_id, amount, percentage?}
    """
    conn = get_connection()
    try:
        # التحقق من أن مجموع التوزيعات يساوي مبلغ السطر (اختياري)
        cursor = conn.cursor()
        for alloc in allocations:
            cursor.execute(
                "INSERT INTO cost_center_allocations (journal_line_id, cost_center_id, amount, percentage) VALUES (?, ?, ?, ?)",
                (journal_line_id, alloc['cost_center_id'], alloc['amount'], alloc.get('percentage'))
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_allocations_for_entry(journal_entry_id):
    """جلب توزيعات كل سطور قيد معين"""
    conn = get_connection()
    query = """
        SELECT jl.id as line_id, jl.account_id, a.name as account_name,
               cca.cost_center_id, cc.name as center_name, cca.amount, cca.percentage
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN cost_centers cc ON cca.cost_center_id = cc.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE jl.journal_entry_id = ?
    """
    result = conn.execute(query, (journal_entry_id,)).fetchall()
    conn.close()
    return result

# ===================== تقارير مراكز التكلفة =====================

def get_cost_center_balance(center_id, from_date=None, to_date=None):
    """
    رصيد مركز تكلفة (مجموع debit - credit) من القيود المرحلة له.
    يمكن تصفيته بتاريخ.
    """
    conn = get_connection()
    query = """
        SELECT 
            SUM(CASE WHEN jl.debit > 0 THEN cca.amount ELSE 0 END) as total_debit,
            SUM(CASE WHEN jl.credit > 0 THEN cca.amount ELSE 0 END) as total_credit
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        WHERE cca.cost_center_id = ?
    """
    params = [center_id]
    if from_date:
        query += " AND je.entry_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND je.entry_date <= ?"
        params.append(to_date)
    result = conn.execute(query, params).fetchone()
    conn.close()
    if result:
        return {
            'total_debit': result['total_debit'] or 0,
            'total_credit': result['total_credit'] or 0,
            'net': (result['total_debit'] or 0) - (result['total_credit'] or 0)
        }
    return {'total_debit': 0, 'total_credit': 0, 'net': 0}

def get_cost_center_income_statement(center_id, from_date, to_date):
    """
    قائمة دخل مبسطة لمركز تكلفة (إيرادات - مصروفات).
    تعتمد على تصنيف الحسابات (account_type) في جدول accounts.
    """
    conn = get_connection()
    query = """
        SELECT a.account_type,
               SUM(CASE WHEN jl.debit > 0 THEN cca.amount ELSE 0 END) as debit_sum,
               SUM(CASE WHEN jl.credit > 0 THEN cca.amount ELSE 0 END) as credit_sum
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE cca.cost_center_id = ? AND je.entry_date BETWEEN ? AND ?
        GROUP BY a.account_type
    """
    rows = conn.execute(query, (center_id, from_date, to_date)).fetchall()
    conn.close()
    
    income = 0
    expenses = 0
    for r in rows:
        if r['account_type'] in ('revenue', 'income'):
            income += (r['credit_sum'] - r['debit_sum'])  # الإيرادات طبيعتها دائنة
        elif r['account_type'] in ('expense', 'cost_of_sales'):
            expenses += (r['debit_sum'] - r['credit_sum'])  # المصروفات مدينة
    return {
        'income': income,
        'expenses': expenses,
        'net_profit': income - expenses
    }

# ===================== موازنات المراكز (اختياري) =====================

def set_budget(cost_center_id, account_id, fiscal_year, amount):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO cost_center_budgets (cost_center_id, account_id, fiscal_year, budget_amount) VALUES (?, ?, ?, ?)",
        (cost_center_id, account_id, fiscal_year, amount)
    )
    conn.commit()
    conn.close()

def get_budget_variance(cost_center_id, fiscal_year):
    """مقارنة فعلي مقابل موازنة"""
    conn = get_connection()
    # ببساطة: نجلب الموازنة والفعلي (يمكن تحسينها)
    query = """
        SELECT a.name, b.budget_amount,
               COALESCE(SUM(CASE WHEN jl.debit > 0 THEN cca.amount ELSE -cca.amount END), 0) as actual
        FROM cost_center_budgets b
        JOIN accounts a ON b.account_id = a.id
        LEFT JOIN cost_center_allocations cca ON cca.cost_center_id = b.cost_center_id
        LEFT JOIN journal_lines jl ON jl.id = cca.journal_line_id
        LEFT JOIN journal_entries je ON jl.journal_entry_id = je.id AND strftime('%Y', je.entry_date) = ?
        WHERE b.cost_center_id = ? AND b.fiscal_year = ?
        GROUP BY b.id
    """
    rows = conn.execute(query, (str(fiscal_year), cost_center_id, fiscal_year)).fetchall()
    conn.close()
    return rows
