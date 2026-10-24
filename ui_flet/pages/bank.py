# ui_flet/pages/bank.py
import flet as ft
import pandas as pd
from datetime import date
from services import bank_service as bank
from services import cash_service
from services.bank_service import transfer_funds
from services.currency_service import get_all_currencies, get_base_currency
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

def _build_transfer_options():
    bank_accounts = bank.get_all_bank_accounts(active_only=True)
    cash_accounts = cash_service.get_all_cash_accounts(active_only=True)
    options, options_map = [], {}
    for b in bank_accounts:
        key = f"bank_{b['id']}"
        options.append(key)
        options_map[key] = {"kind": "bank", "id": b['id'], "name": b['bank_name'], "currency": b.get('currency_code') or '', "balance": float(b.get('current_balance') or 0)}
    for c in cash_accounts:
        key = f"cash_{c['id']}"
        options.append(key)
        options_map[key] = {"kind": "cash", "id": c['id'], "name": c['name'], "currency": c.get('currency_code') or '', "balance": float(c.get('current_balance') or 0)}
    return options, options_map

def _format_transfer_option(key, options_map):
    info = options_map.get(key)
    if not info: return "?"
    icon = "🏦" if info["kind"] == "bank" else "💵"
    return f"{icon} {info['name']} ({info['currency']}) — {info['balance']:,.2f}"

def _get_recent_transfers():
    from database import get_connection, close_connection
    conn = get_connection()
    try:
        rows = []
        try:
            rows.extend([dict(r) for r in conn.execute("SELECT bt.reference, bt.transaction_date, bt.type, bt.amount, ba.bank_name as acc_name, ba.currency_code as currency FROM bank_transactions bt JOIN bank_accounts ba ON bt.bank_account_id = ba.id WHERE bt.reference LIKE 'TR-%'").fetchall()])
        except Exception: pass
        try:
            rows.extend([dict(r) for r in conn.execute("SELECT ct.reference, ct.transaction_date, ct.type, ct.amount, ca.name as acc_name, ca.currency_code as currency FROM cash_transactions ct JOIN cash_accounts ca ON ct.cash_account_id = ca.id WHERE ct.reference LIKE 'TR-%'").fetchall()])
        except Exception: pass

        if not rows: return []
        grouped = {}
        for r in rows:
            ref = r['reference']
            if ref not in grouped:
                grouped[ref] = {'reference': ref, 'date': r['transaction_date'], 'source': None, 'destination': None, 'amount': None, 'currency': r['currency']}
            if r['type'] in ('transfer_out', 'withdrawal'):
                grouped[ref]['source'] = r['acc_name']; grouped[ref]['amount'] = r['amount']
            elif r['type'] in ('transfer_in', 'deposit'):
                grouped[ref]['destination'] = r['acc_name']
        sorted_refs = sorted(grouped.values(), key=lambda x: (x['date'] or '', x['reference']), reverse=True)[:20]
        return [{"المرجع": g['reference'], "التاريخ": g['date'], "من": g['source'] or "—", "إلى": g['destination'] or "—", "المبلغ": f"{g['amount']:,.2f} {g['currency']}" if g['amount'] else "—"} for g in sorted_refs]
    finally:
        close_connection(conn)

class BankPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("🏦 التعاملات البنكية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة الحسابات البنكية والحركات والمصالحات والتحويلات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="🏛️ الحسابات", content=self.build_accounts_tab()),
                ft.Tab(text="💳 الحركات", content=self.build_transactions_tab()),
                ft.Tab(text="🔄 تحويل", content=self.build_transfer_tab()),
                ft.Tab(text="⚖️ مصالحة", content=self.build_reconciliation_tab()),
                ft.Tab(text="📊 ملخص", content=self.build_summary_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. الحسابات
    # ============================================================
    def build_accounts_tab(self):
        currencies = get_all_currencies()
        base = get_base_currency()
        curr_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
        default_label = next((k for k, v in curr_options.items() if v == (base['code'] if base else 'YER')), list(curr_options.keys())[0]) if curr_options else None

        self.new_bank_name = ft.TextField(label="اسم البنك", hint_text="مثال: بنك الكريمي", expand=True)
        self.new_acc_number = ft.TextField(label="رقم الحساب", expand=True)
        self.new_acc_name = ft.TextField(label="اسم الحساب (اختياري)", expand=True)
        self.new_currency = ft.Dropdown(label="العملة", options=[ft.dropdown.Option(k) for k in curr_options.keys()], value=default_label, expand=True)
        self.new_opening = ft.TextField(label="الرصيد الافتتاحي", value="0", keyboard_type=ft.KeyboardType.NUMBER)

        def add_bank_acc(e):
            if not self.new_bank_name.value or not self.new_acc_number.value:
                self.show_snackbar("اسم البنك ورقم الحساب مطلوبان", ACCENT_RED); return
            try:
                bank.create_bank_account(
                    self.new_bank_name.value, self.new_acc_number.value, self.new_acc_name.value,
                    curr_options[self.new_currency.value], float(self.new_opening.value or 0)
                )
                self.show_snackbar("تمت إضافة الحساب البنكي", ACCENT_GREEN)
                self.new_bank_name.value = ""; self.new_acc_number.value = ""; self.new_acc_name.value = ""; self.new_opening.value = "0"
                self.load_accounts_list(); self.refresh_all_dropdowns()
            except Exception as ex:
                self.show_snackbar(str(ex), ACCENT_RED)

        form_container = ft.Container(
            content=ft.Column([
                ft.Text("➕ إضافة حساب بنكي", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                self.new_bank_name, self.new_acc_number, self.new_acc_name,
                ft.Row([self.new_currency]), self.new_opening,
                ft.ElevatedButton("✅ إضافة", on_click=add_bank_acc, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
            ]),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

        self.accounts_list_col = ft.Column(spacing=5)
        self.load_accounts_list()

        list_container = ft.Container(
            content=ft.Column([
                ft.Text("📋 الحسابات البنكية", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                self.accounts_list_col
            ]),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

        return ft.Row([form_container, list_container], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)

    def load_accounts_list(self):
        accounts = bank.get_all_bank_accounts(active_only=False)
        self.accounts_list_col.controls.clear()
        if accounts:
            for acc in accounts:
                active_badge = "🟢" if acc['is_active'] else "🔴"
                self.accounts_list_col.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{acc['bank_name']} - {acc['account_number']}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{acc.get('account_name','')} | {acc['currency_code']} | الرصيد: {acc['current_balance']:,.2f} {active_badge}", color=TEXT_SECONDARY, size=12)
                        ], spacing=2),
                        padding=8,
                        border=ft.border.only(bottom=ft.border.BorderSide(1, GLASS_BORDER))
                    )
                )
        else:
            self.accounts_list_col.controls.append(ft.Text("لا توجد حسابات بنكية", color=TEXT_SECONDARY))
        self.page.update()

    # ============================================================
    # 2. الحركات
    # ============================================================
    def build_transactions_tab(self):
        self.tx_acc_dd = ft.Dropdown(label="اختر الحساب", expand=True)
        self.tx_date = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.tx_type = ft.Dropdown(
            label="نوع الحركة",
            options=[ft.dropdown.Option(k, text=v) for k, v in {"deposit": "إيداع", "withdrawal": "سحب", "transfer_in": "تحويل وارد", "transfer_out": "تحويل صادر"}.items()],
            value="deposit", expand=True
        )
        self.tx_amount = ft.TextField(label="المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.tx_ref = ft.TextField(label="المرجع (اختياري)", expand=True)
        self.tx_desc = ft.TextField(label="البيان", expand=True)

        self.refresh_tx_accounts()

        def add_tx(e):
            if not self.tx_acc_dd.value: return
            if not self.tx_desc.value:
                self.show_snackbar("البيان مطلوب", ACCENT_RED); return
            try: amount = float(self.tx_amount.value)
            except ValueError: self.show_snackbar("مبلغ غير صالح", ACCENT_RED); return
            acc_id = int(self.tx_acc_dd.value.split("_")[1])
            try:
                bank.add_bank_transaction(acc_id, self.tx_date.value, self.tx_desc.value, self.tx_type.value, amount, self.tx_ref.value)
                self.show_snackbar("تم تسجيل الحركة", ACCENT_GREEN)
                self.tx_amount.value = "0"; self.tx_desc.value = ""; self.tx_ref.value = ""
                self.load_tx_table(); self.load_accounts_list()
            except Exception as ex:
                self.show_snackbar(str(ex), ACCENT_RED)

        form = ft.Column([
            ft.Text("تسجيل حركة بنكية", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            self.tx_acc_dd,
            ft.Row([self.tx_date, self.tx_type]),
            ft.Row([self.tx_amount, self.tx_ref]),
            self.tx_desc,
            ft.ElevatedButton("💾 حفظ الحركة", on_click=add_tx, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER)
        ])

        self.tx_filter_dd = ft.Dropdown(label="تصفية حسب الحساب", expand=True)
        self.load_tx_filters()
        self.tx_filter_dd.on_change = lambda e: self.load_tx_table()

        self.tx_table_container = ft.Container()
        self.load_tx_table()

        return ft.Column([form, self.tx_filter_dd, self.tx_table_container], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def refresh_tx_accounts(self):
        accounts = bank.get_all_bank_accounts()
        self.tx_acc_dd.options = [ft.dropdown.Option(f"bank_{a['id']}", text=f"{a['bank_name']} - {a['account_number']}") for a in accounts]
        if accounts and not self.tx_acc_dd.value: self.tx_acc_dd.value = f"bank_{accounts[0]['id']}"

    def load_tx_filters(self):
        active = bank.get_all_bank_accounts(active_only=True)
        self.tx_filter_dd.options = [ft.dropdown.Option("all", text="الكل")] + [ft.dropdown.Option(f"bank_{a['id']}", text=f"{a['bank_name']} - {a['account_number']}") for a in active]
        self.tx_filter_dd.value = "all"

    def load_tx_table(self):
        if self.tx_filter_dd.value == "all":
            transactions = bank.get_bank_transactions()
        else:
            sel_id = int(self.tx_filter_dd.value.split("_")[1])
            transactions = bank.get_bank_transactions(bank_account_id=sel_id)
        
        if transactions:
            df = pd.DataFrame(transactions)
            df['type'] = df['type'].map({"deposit": "إيداع", "withdrawal": "سحب", "transfer_in": "تحويل وارد", "transfer_out": "تحويل صادر"})
            self.tx_table_container.content = temp_data_table(df)
        else:
            self.tx_table_container.content = ft.Text("لا توجد حركات", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 3. تحويل
    # ============================================================
    def build_transfer_tab(self):
        self.transfer_from_dd = ft.Dropdown(label="📤 من (المصدر)", expand=True)
        self.transfer_to_dd = ft.Dropdown(label="📥 إلى (الهدف)", expand=True)
        self.transfer_amount = ft.TextField(label="💰 المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.transfer_date = ft.TextField(label="📅 التاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.transfer_desc = ft.TextField(label="📝 البيان", value="تحويل بين الحسابات", expand=True)
        self.transfer_ref = ft.TextField(label="🔖 المرجع (اختياري)", expand=True)
        self.recent_transfers_container = ft.Container()
        self.load_transfer_options()

        def do_transfer(e):
            if not self.transfer_from_dd.value or not self.transfer_to_dd.value: return
            if self.transfer_from_dd.value == self.transfer_to_dd.value: self.show_snackbar("لا يمكن التحويل لنفس الحساب", ACCENT_RED); return
            try: amount = float(self.transfer_amount.value)
            except ValueError: self.show_snackbar("مبلغ غير صالح", ACCENT_RED); return

            from_info = self.transfer_map[self.transfer_from_dd.value]
            to_info = self.transfer_map[self.transfer_to_dd.value]

            if from_info["currency"] != to_info["currency"]:
                self.show_snackbar("لا يمكن التحويل بين عملتين مختلفتين", ACCENT_RED); return
            if amount > from_info["balance"] + 0.001:
                self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {from_info['balance']:,.2f}", ACCENT_RED); return

            journal_id, err = transfer_funds(
                from_kind=from_info["kind"], from_id=from_info["id"],
                to_kind=to_info["kind"], to_id=to_info["id"],
                amount=amount, transfer_date=self.transfer_date.value,
                description=self.transfer_desc.value, reference=self.transfer_ref.value
            )
            if err: self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
            else:
                self.show_snackbar(f"✅ تم التحويل — القيد: {journal_id}", ACCENT_GREEN)
                self.transfer_amount.value = "0"; self.transfer_ref.value = ""
                self.load_transfer_options(); self.load_recent_transfers(); self.load_accounts_list()

        return ft.Column([
            ft.Text("🔄 تحويل بين الحسابات", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.transfer_from_dd, self.transfer_to_dd]),
            ft.Row([self.transfer_amount, self.transfer_date]),
            ft.Row([self.transfer_desc, self.transfer_ref]),
            ft.ElevatedButton("🔄 تنفيذ التحويل", on_click=do_transfer, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📋 آخر التحويلات", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            self.recent_transfers_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_transfer_options(self):
        options, options_map = _build_transfer_options()
        self.transfer_map = options_map
        if len(options) < 2:
            self.transfer_from_dd.options = []; self.transfer_to_dd.options = []; return
        self.transfer_from_dd.options = [ft.dropdown.Option(k, text=_format_transfer_option(k, options_map)) for k in options]
        if not self.transfer_from_dd.value: self.transfer_from_dd.value = options[0]
        to_options = [k for k in options if k != self.transfer_from_dd.value]
        self.transfer_to_dd.options = [ft.dropdown.Option(k, text=_format_transfer_option(k, options_map)) for k in to_options]
        if self.transfer_to_dd.value not in to_options: self.transfer_to_dd.value = to_options[0] if to_options else None
        
        self.transfer_from_dd.on_change = lambda e: self.update_to_options()
        self.load_recent_transfers()

    def update_to_options(self):
        options, _ = _build_transfer_options()
        to_options = [k for k in options if k != self.transfer_from_dd.value]
        self.transfer_to_dd.options = [ft.dropdown.Option(k, text=_format_transfer_option(k, self.transfer_map)) for k in to_options]
        if self.transfer_to_dd.value not in to_options: self.transfer_to_dd.value = to_options[0] if to_options else None
        self.page.update()

    def load_recent_transfers(self):
        recent = _get_recent_transfers()
        if recent: self.recent_transfers_container.content = temp_data_table(pd.DataFrame(recent))
        else: self.recent_transfers_container.content = ft.Text("لا توجد تحويلات سابقة", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 4. المصالحة
    # ============================================================
    def build_reconciliation_tab(self):
        accounts = bank.get_all_bank_accounts()
        if not accounts: return ft.Text("لا توجد حسابات", color=TEXT_SECONDARY)

        self.rec_acc_dd = ft.Dropdown(
            label="اختر الحساب",
            options=[ft.dropdown.Option(f"bank_{a['id']}", text=f"{a['bank_name']} - {a['account_number']}") for a in accounts],
            value=f"bank_{accounts[0]['id']}", expand=True
        )
        self.rec_balance_text = ft.Text("", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.rec_date = ft.TextField(label="تاريخ كشف البنك", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.rec_stmt_balance = ft.TextField(label="رصيد كشف البنك", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.rec_notes = ft.TextField(label="ملاحظات المصالحة (اختياري)", multiline=True, min_lines=2)
        self.rec_result = ft.Text("", color=TEXT_SECONDARY)
        self.unrec_container = ft.Container()
        
        def update_balance_display(e=None):
            acc_id = int(self.rec_acc_dd.value.split("_")[1])
            acc = next(a for a in accounts if a['id'] == acc_id)
            self.rec_balance_text.value = f"رصيد الدفاتر الحالي: {acc['current_balance']:,.2f} {acc['currency_code']}"
            self.load_unrec(acc_id)
            self.page.update()

        self.rec_acc_dd.on_change = update_balance_display
        update_balance_display()

        def do_reconcile(e):
            acc_id = int(self.rec_acc_dd.value.split("_")[1])
            try: stmt_balance = float(self.rec_stmt_balance.value)
            except ValueError: self.show_snackbar("رصيد غير صالح", ACCENT_RED); return
            
            success, diff = bank.create_bank_reconciliation(acc_id, self.rec_date.value, stmt_balance, notes=self.rec_notes.value)
            if success:
                self.rec_result.value = f"✅ تمت المصالحة. الفرق: {diff:,.2f}"
                self.rec_result.color = ACCENT_GREEN
                update_balance_display()
            else:
                self.rec_result.value = "فشلت المصالحة"
                self.rec_result.color = ACCENT_RED
            self.page.update()

        return ft.Column([
            ft.Text("⚖️ المصالحة البنكية", color=ACCENT_ORANGE, size=20, weight=ft.FontWeight.BOLD),
            self.rec_acc_dd, self.rec_balance_text,
            ft.Row([self.rec_date, self.rec_stmt_balance]),
            self.rec_notes,
            ft.ElevatedButton("🔍 تنفيذ المصالحة", on_click=do_reconcile, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            self.rec_result,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("حركات غير مسواة", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            self.unrec_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_unrec(self, acc_id):
        unrec = bank.get_unreconciled_transactions(acc_id)
        if unrec: self.unrec_container.content = temp_data_table(pd.DataFrame(unrec))
        else: self.unrec_container.content = ft.Text("لا توجد حركات غير مسواة", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 5. ملخص
    # ============================================================
    def build_summary_tab(self):
        self.summary_container = ft.Container()
        self.rec_history_container = ft.Container()
        self.load_summary()
        
        return ft.Column([
            ft.Text("📊 ملخص الأرصدة البنكية", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.summary_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📋 سجل المصالحات", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            self.rec_history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_summary(self):
        summary, total_base = bank.get_bank_balance_summary()
        if summary:
            df = pd.DataFrame(summary)
            base_cur = get_base_currency()
            base_code = base_cur['code'] if base_cur else 'YER'
            self.summary_container.content = ft.Column([
                temp_data_table(df),
                ft.Text(f"إجمالي الأرصدة بالعملة الأساسية ({base_code}): {total_base:,.2f}", color=ACCENT_PURPLE, weight=ft.FontWeight.BOLD, size=16)
            ])
        else:
            self.summary_container.content = ft.Text("لا توجد حسابات بنكية نشطة", color=TEXT_SECONDARY)

        rec = bank.get_reconciliation_history()
        if rec:
            df_rec = pd.DataFrame(rec)
            cols = [c for c in ['id', 'reconciliation_date', 'statement_balance', 'book_balance', 'difference', 'notes'] if c in df_rec.columns]
            self.rec_history_container.content = temp_data_table(df_rec[cols])
        else:
            self.rec_history_container.content = ft.Text("لا توجد مصالحات سابقة", color=TEXT_SECONDARY)
        self.page.update()

    def refresh_all_dropdowns(self):
        self.refresh_tx_accounts()
        if hasattr(self, 'load_transfer_options'): self.load_transfer_options()
        if hasattr(self, 'tx_filter_dd'): self.load_tx_filters()
        self.page.update()
