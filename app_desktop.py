# -*- coding: utf-8 -*-
"""Hokama ERP — Windows Desktop Launcher

Streamlit + Google Chrome App Mode
Readiness Protocol v1
"""

# ============================================================
# multiprocessing bootstrap for PyInstaller
# Keep this before the remaining application imports.
# ============================================================

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

# ============================================================
# Imports
# ============================================================

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

from streamlit_runner import run_streamlit

# ============================================================
# Windows
# ============================================================

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

# ============================================================
# Application settings
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
CHROME_CLOSE_GRACE = 15
CHROME_DETECTION_TIMEOUT = 60

# ============================================================
# Paths
# ============================================================


def get_base_path():
    """Return the directory containing PyInstaller bundled files."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()

    return Path(__file__).resolve().parent


def get_data_dir():
    """Return the launcher data directory and Chrome profile root."""
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
# Logging
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

    print(f"{title}: {message}", file=sys.stderr)


# ============================================================
# Readiness files
# ============================================================


def cleanup_readiness_file(startup_id):
    """Delete only the readiness file belonging to this startup attempt."""
    try:
        path = get_readiness_file(startup_id)
        if path.exists():
            path.unlink()
    except Exception as exc:
        log_message(f"Readiness cleanup failed: {exc}")


def read_readiness_file(startup_id):
    """Read readiness and validate its startup ID and protocol version.

    Returns:
        ("ready", None)
        ("error", error_message)
        (None, None) when no valid signal is available yet.
    """
    path = get_readiness_file(startup_id)

    if not path.exists():
        return None, None

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if data.get("startup_id") != startup_id:
            log_message("Ignored readiness file: startup_id mismatch.")
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
                data.get("error") or "خطأ غير معروف أثناء تهيئة التطبيق.",
            )

        return None, None

    except json.JSONDecodeError:
        # The file may be in the process of being replaced.
        return None, None

    except Exception as exc:
        log_message(f"Readiness read error: {exc}")
        return None, None


# ============================================================
# Port selection
# ============================================================


def find_free_port():
    """Choose a currently available port; startup retry handles races."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


# ============================================================
# HTTP health check
# ============================================================


def http_get(url, timeout=3):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 HokamaERP"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def is_streamlit_healthy(host, port):
    """Check the actual Streamlit health endpoint and application page."""
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

        return "<html" in html_text or "<!doctype html>" in html_text

    except Exception:
        return False


def wait_for_http_health(server, host, port, timeout):
    """Wait for Streamlit HTTP health before opening Chrome."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if not server.is_alive():
            log_message("Streamlit process exited before HTTP readiness.")
            return False

        if is_streamlit_healthy(host, port):
            return True

        time.sleep(HEALTH_CHECK_INTERVAL)

    return False


# ============================================================
# Application readiness
# ============================================================


def wait_for_readiness(
    server,
    host,
    port,
    startup_id,
    timeout=APP_READINESS_TIMEOUT,
):
    """Wait for app.py readiness after Chrome has opened a Streamlit session."""
    deadline = time.monotonic() + timeout
    last_health_check = 0

    while time.monotonic() < deadline:
        if not server.is_alive():
            return (
                False,
                "توقفت عملية Streamlit قبل اكتمال تهيئة التطبيق.",
            )

        status, error_message = read_readiness_file(startup_id)

        if status == "ready":
            log_message("Application readiness confirmed.")
            return True, None

        if status == "error":
            log_message(f"Application startup error: {error_message}")
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
# Google Chrome discovery
# ============================================================


def find_chrome():
    """Find Google Chrome in common installation locations."""
    candidates = []

    for env_name in (
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "ProgramW6432",
    ):
        root = os.getenv(env_name)

        if root:
            candidates.append(
                Path(root)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe"
            )

    local_appdata = os.getenv("LOCALAPPDATA")

    if local_appdata:
        candidates.append(
            Path(local_appdata)
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe"
        )

    for executable_name in ("chrome", "chrome.exe"):
        which_result = shutil.which(executable_name)

        if which_result:
            candidates.append(Path(which_result))

    # Remove duplicates while preserving search order.
    seen = set()

    for candidate in candidates:
        try:
            candidate_key = str(candidate).lower()

            if candidate_key in seen:
                continue

            seen.add(candidate_key)

            if candidate.is_file():
                return str(candidate.resolve())

        except OSError:
            pass

    return None


# ============================================================
# Detect Chrome processes using this profile
# ============================================================


def chrome_process_using_profile(chrome_profile):
    """Return True/False, or None when the process check is unavailable."""
    if sys.platform != "win32":
        return None

    try:
        profile_text = str(chrome_profile)

        encoded_profile = base64.b64encode(
            profile_text.encode("utf-8")
        ).decode("ascii")

        powershell_script = (
            "$targetProfile = [Text.Encoding]::UTF8.GetString("
            "[Convert]::FromBase64String('"
            + encoded_profile
            + "')); "
            "$processes = Get-CimInstance Win32_Process "
            "-Filter \"Name = 'chrome.exe'\" "
            "-ErrorAction SilentlyContinue; "
            "$match = $processes | Where-Object { "
            "$_.CommandLine -and "
            "$_.CommandLine.Contains($targetProfile) "
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
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        if result.returncode != 0:
            return None

        return bool(result.stdout.strip())

    except Exception as exc:
        log_message(f"Chrome process check failed: {exc}")
        return None


# ============================================================
# Launch Chrome
# ============================================================


def launch_chrome(chrome_exe, chrome_profile, url):
    """Open the application in a dedicated Google Chrome App Mode window."""
    browser_args = [
        chrome_exe,
        f"--user-data-dir={chrome_profile}",
        f"--app={url}",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "--disable-features=Translate",
        "--force-color-profile=srgb",
    ]

    chrome_log_path = get_logs_dir() / "chrome.log"
    log_message("Launching Google Chrome App Mode.")

    with chrome_log_path.open("a", encoding="utf-8") as chrome_log:
        process = subprocess.Popen(
            browser_args,
            cwd=str(Path(chrome_exe).parent),
            stdout=chrome_log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    log_message(f"Chrome launcher process started: {process.pid}")
    return process


# ============================================================
# Stop Streamlit
# ============================================================


def stop_server(server):
    if server is None:
        return

    try:
        if server.is_alive():
            log_message("Stopping Streamlit server.")
            server.terminate()
            server.join(timeout=5)

        if server.is_alive() and hasattr(server, "kill"):
            server.kill()
            server.join(timeout=3)

    except Exception:
        log_message(
            "Server shutdown error:\n" + traceback.format_exc()
        )


# ============================================================
# Monitor application
# ============================================================


def monitor_application(server, chrome_profile):
    """Monitor the app and stop Streamlit after its Chrome window closes."""
    log_message("Monitoring Hokama ERP.")

    first_detection = False
    missing_since = None
    detection_deadline = time.monotonic() + CHROME_DETECTION_TIMEOUT

    while True:
        if not server.is_alive():
            log_message("ERROR: Streamlit server process stopped.")
            return False

        chrome_state = chrome_process_using_profile(chrome_profile)

        if chrome_state is True:
            if not first_detection:
                log_message("Chrome application detected.")

            first_detection = True
            missing_since = None

        elif chrome_state is False:
            if first_detection:
                if missing_since is None:
                    missing_since = time.monotonic()

                elif time.monotonic() - missing_since >= CHROME_CLOSE_GRACE:
                    log_message("Chrome application closed.")
                    return True

            elif time.monotonic() >= detection_deadline:
                log_message(
                    "WARNING: Chrome not detected during initial period. "
                    "Keeping server alive."
                )
                detection_deadline = (
                    time.monotonic() + CHROME_DETECTION_TIMEOUT
                )

        else:
            # An unknown process-check result is not treated as browser closure.
            missing_since = None

        time.sleep(MONITOR_INTERVAL)


# ============================================================
# Start Streamlit with retries
# ============================================================


def start_streamlit_with_retry(app_path):
    """Start Streamlit, retrying HTTP startup with a new port and startup ID."""
    for attempt in range(1, STARTUP_RETRIES + 1):
        port = find_free_port()
        startup_id = str(uuid.uuid4())

        cleanup_readiness_file(startup_id)

        log_message(
            f"Starting Streamlit attempt {attempt}/{STARTUP_RETRIES}, "
            f"port={port}, startup_id={startup_id}"
        )

        # run_streamlit is imported from streamlit_runner at module scope.
        # This keeps the multiprocessing target in an importable module on Windows.
        server = multiprocessing.Process(
            target=run_streamlit,
            args=(port, str(app_path), startup_id),
            name="HokamaERP-Streamlit",
            daemon=False,
        )

        server.start()
        log_message(f"Streamlit process started: {server.pid}")

        http_ready = wait_for_http_health(
            server,
            HOST,
            port,
            HTTP_STARTUP_TIMEOUT,
        )

        if http_ready:
            log_message(f"Streamlit HTTP is healthy on port {port}.")
            return server, port, startup_id, None

        log_message(
            f"Streamlit HTTP startup attempt {attempt} failed."
        )

        stop_server(server)
        cleanup_readiness_file(startup_id)

        if attempt < STARTUP_RETRIES:
            time.sleep(1)

    return (
        None,
        None,
        None,
        "فشل تشغيل خادم Streamlit بعد عدة محاولات.",
    )


# ============================================================
# Main function
# ============================================================


def main():
    server = None
    startup_id = None

    try:
        log_message("=" * 60)
        log_message("Starting Hokama ERP Desktop (Google Chrome).")

        # ----------------------------------------------------
        # app.py path
        # ----------------------------------------------------

        app_path = (get_base_path() / "app.py").resolve()

        if not app_path.is_file():
            message = (
                f"لم يتم العثور على ملف التطبيق:\n"
                f"{app_path}\n\n"
                "تأكد من تضمين app.py عند بناء EXE."
            )

            log_message("ERROR: " + message)
            show_error(APP_NAME, message)
            return 1

        # ----------------------------------------------------
        # Find Google Chrome
        # ----------------------------------------------------

        chrome_exe = find_chrome()

        if not chrome_exe:
            message = (
                "لم يتم العثور على Google Chrome.\n"
                "ثبّت Google Chrome ثم أعد تشغيل Hokama ERP."
            )

            log_message("ERROR: " + message)
            show_error(APP_NAME, message)
            return 1

        # ----------------------------------------------------
        # Data directories
        # ----------------------------------------------------

        data_dir = get_data_dir()
        chrome_profile = data_dir / "ChromeProfile"
        chrome_profile.mkdir(parents=True, exist_ok=True)
        logs_dir = get_logs_dir()

        log_message(f"Application: {app_path}")
        log_message(f"Chrome: {chrome_exe}")
        log_message(f"Chrome profile: {chrome_profile}")

        # ----------------------------------------------------
        # 1. Start Streamlit and wait for HTTP health
        # ----------------------------------------------------

        (
            server,
            port,
            startup_id,
            error_msg,
        ) = start_streamlit_with_retry(app_path)

        if server is None:
            detail = read_streamlit_log_tail()
            message = (
                f"{error_msg}\n\n"
                f"آخر سجل Streamlit:\n"
                f"{detail}\n\n"
                f"ملفات السجل:\n"
                f"{logs_dir}"
            )

            log_message("ERROR: " + message)
            show_error("تعذّر تشغيل Hokama ERP", message)
            return 1

        url = f"http://{HOST}:{port}"
        log_message(f"Local URL: {url}")

        # ----------------------------------------------------
        # 2. Open Chrome to create a Streamlit session
        # ----------------------------------------------------

        launch_chrome(chrome_exe, chrome_profile, url)

        # ----------------------------------------------------
        # 3. Wait for app.py readiness
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

            log_message("ERROR: " + message)
            show_error("تعذّر تشغيل Hokama ERP", message)
            return 1

        log_message("Application readiness confirmed successfully.")

        # ----------------------------------------------------
        # 4. Monitor application
        # ----------------------------------------------------

        monitor_ok = monitor_application(server, chrome_profile)

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

        log_message("Hokama ERP browser session closed.")
        return 0

    except KeyboardInterrupt:
        log_message("Interrupted by user.")
        return 0

    except Exception:
        error = traceback.format_exc()
        log_message("Fatal launcher error:\n" + error)

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
            cleanup_readiness_file(startup_id)

        log_message("Hokama ERP launcher stopped.")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    raise SystemExit(main())
