# services/pdf_service.py – خدمة تقارير احترافية (عربي، XBRL، بدون مكتبات)
# v2.0 — استخدام account_type بدل LIKE + تقارير أعمار الذمم وكشوف الحسابات
import sqlite3
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta

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
    h2 {{ color: #D4AF37; font-size: 1.3rem; margin: 1.5rem 0 0.5rem 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0;
             background: rgba(255,255,255,0.03); border-radius: 16px; overflow: hidden;
             border: 1px solid rgba(212,175,55,0.2); }}
    th {{ background: linear-gradient(135deg, rgba(212,175,55,0.3), rgba(212,175,55,0.1));
          padding: 14px; text-align: center; color: #FCF6BA; font-weight: 700; font-size: 0.95rem; }}
    td {{ padding: 12px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.05); }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(212,175,55,0.05); }}
    .total-row {{ font-weight: 800; background: rgba(16,185,129,0.15) !important; }}
    .danger-row {{ font-weight: 700; background: rgba(239,68,68,0.15) !important; }}
    .warning-row {{ font-weight: 700; background: rgba(245,158,11,0.15) !important; }}
    .success-row {{ font-weight: 700; background: rgba(16,185,129,0.15) !important; }}
    .footer {{
        text-align: center; color: #64748B; margin-top: 3rem; font-size: 0.8rem;
        border-top: 1px solid rgba(212,175,55,0.2); padding-top: 1rem;
    }}
    .gold {{ color: #D4AF37; }}
    .green {{ color: #10B981; }}
    .red {{ color: #EF4444; }}
    .orange {{ color: #F59E0B; }}
    .blue {{ color: #3B82F6; }}
    .badge {{
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-size: 0.85rem; font-weight: 700;
    }}
    .badge-paid {{ background: rgba(16,185,129,0.25); color: #10B981; }}
    .badge-partial {{ background: rgba(245,158,11,0.25); color: #F59E0B; }}
    .badge-unpaid {{ background: rgba(239,68,68,0.25); color: #EF4444; }}
    .info-block {{
        background: rgba(212,175,55,0.08); border-right: 4px solid #D4AF37;
        padding: 1rem 1.5rem; margin: 1rem 0; border-radius: 8px;
    }}
    .info-block p {{ margin: 0.3rem 0; }}
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


# ===================== دوال مساعدة داخلية =====================

def _sum_by_account_type(conn, account_type, entry_date=None):
    """
    جمع المبالغ بحسب account_type (Revenue, Expense, Asset, Liability, Equity).
    
    الطريقة:
        - نربط journal_lines.account_name مع accounts.code
        - نستخدم account_type من جدول accounts (أدق من LIKE)
        - نضرب في exchange_rate لتحويل العملات الأجنبية
    
    Returns:
        (debit_total, credit_total)
    """
    if entry_date:
        row = conn.execute("""
            SELECT 
                COALESCE(SUM(jl.debit * jl.exchange_rate), 0) AS debit_total,
                COALESCE(SUM(jl.credit * jl.exchange_rate), 0) AS credit_total
            FROM journal_lines jl
            JOIN journal_entries je ON jl.entry_id = je.id
            JOIN accounts a ON jl.account_name = a.code
            WHERE a.account_type = ? AND je.date <= ?
        """, (account_type, entry_date)).fetchone()
    else:
        row = conn.execute("""
            SELECT 
                COALESCE(SUM(jl.debit * jl.exchange_rate), 0) AS debit_total,
                COALESCE(SUM(jl.credit * jl.exchange_rate), 0) AS credit_total
            FROM journal_lines jl
            JOIN accounts a ON jl.account_name = a.code
            WHERE a.account_type = ?
        """, (account_type,)).fetchone()
    
    if not row:
        return 0.0, 0.0
    return float(row["debit_total"] or 0), float(row["credit_total"] or 0)


def _account_balance(conn, functional_type):
    """
    جلب رصيد حساب بحسب النوع الوظيفي.
    Returns: الرصيد (debit - credit) بالعملة الأساسية.
    """
    row = conn.execute("""
        SELECT 
            COALESCE(SUM(jl.debit * jl.exchange_rate), 0) -
            COALESCE(SUM(jl.credit * jl.exchange_rate), 0) AS balance
        FROM journal_lines jl
        JOIN accounts a ON jl.account_name = a.code
        WHERE a.functional_type = ?
    """, (functional_type,)).fetchone()
    return float(row["balance"] or 0) if row else 0.0


def _save_and_return(html, filename_prefix):
    """حفظ HTML وإرجاع المسار"""
    ensure_output_dir()
    path = os.path.join(
        OUTPUT_DIR,
        f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ===================== التقارير الأساسية (معدلة) =====================

def generate_income_statement():
    """قائمة الدخل — تعتمد على account_type بدل LIKE"""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0]
        if count == 0:
            return None

        rev_d, rev_c = _sum_by_account_type(conn, "Revenue")
        revenue = rev_c - rev_d

        exp_d, exp_c = _sum_by_account_type(conn, "Expense")
        expenses = exp_d - exp_c

        net = revenue - expenses

        body = f"""
        <table>
            <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
            <tr><td>الإيرادات</td><td class="green">{revenue:,.2f}</td></tr>
            <tr><td>المصروفات</td><td class="red">{expenses:,.2f}</td></tr>
            <tr class="total-row">
                <td>صافي الدخل</td>
                <td class="{'green' if net >= 0 else 'red'}">{net:,.2f}</td>
            </tr>
        </table>"""

        html = html_template("قائمة الدخل", body)
        return _save_and_return(html, "income")
    finally:
        conn.close()


def generate_balance_sheet():
    """الميزانية العمومية — تعتمد على account_type"""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0]
        if count == 0:
            return None

        # الأصول: debit - credit
        a_d, a_c = _sum_by_account_type(conn, "Asset")
        assets = a_d - a_c

        # الخصوم: credit - debit
        l_d, l_c = _sum_by_account_type(conn, "Liability")
        liabilities = l_c - l_d

        # حقوق الملكية: credit - debit
        e_d, e_c = _sum_by_account_type(conn, "Equity")
        equity = e_c - e_d

        # صافي الدخل يضاف لحقوق الملكية
        rev_d, rev_c = _sum_by_account_type(conn, "Revenue")
        exp_d, exp_c = _sum_by_account_type(conn, "Expense")
        net_income = (rev_c - rev_d) - (exp_d - exp_c)
        total_equity = equity + net_income

        total_liab_eq = liabilities + total_equity

        body = f"""
        <table>
            <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
            <tr><td class="blue">الأصول</td><td>{assets:,.2f}</td></tr>
            <tr><td class="orange">الخصوم</td><td>{liabilities:,.2f}</td></tr>
            <tr><td style="color:#8B5CF6;">حقوق الملكية</td><td>{equity:,.2f}</td></tr>
            <tr><td style="color:#8B5CF6;">صافي الدخل (المُضاف)</td><td>{net_income:,.2f}</td></tr>
            <tr class="total-row">
                <td>إجمالي الخصوم + حقوق الملكية</td>
                <td>{total_liab_eq:,.2f}</td>
            </tr>
        </table>
        <div class="info-block">
            <p><strong>ملاحظة:</strong> إذا كان الفرق بين الأصول و(الخصوم + حقوق الملكية) لا يساوي صفراً، فهناك قيود غير متوازنة أو عمليات ناقصة.</p>
            <p><strong>الفرق:</strong> <span class="{'green' if abs(assets - total_liab_eq) < 0.01 else 'red'}">{assets - total_liab_eq:,.2f}</span></p>
        </div>"""

        html = html_template("الميزانية العمومية", body)
        return _save_and_return(html, "balance")
    finally:
        conn.close()


def generate_inventory_report():
    """تقرير المخزون"""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            return None
        rows = conn.execute(
            "SELECT name, quantity, reorder_level FROM products ORDER BY quantity ASC"
        ).fetchall()

        rows_html = ""
        for r in rows:
            is_low = r['quantity'] < (r['reorder_level'] or 0)
            status = "⚠️ منخفض" if is_low else "✅ آمن"
            color = "red" if is_low else "green"
            rows_html += (
                f"<tr><td>{r['name']}</td><td>{r['quantity']}</td>"
                f"<td>{r['reorder_level']}</td>"
                f"<td class='{color}'>{status}</td></tr>"
            )

        body = f"""
        <table>
            <tr><th>المنتج</th><th>الكمية</th><th>حد إعادة الطلب</th><th>الحالة</th></tr>
            {rows_html}
        </table>"""
        html = html_template("تقرير المخزون", body)
        return _save_and_return(html, "inventory")
    finally:
        conn.close()


def generate_audit_report():
    """سجل التدقيق"""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        if count == 0:
            return None
        rows = conn.execute(
            "SELECT username, action, table_name, timestamp FROM audit_log "
            "ORDER BY id DESC LIMIT 100"
        ).fetchall()
        rows_html = "".join(
            f"<tr><td>{r['username']}</td><td>{r['action']}</td>"
            f"<td>{r['table_name']}</td><td>{r['timestamp']}</td></tr>"
            for r in rows
        )
        body = f"""
        <table>
            <tr><th>المستخدم</th><th>الإجراء</th><th>الجدول</th><th>التوقيت</th></tr>
            {rows_html}
        </table>"""
        html = html_template("سجل التدقيق", body)
        return _save_and_return(html, "audit")
    finally:
        conn.close()


# ===================== فاتورة HTML (معدّلة) =====================

def generate_invoice_html(invoice_id):
    """فاتورة HTML — مع عرض حالة الدفع الكاملة"""
    conn = get_conn()
    try:
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv:
            return None

        items = conn.execute("""
            SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) AS total
            FROM invoice_items ii
            JOIN products p ON ii.product_id = p.id
            WHERE ii.invoice_id = ?
        """, (invoice_id,)).fetchall()

        # بيانات الطرف
        inv_dict = dict(inv)
        if inv_dict.get("customer_id"):
            c = conn.execute("SELECT name FROM customers WHERE id=?",
                             (inv_dict["customer_id"],)).fetchone()
            party_name = c["name"] if c else "—"
            party_label = "العميل"
        else:
            s = conn.execute("SELECT name FROM suppliers WHERE id=?",
                             (inv_dict["supplier_id"],)).fetchone()
            party_name = s["name"] if s else "—"
            party_label = "المورد"

        # الدفعات المرتبطة
        payments = conn.execute("""
            SELECT ip.amount, ip.payment_date, ip.payment_method, ip.voucher_id
            FROM invoice_payments ip
            WHERE ip.invoice_id = ?
            ORDER BY ip.payment_date, ip.id
        """, (invoice_id,)).fetchall()

        # إجماليات الدفع
        paid = float(inv_dict.get("paid_amount") or 0)
        remaining = float(inv_dict.get("remaining_amount") or 0)
        total = float(inv_dict.get("total") or 0)
        status = inv_dict.get("payment_status") or "unpaid"
        method = inv_dict.get("payment_method") or "—"

        status_label = {
            "unpaid": "🔴 غير مدفوعة",
            "partial": "🟡 مدفوعة جزئياً",
            "paid": "🟢 مدفوعة بالكامل"
        }.get(status, status)

        method_label = {
            "cash": "نقدي",
            "bank": "بنكي",
            "credit": "آجل",
            "mixed": "مختلط"
        }.get(method, method or "—")

        # بنود الفاتورة
        items_html = "".join(
            f"<tr><td>{it['name']}</td><td>{it['quantity']}</td>"
            f"<td>{it['unit_price']:,.2f}</td><td>{it['total']:,.2f}</td></tr>"
            for it in items
        )

        # جدول الدفعات
        payments_html = ""
        if payments:
            payments_html = """
            <h2>الدفعات المرتبطة</h2>
            <table>
                <tr><th>التاريخ</th><th>المبلغ</th><th>طريقة الدفع</th><th>السند</th></tr>
            """
            for p in payments:
                pm_method = {
                    "cash": "نقدي", "bank": "بنكي", "credit": "آجل"
                }.get(p["payment_method"], p["payment_method"])
                payments_html += (
                    f"<tr><td>{p['payment_date']}</td>"
                    f"<td class='green'>{float(p['amount']):,.2f}</td>"
                    f"<td>{pm_method}</td>"
                    f"<td>#{p['voucher_id'] or '—'}</td></tr>"
                )
            payments_html += "</table>"

        body = f"""
        <div class="info-block">
            <p><strong>{party_label}:</strong> {party_name}</p>
            <p><strong>رقم الفاتورة:</strong> #{inv_dict['id']} | <strong>التاريخ:</strong> {inv_dict['invoice_date']}</p>
            <p><strong>حالة الدفع:</strong> <span class="badge badge-{status}">{status_label}</span>
               | <strong>طريقة الدفع:</strong> {method_label}</p>
        </div>

        <h2>بنود الفاتورة</h2>
        <table>
            <tr><th>المنتج</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr>
            {items_html}
        </table>

        <h2>ملخص الدفع</h2>
        <table>
            <tr><th>البيان</th><th>المبلغ</th></tr>
            <tr><td>الإجمالي</td><td class="gold">{total:,.2f}</td></tr>
            <tr><td>المدفوع</td><td class="green">{paid:,.2f}</td></tr>
            <tr class="{'success-row' if remaining < 0.01 else 'warning-row'}">
                <td>المتبقي</td>
                <td>{remaining:,.2f}</td>
            </tr>
        </table>

        {payments_html}
        """

        title = f"فاتورة {'مبيعات' if inv_dict['type']=='sale' else 'مشتريات'} #{inv_dict['id']}"
        html = html_template(title, body)
        return _save_and_return(html, f"invoice_{invoice_id}")
    finally:
        conn.close()


# ===================== تقارير جديدة: أعمار الذمم =====================

def generate_aging_report(party_type='customer'):
    """
    تقرير أعمار الذمم — يقسم المتبقي على الفواتير حسب العمر.
    
    Args:
        party_type: 'customer' (ذمم مدينة) أو 'supplier' (ذمم دائنة)
    """
    conn = get_conn()
    try:
        if party_type == 'customer':
            type_filter = 'sale'
            id_col = 'customer_id'
            parties_table = 'customers'
            title = "تقرير أعمار الذمم المدينة (العملاء)"
            party_label = "العميل"
        else:
            type_filter = 'purchase'
            id_col = 'supplier_id'
            parties_table = 'suppliers'
            title = "تقرير أعمار الذمم الدائنة (الموردون)"
            party_label = "المورد"

        today = date.today()

        rows = conn.execute(f"""
            SELECT 
                p.id AS party_id, p.name AS party_name,
                i.id AS invoice_id, i.invoice_date, i.total,
                COALESCE(i.remaining_amount, i.total) AS remaining
            FROM invoices i
            JOIN {parties_table} p ON i.{id_col} = p.id
            WHERE i.type = ? AND i.status = 'completed'
              AND COALESCE(i.remaining_amount, i.total) > 0.01
            ORDER BY p.name, i.invoice_date
        """, (type_filter,)).fetchall()

        if not rows:
            return None

        # تجميع بحسب الطرف + فئة العمر
        from collections import defaultdict
        aging = defaultdict(lambda: {
            "name": "",
            "current": 0.0,   # 0-30
            "d30": 0.0,       # 31-60
            "d60": 0.0,       # 61-90
            "d90": 0.0,       # 90+
            "total": 0.0
        })

        for r in rows:
            days_old = (today - datetime.strptime(r["invoice_date"], "%Y-%m-%d").date()).days
            amt = float(r["remaining"])
            entry = aging[r["party_id"]]
            entry["name"] = r["party_name"]
            if days_old <= 30:
                entry["current"] += amt
            elif days_old <= 60:
                entry["d30"] += amt
            elif days_old <= 90:
                entry["d60"] += amt
            else:
                entry["d90"] += amt
            entry["total"] += amt

        # بناء الجدول
        rows_html = ""
        grand = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "total": 0.0}
        for pid, e in sorted(aging.items(), key=lambda x: -x[1]["total"]):
            rows_html += (
                f"<tr><td>{e['name']}</td>"
                f"<td class='green'>{e['current']:,.2f}</td>"
                f"<td class='orange'>{e['d30']:,.2f}</td>"
                f"<td style='color:#F97316;'>{e['d60']:,.2f}</td>"
                f"<td class='red'>{e['d90']:,.2f}</td>"
                f"<td class='gold'><strong>{e['total']:,.2f}</strong></td></tr>"
            )
            for k in grand:
                grand[k] += e[k]

        rows_html += (
            f"<tr class='total-row'><td>الإجمالي</td>"
            f"<td>{grand['current']:,.2f}</td>"
            f"<td>{grand['d30']:,.2f}</td>"
            f"<td>{grand['d60']:,.2f}</td>"
            f"<td>{grand['d90']:,.2f}</td>"
            f"<td>{grand['total']:,.2f}</td></tr>"
        )

        body = f"""
        <table>
            <tr>
                <th>{party_label}</th>
                <th>0-30 يوم</th>
                <th>31-60 يوم</th>
                <th>61-90 يوم</th>
                <th>أكثر من 90</th>
                <th>الإجمالي</th>
            </tr>
            {rows_html}
        </table>
        <div class="info-block">
            <p><strong>ملاحظة:</strong> الأعمار محسوبة من تاريخ الفاتورة حتى اليوم ({today.strftime('%Y-%m-%d')}).</p>
        </div>"""

        html = html_template(title, body)
        return _save_and_return(html, f"aging_{party_type}")
    finally:
        conn.close()


def generate_party_statement(party_type, party_id, from_date=None, to_date=None):
    """
    كشف حساب عميل أو مورد لفترة محددة.
    
    يعرض:
        - الفواتير
        - السندات
        - الرصيد الجاري
    """
    conn = get_conn()
    try:
        if party_type == 'customer':
            party_row = conn.execute("SELECT name FROM customers WHERE id=?",
                                     (party_id,)).fetchone()
            type_filter = 'sale'
            id_col = 'customer_id'
            vouchers_type = 'receipt'
            vouchers_party = 'customer'
            title = f"كشف حساب العميل"
        else:
            party_row = conn.execute("SELECT name FROM suppliers WHERE id=?",
                                     (party_id,)).fetchone()
            type_filter = 'purchase'
            id_col = 'supplier_id'
            vouchers_type = 'payment'
            vouchers_party = 'supplier'
            title = f"كشف حساب المورد"

        if not party_row:
            return None

        party_name = party_row["name"]

        if not from_date:
            from_date = "1900-01-01"
        if not to_date:
            to_date = date.today().strftime("%Y-%m-%d")

        # الفواتير
        invoices = conn.execute(f"""
            SELECT id, invoice_date AS d, total, 'invoice' AS kind,
                   'فاتورة #' || id AS description
            FROM invoices
            WHERE type = ? AND {id_col} = ? AND status = 'completed'
              AND invoice_date BETWEEN ? AND ?
        """, (type_filter, party_id, from_date, to_date)).fetchall()

        # السندات
        vouchers = conn.execute("""
            SELECT id, date AS d, amount AS total, 'voucher' AS kind,
                   CASE WHEN type='receipt' THEN 'سند قبض #' || id
                        ELSE 'سند صرف #' || id END AS description
            FROM vouchers
            WHERE party_type = ? AND party_id = ?
              AND date BETWEEN ? AND ?
        """, (vouchers_party, party_id, from_date, to_date)).fetchall()

        # دمج وترتيب
        movements = []
        for inv in invoices:
            movements.append({"date": inv["d"], "desc": inv["description"],
                              "debit": float(inv["total"]), "credit": 0.0})
        for v in vouchers:
            movements.append({"date": v["d"], "desc": v["description"],
                              "debit": 0.0, "credit": float(v["total"])})

        movements.sort(key=lambda x: (x["date"], x["desc"]))

        # بناء الجدول
        running = 0.0
        total_d = 0.0
        total_c = 0.0
        rows_html = ""
        for m in movements:
            running += m["debit"] - m["credit"]
            total_d += m["debit"]
            total_c += m["credit"]
            rows_html += (
                f"<tr><td>{m['date']}</td><td style='text-align:right;'>{m['desc']}</td>"
                f"<td>{m['debit']:,.2f}</td>"
                f"<td>{m['credit']:,.2f}</td>"
                f"<td class='gold'>{running:,.2f}</td></tr>"
            )

        rows_html += (
            f"<tr class='total-row'><td colspan='2'>الإجمالي</td>"
            f"<td>{total_d:,.2f}</td>"
            f"<td>{total_c:,.2f}</td>"
            f"<td>{running:,.2f}</td></tr>"
        )

        body = f"""
        <div class="info-block">
            <p><strong>الطرف:</strong> {party_name}</p>
            <p><strong>الفترة:</strong> من {from_date} إلى {to_date}</p>
            <p><strong>الرصيد النهائي:</strong> <span class="gold">{running:,.2f} ر.ي</span></p>
        </div>
        <table>
            <tr><th>التاريخ</th><th>البيان</th><th>مدين</th><th>دائن</th><th>الرصيد</th></tr>
            {rows_html}
        </table>"""

        html = html_template(f"{title} — {party_name}", body)
        return _save_and_return(html, f"statement_{party_type}_{party_id}")
    finally:
        conn.close()


def generate_unpaid_invoices_report(party_type='all'):
    """
    تقرير الفواتير غير المدفوعة أو المدفوعة جزئياً.
    
    Args:
        party_type: 'customer' | 'supplier' | 'all'
    """
    conn = get_conn()
    try:
        if party_type == 'customer':
            where = "AND i.type = 'sale'"
        elif party_type == 'supplier':
            where = "AND i.type = 'purchase'"
        else:
            where = ""

        rows = conn.execute(f"""
            SELECT i.id, i.type, i.invoice_date, i.total,
                   COALESCE(i.paid_amount, 0) AS paid,
                   COALESCE(i.remaining_amount, i.total) AS remaining,
                   COALESCE(i.payment_status, 'unpaid') AS status,
                   CASE WHEN i.type='sale' THEN c.name ELSE s.name END AS party_name,
                   CASE WHEN i.type='sale' THEN 'مبيعات' ELSE 'مشتريات' END AS kind
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            LEFT JOIN suppliers s ON i.supplier_id = s.id
            WHERE i.status = 'completed'
              AND COALESCE(i.remaining_amount, i.total) > 0.01
              {where}
            ORDER BY i.invoice_date DESC, i.id DESC
        """).fetchall()

        if not rows:
            return None

        status_labels = {
            "unpaid": "🔴 غير مدفوعة",
            "partial": "🟡 مدفوعة جزئياً"
        }

        rows_html = ""
        total_remaining = 0.0
        for r in rows:
            total_remaining += float(r["remaining"])
            st_label = status_labels.get(r["status"], r["status"])
            rows_html += (
                f"<tr>"
                f"<td>#{r['id']}</td>"
                f"<td>{r['kind']}</td>"
                f"<td>{r['invoice_date']}</td>"
                f"<td>{r['party_name'] or '—'}</td>"
                f"<td>{float(r['total']):,.2f}</td>"
                f"<td class='green'>{float(r['paid']):,.2f}</td>"
                f"<td class='red'>{float(r['remaining']):,.2f}</td>"
                f"<td>{st_label}</td>"
                f"</tr>"
            )

        rows_html += (
            f"<tr class='total-row'><td colspan='6'>إجمالي المتبقي</td>"
            f"<td colspan='2'>{total_remaining:,.2f}</td></tr>"
        )

        body = f"""
        <table>
            <tr>
                <th>رقم الفاتورة</th>
                <th>النوع</th>
                <th>التاريخ</th>
                <th>الطرف</th>
                <th>الإجمالي</th>
                <th>المدفوع</th>
                <th>المتبقي</th>
                <th>الحالة</th>
            </tr>
            {rows_html}
        </table>"""

        html = html_template("الفواتير غير المدفوعة", body)
        return _save_and_return(html, "unpaid_invoices")
    finally:
        conn.close()


# ===================== تقارير الصندوق والضريبة (بدون تغيير) =====================

def generate_cash_report(cash_account_id=None):
    """تقرير الصندوق"""
    from services.cash_service import get_cash_balance_summary
    conn = get_conn()
    try:
        summary, total = get_cash_balance_summary()
        if not summary:
            return None
        body = "<h2>ملخص الصناديق</h2><table><tr><th>الصندوق</th><th>العملة</th><th>الرصيد</th></tr>"
        for s in summary:
            body += f"<tr><td>{s['name']}</td><td>{s['currency']}</td><td>{s['balance']:,.2f}</td></tr>"
        body += (
            f"<tr class='total-row'><td colspan='2'>الإجمالي (بالعملة الأساسية)</td>"
            f"<td>{total:,.2f}</td></tr></table>"
        )
        html = html_template("تقرير الصندوق", body)
        return _save_and_return(html, "cash")
    finally:
        conn.close()


def generate_vat_report():
    """تقرير ضريبة القيمة المضافة"""
    conn = get_conn()
    try:
        rate = conn.execute(
            "SELECT rate FROM vat_config WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        vat_rate = rate[0] if rate else 0.15
        sales_vat = conn.execute(
            "SELECT COALESCE(SUM(vat_amount),0) FROM invoices "
            "WHERE type='sale' AND status='completed'"
        ).fetchone()[0]
        purchase_vat = conn.execute(
            "SELECT COALESCE(SUM(vat_amount),0) FROM invoices "
            "WHERE type='purchase' AND status='completed'"
        ).fetchone()[0]
        net_vat = sales_vat - purchase_vat

        body = f"""
        <table>
            <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
            <tr><td>ضريبة المبيعات المستحقة</td><td class="green">{sales_vat:,.2f}</td></tr>
            <tr><td>ضريبة المشتريات القابلة للخصم</td><td class="blue">{purchase_vat:,.2f}</td></tr>
            <tr class="total-row">
                <td>صافي الضريبة {'المستحقة' if net_vat >= 0 else 'القابلة للاسترداد'}</td>
                <td class="{'red' if net_vat >= 0 else 'green'}">{abs(net_vat):,.2f}</td>
            </tr>
        </table>
        <p style="text-align:center;">معدل الضريبة: {vat_rate*100:.0f}%</p>"""

        html = html_template("تقرير ضريبة القيمة المضافة", body)
        return _save_and_return(html, "vat")
    finally:
        conn.close()


# ===================== XBRL (معدّل) =====================

def generate_xbrl_income():
    """توليد XBRL لقائمة الدخل — يعتمد على account_type"""
    conn = get_conn()
    try:
        rev_d, rev_c = _sum_by_account_type(conn, "Revenue")
        revenue = rev_c - rev_d
        exp_d, exp_c = _sum_by_account_type(conn, "Expense")
        expenses = exp_d - exp_c
        net = revenue - expenses

        now = datetime.now()
        xbrl = ET.Element('xbrl', {'xmlns': 'http://www.xbrl.org/2003/instance'})
        ET.SubElement(xbrl, 'schemaRef')
        ctx = ET.SubElement(xbrl, 'context', {'id': 'current'})
        entity = ET.SubElement(ctx, 'entity')
        ET.SubElement(entity, 'identifier',
                      {'scheme': 'http://hokoma-erp.com'}).text = 'حوكمة ERP'
        period = ET.SubElement(ctx, 'period')
        ET.SubElement(period, 'startDate').text = f'{now.year}-01-01'
        ET.SubElement(period, 'endDate').text = now.strftime('%Y-%m-%d')

        unit = ET.SubElement(xbrl, 'unit', {'id': 'YER'})
        ET.SubElement(unit, 'measure').text = 'iso4217:YER'

        rev = ET.SubElement(xbrl, 'Revenue',
                            {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
        rev.text = str(revenue)
        exp = ET.SubElement(xbrl, 'Expenses',
                            {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
        exp.text = str(expenses)
        ni = ET.SubElement(xbrl, 'NetIncome',
                           {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
        ni.text = str(net)

        tree = ET.ElementTree(xbrl)
        ET.indent(tree, space='  ')
        ensure_output_dir()
        path = os.path.join(OUTPUT_DIR,
                            f"xbrl_income_{now.strftime('%Y%m%d_%H%M%S')}.xml")
        tree.write(path, encoding='utf-8', xml_declaration=True)
        return path
    finally:
        conn.close()


def generate_xbrl_balance():
    """توليد XBRL للميزانية — يعتمد على account_type"""
    conn = get_conn()
    try:
        a_d, a_c = _sum_by_account_type(conn, "Asset")
        assets = a_d - a_c
        l_d, l_c = _sum_by_account_type(conn, "Liability")
        liabilities = l_c - l_d
        e_d, e_c = _sum_by_account_type(conn, "Equity")
        equity = e_c - e_d

        now = datetime.now()
        xbrl = ET.Element('xbrl', {'xmlns': 'http://www.xbrl.org/2003/instance'})
        ET.SubElement(xbrl, 'schemaRef')
        ctx = ET.SubElement(xbrl, 'context', {'id': 'current'})
        entity = ET.SubElement(ctx, 'entity')
        ET.SubElement(entity, 'identifier',
                      {'scheme': 'http://hokoma-erp.com'}).text = 'حوكمة ERP'
        period = ET.SubElement(ctx, 'period')
        ET.SubElement(period, 'instant').text = now.strftime('%Y-%m-%d')

        unit = ET.SubElement(xbrl, 'unit', {'id': 'YER'})
        ET.SubElement(unit, 'measure').text = 'iso4217:YER'

        a = ET.SubElement(xbrl, 'Assets',
                          {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
        a.text = str(assets)
        l = ET.SubElement(xbrl, 'Liabilities',
                          {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
        l.text = str(liabilities)
        e = ET.SubElement(xbrl, 'Equity',
                          {'contextRef': 'current', 'unitRef': 'YER', 'decimals': '2'})
        e.text = str(equity)

        tree = ET.ElementTree(xbrl)
        ET.indent(tree, space='  ')
        ensure_output_dir()
        path = os.path.join(OUTPUT_DIR,
                            f"xbrl_balance_{now.strftime('%Y%m%d_%H%M%S')}.xml")
        tree.write(path, encoding='utf-8', xml_declaration=True)
        return path
    finally:
        conn.close()
