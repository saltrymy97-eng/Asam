# ui_flet/pages/cash.py
import flet as ft
import pandas as pd
from datetime import date
from services.cash_service import (
    create_cash_tables, create_cash_account, get_all_cash_accounts,
    add_cash_transaction, get_cash_transactions, get_cash_statement,
    get_cash_balance_summary,
)
from services import bank_service
from services.bank_service import transfer_funds
from services.currency_service import get_all_currencies
from database import get_connection, close_connection
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"
ACCENT_CYAN = "#06B6D4"

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
    bank_accounts = bank_service.get_all_bank_accounts(active_only=True)
    cash_accounts = get_all_cash_accounts(active_only=True)
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
    conn = get_connection()
    try:
        rows = []
        try:
            bank_rows = conn.execute("""
                SELECT bt.reference, bt.transaction_date, bt.type, bt.amount, ba.bank_name as acc_name, ba.currency_code as currency
                FROM bank_transactions bt JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                WHERE bt.reference LIKE 'TR-%'
            """).fetchall()
            rows.extend([dict(r) for r in bank_rows])
        except Exception: pass
        try:
            cash_rows = conn.execute("""
                SELECT ct.reference, ct.transaction_date, ct.type, ct.amount, ca.name as acc_name, ca.currency_code as currency
                FROM cash_transactions ct JOIN cash_accounts ca ON ct.cash_account_id = ca.id
                WHERE ct.reference LIKE 'TR-%'
            """).fetchall()
            rows.extend([dict(r) for r in cash_rows])
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

class CashPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        try: create_cash_tables()
        except Exception as e: print(f"Cash init error: {e}")

        self.header = ft.Text("💰 إدارة الصندوق", size=30, color=GOLD, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("حسابات النقدية متعددة العملات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📊 الأرصدة", content=self.build_balances_tab()),
                ft.Tab(text="➕ إضافة صندوق", content=self.build_add_tab()),
                ft.Tab(text="💵 حركات", content=self.build_transactions_tab()),
                ft.Tab(text="🔄 تحويل", content=self.build_transfer_tab()),
                ft.Tab(text="📋 كشف حساب", content=self.build_statement_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def glass_card(self, title, icon, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=30),
                ft.Text(title, color=TEXT_SECONDARY, size=12),
                ft.Text(str(value), color=color, size=20, weight=ft.FontWeight.BOLD)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

    # ============================================================
    # 1. الأرصدة
    # ============================================================
    def build_balances_tab(self):
        self.balances_row = ft.Row(wrap=True, spacing=10)
        self.total_balance_text = ft.Text("", color=GOLD, size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        self.load_balances()
        return ft.Column([
            ft.Text("أرصدة الصناديق", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.balances_row,
            self.total_balance_text
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_balances(self):
        summary, total_base = get_cash_balance_summary()
        self.balances_row.controls.clear()
        if summary:
            for acc in summary:
                color = ACCENT_GREEN if acc['balance'] >= 0 else ACCENT_RED
                self.balances_row.controls.append(self.glass_card(acc['name'], "💵", f"{acc['balance']:,.2f} {acc['currency']}", color))
            self.total_balance_text.value = f"إجمالي الأرصدة (بالعملة الأساسية): {total_base:,.2f}"
        else:
            self.balances_row.controls.append(ft.Text("لا توجد حسابات صندوق.", color=TEXT_SECONDARY))
            self.total_balance_text.value = ""
        self.page.update()

    # ============================================================
    # 2. إضافة صندوق
    # ============================================================
    def build_add_tab(self):
        currencies = get_all_currencies()
        self.curr_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
        
        self.new_acc_name = ft.TextField(label="اسم الصندوق", hint_text="مثال: صندوق الدولار", expand=True)
        self.new_acc_currency = ft.Dropdown(label="العملة", options=[ft.dropdown.Option(k) for k in self.curr_options.keys()], value=list(self.curr_options.keys())[0] if self.curr_options else None, expand=True)
        self.new_acc_opening = ft.TextField(label="الرصيد الافتتاحي", value="0", keyboard_type=ft.KeyboardType.NUMBER)

        def add_acc(e):
            if not self.new_acc_name.value:
                self.show_snackbar("اسم الصندوق مطلوب", ACCENT_RED); return
            try: opening = float(self.new_acc_opening.value or 0)
            except ValueError: opening = 0.0
            success, msg = create_cash_account(self.new_acc_name.value, self.curr_options[self.new_acc_currency.value], opening)
            if success:
                self.show_snackbar(msg, ACCENT_GREEN)
                self.new_acc_name.value = ""; self.new_acc_opening.value = "0"
                self.load_balances()
                self.refresh_accounts_dropdowns()
            else: self.show_snackbar(msg, ACCENT_RED)

        return ft.Column([
            ft.Text("إضافة حساب صندوق جديد", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            self.new_acc_name,
            ft.Row([self.new_acc_currency, self.new_acc_opening]),
            ft.ElevatedButton("💾 حفظ الصندوق", on_click=add_acc, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 3. حركات
    # ============================================================
    def build_transactions_tab(self):
        self.tx_acc_dd = ft.Dropdown(label="اختر الصندوق", expand=True)
        self.tx_type_dd = ft.Dropdown(label="نوع الحركة", options=[ft.dropdown.Option("إيداع"), ft.dropdown.Option("سحب")], value="إيداع", expand=True)
        self.tx_amount = ft.TextField(label="المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.tx_date = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.tx_desc = ft.TextField(label="الوصف", expand=True)

        self.refresh_accounts_dropdowns()

        def add_tx(e):
            if not self.tx_acc_dd.value: return
            try: amount = float(self.tx_amount.value)
            except ValueError: self.show_snackbar("المبلغ غير صالح", ACCENT_RED); return
            if amount <= 0: self.show_snackbar("المبلغ يجب أن يكون أكبر من صفر", ACCENT_RED); return
            
            acc_id = int(self.tx_acc_dd.value.split("_")[1])
            t_type = "deposit" if self.tx_type_dd.value == "إيداع" else "withdrawal"
            success, msg = add_cash_transaction(acc_id, self.tx_date.value, self.tx_desc.value, t_type, amount)
            if success:
                self.show_snackbar(msg, ACCENT_GREEN)
                self.tx_amount.value = "0"; self.tx_desc.value = ""
                self.load_transactions_table()
                self.load_balances()
            else: self.show_snackbar(msg, ACCENT_RED)

        form = ft.Column([
            ft.Text("حركات الصندوق", color=ACCENT_ORANGE, size=20, weight=ft.FontWeight.BOLD),
            self.tx_acc_dd, ft.Row([self.tx_type_dd, self.tx_amount]), ft.Row([self.tx_date, self.tx_desc]),
            ft.ElevatedButton("💾 تسجيل الحركة", on_click=add_tx, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER)
        ])

        self.tx_filter_dd = ft.Dropdown(label="تصفية حسب الصندوق", expand=True)
        self.load_filters()
        self.tx_filter_dd.on_change = lambda e: self.load_transactions_table()

        self.tx_table_container = ft.Container()
        self.load_transactions_table()

        return ft.Column([form, self.tx_filter_dd, self.tx_table_container], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_filters(self):
        accounts = get_all_cash_accounts(active_only=True)
        self.tx_filter_dd.options = [ft.dropdown.Option("الكل")] + [ft.dropdown.Option(f"{a['id']}:{a['name']}", text=f"{a['name']} ({a['currency_code']})") for a in accounts]
        self.tx_filter_dd.value = "الكل"

    def refresh_accounts_dropdowns(self):
        if hasattr(self, 'tx_acc_dd'):
            accounts = get_all_cash_accounts()
            self.tx_acc_dd.options = [ft.dropdown.Option(f"cash_{a['id']}", text=f"{a['name']} ({a['currency_code']})") for a in accounts]
            if accounts: self.tx_acc_dd.value = f"cash_{accounts[0]['id']}"

    def load_transactions_table(self):
        filter_id = None if self.tx_filter_dd.value == "الكل" or ":" not in self.tx_filter_dd.value else int(self.tx_filter_dd.value.split(":")[0])
        transactions = get_cash_transactions(filter_id)
        if transactions:
            df = pd.DataFrame(transactions)
            df["النوع"] = df["type"].replace({"deposit": "إيداع", "withdrawal": "سحب"})
            df = df.rename(columns={"transaction_date": "التاريخ", "description": "الوصف", "amount": "المبلغ", "account_name": "الصندوق", "currency_code": "العملة"})
            self.tx_table_container.content = temp_data_table(df[["التاريخ", "الصندوق", "النوع", "المبلغ", "العملة", "الوصف"]])
        else:
            self.tx_table_container.content = ft.Text("لا توجد حركات مسجلة", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 4. تحويل
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
            from_key, to_key = self.transfer_from_dd.value, self.transfer_to_dd.value
            if from_key == to_key: self.show_snackbar("لا يمكن التحويل لنفس الحساب", ACCENT_RED); return
            try: amount = float(self.transfer_amount.value)
            except ValueError: self.show_snackbar("مبلغ غير صالح", ACCENT_RED); return

            from_info = self.transfer_map[from_key]
            to_info = self.transfer_map[to_key]

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
                self.load_transfer_options(); self.load_recent_transfers(); self.load_balances()

        return ft.Column([
            ft.Text("🔄 تحويل بين الحسابات", color=GOLD, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.transfer_from_dd, self.transfer_to_dd]),
            ft.Row([self.transfer_amount, self.transfer_date]),
            ft.Row([self.transfer_desc, self.transfer_ref]),
            ft.ElevatedButton("🔄 تنفيذ التحويل", on_click=do_transfer, bgcolor=GOLD, color=ft.colors.BLACK),
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
        
        # تحديث "إلى" عند تغيير "من"
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
        if recent:
            self.recent_transfers_container.content = temp_data_table(pd.DataFrame(recent))
        else:
            self.recent_transfers_container.content = ft.Text("لا توجد تحويلات سابقة", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 5. كشف حساب
    # ============================================================
    def build_statement_tab(self):
        accounts = get_all_cash_accounts()
        if not accounts:
            return ft.Text("لا توجد حسابات صندوق.", color=TEXT_SECONDARY)

        self.stmt_acc_dd = ft.Dropdown(label="اختر الصندوق", options=[ft.dropdown.Option(f"cash_{a['id']}", text=f"{a['name']} ({a['currency_code']})") for a in accounts], value=f"cash_{accounts[0]['id']}", expand=True)
        self.stmt_from = ft.TextField(label="من تاريخ", value=date.today().replace(day=1).strftime("%Y-%m-%d"), expand=True)
        self.stmt_to = ft.TextField(label="إلى تاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.stmt_result = ft.Container()

        def show_stmt(e):
            acc_id = int(self.stmt_acc_dd.value.split("_")[1])
            statement, error = get_cash_statement(acc_id, self.stmt_from.value, self.stmt_to.value)
            if error:
                self.show_snackbar(error, ACCENT_RED); return
            
            content = [ft.Text(f"رصيد افتتاحي: {statement['opening_balance']:,.2f}", color=GOLD, weight=ft.FontWeight.BOLD)]
            if statement['transactions']:
                df = pd.DataFrame(statement['transactions'])
                df["النوع"] = df["type"].replace({"deposit": "إيداع", "withdrawal": "سحب"})
                df = df.rename(columns={"transaction_date": "التاريخ", "description": "الوصف", "amount": "المبلغ"})
                content.append(temp_data_table(df[["التاريخ", "النوع", "المبلغ", "الوصف"]]))
            else:
                content.append(ft.Text("لا توجد حركات في هذه الفترة", color=TEXT_SECONDARY))
            content.append(ft.Text(f"رصيد ختامي: {statement['closing_balance']:,.2f}", color=GOLD, weight=ft.FontWeight.BOLD))
            
            self.stmt_result.content = ft.Column(content)
            self.page.update()

        return ft.Column([
            ft.Text("كشف حساب الصندوق", color=ACCENT_CYAN, size=20, weight=ft.FontWeight.BOLD),
            self.stmt_acc_dd,
            ft.Row([self.stmt_from, self.stmt_to]),
            ft.ElevatedButton("📋 عرض كشف الحساب", on_click=show_stmt, bgcolor=ACCENT_CYAN, color=ft.colors.WHITE),
            self.stmt_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
