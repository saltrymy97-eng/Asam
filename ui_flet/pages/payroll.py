# ui_flet/pages/payroll.py
import flet as ft
import pandas as pd
from datetime import date
from services.payroll_service import (
    create_payroll_tables, get_employees, get_salary_config,
    save_salary_config, calculate_net, run_payroll,
    get_payroll_history, check_employee_payroll_exists,
)
from services.expenses_service import get_payment_accounts
from services.audit_service import log_action
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

class PayrollPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        try: create_payroll_tables()
        except Exception as e: print(f"Payroll init: {e}")

        self.header = ft.Text("💰 كشف الرواتب", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إعداد وتشغيل وسجل رواتب الموظفين", color=TEXT_SECONDARY, size=14)

        self.employees = get_employees()
        if not self.employees:
            self.controls = [
                ft.Column([self.header, self.subtitle], spacing=5),
                ft.Divider(color=GLASS_BORDER),
                ft.Text("⚠️ لا يوجد موظفون. أضف موظفين من وحدة الموارد البشرية أولاً.", color=ACCENT_ORANGE)
            ]
            return

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="⚙️ إعداد الرواتب", content=self.build_config_tab()),
                ft.Tab(text="🚀 تشغيل كشف الراتب", content=self.build_run_tab()),
                ft.Tab(text="📋 سجل الرواتب", content=self.build_history_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. إعداد الرواتب
    # ============================================================
    def build_config_tab(self):
        self.conf_emp_dd = ft.Dropdown(
            label="اختر الموظف",
            options=[ft.dropdown.Option(key=str(e['id']), text=e['name']) for e in self.employees],
            value=str(self.employees[0]['id']), expand=True,
            on_change=lambda e: self.load_config()
        )
        
        self.conf_basic = ft.TextField(label="الراتب الأساسي", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.conf_housing = ft.TextField(label="بدل السكن", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.conf_transport = ft.TextField(label="بدل النقل", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.conf_other = ft.TextField(label="بدلات أخرى", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.conf_deductions = ft.TextField(label="الخصومات", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.conf_net_text = ft.Text("", color=ACCENT_GREEN, size=16, weight=ft.FontWeight.BOLD)
        
        for inp in [self.conf_basic, self.conf_housing, self.conf_transport, self.conf_other, self.conf_deductions]:
            inp.on_change = lambda e: self.update_config_net()

        def save_config(e):
            try:
                basic = float(self.conf_basic.value or 0)
                housing = float(self.conf_housing.value or 0)
                transport = float(self.conf_transport.value or 0)
                other = float(self.conf_other.value or 0)
                deductions = float(self.conf_deductions.value or 0)
            except ValueError:
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return
            
            ok, err = save_salary_config(int(self.conf_emp_dd.value), basic, housing, transport, other, deductions)
            if err:
                self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
            else:
                log_action(username="admin", action="إعداد الراتب", table_name="employee_salaries", new_value=f"الموظف ID: {self.conf_emp_dd.value}, الأساسي: {basic:,.2f}")
                self.show_snackbar("✅ تم حفظ إعدادات الراتب", ACCENT_GREEN)
                self.load_config()

        self.load_config()

        return ft.Column([
            ft.Text("إعدادات الرواتب الشهرية", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD),
            self.conf_emp_dd,
            ft.Row([self.conf_basic, self.conf_housing]),
            ft.Row([self.conf_transport, self.conf_other]),
            ft.Row([self.conf_deductions]),
            self.conf_net_text,
            ft.ElevatedButton("💾 حفظ الإعدادات", on_click=save_config, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=12)

    def load_config(self):
        if not self.conf_emp_dd.value: return
        conf = get_salary_config(int(self.conf_emp_dd.value))
        if conf:
            self.conf_basic.value = str(conf['basic_salary'])
            self.conf_housing.value = str(conf['housing_allowance'])
            self.conf_transport.value = str(conf['transport_allowance'])
            self.conf_other.value = str(conf['other_allowances'])
            self.conf_deductions.value = str(conf['deductions'])
        else:
            for inp in [self.conf_basic, self.conf_housing, self.conf_transport, self.conf_other, self.conf_deductions]:
                inp.value = "0"
        self.update_config_net()

    def update_config_net(self):
        try:
            basic = float(self.conf_basic.value or 0)
            housing = float(self.conf_housing.value or 0)
            transport = float(self.conf_transport.value or 0)
            other = float(self.conf_other.value or 0)
            deductions = float(self.conf_deductions.value or 0)
        except ValueError:
            return
        total_allow, net = calculate_net(basic, housing, transport, other, deductions)
        self.conf_net_text.value = f"صافي الراتب: {net:,.2f}"
        self.page.update()

    # ============================================================
    # 2. تشغيل الكشف
    # ============================================================
    def build_run_tab(self):
        self.run_emp_dd = ft.Dropdown(
            label="اختر الموظف",
            options=[ft.dropdown.Option(key=str(e['id']), text=e['name']) for e in self.employees],
            value=str(self.employees[0]['id']), expand=True,
            on_change=lambda e: self.check_existing()
        )
        self.run_month = ft.TextField(label="الشهر (YYYY-MM)", value=date.today().strftime("%Y-%m"), on_change=lambda e: self.check_existing())
        
        self.run_result = ft.Container()
        self.check_existing()

        return ft.Column([
            ft.Text("تشغيل كشف راتب شهري", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            self.run_emp_dd,
            self.run_month,
            self.run_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def check_existing(self):
        if not self.run_emp_dd.value or not self.run_month.value: return
        try:
            existing = check_employee_payroll_exists(int(self.run_emp_dd.value), self.run_month.value.strip())
        except Exception:
            existing = None

        if existing:
            month = existing.get("month", "—")
            emp_name = existing.get("employee_name", "—")
            net = float(existing.get("net_salary") or 0)
            basic = float(existing.get("basic_salary") or 0)
            allowances = float(existing.get("total_allowances") or 0)
            deductions = float(existing.get("deductions") or 0)
            entry_id = existing.get("journal_entry_id") or "—"

            self.run_result.content = ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("🔒 تم صرف راتب هذا الشهر مسبقاً", color=ACCENT_RED, size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"الموظف: {emp_name} | الشهر: {month} | رقم القيد: #{entry_id}", color=TEXT_SECONDARY, size=12)
                    ]),
                    bgcolor=ft.colors.with_opacity(0.1, ACCENT_RED), padding=15, border_radius=10
                ),
                ft.Row([
                    self._metric("الأساسي", f"{basic:,.2f}"),
                    self._metric("البدلات", f"{allowances:,.2f}"),
                    self._metric("الخصومات", f"{deductions:,.2f}"),
                    self._metric("الصافي", f"{net:,.2f}", ACCENT_GREEN),
                ], spacing=10),
                ft.Text("ℹ️ لا يمكن تشغيل نفس الراتب مرتين في نفس الشهر. احذفه من السجل أولاً.", color=ACCENT_ORANGE, size=12)
            ], spacing=10)
            self.page.update()
            return

        # عرض تفاصيل الراتب + زر التشغيل
        conf = get_salary_config(int(self.run_emp_dd.value))
        if not conf:
            self.run_result.content = ft.Text("⚠️ يرجى إعداد الراتب من التبويب الأول أولاً.", color=ACCENT_ORANGE)
            self.page.update(); return

        total_allow, net = calculate_net(
            float(conf["basic_salary"] or 0), float(conf["housing_allowance"] or 0),
            float(conf["transport_allowance"] or 0), float(conf["other_allowances"] or 0),
            float(conf["deductions"] or 0)
        )

        accounts = get_payment_accounts()
        if not accounts:
            self.run_result.content = ft.Text("⚠️ لا يوجد صندوق أو بنك نشط.", color=ACCENT_RED)
            self.page.update(); return

        self.run_account_dd = ft.Dropdown(
            label="من أي حساب سيتم صرف الرواتب؟",
            options=[ft.dropdown.Option(key=str(a['id']), text=_format_account_label(a)) for a in accounts],
            value=str(accounts[0]['id']), expand=True,
            on_change=lambda e: self.update_run_balance(net)
        )
        self.run_balance_text = ft.Text("", color=TEXT_SECONDARY, size=12)
        self.update_run_balance(net)

        def do_run(e):
            acc = next((a for a in accounts if str(a['id']) == self.run_account_dd.value), None)
            if not acc: return
            if net > acc['balance']:
                self.show_snackbar(f"الرصيد غير كافٍ. المتاح: {acc['balance']:,.2f}", ACCENT_RED); return
            
            # فحص نهائي للتكرار
            re_check = check_employee_payroll_exists(int(self.run_emp_dd.value), self.run_month.value.strip())
            if re_check:
                self.show_snackbar("⚠️ تم صرف راتب هذا الشهر مسبقاً", ACCENT_RED); self.check_existing(); return

            net_amount, error = run_payroll(int(self.run_emp_dd.value), self.run_month.value.strip(), payment_account_code=acc['code'], payment_method=acc['type'])
            if error:
                self.show_snackbar(f"❌ {error}", ACCENT_RED)
            else:
                log_action(username="admin", action="تشغيل كشف راتب", table_name="payroll_runs", new_value=f"الموظف ID: {self.run_emp_dd.value}, الشهر: {self.run_month.value}, الصافي: {net_amount:,.2f}")
                self.show_snackbar(f"✅ تم تشغيل الراتب. الصافي: {net_amount:,.2f}", ACCENT_GREEN)
                self.load_history(); self.check_existing()

        self.run_result.content = ft.Column([
            ft.Row([
                self._metric("الأساسي", f"{float(conf['basic_salary']):,.2f}"),
                self._metric("البدلات", f"{total_allow:,.2f}"),
                self._metric("الخصومات", f"{float(conf['deductions']):,.2f}"),
                self._metric("الصافي", f"{net:,.2f}", ACCENT_GREEN),
            ], spacing=10),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("حساب الدفع", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
            self.run_account_dd, self.run_balance_text,
            ft.ElevatedButton("🚀 تشغيل الكشف وإنشاء القيد", on_click=do_run, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], spacing=10)
        self.page.update()

    def _metric(self, label, value, color=TEXT_PRIMARY):
        return ft.Container(
            content=ft.Column([
                ft.Text(label, color=TEXT_SECONDARY, size=10),
                ft.Text(value, color=color, size=14, weight=ft.FontWeight.BOLD)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=GLASS_BG, padding=10, border_radius=8, expand=True
        )

    def update_run_balance(self, net):
        if not self.run_account_dd.value: return
        accounts = get_payment_accounts()
        acc = next((a for a in accounts if str(a['id']) == self.run_account_dd.value), None)
        if acc and net > 0:
            if net > acc['balance']:
                self.run_balance_text.value = f"⚠️ الرصيد غير كافٍ! المتاح: {acc['balance']:,.2f}"
                self.run_balance_text.color = ACCENT_RED
            else:
                self.run_balance_text.value = f"✅ الرصيد كافٍ — سيتبقى {acc['balance'] - net:,.2f}"
                self.run_balance_text.color = ACCENT_GREEN
        self.page.update()

    # ============================================================
    # 3. سجل الرواتب
    # ============================================================
    def build_history_tab(self):
        self.history_container = ft.Container()
        self.load_history()
        return ft.Column([
            ft.Text("سجل الرواتب الشهرية", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        history = get_payroll_history()
        if history:
            df = pd.DataFrame(history)
            df_display = df.rename(columns={"id": "الرقم", "name": "الموظف", "month": "الشهر", "basic_salary": "الأساسي", "total_allowances": "البدلات", "deductions": "الخصومات", "net_salary": "الصافي", "journal_entry_id": "رقم القيد"})
            cols = [c for c in ["الرقم", "الموظف", "الشهر", "الأساسي", "البدلات", "الخصومات", "الصافي", "رقم القيد"] if c in df_display.columns]
            total = df["net_salary"].sum()
            
            self.history_container.content = ft.Column([
                ft.Container(content=ft.Text(f"💰 إجمالي الرواتب المصروفة: {total:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD), bgcolor=ft.colors.with_opacity(0.15, ACCENT_GREEN), padding=10, border_radius=8),
                temp_data_table(df_display[cols])
            ], spacing=10)
        else:
            self.history_container.content = ft.Text("لا يوجد سجل رواتب بعد", color=TEXT_SECONDARY)
        self.page.update()
