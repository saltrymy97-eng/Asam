# ui_flet/pages/backup.py
import flet as ft
import pandas as pd
import os
import zipfile
from services.backup_service import (
    create_backup, get_backup_list, restore_backup, get_backup_stats,
    delete_old_backups, start_scheduler, stop_scheduler,
    get_all_tables, BACKUP_DIR,
)
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

GOLD = "#D4AF37"

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

class BackupPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("💾 مركز النسخ الاحتياطي", size=30, color=GOLD, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("حماية مؤسسية متكاملة مع تشفير وجدولة وتتبع كامل", color=TEXT_SECONDARY, size=14)

        # FilePicker للرفع
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.page.overlay.append(self.file_picker)
        
        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📋 السجل والتحكم", content=self.build_main_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def kpi_card(self, title, value, icon, color, sub=""):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=24),
                ft.Text(title, color=TEXT_SECONDARY, size=11),
                ft.Text(str(value), color=color, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(sub, color=TEXT_SECONDARY, size=9)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=ft.colors.with_opacity(0.7, ft.colors.BLACK), border=ft.border.all(1, GOLD), border_radius=16, padding=12, expand=True
        )

    def build_main_tab(self):
        stats = get_backup_stats()
        
        # تنبيه
        alert_controls = []
        if stats.get('alert'):
            alert_controls.append(ft.Container(
                content=ft.Text(f"⚠️ {stats.get('alert_msg')}", color=ACCENT_RED),
                bgcolor=ft.colors.with_opacity(0.1, ACCENT_RED), padding=10, border_radius=8
            ))

        # بطاقات
        cards_row = ft.Row([
            self.kpi_card("إجمالي النسخ", stats['total'], "📋", ACCENT_BLUE),
            self.kpi_card("آخر نسخة", stats['latest_time'], "🕐", ACCENT_GREEN),
            self.kpi_card("حجم آخر نسخة", f"{stats['latest_size']:.1f} KB", "📦", ACCENT_ORANGE),
            self.kpi_card("آخر مستخدم", stats.get('latest_user', 'غير معروف'), "👤", ACCENT_PURPLE),
        ], spacing=10)

        # نموذج الإنشاء
        self.backup_user = ft.TextField(label="اسم المستخدم", value="مدير النظام", expand=True)
        self.backup_type = ft.Dropdown(label="نوع النسخة", options=[ft.dropdown.Option("يدوي"), ft.dropdown.Option("تلقائي"), ft.dropdown.Option("قبل تحديث")], value="يدوي", expand=True)
        self.encrypt_cb = ft.Checkbox(label="🔐 تشفير النسخة (AES-256)", value=False)
        self.compress_cb = ft.Checkbox(label="📦 ضغط النسخة (ZIP)", value=True)
        self.notes_input = ft.TextField(label="ملاحظات", multiline=True)

        all_tables = get_all_tables()
        self.tables_dd = ft.Dropdown(
            label="اختر جداول محددة (اتركه فارغاً لنسخ الكل)",
            options=[ft.dropdown.Option(t) for t in all_tables],
            multi_select=True, expand=True
        )

        def do_backup(e):
            try:
                filename, size = create_backup(
                    user=self.backup_user.value, backup_type=self.backup_type.value,
                    tables=list(self.tables_dd.value) if self.tables_dd.value else None,
                    encrypt=self.encrypt_cb.value, compress=self.compress_cb.value,
                    notes=self.notes_input.value
                )
                self.show_snackbar(f"✅ تم إنشاء النسخة: {filename} ({size:.1f} KB)", ACCENT_GREEN)
                self.load_backups_list()
            except Exception as ex:
                self.show_snackbar(f"❌ فشل: {ex}", ACCENT_RED)

        create_form = ft.Container(
            content=ft.Column([
                ft.Text("✨ إنشاء نسخة احتياطية جديدة", color=GOLD, weight=ft.FontWeight.BOLD, size=16),
                ft.Row([self.backup_user, self.backup_type]),
                ft.Row([self.encrypt_cb, self.compress_cb]),
                self.tables_dd, self.notes_input,
                ft.ElevatedButton("🚀 إنشاء النسخة الآن", on_click=do_backup, bgcolor=GOLD, color=ft.colors.BLACK, width=float("inf"))
            ]), bgcolor=GLASS_BG, border=ft.border.all(1, GOLD), border_radius=16, padding=15
        )

        # أدوات النظام
        def start_sched(e):
            start_scheduler()
            self.show_snackbar("✅ تم تشغيل المجدول التلقائي", ACCENT_GREEN)
        def stop_sched(e):
            stop_scheduler()
            self.show_snackbar("⏹️ تم إيقاف المجدول", ACCENT_ORANGE)
        def del_old(e):
            delete_old_backups()
            self.show_snackbar("✅ تم حذف النسخ القديمة", ACCENT_GREEN)
            self.load_backups_list()

        tools_row = ft.Row([
            ft.ElevatedButton("⏰ تشغيل النسخ التلقائي", on_click=start_sched, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, expand=True),
            ft.ElevatedButton("⏹️ إيقاف النسخ التلقائي", on_click=stop_sched, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE, expand=True),
            ft.ElevatedButton("🗑️ حذف النسخ القديمة", on_click=del_old, bgcolor=ACCENT_RED, color=ft.colors.WHITE, expand=True),
        ], spacing=10)

        # سجل النسخ
        self.backups_table_container = ft.Container()
        self.restore_dd = ft.Dropdown(label="اختر نسخة للاستعادة", expand=True)
        self.download_dd = ft.Dropdown(label="اختر نسخة للتحميل", expand=True)
        self.upload_status = ft.Text("", color=TEXT_SECONDARY)
        
        self.load_backups_list()

        def do_restore(e):
            if not self.restore_dd.value: return
            success, msg = restore_backup(self.restore_dd.value)
            if success: self.show_snackbar(msg, ACCENT_GREEN); self.load_backups_list()
            else: self.show_snackbar(msg, ACCENT_RED)

        def do_download(e):
            if not self.download_dd.value: return
            filepath = os.path.join(BACKUP_DIR, self.download_dd.value)
            if os.path.exists(filepath):
                self.show_snackbar(f"📂 الملف في: {filepath}", ACCENT_BLUE)
            else:
                self.show_snackbar("الملف غير موجود", ACCENT_RED)

        restore_section = ft.Container(
            content=ft.Column([
                ft.Text("🔄 استعادة نسخة احتياطية", color=ACCENT_RED, weight=ft.FontWeight.BOLD),
                self.restore_dd,
                ft.ElevatedButton("⚠️ استعادة هذه النسخة", on_click=do_restore, bgcolor=ACCENT_RED, color=ft.colors.WHITE)
            ]), bgcolor=ft.colors.with_opacity(0.05, ACCENT_RED), padding=15, border_radius=12
        )

        download_section = ft.Container(
            content=ft.Column([
                ft.Text("📥 تحميل نسخة", color=ACCENT_BLUE, weight=ft.FontWeight.BOLD),
                self.download_dd,
                ft.ElevatedButton("📥 عرض مسار التحميل", on_click=do_download, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
            ]), bgcolor=ft.colors.with_opacity(0.05, ACCENT_BLUE), padding=15, border_radius=12
        )

        upload_section = ft.Container(
            content=ft.Column([
                ft.Text("📤 استيراد نسخة احتياطية", color=ACCENT_ORANGE, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton("📂 اختر ملف (.db, .zip, .enc)", on_click=lambda e: self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["db", "zip", "enc"]), bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
                self.upload_status
            ]), bgcolor=ft.colors.with_opacity(0.05, ACCENT_ORANGE), padding=15, border_radius=12
        )

        return ft.Column([
            *alert_controls, cards_row, ft.Divider(color=GLASS_BORDER),
            create_form, ft.Divider(color=GLASS_BORDER),
            tools_row, ft.Divider(color=GLASS_BORDER),
            ft.Text("📋 سجل النسخ الاحتياطية", color=GOLD, size=18, weight=ft.FontWeight.BOLD),
            self.backups_table_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Row([restore_section, download_section], spacing=15),
            upload_section
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_backups_list(self):
        backups = get_backup_list()
        if backups:
            df = pd.DataFrame(backups)
            df_display = df.rename(columns={"id": "رقم", "filename": "اسم الملف", "size_kb": "الحجم (KB)", "created_at": "تاريخ الإنشاء", "type": "النوع", "user": "المستخدم", "tables_count": "عدد الجداول", "notes": "ملاحظات"})
            cols = [c for c in ["رقم", "اسم الملف", "تاريخ الإنشاء", "النوع", "المستخدم", "الحجم (KB)", "عدد الجداول", "ملاحظات"] if c in df_display.columns]
            self.backups_table_container.content = temp_data_table(df_display[cols])
            
            filenames = [b['filename'] for b in backups]
            self.restore_dd.options = [ft.dropdown.Option(f) for f in filenames]
            self.download_dd.options = [ft.dropdown.Option(f) for f in filenames]
            if filenames:
                self.restore_dd.value = filenames[0]; self.download_dd.value = filenames[0]
        else:
            self.backups_table_container.content = ft.Text("ℹ️ لا توجد نسخ احتياطية بعد", color=TEXT_SECONDARY)
        self.page.update()

    def on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files: return
        file = e.files[0]
        save_path = os.path.join(BACKUP_DIR, file.name)
        
        # في Flet نحتاج لقراءة محتوى الملف — يمكن استخدام file.path إذا كان سطح مكتب
        try:
            if file.path:
                import shutil
                shutil.copy(file.path, save_path)
                self.upload_status.value = f"✅ تم رفع الملف: {file.name}"
            else:
                self.upload_status.value = "⚠️ تعذر الوصول للملف"
                self.page.update(); return
        except Exception as ex:
            self.upload_status.value = f"❌ فشل الرفع: {ex}"
            self.page.update(); return

        # منطق الاستعادة الذكي
        file_to_restore = None
        if file.name.endswith('.db'):
            file_to_restore = file.name
        elif file.name.endswith('.zip'):
            try:
                with zipfile.ZipFile(save_path, 'r') as zf:
                    db_files = [f for f in zf.namelist() if f.endswith('.db')]
                    if db_files:
                        zf.extract(db_files[0], BACKUP_DIR)
                        file_to_restore = db_files[0]
                        self.upload_status.value = f"✅ تم استخراج: {file_to_restore}"
            except Exception as ex:
                self.upload_status.value = f"❌ فشل الاستخراج: {ex}"
        elif file.name.endswith('.enc'):
            file_to_restore = file.name

        if file_to_restore:
            def do_restore(e):
                success, msg = restore_backup(file_to_restore)
                if success: self.show_snackbar(msg, ACCENT_GREEN)
                else: self.show_snackbar(msg, ACCENT_RED)
            # إضافة زر استعادة
            self.upload_status.value += " — جاهز للاستعادة"
        self.page.update()
