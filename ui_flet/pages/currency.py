# ui_flet/pages/currency.py
import flet as ft
import pandas as pd
from datetime import date
from services import currency_service as cur
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

def temp_data_table(df: pd.DataFrame) -> ft.Control:
    """جدول مؤقت سيتم استبداله لاحقاً"""
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

class CurrencyPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        try:
            cur.create_default_currencies()
        except Exception as e:
            print(f"Currency init error: {e}")

        self.header = ft.Text("💱 العملات وأسعار الصرف", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة العملات وتحويل الأموال بأسعار الصرف اليومية", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="💵 العملات", content=self.build_currencies_tab()),
                ft.Tab(text="📈 أسعار الصرف", content=self.build_rates_tab()),
                ft.Tab(text="🔄 تحويل العملات", content=self.build_convert_tab()),
            ],
            expand=True,
        )

        self.controls = [
            ft.Column([self.header, self.subtitle], spacing=5),
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. تبويب العملات
    # ============================================================
    def build_currencies_tab(self):
        # --- نموذج الإضافة ---
        self.cur_code = ft.TextField(label="رمز العملة", hint_text="مثال: USD, SAR, EUR", expand=True)
        self.cur_name = ft.TextField(label="اسم العملة", hint_text="دولار أمريكي", expand=True)
        self.cur_symbol = ft.TextField(label="الرمز (اختياري)", hint_text="$", expand=True)
        self.cur_is_base = ft.Checkbox(label="عملة أساسية (للتقارير المالية)")
        
        def add_currency(e):
            if not self.cur_code.value or not self.cur_name.value:
                self.show_snackbar("الرمز والاسم مطلوبان", ACCENT_RED)
                return
            try:
                cur.create_currency(self.cur_code.value, self.cur_name.value, self.cur_symbol.value, self.cur_is_base.value)
                self.show_snackbar(f"تمت إضافة {self.cur_code.value}", ACCENT_GREEN)
                self.cur_code.value = ""
                self.cur_name.value = ""
                self.cur_symbol.value = ""
                self.cur_is_base.value = False
                self.refresh_currencies_list()
                self.refresh_dropdowns()
            except ValueError as ex:
                self.show_snackbar(str(ex), ACCENT_RED)

        form_col = ft.Column([
            ft.Text("➕ إضافة عملة جديدة", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
            ft.Row([self.cur_code, self.cur_name]),
            ft.Row([self.cur_symbol]),
            self.cur_is_base,
            ft.ElevatedButton("✅ إضافة", on_click=add_currency, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
        ], spacing=10)
        form_container = ft.Container(content=form_col, bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True)

        # --- قائمة العملات ---
        self.currencies_list_col = ft.Column(spacing=5)
        self.refresh_currencies_list()
        
        list_container = ft.Container(
            content=ft.Column([
                ft.Text("📋 العملات المتاحة", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                self.currencies_list_col
            ], spacing=10),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

        return ft.Row([form_container, list_container], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)

    def refresh_currencies_list(self):
        currencies = cur.get_all_currencies(active_only=False)
        self.currencies_list_col.controls.clear()
        if currencies:
            for c in currencies:
                base_badge = "⭐ أساسية" if c['is_base'] else ""
                active_badge = "🟢" if c['is_active'] else "🔴"
                self.currencies_list_col.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(f"{c['code']} - {c['name']} {c.get('symbol','')}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{base_badge} {active_badge}", color=TEXT_SECONDARY, size=12)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=8,
                        border=ft.border.only(bottom=ft.border.BorderSide(1, GLASS_BORDER))
                    )
                )
        else:
            self.currencies_list_col.controls.append(ft.Text("لا توجد عملات مضافة", color=TEXT_SECONDARY))
        self.page.update()

    # ============================================================
    # 2. تبويب أسعار الصرف
    # ============================================================
    def build_rates_tab(self):
        self.currencies = cur.get_all_currencies()
        codes = [c['code'] for c in self.currencies]
        
        if len(codes) < 2:
            return ft.Text("تحتاج عملتين على الأقل لإدارة أسعار الصرف", color=ACCENT_ORANGE)

        # نموذج إضافة سعر
        self.rate_from = ft.Dropdown(label="من عملة", options=[ft.dropdown.Option(c) for c in codes], value=codes[0], expand=True)
        self.rate_to = ft.Dropdown(label="إلى عملة", options=[ft.dropdown.Option(c) for c in codes], value=codes[1] if len(codes)>1 else codes[0], expand=True)
        self.rate_val = ft.TextField(label="سعر الصرف", value="1.0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.rate_date = ft.TextField(label="التاريخ (YYYY-MM-DD)", value=date.today().strftime("%Y-%m-%d"), expand=True)

        def save_rate(e):
            if self.rate_from.value == self.rate_to.value:
                self.show_snackbar("يجب اختيار عملتين مختلفتين", ACCENT_RED)
                return
            try:
                rate = float(self.rate_val.value)
                cur.set_exchange_rate(self.rate_from.value, self.rate_to.value, rate, self.rate_date.value)
                self.show_snackbar(f"تم حفظ سعر {self.rate_from.value} → {self.rate_to.value}: {rate}", ACCENT_GREEN)
                self.load_history()
            except ValueError:
                self.show_snackbar("سعر الصرف غير صالح", ACCENT_RED)

        form_container = ft.Container(
            content=ft.Column([
                ft.Text("📈 تسجيل سعر صرف جديد", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                ft.Row([self.rate_from, self.rate_to]),
                ft.Row([self.rate_val, self.rate_date]),
                ft.ElevatedButton("💾 حفظ", on_click=save_rate, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
            ]),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15
        )

        # سجل الأسعار
        self.hist_from = ft.Dropdown(label="من", options=[ft.dropdown.Option(c) for c in codes], value=codes[0], expand=True)
        self.hist_to = ft.Dropdown(label="إلى", options=[ft.dropdown.Option(c) for c in codes], value=codes[1], expand=True)
        
        self.hist_table_container = ft.Container()
        
        def on_hist_change(e):
            self.load_history()
        
        self.hist_from.on_change = on_hist_change
        self.hist_to.on_change = on_hist_change

        hist_container = ft.Container(
            content=ft.Column([
                ft.Text("📋 آخر أسعار الصرف", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                ft.Row([self.hist_from, self.hist_to]),
                self.hist_table_container
            ]),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )
        
        self.load_history()

        return ft.Column([form_container, ft.Divider(color=GLASS_BORDER), hist_container], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        if not hasattr(self, 'hist_from') or not self.hist_from.value: return
        history = cur.get_exchange_rate_history(self.hist_from.value, self.hist_to.value)
        if history:
            df = pd.DataFrame(history)
            df = df.rename(columns={"date": "التاريخ", "rate": "السعر"})
            self.hist_table_container.content = temp_data_table(df[["التاريخ", "السعر"]])
        else:
            self.hist_table_container.content = ft.Text("لا يوجد سجل أسعار", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 3. تبويب تحويل العملات
    # ============================================================
    def build_convert_tab(self):
        codes = [c['code'] for c in self.currencies]
        if len(codes) < 2:
            return ft.Text("تحتاج عملتين على الأقل للتحويل", color=ACCENT_ORANGE)

        self.conv_amount = ft.TextField(label="المبلغ", value="1.0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.conv_from = ft.Dropdown(label="من", options=[ft.dropdown.Option(c) for c in codes], value=codes[0], expand=True)
        self.conv_to = ft.Dropdown(label="إلى", options=[ft.dropdown.Option(c) for c in codes], value=codes[1], expand=True)
        
        self.conv_result = ft.Text("", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD)

        def do_convert(e):
            try:
                amount = float(self.conv_amount.value)
                result = cur.convert_amount(amount, self.conv_from.value, self.conv_to.value)
                self.conv_result.value = f"✅ {amount:,.2f} {self.conv_from.value} = {result:,.2f} {self.conv_to.value}"
                self.conv_result.color = ACCENT_GREEN
            except ValueError as ex:
                self.conv_result.value = f"❌ {str(ex)}"
                self.conv_result.color = ACCENT_RED
            self.page.update()

        return ft.Container(
            content=ft.Column([
                ft.Text("🔄 حاسبة تحويل العملات", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                ft.Row([self.conv_amount]),
                ft.Row([self.conv_from, self.conv_to]),
                ft.ElevatedButton("🔄 تحويل", on_click=do_convert, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
                self.conv_result
            ], spacing=15),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=20, expand=True
        )

    def refresh_dropdowns(self):
        """تحديث القوائم المنسدلة في التبويبات الأخرى بعد إضافة عملة جديدة"""
        self.currencies = cur.get_all_currencies()
        codes = [c['code'] for c in self.currencies]
        
        if hasattr(self, 'rate_from'):
            self.rate_from.options = [ft.dropdown.Option(c) for c in codes]
            self.rate_to.options = [ft.dropdown.Option(c) for c in codes]
        if hasattr(self, 'hist_from'):
            self.hist_from.options = [ft.dropdown.Option(c) for c in codes]
            self.hist_to.options = [ft.dropdown.Option(c) for c in codes]
        if hasattr(self, 'conv_from'):
            self.conv_from.options = [ft.dropdown.Option(c) for c in codes]
            self.conv_to.options = [ft.dropdown.Option(c) for c in codes]
        
        self.page.update()
