# ui_flet/pages/currency_revaluation.py
import flet as ft
import pandas as pd
from datetime import date
from services.currency_revaluation_service import (
    get_accounts_with_foreign_currency, get_foreign_balance,
    perform_revaluation, get_revaluation_history, get_treasury_impact_preview,
)
from services.currency_service import get_base_currency, get_exchange_rate
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

class CurrencyRevaluationPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("💱 فروق أسعار الصرف", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إعادة تقييم الأرصدة بالعملات الأجنبية ومعالجة الفروق", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="🔄 إعادة تقييم", content=self.build_revaluation_tab()),
                ft.Tab(text="📋 سجل العمليات", content=self.build_history_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. تبويب إعادة التقييم
    # ============================================================
    def build_revaluation_tab(self):
        accounts = get_accounts_with_foreign_currency()
        if not accounts:
            return ft.Text("ℹ️ لا توجد حسابات لديها معاملات بعملات أجنبية", color=TEXT_SECONDARY)

        self.acc_data = {f"{a['account_code']} - {a['account_name']}": a for a in accounts}
        self.acc_dd = ft.Dropdown(
            label="اختر الحساب", expand=True,
            options=[ft.dropdown.Option(k) for k in self.acc_data.keys()],
            value=list(self.acc_data.keys())[0]
        )
        self.acc_dd.on_change = lambda e: self.on_account_change()

        self.acc_info_text = ft.Text("", color=TEXT_PRIMARY, size=13)
        
        self.rate_input = ft.TextField(label="سعر الصرف الجديد", value="1.0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.rate_input.on_change = lambda e: self.preview_impact()
        self.rate_hint = ft.Text("", color=TEXT_SECONDARY, size=11)
        
        self.date_input = ft.TextField(label="تاريخ إعادة التقييم", value=date.today().strftime("%Y-%m-%d"), expand=True)
        
        self.preview_container = ft.Container()
        self.action_btn = ft.ElevatedButton("💾 تنفيذ إعادة التقييم", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=self.do_revaluation, visible=False)

        self.on_account_change()  # تحميل أولي

        return ft.Column([
            ft.Text("إعادة تقييم الأرصدة بالعملات الأجنبية", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.acc_dd,
            self.acc_info_text,
            ft.Divider(color=GLASS_BORDER),
            ft.Row([self.rate_input, self.date_input]),
            self.rate_hint,
            self.preview_container,
            self.action_btn
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def on_account_change(self):
        if not self.acc_dd.value: return
        acc_data = self.acc_data[self.acc_dd.value]
        self.account_id = acc_data['account_id']
        self.account_name = acc_data['account_name']
        self.currency = acc_data['currency_code']

        foreign_bal, current_local = get_foreign_balance(self.account_id, self.currency)
        self.foreign_bal = foreign_bal
        self.current_local = current_local

        if abs(foreign_bal) < 0.001:
            self.acc_info_text.value = f"⚠️ الحساب {self.account_name} رصيده صفر. لا حاجة لإعادة التقييم."
            self.acc_info_text.color = ACCENT_ORANGE
            self.action_btn.visible = False
            self.preview_container.content = None
            self.page.update()
            return

        self.acc_info_text.value = f"📌 الحساب: {self.account_name} | العملة: {self.currency} | الرصيد الأجنبي: {foreign_bal:,.2f} | القيمة المحلية التاريخية: {current_local:,.2f}"
        self.acc_info_text.color = TEXT_PRIMARY

        # اقتراح سعر الصرف
        base = get_base_currency()
        base_code = base['code'] if base else 'YER'
        try:
            suggested = get_exchange_rate(self.currency, base_code)
            if suggested:
                self.rate_input.value = f"{float(suggested):.4f}"
                self.rate_hint.value = f"💡 سعر الصرف الحالي في النظام: {float(suggested):,.4f}"
            else:
                self.rate_hint.value = ""
        except Exception:
            self.rate_hint.value = ""

        self.preview_impact()

    def preview_impact(self):
        if not hasattr(self, 'account_id'): return
        try: new_rate = float(self.rate_input.value or 1.0)
        except ValueError: return

        preview = get_treasury_impact_preview(self.account_id, self.currency, new_rate)
        if preview.get("error"):
            self.preview_container.content = ft.Text(f"❌ {preview['error']}", color=ACCENT_RED)
            self.action_btn.visible = False
            self.page.update()
            return

        new_local = preview["new_local_value"]
        diff = preview["difference"]
        is_profit = diff > 0

        # محتوى المعاينة
        content = [
            ft.Row([
                ft.Text(f"القيمة الجديدة: {new_local:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Text(f"الفرق: {diff:+,.2f}", color=ACCENT_GREEN if is_profit else ACCENT_RED, weight=ft.FontWeight.BOLD),
                ft.Text("🟢 ربح فروق عملة" if is_profit else "🔴 خسارة فروق عملة", color=ACCENT_GREEN if is_profit else ACCENT_RED, size=12)
            ], spacing=20)
        ]

        # تأثير الصندوق/البنك
        if preview.get("treasury_linked"):
            icon = "💵" if preview["treasury_type"] == "cash" else "🏦"
            kind = "الصندوق" if preview["treasury_type"] == "cash" else "البنك"
            content.append(ft.Container(
                content=ft.Text(f"{icon} تأثير على {kind} «{preview['treasury_name']}»: الرصيد {preview['treasury_old_balance']:,.2f} ← {preview['treasury_new_balance']:,.2f} (تغيير {preview['difference']:+,.2f})", color=TEXT_PRIMARY, size=12),
                bgcolor=ft.colors.with_opacity(0.08, ACCENT_GREEN if is_profit else ACCENT_RED),
                padding=10, border_radius=8
            ))
        else:
            content.append(ft.Text("ℹ️ هذا الحساب غير مرتبط بصندوق أو بنك.", color=TEXT_SECONDARY, size=12))

        self.preview_container.content = ft.Column(content, spacing=10)
        self.action_btn.visible = abs(diff) >= 0.01
        self.action_btn.bgcolor = ACCENT_GREEN if is_profit else ACCENT_RED
        self.page.update()

    def do_revaluation(self, e):
        try: new_rate = float(self.rate_input.value or 1.0)
        except ValueError:
            self.show_snackbar("سعر غير صالح", ACCENT_RED); return

        entry_id, err = perform_revaluation(
            self.account_id, self.currency, new_rate, self.date_input.value, created_by="admin"
        )
        if err:
            self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
        else:
            self.show_snackbar(f"✅ تم إنشاء قيد إعادة التقييم رقم #{entry_id}", ACCENT_GREEN)
            self.on_account_change()

    # ============================================================
    # 2. تبويب السجل
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.load_history()
        return ft.Column([
            ft.Text("سجل عمليات إعادة التقييم", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        history = get_revaluation_history()
        if not history:
            self.history_container.content = ft.Text("لا توجد عمليات سابقة", color=TEXT_SECONDARY)
            self.page.update(); return

        df = pd.DataFrame(history)
        df_display = df.copy()
        if 'difference' in df_display.columns:
            df_display['النوع'] = df_display['difference'].apply(lambda x: "🟢 ربح" if float(x) > 0 else "🔴 خسارة")

        df_display = df_display.rename(columns={
            'id': 'الرقم', 'date': 'التاريخ', 'account_name': 'الحساب',
            'currency_code': 'العملة', 'new_rate': 'السعر الجديد',
            'foreign_balance': 'الرصيد الأجنبي', 'old_local_value': 'قيمة قديمة',
            'new_local_value': 'قيمة جديدة', 'difference': 'الفرق', 'journal_entry_id': 'رقم القيد'
        })
        cols = [c for c in ['الرقم', 'التاريخ', 'الحساب', 'العملة', 'السعر الجديد', 'الرصيد الأجنبي', 'قيمة قديمة', 'قيمة جديدة', 'الفرق', 'النوع', 'رقم القيد'] if c in df_display.columns]

        total_profit = df[df['difference'] > 0]['difference'].sum()
        total_loss = abs(df[df['difference'] < 0]['difference'].sum())

        summary = ft.Row([
            ft.Text(f"عدد العمليات: {len(df)}", color=TEXT_PRIMARY),
            ft.Text(f"إجمالي الأرباح: {total_profit:,.2f}", color=ACCENT_GREEN),
            ft.Text(f"إجمالي الخسائر: {total_loss:,.2f}", color=ACCENT_RED),
        ], spacing=30)

        self.history_container.content = ft.Column([
            summary,
            temp_data_table(df_display[cols])
        ], spacing=15)
        self.page.update()
