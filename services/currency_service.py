# services/currency_service.py – منطق تعدد العملات وأسعار الصرف (مع إدارة العمليات)
import sqlite3
import database
from datetime import date, datetime

def get_conn():
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    return conn

# ===================== إدارة العملات =====================

def create_currency(code, name, symbol="", is_base=False):
    """إضافة عملة جديدة"""
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        if is_base:
            conn.execute("UPDATE currencies SET is_base = 0")
        conn.execute(
            "INSERT INTO currencies (code, name, symbol, is_base) VALUES (?, ?, ?, ?)",
            (code.upper(), name, symbol, 1 if is_base else 0)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_currency(currency_id, name=None, symbol=None, is_active=None, is_base=None):
    """تحديث بيانات عملة"""
    conn = get_conn()
    fields = []
    values = []
    if name: fields.append("name = ?"); values.append(name)
    if symbol: fields.append("symbol = ?"); values.append(symbol)
    if is_active is not None: fields.append("is_active = ?"); values.append(1 if is_active else 0)
    if is_base is not None and is_base: 
        fields.append("is_base = 1")
    if not fields: return
    try:
        conn.execute("BEGIN")
        values.append(currency_id)
        conn.execute(f"UPDATE currencies SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_currencies(active_only=True):
    """جلب قائمة العملات"""
    conn = get_conn()
    query = "SELECT * FROM currencies"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY code"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_base_currency():
    """جلب العملة الأساسية"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM currencies WHERE is_base = 1").fetchone()
    conn.close()
    return dict(row) if row else None

def create_default_currencies():
    """إنشاء العملات الافتراضية إذا لم توجد عملات"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
    conn.close()
    if count == 0:
        try:
            create_currency("YER", "ريال يمني", "﷼", is_base=True)
        except:
            pass  # تجاهل الخطأ إذا كانت العملة موجودة
        try:
            create_currency("USD", "دولار أمريكي", "$")
        except:
            pass
        try:
            create_currency("SAR", "ريال سعودي", "﷼")
        except:
            pass

# ===================== أسعار الصرف =====================

def set_exchange_rate(from_currency, to_currency, rate, rate_date=None):
    """تحديد سعر صرف (مع إدارة العمليات)"""
    if rate_date is None:
        rate_date = date.today().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO exchange_rates (from_currency, to_currency, rate, date)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(from_currency, to_currency, date) DO UPDATE SET rate = ?""",
            (from_currency.upper(), to_currency.upper(), rate, rate_date, rate)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_exchange_rate(from_currency, to_currency, rate_date=None):
    """جلب سعر الصرف لتاريخ محدد (أو آخر سعر متاح)"""
    if rate_date is None:
        rate_date = date.today().strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute(
        "SELECT rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? AND date = ?",
        (from_currency.upper(), to_currency.upper(), rate_date)
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? ORDER BY date DESC LIMIT 1",
            (from_currency.upper(), to_currency.upper())
        ).fetchone()
    conn.close()
    return row['rate'] if row else None

def convert_amount(amount, from_currency, to_currency, rate_date=None):
    """تحويل مبلغ بين عملتين"""
    rate = get_exchange_rate(from_currency, to_currency, rate_date)
    if rate is None:
        raise ValueError(f"لا يوجد سعر صرف من {from_currency} إلى {to_currency}")
    return amount * rate

def get_exchange_rate_history(from_currency, to_currency, limit=30):
    """سجل أسعار الصرف"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM exchange_rates WHERE from_currency = ? AND to_currency = ? ORDER BY date DESC LIMIT ?",
        (from_currency.upper(), to_currency.upper(), limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===================== دوال مساعدة =====================

def get_currency_choices():
    """قائمة مناسبة لـ selectbox في الواجهات"""
    currencies = get_all_currencies()
    return {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
