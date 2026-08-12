# services/vat_service.py – وحدة إدارة ضريبة القيمة المضافة والإقرارات الضريبية (احترافي)
import sqlite3
from database import get_connection
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry
from services.audit_service import log_action

def create_vat_table():
    """إنشاء وتحديث جدول إعدادات الضريبة بأمان"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vat_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT DEFAULT 'ضريبة القيمة المضافة',
                rate REAL NOT NULL DEFAULT 0.15,
                is_active INTEGER DEFAULT 1 CHECK(is_active IN (0,1)),
                created_at TEXT
            )
        """)
        
        # إضافة الأعمدة الناقصة بأمان في حال وجود نسخة قديمة من الجدول
        columns = [row[1] for row in conn.execute("PRAGMA table_info(vat_config)").fetchall()]
        
        if 'name' not in columns:
            try:
                conn.execute("ALTER TABLE vat_config ADD COLUMN name TEXT DEFAULT 'ضريبة القيمة المضافة'")
            except sqlite3.OperationalError:
                pass

        if 'created_at' not in columns:
            try:
                conn.execute("ALTER TABLE vat_config ADD COLUMN created_at TEXT")
            except sqlite3.OperationalError:
                pass
            
        # التأكد من وجود سجل افتراضي مفعل
        count = conn.execute("SELECT COUNT(*) FROM vat_config").fetchone()[0]
        if count == 0:
            conn.execute("INSERT INTO vat_config (name, rate, is_active) VALUES ('ضريبة القيمة المضافة', 0.15, 1)")
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        # تتفادى عدم تحميل واجهة المستخدم عند وجود تنبيهات غير حرجة
        pass
    finally:
        conn.close()

# ========== إعدادات ونسب الضريبة ==========

def get_vat_rate():
    """جلب نسبة الضريبة الحالية المفعلة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT rate FROM vat_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
        return row["rate"] if row else 0.15
    except:
        return 0.15
    finally:
        conn.close()

def update_vat_rate(new_rate, name="ضريبة القيمة المضافة"):
    """تحديث نسبة الضريبة وإرشيف النسب القديمة"""
    conn = get_connection()
    try:
        conn.execute("UPDATE vat_config SET is_active = 0")
        conn.execute("INSERT INTO vat_config (name, rate, is_active) VALUES (?, ?, 1)", (name, new_rate))
        conn.commit()
        
        log_action("admin", "تحديث نسبة الضريبة", "vat_config", f"النسبة الجديدة: {new_rate * 100}%")
        return True, "تم تحديث نسبة الضريبة بنجاح"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_vat_history():
    """جلب سجل تغييرات نسب الضريبة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM vat_config ORDER BY id DESC LIMIT 20").fetchall()
        return [dict(r) for r in rows]
    except:
        return []
    finally:
        conn.close()

# ========== الحسابات والعمليات الحسابية ==========

def calculate_vat(amount, rate=None):
    """حساب قيمة الضريبة لمبلغ صافي"""
    if rate is None:
        rate = get_vat_rate()
    return round(amount * rate, 2)

def calculate_reverse_vat(total_amount, rate=None):
    """احتساب المبلغ قبل الضريبة وقيمة الضريبة من المبلغ الإجمالي"""
    if rate is None:
        rate = get_vat_rate()
    before_vat = round(total_amount / (1 + rate), 2)
    vat_amount = round(total_amount - before_vat, 2)
    return before_vat, vat_amount

# ========== تقارير الإقرار الضريبي وتصفية الفترة ==========

def get_vat_report(start_date=None, end_date=None):
    """تقرير ملخص الضريبة لفترة محددة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    date_clause = ""
    params = []
    if start_date and end_date:
        date_clause = " AND invoice_date BETWEEN ? AND ?"
        params = [start_date, end_date]
        
    query_sales = f"SELECT COALESCE(SUM(total), 0), COALESCE(SUM(vat_amount), 0) FROM invoices WHERE type='sale' AND status='completed'{date_clause}"
    query_purchases = f"SELECT COALESCE(SUM(total), 0), COALESCE(SUM(vat_amount), 0) FROM invoices WHERE type='purchase' AND status='completed'{date_clause}"
    
    sales = conn.execute(query_sales, params).fetchone()
    purchases = conn.execute(query_purchases, params).fetchone()
    conn.close()
    
    total_sales = sales[0]
    output_vat = sales[1]
    
    total_purchases = purchases[0]
    input_vat = purchases[1]
    
    net_vat = round(output_vat - input_vat, 2)
    
    return {
        "rate": get_vat_rate(),
        "total_sales": total_sales,
        "total_purchases": total_purchases,
        "output_vat": output_vat,
        "input_vat": input_vat,
        "net_vat": net_vat
    }

def get_tax_return_report(start_date=None, end_date=None):
    """تقرير الإقرار الضريبي التفصيلي للفواتير"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    date_clause = ""
    params = []
    if start_date and end_date:
        date_clause = " AND invoice_date BETWEEN ? AND ?"
        params = [start_date, end_date]
        
    sales_data = conn.execute(
        f"SELECT COALESCE(SUM(vat_amount),0), COALESCE(SUM(total - vat_amount),0) FROM invoices WHERE type='sale' AND status='completed'{date_clause}",
        params
    ).fetchone()
    
    purchases_data = conn.execute(
        f"SELECT COALESCE(SUM(vat_amount),0), COALESCE(SUM(total - vat_amount),0) FROM invoices WHERE type='purchase' AND status='completed'{date_clause}",
        params
    ).fetchone()
    
    invoices = conn.execute(
        f"SELECT id, type, invoice_date, total, vat_amount, vat_rate, COALESCE(reference, CAST(id AS TEXT)) AS invoice_number FROM invoices WHERE status='completed'{date_clause} ORDER BY invoice_date DESC",
        params
    ).fetchall()
    conn.close()
    
    output_vat = sales_data[0]
    sales_before_tax = sales_data[1]
    
    input_vat = purchases_data[0]
    purchases_before_tax = purchases_data[1]
    
    net_vat = round(output_vat - input_vat, 2)
    
    return {
        "rate": get_vat_rate(),
        "total_output_vat": output_vat,
        "total_input_vat": input_vat,
        "net_vat": net_vat,
        "sales_before_tax": sales_before_tax,
        "purchases_before_tax": purchases_before_tax,
        "invoices": [dict(inv) for inv in invoices]
    }

def post_vat_settlement_entry(settlement_date, start_date, end_date, description="تسوية وإقفال ضريبة القيمة المضافة للفترة"):
    """توليد قيد تسوية آلي لإقفال حسابات ضريبة المخرجات والمدخلات وتسجيل الالتزام الصافي"""
    report = get_vat_report(start_date, end_date)
    output_vat = report['output_vat']
    input_vat = report['input_vat']
    net_vat = report['net_vat']

    if output_vat == 0 and input_vat == 0:
        return False, "لا توجد مبالغ ضريبية مستحقة للتسوية خلال هذه الفترة"

    vat_output_acc = get_functional_account("sales_tax")
    vat_input_acc = get_functional_account("purchase_tax")
    vat_payable_acc = get_functional_account("sales_tax")

    lines = [
        # إقفال ضريبة المخرجات
        {
            "account_name": vat_output_acc,
            "debit": output_vat,
            "credit": 0.0,
            "currency_code": "YER",
            "exchange_rate": 1.0
        },
        # إقفال ضريبة المدخلات
        {
            "account_name": vat_input_acc,
            "debit": 0.0,
            "credit": input_vat,
            "currency_code": "YER",
            "exchange_rate": 1.0
        }
    ]

    # تسجيل الفارق في حساب الضريبة المستحقة السداد/الاسترداد
    if net_vat > 0:
        lines.append({
            "account_name": vat_payable_acc,
            "debit": 0.0,
            "credit": net_vat,
            "currency_code": "YER",
            "exchange_rate": 1.0
        })
    elif net_vat < 0:
        lines.append({
            "account_name": vat_payable_acc,
            "debit": abs(net_vat),
            "credit": 0.0,
            "currency_code": "YER",
            "exchange_rate": 1.0
        })

    journal_id = save_journal_entry(
        entry_date=settlement_date,
        description=f"{description} ({start_date} إلى {end_date})",
        lines=lines
    )

    log_action("admin", "إصدار قيد تسوية الضريبة", "journal_entries", f"رقم القيد: {journal_id}, الصافي: {net_vat}")
    return True, f"تم إنشاء قيد التسوية الضريبية بنجاح برقم قيد: {journal_id}"
