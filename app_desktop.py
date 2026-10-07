# app_desktop.py — مشغل نظام حوكمة ERP كتطبيق سطح مكتب (v2.1)
# v2.1:
# - إزالة استدعاءات chcp التي قد تسبب ظهور نوافذ Console سوداء أثناء التشغيل
# - الإبقاء على إعدادات UTF-8 عبر متغيرات البيئة
# - الحفاظ على multiprocessing + Streamlit + WebView2 كما هي
# - لا تغيير في منطق النظام أو قاعدة البيانات

import os
import sys
import io
import time
import socket
import multiprocessing
import asyncio
import traceback


# ═══════════════════════════════════════════════════════════
# إعداد UTF-8 على Windows
# ملاحظة:
# لا نستخدم os.system("chcp ...") حتى لا تظهر نوافذ Console
# أثناء تشغيل التطبيق.
# ═══════════════════════════════════════════════════════════

if sys.platform == 'win32':
    # إعداد متغيرات البيئة لدعم UTF-8
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    # إعادة ضبط stdout/stderr إن كانت متاحة
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(
                encoding='utf-8',
                errors='replace'
            )

        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(
                encoding='utf-8',
                errors='replace'
            )

    except Exception:
        # fallback آمن
        try:
            if sys.stdout and hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )

            if sys.stderr and hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )

        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# Imports
# ═══════════════════════════════════════════════════════════

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
    """التحقق من أن السيرفر أصبح جاهزاً"""
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
    """تحديد مسار الملفات الخارجية بدقة"""

    try:
        base_path = sys._MEIPASS

    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# ═══════════════════════════════════════════════════════════
# تشغيل Streamlit في عملية منفصلة
# ═══════════════════════════════════════════════════════════

def run_streamlit(port, app_path):
    """تشغيل Streamlit في عملية منفصلة تماماً"""

    # -------------------------------------------------------
    # إعداد UTF-8 للعملية الجديدة
    # لا نستخدم chcp هنا حتى لا تظهر نافذة Console
    # -------------------------------------------------------

    if sys.platform == 'win32':

        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"

        try:
            if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(
                    encoding='utf-8',
                    errors='replace'
                )

            if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(
                    encoding='utf-8',
                    errors='replace'
                )

        except Exception:
            pass

    # -------------------------------------------------------
    # منع ظهور مخرجات Streamlit في Console
    # -------------------------------------------------------

    try:
        sys.stdout = open(
            os.devnull,
            "w",
            encoding='utf-8'
        )

        sys.stderr = open(
            os.devnull,
            "w",
            encoding='utf-8'
        )

    except Exception:
        pass

    try:

        # ---------------------------------------------------
        # ضبط مجلد العمل بجانب EXE
        # ---------------------------------------------------

        if getattr(sys, 'frozen', False):

            exe_dir = os.path.dirname(sys.executable)

            os.chdir(exe_dir)

            os.makedirs(
                os.path.join(exe_dir, "data"),
                exist_ok=True
            )

        # ---------------------------------------------------
        # إعداد Event Loop على Windows
        # ---------------------------------------------------

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        asyncio.set_event_loop(
            asyncio.new_event_loop()
        )

        # ---------------------------------------------------
        # إعداد Streamlit
        # ---------------------------------------------------

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

        # ---------------------------------------------------
        # تشغيل Streamlit
        # ---------------------------------------------------

        stcli.main()

    except Exception as e:

        # ---------------------------------------------------
        # تسجيل الخطأ في ملف بجانب EXE
        # ---------------------------------------------------

        try:

            exe_dir = os.path.dirname(
                os.path.abspath(sys.executable)
            )

            with open(
                os.path.join(
                    exe_dir,
                    "server_error_log.txt"
                ),
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    "خطأ في عملية Streamlit المستقلة:\n"
                )

                f.write(
                    str(e) + "\n"
                )

                f.write(
                    traceback.format_exc()
                )

        except Exception:
            pass

    except SystemExit:
        pass


# ═══════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════

def main():

    # -------------------------------------------------------
    # تحديد مسار التطبيق
    # -------------------------------------------------------

    base_path = get_base_path()

    app_py_path = os.path.join(
        base_path,
        "app.py"
    )

    # -------------------------------------------------------
    # إعداد السيرفر المحلي
    # -------------------------------------------------------

    host = "127.0.0.1"

    port = find_free_port()

    url = f"http://{host}:{port}"

    # -------------------------------------------------------
    # تشغيل Streamlit في عملية منفصلة
    # -------------------------------------------------------

    p = multiprocessing.Process(
        target=run_streamlit,
        args=(
            port,
            app_py_path
        ),
        daemon=True
    )

    p.start()

    # -------------------------------------------------------
    # انتظار جاهزية Streamlit
    # -------------------------------------------------------

    max_retries = 80

    retries = 0

    while (
        not is_server_running(host, port)
        and retries < max_retries
    ):

        time.sleep(0.5)

        retries += 1

    # -------------------------------------------------------
    # إذا لم يستجب السيرفر
    # -------------------------------------------------------

    if retries >= max_retries:

        try:

            exe_dir = os.path.dirname(
                os.path.abspath(sys.executable)
            )

            with open(
                os.path.join(
                    exe_dir,
                    "server_error_log.txt"
                ),
                "a",
                encoding="utf-8"
            ) as f:

                f.write(
                    f"\nانتهى الوقت (Timeout): "
                    f"السيرفر لم يستجب بعد "
                    f"{max_retries / 2} ثانية."
                )

        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    # إعداد نافذة التطبيق
    # ═══════════════════════════════════════════════════════

    window_title = "ERP Governance System - Asam"

    webview.create_window(

        title=window_title,

        url=url,

        width=1280,

        height=800,

        min_size=(800, 600),

        resizable=True,

        maximized=True,

        fullscreen=False,

        confirm_close=False,

        text_select=True,

        easy_drag=False,
    )

    # ═══════════════════════════════════════════════════════
    # تشغيل WebView2 / Edge
    # ═══════════════════════════════════════════════════════

    webview.start(

        private_mode=False,

        storage_path=None,

        debug=False,

        gui='edgechromium',
    )


# ═══════════════════════════════════════════════════════════
# نقطة تشغيل البرنامج
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":

    multiprocessing.freeze_support()

    main()
