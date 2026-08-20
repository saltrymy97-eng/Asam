# services/fifo_service.py – منطق FIFO للمخزون (إصدار تجاري متكامل ومستقر)
import sqlite3
from datetime import date
from database import get_connection

def create_fifo_tables():
    """إنشاء جداول FIFO إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            batch_date TEXT NOT NULL,
            reference TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fifo_consumptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            consumed_qty REAL NOT NULL,
            consumption_date TEXT NOT NULL,
            reference TEXT,
            FOREIGN KEY (batch_id) REFERENCES inventory_batches(id)
        )
    """)
    conn.commit()
    conn.close()

def add_batch(product_id, quantity, unit_cost, batch_date, reference="", conn=None):
    """إضافة دفعة شراء مع حماية العملية واعتماد الحفظ"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute(
            "INSERT INTO inventory_batches (product_id, quantity, unit_cost, batch_date, reference) VALUES (?,?,?,?,?)",
            (product_id, quantity, unit_cost, batch_date, reference)
        )
        # تم إضافة الـ commit لحفظ البيانات فعلياً في قاعدة البيانات
        if own_conn:
            conn.commit()
        return True, None
    except Exception as e:
        if own_conn:
            conn.rollback()
        return False, str(e)
    finally:
        if own_conn:
            conn.close()

def get_available_batches(product_id, conn=None):
    """جلب الدفعات المتاحة لمنتج معين (يدعم اتصال خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        own_conn = True
    cursor = conn.execute("""
        SELECT b.*, 
               b.quantity - COALESCE(SUM(c.consumed_qty), 0) as remaining
        FROM inventory_batches b
        LEFT JOIN fifo_consumptions c ON b.id = c.batch_id
        WHERE b.product_id = ?
        GROUP BY b.id
        HAVING remaining > 0
        ORDER BY b.batch_date ASC, b.id ASC
    """, (product_id,))
    batches = [dict(row) for row in cursor.fetchall()]
    if own_conn:
        conn.close()
    return batches

def get_consumed_batches(product_id, conn=None):
    """جلب الدفعات المستهلكة لمنتج معين (للإرجاع)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        own_conn = True
    cursor = conn.execute("""
        SELECT b.*, 
               COALESCE(SUM(c.consumed_qty), 0) as total_consumed
        FROM inventory_batches b
        JOIN fifo_consumptions c ON b.id = c.batch_id
        WHERE b.product_id = ?
        GROUP BY b.id
        HAVING total_consumed > 0
        ORDER BY b.batch_date DESC, b.id DESC
    """, (product_id,))
    batches = [dict(row) for row in cursor.fetchall()]
    if own_conn:
        conn.close()
    return batches

def get_fifo_cost(product_id, quantity, conn=None):
    """حساب تكلفة الكمية المطلوبة حسب FIFO"""
    batches = get_available_batches(product_id, conn)
    total_cost = 0.0
    remaining = quantity
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch["remaining"], remaining)
        total_cost += take * batch["unit_cost"]
        remaining -= take
    if remaining > 0:
        return None
    return total_cost

def consume_fifo(product_id, quantity, consumption_date=None, conn=None, reference=""):
    """استهلاك المخزون حسب FIFO (يدعم التواريخ المخصصة)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
        conn.execute("BEGIN")

    if consumption_date is None:
        consumption_date = date.today().strftime("%Y-%m-%d")

    try:
        batches = get_available_batches(product_id, conn)
        total_cost = 0.0
        remaining_to_consume = quantity

        for batch in batches:
            if remaining_to_consume <= 0:
                break
            qty_available = batch["remaining"]
            qty_to_take = min(qty_available, remaining_to_consume)
            cost = qty_to_take * batch["unit_cost"]
            total_cost += cost

            conn.execute(
                "INSERT INTO fifo_consumptions (batch_id, consumed_qty, consumption_date, reference) VALUES (?,?,?,?)",
                (batch["id"], qty_to_take, consumption_date, reference)
            )
            remaining_to_consume -= qty_to_take

        if remaining_to_consume > 0:
            if own_conn:
                conn.rollback()
            return None, remaining_to_consume

        if own_conn:
            conn.commit()
        return total_cost, 0
    except Exception as e:
        if own_conn:
            conn.rollback()
        return None, str(e)
    finally:
        if own_conn:
            conn.close()

def return_fifo_to_original_batch(product_id, quantity, sale_invoice_id, conn=None, reference=""):
    """إعادة بضاعة مرتجع المبيعات لنفس دفعة الشراء الأصلية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
        conn.execute("BEGIN")

    try:
        sale_ref = f"فاتورة مبيعات #{sale_invoice_id}"
        consumptions = conn.execute("""
            SELECT c.id, c.batch_id, c.consumed_qty, b.unit_cost
            FROM fifo_consumptions c
            JOIN inventory_batches b ON c.batch_id = b.id
            WHERE c.reference = ? AND b.product_id = ?
            ORDER BY c.id ASC
        """, (sale_ref, product_id)).fetchall()

        if not consumptions:
            if own_conn:
                conn.rollback()
            return None, f"لا توجد سجلات استهلاك FIFO للمنتج {product_id} في فاتورة البيع #{sale_invoice_id}"

        total_consumed = sum(c["consumed_qty"] for c in consumptions)
        
        return_ref = f"مرتجع مبيعات"
        already_returned = conn.execute("""
            SELECT COALESCE(SUM(fc2.consumed_qty), 0)
            FROM fifo_consumptions fc2
            WHERE fc2.reference LIKE ? AND fc2.batch_id IN (
                SELECT c.batch_id FROM fifo_consumptions c WHERE c.reference = ?
            )
        """, (f"%{return_ref}%", sale_ref)).fetchone()[0]

        available_to_return = total_consumed - already_returned

        if quantity > available_to_return:
            if own_conn:
                conn.rollback()
            return None, f"الكمية المطلوبة ({quantity}) أكبر من المتاح للإرجاع ({available_to_return})"

        total_cost = 0.0
        remaining = quantity

        for cons in consumptions:
            if remaining <= 0:
                break
            
            take = min(cons["consumed_qty"], remaining)
            cost = take * cons["unit_cost"]
            total_cost += cost

            if take >= cons["consumed_qty"]:
                conn.execute("DELETE FROM fifo_consumptions WHERE id = ?", (cons["id"],))
            else:
                conn.execute(
                    "UPDATE fifo_consumptions SET consumed_qty = consumed_qty - ? WHERE id = ?",
                    (take, cons["id"])
                )

            remaining -= take

        if own_conn:
            conn.commit()
        return total_cost, 0

    except Exception as e:
        if own_conn:
            conn.rollback()
        return None, str(e)
    finally:
        if own_conn:
            conn.close()

def return_fifo(product_id, quantity, unit_cost, batch_date=None, conn=None, reference=""):
    """إعادة بضاعة للمخزون (إنشاء دفعة جديدة مع دعم تحديد التاريخ)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
        conn.execute("BEGIN")
        
    if batch_date is None:
        batch_date = date.today().strftime("%Y-%m-%d")
        
    try:
        conn.execute(
            "INSERT INTO inventory_batches (product_id, quantity, unit_cost, batch_date, reference) VALUES (?,?,?,?,?)",
            (product_id, quantity, unit_cost, batch_date, reference)
        )
        if own_conn:
            conn.commit()
        return True, None
    except Exception as e:
        if own_conn:
            conn.rollback()
        return False, str(e)
    finally:
        if own_conn:
            conn.close()

def remove_last_batch(product_id, quantity, consumption_date=None, conn=None, reference=""):
    """خصم دفعة من المخزون حسب LIFO (مرتجع مشتريات مع دعم تحديد التاريخ)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
        conn.execute("BEGIN")
        
    if consumption_date is None:
        consumption_date = date.today().strftime("%Y-%m-%d")
        
    try:
        batches = get_available_batches(product_id, conn)
        if not batches:
            if own_conn:
                conn.rollback()
            return None, "لا توجد دفعات متاحة للمنتج"
        latest = batches[-1]
        if quantity > latest["remaining"]:
            if own_conn:
                conn.rollback()
            return None, f"الكمية المطلوبة ({quantity}) أكبر من أحدث دفعة ({latest['remaining']})"
        cost = quantity * latest["unit_cost"]
        
        conn.execute(
            "INSERT INTO fifo_consumptions (batch_id, consumed_qty, consumption_date, reference) VALUES (?,?,?,?)",
            (latest["id"], quantity, consumption_date, reference)
        )
        if own_conn:
            conn.commit()
        return cost, 0
    except Exception as e:
        if own_conn:
            conn.rollback()
        return None, str(e)
    finally:
        if own_conn:
            conn.close()

def get_product_cost(product_id):
    """تكلفة المخزون المتبقي حسب FIFO"""
    batches = get_available_batches(product_id)
    return sum(b["remaining"] * b["unit_cost"] for b in batches)

def get_products_for_select():
    """جلب المنتجات للاختيار"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute("SELECT id, name FROM products ORDER BY name").fetchall()
    conn.close()
    return [dict(p) for p in products]
