# ui_flet/pages/attachment.py
import flet as ft
import pandas as pd
import os
import shutil
from services import attachment_service as att
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

CY = "#06B6D4"

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

class AttachmentPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        # FilePicker لرفع الملفات
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.page.overlay.append(self.file_picker)
        self.pending_file_path = None
        self.pending_file_name = None

        self.header = ft.Text("📎 إدارة المرفقات", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("أرشفة المستندات وربطها بالسجلات بكل سهولة", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📤 رفع مرفق جديد", content=self.build_upload_tab()),
                ft.Tab(text="📁 تصفح المرفقات", content=self.build_browse_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def kpi_box(self, icon, label, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=28),
                ft.Text(label, color=TEXT_SECONDARY, size=11),
                ft.Text(str(value), color=color, size=20, weight=ft.FontWeight.BOLD)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=15, expand=True
        )

    # ============================================================
    # 1. رفع مرفق
    # ============================================================
    def build_upload_tab(self):
        all_attachments = att.get_attachments()
        total_count = len(all_attachments)
        total_size_kb = sum(a['file_size'] for a in all_attachments) / 1024 if all_attachments else 0

        cards_row = ft.Row([
            self.kpi_box("📦", "عدد المرفقات", total_count, ACCENT_BLUE),
            self.kpi_box("💾", "الحجم الإجمالي", f"{total_size_kb:.1f} ك.ب", ACCENT_GREEN),
            self.kpi_box("📁", "الصيغ المدعومة", "6 صيغ", ACCENT_ORANGE),
        ], spacing=10)

        self.file_info_text = ft.Text("لم يتم اختيار ملف", color=TEXT_SECONDARY, size=12)
        
        # قائمة السجلات
        self.linked_table_dd = ft.Dropdown(
            label="نوع السجل المرتبط",
            options=[
                ft.dropdown.Option("invoices", text="🧾 فاتورة"),
                ft.dropdown.Option("journal_entries", text="📝 قيد"),
                ft.dropdown.Option("customers", text="👤 عميل"),
                ft.dropdown.Option("suppliers", text="🚚 مورد"),
                ft.dropdown.Option("employees", text="👔 موظف"),
                ft.dropdown.Option("products", text="📦 منتج"),
                ft.dropdown.Option("cost_centers", text="🏢 مركز تكلفة"),
            ], value="invoices", expand=True
        )
        self.linked_id_input = ft.TextField(label="رقم السجل", value="1", keyboard_type=ft.KeyboardType.NUMBER, width=150)

        def pick_file(e):
            self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["pdf", "jpg", "jpeg", "png", "xlsx", "docx", "zip"])

        def upload(e):
            if not self.pending_file_path:
                self.show_snackbar("⚠️ اختر ملفاً أولاً", ACCENT_ORANGE); return
            try:
                # محاكاة كائن يشبه الملف المرفوع في Streamlit
                class FileWrapper:
                    def __init__(self, path, name):
                        self.path = path
                        self.name = name
                    def getbuffer(self):
                        with open(self.path, "rb") as f:
                            return f.read()
                
                file_wrapper = FileWrapper(self.pending_file_path, self.pending_file_name)
                success, name = att.upload_attachment(
                    file_wrapper, self.linked_table_dd.value, int(self.linked_id_input.value), "admin"
                )
                self.show_snackbar(f"✅ تم رفع الملف '{name}' بنجاح", ACCENT_GREEN)
                self.pending_file_path = None
                self.pending_file_name = None
                self.file_info_text.value = "لم يتم اختيار ملف"
                self.file_info_text.color = TEXT_SECONDARY
                self.build_upload_tab()
            except Exception as ex:
                self.show_snackbar(f"❌ فشل الرفع: {ex}", ACCENT_RED)

        return ft.Column([
            cards_row,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📤 رفع مرفق جديد", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.ElevatedButton("📂 اختر ملفاً", on_click=pick_file, bgcolor=ACCENT_PURPLE, color=ft.colors.WHITE),
                self.file_info_text
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([self.linked_table_dd, self.linked_id_input]),
            ft.ElevatedButton("🚀 رفع المرفق الآن", on_click=upload, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, width=float("inf"))
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files:
            self.show_snackbar("لم يتم اختيار ملف", ACCENT_ORANGE); return
        f = e.files[0]
        self.pending_file_path = f.path
        self.pending_file_name = f.name
        self.file_info_text.value = f"📎 {f.name}"
        self.file_info_text.color = ACCENT_GREEN
        self.page.update()

    # ============================================================
    # 2. تصفح المرفقات
    # ============================================================
    def build_browse_tab(self):
        self.filter_dd = ft.Dropdown(
            label="تصفية حسب النوع",
            options=[ft.dropdown.Option("الكل"), ft.dropdown.Option("فواتير"), ft.dropdown.Option("قيود"), ft.dropdown.Option("عملاء"), ft.dropdown.Option("موردون"), ft.dropdown.Option("موظفون"), ft.dropdown.Option("منتجات"), ft.dropdown.Option("مراكز تكلفة")],
            value="الكل", on_change=lambda e: self.load_attachments()
        )
        self.attachments_container = ft.Container()
        self.action_container = ft.Container()
        
        self.load_attachments()

        return ft.Column([
            ft.Text("📁 المرفقات الحالية", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            self.filter_dd,
            self.attachments_container,
            self.action_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_attachments(self):
        table_map = {
            "فواتير": "invoices", "قيود": "journal_entries", "عملاء": "customers",
            "موردون": "suppliers", "موظفون": "employees", "منتجات": "products",
            "مراكز تكلفة": "cost_centers"
        }
        link_table = table_map.get(self.filter_dd.value) if self.filter_dd.value != "الكل" else None
        attachments = att.get_attachments(linked_table=link_table)
        
        if attachments:
            df = pd.DataFrame(attachments)
            df['نوع السجل'] = df['linked_table'].map({
                "invoices": "🧾 فاتورة", "journal_entries": "📝 قيد", "customers": "👤 عميل",
                "suppliers": "🚚 مورد", "employees": "👔 موظف", "products": "📦 منتج",
                "cost_centers": "🏢 مركز تكلفة"
            })
            df_display = df.rename(columns={"id": "رقم", "original_name": "اسم الملف", "file_size": "الحجم", "linked_id": "رقم السجل", "uploaded_at": "تاريخ الرفع"})
            cols = [c for c in ["رقم", "اسم الملف", "الحجم", "نوع السجل", "رقم السجل", "تاريخ الرفع"] if c in df_display.columns]
            self.attachments_container.content = temp_data_table(df_display[cols])

            attach_ids = [str(a['id']) for a in attachments]
            self.selected_attach_dd = ft.Dropdown(
                label="اختر مرفقاً للإجراءات",
                options=[ft.dropdown.Option(key=str(a['id']), text=a['original_name']) for a in attachments],
                value=attach_ids[0] if attach_ids else None,
                on_change=lambda e: self.load_attachment_actions(attachments)
            )
            self.load_attachment_actions(attachments)
            self.action_container.content = ft.Column([self.selected_attach_dd, self.actions_row])
        else:
            self.attachments_container.content = ft.Text("ℹ️ لا توجد مرفقات حالياً", color=TEXT_SECONDARY)
            self.action_container.content = None
        self.page.update()

    def load_attachment_actions(self, attachments):
        if not hasattr(self, 'selected_attach_dd') or not self.selected_attach_dd.value: return
        selected_id = int(self.selected_attach_dd.value)
        selected = att.get_attachment_by_id(selected_id)
        
        if selected and os.path.exists(selected['file_path']):
            def open_file(e):
                try: os.startfile(selected['file_path'])
                except Exception as ex: self.show_snackbar(f"لا يمكن فتح الملف: {ex}", ACCENT_RED)
            
            def delete_file(e):
                att.delete_attachment(selected_id)
                self.show_snackbar("✅ تم حذف المرفق", ACCENT_GREEN)
                self.load_attachments()
            
            self.actions_row = ft.Row([
                ft.ElevatedButton("📂 فتح الملف", on_click=open_file, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE, expand=True),
                ft.ElevatedButton("🗑️ حذف المرفق", on_click=delete_file, bgcolor=ACCENT_RED, color=ft.colors.WHITE, expand=True)
            ], spacing=10)
        else:
            self.actions_row = ft.Text("⚠️ الملف غير موجود على القرص", color=ACCENT_ORANGE)
        self.page.update()
