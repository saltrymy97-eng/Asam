# services/inventory_adjustment_service.py – التسويات المخزنية والجرد (v2.0)
# ✅ Connection Registry + conn=None
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.fifo_service import (
    consume_fifo, add_batch, get_fifo_cost, get_available_batches
)
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


def create_adjustments_table(conn=None):
    """إنشاء جدول التسويات إذا لم يكن موجوداً"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


def get_products_for_adjustment(conn=None):
    """جلب المنتجات مع الكمية الحالية في النظام"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        products = conn.execute("""
            SELECT id, name, quantity, selling_price, purchase_price
            FROM products ORDER BY name
        """).fetchall()
        return [dict(p) for p in products]
    finally:
        if own_conn:
            close_connection(conn)


def create_adjustment(product_id, expected_qty, actual_qty, unit_cost=None,
                      reason="", reference="", created_by="admin",
                      adjustment_date=None, conn=None):
    """
    إنشاء تسوية مخزنية (جرد) مع القيد المحاسبي.
    
    - إذا actual > expected → فائض (قيد إيرادات فائض الجرد)
    - إذا actual < expected → عجز (قيد خسائر عجز الجرد)
    
    ⚠️ ملاحظة: لا يمس الصندوق/البنك — لا يحتاج فحص رصيد.
    """
    if adjustment_date is None:
        adjustment_date = date.today().strftime("%Y-%m-%d")

    create_adjustments_table(conn=conn)

    # الحسابات الوظيفية
    inventory_acc = get_functional_account("inventory")
    inventory_gain_acc = (
        get_functional_account("inventory_gain")
        or get_functional_account("other_income")
        or get_functional_account("cogs")
    )
    inventory_loss_acc = (
        get_functional_account("inventory_loss")
        or get_functional_account("cogs")
        or get_functional_account("other_expense")
    )

    if not inventory_acc:
        return None, "حساب المخزون الوظيفي (inventory) غير معرف في شجرة الحسابات"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # 1. جلب بيانات المنتج
        product = conn.execute(
            "SELECT id, name, quantity, selling_price FROM products WHERE id=?",
            (product_id,)
        ).fetchone()
        if not product:
            raise Exception("المنتج غير موجود")

        system_qty = product["quantity"]
        difference = actual_qty - expected_qty

        if difference == 0:
            raise Exception("لا يوجد فرق بين الكمية الفعلية والمتوقعة")

        # 2. تحديد التكلفة
        if unit_cost is None:
            if difference > 0:
                batches = get_available_batches(product_id, conn)
                if batches:
                    unit_cost = batches[-1]["unit_cost"]
                else:
                    unit_cost = (
                        product["selling_price"]
                        if product["selling_price"] else 1.0
                    )
            else:
                fifo_cost = get_fifo_cost(product_id, abs(difference), conn)
                if fifo_cost is None:
                    raise Exception("لا توجد دفعات كافية لحساب تكلفة العجز")
                unit_cost = fifo_cost / abs(difference)
        else:
            unit_cost = float(unit_cost)

        total_cost = round(abs(difference) * unit_cost, 2)

        # 3. تحديث المخزون و FIFO وإعداد سطور القيد
        if difference > 0:
            if not inventory_gain_acc:
                raise Exception("حساب أرباح/فائض الجرد (inventory_gain) غير معرف")

            # فائض
            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (difference, product_id)
            )
            conn.execute("""
                INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                VALUES (?, 'in', ?, ?, ?)
            """, (product_id, difference, adjustment_date,
                  f"تسوية جرد (فائض) - مرجع: {reference}"))

            add_batch(
                product_id, difference, unit_cost, adjustment_date,
                reference=f"تسوية جرد (فائض) - {reference}", conn=conn
            )

            lines = [
                {
                    "account": inventory_acc,
                    "debit": total_cost,
                    "credit": 0.0,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                },
                {
                    "account": inventory_gain_acc,
                    "debit": 0.0,
                    "credit": total_cost,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                },
            ]
            desc = f"فائض جرد - {product['name']} (+{difference})"
        else:
            if not inventory_loss_acc:
                raise Exception("حساب خسائر/عجز الجرد (inventory_loss) غير معرف")

            # عجز
            qty_to_remove = abs(difference)
            if system_qty < qty_to_remove:
                raise Exception(
                    f"الكمية المتاحة ({system_qty}) أقل من العجز ({qty_to_remove})"
                )

            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (qty_to_remove, product_id)
            )
            conn.execute("""
                INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                VALUES (?, 'out', ?, ?, ?)
            """, (product_id, qty_to_remove, adjustment_date,
                  f"تسوية جرد (عجز) - مرجع: {reference}"))

            cost, err = consume_fifo(
                product_id, qty_to_remove, conn=conn,
                reference=f"تسوية جرد (عجز) - {reference}"
            )
            if cost is None:
                raise Exception(f"فشل استهلاك FIFO: {err}")
            total_cost = round(cost, 2)

            lines = [
                {
                    "account": inventory_loss_acc,
                    "debit": total_cost,
                    "credit": 0.0,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                },
                {
                    "account": inventory_acc,
                    "debit": 0.0,
                    "credit": total_cost,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                },
            ]
            desc = f"عجز جرد - {product['name']} (-{abs(difference)})"

        # 4. إدراج سجل التسوية
        cur = conn.execute("""
            INSERT INTO inventory_adjustments 
                (date, product_id, expected_qty, actual_qty, difference,
                 unit_cost, total_cost, reason, reference, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (adjustment_date, product_id, expected_qty, actual_qty, difference,
              unit_cost, total_cost, reason, reference, created_by))
        adj_id = cur.lastrowid

        # 5. إنشاء القيد
        entry_id, error = save_journal_entry(
            description=f"{desc} - تسوية #{adj_id}",
            lines=lines,
            entry_date=adjustment_date,
            conn=conn,
        )
        if error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {error}")

        conn.execute(
            "UPDATE inventory_adjustments SET journal_entry_id=? WHERE id=?",
            (entry_id, adj_id)
        )

        if own_conn:
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
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def get_adjustments(limit=50, conn=None):
    """سجل التسويات المخزنية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        adjustments = conn.execute("""
            SELECT a.*, p.name as product_name
            FROM inventory_adjustments a
            JOIN products p ON a.product_id = p.id
            ORDER BY a.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(a) for a in adjustments]
    finally:
        if own_conn:
            close_connection(conn)
