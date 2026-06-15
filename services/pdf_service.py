# services/pdf_service.py – خدمة تقارير احترافية (عربي، XBRL، بدون مكتبات)
import sqlite3
import os
import xml.etree.ElementTree as ET
from datetime import datetime

DB_PATH = os.path.join("data", "erp.db")
OUTPUT_DIR = "reports"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

# ===================== قوالب HTML احترافية =====================

def html_template(title, body, logo_text="حوكمة ERP", subtitle="إدارة ذكية .. قرارات واثقة"):
    """قالب HTML احترافي بتصميم ذهبي"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<title>{title} - {logo_text}</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    * {{ font-family: 'Cairo', sans-serif; }}
    body {{
        background: linear-gradient(135deg, #02060d 0%, #0a1324 40%, #060e1a 100%);
        color: #F8FAFC; padding: 2rem; min-height: 100vh;
    }}
    .header {{
        text-align: center; margin-bottom: 2rem;
        border-bottom: 2px solid #D4AF37; padding-bottom: 1.5rem;
    }}
    .header .logo {{
        font-size: 2.5rem; font-weight: 800;
        background: linear-gradient(135deg, #D4AF37, #FCF6BA, #D4AF37);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .header .subtitle {{ color: #CBD5E1; font-size: 1rem; letter-spacing: 3px; }}
    .header .meta {{ color: #64748B; font-size: 0.85rem; margin-top: 0.5rem; }}
    h1 {{ color: #D4AF37; text-align: center; font-size: 1.8rem; margin: 1.5rem 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0;
             background: rgba(255,255,255,0.03); border-radius: 16px; overflow: hidden;
             border: 1px solid rgba(212,175,55,0.2); }}
    th {{ background: linear-gradient(135deg, rgba(212,175,55,0.3), rgba(212,175,55,0.1));
          padding: 14px; text-align: center; color: #FCF6BA; font-weight: 700; font-size: 0.95rem; }}
    td {{ padding: 12px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.05); }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(212,175,55,0.05); }}
    .total-row {{ font-weight: 800; background: rgba(16,185,129,0.15) !important; }}
    .footer {{
        text-align: center; color: #64748B; margin-top: 3rem; font-size: 0.8rem;
        border-top: 1px solid rgba(212,175,55,0.2); padding-top: 1rem;
    }}
    .gold {{ color: #D4AF37; }}
    @media print {{ body {{ background: white; color: black; }} }}
</style>
</head>
<body>
    <div class="header">
        <div class="logo">{logo_text}</div>
        <div class="subtitle">{subtitle}</div>
        <div class="meta">تاريخ التقرير: {now}</div>
    </div>
    <h1>{title}</h1>
    {body}
    <div class="footer">© {datetime.now().year} {logo_text} – جميع الحقوق محفوظة</div>
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
        <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
        <tr><td>الإيرادات</td><td style="color:#10B981;">{revenue:,.2f}</td></tr>
        <tr><td>المصروفات</td><td style="color:#EF4444;">{expenses:,.2f}</td></tr>
        <tr class="total-row"><td>صافي الدخل</td><td style="color:{'#10B981' if net >= 0 else '#EF4444'};">{net:,.2f}</td></tr>
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
        <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
        <tr><td style="color:#3B82F6;">الأصول</td><td>{assets:,.2f}</td></tr>
        <tr><td style="color:#F59E0B;">الخصوم</td><td>{liabilities:,.2f}</td></tr>
        <tr><td style="color:#8B5CF6;">حقوق الملكية</td><td>{equity:,.2f}</td></tr>
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
    rows = conn.execute("SELECT name, quantity, reorder_level FROM products ORDER BY quantity ASC").fetchall()
    conn.close()
    rows_html = ""
    for r in rows:
        status = "⚠️ منخفض" if r['quantity'] < r['reorder_level'] else "✅ آمن"
        color = "#EF4444" if r['quantity'] < r['reorder_level'] else "#10B981"
        rows_html += f"<tr><td>{r['name']}</td><td>{r['quantity']}</td><td>{r['reorder_level']}</td><td style='color:{color};'>{status}</td></tr>"
    body = f"""
    <table>
        <tr><th>المنتج</th><th>الكمية</th><th>حد إعادة الطلب</th><th>الحالة</th></tr>
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

def generate_invoice_html(invoice_id):
    conn = get_conn()
    inv = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        return None
    items = conn.execute("""
        SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
        FROM invoice_items ii JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    items_html = "".join(f"<tr><td>{it['name']}</td><td>{it['quantity']}</td><td>{it['unit_price']:,.2f}</td><td>{it['total']:,.2f}</td></tr>" for it in items)
    body = f"""
    <div style="text-align:center; margin-bottom:1rem;">
        <p>رقم الفاتورة: <strong>#{inv['id']}</strong> | التاريخ: <strong>{inv['invoice_date']}</strong></p>
        <p>الإجمالي: <strong style="color:#D4AF37; font-size:1.5rem;">{inv['total']:,.2f} ر.ي</strong></p>
    </div>
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

def generate_cash_report(cash_account_id=None):
    """تقرير الصندوق"""
    conn = get_conn()
    from services.cash_service import get_cash_balance_summary, get_cash_statement
    from datetime import date as dt
    summary, total = get_cash_balance_summary()
    if not summary:
        conn.close()
        return None
    today = dt.today()
    from_date = today.replace(day=1).strftime('%Y-%m-%d')
    to_date = today.strftime('%Y-%m-%d')
    body = "<h2 style='color:#D4AF37;'>ملخص الصناديق</h2><table><tr><th>الصندوق</th><th>العملة</th><th>الرصيد</th></tr>"
    for s in summary:
        body += f"<tr><td>{s['name']}</td><td>{s['currency']}</td><td>{s['balance']:,.2f}</td></tr>"
    body += f"<tr class='total-row'><td colspan='2'>الإجمالي (بالعملة الأساسية)</td><td>{total:,.2f}</td></tr></table>"
    conn.close()
    html = html_template("تقرير الصندوق", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"cash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def generate_vat_report():
    """تقرير ضريبة القيمة المضافة"""
    conn = get_conn()
    rate = conn.execute("SELECT rate FROM vat_config WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()
    vat_rate = rate[0] if rate else 0.15
    sales_vat = conn.execute("SELECT COALESCE(SUM(vat_amount),0) FROM invoices WHERE type='sale' AND status='completed'").fetchone()[0]
    purchase_vat = conn.execute("SELECT COALESCE(SUM(vat_amount),0) FROM invoices WHERE type='purchase' AND status='completed'").fetchone()[0]
    net_vat = sales_vat - purchase_vat
    conn.close()
    body = f"""
    <table>
        <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
        <tr><td>ضريبة المبيعات المستحقة</td><td>{sales_vat:,.2f}</td></tr>
        <tr><td>ضريبة المشتريات القابلة للخصم</td><td>{purchase_vat:,.2f}</td></tr>
        <tr class="total-row"><td>صافي الضريبة {'المستحقة' if net_vat >= 0 else 'القابلة للاسترداد'}</td><td>{abs(net_vat):,.2f}</td></tr>
    </table>
    <p style="text-align:center; color:#CBD5E1;">معدل الضريبة: {vat_rate*100:.0f}%</p>"""
    html = html_template("تقرير ضريبة القيمة المضافة", body)
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"vat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

# ===================== XBRL (لغة تقارير الأعمال الموسعة) =====================

def generate_xbrl_income():
    """توليد تقرير قائمة الدخل بصيغة XBRL"""
    conn = get_conn()
    revenue = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    conn.close()
    net = revenue - expenses
    now = datetime.now()
    
    xbrl = ET.Element('xbrl', {'xmlns': 'http://www.xbrl.org/2003/instance'})
    schema = ET.SubElement(xbrl, 'schemaRef')
    ctx = ET.SubElement(xbrl, 'context', {'id': 'current'})
    entity = ET.SubElement(ctx, 'entity')
    ET.SubElement(entity, 'identifier', {'scheme': 'http://hokoma-erp.com'}).text = 'حوكمة ERP'
    period = ET.SubElement(ctx, 'period')
    ET.SubElement(period, 'startDate').text = f'{now.year}-01-01'
    ET.SubElement(period, 'endDate').text = now.strftime('%Y-%m-%d')
    
    unit = ET.SubElement(xbrl, 'unit', {'id': 'YER'})
    ET.SubElement(unit, 'measure').text = 'iso4217:YER'
    
    rev = ET.SubElement(xbrl, 'Revenue', {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
    rev.text = str(revenue)
    exp = ET.SubElement(xbrl, 'Expenses', {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
    exp.text = str(expenses)
    ni = ET.SubElement(xbrl, 'NetIncome', {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
    ni.text = str(net)
    
    tree = ET.ElementTree(xbrl)
    ET.indent(tree, space='  ')
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"xbrl_income_{now.strftime('%Y%m%d_%H%M%S')}.xml")
    tree.write(path, encoding='utf-8', xml_declaration=True)
    return path

def generate_xbrl_balance():
    """توليد تقرير الميزانية العمومية بصيغة XBRL"""
    conn = get_conn()
    assets = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '3%'").fetchone()[0]
    conn.close()
    now = datetime.now()
    
    xbrl = ET.Element('xbrl', {'xmlns': 'http://www.xbrl.org/2003/instance'})
    ET.SubElement(xbrl, 'schemaRef')
    ctx = ET.SubElement(xbrl, 'context', {'id': 'current'})
    entity = ET.SubElement(ctx, 'entity')
    ET.SubElement(entity, 'identifier', {'scheme': 'http://hokoma-erp.com'}).text = 'حوكمة ERP'
    period = ET.SubElement(ctx, 'period')
    ET.SubElement(period, 'instant').text = now.strftime('%Y-%m-%d')
    
    unit = ET.SubElement(xbrl, 'unit', {'id': 'YER'})
    ET.SubElement(unit, 'measure').text = 'iso4217:YER'
    
    a = ET.SubElement(xbrl, 'Assets', {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
    a.text = str(assets)
    l = ET.SubElement(xbrl, 'Liabilities', {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
    l.text = str(liabilities)
    e = ET.SubElement(xbrl, 'Equity', {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
    e.text = str(equity)
    
    tree = ET.ElementTree(xbrl)
    ET.indent(tree, space='  ')
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"xbrl_balance_{now.strftime('%Y%m%d_%H%M%S')}.xml")
    tree.write(path, encoding='utf-8', xml_declaration=True)
    return path
