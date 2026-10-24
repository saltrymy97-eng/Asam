# ui_flet/pages/closing.py
import flet as ft
import pandas as pd
from datetime import date
from services.closing_service import (
    create_closing_entry, create_cost_center_closing_entry, get_closing_summary,
)
from services import cost_center_service as ccs
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

def temp_data_table(df: pd.DataFrame) -> ft.Control:
    if df is None or df.empty:
        return ft.Text("لا توجد بيانات للعرض", color=TEXT_SECONDARY)
    columns = [ft.DataColumn(ft.Text(str(c), weight=ft.FontWeight.BOLD)) for c in df.columns]
    rows = [ft.DataRow(cells=[ft.DataCell(ft.Text(str(v))) for v in r]) for _, r in df.iterrows()]
    return ft.Row(
        controls=[ft.DataTable(
            columns=columns, rows=rows, border=ft.border.all(1, GLASS_BORDER),
            border_radius=10, vertical_lines=ft.border.BorderSide(1, GLASS_BORDER),
            horizontal_lines=ft.border.BorderSide(1, GLASS_BORDER),
            heading_row_color=ft.colors.with_opacity(0.15, ft.colors.WHITE),
        )], scroll=ft.ScrollMode.AUTO, expand=True
    )

class ClosingPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.confirm_close_year = False
        self.confirm_close_cc = False

        self.header = ft.Text("🧾 قيد إغلاق الحسابات", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إنشاء قيد تلقائي لإغلاق الإيرادات والمصروفات وترحيل صافي الدخل", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="🏢 إغلاق الشركة (عام)", content=self.build_company_closing_tab()),
                ft.Tab(text="🏷️ إغلاق مركز تكلفة", content=self.build_cc_closing_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. إغلاق الشركة
    # ============================================================
    def build_company_closing_tab(self):
        current_year = date.today().year
        self.year_input = ft.TextField(label="السنة المالية", value=str(current_year), keyboard_type=ft.KeyboardType.NUMBER, width=150)
        
        self.status_container = ft.Container()
        self.liquidity_container = ft.Container()
        self.action_container = ft.Container()
        
        self.load_company_summary()

        return ft.Column([
            ft.Row([self.year_input], alignment=ft.MainAxisAlignment.START),
            ft.Text("⚠️ الإغلاق نهائي — لا يمكن التراجع عنه تلقائياً.", color=ACCENT_RED, size=12),
            ft.Divider(color=GLASS_BORDER),
            self.status_container,
            ft.Text("💼 ملخص السيولة الحالي", color=ACCENT_BLUE, size=16, weight=ft.FontWeight.BOLD),
            self.liquidity_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Container(
                content=ft.Text(
                    "ما يفعله قيد الإغلاق:\n"
                    "• تصفير أرصدة حسابات الإيرادات (4xxx) في الأرباح المحتجزة.\n"
                    "• تصفير أرصدة حسابات المصروفات (5xxx) في الأرباح المحتجزة.\n"
                    "• ترحيل صافي الدخل (ربح/خسارة) إلى حساب الأرباح المحتجزة.\n"
                    "• لا يمسّ الصناديق أو البنوك أو الأصول.",
                    color=TEXT_SECONDARY, size=12
                ), bgcolor=GLASS_BG, padding=15, border_radius=10
            ),
            self.action_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_company_summary(self):
        try: year = int(self.year_input.value or 0)
        except ValueError: return

        summary = get_closing_summary(year)
        if summary.get("error"):
            self.status_container.content = ft.Text(f"❌ {summary['error']}", color=ACCENT_RED)
            self.liquidity_container.content = None
            self.action_container.content = None
            self.page.update()
            return

        # 1. حالة السنة
        closed = summary.get("closed", False)
        if closed:
            color = ACCENT_GREEN; icon = "✅"
            status = f"مُغلقة في {summary.get('closed_at', '—')} بواسطة {summary.get('closed_by', '—')}"
        else:
            color = ACCENT_ORANGE; icon = "⚠️"
            status = "غير مُغلقة بعد"
        
        self.status_container.content = ft.Container(
            content=ft.Text(f"حالة السنة المالية {year}: {icon} {status}", color=color, weight=ft.FontWeight.BOLD, size=14),
            bgcolor=ft.colors.with_opacity(0.1, color), padding=15, border_radius=10,
            border=ft.border.only(left=ft.border.BorderSide(5, color))
        )

        # 2. السيولة
        cash = summary.get("cash_total", 0.0)
        bank = summary.get("bank_total", 0.0)
        liquidity = summary.get("liquidity_total", 0.0)
        
        liq_content = [
            ft.Row([
                ft.Container(content=ft.Column([ft.Text(f"{cash:,.2f}", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD), ft.Text("إجمالي الصناديق", color=TEXT_SECONDARY, size=11)]), expand=True, bgcolor=GLASS_BG, padding=10, border_radius=10),
                ft.Container(content=ft.Column([ft.Text(f"{bank:,.2f}", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD), ft.Text("إجمالي البنوك", color=TEXT_SECONDARY, size=11)]), expand=True, bgcolor=GLASS_BG, padding=10, border_radius=10),
                ft.Container(content=ft.Column([ft.Text(f"{liquidity:,.2f}", color=ACCENT_PURPLE, size=18, weight=ft.FontWeight.BOLD), ft.Text("إجمالي السيولة", color=TEXT_SECONDARY, size=11)]), expand=True, bgcolor=GLASS_BG, padding=10, border_radius=10),
            ], spacing=10)
        ]
        
        cash_accounts = summary.get("cash_accounts", [])
        if cash_accounts:
            df = pd.DataFrame(cash_accounts)
            liq_content.append(ft.ExpansionTile(
                title=ft.Text(f"💵 تفاصيل الصناديق ({len(cash_accounts)})", color=TEXT_PRIMARY),
                controls=[temp_data_table(df)]
            ))
            
        bank_accounts = summary.get("bank_accounts", [])
        if bank_accounts:
            df = pd.DataFrame(bank_accounts)
            liq_content.append(ft.ExpansionTile(
                title=ft.Text(f"🏦 تفاصيل البنوك ({len(bank_accounts)})", color=TEXT_PRIMARY),
                controls=[temp_data_table(df)]
            ))

        self.liquidity_container.content = ft.Column(liq_content, spacing=10)

        # 3. زر الإغلاق
        if closed:
            self.action_container.content = ft.Text(f"⚠️ السنة {year} مُغلقة مسبقاً. لا يمكن إغلاقها مرة أخرى.", color=ACCENT_ORANGE)
        else:
            if not self.confirm_close_year:
                self.action_container.content = ft.ElevatedButton(
                    f"🚀 بدء إغلاق السنة {year}", bgcolor=ACCENT_BLUE, color=ft.colors.WHITE,
                    on_click=lambda e: self.start_close_year()
                )
            else:
                self.action_container.content = ft.Column([
                    ft.Text(f"⚠️ تأكيد نهائي: أنت على وشك إغلاق السنة {year} للشركة بالكامل. لا يمكن التراجع!", color=ACCENT_RED, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.ElevatedButton(f"✅ نعم، أغلق السنة {year}", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=lambda e: self.do_close_year()),
                        ft.ElevatedButton("❌ إلغاء", bgcolor=ACCENT_RED, color=ft.colors.WHITE, on_click=lambda e: self.cancel_close_year())
                    ], spacing=15)
                ])
        
        self.page.update()

    def start_close_year(self):
        self.confirm_close_year = True
        self.load_company_summary()

    def cancel_close_year(self):
        self.confirm_close_year = False
        self.load_company_summary()

    def do_close_year(self):
        try: year = int(self.year_input.value or 0)
        except ValueError: return
        self.confirm_close_year = False
        
        success, net_income, error = create_closing_entry(year, username="admin")
        if error:
            self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)
        elif success:
            self.show_snackbar(f"✅ تم إغلاق السنة {year} — صافي الدخل: {net_income:,.2f}", ACCENT_GREEN)
        self.load_company_summary()

    # ============================================================
    # 2. إغلاق مركز تكلفة
    # ============================================================
    def build_cc_closing_tab(self):
        centers = ccs.get_all_cost_centers()
        if not centers:
            return ft.Text("ℹ️ لا توجد مراكز تكلفة — أنشئ مركزاً أولاً من وحدة مراكز التكلفة.", color=TEXT_SECONDARY)

        self.center_dd = ft.Dropdown(
            label="اختر مركز التكلفة",
            options=[ft.dropdown.Option(key=str(c['id']), text=f"{c.get('code','')} - {c.get('name','')}") for c in centers],
            value=str(centers[0]['id']), expand=True
        )
        self.cc_year = ft.TextField(label="السنة المالية", value=str(date.today().year), keyboard_type=ft.KeyboardType.NUMBER, width=150)
        self.cc_action_container = ft.Container()
        
        self.load_cc_action()

        return ft.Column([
            ft.Text("🏷️ إغلاق مركز تكلفة محدد", color=ACCENT_PURPLE, size=18, weight=ft.FontWeight.BOLD),
            ft.Text("تصفير إيرادات ومصروفات مركز تكلفة معين في حساب الأرباح المحتجزة.", color=TEXT_SECONDARY, size=12),
            ft.Row([self.center_dd, self.cc_year]),
            ft.Divider(color=GLASS_BORDER),
            self.cc_action_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_cc_action(self):
        if not self.confirm_close_cc:
            self.cc_action_container.content = ft.ElevatedButton(
                "🚀 إغلاق مركز التكلفة", bgcolor=ACCENT_BLUE, color=ft.colors.WHITE,
                on_click=lambda e: self.start_close_cc()
            )
        else:
            self.cc_action_container.content = ft.Column([
                ft.Text("⚠️ تأكيد نهائي: إغلاق مركز التكلفة للسنة المحددة. لا يمكن التراجع!", color=ACCENT_RED, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.ElevatedButton("✅ نعم، أغلق المركز", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=lambda e: self.do_close_cc()),
                    ft.ElevatedButton("❌ إلغاء", bgcolor=ACCENT_RED, color=ft.colors.WHITE, on_click=lambda e: self.cancel_close_cc())
                ], spacing=15)
            ])
        self.page.update()

    def start_close_cc(self):
        self.confirm_close_cc = True
        self.load_cc_action()

    def cancel_close_cc(self):
        self.confirm_close_cc = False
        self.load_cc_action()

    def do_close_cc(self):
        try:
            center_id = int(self.center_dd.value)
            year = int(self.cc_year.value or 0)
        except ValueError: return
        self.confirm_close_cc = False
        
        success, net_income, error = create_cost_center_closing_entry(year, center_id, username="admin")
        if error:
            self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)
        elif success:
            self.show_snackbar(f"✅ تم إغلاق المركز للسنة {year} — صافي الدخل: {net_income:,.2f}", ACCENT_GREEN)
        self.load_cc_action()
