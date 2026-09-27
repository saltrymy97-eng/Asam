# services/returns_service.py – منطق أعمال المرتجعات (v3.0)
# ✅ Connection Registry + 3 طرق استرداد (account/cash/bank) + حماية الرصيد
import sqlite3
from collections import defaultdict
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.chart_service import get_functional_account
from services.fifo_service import (
    return_fifo_to_original_batch,
    remove_last_batch,
    get_fifo_cost,
)


def _add_invoice_columns(conn=None):
    """إضافة أعمدة reason و reference (آمن)"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        for col, definition in [("reason", "TEXT"), ("reference", "INTEGER")]:
            try:
                conn.execute(f"ALTER TABLE invoices ADD COLUMN {col} {definition}")
            except Exception:
                pass
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# استعلامات الفواتير
# ============================================================
def get_sales_invoices(conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute("""
            SELECT i.id, i.invoice_date, c.name as customer, i.total, i.vat_rate,
                   i.vat_amount, i.currency_code, i.exchange_rate, i.customer_id
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            WHERE i.type = 'sale' AND i.status = 'completed'
            ORDER BY i.id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def get_purchase_invoices(conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute("""
            SELECT i.id, i.invoice_date, s.name as supplier, i.total, i.vat_rate,
                   i.vat_amount, i.currency_code, i.exchange_rate, i.supplier_id
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.id
            WHERE i.type = 'purchase' AND i.status = 'completed'
            ORDER BY i.id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def get_invoice_items(invoice_id, conn=None):
    """جلب بنود فاتورة مع الكميات المباعة والمرجعة والمتبقية"""
    _add_invoice_columns(conn)

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        items = conn.execute("""
            SELECT ii.id, ii.quantity, ii.unit_price, p.name, ii.product_id
            FROM invoice_items ii
            JOIN products p ON ii.product_id = p.id
            WHERE ii.invoice_id = ?
        """, (invoice_id,)).fetchall()

        result = []
        for item in items:
            returned_qty = conn.execute("""
                SELECT COALESCE(SUM(ri.quantity), 0)
                FROM invoice_items ri
                JOIN invoices r ON ri.invoice_id = r.id
                WHERE r.type IN ('sale_return', 'purchase_return')
                  AND r.reference = ?
                  AND ri.product_id = ?
            """, (invoice_id, item["product_id"])).fetchone()[0]

            sold_qty = int(item["quantity"])
            returned = int(returned_qty or 0)
            available = max(0, sold_qty - returned)

            result.append({
                "id": item["id"],
                "quantity": sold_qty,
                "returned_qty": returned,
                "available_qty": available,
                "unit_price": item["unit_price"],
                "name": item["name"],
                "product_id": item["product_id"],
            })
        return result
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# ✅ العملية الرئيسية — process_return
# ============================================================
def process_return(invoice_type, invoice_id, items_to_return, return_date,
                   reason="", refund_method="account",
                   cash_account_code=None, bank_account_code=None):
    """
    تنفيذ عملية المرتجع كاملة.
    
    Args:
        invoice_type:        'sale' | 'purchase'
        invoice_id:          معرف الفاتورة الأصلية
        items_to_return:     قائمة [(اسم_المنتج, الكمية), ...]
        return_date:         تاريخ المرتجع
        reason:              سبب المرتجع
        refund_method:       'account' | 'cash' | 'bank'
        cash_account_code:   كود الصندوق (للاسترداد النقدي)
        bank_account_code:   كود البنك (للاسترداد البنكي)
    
    Returns:
        (True, return_invoice_id, total, None)      نجاح
        (False, "رسالة الخطأ", 0, None)            فشل
        (True, return_invoice_id, total, "ملاحظة")  نجاح + تحذير
    """
    _add_invoice_columns()

    # ============ التحقق من المدخلات ============
    if not items_to_return:
        return False, "يجب اختيار منتج واحد على الأقل", 0, None

    if refund_method == 'cash' and not cash_account_code:
        return False, "يجب اختيار الصندوق للاسترداد النقدي", 0, None

    if refund_method == 'bank' and not bank_account_code:
        return False, "يجب اختيار الحساب البنكي للاسترداد البنكي", 0, None

    conn = get_connection()
    try:
        conn.execute("BEGIN")

        # ============ 1. جلب الفاتورة الأصلية ============
        if invoice_type == "sale":
            original_inv = conn.execute("""
                SELECT i.*, c.name as party_name, i.customer_id as party_id
                FROM invoices i
                JOIN customers c ON i.customer_id = c.id
                WHERE i.id = ?
            """, (invoice_id,)).fetchone()
        else:
            original_inv = conn.execute("""
                SELECT i.*, s.name as party_name, i.supplier_id as party_id
                FROM invoices i
                JOIN suppliers s ON i.supplier_id = s.id
                WHERE i.id = ?
            """, (invoice_id,)).fetchone()

        if not original_inv:
            conn.rollback()
            return False, "الفاتورة الأصلية غير موجودة", 0, None

        original_inv = dict(original_inv)
        party_name = original_inv["party_name"] or "غير معروف"
        vat_rate = float(original_inv["vat_rate"] or 0.15)
        currency_code = original_inv["currency_code"] or "YER"
        exchange_rate = float(original_inv["exchange_rate"] or 1.0)

        # ============ 2. تجميع الكميات ============
        qty_by_product = defaultdict(int)
        for product_name, qty in items_to_return:
            qty_by_product[product_name] += qty

        # ============ 3. التحقق من الكميات المتاحة ============
        available_items = get_invoice_items(invoice_id, conn=conn)
        available_dict = {item['name']: item for item in available_items}

        for product_name, total_qty in qty_by_product.items():
            if product_name not in available_dict:
                conn.rollback()
                return False, f"المنتج '{product_name}' غير موجود في الفاتورة", 0, None
            if total_qty > available_dict[product_name]['available_qty']:
                conn.rollback()
                return False, (
                    f"الكمية المطلوبة ({total_qty}) أكبر من المتاح للإرجاع "
                    f"({available_dict[product_name]['available_qty']}) للمنتج '{product_name}'"
                ), 0, None

        # ============ 4. حماية إضافية لمرتجع المشتريات ============
        if invoice_type == "purchase":
            for product_name, total_qty in qty_by_product.items():
                current = conn.execute(
                    "SELECT quantity FROM products WHERE name = ?", (product_name,)
                ).fetchone()
                if not current:
                    conn.rollback()
                    return False, f"المنتج '{product_name}' غير موجود في المخزون", 0, None
                if total_qty > current["quantity"]:
                    conn.rollback()
                    return False, (
                        f"لا يمكن إرجاع {total_qty} وحدة من '{product_name}'. "
                        f"الرصيد الحالي: {current['quantity']} فقط"
                    ), 0, None

        # ============ 5. حساب المبالغ ============
        subtotal_return = 0.0
        items_data = []

        for product_name, total_qty in qty_by_product.items():
            product = conn.execute(
                "SELECT id, purchase_price, selling_price FROM products WHERE name = ?",
                (product_name,)
            ).fetchone()
            if not product:
                continue

            unit_price = (
                float(product["selling_price"] or 0)
                if invoice_type == "sale"
                else float(product["purchase_price"] or 0)
            )
            line_total = total_qty * unit_price
            subtotal_return += line_total

            items_data.append({
                "product_id": product["id"],
                "product_name": product_name,
                "quantity": total_qty,
                "unit_price": unit_price,
                "line_total": line_total,
            })

        if subtotal_return == 0:
            conn.rollback()
            return False, "لا توجد منتجات صالحة للمرتجع", 0, None

        vat_amount = subtotal_return * vat_rate
        total_return = subtotal_return + vat_amount

        # ============ 6. فحص الرصيد قبل السند ============
        if refund_method == 'cash' and cash_account_code:
            from services.cash_service import check_sufficient_balance
            ok, err = check_sufficient_balance(cash_account_code, total_return, conn=conn)
            if not ok:
                conn.rollback()
                return False, f"لا يمكن الاسترداد النقدي: {err}", 0, None

        if refund_method == 'bank' and bank_account_code:
            from services.bank_service import get_bank_account_by_code
            bank_acc = get_bank_account_by_code(bank_account_code, conn=conn)
            if not bank_acc:
                conn.rollback()
                return False, "الحساب البنكي غير موجود", 0, None
            if float(bank_acc['current_balance'] or 0) < total_return:
                conn.rollback()
                return False, (
                    f"الرصيد غير كافٍ في '{bank_acc['bank_name']}'. "
                    f"المتاح: {bank_acc['current_balance']:,.2f}، "
                    f"المطلوب: {total_return:,.2f}"
                ), 0, None

        # ============ 7. إدراج فاتورة المرتجع ============
        if invoice_type == "sale":
            cursor = conn.execute("""
                INSERT INTO invoices (type, customer_id, invoice_date, total, status,
                                     vat_rate, vat_amount, currency_code, exchange_rate,
                                     reason, reference)
                VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?)
            """, ('sale_return', original_inv["party_id"], return_date, total_return,
                  vat_rate, vat_amount, currency_code, exchange_rate, reason, invoice_id))
        else:
            cursor = conn.execute("""
                INSERT INTO invoices (type, supplier_id, invoice_date, total, status,
                                     vat_rate, vat_amount, currency_code, exchange_rate,
                                     reason, reference)
                VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?)
            """, ('purchase_return', original_inv["party_id"], return_date, total_return,
                  vat_rate, vat_amount, currency_code, exchange_rate, reason, invoice_id))

        return_invoice_id = cursor.lastrowid

        # ============ 8. إدراج البنود + المخزون + FIFO ============
        total_fifo_cost = 0.0

        for item in items_data:
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (return_invoice_id, item["product_id"], item["quantity"], item["unit_price"]))

            if invoice_type == "sale":
                conn.execute(
                    "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                    (item["quantity"], item["product_id"])
                )
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'in', ?, ?, ?)
                """, (item["product_id"], item["quantity"], return_date,
                     f"مرتجع مبيعات #{return_invoice_id}"))

                cost, err = return_fifo_to_original_batch(
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    sale_invoice_id=invoice_id,
                    conn=conn,
                    reference=f"مرتجع مبيعات #{return_invoice_id}"
                )
                if cost is None:
                    raise Exception(f"فشل إرجاع FIFO: {err}")
                total_fifo_cost += cost
            else:
                conn.execute(
                    "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                    (item["quantity"], item["product_id"])
                )
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'out', ?, ?, ?)
                """, (item["product_id"], item["quantity"], return_date,
                     f"مرتجع مشتريات #{return_invoice_id}"))

                cost, err = remove_last_batch(
                    item["product_id"], item["quantity"],
                    conn=conn,
                    reference=f"مرتجع مشتريات #{return_invoice_id}"
                )
                if cost is None:
                    raise Exception(f"فشل خصم FIFO: {err}")
                total_fifo_cost += cost

        # ============ 9. القيد المحاسبي ============
        from services.accounting_service import save_journal_entry

        if invoice_type == "sale":
            acc_sales = get_functional_account("sales_revenue")
            acc_vat = get_functional_account("sales_tax")
            acc_receivables = get_functional_account("accounts_receivable")
            acc_inventory = get_functional_account("inventory")
            acc_cogs = get_functional_account("cogs")

            if refund_method == 'account':
                # خصم من العميل
                lines = [
                    {"account": acc_sales, "debit": subtotal_return, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_vat, "debit": vat_amount, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_receivables, "debit": 0, "credit": total_return,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_inventory, "debit": total_fifo_cost, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_cogs, "debit": 0, "credit": total_fifo_cost,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                ]
            elif refund_method == 'cash':
                # استرداد نقدي من الصندوق
                lines = [
                    {"account": acc_sales, "debit": subtotal_return, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_vat, "debit": vat_amount, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": cash_account_code, "debit": 0, "credit": total_return,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_inventory, "debit": total_fifo_cost, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_cogs, "debit": 0, "credit": total_fifo_cost,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                ]
            else:  # bank
                lines = [
                    {"account": acc_sales, "debit": subtotal_return, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_vat, "debit": vat_amount, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": bank_account_code, "debit": 0, "credit": total_return,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_inventory, "debit": total_fifo_cost, "credit": 0,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                    {"account": acc_cogs, "debit": 0, "credit": total_fifo_cost,
                     "currency_code": currency_code, "exchange_rate": exchange_rate},
                ]
        else:  # purchase
            acc_payables = get_functional_account("accounts_payable")
            acc_purchase_tax = get_functional_account("purchase_tax")
            acc_vat = get_functional_account("sales_tax")

            lines = [
                {"account": acc_payables, "debit": total_return, "credit": 0,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": acc_purchase_tax, "debit": 0, "credit": subtotal_return,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": acc_vat, "debit": 0, "credit": vat_amount,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
            ]

        entry_id, entry_error = save_journal_entry(
            description=f"مرتجع {'مبيعات' if invoice_type == 'sale' else 'مشتريات'} #{return_invoice_id} - {party_name}",
            lines=lines,
            entry_date=return_date,
            conn=conn
        )
        if entry_error:
            raise Exception(f"فشل إنشاء القيد: {entry_error}")

        conn.commit()

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e), 0, None
    finally:
        close_connection(conn)

    # ============ 10. إنشاء سند الصرف (نقدي أو بنكي) ============
    payment_note = None
    if invoice_type == 'sale' and refund_method in ('cash', 'bank'):
        try:
            from services.receipts_service import create_voucher
            target_account = cash_account_code if refund_method == 'cash' else bank_account_code
            voucher_type = 'payment'  # سند صرف
            ref_text = 'استرداد نقدي' if refund_method == 'cash' else 'تحويل بنكي'

            voucher_id, verr = create_voucher(
                voucher_type='payment',
                party_type='customer',
                party_id=original_inv["party_id"],
                amount=total_return,
                account=target_account,
                invoice_id=return_invoice_id,
                reference=f"{ref_text} لمرتجع #{return_invoice_id}",
                notes=f"{ref_text} - {reason}",
                created_by="system",
                auto_link=False,
                conn=None,
            )
            if verr:
                payment_note = f"⚠️ المرتجع تم لكن السند لم يُنشأ: {verr}"
        except Exception as e:
            payment_note = f"⚠️ فشل إنشاء سند الاسترداد: {e}"

    # ============ 11. تسجيل التدقيق ============
    try:
        refund_label = {
            'account': 'حساب',
            'cash': 'نقدي',
            'bank': 'بنكي'
        }.get(refund_method, refund_method)

        log_action(
            username="admin",
            action=f"مرتجع {'مبيعات' if invoice_type == 'sale' else 'مشتريات'}",
            table_name="invoices",
            record_id=return_invoice_id,
            new_value=(
                f"الإجمالي: {total_return:,.2f}, السبب: {reason}, "
                f"طريقة الاسترداد: {refund_label}, "
                f"تكلفة FIFO: {total_fifo_cost:,.2f}"
            )
        )
    except Exception:
        pass

    return True, return_invoice_id, total_return, payment_note


def get_return_history(conn=None):
    """سجل المرتجعات"""
    _add_invoice_columns(conn)
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute("""
            SELECT
                i.id, i.type, i.invoice_date, i.total, i.status, i.reason,
                i.vat_rate, i.vat_amount, i.currency_code,
                (SELECT SUM(ii.quantity) FROM invoice_items ii WHERE ii.invoice_id = i.id) as total_qty
            FROM invoices i
            WHERE i.type IN ('sale_return', 'purchase_return')
            ORDER BY i.id DESC
            LIMIT 50
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)
