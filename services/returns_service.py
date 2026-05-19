# services/returns_service.py - منطق أعمال مرتجعات البضاعة (مع الكمية المرتجعة)
import sqlite3

DB_PATH = "erp.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_reason_column():
    """إضافة عمود reason لجدول invoices إذا لم يكن موجوداً"""
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN reason TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def get_sales_invoices():
    """جلب فواتير المبيعات المكتملة"""
    conn = get_connection()
    invoices = conn.execute("""
        SELECT i.id, i.invoice_date, c.name as customer, i.total
        FROM invoices i
        JOIN customers c ON i.party_id = c.id
        WHERE i.type = 'sale' AND i.status = 'completed'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return invoices

def get_purchase_invoices():
    """جلب فواتير المشتريات المكتملة"""
    conn = get_connection()
    invoices = conn.execute("""
        SELECT i.id, i.invoice_date, s.name as supplier, i.total
        FROM invoices i
        JOIN suppliers s ON i.party_id = s.id
        WHERE i.type = 'purchase' AND i.status = 'completed'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return invoices

def get_invoice_items(invoice_id):
    """جلب بنود فاتورة محددة مع اسم المنتج"""
    conn = get_connection()
    items = conn.execute("""
        SELECT ii.id, ii.quantity, ii.unit_price, p.name
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    return items

def process_return(invoice_type, invoice_id, items_to_return, return_date, reason=""):
    """تنفيذ عملية المرتجع"""
    add_reason_column()
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO invoices (type, party_id, invoice_date, total, status, reason)
            VALUES (?, ?, ?, 0, 'completed', ?)
        """, (f'{invoice_type}_return', 0, return_date, reason))
        return_invoice_id = cursor.lastrowid
        total_return = 0.0
        for product_name, qty in items_to_return:
            product = conn.execute(
                "SELECT id, purchase_price, selling_price FROM products WHERE name = ?",
                (product_name,)
            ).fetchone()
            if not product:
                continue
            unit_price = product["selling_price"] if invoice_type == "sale" else product["purchase_price"]
            line_total = qty * unit_price
            total_return += line_total
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (return_invoice_id, product["id"], qty, unit_price))
            if invoice_type == "sale":
                conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (qty, product["id"]))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'in', ?, ?, ?)
                """, (product["id"], qty, return_date, f"مرتجع مبيعات #{return_invoice_id}"))
            else:
                conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (qty, product["id"]))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'out', ?, ?, ?)
                """, (product["id"], qty, return_date, f"مرتجع مشتريات #{return_invoice_id}"))
        conn.execute("UPDATE invoices SET total = ? WHERE id = ?", (total_return, return_invoice_id))
        conn.commit()
        return True, return_invoice_id, total_return
    except Exception as e:
        conn.rollback()
        return False, str(e), 0
    finally:
        conn.close()

def get_return_history():
    """سجل المرتجعات مع سبب الإرجاع والكمية المرتجعة"""
    add_reason_column()
    conn = get_connection()
    returns = conn.execute("""
        SELECT 
            i.id, 
            i.type, 
            i.invoice_date, 
            i.total, 
            i.status, 
            i.reason,
            (SELECT SUM(ii.quantity) FROM invoice_items ii WHERE ii.invoice_id = i.id) as total_qty
        FROM invoices i
        WHERE i.type IN ('sale_return', 'purchase_return')
        ORDER BY i.id DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return returns
