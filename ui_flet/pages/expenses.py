# ui_flet/pages/expenses.py
import flet as ft
import pandas as pd
from datetime import date
from services.expenses_service import (
    create_expenses_table, get_payment_accounts,
    get_suppliers_for_expense, create_expense, get_expenses,
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

def _format_account_label(acc):
    icon = "💵" if acc["type"] == "cash" else "🏦"
    return f"{icon} {acc['name']} ({acc['currency']}) — الرصيد: {acc['balance']:,.2f}"

class ExpensesPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        try: create_expenses_table()
        except Exception as e: print(f"Expenses init: {e}")

        self.header = ft.Text("🧾 المصروفات التشغيلية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("تسجيل المصروفات (إيجار، كهرباء، رواتب...) وربطها محاسبياً", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="➕ تسجيل مصروف", content=self.build_add_tab()),
                ft.Tab(text="📋 سجل المصروفات", content=self.build_history_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. تسجيل مصروف
    # ============================================================
    def build_add_tab(self):
        # حقول أساسية
        self.exp_cat = ft.TextField(label="نوع المصروف", hint_text="مثال: إيجار، كهرباء، رواتب...", expand=True)
        self.exp_amount = ft.TextField(label="المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.exp_date = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        
        # طريقة الدفع
        self.payment_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="cash", label="💵 نقدي (من صندوق)"),
                ft.Radio(value="bank", label="🏦 بنكي (تحويل)"),
                ft.Radio(value="credit", label="📌 آجل (على المورد)")
            ]), value="cash", on_change=self.on_payment_change
        )
        
        # حاويات الحساب والمورد
        self.account_dd = ft.Dropdown(label="من أي حساب سيتم الدفع؟", expand=True)
        self.account_status = ft.Text("", color=TEXT_SECONDARY, size=12)
        
        self.supplier_dd = ft.Dropdown(label="اختر المورد", expand=True, visible=False)
        
        # حقول إضافية
        self.exp_ref = ft.TextField(label="رقم فاتورة المورد (اختياري)", expand=True)
        self.exp_notes = ft.TextField(label="ملاحظات", multiline=True, min_lines=2)
        
        # زر الحفظ
        self.save_btn = ft.ElevatedButton("💾 حفظ المصروف", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=self.save_expense)

        # تهيئة أولية
        self.on_payment_change(None)

        return ft.Column([
            ft.Text("تسجيل مصروف جديد", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            self.exp_cat,
            ft.Row([self.exp_amount, self.exp_date]),
            ft.Divider(color=GLASS_BORDER),
            self.payment_radio,
            self.account_dd, self.account_status, self.supplier_dd,
            ft.Divider(color=GLASS_BORDER),
            self.exp_ref, self.exp_notes,
            self.save_btn
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def on_payment_change(self, e):
        method = self.payment_radio.value
        
        if method in ('cash', 'bank'):
            self.account_dd.visible = True
            self.supplier_dd.visible = False
            
            accounts = get_payment_accounts()
            filtered = [a for a in accounts if a["type"] == ("cash" if method == "cash" else "bank")]
            self.account_dd.options = [ft.dropdown.Option(key=str(a['id']), text=_format_account_label(a)) for a in filtered]
            if filtered: self.account_dd.value = str(filtered[0]['id'])
        else:  # credit
            self.account_dd.visible = False
            self.supplier_dd.visible = True
            
            suppliers = get_suppliers_for_expense()
            self.supplier_dd.options = [ft.dropdown.Option(key=str(s['id']), text=s['name']) for s in suppliers]
            if suppliers: self.supplier_dd.value = str(suppliers[0]['id'])
        
        self.check_balance()
        self.page.update()

    def check_balance(self):
        method = self.payment_radio.value
        if method not in ('cash', 'bank'): 
            self.account_status.value = ""
            self.page.update()
            return
        
        try: amount = float(self.exp_amount.value or 0)
        except ValueError: amount = 0.0
        
        accounts = get_payment_accounts()
        filtered = [a for a in accounts if a["type"] == ("cash" if method == "cash" else "bank")]
        acc = next((a for a in filtered if str(a['id']) == self.account_dd.value), None)
        
        if acc and amount > 0:
            if amount > acc['balance']:
                self.account_status.value = f"⚠️ الرصيد غير كافٍ! المتاح: {acc['balance']:,.2f} {acc['currency']} | المطلوب: {amount:,.2f}"
                self.account_status.color = ACCENT_RED
                self.save_btn.disabled = True
            else:
                self.account_status.value = f"✅ الرصيد كافٍ — سيتبقى {acc['balance'] - amount:,.2f} {acc['currency']}"
                self.account_status.color = ACCENT_GREEN
                self.save_btn.disabled = False
        else:
            self.account_status.value = ""
            self.save_btn.disabled = False
        self.page.update()

    def save_expense(self, e):
        if not self.exp_cat.value or not self.exp_cat.value.strip():
            self.show_snackbar("نوع المصروف مطلوب", ACCENT_RED); return
        try: amount = float(self.exp_amount.value or 0)
        except ValueError: amount = 0.0
        if amount <= 0:
            self.show_snackbar("المبلغ يجب أن يكون أكبر من صفر", ACCENT_RED); return

        method = self.payment_radio.value
        account_code = None
        party_type = None
        party_id = None

        if method in ('cash', 'bank'):
            accounts = get_payment_accounts()
            filtered = [a for a in accounts if a["type"] == ("cash" if method == "cash" else "bank")]
            acc = next((a for a in filtered if str(a['id']) == self.account_dd.value), None)
            if not acc:
                self.show_snackbar("اختر حساباً صحيحاً", ACCENT_RED); return
            if amount > acc['balance']:
                self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {acc['balance']:,.2f}", ACCENT_RED); return
            account_code = acc["code"]
        else:  # credit
            if not self.supplier_dd.value:
                self.show_snackbar("اختر المورد", ACCENT_RED); return
            party_type = "supplier"
            party_id = int(self.supplier_dd.value)
            account_code = ""

        eid, err = create_expense(
            self.exp_date.value, self.exp_cat.value.strip(), amount,
            account_code, method, party_type, party_id,
            self.exp_ref.value, self.exp_notes.value, "admin"
        )
        if err:
            self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
        else:
            self.show_snackbar(f"✅ تم تسجيل المصروف رقم {eid}", ACCENT_GREEN)
            self.exp_cat.value = ""; self.exp_amount.value = "0"; self.exp_ref.value = ""; self.exp_notes.value = ""
            self.check_balance()

    # ============================================================
    # 2. سجل المصروفات
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.load_history()
        
        return ft.Column([
            ft.Text("سجل المصروفات", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        expenses = get_expenses()
        if expenses:
            total = sum(float(e.get('amount', 0)) for e in expenses)
            df = pd.DataFrame(expenses)
            
            method_labels = {"cash": "💵 نقدي", "bank": "🏦 بنكي", "credit": "📌 آجل"}
            df["payment_method"] = df["payment_method"].apply(lambda x: method_labels.get(x, x))
            
            df_display = df.rename(columns={
                "id": "الرقم", "date": "التاريخ", "category": "النوع", "amount": "المبلغ",
                "account_code": "الحساب", "payment_method": "طريقة الدفع",
                "party_name": "المورد", "invoice_ref": "رقم الفاتورة", "notes": "ملاحظات"
            })
            cols = [c for c in ["الرقم", "التاريخ", "النوع", "المبلغ", "طريقة الدفع", "الحساب", "المورد", "رقم الفاتورة", "ملاحظات"] if c in df_display.columns]
            
            self.history_container.content = ft.Column([
                ft.Container(
                    content=ft.Text(f"💰 إجمالي المصروفات: {total:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.colors.with_opacity(0.15, ACCENT_GREEN), padding=10, border_radius=8
                ),
                temp_data_table(df_display[cols])
            ], spacing=15)
        else:
            self.history_container.content = ft.Text("لا توجد مصروفات مسجلة بعد", color=TEXT_SECONDARY)
        self.page.update()
