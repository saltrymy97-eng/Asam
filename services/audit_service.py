# services/audit_service.py - منطق سجل التدقيق (v2.1)
# ✅ Connection Registry — لا اتصالات منفصلة
# ✅ v2.1: JSON للقيم + user_id + تسجيل دائم مستقل عن Transactions
import sqlite3
import json
from datetime import datetime
from database import get_connection, close_connection


def _resolve_conn(conn):
    """يرجع (conn, owns)"""
    if conn is None:
        return get_connection(), True
    return conn, False


def _serialize_value(value):
    """
    تحويل آمن لأي قيمة إلى JSON string.
    - None → None
    - dict/list → JSON
    - primitives → str
    """
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return str(value)
    return str(value)


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
        # ✅ إضافة أعمدة جديدة (آمنة)
        _safe_add_column(c, "audit_log", "user_id", "INTEGER")
        _safe_add_column(c, "audit_log", "ip_address", "TEXT")
        _safe_add_column(c, "audit_log", "session_id", "TEXT")

        # ✅ فهارس لتسريع البحث
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(username)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name)")

        if owns:
            c.commit()
    finally:
        if owns:
            close_connection(c)


def _safe_add_column(conn, table, column, definition):
    """إضافة عمود بأمان إن لم يكن موجوداً"""
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception as e:
        print(f"⚠️ تعذر إضافة العمود {column} إلى {table}: {e}")


def log_action(username, action, table_name, record_id=None,
               old_value=None, new_value=None, conn=None,
               user_id=None, ip_address=None, session_id=None,
               commit_now=True):
    """
    تسجيل إجراء في سجل التدقيق.
    
    ✅ لا يُغلق الاتصال المُمرَّر.
    ✅ لا يُوقف العملية إذا فشل التدقيق.
    
    Args:
        commit_now: إذا True (افتراضي)، يعمل commit دائماً حتى مع conn مُمرَّر.
                    هذا يضمن بقاء سجل التدقيق حتى لو rollback العملية الأصلية.
                    ⚠️ استخدم commit_now=False فقط داخل Transaction حساس
                       تريد إلغاء السجل مع العملية.
    """
    c, owns = _resolve_conn(conn)
    try:
        c.execute("""
            INSERT INTO audit_log
                (username, action, table_name, record_id,
                 old_value, new_value, timestamp,
                 user_id, ip_address, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            action,
            table_name,
            record_id,
            _serialize_value(old_value),
            _serialize_value(new_value),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            ip_address,
            session_id,
        ))
        # ✅ commit دائماً (حتى مع conn خارجي) لضمان بقاء السجل
        if owns or commit_now:
            c.commit()
    except Exception as e:
        try:
            print(f"Audit log error: {e}")
        except Exception:
            pass
    finally:
        if owns:
            close_connection(c)


def log_create(username, table_name, record_id, new_value="", conn=None,
               user_id=None, **kwargs):
    """تسجيل عملية إنشاء"""
    log_action(username, f"إنشاء {table_name}", table_name,
               record_id, new_value=new_value, conn=conn,
               user_id=user_id, **kwargs)


def log_update(username, table_name, record_id, old_value="",
               new_value="", conn=None, user_id=None, **kwargs):
    """تسجيل عملية تعديل"""
    log_action(username, f"تعديل {table_name}", table_name, record_id,
               old_value=old_value, new_value=new_value, conn=conn,
               user_id=user_id, **kwargs)


def log_delete(username, table_name, record_id, old_value="", conn=None,
               user_id=None, **kwargs):
    """تسجيل عملية حذف"""
    log_action(username, f"حذف {table_name}", table_name, record_id,
               old_value=old_value, conn=conn, user_id=user_id, **kwargs)


def log_login(username, success=True, ip_address=None, conn=None):
    """تسجيل محاولة تسجيل دخول"""
    log_action(
        username=username,
        action="تسجيل دخول ناجح" if success else "تسجيل دخول فاشل",
        table_name="users",
        record_id=None,
        new_value=f"IP: {ip_address}" if ip_address else None,
        ip_address=ip_address,
        conn=conn,
    )


def log_logout(username, conn=None):
    """تسجيل خروج"""
    log_action(username, "تسجيل خروج", "users", conn=conn)


def get_audit_logs(filter_table=None, filter_user=None,
                   date_from=None, date_to=None,
                   search_text=None,
                   limit=100, conn=None):
    """
    جلب سجل التدقيق مع فلاتر متقدمة.
    """
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
        if date_from:
            query += " AND date(timestamp) >= date(?)"
            params.append(date_from)
        if date_to:
            query += " AND date(timestamp) <= date(?)"
            params.append(date_to)
        if search_text:
            # ✅ بحث نصي شامل في كل الأعمدة
            query += (
                " AND (action LIKE ? OR table_name LIKE ? "
                "OR old_value LIKE ? OR new_value LIKE ? "
                "OR username LIKE ?)"
            )
            pattern = f"%{search_text}%"
            params.extend([pattern] * 5)

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
