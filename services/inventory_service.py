# services/inventory_service.py – منطق إدارة المخزون (مع إدارة العمليات وحماية من الصرف الزائد)
import sqlite3
from database import get_connection
from services.audit_service import log_action

def get_all_products():
    """جلب جميع المنتجات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(p) for p in products]

def add_product(name, barcode, category, purchase_price, selling_price, quantity, reorder_level, username="admin"):
    """إضافة منتج جديد مع حماية العملية"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO products (name, barcode, category, purchase_price, selling_price, quantity, reorder_level)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, barcode if barcode else None, category, purchase_price, selling_price, quantity, reorder_level)
        )
        conn.commit()
        
        log_action(
            username=username,
            action="إضافة منتج",
            table_name="products",
            new_value=f"المنتج: {name}, السعر: {selling_price}"
        )
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def record_stock_movement(product_id, product_name, move_type, quantity, reference, username="admin"):
    """
    تسجيل حركة مخزون مع حماية العملية ومنع الصرف الزائد
    :param move_type: 'داخل' أو 'خارج'
    """
    conn = get_connection()
    try:
        # تحديد نوع الحركة باللغة الإنجليزية
        if "داخل" in move_type or "in" in move_type.lower():
            type_en = "in"
            sign = 1
        else:
            type_en = "out"
            sign = -1

        # ✅ حماية: إذا كانت الحركة صرف، تحقق من الرصيد المتاح
        if type_en == "out":
            current = conn.execute(
                "SELECT quantity FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if not current:
                return False, "المنتج غير موجود"
            available = current[0]
            if quantity > available:
                return False, f"❌ لا يمكن صرف {quantity} وحدة. الرصيد المتاح: {available} فقط"

        # بدء المعاملة المحمية
        conn.execute("BEGIN")
        
        # تسجيل الحركة
        conn.execute(
            "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, ?, ?, date('now'), ?)",
            (product_id, type_en, quantity, reference)
        )
        
        # تحديث الكمية
        conn.execute(
            "UPDATE products SET quantity = quantity + ? WHERE id = ?",
            (sign * quantity, product_id)
        )
        
        conn.commit()
        
        log_action(
            username=username,
            action="حركة مخزون",
            table_name="stock_movements",
            new_value=f"{move_type} - المنتج: {product_name}, الكمية: {quantity}"
        )
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_stock_movements(limit=50):
    """سجل حركات المخزون"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    movements = conn.execute("""
        SELECT sm.id, p.name as product, sm.type, sm.quantity, sm.date, sm.reference
        FROM stock_movements sm
        JOIN products p ON sm.product_id = p.id
        ORDER BY sm.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(m) for m in movements]

def get_low_stock_products():
    """المنتجات تحت الحد الأدنى"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute(
        "SELECT name, quantity, reorder_level FROM products WHERE quantity < reorder_level"
    ).fetchall()
    conn.close()
    return [dict(p) for p in products]

def get_products_for_select():
    """جلب المنتجات للاختيار (id, name)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute("SELECT id, name FROM products ORDER BY name").fetchall()
    conn.close()
    return [dict(p) for p in products]
