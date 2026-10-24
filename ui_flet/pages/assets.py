# ui_flet/pages/assets.py
import flet as ft
import pandas as pd
from datetime import date
from services.assets_service import (
    create_assets_tables, add_asset, get_all_assets, run_depreciation,
    run_all_depreciations, get_depreciation_history, get_assets_summary,
    update_asset_depreciation,
)
from services.expenses_service import get_payment_accounts
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

CY = "#06B6D4"

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

def _format_account_label(acc):
    icon = "💵" if acc["type"] == "cash" else "🏦"
    return f"{icon} {acc['name']} ({acc['currency']}) — الرصيد: {acc['balance']:,.2f}"

class AssetsPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.selected_acc_for_dep = None

        try: create_assets_tables()
        except Exception as e: print(f"Assets init: {e}")

        self.header = ft.Text("🏢 الأصول الثابتة والإهلاكات", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة الأصول الثابتة وجدولة الإهلاكات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📋 الأصول", content=self.build_list_tab()),
                ft.Tab(text="➕ إضافة أصل", content=self.build_add_tab()),
                ft.Tab(text="📉 تشغيل الإهلاك", content=self.build_dep_tab()),
                ft.Tab(text="📊 لوحة التحكم", content=self.build_dashboard_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def kpi_card(self, icon, title, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=24),
                ft.Text(title, color=TEXT_SECONDARY, size=11),
                ft.Text(str(value), color=color, size=16, weight=ft.FontWeight.BOLD)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=12, expand=True
        )

    # ============================================================
    # 1. قائمة الأصول + تعديل الإهلاك
    # ============================================================
    def build_list_tab(self):
        self.assets_container = ft.Container()
        self.edit_container = ft.Container()
        self.history_container = ft.Container()
        
        self.load_assets()
        
        return ft.Column([
            ft.Text("قائمة الأصول الثابتة", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD),
            self.assets_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("✏️ تعديل إهلاك أصل موجود", color=ACCENT_ORANGE, size=16, weight=ft.FontWeight.BOLD),
            self.edit_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("سجل الإهلاكات", color=ACCENT_PURPLE, size=16, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_assets(self):
        assets = get_all_assets()
        if assets:
            self.assets_container.content = temp_data_table(pd.DataFrame(assets))
            self.load_edit_form(assets)
        else:
            self.assets_container.content = ft.Text("لا توجد أصول ثابتة بعد", color=TEXT_SECONDARY)
        self.load_history()
        self.page.update()

    def load_edit_form(self, assets):
        self.edit_asset_dd = ft.Dropdown(
            label="اختر الأصل",
            options=[ft.dropdown.Option(key=str(a['id']), text=f"#{a['id']} — {a['name']} (إهلاك: {a.get('monthly_depreciation') or 0:,.2f})") for a in assets],
            value=str(assets[0]['id']), expand=True
        )
        self.edit_asset_dd.on_change = lambda e: self.load_edit_data(assets)

        self.edit_mode_radio = ft.RadioGroup(
            content=ft.Row([ft.Radio(value="life", label="📅 بالعمر الإنتاجي"), ft.Radio(value="rate", label="📊 بنسبة سنوية %"), ft.Radio(value="manual", label="💵 بقيمة يدوية")]),
            value="life", on_change=lambda e: self.toggle_edit_fields()
        )
        self.edit_life = ft.TextField(label="العمر الإنتاجي (سنوات)", value="5", keyboard_type=ft.KeyboardType.NUMBER, visible=True)
        self.edit_rate = ft.TextField(label="النسبة السنوية (%)", value="20", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        self.edit_manual = ft.TextField(label="القيمة الشهرية", value="100", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        
        self.edit_info = ft.Text("", color=TEXT_SECONDARY, size=12)

        def save_edit(e):
            asset_id = int(self.edit_asset_dd.value)
            try:
                if self.edit_mode_radio.value == "life":
                    life = int(self.edit_life.value)
                    ok, msg = update_asset_depreciation(asset_id, useful_life_years=life, updated_by="admin")
                elif self.edit_mode_radio.value == "rate":
                    rate = float(self.edit_rate.value)
                    ok, msg = update_asset_depreciation(asset_id, annual_depreciation_rate=rate, updated_by="admin")
                else:
                    manual = float(self.edit_manual.value)
                    ok, msg = update_asset_depreciation(asset_id, manual_monthly_depreciation=manual, updated_by="admin")
            except ValueError:
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return

            if ok:
                self.show_snackbar(f"✅ {msg}", ACCENT_GREEN)
                self.load_assets()
            else:
                self.show_snackbar(f"❌ {msg}", ACCENT_RED)

        self.edit_save_btn = ft.ElevatedButton("💾 حفظ التعديل", on_click=save_edit, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)

        self.edit_container.content = ft.Column([
            self.edit_asset_dd,
            self.edit_info,
            self.edit_mode_radio,
            self.edit_life, self.edit_rate, self.edit_manual,
            self.edit_save_btn
        ], spacing=10)
        self.load_edit_data(assets)

    def load_edit_data(self, assets):
        asset = next((a for a in assets if str(a['id']) == self.edit_asset_dd.value), None)
        if asset:
            self.edit_info.value = f"النسبة الحالية: {asset.get('annual_depreciation_rate') or 0:.2f}% | الإهلاك الشهري: {asset.get('monthly_depreciation') or 0:,.2f} | العمر: {asset.get('useful_life_years') or 0} سنة"
            self.edit_life.value = str(asset.get('useful_life_years') or 5)
            self.edit_rate.value = str(asset.get('annual_depreciation_rate') or 20)
            self.edit_manual.value = str(asset.get('monthly_depreciation') or 100)
            self.page.update()

    def toggle_edit_fields(self):
        self.edit_life.visible = self.edit_mode_radio.value == "life"
        self.edit_rate.visible = self.edit_mode_radio.value == "rate"
        self.edit_manual.visible = self.edit_mode_radio.value == "manual"
        self.page.update()

    def load_history(self):
        history = get_depreciation_history()
        if history:
            self.history_container.content = temp_data_table(pd.DataFrame(history))
        else:
            self.history_container.content = ft.Text("لا توجد إهلاكات مسجلة بعد", color=TEXT_SECONDARY)

    # ============================================================
    # 2. إضافة أصل
    # ============================================================
    def build_add_tab(self):
        self.a_name = ft.TextField(label="اسم الأصل", expand=True)
        self.a_category = ft.Dropdown(label="الفئة", options=[ft.dropdown.Option(c) for c in ["أثاث ومعدات", "مباني", "آلات", "مركبات", "أجهزة كمبيوتر", "أخرى"]], value="أثاث ومعدات", expand=True)
        self.a_date = ft.TextField(label="تاريخ الشراء", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.a_cost = ft.TextField(label="تكلفة الشراء", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.a_salvage = ft.TextField(label="قيمة الخردة", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.a_method = ft.Dropdown(label="طريقة الإهلاك", options=[ft.dropdown.Option("قسط ثابت"), ft.dropdown.Option("متناقص")], value="قسط ثابت", expand=True)
        self.a_notes = ft.TextField(label="ملاحظات", multiline=True, min_lines=2)
        
        self.dep_mode_radio = ft.RadioGroup(
            content=ft.Row([ft.Radio(value="life", label="📅 العمر الإنتاجي"), ft.Radio(value="rate", label="📊 نسبة سنوية %"), ft.Radio(value="manual", label="💵 قيمة يدوية")]),
            value="life", on_change=lambda e: self.toggle_add_fields()
        )
        self.a_life = ft.TextField(label="العمر الإنتاجي (سنوات)", value="5", keyboard_type=ft.KeyboardType.NUMBER, visible=True)
        self.a_rate = ft.TextField(label="النسبة السنوية (%)", value="20", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        self.a_manual = ft.TextField(label="القيمة الشهرية", value="100", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        self.a_hint = ft.Text("", color=ACCENT_BLUE, size=12)

        for inp in [self.a_cost, self.a_salvage, self.a_life, self.a_rate, self.a_manual]:
            inp.on_change = lambda e: self.update_add_hint()

        self.a_payment_radio = ft.RadioGroup(
            content=ft.Row([ft.Radio(value="bank", label="🏦 بنكي"), ft.Radio(value="cash", label="💵 نقدي"), ft.Radio(value="none", label="بدون قيد")]),
            value="bank", on_change=lambda e: self.on_payment_change()
        )
        self.a_account_dd = ft.Dropdown(label="من أي حساب تم الدفع؟", expand=True)
        self.a_balance_text = ft.Text("", color=TEXT_SECONDARY, size=12)

        self.on_payment_change()
        self.update_add_hint()

        def save_asset(e):
            try:
                cost = float(self.a_cost.value or 0)
                salvage = float(self.a_salvage.value or 0)
            except ValueError:
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return
            if not self.a_name.value or cost <= 0:
                self.show_snackbar("الاسم والتكلفة مطلوبان", ACCENT_RED); return

            payment_code = None
            payment_method = None
            if self.a_payment_radio.value != "none":
                acc = get_payment_accounts()
                sel = next((x for x in acc if str(x['id']) == self.a_account_dd.value), None)
                if sel:
                    payment_code = sel['code']; payment_method = sel['type']
                    if cost > sel['balance']:
                        self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {sel['balance']:,.2f}", ACCENT_RED); return

            life = 5; rate = 0.0; manual = 0.0
            try:
                if self.dep_mode_radio.value == "life": life = int(self.a_life.value)
                elif self.dep_mode_radio.value == "rate": rate = float(self.a_rate.value)
                else: manual = float(self.a_manual.value)
            except ValueError:
                self.show_snackbar("قيم الإهلاك غير صالحة", ACCENT_RED); return

            asset_id, err = add_asset(
                name=self.a_name.value, category=self.a_category.value,
                purchase_date=self.a_date.value, purchase_cost=cost,
                salvage_value=salvage, useful_life_years=life, method=self.a_method.value,
                notes=self.a_notes.value, payment_account_code=payment_code,
                payment_method=payment_method, created_by="admin",
                annual_depreciation_rate=rate, manual_monthly_depreciation=manual
            )
            if err:
                self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
            else:
                self.show_snackbar(f"✅ تم إضافة الأصل برقم {asset_id}", ACCENT_GREEN)
                self.a_name.value = ""; self.a_cost.value = "0"; self.a_salvage.value = "0"; self.a_notes.value = ""
                self.load_assets()

        return ft.Column([
            ft.Text("إضافة أصل ثابت جديد", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.a_name, self.a_category]),
            ft.Row([self.a_date, self.a_cost, self.a_salvage]),
            self.a_method,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📉 طريقة احتساب الإهلاك الشهري", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
            self.dep_mode_radio, self.a_life, self.a_rate, self.a_manual,
            self.a_hint,
            self.a_notes,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("💳 كيف تم شراء الأصل؟", color=ACCENT_PURPLE, weight=ft.FontWeight.BOLD),
            self.a_payment_radio, self.a_account_dd, self.a_balance_text,
            ft.ElevatedButton("💾 حفظ الأصل", on_click=save_asset, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    def toggle_add_fields(self):
        self.a_life.visible = self.dep_mode_radio.value == "life"
        self.a_rate.visible = self.dep_mode_radio.value == "rate"
        self.a_manual.visible = self.dep_mode_radio.value == "manual"
        self.update_add_hint()

    def update_add_hint(self):
        try:
            cost = float(self.a_cost.value or 0)
            salvage = float(self.a_salvage.value or 0)
        except ValueError:
            return
        if cost <= 0 or salvage >= cost:
            self.a_hint.value = ""
            self.page.update(); return

        base = cost - salvage
        if self.dep_mode_radio.value == "life":
            try: life = int(self.a_life.value)
            except ValueError: life = 1
            auto = base / (life * 12) if life > 0 else 0
            self.a_hint.value = f"💡 الإهلاك الشهري المتوقع: {auto:,.2f}"
        elif self.dep_mode_radio.value == "rate":
            try: rate = float(self.a_rate.value)
            except ValueError: rate = 0
            auto = base * (rate / 100) / 12
            self.a_hint.value = f"💡 الإهلاك الشهري المتوقع: {auto:,.2f} (سنوي: {auto * 12:,.2f})"
        else:
            try: manual = float(self.a_manual.value)
            except ValueError: manual = 1
            months = base / manual if manual > 0 else 0
            self.a_hint.value = f"💡 سيُستهلك الأصل خلال {months:,.1f} شهر (~{months/12:,.1f} سنة)"
        self.page.update()

    def on_payment_change(self):
        if self.a_payment_radio.value == "none":
            self.a_account_dd.visible = False
            self.a_balance_text.value = ""
            self.page.update(); return

        self.a_account_dd.visible = True
        accounts = get_payment_accounts()
        filtered = [a for a in accounts if a["type"] == ("bank" if self.a_payment_radio.value == "bank" else "cash")]
        self.a_account_dd.options = [ft.dropdown.Option(key=str(a['id']), text=_format_account_label(a)) for a in filtered]
        if filtered:
            self.a_account_dd.value = str(filtered[0]['id'])
            self.update_balance_text()
        self.page.update()

    def update_balance_text(self):
        try: cost = float(self.a_cost.value or 0)
        except ValueError: cost = 0.0
        accounts = get_payment_accounts()
        filtered = [a for a in accounts if a["type"] == ("bank" if self.a_payment_radio.value == "bank" else "cash")]
        acc = next((a for a in filtered if str(a['id']) == self.a_account_dd.value), None)
        if acc and cost > 0:
            if cost > acc['balance']:
                self.a_balance_text.value = f"⚠️ الرصيد غير كافٍ! المتاح: {acc['balance']:,.2f}"
                self.a_balance_text.color = ACCENT_RED
            else:
                self.a_balance_text.value = f"✅ الرصيد كافٍ — سيتبقى {acc['balance'] - cost:,.2f}"
                self.a_balance_text.color = ACCENT_GREEN
        self.page.update()

    # ============================================================
    # 3. تشغيل الإهلاك
    # ============================================================
    def build_dep_tab(self):
        self.dep_assets_container = ft.Container()
        self.dep_alert_text = ft.Text("", color=ACCENT_ORANGE, size=13)
        
        def run_all(e):
            results = run_all_depreciations()
            success_count = sum(1 for r in results if r[1])
            self.show_snackbar(f"✅ تم تشغيل الإهلاك لـ {success_count} أصل", ACCENT_GREEN)
            self.load_assets()
            self.load_dep_assets()

        self.single_asset_dd = ft.Dropdown(label="اختر أصلاً للتشغيل الفردي", expand=True)
        def run_single(e):
            if not self.single_asset_dd.value: return
            ok, msg = run_depreciation(int(self.single_asset_dd.value))
            if ok: self.show_snackbar(f"✅ {msg}", ACCENT_GREEN); self.load_assets(); self.load_dep_assets()
            else: self.show_snackbar(f"❌ {msg}", ACCENT_RED)

        self.load_dep_assets()

        return ft.Column([
            ft.Text("تشغيل الإهلاك الشهري", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            self.dep_alert_text,
            self.dep_assets_container,
            ft.Row([
                ft.ElevatedButton("🚀 تشغيل إهلاك جميع الأصول النشطة", on_click=run_all, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, expand=True),
                self.single_asset_dd,
                ft.ElevatedButton("📉 تشغيل إهلاك الأصل", on_click=run_single, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
            ], spacing=10)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_dep_assets(self):
        assets = get_all_assets()
        active = [a for a in assets if a['status'] == 'نشط' and (a.get('monthly_depreciation') or 0) > 0]
        current_month = date.today().strftime("%Y-%m")
        not_dep = [a['name'] for a in active if (a.get('last_depreciation_date') or "")[:7] != current_month]
        
        if not_dep:
            self.dep_alert_text.value = f"⚠️ {len(not_dep)} أصل لم يُهلك بعد هذا الشهر"
        elif active:
            self.dep_alert_text.value = "✅ جميع الأصول النشطة تم إهلاكها هذا الشهر"
            self.dep_alert_text.color = ACCENT_GREEN
        else:
            self.dep_alert_text.value = ""

        if active:
            df = pd.DataFrame(active)
            self.dep_assets_container.content = temp_data_table(df[['name', 'purchase_cost', 'monthly_depreciation', 'accumulated_depreciation', 'book_value']])
            self.single_asset_dd.options = [ft.dropdown.Option(key=str(a['id']), text=f"{a['name']} (إهلاك: {a.get('monthly_depreciation') or 0:,.2f})") for a in active]
            if not self.single_asset_dd.value: self.single_asset_dd.value = str(active[0]['id'])
        else:
            self.dep_assets_container.content = ft.Text("لا توجد أصول نشطة قابلة للإهلاك", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 4. لوحة التحكم
    # ============================================================
    def build_dashboard_tab(self):
        summary = get_assets_summary()
        assets = get_all_assets()
        
        cards_row = ft.Row([
            self.kpi_card("🏢", "إجمالي الأصول", summary['total_count'], ACCENT_BLUE),
            self.kpi_card("💰", "تكلفة الشراء", f"{summary['total_cost']:,.0f}", ACCENT_GREEN),
            self.kpi_card("📉", "الإهلاك المتراكم", f"{summary['total_depreciation']:,.0f}", ACCENT_ORANGE),
            self.kpi_card("📊", "القيمة الدفترية", f"{summary['total_book_value']:,.0f}", ACCENT_PURPLE),
        ], spacing=10)

        active = [a for a in assets if a['status'] == 'نشط']
        active_container = ft.Container()
        if active:
            df = pd.DataFrame(active)
            cols = [c for c in ['name', 'category', 'purchase_cost', 'monthly_depreciation', 'accumulated_depreciation', 'book_value'] if c in df.columns]
            active_container.content = temp_data_table(df[cols])
        else:
            active_container.content = ft.Text("لا توجد أصول نشطة", color=TEXT_SECONDARY)

        return ft.Column([
            cards_row,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("الأصول النشطة", color=ACCENT_GREEN, size=16, weight=ft.FontWeight.BOLD),
            active_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
