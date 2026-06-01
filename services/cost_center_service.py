import sqlite3
from datetime import datetime
import database

def get_connection():
    """إنشاء اتصال مع دعم أسماء الأعمدة"""
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row   # هذا السطر يحل الخطأ
    return conn

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

def delete_cost_center(center_id):
    """
    حذف مركز تكلفة (فقط إذا لم يكن لديه أبناء أو توزيعات مرتبطة)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # التحقق من عدم وجود أبناء
        children = cursor.execute(
            "SELECT COUNT(*) as cnt FROM cost_centers WHERE parent_id = ?", (center_id,)
        ).fetchone()
        if children['cnt'] > 0:
            raise ValueError("لا يمكن حذف المركز لأن لديه مراكز فرعية. احذفها أولاً.")
        
        # التحقق من عدم وجود توزيعات مرتبطة
        allocations = cursor.execute(
            "SELECT COUNT(*) as cnt FROM cost_center_allocations WHERE cost_center_id = ?", (center_id,)
        ).fetchone()
        if allocations['cnt'] > 0:
            raise ValueError("لا يمكن حذف المركز لأن لديه توزيعات محاسبية مرتبطة. قم بإلغاء التوزيعات أولاً.")
        
        cursor.execute("DELETE FROM cost_centers WHERE id = ?", (center_id,))
        conn.commit()
        return True
    except ValueError:
        raise
    except Exception as e:
        conn.rollback()
        raise e
    finally:
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
    if not centers:
        return []
    
    tree = {}
    for c in centers:
        tree[c['id']] = {**dict(c), 'children': []}
    
    roots = []
    for c in centers:
        if c['parent_id'] and c['parent_id'] in tree:
            tree[c['parent_id']]['children'].append(tree[c['id']])
        else:
            roots.append(tree[c['id']])
    return roots

def get_cost_center_by_id(center_id):
    """جلب بيانات مركز واحد"""
    conn = get_connection()
    center = conn.execute(
        "SELECT id, code, name, parent_id, is_active FROM cost_centers WHERE id = ?",
        (center_id,)
    ).fetchone()
    conn.close()
    return center

# ===================== توزيع القيود على المراكز =====================

def allocate_journal_line(journal_line_id, allocations):
    """
    توزيع مبلغ سطر قيد على مراكز تكلفة.
    allocations: قائمة من dict {cost_center_id, amount, percentage?}
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM cost_center_allocations WHERE journal_line_id = ?",
            (journal_line_id,)
        )
        
        for alloc in allocations:
            center = cursor.execute(
                "SELECT id FROM cost_centers WHERE id = ? AND is_active = 1",
                (alloc['cost_center_id'],)
            ).fetchone()
            if not center:
                raise ValueError(f"مركز التكلفة {alloc['cost_center_id']} غير موجود أو غير نشط")
            
            cursor.execute(
                "INSERT INTO cost_center_allocations (journal_line_id, cost_center_id, amount, percentage) VALUES (?, ?, ?, ?)",
                (journal_line_id, alloc['cost_center_id'], alloc['amount'], alloc.get('percentage'))
            )
        conn.commit()
        return True
    except ValueError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_allocations_for_entry(journal_entry_id):
    """جلب توزيعات كل سطور قيد معين - متوافق مع account_name"""
    conn = get_connection()
    query = """
        SELECT jl.id as line_id, jl.account_name, 
               a.code as account_code, a.name as account_name_display,
               jl.debit, jl.credit,
               cca.cost_center_id, cc.name as center_name, cc.code as center_code, 
               cca.amount, cca.percentage
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN cost_centers cc ON cca.cost_center_id = cc.id
        LEFT JOIN accounts a ON a.name = jl.account_name
        WHERE jl.entry_id = ?
        ORDER BY jl.id, cc.code
    """
    result = conn.execute(query, (journal_entry_id,)).fetchall()
    conn.close()
    return result

def get_allocations_for_line(journal_line_id):
    """جلب توزيعات سطر قيد واحد"""
    conn = get_connection()
    query = """
        SELECT cca.id, cca.cost_center_id, cc.name as center_name, cc.code as center_code,
               cca.amount, cca.percentage
        FROM cost_center_allocations cca
        JOIN cost_centers cc ON cca.cost_center_id = cc.id
        WHERE cca.journal_line_id = ?
        ORDER BY cc.code
    """
    result = conn.execute(query, (journal_line_id,)).fetchall()
    conn.close()
    return result

def delete_allocation(allocation_id):
    """حذف توزيع واحد"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM cost_center_allocations WHERE id = ?", (allocation_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ===================== تقارير مراكز التكلفة =====================

def get_cost_center_balance(center_id, from_date=None, to_date=None):
    """
    رصيد مركز تكلفة (مجموع debit - credit) من القيود المرحلة له.
    """
    conn = get_connection()
    query = """
        SELECT 
            COALESCE(SUM(CASE WHEN jl.debit > 0 THEN cca.amount ELSE 0 END), 0) as total_debit,
            COALESCE(SUM(CASE WHEN jl.credit > 0 THEN cca.amount ELSE 0 END), 0) as total_credit
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE cca.cost_center_id = ?
    """
    params = [center_id]
    if from_date:
        query += " AND je.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND je.date <= ?"
        params.append(to_date)
    
    result = conn.execute(query, params).fetchone()
    conn.close()
    
    total_debit = result['total_debit'] or 0
    total_credit = result['total_credit'] or 0
    
    return {
        'total_debit': total_debit,
        'total_credit': total_credit,
        'net': total_debit - total_credit
    }

def get_cost_center_income_statement(center_id, from_date, to_date):
    """
    قائمة دخل محسّنة لمركز تكلفة (إيرادات - مصروفات).
    تعتمد على وجود عمود account_type في جدول accounts.
    """
    conn = get_connection()
    query = """
        SELECT 
            a.code as account_code,
            a.name as account_name,
            a.account_type,
            COALESCE(SUM(jl.debit), 0) as total_debit,
            COALESCE(SUM(jl.credit), 0) as total_credit,
            COALESCE(SUM(cca.amount), 0) as allocated_amount
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN accounts a ON a.name = jl.account_name
        WHERE cca.cost_center_id = ? 
          AND je.date BETWEEN ? AND ?
        GROUP BY a.code, a.name, a.account_type
        ORDER BY a.code
    """
    rows = conn.execute(query, (center_id, from_date, to_date)).fetchall()
    conn.close()
    
    income = 0
    expenses = 0
    details = []
    
    for r in rows:
        account_type = r['account_type'] or ''
        if account_type in ('revenue', 'income'):
            net = r['total_credit'] - r['total_debit']
            income += net
        elif account_type in ('expense', 'cost_of_sales'):
            net = r['total_debit'] - r['total_credit']
            expenses += net
        else:
            net = r['total_debit'] - r['total_credit']
        
        details.append({
            'account_code': r['account_code'],
            'account_name': r['account_name'],
            'account_type': account_type,
            'debit': r['total_debit'],
            'credit': r['total_credit'],
            'net': net,
            'allocated': r['allocated_amount']
        })
    
    return {
        'income': income,
        'expenses': expenses,
        'net_profit': income - expenses,
        'details': details
    }

def get_cost_center_trial_balance(center_id, from_date=None, to_date=None):
    """
    ميزان مراجعة لمركز تكلفة واحد - يستخدم account_type إن وجد.
    """
    conn = get_connection()
    query = """
        SELECT 
            a.code as account_code,
            a.name as account_name,
            a.account_type,
            COALESCE(SUM(jl.debit), 0) as total_debit,
            COALESCE(SUM(jl.credit), 0) as total_credit,
            CASE 
                WHEN a.account_type IN ('asset', 'expense', 'cost_of_sales') 
                    THEN COALESCE(SUM(jl.debit), 0) - COALESCE(SUM(jl.credit), 0)
                ELSE COALESCE(SUM(jl.credit), 0) - COALESCE(SUM(jl.debit), 0)
            END as balance
        FROM journal_lines jl
        JOIN cost_center_allocations cca ON jl.id = cca.journal_line_id
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN accounts a ON a.name = jl.account_name
        WHERE cca.cost_center_id = ?
    """
    params = [center_id]
    if from_date:
        query += " AND je.date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND je.date <= ?"
        params.append(to_date)
    
    query += " GROUP BY a.code, a.name, a.account_type ORDER BY a.code"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows

def get_all_centers_summary(from_date=None, to_date=None):
    """
    ملخص جميع مراكز التكلفة - للمقارنة بين المراكز
    """
    conn = get_connection()
    query = """
        SELECT 
            cc.id as center_id,
            cc.code as center_code,
            cc.name as center_name,
            COUNT(DISTINCT jl.id) as transaction_count,
            COALESCE(SUM(cca.amount), 0) as total_allocated
        FROM cost_centers cc
        LEFT JOIN cost_center_allocations cca ON cc.id = cca.cost_center_id
        LEFT JOIN journal_lines jl ON cca.journal_line_id = jl.id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id
        WHERE cc.is_active = 1
    """
    params = []
    if from_date:
        query += " AND (je.date >= ? OR je.date IS NULL)"
        params.append(from_date)
    if to_date:
        query += " AND (je.date <= ? OR je.date IS NULL)"
        params.append(to_date)
    
    query += " GROUP BY cc.id, cc.code, cc.name ORDER BY total_allocated DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows

# ===================== موازنات المراكز =====================

def set_budget(cost_center_id, account_id, fiscal_year, amount):
    """
    إضافة أو تحديث موازنة لحساب معين داخل مركز تكلفة لسنة مالية
    """
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO cost_center_budgets (cost_center_id, account_id, fiscal_year, budget_amount) 
               VALUES (?, ?, ?, ?)
               ON CONFLICT(cost_center_id, account_id, fiscal_year) 
               DO UPDATE SET budget_amount = ?""",
            (cost_center_id, account_id, fiscal_year, amount, amount)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_budget_variance(cost_center_id, fiscal_year, as_of_month=None):
    """
    مقارنة فعلي مقابل موازنة - تراعي طبيعة الحساب.
    تحتاج إلى account_type في جدول accounts.
    """
    conn = get_connection()
    
    date_condition = "strftime('%Y', je.date) = CAST(? AS TEXT)"
    params = [fiscal_year]
    
    if as_of_month:
        date_condition += " AND strftime('%m', je.date) <= ?"
        params.append(str(as_of_month).zfill(2))
    
    query = f"""
        SELECT 
            a.code as account_code,
            a.name as account_name,
            a.account_type,
            b.budget_amount,
            COALESCE(
                SUM(
                    CASE 
                        WHEN a.account_type IN ('expense', 'cost_of_sales', 'asset') 
                            THEN (jl.debit - jl.credit)
                        WHEN a.account_type IN ('revenue', 'income', 'liability', 'equity') 
                            THEN (jl.credit - jl.debit)
                        ELSE (jl.debit - jl.credit)
                    END
                ), 0
            ) as actual
        FROM cost_center_budgets b
        JOIN accounts a ON b.account_id = a.id
        LEFT JOIN cost_center_allocations cca 
            ON cca.cost_center_id = b.cost_center_id 
            AND cca.journal_line_id IN (
                SELECT jl2.id FROM journal_lines jl2
                JOIN journal_entries je2 ON jl2.entry_id = je2.id
                WHERE {date_condition}
            )
        LEFT JOIN journal_lines jl ON jl.id = cca.journal_line_id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id
        WHERE b.cost_center_id = ? 
          AND b.fiscal_year = ?
          AND b.budget_amount != 0
        GROUP BY a.code, a.name, a.account_type, b.budget_amount
        ORDER BY a.code
    """
    
    params.extend([cost_center_id, fiscal_year])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    result = []
    total_budget = 0
    total_actual = 0
    
    for r in rows:
        variance = r['actual'] - r['budget_amount']
        variance_pct = (variance / r['budget_amount'] * 100) if r['budget_amount'] != 0 else 0
        
        result.append({
            'account_code': r['account_code'],
            'account_name': r['account_name'],
            'account_type': r['account_type'],
            'budget': r['budget_amount'],
            'actual': r['actual'],
            'variance': variance,
            'variance_pct': round(variance_pct, 2),
            'status': 'favourable' if ((r['account_type'] in ('revenue', 'income') and variance > 0) or 
                                       (r['account_type'] in ('expense', 'cost_of_sales') and variance < 0))
                      else 'unfavourable'
        })
        
        total_budget += r['budget_amount']
        total_actual += r['actual']
    
    return {
        'details': result,
        'total_budget': total_budget,
        'total_actual': total_actual,
        'total_variance': total_actual - total_budget,
        'total_variance_pct': round((total_actual - total_budget) / total_budget * 100, 2) if total_budget != 0 else 0
    }

def get_budgets_for_center(cost_center_id, fiscal_year=None):
    """جلب الموازنات المسجلة لمركز تكلفة"""
    conn = get_connection()
    query = """
        SELECT b.id, b.cost_center_id, b.account_id, 
               a.code as account_code, a.name as account_name, a.account_type,
               b.fiscal_year, b.budget_amount
        FROM cost_center_budgets b
        JOIN accounts a ON b.account_id = a.id
        WHERE b.cost_center_id = ?
    """
    params = [cost_center_id]
    if fiscal_year:
        query += " AND b.fiscal_year = ?"
        params.append(fiscal_year)
    
    query += " ORDER BY a.code"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows

def delete_budget(budget_id):
    """حذف موازنة"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM cost_center_budgets WHERE id = ?", (budget_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ===================== دوال مساعدة =====================

def get_center_transactions(center_id, limit=50):
    """جلب آخر المعاملات المالية على مركز تكلفة"""
    conn = get_connection()
    query = """
        SELECT 
            je.id as entry_id,
            je.date as entry_date,
            je.description as entry_description,
            jl.id as line_id,
            jl.description as line_description,
            a.code as account_code,
            jl.account_name,
            jl.debit,
            jl.credit,
            cca.amount as allocated_amount
        FROM cost_center_allocations cca
        JOIN journal_lines jl ON cca.journal_line_id = jl.id
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN accounts a ON a.name = jl.account_name
        WHERE cca.cost_center_id = ?
        ORDER BY je.date DESC, je.id DESC
        LIMIT ?
    """
    rows = conn.execute(query, (center_id, limit)).fetchall()
    conn.close()
    return rows

def validate_allocation_total(line_amount, allocations):
    """التحقق من أن مجموع التوزيعات يساوي مبلغ السطر"""
    total = sum(a['amount'] for a in allocations)
    return abs(total - line_amount) < 0.01, total
