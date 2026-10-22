# app_desktop.py — النسخة النهائية (v12.0) - اختبار كرت الشاشة الطبيعي
import os
import sys
import time
import socket
import multiprocessing
import asyncio
import traceback
import urllib.request

# إعداد UTF-8
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

# ═══════════════════════════════════════════════════════════
# 🎯 إعدادات كرت الشاشة الطبيعية (بناءً على نصيحة ChatGPT)
# ═══════════════════════════════════════════════════════════
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-gl=angle --use-angle=default"

# ═══════════════════════════════════════════════════════════
# Imports
# ═══════════════════════════════════════════════════════════
from streamlit.web import cli as stcli
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
# (تمت إزالة استيراد QWebEngineSettings لأننا سنستخدم الإعدادات الافتراضية)

def find_free_port():
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
    try:
        url = f"http://{host}:{port}/_stcore/health"
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False

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
            "--server.fileWatcherType=none", # يقلل استهلاك المعالج
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

def main():
    base_path = get_base_path()
    app_py_path = os.path.join(base_path, "app.py")
    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    p = multiprocessing.Process(target=run_streamlit, args=(port, app_py_path), daemon=True)
    p.start()

    max_retries = 120
    retries = 0
    server_ready = False
    while retries < max_retries:
        if is_streamlit_ready(host, port):
            server_ready = True
            break
        if not p.is_alive():
            break
        time.sleep(0.5)
        retries += 1

    if not server_ready:
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════
    # تشغيل النافذة (بإعدادات افتراضية نظيفة)
    # ═══════════════════════════════════════════════════════════
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("ERP Governance System - Asam")
    window.setGeometry(100, 100, 1280, 800)

    browser = QWebEngineView()
    # لا توجد إعدادات إضافية هنا.. اتركنا Qt و Chromium يعملان بطبيعتهما
    
    browser.setUrl(QUrl(url))
    window.setCentralWidget(browser)
    window.showMaximized()

    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
