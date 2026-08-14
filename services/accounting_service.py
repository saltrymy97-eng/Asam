# services/accounting_service.py - منطق الحسابات وقيود اليومية (مع دعم الاتصال الخارجي – إصدار احترافي)
import sqlite3
import uuid
import os
from datetime import date
from services import cost_center_service
from services.currency_service import get_base_currency, get_exchange_rate
from services.period_service import is_period_closed

DB_PATH = os.path.join("data", "erp.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_code(account_input, conn=None):
    """تحويل اسم الحساب إلى كود، أو إرجاع الكود إذا كان رقماً (يدعم اتصال خارجي)"""
    if not account_input or not account_input.strip():
        return None
    
    account_input = account_input.strip()
    
    if account_input.isdigit():
        return account_input
    
    own_conn = False
    if conn is None:
        conn = get_conn()
        own_conn = True
    
    row = conn.execute(
        "SELECT code FROM accounts WHERE name = ? OR name LIKE ? OR code = ?",
        (account_input, f"%{account_input}%", account_input)
    ).fetchone()
    
    if own_conn:
        conn.close()
    
    if row:
        return row["code"]
    
    if account_input[0].isdigit():
        code_part = account_input.split("-")[0].strip()
        if code_part.isdigit():
            return code_part
    
    return None

def save_journal_entry(description, lines, entry_date=None, cost_center_allocations=None, conn=None, skip_period_check=False):
    """
    حفظ قيد يومية جديد.
    إذا تم تمرير conn خارجي، لا يتم إنشاء معاملة منفصلة (المعاملة تدار خارجياً).
    skip_period_check: إذا كان True، يتم تخطي التحقق من الفترات المغلقة.
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")
    
    # ✅ التحقق مما إذا كانت الفترة مغلقة (إلا إذا كان الطلب يتطلب تخطي الفحص)
    if not skip_period_check and is_period_closed(entry_date):
        return None, f"لا يمكن حفظ القيد في فترة مغلقة: {entry_date}. يرجى فتح الفترة أولاً."
    
    base_currency = get_base_currency()
    base_code = base_currency['code'] if base_currency else 'YER'
    
    own_conn = False
    if conn is None:
        conn = get_conn()
        own_conn = True
    
    try:
        if own_conn:
            conn.execute("BEGIN")
        
        # ✅ مرجع فريد احترافي لكل قيد
        reference = f"ENT-{entry_date}-{uuid.uuid4().hex[:8]}"
        
        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (entry_date, description, reference)
        )
        entry_id = cur.lastrowid
        
        line_ids = []
        for idx, line in enumerate(lines):
            account_name = line["account"]
            if not account_name.isdigit():
                # تمرير نفس الاتصال لتجنب فتح اتصال جديد
                code = get_account_code(account_name, conn)
                if code:
                    account_name = code
            
            currency_code = line.get("currency_code", base_code)
            exchange_rate = line.get("exchange_rate", 1.0)
            if currency_code != base_code and exchange_rate == 1.0:
                fetched_rate = get_exchange_rate(currency_code, base_code)
                if fetched_rate:
                    exchange_rate = fetched_rate
            
            cur_line = conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, account_name, line["debit"], line["credit"], currency_code, exchange_rate)
            )
            line_ids.append(cur_line.lastrowid)
        
        if cost_center_allocations:
            for alloc_entry in cost_center_allocations:
                line_index = alloc_entry.get('line_index', 0)
                if line_index < len(line_ids):
                    journal_line_id = line_ids[line_index]
                    allocations = alloc_entry.get('allocations', [])
                    if allocations:
                        cost_center_service.allocate_journal_line(journal_line_id, allocations)
        
        if own_conn:
            conn.commit()
        return entry_id, None
    except Exception as e:
        if own_conn:
            conn.rollback()
        return None, str(e)
    finally:
        if own_conn:
            conn.close()

def update_journal_entry(entry_id, description, lines, entry_date=None, cost_center_allocations=None):
    """تحديث قيد موجود مع دعم العملات"""
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")
    
    if is_period_closed(entry_date):
        return False, f"لا يمكن تحديث قيد في فترة مغلقة: {entry_date}. يرجى فتح الفترة أولاً."
    
    base_currency = get_base_currency()
    base_code = base_currency['code'] if base_currency else 'YER'
    
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        
        conn.execute(
            "UPDATE journal_entries SET date = ?, description = ? WHERE id = ?",
            (entry_date, description, entry_id)
        )
        
        old_lines = conn.execute("SELECT id FROM journal_lines WHERE entry_id = ?", (entry_id,)).fetchall()
        for ol in old_lines:
            conn.execute("DELETE FROM cost_center_allocations WHERE journal_line_id = ?", (ol['id'],))
        conn.execute("DELETE FROM journal_lines WHERE entry_id = ?", (entry_id,))
        
        line_ids = []
        for idx, line in enumerate(lines):
            account_name = line["account"]
            if not account_name.isdigit():
                code = get_account_code(account_name, conn)
                if code:
                    account_name = code
            
            currency_code = line.get("currency_code", base_code)
            exchange_rate = line.get("exchange_rate", 1.0)
            if currency_code != base_code and exchange_rate == 1.0:
                fetched_rate = get_exchange_rate(currency_code, base_code)
                if fetched_rate:
                    exchange_rate = fetched_rate
            
            cur_line = conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit, currency_code, exchange_rate) VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, account_name, line["debit"], line["credit"], currency_code, exchange_rate)
            )
            line_ids.append(cur_line.lastrowid)
        
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
    """تفاصيل قيد محدد مع توزيعات مراكز التكلفة وبيانات العملة"""
    conn = get_conn()
    lines = conn.execute(
        "SELECT id, account_name, debit, credit, currency_code, exchange_rate FROM journal_lines WHERE entry_id = ?",
        (entry_id,)
    ).fetchall()
    
    result = []
    for l in lines:
        line_dict = dict(l)
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
        SELECT je.date, je.description, jl.debit, jl.credit, jl.currency_code, jl.exchange_rate
        FROM journal_lines jl
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE jl.account_name = ?
        ORDER BY je.date, je.id
    """, (account_name,)).fetchall()
    conn.close()
    return [dict(l) for l in ledger]

def get_trial_balance():
    """ميزان المراجعة (بالعملة الأساسية من خلال ضرب المبالغ بسعر الصرف)"""
    conn = get_conn()
    tb = conn.execute("""
        SELECT account_name,
               SUM(debit * exchange_rate) as total_debit,
               SUM(credit * exchange_rate) as total_credit
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
    """جلب القيد كاملاً مع توزيعات مراكز التكلفة"""
    return cost_center_service.get_allocations_for_entry(entry_id)
