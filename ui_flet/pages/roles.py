# ui_flet/pages/roles.py
import flet as ft
import pandas as pd
from services.roles_service import (
    create_roles_tables, get_all_roles, get_role_permissions,
    get_all_users_with_roles, assign_role_to_user
)
from services.auth_service import create_user, change_password
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

def temp_data_table(df: pd.DataFrame) -> ft.Control:
    """جدول مؤقت سيتم استبداله لاحقاً"""
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

class RolesPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        try:
            create_roles_tables()
        except Exception as e:
            print(f"Roles table error: {e}")

        self.header = ft.Text("🛡️ الصلاحيات والأدوار", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة الأدوار والمستخدمين والصلاحيات", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="🔑 الأدوار والصلاحيات", content=self.build_roles_tab()),
                ft.Tab(text="👥 المستخدمين", content=self.build_users_tab()),
                ft.Tab(text="⚙️ تعيين دور", content=self.build_assign_tab()),
                ft.Tab(text="➕ إضافة مستخدم", content=self.build_add_user_tab()),
                ft.Tab(text="🔒 تغيير كلمة المرور", content=self.build_password_tab()),
            ],
            expand=True,
        )

        self.controls = [
            ft.Column([self.header, self.subtitle], spacing=5),
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    def _current_username(self):
        return "admin" # مؤقتاً

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    # ============================================================
    # 1. الأدوار والصلاحيات
    # ============================================================
    def build_roles_tab(self):
        roles = get_all_roles()
        controls = [ft.Text("الأدوار والصلاحيات", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD)]
        
        if roles:
            for role in roles:
                perms = get_role_permissions(role["id"])
                perm_controls = []
                
                if perms:
                    for p in perms:
                        def chk(val): return "✅" if val else "❌"
                        text = f"**{p['module']}**: عرض {chk(p['can_view'])} | إضافة {chk(p['can_add'])} | تعديل {chk(p['can_edit'])} | حذف {chk(p['can_delete'])} | موافقة {chk(p['can_approve'])}"
                        perm_controls.append(ft.Text(text, color=TEXT_SECONDARY))
                else:
                    perm_controls.append(ft.Text("لا توجد صلاحيات", color=TEXT_SECONDARY))

                controls.append(
                    ft.ExpansionTile(
                        title=ft.Text(f"🔑 {role['name']}", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        controls=[ft.Container(content=ft.Column(perm_controls), padding=10)]
                    )
                )
        else:
            controls.append(ft.Text("لا توجد أدوار", color=TEXT_SECONDARY))

        return ft.Column(controls, scroll=ft.ScrollMode.AUTO, expand=True)

    # ============================================================
    # 2. المستخدمين
    # ============================================================
    def build_users_tab(self):
        self.users_table_container = ft.Container()
        self.load_users_table()
        
        return ft.Column([
            ft.Text("المستخدمين وأدوارهم", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD),
            self.users_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def load_users_table(self):
        users = get_all_users_with_roles()
        if users:
            df = pd.DataFrame(users)
            df = df.rename(columns={"username": "المستخدم", "full_name": "الاسم", "role_name": "الدور الحالي"})
            self.users_table_container.content = temp_data_table(df[["المستخدم", "الاسم", "الدور الحالي"]])
        else:
            self.users_table_container.content = ft.Text("لا يوجد مستخدمون", color=TEXT_SECONDARY)
        self.page.update()

    # ============================================================
    # 3. تعيين دور
    # ============================================================
    def build_assign_tab(self):
        users = get_all_users_with_roles()
        roles = get_all_roles()

        if not users or not roles:
            return ft.Text("لا يوجد مستخدمون أو أدوار كافية", color=TEXT_SECONDARY)

        self.assign_user_dd = ft.Dropdown(
            label="اختر المستخدم",
            options=[ft.dropdown.Option(key=str(u['id']), text=u['username']) for u in users],
            value=str(users[0]['id']),
            expand=True
        )
        self.assign_role_dd = ft.Dropdown(
            label="اختر الدور",
            options=[ft.dropdown.Option(key=str(r['id']), text=r['name']) for r in roles],
            value=str(roles[0]['id']),
            expand=True
        )

        def do_assign(e):
            user_id = int(self.assign_user_dd.value)
            role_id = int(self.assign_role_dd.value)
            assign_role_to_user(user_id, role_id)
            self.show_snackbar("تم تعيين الدور بنجاح", ACCENT_GREEN)
            self.load_users_table()

        return ft.Column([
            ft.Text("تعيين دور لمستخدم", color=ACCENT_ORANGE, size=20, weight=ft.FontWeight.BOLD),
            self.assign_user_dd,
            self.assign_role_dd,
            ft.ElevatedButton("💾 تعيين الدور", on_click=do_assign, bgcolor=ACCENT_BLUE, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 4. إضافة مستخدم
    # ============================================================
    def build_add_user_tab(self):
        roles = get_all_roles()
        if not roles:
            return ft.Text("يجب إنشاء الأدوار أولاً من تبويب الأدوار والصلاحيات", color=ACCENT_ORANGE)

        self.new_username = ft.TextField(label="اسم المستخدم", expand=True)
        self.new_password = ft.TextField(label="كلمة المرور", password=True, can_reveal_password=True, expand=True)
        self.new_fullname = ft.TextField(label="الاسم الكامل", expand=True)
        self.new_role_dd = ft.Dropdown(
            label="الدور",
            options=[ft.dropdown.Option(key=str(r['id']), text=r['name']) for r in roles],
            value=str(roles[0]['id']),
            expand=True
        )

        def do_add(e):
            if not self.new_username.value or not self.new_password.value:
                self.show_snackbar("اسم المستخدم وكلمة المرور مطلوبان", ACCENT_RED)
                return
            
            role_id = int(self.new_role_dd.value)
            success, message = create_user(
                self.new_username.value, self.new_password.value, 
                self.new_fullname.value, role_id
            )
            if success:
                self.show_snackbar(message, ACCENT_GREEN)
                self.new_username.value = ""
                self.new_password.value = ""
                self.new_fullname.value = ""
                self.load_users_table()
            else:
                self.show_snackbar(message, ACCENT_RED)

        return ft.Column([
            ft.Text("➕ إضافة مستخدم جديد", color=ACCENT_PURPLE, size=20, weight=ft.FontWeight.BOLD),
            self.new_username,
            self.new_password,
            self.new_fullname,
            self.new_role_dd,
            ft.ElevatedButton("💾 إنشاء المستخدم", on_click=do_add, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    # ============================================================
    # 5. تغيير كلمة المرور
    # ============================================================
    def build_password_tab(self):
        current_user = self._current_username()
        
        self.old_pw = ft.TextField(label="كلمة المرور الحالية", password=True, can_reveal_password=True, expand=True)
        self.new_pw = ft.TextField(label="كلمة المرور الجديدة", password=True, can_reveal_password=True, expand=True)
        self.confirm_pw = ft.TextField(label="تأكيد كلمة المرور الجديدة", password=True, can_reveal_password=True, expand=True)

        def do_change(e):
            if not self.old_pw.value or not self.new_pw.value or not self.confirm_pw.value:
                self.show_snackbar("جميع الحقول مطلوبة", ACCENT_RED)
                return
            if self.new_pw.value != self.confirm_pw.value:
                self.show_snackbar("كلمة المرور الجديدة وتأكيدها غير متطابقين", ACCENT_RED)
                return
            if len(self.new_pw.value) < 6:
                self.show_snackbar("يجب أن تكون كلمة المرور 6 أحرف على الأقل", ACCENT_RED)
                return

            success, message = change_password(current_user, self.old_pw.value, self.new_pw.value)
            if success:
                self.show_snackbar(message, ACCENT_GREEN)
                self.old_pw.value = ""
                self.new_pw.value = ""
                self.confirm_pw.value = ""
            else:
                self.show_snackbar(message, ACCENT_RED)

        return ft.Column([
            ft.Text("🔒 تغيير كلمة المرور", color=ACCENT_RED, size=20, weight=ft.FontWeight.BOLD),
            ft.Text(f"المستخدم الحالي: {current_user}", color=TEXT_SECONDARY),
            self.old_pw,
            self.new_pw,
            self.confirm_pw,
            ft.ElevatedButton("🔒 تغيير كلمة المرور", on_click=do_change, bgcolor=ACCENT_RED, color=ft.colors.WHITE)
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)
