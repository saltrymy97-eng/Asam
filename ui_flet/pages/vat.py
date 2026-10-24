# ui_flet/pages/vat.py
import flet as ft
import pandas as pd
from datetime import date
from services.vat_service import (
    create_vat_table, get_vat_rate, update_vat_rate, calculate_vat,
    calculate_reverse_vat, get_vat_report, get_tax_return_report,
    get_vat_history, pay_vat,
)
from services.expenses_service import get_payment_accounts
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

def _get_vat_payments(limit=50):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT v.id, v.date, v.amount, v.account, v.reference, v.notes, v.created_by,
                (SELECT ba.bank_name FROM bank_transactions bt JOIN bank_accounts ba ON bt.bank_account_id = ba.id WHERE bt.reference = 'vat_payment#' || v.journal_entry_id LIMIT 1) AS bank_source,
                (SELECT ca.name FROM cash_transactions ct JOIN cash_accounts ca ON ct.cash_account_id = ca.id WHERE ct.reference = 'vat_payment#' || v.journal_entry_id LIMIT 1) AS cash_source,
                CASE
                    WHEN EXISTS (SELECT 1 FROM bank_transactions bt WHERE bt.reference = 'vat_payment#' || v.journal_entry_id) THEN 'bank'
                    WHEN EXISTS (SELECT 1 FROM cash_transactions ct WHERE ct.reference = 'vat_payment#' || v.journal_entry_id) THEN 'cash'
                    ELSE 'other'
                END AS source_type
            FROM vouchers v WHERE v.type = 'payment' AND v.party_type = 'tax_authority'
            ORDER BY v.id DESC LIMIT ?
        """, (limit,)).fetchall()

        results = []
        for r in rows:
            row = dict(r)
            if row.get("bank_source"):
                row["payment_source"], row["source_type"] = row["bank_source"], "bank"
            elif row.get("cash_source"):
                row["payment_source"], row["source_type"] = row["cash_source"], "cash"
            else:
                row["payment_source"], row["source_type"] = row.get("account") or "—", "other"
            results.append(row)
        return results
    except Exception as e:
        print(f"Error fetching VAT payments: {e}")
        return []
    finally:
        close_connection(conn)

class VATPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        try:
            create_vat_table()
        except Exception as e:
            print(f"VAT init error: {e}")

        self.header = ft.Text("🧾 ضريبة القيمة المضافة (VAT)", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة ضريبة القيمة المضافة والتقارير", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="⚙️ الإعدادات", content=self.build_settings_tab()),
                ft.Tab(text="🧮 حاسبة الضريبة", content=self.build_calculator_tab()),
                ft.Tab(text="🔄 الضريبة العكسية", content=self.build_reverse_calc_tab()),
                ft.Tab(text="💳 دفع الضريبة", content=self.build_payment_tab()),
                ft.Tab(text="📊 التقارير", content=self.build_reports_tab()),
            ],
            expand=True,
        )

        self.controls = [
            ft.Column([self.header, self.subtitle], spacing=5),
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def kpi_card(self, icon, title, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=30),
                ft.Text(title, color=TEXT_SECONDARY, size=12),
                ft.Text(str(value), color=color, size=22, weight=ft.FontWeight.BOLD)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

    # ============================================================
    # 1. الإعدادات
    # ============================================================
    def build_settings_tab(self):
        current_rate = get_vat_rate()
        
        self.rate_display = ft.Text(f"النسبة الحالية: {current_rate * 100:.0f}%", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD, size=18)
        self.new_rate_input = ft.TextField(label="تحديث النسبة (%)", value=str(current_rate * 100), keyboard_type=ft.KeyboardType.NUMBER, width=200)

        def update_rate(e):
            try:
                new_rate = float(self.new_rate_input.value) / 100
                update_vat_rate(new_rate)
                self.rate_display.value = f"النسبة الحالية: {new_rate * 100:.0f}%"
                self.show_snackbar(f"✅ تم تحديث نسبة الضريبة إلى {new_rate * 100:.0f}%", ACCENT_GREEN)
                self.load_history()
            except ValueError:
                self.show_snackbar("نسبة غير صالحة", ACCENT_RED)

        self.history_container = ft.Container()
        self.load_history()

        return ft.Column([
            ft.Text("إعدادات الضريبة", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.rate_display,
            ft.Row([self.new_rate_input, ft.ElevatedButton("💾 تحديث النسبة", on_click=update_rate, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)]),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("سجل التغييرات", color=ACCENT_PURPLE, size=18, weight=ft.FontWeight.BOLD),
            self.history_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_history(self):
        history = get_vat_history()
        if history:
            df = pd.DataFrame(history)
            df['name'] = df.get('name', 'ضريبة القيمة المضافة')
            df['created_at'] = df['created_at'].apply(lambda x: x if (x and str(x).strip() and str(x).lower() != 'none') else "—") if 'created_at' in df.columns else "—"
            df = df.rename(columns={"name": "الاسم", "rate": "النسبة", "is_active": "نشط", "created_at": "التاريخ"})
            df["النسبة"] = df["النسبة"].apply(lambda x: f"{x * 100:.0f}%" if pd.notna(x) else "—")
            df["نشط"] = df["نشط"].apply(lambda x: "✅" if x else "❌")
            cols = [c for c in ["الاسم", "النسبة", "نشط", "التاريخ"] if c in df.columns]
            self.history_container.content = temp_data_table(df[cols])
        else:
            self.history_container.content = ft.Text("لا توجد تغييرات سابقة", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 2. حاسبة الضريبة
    # ============================================================
    def build_calculator_tab(self):
        self.calc_amount = ft.TextField(label="المبلغ (قبل الضريبة)", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        self.calc_result_container = ft.Row()

        def do_calc(e):
            try:
                amount = float(self.calc_amount.value)
            except ValueError: return
            vat_amount = calculate_vat(amount)
            total = amount + vat_amount
            self.calc_result_container.controls = [
                self.kpi_card("💰", "المبلغ الأساسي", f"{amount:,.2f}", ACCENT_BLUE),
                self.kpi_card("🧾", "قيمة الضريبة", f"{vat_amount:,.2f}", ACCENT_ORANGE),
                self.kpi_card("💎", "الإجمالي", f"{total:,.2f}", ACCENT_GREEN),
            ]
            self.page.update()

        return ft.Column([
            ft.Text("حساب الضريبة على مبلغ", color=ACCENT_ORANGE, size=20, weight=ft.FontWeight.BOLD),
            self.calc_amount,
            ft.ElevatedButton("🧮 احسب الضريبة", on_click=do_calc, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            self.calc_result_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 3. الضريبة العكسية
    # ============================================================
    def build_reverse_calc_tab(self):
        self.rev_amount = ft.TextField(label="المبلغ الإجمالي (شامل الضريبة)", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        self.rev_result_container = ft.Row()

        def do_rev_calc(e):
            try:
                total_amount = float(self.rev_amount.value)
            except ValueError: return
            before_tax, vat_amt = calculate_reverse_vat(total_amount)
            self.rev_result_container.controls = [
                self.kpi_card("💎", "الإجمالي (شامل الضريبة)", f"{total_amount:,.2f}", ACCENT_BLUE),
                self.kpi_card("📋", "المبلغ قبل الضريبة", f"{before_tax:,.2f}", ACCENT_GREEN),
                self.kpi_card("🧾", "قيمة الضريبة", f"{vat_amt:,.2f}", ACCENT_ORANGE),
            ]
            self.page.update()

        return ft.Column([
            ft.Text("الضريبة العكسية", color=ACCENT_ORANGE, size=20, weight=ft.FontWeight.BOLD),
            self.rev_amount,
            ft.ElevatedButton("🔍 احسب الضريبة العكسية", on_click=do_rev_calc, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            self.rev_result_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 4. دفع الضريبة
    # ============================================================
    def build_payment_tab(self):
        self.pay_start = ft.TextField(label="من تاريخ", value=date.today().replace(day=1).strftime("%Y-%m-%d"))
        self.pay_end = ft.TextField(label="إلى تاريخ", value=date.today().strftime("%Y-%m-%d"))
        self.vat_summary_container = ft.Container()

        def check_summary(e):
            report = get_vat_report(self.pay_start.value, self.pay_end.value)
            net_vat = report.get('net_vat', 0)
            if net_vat > 0:
                text = f"⚠️ ضريبة مستحقة الدفع: {net_vat:,.2f}\nضريبة المخرجات: {report.get('output_vat', 0):,.2f}\nضريبة المدخلات: {report.get('input_vat', 0):,.2f}"
                color = ACCENT_ORANGE
            elif net_vat < 0:
                text = f"ℹ️ رصيد ضريبي دائن: {abs(net_vat):,.2f} — لا داعي للدفع"
                color = ACCENT_BLUE
            else:
                text = "✅ لا يوجد مستحقات ضريبية في الفترة"
                color = ACCENT_GREEN
            self.vat_summary_container.content = ft.Text(text, color=color, weight=ft.FontWeight.BOLD)
            self.net_vat_val = net_vat
            self.page.update()

        # إعدادات الدفع
        self.pay_method = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="bank", label="بنكي (تحويل)"),
                ft.Radio(value="cash", label="نقدي (من صندوق)")
            ]),
            value="bank", on_change=self.on_method_change
        )
        self.account_dd = ft.Dropdown(label="اختر الحساب", expand=True)
        self.pay_amount = ft.TextField(label="المبلغ المراد دفعه", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        self.pay_date = ft.TextField(label="تاريخ الدفع", value=date.today().strftime("%Y-%m-%d"))
        self.pay_ref = ft.TextField(label="المرجع (رقم إشعار الدفع)")
        self.pay_notes = ft.TextField(label="ملاحظات", multiline=True)
        self.pay_status = ft.Text("", color=TEXT_SECONDARY)

        self.net_vat_val = 0.0

        def do_pay(e):
            if not self.account_dd.value:
                self.show_snackbar("اختر الحساب أولاً", ACCENT_RED)
                return
            try:
                amount = float(self.pay_amount.value)
            except ValueError:
                self.show_snackbar("المبلغ غير صالح", ACCENT_RED)
                return

            acc = next((a for a in self._all_accounts if str(a["id"]) == self.account_dd.value), None)
            if not acc: return

            if amount > acc["balance"]:
                self.pay_status.value = f"⚠️ الرصيد غير كافٍ. المتاح: {acc['balance']:,.2f}"
                self.pay_status.color = ACCENT_RED
                self.page.update()
                return

            journal_id, err = pay_vat(
                amount=amount, payment_date=self.pay_date.value,
                payment_account_code=acc["code"], payment_method=self.pay_method.value,
                reference=self.pay_ref.value, notes=self.pay_notes.value,
                created_by="admin", payment_account_id=acc["id"]
            )
            if err:
                self.show_snackbar(f"❌ فشل: {err}", ACCENT_RED)
            else:
                self.show_snackbar(f"✅ تم تسجيل دفع الضريبة — رقم القيد: {journal_id}", ACCENT_GREEN)
                self.load_payments()

        self.payments_container = ft.Container()

        payment_form = ft.Column([
            ft.Text("💳 دفع الضريبة لجهة الضرائب", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.pay_start, self.pay_end]),
            ft.ElevatedButton("📊 ملخص الضريبة المستحقة", on_click=check_summary, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
            self.vat_summary_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📝 تسجيل دفع الضريبة", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            self.pay_method,
            self.account_dd,
            ft.Row([self.pay_amount, self.pay_date]),
            self.pay_ref, self.pay_notes, self.pay_status,
            ft.ElevatedButton("💳 تسجيل دفع الضريبة", on_click=do_pay, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ])

        self.load_payments()

        return ft.Column([
            payment_form,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📋 سجل مدفوعات الضريبة", color=ACCENT_PURPLE, size=18, weight=ft.FontWeight.BOLD),
            self.payments_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def on_method_change(self, e):
        method = self.pay_method.value
        self._all_accounts = get_payment_accounts()
        filtered = [a for a in self._all_accounts if a["type"] == ("bank" if method == "bank" else "cash")]
        self.account_dd.options = [
            ft.dropdown.Option(key=str(a["id"]), text=f"{a['name']} ({a['currency']}) — {a['balance']:,.2f}")
            for a in filtered
        ]
        if filtered:
            self.account_dd.value = str(filtered[0]["id"])
        self.page.update()

    def load_payments(self):
        payments = _get_vat_payments(limit=100)
        if payments:
            df = pd.DataFrame(payments)
            df["المصدر"] = df["source_type"].apply(lambda x: "💵" if x == "cash" else ("🏦" if x == "bank" else "📌")) + " " + df["payment_source"].fillna("—")
            df["النوع"] = df["source_type"].apply(lambda x: "نقدي" if x == "cash" else ("بنكي" if x == "bank" else "أخرى"))
            df = df.rename(columns={"id": "الرقم", "date": "التاريخ", "amount": "المبلغ", "reference": "المرجع", "notes": "الملاحظات", "created_by": "بواسطة"})
            cols = [c for c in ["الرقم", "التاريخ", "المبلغ", "النوع", "المصدر", "المرجع", "الملاحظات", "بواسطة"] if c in df.columns]
            self.payments_container.content = temp_data_table(df[cols])
        else:
            self.payments_container.content = ft.Text("لا توجد مدفوعات ضريبية مسجلة بعد", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 5. التقارير
    # ============================================================
    def build_reports_tab(self):
        self.rep_start = ft.TextField(label="من تاريخ", value=date.today().replace(day=1).strftime("%Y-%m-%d"))
        self.rep_end = ft.TextField(label="إلى تاريخ", value=date.today().strftime("%Y-%m-%d"))
        self.report_container = ft.Container()

        def show_summary(e):
            report = get_vat_report(self.rep_start.value, self.rep_end.value)
            self.report_container.content = ft.Column([
                ft.Text(f"نسبة الضريبة: {report['rate'] * 100:.0f}%", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.kpi_card("🛒", "إجمالي المبيعات", f"{report['total_sales']:,.2f}", ACCENT_BLUE),
                    self.kpi_card("📤", "ضريبة المخرجات", f"{report['output_vat']:,.2f}", ACCENT_RED),
                    self.kpi_card("📥", "ضريبة المدخلات", f"{report['input_vat']:,.2f}", ACCENT_ORANGE),
                    self.kpi_card("💎", "صافي الضريبة", f"{report['net_vat']:,.2f}", ACCENT_GREEN),
                ])
            ])
            self.page.update()

        def show_tax_return(e):
            tax_return = get_tax_return_report(self.rep_start.value, self.rep_end.value)
            content = ft.Column([
                ft.Text(f"نسبة الضريبة: {tax_return['rate'] * 100:.0f}%", color=ACCENT_GREEN, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.kpi_card("📤", "ضريبة المخرجات", f"{tax_return['total_output_vat']:,.2f}", ACCENT_RED),
                    self.kpi_card("📥", "ضريبة المدخلات", f"{tax_return['total_input_vat']:,.2f}", ACCENT_ORANGE),
                    self.kpi_card("💎", "صافي الضريبة", f"{tax_return['net_vat']:,.2f}", ACCENT_GREEN),
                ])
            ])
            if tax_return["invoices"]:
                df = pd.DataFrame(tax_return["invoices"]).rename(columns={"id": "رقم الفاتورة", "type": "النوع", "invoice_date": "التاريخ", "total": "الإجمالي", "vat_amount": "الضريبة", "vat_rate": "النسبة"})
                df["النوع"] = df["النوع"].apply(lambda x: "بيع" if x == "sale" else "شراء")
                df["النسبة"] = df["النسبة"].apply(lambda x: f"{x*100:.0f}%")
                content.controls.append(ft.Text("📋 تفاصيل الفواتير", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD))
                content.controls.append(temp_data_table(df[["رقم الفاتورة", "النوع", "التاريخ", "الإجمالي", "الضريبة", "النسبة"]]))
            self.report_container.content = content
            self.page.update()

        return ft.Column([
            ft.Text("تقارير الضريبة", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.rep_start, self.rep_end]),
            ft.Row([
                ft.ElevatedButton("📊 عرض تقرير الملخص", on_click=show_summary, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
                ft.ElevatedButton("📋 عرض تقرير الإقرار الضريبي", on_click=show_tax_return, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
            ]),
            self.report_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
