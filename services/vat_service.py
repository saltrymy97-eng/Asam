# services/vat_service.py – منطق ضريبة القيمة المضافة (VAT) مع إصلاح الأعمدة
import sqlite3
from database import get_connection

def create_vat_table():
    """إنشاء جدول إعدادات الضريبة إذا لم يكن موجوداً، وإصلاح الأعمدة الناقصة"""
    conn = get_connection()
    
    # إنشاء الجدول الأساسي (قد يكون موجوداً)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vat_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'ضريبة القيمة المضافة',
            rate REAL NOT NULL DEFAULT 0.15,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    
    # 🆕 إضافة عمود name إذا كان الجدول موجوداً مسبقاً بدون هذا العمود
    try:
        conn.execute("ALTER TABLE vat_config ADD COLUMN name TEXT NOT NULL DEFAULT 'ضريبة القيمة المضافة'")
    except sqlite3.OperationalError:
        pass  # العمود موجود مسبقاً
    
    # تعبئة الأعمدة الفارغة بقيمة افتراضية (للبيانات القديمة)
    conn.execute("UPDATE vat_config SET name = 'ضريبة القيمة المضافة' WHERE name IS NULL OR name = ''")
    
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

def calculate_reverse_vat(total_amount, rate=None):
    """حساب الضريبة العكسية (استخراج المبلغ قبل الضريبة وقيمة الضريبة من الإجمالي)"""
    if rate is None:
        rate = get_vat_rate()
    amount_before_tax = round(total_amount / (1 + rate), 2)
    vat_amount = round(total_amount - amount_before_tax, 2)
    return amount_before_tax, vat_amount

def get_vat_report(start_date=None, end_date=None):
    """تقرير الضريبة (المخرجات والمدخلات)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    sales_query = """
        SELECT COALESCE(SUM(total), 0) as total_sales
        FROM invoices
        WHERE type = 'sale' AND status = 'completed'
    """
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

def get_tax_return_report(start_date=None, end_date=None):
    """تقرير الإقرار الضريبي (Tax Return) باستخدام بيانات الضريبة الفعلية المخزنة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row

    sales_query = """
        SELECT COALESCE(SUM(vat_amount), 0) as total_output_vat,
               COALESCE(SUM(total - vat_amount), 0) as total_sales_before_tax
        FROM invoices
        WHERE type = 'sale' AND status = 'completed'
    """
    purchases_query = """
        SELECT COALESCE(SUM(vat_amount), 0) as total_input_vat,
               COALESCE(SUM(total - vat_amount), 0) as total_purchases_before_tax
        FROM invoices
        WHERE type = 'purchase' AND status = 'completed'
    """
    
    params = ()
    if start_date and end_date:
        date_filter = " AND invoice_date BETWEEN ? AND ?"
        sales_query += date_filter
        purchases_query += date_filter
        params = (start_date, end_date)
    
    sales_data = conn.execute(sales_query, params).fetchone()
    purchases_data = conn.execute(purchases_query, params).fetchone()
    
    invoices_query = """
        SELECT id, type, invoice_date, total, vat_amount, vat_rate
        FROM invoices
        WHERE status = 'completed'
    """
    if start_date and end_date:
        invoices_query += " AND invoice_date BETWEEN ? AND ?"
        invoices = conn.execute(invoices_query, params).fetchall()
    else:
        invoices = conn.execute(invoices_query).fetchall()
    
    conn.close()
    
    return {
        "rate": get_vat_rate(),
        "total_output_vat": sales_data["total_output_vat"],
        "total_input_vat": purchases_data["total_input_vat"],
        "net_vat": round(sales_data["total_output_vat"] - purchases_data["total_input_vat"], 2),
        "sales_before_tax": sales_data["total_sales_before_tax"],
        "purchases_before_tax": purchases_data["total_purchases_before_tax"],
        "invoices": [dict(inv) for inv in invoices]
    }

def get_vat_history():
    """سجل تغييرات نسبة الضريبة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM vat_config ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()
    # التأكد من وجود اسم افتراضي للسجلات القديمة
    history = []
    for r in rows:
        rec = dict(r)
        if 'name' not in rec or not rec.get('name'):
            rec['name'] = 'ضريبة القيمة المضافة'
        history.append(rec)
    return history
