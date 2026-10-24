# ui_flet/pages/purchases.py
import flet as ft
import pandas as pd
from services.purchases_service import (
    get_suppliers, get_products_for_purchase, create_purchase_invoice,
    get_purchase_invoices, get_invoice_details, add_supplier,
    get_all_suppliers, create_payment_voucher_for_invoice,
)
from services.currency_service import get_all_currencies, get_base_currency
from services.expenses_service import get_payment_accounts
from services.vat_service import get_vat_rate
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

PAYMENT_STATUS_LABELS = {"unpaid": "🔴 غير مدفوعة", "partial": "🟡 مدفوعة جزئياً", "paid": "🟢 مدفوعة بالكامل"}
PAYMENT_METHOD_LABELS = {"cash": "نقدي", "bank": "بنكي", "credit": "آجل", "mixed": "مختلط"}

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

class PurchasesPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.purchase_items = []

        self.header = ft.Text("🚚 إدارة المشتريات", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إنشاء فواتير الشراء وإدارة الموردين", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📝 إنشاء فاتورة", content=self.build_invoice_tab()),
                ft.Tab(text="📋 فواتير المشتريات", content=self.build_invoices_tab()),
                ft.Tab(text="👥 الموردين", content=self.build_suppliers_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. إنشاء فاتورة
    # ============================================================
    def build_invoice_tab(self):
        suppliers = get_suppliers()
        self.supplier_dd = ft.Dropdown(
            label="اختر المورد",
            options=[ft.dropdown.Option(key=str(s['id']), text=s['name']) for s in suppliers] if suppliers else [],
            value=str(suppliers[0]['id']) if suppliers else None,
            expand=True, disabled=not suppliers
        )
        
        currencies = get_all_currencies()
        base_currency = get_base_currency()
        curr_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
        default_label = next((k for k, v in curr_options.items() if v == (base_currency['code'] if base_currency else 'YER')), list(curr_options.keys())[0]) if curr_options else None
        self.currency_dd = ft.Dropdown(label="💱 العملة", options=[ft.dropdown.Option(k) for k in curr_options.keys()], value=default_label, expand=True)

        self.products_data = get_products_for_purchase()
        self.product_dd = ft.Dropdown(
            label="اختر المنتج",
            options=[ft.dropdown.Option(key=str(p['id']), text=p['name']) for p in self.products_data] if self.products_data else [],
            expand=True, disabled=not self.products_data
        )
        if self.products_data: self.product_dd.value = str(self.products_data[0]['id'])

        self.qty_input = ft.TextField(label="الكمية", value="1", keyboard_type=ft.KeyboardType.NUMBER, width=100)
        self.unit_price_input = ft.TextField(label="سعر الشراء للوحدة", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=150)

        # تحديث سعر الوحدة تلقائياً عند تغيير المنتج
        def on_product_change(e):
            if not self.product_dd.value: return
            prod = next(p for p in self.products_data if str(p['id']) == self.product_dd.value)
            self.unit_price_input.value = str(prod['purchase_price'] or 0)
            self.page.update()
        self.product_dd.on_change = on_product_change
        if self.products_data: on_product_change(None)

        def add_item(e):
            if not self.product_dd.value: return
            try: 
                qty = int(self.qty_input.value)
                price = float(self.unit_price_input.value)
            except ValueError: 
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return
            
            product = next(p for p in self.products_data if str(p['id']) == self.product_dd.value)
            self.purchase_items.append({
                "product_id": product['id'], "name": product['name'],
                "quantity": qty, "unit_price": price, "total": qty * price
            })
            self.show_snackbar(f"تمت إضافة {product['name']}", ACCENT_GREEN)
            self.refresh_items_display()

        self.items_table_container = ft.Container()
        self.totals_text = ft.Text("", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD)
        self.vat_details_text = ft.Text("", color=TEXT_SECONDARY, size=12)

        self.payment_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="cash", label="نقدي/بنكي (فوري)"),
                ft.Radio(value="credit", label="آجل"),
                ft.Radio(value="partial", label="جزئي")
            ]),
            value="cash", on_change=self.on_payment_change
        )
        
        self.account_dd = ft.Dropdown(label="💵 من صندوق/بنك", expand=True)
        self.paid_amount_input = ft.TextField(label="المبلغ المدفوع الآن", value="0", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        self.paid_status_text = ft.Text("", color=ACCENT_ORANGE, size=13)

        self.save_btn = ft.ElevatedButton("💾 حفظ فاتورة المشتريات", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=self.save_invoice)
        self.clear_btn = ft.ElevatedButton("🗑️ مسح البنود", bgcolor=ACCENT_RED, color=ft.colors.WHITE, on_click=self.clear_items)

        self.on_payment_change(None)

        return ft.Column([
            ft.Text("إنشاء فاتورة مشتريات جديدة", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.supplier_dd, self.currency_dd]),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("إضافة منتجات", color=ACCENT_GREEN, size=16, weight=ft.FontWeight.BOLD),
            ft.Row([self.product_dd, self.qty_input, self.unit_price_input, ft.ElevatedButton("➕ إضافة", on_click=add_item, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)]),
            self.items_table_container,
            ft.Column([self.totals_text, self.vat_details_text], spacing=2),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("💳 تفاصيل الدفع للمورد", color=ACCENT_ORANGE, size=16, weight=ft.FontWeight.BOLD),
            self.payment_radio,
            self.account_dd,
            self.paid_amount_input,
            self.paid_status_text,
            ft.Row([self.save_btn, self.clear_btn], spacing=15)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    def on_payment_change(self, e):
        self.payment_choice = self.payment_radio.value
        self.paid_amount_input.visible = self.payment_choice == "partial"
        
        if self.payment_choice in ('cash', 'partial'):
            accounts = get_payment_accounts()
            self.account_dd.options = [ft.dropdown.Option(key=str(a['id']), text=_format_account_label(a)) for a in accounts]
            if accounts and not self.account_dd.value: self.account_dd.value = str(accounts[0]['id'])
            self.account_dd.visible = True
        else:
            self.account_dd.visible = False
            
        self.update_payment_status()
        self.page.update()

    def update_payment_status(self):
        if not hasattr(self, 'payment_choice'): return
        total, vat, total_w_vat = self.calculate_totals()
        
        if self.payment_choice == "cash":
            self.paid_status_text.value = f"💵 سيتم دفع {total_w_vat:,.2f} للمورد فوراً (شامل الضريبة)"
            self.paid_status_text.color = ACCENT_GREEN
        elif self.payment_choice == "credit":
            self.paid_status_text.value = f"📌 سيتم تسجيل {total_w_vat:,.2f} على حساب المورد"
            self.paid_status_text.color = ACCENT_ORANGE
        else:
            try: paid = float(self.paid_amount_input.value or 0)
            except ValueError: paid = 0.0
            remaining = total_w_vat - paid
            acc = next((a for a in get_payment_accounts() if str(a['id']) == self.account_dd.value), None)
            if acc and paid > acc['balance']:
                self.paid_status_text.value = f"⚠️ الرصيد غير كافٍ! المتاح: {acc['balance']:,.2f} | متبقي: {remaining:,.2f}"
                self.paid_status_text.color = ACCENT_RED
            else:
                self.paid_status_text.value = f"💵 مدفوع: {paid:,.2f} | 🔴 متبقي: {remaining:,.2f}"
                self.paid_status_text.color = ACCENT_ORANGE
        self.page.update()

    def calculate_totals(self):
        total = sum(item["total"] for item in self.purchase_items)
        try: vat_rate = float(get_vat_rate() or 0)
        except Exception: vat_rate = 0.0
        vat = total * vat_rate
        return total, vat, total + vat

    def refresh_items_display(self):
        if self.purchase_items:
            df = pd.DataFrame(self.purchase_items).rename(columns={"name": "المنتج", "quantity": "الكمية", "unit_price": "السعر", "total": "الإجمالي"})
            self.items_table_container.content = temp_data_table(df[["المنتج", "الكمية", "السعر", "الإجمالي"]])
            total, vat, total_w_vat = self.calculate_totals()
            currency = self.currency_dd.value.split(" - ")[0] if self.currency_dd.value else "YER"
            self.totals_text.value = f"الإجمالي: {total:,.2f} {currency}"
            self.vat_details_text.value = f"الفرعي: {total:,.2f} | الضريبة ({get_vat_rate()*100:.0f}%): {vat:,.2f} | الإجمالي النهائي: {total_w_vat:,.2f}"
            self.save_btn.disabled = False
        else:
            self.items_table_container.content = ft.Text("لا توجد بنود بعد", color=TEXT_SECONDARY)
            self.totals_text.value = ""
            self.vat_details_text.value = ""
            self.save_btn.disabled = True
        self.update_payment_status()
        self.page.update()

    def clear_items(self, e):
        self.purchase_items = []
        self.refresh_items_display()

    def save_invoice(self, e):
        if not self.purchase_items or not self.supplier_dd.value: return
        
        total, vat, total_w_vat = self.calculate_totals()
        currency_code = self.currency_dd.value.split(" - ")[0] if self.currency_dd.value else "YER"
        
        actual_paid = 0.0
        actual_method = "credit"
        cash_account = None
        selected_acc = None

        if self.payment_choice in ('cash', 'partial'):
            selected_acc = next((a for a in get_payment_accounts() if str(a['id']) == self.account_dd.value), None)
            if not selected_acc:
                self.show_snackbar("⚠️ اختر حساباً صحيحاً", ACCENT_RED); return

        if self.payment_choice == "cash":
            actual_paid = total_w_vat
            actual_method = selected_acc['type']
            cash_account = selected_acc['code']
        elif self.payment_choice == "partial":
            try: actual_paid = float(self.paid_amount_input.value or 0)
            except ValueError: actual_paid = 0.0
            if actual_paid > selected_acc['balance']:
                self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {selected_acc['balance']:,.2f}", ACCENT_RED); return
            actual_method = "mixed" if actual_paid < total_w_vat else selected_acc['type']
            cash_account = selected_acc['code']

        try:
            invoice_id, total_saved, error = create_purchase_invoice(
                supplier_id=int(self.supplier_dd.value),
                items=self.purchase_items,
                username="admin",
                currency_code=currency_code,
                paid_amount=actual_paid,
                payment_method=actual_method,
                cash_account=cash_account
            )
            if error and invoice_id is None:
                self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)
            elif error and invoice_id:
                self.show_snackbar(f"⚠️ تم حفظ الفاتورة {invoice_id} بدون سند: {error}", ACCENT_ORANGE)
                self.clear_items(None)
            else:
                self.show_snackbar(f"✅ تم حفظ الفاتورة رقم {invoice_id} — المدفوع: {actual_paid:,.2f}", ACCENT_GREEN)
                self.clear_items(None)
        except Exception as ex:
            self.show_snackbar(f"❌ خطأ: {ex}", ACCENT_RED)

    # ============================================================
    # 2. فواتير المشتريات
    # ============================================================
    def build_invoices_tab(self):
        self.invoices_container = ft.Container()
        self.details_container = ft.Container()
        self.inv_selector = ft.Dropdown(label="اختر فاتورة", on_change=lambda e: self.load_invoice_details(int(e.control.value)))
        self.load_invoices()
        
        return ft.Column([
            ft.Text("فواتير المشتريات المسجلة", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            self.invoices_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("تفاصيل الفاتورة", color=ACCENT_BLUE, size=16, weight=ft.FontWeight.BOLD),
            self.inv_selector,
            self.details_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_invoices(self):
        all_invoices = get_purchase_invoices()
        if all_invoices:
            df = pd.DataFrame(all_invoices)
            cols = [c for c in ["id", "supplier", "invoice_date", "total", "paid_amount", "remaining_amount", "payment_status"] if c in df.columns]
            df_display = df[cols].copy()
            if "payment_status" in df_display.columns:
                df_display["payment_status"] = df_display["payment_status"].map(PAYMENT_STATUS_LABELS).fillna(df_display["payment_status"])
            if "has_warning" in df.columns:
                df_display["⚠️"] = df["has_warning"].apply(lambda x: "⚠️" if x else "✅")
                
            self.invoices_container.content = temp_data_table(df_display)
            
            inv_ids = [str(inv['id']) for inv in all_invoices]
            self.inv_selector.options = [ft.dropdown.Option(i) for i in inv_ids]
            if inv_ids:
                self.inv_selector.value = inv_ids[0]
                self.load_invoice_details(int(inv_ids[0]))
        else:
            self.invoices_container.content = ft.Text("لا توجد فواتير مشتريات بعد", color=TEXT_SECONDARY)

    def load_invoice_details(self, inv_id):
        all_invoices = get_purchase_invoices()
        details = get_invoice_details(inv_id)
        inv = next((i for i in all_invoices if i['id'] == inv_id), None)
        
        content = []
        if details:
            df = pd.DataFrame(details)
            content.append(temp_data_table(df))
            content.append(ft.Text(f"الإجمالي: {sum(d['total'] for d in details):,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD))
        
        if inv:
            content.append(ft.Row([
                ft.Text(f"الإجمالي: {float(inv['total']):,.2f}", color=TEXT_PRIMARY),
                ft.Text(f"المدفوع: {float(inv.get('paid_amount',0)):,.2f}", color=ACCENT_GREEN),
                ft.Text(f"المتبقي: {float(inv.get('remaining_amount',0)):,.2f}", color=ACCENT_RED)
            ], spacing=20))
            content.append(ft.Text(f"الحالة: {PAYMENT_STATUS_LABELS.get(inv.get('payment_status'), '—')} | الطريقة: {PAYMENT_METHOD_LABELS.get(inv.get('payment_method'), '—')}", color=TEXT_SECONDARY))
        
            if inv.get('has_warning'):
                content.append(ft.Container(
                    content=ft.Text(f"⚠️ تنبيه: {inv.get('reference', '')}", color=ACCENT_RED),
                    bgcolor=ft.colors.with_opacity(0.1, ACCENT_RED), padding=10, border_radius=8
                ))
                
                paid_amt = float(inv.get('paid_amount', 0))
                if paid_amt > 0:
                    manual_accounts = get_payment_accounts()
                    if manual_accounts:
                        manual_dd = ft.Dropdown(
                            label="💵 من أي صندوق/بنك سيتم الصرف؟",
                            options=[ft.dropdown.Option(key=str(a['id']), text=_format_account_label(a)) for a in manual_accounts],
                            value=str(manual_accounts[0]['id'])
                        )
                        
                        def do_manual_voucher(e):
                            acc = next(a for a in manual_accounts if str(a['id']) == manual_dd.value)
                            if paid_amt > acc['balance']:
                                self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {acc['balance']:,.2f}", ACCENT_RED); return
                            vid, verr = create_payment_voucher_for_invoice(
                                invoice_id=inv_id, username="admin", payment_account_code=acc['code']
                            )
                            if verr:
                                self.show_snackbar(f"❌ فشل: {verr}", ACCENT_RED)
                            else:
                                self.show_snackbar(f"✅ تم إنشاء سند الصرف رقم {vid}", ACCENT_GREEN)
                                self.load_invoices()
                                
                        content.append(ft.Column([
                            ft.Text("🔧 إنشاء سند الصرف يدوياً", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
                            manual_dd,
                            ft.ElevatedButton("🔧 إنشاء سند الصرف", on_click=do_manual_voucher, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
                        ], spacing=10))

        self.details_container.content = ft.Column(content, spacing=10)
        self.page.update()

    # ============================================================
    # 3. الموردين
    # ============================================================
    def build_suppliers_tab(self):
        self.supp_name = ft.TextField(label="اسم المورد", expand=True)
        self.supp_phone = ft.TextField(label="رقم الهاتف", expand=True)
        self.supp_addr = ft.TextField(label="عنوان المورد", expand=True)
        self.suppliers_table_container = ft.Container()

        def add_supp(e):
            if not self.supp_name.value:
                self.show_snackbar("اسم المورد مطلوب", ACCENT_RED); return
            add_supplier(self.supp_name.value, self.supp_phone.value, self.supp_addr.value, "admin")
            self.show_snackbar(f"تمت إضافة {self.supp_name.value}", ACCENT_GREEN)
            self.supp_name.value = ""; self.supp_phone.value = ""; self.supp_addr.value = ""
            self.load_suppliers()
            
            suppliers = get_suppliers()
            self.supplier_dd.options = [ft.dropdown.Option(key=str(s['id']), text=s['name']) for s in suppliers]
            self.supplier_dd.disabled = not suppliers
            if suppliers and not self.supplier_dd.value: self.supplier_dd.value = str(suppliers[0]['id'])
            self.page.update()

        self.load_suppliers()

        return ft.Column([
            ft.Text("إضافة مورد جديد", color=ACCENT_ORANGE, size=16, weight=ft.FontWeight.BOLD),
            ft.Row([self.supp_name, self.supp_phone]),
            self.supp_addr,
            ft.ElevatedButton("➕ إضافة المورد", on_click=add_supp, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("الموردين الحاليين", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            self.suppliers_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_suppliers(self):
        suppliers = get_all_suppliers()
        if suppliers:
            self.suppliers_table_container.content = temp_data_table(pd.DataFrame(suppliers))
        else:
            self.suppliers_table_container.content = ft.Text("لا يوجد موردون بعد", color=TEXT_SECONDARY)
        self.page.update()
