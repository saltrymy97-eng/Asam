
# app_desktop.py
# Hokama ERP — Windows Desktop Launcher (v2.3)
# Streamlit + Microsoft Edge App Mode
# Improved startup checks, port retry, and process monitoring.

import asyncio
import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path


if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"


APP_NAME = "Hokama ERP"
HOST = "127.0.0.1"

STARTUP_TIMEOUT = 90
STARTUP_RETRIES = 3
HEALTH_CHECK_INTERVAL = 0.5
STABLE_CHECKS_REQUIRED = 4

MONITOR_INTERVAL = 2
EDGE_CLOSE_GRACE = 15
EDGE_DETECTION_TIMEOUT = 60


def get_base_path():
    """مجلد ملفات التطبيق المضمّنة."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent


def get_data_dir():
    """مجلد بيانات المشغّل وملفات السجل وملف تعريف Edge."""
    root = Path(os.getenv("LOCALAPPDATA") or Path.home())
    path = root / "HokamaERP"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir():
    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def show_error(title, message):
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, title, 0x10
            )
            return
        except Exception:
            pass

    print(f"{title}: {message}", file=sys.stderr)


def find_free_port():
    """اختيار منفذ متاح مبدئيًا."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def is_port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def http_get(url, timeout=3):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 HokamaERP"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def is_streamlit_healthy(host, port):
    """فحص صحة خادم Streamlit واستجابة الصفحة الرئيسية."""
    try:
        status, _ = http_get(
            f"http://{host}:{port}/_stcore/health",
            timeout=2,
        )

        if status != 200:
            return False

        status, body = http_get(
            f"http://{host}:{port}/",
            timeout=4,
        )

        if status != 200:
            return False

        html = body.decode("utf-8", errors="ignore").lower()

        return (
            "<!doctype html>" in html
            or "<html" in html
        )

    except Exception:
        return False


def wait_for_streamlit(server, host, port, timeout=STARTUP_TIMEOUT):
    """
    لا يكتفي باستجابة واحدة.
    يشترط نجاح عدة فحوص متتالية واستمرار عملية الخادم.
    """
    deadline = time.monotonic() + timeout
    stable_checks = 0

    while time.monotonic() < deadline:
        if not server.is_alive():
            log_message("Streamlit process exited during startup")
            return False

        if is_streamlit_healthy(host, port):
            stable_checks += 1

            log_message(
                f"Streamlit health check: "
                f"{stable_checks}/{STABLE_CHECKS_REQUIRED}"
            )

            if stable_checks >= STABLE_CHECKS_REQUIRED:
                return True
        else:
            stable_checks = 0

        time.sleep(HEALTH_CHECK_INTERVAL)

    return False


def run_streamlit(port, app_path):
    """تشغيل Streamlit في عملية مستقلة."""
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        asyncio.set_event_loop(asyncio.new_event_loop())

        logs_dir = get_logs_dir()
        streamlit_log_path = logs_dir / "streamlit.log"

        with streamlit_log_path.open(
            "a",
            encoding="utf-8",
        ) as child_log:

            sys.stdout = child_log
            sys.stderr = child_log

            from streamlit.web import cli as stcli

            sys.argv = [
                "streamlit",
                "run",
                app_path,
                f"--server.port={port}",
                f"--server.address={HOST}",
                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",
                "--server.enableCORS=false",
                "--server.enableXsrfProtection=false",
                "--browser.gatherUsageStats=false",
                "--global.developmentMode=false",
            ]

            stcli.main()

    except SystemExit:
        pass

    except Exception:
        log_message(
            "Streamlit child error:\n"
            + traceback.format_exc()
        )


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
        candidates.append(Path(which_result))

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except OSError:
            pass

    return None


def edge_process_using_profile(edge_profile):
    """
    True  = توجد عملية Edge تستخدم الملف الشخصي.
    False = لا توجد عملية.
    None  = تعذر إجراء الفحص.
    """
    if sys.platform != "win32":
        return None

    profile_text = str(edge_profile).replace("'", "''")

    powershell_script = (
        "$p = Get-CimInstance Win32_Process "
        "-Filter \"Name = 'msedge.exe'\" "
        "-ErrorAction SilentlyContinue; "
        f"$p | Where-Object {{ $_.CommandLine -like "
        f"('*' + '{profile_text}' + '*') }} | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )

    try:
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
            timeout=6,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )

        if result.returncode != 0:
            return None

        return bool(result.stdout.strip())

    except Exception as exc:
        log_message("Edge process check failed: " + str(exc))
        return None


def launch_edge(edge_exe, edge_profile, url, logs_dir):
    """فتح نافذة Edge مرة واحدة."""
    browser_args = [
        edge_exe,
        f"--user-data-dir={edge_profile}",
        f"--app={url}",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "--disable-features=Translate",
        "--disable-gpu",
        "--force-color-profile=srgb",
    ]

    edge_log_path = logs_dir / "edge.log"

    log_message("Launching Edge app mode")

    with edge_log_path.open("a", encoding="utf-8") as edge_log:
        process = subprocess.Popen(
            browser_args,
            cwd=str(Path(edge_exe).parent),
            stdout=edge_log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )

    log_message(f"Edge launcher process started: {process.pid}")

    return process


def stop_server(server):
    if server is None:
        return

    try:
        if server.is_alive():
            log_message("Stopping Streamlit server")

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


def read_streamlit_log_tail(logs_dir):
    path = logs_dir / "streamlit.log"

    try:
        if path.exists():
            return path.read_text(
                encoding="utf-8",
                errors="replace",
            )[-4000:]
    except Exception:
        pass

    return ""


def monitor_application(server, edge_profile):
    """
    مراقبة خادم Streamlit ونافذة Edge.
    لا يعتمد على browser.poll().
    """
    log_message("Monitoring Hokama ERP")

    first_detection = False
    missing_since = None
    detection_deadline = (
        time.monotonic() + EDGE_DETECTION_TIMEOUT
    )

    while True:
        if not server.is_alive():
            log_message("ERROR: Streamlit process stopped")
            return False

        edge_state = edge_process_using_profile(edge_profile)

        if edge_state is True:
            if not first_detection:
                log_message("Edge application detected")

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
                        "Edge profile process is no longer detected"
                    )
                    return True

            elif time.monotonic() >= detection_deadline:
                log_message(
                    "WARNING: Edge was not detected within "
                    "the initial detection period. "
                    "Keeping server alive."
                )

                detection_deadline = (
                    time.monotonic() + EDGE_DETECTION_TIMEOUT
                )

        else:
            missing_since = None

        time.sleep(MONITOR_INTERVAL)


def start_streamlit_with_retry(app_path):
    """
    تشغيل Streamlit مع إعادة المحاولة عند فشل بدء الخادم
    أو تعارض المنفذ.
    """
    for attempt in range(1, STARTUP_RETRIES + 1):
        port = find_free_port()

        log_message(
            f"Starting Streamlit attempt {attempt}/"
            f"{STARTUP_RETRIES} on port {port}"
        )

        server = multiprocessing.Process(
            target=run_streamlit,
            args=(port, str(app_path)),
            name="HokamaERP-Streamlit",
            daemon=True,
        )

        server.start()

        log_message(
            f"Streamlit process started: {server.pid}"
        )

        if wait_for_streamlit(
            server,
            HOST,
            port,
            STARTUP_TIMEOUT,
        ):
            log_message(
                f"Streamlit server is stable on port {port}"
            )
            return server, port

        log_message(
            f"Streamlit startup attempt {attempt} failed"
        )

        stop_server(server)

        if attempt < STARTUP_RETRIES:
            time.sleep(1)

    return None, None


def main():
    server = None
    browser = None

    try:
        app_path = get_base_path() / "app.py"

        if not app_path.is_file():
            message = (
                f"لم يتم العثور على ملف التطبيق:\n{app_path}\n\n"
                "تأكد من تضمين app.py عند بناء EXE."
            )

            log_message("ERROR: " + message)
            show_error(APP_NAME, message)
            return 1

        edge_exe = find_edge()

        if not edge_exe:
            message = (
                "لم يتم العثور على Microsoft Edge.\n"
                "ثبّت Edge ثم شغّل Hokama ERP مرة أخرى."
            )

            log_message("ERROR: " + message)
            show_error(APP_NAME, message)
            return 1

        data_dir = get_data_dir()
        logs_dir = get_logs_dir()

        edge_profile = data_dir / "EdgeProfile"
        edge_profile.mkdir(parents=True, exist_ok=True)

        log_message("=" * 55)
        log_message("Starting Hokama ERP Desktop v2.3")
        log_message(f"Application: {app_path}")
        log_message(f"Edge: {edge_exe}")
        log_message(f"Edge profile: {edge_profile}")

        # تشغيل Streamlit وفحص استقراره.
        server, port = start_streamlit_with_retry(app_path)

        if server is None:
            detail = read_streamlit_log_tail(logs_dir)

            message = (
                "تعذّر تشغيل خادم التطبيق بعد عدة محاولات.\n\n"
                f"سجل الأخطاء:\n{detail}\n\n"
                f"ملفات السجل:\n{logs_dir}"
            )

            log_message("ERROR: " + message)
            show_error("تعذّر تشغيل Hokama ERP", message)
            return 1

        url = f"http://{HOST}:{port}"
        log_message(f"Local URL: {url}")

        # إعادة تأكيد صحة الخادم قبل فتح المتصفح.
        if not is_streamlit_healthy(HOST, port):
            log_message(
                "ERROR: Streamlit health check failed "
                "immediately before Edge launch"
            )

            show_error(
                APP_NAME,
                "بدأ الخادم لكنه لم يعد يستجيب قبل فتح المتصفح.\n"
                f"راجع السجلات داخل:\n{logs_dir}",
            )
            return 1

        # فتح Edge مرة واحدة فقط.
        browser = launch_edge(
            edge_exe,
            edge_profile,
            url,
            logs_dir,
        )

        log_message(
            "Edge launch requested. "
            "No automatic second window will be opened."
        )

        monitor_ok = monitor_application(
            server,
            edge_profile,
        )

        if not monitor_ok:
            detail = read_streamlit_log_tail(logs_dir)

            log_message(
                "Application monitor detected a server failure"
            )

            show_error(
                APP_NAME,
                "توقف خادم التطبيق.\n\n"
                f"آخر سجل Streamlit:\n{detail}\n\n"
                f"ملفات السجل:\n{logs_dir}",
            )

            return 1

        log_message("Hokama ERP browser session closed")
        return 0

    except KeyboardInterrupt:
        log_message("Interrupted by user")
        return 0

    except Exception:
        error = traceback.format_exc()

        log_message(
            "Fatal launcher error:\n" + error
        )

        show_error(
            "Hokama ERP — خطأ",
            "حدث خطأ أثناء تشغيل التطبيق.\n"
            f"راجع السجل:\n"
            f"{get_logs_dir() / 'startup.log'}",
        )

        return 1

    finally:
        stop_server(server)
        log_message("Hokama ERP launcher stopped")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
