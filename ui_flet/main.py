# ui_flet/main.py
import flet as ft
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from ui_flet import shared
from ui_flet.shared import *
import database
from services.roles_service import get_allowed_modules, seed_default_roles


# ============================================================
# 🔧 الحيلة الذكية: احتواء temp_data_table عالمياً
# ============================================================
def patch_page_tables(page_module):
    """
    يستبدل temp_data_table المحلية في أي صفحة بنسخة shared العريضة.
    يُستدعى تلقائياً من load_page قبل استخدام الصفحة.
    """
    if hasattr(page_module, 'temp_data_table'):
        page_module.temp_data_table = shared.temp_data_table
    if hasattr(page_module, 'build_data_table'):
        page_module.build_data_table = shared.build_data_table


class MainApp(ft.Row):
    def __init__(self, page: ft.Page, user: dict):
        super().__init__()
        self.page = page
        self.user = user
        self.expand = True

        self.content_area = ft.Container(
            expand=True,
            padding=20,
            bgcolor=BG_MAIN,
        )

        self.sidebar = self.build_sidebar()
        self.controls = [self.sidebar, self.content_area]
        self.load_page("لوحة المعلومات")

    # ============================================================
    # بناء القائمة الجانبية
    # ============================================================
    def build_sidebar(self):
        username = self.user.get('username', '')
        allowed_modules = None if username == 'admin' else get_allowed_modules(username)

        def can_access(module):
            if username == 'admin':
                return True
            return module in allowed_modules if allowed_modules else False

        def menu_section(title):
            return ft.Container(
                content=ft.Text(title, color=ACCENT_PURPLE, size=11, weight=ft.FontWeight.BOLD),
                margin=ft.margin.only(top=12, bottom=4, left=10, right=10),
                padding=ft.padding.symmetric(vertical=6, horizontal=8),
                bgcolor=ft.colors.with_opacity(0.6, "#EDE9FE"),
                border_radius=10,
            )

        def menu_button(text, page_name, module=None):
            if module and not can_access(module):
                return ft.Container()
            return ft.TextButton(
                content=ft.Text(text, size=13, color=TEXT_PRIMARY),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.padding.symmetric(vertical=8, horizontal=10),
                    alignment=ft.alignment.center_right,
                    overlay_color=ft.colors.with_opacity(0.1, ACCENT_BLUE),
                ),
                on_click=lambda e: self.load_page(page_name),
            )

        sidebar_column = ft.Column(
            [
                ft.Container(
                    content=ft.Column([
                        ft.Text("🏢", size=36),
                        ft.Text("حوكمة ERP", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                        ft.Text("إدارة ذكية .. قرارات واثقة", size=10, color=ACCENT_PURPLE),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    padding=15,
                ),
                ft.Divider(color=GLASS_BORDER, height=1),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"👤 {self.user.get('full_name', self.user.get('username', 'مستخدم'))}",
                                color=ACCENT_GREEN, size=12, weight=ft.FontWeight.BOLD),
                        ft.Text("مرحباً بك", color=TEXT_SECONDARY, size=10),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    padding=8,
                ),
                ft.Divider(color=GLASS_BORDER, height=1),

                menu_section("🏠 الرئيسية"),
                menu_button("📊 لوحة المعلومات", "لوحة المعلومات"),

                menu_section("📦 العمليات"),
                menu_button("🛒 المبيعات", "المبيعات", "المبيعات"),
                menu_button("📋 المشتريات", "المشتريات", "المشتريات"),
                menu_button("🔄 المرتجعات", "المرتجعات", "مرتجعات البضاعة"),
                menu_button("💵 سندات القبض/الصرف", "سندات القبض والصرف", "سندات القبض والصرف"),
                menu_button("📦 المخزون", "المخزون", "المخزون"),
                menu_button("📦 التسويات المخزنية", "التسويات المخزنية", "التسويات المخزنية"),
                menu_button("🧾 المصروفات", "المصروفات", "المصروفات"),
                menu_button("👥 CRM", "إدارة العملاء", "إدارة العملاء"),

                menu_section("💰 المحاسبة والمالية"),
                menu_button("🧾 الحسابات", "الحسابات", "الحسابات"),
                menu_button("🌳 شجرة الحسابات", "شجرة الحسابات", "شجرة الحسابات"),
                menu_button("📈 القوائم المالية", "القوائم المالية", "القوائم المالية"),
                menu_button("🏢 مراكز التكلفة", "مراكز التكلفة", "مراكز التكلفة"),
                menu_button("💱 العملات", "العملات", "العملات"),
                menu_button("📋 الأرصدة الافتتاحية", "الأرصدة الافتتاحية", "الأرصدة الافتتاحية"),
                menu_button("💰 الصندوق", "الصندوق", "الصندوق"),
                menu_button("🏦 البنوك", "البنوك", "التعاملات البنكية"),
                menu_button("🧾 الضريبة", "الضريبة", "الضريبة"),
                menu_button("🔒 إغلاق الحسابات", "إغلاق الحسابات", "إغلاق الحسابات"),
                menu_button("📅 إغلاق الفترات", "إغلاق الفترات", "إغلاق الفترات"),
                menu_button("📊 FIFO", "FIFO", "FIFO المخزون"),
                menu_button("💱 تقييم العملات", "تقييم العملات", "تقييم العملات"),

                menu_section("👥 إدارة الأعمال"),
                menu_button("👔 الموارد البشرية", "الموارد البشرية", "الموارد البشرية"),
                menu_button("💰 كشف الرواتب", "كشف الرواتب", "كشف الرواتب"),
                menu_button("🏗️ الأصول الثابتة", "الأصول الثابتة", "الأصول الثابتة"),
                menu_button("📎 المرفقات", "المرفقات", "المرفقات"),

                menu_section("⚙️ النظام والأمان"),
                menu_button("🛡️ الصلاحيات", "الصلاحيات", "الصلاحيات"),
                menu_button("📋 سجل التدقيق", "سجل التدقيق", "سجل التدقيق"),
                menu_button("💾 النسخ الاحتياطي", "النسخ الاحتياطي", "نسخ احتياطي"),
                menu_button("📄 التقارير", "التقارير", "التقارير المالية XBRL"),

                menu_section("🤖 الذكاء الاصطناعي"),
                menu_button("🧠 المساعد الذكي", "المساعد الذكي", "المساعد الذكي"),

                ft.Divider(color=GLASS_BORDER),
                ft.TextButton(
                    content=ft.Text("🚪 تسجيل الخروج", size=13, color=ACCENT_RED),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.padding.symmetric(vertical=8, horizontal=10),
                        alignment=ft.alignment.center_right,
                    ),
                    on_click=lambda e: self.logout(),
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=2,
        )

        return ft.Container(
            content=sidebar_column,
            width=260,
            bgcolor=ft.colors.with_opacity(0.85, ft.colors.WHITE),
            padding=8,
            border=ft.border.only(right=ft.border.BorderSide(1, GLASS_BORDER)),
            shadow=SHADOW_MEDIUM,
        )

    # ============================================================
    # تحميل الصفحات مع patch_page_tables
    # ============================================================
    def load_page(self, page_name):
        try:
            if page_name == "لوحة المعلومات":
                from ui_flet.pages import dashboard as mod
                patch_page_tables(mod)
                self.content_area.content = mod.DashboardPage(self.page)

            elif page_name == "المبيعات":
                from ui_flet.pages import sales as mod
                patch_page_tables(mod)
                self.content_area.content = mod.SalesPage(self.page)

            elif page_name == "المشتريات":
                from ui_flet.pages import purchases as mod
                patch_page_tables(mod)
                self.content_area.content = mod.PurchasesPage(self.page)

            elif page_name == "المرتجعات":
                from ui_flet.pages import returns as mod
                patch_page_tables(mod)
                self.content_area.content = mod.ReturnsPage(self.page)

            elif page_name == "سندات القبض والصرف":
                from ui_flet.pages import receipts as mod
                patch_page_tables(mod)
                self.content_area.content = mod.ReceiptsPage(self.page)

            elif page_name == "المخزون":
                from ui_flet.pages import inventory as mod
                patch_page_tables(mod)
                self.content_area.content = mod.InventoryPage(self.page)

            elif page_name == "التسويات المخزنية":
                from ui_flet.pages import inventory_adjustment as mod
                patch_page_tables(mod)
                self.content_area.content = mod.InventoryAdjustmentPage(self.page)

            elif page_name == "المصروفات":
                from ui_flet.pages import expenses as mod
                patch_page_tables(mod)
                self.content_area.content = mod.ExpensesPage(self.page)

            elif page_name == "إدارة العملاء":
                from ui_flet.pages import crm as mod
                patch_page_tables(mod)
                self.content_area.content = mod.CRMPage(self.page)

            elif page_name == "الحسابات":
                from ui_flet.pages import accounting as mod
                patch_page_tables(mod)
                self.content_area.content = mod.AccountingPage(self.page)

            elif page_name == "شجرة الحسابات":
                from ui_flet.pages import chart as mod
                patch_page_tables(mod)
                self.content_area.content = mod.ChartPage(self.page)

            elif page_name == "القوائم المالية":
                from ui_flet.pages import financial as mod
                patch_page_tables(mod)
                self.content_area.content = mod.FinancialPage(self.page)

            elif page_name == "مراكز التكلفة":
                from ui_flet.pages import cost_center as mod
                patch_page_tables(mod)
                self.content_area.content = mod.CostCenterPage(self.page)

            elif page_name == "العملات":
                from ui_flet.pages import currency as mod
                patch_page_tables(mod)
                self.content_area.content = mod.CurrencyPage(self.page)

            elif page_name == "الأرصدة الافتتاحية":
                from ui_flet.pages import opening_balances as mod
                patch_page_tables(mod)
                self.content_area.content = mod.OpeningBalancesPage(self.page)

            elif page_name == "الصندوق":
                from ui_flet.pages import cash as mod
                patch_page_tables(mod)
                self.content_area.content = mod.CashPage(self.page)

            elif page_name == "البنوك":
                from ui_flet.pages import bank as mod
                patch_page_tables(mod)
                self.content_area.content = mod.BankPage(self.page)

            elif page_name == "الضريبة":
                from ui_flet.pages import vat as mod
                patch_page_tables(mod)
                self.content_area.content = mod.VATPage(self.page)

            elif page_name == "إغلاق الحسابات":
                from ui_flet.pages import closing as mod
                patch_page_tables(mod)
                self.content_area.content = mod.ClosingPage(self.page)

            elif page_name == "إغلاق الفترات":
                from ui_flet.pages import period as mod
                patch_page_tables(mod)
                self.content_area.content = mod.PeriodPage(self.page)

            elif page_name == "FIFO":
                from ui_flet.pages import fifo as mod
                patch_page_tables(mod)
                self.content_area.content = mod.FifoPage(self.page)

            elif page_name == "تقييم العملات":
                from ui_flet.pages import currency_revaluation as mod
                patch_page_tables(mod)
                self.content_area.content = mod.CurrencyRevaluationPage(self.page)

            elif page_name == "الموارد البشرية":
                from ui_flet.pages import hr as mod
                patch_page_tables(mod)
                self.content_area.content = mod.HRPage(self.page)

            elif page_name == "كشف الرواتب":
                from ui_flet.pages import payroll as mod
                patch_page_tables(mod)
                self.content_area.content = mod.PayrollPage(self.page)

            elif page_name == "الأصول الثابتة":
                from ui_flet.pages import assets as mod
                patch_page_tables(mod)
                self.content_area.content = mod.AssetsPage(self.page)

            elif page_name == "المرفقات":
                from ui_flet.pages import attachment as mod
                patch_page_tables(mod)
                self.content_area.content = mod.AttachmentPage(self.page)

            elif page_name == "الصلاحيات":
                from ui_flet.pages import roles as mod
                patch_page_tables(mod)
                self.content_area.content = mod.RolesPage(self.page)

            elif page_name == "سجل التدقيق":
                from ui_flet.pages import audit_log as mod
                patch_page_tables(mod)
                self.content_area.content = mod.AuditLogPage(self.page)

            elif page_name == "النسخ الاحتياطي":
                from ui_flet.pages import backup as mod
                patch_page_tables(mod)
                self.content_area.content = mod.BackupPage(self.page)

            elif page_name == "التقارير":
                from ui_flet.pages import pdf_reports as mod
                patch_page_tables(mod)
                self.content_area.content = mod.PdfReportsPage(self.page)

            elif page_name == "المساعد الذكي":
                from ui_flet.pages import ai as mod
                patch_page_tables(mod)
                self.content_area.content = mod.AIPage(self.page)

            else:
                self.content_area.content = ft.Text(
                    f"⚠️ صفحة غير معروفة: {page_name}", color=ACCENT_ORANGE
                )

        except Exception as e:
            self.content_area.content = ft.Column([
                ft.Text(f"❌ خطأ في تحميل: {page_name}", size=18, color=ACCENT_RED, weight=ft.FontWeight.BOLD),
                ft.Text(str(e), color=TEXT_SECONDARY, size=12, selectable=True),
            ], spacing=10)

        self.page.update()

    # ============================================================
    # تسجيل الخروج
    # ============================================================
    def logout(self):
        self.page.session.set("user", None)
        self.page.session.set("logged_in", False)
        self.page.go("/")
        self.page.update()


# ============================================================
# نقطة الدخول
# ============================================================
def main(page: ft.Page):
    page.title = "حوكمة ERP - Hokama ERP"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F1F5F9"
    page.padding = 0
    page.window_min_width = 1024
    page.window_min_height = 700

    page.fonts = {
        "Cairo": "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf"
    }
    page.theme = ft.Theme(font_family="Cairo")

    database.init_db()
    database.create_default_admin()
    seed_default_roles()

    user = page.session.get("user")
    logged_in = page.session.get("logged_in", False)

    if not logged_in or not user:
        from ui_flet.pages.auth import AuthPage
        page.add(AuthPage(page))
    else:
        page.add(MainApp(page, user))


if __name__ == "__main__":
    ft.app(target=main)
