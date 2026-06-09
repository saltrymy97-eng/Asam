# services/inventory_adjustment_service.py – التسويات المخزنية والجرد (متكاملة محاسبياً)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.fifo_service import consume_fifo, add_batch, get_fifo_cost, get_available_batches
from services.accounting_service import save_journal_entry

def create_adjustments_table():
    """إنشاء جدول التسويات إذا لم يكن موجوداً"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            expected_qty REAL NOT NULL,
            actual_qty REAL NOT NULL,
            difference REAL NOT NULL,
            unit_cost REAL,
            total_cost REAL,
            reason TEXT,
            reference TEXT,
            journal_entry_id INTEGER,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    conn.close()

def get_products_for_adjustment():
    """جلب المنتجات مع الكمية الحالية في النظام"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute("""
        SELECT id, name, quantity, selling_price, purchase_price
        FROM products ORDER BY name
    """).fetchall()
    conn.close()
    return [dict(p) for p in products]

def create_adjustment(product_id, expected_qty, actual_qty, unit_cost=None,
                      reason="", reference="", created_by="admin", adjustment_date=None):
    """
    إنشاء تسوية مخزنية (جرد) مع القيد المحاسبي.
    إذا actual > expected => فائض (يضاف للمخزون وFIFO).
    إذا actual < expected => عجز (يخصم من المخزون وFIFO).
    """
    if adjustment_date is None:
        adjustment_date = date.today().strftime("%Y-%m-%d")
    
    create_adjustments_table()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        
        # 1. جلب بيانات المنتج
        product = conn.execute("SELECT id, name, quantity FROM products WHERE id=?", 
                               (product_id,)).fetchone()
        if not product:
            raise Exception("المنتج غير موجود")
        
        system_qty = product["quantity"]
        difference = actual_qty - expected_qty
        
        if difference == 0:
            raise Exception("لا يوجد فرق بين الكمية الفعلية والمتوقعة")
        
        # 2. تحديد التكلفة إذا لم يعطها المستخدم
        if unit_cost is None:
            if difference > 0:
                batches = get_available_batches(product_id, conn)
                if batches:
                    unit_cost = batches[-1]["unit_cost"]
                else:
                    unit_cost = product["selling_price"] if product["selling_price"] else 1.0
            else:
                fifo_cost = get_fifo_cost(product_id, abs(difference), conn)
                if fifo_cost is None:
                    raise Exception("لا توجد دفعات كافية لحساب تكلفة العجز")
                unit_cost = fifo_cost / abs(difference)
        else:
            unit_cost = float(unit_cost)
        
        total_cost = abs(difference) * unit_cost
        
        # 3. تحديث المخزون وFIFO
        if difference > 0:
            # فائض: إضافة للمخزون
            conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?",
                        (difference, product_id))
            conn.execute("""
                INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                VALUES (?, 'in', ?, ?, ?)
            """, (product_id, difference, adjustment_date, f"تسوية جرد (فائض) - مرجع: {reference}"))
            
            add_batch(product_id, difference, unit_cost, adjustment_date,
                     reference=f"تسوية جرد (فائض) - {reference}", conn=conn)
            
            # القيد المحاسبي - استخدام الأكواد الموحدة
            lines = [
                {"account": "114", "debit": total_cost, "credit": 0},  # المخزون
                {"account": "44", "debit": 0, "credit": total_cost}    # إيرادات أخرى (فائض)
            ]
            desc = f"فائض جرد - {product['name']} (+{difference})"
        else:
            # عجز: خصم من المخزون
            qty_to_remove = abs(difference)
            if system_qty < qty_to_remove:
                raise Exception(f"الكمية المتاحة ({system_qty}) أقل من العجز ({qty_to_remove})")
            
            conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?",
                        (qty_to_remove, product_id))
            conn.execute("""
                INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                VALUES (?, 'out', ?, ?, ?)
            """, (product_id, qty_to_remove, adjustment_date, f"تسوية جرد (عجز) - مرجع: {reference}"))
            
            cost, err = consume_fifo(product_id, qty_to_remove, conn=conn,
                                    reference=f"تسوية جرد (عجز) - {reference}")
            if cost is None:
                raise Exception(f"فشل استهلاك FIFO: {err}")
            total_cost = cost
            
            # القيد المحاسبي - استخدام الأكواد الموحدة
            lines = [
                {"account": "546", "debit": total_cost, "credit": 0},  # مصروفات إدارية (عجز)
                {"account": "114", "debit": 0, "credit": total_cost}   # المخزون
            ]
            desc = f"عجز جرد - {product['name']} (-{abs(difference)})"
        
        # 4. إدراج سجل التسوية
        cur = conn.execute("""
            INSERT INTO inventory_adjustments 
            (date, product_id, expected_qty, actual_qty, difference, unit_cost, total_cost, reason, reference, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (adjustment_date, product_id, expected_qty, actual_qty, difference,
              unit_cost, total_cost, reason, reference, created_by))
        adj_id = cur.lastrowid
        
        # 5. إنشاء القيد المحاسبي
        entry_id, error = save_journal_entry(
            description=f"{desc} - تسوية #{adj_id}",
            lines=lines,
            entry_date=adjustment_date,
            conn=conn
        )
        if error:
            raise Exception(f"فشل القيد المحاسبي: {error}")
        
        conn.execute("UPDATE inventory_adjustments SET journal_entry_id=? WHERE id=?", 
                    (entry_id, adj_id))
        
        conn.commit()
        
        log_action(
            username=created_by,
            action="تسوية مخزنية",
            table_name="inventory_adjustments",
            record_id=adj_id,
            new_value=f"{product['name']}: {difference:+.2f} وحدة، التكلفة: {total_cost:,.2f}"
        )
        
        return adj_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_adjustments(limit=50):
    """سجل التسويات المخزنية"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    adjustments = conn.execute("""
        SELECT a.*, p.name as product_name
        FROM inventory_adjustments a
        JOIN products p ON a.product_id = p.id
        ORDER BY a.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(a) for a in adjustments]
