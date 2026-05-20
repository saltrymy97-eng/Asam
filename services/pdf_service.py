# services/pdf_service.py – خدمة تقارير PDF (fpdf2 + دعم عربي بسيط)
import sqlite3
import os
from datetime import datetime
from fpdf import FPDF

DB_PATH = "erp.db"
OUTPUT_DIR = "pdf_reports"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

class ArabicPDF(FPDF):
    def __init__(self):
        super().__init__()
        # الخط Arabic (يحتوي على الأحرف العربية الأساسية)
        self.add_font("Arabic", "", "DejaVuSansCondensed.ttf", uni=True)
        self.add_font("Arabic", "B", "DejaVuSansCondensed.ttf", uni=True)
        self.set_auto_page_break(True, 15)

    def header(self):
        self.set_font("Arabic", "B", 14)
        self.set_text_color(139, 92, 246)
        self.cell(0, 10, "XD ERP", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(139, 92, 246)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arabic", "", 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, f"تم الإنشاء بواسطة XD ERP – {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")

    def add_table(self, headers, data, col_widths=None):
        """إضافة جدول منسق"""
        self.set_font("Arabic", "B", 10)
        self.set_fill_color(139, 92, 246)
        self.set_text_color(255, 255, 255)
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, border=1, fill=True, align="C")
        self.ln()
        self.set_font("Arabic", "", 9)
        self.set_text_color(203, 213, 225)
        for row in data:
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 7, str(cell), border=1, align="C")
            self.ln()

def generate_income_statement():
    conn = get_conn()
    revenue = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(jl.debit)-SUM(jl.credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    conn.close()
    net = revenue - expenses
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font("Arabic", "B", 16)
    pdf.set_text_color(248, 250, 252)
    pdf.cell(0, 10, "قائمة الدخل", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    data = [
        ["الإيرادات", f"{revenue:,.2f}"],
        ["المصروفات", f"{expenses:,.2f}"],
        ["صافي الدخل", f"{net:,.2f}"],
    ]
    pdf.add_table(["البيان", "المبلغ (ريال)"], data, [95, 95])
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"income_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(path)
    return path

def generate_balance_sheet():
    conn = get_conn()
    assets = conn.execute("SELECT COALESCE(SUM(jl.debit)-SUM(jl.credit),0) FROM journal_lines WHERE account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines WHERE account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines WHERE account_name LIKE '3%'").fetchone()[0]
    conn.close()
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font("Arabic", "B", 16)
    pdf.set_text_color(248, 250, 252)
    pdf.cell(0, 10, "الميزانية العمومية", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    data = [
        ["الأصول", f"{assets:,.2f}"],
        ["الخصوم", f"{liabilities:,.2f}"],
        ["حقوق الملكية", f"{equity:,.2f}"],
    ]
    pdf.add_table(["البيان", "المبلغ (ريال)"], data, [95, 95])
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"balance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(path)
    return path

def generate_inventory_report():
    conn = get_conn()
    rows = conn.execute("SELECT name, quantity, reorder_level FROM products").fetchall()
    conn.close()
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font("Arabic", "B", 16)
    pdf.set_text_color(248, 250, 252)
    pdf.cell(0, 10, "تقرير المخزون", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    data = [[r['name'], str(r['quantity']), str(r['reorder_level'])] for r in rows]
    pdf.add_table(["المنتج", "الكمية", "حد إعادة الطلب"], data, [70, 60, 60])
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(path)
    return path

def generate_audit_report():
    conn = get_conn()
    rows = conn.execute("SELECT username, action, table_name, timestamp FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font("Arabic", "B", 16)
    pdf.set_text_color(248, 250, 252)
    pdf.cell(0, 10, "سجل التدقيق", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    data = [[r['username'], r['action'], r['table_name'], r['timestamp']] for r in rows]
    pdf.add_table(["المستخدم", "الإجراء", "الجدول", "التوقيت"], data, [35, 45, 40, 70])
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(path)
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
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font("Arabic", "B", 16)
    pdf.set_text_color(248, 250, 252)
    pdf.cell(0, 10, f"فاتورة #{inv['id']}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arabic", "", 10)
    pdf.cell(0, 8, f"التاريخ: {inv['invoice_date']} | الإجمالي: {inv['total']:,.2f} ريال", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    data = [[it['name'], str(it['quantity']), f"{it['unit_price']:,.2f}", f"{it['total']:,.2f}"] for it in items]
    pdf.add_table(["المنتج", "الكمية", "سعر الوحدة", "الإجمالي"], data, [50, 40, 50, 50])
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, f"invoice_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(path)
    return path
