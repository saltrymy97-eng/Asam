# services/dashboard_service.py – منطق لوحة المعلومات والمؤشرات (SQLite)
import sqlite3
from database import get_connection

def get_kpi_cards():
    """جلب بيانات البطاقات الإحصائية"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row

    products_count = conn.execute("SELECT COUNT(*) as cnt FROM products").fetchone()["cnt"]
    total_qty = conn.execute("SELECT COALESCE(SUM(quantity),0) as total FROM products").fetchone()["total"] or 0
    total_sales = conn.execute("SELECT COALESCE(SUM(total),0) as total FROM invoices WHERE type='sale'").fetchone()["total"] or 0
    total_purchases = conn.execute("SELECT COALESCE(SUM(total),0) as total FROM invoices WHERE type='purchase'").fetchone()["total"] or 0
    customers_count = conn.execute("SELECT COUNT(*) as cnt FROM customers").fetchone()["cnt"]
    suppliers_count = conn.execute("SELECT COUNT(*) as cnt FROM suppliers").fetchone()["cnt"]
    employees_count = conn.execute("SELECT COUNT(*) as cnt FROM employees").fetchone()["cnt"]

    revenue = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    net_income = revenue - expenses

    conn.close()

    return {
        "products_count": products_count,
        "total_qty": total_qty,
        "total_sales": total_sales,
        "total_purchases": total_purchases,
        "customers_count": customers_count,
        "suppliers_count": suppliers_count,
        "employees_count": employees_count,
        "revenue": revenue,
        "expenses": expenses,
        "net_income": net_income
    }

def get_inventory_by_category():
    """توزيع المخزون حسب الفئة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT category, COALESCE(SUM(quantity),0) as total FROM products GROUP BY category").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_monthly_sales():
    """المبيعات الشهرية لآخر 12 شهر"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total
        FROM invoices WHERE type='sale' AND status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_products(limit=5):
    """أفضل المنتجات مبيعاً"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT p.name, COALESCE(SUM(ii.quantity),0) as total_qty,
               COALESCE(SUM(ii.quantity * ii.unit_price),0) as total_sales
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        JOIN invoices i ON ii.invoice_id = i.id
        WHERE i.type = 'sale' AND i.status = 'completed'
        GROUP BY p.id, p.name
        ORDER BY total_sales DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_low_stock_products(limit=5):
    """المنتجات منخفضة المخزون"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT name, quantity, reorder_level
        FROM products
        WHERE quantity < reorder_level
        ORDER BY quantity ASC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_invoices(limit=5):
    """آخر الفواتير"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT i.id, i.type, i.invoice_date, i.total, i.status,
               CASE WHEN i.type='sale' THEN c.name ELSE s.name END as party_name
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id AND i.type = 'sale'
        LEFT JOIN suppliers s ON i.party_id = s.id AND i.type = 'purchase'
        ORDER BY i.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_activities(limit=8):
    """آخر الأنشطة من سجل التدقيق"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT username, action, table_name, timestamp
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except:
        return []
    finally:
        conn.close()
