# services/purchases_service.py – منطق أعمال المشتريات (SQLite)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action

def get_suppliers():
    """جلب الموردين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return [dict(s) for s in suppliers]

def get_products_for_purchase():
    """جلب جميع المنتجات للشراء"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute("SELECT id, name, purchase_price FROM products ORDER BY name").fetchall()
    conn.close()
    return [dict(p) for p in products]

def create_purchase_invoice(supplier_id, items, username="admin"):
    """إنشاء فاتورة مشتريات محمية"""
    total = sum(item["quantity"] * item["unit_price"] for item in items)
    conn = get_connection()

    try:
        conn.execute("BEGIN")

        supplier_check = conn.execute("SELECT id FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not supplier_check:
            conn.rollback()
            conn.close()
            return None, 0, "المورد غير موجود"

        for item in items:
            product_check = conn.execute("SELECT id FROM products WHERE id = ?", (item["product_id"],)).fetchone()
            if not product_check:
                conn.rollback()
                conn.close()
                return None, 0, f"المنتج {item.get('name', item['product_id'])} غير موجود"

        cur = conn.execute(
            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('purchase', ?, date('now'), ?, 'completed')",
            (supplier_id, total)
        )
        invoice_id = cur.lastrowid

        for item in items:
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'in', ?, date('now'), ?)",
                (item["product_id"], item["quantity"], f"فاتورة مشتريات #{invoice_id}")
            )
            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (item["quantity"], item["product_id"])
            )

        conn.commit()

        supplier_name = "غير معروف"
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
            if row:
                supplier_name = row["name"]
        except:
            pass

        log_action(
            username=username,
            action="فاتورة مشتريات",
            table_name="invoices",
            record_id=invoice_id,
            new_value=f"المورد: {supplier_name}, الإجمالي: {total:,.2f}"
        )

        return invoice_id, total, None

    except Exception as e:
        conn.rollback()
        return None, 0, str(e)
    finally:
        conn.close()

def get_purchase_invoices():
    """جلب فواتير المشتريات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    invoices = conn.execute("""
        SELECT i.id, s.name as supplier, i.invoice_date, i.total, i.status
        FROM invoices i
        LEFT JOIN suppliers s ON i.party_id = s.id
        WHERE i.type = 'purchase'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return [dict(inv) for inv in invoices]

def get_invoice_details(invoice_id):
    """جلب تفاصيل فاتورة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    details = conn.execute("""
        SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    return [dict(d) for d in details]

def add_supplier(name, phone, address, username="admin"):
    """إضافة مورد"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)",
        (name, phone, address)
    )
    conn.commit()
    conn.close()

    log_action(
        username=username,
        action="إضافة مورد",
        table_name="suppliers",
        new_value=f"المورد: {name}, الهاتف: {phone}"
    )
    return True

def get_all_suppliers():
    """جلب جميع الموردين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT * FROM suppliers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(s) for s in suppliers]
