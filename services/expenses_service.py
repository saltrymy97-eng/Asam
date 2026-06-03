# services/expenses_service.py – وحدة المصروفات التشغيلية (متكاملة محاسبياً)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.accounting_service import save_journal_entry

def create_expenses_table():
    """إنشاء جدول المصروفات إذا لم يكن موجوداً"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            account_code TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            party_type TEXT,
            party_id INTEGER,
            invoice_ref TEXT,
            notes TEXT,
            journal_entry_id INTEGER,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_expense_categories():
    """فئات المصروفات القياسية (مع ربطها بالحسابات)"""
    return [
        {"code": "إيجار", "account": "إيجار"},
        {"code": "كهرباء", "account": "كهرباء"},
        {"code": "ماء", "account": "ماء"},
        {"code": "رواتب", "account": "رواتب"},
        {"code": "صيانة", "account": "صيانة"},
        {"code": "إعلانات", "account": "إعلانات"},
        {"code": "اتصالات", "account": "اتصالات"},
        {"code": "أخرى", "account": "مصروفات أخرى"}
    ]

def get_cash_accounts():
    """جلب حسابات النقدية (لدفع المصروف)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    # نحاول جلب حسابات تحت الأصول (1)
    accounts = conn.execute("""
        SELECT code, name FROM accounts
        WHERE parent_id = (SELECT id FROM accounts WHERE code = '1')
        ORDER BY code
    """).fetchall()
    conn.close()
    if not accounts:
        return [{"code": "صندوق", "name": "صندوق"}, {"code": "بنك", "name": "بنك"}]
    return [{"code": a["code"], "name": a["name"]} for a in accounts]

def get_suppliers_for_expense():
    """جلب الموردين لاستخدامهم في المصروفات الآجلة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return [dict(s) for s in suppliers]

def create_expense(expense_date, category, amount, account_code, payment_method,
                   party_type=None, party_id=None, invoice_ref="", notes="",
                   created_by="admin"):
    """
    إنشاء مصروف مع القيد المحاسبي التلقائي
    
    payment_method: 'cash' (نقدي) أو 'credit' (آجل)
    """
    create_expenses_table()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        
        # 1. إدراج المصروف
        cur = conn.execute("""
            INSERT INTO expenses (date, category, amount, account_code, payment_method,
                                 party_type, party_id, invoice_ref, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (expense_date, category, amount, account_code, payment_method,
              party_type, party_id, invoice_ref, notes, created_by))
        expense_id = cur.lastrowid
        
        # 2. تحديد أسماء الحسابات
        # حساب المصروف (مدين)
        expense_account = category
        
        # حساب الدائن
        if payment_method == 'credit' and party_type == 'supplier' and party_id:
            supplier = conn.execute("SELECT name FROM suppliers WHERE id=?", 
                                   (party_id,)).fetchone()
            credit_account = supplier["name"] if supplier else "مورد غير معروف"
        else:
            credit_account = account_code  # النقدية (صندوق/بنك)
        
        # 3. إنشاء القيد المحاسبي
        lines = [
            {"account": expense_account, "debit": amount, "credit": 0},
            {"account": credit_account, "debit": 0, "credit": amount}
        ]
        
        desc = f"مصروف {category} #{expense_id}"
        if invoice_ref:
            desc += f" - فاتورة: {invoice_ref}"
            
        entry_id, error = save_journal_entry(
            description=desc,
            lines=lines,
            entry_date=expense_date,
            conn=conn
        )
        if error:
            raise Exception(f"فشل القيد المحاسبي: {error}")
        
        # 4. ربط القيد بالمصروف
        conn.execute("UPDATE expenses SET journal_entry_id=? WHERE id=?", 
                    (entry_id, expense_id))
        
        conn.commit()
        
        log_action(
            username=created_by,
            action="تسجيل مصروف",
            table_name="expenses",
            record_id=expense_id,
            new_value=f"{category}: {amount:,.2f}"
        )
        
        return expense_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_expenses(limit=100):
    """سجل المصروفات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    expenses = conn.execute("""
        SELECT e.*, 
               CASE WHEN e.party_type='supplier' THEN s.name 
                    ELSE NULL END as party_name
        FROM expenses e
        LEFT JOIN suppliers s ON e.party_id = s.id
        ORDER BY e.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(ex) for ex in expenses]
