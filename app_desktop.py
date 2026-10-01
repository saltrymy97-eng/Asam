# app_desktop.py — مشغل نظام حوكمة ERP كتطبيق سطح مكتب (v2.0)
# ✅ v2.0: إصلاح مشكلة التمرير على الشاشات الكبيرة
#         - maximized=True (نافذة مِلء الشاشة)
#         - min_size أصغر (800x600)
#         - text_select=True (تحسين WebView2)
#         - دعم خاص لـ WebView2 (Edge)
import os
import sys
import io
import time
import socket
import multiprocessing
import asyncio
import traceback


# ═══════════════════════════════════════════════════════════
# ✅ الحل الشامل لمشاكل Unicode على Windows
# يجب أن يكون قبل أي import آخر
# ═══════════════════════════════════════════════════════════
if sys.platform == 'win32':
    # 1) تغيير Console إلى UTF-8
    try:
        os.system("chcp 65001 > nul 2>&1")
    except Exception:
        pass

    # 2) إعداد متغيرات البيئة
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    # 3) إعادة توجيه stdout/stderr إلى UTF-8
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        # fallback: استبدال بـ TextIOWrapper
        try:
            if sys.stdout and hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer, encoding='utf-8', errors='replace',
                    line_buffering=True
                )
            if sys.stderr and hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer, encoding='utf-8', errors='replace',
                    line_buffering=True
                )
        except Exception:
            pass


import webview
from streamlit.web import cli as stcli


# ═══════════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════════
def find_free_port():
    """البحث عن منفذ شبكة فارغ"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]


def is_server_running(host, port):
    """التحقق من أن السيرفر استيقظ وأصبح جاهزاً"""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (socket.error, TimeoutError, OSError):
        return False


def get_base_path():
    """المسار الآمن للملفات المدمجة داخل الـ EXE"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path):
    """تحديد مسار الأيقونة أو الملفات الخارجية بدقة"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def run_streamlit(port, app_path):
    """تشغيل السيرفر في عملية (Process) منفصلة تماماً"""
    # ✅ إعادة تطبيق الحل الشامل في العملية الجديدة
    if sys.platform == 'win32':
        try:
            os.system("chcp 65001 > nul 2>&1")
        except Exception:
            pass
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"
        try:
            if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    sys.stdout = open(os.devnull, "w", encoding='utf-8')
    sys.stderr = open(os.devnull, "w", encoding='utf-8')

    try:
        # ✅ ضبط مجلد العمل بجانب EXE
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            os.chdir(exe_dir)
            os.makedirs(os.path.join(exe_dir, "data"), exist_ok=True)

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.set_event_loop(asyncio.new_event_loop())

        sys.argv = [
            "streamlit",
            "run",
            app_path,
            f"--server.port={port}",
            "--server.headless=true",
            "--server.allowRunOnSave=false",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false"
        ]
        stcli.main()

    except Exception as e:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        with open(os.path.join(exe_dir, "server_error_log.txt"), "w", encoding="utf-8") as f:
            f.write("خطأ في عملية Streamlit المستقلة:\n")
            f.write(str(e) + "\n")
            f.write(traceback.format_exc())
    except SystemExit:
        pass


# ═══════════════════════════════════════════════════════════
# ✅ الدالة الرئيسية — v2.0 (مُعدَّلة لإصلاح التمرير)
# ═══════════════════════════════════════════════════════════
def main():
    base_path = get_base_path()
    app_py_path = os.path.join(base_path, "app.py")

    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    # ✅ تشغيل Streamlit في عملية منفصلة
    p = multiprocessing.Process(
        target=run_streamlit,
        args=(port, app_py_path),
        daemon=True
    )
    p.start()

    # ✅ انتظار جاهزية السيرفر
    max_retries = 80
    retries = 0
    while not is_server_running(host, port) and retries < max_retries:
        time.sleep(0.5)
        retries += 1

    if retries >= max_retries:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        with open(os.path.join(exe_dir, "server_error_log.txt"),
                  "a", encoding="utf-8") as f:
            f.write(
                f"\nانتهى الوقت (Timeout): "
                f"السيرفر لم يستجب بعد {max_retries/2} ثانية."
            )

    window_title = "ERP Governance System - Asam"

    # ═══════════════════════════════════════════════════════════
    # ✅✅✅ الإصلاح الأساسي لمشكلة التمرير
    # ═══════════════════════════════════════════════════════════
    # - maximized=True       ← النافذة تفتح مِلء الشاشة (يحل التمرير)
    # - min_size أصغر        ← لإتاحة مساحة للتمرير
    # - text_select=True     ← يحسّن WebView2
    # - confirm_close=False  ← إغلاق سريع
    # ═══════════════════════════════════════════════════════════
    webview.create_window(
        title=window_title,
        url=url,
        width=1280,              # عرض ابتدائي (سيتم تجاهله مع maximized)
        height=800,              # ارتفاع ابتدائي (سيتم تجاهله)
        min_size=(800, 600),     # ✅ حجم أدنى أصغر
        resizable=True,          # ✅ قابل للتحجيم
        maximized=True,          # ✅✅✅ مِلء الشاشة تلقائياً
        fullscreen=False,        # ✅ ليس fullscreen (يسمح بالتمرير)
        confirm_close=False,     # ✅ إغلاق سريع
        text_select=True,        # ✅ تحسين التفاعل مع WebView2
        easy_drag=False,         # ✅ لا سحب بالخلفية
    )

    # ✅ بدء WebView2 مع إعدادات صريحة
    webview.start(
        private_mode=False,
        storage_path=None,
        debug=False,
        gui='edgechromium',  # ✅ استخدام WebView2 (Edge) صراحةً
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
