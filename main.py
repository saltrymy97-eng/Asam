# main.py (الموجود في الجذر)
import os
import sys
import flet as ft

# التأكد من مسار المشروع
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# استيراد التطبيق الرئيسي من مجلد ui_flet
from ui_flet.main import main

if __name__ == "__main__":
    ft.app(target=main)
