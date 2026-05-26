# services/crm_service.py – منطق إدارة علاقات العملاء (CRM)
import sqlite3
from datetime import date, datetime
from database import get_connection
from services.audit_service import log_action

def create_crm_tables():
    """إنشاء جداول CRM إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            phone TEXT,
            email TEXT,
            source TEXT DEFAULT 'أخرى',
            status TEXT DEFAULT 'جديد',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            title TEXT NOT NULL,
            amount REAL DEFAULT 0,
            stage TEXT DEFAULT 'مؤهل',
            probability INTEGER DEFAULT 50,
            expected_close_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (lead_id) REFERENCES crm_leads(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            type TEXT DEFAULT 'اتصال',
            date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (lead_id) REFERENCES crm_leads(id)
        )
    """)
    # إضافة أعمدة جديدة لجدول customers إذا لم تكن موجودة
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN lead_id INTEGER REFERENCES crm_leads(id)")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN customer_type TEXT DEFAULT 'عادي'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

# ========== دوال العملاء المحتملين (Leads) ==========

def add_lead(name, company="", phone="", email="", source="أخرى", status="جديد", notes=""):
    """إضافة عميل محتمل جديد"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO crm_leads (name, company, phone, email, source, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, company, phone, email, source, status, notes)
    )
    conn.commit()
    lead_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return lead_id

def update_lead(lead_id, name=None, company=None, phone=None, email=None, source=None, status=None, notes=None):
    """تحديث بيانات عميل محتمل"""
    conn = get_connection()
    updates = []
    params = []
    if name: updates.append("name=?"); params.append(name)
    if company: updates.append("company=?"); params.append(company)
    if phone: updates.append("phone=?"); params.append(phone)
    if email: updates.append("email=?"); params.append(email)
    if source: updates.append("source=?"); params.append(source)
    if status: updates.append("status=?"); params.append(status)
    if notes: updates.append("notes=?"); params.append(notes)
    if updates:
        updates.append("updated_at=datetime('now','localtime')")
        conn.execute(f"UPDATE crm_leads SET {', '.join(updates)} WHERE id=?", params + [lead_id])
        conn.commit()
    conn.close()

def get_all_leads(status=None):
    """جلب العملاء المحتملين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    if status:
        rows = conn.execute("SELECT * FROM crm_leads WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM crm_leads ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def convert_lead_to_customer(lead_id):
    """تحويل عميل محتمل إلى عميل فعلي"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    lead = conn.execute("SELECT * FROM crm_leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return None
    conn.execute(
        "INSERT INTO customers (name, phone, address, lead_id, customer_type) VALUES (?, ?, ?, ?, 'محتمل')",
        (lead["name"], lead["phone"] or "", lead["company"] or "", lead_id)
    )
    customer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("UPDATE crm_leads SET status='تحول لعميل', updated_at=datetime('now','localtime') WHERE id=?", (lead_id,))
    conn.commit()
    conn.close()
    return customer_id

# ========== دوال الفرص البيعية (Opportunities) ==========

def add_opportunity(lead_id, title, amount=0, stage="مؤهل", probability=50, expected_close_date=None):
    """إضافة فرصة بيعية"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO crm_opportunities (lead_id, title, amount, stage, probability, expected_close_date) VALUES (?, ?, ?, ?, ?, ?)",
        (lead_id, title, amount, stage, probability, expected_close_date)
    )
    conn.commit()
    conn.close()

def get_opportunities(lead_id=None, stage=None):
    """جلب الفرص البيعية"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    query = "SELECT o.*, l.name as lead_name FROM crm_opportunities o JOIN crm_leads l ON o.lead_id = l.id WHERE 1=1"
    params = []
    if lead_id: query += " AND o.lead_id=?"; params.append(lead_id)
    if stage: query += " AND o.stage=?"; params.append(stage)
    rows = conn.execute(query + " ORDER BY o.expected_close_date", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pipeline_summary():
    """ملخص خط أنابيب المبيعات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    stages = conn.execute("""
        SELECT stage, COUNT(*) as count, COALESCE(SUM(amount),0) as total_amount
        FROM crm_opportunities
        GROUP BY stage ORDER BY total_amount DESC
    """).fetchall()
    conn.close()
    return [dict(s) for s in stages]

# ========== دوال التفاعلات (Interactions) ==========

def add_interaction(lead_id, interaction_type="اتصال", interaction_date=None, notes=""):
    """تسجيل تفاعل مع عميل"""
    if interaction_date is None:
        interaction_date = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        "INSERT INTO crm_interactions (lead_id, type, date, notes) VALUES (?, ?, ?, ?)",
        (lead_id, interaction_type, interaction_date, notes)
    )
    conn.commit()
    conn.close()

def get_interactions(lead_id=None):
    """جلب التفاعلات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    if lead_id:
        rows = conn.execute("SELECT i.*, l.name as lead_name FROM crm_interactions i JOIN crm_leads l ON i.lead_id = l.id WHERE i.lead_id=? ORDER BY i.date DESC", (lead_id,)).fetchall()
    else:
        rows = conn.execute("SELECT i.*, l.name as lead_name FROM crm_interactions i JOIN crm_leads l ON i.lead_id = l.id ORDER BY i.date DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ========== دوال التقارير ==========

def get_crm_summary():
    """ملخص CRM"""
    conn = get_connection()
    total_leads = conn.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0]
    new_leads = conn.execute("SELECT COUNT(*) FROM crm_leads WHERE status='جديد'").fetchone()[0]
    total_opportunities = conn.execute("SELECT COUNT(*) FROM crm_opportunities").fetchone()[0]
    won = conn.execute("SELECT COUNT(*) FROM crm_opportunities WHERE stage='مغلق ناجح'").fetchone()[0]
    pipeline_value = conn.execute("SELECT COALESCE(SUM(amount),0) FROM crm_opportunities WHERE stage NOT IN ('مغلق ناجح', 'مغلق خاسر')").fetchone()[0]
    conn.close()
    return {
        "total_leads": total_leads, "new_leads": new_leads,
        "total_opportunities": total_opportunities, "won": won,
        "pipeline_value": pipeline_value
    }
