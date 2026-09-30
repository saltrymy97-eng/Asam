# services/fifo_service.py – منطق FIFO للمخزون (v2.0)
# ✅ إصلاح: إزالة التسجيل المزدوج في stock_movements و products
# الآن fifo_service يُدير الدفعات فقط — الخدمات المُستدعية تُسجّل stock_movements
import sqlite3
from datetime import date
from database import get_connection, close_connection


# ============================================================
# مساعد: توحيد منطق الاتصال
# ============================================================
def _resolve_conn(conn):
    """يرجع (conn, owns_conn)"""
    if conn is None:
        return get_connection(), True
    return conn, False


def _release_conn(conn, owns_conn):
    """لا يُغلق — Registry يُدير"""
    if owns_conn:
        close_connection(conn)


# ============================================================
# إنشاء الجداول
# ============================================================
def create_fifo_tables(conn=None):
    """إنشاء جداول FIFO إذا لم تكن موجودة"""
    c, owns = _resolve_conn(conn)
    try:
        c.execute("""
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS fifo_consumptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                consumed_qty REAL NOT NULL,
                consumption_date TEXT NOT NULL,
                reference TEXT,
                FOREIGN KEY (batch_id) REFERENCES inventory_batches(id)
            )
        """)
        if owns:
            c.commit()
    finally:
        _release_conn(c, owns)


# ============================================================
# ✅ add_batch — إضافة دفعة (بدون stock_movements)
# ============================================================
def add_batch(product_id, quantity, unit_cost, batch_date, reference="", conn=None):
    """
    إضافة دفعة شراء.
    ✅ v2.0: يُسجّل الدفعة فقط — لا يُسجّل stock_movements.
    الخدمة المُستدعية مسؤولة عن stock_movements و products.quantity.
    """
    c, owns = _resolve_conn(conn)
    try:
        c.execute(
            "INSERT INTO inventory_batches "
            "(product_id, quantity, unit_cost, batch_date, reference) "
            "VALUES (?, ?, ?, ?, ?)",
            (product_id, quantity, unit_cost, batch_date, reference)
        )
        if owns:
            c.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# الاستعلامات
# ============================================================
def get_available_batches(product_id, conn=None):
    """جلب الدفعات المتاحة لمنتج معين"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        cursor = c.execute("""
            SELECT b.*, 
                   b.quantity - COALESCE(SUM(cc.consumed_qty), 0) as remaining
            FROM inventory_batches b
            LEFT JOIN fifo_consumptions cc ON b.id = cc.batch_id
            WHERE b.product_id = ?
            GROUP BY b.id
            HAVING remaining > 0
            ORDER BY b.batch_date ASC, b.id ASC
        """, (product_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        _release_conn(c, owns)


def get_consumed_batches(product_id, conn=None):
    """جلب الدفعات المستهلكة لمنتج معين"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        cursor = c.execute("""
            SELECT b.*, 
                   COALESCE(SUM(cc.consumed_qty), 0) as total_consumed
            FROM inventory_batches b
            JOIN fifo_consumptions cc ON b.id = cc.batch_id
            WHERE b.product_id = ?
            GROUP BY b.id
            HAVING total_consumed > 0
            ORDER BY b.batch_date DESC, b.id DESC
        """, (product_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        _release_conn(c, owns)


def get_fifo_cost(product_id, quantity, conn=None):
    """حساب تكلفة الكمية المطلوبة حسب FIFO (بدون تعديل)"""
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


# ============================================================
# ✅ consume_fifo — استهلاك الدفعات (بدون stock_movements)
# ============================================================
def consume_fifo(product_id, quantity, consumption_date=None,
                 conn=None, reference=""):
    """
    استهلاك المخزون حسب FIFO.
    ✅ v2.0: يُسجّل الاستهلاك في fifo_consumptions فقط.
    الخدمة المُستدعية مسؤولة عن stock_movements و products.quantity.
    
    Returns:
        (total_cost, 0)   → نجاح
        (None, error)     → فشل
    """
    if consumption_date is None:
        consumption_date = date.today().strftime("%Y-%m-%d")

    c, owns = _resolve_conn(conn)
    try:
        batches = get_available_batches(product_id, c)
        total_cost = 0.0
        remaining_to_consume = quantity

        for batch in batches:
            if remaining_to_consume <= 0:
                break
            qty_available = batch["remaining"]
            qty_to_take = min(qty_available, remaining_to_consume)
            cost = qty_to_take * batch["unit_cost"]
            total_cost += cost

            c.execute(
                "INSERT INTO fifo_consumptions "
                "(batch_id, consumed_qty, consumption_date, reference) "
                "VALUES (?, ?, ?, ?)",
                (batch["id"], qty_to_take, consumption_date, reference)
            )
            remaining_to_consume -= qty_to_take

        if remaining_to_consume > 0:
            return None, f"الكمية غير كافية. متبقي: {remaining_to_consume}"

        if owns:
            c.commit()
        return total_cost, 0

    except Exception as e:
        return None, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# ✅ return_fifo_to_original_batch (بدون stock_movements)
# ============================================================
def return_fifo_to_original_batch(product_id, quantity, sale_invoice_id,
                                   conn=None, reference=""):
    """
    إعادة بضاعة مرتجع المبيعات لنفس دفعة الشراء الأصلية.
    ✅ v2.0: يُعدّل fifo_consumptions فقط.
    الخدمة المُستدعية مسؤولة عن stock_movements و products.quantity.
    """
    c, owns = _resolve_conn(conn)
    try:
        sale_ref = f"فاتورة مبيعات #{sale_invoice_id}"
        consumptions = c.execute("""
            SELECT c.id, c.batch_id, c.consumed_qty, b.unit_cost
            FROM fifo_consumptions c
            JOIN inventory_batches b ON c.batch_id = b.id
            WHERE c.reference = ? AND b.product_id = ?
            ORDER BY c.id ASC
        """, (sale_ref, product_id)).fetchall()

        if not consumptions:
            return None, (
                f"لا توجد سجلات استهلاك FIFO للمنتج "
                f"{product_id} في فاتورة البيع #{sale_invoice_id}"
            )

        total_consumed = sum(row["consumed_qty"] for row in consumptions)

        return_ref = "مرتجع مبيعات"
        already_returned_query = c.execute("""
            SELECT COALESCE(SUM(fc2.consumed_qty), 0)
            FROM fifo_consumptions fc2
            WHERE fc2.reference LIKE ? AND fc2.batch_id IN (
                SELECT cc.batch_id FROM fifo_consumptions cc WHERE cc.reference = ?
            )
        """, (f"%{return_ref}%", sale_ref)).fetchone()

        already_returned = already_returned_query[0] if already_returned_query else 0
        available_to_return = total_consumed - already_returned

        if quantity > available_to_return:
            return None, (
                f"الكمية المطلوبة ({quantity}) أكبر من "
                f"المتاح للإرجاع ({available_to_return})"
            )

        total_cost = 0.0
        remaining = quantity

        for cons in consumptions:
            if remaining <= 0:
                break

            take = min(cons["consumed_qty"], remaining)
            cost = take * cons["unit_cost"]
            total_cost += cost

            if take >= cons["consumed_qty"]:
                c.execute("DELETE FROM fifo_consumptions WHERE id = ?",
                          (cons["id"],))
            else:
                c.execute(
                    "UPDATE fifo_consumptions "
                    "SET consumed_qty = consumed_qty - ? WHERE id = ?",
                    (take, cons["id"])
                )

            remaining -= take

        if owns:
            c.commit()
        return total_cost, 0

    except Exception as e:
        return None, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# return_fifo — إعادة دفعة (Alias لـ add_batch)
# ============================================================
def return_fifo(product_id, quantity, unit_cost, batch_date=None,
                conn=None, reference=""):
    """إعادة بضاعة للمخزون (مشتريات جديدة)"""
    return add_batch(product_id, quantity, unit_cost, batch_date,
                     reference, conn)


# ============================================================
# ✅ remove_last_batch (بدون stock_movements)
# ============================================================
def remove_last_batch(product_id, quantity, consumption_date=None,
                      conn=None, reference=""):
    """
    خصم دفعة من المخزون حسب LIFO (مرتجع مشتريات).
    ✅ v2.0: يُعدّل fifo_consumptions فقط.
    """
    if consumption_date is None:
        consumption_date = date.today().strftime("%Y-%m-%d")

    c, owns = _resolve_conn(conn)
    try:
        batches = get_available_batches(product_id, c)
        if not batches:
            return None, "لا توجد دفعات متاحة للمنتج"

        latest = batches[-1]
        if quantity > latest["remaining"]:
            return None, (
                f"الكمية المطلوبة ({quantity}) أكبر من "
                f"أحدث دفعة ({latest['remaining']})"
            )

        cost = quantity * latest["unit_cost"]

        c.execute(
            "INSERT INTO fifo_consumptions "
            "(batch_id, consumed_qty, consumption_date, reference) "
            "VALUES (?, ?, ?, ?)",
            (latest["id"], quantity, consumption_date, reference)
        )

        if owns:
            c.commit()
        return cost, 0

    except Exception as e:
        return None, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# تكلفة المخزون المتبقي
# ============================================================
def get_product_cost(product_id, conn=None):
    """تكلفة المخزون المتبقي حسب FIFO"""
    batches = get_available_batches(product_id, conn)
    return sum(b["remaining"] * b["unit_cost"] for b in batches)


def get_products_for_select(conn=None):
    """جلب المنتجات للاختيار"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        products = c.execute(
            "SELECT id, name FROM products ORDER BY name"
        ).fetchall()
        return [dict(p) for p in products]
    finally:
        _release_conn(c, owns)
