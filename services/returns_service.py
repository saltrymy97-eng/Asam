# services/returns_service.py – منطق أعمال المرتجعات (مع إدارة العمليات - نسخة آمنة)
import sqlite3
from database import get_connection
from services.audit_service import log_action

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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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
    conn.row_factory = sqlite3.Row
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
    تنفيذ عملية المرتجع مع إدارة العمليات
    :param invoice_type: 'sale' أو 'purchase'
    :param invoice_id: رقم الفاتورة الأصلية
    :param items_to_return: قائمة من (product_name, quantity)
    :param return_date: تاريخ المرتجع
    :param reason: سبب المرتجع
    """
    add_reason_column()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. حساب الإجمالي أولاً لتجنب UPDATE إضافي
        total_return = 0.0
        items_data = []
        
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
            items_data.append((product["id"], qty, unit_price, line_total))
        
        if total_return == 0:
            return False, "لا توجد منتجات صالحة للمرتجع", 0
        
        # 2. بدء العملية المحمية
        conn.execute("BEGIN")
        
        # 🆕 إدراج فاتورة المرتجع مع الإجمالي الفعلي و party_id = NULL (آمن)
        cursor = conn.execute("""
            INSERT INTO invoices (type, party_id, invoice_date, total, status, reason)
            VALUES (?, NULL, ?, ?, 'completed', ?)
        """, (f'{invoice_type}_return', return_date, total_return, reason))
        return_invoice_id = cursor.lastrowid
        
        # 3. إدراج البنود وتحديث المخزون
        for product_id, qty, unit_price, line_total in items_data:
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (return_invoice_id, product_id, qty, unit_price))
            
            if invoice_type == "sale":
                # مرتجع مبيعات: نرجع البضاعة للمخزون
                conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (qty, product_id))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'in', ?, ?, ?)
                """, (product_id, qty, return_date, f"مرتجع مبيعات #{return_invoice_id}"))
            else:
                # مرتجع مشتريات: نخرج البضاعة من المخزون
                conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (qty, product_id))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'out', ?, ?, ?)
                """, (product_id, qty, return_date, f"مرتجع مشتريات #{return_invoice_id}"))
        
        conn.commit()
        
        # 4. تسجيل العملية في سجل التدقيق
        return_type_name = "مرتجع مبيعات" if invoice_type == "sale" else "مرتجع مشتريات"
        log_action(
            username="admin",
            action=return_type_name,
            table_name="invoices",
            record_id=return_invoice_id,
            new_value=f"الإجمالي: {total_return:,.2f}, السبب: {reason}"
        )
        
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
    conn.row_factory = sqlite3.Row
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
