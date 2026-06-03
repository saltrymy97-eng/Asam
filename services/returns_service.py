# services/returns_service.py – منطق أعمال المرتجعات (مع إدارة العمليات - نسخة آمنة ومُحسَّنة)
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

def add_reference_column():
    """إضافة عمود reference لجدول invoices إذا لم يكن موجوداً"""
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN reference INTEGER")
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
    """جلب بنود فاتورة محددة مع اسم المنتج والكمية المتاحة للإرجاع"""
    add_reason_column()
    add_reference_column()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    items = conn.execute("""
        SELECT ii.id, ii.quantity, ii.unit_price, p.name, ii.product_id
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    
    result = []
    for item in items:
        returned_qty = conn.execute("""
            SELECT COALESCE(SUM(ri.quantity), 0)
            FROM invoice_items ri
            JOIN invoices r ON ri.invoice_id = r.id
            WHERE r.type IN ('sale_return', 'purchase_return')
              AND r.reference = ?
              AND ri.product_id = ?
        """, (invoice_id, item["product_id"])).fetchone()[0]
        
        available = item["quantity"] - returned_qty
        result.append({
            "id": item["id"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
            "name": item["name"],
            "available_qty": max(0, available),
            "product_id": item["product_id"]
        })
    
    conn.close()
    return result

def process_return(invoice_type, invoice_id, items_to_return, return_date, reason=""):
    """
    تنفيذ عملية المرتجع مع إدارة العمليات والتحقق من الكميات والرصيد
    """
    add_reason_column()
    add_reference_column()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. التحقق من الكميات المتاحة للإرجاع
        available_items = get_invoice_items(invoice_id)
        available_dict = {item['name']: item for item in available_items}
        
        for product_name, qty in items_to_return:
            if product_name not in available_dict:
                return False, f"المنتج '{product_name}' غير موجود في الفاتورة الأصلية", 0
            if qty > available_dict[product_name]['available_qty']:
                return False, f"الكمية المطلوبة ({qty}) أكبر من المتاح للإرجاع ({available_dict[product_name]['available_qty']}) للمنتج '{product_name}'", 0
        
        # ✅ حماية إضافية لمرتجع المشتريات: التحقق من الرصيد الحالي
        if invoice_type == "purchase":
            for product_name, qty in items_to_return:
                current = conn.execute(
                    "SELECT quantity FROM products WHERE name = ?", (product_name,)
                ).fetchone()
                if not current:
                    return False, f"المنتج '{product_name}' غير موجود في المخزون", 0
                if qty > current["quantity"]:
                    return False, f"لا يمكن إرجاع {qty} وحدة من '{product_name}'. الرصيد الحالي: {current['quantity']} فقط", 0
        
        # 2. حساب الإجمالي
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
        
        # 3. بدء العملية المحمية
        conn.execute("BEGIN")
        
        cursor = conn.execute("""
            INSERT INTO invoices (type, party_id, invoice_date, total, status, reason, reference)
            VALUES (?, NULL, ?, ?, 'completed', ?, ?)
        """, (f'{invoice_type}_return', return_date, total_return, reason, invoice_id))
        return_invoice_id = cursor.lastrowid
        
        # 4. إدراج البنود وتحديث المخزون
        for product_id, qty, unit_price, line_total in items_data:
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (return_invoice_id, product_id, qty, unit_price))
            
            if invoice_type == "sale":
                conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (qty, product_id))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'in', ?, ?, ?)
                """, (product_id, qty, return_date, f"مرتجع مبيعات #{return_invoice_id}"))
            else:
                conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (qty, product_id))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'out', ?, ?, ?)
                """, (product_id, qty, return_date, f"مرتجع مشتريات #{return_invoice_id}"))
        
        conn.commit()
        
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
