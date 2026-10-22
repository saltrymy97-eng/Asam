# app_desktop.py — النسخة الاحترافية (v4.1)
# v4.1: منفذ ديناميكي (يختار منفذاً فارغاً ويمرره للخادم والنافذة معاً)

import os
import sys
import time
import socket
import multiprocessing
import asyncio
import traceback
import urllib.request
import threading

# إعداد UTF-8
if sys.platform == 'win32':
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

from streamlit.web import cli as stcli
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

# ═══════════════════════════════════════════════════════════
# دالة البحث عن منفذ فارغ
# ═══════════════════════════════════════════════════════════
def find_free_port():
    """يبحث عن منفذ فارغ ويعيده"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def is_streamlit_ready(host, port):
    """فحص جاهزية Streamlit"""
    try:
        url = f"http://{host}:{port}/_stcore/health"
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════
# تشغيل Streamlit في Thread
# ═══════════════════════════════════════════════════════════
def run_streamlit(port, app_path):
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
                f.write("خطأ:\n" + str(e) + "\n" + traceback.format_exc())
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

    # 1. البحث عن منفذ فارغ (مرة واحدة)
    port = find_free_port()
    url = f"http://{host}:{port}"
    
    print(f"🔍 تم اختيار المنفذ الفارغ: {port}")

    # 2. تشغيل الخادم على المنفذ المحدد
    server_thread = threading.Thread(target=run_streamlit, args=(port, app_py_path), daemon=True)
    server_thread.start()

    # 3. الانتظار حتى يصبح الخادم جاهزاً (فحص الصحة)
    max_retries = 120
    retries = 0
    server_ready = False
    
    print("⏳ جاري انتظار الخادم...")
    while retries < max_retries:
        if is_streamlit_ready(host, port):
            server_ready = True
            break
        time.sleep(0.5)
        retries += 1

    if not server_ready:
        print("❌ فشل تشغيل الخادم.")
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            with open(os.path.join(exe_dir, "server_error_log.txt"), "a", encoding="utf-8") as f:
                f.write(f"\nفشل التشغيل: الخادم لم يستجب (Timeout).")
        except Exception:
            pass
        sys.exit(1)

    print(f"✅ الخادم جاهز على المنفذ {port}، جاري فتح النافذة...")

    # 4. تشغيل نافذة PySide6 على نفس المنفذ (نمرر نفس المتغير port)
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("ERP Governance System - Asam")
    window.setGeometry(100, 100, 1280, 800)
    
    browser = QWebEngineView()
    settings = browser.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    
    # ✅ الرابط هنا يحتوي على نفس المنفذ الذي اخترناه للخادم
    browser.setUrl(QUrl(url))
    window.setCentralWidget(browser)
    window.showMaximized()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
