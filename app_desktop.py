
# -*- coding: utf-8 -*-
# Hokama ERP — Windows Desktop Launcher
# Streamlit + Microsoft Edge App Mode
# Readiness Protocol v1

# ============================================================
# معالجة multiprocessing في PyInstaller
# يجب أن تكون مبكرة قبل بقية الاستيرادات
# ============================================================

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()


# ============================================================
# Imports
# ============================================================

import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import uuid

from pathlib import Path


# ============================================================
# Windows
# ============================================================

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"


# ============================================================
# إعدادات التطبيق
# ============================================================

APP_NAME = "Hokama ERP"
HOST = "127.0.0.1"

PROTOCOL_VERSION = 1

HTTP_STARTUP_TIMEOUT = 60
APP_READINESS_TIMEOUT = 120

STARTUP_RETRIES = 3

HEALTH_CHECK_INTERVAL = 0.5
READY_CHECK_INTERVAL = 0.5

MONITOR_INTERVAL = 2
EDGE_CLOSE_GRACE = 15
EDGE_DETECTION_TIMEOUT = 60


# ============================================================
# المسارات
# ============================================================

def get_base_path():
    """مجلد الملفات المضمّنة بواسطة PyInstaller."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()

    return Path(__file__).resolve().parent


def get_data_dir():
    """مجلد بيانات المشغّل وملف تعريف Edge."""

    root = Path(os.getenv("LOCALAPPDATA") or Path.home())

    path = root / "HokamaERP"
    path.mkdir(parents=True, exist_ok=True)

    return path


def get_logs_dir():

    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)

    return path


def get_run_dir():

    path = get_data_dir() / "run"
    path.mkdir(parents=True, exist_ok=True)

    return path


def get_readiness_file(startup_id):

    return get_run_dir() / f"{startup_id}.json"


# ============================================================
# السجلات
# ============================================================

def log_message(message):

    try:
        log_file = get_logs_dir() / "startup.log"

        with log_file.open("a", encoding="utf-8") as log:

            log.write(
                time.strftime("%Y-%m-%d %H:%M:%S")
                + " | "
                + str(message)
                + "\n"
            )

    except Exception:
        pass


def read_streamlit_log_tail(max_chars=8000):

    path = get_logs_dir() / "streamlit.log"

    try:

        if path.exists():

            return path.read_text(
                encoding="utf-8",
                errors="replace",
            )[-max_chars:]

    except Exception:
        pass

    return "لا يوجد سجل Streamlit متاح."


def show_error(title, message):

    if sys.platform == "win32":

        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                str(message),
                str(title),
                0x10,
            )

            return

        except Exception:
            pass

    print(
        f"{title}: {message}",
        file=sys.stderr,
    )


# ============================================================
# ملفات الجاهزية
# ============================================================

def cleanup_readiness_file(startup_id):
    """حذف ملف المحاولة الحالية فقط."""

    try:

        path = get_readiness_file(startup_id)

        if path.exists():
            path.unlink()

    except Exception as exc:

        log_message(
            f"Readiness cleanup failed: {exc}"
        )


def read_readiness_file(startup_id):
    """
    قراءة ملف الجاهزية والتحقق من هويته وإصدار البروتوكول.

    تعيد:
        ("ready", None)
        ("error", رسالة)
        (None, None) إذا لم تصل إشارة صالحة بعد.
    """

    path = get_readiness_file(startup_id)

    if not path.exists():
        return None, None

    try:

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if data.get("startup_id") != startup_id:

            log_message(
                "Ignored readiness file: startup_id mismatch."
            )

            return None, None

        if data.get("protocol_version") != PROTOCOL_VERSION:

            return (
                "error",
                "إصدار بروتوكول الجاهزية غير متوافق بين المشغّل والتطبيق.",
            )

        status = data.get("status")

        if status == "ready":

            return "ready", None

        if status == "error":

            return (
                "error",
                data.get("error")
                or "خطأ غير معروف أثناء تهيئة التطبيق.",
            )

        return None, None

    except json.JSONDecodeError:

        # قد يكون الملف في طور الاستبدال.
        return None, None

    except Exception as exc:

        log_message(
            f"Readiness read error: {exc}"
        )

        return None, None


# ============================================================
# اختيار المنفذ
# ============================================================

def find_free_port():
    """
    اختيار منفذ متاح مبدئيًا.
    إذا حدث تعارض عند ربط Streamlit بالمنفذ،
    ستتعامل إعادة المحاولة مع ذلك.
    """

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:

        sock.bind((HOST, 0))

        return sock.getsockname()[1]


# ============================================================
# HTTP Health Check
# ============================================================

def http_get(url, timeout=3):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 HokamaERP"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:

        return response.status, response.read()


def is_streamlit_healthy(host, port):
    """التحقق من استجابة Streamlit الفعلية."""

    try:

        status, health_body = http_get(
            f"http://{host}:{port}/_stcore/health",
            timeout=2,
        )

        if status != 200:
            return False

        health_text = health_body.decode(
            "utf-8",
            errors="ignore",
        ).strip().lower()

        if health_text not in ("ok", "healthy"):
            return False

        status, page_body = http_get(
            f"http://{host}:{port}/",
            timeout=4,
        )

        if status != 200:
            return False

        html_text = page_body.decode(
            "utf-8",
            errors="ignore",
        ).lower()

        return (
            "<html" in html_text
            or "<!doctype html>" in html_text
        )

    except Exception:

        return False


def wait_for_http_health(
    server,
    host,
    port,
    timeout,
):
    """انتظار صحة خادم Streamlit قبل فتح Edge."""

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        if not server.is_alive():

            log_message(
                "Streamlit process exited before HTTP readiness."
            )

            return False

        if is_streamlit_healthy(host, port):

            return True

        time.sleep(HEALTH_CHECK_INTERVAL)

    return False


# ============================================================
# انتظار جاهزية التطبيق
# ============================================================

def wait_for_readiness(
    server,
    host,
    port,
    startup_id,
    timeout=APP_READINESS_TIMEOUT,
):
    """
    هذه المرحلة تبدأ بعد فتح Edge؛ لأن app.py يحتاج
    إلى جلسة Streamlit حتى يبدأ التنفيذ.
    """

    deadline = time.monotonic() + timeout

    last_health_check = 0

    while time.monotonic() < deadline:

        if not server.is_alive():

            return (
                False,
                "توقفت عملية Streamlit قبل اكتمال تهيئة التطبيق.",
            )

        status, error_message = read_readiness_file(
            startup_id
        )

        if status == "ready":

            log_message(
                "Application readiness confirmed."
            )

            return True, None

        if status == "error":

            log_message(
                f"Application startup error: {error_message}"
            )

            return False, error_message

        now = time.monotonic()

        if now - last_health_check >= 3:

            last_health_check = now

            if not is_streamlit_healthy(host, port):

                log_message(
                    "Warning: Streamlit HTTP health check failed "
                    "while waiting for app readiness."
                )

        time.sleep(READY_CHECK_INTERVAL)

    return (
        False,
        "انتهت مهلة انتظار إشارة الجاهزية من app.py.\n"
        "راجع سجل Streamlit لمعرفة سبب التأخير.",
    )


# ============================================================
# تشغيل Streamlit
# ============================================================

def run_streamlit(port, app_path, startup_id):
    """تشغيل Streamlit داخل عملية مستقلة."""

    try:

        # ----------------------------------------------------
        # تجهيز مسار التطبيق
        # ----------------------------------------------------

        app_path = Path(app_path).resolve()

        if not app_path.is_file():

            raise FileNotFoundError(
                f"لم يتم العثور على app.py: {app_path}"
            )

        app_root = app_path.parent

        # إضافة مجلد التطبيق إلى مسارات Python.
        # هذا يساعد على العثور على database و ui و services.

        app_root_text = str(app_root)

        if app_root_text not in sys.path:

            sys.path.insert(
                0,
                app_root_text,
            )

        # جعل مجلد التطبيق مجلد العمل الحالي.
        os.chdir(app_root)

        # ----------------------------------------------------
        # إعداد asyncio على Windows
        # ----------------------------------------------------

        if sys.platform == "win32":

            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        asyncio.set_event_loop(
            asyncio.new_event_loop()
        )

        # ----------------------------------------------------
        # إعداد السجل
        # ----------------------------------------------------

        logs_dir = get_logs_dir()

        streamlit_log_path = (
            logs_dir / "streamlit.log"
        )

        with streamlit_log_path.open(
            "a",
            encoding="utf-8",
        ) as child_log:

            sys.stdout = child_log
            sys.stderr = child_log

            child_log.write(
                "\n"
                + "=" * 65
                + "\n"
                + f"New Streamlit startup: {startup_id}\n"
                + f"Port: {port}\n"
                + f"Application: {app_path}\n"
                + f"Working directory: {app_root}\n"
                + "=" * 65
                + "\n"
            )

            child_log.flush()

            # ------------------------------------------------
            # متغيرات بروتوكول الجاهزية
            # ------------------------------------------------

            os.environ["HOKAMA_STARTUP_ID"] = startup_id

            os.environ["HOKAMA_READINESS_PROTOCOL"] = str(
                PROTOCOL_VERSION
            )

            # ------------------------------------------------
            # تشغيل Streamlit
            # ------------------------------------------------

            from streamlit.web import cli as stcli

            sys.argv = [
                "streamlit",
                "run",
                str(app_path),

                f"--server.port={port}",
                f"--server.address={HOST}",

                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",

                "--browser.gatherUsageStats=false",
                "--global.developmentMode=false",
            ]

            # نترك CORS وXSRF على الإعدادات الافتراضية.

            stcli.main()

    except SystemExit as exc:

        log_message(
            f"Streamlit exited with code: {exc.code}"
        )

    except Exception:

        error_text = traceback.format_exc()

        log_message(
            "Streamlit child fatal error:\n"
            + error_text
        )


# ============================================================
# اكتشاف Edge
# ============================================================

def find_edge():

    candidates = []

    for env_name in (
        "PROGRAMFILES(X86)",
        "PROGRAMFILES",
        "ProgramW6432",
    ):

        root = os.getenv(env_name)

        if root:

            candidates.append(
                Path(root)
                / "Microsoft"
                / "Edge"
                / "Application"
                / "msedge.exe"
            )

    local_appdata = os.getenv("LOCALAPPDATA")

    if local_appdata:

        candidates.append(
            Path(local_appdata)
            / "Microsoft"
            / "Edge"
            / "Application"
            / "msedge.exe"
        )

    which_result = shutil.which("msedge")

    if which_result:

        candidates.append(
            Path(which_result)
        )

    for candidate in candidates:

        try:

            if candidate.is_file():

                return str(candidate.resolve())

        except OSError:

            pass

    return None


# ============================================================
# فحص عمليات Edge الخاصة بملف التعريف
# ============================================================

def edge_process_using_profile(edge_profile):
    """
    True  = توجد عملية Edge تستخدم الملف الشخصي.
    False = لا توجد عملية.
    None  = تعذر الفحص.
    """

    if sys.platform != "win32":
        return None

    try:

        profile_text = str(edge_profile)

        encoded_profile = base64.b64encode(
            profile_text.encode("utf-8")
        ).decode("ascii")

        powershell_script = (
            "$profile = [Text.Encoding]::UTF8.GetString("
            "[Convert]::FromBase64String('"
            + encoded_profile
            + "')); "

            "$processes = Get-CimInstance Win32_Process "
            "-Filter \"Name = 'msedge.exe'\" "
            "-ErrorAction SilentlyContinue; "

            "$match = $processes | Where-Object { "
            "$_.CommandLine -and "
            "$_.CommandLine.Contains($profile) "
            "} | Select-Object -First 1; "

            "if ($match) { $match.ProcessId }"
        )

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script,
            ],

            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=8,

            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )

        if result.returncode != 0:
            return None

        return bool(
            result.stdout.strip()
        )

    except Exception as exc:

        log_message(
            f"Edge process check failed: {exc}"
        )

        return None


# ============================================================
# تشغيل Edge
# ============================================================

def launch_edge(
    edge_exe,
    edge_profile,
    url,
):
    """فتح نافذة Edge App Mode."""

    browser_args = [
        edge_exe,

        f"--user-data-dir={edge_profile}",
        f"--app={url}",

        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",

        "--disable-background-mode",
        "--disable-features=Translate",
        "--force-color-profile=srgb",
    ]

    edge_log_path = (
        get_logs_dir() / "edge.log"
    )

    log_message(
        "Launching Microsoft Edge App Mode."
    )

    with edge_log_path.open(
        "a",
        encoding="utf-8",
    ) as edge_log:

        process = subprocess.Popen(
            browser_args,

            cwd=str(
                Path(edge_exe).parent
            ),

            stdout=edge_log,
            stderr=subprocess.STDOUT,

            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )

    log_message(
        f"Edge launcher process started: {process.pid}"
    )

    return process


# ============================================================
# إيقاف Streamlit
# ============================================================

def stop_server(server):

    if server is None:
        return

    try:

        if server.is_alive():

            log_message(
                "Stopping Streamlit server."
            )

            server.terminate()
            server.join(timeout=5)

        if server.is_alive() and hasattr(server, "kill"):

            server.kill()
            server.join(timeout=3)

    except Exception:

        log_message(
            "Server shutdown error:\n"
            + traceback.format_exc()
        )


# ============================================================
# مراقبة التطبيق
# ============================================================

def monitor_application(
    server,
    edge_profile,
):
    """مراقبة الخادم وإغلاقه بعد إغلاق نافذة Edge."""

    log_message(
        "Monitoring Hokama ERP."
    )

    first_detection = False

    missing_since = None

    detection_deadline = (
        time.monotonic() + EDGE_DETECTION_TIMEOUT
    )

    while True:

        if not server.is_alive():

            log_message(
                "ERROR: Streamlit server process stopped."
            )

            return False

        edge_state = edge_process_using_profile(
            edge_profile
        )

        if edge_state is True:

            if not first_detection:

                log_message(
                    "Edge application detected."
                )

            first_detection = True
            missing_since = None

        elif edge_state is False:

            if first_detection:

                if missing_since is None:

                    missing_since = time.monotonic()

                elif (
                    time.monotonic() - missing_since
                    >= EDGE_CLOSE_GRACE
                ):

                    log_message(
                        "Edge application closed."
                    )

                    return True

            elif time.monotonic() >= detection_deadline:

                log_message(
                    "WARNING: Edge not detected during initial period. "
                    "Keeping server alive."
                )

                detection_deadline = (
                    time.monotonic()
                    + EDGE_DETECTION_TIMEOUT
                )

        else:

            # الفحص المجهول لا يعتبر إغلاقًا للمتصفح.
            missing_since = None

        time.sleep(
            MONITOR_INTERVAL
        )


# ============================================================
# تشغيل Streamlit مع إعادة المحاولة
# ============================================================

def start_streamlit_with_retry(app_path):
    """
    كل محاولة لها startup_id مستقل.

    ننتظر HTTP فقط هنا، ثم نفتح Edge
    وننتظر جاهزية app.py.
    """

    for attempt in range(
        1,
        STARTUP_RETRIES + 1,
    ):

        port = find_free_port()

        startup_id = str(
            uuid.uuid4()
        )

        cleanup_readiness_file(
            startup_id
        )

        log_message(
            f"Starting Streamlit attempt "
            f"{attempt}/{STARTUP_RETRIES}, "
            f"port={port}, "
            f"startup_id={startup_id}"
        )

        server = multiprocessing.Process(
            target=run_streamlit,

            args=(
                port,
                str(app_path),
                startup_id,
            ),

            name="HokamaERP-Streamlit",
            daemon=False,
        )

        server.start()

        log_message(
            f"Streamlit process started: {server.pid}"
        )

        http_ready = wait_for_http_health(
            server,
            HOST,
            port,
            HTTP_STARTUP_TIMEOUT,
        )

        if http_ready:

            log_message(
                f"Streamlit HTTP is healthy on port {port}."
            )

            return (
                server,
                port,
                startup_id,
                None,
            )

        log_message(
            f"Streamlit HTTP startup attempt {attempt} failed."
        )

        stop_server(server)

        cleanup_readiness_file(
            startup_id
        )

        if attempt < STARTUP_RETRIES:

            time.sleep(1)

    return (
        None,
        None,
        None,
        "فشل تشغيل خادم Streamlit بعد عدة محاولات.",
    )


# ============================================================
# الدالة الرئيسية
# ============================================================

def main():

    server = None

    startup_id = None

    try:

        log_message("=" * 60)

        log_message(
            "Starting Hokama ERP Desktop."
        )

        # ----------------------------------------------------
        # مسار app.py
        # ----------------------------------------------------

        app_path = (
            get_base_path() / "app.py"
        ).resolve()

        if not app_path.is_file():

            message = (
                f"لم يتم العثور على ملف التطبيق:\n"
                f"{app_path}\n\n"
                "تأكد من تضمين app.py عند بناء EXE."
            )

            log_message(
                "ERROR: " + message
            )

            show_error(
                APP_NAME,
                message,
            )

            return 1

        # ----------------------------------------------------
        # اكتشاف Edge
        # ----------------------------------------------------

        edge_exe = find_edge()

        if not edge_exe:

            message = (
                "لم يتم العثور على Microsoft Edge.\n"
                "ثبّت Edge ثم أعد تشغيل النظام."
            )

            log_message(
                "ERROR: " + message
            )

            show_error(
                APP_NAME,
                message,
            )

            return 1

        # ----------------------------------------------------
        # مجلدات البيانات
        # ----------------------------------------------------

        data_dir = get_data_dir()

        edge_profile = (
            data_dir / "EdgeProfile"
        )

        edge_profile.mkdir(
            parents=True,
            exist_ok=True,
        )

        logs_dir = get_logs_dir()

        log_message(
            f"Application: {app_path}"
        )

        log_message(
            f"Edge: {edge_exe}"
        )

        log_message(
            f"Edge profile: {edge_profile}"
        )

        # ----------------------------------------------------
        # 1. تشغيل Streamlit وانتظار صحة HTTP
        # ----------------------------------------------------

        (
            server,
            port,
            startup_id,
            error_msg,
        ) = start_streamlit_with_retry(
            app_path
        )

        if server is None:

            detail = read_streamlit_log_tail()

            message = (
                f"{error_msg}\n\n"
                f"آخر سجل Streamlit:\n"
                f"{detail}\n\n"
                f"ملفات السجل:\n"
                f"{logs_dir}"
            )

            log_message(
                "ERROR: " + message
            )

            show_error(
                "تعذّر تشغيل Hokama ERP",
                message,
            )

            return 1

        url = (
            f"http://{HOST}:{port}"
        )

        log_message(
            f"Local URL: {url}"
        )

        # ----------------------------------------------------
        # 2. فتح Edge لإنشاء جلسة Streamlit
        # ----------------------------------------------------

        launch_edge(
            edge_exe,
            edge_profile,
            url,
        )

        # ----------------------------------------------------
        # 3. انتظار جاهزية app.py
        # ----------------------------------------------------

        ready, readiness_error = wait_for_readiness(
            server=server,
            host=HOST,
            port=port,
            startup_id=startup_id,
            timeout=APP_READINESS_TIMEOUT,
        )

        if not ready:

            detail = read_streamlit_log_tail()

            message = (
                "تعذّر إكمال تهيئة التطبيق:\n\n"
                f"{readiness_error}\n\n"
                f"آخر سجل Streamlit:\n"
                f"{detail}\n\n"
                f"ملفات السجل:\n"
                f"{logs_dir}"
            )

            log_message(
                "ERROR: " + message
            )

            show_error(
                "تعذّر تشغيل Hokama ERP",
                message,
            )

            return 1

        log_message(
            "Application readiness confirmed successfully."
        )

        # ----------------------------------------------------
        # 4. مراقبة التطبيق
        # ----------------------------------------------------

        monitor_ok = monitor_application(
            server,
            edge_profile,
        )

        if not monitor_ok:

            detail = read_streamlit_log_tail()

            show_error(
                APP_NAME,

                "توقف خادم التطبيق.\n\n"
                f"آخر سجل Streamlit:\n"
                f"{detail}\n\n"
                f"ملفات السجل:\n"
                f"{logs_dir}",
            )

            return 1

        log_message(
            "Hokama ERP browser session closed."
        )

        return 0

    except KeyboardInterrupt:

        log_message(
            "Interrupted by user."
        )

        return 0

    except Exception:

        error = traceback.format_exc()

        log_message(
            "Fatal launcher error:\n"
            + error
        )

        show_error(
            "Hokama ERP — خطأ",

            "حدث خطأ أثناء تشغيل التطبيق.\n\n"
            "راجع السجل:\n"
            f"{get_logs_dir() / 'startup.log'}",
        )

        return 1

    finally:

        stop_server(server)

        if startup_id:

            cleanup_readiness_file(
                startup_id
            )

        log_message(
            "Hokama ERP launcher stopped."
        )


# ============================================================
# نقطة الدخول
# ============================================================

if __name__ == "__main__":
    raise SystemExit(main())
