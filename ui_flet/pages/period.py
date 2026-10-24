# ui_flet/pages/period.py
import flet as ft
import pandas as pd
from services.period_service import (
    create_periods_table, close_period, reopen_period,
    get_closed_periods, get_available_months, get_available_years
)
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

class PeriodPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        try:
            create_periods_table()
        except Exception as e:
            print(f"Periods table error: {e}")

        self.header = ft.Text("📅 إغلاق الفترات المالية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إغلاق وإعادة فتح الشهور والسنوات المالية", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="🔒 إغلاق / فتح", content=self.build_close_tab()),
                ft.Tab(text="📋 الفترات المغلقة", content=self.build_view_tab()),
            ],
            expand=True,
        )

        self.controls = [
            ft.Column([self.header, self.subtitle], spacing=5),
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    def _current_username(self):
        return "admin" # مؤقتاً حتى نربط الدخول

    # ============================================================
    # 1. إغلاق / فتح
    # ============================================================
    def build_close_tab(self):
        # --- إغلاق شهر ---
        months = get_available_months()
        self.month_dd = ft.Dropdown(
            label="اختر الشهر", 
            options=[ft.dropdown.Option(m) for m in months],
            value=months[0] if months else None,
            disabled=not months
        )
        month_btn = ft.ElevatedButton(
            "🔒 إغلاق الشهر", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE,
            on_click=self.close_month, disabled=not months
        )
        
        month_col = ft.Column([
            ft.Text("إغلاق شهر", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD, size=16),
            self.month_dd,
            month_btn
        ], spacing=10)
        
        if not months:
            month_col.controls.append(ft.Text("لا توجد شهور متاحة (لا توجد قيود)", color=TEXT_SECONDARY, size=12))

        # --- إغلاق سنة ---
        years = get_available_years()
        self.year_dd = ft.Dropdown(
            label="اختر السنة", 
            options=[ft.dropdown.Option(y) for y in years],
            value=years[0] if years else None,
            disabled=not years
        )
        year_btn = ft.ElevatedButton(
            "🔒 إغلاق السنة", bgcolor=ACCENT_BLUE, color=ft.colors.WHITE,
            on_click=self.close_year, disabled=not years
        )
        
        year_col = ft.Column([
            ft.Text("إغلاق سنة", color=ACCENT_BLUE, weight=ft.FontWeight.BOLD, size=16),
            self.year_dd,
            year_btn
        ], spacing=10)
        
        if not years:
            year_col.controls.append(ft.Text("لا توجد سنوات متاحة", color=TEXT_SECONDARY, size=12))

        # --- إعادة فتح ---
        self.reopen_dd = ft.Dropdown(label="اختر الفترة لإعادة فتحها", expand=True)
        self.reopen_btn = ft.ElevatedButton(
            "🔓 إعادة فتح الفترة", bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE,
            on_click=self.reopen_selected
        )
        self.reopen_status = ft.Text("", color=TEXT_SECONDARY, size=12)
        
        # تحميل الفترات المغلقة في القائمة
        self.load_reopen_options()

        reopen_col = ft.Column([
            ft.Text("🔓 إعادة فتح فترة", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD, size=16),
            self.reopen_dd,
            self.reopen_btn,
            self.reopen_status
        ], spacing=10)

        return ft.Column([
            ft.Row([month_col, year_col], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ft.Divider(color=GLASS_BORDER),
            reopen_col
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=20)

    def load_reopen_options(self):
        periods = get_closed_periods()
        self.closed_periods_data = periods
        if periods:
            options = []
            for p in periods:
                type_str = "شهر" if p['period_type'] == 'month' else "سنة"
                label = f"{type_str}: {p['period_value']} (أغلقها {p['closed_by']} في {p['closed_at']})"
                options.append(ft.dropdown.Option(key=str(p['id']), text=label))
            self.reopen_dd.options = options
            self.reopen_dd.disabled = False
            self.reopen_btn.disabled = False
            if not self.reopen_dd.value and options:
                self.reopen_dd.value = options[0].key
        else:
            self.reopen_dd.options = []
            self.reopen_dd.disabled = True
            self.reopen_btn.disabled = True

    def close_month(self, e):
        if not self.month_dd.value: return
        close_period("month", self.month_dd.value, self._current_username())
        self.show_snackbar(f"تم إغلاق شهر {self.month_dd.value}", ACCENT_GREEN)
        self.refresh_all()

    def close_year(self, e):
        if not self.year_dd.value: return
        close_period("year", self.year_dd.value, self._current_username())
        self.show_snackbar(f"تم إغلاق سنة {self.year_dd.value}", ACCENT_GREEN)
        self.refresh_all()

    def reopen_selected(self, e):
        if not self.reopen_dd.value or not self.closed_periods_data: return
        period_id = int(self.reopen_dd.value)
        p = next((x for x in self.closed_periods_data if x['id'] == period_id), None)
        
        if p:
            reopen_period(p["period_type"], p["period_value"])
            self.show_snackbar(f"تم إعادة فتح {p['period_type']}: {p['period_value']}", ACCENT_GREEN)
            self.refresh_all()

    def refresh_all(self):
        # تحديث قائمة الشهور والسنوات
        months = get_available_months()
        self.month_dd.options = [ft.dropdown.Option(m) for m in months]
        self.month_dd.disabled = not months
        if months and not self.month_dd.value: self.month_dd.value = months[0]

        years = get_available_years()
        self.year_dd.options = [ft.dropdown.Option(y) for y in years]
        self.year_dd.disabled = not years
        if years and not self.year_dd.value: self.year_dd.value = years[0]

        # تحديث قائمة إعادة الفتح
        self.load_reopen_options()
        
        # تحديث تبويب العرض (إن كان مبنياً)
        if hasattr(self, 'view_table_container'):
            self.load_view_table()

        self.page.update()

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 2. عرض الفترات المغلقة
    # ============================================================
    def build_view_tab(self):
        self.view_table_container = ft.Container()
        self.load_view_table()
        
        return ft.Column([
            ft.Text("الفترات المغلقة حالياً", color=ACCENT_RED, size=20, weight=ft.FontWeight.BOLD),
            self.view_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_view_table(self):
        periods = get_closed_periods()
        if periods:
            df = pd.DataFrame(periods)
            df = df.drop("id", axis=1) if "id" in df.columns else df
            self.view_table_container.content = temp_data_table(df)
        else:
            self.view_table_container.content = ft.Text("لا توجد فترات مغلقة", color=TEXT_SECONDARY)
