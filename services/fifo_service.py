# services/fifo_service.py – منطق FIFO للمخزون (متوافق مع المعاملات المشتركة)
import sqlite3
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
    """إضافة دفعة شراء مع حماية العملية (يدعم اتصال خارجي)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN")
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

def get_fifo_cost(product_id, quantity, conn=None):
    """
    حساب تكلفة الكمية المطلوبة حسب FIFO (بدون استهلاك فعلي).
    يُرجع التكلفة الإجمالية أو None إذا كانت الكمية غير كافية.
    """
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
        return None  # لا توجد دفعات كافية
    return total_cost

def consume_fifo(product_id, quantity, conn=None, reference=""):
    """
    استهلاك المخزون حسب FIFO مع حماية العملية (يدعم اتصال خارجي).
    إذا تم تمرير conn، يفترض أن المعاملة تدار خارجياً.
    """
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

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
                "INSERT INTO fifo_consumptions (batch_id, consumed_qty, consumption_date, reference) VALUES (?,?,?, date('now'), ?)",
                (batch["id"], qty_to_take, reference)
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
