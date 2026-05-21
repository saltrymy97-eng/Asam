# services/fifo_service.py – منطق FIFO للمخزون (مع إدارة العمليات)
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

def add_batch(product_id, quantity, unit_cost, batch_date, reference=""):
    """إضافة دفعة شراء مع حماية العملية"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO inventory_batches (product_id, quantity, unit_cost, batch_date, reference) VALUES (?,?,?,?,?)",
            (product_id, quantity, unit_cost, batch_date, reference)
        )
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_available_batches(product_id):
    """جلب الدفعات المتاحة لمنتج معين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
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
    conn.close()
    return batches

def consume_fifo(product_id, quantity, consumption_date, reference=""):
    """استهلاك المخزون حسب FIFO مع حماية العملية"""
    batches = get_available_batches(product_id)
    total_cost = 0.0
    remaining_to_consume = quantity
    conn = get_connection()
    
    try:
        conn.execute("BEGIN")
        
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
            conn.rollback()
            conn.close()
            return None, remaining_to_consume

        conn.commit()
        return total_cost, 0
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
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
