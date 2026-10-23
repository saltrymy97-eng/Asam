# app_desktop.py — النسخة النهائية (v27.0) - Chrome Native App (ملف تعريف معزول)
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
import tempfile

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
    # البحث عن Google Chrome حصرياً
    # ═══════════════════════════════════════════════════════════
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    
    browser_exe = None
    for path in chrome_paths:
        if os.path.exists(path):
            browser_exe = path
            break

    # ═══════════════════════════════════════════════════════════
    # إنشاء ملف تعريف مؤقت ومعزول (لحل مشكلة اختيار المستخدم)
    # ═══════════════════════════════════════════════════════════
    if browser_exe:
        # إنشاء مجلد مؤقت لملف التعريف (في مجلد البيانات الخاص بالتطبيق)
        if getattr(sys, 'frozen', False):
            app_data_dir = os.path.dirname(sys.executable)
        else:
            app_data_dir = os.path.dirname(os.path.abspath(__file__))
            
        chrome_profile_dir = os.path.join(app_data_dir, "chrome_profile")
        os.makedirs(chrome_profile_dir, exist_ok=True)

        # تشغيل كروم باستخدام ملف التعريف المؤقت
        subprocess.Popen([
            browser_exe, 
            f"--app={url}", 
            "--start-maximized", 
            "--force-color-profile=srgb",
            f"--user-data-dir={chrome_profile_dir}",  # 🎯 استخدام ملف تعريف مؤقت ومعزول
            "--no-first-run",                        # منع شاشات الترحيب
            "--disable-features=Translate",          # منع شريط الترجمة
            "--disable-infobars"                     # إخفاء شرائط المعلومات
        ])
    else:
        # إذا لم يوجد Chrome، استخدم المتصفح الافتراضي
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
