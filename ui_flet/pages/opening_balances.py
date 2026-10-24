# ui_flet/pages/opening_balances.py
import flet as ft
import pandas as pd
import math
from datetime import date
from services.opening_balances_service import (
    get_accounts_for_opening, get_products_for_opening, create_opening_balances,
)
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

def _safe_float(value, default=0.0):
    if value is None: return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f): return default
        return f
    except (ValueError, TypeError):
        return default

class OpeningBalancesPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("📋 الأرصدة الافتتاحية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("تسجيل أرصدة بداية المدة للحسابات والمخزون", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="أرصدة الحسابات", content=self.build_accounts_tab()),
                ft.Tab(text="أرصدة المخزون", content=self.build_inventory_tab()),
            ], expand=True,
        )
        
        # شريط الحفظ السفلي
        self.entry_date = ft.TextField(label="تاريخ الافتتاح", value=date.today().strftime("%Y-%m-%d"), width=200)
        self.summary_text = ft.Text("", color=TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD)
        self.save_btn = ft.ElevatedButton("💾 حفظ الأرصدة الافتتاحية", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=self.save_opening, disabled=True)
        
        bottom_bar = ft.Container(
            content=ft.Column([
                ft.Divider(color=GLASS_BORDER),
                ft.Row([self.entry_date, self.summary_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.save_btn
            ]), padding=10
        )

        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs, bottom_bar]
        self.account_balances = []
        self.inventory_items = []

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. أرصدة الحسابات
    # ============================================================
    def build_accounts_tab(self):
        accounts = get_accounts_for_opening()
        if not accounts:
            return ft.Text("لا توجد حسابات في شجرة الحسابات", color=TEXT_SECONDARY)

        self.acc_rows = []
        rows = []
        for acc in accounts:
            dr_input = ft.TextField(value="0", keyboard_type=ft.KeyboardType.NUMBER, width=100, text_align=ft.TextAlign.RIGHT)
            cr_input = ft.TextField(value="0", keyboard_type=ft.KeyboardType.NUMBER, width=100, text_align=ft.TextAlign.RIGHT)
            
            dr_input.on_change = self.recalculate_totals
            cr_input.on_change = self.recalculate_totals
            
            self.acc_rows.append({"code": acc['code'], "name": acc['name'], "dr": dr_input, "cr": cr_input})
            
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(acc['code']))),
                ft.DataCell(ft.Text(acc['name'])),
                ft.DataCell(dr_input),
                ft.DataCell(cr_input)
            ]))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("الكود")),
                ft.DataColumn(ft.Text("اسم الحساب")),
                ft.DataColumn(ft.Text("رصيد مدين")),
                ft.DataColumn(ft.Text("رصيد دائن"))
            ], rows=rows, border=ft.border.all(1, GLASS_BORDER), border_radius=10,
            heading_row_color=ft.colors.with_opacity(0.15, ft.colors.WHITE),
        )

        self.acc_totals_text = ft.Text("", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        
        return ft.Column([
            ft.Text("أرصدة الحسابات الافتتاحية", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([table], scroll=ft.ScrollMode.AUTO, expand=True),
            self.acc_totals_text
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 2. أرصدة المخزون
    # ============================================================
    def build_inventory_tab(self):
        products = get_products_for_opening()
        if not products:
            return ft.Text("لا توجد منتجات", color=TEXT_SECONDARY)

        self.inv_rows = []
        rows = []
        for p in products:
            qty_input = ft.TextField(value="0", keyboard_type=ft.KeyboardType.NUMBER, width=100, text_align=ft.TextAlign.RIGHT)
            cost_input = ft.TextField(value=str(_safe_float(p['purchase_price'], 0.0)), keyboard_type=ft.KeyboardType.NUMBER, width=100, text_align=ft.TextAlign.RIGHT)
            
            qty_input.on_change = self.recalculate_totals
            cost_input.on_change = self.recalculate_totals
            
            self.inv_rows.append({"id": p['id'], "name": p['name'], "qty": qty_input, "cost": cost_input})
            
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(p['id']))),
                ft.DataCell(ft.Text(p['name'])),
                ft.DataCell(qty_input),
                ft.DataCell(cost_input)
            ]))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("الرقم")),
                ft.DataColumn(ft.Text("اسم المنتج")),
                ft.DataColumn(ft.Text("الكمية")),
                ft.DataColumn(ft.Text("تكلفة الوحدة"))
            ], rows=rows, border=ft.border.all(1, GLASS_BORDER), border_radius=10,
            heading_row_color=ft.colors.with_opacity(0.15, ft.colors.WHITE),
        )

        self.inv_total_text = ft.Text("", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)

        return ft.Column([
            ft.Text("أرصدة المخزون الافتتاحية", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([table], scroll=ft.ScrollMode.AUTO, expand=True),
            self.inv_total_text
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # إعادة حساب المجاميع ديناميكياً
    # ============================================================
    def recalculate_totals(self, e=None):
        # 1. حساب الحسابات
        total_dr = 0.0
        total_cr = 0.0
        self.account_balances = []
        
        for row in self.acc_rows:
            dr = _safe_float(row['dr'].value)
            cr = _safe_float(row['cr'].value)
            if dr > 0 or cr > 0:
                self.account_balances.append({"code": row['code'], "name": row['name'], "debit": dr, "credit": cr})
                total_dr += dr
                total_cr += cr
        
        if hasattr(self, 'acc_totals_text'):
            self.acc_totals_text.value = f"إجمالي المدين: {total_dr:,.2f} | إجمالي الدائن: {total_cr:,.2f} | الفرق: {total_dr - total_cr:,.2f}"

        # 2. حساب المخزون
        total_inv = 0.0
        self.inventory_items = []
        
        for row in self.inv_rows:
            qty = _safe_float(row['qty'].value)
            if qty > 0:
                cost = _safe_float(row['cost'].value)
                self.inventory_items.append({"product_id": int(row['id']), "quantity": qty, "unit_cost": cost})
                total_inv += qty * cost

        if hasattr(self, 'inv_total_text'):
            self.inv_total_text.value = f"إجمالي قيمة المخزون: {total_inv:,.2f}"

        # 3. التحديث النهائي للشريط السفلي
        total_dr_with_inv = round(total_dr + total_inv, 2)
        total_cr = round(total_cr, 2)
        diff = round(total_dr_with_inv - total_cr, 2)
        is_balanced = abs(diff) < 0.01
        
        status_color = ACCENT_GREEN if is_balanced else ACCENT_ORANGE
        status_text = "✅ متوازن" if is_balanced else f"⚠️ غير متوازن (سيُسوّى عبر الأرباح المبقاة)"
        
        if total_dr_with_inv > 0 or total_cr > 0:
            self.summary_text.value = f"المدين (مع المخزون): {total_dr_with_inv:,.2f} | الدائن: {total_cr:,.2f} | {status_text}"
            self.summary_text.color = status_color
            self.save_btn.disabled = False
        else:
            self.summary_text.value = ""
            self.save_btn.disabled = True
            
        self.page.update()

    # ============================================================
    # الحفظ
    # ============================================================
    def save_opening(self, e):
        if not self.account_balances and not self.inventory_items:
            self.show_snackbar("لا توجد بيانات للحفظ", ACCENT_RED); return
            
        entry_id, err = create_opening_balances(
            self.account_balances, self.inventory_items,
            self.entry_date.value, "admin"
        )
        if err:
            self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
        else:
            self.show_snackbar(f"✅ تم تسجيل الأرصدة الافتتاحية بقيد رقم {entry_id}", ACCENT_GREEN)
            # تصفير الحقول
            for row in self.acc_rows: row['dr'].value = "0"; row['cr'].value = "0"
            for row in self.inv_rows: row['qty'].value = "0"
            self.recalculate_totals()
