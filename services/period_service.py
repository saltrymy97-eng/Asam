# services/period_service.py – منطق إغلاق الفترات المالية
# v2.0 — دعم conn خارجي لمنع database is locked
import sqlite3
from datetime import datetime
from database import get_connection


def create_periods_table():
    """إنشاء جدول الفترات المغلقة إذا لم يكن موجوداً"""
    conn = get_connection()
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
    conn.commit()
    conn.close()


def ensure_periods_table():
    """ضمان وجود الجدول (يُستدعى عند بدء التطبيق)"""
    create_periods_table()


def is_period_closed(date_str, conn=None):
    """
    التحقق مما إذا كان التاريخ يقع ضمن فترة مغلقة.
    
    ✅ التعديل: تقبل conn خارجي، لتفادي فتح اتصال جديد داخل معاملة.
    إذا مررنا conn → نستخدمه. وإلا → نفتح اتصالاً جديداً ونُغلقه.
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        # تحويل التاريخ بأمان
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                return False

        month_key = dt.strftime("%Y-%m")
        year_key = dt.strftime("%Y")

        # ✅ نستخدم نفس الاتصال (conn) — لا اتصال جديد
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
            conn.close()


def close_period(period_type, period_value, username, conn=None):
    """إغلاق فترة مالية (تقبل conn خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute(
            "INSERT OR IGNORE INTO closed_periods "
            "(period_type, period_value, closed_at, closed_by) "
            "VALUES (?, ?, datetime('now'), ?)",
            (period_type, period_value, username)
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def reopen_period(period_type, period_value, conn=None):
    """إعادة فتح فترة مالية (تقبل conn خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute(
            "DELETE FROM closed_periods WHERE period_type=? AND period_value=?",
            (period_type, period_value)
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


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
            conn.close()


def get_available_months(conn=None):
    """جلب قائمة الشهور التي لديها قيود"""
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
            conn.close()


def get_available_years(conn=None):
    """جلب قائمة السنوات التي لديها قيود"""
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
            conn.close()
