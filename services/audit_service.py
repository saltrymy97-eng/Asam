# services/audit_service.py - منطق سجل التدقيق (حوكمة ERP)
import sqlite3
from datetime import datetime

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_audit_table():
    """إنشاء جدول سجل التدقيق إذا لم يكن موجوداً"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT,
            table_name TEXT,
            record_id INTEGER,
            old_value TEXT,
            new_value TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_action(username, action, table_name, record_id=None, old_value=None, new_value=None):
    """
    تسجيل إجراء في سجل التدقيق.
    للإنشاء: استخدم new_value فقط.
    للتعديل: استخدم old_value و new_value.
    للحذف: استخدم old_value فقط.
    """
    create_audit_table()
    conn = get_conn()
    conn.execute("""
        INSERT INTO audit_log (username, action, table_name, record_id, old_value, new_value, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        username,
        action,
        table_name,
        record_id,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def log_create(username, table_name, record_id, new_value=""):
    """تسجيل عملية إنشاء سجل جديد"""
    log_action(username, f"إنشاء {table_name}", table_name, record_id, new_value=new_value)

def log_update(username, table_name, record_id, old_value="", new_value=""):
    """تسجيل عملية تعديل سجل"""
    log_action(username, f"تعديل {table_name}", table_name, record_id, old_value=old_value, new_value=new_value)

def log_delete(username, table_name, record_id, old_value=""):
    """تسجيل عملية حذف سجل"""
    log_action(username, f"حذف {table_name}", table_name, record_id, old_value=old_value)

def get_audit_logs(filter_table=None, filter_user=None, limit=100):
    """جلب سجل التدقيق مع إمكانية التصفية"""
    conn = get_conn()
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if filter_table:
        query += " AND table_name = ?"
        params.append(filter_table)
    if filter_user:
        query += " AND username = ?"
        params.append(filter_user)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    logs = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(log) for log in logs]

def get_audit_stats():
    """إحصائيات سجل التدقيق"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    today = conn.execute("SELECT COUNT(*) FROM audit_log WHERE date(timestamp) = date('now')").fetchone()[0]
    top_users = conn.execute("SELECT username, COUNT(*) as cnt FROM audit_log GROUP BY username ORDER BY cnt DESC LIMIT 5").fetchall()
    top_actions = conn.execute("SELECT action, COUNT(*) as cnt FROM audit_log GROUP BY action ORDER BY cnt DESC LIMIT 5").fetchall()
    conn.close()
    return {
        "total": total,
        "today": today,
        "top_users": [dict(u) for u in top_users],
        "top_actions": [dict(a) for a in top_actions]
    }
