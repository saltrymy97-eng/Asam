# services/inventory_adjustment_service.py – التسويات المخزنية والجرد (v3.0)
# ✅ Connection Registry + conn=None
# ✅ v3.0: 
#    - إزالة fallback غير النظيف للحسابات (استخدام _get_required_account)
#    - إصلاح unit_cost في العجز — متسق مع FIFO
#    - استخدام purchase_price بدل selling_price في الفائض
#    - تحقق صارم من unit_cost اليدوي
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.fifo_service import (
    consume_fifo, add_batch, get_fifo_cost, get_available_batches
)
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


# ============================================================
# ✅ v3.0: دالة مساعدة — جلب حساب وظيفي إلزامي (بدون fallback)
# ============================================================
def _get_required_account(functional_type, purpose_ar):
    """
    جلب حساب وظيفي إلزامي — بدون fallback.
    
    Args:
        functional_type: النوع الوظيفي (مثل "inventory_gain")
        purpose_ar:      وصف الحساب بالعربية (للرسالة)
    
    Returns:
        (code, None) عند النجاح
        (None, "رسالة الخطأ") عند الفشل
    """
    try:
        code = get_functional_account(functional_type)
        if not code:
            return None, (
                f"⚠️ الحساب المحاسبي '{purpose_ar}' معرّف لكن بقيمة فارغة.\n"
                f"النوع الوظيفي: `{functional_type}`"
            )
        return code, None
    except ValueError as e:
        return None, (
            f"⚠️ الحساب المحاسبي '{purpose_ar}' غير مهيأ في شجرة الحسابات.\n\n"
            f"النوع الوظيفي المطلوب: `{functional_type}`\n\n"
            f"السبب: {str(e)}\n\n"
            f"الحل:\n"
            f"1. افتح شجرة الحسابات\n"
            f"2. أضف حساباً بالنوع الوظيفي `{functional_type}`\n"
            f"3. أعد المحاولة"
        )
    except Exception as e:
        return None, (
            f"⚠️ خطأ غير متوقع أثناء جلب حساب '{purpose_ar}': {str(e)}"
        )


# ============================================================
# إنشاء الجداول
# ============================================================
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


# ============================================================
# ✅ v3.0: إنشاء تسوية مخزنية (جرد) — محدَّث
# ============================================================
def create_adjustment(product_id, expected_qty, actual_qty, unit_cost=None,
                      reason="", reference="", created_by="admin",
                      adjustment_date=None, conn=None):
    """
    إنشاء تسوية مخزنية (جرد) مع القيد المحاسبي.
    
    - إذا actual > expected → فائض (قيد إيرادات فائض الجرد)
    - إذا actual < expected → عجز (قيد خسائر عجز الجرد)
    
    ✅ v3.0:
       - لا fallback للحسابات
       - unit_cost في العجز = total_cost_FIFO / difference
       - استخدام purchase_price بدل selling_price في الفائض
    """
    if adjustment_date is None:
        adjustment_date = date.today().strftime("%Y-%m-%d")

    create_adjustments_table(conn=conn)

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # ============================================================
        # 1. جلب بيانات المنتج
        # ============================================================
        product = conn.execute(
            "SELECT id, name, quantity, purchase_price FROM products WHERE id=?",
            (product_id,)
        ).fetchone()
        if not product:
            if own_conn:
                conn.rollback()
            return None, "المنتج غير موجود"

        product_name = product["name"]
        system_qty = float(product["quantity"] or 0)
        system_purchase_price = float(product["purchase_price"] or 0)

        # تحقق من الكميات
        expected_qty = float(expected_qty)
        actual_qty = float(actual_qty)
        difference = actual_qty - expected_qty

        if abs(difference) < 0.0001:
            if own_conn:
                conn.rollback()
            return None, "لا يوجد فرق بين الكمية الفعلية والمتوقعة"

        # ============================================================
        # 2. جلب الحسابات الوظيفية (بدون fallback)
        # ============================================================
        inventory_acc, err = _get_required_account("inventory", "المخزون")
        if err:
            if own_conn:
                conn.rollback()
            return None, err

        # ============================================================
        # 3. تحديد الحساب المقابل + التكلفة حسب نوع الفرق
        # ============================================================
        if difference > 0:
            # ===== فائض =====
            inventory_gain_acc, err = _get_required_account(
                "inventory_gain", "أرباح/فائض الجرد"
            )
            if err:
                if own_conn:
                    conn.rollback()
                return None, err

            # تحديد unit_cost للفائض
            if unit_cost is None:
                # أولوية 1: آخر دفعة FIFO
                batches = get_available_batches(product_id, conn)
                if batches:
                    unit_cost = float(batches[-1]["unit_cost"])
                else:
                    # أولوية 2: purchase_price من المنتج
                    if system_purchase_price > 0:
                        unit_cost = system_purchase_price
                    else:
                        if own_conn:
                            conn.rollback()
                        return None, (
                            "لا توجد دفعات FIFO ولا سعر شراء معرّف للمنتج. "
                            "لا يمكن تحديد تكلفة الفائض."
                        )
            else:
                try:
                    unit_cost = float(unit_cost)
                except (TypeError, ValueError):
                    if own_conn:
                        conn.rollback()
                    return None, "قيمة unit_cost يجب أن تكون رقماً"

                if unit_cost < 0:
                    if own_conn:
                        conn.rollback()
                    return None, "قيمة unit_cost لا يمكن أن تكون سالبة"

            total_cost = round(abs(difference) * unit_cost, 2)

            # تحديث الكمية + stock_movement
            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (difference, product_id)
            )
            conn.execute("""
                INSERT INTO stock_movements
                (product_id, type, quantity, date, reference)
                VALUES (?, 'in', ?, ?, ?)
            """, (product_id, difference, adjustment_date,
                  f"تسوية جرد (فائض) - مرجع: {reference}"))

            # إضافة دفعة FIFO
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
            desc = f"فائض جرد - {product_name} (+{difference})"

        else:
            # ===== عجز =====
            inventory_loss_acc, err = _get_required_account(
                "inventory_loss", "خسائر/عجز الجرد"
            )
            if err:
                if own_conn:
                    conn.rollback()
                return None, err

            qty_to_remove = abs(difference)

            # ✅ فحص الكمية المتاحة
            if system_qty < qty_to_remove - 0.0001:
                if own_conn:
                    conn.rollback()
                return None, (
                    f"الكمية المتاحة في النظام ({system_qty:,.2f}) "
                    f"أقل من العجز ({qty_to_remove:,.2f})"
                )

            # ✅ فحص FIFO كافٍ — قبل أي تعديل
            fifo_cost_check = get_fifo_cost(product_id, qty_to_remove, conn)
            if fifo_cost_check is None:
                if own_conn:
                    conn.rollback()
                return None, (
                    "لا توجد دفعات FIFO كافية لحساب تكلفة العجز. "
                    "تأكد من وجود دفعات شراء كافية في المخزون."
                )

            # ✅ الآن: تحديث الكمية + stock_movement
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (qty_to_remove, product_id)
            )
            conn.execute("""
                INSERT INTO stock_movements
                (product_id, type, quantity, date, reference)
                VALUES (?, 'out', ?, ?, ?)
            """, (product_id, qty_to_remove, adjustment_date,
                  f"تسوية جرد (عجز) - مرجع: {reference}"))

            # ✅ استهلاك FIFO الفعلي
            cost, fifo_err = consume_fifo(
                product_id, qty_to_remove, conn=conn,
                reference=f"تسوية جرد (عجز) - {reference}"
            )
            if cost is None:
                if own_conn:
                    conn.rollback()
                return None, f"فشل استهلاك FIFO: {fifo_err}"

            total_cost = round(cost, 2)

            # ✅ v3.0: إعادة حساب unit_cost — متسق مع FIFO الفعلي
            # (يتم تجاهل unit_cost اليدوي في العجز — لأن FIFO هو المرجع)
            unit_cost = round(total_cost / qty_to_remove, 4) if qty_to_remove > 0 else 0

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
            desc = f"عجز جرد - {product_name} (-{qty_to_remove})"

        # ============================================================
        # 4. إدراج سجل التسوية
        # ============================================================
        cur = conn.execute("""
            INSERT INTO inventory_adjustments 
                (date, product_id, expected_qty, actual_qty, difference,
                 unit_cost, total_cost, reason, reference, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (adjustment_date, product_id, expected_qty, actual_qty, difference,
              unit_cost, total_cost, reason, reference, created_by))
        adj_id = cur.lastrowid

        # ============================================================
        # 5. إنشاء القيد المحاسبي
        # ============================================================
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
            new_value=(
                f"{product_name}: {difference:+.2f} وحدة، "
                f"التكلفة: {total_cost:,.2f}، القيد: #{entry_id}"
            )
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
