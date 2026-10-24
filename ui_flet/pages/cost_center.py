# ui_flet/pages/cost_center.py
import flet as ft
import pandas as pd
from datetime import date
from services import cost_center_service as ccs
from services import closing_service as closing_service
import database
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

try:
    from flet_plotly import PlotlyChart
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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

class CostCenterPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("🏢 مراكز التكلفة", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة متطورة لتحليل الأداء المالي حسب القطاعات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📝 إدارة المراكز", content=self.build_manage_tab()),
                ft.Tab(text="🌳 توزيع المعاملات", content=self.build_distribution_tab()),
                ft.Tab(text="📊 تحليل وتقارير", content=self.build_analysis_tab()),
                ft.Tab(text="💰 الموازنات", content=self.build_budget_tab()),
                ft.Tab(text="🔒 إقفال المراكز", content=self.build_closing_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. إدارة المراكز
    # ============================================================
    def build_manage_tab(self):
        # النموذج
        self.cc_code = ft.TextField(label="رمز المركز", hint_text="SALES-NORTH", expand=True)
        self.cc_name = ft.TextField(label="اسم المركز", hint_text="مبيعات المنطقة الشمالية", expand=True)
        self.cc_parent = ft.Dropdown(label="المركز الأب", expand=True)
        
        def refresh_parents():
            centers = ccs.get_all_cost_centers(active_only=True)
            self.cc_parent.options = [ft.dropdown.Option(key="0", text="لا يوجد (مركز رئيسي)")] + [
                ft.dropdown.Option(key=str(c['id']), text=f"{c['code']} - {c['name']}") for c in centers
            ]
            if not self.cc_parent.value: self.cc_parent.value = "0"
        refresh_parents()

        def add_cc(e):
            if not self.cc_code.value or not self.cc_name.value:
                self.show_snackbar("الرمز والاسم مطلوبان", ACCENT_RED); return
            try:
                parent_id = None if self.cc_parent.value == "0" else int(self.cc_parent.value)
                ccs.create_cost_center(self.cc_code.value, self.cc_name.value, parent_id)
                self.show_snackbar("تمت الإضافة بنجاح", ACCENT_GREEN)
                self.cc_code.value = ""; self.cc_name.value = ""
                refresh_parents()
                self.refresh_tree_and_table()
            except ValueError as ex:
                self.show_snackbar(str(ex), ACCENT_RED)

        form_container = ft.Container(
            content=ft.Column([
                ft.Text("➕ إضافة مركز جديد", color=ACCENT_BLUE, weight=ft.FontWeight.BOLD),
                ft.Row([self.cc_code, self.cc_name]),
                self.cc_parent,
                ft.ElevatedButton("✅ إضافة", on_click=add_cc, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
            ]),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15
        )

        # الشجرة والجدول
        self.tree_container = ft.Container()
        self.table_container = ft.Container()
        self.edit_container = ft.Container()
        
        self.refresh_tree_and_table()

        return ft.Column([
            ft.Row([form_container, self.tree_container], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📋 جميع المراكز", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
            self.table_container,
            ft.Divider(color=GLASS_BORDER),
            self.edit_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def refresh_tree_and_table(self):
        # الشجرة
        tree = ccs.get_cost_center_tree()
        tree_lines = []
        def render(nodes, indent=0):
            for node in nodes:
                icon = "📁" if node['children'] else "📄"
                active = "🟢" if node['is_active'] else "🔴"
                tree_lines.append(f"{'    ' * indent}{icon} {active} {node['code']} - {node['name']}")
                if node['children']: render(node['children'], indent + 1)
        render(tree)
        self.tree_container.content = ft.Container(
            content=ft.Column([
                ft.Text("📌 الشجرة التنظيمية", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Column([ft.Text(l, color=TEXT_SECONDARY, size=12) for l in tree_lines], spacing=2)
            ]),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

        # الجدول
        centers = ccs.get_all_cost_centers(active_only=False)
        if centers:
            df = pd.DataFrame(centers)
            df['الحالة'] = df['is_active'].map({1: '🟢 نشط', 0: '🔴 غير نشط'})
            self.table_container.content = temp_data_table(df[['id', 'code', 'name', 'الحالة']])
            self.build_edit_form(df)
        else:
            self.table_container.content = ft.Text("لا توجد بيانات", color=TEXT_SECONDARY)
        self.page.update()

    def build_edit_form(self, df):
        self.edit_dd = ft.Dropdown(
            label="اختر المركز للتعديل",
            options=[ft.dropdown.Option(key=str(row['id']), text=f"{row['code']} - {row['name']}") for _, row in df.iterrows()],
            value=str(df.iloc[0]['id']), expand=True
        )
        self.edit_name = ft.TextField(label="الاسم الجديد", value=df.iloc[0]['name'], expand=True)
        self.edit_code = ft.TextField(label="الرمز الجديد", value=df.iloc[0]['code'], expand=True)
        self.edit_active = ft.Checkbox(label="نشط", value=bool(df.iloc[0]['is_active']))

        def on_select(e):
            sel = df[df['id'] == int(self.edit_dd.value)].iloc[0]
            self.edit_name.value = sel['name']
            self.edit_code.value = sel['code']
            self.edit_active.value = bool(sel['is_active'])
            self.page.update()

        def save_edit(e):
            ccs.update_cost_center(int(self.edit_dd.value), code=self.edit_code.value, name=self.edit_name.value, is_active=1 if self.edit_active.value else 0)
            self.show_snackbar("تم التحديث", ACCENT_GREEN)
            self.refresh_tree_and_table()

        self.edit_dd.on_change = on_select
        self.edit_container.content = ft.Column([
            ft.Text("✏️ تعديل مركز", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
            self.edit_dd,
            ft.Row([self.edit_name, self.edit_code]),
            self.edit_active,
            ft.ElevatedButton("💾 حفظ التعديلات", on_click=save_edit, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
        ], spacing=10)

    # ============================================================
    # 2. توزيع المعاملات
    # ============================================================
    def build_distribution_tab(self):
        conn = database.get_connection()
        entries = conn.execute("SELECT id, date, description FROM journal_entries ORDER BY id DESC LIMIT 20").fetchall()
        conn.close()
        if not entries:
            return ft.Text("لا توجد قيود مسجلة", color=TEXT_SECONDARY)

        self.entry_map = {e['id']: f"#{e['id']} - {e['date']} - {e['description']}" for e in entries}
        self.dist_entry_dd = ft.Dropdown(
            label="اختر القيد",
            options=[ft.dropdown.Option(key=str(k), text=v) for k, v in self.entry_map.items()],
            value=str(entries[0]['id']), expand=True
        )
        self.dist_entry_dd.on_change = lambda e: self.load_dist_lines()

        self.dist_lines_container = ft.Container()
        self.load_dist_lines()

        return ft.Column([
            ft.Text("📌 توزيع سطر قيد على مراكز التكلفة", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.dist_entry_dd,
            self.dist_lines_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_dist_lines(self):
        if not self.dist_entry_dd.value: return
        entry_id = int(self.dist_entry_dd.value)
        conn = database.get_connection()
        lines = conn.execute("SELECT id, account_name, debit, credit FROM journal_lines WHERE entry_id = ?", (entry_id,)).fetchall()
        conn.close()
        if not lines:
            self.dist_lines_container.content = ft.Text("القيد لا يحتوي على سطور", color=TEXT_SECONDARY)
            self.page.update(); return

        line_options = {l['id']: f"{l['account_name']} (مدين: {l['debit']:,.2f}, دائن: {l['credit']:,.2f})" for l in lines}
        self.dist_line_dd = ft.Dropdown(
            label="اختر السطر",
            options=[ft.dropdown.Option(key=str(k), text=v) for k, v in line_options.items()],
            value=str(lines[0]['id']), expand=True
        )
        self.dist_line_dd.on_change = lambda e: self.load_dist_centers(lines)
        
        self.dist_centers_container = ft.Container()
        self.load_dist_centers(lines)
        
        self.dist_lines_container.content = ft.Column([self.dist_line_dd, self.dist_centers_container], spacing=15)
        self.page.update()

    def load_dist_centers(self, lines):
        if not self.dist_line_dd.value: return
        line_id = int(self.dist_line_dd.value)
        line = next(l for l in lines if l['id'] == line_id)
        line_amount = line['debit'] if line['debit'] > 0 else line['credit']
        
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            self.dist_centers_container.content = ft.Text("لا توجد مراكز تكلفة نشطة", color=TEXT_SECONDARY)
            self.page.update(); return

        # قائمة التوزيعات
        self.alloc_rows = [] # (center_dd, amount_input, pct_input)
        rows_control = ft.Column()
        self.remaining_text = ft.Text(f"المتبقي: {line_amount:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        
        def add_alloc_row(e=None):
            idx = len(self.alloc_rows)
            center_dd = ft.Dropdown(label=f"المركز {idx+1}", options=[ft.dropdown.Option(key=str(c['id']), text=f"{c['code']} - {c['name']}") for c in centers], expand=True)
            amount_input = ft.TextField(label=f"المبلغ {idx+1}", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=120)
            pct_input = ft.TextField(label=f"% {idx+1}", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=80)
            
            amount_input.on_change = lambda e: self.recalc_dist(line_amount)
            pct_input.on_change = lambda e: self.recalc_dist(line_amount)
            center_dd.on_change = lambda e: self.recalc_dist(line_amount)
            
            self.alloc_rows.append((center_dd, amount_input, pct_input))
            rows_control.controls.append(ft.Row([center_dd, amount_input, pct_input]))
            self.page.update()

        def save_dist(e):
            allocs = []
            total = 0.0
            for cdd, ai, pi in self.alloc_rows:
                if not cdd.value: continue
                try: amt = float(ai.value or 0)
                except ValueError: amt = 0.0
                if amt > 0:
                    allocs.append({'cost_center_id': int(cdd.value), 'amount': amt, 'percentage': float(pi.value or 0)})
                    total += amt
            if abs(total - line_amount) > 0.01:
                self.show_snackbar(f"يجب أن يساوي مجموع التوزيعات {line_amount:,.2f}", ACCENT_RED); return
            if not allocs:
                self.show_snackbar("لم يتم إدخال أي توزيع", ACCENT_RED); return
            try:
                ccs.allocate_journal_line(line_id, allocs)
                self.show_snackbar("تم حفظ التوزيعات بنجاح", ACCENT_GREEN)
            except Exception as ex:
                self.show_snackbar(str(ex), ACCENT_RED)

        add_alloc_row()
        add_alloc_row() # بدءاً بصفين

        self.dist_centers_container.content = ft.Column([
            ft.Text(f"المبلغ الإجمالي للسطر: {line_amount:,.2f}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
            rows_control,
            self.remaining_text,
            ft.Row([
                ft.ElevatedButton("➕ إضافة مركز توزيع آخر", on_click=add_alloc_row, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
                ft.ElevatedButton("💾 حفظ التوزيعات", on_click=save_dist, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
            ], spacing=10)
        ], spacing=10)
        self.page.update()

    def recalc_dist(self, total_amount):
        total = 0.0
        for cdd, ai, pi in self.alloc_rows:
            try: total += float(ai.value or 0)
            except ValueError: pass
        remaining = total_amount - total
        self.remaining_text.value = f"المتبقي: {remaining:,.2f}"
        self.remaining_text.color = ACCENT_GREEN if abs(remaining) < 0.01 else ACCENT_ORANGE
        self.page.update()

    # ============================================================
    # 3. تحليل وتقارير
    # ============================================================
    def build_analysis_tab(self):
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            return ft.Text("لا توجد مراكز", color=TEXT_SECONDARY)

        self.an_center_dd = ft.Dropdown(
            label="اختر المركز",
            options=[ft.dropdown.Option(key=str(c['id']), text=c['name']) for c in centers],
            value=str(centers[0]['id']), expand=True
        )
        self.an_from = ft.TextField(label="من تاريخ", value=date.today().replace(day=1).strftime("%Y-%m-%d"), expand=True)
        self.an_to = ft.TextField(label="إلى تاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.an_result = ft.Container()

        def show_analysis(e):
            cid = int(self.an_center_dd.value)
            balance = ccs.get_cost_center_balance(cid, self.an_from.value, self.an_to.value)
            stmt = ccs.get_cost_center_income_statement(cid, self.an_from.value, self.an_to.value)
            
            content = [
                ft.Row([
                    ft.Container(content=ft.Column([ft.Text(f"{balance['net']:,.2f}", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD), ft.Text("صافي التدفق", color=TEXT_SECONDARY, size=11)]), bgcolor=GLASS_BG, padding=15, border_radius=12, expand=True),
                    ft.Container(content=ft.Column([ft.Text(f"{stmt['income']:,.2f}", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD), ft.Text("الإيرادات", color=TEXT_SECONDARY, size=11)]), bgcolor=GLASS_BG, padding=15, border_radius=12, expand=True),
                    ft.Container(content=ft.Column([ft.Text(f"{stmt['expenses']:,.2f}", color=ACCENT_RED, size=20, weight=ft.FontWeight.BOLD), ft.Text("المصروفات", color=TEXT_SECONDARY, size=11)]), bgcolor=GLASS_BG, padding=15, border_radius=12, expand=True),
                ], spacing=15)
            ]
            
            if PLOTLY_AVAILABLE:
                fig = go.Figure(data=[
                    go.Bar(name='الإيرادات', x=['الإيرادات'], y=[stmt['income']], marker_color='#a78bfa'),
                    go.Bar(name='المصروفات', x=['المصروفات'], y=[stmt['expenses']], marker_color='#60a5fa')
                ])
                fig.update_layout(title="الإيرادات مقابل المصروفات", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
                content.append(ft.Container(content=PlotlyChart(fig, expand=True), height=300))
            
            self.an_result.content = ft.Column(content, spacing=15)
            self.page.update()

        return ft.Column([
            ft.Text("📊 تحليل الأداء حسب المركز", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.an_center_dd, ft.Row([self.an_from, self.an_to]),
            ft.ElevatedButton("📈 عرض التحليل", on_click=show_analysis, bgcolor=ACCENT_PURPLE, color=ft.colors.WHITE),
            self.an_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 4. الموازنات
    # ============================================================
    def build_budget_tab(self):
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            return ft.Text("لا توجد مراكز", color=TEXT_SECONDARY)

        self.budget_center_dd = ft.Dropdown(
            label="المركز", options=[ft.dropdown.Option(key=str(c['id']), text=c['name']) for c in centers],
            value=str(centers[0]['id']), expand=True
        )
        self.budget_year = ft.TextField(label="السنة المالية", value="2025", keyboard_type=ft.KeyboardType.NUMBER)
        self.budget_result = ft.Container()

        def show_budget(e):
            cid = int(self.budget_center_dd.value)
            yr = int(self.budget_year.value or 2025)
            data = ccs.get_budget_variance(cid, yr)
            if data and data.get('details'):
                df = pd.DataFrame(data['details'])
                df_display = df[['account_name', 'budget', 'actual', 'variance', 'variance_pct']]
                df_display.columns = ['الحساب', 'الموازنة', 'الفعلي', 'الانحراف', 'نسبة الانحراف %']
                
                content = [temp_data_table(df_display)]
                if PLOTLY_AVAILABLE:
                    fig = px.bar(df, x='account_name', y=['budget', 'actual'], barmode='group',
                                 color_discrete_map={'budget': '#a78bfa', 'actual': '#60a5fa'})
                    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
                    content.append(ft.Container(content=PlotlyChart(fig, expand=True), height=300))
                self.budget_result.content = ft.Column(content, spacing=15)
            else:
                self.budget_result.content = ft.Text("لا توجد موازنات مسجلة لهذا المركز", color=TEXT_SECONDARY)
            self.page.update()

        # إضافة موازنة
        conn = database.get_connection()
        accounts = conn.execute("SELECT id, name FROM accounts ORDER BY name").fetchall()
        conn.close()
        
        self.budget_account_dd = ft.Dropdown(
            label="الحساب", options=[ft.dropdown.Option(key=str(a['id']), text=a['name']) for a in accounts],
            value=str(accounts[0]['id']) if accounts else None, expand=True
        )
        self.budget_amount = ft.TextField(label="المبلغ المخطط", value="0", keyboard_type=ft.KeyboardType.NUMBER)

        def save_budget(e):
            cid = int(self.budget_center_dd.value)
            yr = int(self.budget_year.value or 2025)
            acc_id = int(self.budget_account_dd.value)
            try: amt = float(self.budget_amount.value or 0)
            except ValueError: amt = 0.0
            ccs.set_budget(cid, acc_id, yr, amt)
            self.show_snackbar("تم حفظ الموازنة", ACCENT_GREEN)
            show_budget(None)

        return ft.Column([
            ft.Text("💰 الموازنة التقديرية للمراكز", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            ft.Row([self.budget_center_dd, self.budget_year]),
            ft.ElevatedButton("🔍 عرض الموازنة والانحرافات", on_click=show_budget, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
            self.budget_result,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("➕ إضافة/تحديث موازنة", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
            self.budget_account_dd, self.budget_amount,
            ft.ElevatedButton("💾 حفظ الموازنة", on_click=save_budget, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 5. إقفال المراكز
    # ============================================================
    def build_closing_tab(self):
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            return ft.Text("لا توجد مراكز تكلفة نشطة", color=TEXT_SECONDARY)

        self.closing_center_dd = ft.Dropdown(
            label="اختر المركز لإقفاله",
            options=[ft.dropdown.Option(key=str(c['id']), text=f"{c['code']} - {c['name']}") for c in centers],
            value=str(centers[0]['id']), expand=True
        )
        self.closing_year = ft.TextField(label="السنة المالية للإقفال", value="2025", keyboard_type=ft.KeyboardType.NUMBER)
        self.closing_retained = ft.TextField(label="كود حساب الأرباح المحتجزة", value="310000")

        def do_closing(e):
            try:
                cid = int(self.closing_center_dd.value)
                yr = int(self.closing_year.value or 2025)
            except ValueError:
                self.show_snackbar("قيم غير صالحة", ACCENT_RED); return
            
            success, net_income, error = closing_service.create_cost_center_closing_entry(
                year=yr, cost_center_id=cid, retained_earnings_code=self.closing_retained.value
            )
            if success:
                self.show_snackbar(f"✅ تم إقفال المركز! صافي الدخل: {net_income:,.2f}", ACCENT_GREEN)
            else:
                self.show_snackbar(f"❌ فشل الإقفال: {error}", ACCENT_RED)

        return ft.Column([
            ft.Text("🔒 إقفال مركز تكلفة لسنة مالية", color=ACCENT_RED, size=20, weight=ft.FontWeight.BOLD),
            ft.Text("هذه العملية تنشئ قيد إغلاق لمركز التكلفة المحدد، حيث يتم تصفير أرصدة الإيرادات والمصروفات المرتبطة به وتوجيه صافي الدخل إلى حساب الأرباح المحتجزة.", color=TEXT_SECONDARY, size=12),
            ft.Divider(color=GLASS_BORDER),
            self.closing_center_dd, self.closing_year, self.closing_retained,
            ft.ElevatedButton("🔒 تنفيذ إقفال المركز", on_click=do_closing, bgcolor=ACCENT_RED, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
