# services/currency_service.py – إدارة العملات وأسعار الصرف (v2.0)
# ✅ Connection Registry — لا اتصالات منفصلة
import sqlite3
from datetime import date
from database import get_connection, close_connection


def _resolve_conn(conn):
    """يرجع (conn, owns)"""
    if conn is None:
        return get_connection(), True
    return conn, False


# ===================== التثبيت التلقائي والصيانة =====================

def init_currency_system(default_base="YER", conn=None):
    """فحص وتثبيت نظام العملات تلقائياً عند التشغيل."""
    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")

        # إنشاء جدول العملات
        c.execute("""
            CREATE TABLE IF NOT EXISTS currencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                symbol TEXT,
                is_base INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)

        # إنشاء جدول أسعار الصرف
        c.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                date TEXT NOT NULL,
                UNIQUE(from_currency, to_currency, date)
            )
        """)

        # فحص هل توجد عملات
        count = c.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
        if count == 0:
            c.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('YER', 'ريال يمني', 'ر.ي', 1)")
            c.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('SAR', 'ريال سعودي', 'ر.س', 0)")
            c.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('USD', 'دولار أمريكي', 'USD', 0)")
            c.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('EUR', 'يورو', 'EUR', 0)")
        else:
            base_count = c.execute("SELECT COUNT(*) FROM currencies WHERE is_base = 1").fetchone()[0]
            if base_count == 0:
                c.execute("UPDATE currencies SET is_base = 1 WHERE code = ?", (default_base.upper(),))
            elif base_count > 1:
                c.execute("UPDATE currencies SET is_base = 0")
                c.execute("UPDATE currencies SET is_base = 1 WHERE code = ?", (default_base.upper(),))

        if owns:
            c.execute("COMMIT")
    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        print(f"Error initializing currency system: {e}")
    finally:
        if owns:
            close_connection(c)


# ===================== إدارة العملات =====================

def create_currency(code, name, symbol="", is_base=False, conn=None):
    """إضافة عملة جديدة"""
    code = code.upper().strip()
    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")
        if is_base:
            c.execute("UPDATE currencies SET is_base = 0")
        c.execute(
            "INSERT INTO currencies (code, name, symbol, is_base) VALUES (?, ?, ?, ?)",
            (code, name, symbol, 1 if is_base else 0)
        )
        if owns:
            c.execute("COMMIT")
        return True
    except sqlite3.IntegrityError:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return False
    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        raise e
    finally:
        if owns:
            close_connection(c)


def set_base_currency(currency_code, conn=None):
    """تغيير العملة الأساسية"""
    currency_code = currency_code.upper().strip()
    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE currencies SET is_base = 0")
        c.execute("UPDATE currencies SET is_base = 1 WHERE code = ?", (currency_code,))
        if owns:
            c.execute("COMMIT")
        return True
    except Exception:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return False
    finally:
        if owns:
            close_connection(c)


def get_all_currencies(active_only=True, conn=None):
    """جلب جميع العملات"""
    c, owns = _resolve_conn(conn)
    try:
        query = "SELECT * FROM currencies"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY is_base DESC, code ASC"
        rows = c.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns:
            close_connection(c)


def get_base_currency(conn=None):
    """جلب العملة الأساسية"""
    c, owns = _resolve_conn(conn)
    try:
        row = c.execute(
            "SELECT * FROM currencies WHERE is_base = 1 LIMIT 1"
        ).fetchone()
        return dict(row) if row else {
            "code": "YER", "name": "ريال يمني",
            "symbol": "ر.ي", "is_base": 1
        }
    finally:
        if owns:
            close_connection(c)


# ===================== أسعار الصرف والتحويل =====================

def set_exchange_rate(from_currency, to_currency, rate, rate_date=None, conn=None):
    """تسجيل أو تحديث سعر صرف"""
    if rate_date is None:
        rate_date = date.today().strftime("%Y-%m-%d")

    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()

    if from_curr == to_curr:
        return True

    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")
        c.execute(
            """INSERT INTO exchange_rates (from_currency, to_currency, rate, date)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(from_currency, to_currency, date) DO UPDATE SET rate = ?""",
            (from_curr, to_curr, float(rate), rate_date, float(rate))
        )
        if owns:
            c.execute("COMMIT")
        return True
    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        raise e
    finally:
        if owns:
            close_connection(c)


def get_exchange_rate(from_currency, to_currency, rate_date=None, conn=None):
    """جلب سعر الصرف مع دعم العكسي"""
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()

    if from_curr == to_curr:
        return 1.0

    if rate_date is None:
        rate_date = date.today().strftime("%Y-%m-%d")

    c, owns = _resolve_conn(conn)
    try:
        # 1. سعر مباشر
        row = c.execute(
            "SELECT rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (from_curr, to_curr, rate_date)
        ).fetchone()

        if row and row['rate']:
            return float(row['rate'])

        # 2. سعر عكسي
        inv_row = c.execute(
            "SELECT rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (to_curr, from_curr, rate_date)
        ).fetchone()

        if inv_row and inv_row['rate'] and float(inv_row['rate']) > 0:
            return 1.0 / float(inv_row['rate'])

        return None
    finally:
        if owns:
            close_connection(c)


def convert_amount(amount, from_currency, to_currency, rate_date=None, conn=None):
    """تحويل مبلغ"""
    rate = get_exchange_rate(from_currency, to_currency, rate_date, conn=conn)
    if rate is None:
        raise ValueError(f"لا يوجد سعر صرف مسجل بين {from_currency} و {to_currency}")
    return float(amount) * rate


def get_exchange_rate_history(from_currency, to_currency, limit=30, conn=None):
    """سجل أسعار الصرف"""
    c, owns = _resolve_conn(conn)
    try:
        rows = c.execute(
            "SELECT date, rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? ORDER BY date DESC LIMIT ?",
            (from_currency.upper(), to_currency.upper(), limit)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if owns:
            close_connection(c)


# ===================== التهيئة =====================
init_currency_system(default_base="YER")

# توافق مع الإصدارات السابقة
create_default_currencies = init_currency_system
