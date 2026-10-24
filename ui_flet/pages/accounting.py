# ui_flet/pages/accounting.py
import flet as ft
import pandas as pd
from datetime import date
from services.accounting_service import (
    get_account_code, save_journal_entry, get_recent_entries,
    get_entry_details, get_ledger, get_trial_balance, get_distinct_accounts,
)
from services.audit_service import log_action
from services import cost_center_service
from services.currency_service import get_base_currency, get_exchange_rate
from database import get_connection, close_connection
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

def get_account_display_name(code):
    if not code: return ""
    conn = get_connection()
    try:
        if code.isdigit() or "." in code:
            row = conn.execute("SELECT code, name FROM accounts WHERE code = ?", (code,)).fetchone()
            if row: return f"{row['code']} - {row['name']}"
        return code
    finally: close_connection(conn)

def get_accounts_list(include_system=False):
    conn = get_connection()
    try:
        q = "SELECT code, name, is_system FROM accounts WHERE is_active = 1"
        if not include_system:
            q += " AND (is_system IS NULL OR is_system = 0) AND code NOT LIKE '%.%'"
        q += " ORDER BY code"
        return [f"{a['code']} - {a['name']}" for a in conn.execute(q).fetchall()]
    finally: close_connection(conn)

def get_cost_centers_list():
    centers = cost_center_service.get_all_cost_centers(active_only=True)
    if not centers: return [], {}
    options = [f"{c['code']} - {c['name']}" for c in centers]
    mapping = {f"{c['code']} - {c['name']}": c['id'] for c in centers}
    return options, mapping

def get_all_currencies():
    conn = get_connection()
    try:
        return conn.execute("SELECT code, name, symbol FROM currencies WHERE is_active = 1 ORDER BY is_base DESC, code").fetchall()
    finally: close_connection(conn)

class AccountingPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("🧾 الحسابات", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("قيود اليومية، دفتر الأستاذ، وميزان المراجعة", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📝 قيود اليومية", content=self.build_journal_tab()),
                ft.Tab(text="📖 دفتر الأستاذ", content=self.build_ledger_tab()),
                ft.Tab(text="⚖️ ميزان المراجعة", content=self.build_trial_balance_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. قيود اليومية
    # ============================================================
    def build_journal_tab(self):
        accounts_list = get_accounts_list()
        cc_options, cc_mapping = get_cost_centers_list()
        currencies = get_all_currencies()

        if not accounts_list:
            return ft.Text("لا توجد حسابات. أضف حسابات من شجرة الحسابات أولاً.", color=ACCENT_ORANGE)

        self.journal_date = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"))
        self.journal_desc = ft.TextField(label="البيان", hint_text="أدخل وصف العملية المالية", expand=True)
        self.curr_names = [f"{c['code']} - {c['name']}" for c in currencies]
        self.base_currency = get_base_currency()
        
        # 4 أسطر للقيد
        self.lines_data = []  # [(acc_dd, deb_input, cred_input, curr_dd)]
        self.lines_container = ft.Column(spacing=10)
        
        for i in range(4):
            acc_dd = ft.Dropdown(
                label=f"الحساب {i+1}",
                options=[ft.dropdown.Option(a) for a in accounts_list],
                expand=True
            )
            deb_input = ft.TextField(label=f"مدين {i+1}", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=120)
            cred_input = ft.TextField(label=f"دائن {i+1}", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=120)
            curr_dd = ft.Dropdown(
                label=f"العملة {i+1}",
                options=[ft.dropdown.Option(c) for c in self.curr_names],
                value=self.curr_names[0] if self.curr_names else None,
                width=180
            )
            self.lines_data.append((acc_dd, deb_input, cred_input, curr_dd))
            
            self.lines_container.controls.append(
                ft.Row([acc_dd, deb_input, cred_input, curr_dd])
            )

        def save_entry(e):
            if not self.journal_desc.value:
                self.show_snackbar("البيان مطلوب", ACCENT_RED); return
            
            lines = []
            for i, (acc, deb, cred, curr) in enumerate(self.lines_data):
                if not acc.value: continue
                try:
                    d = float(deb.value or 0); c = float(cred.value or 0)
                except ValueError:
                    d, c = 0.0, 0.0
                if d == 0 and c == 0: continue
                
                code = acc.value.split(" - ")[-1]
                curr_code = curr.value.split(" - ")[0] if curr.value else "YER"
                lines.append({"account": code, "debit": d, "credit": c, "currency_code": curr_code})
            
            if not lines:
                self.show_snackbar("أضف سطراً محاسبياً واحداً على الأقل", ACCENT_RED); return

            entry_id, error = save_journal_entry(self.journal_desc.value, lines, self.journal_date.value)
            if error:
                self.show_snackbar(f"❌ {error}", ACCENT_RED)
            else:
                log_action(username="admin", action="قيد يومية", table_name="journal_entries", record_id=entry_id, new_value=f"البيان: {self.journal_desc.value}")
                self.show_snackbar(f"✅ تم تسجيل القيد #{entry_id}", ACCENT_GREEN)
                self.journal_desc.value = ""
                for acc, deb, cred, curr in self.lines_data:
                    acc.value = None; deb.value = "0"; cred.value = "0"
                self.load_recent_entries()

        form_card = ft.Container(
            content=ft.Column([
                ft.Row([self.journal_date]),
                self.journal_desc,
                ft.Text("الأسطر المحاسبية (حتى 4 أسطر)", color=TEXT_SECONDARY, size=12),
                self.lines_container,
                ft.ElevatedButton("💾 حفظ القيد", on_click=save_entry, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
            ], spacing=10),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15
        )

        # آخر القيود
        self.recent_container = ft.Container()
        self.details_container = ft.Container()
        self.load_recent_entries()

        return ft.Column([
            ft.Text("تسجيل قيد يومية", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD),
            form_card,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("آخر قيود اليومية", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            self.recent_container,
            self.details_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_recent_entries(self):
        entries = get_recent_entries()
        if entries:
            df = pd.DataFrame(entries)
            self.recent_container.content = temp_data_table(df)
            
            # قائمة لاختيار القيد
            self.entry_selector = ft.Dropdown(
                label="اختر قيداً لعرض تفاصيله",
                options=[ft.dropdown.Option(key=str(e['id']), text=f"#{e['id']} - {e['date']}") for e in entries],
                value=str(entries[0]['id']), on_change=lambda e: self.load_entry_details(int(e.control.value))
            )
            self.load_entry_details(entries[0]['id'])
            self.details_container.content = ft.Column([self.entry_selector, self.entry_details_inner])
        else:
            self.recent_container.content = ft.Text("لا توجد قيود بعد", color=TEXT_SECONDARY)
            self.details_container.content = None
        self.page.update()

    def load_entry_details(self, entry_id):
        details = get_entry_details(entry_id)
        content = []
        if details:
            for line in details:
                display_name = get_account_display_name(line['account_name'])
                content.append(ft.Container(
                    content=ft.Text(f"الحساب: {display_name} | مدين: {line['debit']:,.2f} | دائن: {line['credit']:,.2f} | العملة: {line['currency_code']} | سعر الصرف: {line['exchange_rate']}", color=TEXT_PRIMARY, size=12),
                    bgcolor=GLASS_BG, padding=10, border_radius=8
                ))
                if line.get('cost_center_allocations'):
                    alloc_df = pd.DataFrame(line['cost_center_allocations'])
                    content.append(ft.Text("توزيع مراكز التكلفة:", color=TEXT_SECONDARY, size=11))
                    content.append(temp_data_table(alloc_df))
            
            total_d = sum(d['debit'] for d in details)
            total_c = sum(d['credit'] for d in details)
            content.append(ft.Text(f"المجموع: مدين {total_d:,.2f} | دائن {total_c:,.2f}", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD))
        
        self.entry_details_inner = ft.Column(content, spacing=8)
        if hasattr(self, 'details_container') and self.details_container.content:
            self.details_container.content.controls[-1] = self.entry_details_inner
        self.page.update()

    # ============================================================
    # 2. دفتر الأستاذ
    # ============================================================
    def build_ledger_tab(self):
        accounts = get_distinct_accounts()
        if not accounts:
            return ft.Text("لا توجد حسابات بعد", color=TEXT_SECONDARY)

        self.display_accounts = [get_account_display_name(acc) for acc in accounts]
        self.acc_mapping = dict(zip(self.display_accounts, accounts))
        self.ledger_dd = ft.Dropdown(label="اختر الحساب", options=[ft.dropdown.Option(a) for a in self.display_accounts], value=self.display_accounts[0], expand=True, on_change=lambda e: self.load_ledger())
        self.ledger_container = ft.Container()
        self.ledger_balance_text = ft.Text("", color=ACCENT_GREEN, size=16, weight=ft.FontWeight.BOLD)
        self.load_ledger()

        return ft.Column([
            ft.Text("دفتر الأستاذ العام", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            self.ledger_dd,
            self.ledger_container,
            self.ledger_balance_text
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_ledger(self):
        if not self.ledger_dd.value: return
        selected = self.acc_mapping[self.ledger_dd.value]
        ledger = get_ledger(selected)
        if ledger:
            df = pd.DataFrame(ledger)
            df["رصيد مدين"] = (df["debit"] - df["credit"]).apply(lambda x: x if x > 0 else 0)
            df["رصيد دائن"] = (df["credit"] - df["debit"]).apply(lambda x: x if x > 0 else 0)
            if "account_name" in df.columns:
                df["account_name"] = df["account_name"].apply(get_account_display_name)
            
            cols = ["date", "description", "debit", "credit", "رصيد مدين", "رصيد دائن", "currency_code", "exchange_rate"]
            if "account_name" in df.columns: cols.insert(2, "account_name")
            df = df[[c for c in cols if c in df.columns]]
            
            self.ledger_container.content = temp_data_table(df)
            final = df["debit"].sum() - df["credit"].sum()
            if final > 0: self.ledger_balance_text.value = f"الرصيد النهائي: {final:,.2f} (مدين)"
            elif final < 0: self.ledger_balance_text.value = f"الرصيد النهائي: {abs(final):,.2f} (دائن)"
            else: self.ledger_balance_text.value = "الرصيد النهائي: 0.00"
        else:
            self.ledger_container.content = ft.Text("لا توجد حركات على هذا الحساب", color=TEXT_SECONDARY)
            self.ledger_balance_text.value = ""
        self.page.update()

    # ============================================================
    # 3. ميزان المراجعة
    # ============================================================
    def build_trial_balance_tab(self):
        tb = get_trial_balance()
        if not tb:
            return ft.Text("لا توجد قيود لعرض ميزان المراجعة", color=TEXT_SECONDARY)

        df = pd.DataFrame(tb)
        df["رصيد مدين"] = (df["total_debit"] - df["total_credit"]).apply(lambda x: x if x > 0 else 0)
        df["رصيد دائن"] = (df["total_credit"] - df["total_debit"]).apply(lambda x: x if x > 0 else 0)
        df["account_name"] = df["account_name"].apply(get_account_display_name)
        df = df[["account_name", "total_debit", "total_credit", "رصيد مدين", "رصيد دائن"]]
        
        total_d = df["total_debit"].sum()
        total_c = df["total_credit"].sum()
        is_balanced = abs(total_d - total_c) < 0.01

        return ft.Column([
            ft.Text("ميزان المراجعة", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            temp_data_table(df),
            ft.Row([
                ft.Text(f"إجمالي المدين: {total_d:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Text(f"إجمالي الدائن: {total_c:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text("✅ الميزان متوازن" if is_balanced else "⚠️ الميزان غير متوازن", color=ACCENT_GREEN if is_balanced else ACCENT_RED, weight=ft.FontWeight.BOLD)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
