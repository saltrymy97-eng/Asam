# ui_flet/pages/inventory_adjustment.py
import flet as ft
import pandas as pd
from datetime import date
from services.inventory_adjustment_service import (
    create_adjustments_table, get_products_for_adjustment,
    create_adjustment, get_adjustments,
)
from services.fifo_service import get_fifo_cost
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

try:
    from flet_plotly import PlotlyChart
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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

class InventoryAdjustmentPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        try: create_adjustments_table()
        except Exception as e: print(f"Adj init: {e}")

        self.header = ft.Text("📦 التسويات المخزنية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("الجرد الفعلي واكتشاف العجز والفائض مع التكامل المحاسبي", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📝 تسجيل جرد", content=self.build_add_tab()),
                ft.Tab(text="📋 سجل التسويات", content=self.build_history_tab()),
                ft.Tab(text="📊 تحليل الانحرافات", content=self.build_analysis_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def kpi_card(self, title, value, icon, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=24, color=color),
                ft.Text(str(value), color=color, size=18, weight=ft.FontWeight.BOLD),
                ft.Text(title, color=TEXT_SECONDARY, size=11)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

    # ============================================================
    # 1. تسجيل جرد
    # ============================================================
    def build_add_tab(self):
        products = get_products_for_adjustment()
        if not products:
            return ft.Text("لا توجد منتجات في المخزون", color=TEXT_SECONDARY)

        self.products = products
        self.prod_dd = ft.Dropdown(
            label="اختر المنتج",
            options=[ft.dropdown.Option(key=str(p['id']), text=f"{p['name']} (النظام: {p['quantity']})") for p in products],
            value=str(products[0]['id']), expand=True
        )
        self.prod_dd.on_change = lambda e: self.on_product_change()

        self.prod_info = ft.Text("", color=TEXT_SECONDARY, size=12)
        self.actual_qty = ft.TextField(label="الكمية الفعلية (بعد الجرد)", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        self.diff_text = ft.Text("", color=TEXT_SECONDARY, size=14, weight=ft.FontWeight.BOLD)
        self.unit_cost_input = ft.TextField(label="تكلفة الوحدة (اختياري — اتركها 0 للحساب التلقائي)", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.adj_date = ft.TextField(label="تاريخ التسوية", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.reason_input = ft.TextField(label="سبب التسوية", hint_text="مثال: جرد سنوي، تلف، سرقة...", expand=True)
        self.ref_input = ft.TextField(label="المرجع (رقم محضر الجرد)", expand=True)
        self.cost_preview = ft.Text("", color=ACCENT_ORANGE, size=13, weight=ft.FontWeight.BOLD)
        self.save_btn = ft.ElevatedButton("💾 حفظ التسوية", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=self.save_adjustment, disabled=True)

        self.actual_qty.on_change = lambda e: self.on_qty_change()
        self.unit_cost_input.on_change = lambda e: self.on_qty_change()

        self.on_product_change()

        return ft.Column([
            ft.Text("تسجيل الجرد الفعلي", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            self.prod_dd,
            self.prod_info,
            ft.Divider(color=GLASS_BORDER),
            self.actual_qty,
            self.diff_text,
            ft.Row([self.unit_cost_input, self.adj_date]),
            self.reason_input, self.ref_input,
            self.cost_preview,
            self.save_btn
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    def on_product_change(self):
        if not self.prod_dd.value: return
        prod = next(p for p in self.products if str(p['id']) == self.prod_dd.value)
        self.current_prod = prod
        self.prod_info.value = f"الكمية في النظام: {prod['quantity']} | سعر البيع: {prod['selling_price']} | سعر الشراء: {prod['purchase_price']}"
        self.actual_qty.value = str(prod['quantity'])
        self.on_qty_change()

    def on_qty_change(self):
        if not hasattr(self, 'current_prod'): return
        prod = self.current_prod
        try: actual = float(self.actual_qty.value or 0)
        except ValueError: actual = 0.0
        diff = actual - float(prod['quantity'])

        if diff > 0:
            self.diff_text.value = f"✅ فائض: +{diff:.2f} وحدة"
            self.diff_text.color = ACCENT_GREEN
        elif diff < 0:
            self.diff_text.value = f"⚠️ عجز: {diff:.2f} وحدة"
            self.diff_text.color = ACCENT_RED
        else:
            self.diff_text.value = "📊 الكمية متطابقة"
            self.diff_text.color = ACCENT_BLUE

        # حساب التكلفة التقديرية
        if diff == 0:
            self.cost_preview.value = ""
            self.save_btn.disabled = True
        else:
            if diff > 0:
                try: unit_input = float(self.unit_cost_input.value or 0)
                except ValueError: unit_input = 0.0
                effective = unit_input if unit_input > 0 else (prod['purchase_price'] or 0)
                total = abs(diff) * effective
                self.cost_preview.value = f"التكلفة التقديرية: {total:,.2f} ({abs(diff):g} × {effective:,.2f})"
                self.save_btn.disabled = False
            else:
                fifo_cost = get_fifo_cost(prod['id'], abs(diff))
                if fifo_cost is not None:
                    avg = fifo_cost / abs(diff) if abs(diff) > 0 else 0
                    self.cost_preview.value = f"تكلفة FIFO الفعلية: {fifo_cost:,.2f} ({abs(diff):g} × {avg:,.2f} — متوسط FIFO)"
                    self.save_btn.disabled = False
                else:
                    self.cost_preview.value = "⚠️ لا يمكن تحديد التكلفة — لا توجد دفعات FIFO كافية"
                    self.save_btn.disabled = True
        self.page.update()

    def save_adjustment(self, e):
        if not hasattr(self, 'current_prod'): return
        prod = self.current_prod
        try: actual = float(self.actual_qty.value or 0)
        except ValueError: actual = 0.0
        diff = actual - float(prod['quantity'])
        if diff == 0: return

        try: unit_input = float(self.unit_cost_input.value or 0)
        except ValueError: unit_input = 0.0
        unit_cost_to_send = unit_input if unit_input > 0 else None

        adj_id, err = create_adjustment(
            product_id=prod['id'], expected_qty=prod['quantity'],
            actual_qty=actual, unit_cost=unit_cost_to_send,
            reason=self.reason_input.value, reference=self.ref_input.value,
            created_by="admin", adjustment_date=self.adj_date.value
        )
        if err:
            self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
        else:
            self.show_snackbar(f"✅ تم تسجيل التسوية رقم {adj_id} مع القيد المحاسبي", ACCENT_GREEN)
            self.reason_input.value = ""; self.ref_input.value = ""
            self.on_product_change()

    # ============================================================
    # 2. سجل التسويات
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.kpi_row = ft.Row(spacing=10)
        self.load_history()
        
        return ft.Column([
            ft.Text("📋 سجل التسويات المخزنية", color=ACCENT_PURPLE, size=18, weight=ft.FontWeight.BOLD),
            self.history_container,
            ft.Divider(color=GLASS_BORDER),
            self.kpi_row
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        adjustments = get_adjustments()
        if adjustments:
            df = pd.DataFrame(adjustments)
            df['النوع'] = df['difference'].apply(lambda x: '🟢 فائض' if x > 0 else '🔴 عجز')
            df['الفرق'] = df['difference'].apply(lambda x: f"+{x:.2f}" if x > 0 else f"{x:.2f}")
            
            df_display = df.rename(columns={'id': 'الرقم', 'date': 'التاريخ', 'product_name': 'المنتج', 'expected_qty': 'المتوقعة', 'actual_qty': 'الفعلية', 'unit_cost': 'تكلفة الوحدة', 'total_cost': 'الإجمالي', 'reason': 'السبب', 'reference': 'المرجع'})
            cols = [c for c in ['الرقم', 'التاريخ', 'النوع', 'المنتج', 'المتوقعة', 'الفعلية', 'الفرق', 'تكلفة الوحدة', 'الإجمالي', 'السبب', 'المرجع'] if c in df_display.columns]
            self.history_container.content = temp_data_table(df_display[cols])

            total_gain = sum(float(r['total_cost'] or 0) for _, r in df.iterrows() if float(r['difference'] or 0) > 0)
            total_loss = sum(float(r['total_cost'] or 0) for _, r in df.iterrows() if float(r['difference'] or 0) < 0)
            
            self.kpi_row.controls = [
                self.kpi_card("إجمالي التسويات", str(len(adjustments)), "📋", ACCENT_BLUE),
                self.kpi_card("قيمة الفائض", f"{total_gain:,.2f}", "🟢", ACCENT_GREEN),
                self.kpi_card("قيمة العجز", f"{total_loss:,.2f}", "🔴", ACCENT_RED),
            ]
        else:
            self.history_container.content = ft.Text("لا توجد تسويات مسجلة بعد", color=TEXT_SECONDARY)
            self.kpi_row.controls = []
        self.page.update()

    # ============================================================
    # 3. تحليل الانحرافات
    # ============================================================
    def build_analysis_tab(self):
        self.charts_container = ft.Column(spacing=15)
        self.load_charts()
        return ft.Column([
            ft.Text("📊 تحليل الانحرافات المخزنية", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            self.charts_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_charts(self):
        if not PLOTLY_AVAILABLE:
            self.charts_container.controls = [ft.Text("⚠️ لتثبيت الرسوم البيانية: pip install flet-plotly", color=ACCENT_ORANGE)]
            self.page.update(); return

        adjustments = get_adjustments()
        if not adjustments:
            self.charts_container.controls = [ft.Text("لا توجد بيانات كافية للتحليل", color=TEXT_SECONDARY)]
            self.page.update(); return

        df = pd.DataFrame(adjustments)
        
        # رسم 1: قيمة الانحرافات حسب المنتج
        df_chart = df.groupby('product_name')['total_cost'].sum().reset_index()
        df_chart['type'] = df.groupby('product_name')['difference'].sum().apply(lambda x: 'فائض' if x > 0 else 'عجز').values
        fig = px.bar(df_chart, x='product_name', y='total_cost', color='type', color_discrete_map={'فائض': '#10B981', 'عجز': '#EF4444'}, title="قيمة الانحرافات حسب المنتج")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=300, margin=dict(t=30, b=20, l=20, r=20))
        
        # رسم 2: توزيع الانحرافات
        gain = df[df['difference'] > 0]['total_cost'].sum()
        loss = abs(df[df['difference'] < 0]['total_cost'].sum())
        pie_data = pd.DataFrame({'النوع': ['فائض', 'عجز'], 'القيمة': [gain, loss]})
        fig2 = px.pie(pie_data, names='النوع', values='القيمة', color='النوع', color_discrete_map={'فائض': '#10B981', 'عجز': '#EF4444'}, hole=0.5, title="توزيع الانحرافات")
        fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=300, margin=dict(t=30, b=20, l=20, r=20))

        self.charts_container.controls = [
            ft.Container(content=PlotlyChart(fig, expand=True), height=350),
            ft.Container(content=PlotlyChart(fig2, expand=True), height=350)
        ]
        self.page.update()
