# ui_flet/pages/crm.py
import flet as ft
import pandas as pd
from datetime import date

# استيراد الخدمات الخاصة بك
from services.crm_service import (
    create_crm_tables,
    add_lead,
    update_lead,
    get_all_leads,
    convert_lead_to_customer,
    add_opportunity,
    get_opportunities,
    get_pipeline_summary,
    add_interaction,
    get_interactions,
    get_crm_summary
)

# استيراد الثيم والدوال المشتركة
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, build_data_table, GLASS_BG, GLASS_BORDER
)

class CRMPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        # استدعاء إنشاء الجداول مرة واحدة فقط
        try:
            create_crm_tables()
        except Exception as e:
            print(f"CRM Tables already exist or error: {e}")

        self.header = ft.Text("🤝 إدارة علاقات العملاء (CRM)", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        
        # بناء التبويبات
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="👥 العملاء المحتملين", content=self.build_leads_tab()),
                ft.Tab(text="💼 الفرص البيعية", content=self.build_opportunities_tab()),
                ft.Tab(text="📞 التفاعلات", content=self.build_interactions_tab()),
                ft.Tab(text="📊 لوحة التحكم", content=self.build_dashboard_tab()),
                ft.Tab(text="🔄 تحويل لعميل", content=self.build_convert_tab()),
            ],
            expand=True,
        )

        self.controls = [
            self.header,
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    # ============================================================
    # 1. تبويب العملاء المحتملين
    # ============================================================
    def build_leads_tab(self):
        # الحقول
        self.lead_name = ft.TextField(label="الاسم", expand=True)
        self.lead_company = ft.TextField(label="الشركة", expand=True)
        self.lead_phone = ft.TextField(label="الهاتف", expand=True)
        self.lead_email = ft.TextField(label="البريد الإلكتروني", expand=True)
        self.lead_source = ft.TextField(label="المصدر (نص حر)", expand=True, hint_text="مثال: معرض، إحالة...")
        self.lead_status = ft.Dropdown(
            label="الحالة",
            options=[ft.dropdown.Option(s) for s in ["جديد", "مؤهل", "قيد المتابعة", "غير مهتم", "تحول لعميل"]],
            value="جديد",
            expand=True
        )
        self.lead_notes = ft.TextField(label="ملاحظات", multiline=True, min_lines=2)

        # دالة الحفظ
        def save_lead(e):
            if not self.lead_name.value:
                self.page.snack_bar = ft.SnackBar(ft.Text("الاسم مطلوب", color=ACCENT_RED))
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            add_lead(
                self.lead_name.value, self.lead_company.value, self.lead_phone.value,
                self.lead_email.value, self.lead_source.value, self.lead_status.value, self.lead_notes.value
            )
            
            self.page.snack_bar = ft.SnackBar(ft.Text(f"تم إضافة {self.lead_name.value}"), bgcolor=ACCENT_GREEN)
            self.page.snack_bar.open = True
            self.load_leads_table() # تحديث الجدول
            self.page.update()

        form_content = ft.Column([
            ft.Row([self.lead_name, self.lead_company]),
            ft.Row([self.lead_phone, self.lead_email]),
            ft.Row([self.lead_source, self.lead_status]),
            self.lead_notes,
            ft.ElevatedButton("💾 حفظ", on_click=save_lead, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
        ])

        # الجدول
        self.leads_table_container = ft.Container()
        self.load_leads_table()

        return ft.Column([
            ft.ExpansionTile(
                title=ft.Text("➕ إضافة عميل محتمل جديد", color=ACCENT_BLUE),
                controls=[ft.Container(content=form_content, padding=10)],
            ),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("قائمة العملاء المحتملين", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.leads_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def load_leads_table(self):
        leads = get_all_leads()
        if leads:
            df = pd.DataFrame(leads)
            self.leads_table_container.content = build_data_table(df)
        else:
            self.leads_table_container.content = ft.Text("لا يوجد عملاء محتملون بعد", color=TEXT_SECONDARY)

    # ============================================================
    # 2. تبويب الفرص البيعية
    # ============================================================
    def build_opportunities_tab(self):
        self.opp_lead = ft.Dropdown(label="العميل المحتمل", expand=True)
        self.opp_title = ft.TextField(label="عنوان الفرصة", expand=True)
        self.opp_amount = ft.TextField(label="القيمة المتوقعة", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.opp_stage = ft.Dropdown(
            label="المرحلة",
            options=[ft.dropdown.Option(s) for s in ["مؤهل", "عرض سعر", "تفاوض", "مغلق ناجح", "مغلق خاسر"]],
            value="مؤهل", expand=True
        )
        self.opp_prob = ft.Slider(min=0, max=100, divisions=100, label="{value}%", value=50)
        self.opp_date = ft.TextField(label="تاريخ الإغلاق المتوقع (YYYY-MM-DD)", value=date.today().strftime("%Y-%m-%d"))

        self.load_leads_to_dropdown()

        def save_opp(e):
            try:
                lead_id = int(self.opp_lead.value)
                amount = float(self.opp_amount.value or 0)
            except ValueError:
                return

            if self.opp_title.value:
                add_opportunity(lead_id, self.opp_title.value, amount, self.opp_stage.value, int(self.opp_prob.value), self.opp_date.value)
                self.page.snack_bar = ft.SnackBar(ft.Text("تمت الإضافة"), bgcolor=ACCENT_GREEN)
                self.page.snack_bar.open = True
                self.load_opps_table()
                self.page.update()

        form_content = ft.Column([
            ft.Row([self.opp_lead]),
            ft.Row([self.opp_title, self.opp_amount]),
            ft.Row([self.opp_stage]),
            ft.Text("نسبة الإغلاق", color=TEXT_SECONDARY),
            self.opp_prob,
            self.opp_date,
            ft.ElevatedButton("💾 حفظ", on_click=save_opp, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ])

        self.opps_table_container = ft.Container()
        self.load_opps_table()

        return ft.Column([
            ft.ExpansionTile(
                title=ft.Text("➕ إضافة فرصة بيعية", color=ACCENT_GREEN),
                controls=[ft.Container(content=form_content, padding=10)],
            ),
            ft.Divider(color=GLASS_BORDER),
            self.opps_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def load_leads_to_dropdown(self):
        leads = get_all_leads()
        self.opp_lead.options = [ft.dropdown.Option(key=str(l['id']), text=l['name']) for l in leads]

    def load_opps_table(self):
        opportunities = get_opportunities()
        if opportunities:
            df = pd.DataFrame(opportunities)
            df = df.drop(columns=['notes'], errors='ignore')
            self.opps_table_container.content = build_data_table(df)
        else:
            self.opps_table_container.content = ft.Text("لا توجد فرص بيعية بعد", color=TEXT_SECONDARY)

    # ============================================================
    # 3. تبويب التفاعلات
    # ============================================================
    def build_interactions_tab(self):
        self.inter_lead = ft.Dropdown(label="العميل", expand=True)
        self.inter_type = ft.Dropdown(
            label="نوع التفاعل",
            options=[ft.dropdown.Option(s) for s in ["اتصال", "بريد إلكتروني", "اجتماع", "رسالة", "أخرى"]],
            value="اتصال", expand=True
        )
        self.inter_date = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"))
        self.inter_notes = ft.TextField(label="ملاحظات", multiline=True)

        # تعبئة القائمة
        leads = get_all_leads()
        self.inter_lead.options = [ft.dropdown.Option(key=str(l['id']), text=l['name']) for l in leads]

        def save_inter(e):
            try:
                lead_id = int(self.inter_lead.value)
            except (ValueError, TypeError):
                return
            
            add_interaction(lead_id, self.inter_type.value, self.inter_date.value, self.inter_notes.value)
            self.page.snack_bar = ft.SnackBar(ft.Text("تم التسجيل"), bgcolor=ACCENT_GREEN)
            self.page.snack_bar.open = True
            self.load_inter_table()
            self.page.update()

        form_content = ft.Column([
            ft.Row([self.inter_lead]),
            ft.Row([self.inter_type, self.inter_date]),
            self.inter_notes,
            ft.ElevatedButton("💾 حفظ", on_click=save_inter, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE)
        ])

        self.inter_table_container = ft.Container()
        self.load_inter_table()

        return ft.Column([
            ft.ExpansionTile(
                title=ft.Text("➕ تسجيل تفاعل", color=ACCENT_ORANGE),
                controls=[ft.Container(content=form_content, padding=10)],
            ),
            ft.Divider(color=GLASS_BORDER),
            self.inter_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def load_inter_table(self):
        interactions = get_interactions()
        if interactions:
            df = pd.DataFrame(interactions)
            self.inter_table_container.content = build_data_table(df)
        else:
            self.inter_table_container.content = ft.Text("لا توجد تفاعلات بعد", color=TEXT_SECONDARY)

    # ============================================================
    # 4. تبويب لوحة التحكم
    # ============================================================
    def build_dashboard_tab(self):
        summary = get_crm_summary()
        
        def kpi_card(icon, title, value, color):
            return ft.Container(
                content=ft.Column([
                    ft.Text(icon, size=30),
                    ft.Text(title, color=TEXT_SECONDARY, size=12),
                    ft.Text(str(value), color=color, size=24, weight=ft.FontWeight.BOLD)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
            )

        # بطاقات المؤشرات
        cards = ft.Row([
            kpi_card("👥", "إجمالي العملاء", summary.get('total_leads', 0), ACCENT_BLUE),
            kpi_card("🆕", "جديد", summary.get('new_leads', 0), ACCENT_GREEN),
            kpi_card("💼", "الفرص", summary.get('total_opportunities', 0), ACCENT_ORANGE),
            kpi_card("💰", "قيمة الأنابيب", f"{summary.get('pipeline_value', 0):,.0f}", ACCENT_PURPLE),
        ])

        # جدول خط الأنابيب
        pipeline = get_pipeline_summary()
        pipeline_container = ft.Container()
        if pipeline:
            df = pd.DataFrame(pipeline)
            pipeline_container.content = build_data_table(df)
        else:
            pipeline_container.content = ft.Text("لا توجد فرص بعد", color=TEXT_SECONDARY)

        return ft.Column([
            cards,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("خط أنابيب المبيعات", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            pipeline_container
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # ============================================================
    # 5. تبويب تحويل لعميل
    # ============================================================
    def build_convert_tab(self):
        leads = get_all_leads()
        unconverted = [l for l in leads if l['status'] != 'تحول لعميل']
        
        self.convert_dropdown = ft.Dropdown(
            label="اختر العميل للتحويل",
            expand=True
        )
        
        if unconverted:
            self.convert_dropdown.options = [
                ft.dropdown.Option(key=str(l['id']), text=f"{l['name']} ({l['company'] or 'لا شركة'})") 
                for l in unconverted
            ]
            self.convert_dropdown.value = str(unconverted[0]['id'])

        def do_convert(e):
            if not self.convert_dropdown.value:
                return
            lead_id = int(self.convert_dropdown.value)
            customer_id = convert_lead_to_customer(lead_id)
            if customer_id:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"تم التحويل بنجاح! رقم العميل: {customer_id}"), bgcolor=ACCENT_GREEN)
                self.page.snack_bar.open = True
                # تحديث القائمة
                self.convert_dropdown.options = [o for o in self.convert_dropdown.options if o.key != str(lead_id)]
                self.page.update()
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text("فشل التحويل"), bgcolor=ACCENT_RED)
                self.page.snack_bar.open = True
                self.page.update()

        if not unconverted:
            return ft.Container(content=ft.Text("جميع العملاء المحتملين تم تحويلهم بالفعل", color=TEXT_SECONDARY), padding=20)

        return ft.Column([
            ft.Text("تحويل عميل محتمل إلى عميل فعلي", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
            self.convert_dropdown,
            ft.ElevatedButton("🔄 تحويل إلى عميل فعلي", on_click=do_convert, bgcolor=ACCENT_PURPLE, color=ft.colors.WHITE)
        ], expand=True)
