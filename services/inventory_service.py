# services/inventory_service.py – منطق إدارة المخزون (v2.0)
# ✅ conn=None + Registry + BEGIN IMMEDIATE (منع Race Condition)
# ✅ حماية صارمة من الصرف الزائد + تسجيل username
import sqlite3
from database import get_connection, close_connection
from services.audit_service import log_action


# ============================================================
# مساعد: توحيد منطق الاتصال
# ============================================================
def _resolve_conn(conn):
    """يرجع (conn, owns_conn) — يفتح اتصالاً إذا لم يُمرَّر"""
    if conn is None:
        return get_connection(), True
    return conn, False


def _release_conn(conn, owns_conn):
    """يغلق الاتصال فقط إذا كنا نملكه"""
    if owns_conn:
        close_connection(conn)


def _normalize_move_type(move_type: str) -> str:
    """توحيد نوع الحركة إلى 'in' أو 'out'"""
    if move_type is None:
        raise ValueError("نوع الحركة مطلوب")
    mt = str(move_type).strip().lower()
    if mt in ("داخل", "in", "إدخال", "ادخال", "add", "+"):
        return "in"
    if mt in ("خارج", "out", "صرف", "إخراج", "اخراج", "remove", "-"):
        return "out"
    raise ValueError(f"نوع حركة غير معروف: {move_type}")


# ============================================================
# المنتجات
# ============================================================
def get_all_products(conn=None):
    """جلب جميع المنتجات"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        _release_conn(c, owns)


def add_product(name, barcode, category, purchase_price, selling_price,
                quantity, reorder_level, username="admin", conn=None):
    """
    إضافة منتج جديد.
    ✅ يقبل conn خارجي (للاستخدام داخل Transaction أكبر).
    ✅ validation صارم.
    """
    # --- validation ---
    if not name or not str(name).strip():
        return False, "اسم المنتج مطلوب"
    try:
        purchase_price = float(purchase_price or 0)
        selling_price = float(selling_price or 0)
        quantity = float(quantity or 0)
        reorder_level = float(reorder_level or 0)
    except (TypeError, ValueError):
        return False, "قيم الأسعار/الكميات يجب أن تكون أرقاماً"

    if purchase_price < 0 or selling_price < 0:
        return False, "الأسعار لا يمكن أن تكون سالبة"
    if quantity < 0:
        return False, "الكمية الافتتاحية لا يمكن أن تكون سالبة"
    if reorder_level < 0:
        return False, "حد الطلب لا يمكن أن يكون سالباً"

    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")

        cur = c.execute(
            """INSERT INTO products
               (name, barcode, category, purchase_price, selling_price,
                quantity, reorder_level)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(name).strip(),
             barcode if barcode else None,
             category,
             purchase_price,
             selling_price,
             quantity,
             reorder_level)
        )
        product_id = cur.lastrowid

        # ✅ تسجيل حركة افتتاحية إذا كانت الكمية > 0
        if quantity > 0:
            c.execute(
                """INSERT INTO stock_movements
                   (product_id, type, quantity, date, reference)
                   VALUES (?, 'in', ?, date('now'), ?)""",
                (product_id, quantity, "رصيد افتتاحي")
            )

        if owns:
            c.commit()

        log_action(
            username=username,
            action="إضافة منتج",
            table_name="products",
            record_id=product_id,
            new_value=f"المنتج: {name}, السعر: {selling_price}, الكمية: {quantity}"
        )
        return True, None

    except Exception as e:
        if owns:
            try:
                c.rollback()
            except Exception:
                pass
        return False, str(e)
    finally:
        _release_conn(c, owns)


def update_product_quantity(product_id, new_quantity, username="admin", conn=None):
    """
    تعديل مباشر لكمية منتج (تسوية إدارية).
    ⚠️ لا تُستخدم للبيع/الشراء — فقط للتسويات.
    """
    try:
        new_quantity = float(new_quantity or 0)
    except (TypeError, ValueError):
        return False, "الكمية يجب أن تكون رقماً"
    if new_quantity < 0:
        return False, "الكمية لا يمكن أن تكون سالبة"

    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")

        prod = c.execute(
            "SELECT name, quantity FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()
        if not prod:
            if owns:
                c.rollback()
            return False, "المنتج غير موجود"

        old_qty = float(prod["quantity"] or 0)
        diff = new_quantity - old_qty

        c.execute(
            "UPDATE products SET quantity = ? WHERE id = ?",
            (new_quantity, product_id)
        )

        if abs(diff) > 0.0001:
            move_type = "in" if diff > 0 else "out"
            c.execute(
                """INSERT INTO stock_movements
                   (product_id, type, quantity, date, reference)
                   VALUES (?, ?, ?, date('now'), ?)""",
                (product_id, move_type, abs(diff),
                 f"تسوية إدارية من {old_qty} إلى {new_quantity}")
            )

        if owns:
            c.commit()

        log_action(
            username=username,
            action="تسوية كمية",
            table_name="products",
            record_id=product_id,
            new_value=f"{prod['name']}: {old_qty} → {new_quantity}"
        )
        return True, None

    except Exception as e:
        if owns:
            try:
                c.rollback()
            except Exception:
                pass
        return False, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# حركات المخزون — ✅ الحماية الأساسية من الصرف الزائد
# ============================================================
def record_stock_movement(product_id, product_name, move_type, quantity,
                          reference, username="admin", conn=None):
    """
    تسجيل حركة مخزون مع حماية صارمة من الصرف الزائد.
    ✅ BEGIN IMMEDIATE — يمنع Race Condition
    ✅ فحص الكمية داخل Transaction
    ✅ رفض الكميات السالبة أو الصفرية
    """
    # --- validation أولي ---
    try:
        type_en = _normalize_move_type(move_type)
    except ValueError as e:
        return False, str(e)

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return False, "الكمية يجب أن تكون رقماً"

    if quantity <= 0:
        return False, "الكمية يجب أن تكون أكبر من صفر"

    sign = 1 if type_en == "in" else -1

    c, owns = _resolve_conn(conn)
    try:
        # ✅ BEGIN IMMEDIATE قبل أي قراءة — يمنع Race Condition
        if owns:
            c.execute("BEGIN IMMEDIATE")

        # ✅ قراءة الكمية داخل Transaction
        row = c.execute(
            "SELECT name, quantity FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if not row:
            if owns:
                c.rollback()
            return False, f"المنتج #{product_id} غير موجود"

        available = float(row["quantity"] or 0)
        product_real_name = row["name"] or product_name

        # ✅ فحص الصرف الزائد
        if type_en == "out":
            if available < quantity - 0.0001:
                if owns:
                    c.rollback()
                return False, (
                    f"❌ لا يمكن صرف {quantity:,.2f} وحدة من «{product_real_name}». "
                    f"الرصيد المتاح: {available:,.2f} فقط"
                )

        # تسجيل الحركة
        c.execute(
            """INSERT INTO stock_movements
               (product_id, type, quantity, date, reference)
               VALUES (?, ?, ?, date('now'), ?)""",
            (product_id, type_en, quantity, reference or "")
        )

        # تحديث الكمية
        c.execute(
            "UPDATE products SET quantity = quantity + ? WHERE id = ?",
            (sign * quantity, product_id)
        )

        # ✅ فحص نهائي: الكمية لا يجب أن تكون سالبة
        new_qty_row = c.execute(
            "SELECT quantity FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()
        new_qty = float(new_qty_row["quantity"] or 0)

        if new_qty < -0.0001:
            if owns:
                c.rollback()
            return False, (
                f"❌ العملية ستؤدي إلى رصيد سالب ({new_qty:,.2f}) — تم الإلغاء"
            )

        if owns:
            c.commit()

        log_action(
            username=username,
            action="حركة مخزون",
            table_name="stock_movements",
            new_value=(
                f"{'داخل' if type_en == 'in' else 'خارج'} — "
                f"{product_real_name}, الكمية: {quantity:,.2f}, "
                f"المرجع: {reference or '—'}"
            )
        )
        return True, None

    except Exception as e:
        if owns:
            try:
                c.rollback()
            except Exception:
                pass
        return False, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# السجلات والتقارير
# ============================================================
def get_stock_movements(limit=50, conn=None):
    """سجل حركات المخزون"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        rows = c.execute("""
            SELECT sm.id, p.name as product, sm.type,
                   sm.quantity, sm.date, sm.reference
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            ORDER BY sm.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        _release_conn(c, owns)


def get_low_stock_products(conn=None):
    """المنتجات تحت الحد الأدنى"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            """SELECT id, name, quantity, reorder_level
               FROM products
               WHERE quantity < reorder_level
               ORDER BY (reorder_level - quantity) DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        _release_conn(c, owns)


def get_products_for_select(conn=None):
    """جلب المنتجات للاختيار (id, name)"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT id, name FROM products ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        _release_conn(c, owns)


def get_product_by_id(product_id, conn=None):
    """جلب منتج واحد بالمعرّف"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        row = c.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        _release_conn(c, owns)


def get_product_quantity(product_id, conn=None):
    """جلب كمية منتج فقط (خفيف وسريع)"""
    c, owns = _resolve_conn(conn)
    try:
        row = c.execute(
            "SELECT quantity FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()
        if not row:
            return None
        return float(row["quantity"] or 0)
    finally:
        _release_conn(c, owns)
