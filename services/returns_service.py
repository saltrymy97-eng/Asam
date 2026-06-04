# services/returns_service.py – منطق أعمال المرتجعات (إصدار تجاري: FIFO دقيق + قيود + حماية + أعمدة احترافية)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.fifo_service import (
    return_fifo_to_original_batch,
    remove_last_batch,
    get_fifo_cost
)

def add_reason_column():
    """إضافة عمود reason لجدول invoices إذا لم يكن موجوداً"""
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN reason TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def add_reference_column():
    """إضافة عمود reference لجدول invoices إذا لم يكن موجوداً"""
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN reference INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def get_sales_invoices():
    """جلب فواتير المبيعات المكتملة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, i.invoice_date, c.name as customer, i.total, i.vat_rate, i.vat_amount,
               i.currency_code, i.exchange_rate, i.customer_id
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.type = 'sale' AND i.status = 'completed'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return invoices

def get_purchase_invoices():
    """جلب فواتير المشتريات المكتملة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, i.invoice_date, s.name as supplier, i.total, i.vat_rate, i.vat_amount,
               i.currency_code, i.exchange_rate, i.supplier_id
        FROM invoices i
        JOIN suppliers s ON i.supplier_id = s.id
        WHERE i.type = 'purchase' AND i.status = 'completed'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return invoices

def get_invoice_items(invoice_id):
    """جلب بنود فاتورة محددة مع اسم المنتج والكمية المتاحة للإرجاع"""
    add_reason_column()
    add_reference_column()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
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
        
        available = item["quantity"] - returned_qty
        result.append({
            "id": item["id"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
            "name": item["name"],
            "available_qty": max(0, available),
            "product_id": item["product_id"]
        })
    
    conn.close()
    return result

def process_return(invoice_type, invoice_id, items_to_return, return_date, reason=""):
    """
    تنفيذ عملية المرتجع كاملة (إصدار تجاري):
    - فحص الكميات والرصيد
    - تحديث المخزون
    - FIFO دقيق: مرتجع المبيعات يعيد البضاعة لنفس دفعة الشراء الأصلية
    - القيد المحاسبي قبل commit
    """
    add_reason_column()
    add_reference_column()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. جلب بيانات الفاتورة الأصلية
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
            return False, "الفاتورة الأصلية غير موجودة", 0
        
        party_name = original_inv["party_name"] or "غير معروف"
        vat_rate = original_inv["vat_rate"] or 0.15
        currency_code = original_inv["currency_code"] or "YER"
        exchange_rate = original_inv["exchange_rate"] or 1.0
        
        # 2. التحقق من الكميات المتاحة للإرجاع
        available_items = get_invoice_items(invoice_id)
        available_dict = {item['name']: item for item in available_items}
        
        for product_name, qty in items_to_return:
            if product_name not in available_dict:
                return False, f"المنتج '{product_name}' غير موجود في الفاتورة الأصلية", 0
            if qty > available_dict[product_name]['available_qty']:
                return False, f"الكمية المطلوبة ({qty}) أكبر من المتاح للإرجاع ({available_dict[product_name]['available_qty']}) للمنتج '{product_name}'", 0
        
        # حماية إضافية لمرتجع المشتريات
        if invoice_type == "purchase":
            for product_name, qty in items_to_return:
                current = conn.execute(
                    "SELECT quantity FROM products WHERE name = ?", (product_name,)
                ).fetchone()
                if not current:
                    return False, f"المنتج '{product_name}' غير موجود في المخزون", 0
                if qty > current["quantity"]:
                    return False, f"لا يمكن إرجاع {qty} وحدة من '{product_name}'. الرصيد الحالي: {current['quantity']} فقط", 0
        
        # 3. حساب المبالغ وتجهيز بيانات المنتجات
        subtotal_return = 0.0
        items_data = []
        
        for product_name, qty in items_to_return:
            product = conn.execute(
                "SELECT id, purchase_price, selling_price FROM products WHERE name = ?",
                (product_name,)
            ).fetchone()
            if not product:
                continue
            
            unit_price = product["selling_price"] if invoice_type == "sale" else product["purchase_price"]
            line_total = qty * unit_price
            subtotal_return += line_total
            items_data.append({
                "product_id": product["id"],
                "product_name": product_name,
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_total
            })
        
        if subtotal_return == 0:
            return False, "لا توجد منتجات صالحة للمرتجع", 0
        
        vat_amount = subtotal_return * vat_rate
        total_return = subtotal_return + vat_amount
        
        # 4. بدء المعاملة المحمية
        conn.execute("BEGIN")
        
        # 5. إدراج فاتورة المرتجع (باستخدام العمود المناسب)
        if invoice_type == "sale":
            cursor = conn.execute("""
                INSERT INTO invoices (type, customer_id, invoice_date, total, status, vat_rate, vat_amount,
                                     currency_code, exchange_rate, reason, reference)
                VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?)
            """, (f'sale_return', original_inv["party_id"], return_date, total_return,
                  vat_rate, vat_amount, currency_code, exchange_rate, reason, invoice_id))
        else:
            cursor = conn.execute("""
                INSERT INTO invoices (type, supplier_id, invoice_date, total, status, vat_rate, vat_amount,
                                     currency_code, exchange_rate, reason, reference)
                VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?)
            """, (f'purchase_return', original_inv["party_id"], return_date, total_return,
                  vat_rate, vat_amount, currency_code, exchange_rate, reason, invoice_id))
        return_invoice_id = cursor.lastrowid
        
        # 6. إدراج البنود وتحديث المخزون وFIFO
        total_fifo_cost = 0.0
        
        for item in items_data:
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (return_invoice_id, item["product_id"], item["quantity"], item["unit_price"]))
            
            if invoice_type == "sale":
                conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?",
                           (item["quantity"], item["product_id"]))
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
                conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?",
                           (item["quantity"], item["product_id"]))
                conn.execute("""
                    INSERT INTO stock_movements (product_id, type, quantity, date, reference)
                    VALUES (?, 'out', ?, ?, ?)
                """, (item["product_id"], item["quantity"], return_date,
                     f"مرتجع مشتريات #{return_invoice_id}"))
                
                cost, err = remove_last_batch(
                    item["product_id"], item["quantity"],
                    conn=conn, reference=f"مرتجع مشتريات #{return_invoice_id}"
                )
                if cost is None:
                    raise Exception(f"فشل خصم FIFO: {err}")
                total_fifo_cost += cost
        
        # 7. إنشاء القيد المحاسبي (قبل commit)
        from services.accounting_service import save_journal_entry
        
        if invoice_type == "sale":
            lines = [
                {"account": "مردودات المبيعات", "debit": subtotal_return, "credit": 0,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": "ضريبة القيمة المضافة المستحقة", "debit": vat_amount, "credit": 0,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": party_name, "debit": 0, "credit": total_return,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": "المخزون", "debit": total_fifo_cost, "credit": 0,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": "تكلفة البضاعة المباعة", "debit": 0, "credit": total_fifo_cost,
                 "currency_code": currency_code, "exchange_rate": exchange_rate}
            ]
        else:
            # ✅ مرتجع مشتريات: بدون سطر المخزون
            lines = [
                {"account": party_name, "debit": total_return, "credit": 0,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": "مردودات المشتريات", "debit": 0, "credit": subtotal_return,
                 "currency_code": currency_code, "exchange_rate": exchange_rate},
                {"account": "ضريبة القيمة المضافة المدخلة", "debit": 0, "credit": vat_amount,
                 "currency_code": currency_code, "exchange_rate": exchange_rate}
            ]
        
        entry_id, entry_error = save_journal_entry(
            description=f"مرتجع {'مبيعات' if invoice_type == 'sale' else 'مشتريات'} #{return_invoice_id} - {party_name}",
            lines=lines,
            entry_date=return_date,
            conn=conn
        )
        
        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {entry_error}")
        
        conn.commit()
        
        return_type_name = "مرتجع مبيعات" if invoice_type == "sale" else "مرتجع مشتريات"
        log_action(
            username="admin", action=return_type_name, table_name="invoices",
            record_id=return_invoice_id,
            new_value=f"الإجمالي: {total_return:,.2f}, السبب: {reason}, تكلفة FIFO الأصلية: {total_fifo_cost:,.2f}"
        )
        
        return True, return_invoice_id, total_return
        
    except Exception as e:
        conn.rollback()
        return False, str(e), 0
    finally:
        conn.close()

def get_return_history():
    """سجل المرتجعات"""
    add_reason_column()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    returns = conn.execute("""
        SELECT 
            i.id, i.type, i.invoice_date, i.total, i.status, i.reason,
            i.vat_rate, i.vat_amount, i.currency_code,
            (SELECT SUM(ii.quantity) FROM invoice_items ii WHERE ii.invoice_id = i.id) as total_qty
        FROM invoices i
        WHERE i.type IN ('sale_return', 'purchase_return')
        ORDER BY i.id DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    # تحويل الصفوف إلى قواميس لتتوافق مع واجهة المستخدم
    return [dict(r) for r in returns]
