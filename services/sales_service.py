# services/sales_service.py – منطق أعمال المبيعات (مع إدارة العمليات)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action

def get_customers():
    """جلب العملاء"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
    conn.close()
    return [dict(c) for c in customers]

def get_products_for_sale():
    """جلب المنتجات المتاحة للبيع (الكمية > 0)"""
    conn = get_connection()
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
    total = sum(item["quantity"] * item["unit_price"] for item in items)
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        conn.execute("BEGIN")
        
        cur = conn.execute(
            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('sale', ?, date('now'), ?, 'completed')",
            (customer_id, total)
        )
        invoice_id = cur.lastrowid
        
        for item in items:
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'out', ?, date('now'), ?)",
                (item["product_id"], item["quantity"], f"فاتورة مبيعات #{invoice_id}")
            )
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (item["quantity"], item["product_id"])
            )
        
        conn.commit()
        
        customer_name = "غير معروف"
        try:
            row = conn.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if row:
                customer_name = row["name"]
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
        conn.rollback()
        return None, 0, str(e)
    finally:
        conn.close()

def get_sale_invoices():
    """جلب فواتير المبيعات المسجلة"""
    conn = get_connection()
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
    conn = get_connection()
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
    conn = get_connection()
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
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(c) for c in customers]
