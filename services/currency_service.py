# services/currency_service.py – إدارة العملات وأسعار الصرف (إصدار محترف مع تحويل عكسي وتثبيت تلقائي)
import sqlite3
import os
from datetime import date

DB_PATH = os.path.join("data", "erp.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ===================== التثبيت التلقائي والصيانة =====================

def init_currency_system(default_base="YER"):
    """
    فحص وتثبيت نظام العملات تلقائياً عند التشغيل:
    1. إنشاء العملات الافتراضية إذا كان الجدول فارغاً.
    2. التأكد من وجود عملة أساسية واحدة فقط مسجلة في النظام.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        # إنشاء جدول العملات إن لم يكن موجوداً
        conn.execute("""
            CREATE TABLE IF NOT EXISTS currencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                symbol TEXT,
                is_base INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # إنشاء جدول أسعار الصرف إن لم يكن موجوداً
        conn.execute("""
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
        count = conn.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
        if count == 0:
            conn.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('YER', 'ريال يمني', '﷼', 1)")
            conn.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('SAR', 'ريال سعودي', '﷼', 0)")
            conn.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('USD', 'دولار أمريكي', '$', 0)")
            conn.execute("INSERT INTO currencies (code, name, symbol, is_base) VALUES ('EUR', 'يورو', '€', 0)")
        else:
            # التأكد من وجود عملة أساسية واحدة فقط
            base_count = conn.execute("SELECT COUNT(*) FROM currencies WHERE is_base = 1").fetchone()[0]
            if base_count == 0:
                conn.execute("UPDATE currencies SET is_base = 1 WHERE code = ?", (default_base.upper(),))
            elif base_count > 1:
                conn.execute("UPDATE currencies SET is_base = 0")
                conn.execute("UPDATE currencies SET is_base = 1 WHERE code = ?", (default_base.upper(),))
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error initializing currency system: {e}")
    finally:
        conn.close()

# ===================== إدارة العملات =====================

def create_currency(code, name, symbol="", is_base=False):
    """إضافة عملة جديدة مع ضبط العملة الأساسية عند الطلب"""
    code = code.upper().strip()
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        if is_base:
            conn.execute("UPDATE currencies SET is_base = 0")
        conn.execute(
            "INSERT INTO currencies (code, name, symbol, is_base) VALUES (?, ?, ?, ?)",
            (code, name, symbol, 1 if is_base else 0)
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

def set_base_currency(currency_code):
    """تغيير العملة الأساسية للنظام احترافياً"""
    currency_code = currency_code.upper().strip()
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute("UPDATE currencies SET is_base = 0")
        conn.execute("UPDATE currencies SET is_base = 1 WHERE code = ?", (currency_code,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_all_currencies(active_only=True):
    """جلب جميع العملات مفروزة بحسب العملة الأساسية أولاً"""
    conn = get_conn()
    query = "SELECT * FROM currencies"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY is_base DESC, code ASC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_base_currency():
    """جلب بيانات العملة الأساسية الحالية"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM currencies WHERE is_base = 1 LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else {"code": "YER", "name": "ريال يمني", "symbol": "﷼", "is_base": 1}

# ===================== أسعار الصرف والتحويل الذكي =====================

def set_exchange_rate(from_currency, to_currency, rate, rate_date=None):
    """تسجيل أو تحديث سعر صرف لعملة"""
    if rate_date is None:
        rate_date = date.today().strftime("%Y-%m-%d")
        
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()
    
    if from_curr == to_curr:
        return True

    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO exchange_rates (from_currency, to_currency, rate, date)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(from_currency, to_currency, date) DO UPDATE SET rate = ?""",
            (from_curr, to_curr, float(rate), rate_date, float(rate))
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_exchange_rate(from_currency, to_currency, rate_date=None):
    """
    جلب سعر الصرف المحسوب ذكياً:
    1. إرجاع 1.0 إذا كانت العملتان متطابقتين.
    2. البحث عن سعر مباشر (Direct Rate) لتاريخ القيد أو أحدث تاريخ قبله.
    3. البحث عن سعر عكسي (Inverse Rate) وحساب المقلوب (1 / Rate) تلقائياً.
    """
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()
    
    if from_curr == to_curr:
        return 1.0
        
    if rate_date is None:
        rate_date = date.today().strftime("%Y-%m-%d")
        
    conn = get_conn()
    
    # 1. البحث عن سعر مباشر
    row = conn.execute(
        "SELECT rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? AND date <= ? ORDER BY date DESC LIMIT 1",
        (from_curr, to_curr, rate_date)
    ).fetchone()
    
    if row and row['rate']:
        conn.close()
        return float(row['rate'])
        
    # 2. البحث عن سعر عكسي وحسابه تلقائياً
    inv_row = conn.execute(
        "SELECT rate FROM exchange_rates WHERE from_currency = ? AND to_currency = ? AND date <= ? ORDER BY date DESC LIMIT 1",
        (to_curr, from_curr, rate_date)
    ).fetchone()
    
    conn.close()
    if inv_row and inv_row['rate'] and float(inv_row['rate']) > 0:
        return 1.0 / float(inv_row['rate'])
        
    return None

def convert_amount(amount, from_currency, to_currency, rate_date=None):
    """تحويل مبلغ مالياً بين عملتين بناءً على أحدث سعر صرف متوفر"""
    rate = get_exchange_rate(from_currency, to_currency, rate_date)
    if rate is None:
        raise ValueError(f"لا يوجد سعر صرف مسجل بين {from_currency} و {to_currency}")
    return float(amount) * rate

# ===================== تشغيل الفحص التلقائي =====================
init_currency_system(default_base="YER")

# ===================== توافق مع الإصدارات السابقة =====================
# ✅ تمت إضافة هذا السطر للحفاظ على التوافق مع الملفات القديمة التي تستورد create_default_currencies
create_default_currencies = init_currency_system
