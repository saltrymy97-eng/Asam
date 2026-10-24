# ui_flet/pages/receipts.py
import flet as ft
import pandas as pd
from datetime import date
from services.receipts_service import (
    create_vouchers_table, get_payment_accounts, get_customers_with_balances,
    get_suppliers_with_balances, get_invoices_for_party, create_voucher,
    get_vouchers, get_voucher_details, link_voucher_to_invoice,
    unlink_voucher_from_invoice, get_unlinked_vouchers,
    get_vouchers_by_party, get_party_invoices_with_status,
)
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

PAYMENT_STATUS_LABELS = {"unpaid": "🔴 غير مدفوعة", "partial": "🟡 مدفوعة جزئياً", "paid": "🟢 مدفوعة بالكامل"}

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

def _get_value(d, *keys, default=0):
    if d is None: return default
    for k in keys:
        if k in d and d[k] is not None: return d[k]
    return default

def _account_icon(acc_type: str) -> str:
    return "🏦" if acc_type == "bank" else "💵"

def _account_label(acc: dict) -> str:
    icon = _account_icon(acc.get("type", "cash"))
    return f"{icon} {acc.get('code', '')} - {acc.get('name', '—')} | الرصيد: {float(acc.get('balance', 0) or 0):,.2f} {acc.get('currency', 'YER')}"

class ReceiptsPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        try: create_vouchers_table()
        except Exception as e: print(f"Receipts init: {e}")

        self.header = ft.Text("💵 سندات القبض والصرف", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة المقبوضات والمدفوعات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="🧾 سند قبض", content=self.build_voucher_form('receipt')),
                ft.Tab(text="📤 سند صرف", content=self.build_voucher_form('payment')),
                ft.Tab(text="📋 سجل السندات", content=self.build_history_tab()),
                ft.Tab(text="🔗 ربط السندات بالفواتير", content=self.build_link_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # نموذج السند (قبض/صرف)
    # ============================================================
    def build_voucher_form(self, voucher_type: str):
        is_receipt = voucher_type == 'receipt'
        party_type = 'customer' if is_receipt else 'supplier'
        title = "سند قبض" if is_receipt else "سند صرف"
        color = ACCENT_GREEN if is_receipt else ACCENT_RED

        accounts = get_payment_accounts()
        if not accounts:
            return ft.Text("⚠️ لا توجد صناديق أو بنوك نشطة. أضف حساباً أولاً.", color=ACCENT_ORANGE)

        parties = get_customers_with_balances() if is_receipt else get_suppliers_with_balances()
        if not parties:
            return ft.Text(f"لا يوجد {('عملاء' if is_receipt else 'موردون')}", color=ACCENT_ORANGE)

        self.party_dd = ft.Dropdown(
            label=f"اختر {'العميل' if is_receipt else 'المورد'}",
            options=[ft.dropdown.Option(key=str(p['id']), text=f"{p['name']} (رصيد: {float(p['balance']):,.2f})") for p in parties],
            value=str(parties[0]['id']), expand=True
        )
        self.account_dd = ft.Dropdown(
            label="حساب الدفع (صندوق / بنك)",
            options=[ft.dropdown.Option(key=str(a['id']), text=_account_label(a)) for a in accounts],
            value=str(accounts[0]['id']), expand=True
        )
        self.invoice_dd = ft.Dropdown(label="ربط بفاتورة (اختياري)", expand=True)
        self.amount_input = ft.TextField(label="المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.date_input = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.ref_input = ft.TextField(label="المرجع (اختياري)", expand=True)
        self.notes_input = ft.TextField(label="ملاحظات", multiline=True, min_lines=2)
        self.status_text = ft.Text("", color=TEXT_SECONDARY, size=13)
        self.party_info_text = ft.Text("", color=TEXT_PRIMARY, size=12)
        self.account_info_text = ft.Text("", color=TEXT_PRIMARY, size=12)

        def update_party_info(e=None):
            party = next((p for p in parties if str(p['id']) == self.party_dd.value), None)
            if party:
                self.party_info_text.value = f"👤 الطرف: {party['name']} | الرصيد المستحق: {float(party['balance']):,.2f}"
            # جلب الفواتير المتاحة
            invoices = get_invoices_for_party(party_type, int(self.party_dd.value))
            self.invoice_dd.options = [ft.dropdown.Option(key="none", text="بدون فاتورة (دفعة عامة)")]
            for inv in invoices:
                remaining = _get_value(inv, 'remaining_amount', 'remaining')
                self.invoice_dd.options.append(ft.dropdown.Option(key=str(inv['id']), text=f"فاتورة #{inv['id']} | المتبقي: {float(remaining):,.2f}"))
            self.invoice_dd.value = "none"
            self.page.update()

        def update_account_info(e=None):
            acc = next((a for a in accounts if str(a['id']) == self.account_dd.value), None)
            if acc:
                icon = _account_icon(acc.get("type", "cash"))
                kind = "بنك" if acc.get("type") == "bank" else "صندوق"
                self.account_info_text.value = f"{icon} {kind}: {acc.get('name','—')} ({acc.get('code','')}) | الرصيد: {float(acc.get('balance',0)):,.2f} {acc.get('currency','YER')}"
            self.check_balance()
            self.page.update()

        def check_balance(e=None):
            if is_receipt: return
            try: amount = float(self.amount_input.value or 0)
            except ValueError: amount = 0.0
            acc = next((a for a in accounts if str(a['id']) == self.account_dd.value), None)
            if acc and amount > 0:
                available = float(acc.get('balance', 0) or 0)
                if amount > available + 0.01:
                    self.status_text.value = f"❌ نقص: {amount - available:,.2f}"
                    self.status_text.color = ACCENT_RED
                else:
                    self.status_text.value = "✅ الرصيد كافٍ"
                    self.status_text.color = ACCENT_GREEN
            self.page.update()

        def save_voucher(e):
            if not self.party_dd.value or not self.account_dd.value: return
            try: amount = float(self.amount_input.value or 0)
            except ValueError: amount = 0.0
            if amount <= 0:
                self.show_snackbar("المبلغ يجب أن يكون أكبر من صفر", ACCENT_RED); return
            
            acc = next((a for a in accounts if str(a['id']) == self.account_dd.value), None)
            if not is_receipt and amount > float(acc.get('balance', 0) or 0) + 0.01:
                self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {float(acc.get('balance',0)):,.2f}", ACCENT_RED); return

            inv_id = None if self.invoice_dd.value == "none" or not self.invoice_dd.value else int(self.invoice_dd.value)
            
            vid, err = create_voucher(
                voucher_type=voucher_type, party_type=party_type,
                party_id=int(self.party_dd.value), amount=amount,
                account=acc.get("code", ""), invoice_id=inv_id,
                reference=self.ref_input.value, notes=self.notes_input.value,
                created_by="admin", voucher_date=self.date_input.value
            )
            if err:
                self.show_snackbar(f"❌ فشل الحفظ: {err}", ACCENT_RED)
            else:
                self.show_snackbar(f"✅ تم إنشاء {title} رقم #{vid}", ACCENT_GREEN)
                self.amount_input.value = "0"; self.ref_input.value = ""; self.notes_input.value = ""
                self.check_balance()

        self.party_dd.on_change = update_party_info
        self.account_dd.on_change = update_account_info
        self.amount_input.on_change = check_balance

        update_party_info()
        update_account_info()

        form = ft.Column([
            ft.Text(f"🧾 {title}", color=color, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.party_dd, self.account_dd]),
            self.party_info_text, self.account_info_text,
            ft.Divider(color=GLASS_BORDER),
            self.invoice_dd,
            ft.Row([self.amount_input, self.date_input]),
            self.ref_input, self.notes_input,
            self.status_text,
            ft.ElevatedButton(f"💾 حفظ {title}", on_click=save_voucher, bgcolor=color, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

        return form

    # ============================================================
    # سجل السندات
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.details_container = ft.Container()
        self.voucher_selector = ft.Dropdown(label="اختر سند لعرض التفاصيل", on_change=lambda e: self.load_details(int(e.control.value)))
        self.load_history()
        
        return ft.Column([
            ft.Text("سجل السندات", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.history_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("تفاصيل السند", color=ACCENT_BLUE, size=16, weight=ft.FontWeight.BOLD),
            self.voucher_selector,
            self.details_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        vouchers = get_vouchers()
        if vouchers:
            df = pd.DataFrame(vouchers)
            df['linked_amount'] = df['linked_amount'].fillna(0).astype(float)
            df['unlinked'] = df['amount'].astype(float) - df['linked_amount']
            df['ربط'] = df.apply(lambda r: "✅ مربوط بالكامل" if r['unlinked'] < 0.01 else ("🟡 مربوط جزئياً" if r['linked_amount'] > 0.01 else "🔴 غير مربوط"), axis=1)
            
            df_display = pd.DataFrame({
                'الرقم': df['id'], 'النوع': df['type'].apply(lambda x: 'قبض' if x == 'receipt' else 'صرف'),
                'التاريخ': df['date'], 'الطرف': df['party_name'], 'المبلغ': df['amount'],
                'المربوط': df['linked_amount'], 'غير المربوط': df['unlinked'],
                'الحالة': df['ربط'], 'المرجع': df['reference']
            })
            self.history_container.content = temp_data_table(df_display)
            ids = [str(v['id']) for v in vouchers]
            self.voucher_selector.options = [ft.dropdown.Option(i) for i in ids]
            if ids: self.voucher_selector.value = ids[0]
        else:
            self.history_container.content = ft.Text("لا توجد سندات بعد", color=TEXT_SECONDARY)

    def load_details(self, vid):
        details = get_voucher_details(vid)
        if not details:
            self.details_container.content = ft.Text("لا توجد تفاصيل", color=TEXT_SECONDARY); self.page.update(); return
        content = [
            ft.Row([
                ft.Text(f"الرقم: {details['id']}", color=TEXT_PRIMARY),
                ft.Text(f"النوع: {'قبض' if details['type'] == 'receipt' else 'صرف'}", color=TEXT_PRIMARY),
                ft.Text(f"المبلغ: {float(details['amount']):,.2f}", color=ACCENT_GREEN),
                ft.Text(f"المربوط: {float(details.get('linked_amount', 0)):,.2f}", color=ACCENT_ORANGE),
            ], spacing=20),
            ft.Text(f"الطرف: {details.get('party_name', '—')} | التاريخ: {details.get('date', '—')} | الحساب: {details.get('account', '—')}", color=TEXT_SECONDARY)
        ]
        if details.get("lines"):
            content.append(ft.Text("📊 القيد المحاسبي", color=ACCENT_BLUE, weight=ft.FontWeight.BOLD))
            content.append(temp_data_table(pd.DataFrame(details["lines"])))
        if details.get("linked_payments"):
            content.append(ft.Text("🔗 الدفعات المرتبطة بفواتير", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD))
            df_pay = pd.DataFrame(details["linked_payments"])
            cols = [c for c in ['id', 'invoice_id', 'amount', 'payment_date', 'payment_method'] if c in df_pay.columns]
            content.append(temp_data_table(df_pay[cols]))
        else:
            content.append(ft.Text("🔴 هذا السند غير مربوط بأي فاتورة بعد", color=ACCENT_ORANGE))
        self.details_container.content = ft.Column(content, spacing=10)
        self.page.update()

    # ============================================================
    # ربط السندات بالفواتير
    # ============================================================
    def build_link_tab(self):
        self.party_kind_radio = ft.RadioGroup(
            content=ft.Row([ft.Radio(value="customer", label="عميل"), ft.Radio(value="supplier", label="مورد")]),
            value="customer", on_change=lambda e: self.refresh_link_ui()
        )
        self.party_dd_link = ft.Dropdown(label="اختر الطرف", expand=True)
        self.party_dd_link.on_change = lambda e: self.refresh_link_data()
        
        self.unlinked_dd = ft.Dropdown(label="📄 السندات غير المربوطة", expand=True)
        self.invoice_dd_link = ft.Dropdown(label="📋 الفواتير المعلقة", expand=True)
        self.link_info_text = ft.Text("", color=TEXT_SECONDARY, size=12)
        self.link_amount = ft.TextField(label="المبلغ المراد ربطه", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        
        # قسم إلغاء الربط
        self.linked_voucher_dd = ft.Dropdown(label="اختر سنداً مربوطاً", expand=True)
        self.linked_voucher_dd.on_change = lambda e: self.load_linked_payments()
        self.linked_payments_container = ft.Container()
        
        self.refresh_link_ui()
        
        return ft.Column([
            ft.Text("🔗 ربط السندات اليدوية بالفواتير", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            ft.Text("استخدم هذا التبويب لربط السندات التي أُنشئت بدون فاتورة، أو لتعديل الربط وإلغائه.", color=TEXT_SECONDARY, size=12),
            self.party_kind_radio,
            self.party_dd_link,
            ft.Divider(color=GLASS_BORDER),
            ft.Row([self.unlinked_dd, self.invoice_dd_link]),
            self.link_info_text, self.link_amount,
            ft.ElevatedButton("🔗 ربط السند بالفاتورة", on_click=self.do_link, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("🗑️ إلغاء ربط سابق", color=ACCENT_RED, size=16, weight=ft.FontWeight.BOLD),
            self.linked_voucher_dd, self.linked_payments_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    def refresh_link_ui(self):
        party_type = self.party_kind_radio.value
        parties = get_customers_with_balances() if party_type == 'customer' else get_suppliers_with_balances()
        self.party_dd_link.options = [ft.dropdown.Option(key=str(p['id']), text=f"{p['name']} (رصيد: {float(p['balance']):,.2f})") for p in parties]
        if parties: self.party_dd_link.value = str(parties[0]['id'])
        self.refresh_link_data()
        self.page.update()

    def refresh_link_data(self):
        if not self.party_dd_link.value: return
        party_type = self.party_kind_radio.value
        party_id = int(self.party_dd_link.value)
        
        # السندات غير المربوطة
        unlinked = get_unlinked_vouchers(party_type, party_id)
        self.unlinked_dd.options = [ft.dropdown.Option(key=str(v['id']), text=f"#{v['id']} | {v['date']} | مبلغ: {float(v['amount']):,.2f}") for v in unlinked]
        if unlinked: self.unlinked_dd.value = str(unlinked[0]['id'])
        
        # الفواتير المعلقة
        invoices = get_party_invoices_with_status(party_type, party_id, only_pending=True)
        self.invoice_dd_link.options = [ft.dropdown.Option(key=str(inv['id']), text=f"#{inv['id']} | متبقي: {float(_get_value(inv, 'remaining_amount', 'remaining')):,.2f}") for inv in invoices]
        if invoices: self.invoice_dd_link.value = str(invoices[0]['id'])
        
        # السندات المربوطة (لإلغاء الربط)
        linked_vouchers = get_vouchers_by_party(party_type, party_id)
        linked_vouchers = [v for v in linked_vouchers if float(v.get('linked_amount', 0)) > 0.01]
        self.linked_voucher_dd.options = [ft.dropdown.Option(key=str(v['id']), text=f"#{v['id']} | مربوط: {float(v.get('linked_amount', 0)):,.2f}") for v in linked_vouchers]
        if linked_vouchers: 
            self.linked_voucher_dd.value = str(linked_vouchers[0]['id'])
            self.load_linked_payments()
        else:
            self.linked_payments_container.content = ft.Text("لا توجد سندات مربوطة", color=TEXT_SECONDARY)
            
        self.update_link_info()
        self.page.update()

    def update_link_info(self):
        # يمكن إضافة حساب المبلغ الأقصى هنا لاحقاً
        self.link_info_text.value = "ملاحظة: يتم تحديد المبلغ الأقصى تلقائياً عند الربط (المتبقي من السند أو الفاتورة)."
        self.page.update()

    def do_link(self, e):
        if not self.unlinked_dd.value or not self.invoice_dd_link.value: return
        try: amount = float(self.link_amount.value or 0)
        except ValueError: amount = 0.0
        if amount <= 0:
            self.show_snackbar("أدخل مبلغاً صحيحاً", ACCENT_RED); return
        
        ok, err = link_voucher_to_invoice(int(self.unlinked_dd.value), int(self.invoice_dd_link.value), amount)
        if ok:
            self.show_snackbar(f"✅ تم ربط {amount:,.2f}", ACCENT_GREEN)
            self.refresh_link_data()
        else:
            self.show_snackbar(f"❌ {err}", ACCENT_RED)

    def load_linked_payments(self):
        if not self.linked_voucher_dd.value: return
        vid = int(self.linked_voucher_dd.value)
        details = get_voucher_details(vid)
        linked = details.get('linked_payments', [])
        if linked:
            df = pd.DataFrame(linked)
            cols = [c for c in ['id', 'invoice_id', 'amount', 'payment_date', 'payment_method'] if c in df.columns]
            content = [temp_data_table(df[cols])]
            
            payment_opts = {f"دفعة #{p['id']} - فاتورة #{p['invoice_id']} - {float(p['amount']):,.2f}": p for p in linked}
            pay_dd = ft.Dropdown(label="اختر الدفعة لإلغاء ربطها", options=[ft.dropdown.Option(k) for k in payment_opts.keys()])
            if payment_opts: pay_dd.value = list(payment_opts.keys())[0]
            
            def do_unlink(e):
                sel_pay = payment_opts[pay_dd.value]
                ok, err = unlink_voucher_from_invoice(sel_pay['id'])
                if ok:
                    self.show_snackbar(f"✅ تم إلغاء ربط الدفعة #{sel_pay['id']}", ACCENT_GREEN)
                    self.refresh_link_data()
                else:
                    self.show_snackbar(f"❌ {err}", ACCENT_RED)
                    
            content.append(pay_dd)
            content.append(ft.ElevatedButton("🗑️ إلغاء الربط", on_click=do_unlink, bgcolor=ACCENT_RED, color=ft.colors.WHITE))
            self.linked_payments_container.content = ft.Column(content)
        else:
            self.linked_payments_container.content = ft.Text("لا توجد دفعات مرتبطة بهذا السند", color=TEXT_SECONDARY)
        self.page.update()
