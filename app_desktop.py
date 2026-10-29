
# app_desktop.py
# Hokama ERP — Windows Desktop Launcher (v2.1)
# Streamlit + Microsoft Edge App Mode
#
# Improvements:
# - Persistent Edge profile.
# - Waits for the actual Edge process using the dedicated profile.
# - Does not mistake the initial Edge launcher exit for browser closure.
# - Retries opening the app if Edge does not start correctly.
# - Monitors Streamlit while the browser is running.
# - Keeps startup and diagnostic logs.

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
STARTUP_TIMEOUT = 60
EDGE_START_TIMEOUT = 25
EDGE_RETRY_DELAY = 8
MONITOR_INTERVAL = 2


def get_base_path():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_data_dir():
    root = Path(os.getenv("LOCALAPPDATA") or Path.home())
    path = root / "HokamaERP"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_message(message):
    try:
        log_dir = get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        with (log_dir / "startup.log").open(
            "a", encoding="utf-8"
        ) as log:
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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def is_streamlit_fully_ready(host, port):
    # Check Streamlit health endpoint.
    try:
        health_url = f"http://{host}:{port}/_stcore/health"

        with urllib.request.urlopen(
            health_url, timeout=2
        ) as response:
            if response.status != 200:
                return False

    except Exception:
        return False

    # Check that the main page returns actual HTML.
    try:
        root_url = f"http://{host}:{port}/"

        req = urllib.request.Request(
            root_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        with urllib.request.urlopen(
            req, timeout=3
        ) as response:
            if response.status != 200:
                return False

            html = response.read().decode(
                "utf-8", errors="ignore"
            )

            return "<!DOCTYPE html>" in html

    except Exception:
        return False


def run_streamlit(port, app_path):
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        asyncio.set_event_loop(asyncio.new_event_loop())

        log_dir = get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        with (log_dir / "streamlit.log").open(
            "a", encoding="utf-8"
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


def edge_process_using_profile(edge_profile):
    """
    يتحقق من وجود عملية Edge تستخدم ملف التعريف الخاص بالنظام.

    لا نعتمد على browser.poll() وحده؛ لأن عملية إطلاق Edge
    قد تنتهي بعد تسليم الأمر إلى عملية Edge أخرى.
    """

    if sys.platform != "win32":
        return False

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
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        return bool(result.stdout.strip())

    except Exception as exc:
        log_message(
            "Edge process check failed: " + str(exc)
        )
        return None


def launch_edge(edge_exe, edge_profile, url, logs_dir):
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

    edge_log_path = logs_dir / "edge.log"

    log_message("Launching Edge app mode")

    with edge_log_path.open(
        "a", encoding="utf-8"
    ) as edge_log:

        process = subprocess.Popen(
            browser_args,
            cwd=str(Path(edge_exe).parent),
            stdout=edge_log,
            stderr=subprocess.STDOUT,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if sys.platform == "win32"
                else 0
            ),
        )

    log_message(
        f"Edge launcher process started: {process.pid}"
    )

    return process


def wait_for_edge(edge_profile, timeout):
    """
    ينتظر ظهور عملية Edge الفعلية المرتبطة بملف التعريف.
    """

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        state = edge_process_using_profile(edge_profile)

        if state is True:
            log_message(
                "Detected Edge process using Hokama profile"
            )
            return True

        time.sleep(1)

    return False


def main():
    server = None
    browser = None

    try:
        app_path = get_base_path() / "app.py"

        if not app_path.is_file():
            message = (
                f"لم يتم العثور على ملف التطبيق:\n{app_path}\n\n"
                "تأكد من تضمين app.py وملفات التطبيق عند بناء EXE."
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

        logs_dir = data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Persistent browser profile.
        edge_profile = data_dir / "EdgeProfile"
        edge_profile.mkdir(parents=True, exist_ok=True)

        # Use a free local port.
        port = find_free_port()
        url = f"http://{HOST}:{port}"

        log_message("=" * 55)
        log_message("Starting Hokama ERP Desktop v2.1")
        log_message(f"Application: {app_path}")
        log_message(f"Edge: {edge_exe}")
        log_message(f"Edge profile: {edge_profile}")
        log_message(f"Local URL: {url}")

        # Start Streamlit.
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

        # Wait for Streamlit to become ready.
        ready = False
        deadline = time.monotonic() + STARTUP_TIMEOUT

        while time.monotonic() < deadline:
            if not server.is_alive():
                log_message(
                    "ERROR: Streamlit process exited during startup"
                )
                break

            if is_streamlit_fully_ready(HOST, port):
                ready = True
                break

            time.sleep(0.5)

        if not ready:
            log_message(
                "ERROR: Streamlit failed to become fully ready"
            )

            detail = ""
            streamlit_log = logs_dir / "streamlit.log"

            try:
                if streamlit_log.exists():
                    detail = (
                        "\n\nآخر سجل Streamlit:\n"
                        + streamlit_log.read_text(
                            encoding="utf-8",
                            errors="replace",
                        )[-3000:]
                    )
            except Exception:
                pass

            show_error(
                "تعذّر تشغيل Hokama ERP",
                "لم يبدأ خادم التطبيق خلال المهلة المحددة.\n"
                f"راجع السجل:\n{logs_dir / 'startup.log'}"
                + detail,
            )

            return 1

        log_message("Streamlit is fully ready")

        # Allow the server to settle before opening Edge.
        time.sleep(2)

        # First Edge launch.
        browser = launch_edge(
            edge_exe,
            edge_profile,
            url,
            logs_dir,
        )

        edge_ready = wait_for_edge(
            edge_profile,
            EDGE_START_TIMEOUT,
        )

        # Retry if Edge did not start using our profile.
        if not edge_ready:
            log_message(
                "WARNING: Edge was not detected. "
                "Retrying launch."
            )

            time.sleep(EDGE_RETRY_DELAY)

            if not server.is_alive():
                raise RuntimeError(
                    "Streamlit stopped before Edge retry"
                )

            if not is_streamlit_fully_ready(HOST, port):
                raise RuntimeError(
                    "Streamlit is no longer responding"
                )

            browser = launch_edge(
                edge_exe,
                edge_profile,
                url,
                logs_dir,
            )

            edge_ready = wait_for_edge(
                edge_profile,
                EDGE_START_TIMEOUT,
            )

        if not edge_ready:
            log_message(
                "ERROR: Edge did not start with Hokama profile"
            )

            show_error(
                APP_NAME,
                "تعذّر تشغيل نافذة Microsoft Edge.\n\n"
                "تأكد من أن Edge غير مغلق أو عالق في الخلفية، "
                "ثم أعد تشغيل النظام.\n\n"
                f"ملفات السجل:\n{logs_dir}",
            )

            return 1

        log_message("Edge is running. Monitoring application.")

        # Monitor the actual Edge process, not only the launcher Popen.
        missing_edge_checks = 0

        while True:
            if not server.is_alive():
                log_message(
                    "ERROR: Streamlit process stopped unexpectedly"
                )

                show_error(
                    APP_NAME,
                    "توقف خادم التطبيق.\n"
                    f"راجع ملفات السجل داخل:\n{logs_dir}",
                )

                return 1

            edge_state = edge_process_using_profile(
                edge_profile
            )

            if edge_state is True:
                missing_edge_checks = 0

            elif edge_state is False:
                missing_edge_checks += 1

                # Avoid stopping the server because of a temporary
                # process transition or Edge restart.
                if missing_edge_checks >= 3:
                    log_message(
                        "Edge process using Hokama profile "
                        "is no longer detected"
                    )
                    break

            else:
                # If the process check itself fails, do not assume
                # that the user closed Edge.
                missing_edge_checks = 0

            time.sleep(MONITOR_INTERVAL)

        log_message("Hokama ERP browser window closed")

        return 0

    except KeyboardInterrupt:
        log_message("Interrupted by user")
        return 0

    except Exception:
        error = traceback.format_exc()

        log_message("Fatal launcher error:\n" + error)

        show_error(
            "Hokama ERP — خطأ",
            "حدث خطأ أثناء تشغيل التطبيق.\n"
            f"راجع السجل:\n"
            f"{get_data_dir() / 'logs' / 'startup.log'}",
        )

        return 1

    finally:
        stop_server(server)
        log_message("Hokama ERP launcher stopped")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
