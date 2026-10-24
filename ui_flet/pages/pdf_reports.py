# ui_flet/pages/pdf_reports.py
import flet as ft
import os
from datetime import date, timedelta
from services.pdf_service import (
    generate_income_statement, generate_balance_sheet, generate_inventory_report,
    generate_audit_report, generate_invoice_html, generate_cash_report,
    generate_vat_report, generate_xbrl_income, generate_xbrl_balance,
    generate_aging_report, generate_party_statement,
    generate_unpaid_invoices_report, OUTPUT_DIR, ensure_output_dir,
)
from services.sales_service import get_all_customers
from services.purchases_service import get_all_suppliers
from services import cost_center_service as ccs
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

GOLD = "#D4AF37"

class PdfReportsPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        try: ensure_output_dir()
        except: pass

        self.header = ft.Text("📄 التقارير المالية", size=30, color=GOLD, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("تقارير HTML و XBRL احترافية مع فلترة كاملة", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📊 تقارير مالية", content=self.build_financial_tab()),
                ft.Tab(text="💰 الذمم والعملاء", content=self.build_receivables_tab()),
                ft.Tab(text="🏢 تقارير إدارية", content=self.build_admin_tab()),
                ft.Tab(text="🌐 تقارير XBRL", content=self.build_xbrl_tab()),
                ft.Tab(text="📋 التقارير السابقة", content=self.build_history_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def _render_download(self, path, key_suffix=""):
        """عرض رسالة نجاح مع مسار الملف"""
        if not path:
            self.show_snackbar("⚠️ لا توجد بيانات كافية لإنشاء هذا التقرير", ACCENT_ORANGE); return
        filename = os.path.basename(path)
        self.show_snackbar(f"✅ تم إنشاء التقرير: {filename} في مجلد OUTPUT_DIR", ACCENT_GREEN)

    def _render_filters(self, key_prefix=""):
        """عرض فلاتر السنة + الشهر + مركز التكلفة"""
        current_year = date.today().year
        years = list(range(current_year - 5, current_year + 3))
        
        year_dd = ft.Dropdown(label="📅 السنة", options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(str(y)) for y in years], value=str(current_year), expand=True)
        month_dd = ft.Dropdown(label="📅 الشهر", options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(f"{i:02d}") for i in range(1, 13)], value="الكل", expand=True)
        
        centers = ccs.get_all_cost_centers(active_only=True)
        center_options = [ft.dropdown.Option("0", text="كل الشركة (بدون تصفية)")] + [ft.dropdown.Option(str(c['id']), text=f"{c['code']} - {c['name']}") for c in centers]
        center_dd = ft.Dropdown(label="🏢 مركز التكلفة", options=center_options, value="0", expand=True)

        def get_filters():
            year = None if year_dd.value == "الكل" else int(year_dd.value)
            month = None if month_dd.value == "الكل" or year is None else int(month_dd.value)
            cid = None if center_dd.value == "0" else int(center_dd.value)
            return {"year": year, "month": month, "cost_center_id": cid}

        return year_dd, month_dd, center_dd, get_filters

    # ============================================================
    # 1. تقارير مالية
    # ============================================================
    def build_financial_tab(self):
        self.fin_report_type = ft.Dropdown(
            label="اختر التقرير",
            options=[ft.dropdown.Option("income"), ft.dropdown.Option("balance"), ft.dropdown.Option("vat")],
            value="income", expand=True,
            on_change=lambda e: self.toggle_fin_filters()
        )
        
        self.fin_filters_container = ft.Column()
        self.fin_year, self.fin_month, self.fin_center, self.get_fin_filters = self._render_filters("fin")
        self.fin_filters_container.controls = [
            ft.Text("🎯 فلترة التقرير", color=ACCENT_BLUE, weight=ft.FontWeight.BOLD),
            ft.Row([self.fin_year, self.fin_month]),
            self.fin_center
        ]
        self.toggle_fin_filters()

        def gen_fin(e):
            filters = self.get_fin_filters()
            path = None
            if self.fin_report_type.value == "income":
                path = generate_income_statement(year=filters["year"], month=filters["month"], cost_center_id=filters["cost_center_id"])
            elif self.fin_report_type.value == "balance":
                path = generate_balance_sheet(year=filters["year"], month=filters["month"], cost_center_id=filters["cost_center_id"])
            elif self.fin_report_type.value == "vat":
                path = generate_vat_report()
            self._render_download(path, "fin")

        return ft.Column([
            ft.Text("التقارير المالية", color=GOLD, size=18, weight=ft.FontWeight.BOLD),
            self.fin_report_type,
            self.fin_filters_container,
            ft.ElevatedButton("🚀 توليد التقرير المالي", on_click=gen_fin, bgcolor=GOLD, color=ft.colors.BLACK)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def toggle_fin_filters(self):
        is_vat = self.fin_report_type.value == "vat"
        self.fin_filters_container.visible = not is_vat
        self.page.update()

    # ============================================================
    # 2. الذمم والعملاء
    # ============================================================
    def build_receivables_tab(self):
        # 2.1 أعمار الذمم
        self.aging_party = ft.RadioGroup(content=ft.Row([ft.Radio(value="customer", label="العملاء"), ft.Radio(value="supplier", label="الموردون")]), value="customer")
        def gen_aging(e):
            path = generate_aging_report(self.aging_party.value)
            self._render_download(path, "aging")
            
        # 2.2 كشف حساب
        self.stmt_party_type = ft.RadioGroup(content=ft.Row([ft.Radio(value="customer", label="عميل"), ft.Radio(value="supplier", label="مورد")]), value="customer", on_change=lambda e: self.load_stmt_parties())
        self.stmt_party_dd = ft.Dropdown(label="اختر الطرف", expand=True)
        self.stmt_from = ft.TextField(label="من تاريخ", value=(date.today() - timedelta(days=90)).strftime("%Y-%m-%d"), expand=True)
        self.stmt_to = ft.TextField(label="إلى تاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.load_stmt_parties()
        
        def gen_stmt(e):
            if not self.stmt_party_dd.value: return
            path = generate_party_statement(self.stmt_party_type.value, int(self.stmt_party_dd.value), self.stmt_from.value, self.stmt_to.value)
            self._render_download(path, "stmt")

        # 2.3 الفواتير غير المدفوعة
        self.unpaid_type = ft.RadioGroup(content=ft.Row([ft.Radio(value="all", label="الكل"), ft.Radio(value="customer", label="مبيعات"), ft.Radio(value="supplier", label="مشتريات")]), value="all")
        def gen_unpaid(e):
            path = generate_unpaid_invoices_report(self.unpaid_type.value)
            self._render_download(path, "unpaid")

        return ft.Column([
            ft.Text("📅 أعمار الذمم", color=GOLD, size=16, weight=ft.FontWeight.BOLD),
            self.aging_party, ft.ElevatedButton("🚀 توليد", on_click=gen_aging, bgcolor=GOLD, color=ft.colors.BLACK),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📑 كشف حساب", color=ACCENT_BLUE, size=16, weight=ft.FontWeight.BOLD),
            self.stmt_party_type, self.stmt_party_dd, ft.Row([self.stmt_from, self.stmt_to]),
            ft.ElevatedButton("🚀 توليد كشف الحساب", on_click=gen_stmt, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("🧾 الفواتير غير المدفوعة", color=ACCENT_ORANGE, size=16, weight=ft.FontWeight.BOLD),
            self.unpaid_type, ft.ElevatedButton("🚀 توليد", on_click=gen_unpaid, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_stmt_parties(self):
        parties = get_all_customers() if self.stmt_party_type.value == "customer" else get_all_suppliers()
        self.stmt_party_dd.options = [ft.dropdown.Option(key=str(p['id']), text=p['name']) for p in parties]
        if parties: self.stmt_party_dd.value = str(parties[0]['id'])
        self.page.update()

    # ============================================================
    # 3. تقارير إدارية
    # ============================================================
    def build_admin_tab(self):
        self.admin_report_type = ft.Dropdown(
            label="اختر التقرير",
            options=[ft.dropdown.Option("inventory"), ft.dropdown.Option("audit"), ft.dropdown.Option("cash"), ft.dropdown.Option("invoice")],
            value="inventory", expand=True,
            on_change=lambda e: self.toggle_invoice_input()
        )
        self.invoice_id_input = ft.TextField(label="رقم الفاتورة", value="1", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        self.toggle_invoice_input()

        def gen_admin(e):
            path = None
            if self.admin_report_type.value == "inventory": path = generate_inventory_report()
            elif self.admin_report_type.value == "audit": path = generate_audit_report()
            elif self.admin_report_type.value == "cash": path = generate_cash_report()
            elif self.admin_report_type.value == "invoice":
                try: iid = int(self.invoice_id_input.value or 0)
                except ValueError: iid = 0
                if iid > 0: path = generate_invoice_html(iid)
            self._render_download(path, "admin")

        return ft.Column([
            ft.Text("التقارير الإدارية والرقابية", color=GOLD, size=18, weight=ft.FontWeight.BOLD),
            self.admin_report_type, self.invoice_id_input,
            ft.ElevatedButton("🚀 توليد التقرير الإداري", on_click=gen_admin, bgcolor=GOLD, color=ft.colors.BLACK)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def toggle_invoice_input(self):
        self.invoice_id_input.visible = self.admin_report_type.value == "invoice"
        self.page.update()

    # ============================================================
    # 4. تقارير XBRL
    # ============================================================
    def build_xbrl_tab(self):
        self.xbrl_year, self.xbrl_month, self.xbrl_center, self.get_xbrl_filters = self._render_filters("xbrl")
        
        def gen_xbrl_income(e):
            filters = self.get_xbrl_filters()
            path = generate_xbrl_income(year=filters["year"], month=filters["month"], cost_center_id=filters["cost_center_id"])
            self._render_download(path, "xbrl_i")

        def gen_xbrl_balance(e):
            filters = self.get_xbrl_filters()
            path = generate_xbrl_balance(year=filters["year"], month=filters["month"], cost_center_id=filters["cost_center_id"])
            self._render_download(path, "xbrl_b")

        return ft.Column([
            ft.Text("🌐 تقارير XBRL (لغة تقارير الأعمال الموسعة)", color=GOLD, size=18, weight=ft.FontWeight.BOLD),
            ft.Text("تقارير XML قابلة للقراءة آلياً من قبل الجهات الرقابية والبنوك.", color=TEXT_SECONDARY, size=12),
            ft.Row([self.xbrl_year, self.xbrl_month]), self.xbrl_center,
            ft.Row([
                ft.ElevatedButton("📊 XBRL قائمة الدخل", on_click=gen_xbrl_income, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, expand=True),
                ft.ElevatedButton("⚖️ XBRL الميزانية", on_click=gen_xbrl_balance, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE, expand=True),
            ], spacing=15)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 5. التقارير السابقة
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.load_history()
        return ft.Column([
            ft.Text("📋 التقارير السابقة", color=GOLD, size=18, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        if os.path.exists(OUTPUT_DIR):
            all_files = sorted(os.listdir(OUTPUT_DIR), reverse=True)
            files = [f for f in all_files if f.endswith(('.html', '.xml'))]
            if files:
                rows = []
                for file in files[:10]:
                    path = os.path.join(OUTPUT_DIR, file)
                    size_kb = os.path.getsize(path) / 1024
                    icon = "🌐" if file.endswith('.xml') else "📄"
                    rows.append(ft.Row([
                        ft.Text(f"{icon} {file}", color=TEXT_PRIMARY, expand=True),
                        ft.Text(f"{size_kb:.1f} KB", color=TEXT_SECONDARY, size=12),
                        ft.IconButton(icon=ft.icons.FOLDER_OPEN, tooltip="فتح المجلد", on_click=lambda e, p=path: self.open_file(p))
                    ]))
                self.history_container.content = ft.Column(rows, spacing=5)
            else:
                self.history_container.content = ft.Text("لا توجد تقارير سابقة", color=TEXT_SECONDARY)
        else:
            self.history_container.content = ft.Text("لا توجد تقارير سابقة", color=TEXT_SECONDARY)
        self.page.update()

    def open_file(self, path):
        try:
            os.startfile(path)  # يعمل على Windows
        except Exception as ex:
            self.show_snackbar(f"لا يمكن فتح الملف: {ex}", ACCENT_RED)
