# app_desktop.py — النسخة النهائية (v38.0) - Firefox Portable Kiosk Mode
import os
import sys
import time
import socket
import multiprocessing
import asyncio
import traceback
import urllib.request
import subprocess
import webbrowser

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
# Imports
# ═══════════════════════════════════════════════════════════
from streamlit.web import cli as stcli

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
    """فحص صحة Streamlit للتأكد من أنه جاهز 100% قبل فتح المتصفح"""
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
            "--server.fileWatcherType=none",
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
    # البحث عن Firefox المدمج أولاً، ثم Firefox المثبت
    # ═══════════════════════════════════════════════════════════
    bundled_firefox = os.path.join(base_path, "firefox_portable", "firefox.exe")
    
    if os.path.exists(bundled_firefox):
        browser_exe = bundled_firefox
        print("Using bundled Firefox...")
    else:
        # البحث عن Firefox المثبت (خطة بديلة)
        firefox_paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
        ]
        browser_exe = next((path for path in firefox_paths if os.path.exists(path)), None)
        if browser_exe:
            print("Using installed Firefox...")

    # ═══════════════════════════════════════════════════════════
    # التشغيل في وضع Kiosk (ملء الشاشة بدون أدوات)
    # ═══════════════════════════════════════════════════════════
    if browser_exe:
        # إنشاء مجلد بيانات مؤقت لـ Firefox (لتجنب شاشات الترحيب)
        if getattr(sys, 'frozen', False):
            app_data_dir = os.path.dirname(sys.executable)
        else:
            app_data_dir = os.path.dirname(os.path.abspath(__file__))
            
        firefox_profile_dir = os.path.join(app_data_dir, "firefox_profile")
        os.makedirs(firefox_profile_dir, exist_ok=True)

        # تشغيل Firefox في وضع Kiosk مع ملف تعريف معزول
        subprocess.Popen([
            browser_exe,
            "-kiosk",                              # وضع ملء الشاشة (بدون أدوات)
            "-profile", firefox_profile_dir,       # ملف تعريف معزول (لتجنب شاشات الترحيب)
            "-no-remote",                          # منع استخدام نسخة Firefox مفتوحة
            url
        ])
    else:
        # إذا لم يوجد Firefox، استخدم المتصفح الافتراضي
        print("No Firefox found. Opening default browser...")
        webbrowser.open(url)

    # إبقاء العملية الرئيسية مفتوحة (حتى لا يتوقف الخادم)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
