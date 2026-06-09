# services/pdf_service.py – خدمة تقارير HTML (عربي، بدون مكتبات)
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join("data", "erp.db")
OUTPUT_DIR = "pdf_reports"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def html_template(title, body):
    """قالب HTML أساسي بتنسيق جميل"""
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
    body {{ font-family: Arial, sans-serif; background:#1E1B4B; color:#F8FAFC; padding:2rem; }}
    h1 {{ color:#8B5CF6; text-align:center; }}
    table {{ width:100%; border-collapse:collapse; margin:1rem 0; background:rgba(255,255,255,0.05); border-radius:12px; }}
    th {{ background:rgba(139,92,246,0.3); padding:12px; text-align:center; }}
    td {{ padding:10px; text-align:center; border-bottom:1px solid rgba(255,255,255,0.1); }}
    .footer {{ text-align:center; color:#64748B; margin-top:2rem; font-size:0.8rem; }}
</style>
</head>
<body>
    <h1>{title}</h1>
    {body}
    <div class="footer">تم الإنشاء بواسطة XD ERP – {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</body>
</html>"""

def generate_income_statement():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0]
    if count == 0:
        conn.close()
        return None
    revenue = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    conn.close()
    net = revenue - expenses
    body = f"""
    <table>
        <tr><th>البيان</th><th>المبلغ (ريال)</th></tr>
        <tr><td>الإيرادات</td><td>{revenue:,.2f}</td></tr>
        <tr><td>المصروفات</td><td>{expenses:,.2f}</td></tr>
        <tr style="font-weight:bold; background:rgba(16,185,129,0.2);"><td>صافي الدخل</td><td>{net:,.2f}</td></tr>
    </table>"""
    html = html_template("قائمة الدخل", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"income_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def generate_balance_sheet():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0]
    if count == 0:
        conn.close()
        return None
    assets = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '3%'").fetchone()[0]
    conn.close()
    body = f"""
    <table>
        <tr><th>البيان</th><th>المبلغ (ريال)</th></tr>
        <tr><td>الأصول</td><td>{assets:,.2f}</td></tr>
        <tr><td>الخصوم</td><td>{liabilities:,.2f}</td></tr>
        <tr><td>حقوق الملكية</td><td>{equity:,.2f}</td></tr>
    </table>"""
    html = html_template("الميزانية العمومية", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"balance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def generate_inventory_report():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        conn.close()
        return None
    rows = conn.execute("SELECT name, quantity, reorder_level FROM products").fetchall()
    conn.close()
    rows_html = "".join(f"<tr><td>{r['name']}</td><td>{r['quantity']}</td><td>{r['reorder_level']}</td></tr>" for r in rows)
    body = f"""
    <table>
        <tr><th>المنتج</th><th>الكمية</th><th>حد إعادة الطلب</th></tr>
        {rows_html}
    </table>"""
    html = html_template("تقرير المخزون", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def generate_audit_report():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    if count == 0:
        conn.close()
        return None
    rows = conn.execute("SELECT username, action, table_name, timestamp FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    rows_html = "".join(f"<tr><td>{r['username']}</td><td>{r['action']}</td><td>{r['table_name']}</td><td>{r['timestamp']}</td></tr>" for r in rows)
    body = f"""
    <table>
        <tr><th>المستخدم</th><th>الإجراء</th><th>الجدول</th><th>التوقيت</th></tr>
        {rows_html}
    </table>"""
    html = html_template("سجل التدقيق", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def generate_invoice_pdf(invoice_id):
    conn = get_conn()
    inv = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        return None
    items = conn.execute("""
        SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    items_html = "".join(f"<tr><td>{it['name']}</td><td>{it['quantity']}</td><td>{it['unit_price']:,.2f}</td><td>{it['total']:,.2f}</td></tr>" for it in items)
    body = f"""
    <p>رقم الفاتورة: {inv['id']} | التاريخ: {inv['invoice_date']} | الإجمالي: {inv['total']:,.2f} ريال</p>
    <table>
        <tr><th>المنتج</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr>
        {items_html}
    </table>"""
    html = html_template(f"فاتورة #{inv['id']}", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"invoice_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
