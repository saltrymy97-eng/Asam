# services/period_service.py – منطق إغلاق الفترات المالية
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

def is_period_closed(date_str):
    """التحقق مما إذا كان التاريخ يقع ضمن فترة مغلقة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            conn.close()
            return False
    
    month_key = dt.strftime("%Y-%m")
    year_key = dt.strftime("%Y")
    
    month_closed = conn.execute(
        "SELECT COUNT(*) as cnt FROM closed_periods WHERE period_type='month' AND period_value=?",
        (month_key,)
    ).fetchone()["cnt"] > 0
    
    year_closed = conn.execute(
        "SELECT COUNT(*) as cnt FROM closed_periods WHERE period_type='year' AND period_value=?",
        (year_key,)
    ).fetchone()["cnt"] > 0
    
    conn.close()
    return month_closed or year_closed

def close_period(period_type, period_value, username):
    """إغلاق فترة مالية"""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO closed_periods (period_type, period_value, closed_at, closed_by) VALUES (?, ?, datetime('now'), ?)",
        (period_type, period_value, username)
    )
    conn.commit()
    conn.close()

def reopen_period(period_type, period_value):
    """إعادة فتح فترة مالية"""
    conn = get_connection()
    conn.execute(
        "DELETE FROM closed_periods WHERE period_type=? AND period_value=?",
        (period_type, period_value)
    )
    conn.commit()
    conn.close()

def get_closed_periods():
    """جلب جميع الفترات المغلقة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    periods = conn.execute("SELECT * FROM closed_periods ORDER BY period_value DESC").fetchall()
    conn.close()
    return [dict(p) for p in periods]

def get_available_months():
    """جلب قائمة الشهور التي لديها قيود"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    months = conn.execute(
        "SELECT DISTINCT strftime('%Y-%m', date) as month FROM journal_entries ORDER BY month DESC"
    ).fetchall()
    conn.close()
    return [m["month"] for m in months]

def get_available_years():
    """جلب قائمة السنوات التي لديها قيود"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    years = conn.execute(
        "SELECT DISTINCT strftime('%Y', date) as year FROM journal_entries ORDER BY year DESC"
    ).fetchall()
    conn.close()
    return [y["year"] for y in years]
