# services/period_service.py – منطق إغلاق الفترات المالية (v3.0)
# ✅ Connection Registry — لا conn.close()
from datetime import datetime
from database import get_connection, close_connection


def create_periods_table(conn=None):
    """إنشاء جدول الفترات المغلقة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS closed_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_type TEXT NOT NULL,
                period_value TEXT NOT NULL,
                closed_at TEXT NOT NULL,
                closed_by TEXT NOT NULL,
                UNIQUE(period_type, period_value)
            )
        """)
        if own_conn:
            conn.execute("COMMIT")
    finally:
        if own_conn:
            close_connection(conn)


def ensure_periods_table():
    """ضمان وجود الجدول"""
    create_periods_table()


def is_period_closed(date_str, conn=None):
    """التحقق مما إذا كان التاريخ في فترة مغلقة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                return False

        month_key = dt.strftime("%Y-%m")
        year_key = dt.strftime("%Y")

        month_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM closed_periods "
            "WHERE period_type='month' AND period_value=?",
            (month_key,)
        ).fetchone()

        year_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM closed_periods "
            "WHERE period_type='year' AND period_value=?",
            (year_key,)
        ).fetchone()

        month_closed = (month_row["cnt"] if month_row else 0) > 0
        year_closed = (year_row["cnt"] if year_row else 0) > 0

        return month_closed or year_closed

    finally:
        if own_conn:
            close_connection(conn)


def close_period(period_type, period_value, username, conn=None):
    """إغلاق فترة مالية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR IGNORE INTO closed_periods "
            "(period_type, period_value, closed_at, closed_by) "
            "VALUES (?, ?, datetime('now'), ?)",
            (period_type, period_value, username)
        )
        if own_conn:
            conn.execute("COMMIT")
    except Exception:
        if own_conn:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        raise
    finally:
        if own_conn:
            close_connection(conn)


def reopen_period(period_type, period_value, conn=None):
    """إعادة فتح فترة مالية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM closed_periods WHERE period_type=? AND period_value=?",
            (period_type, period_value)
        )
        if own_conn:
            conn.execute("COMMIT")
    except Exception:
        if own_conn:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        raise
    finally:
        if own_conn:
            close_connection(conn)


def get_closed_periods(conn=None):
    """جلب جميع الفترات المغلقة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute(
            "SELECT * FROM closed_periods ORDER BY period_value DESC"
        ).fetchall()
        return [dict(p) for p in rows]
    finally:
        if own_conn:
            close_connection(conn)


def get_available_months(conn=None):
    """قائمة الشهور"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        months = conn.execute(
            "SELECT DISTINCT strftime('%Y-%m', date) as month "
            "FROM journal_entries ORDER BY month DESC"
        ).fetchall()
        return [m["month"] for m in months]
    finally:
        if own_conn:
            close_connection(conn)


def get_available_years(conn=None):
    """قائمة السنوات"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        years = conn.execute(
            "SELECT DISTINCT strftime('%Y', date) as year "
            "FROM journal_entries ORDER BY year DESC"
        ).fetchall()
        return [y["year"] for y in years]
    finally:
        if own_conn:
            close_connection(conn)
