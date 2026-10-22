# app_desktop.py — مشغل نظام حوكمة ERP كتطبيق سطح مكتب (v3.0)
# v3.0: الانتقال إلى PySide6 (محرك Chromium) + فحص الصحة + تفعيل أدوات المطور

import os
import sys
import io
import time
import socket
import multiprocessing
import asyncio
import traceback
import urllib.request

# ═══════════════════════════════════════════════════════════
# إعداد UTF-8 على Windows
# ═══════════════════════════════════════════════════════════
if sys.platform == 'win32':
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        try:
            if sys.stdout and hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
            if sys.stderr and hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
# Imports
# ═══════════════════════════════════════════════════════════
from streamlit.web import cli as stcli
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

# ═══════════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════════
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]

def is_streamlit_ready(host, port):
    """فحص صحة Streamlit بدلاً من فحص المنفذ فقط (يمنع الشاشة البيضاء)"""
    try:
        url = f"http://{host}:{port}/_stcore/health"
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ═══════════════════════════════════════════════════════════
# تشغيل Streamlit في عملية منفصلة
# ═══════════════════════════════════════════════════════════
def run_streamlit(port, app_path):
    if sys.platform == 'win32':
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"
        try:
            if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    try:
        sys.stdout = open(os.devnull, "w", encoding='utf-8')
        sys.stderr = open(os.devnull, "w", encoding='utf-8')
    except Exception:
        pass

    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            os.chdir(exe_dir)
            os.makedirs(os.path.join(exe_dir, "data"), exist_ok=True)

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.set_event_loop(asyncio.new_event_loop())

        sys.argv = [
            "streamlit", "run", app_path,
            f"--server.port={port}",
            "--server.headless=true",
            "--server.allowRunOnSave=false",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false"
        ]

        stcli.main()

    except Exception as e:
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            with open(os.path.join(exe_dir, "server_error_log.txt"), "w", encoding="utf-8") as f:
                f.write("خطأ في عملية Streamlit المستقلة:\n")
                f.write(str(e) + "\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
    except SystemExit:
        pass

# ═══════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════
def main():
    base_path = get_base_path()
    app_py_path = os.path.join(base_path, "app.py")
    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    p = multiprocessing.Process(
        target=run_streamlit,
        args=(port, app_py_path),
        daemon=True
    )
    p.start()

    # ═══════════════════════════════════════════════════════════
    # الانتظار الذكي (فحص الصحة + فحص العملية)
    # ═══════════════════════════════════════════════════════════
    max_retries = 120 # مهلة 60 ثانية
    retries = 0
    server_ready = False
    
    print("⏳ جاري انتظار الخادم...")
    while retries < max_retries:
        if is_streamlit_ready(host, port):
            server_ready = True
            break
        
        # إذا ماتت عملية الخادم فجأة (حدث خطأ داخلي)، نتوقف فوراً
        if not p.is_alive():
            print("❌ خطأ: توقفت عملية الخادم فجأة قبل أن تصبح جاهزة.")
            break
            
        time.sleep(0.5)
        retries += 1

    if not server_ready:
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            with open(os.path.join(exe_dir, "server_error_log.txt"), "a", encoding="utf-8") as f:
                f.write(f"\nفشل التشغيل: الخادم لم يستجب أو توقف (Timeout/Process died).")
        except Exception:
            pass
        sys.exit(1)

    print("✅ الخادم جاهز، جاري فتح النافذة...")

    # ═══════════════════════════════════════════════════════════
    # تشغيل نافذة PySide6
    # ═══════════════════════════════════════════════════════════
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("ERP Governance System - Asam")
    window.setGeometry(100, 100, 1280, 800)
    
    browser = QWebEngineView()
    
    # ✅ تفعيل أدوات المطور (F12 / Right-Click -> Inspect)
    settings = browser.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.DeveloperExtrasEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    
    browser.setUrl(QUrl(url))
    window.setCentralWidget(browser)
    
    # فتح النافذة بحجم الشاشة الكامل
    window.showMaximized()
    
    sys.exit(app.exec())

# ═══════════════════════════════════════════════════════════
# نقطة تشغيل البرنامج
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
