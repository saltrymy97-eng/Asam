# ui_flet/pages/fifo.py
import flet as ft
import pandas as pd
from datetime import date
from services.fifo_service import (
    create_fifo_tables, add_batch, get_available_batches,
    consume_fifo, get_products_for_select,
)
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

class FifoPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        try: create_fifo_tables()
        except Exception as e: print(f"FIFO init: {e}")

        self.header = ft.Text("📦 وحدة المخزون (FIFO)", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("نظام متقدم لإدارة وتقييم المخزون المالي بذكاء ودقة", color=TEXT_SECONDARY, size=14)

        self.products = get_products_for_select()
        self.product_dict = {str(p['id']): p['name'] for p in self.products}

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📥 تسجيل دفعة شراء", content=self.build_add_batch_tab()),
                ft.Tab(text="📤 صرف مخزني", content=self.build_consume_tab()),
                ft.Tab(text="📊 تفاصيل الدفعات", content=self.build_view_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. تسجيل دفعة شراء
    # ============================================================
    def build_add_batch_tab(self):
        if not self.products:
            return ft.Text("⚠️ يرجى إضافة منتجات إلى النظام للبدء.", color=ACCENT_ORANGE)

        self.batch_prod = ft.Dropdown(
            label="تحديد المنتج",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in self.product_dict.items()],
            value=list(self.product_dict.keys())[0], expand=True
        )
        self.batch_qty = ft.TextField(label="الكمية الواردة", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.batch_cost = ft.TextField(label="تكلفة الوحدة", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.batch_date = ft.TextField(label="تاريخ الدفعة", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.batch_ref = ft.TextField(label="رقم المرجع (اختياري)", expand=True)

        def save_batch(e):
            try:
                qty = float(self.batch_qty.value or 0)
                cost = float(self.batch_cost.value or 0)
            except ValueError:
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return
            if qty <= 0 or cost <= 0:
                self.show_snackbar("الكمية والتكلفة يجب أن تكون أكبر من الصفر", ACCENT_RED); return
            
            success, error = add_batch(
                int(self.batch_prod.value), qty, cost, self.batch_date.value, self.batch_ref.value
            )
            if success:
                self.show_snackbar("✅ تمت العملية بنجاح", ACCENT_GREEN)
                self.batch_qty.value = "0"; self.batch_cost.value = "0"; self.batch_ref.value = ""
            else:
                self.show_snackbar(f"❌ خطأ: {error}", ACCENT_RED)

        return ft.Column([
            ft.Text("إضافة رصيد وارد جديد", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD),
            self.batch_prod,
            ft.Row([self.batch_qty, self.batch_cost]),
            ft.Row([self.batch_date, self.batch_ref]),
            ft.ElevatedButton("💾 حفظ الدفعة في المستودع", on_click=save_batch, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 2. صرف مخزني
    # ============================================================
    def build_consume_tab(self):
        if not self.products:
            return ft.Text("⚠️ يرجى إضافة منتجات إلى النظام.", color=ACCENT_ORANGE)

        self.cons_prod = ft.Dropdown(
            label="تحديد المنتج للصرف",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in self.product_dict.items()],
            value=list(self.product_dict.keys())[0], expand=True
        )
        self.cons_prod.on_change = lambda e: self.update_available()
        
        self.available_text = ft.Text("", color=ACCENT_BLUE, size=13, weight=ft.FontWeight.BOLD)
        self.cons_qty = ft.TextField(label="الكمية المطلوب صرفها", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.cons_date = ft.TextField(label="تاريخ الصرف", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.cons_ref = ft.TextField(label="مرجع الصرف (رقم إذن الصرف)", expand=True)
        
        self.update_available()

        def do_consume(e):
            try: qty = float(self.cons_qty.value or 0)
            except ValueError: 
                self.show_snackbar("كمية غير صالحة", ACCENT_RED); return
            if qty <= 0:
                self.show_snackbar("الكمية يجب أن تكون أكبر من صفر", ACCENT_RED); return
            
            available = sum(b["remaining"] for b in get_available_batches(int(self.cons_prod.value)))
            if qty > available:
                self.show_snackbar(f"الكمية المطلوبة تتجاوز الرصيد المتاح ({available:,.2f})", ACCENT_RED); return

            total_cost, error = consume_fifo(
                product_id=int(self.cons_prod.value), quantity=qty,
                consumption_date=self.cons_date.value, reference=self.cons_ref.value
            )
            if error:
                self.show_snackbar(f"❌ خطأ: {error}", ACCENT_RED)
            else:
                self.show_snackbar(f"✅ تم الصرف. تكلفة البضاعة المنصرفة: {total_cost:,.2f}", ACCENT_GREEN)
                self.cons_qty.value = "0"; self.cons_ref.value = ""
                self.update_available()

        return ft.Column([
            ft.Text("تسجيل استهلاك / صرف", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            self.cons_prod,
            self.available_text,
            ft.Row([self.cons_qty, self.cons_date]),
            self.cons_ref,
            ft.ElevatedButton("✅ اعتماد الصرف حسب (FIFO)", on_click=do_consume, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def update_available(self):
        if not self.cons_prod.value: return
        available = sum(b["remaining"] for b in get_available_batches(int(self.cons_prod.value)))
        self.available_text.value = f"📦 الرصيد المتاح حالياً: {available:,.2f} وحدة"
        self.page.update()

    # ============================================================
    # 3. تفاصيل الدفعات
    # ============================================================
    def build_view_tab(self):
        if not self.products:
            return ft.Text("⚠️ يرجى إضافة منتجات إلى النظام.", color=ACCENT_ORANGE)

        self.view_prod = ft.Dropdown(
            label="استعراض منتج معين",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in self.product_dict.items()],
            value=list(self.product_dict.keys())[0], expand=True
        )
        self.view_prod.on_change = lambda e: self.load_batches()
        
        self.batches_container = ft.Container()
        self.total_text = ft.Text("", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD)
        
        self.load_batches()

        return ft.Column([
            ft.Text("تقييم الدفعات المتبقية بالمخزن", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            self.view_prod,
            self.batches_container,
            self.total_text
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_batches(self):
        if not self.view_prod.value: return
        batches = get_available_batches(int(self.view_prod.value))
        if batches:
            df = pd.DataFrame(batches)
            df = df.rename(columns={"batch_date": "تاريخ الدفعة", "remaining": "الرصيد المتبقي", "unit_cost": "تكلفة الوحدة", "reference": "المرجع"})
            df["إجمالي القيمة"] = df["الرصيد المتبقي"] * df["تكلفة الوحدة"]
            
            total_cost = df["إجمالي القيمة"].sum()
            self.batches_container.content = temp_data_table(df[["تاريخ الدفعة", "الرصيد المتبقي", "تكلفة الوحدة", "إجمالي القيمة", "المرجع"]])
            self.total_text.value = f"💰 إجمالي القيمة الدفترية للمخزون: {total_cost:,.2f}"
        else:
            self.batches_container.content = ft.Text("لا توجد أرصدة حالية لهذا المنتج.", color=TEXT_SECONDARY)
            self.total_text.value = ""
        self.page.update()
