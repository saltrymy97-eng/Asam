# services/inventory_service.py – منطق إدارة المخزون (v3.0)
# ✅ conn=None + Registry + BEGIN IMMEDIATE (منع Race Condition)
# ✅ حماية صارمة من الصرف الزائد + تسجيل username
# ✅ إصلاح: _normalize_move_type يقبل "داخل (إضافة)" و"خارج (صرف)"
# ✅ v3.0: إضافة record_manual_stock_movement — حركة مخزون يدوية متكاملة محاسبياً
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action


# ============================================================
# ✅ v3.0: تعريف الأسباب المعتمدة
# ============================================================
# كل سبب → (debit_functional, credit_functional)
# - "inventory" → functional_type
# - الـ debit/credit يُستخدمان في القيد

MANUAL_ADD_REASONS = {
    "رصيد افتتاحي": {
        "debit": "inventory",
        "credit": "capital",
        "description": "إدخال رصيد بداية المدة",
    },
    "تسوية جرد - زيادة": {
        "debit": "inventory",
        "credit": "inventory_gain",
        "description": "زيادة ناتجة عن جرد فعلي",
    },
}

MANUAL_REMOVE_REASONS = {
    "تسوية جرد - نقص": {
        "debit": "inventory_loss",
        "credit": "inventory",
        "description": "نقص ناتج عن جرد فعلي",
    },
    "تلف": {
        "debit": "inventory_loss",
        "credit": "inventory",
        "description": "خسارة فعلية بسبب التلف",
    },
    "استخدام داخلي": {
        "debit": "operating_expense",
        "credit": "inventory",
        "description": "صرف للاستخدام الداخلي",
    },
}


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


def _normalize_move_type(move_type) -> str:
    """
    توحيد نوع الحركة إلى 'in' أو 'out'.
    ✅ يقبل كل الصيغ:
       - "داخل" / "داخل (إضافة)" / "إضافة" / "in" / "add" / "+"
       - "خارج" / "خارج (صرف)" / "صرف" / "out" / "remove" / "-"
    """
    if move_type is None:
        raise ValueError("نوع الحركة مطلوب")

    mt = str(move_type).strip().lower()

    if any(k in mt for k in ("داخل", "إضاف", "إدخال", "ادخال", "in", "add", "+")):
        return "in"
    if any(k in mt for k in ("خارج", "صرف", "إخراج", "اخراج", "out", "remove", "-")):
        return "out"

    raise ValueError(f"نوع حركة غير معروف: {move_type}")


# ============================================================
# ✅ v3.0: دالة مساعدة — تحديد الحسابات حسب السبب
# ============================================================
def _resolve_manual_accounts(reason, movement_type, conn):
    """
    إرجاع (debit_code, credit_code, error_message).
    
    Args:
        reason:        اسم السبب (نص عربي)
        movement_type: 'in' أو 'out'
        conn:          اتصال قاعدة البيانات
    
    Returns:
        (debit_code, credit_code, None) عند النجاح
        (None, None, "رسالة الخطأ")   عند الفشل
    """
    from services.chart_service import get_functional_account

    # 1. اختيار القاموس المناسب
    if movement_type == "in":
        reasons_map = MANUAL_ADD_REASONS
    else:
        reasons_map = MANUAL_REMOVE_REASONS

    # 2. فحص وجود السبب
    if reason not in reasons_map:
        return None, None, f"سبب غير معتمد: {reason}"

    rule = reasons_map[reason]

    # 3. تحديد الحسابات
    try:
        debit_code = get_functional_account(rule["debit"], conn=conn)
    except ValueError as e:
        return None, None, (
            f"⚠️ الحساب المحاسبي المدين غير مهيأ للسبب '{reason}'.\n\n"
            f"النوع الوظيفي المطلوب: `{rule['debit']}`\n\n"
            f"السبب: {str(e)}\n\n"
            f"الحل:\n"
            f"1. افتح شجرة الحسابات\n"
            f"2. أضف حساباً بالنوع الوظيفي `{rule['debit']}`\n"
            f"3. أعد المحاولة"
        )

    try:
        credit_code = get_functional_account(rule["credit"], conn=conn)
    except ValueError as e:
        return None, None, (
            f"⚠️ الحساب المحاسبي الدائن غير مهيأ للسبب '{reason}'.\n\n"
            f"النوع الوظيفي المطلوب: `{rule['credit']}`\n\n"
            f"السبب: {str(e)}\n\n"
            f"الحل:\n"
            f"1. افتح شجرة الحسابات\n"
            f"2. أضف حساباً بالنوع الوظيفي `{rule['credit']}`\n"
            f"3. أعد المحاولة"
        )

    return debit_code, credit_code, None


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
# حركات المخزون — الحماية الأساسية من الصرف الزائد
# ============================================================
def record_stock_movement(product_id, product_name, move_type, quantity,
                          reference, username="admin", conn=None):
    """
    تسجيل حركة مخزون مع حماية صارمة من الصرف الزائد.
    ✅ BEGIN IMMEDIATE — يمنع Race Condition
    ✅ فحص الكمية داخل Transaction
    ✅ رفض الكميات السالبة أو الصفرية
    ✅ يقبل "داخل (إضافة)" و"خارج (صرف)"
    """
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
        if owns:
            c.execute("BEGIN IMMEDIATE")

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

        if type_en == "out":
            if available < quantity - 0.0001:
                if owns:
                    c.rollback()
                return False, (
                    f"❌ لا يمكن صرف {quantity:,.2f} وحدة من «{product_real_name}». "
                    f"الرصيد المتاح: {available:,.2f} فقط"
                )

        c.execute(
            """INSERT INTO stock_movements
               (product_id, type, quantity, date, reference)
               VALUES (?, ?, ?, date('now'), ?)""",
            (product_id, type_en, quantity, reference or "")
        )

        c.execute(
            "UPDATE products SET quantity = quantity + ? WHERE id = ?",
            (sign * quantity, product_id)
        )

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
# ✅ v3.0: حركة المخزون اليدوية — متكاملة محاسبياً
# ============================================================
def record_manual_stock_movement(
    product_id,
    movement_type,
    quantity,
    reason,
    unit_cost=None,
    reference="",
    notes="",
    created_by="admin",
    conn=None,
):
    """
    حركة مخزون يدوية متكاملة محاسبياً.
    
    يجمع في Transaction واحدة:
      1. فحوصات (منتج، كمية، نوع، سبب)
      2. تحديد الحسابات (حسب السبب)
      3. حساب التكلفة:
         - إضافة: unit_cost (مطلوب)
         - صرف: consume_fifo → total_cost
      4. تسجيل دفعة/استهلاك FIFO
      5. stock_movement + products.quantity (عبر record_stock_movement)
      6. journal_entry (عبر save_journal_entry)
      7. audit_log
    
    Args:
        product_id:     معرف المنتج
        movement_type:  'in' أو 'out' (أو "داخل"/"خارج")
        quantity:       الكمية
        reason:         السبب (من MANUAL_ADD_REASONS أو MANUAL_REMOVE_REASONS)
        unit_cost:      سعر الوحدة (مطلوب للإضافة فقط)
        reference:      المرجع (اختياري — يُولَّد تلقائياً)
        notes:          ملاحظات (اختياري)
        created_by:     اسم المستخدم
        conn:           اتصال خارجي (اختياري)
    
    Returns:
        (True, {
            "journal_id": ...,
            "stock_movement_id": ...,
            "total_cost": ...,
            "reference": ...,
            "product_name": ...,
            "quantity": ...,
            "movement_type": ...,
            "reason": ...,
        }) على النجاح
        
        (False, {"error": "رسالة الخطأ"}) على الفشل
    """
    # ============================================================
    # 1. التحقق من نوع الحركة
    # ============================================================
    try:
        type_en = _normalize_move_type(movement_type)
    except ValueError as e:
        return False, {"error": str(e)}

    # ============================================================
    # 2. التحقق من الكمية
    # ============================================================
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return False, {"error": "الكمية يجب أن تكون رقماً"}

    if quantity <= 0:
        return False, {"error": "الكمية يجب أن تكون أكبر من صفر"}

    # ============================================================
    # 3. التحقق من السبب
    # ============================================================
    if type_en == "in":
        valid_reasons = MANUAL_ADD_REASONS
    else:
        valid_reasons = MANUAL_REMOVE_REASONS

    if reason not in valid_reasons:
        return False, {
            "error": (
                f"السبب '{reason}' غير مناسب لنوع الحركة "
                f"({'داخل' if type_en == 'in' else 'خارج'})."
            )
        }

    # ============================================================
    # 4. التحقق من unit_cost (للإضافة فقط)
    # ============================================================
    if type_en == "in":
        if unit_cost is None:
            return False, {"error": "سعر التكلفة مطلوب عند الإضافة"}

        try:
            unit_cost = float(unit_cost)
        except (TypeError, ValueError):
            return False, {"error": "سعر التكلفة يجب أن يكون رقماً"}

        if unit_cost <= 0:
            return False, {"error": "سعر التكلفة يجب أن يكون أكبر من صفر"}

    # ============================================================
    # 5. بدء Transaction
    # ============================================================
    c, owns = _resolve_conn(conn)
    try:
        if owns:
            c.execute("BEGIN IMMEDIATE")

        # ------------------------------------------------------------
        # 5.1 التحقق من المنتج
        # ------------------------------------------------------------
        c.row_factory = sqlite3.Row
        product = c.execute(
            "SELECT id, name, quantity FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if not product:
            if owns:
                c.rollback()
            return False, {"error": f"المنتج #{product_id} غير موجود"}

        product_name = product["name"]
        current_qty = float(product["quantity"] or 0)

        # ------------------------------------------------------------
        # 5.2 التحقق من الكمية (للصرف)
        # ------------------------------------------------------------
        if type_en == "out":
            if current_qty < quantity - 0.0001:
                if owns:
                    c.rollback()
                return False, {
                    "error": (
                        f"❌ لا يمكن صرف {quantity:,.2f} وحدة من «{product_name}». "
                        f"الرصيد المتاح: {current_qty:,.2f} فقط"
                    )
                }

        # ------------------------------------------------------------
        # 5.3 تحديد الحسابات
        # ------------------------------------------------------------
        debit_code, credit_code, acc_err = _resolve_manual_accounts(
            reason, type_en, c
        )
        if acc_err:
            if owns:
                c.rollback()
            return False, {"error": acc_err}

        # ------------------------------------------------------------
        # 5.4 تحديد التكلفة (FIFO / unit_cost)
        # ------------------------------------------------------------
        movement_date = date.today().strftime("%Y-%m-%d")

        # توليد المرجع إذا لم يُمرَّر
        if not reference or not str(reference).strip():
            reference = f"MAN-{movement_date.replace('-', '')}-{product_id}-{int(quantity)}"

        from services.fifo_service import add_batch, consume_fifo

        if type_en == "in":
            # ===== الإضافة =====
            total_cost = round(quantity * unit_cost, 2)

            # إضافة دفعة FIFO
            ok_batch, batch_err = add_batch(
                product_id=product_id,
                quantity=quantity,
                unit_cost=unit_cost,
                batch_date=movement_date,
                reference=reference,
                conn=c,
            )
            if not ok_batch:
                if owns:
                    c.rollback()
                return False, {
                    "error": f"فشل إضافة دفعة FIFO: {batch_err}"
                }

        else:
            # ===== الصرف =====
            total_cost, fifo_err = consume_fifo(
                product_id=product_id,
                quantity=quantity,
                consumption_date=movement_date,
                conn=c,
                reference=reference,
            )

            if total_cost is None:
                if owns:
                    c.rollback()
                return False, {
                    "error": (
                        f"⚠️ تعذر تحديد تكلفة المخزون المصروف وفق نظام FIFO.\n\n"
                        f"التفاصيل: {fifo_err}\n\n"
                        f"الحل المقترح:\n"
                        f"- تأكد من وجود دفعات شراء كافية في المخزون.\n"
                        f"- إذا كانت هناك حاجة، أضف رصيداً افتتاحياً أولاً."
                    )
                }

            total_cost = round(total_cost, 2)

        if total_cost <= 0:
            if owns:
                c.rollback()
            return False, {
                "error": f"قيمة الحركة المحسوبة غير صحيحة: {total_cost}"
            }

        # ------------------------------------------------------------
        # 5.5 تسجيل الحركة + تحديث الكمية
        # ------------------------------------------------------------
        ok_movement, move_err = record_stock_movement(
            product_id=product_id,
            product_name=product_name,
            move_type=type_en,
            quantity=quantity,
            reference=reference,
            username=created_by,
            conn=c,
        )
        if not ok_movement:
            if owns:
                c.rollback()
            return False, {"error": f"فشل تسجيل الحركة: {move_err}"}

        # الحصول على آخر stock_movement_id
        sm_row = c.execute(
            "SELECT last_insert_rowid() as id"
        ).fetchone()
        stock_movement_id = sm_row["id"] if sm_row else None

        # ------------------------------------------------------------
        # 5.6 إنشاء القيد المحاسبي
        # ------------------------------------------------------------
        from services.accounting_service import save_journal_entry

        description = (
            f"حركة مخزون يدوية — {reason} — {product_name} "
            f"({quantity:,.2f} وحدة)"
        )
        if notes:
            description += f" — {notes}"

        journal_lines = [
            {
                "account": debit_code,
                "debit": total_cost,
                "credit": 0.0,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
            {
                "account": credit_code,
                "debit": 0.0,
                "credit": total_cost,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
        ]

        journal_result = save_journal_entry(
            description=description,
            lines=journal_lines,
            entry_date=movement_date,
            conn=c,
        )

        # save_journal_entry يُعيد tuple دائماً
        if isinstance(journal_result, tuple):
            journal_id, jerr = journal_result
            if jerr:
                if owns:
                    c.rollback()
                return False, {
                    "error": f"فشل إنشاء القيد المحاسبي: {jerr}"
                }
        else:
            journal_id = journal_result

        # ------------------------------------------------------------
        # 5.7 تسجيل audit log
        # ------------------------------------------------------------
        log_action(
            username=created_by,
            action=f"حركة مخزون يدوية ({'إضافة' if type_en == 'in' else 'صرف'})",
            table_name="stock_movements",
            record_id=stock_movement_id,
            new_value={
                "product": product_name,
                "quantity": quantity,
                "reason": reason,
                "total_cost": total_cost,
                "journal_id": journal_id,
                "reference": reference,
            },
        )

        # ------------------------------------------------------------
        # 5.8 Commit
        # ------------------------------------------------------------
        if owns:
            c.commit()

        return True, {
            "journal_id": journal_id,
            "stock_movement_id": stock_movement_id,
            "total_cost": total_cost,
            "reference": reference,
            "product_name": product_name,
            "quantity": quantity,
            "movement_type": type_en,
            "reason": reason,
        }

    except Exception as e:
        if owns:
            try:
                c.rollback()
            except Exception:
                pass
        return False, {"error": f"خطأ غير متوقع: {str(e)}"}
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
