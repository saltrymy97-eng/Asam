# services/pdf_service.py – خدمة تقارير احترافية (v4.0)
# ✅ توحيد: يستخدم financial_service كمرجع واحد
# ✅ إضافة: فلترة السنة + الشهر + مركز التكلفة
# ✅ Registry + مسار مطلق
import sqlite3
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, calendar

# ============================================================
# المسار المطلق
# ============================================================
if getattr(sys, 'frozen', False):
    _APP_BASE = os.path.dirname(sys.executable)
else:
    _APP_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(_APP_BASE, "data", "erp.db")
OUTPUT_DIR = os.path.join(_APP_BASE, "reports")


def get_conn():
    """اتصال — يستخدم Registry"""
    try:
        from database import get_connection, close_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _close(conn):
    """إغلاق آمن"""
    try:
        from database import close_connection
        close_connection(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


# ============================================================
# ✅ بناء الفترة — يستخدم نفس منطق financial_service
# ============================================================
def _build_period(year=None, month=None, from_date=None, to_date=None):
    """
    بناء from_date و to_date.
    الأولوية: from_date/to_date → year+month → year → None
    """
    if from_date and to_date:
        return str(from_date)[:10], str(to_date)[:10]

    if year:
        try:
            y = int(year)
        except (TypeError, ValueError):
            return None, None

        if month:
            try:
                m = int(month)
                last_day = calendar.monthrange(y, m)[1]
                return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last_day:02d}"
            except (TypeError, ValueError):
                pass

        return f"{y}-01-01", f"{y}-12-31"

    return None, None


# ============================================================
# قالب HTML
# ============================================================
def html_template(title, body, logo_text="حوكمة ERP",
                  subtitle="إدارة ذكية .. قرارات واثقة"):
    """قالب HTML احترافي"""
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
    .success-row {{ font-weight: 700; background: rgba(16,185,129,0.15) !important; }}
    .warning-row {{ font-weight: 700; background: rgba(245,158,11,0.15) !important; }}
    .danger-row {{ font-weight: 700; background: rgba(239,68,68,0.15) !important; }}
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
    .filter-badge {{
        display: inline-block; padding: 6px 14px; margin: 4px;
        background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3);
        border-radius: 8px; color: #93C5FD; font-size: 0.85rem;
    }}
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


# ============================================================
# ✅ مساعدات
# ============================================================
def _save_and_return(html, filename_prefix):
    ensure_output_dir()
    path = os.path.join(
        OUTPUT_DIR,
        f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def _filter_badge(year=None, month=None, cost_center_id=None,
                  from_date=None, to_date=None, conn=None):
    """شريط الفلاتر"""
    badges = []

    if from_date and to_date:
        badges.append(f"📅 الفترة: {from_date} → {to_date}")
    elif year:
        if month:
            badges.append(f"📅 {year}/{int(month):02d}")
        else:
            badges.append(f"📅 السنة: {year}")

    if cost_center_id and conn:
        try:
            row = conn.execute(
                "SELECT code, name FROM cost_centers WHERE id = ?",
                (cost_center_id,)
            ).fetchone()
            if row:
                badges.append(f"🏢 مركز: {row['code']} - {row['name']}")
        except Exception:
            pass

    if not badges:
        badges.append("📅 كل الفترات")

    return "<div style='text-align:center;'>" + "".join(
        f"<span class='filter-badge'>{b}</span>" for b in badges
    ) + "</div>"


# ============================================================
# ✅ قائمة الدخل — تستخدم financial_service
# ============================================================
def generate_income_statement(year=None, month=None, cost_center_id=None,
                               from_date=None, to_date=None):
    """
    قائمة الدخل — توحيد مع financial_service.
    """
    from_date_c, to_date_c = _build_period(year, month, from_date, to_date)

    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0]
        if count == 0:
            return None

        # ✅ استخدام financial_service — مصدر واحد للحقيقة
        try:
            from services.financial_service import get_income_statement
            income_data = get_income_statement(
                cost_center_id=cost_center_id,
                year=year,
                month=month,
                conn=conn,
            )
            revenue = float(income_data.get('total_revenue', 0))
            expenses = float(income_data.get('total_expenses', 0))
            net = float(income_data.get('net_income', 0))
        except Exception as e:
            print(f"⚠️ فشل financial_service: {e}")
            # fallback — حساب بسيط
            revenue, expenses, net = 0.0, 0.0, 0.0

        body = _filter_badge(year, month, cost_center_id,
                              from_date_c, to_date_c, conn)
        body += f"""
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
        _close(conn)


# ============================================================
# ✅ الميزانية العمومية — تستخدم financial_service
# ============================================================
def generate_balance_sheet(year=None, month=None, cost_center_id=None,
                            from_date=None, to_date=None):
    """
    الميزانية العمومية — توحيد مع financial_service.
    """
    _, to_date_c = _build_period(year, month, from_date, to_date)

    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0]
        if count == 0:
            return None

        # ✅ استخدام financial_service
        try:
            from services.financial_service import get_balance_sheet
            bs = get_balance_sheet(
                cost_center_id=cost_center_id,
                year=year,
                month=month,
                conn=conn,
            )
            assets = float(bs.get('total_assets', 0))
            liabilities = float(bs.get('total_liabilities', 0))
            total_equity = float(bs.get('total_equity', 0))
            total_liab_eq = float(bs.get('total_liab_equity', 0))
        except Exception as e:
            print(f"⚠️ فشل financial_service: {e}")
            assets, liabilities, total_equity, total_liab_eq = 0.0, 0.0, 0.0, 0.0

        body = _filter_badge(year, month, cost_center_id,
                              None, to_date_c, conn)
        body += f"""
        <table>
            <tr><th>البيان</th><th>المبلغ (ر.ي)</th></tr>
            <tr><td class="blue">الأصول</td><td>{assets:,.2f}</td></tr>
            <tr><td class="orange">الخصوم</td><td>{liabilities:,.2f}</td></tr>
            <tr><td style="color:#8B5CF6;">حقوق الملكية</td><td>{total_equity:,.2f}</td></tr>
            <tr class="total-row">
                <td>إجمالي الخصوم + حقوق الملكية</td>
                <td>{total_liab_eq:,.2f}</td>
            </tr>
        </table>
        <div class="info-block">
            <p><strong>الفرق:</strong> <span class="{'green' if abs(assets - total_liab_eq) < 0.01 else 'red'}">{assets - total_liab_eq:,.2f}</span></p>
        </div>"""

        html = html_template("الميزانية العمومية", body)
        return _save_and_return(html, "balance")
    finally:
        _close(conn)


# ============================================================
# تقرير المخزون
# ============================================================
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
        _close(conn)


# ============================================================
# تقرير التدقيق
# ============================================================
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
        _close(conn)


# ============================================================
# فاتورة HTML
# ============================================================
def generate_invoice_html(invoice_id):
    """فاتورة HTML"""
    conn = get_conn()
    try:
        inv = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv:
            return None

        items = conn.execute("""
            SELECT p.name, ii.quantity, ii.unit_price,
                   (ii.quantity * ii.unit_price) AS total
            FROM invoice_items ii
            JOIN products p ON ii.product_id = p.id
            WHERE ii.invoice_id = ?
        """, (invoice_id,)).fetchall()

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

        payments = conn.execute("""
            SELECT ip.amount, ip.payment_date, ip.payment_method, ip.voucher_id
            FROM invoice_payments ip
            WHERE ip.invoice_id = ?
            ORDER BY ip.payment_date, ip.id
        """, (invoice_id,)).fetchall()

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
            "cash": "نقدي", "bank": "بنكي",
            "credit": "آجل", "mixed": "مختلط"
        }.get(method, method or "—")

        items_html = "".join(
            f"<tr><td>{it['name']}</td><td>{it['quantity']}</td>"
            f"<td>{it['unit_price']:,.2f}</td><td>{it['total']:,.2f}</td></tr>"
            for it in items
        )

        payments_html = ""
        if payments:
            payments_html = """
            <h2>الدفعات المرتبطة</h2>
            <table>
                <tr><th>التاريخ</th><th>المبلغ</th><th>طريقة الدفع</th><th>السند</th></tr>
            """
            for p in payments:
                pm_method = {"cash": "نقدي", "bank": "بنكي", "credit": "آجل"}.get(
                    p["payment_method"], p["payment_method"]
                )
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
        _close(conn)


# ============================================================
# تقرير أعمار الذمم
# ============================================================
def generate_aging_report(party_type='customer'):
    """تقرير أعمار الذمم"""
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

        from collections import defaultdict
        aging = defaultdict(lambda: {
            "name": "", "current": 0.0, "d30": 0.0,
            "d60": 0.0, "d90": 0.0, "total": 0.0
        })

        for r in rows:
            days_old = (today - datetime.strptime(
                r["invoice_date"], "%Y-%m-%d"
            ).date()).days
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
                <th>{party_label}</th><th>0-30 يوم</th><th>31-60 يوم</th>
                <th>61-90 يوم</th><th>أكثر من 90</th><th>الإجمالي</th>
            </tr>
            {rows_html}
        </table>
        <div class="info-block">
            <p><strong>ملاحظة:</strong> الأعمار محسوبة من تاريخ الفاتورة حتى اليوم ({today.strftime('%Y-%m-%d')}).</p>
        </div>"""

        html = html_template(title, body)
        return _save_and_return(html, f"aging_{party_type}")
    finally:
        _close(conn)


# ============================================================
# كشف حساب طرف
# ============================================================
def generate_party_statement(party_type, party_id, from_date=None, to_date=None):
    """كشف حساب عميل أو مورد"""
    conn = get_conn()
    try:
        if party_type == 'customer':
            party_row = conn.execute("SELECT name FROM customers WHERE id=?",
                                     (party_id,)).fetchone()
            type_filter = 'sale'
            id_col = 'customer_id'
            vouchers_party = 'customer'
            title = "كشف حساب العميل"
        else:
            party_row = conn.execute("SELECT name FROM suppliers WHERE id=?",
                                     (party_id,)).fetchone()
            type_filter = 'purchase'
            id_col = 'supplier_id'
            vouchers_party = 'supplier'
            title = "كشف حساب المورد"

        if not party_row:
            return None

        party_name = party_row["name"]

        if not from_date:
            from_date = "1900-01-01"
        if not to_date:
            to_date = date.today().strftime("%Y-%m-%d")

        invoices = conn.execute(f"""
            SELECT id, invoice_date AS d, total, 'invoice' AS kind,
                   'فاتورة #' || id AS description
            FROM invoices
            WHERE type = ? AND {id_col} = ? AND status = 'completed'
              AND invoice_date BETWEEN ? AND ?
        """, (type_filter, party_id, from_date, to_date)).fetchall()

        vouchers = conn.execute("""
            SELECT id, date AS d, amount AS total, 'voucher' AS kind,
                   CASE WHEN type='receipt' THEN 'سند قبض #' || id
                        ELSE 'سند صرف #' || id END AS description
            FROM vouchers
            WHERE party_type = ? AND party_id = ?
              AND date BETWEEN ? AND ?
        """, (vouchers_party, party_id, from_date, to_date)).fetchall()

        movements = []
        for inv in invoices:
            movements.append({"date": inv["d"], "desc": inv["description"],
                              "debit": float(inv["total"]), "credit": 0.0})
        for v in vouchers:
            movements.append({"date": v["d"], "desc": v["description"],
                              "debit": 0.0, "credit": float(v["total"])})

        movements.sort(key=lambda x: (x["date"], x["desc"]))

        running = 0.0
        total_d = 0.0
        total_c = 0.0
        rows_html = ""
        for m in movements:
            running += m["debit"] - m["credit"]
            total_d += m["debit"]
            total_c += m["credit"]
            rows_html += (
                f"<tr><td>{m['date']}</td>"
                f"<td style='text-align:right;'>{m['desc']}</td>"
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
        _close(conn)


# ============================================================
# الفواتير غير المدفوعة
# ============================================================
def generate_unpaid_invoices_report(party_type='all'):
    """تقرير الفواتير غير المدفوعة"""
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
                f"<td>#{r['id']}</td><td>{r['kind']}</td>"
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
                <th>رقم الفاتورة</th><th>النوع</th><th>التاريخ</th>
                <th>الطرف</th><th>الإجمالي</th><th>المدفوع</th>
                <th>المتبقي</th><th>الحالة</th>
            </tr>
            {rows_html}
        </table>"""

        html = html_template("الفواتير غير المدفوعة", body)
        return _save_and_return(html, "unpaid_invoices")
    finally:
        _close(conn)


# ============================================================
# تقرير الصندوق
# ============================================================
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
        _close(conn)


# ============================================================
# تقرير الضريبة
# ============================================================
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
        _close(conn)


# ============================================================
# XBRL — بالفلترة
# ============================================================
def generate_xbrl_income(year=None, month=None, cost_center_id=None,
                          from_date=None, to_date=None):
    """XBRL لقائمة الدخل — يستخدم financial_service"""
    from_date_c, to_date_c = _build_period(year, month, from_date, to_date)

    conn = get_conn()
    try:
        try:
            from services.financial_service import get_income_statement
            income_data = get_income_statement(
                cost_center_id=cost_center_id,
                year=year,
                month=month,
                conn=conn,
            )
            revenue = float(income_data.get('total_revenue', 0))
            expenses = float(income_data.get('total_expenses', 0))
            net = float(income_data.get('net_income', 0))
        except Exception:
            revenue, expenses, net = 0.0, 0.0, 0.0

        now = datetime.now()
        xbrl = ET.Element('xbrl', {'xmlns': 'http://www.xbrl.org/2003/instance'})
        ET.SubElement(xbrl, 'schemaRef')
        ctx = ET.SubElement(xbrl, 'context', {'id': 'current'})
        entity = ET.SubElement(ctx, 'entity')
        ET.SubElement(entity, 'identifier',
                      {'scheme': 'http://hokoma-erp.com'}).text = 'حوكمة ERP'
        period = ET.SubElement(ctx, 'period')
        ET.SubElement(period, 'startDate').text = from_date_c or f'{now.year}-01-01'
        ET.SubElement(period, 'endDate').text = to_date_c or now.strftime('%Y-%m-%d')

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
        _close(conn)


def generate_xbrl_balance(year=None, month=None, cost_center_id=None,
                           from_date=None, to_date=None):
    """XBRL للميزانية — يستخدم financial_service"""
    _, to_date_c = _build_period(year, month, from_date, to_date)

    conn = get_conn()
    try:
        try:
            from services.financial_service import get_balance_sheet
            bs = get_balance_sheet(
                cost_center_id=cost_center_id,
                year=year,
                month=month,
                conn=conn,
            )
            assets = float(bs.get('total_assets', 0))
            liabilities = float(bs.get('total_liabilities', 0))
            equity = float(bs.get('total_equity', 0))
        except Exception:
            assets, liabilities, equity = 0.0, 0.0, 0.0

        now = datetime.now()
        xbrl = ET.Element('xbrl', {'xmlns': 'http://www.xbrl.org/2003/instance'})
        ET.SubElement(xbrl, 'schemaRef')
        ctx = ET.SubElement(xbrl, 'context', {'id': 'current'})
        entity = ET.SubElement(ctx, 'entity')
        ET.SubElement(entity, 'identifier',
                      {'scheme': 'http://hokoma-erp.com'}).text = 'حوكمة ERP'
        period = ET.SubElement(ctx, 'period')
        ET.SubElement(period, 'instant').text = to_date_c or now.strftime('%Y-%m-%d')

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
        _close(conn)
