# ui_flet/pages/financial.py
import flet as ft
import pandas as pd
from datetime import datetime
from services.financial_service import get_income_statement, get_balance_sheet
from services import cost_center_service as ccs
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

ACCENT_CYAN = "#06B6D4"

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

class FinancialPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("📊 القوائم المالية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("قائمة الدخل والميزانية العمومية", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📈 قائمة الدخل", content=self.build_income_tab()),
                ft.Tab(text="⚖️ الميزانية العمومية", content=self.build_balance_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def glass_card(self, title, icon, value, color, subtitle=""):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=30),
                ft.Text(title, color=TEXT_SECONDARY, size=12),
                ft.Text(str(value), color=color, size=20, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, color=TEXT_SECONDARY, size=10) if subtitle else ft.Container()
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

    # ============================================================
    # 1. قائمة الدخل
    # ============================================================
    def build_income_tab(self):
        # اختيار السنة والشهر
        self.year_dd = ft.Dropdown(label="📅 السنة", options=[ft.dropdown.Option(str(y)) for y in range(2023, datetime.now().year + 2)], value=str(datetime.now().year), width=120)
        self.month_dd = ft.Dropdown(label="📅 الشهر", options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(f"{i:02d}") for i in range(1, 13)], value="الكل", width=120)
        
        # فلتر مراكز التكلفة
        centers = ccs.get_all_cost_centers(active_only=True)
        self.center_map = {0: "كل الشركة (بدون تصفية)"}
        for c in centers: self.center_map[c['id']] = f"{c['code']} - {c['name']}"
        self.center_dd = ft.Dropdown(label="🏢 مركز التكلفة", options=[ft.dropdown.Option(key=str(k), text=v) for k, v in self.center_map.items()], value="0", expand=True)

        self.income_result = ft.Container()
        self.period_caption = ft.Text("", color=TEXT_SECONDARY, size=12)

        def refresh_income(e=None):
            year = int(self.year_dd.value)
            month = None if self.month_dd.value == "الكل" else self.month_dd.value
            cid = None if self.center_dd.value == "0" else int(self.center_dd.value)
            
            period_label = str(year) + (f"-{month}" if month else "")
            self.period_caption.value = f"📌 عرض البيانات للفترة: {period_label}"

            income = get_income_statement(cid, year, month)
            
            content = []
            if cid:
                center_name = self.center_map[cid]
                content.append(ft.Text(f"يتم عرض بيانات مركز التكلفة: {center_name}", color=ACCENT_BLUE, size=12))

            if income['total_revenue'] == 0 and income['total_expenses'] == 0:
                content.append(ft.Text("⚠️ لا توجد بيانات مالية للفترة/المركز المحدد.", color=ACCENT_ORANGE))
            else:
                net = income['net_income']
                content.append(ft.Row([
                    self.glass_card("الإيرادات", "📈", f"{income['total_revenue']:,.2f}", ACCENT_GREEN),
                    self.glass_card("المصروفات", "📉", f"{income['total_expenses']:,.2f}", ACCENT_RED),
                    self.glass_card("صافي الدخل", "💎", f"{net:,.2f}", ACCENT_GREEN if net >= 0 else ACCENT_RED, "ربح ✅" if net >= 0 else "خسارة ⚠️")
                ], spacing=10))

                # جداول جانبية
                rev_content = [ft.Text("الإيرادات", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD)]
                rev_content.append(temp_data_table(pd.DataFrame(income['revenue']).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})) if income['revenue'] else ft.Text("لا توجد إيرادات مسجلة", color=TEXT_SECONDARY))
                
                exp_content = [ft.Text("المصروفات", color=ACCENT_RED, weight=ft.FontWeight.BOLD)]
                exp_content.append(temp_data_table(pd.DataFrame(income['expenses']).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})) if income['expenses'] else ft.Text("لا توجد مصروفات مسجلة", color=TEXT_SECONDARY))
                
                content.append(ft.Row([
                    ft.Column(rev_content, expand=True),
                    ft.Column(exp_content, expand=True)
                ], spacing=15))

            self.income_result.content = ft.Column(content, spacing=15)
            self.page.update()

        self.year_dd.on_change = refresh_income
        self.month_dd.on_change = refresh_income
        self.center_dd.on_change = refresh_income
        refresh_income()

        return ft.Column([
            ft.Row([self.year_dd, self.month_dd]),
            self.center_dd,
            self.period_caption,
            ft.Divider(color=GLASS_BORDER),
            self.income_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 2. الميزانية العمومية
    # ============================================================
    def build_balance_tab(self):
        self.bal_year_dd = ft.Dropdown(label="📅 السنة", options=[ft.dropdown.Option(str(y)) for y in range(2023, datetime.now().year + 2)], value=str(datetime.now().year), width=120)
        self.bal_month_dd = ft.Dropdown(label="📅 الشهر", options=[ft.dropdown.Option("الكل")] + [ft.dropdown.Option(f"{i:02d}") for i in range(1, 13)], value="الكل", width=120)
        
        centers = ccs.get_all_cost_centers(active_only=True)
        self.bal_center_map = {0: "كل الشركة (بدون تصفية)"}
        for c in centers: self.bal_center_map[c['id']] = f"{c['code']} - {c['name']}"
        self.bal_center_dd = ft.Dropdown(label="🏢 مركز التكلفة", options=[ft.dropdown.Option(key=str(k), text=v) for k, v in self.bal_center_map.items()], value="0", expand=True)

        self.bal_result = ft.Container()

        def refresh_balance(e=None):
            year = int(self.bal_year_dd.value)
            month = None if self.bal_month_dd.value == "الكل" else self.bal_month_dd.value
            cid = None if self.bal_center_dd.value == "0" else int(self.bal_center_dd.value)

            balance = get_balance_sheet(cid, year, month)
            content = []

            if cid and balance['total_assets'] == 0 and balance['total_liabilities'] == 0:
                content.append(ft.Text("⚠️ لا توجد بيانات ميزانية لهذا المركز.", color=ACCENT_ORANGE))
            elif balance['total_assets'] == 0 and balance['total_liabilities'] == 0 and not cid:
                content.append(ft.Text("⚠️ لا توجد بيانات للميزانية العمومية.", color=ACCENT_ORANGE))
            else:
                content.append(ft.Row([
                    self.glass_card("الأصول", "🏢", f"{balance['total_assets']:,.2f}", ACCENT_BLUE),
                    self.glass_card("الخصوم", "📋", f"{balance['total_liabilities']:,.2f}", ACCENT_ORANGE),
                    self.glass_card("حقوق الملكية", "👑", f"{balance['total_equity']:,.2f}", ACCENT_PURPLE)
                ], spacing=10))

                # جداول جانبية
                assets_content = [ft.Text("الأصول", color=ACCENT_BLUE, weight=ft.FontWeight.BOLD)]
                assets_content.append(temp_data_table(pd.DataFrame(balance['assets']).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})) if balance['assets'] else ft.Text("لا توجد أصول مسجلة", color=TEXT_SECONDARY))
                
                combined = balance['liabilities'] + balance['equity']
                liab_content = [ft.Text("الخصوم وحقوق الملكية", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD)]
                liab_content.append(temp_data_table(pd.DataFrame(combined).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})) if combined else ft.Text("لا توجد خصوم أو حقوق ملكية", color=TEXT_SECONDARY))
                
                content.append(ft.Row([
                    ft.Column(assets_content, expand=True),
                    ft.Column(liab_content, expand=True)
                ], spacing=15))

                # التوازن
                is_balanced = abs(balance['total_assets'] - balance['total_liab_equity']) < 0.01
                content.append(ft.Row([
                    ft.Text(f"إجمالي الأصول: {balance['total_assets']:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Text(f"إجمالي الخصوم + حقوق الملكية: {balance['total_liab_equity']:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
                content.append(ft.Text("✅ الميزانية متوازنة" if is_balanced else "⚠️ الميزانية غير متوازنة", color=ACCENT_GREEN if is_balanced else ACCENT_RED, weight=ft.FontWeight.BOLD))

            self.bal_result.content = ft.Column(content, spacing=15)
            self.page.update()

        self.bal_year_dd.on_change = refresh_balance
        self.bal_month_dd.on_change = refresh_balance
        self.bal_center_dd.on_change = refresh_balance
        refresh_balance()

        return ft.Column([
            ft.Row([self.bal_year_dd, self.bal_month_dd]),
            self.bal_center_dd,
            ft.Divider(color=GLASS_BORDER),
            self.bal_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
