# ui_flet/pages/returns.py
import flet as ft
import pandas as pd
from datetime import date
from services.returns_service import (
    get_sales_invoices, get_purchase_invoices, get_invoice_items,
    process_return, get_return_history,
)
from services.cash_service import get_all_cash_accounts
from services.bank_service import get_all_bank_accounts
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

class ReturnsPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("🔄 مرتجعات البضاعة", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة مرتجعات المبيعات والمشتريات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="مرتجع مبيعات", content=self.build_sales_return_tab()),
                ft.Tab(text="مرتجع مشتريات", content=self.build_purchase_return_tab()),
                ft.Tab(text="سجل المرتجعات", content=self.build_history_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # نموذج المرتجع الموحد
    # ============================================================
    def render_return_form(self, invoice_type, inv, items, prefix):
        container = ft.Column(spacing=10)
        
        # 1. عرض البنود
        display_items = [{
            "اسم المنتج": item["name"],
            "الكمية المباعة": item["quantity"],
            "المرجع سابقاً": item.get("returned_qty", 0),
            "المتاح للإرجاع": item["available_qty"],
            "سعر الوحدة": f"{item['unit_price']:,.2f}",
        } for item in items]
        
        container.controls.append(temp_data_table(pd.DataFrame(display_items)))
        container.controls.append(ft.Divider(color=GLASS_BORDER))
        container.controls.append(ft.Text("اختر الكميات المراد إرجاعها", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD))

        # 2. حقول الكميات
        qty_inputs = {}
        has_available = False
        
        for item in items:
            available = item["available_qty"]
            if available <= 0: continue
            has_available = True
            
            qty_input = ft.TextField(label=f"الكمية (متاح: {available})", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=150)
            qty_inputs[item["id"]] = (item, qty_input)
            
            container.controls.append(ft.Row([
                ft.Text(f"{item['name']} — مباع: {item['quantity']}، مرجع: {item.get('returned_qty', 0)}", color=TEXT_PRIMARY, expand=True),
                qty_input
            ]))

        if not has_available:
            container.controls.append(ft.Text("لا توجد كميات متاحة للإرجاع في هذه الفاتورة", color=TEXT_SECONDARY))
            return container

        # 3. تاريخ وسبب
        return_date = ft.TextField(label="تاريخ المرتجع", value=date.today().strftime("%Y-%m-%d"))
        reason = ft.TextField(label="سبب الإرجاع (اختياري)", multiline=True)
        
        # 4. طريقة الاسترداد
        refund_method = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="account", label="💼 خصم من الحساب"),
                ft.Radio(value="cash", label="💵 استرداد نقدي"),
                ft.Radio(value="bank", label="🏦 تحويل بنكي")
            ]), value="account"
        )
        
        account_dd = ft.Dropdown(label="اختر الحساب", expand=True)
        account_status = ft.Text("", color=TEXT_SECONDARY, size=12)
        
        def on_refund_change(e):
            method = refund_method.value
            if method == "cash":
                accounts = get_all_cash_accounts(active_only=True)
                account_dd.options = [ft.dropdown.Option(key=str(a['id']), text=f"{a['name']} ({a['currency_code']}) — {a['current_balance']:,.2f}") for a in accounts]
                if accounts: account_dd.value = str(accounts[0]['id'])
                account_dd.visible = True
            elif method == "bank":
                accounts = get_all_bank_accounts(active_only=True)
                account_dd.options = [ft.dropdown.Option(key=str(a['id']), text=f"{b['bank_name']} ({b['account_number']}) — {b['current_balance']:,.2f}") for b in accounts]
                if accounts: account_dd.value = str(accounts[0]['id'])
                account_dd.visible = True
            else:
                account_dd.visible = False
            self.update_refund_status()
        
        refund_method.on_change = on_refund_change
        account_dd.on_change = lambda e: self.update_refund_status()

        # 5. الإجمالي وزر التأكيد
        total_text = ft.Text("", color=ACCENT_PURPLE, size=16, weight=ft.FontWeight.BOLD)
        
        def confirm_return(e):
            return_items = []
            for item_id, (item, inp) in qty_inputs.items():
                try: qty = int(inp.value or 0)
                except ValueError: qty = 0
                if qty > 0:
                    if qty > item["available_qty"]: qty = item["available_qty"]
                    return_items.append((item["name"], qty))
            
            if not return_items:
                self.show_snackbar("أدخل كمية واحدة على الأقل", ACCENT_RED); return
            
            method = refund_method.value
            cash_code, bank_code = None, None
            
            if method in ('cash', 'bank'):
                if not account_dd.value:
                    self.show_snackbar("اختر الحساب", ACCENT_RED); return
                # التحقق من الرصيد
                estimate = sum(qty * float(next(i['unit_price'] for i in items if i['name'] == name)) for name, qty in return_items)
                estimate *= (1 + float(inv.get("vat_rate") or 0.15))
                
                if method == "cash":
                    acc = next((a for a in get_all_cash_accounts(active_only=True) if str(a['id']) == account_dd.value), None)
                    if acc and estimate > acc['current_balance']:
                        self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {acc['current_balance']:,.2f}", ACCENT_RED); return
                    cash_code = acc['account_code']
                else:
                    acc = next((b for b in get_all_bank_accounts(active_only=True) if str(b['id']) == account_dd.value), None)
                    if acc and estimate > acc['current_balance']:
                        self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {acc['current_balance']:,.2f}", ACCENT_RED); return
                    bank_code = acc['account_code']

            ok, result, total, note = process_return(
                invoice_type, inv["id"], return_items, return_date.value,
                reason.value, refund_method=method, cash_account_code=cash_code, bank_account_code=bank_code
            )
            if ok:
                msg = f"✅ تم تسجيل المرتجع رقم {result} — الإجمالي: {total:,.2f}"
                if note: msg += f"\n{note}"
                self.show_snackbar(msg, ACCENT_GREEN)
                self.refresh_tabs()
            else:
                self.show_snackbar(f"❌ فشل: {result}", ACCENT_RED)

        def update_totals(e=None):
            estimate = 0.0
            for item_id, (item, inp) in qty_inputs.items():
                try: qty = int(inp.value or 0)
                except ValueError: qty = 0
                if qty > 0:
                    estimate += qty * float(item['unit_price'])
            estimate *= (1 + float(inv.get("vat_rate") or 0.15))
            total_text.value = f"💰 الإجمالي المتوقع للمرتجع: {estimate:,.2f}"
            self.page.update()

        for item_id, (item, inp) in qty_inputs.items():
            inp.on_change = update_totals
        update_totals()

        container.controls.extend([
            return_date, reason,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("طريقة الاسترداد", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD),
            refund_method, account_dd, account_status,
            total_text,
            ft.ElevatedButton(f"✅ تأكيد مرتجع {'المبيعات' if invoice_type == 'sale' else 'المشتريات'}",
                              on_click=confirm_return, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ])
        
        on_refund_change(None)
        return container

    def update_refund_status(self):
        # تحديث حالة الرصيد بعد الاختيار (يمكن التوسع لاحقاً)
        pass

    def refresh_tabs(self):
        # إعادة بناء التبويبات لتحديث البيانات
        self.tabs.tabs = [
            ft.Tab(text="مرتجع مبيعات", content=self.build_sales_return_tab()),
            ft.Tab(text="مرتجع مشتريات", content=self.build_purchase_return_tab()),
            ft.Tab(text="سجل المرتجعات", content=self.build_history_tab()),
        ]
        self.page.update()

    # ============================================================
    # 1. مرتجع مبيعات
    # ============================================================
    def build_sales_return_tab(self):
        invoices = get_sales_invoices()
        if not invoices:
            return ft.Text("لا توجد فواتير مبيعات مكتملة", color=TEXT_SECONDARY)

        self.sales_inv_dd = ft.Dropdown(
            label="اختر الفاتورة",
            options=[ft.dropdown.Option(key=str(inv['id']), text=f"فاتورة #{inv['id']} - {inv['customer']} ({inv['invoice_date']})") for inv in invoices],
            value=str(invoices[0]['id']), expand=True
        )
        self.sales_return_container = ft.Container()

        def on_inv_change(e):
            inv_id = int(self.sales_inv_dd.value)
            inv = next(i for i in invoices if i['id'] == inv_id)
            items = get_invoice_items(inv_id)
            if items:
                self.sales_return_container.content = self.render_return_form("sale", inv, items, "sret")
            else:
                self.sales_return_container.content = ft.Text("لا توجد بنود في هذه الفاتورة", color=TEXT_SECONDARY)
            self.page.update()

        self.sales_inv_dd.on_change = on_inv_change
        on_inv_change(None)

        return ft.Column([
            ft.Text("إرجاع بضاعة من عميل", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            self.sales_inv_dd, self.sales_return_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 2. مرتجع مشتريات
    # ============================================================
    def build_purchase_return_tab(self):
        invoices = get_purchase_invoices()
        if not invoices:
            return ft.Text("لا توجد فواتير مشتريات مكتملة", color=TEXT_SECONDARY)

        self.purchase_inv_dd = ft.Dropdown(
            label="اختر الفاتورة",
            options=[ft.dropdown.Option(key=str(inv['id']), text=f"فاتورة #{inv['id']} - {inv['supplier']} ({inv['invoice_date']})") for inv in invoices],
            value=str(invoices[0]['id']), expand=True
        )
        self.purchase_return_container = ft.Container()

        def on_inv_change(e):
            inv_id = int(self.purchase_inv_dd.value)
            inv = next(i for i in invoices if i['id'] == inv_id)
            items = get_invoice_items(inv_id)
            if items:
                self.purchase_return_container.content = self.render_return_form("purchase", inv, items, "pret")
            else:
                self.purchase_return_container.content = ft.Text("لا توجد بنود في هذه الفاتورة", color=TEXT_SECONDARY)
            self.page.update()

        self.purchase_inv_dd.on_change = on_inv_change
        on_inv_change(None)

        return ft.Column([
            ft.Text("إرجاع بضاعة للمورد", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.purchase_inv_dd, self.purchase_return_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 3. سجل المرتجعات
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.load_history()
        
        return ft.Column([
            ft.Text("سجل عمليات المرتجعات", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        returns = get_return_history()
        if returns:
            display = [{
                "رقم المرتجع": r['id'],
                "النوع": "مرتجع مبيعات" if r['type'] == 'sale_return' else "مرتجع مشتريات",
                "التاريخ": r['invoice_date'],
                "الإجمالي": f"{float(r['total'] or 0):,.2f}",
                "الكمية": r.get('total_qty', 0),
                "السبب": r.get('reason', '') or '—',
            } for r in returns]
            self.history_container.content = temp_data_table(pd.DataFrame(display))
        else:
            self.history_container.content = ft.Text("لا توجد مرتجعات بعد", color=TEXT_SECONDARY)
        self.page.update()
