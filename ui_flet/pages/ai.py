# ui_flet/pages/ai.py
import flet as ft
import pandas as pd
import json
import os
from datetime import date, datetime
from services.ai_service import (
    GROQ_API_KEY, create_ai_tables, query_groq, save_chat_history, get_chat_history,
    get_comprehensive_data, get_inventory_data, get_employee_info, get_recent_entries,
    get_financial_ratios, get_business_snapshot, analyze_cost_center_performance,
    compare_cost_centers, get_cost_center_budget_analysis, generate_template_entry,
    get_available_operations, get_operation_description, is_mixed_operation,
    is_vat_operation, is_inventory_adjustment, is_salary_operation,
)
from services import cost_center_service as ccs
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

GOLD = "#D4AF37"

AVAILABLE_MODELS = {
    "GPT OSS 20B (عالي الدقة)": "openai/gpt-oss-20b",
    "compound-mini": "groq/compound-mini",
}

def temp_data_table(df: pd.DataFrame) -> ft.Control:
    if df is None or df.empty:
        return ft.Text("لا توجد بيانات", color=TEXT_SECONDARY)
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

class AIPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.selected_model = "openai/gpt-oss-20b"
        self.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try: create_ai_tables()
        except Exception as e: print(f"AI init: {e}")

        self.header = ft.Text("🤖 المساعد المالي الذكي", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("AI ENTERPRISE HUB — نظرة عامة على مؤشرات الأداء، التحليلات، وتوليد القيود الآلية", color=TEXT_SECONDARY, size=14)

        self.model_dd = ft.Dropdown(
            label="اختر المحرك:", options=[ft.dropdown.Option(k) for k in AVAILABLE_MODELS.keys()],
            value=list(AVAILABLE_MODELS.keys())[0], width=250,
            on_change=lambda e: self.set_model()
        )

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="🧠 مساعد", content=self.build_assistant_tab()),
                ft.Tab(text="📊 محلل", content=self.build_analyst_tab()),
                ft.Tab(text="📦 مخزون", content=self.build_inventory_tab()),
                ft.Tab(text="💬 موظفين", content=self.build_hr_tab()),
                ft.Tab(text="📝 قيود", content=self.build_entries_tab()),
                ft.Tab(text="🔍 احتيال", content=self.build_fraud_tab()),
                ft.Tab(text="🔮 تنبؤات", content=self.build_forecast_tab()),
                ft.Tab(text="📈 تقرير شامل", content=self.build_board_tab()),
                ft.Tab(text="🎯 مراكز تكلفة", content=self.build_cost_center_tab()),
            ], expand=True,
        )

        # FilePicker للصوت
        self.audio_picker = ft.FilePicker(on_result=self.on_audio_picked)
        self.page.overlay.append(self.audio_picker)

        self.controls = [
            ft.Row([self.header, self.model_dd], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.subtitle,
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def set_model(self):
        self.selected_model = AVAILABLE_MODELS[self.model_dd.value]
        self.show_snackbar(f"✅ تم اختيار: {self.model_dd.value}", ACCENT_GREEN)

    def render_ai_response(self, content):
        """عرض رد AI في بطاقة زجاجية"""
        if not content: return ft.Text("لا توجد استجابة", color=TEXT_SECONDARY)
        return ft.Container(
            content=ft.Markdown(content, selectable=True),
            bgcolor=GLASS_BG, border=ft.border.all(1, GOLD), border_radius=16, padding=20
        )

    # ============================================================
    # 1. مساعد
    # ============================================================
    def build_assistant_tab(self):
        self.chat_history_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=350)
        self.question_input = ft.TextField(label="اطرح سؤالك المالي أو التشغيلي هنا...", multiline=True, expand=True)
        self.response_container = ft.Container()

        def send_question(e):
            question = self.question_input.value.strip()
            if not question: return
            
            # إضافة سؤال المستخدم
            self.chat_history_col.controls.append(ft.Container(
                content=ft.Text(f"👤 {question}", color=TEXT_PRIMARY, size=13),
                bgcolor=ft.colors.with_opacity(0.1, ACCENT_BLUE), padding=10, border_radius=8
            ))
            
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"""أنت مستشار مالي ومدير مالي (CFO) خبير تعمل ضمن نظام ERP. البيانات الحالية للشركة:\n{d}\nالمطلوب:\n1. قدم إجابة وافية، دقيقة، ومنظمة مهنياً.\n2. استخدم العناوين العريضة والجداول لتوضيح الأرقام.\n3. اشرح التأثير المالي والتشغيلي بوضوح.\n4. حافظ على نبرة احترافية، رصينة، وداعمة لاتخاذ القرار (استخدم تنسيق Markdown)."""
            
            with self.page.session:
                ans = query_groq(prompt, question, model=self.selected_model, max_tokens=2048)
            
            self.chat_history_col.controls.append(self.render_ai_response(ans))
            self.response_container.content = self.chat_history_col
            save_chat_history(self.active_session, "user", question, self.selected_model, "مساعد")
            save_chat_history(self.active_session, "assistant", ans, self.selected_model, "مساعد")
            self.question_input.value = ""
            self.page.update()

        def pick_audio(e):
            self.audio_picker.pick_files(allowed_extensions=["wav", "mp3", "m4a", "ogg"], allow_multiple=False)

        self.response_container.content = self.chat_history_col

        return ft.Column([
            self.response_container,
            ft.Row([
                ft.IconButton(icon=ft.icons.MIC, on_click=pick_audio, tooltip="تسجيل صوتي"),
                self.question_input,
                ft.IconButton(icon=ft.icons.SEND, on_click=send_question, tooltip="إرسال")
            ], vertical_alignment=ft.CrossAxisAlignment.END)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def on_audio_picked(self, e: ft.FilePickerResultEvent):
        if not e.files:
            self.show_snackbar("لم يتم اختيار ملف", ACCENT_ORANGE); return
        self.show_snackbar(f"⚠️ معالجة الصوت غير متاحة في Flet حالياً. الرجاء كتابة السؤال نصياً.", ACCENT_ORANGE)

    # ============================================================
    # 2. محلل
    # ============================================================
    def build_analyst_tab(self):
        self.analyst_result = ft.Container()
        
        def run_analysis(e):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            prompt = f"""أنت محلل مالي أول ومستشار استراتيجي. الأرقام:\nالإيرادات: {data.get('revenue',0):,.2f} | المصروفات: {data.get('expenses',0):,.2f} | صافي الدخل: {data.get('net_income',0):,.2f}\nالنسب: {json.dumps(ratios, ensure_ascii=False)}\n\nالمطلوب تقديم تقرير تحليل مالي مهيكل كالتالي:\n1. الملخص التنفيذي.\n2. تحليل النسب.\n3. نقاط القوة والضعف (SWOT).\n4. التوصيات الاستراتيجية."""
            ans = query_groq(prompt, "قدم التحليل المالي الشامل", model=self.selected_model, max_tokens=2048)
            self.analyst_result.content = self.render_ai_response(ans)
            self.page.update()

        return ft.Column([
            ft.Text("📊 التحليل المالي والنسب", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("🚀 بدء التحليل المالي الشامل", on_click=run_analysis, bgcolor=GOLD, color=ft.colors.BLACK),
            self.analyst_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 3. مخزون
    # ============================================================
    def build_inventory_tab(self):
        self.inv_result = ft.Container()
        self.low_stock_container = ft.Container()
        
        low, allp = get_inventory_data()
        if low:
            self.low_stock_container.content = ft.Container(
                content=ft.Text(f"⚠️ يوجد {len(low)} منتجات تحت الحد الأدنى للطلب!", color=ACCENT_RED),
                bgcolor=ft.colors.with_opacity(0.1, ACCENT_RED), padding=10, border_radius=8
            )

        def run_inv_analysis(e):
            if not allp:
                self.show_snackbar("لا توجد بيانات مخزون", ACCENT_ORANGE); return
            df = pd.DataFrame(allp)
            prompt = f"""أنت خبير متمرس في إدارة سلاسل الإمداد والمخزون. البيانات:\n{df.to_string()}\nالمطلوب تقديم تحليل شامل:\n1. التقييم العام.\n2. الأصناف الحرجة.\n3. المخاطر التشغيلية والمالية.\n4. الإجراءات التصحيحية."""
            ans = query_groq(prompt, "حلل المخزون وقدم تقريراً إدارياً", model=self.selected_model, max_tokens=2048)
            self.inv_result.content = self.render_ai_response(ans)
            self.page.update()

        return ft.Column([
            ft.Text("📦 تحليل المخزون واكتشاف العجز", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.low_stock_container,
            ft.ElevatedButton("📦 تحليل حالة المخزون", on_click=run_inv_analysis, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            self.inv_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 4. موظفين
    # ============================================================
    def build_hr_tab(self):
        self.hr_name = ft.TextField(label="اسم الموظف:", expand=True)
        self.hr_question = ft.TextField(label="السؤال:", expand=True)
        self.hr_result = ft.Container()
        
        def run_hr(e):
            if not self.hr_name.value or not self.hr_question.value: return
            emp, sal = get_employee_info(self.hr_name.value)
            if emp:
                info = f"{emp['name']} - {emp['position']} | الراتب الأساسي: {sal.get('basic_salary',0) if sal else 0}"
                prompt = f"""أنت مدير موارد بشرية (HR Manager) محترف ولبق.\nبيانات الموظف: {info}.\nأجب على استفسار الموظف ({self.hr_question.value}) بأسلوب مهني، داعم، وواضح."""
                ans = query_groq(prompt, self.hr_question.value, model=self.selected_model, max_tokens=1000)
                self.hr_result.content = self.render_ai_response(ans)
            else:
                self.hr_result.content = ft.Text("❌ الموظف غير موجود", color=ACCENT_RED)
            self.page.update()

        return ft.Column([
            ft.Text("💬 استعلامات الموارد البشرية الذكية", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.hr_name, self.hr_question]),
            ft.ElevatedButton("استعلام", on_click=run_hr, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE),
            self.hr_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 5. قيود
    # ============================================================
    def build_entries_tab(self):
        operations = get_available_operations()
        self.op_dd = ft.Dropdown(label="اختر نوع العملية المالية", options=[ft.dropdown.Option(o) for o in operations], value=operations[0] if operations else None, expand=True)
        self.op_desc = ft.Text("", color=TEXT_SECONDARY, size=12)
        self.op_dd.on_change = lambda e: self.on_op_change(operations)
        
        self.entry_inputs_container = ft.Column()
        self.entry_result = ft.Container()
        self.on_op_change(operations)

        return ft.Column([
            ft.Text("🪄 محرك القيود المحاسبية الذكي", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.op_dd,
            self.op_desc,
            ft.Divider(color=GLASS_BORDER),
            self.entry_inputs_container,
            self.entry_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def on_op_change(self, operations):
        if not self.op_dd.value: return
        selected_op = self.op_dd.value
        self.op_desc.value = f"📌 {get_operation_description(selected_op)}"
        
        self.entry_inputs_container.controls.clear()
        
        if is_mixed_operation(selected_op):
            self.total_amount = ft.TextField(label="المبلغ الإجمالي", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.cash_amount = ft.TextField(label="الجزء النقدي", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.credit_amount = ft.TextField(label="الجزء الآجل", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.vat_rate = self.expense_name = None
            self.entry_inputs_container.controls = [ft.Row([self.total_amount, self.cash_amount, self.credit_amount])]
        elif is_vat_operation(selected_op):
            self.total_amount = ft.TextField(label="المبلغ شامل الضريبة", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.vat_rate = ft.TextField(label="نسبة الضريبة (%)", value="15", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.cash_amount = self.credit_amount = self.expense_name = None
            self.entry_inputs_container.controls = [ft.Row([self.total_amount, self.vat_rate])]
        elif selected_op == "سداد مصروف":
            self.total_amount = ft.TextField(label="المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.expense_name = ft.TextField(label="اسم المصروف", value="كهرباء", expand=True)
            self.vat_rate = self.cash_amount = self.credit_amount = None
            self.entry_inputs_container.controls = [ft.Row([self.total_amount, self.expense_name])]
        elif is_inventory_adjustment(selected_op):
            self.total_amount = ft.TextField(label="قيمة التسوية", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.adj_type = ft.Dropdown(label="نوع التسوية", options=[ft.dropdown.Option("عجز (نقص)"), ft.dropdown.Option("فائض (زيادة)")], value="عجز (نقص)", expand=True)
            self.vat_rate = self.cash_amount = self.credit_amount = self.expense_name = None
            self.entry_inputs_container.controls = [ft.Row([self.total_amount, self.adj_type])]
        else:
            self.total_amount = ft.TextField(label="المبلغ", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
            self.vat_rate = self.cash_amount = self.credit_amount = self.expense_name = None
            self.entry_inputs_container.controls = [self.total_amount]
        
        self.entry_inputs_container.controls.append(ft.ElevatedButton("✨ توليد القيد المحاسبي", on_click=self.do_generate_entry, bgcolor=GOLD, color=ft.colors.BLACK))
        self.page.update()

    def do_generate_entry(self, e):
        try: total = float(self.total_amount.value or 0)
        except ValueError: total = 0.0
        if total <= 0:
            self.show_snackbar("⚠️ يرجى إدخال مبلغ صحيح أكبر من الصفر", ACCENT_ORANGE); return

        selected_op = self.op_dd.value
        cash = credit = vat = exp_name = adj_side = inv_side = None
        try:
            if is_mixed_operation(selected_op):
                cash = float(self.cash_amount.value or 0); credit = float(self.credit_amount.value or 0)
            elif is_vat_operation(selected_op):
                vat = float(self.vat_rate.value or 0) / 100
            elif selected_op == "سداد مصروف":
                exp_name = self.expense_name.value
            elif is_inventory_adjustment(selected_op):
                if self.adj_type.value == "عجز (نقص)": adj_side, inv_side = "debit", "credit"
                else: adj_side, inv_side = "credit", "debit"
        except (ValueError, AttributeError): pass

        entry, display, confidence, confidence_label, confidence_color = generate_template_entry(
            operation_type=selected_op, amount=total, cash_amount=cash, credit_amount=credit,
            expense_name=exp_name, vat_rate=vat, adjustment_side=adj_side, inventory_side=inv_side
        )
        
        if entry:
            self.entry_result.content = ft.Column([
                ft.Text("🧾 القيد المحاسبي المولد:", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Container(content=ft.Text(display, font_family="monospace"), bgcolor="#1E293B", padding=15, border_radius=8),
                ft.Row([
                    ft.Text(f"مستوى الثقة: {confidence}% - {confidence_label}", color=confidence_color, weight=ft.FontWeight.BOLD)
                ])
            ])
        else:
            self.entry_result.content = ft.Text(f"❌ {display}", color=ACCENT_RED)
        self.page.update()

    # ============================================================
    # 6. احتيال
    # ============================================================
    def build_fraud_tab(self):
        self.fraud_result = ft.Container()
        
        def run_fraud(e):
            entries = get_recent_entries()
            if not entries:
                self.show_snackbar("لا توجد قيود كافية للفحص", ACCENT_ORANGE); return
            df = pd.DataFrame(entries)
            prompt = f"""أنت مدقق مالي جنائي ومراجع داخلي (Forensic Auditor).\nافحص القيود الأخيرة:\n{df.to_string()}\nالمطلوب:\n1. نتيجة الفحص الأولية.\n2. الملاحظات والتشوهات (إن وجدت).\n3. مؤشرات الخطر الإداري.\n4. التوصيات الرقابية."""
            ans = query_groq(prompt, "افحص القيود واستخرج تقريراً", model=self.selected_model, max_tokens=2048)
            self.fraud_result.content = self.render_ai_response(ans)
            self.page.update()

        return ft.Column([
            ft.Text("🕵️ نظام كشف الاحتيال والتشوهات", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("🔍 فحص القيود الأخيرة", on_click=run_fraud, bgcolor=ACCENT_RED, color=ft.colors.WHITE),
            self.fraud_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 7. تنبؤات
    # ============================================================
    def build_forecast_tab(self):
        self.forecast_period = ft.Dropdown(label="حدد الأفق الزمني", options=[ft.dropdown.Option(p) for p in ["الشهر القادم", "الربع القادم", "نهاية العام"]], value="الشهر القادم", expand=True)
        self.forecast_result = ft.Container()
        
        def run_forecast(e):
            data = get_comprehensive_data()
            prompt = f"""أنت خبير تخطيط مالي واستشراف أعمال (FP&A Manager). بناءً على البيانات: {json.dumps(data, ensure_ascii=False)}\nالفترة: {self.forecast_period.value}\nالمطلوب:\n1. التوقعات المالية.\n2. جدول السيناريوهات.\n3. المخاطر المحتملة.\n4. استراتيجيات التحوط والنمو."""
            ans = query_groq(prompt, "قم بتوليد التنبؤ المالي", model=self.selected_model, max_tokens=2048)
            self.forecast_result.content = self.render_ai_response(ans)
            self.page.update()

        return ft.Column([
            ft.Text("🔮 التخطيط المالي والتنبؤ", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.forecast_period,
            ft.ElevatedButton("🚀 توليد التنبؤ المالي", on_click=run_forecast, bgcolor=ACCENT_PURPLE, color=ft.colors.WHITE),
            self.forecast_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 8. تقرير شامل
    # ============================================================
    def build_board_tab(self):
        self.board_result = ft.Container()
        
        def run_board(e):
            data = get_comprehensive_data()
            prompt = f"""أنت مستشار استراتيجي ومالي لمجلس الإدارة. بناءً على: {json.dumps(data, ensure_ascii=False)}\nالمطلوب إعداد تقرير مجلس إدارة (Board Report):\n1. الملخص التنفيذي.\n2. الأداء المالي.\n3. الأداء التشغيلي.\n4. تقييم المخاطر.\n5. القرارات الاستراتيجية المقترحة."""
            ans = query_groq(prompt, "أصدر تقرير مجلس الإدارة", model=self.selected_model, max_tokens=3000)
            self.board_result.content = self.render_ai_response(ans)
            self.page.update()

        return ft.Column([
            ft.Text("📑 تقرير مجلس الإدارة الآلي", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("📄 إصدار التقرير الشامل", on_click=run_board, bgcolor=GOLD, color=ft.colors.BLACK),
            self.board_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 9. مراكز تكلفة
    # ============================================================
    def build_cost_center_tab(self):
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            return ft.Text("⚠️ لا توجد مراكز تكلفة نشطة", color=ACCENT_ORANGE)

        self.cc_dd = ft.Dropdown(
            label="حدد مركز التكلفة (القطاع)",
            options=[ft.dropdown.Option(key=str(c['id']), text=f"{c['code']} - {c['name']}") for c in centers],
            value=str(centers[0]['id']), expand=True
        )
        self.cc_result = ft.Container()

        def run_perf(e):
            ans = analyze_cost_center_performance(int(self.cc_dd.value))
            self.cc_result.content = self.render_ai_response(ans)
            self.page.update()

        def run_comp(e):
            ans = compare_cost_centers()
            self.cc_result.content = self.render_ai_response(ans)
            self.page.update()

        def run_budget(e):
            ans = get_cost_center_budget_analysis(int(self.cc_dd.value), datetime.now().year)
            self.cc_result.content = self.render_ai_response(ans)
            self.page.update()

        return ft.Column([
            ft.Text("🏢 تحليل أداء قطاعات الأعمال", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.cc_dd,
            ft.Row([
                ft.ElevatedButton("📊 تقييم الأداء", on_click=run_perf, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, expand=True),
                ft.ElevatedButton("⚖️ مقارنة القطاعات", on_click=run_comp, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE, expand=True),
                ft.ElevatedButton("📉 تحليل الانحرافات", on_click=run_budget, bgcolor=ACCENT_PURPLE, color=ft.colors.WHITE, expand=True),
            ], spacing=10),
            self.cc_result
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
