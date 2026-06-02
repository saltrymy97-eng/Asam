# services/vat_service.py – ضريبة القيمة المضافة (محصن بالكامل)
import sqlite3
from database import get_connection

def create_vat_table():
    conn = get_connection()
    # إنشاء الجدول إن لم يكن موجوداً
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vat_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT 'ضريبة القيمة المضافة',
            rate REAL NOT NULL DEFAULT 0.15,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # محاولة إضافة العمود name إذا كان الجدول قديماً
    try:
        conn.execute("ALTER TABLE vat_config ADD COLUMN name TEXT DEFAULT 'ضريبة القيمة المضافة'")
    except:
        pass
    # تعبئة أي قيم فارغة
    conn.execute("UPDATE vat_config SET name = 'ضريبة القيمة المضافة' WHERE name IS NULL OR name = ''")
    conn.commit()

    # إدراج سجل افتراضي إذا كان الجدول فارغاً
    count = conn.execute("SELECT COUNT(*) FROM vat_config").fetchone()[0]
    if count == 0:
        conn.execute("INSERT INTO vat_config (name, rate, is_active) VALUES ('ضريبة القيمة المضافة', 0.15, 1)")
        conn.commit()
    conn.close()

def get_vat_rate():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT rate FROM vat_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["rate"] if row else 0.15

def update_vat_rate(new_rate, name=None):
    conn = get_connection()
    conn.execute("UPDATE vat_config SET is_active = 0")
    conn.execute("INSERT INTO vat_config (name, rate, is_active) VALUES (?, ?, 1)",
                 (name or "ضريبة القيمة المضافة", new_rate))
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
    out_vat = round(sales * rate, 2)
    in_vat = round(purchases * rate, 2)
    return {
        "rate": rate,
        "total_sales": sales,
        "total_purchases": purchases,
        "output_vat": out_vat,
        "input_vat": in_vat,
        "net_vat": out_vat - in_vat
    }

def get_tax_return_report(start_date=None, end_date=None):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    params = ()
    date_filter = ""
    if start_date and end_date:
        date_filter = " AND invoice_date BETWEEN ? AND ?"
        params = (start_date, end_date)

    out_data = conn.execute(f"SELECT COALESCE(SUM(vat_amount),0), COALESCE(SUM(total - vat_amount),0) FROM invoices WHERE type='sale' AND status='completed'{date_filter}", params).fetchone()
    in_data = conn.execute(f"SELECT COALESCE(SUM(vat_amount),0), COALESCE(SUM(total - vat_amount),0) FROM invoices WHERE type='purchase' AND status='completed'{date_filter}", params).fetchone()
    invs = conn.execute(f"SELECT id, type, invoice_date, total, vat_amount, vat_rate FROM invoices WHERE status='completed'{date_filter}", params).fetchall()
    conn.close()

    return {
        "rate": get_vat_rate(),
        "total_output_vat": out_data[0],
        "total_input_vat": in_data[0],
        "net_vat": round(out_data[0] - in_data[0], 2),
        "sales_before_tax": out_data[1],
        "purchases_before_tax": in_data[1],
        "invoices": [dict(inv) for inv in invs]
    }

def get_vat_history():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM vat_config ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        # تعويض غياب العمود يدوياً (حماية إضافية)
        if 'name' not in d or not d.get('name'):
            d['name'] = 'ضريبة القيمة المضافة'
        if 'created_at' not in d:
            d['created_at'] = ''
        if 'is_active' not in d:
            d['is_active'] = 0
        if 'rate' not in d:
            d['rate'] = 0.15
        result.append(d)
    return result
