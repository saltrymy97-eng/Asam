# ui_flet/main.py
import flet as ft
import os
import sys

# ✅ إضافة مسار المشروع الرئيسي للتمكن من استيراد الخدمات وقاعدة البيانات
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from ui_flet.shared import *
import database

class MainApp(ft.Row):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        # مؤقتاً: نضع مستخدم افتراضي (سنربط شاشة الدخول لاحقاً)
        self.user = {"username": "admin", "full_name": "مدير النظام"}
        
        # منطقة عرض المحتوى (سيتم وضع الصفحات هنا)
        self.content_area = ft.Container(expand=True, padding=20)
        
        # بناء القائمة الجانبية
        self.sidebar = self.build_sidebar()
        
        # وضع القائمة والمحتوى في الصفحة
        self.controls = [self.sidebar, self.content_area]
        
        # عرض الصفحة الافتراضية
        self.load_page("لوحة المعلومات")

    def build_sidebar(self):
        """بناء القائمة الجانبية بنفس تصميم app.py"""
        
        def menu_section(title):
            return ft.Container(
                content=ft.Text(title, color=ACCENT_PURPLE, size=12, weight=ft.FontWeight.BOLD),
                margin=ft.margin.only(top=15, bottom=5, left=10, right=10),
                padding=ft.padding.all(8),
                bgcolor=ft.colors.with_opacity(0.03, ft.colors.WHITE),
                border_radius=12,
            )

        def menu_button(text, page_name):
            return ft.TextButton(
                content=ft.Text(text, size=14, color=ft.colors.WHITE),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=10,
                    alignment=ft.alignment.center_right,
                ),
                on_click=lambda e: self.load_page(page_name),
            )

        sidebar_column = ft.Column(
            [
                # الشعار
                ft.Container(
                    content=ft.Column([
                        ft.Text("🏢", size=40),
                        ft.Text("حوكمة ERP", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                        ft.Text("إدارة ذكية .. قرارات واثقة", size=12, color=ACCENT_PURPLE),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                ),
                ft.Divider(color=GLASS_BORDER),
                
                # المجموعات (مختصرة للبداية حتى لا نطيل الملف)
                menu_section("🏠 الرئيسية"),
                menu_button("📊 لوحة المعلومات", "لوحة المعلومات"),
                
                menu_section("💰 المحاسبة والمالية"),
                menu_button("🧾 حسابات", "الحسابات"),
                menu_button("🌳 شجرة الحسابات", "شجرة الحسابات"),
                
                menu_section("📦 العمليات"),
                menu_button("🛒 مبيعات", "المبيعات"),
                menu_button("📋 مشتريات", "المشتريات"),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Container(
            content=sidebar_column,
            width=250,
            bgcolor="#141428",
            padding=10,
            border=ft.border.only(right=ft.border.BorderSide(1, GLASS_BORDER)),
        )

    def load_page(self, page_name):
        """دالة التنقل بين الصفحات (مؤقتة)"""
        self.content_area.content = ft.Column([
            ft.Text(f"مرحباً بك في {page_name}", size=30, color=TEXT_PRIMARY),
            ft.Text("هذه الصفحة قيد الترحيل إلى Flet...", size=16, color=TEXT_SECONDARY)
        ])
        self.page.update()

def main(page: ft.Page):
    # إعدادات الصفحة الأساسية
    page.title = "حوكمة ERP - Hokama ERP"
    page.rtl = True # اتجاه من اليمين لليسار
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0A0A1E"
    page.padding = 0
    
    # إعداد الخط العربي (Cairo)
    page.fonts = {
        "Cairo": "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf"
    }
    page.theme = ft.Theme(font_family="Cairo")
    
    # تهيئة قاعدة البيانات (نفس ما يفعله app.py)
    database.init_db()
    database.create_default_admin()
    
    # تشغيل التطبيق
    app = MainApp(page)
    page.add(app)

if __name__ == "__main__":
    ft.app(target=main)
