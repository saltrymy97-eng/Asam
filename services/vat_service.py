# services/vat_service.py – منطق ضريبة القيمة المضافة (VAT) - نسخة نهائية
import sqlite3
from database import get_connection

def create_vat_table():
    """إنشاء جدول إعدادات الضريبة وإصلاحه تلقائياً إذا كان ناقصاً"""
    conn = get_connection()
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vat_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT 'ضريبة القيمة المضافة',
            rate REAL NOT NULL DEFAULT 0.15,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    try:
        conn.execute("ALTER TABLE vat_config ADD COLUMN name TEXT DEFAULT 'ضريبة القيمة المضافة'")
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute("ALTER TABLE vat_config ADD COLUMN created_at TEXT DEFAULT (datetime('now','localtime'))")
    except sqlite3.OperationalError:
        pass
    
    conn.execute("UPDATE vat_config SET name = 'ضريبة القيمة المضافة' WHERE name IS NULL OR name = ''")
    conn.execute("UPDATE vat_config SET created_at = datetime('now','localtime') WHERE created_at IS NULL OR created_at = ''")
    conn.commit()
    
    count = conn.execute("SELECT COUNT(*) FROM vat_config").fetchone()[0]
    if count == 0:
        conn.execute("INSERT INTO vat_config (name, rate, is_active) VALUES ('ضريبة القيمة المضافة', 0.15, 1)")
        conn.commit()
    conn.close()

def get_vat_rate():
    """جلب نسبة الضريبة النشطة حالياً"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT rate FROM vat_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["rate"] if row else 0.15

def update_vat_rate(new_rate, name=None):
    """تحديث نسبة الضريبة"""
    conn = get_connection()
    conn.execute("UPDATE vat_config SET is_active = 0")
    conn.execute(
        "INSERT INTO vat_config (name, rate, is_active) VALUES (?, ?, 1)",
        (name or "ضريبة القيمة المضافة", new_rate)
    )
    conn.commit()
    conn.close()
    return True

def calculate_vat(amount, rate=None):
    if rate is None:
        rate = get_vat_rate()
    return round(amount * rate, 2)

def calculate_reverse_vat(total_amount, rate=None):
    if rate is None:
        rate = get_vat_rate()
    before = round(total_amount / (1 + rate), 2)
    vat = round(total_amount - before, 2)
    return before, vat

def get_vat_report(start_date=None, end_date=None):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    params = ()
    date_filter = ""
    if start_date and end_date:
        date_filter = " AND invoice_date BETWEEN ? AND ?"
        params = (start_date, end_date)
    sales = conn.execute(f"SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='sale' AND status='completed'{date_filter}", params).fetchone()[0]
    purchases = conn.execute(f"SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='purchase' AND status='completed'{date_filter}", params).fetchone()[0]
    conn.close()
    rate = get_vat_rate()
    return {
        "rate": rate,
        "total_sales": sales,
        "total_purchases": purchases,
        "output_vat": round(sales * rate, 2),
        "input_vat": round(purchases * rate, 2),
        "net_vat": round(sales * rate - purchases * rate, 2)
    }

def get_tax_return_report(start_date=None, end_date=None):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    params = ()
    date_filter = ""
    if start_date and end_date:
        date_filter = " AND invoice_date BETWEEN ? AND ?"
        params = (start_date, end_date)
    out = conn.execute(f"SELECT COALESCE(SUM(vat_amount),0), COALESCE(SUM(total - vat_amount),0) FROM invoices WHERE type='sale' AND status='completed'{date_filter}", params).fetchone()
    inp = conn.execute(f"SELECT COALESCE(SUM(vat_amount),0), COALESCE(SUM(total - vat_amount),0) FROM invoices WHERE type='purchase' AND status='completed'{date_filter}", params).fetchone()
    invs = conn.execute(f"SELECT id, type, invoice_date, total, vat_amount, vat_rate FROM invoices WHERE status='completed'{date_filter}", params).fetchall()
    conn.close()
    return {
        "rate": get_vat_rate(),
        "total_output_vat": out[0],
        "total_input_vat": inp[0],
        "net_vat": round(out[0] - inp[0], 2),
        "sales_before_tax": out[1],
        "purchases_before_tax": inp[1],
        "invoices": [dict(inv) for inv in invs]
    }

def get_vat_history():
    """سجل تغييرات نسبة الضريبة (مع ضمان ظهور جميع الحقول)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        rows = conn.execute("SELECT * FROM vat_config ORDER BY id DESC LIMIT 10").fetchall()
    except:
        conn.close()
        return []
    
    conn.close()
    
    result = []
    for r in rows:
        d = dict(r)
        if 'name' not in d or not d.get('name'):
            d['name'] = 'ضريبة القيمة المضافة'
        if 'rate' not in d:
            d['rate'] = 0.15
        if 'is_active' not in d:
            d['is_active'] = 0
        if 'created_at' not in d or not d.get('created_at'):
            d['created_at'] = 'غير محدد'
        result.append(d)
    
    return result
