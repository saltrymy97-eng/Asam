# ui_flet/pages/auth.py
import flet as ft
from database import init_db
from services.auth_service import verify_user, change_password, logout_session

PR = "#7C3AED"
BL = "#2563EB"
T = "#F8FAFC"
S = "#94A3B8"

class AuthPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.show_password_change = False
        self._setup_page()
        init_db()
        self.build()

    def _setup_page(self):
        self.page.title = "حوكمة ERP - الدخول"
        self.page.rtl = True
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#020617"
        self.page.padding = 0
        self.page.fonts = {
            "Tajawal": "https://github.com/google/fonts/raw/main/ofl/tajawal/Tajawal-Regular.ttf",
        }
        self.page.theme = ft.Theme(font_family="Tajawal")

    def _get_client_ip(self):
        try: return self.page.client_ip or "محلي"
        except: return "محلي"

    def build(self):
        self.controls.clear()
        if self.show_password_change:
            self.controls.append(self._build_password_change_form())
        else:
            self.controls.append(self._build_login_form())
        self.page.update()

    def _build_orb(self, text="حوكمة", size=210, icon=None):
        inner = ft.Text(icon, size=70) if icon else ft.Text(text, size=50, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE)
        return ft.Container(
            content=ft.Stack([
                ft.Container(width=size, height=size, border_radius=size//2,
                             gradient=ft.RadialGradient(colors=[ft.colors.with_opacity(0.4, PR), ft.colors.TRANSPARENT], radius=1.0)),
                ft.Container(
                    content=inner, width=size, height=size, border_radius=size//2,
                    bgcolor=ft.colors.with_opacity(0.15, PR),
                    border=ft.border.all(2, ft.colors.with_opacity(0.6, PR)),
                    shadow=ft.BoxShadow(blur_radius=40, color=ft.colors.with_opacity(0.5, PR), spread_radius=10),
                    alignment=ft.alignment.center
                )
            ]), margin=ft.margin.only(bottom=30)
        )

    def _build_login_form(self):
        header = ft.Column([
            self._build_orb("حوكمة"),
            ft.Text("إدارة ذكية .. قرارات واثقة", size=18, color=S, weight=ft.FontWeight.BOLD),
            ft.Container(width=250, height=2, gradient=ft.LinearGradient(colors=[ft.colors.TRANSPARENT, PR, ft.colors.TRANSPARENT]), margin=ft.margin.only(top=15, bottom=30))
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.login_user = ft.TextField(label="👤 معرف المستخدم", hint_text="أدخل اسم المستخدم", border_radius=18, bgcolor="#030712")
        self.login_pass = ft.TextField(label="🔒 رمز المرور", hint_text="••••••••", password=True, can_reveal_password=True, border_radius=18, bgcolor="#030712")

        def do_login(e):
            if not self.login_user.value or not self.login_pass.value:
                self._show_error("يرجى إدخال اسم المستخدم وكلمة المرور"); return
            user = verify_user(self.login_user.value.strip(), self.login_pass.value, ip_address=self._get_client_ip())
            if user:
                # ✅ حفظ الجلسة والانتقال للتطبيق الرئيسي
                self.page.session.set("user", user)
                self.page.session.set("logged_in", True)
                self._show_success("✅ تم الدخول بنجاح")
                # إعادة تحميل main
                from ui_flet.main import MainApp
                self.page.controls.clear()
                self.page.add(MainApp(self.page, user))
                self.page.update()
            else:
                self._show_error("❌ فشلت المصادقة. يرجى مراجعة البيانات.")

        def show_change_pw(e):
            self.show_password_change = True
            self.build()

        form_card = ft.Container(
            content=ft.Column([
                self.login_user, self.login_pass,
                ft.ElevatedButton("🚀 مصادقة والدخول", on_click=do_login, bgcolor=PR, color=ft.colors.WHITE, width=float("inf"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20), padding=20)),
                ft.ElevatedButton("🔑 تغيير الرمز", on_click=show_change_pw, bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE), color=T, width=float("inf"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20), padding=20))
            ], spacing=15),
            bgcolor=ft.colors.with_opacity(0.75, "#0F172A"),
            border=ft.border.all(1, ft.colors.with_opacity(0.08, ft.colors.WHITE)),
            border_radius=40, padding=40,
            shadow=ft.BoxShadow(blur_radius=100, color=ft.colors.with_opacity(0.9, ft.colors.BLACK))
        )

        dev = ft.Container(content=ft.Text("حوكمة ERP • نظام محاسبي متكامل\nتطوير: سالم التريمي", color=ft.colors.with_opacity(0.5, ft.colors.WHITE), size=12, text_align=ft.TextAlign.CENTER), margin=ft.margin.only(top=60), alignment=ft.alignment.center)

        return ft.Container(
            content=ft.Column([header, ft.Container(content=form_card, width=500), dev], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO),
            alignment=ft.alignment.center, expand=True, padding=20
        )

    def _build_password_change_form(self):
        header = ft.Column([
            self._build_orb("", size=150, icon="🛡️"),
            ft.Text("تأمين الهوية الرقمية", size=24, color=T, weight=ft.FontWeight.BOLD),
            ft.Text("يرجى تحديث رمز الحماية الخاص بك للمتابعة بأمان", size=14, color=S),
            ft.Container(width=250, height=2, gradient=ft.LinearGradient(colors=[ft.colors.TRANSPARENT, PR, ft.colors.TRANSPARENT]), margin=ft.margin.only(top=15, bottom=30))
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.ch_user = ft.TextField(label="👤 اسم المستخدم", border_radius=18, bgcolor="#030712")
        self.ch_old = ft.TextField(label="🔓 الرمز الحالي", password=True, can_reveal_password=True, border_radius=18, bgcolor="#030712")
        self.ch_new = ft.TextField(label="✨ الرمز الجديد", password=True, can_reveal_password=True, border_radius=18, bgcolor="#030712")
        self.ch_confirm = ft.TextField(label="✅ تأكيد الرمز", password=True, can_reveal_password=True, border_radius=18, bgcolor="#030712")

        def do_change(e):
            if not self.ch_user.value or not self.ch_old.value or not self.ch_new.value:
                self._show_error("جميع الحقول مطلوبة"); return
            if self.ch_new.value != self.ch_confirm.value:
                self._show_error("عدم تطابق في تأكيد الرمز"); return
            if len(self.ch_new.value) < 4:
                self._show_error("رمز المرور ضعيف (4 خانات على الأقل)"); return
            success, msg = change_password(self.ch_user.value, self.ch_old.value, self.ch_new.value, changed_by=self.ch_user.value)
            if success:
                self._show_success(f"✨ {msg}")
                self.show_password_change = False
                self.build()
            else:
                self._show_error(f"❌ {msg}")

        form_card = ft.Container(
            content=ft.Column([
                self.ch_user, self.ch_old, self.ch_new, self.ch_confirm,
                ft.ElevatedButton("💾 حفظ البيانات", on_click=do_change, bgcolor=PR, color=ft.colors.WHITE, width=float("inf"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20), padding=20)),
                ft.ElevatedButton("↩️ تراجع", on_click=lambda e: (setattr(self, 'show_password_change', False), self.build()), bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE), color=T, width=float("inf"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20), padding=20))
            ], spacing=15),
            bgcolor=ft.colors.with_opacity(0.75, "#0F172A"),
            border=ft.border.all(1, ft.colors.with_opacity(0.08, ft.colors.WHITE)),
            border_radius=40, padding=40,
            shadow=ft.BoxShadow(blur_radius=100, color=ft.colors.with_opacity(0.9, ft.colors.BLACK))
        )

        return ft.Container(
            content=ft.Column([header, ft.Container(content=form_card, width=500)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO),
            alignment=ft.alignment.center, expand=True, padding=20
        )

    def _show_error(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=ft.colors.RED)
        self.page.snack_bar.open = True
        self.page.update()

    def _show_success(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=ft.colors.GREEN)
        self.page.snack_bar.open = True
        self.page.update()
