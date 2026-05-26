# services/dashboard_service.py – منطق لوحة المعلومات والمؤشرات (مُحدث مع الإشعارات الفورية)
import sqlite3
from database import get_connection
from datetime import date, timedelta

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

    # 🆕 إحصائيات اليوم
    today = date.today().strftime("%Y-%m-%d")
    today_sales = conn.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='sale' AND invoice_date=?", (today,)).fetchone()[0]
    today_purchases = conn.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='purchase' AND invoice_date=?", (today,)).fetchone()[0]
    today_invoices = conn.execute("SELECT COUNT(*) FROM invoices WHERE invoice_date=?", (today,)).fetchone()[0]

    # 🆕 نمو الإيرادات (مقارنة بالشهر السابق)
    this_month = date.today().strftime("%Y-%m")
    last_month = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    
    this_month_sales = conn.execute("""
        SELECT COALESCE(SUM(total),0) FROM invoices 
        WHERE type='sale' AND status='completed' AND strftime('%Y-%m', invoice_date)=?
    """, (this_month,)).fetchone()[0]
    
    last_month_sales = conn.execute("""
        SELECT COALESCE(SUM(total),0) FROM invoices 
        WHERE type='sale' AND status='completed' AND strftime('%Y-%m', invoice_date)=?
    """, (last_month,)).fetchone()[0]
    
    growth = ((this_month_sales - last_month_sales) / last_month_sales * 100) if last_month_sales > 0 else 0

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
        "net_income": net_income,
        "today_sales": today_sales,
        "today_purchases": today_purchases,
        "today_invoices": today_invoices,
        "growth": growth
    }

def get_alerts():
    """🆕 جلب التنبيهات والإشعارات الفورية"""
    alerts = []
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    today = date.today().strftime("%Y-%m-%d")

    # 1. منتجات منخفضة المخزون (أقل من حد إعادة الطلب)
    low_stock = conn.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE quantity < reorder_level"
    ).fetchone()["cnt"]
    if low_stock > 0:
        alerts.append({
            "type": "warning",
            "icon": "📦",
            "title": "منتجات منخفضة المخزون",
            "message": f"يوجد {low_stock} منتجات تحت الحد الأدنى",
            "time": "الآن"
        })

    # 2. فواتير اليوم
    today_invoices = conn.execute(
        "SELECT COUNT(*) as cnt FROM invoices WHERE invoice_date=?", (today,)
    ).fetchone()["cnt"]
    if today_invoices > 0:
        today_sales = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='sale' AND invoice_date=?", (today,)
        ).fetchone()[0]
        alerts.append({
            "type": "info",
            "icon": "🧾",
            "title": "فواتير اليوم",
            "message": f"{today_invoices} فاتورة بقيمة {today_sales:,.0f}",
            "time": "اليوم"
        })

    # 3. موظفين بدون راتب هذا الشهر
    current_month = date.today().strftime("%Y-%m")
    unpaid = conn.execute("""
        SELECT COUNT(*) as cnt FROM employees e 
        WHERE e.id NOT IN (
            SELECT employee_id FROM payroll_runs WHERE month=?
        )
    """, (current_month,)).fetchone()["cnt"]
    if unpaid > 0:
        alerts.append({
            "type": "danger",
            "icon": "⚠️",
            "title": "رواتب متأخرة",
            "message": f"{unpaid} موظفين لم يستلموا رواتبهم هذا الشهر",
            "time": "الشهر الحالي"
        })

    # 4. عملاء محتملين جدد (CRM)
    try:
        new_leads = conn.execute(
            "SELECT COUNT(*) as cnt FROM crm_leads WHERE status='جديد'"
        ).fetchone()["cnt"]
        if new_leads > 0:
            alerts.append({
                "type": "success",
                "icon": "🤝",
                "title": "عملاء محتملين جدد",
                "message": f"{new_leads} عملاء جدد ينتظرون المتابعة",
                "time": "الآن"
            })
    except:
        pass

    # 5. فترات مالية تحتاج إغلاق
    last_month_str = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    is_closed = conn.execute(
        "SELECT COUNT(*) FROM closed_periods WHERE period_type='month' AND period_value=?",
        (last_month_str,)
    ).fetchone()[0]
    if not is_closed:
        alerts.append({
            "type": "warning",
            "icon": "📅",
            "title": "فترة غير مغلقة",
            "message": f"الشهر الماضي {last_month_str} لم يُغلق بعد",
            "time": "الشهر الماضي"
        })

    conn.close()
    return alerts

def get_quick_stats():
    """🆕 إحصائيات سريعة للعرض في أعلى لوحة المعلومات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    today = date.today().strftime("%Y-%m-%d")
    
    today_sales = conn.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='sale' AND invoice_date=?", (today,)).fetchone()[0]
    today_purchases = conn.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE type='purchase' AND invoice_date=?", (today,)).fetchone()[0]
    low_stock = conn.execute("SELECT COUNT(*) FROM products WHERE quantity < reorder_level").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    
    conn.close()
    return {
        "today_sales": today_sales,
        "today_purchases": today_purchases,
        "low_stock": low_stock,
        "total_customers": total_customers
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
