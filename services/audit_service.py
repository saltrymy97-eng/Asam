# services/audit_service.py - منطق سجل التدقيق (v2.0)
# ✅ Connection Registry — لا اتصالات منفصلة
import sqlite3
from datetime import datetime
from database import get_connection, close_connection


def _resolve_conn(conn):
    """يرجع (conn, owns)"""
    if conn is None:
        return get_connection(), True
    return conn, False


def create_audit_table(conn=None):
    """إنشاء جدول سجل التدقيق"""
    c, owns = _resolve_conn(conn)
    try:
        c.execute("""
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
        if owns:
            c.commit()
    finally:
        if owns:
            close_connection(c)


def log_action(username, action, table_name, record_id=None,
               old_value=None, new_value=None, conn=None):
    """
    تسجيل إجراء في سجل التدقيق.
    ✅ لا يُغلق الاتصال المُمرَّر.
    ✅ لا يُوقف العملية إذا فشل التدقيق.
    """
    c, owns = _resolve_conn(conn)
    try:
        c.execute("""
            INSERT INTO audit_log
                (username, action, table_name, record_id,
                 old_value, new_value, timestamp)
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
        if owns:
            c.commit()
    except Exception as e:
        # ✅ لا نُوقف العملية إذا فشل التدقيق
        try:
            print(f"Audit log error: {e}")
        except Exception:
            pass
    finally:
        if owns:
            close_connection(c)


def log_create(username, table_name, record_id, new_value="", conn=None):
    """تسجيل عملية إنشاء"""
    log_action(username, f"إنشاء {table_name}", table_name,
               record_id, new_value=new_value, conn=conn)


def log_update(username, table_name, record_id, old_value="",
               new_value="", conn=None):
    """تسجيل عملية تعديل"""
    log_action(username, f"تعديل {table_name}", table_name, record_id,
               old_value=old_value, new_value=new_value, conn=conn)


def log_delete(username, table_name, record_id, old_value="", conn=None):
    """تسجيل عملية حذف"""
    log_action(username, f"حذف {table_name}", table_name, record_id,
               old_value=old_value, conn=conn)


def get_audit_logs(filter_table=None, filter_user=None, limit=100, conn=None):
    """جلب سجل التدقيق"""
    c, owns = _resolve_conn(conn)
    try:
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
        logs = c.execute(query, params).fetchall()
        return [dict(log) for log in logs]
    finally:
        if owns:
            close_connection(c)


def get_audit_stats(conn=None):
    """إحصائيات سجل التدقيق"""
    c, owns = _resolve_conn(conn)
    try:
        total = c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        today = c.execute(
            "SELECT COUNT(*) FROM audit_log "
            "WHERE date(timestamp) = date('now')"
        ).fetchone()[0]
        top_users = c.execute(
            "SELECT username, COUNT(*) as cnt FROM audit_log "
            "GROUP BY username ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        top_actions = c.execute(
            "SELECT action, COUNT(*) as cnt FROM audit_log "
            "GROUP BY action ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        return {
            "total": total,
            "today": today,
            "top_users": [dict(u) for u in top_users],
            "top_actions": [dict(a) for a in top_actions]
        }
    finally:
        if owns:
            close_connection(c)


# إنشاء الجدول تلقائياً
create_audit_table()
