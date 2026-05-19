# services/returns_service.py - منطق أعمال مرتجعات البضاعة
import sqlite3

DB_PATH = "erp.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    """
    تنفيذ عملية المرتجع:
    - invoice_type: 'sale' أو 'purchase'
    - invoice_id: رقم الفاتورة
    - items_to_return: قائمة من (product_name, quantity)
    - return_date: تاريخ المرتجع
    - reason: سبب الإرجاع
    """
    conn = get_connection()
    
    try:
        # 1. إنشاء فاتورة مرتجع
        cursor = conn.execute("""
            INSERT INTO invoices (type, party_id, invoice_date, total, status)
            VALUES (?, ?, ?, 0, 'completed')
        """, (f'{invoice_type}_return', 0, return_date))
        return_invoice_id = cursor.lastrowid
        
        total_return = 0.0
        
        for product_name, qty in items_to_return:
            # جلب المنتج من جدول products
            product = conn.execute(
                "SELECT id, purchase_price, selling_price FROM products WHERE name = ?",
                (product_name,)
            ).fetchone()
            
            if not product:
                continue
            
            # تحديد السعر حسب نوع الفاتورة
            unit_price = product["selling_price"] if invoice_type == "sale" else product["purchase_price"]
            line_total = qty * unit_price
            total_return += line_total
            
            # إضافة بند المرتجع
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (return_invoice_id, product["id"], qty, unit_price))
            
            # تحديث المخزون (عكس حركة الفاتورة الأصلية)
            if invoice_type == "sale":
                # مرتجع مبيعات: زيادة المخزون
                conn.execute(
                    "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                    (qty, product["id"])
                )
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'in', ?, ?, ?)
                """, (product["id"], qty, return_date, f"مرتجع مبيعات #{return_invoice_id}"))
            else:
                # مرتجع مشتريات: تقليل المخزون
                conn.execute(
                    "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                    (qty, product["id"])
                )
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'out', ?, ?, ?)
                """, (product["id"], qty, return_date, f"مرتجع مشتريات #{return_invoice_id}"))
        
        # تحديث إجمالي فاتورة المرتجع
        conn.execute(
            "UPDATE invoices SET total = ? WHERE id = ?",
            (total_return, return_invoice_id)
        )
        
        conn.commit()
        return True, return_invoice_id, total_return
    except Exception as e:
        conn.rollback()
        return False, str(e), 0
    finally:
        conn.close()

def get_return_history():
    """سجل المرتجعات"""
    conn = get_connection()
    returns = conn.execute("""
        SELECT id, type, invoice_date, total, status
        FROM invoices
        WHERE type IN ('sale_return', 'purchase_return')
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return returns
