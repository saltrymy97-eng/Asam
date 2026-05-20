# services/accounting_service.py - منطق الحسابات وقيود اليومية (إصدار محسن)
import sqlite3
from datetime import date

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
    
    # إذا كان رقماً (كود)، أرجعه كما هو
    if account_input.isdigit():
        return account_input
    
    conn = get_conn()
    
    # 🔍 البحث بطرق متعددة لضمان الوصول للحساب
    row = conn.execute(
        "SELECT code FROM accounts WHERE name = ? OR name LIKE ? OR code = ?",
        (account_input, f"%{account_input}%", account_input)
    ).fetchone()
    
    conn.close()
    
    if row:
        return row["code"]
    
    # 🆕 تحقق إضافي: إذا كان الإدخال يبدأ برقم (مثلاً "1-الأصول")
    if account_input[0].isdigit():
        code_part = account_input.split("-")[0].strip()
        if code_part.isdigit():
            return code_part
    
    return None

def save_journal_entry(description, lines, entry_date=None):
    """حفظ قيد يومية جديد وإرجاع (entry_id, error_message)"""
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")
    
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (entry_date, description, "")
        )
        entry_id = cur.lastrowid
        
        for line in lines:
            # 🔍 محاولة أخيرة لتحويل الاسم إلى كود قبل الحفظ
            account_name = line["account"]
            if not account_name.isdigit():
                code = get_account_code(account_name)
                if code:
                    account_name = code
            
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                (entry_id, account_name, line["debit"], line["credit"])
            )
        
        conn.commit()
        return entry_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
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
    """تفاصيل قيد محدد"""
    conn = get_conn()
    lines = conn.execute(
        "SELECT account_name, debit, credit FROM journal_lines WHERE entry_id = ?",
        (entry_id,)
    ).fetchall()
    conn.close()
    return [dict(l) for l in lines]

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
