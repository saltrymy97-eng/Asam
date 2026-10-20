# app_desktop.py — مشغل نظام حوكمة ERP كتطبيق سطح مكتب (v3.0 - Edge App Mode)
# ✅ v3.0:
#    - التخلص التام من pywebview (يستخدم Edge App Mode بدلاً منه)
#    - إصلاح دورة حياة السيرفر (إزالة daemon=True)
#    - فحص جاهزية HTTP حقيقي بدلاً من TCP
#    - تسجيل الأخطاء في ملف app_error_log.txt
#    - الإبقاء على إعدادات UTF-8 ودعم multiprocessing

import os
import sys
import io
import time
import socket
import multiprocessing
import asyncio
import subprocess
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
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
                )
            if sys.stderr and hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
                )
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════════

def find_free_port():
    """البحث عن منفذ شبكة فارغ"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]

def wait_for_server_http(host, port, timeout=60):
    """التحقق من جاهزية Streamlit عبر HTTP حقيقي"""
    url = f"http://{host}:{port}/_stcore/health"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def get_base_path():
    """المسار الآمن للملفات المدمجة داخل الـ EXE"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def log_error(context, error=None):
    """تسجيل الأخطاء في ملف بجانب EXE"""
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.getcwd()
        with open(os.path.join(exe_dir, "app_error_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"\n--- [{time.strftime('%Y-%m-%d %H:%M:%S')}] {context} ---\n")
            if error:
                f.write(str(error) + "\n")
            f.write(traceback.format_exc())
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
# تشغيل Streamlit في عملية منفصلة
# ═══════════════════════════════════════════════════════════

def run_streamlit(port, app_path):
    """تشغيل Streamlit في عملية منفصلة"""
    if sys.platform == 'win32':
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"

    try:
        sys.stdout = open(os.devnull, "w", encoding='utf-8')
        sys.stderr = open(os.devnull, "w", encoding='utf-8')
    except Exception:
        pass

    try:
        from streamlit.web import cli as stcli

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
        log_error("run_streamlit", e)
        sys.exit(1)

# ═══════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════

def main():
    base_path = get_base_path()
    app_py_path = os.path.join(base_path, "app.py")

    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    # 1. تشغيل Streamlit (بدون daemon=True)
    p = multiprocessing.Process(target=run_streamlit, args=(port, app_py_path))
    p.start()

    # 2. انتظار جاهزية HTTP
    if not wait_for_server_http(host, port, timeout=60):
        log_error("Timeout: Streamlit did not respond within 60s")
        p.terminate()
        p.join()
        return

    # 3. تحديد مسار Edge
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    edge_exe = "msedge"  # fallback (يبحث في PATH)
    for path in edge_paths:
        if os.path.exists(path):
            edge_exe = path
            break

    # 4. تشغيل Edge App Mode
    try:
        browser_process = subprocess.Popen([
            edge_exe,
            f"--app={url}",
            "--window-size=1366,768",
            "--window-position=0,0"
        ])
        
        # الانتظار حتى يغلق المستخدم النافذة
        browser_process.wait()

    except FileNotFoundError:
        log_error("Edge not found - falling back to default browser")
        import webbrowser
        webbrowser.open(url)
    except Exception as e:
        log_error("Failed to launch Edge", e)

    finally:
        # 5. إغلاق Streamlit عند إغلاق النافذة
        if p.is_alive():
            p.terminate()
            p.join()

# ═══════════════════════════════════════════════════════════
# نقطة تشغيل البرنامج
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
