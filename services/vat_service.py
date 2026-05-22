# services/vat_service.py – منطق ضريبة القيمة المضافة (VAT)
import sqlite3
from database import get_connection

def create_vat_table():
    """إنشاء جدول إعدادات الضريبة إذا لم يكن موجوداً"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vat_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'ضريبة القيمة المضافة',
            rate REAL NOT NULL DEFAULT 0.15,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # إدراج سجل افتراضي إذا كان الجدول فارغاً
    exists = conn.execute("SELECT COUNT(*) FROM vat_config").fetchone()[0]
    if exists == 0:
        conn.execute(
            "INSERT INTO vat_config (name, rate, is_active) VALUES (?, ?, ?)",
            ("ضريبة القيمة المضافة", 0.15, 1)
        )
        conn.commit()
    conn.close()

def get_vat_rate():
    """جلب نسبة الضريبة النشطة حالياً"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT rate FROM vat_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["rate"] if row else 0.15

def update_vat_rate(new_rate, name=None):
    """تحديث نسبة الضريبة (تعطيل القديم وإدراج جديد)"""
    conn = get_connection()
    # تعطيل جميع السجلات القديمة
    conn.execute("UPDATE vat_config SET is_active = 0")
    # إدراج السجل الجديد
    conn.execute(
        "INSERT INTO vat_config (name, rate, is_active) VALUES (?, ?, 1)",
        (name or "ضريبة القيمة المضافة", new_rate)
    )
    conn.commit()
    conn.close()
    return True

def calculate_vat(amount, rate=None):
    """حساب قيمة الضريبة لمبلغ معين"""
    if rate is None:
        rate = get_vat_rate()
    return round(amount * rate, 2)

def get_vat_report(start_date=None, end_date=None):
    """تقرير الضريبة (المخرجات والمدخلات)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    # ضريبة المبيعات (المخرجات)
    sales_query = """
        SELECT COALESCE(SUM(total), 0) as total_sales
        FROM invoices
        WHERE type = 'sale' AND status = 'completed'
    """
    # ضريبة المشتريات (المدخلات)
    purchases_query = """
        SELECT COALESCE(SUM(total), 0) as total_purchases
        FROM invoices
        WHERE type = 'purchase' AND status = 'completed'
    """
    
    params = ()
    if start_date and end_date:
        date_filter = " AND invoice_date BETWEEN ? AND ?"
        sales_query += date_filter
        purchases_query += date_filter
        params = (start_date, end_date)
    
    sales_total = conn.execute(sales_query, params).fetchone()["total_sales"]
    purchases_total = conn.execute(purchases_query, params).fetchone()["total_purchases"]
    
    rate = get_vat_rate()
    output_vat = round(sales_total * rate, 2)
    input_vat = round(purchases_total * rate, 2)
    net_vat = round(output_vat - input_vat, 2)
    
    conn.close()
    
    return {
        "rate": rate,
        "total_sales": sales_total,
        "total_purchases": purchases_total,
        "output_vat": output_vat,
        "input_vat": input_vat,
        "net_vat": net_vat
    }

def get_vat_history():
    """سجل تغييرات نسبة الضريبة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM vat_config ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
