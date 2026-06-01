# services/accounting_service.py - منطق الحسابات وقيود اليومية (مع إدارة العمليات ومراكز التكلفة)
import sqlite3
from datetime import date
from services import cost_center_service

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_code(account_input):
    """تحويل اسم الحساب إلى كود، أو إرجاع الكود إذا كان رقماً"""
    if not account_input or not account_input.strip():
        return None
    
    account_input = account_input.strip()
    
    if account_input.isdigit():
        return account_input
    
    conn = get_conn()
    
    row = conn.execute(
        "SELECT code FROM accounts WHERE name = ? OR name LIKE ? OR code = ?",
        (account_input, f"%{account_input}%", account_input)
    ).fetchone()
    
    conn.close()
    
    if row:
        return row["code"]
    
    if account_input[0].isdigit():
        code_part = account_input.split("-")[0].strip()
        if code_part.isdigit():
            return code_part
    
    return None

def save_journal_entry(description, lines, entry_date=None, cost_center_allocations=None):
    """
    حفظ قيد يومية جديد مع إدارة العمليات ودعم مراكز التكلفة
    
    Parameters:
    - description: وصف القيد
    - lines: قائمة من dict تحتوي على account, debit, credit
    - entry_date: تاريخ القيد (اختياري، الافتراضي اليوم)
    - cost_center_allocations: قائمة اختيارية لتوزيعات مراكز التكلفة
      مثال: [{'line_index': 0, 'allocations': [{'cost_center_id': 1, 'amount': 500, 'percentage': 100}]}]
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")
    
    conn = get_conn()
    try:
        conn.execute("BEGIN")  # بداية العملية المحمية
        
        # إدخال رأس القيد - نستخدم "date" وليس "entry_date" كما في جدول journal_entries الفعلي
        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (entry_date, description, "")
        )
        entry_id = cur.lastrowid
        
        line_ids = []  # لتخزين معرفات الأسطر المُنشأة
        
        for idx, line in enumerate(lines):
            account_name = line["account"]
            if not account_name.isdigit():
                code = get_account_code(account_name)
                if code:
                    account_name = code
            
            cur_line = conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                (entry_id, account_name, line["debit"], line["credit"])
            )
            line_ids.append(cur_line.lastrowid)
        
        # معالجة توزيعات مراكز التكلفة إن وُجدت
        if cost_center_allocations:
            for alloc_entry in cost_center_allocations:
                line_index = alloc_entry.get('line_index', 0)
                if line_index < len(line_ids):
                    journal_line_id = line_ids[line_index]
                    allocations = alloc_entry.get('allocations', [])
                    if allocations:
                        cost_center_service.allocate_journal_line(journal_line_id, allocations)
        
        conn.commit()  # حفظ نهائي
        return entry_id, None
    except Exception as e:
        conn.rollback()  # إلغاء كل شيء عند الفشل
        return None, str(e)
    finally:
        conn.close()

def update_journal_entry(entry_id, description, lines, entry_date=None, cost_center_allocations=None):
    """
    تحديث قيد موجود - يحذف السطور القديمة ويعيد إدراجها مع التوزيعات الجديدة
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")
    
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        
        # تحديث رأس القيد
        conn.execute(
            "UPDATE journal_entries SET date = ?, description = ? WHERE id = ?",
            (entry_date, description, entry_id)
        )
        
        # حذف السطور القديمة (ستحذف التوزيعات تلقائياً إذا كان هناك foreign key مع CASCADE، وإلا نحذف يدوياً)
        old_lines = conn.execute("SELECT id FROM journal_lines WHERE entry_id = ?", (entry_id,)).fetchall()
        for ol in old_lines:
            conn.execute("DELETE FROM cost_center_allocations WHERE journal_line_id = ?", (ol['id'],))
        conn.execute("DELETE FROM journal_lines WHERE entry_id = ?", (entry_id,))
        
        # إعادة إدراج السطور
        line_ids = []
        for idx, line in enumerate(lines):
            account_name = line["account"]
            if not account_name.isdigit():
                code = get_account_code(account_name)
                if code:
                    account_name = code
            
            cur_line = conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                (entry_id, account_name, line["debit"], line["credit"])
            )
            line_ids.append(cur_line.lastrowid)
        
        # إعادة التوزيعات
        if cost_center_allocations:
            for alloc_entry in cost_center_allocations:
                line_index = alloc_entry.get('line_index', 0)
                if line_index < len(line_ids):
                    journal_line_id = line_ids[line_index]
                    allocations = alloc_entry.get('allocations', [])
                    if allocations:
                        cost_center_service.allocate_journal_line(journal_line_id, allocations)
        
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_recent_entries(limit=10):
    """آخر قيود اليومية"""
    conn = get_conn()
    entries = conn.execute(
        "SELECT id, date, description, reference FROM journal_entries ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(e) for e in entries]

def get_entry_details(entry_id):
    """تفاصيل قيد محدد مع توزيعات مراكز التكلفة"""
    conn = get_conn()
    lines = conn.execute(
        "SELECT id, account_name, debit, credit FROM journal_lines WHERE entry_id = ?",
        (entry_id,)
    ).fetchall()
    
    result = []
    for l in lines:
        line_dict = dict(l)
        # جلب توزيعات مراكز التكلفة لهذا السطر
        allocations = conn.execute("""
            SELECT cca.id, cca.cost_center_id, cc.name as center_name, cc.code as center_code,
                   cca.amount, cca.percentage
            FROM cost_center_allocations cca
            JOIN cost_centers cc ON cca.cost_center_id = cc.id
            WHERE cca.journal_line_id = ?
        """, (l['id'],)).fetchall()
        line_dict['cost_center_allocations'] = [dict(a) for a in allocations] if allocations else []
        result.append(line_dict)
    
    conn.close()
    return result

def get_ledger(account_name):
    """دفتر الأستاذ لحساب محدد"""
    conn = get_conn()
    ledger = conn.execute("""
        SELECT je.date, je.description, jl.debit, jl.credit
        FROM journal_lines jl
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE jl.account_name = ?
        ORDER BY je.date, je.id
    """, (account_name,)).fetchall()
    conn.close()
    return [dict(l) for l in ledger]

def get_trial_balance():
    """ميزان المراجعة"""
    conn = get_conn()
    tb = conn.execute("""
        SELECT account_name,
               SUM(debit) as total_debit,
               SUM(credit) as total_credit
        FROM journal_lines
        GROUP BY account_name
        ORDER BY account_name
    """).fetchall()
    conn.close()
    return [dict(t) for t in tb]

def get_distinct_accounts():
    """جميع الحسابات المستخدمة في القيود"""
    conn = get_conn()
    accounts = conn.execute(
        "SELECT DISTINCT account_name FROM journal_lines ORDER BY account_name"
    ).fetchall()
    conn.close()
    return [a["account_name"] for a in accounts]

def get_entry_with_allocations(entry_id):
    """جلب القيد كاملاً مع توزيعات مراكز التكلفة (استدعاء للخدمة المخصصة)"""
    return cost_center_service.get_allocations_for_entry(entry_id)
