# ui_flet/pages/hr.py
import flet as ft
import pandas as pd
from datetime import date
from services.hr_service import (
    get_all_employees, add_employee, get_employees_for_select,
    record_attendance, get_attendance_history,
)
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

class HRPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        self.header = ft.Text("👥 الموارد البشرية", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة الموظفين والحضور والانصراف", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="👥 الموظفين", content=self.build_employees_tab()),
                ft.Tab(text="➕ إضافة موظف", content=self.build_add_tab()),
                ft.Tab(text="📅 الحضور والانصراف", content=self.build_attendance_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. قائمة الموظفين
    # ============================================================
    def build_employees_tab(self):
        self.employees_container = ft.Container()
        self.load_employees()
        return ft.Column([
            ft.Text("قائمة الموظفين", color=ACCENT_BLUE, size=18, weight=ft.FontWeight.BOLD),
            self.employees_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_employees(self):
        employees = get_all_employees()
        if employees:
            self.employees_container.content = temp_data_table(pd.DataFrame(employees))
        else:
            self.employees_container.content = ft.Text("لا يوجد موظفون بعد", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 2. إضافة موظف
    # ============================================================
    def build_add_tab(self):
        self.emp_name = ft.TextField(label="اسم الموظف", expand=True)
        self.emp_position = ft.TextField(label="المسمى الوظيفي", expand=True)
        self.emp_salary = ft.TextField(label="الراتب", value="0", keyboard_type=ft.KeyboardType.NUMBER, expand=True)
        self.emp_join_date = ft.TextField(label="تاريخ الالتحاق", value=date.today().strftime("%Y-%m-%d"), expand=True)

        def add_emp(e):
            if not self.emp_name.value:
                self.show_snackbar("الاسم مطلوب", ACCENT_RED); return
            try: salary = float(self.emp_salary.value or 0)
            except ValueError: salary = 0.0

            success, error = add_employee(
                self.emp_name.value, self.emp_position.value, salary,
                self.emp_join_date.value, "admin"
            )
            if success:
                self.show_snackbar(f"✅ تمت إضافة الموظف '{self.emp_name.value}'", ACCENT_GREEN)
                self.emp_name.value = ""; self.emp_position.value = ""; self.emp_salary.value = "0"
                self.load_employees()
                self.load_emp_dropdowns()
            else:
                self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)

        return ft.Column([
            ft.Text("إضافة موظف جديد", color=ACCENT_GREEN, size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.emp_name, self.emp_position]),
            ft.Row([self.emp_salary, self.emp_join_date]),
            ft.ElevatedButton("➕ إضافة", on_click=add_emp, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 3. الحضور والانصراف
    # ============================================================
    def build_attendance_tab(self):
        self.emp_dd = ft.Dropdown(label="اختر الموظف", expand=True)
        self.att_date = ft.TextField(label="التاريخ", value=date.today().strftime("%Y-%m-%d"), expand=True)
        self.att_status = ft.Dropdown(
            label="الحالة",
            options=[ft.dropdown.Option(s) for s in ["حاضر", "غائب", "إجازة", "مريض"]],
            value="حاضر", expand=True
        )
        self.attendance_container = ft.Container()

        self.load_emp_dropdowns()

        def record_att(e):
            if not self.emp_dd.value:
                self.show_snackbar("اختر الموظف", ACCENT_RED); return
            emp_id = int(self.emp_dd.value)
            emp_name = self.emp_dd.value.split(": ")[-1] if ": " in self.emp_dd.value else ""
            
            success, error = record_attendance(emp_id, emp_name, self.att_date.value, self.att_status.value, "admin")
            if success:
                self.show_snackbar("✅ تم تسجيل الحضور", ACCENT_GREEN)
                self.load_attendance()
            else:
                self.show_snackbar(f"❌ فشل: {error}", ACCENT_RED)

        self.load_attendance()

        return ft.Column([
            ft.Text("تسجيل الحضور اليومي", color=ACCENT_ORANGE, size=18, weight=ft.FontWeight.BOLD),
            self.emp_dd,
            ft.Row([self.att_date, self.att_status]),
            ft.ElevatedButton("✅ تسجيل الحضور", on_click=record_att, bgcolor=ACCENT_ORANGE, color=ft.colors.WHITE),
            ft.Divider(color=GLASS_BORDER),
            ft.Text("سجل الحضور", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            self.attendance_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def load_emp_dropdowns(self):
        employees = get_employees_for_select()
        self.emp_dd.options = [ft.dropdown.Option(key=str(e['id']), text=f"{e['id']}: {e['name']}") for e in employees]
        if employees and not self.emp_dd.value:
            self.emp_dd.value = str(employees[0]['id'])
        self.page.update()

    def load_attendance(self):
        attendance = get_attendance_history()
        if attendance:
            self.attendance_container.content = temp_data_table(pd.DataFrame(attendance))
        else:
            self.attendance_container.content = ft.Text("لا يوجد سجل حضور بعد", color=TEXT_SECONDARY)
        self.page.update()
