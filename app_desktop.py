# app_desktop.py — النسخة النهائية الاحترافية (v8.0)
# v8.0: تعطيل تسريع كرت الشاشة (لحل الشاشة السوداء) + منفذ ديناميكي + فحص صحة

import os
import sys
import time
import socket
import multiprocessing
import asyncio
import traceback
import urllib.request

# ═══════════════════════════════════════════════════════════
# إعداد UTF-8
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
        pass

# ═══════════════════════════════════════════════════════════
# 🎯 السر هنا: تعطيل تسريع كرت الشاشة لمحرك Chromium
# يجب أن يكون هذا قبل استيراد PySide6
# ═══════════════════════════════════════════════════════════
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer --no-sandbox"

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

# ═══════════════════════════════════════════════════════════
# تشغيل Streamlit
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
                f.write("خطأ في Streamlit:\n" + str(e) + "\n" + traceback.format_exc())
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

    # 1. اختيار منفذ فارغ
    port = find_free_port()
    url = f"http://{host}:{port}"

    # 2. تشغيل الخادم في Process (لأن Streamlit لا يعمل في Thread)
    p = multiprocessing.Process(target=run_streamlit, args=(port, app_py_path), daemon=True)
    p.start()

    # 3. الانتظار الذكي (فحص الصحة)
    max_retries = 120 # 60 ثانية
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

    # 4. معالجة الفشل
    if not server_ready:
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            with open(os.path.join(exe_dir, "server_error_log.txt"), "a", encoding="utf-8") as f:
                f.write(f"\nفشل التشغيل: الخادم لم يستجب (Timeout).")
        except Exception:
            pass
        sys.exit(1)

    # 5. تشغيل نافذة PySide6
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("ERP Governance System - Asam")
    window.setGeometry(100, 100, 1280, 800)

    browser = QWebEngineView()
    
    # إعدادات إضافية لضمان الأمان وتجاوز الحظر
    settings = browser.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
    # تعطيل تسريع الرسم (لتجنب الشاشة السوداء نهائياً)
    settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)

    browser.setUrl(QUrl(url))
    window.setCentralWidget(browser)
    window.showMaximized()

    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
