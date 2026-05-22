# services/sales_service.py – منطق أعمال المبيعات (PostgreSQL)
import psycopg2.extras
from datetime import date
from database import get_connection
from services.audit_service import log_action

def _dict_cursor(conn):
    """إرجاع cursor بقاموس للقراءة فقط"""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def get_customers():
    """جلب العملاء"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT id, name FROM customers ORDER BY name")
    customers = c.fetchall()
    conn.close()
    return [dict(row) for row in customers]

def get_products_for_sale():
    """جلب المنتجات المتاحة للبيع (الكمية > 0)"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT id, name, selling_price, quantity FROM products WHERE quantity > 0 ORDER BY name")
    products = c.fetchall()
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
    
    try:
        conn.execute("BEGIN")
        c = conn.cursor()
        
        c.execute(
            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('sale', %s, CURRENT_DATE, %s, 'completed') RETURNING id",
            (customer_id, total)
        )
        invoice_id = c.fetchone()[0]
        
        for item in items:
            c.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
            )
            c.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (%s, 'out', %s, CURRENT_DATE, %s)",
                (item["product_id"], item["quantity"], f"فاتورة مبيعات #{invoice_id}")
            )
            c.execute(
                "UPDATE products SET quantity = quantity - %s WHERE id = %s",
                (item["quantity"], item["product_id"])
            )
        
        conn.commit()
        
        customer_name = "غير معروف"
        try:
            c2 = _dict_cursor(conn)
            c2.execute("SELECT name FROM customers WHERE id = %s", (customer_id,))
            row = c2.fetchone()
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
    c = _dict_cursor(conn)
    c.execute("""
        SELECT i.id, c.name as customer, i.invoice_date, i.total, i.status
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id
        WHERE i.type = 'sale'
        ORDER BY i.id DESC
    """)
    invoices = c.fetchall()
    conn.close()
    return [dict(inv) for inv in invoices]

def get_invoice_details(invoice_id):
    """جلب تفاصيل فاتورة محددة"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("""
        SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = %s
    """, (invoice_id,))
    details = c.fetchall()
    conn.close()
    return [dict(d) for d in details]

def add_customer(name, phone, address, username="admin"):
    """إضافة عميل جديد"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO customers (name, phone, address) VALUES (%s, %s, %s)",
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
    c = _dict_cursor(conn)
    c.execute("SELECT * FROM customers ORDER BY id DESC")
    customers = c.fetchall()
    conn.close()
    return [dict(cust) for cust in customers]
