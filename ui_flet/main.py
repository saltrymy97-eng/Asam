# ui_flet/main.py
import flet as ft
import os
import sys

# ✅ إضافة مسار المشروع الرئيسي للتمكن من استيراد الخدمات وقاعدة البيانات
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from ui_flet.shared import *
import database
from services.roles_service import get_allowed_modules, seed_default_roles


class MainApp(ft.Row):
    def __init__(self, page: ft.Page, user: dict):
        super().__init__()
        self.page = page
        self.user = user
        self.expand = True
        self.current_page = "لوحة المعلومات"

        # منطقة عرض المحتوى
        self.content_area = ft.Container(expand=True, padding=20)

        # بناء القائمة الجانبية
        self.sidebar = self.build_sidebar()

        self.controls = [self.sidebar, self.content_area]

        # عرض الصفحة الافتراضية
        self.load_page("لوحة المعلومات")

    def build_sidebar(self):
        """بناء القائمة الجانبية الكاملة لجميع الوحدات الـ 31"""

        # التحقق من صلاحيات المستخدم
        username = self.user.get('username', '')
        if username == 'admin':
            allowed_modules = None  # المدير يرى كل شيء
        else:
            allowed_modules = get_allowed_modules(username)

        def can_access(module):
            if username == 'admin':
                return True
            return module in allowed_modules if allowed_modules else False

        def menu_section(title):
            return ft.Container(
                content=ft.Text(title, color=ACCENT_PURPLE, size=11, weight=ft.FontWeight.BOLD),
                margin=ft.margin.only(top=12, bottom=4, left=10, right=10),
                padding=ft.padding.symmetric(vertical=6, horizontal=8),
                bgcolor=ft.colors.with_opacity(0.03, ft.colors.WHITE),
                border_radius=10,
            )

        def menu_button(text, page_name, module=None):
            # إذا كان هناك module محدد، نتحقق من الصلاحية
            if module and not can_access(module):
                return ft.Container()  # لا نعرض الزر
            return ft.TextButton(
                content=ft.Text(text, size=13, color=ft.colors.WHITE),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.padding.symmetric(vertical=8, horizontal=10),
                    alignment=ft.alignment.center_right,
                ),
                on_click=lambda e: self.load_page(page_name),
            )

        # بناء القائمة الكاملة
        sidebar_column = ft.Column(
            [
                # الشعار
                ft.Container(
                    content=ft.Column([
                        ft.Text("🏢", size=36),
                        ft.Text("حوكمة ERP", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                        ft.Text("إدارة ذكية .. قرارات واثقة", size=10, color=ACCENT_PURPLE),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    padding=15,
                ),
                ft.Divider(color=GLASS_BORDER, height=1),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"👤 {self.user.get('full_name', self.user.get('username', 'مستخدم'))}", color=ACCENT_GREEN, size=12, weight=ft.FontWeight.BOLD),
                        ft.Text("مرحباً بك", color=TEXT_SECONDARY, size=10),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    padding=8,
                ),
                ft.Divider(color=GLASS_BORDER, height=1),

                # ============ الرئيسية ============
                menu_section("🏠 الرئيسية"),
                menu_button("📊 لوحة المعلومات", "لوحة المعلومات"),

                # ============ العمليات ============
                menu_section("📦 العمليات"),
                menu_button("🛒 المبيعات", "المبيعات", "المبيعات"),
                menu_button("📋 المشتريات", "المشتريات", "المشتريات"),
                menu_button("🔄 المرتجعات", "المرتجعات", "مرتجعات البضاعة"),
                menu_button("💵 سندات القبض/الصرف", "سندات القبض والصرف", "سندات القبض والصرف"),
                menu_button("📦 المخزون", "المخزون", "المخزون"),
                menu_button("📦 التسويات المخزنية", "التسويات المخزنية", "التسويات المخزنية"),
                menu_button("🧾 المصروفات", "المصروفات", "المصروفات"),
                menu_button("👥 CRM", "إدارة العملاء", "إدارة العملاء"),

                # ============ المحاسبة والمالية ============
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

                # ============ إدارة الأعمال ============
                menu_section("👥 إدارة الأعمال"),
                menu_button("👔 الموارد البشرية", "الموارد البشرية", "الموارد البشرية"),
                menu_button("💰 كشف الرواتب", "كشف الرواتب", "كشف الرواتب"),
                menu_button("🏗️ الأصول الثابتة", "الأصول الثابتة", "الأصول الثابتة"),
                menu_button("📎 المرفقات", "المرفقات", "المرفقات"),

                # ============ النظام والأمان ============
                menu_section("⚙️ النظام والأمان"),
                menu_button("🛡️ الصلاحيات", "الصلاحيات", "الصلاحيات"),
                menu_button("📋 سجل التدقيق", "سجل التدقيق", "سجل التدقيق"),
                menu_button("💾 النسخ الاحتياطي", "النسخ الاحتياطي", "نسخ احتياطي"),
                menu_button("📄 التقارير", "التقارير", "التقارير المالية XBRL"),

                # ============ الذكاء الاصطناعي ============
                menu_section("🤖 الذكاء الاصطناعي"),
                menu_button("🧠 المساعد الذكي", "المساعد الذكي", "المساعد الذكي"),

                # ============ الخروج ============
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
            bgcolor="#0F172A",
            padding=8,
            border=ft.border.only(right=ft.border.BorderSide(1, GLASS_BORDER)),
        )

    def load_page(self, page_name):
        """توجيه الطلب إلى الصفحة المناسبة"""
        self.current_page = page_name
        
        try:
            # ============ الرئيسية ============
            if page_name == "لوحة المعلومات":
                from ui_flet.pages.dashboard import DashboardPage
                self.content_area.content = DashboardPage(self.page)

            # ============ العمليات ============
            elif page_name == "المبيعات":
                from ui_flet.pages.sales import SalesPage
                self.content_area.content = SalesPage(self.page)
            elif page_name == "المشتريات":
                from ui_flet.pages.purchases import PurchasesPage
                self.content_area.content = PurchasesPage(self.page)
            elif page_name == "المرتجعات":
                from ui_flet.pages.returns import ReturnsPage
                self.content_area.content = ReturnsPage(self.page)
            elif page_name == "سندات القبض والصرف":
                from ui_flet.pages.receipts import ReceiptsPage
                self.content_area.content = ReceiptsPage(self.page)
            elif page_name == "المخزون":
                from ui_flet.pages.inventory import InventoryPage
                self.content_area.content = InventoryPage(self.page)
            elif page_name == "التسويات المخزنية":
                from ui_flet.pages.inventory_adjustment import InventoryAdjustmentPage
                self.content_area.content = InventoryAdjustmentPage(self.page)
            elif page_name == "المصروفات":
                from ui_flet.pages.expenses import ExpensesPage
                self.content_area.content = ExpensesPage(self.page)
            elif page_name == "إدارة العملاء":
                from ui_flet.pages.crm import CRMPage
                self.content_area.content = CRMPage(self.page)

            # ============ المحاسبة والمالية ============
            elif page_name == "الحسابات":
                from ui_flet.pages.accounting import AccountingPage
                self.content_area.content = AccountingPage(self.page)
            elif page_name == "شجرة الحسابات":
                from ui_flet.pages.chart import ChartPage
                self.content_area.content = ChartPage(self.page)
            elif page_name == "القوائم المالية":
                from ui_flet.pages.financial import FinancialPage
                self.content_area.content = FinancialPage(self.page)
            elif page_name == "مراكز التكلفة":
                from ui_flet.pages.cost_center import CostCenterPage
                self.content_area.content = CostCenterPage(self.page)
            elif page_name == "العملات":
                from ui_flet.pages.currency import CurrencyPage
                self.content_area.content = CurrencyPage(self.page)
            elif page_name == "الأرصدة الافتتاحية":
                from ui_flet.pages.opening_balances import OpeningBalancesPage
                self.content_area.content = OpeningBalancesPage(self.page)
            elif page_name == "الصندوق":
                from ui_flet.pages.cash import CashPage
                self.content_area.content = CashPage(self.page)
            elif page_name == "البنوك":
                from ui_flet.pages.bank import BankPage
                self.content_area.content = BankPage(self.page)
            elif page_name == "الضريبة":
                from ui_flet.pages.vat import VATPage
                self.content_area.content = VATPage(self.page)
            elif page_name == "إغلاق الحسابات":
                from ui_flet.pages.closing import ClosingPage
                self.content_area.content = ClosingPage(self.page)
            elif page_name == "إغلاق الفترات":
                from ui_flet.pages.period import PeriodPage
                self.content_area.content = PeriodPage(self.page)
            elif page_name == "FIFO":
                from ui_flet.pages.fifo import FifoPage
                self.content_area.content = FifoPage(self.page)
            elif page_name == "تقييم العملات":
                from ui_flet.pages.currency_revaluation import CurrencyRevaluationPage
                self.content_area.content = CurrencyRevaluationPage(self.page)

            # ============ إدارة الأعمال ============
            elif page_name == "الموارد البشرية":
                from ui_flet.pages.hr import HRPage
                self.content_area.content = HRPage(self.page)
            elif page_name == "كشف الرواتب":
                from ui_flet.pages.payroll import PayrollPage
                self.content_area.content = PayrollPage(self.page)
            elif page_name == "الأصول الثابتة":
                from ui_flet.pages.assets import AssetsPage
                self.content_area.content = AssetsPage(self.page)
            elif page_name == "المرفقات":
                from ui_flet.pages.attachment import AttachmentPage
                self.content_area.content = AttachmentPage(self.page)

            # ============ النظام والأمان ============
            elif page_name == "الصلاحيات":
                from ui_flet.pages.roles import RolesPage
                self.content_area.content = RolesPage(self.page)
            elif page_name == "سجل التدقيق":
                from ui_flet.pages.audit_log import AuditLogPage
                self.content_area.content = AuditLogPage(self.page)
            elif page_name == "النسخ الاحتياطي":
                from ui_flet.pages.backup import BackupPage
                self.content_area.content = BackupPage(self.page)
            elif page_name == "التقارير":
                from ui_flet.pages.pdf_reports import PdfReportsPage
                self.content_area.content = PdfReportsPage(self.page)

            # ============ الذكاء الاصطناعي ============
            elif page_name == "المساعد الذكي":
                from ui_flet.pages.ai import AIPage
                self.content_area.content = AIPage(self.page)

            else:
                self.content_area.content = ft.Column([
                    ft.Text(f"⚠️ الصفحة '{page_name}' غير معروفة", size=20, color=ACCENT_ORANGE),
                ], alignment=ft.MainAxisAlignment.CENTER)

        except Exception as e:
            self.content_area.content = ft.Column([
                ft.Text(f"❌ خطأ في تحميل الصفحة: {page_name}", size=20, color=ACCENT_RED, weight=ft.FontWeight.BOLD),
                ft.Text(str(e), color=TEXT_SECONDARY, size=12, selectable=True),
            ], spacing=10)

        self.page.update()

    def logout(self):
        """تسجيل الخروج والعودة لشاشة الدخول"""
        # مسح الجلسة
        self.page.session.set("user", None)
        self.page.session.set("logged_in", False)
        # إعادة تحميل الصفحة (ستعود إلى AuthPage)
        self.page.go("/")
        self.page.update()


def main(page: ft.Page):
    # ============ إعدادات الصفحة الأساسية ============
    page.title = "حوكمة ERP - Hokama ERP"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0A0A1E"
    page.padding = 0
    page.window_min_width = 1024
    page.window_min_height = 700

    # إعداد الخط العربي
    page.fonts = {
        "Cairo": "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf"
    }
    page.theme = ft.Theme(font_family="Cairo")

    # ============ تهيئة قاعدة البيانات ============
    database.init_db()
    database.create_default_admin()
    seed_default_roles()

    # ============ فحص حالة الدخول ============
    user = page.session.get("user")
    logged_in = page.session.get("logged_in", False)

    if not logged_in or not user:
        # عرض شاشة الدخول
        from ui_flet.pages.auth import AuthPage
        auth_page = AuthPage(page)
        page.add(auth_page)
        
        # ✅ نظام الاستماع لتغير الجلسة (بعد تسجيل الدخول)
        def check_login():
            # هذه الدالة تُستدعى عبر الأحداث في AuthPage
            pass
    else:
        # عرض التطبيق الرئيسي
        app = MainApp(page, user)
        page.add(app)


if __name__ == "__main__":
    ft.app(target=main)
