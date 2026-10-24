# ui_flet/pages/inventory.py
import flet as ft
import pandas as pd
from services.inventory_service import (
    get_all_products, add_product, record_stock_movement,
    get_stock_movements, get_low_stock_products,
    get_products_for_select, get_product_quantity,
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

class InventoryPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("📦 إدارة المخزون", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة المنتجات وحركات المخزون وتنبيهات النقص", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📋 المنتجات", content=self.build_products_tab()),
                ft.Tab(text="➕ إضافة منتج", content=self.build_add_product_tab()),
                ft.Tab(text="🔄 حركة المخزون", content=self.build_movement_tab()),
                ft.Tab(text="⚠️ تنبيهات النقص", content=self.build_low_stock_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. المنتجات
    # ============================================================
    def build_products_tab(self):
        self.cat_filter_dd = ft.Dropdown(label="الفئة", expand=True)
        self.products_table_container = ft.Container()
        self.products_count_text = ft.Text("", color=TEXT_SECONDARY, size=12)
        self.load_products()
        
        return ft.Column([
            ft.Text("جميع المنتجات", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.cat_filter_dd,
            self.products_table_container,
            self.products_count_text
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    def load_products(self):
        products = get_all_products()
        if products:
            df = pd.DataFrame(products)
            categories = ["الكل"] + sorted(set(p.get("category") or "—" for p in products))
            self.cat_filter_dd.options = [ft.dropdown.Option(c) for c in categories]
            if not self.cat_filter_dd.value: self.cat_filter_dd.value = "الكل"
            self.cat_filter_dd.on_change = lambda e: self.filter_products(products)
            self.filter_products(products)
        else:
            self.products_table_container.content = ft.Text("لا توجد منتجات حالياً", color=TEXT_SECONDARY)
            self.products_count_text.value = ""

    def filter_products(self, products):
        df = pd.DataFrame(products)
        cat_filter = self.cat_filter_dd.value
        if cat_filter and cat_filter != "الكل":
            df = df[df['category'] == cat_filter]
        
        display_cols = [c for c in ['id', 'name', 'barcode', 'category', 'purchase_price', 'selling_price', 'quantity', 'reorder_level'] if c in df.columns]
        self.products_table_container.content = temp_data_table(df[display_cols])
        self.products_count_text.value = f"📊 إجمالي المنتجات: {len(df)} من {len(products)}"
        self.page.update()

    # ============================================================
    # 2. إضافة منتج
    # ============================================================
    def build_add_product_tab(self):
        self.p_name = ft.TextField(label="اسم المنتج *", expand=True)
        self.p_barcode = ft.TextField(label="الباركود (اختياري)", expand=True)
        self.p_category = ft.TextField(label="الفئة", value="عام", expand=True)
        self.p_purchase = ft.TextField(label="سعر الشراء", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.p_selling = ft.TextField(label="سعر البيع", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.p_qty = ft.TextField(label="الكمية الابتدائية", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.p_reorder = ft.TextField(label="حد إعادة الطلب", value="10", keyboard_type=ft.KeyboardType.NUMBER, expand=True)

        def add_prod(e):
            if not self.p_name.value or not self.p_name.value.strip():
                self.show_snackbar("اسم المنتج مطلوب", ACCENT_RED); return
            try:
                pp = float(self.p_purchase.value or 0)
                sp = float(self.p_selling.value or 0)
                qty = float(self.p_qty.value or 0)
                reorder = float(self.p_reorder.value or 10)
            except ValueError:
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return

            success, error = add_product(
                self.p_name.value.strip(), self.p_barcode.value, self.p_category.value,
                pp, sp, qty, reorder, username="admin"
            )
            if success:
                self.show_snackbar(f"✅ تمت إضافة «{self.p_name.value}»", ACCENT_GREEN)
                self.p_name.value = ""; self.p_barcode.value = ""; self.p_purchase.value = "0"
                self.p_selling.value = "0"; self.p_qty.value = "0"; self.p_reorder.value = "10"
                self.load_products()
            else:
                self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)

        return ft.Column([
            ft.Text("إضافة منتج جديد", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.p_name, self.p_barcode]),
            self.p_category,
            ft.Row([self.p_purchase, self.p_selling]),
            ft.Row([self.p_qty, self.p_reorder]),
            ft.ElevatedButton("💾 إضافة المنتج", on_click=add_prod, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 3. حركة المخزون
    # ============================================================
    def build_movement_tab(self):
        products_list = get_products_for_select()
        if not products_list:
            return ft.Text("⚠️ لا توجد منتجات — أضف منتجاً أولاً", color=ACCENT_ORANGE)

        self.move_product_dd = ft.Dropdown(
            label="اختر المنتج",
            options=[ft.dropdown.Option(key=str(p['id']), text=p['name']) for p in products_list],
            value=str(products_list[0]['id']), expand=True
        )
        self.move_product_dd.on_change = lambda e: self.update_qty_card()

        self.qty_card_container = ft.Container()
        self.move_type_radio = ft.RadioGroup(
            content=ft.Row([ft.Radio(value="in", label="داخل (إضافة)"), ft.Radio(value="out", label="خارج (صرف)")]),
            value="in", on_change=lambda e: self.update_qty_card()
        )
        self.move_qty = ft.TextField(label="الكمية", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.move_qty.on_change = lambda e: self.update_qty_card()
        self.move_ref = ft.TextField(label="المرجع (رقم الفاتورة أو الإذن)", expand=True)
        self.move_status = ft.Text("", color=TEXT_SECONDARY)

        # الجدول السفلي
        self.movements_table_container = ft.Container()

        def save_movement(e):
            if not self.move_product_dd.value: return
            try: qty = float(self.move_qty.value or 0)
            except ValueError: 
                self.show_snackbar("كمية غير صالحة", ACCENT_RED); return
            if qty <= 0: 
                self.show_snackbar("الكمية يجب أن تكون أكبر من صفر", ACCENT_RED); return

            prod_id = int(self.move_product_dd.value)
            prod_name = next(p['name'] for p in products_list if str(p['id']) == self.move_product_dd.value)
            
            # التحقق من الرصيد للصرف
            if self.move_type_radio.value == "out":
                current_qty = get_product_quantity(prod_id) or 0.0
                if qty > current_qty + 0.0001:
                    self.show_snackbar(f"لا يمكن صرف {qty:,.2f} — المتاح: {current_qty:,.2f}", ACCENT_RED); return

            move_type = "داخل (إضافة)" if self.move_type_radio.value == "in" else "خارج (صرف)"
            success, error = record_stock_movement(prod_id, prod_name, move_type, qty, self.move_ref.value, username="admin")
            if success:
                self.show_snackbar("✅ تم تسجيل الحركة", ACCENT_GREEN)
                self.move_qty.value = "0"; self.move_ref.value = ""
                self.load_movements_table(); self.update_qty_card()
            else:
                self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)

        self.update_qty_card()
        self.load_movements_table()

        return ft.Column([
            ft.Text("تسجيل حركة مخزون", color=ACCENT_ORANGE, size=20, weight=ft.FontWeight.BOLD),
            self.move_product_dd,
            self.qty_card_container,
            ft.Row([self.move_type_radio]),
            ft.Row([self.move_qty, self.move_ref]),
            self.move_status,
            ft.ElevatedButton("💾 تسجيل الحركة", on_click=save_movement, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📋 سجل حركات المخزون", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            self.movements_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def update_qty_card(self):
        if not self.move_product_dd.value: return
        prod_id = int(self.move_product_dd.value)
        products_all = get_all_products()
        prod = next((p for p in products_all if p['id'] == prod_id), None)
        if not prod: return
        
        current_qty = get_product_quantity(prod_id) or 0.0
        reorder = float(prod.get('reorder_level', 0) or 0)
        
        if current_qty <= 0:
            color, icon, note = ACCENT_RED, "🔴", "نفد المخزون!"
        elif current_qty < reorder:
            color, icon, note = ACCENT_ORANGE, "🟡", f"أقل من حد الطلب ({reorder:g})"
        else:
            color, icon, note = ACCENT_GREEN, "🟢", "متوفر"

        self.qty_card_container.content = ft.Container(
            content=ft.Text(f"{icon} {prod['name']}: {current_qty:,.2f} — {note}", color=color, size=13, weight=ft.FontWeight.BOLD),
            bgcolor=ft.colors.with_opacity(0.1, color), border_radius=8, padding=10
        )

        # التحقق من النقص
        try: move_qty = float(self.move_qty.value or 0)
        except ValueError: move_qty = 0.0
        
        if self.move_type_radio.value == "out" and move_qty > current_qty + 0.0001:
            shortage = move_qty - current_qty
            self.move_status.value = f"❌ لا يمكن صرف {move_qty:,.2f} — المتاح: {current_qty:,.2f} (نقص: {shortage:,.2f})"
            self.move_status.color = ACCENT_RED
        elif self.move_type_radio.value == "out" and move_qty > 0:
            remaining = current_qty - move_qty
            self.move_status.value = f"✅ سيتبقى بعد الصرف: {remaining:,.2f}"
            self.move_status.color = ACCENT_GREEN
        else:
            self.move_status.value = ""
        
        self.page.update()

    def load_movements_table(self):
        movements = get_stock_movements()
        if movements:
            df = pd.DataFrame(movements)
            if 'type' in df.columns:
                df['type'] = df['type'].apply(lambda x: "🟢 داخل" if x == "in" else "🔴 خارج")
            self.movements_table_container.content = temp_data_table(df)
        else:
            self.movements_table_container.content = ft.Text("لا توجد حركات مخزون بعد", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 4. تنبيهات النقص
    # ============================================================
    def build_low_stock_tab(self):
        self.low_stock_container = ft.Container()
        self.load_low_stock()
        
        return ft.Column([
            ft.Text("⚠️ منتجات تحت الحد الأدنى", color=ACCENT_RED, size=20, weight=ft.FontWeight.BOLD),
            self.low_stock_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_low_stock(self):
        low_stock = get_low_stock_products()
        if low_stock:
            df = pd.DataFrame(low_stock)
            if 'quantity' in df.columns and 'reorder_level' in df.columns:
                df['النقص'] = df['reorder_level'].astype(float) - df['quantity'].astype(float)
            self.low_stock_container.content = ft.Column([
                ft.Text(f"يوجد {len(low_stock)} منتج تحت حد الطلب:", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
                temp_data_table(df)
            ])
        else:
            self.low_stock_container.content = ft.Text("✅ جميع المنتجات بمستويات آمنة", color=ACCENT_GREEN)
        self.page.update()
