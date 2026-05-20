# services/sales_service.py – منطق أعمال المبيعات (مع إدارة العمليات)
import sqlite3
from datetime import date
from services.transaction import protected_connection

DB_PATH = "erp.db"

def get_customers():
    """جلب العملاء"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
    conn.close()
    return [dict(c) for c in customers]

def get_products_for_sale():
    """جلب المنتجات المتاحة للبيع (الكمية > 0)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    products = conn.execute("SELECT id, name, selling_price, quantity FROM products WHERE quantity > 0 ORDER BY name").fetchall()
    conn.close()
    return [dict(p) for p in products]

def create_sale_invoice(customer_id, items, username="admin"):
    """
    إنشاء فاتورة مبيعات محمية بالكامل.
    items: قائمة من dict تحتوي على product_id, quantity, unit_price
    تُرجع (invoice_id, total, error_message)
    """
    from services.audit_service import log_action
    
    total = sum(item["quantity"] * item["unit_price"] for item in items)
    
    try:
        with protected_connection() as conn:
            # 1. إنشاء الفاتورة
            cur = conn.execute(
                "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('sale', ?, date('now'), ?, 'completed')",
                (customer_id, total)
            )
            invoice_id = cur.lastrowid
            
            # 2. إدراج البنود وتحديث المخزون
            for item in items:
                # إدراج بند الفاتورة
                conn.execute(
                    "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
                )
                # تسجيل حركة مخزون (خارج)
                conn.execute(
                    "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'out', ?, date('now'), ?)",
                    (item["product_id"], item["quantity"], f"فاتورة مبيعات #{invoice_id}")
                )
                # تقليل المخزون
                conn.execute(
                    "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                    (item["quantity"], item["product_id"])
                )
        
        # تسجيل في سجل التدقيق (خارج العملية المحمية)
        customer_name = "غير معروف"
        try:
            conn_temp = sqlite3.connect(DB_PATH)
            row = conn_temp.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if row:
                customer_name = row[0]
            conn_temp.close()
        except:
            pass
        
        log_action(
            username=username,
            action="فاتورة مبيعات",
            table_name="invoices",
            record_id=invoice_id,
            new_value=f"العميل: {customer_name}, الإجمالي: {total:,.2f}"
        )
        
        return invoice_id, total, None
        
    except Exception as e:
        return None, 0, str(e)

def get_sale_invoices():
    """جلب فواتير المبيعات المسجلة"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, c.name as customer, i.invoice_date, i.total, i.status
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id
        WHERE i.type = 'sale'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return [dict(inv) for inv in invoices]

def get_invoice_details(invoice_id):
    """جلب تفاصيل فاتورة محددة"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    details = conn.execute("""
        SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    return [dict(d) for d in details]

def add_customer(name, phone, address, username="admin"):
    """إضافة عميل جديد"""
    from services.audit_service import log_action
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
        (name, phone, address)
    )
    conn.commit()
    conn.close()
    
    log_action(
        username=username,
        action="إضافة عميل",
        table_name="customers",
        new_value=f"العميل: {name}, الهاتف: {phone}"
    )
    return True

def get_all_customers():
    """جلب جميع العملاء"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(c) for c in customers]
