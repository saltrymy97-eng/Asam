# services/purchases_service.py – منطق أعمال المشتريات (PostgreSQL)
import psycopg2.extras
from datetime import date
from database import get_connection
from services.audit_service import log_action

def _dict_cursor(conn):
    """إرجاع cursor بقاموس للقراءة فقط"""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def get_suppliers():
    """جلب الموردين"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = c.fetchall()
    conn.close()
    return [dict(s) for s in suppliers]

def get_products_for_purchase():
    """جلب جميع المنتجات للشراء"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT id, name, purchase_price FROM products ORDER BY name")
    products = c.fetchall()
    conn.close()
    return [dict(p) for p in products]

def create_purchase_invoice(supplier_id, items, username="admin"):
    """
    إنشاء فاتورة مشتريات محمية بالكامل.
    items: قائمة من dict تحتوي على product_id, quantity, unit_price
    تُرجع (invoice_id, total, error_message)
    """
    total = sum(item["quantity"] * item["unit_price"] for item in items)
    conn = get_connection()

    try:
        conn.execute("BEGIN")
        c = conn.cursor()

        supplier_check = c.execute("SELECT id FROM suppliers WHERE id = %s", (supplier_id,)).fetchone()
        if not supplier_check:
            conn.rollback()
            conn.close()
            return None, 0, "المورد غير موجود"

        for item in items:
            product_check = c.execute("SELECT id FROM products WHERE id = %s", (item["product_id"],)).fetchone()
            if not product_check:
                conn.rollback()
                conn.close()
                return None, 0, f"المنتج {item.get('name', item['product_id'])} غير موجود"

        c.execute(
            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('purchase', %s, CURRENT_DATE, %s, 'completed') RETURNING id",
            (supplier_id, total)
        )
        invoice_id = c.fetchone()[0]

        for item in items:
            c.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
            )
            c.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (%s, 'in', %s, CURRENT_DATE, %s)",
                (item["product_id"], item["quantity"], f"فاتورة مشتريات #{invoice_id}")
            )
            c.execute(
                "UPDATE products SET quantity = quantity + %s WHERE id = %s",
                (item["quantity"], item["product_id"])
            )

        conn.commit()

        supplier_name = "غير معروف"
        try:
            c2 = _dict_cursor(conn)
            c2.execute("SELECT name FROM suppliers WHERE id = %s", (supplier_id,))
            row = c2.fetchone()
            if row:
                supplier_name = row["name"]
        except:
            pass

        log_action(
            username=username,
            action="فاتورة مشتريات",
            table_name="invoices",
            record_id=invoice_id,
            new_value=f"المورد: {supplier_name}, الإجمالي: {total:,.2f}"
        )

        return invoice_id, total, None

    except Exception as e:
        conn.rollback()
        return None, 0, str(e)
    finally:
        conn.close()

def get_purchase_invoices():
    """جلب فواتير المشتريات المسجلة"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("""
        SELECT i.id, s.name as supplier, i.invoice_date, i.total, i.status
        FROM invoices i
        LEFT JOIN suppliers s ON i.party_id = s.id
        WHERE i.type = 'purchase'
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

def add_supplier(name, phone, address, username="admin"):
    """إضافة مورد جديد"""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO suppliers (name, phone, address) VALUES (%s, %s, %s)",
        (name, phone, address)
    )
    conn.commit()
    conn.close()

    log_action(
        username=username,
        action="إضافة مورد",
        table_name="suppliers",
        new_value=f"المورد: {name}, الهاتف: {phone}"
    )
    return True

def get_all_suppliers():
    """جلب جميع الموردين"""
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT * FROM suppliers ORDER BY id DESC")
    suppliers = c.fetchall()
    conn.close()
    return [dict(s) for s in suppliers]
