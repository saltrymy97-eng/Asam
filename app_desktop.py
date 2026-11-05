# -*- coding: utf-8 -*-
"""Hokama ERP — Windows Desktop Launcher

Streamlit + Google Chrome App Mode
Fixed Readiness Protocol ID: 1111
Single-instance protection: Windows Mutex
"""

# multiprocessing bootstrap for PyInstaller: keep this early.
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

import base64
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

from streamlit_runner import run_streamlit

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

APP_NAME = "Hokama ERP"
HOST = "127.0.0.1"

# These values must match streamlit_runner.py and app.py.
PROTOCOL_ID = "1111"
PROTOCOL_VERSION = 1
READINESS_FILENAME = "readiness.json"
MUTEX_NAME = r"Local\HokamaERP_Desktop_Single_Instance"
ERROR_ALREADY_EXISTS = 183

HTTP_STARTUP_TIMEOUT = 60
APP_READINESS_TIMEOUT = 120
STARTUP_RETRIES = 3
HEALTH_CHECK_INTERVAL = 0.5
READY_CHECK_INTERVAL = 0.5
MONITOR_INTERVAL = 2
CHROME_CLOSE_GRACE = 15
CHROME_DETECTION_TIMEOUT = 60

_READINESS_LAST_DIAGNOSTIC = None


# ============================================================
# Paths
# ============================================================

def get_base_path():
    """Return the directory containing PyInstaller bundled files."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent


def get_data_dir():
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


def get_readiness_file():
    return get_run_dir() / READINESS_FILENAME


# ============================================================
# Logging and error display
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


def read_streamlit_log_tail(max_chars=10000):
    path = get_logs_dir() / "streamlit.log"
    try:
        if path.exists():
            return path.read_text(
                encoding="utf-8", errors="replace"
            )[-max_chars:]
    except Exception:
        pass
    return "لا يوجد سجل Streamlit متاح."


def show_error(title, message):
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(
                None, str(message), str(title), 0x10
            )
            return
        except Exception:
            pass
    print("{}: {}".format(title, message), file=sys.stderr)


# ============================================================
# Single-instance protection (Windows named Mutex)
# ============================================================

def acquire_single_instance_mutex():
    """Return (handle, already_running, error_text)."""
    if sys.platform != "win32":
        log_message(
            "WARNING: Windows Mutex is unavailable on this platform; "
            "single-instance protection was not applied."
        )
        return None, False, None

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        create_mutex.restype = ctypes.c_void_p

        ctypes.set_last_error(0)
        handle = create_mutex(None, True, MUTEX_NAME)
        error_code = ctypes.get_last_error()

        if not handle:
            return None, False, "CreateMutexW failed with Windows error {}".format(
                error_code
            )

        if error_code == ERROR_ALREADY_EXISTS:
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.c_void_p]
            close_handle.restype = ctypes.c_bool
            close_handle(handle)
            return None, True, None

        # Keep the handle alive for the complete lifetime of the launcher.
        return (kernel32, handle), False, None

    except Exception:
        return None, False, traceback.format_exc()


def release_single_instance_mutex(mutex_token):
    if not mutex_token or sys.platform != "win32":
        return

    try:
        kernel32, handle = mutex_token
        release_mutex = kernel32.ReleaseMutex
        release_mutex.argtypes = [ctypes.c_void_p]
        release_mutex.restype = ctypes.c_bool
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_bool
        release_mutex(handle)
        close_handle(handle)
        log_message("Single-instance Mutex released.")
    except Exception:
        log_message(
            "Mutex release error:\n" + traceback.format_exc()
        )


# ============================================================
# Fixed readiness file and diagnostics
# ============================================================

def cleanup_readiness_file():
    """Remove the single readiness file before a fresh launch/attempt."""
    path = get_readiness_file()
    try:
        if path.exists():
            path.unlink()
            log_message("Removed stale readiness file: {}".format(path))
        else:
            log_message("No previous readiness file found: {}".format(path))
    except Exception as exc:
        log_message(
            "READINESS CLEANUP FAILED | path={} | error={!r}".format(
                path, exc
            )
        )
        raise


def _readiness_issue_once(message):
    global _READINESS_LAST_DIAGNOSTIC
    if message != _READINESS_LAST_DIAGNOSTIC:
        log_message(message)
        _READINESS_LAST_DIAGNOSTIC = message


def read_readiness_file(expected_pid=None):
    """Return ('ready', None), ('error', text), or (None, None)."""
    path = get_readiness_file()
    expected_id = PROTOCOL_ID
    expected_version = PROTOCOL_VERSION

    if not path.exists():
        return None, None

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        _readiness_issue_once(
            "[READINESS JSON ERROR] path={} | error={} | waiting for atomic write".format(
                path, exc
            )
        )
        return None, None
    except Exception as exc:
        _readiness_issue_once(
            "[READINESS READ ERROR] path={} | error={!r}".format(path, exc)
        )
        return None, None

    received_id = str(data.get("protocol_id", "<MISSING>")).strip()
    received_version = data.get("protocol_version", "<MISSING>")
    status = data.get("status", "<MISSING>")
    source = data.get("source", "<MISSING>")
    received_pid = data.get("pid", "<MISSING>")

    log_message(
        "[READINESS CHECK] expected_id={!r} | received_id={!r} | "
        "expected_version={!r} | received_version={!r} | "
        "expected_pid={!r} | received_pid={!r} | "
        "status={!r} | source={!r} | file={!r}".format(
            expected_id,
            received_id,
            expected_version,
            received_version,
            expected_pid,
            received_pid,
            status,
            source,
            str(path),
        )
    )

    if received_id != expected_id:
        message = (
            "عدم تطابق معرّف البروتوكول: المتوقع={!r}، المستلم={!r}. "
            "المصدر={!r}، الملف={!r}.".format(
                expected_id, received_id, source, path
            )
        )
        log_message("[READINESS ID MISMATCH] " + message)
        return "error", message

    if received_version != expected_version:
        message = (
            "عدم توافق إصدار البروتوكول: المتوقع={!r}، المستلم={!r}. "
            "المصدر={!r}، الملف={!r}.".format(
                expected_version, received_version, source, path
            )
        )
        log_message("[READINESS VERSION MISMATCH] " + message)
        return "error", message

    if expected_pid is not None and received_pid != expected_pid:
        message = (
            "إشارة الجاهزية صادرة من عملية مختلفة: "
            "PID المتوقع={!r}، PID المستلم={!r}. "
            "قد تكون الإشارة من عملية قديمة متبقية.".format(
                expected_pid, received_pid
            )
        )
        log_message("[READINESS PID MISMATCH] " + message)
        return "error", message

    if status == "ready":
        log_message(
            "[READINESS SUCCESS] protocol_id={} | source={} | pid={}".format(
                received_id, source, received_pid
            )
        )
        return "ready", None

    if status == "error":
        error_text = data.get("error") or "خطأ غير معروف أثناء تهيئة التطبيق."
        message = (
            "أبلغ app.py عن فشل التهيئة. protocol_id={!r} | "
            "source={!r} | error={} ".format(
                received_id, source, error_text
            )
        )
        log_message("[READINESS APP ERROR] " + message)
        return "error", message

    _readiness_issue_once(
        "[READINESS UNKNOWN STATUS] expected_id={!r} | received_id={!r} | "
        "status={!r} | source={!r} | file={!r}".format(
            expected_id, received_id, status, source, path
        )
    )
    return None, None


# ============================================================
# Port selection and HTTP health
# ============================================================

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def http_get(url, timeout=3):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 HokamaERP"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def is_streamlit_healthy(host, port):
    try:
        status, health_body = http_get(
            "http://{}:{}/_stcore/health".format(host, port), timeout=2
        )
        if status != 200:
            return False
        health_text = health_body.decode(
            "utf-8", errors="ignore"
        ).strip().lower()
        if health_text not in ("ok", "healthy"):
            return False

        status, page_body = http_get(
            "http://{}:{}/".format(host, port), timeout=4
        )
        if status != 200:
            return False
        html_text = page_body.decode("utf-8", errors="ignore").lower()
        return "<html" in html_text or "<!doctype html>" in html_text
    except Exception:
        return False


def wait_for_http_health(server, host, port, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not server.is_alive():
            log_message(
                "Streamlit process exited before HTTP readiness. exitcode={}".format(
                    server.exitcode
                )
            )
            return False
        if is_streamlit_healthy(host, port):
            return True
        time.sleep(HEALTH_CHECK_INTERVAL)
    return False


def wait_for_readiness(server, host, port, timeout=APP_READINESS_TIMEOUT):
    deadline = time.monotonic() + timeout
    last_health_check = 0
    while time.monotonic() < deadline:
        if not server.is_alive():
            message = (
                "توقفت عملية Streamlit قبل اكتمال التهيئة. exitcode={}".format(
                    server.exitcode
                )
            )
            log_message("[READINESS PROCESS EXIT] " + message)
            return False, message

        status, error_message = read_readiness_file(expected_pid=server.pid)
        if status == "ready":
            return True, None
        if status == "error":
            return False, error_message

        now = time.monotonic()
        if now - last_health_check >= 3:
            last_health_check = now
            if not is_streamlit_healthy(host, port):
                log_message(
                    "Warning: Streamlit HTTP health check failed while "
                    "waiting for app readiness."
                )
        time.sleep(READY_CHECK_INTERVAL)

    path = get_readiness_file()
    message = (
        "انتهت مهلة انتظار إشارة الجاهزية من app.py.\n"
        "Protocol ID المتوقع: {}\n"
        "ملف الجاهزية المتوقع: {}\n"
        "راجع startup.log وstreamlit.log لمعرفة المرحلة التي توقفت عندها التهيئة."
    ).format(PROTOCOL_ID, path)
    log_message("[READINESS TIMEOUT] " + message.replace("\n", " | "))
    return False, message


# ============================================================
# Google Chrome discovery and monitoring
# ============================================================

def find_chrome():
    candidates = []
    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "ProgramW6432"):
        root = os.getenv(env_name)
        if root:
            candidates.append(
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
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


def chrome_process_using_profile(chrome_profile):
    if sys.platform != "win32":
        return None
    try:
        profile_text = str(chrome_profile)
        encoded_profile = base64.b64encode(
            profile_text.encode("utf-8")
        ).decode("ascii")
        powershell_script = (
            "$targetProfile = [Text.Encoding]::UTF8.GetString("
            "[Convert]::FromBase64String('" + encoded_profile + "')); "
            "$processes = Get-CimInstance Win32_Process "
            "-Filter \"Name = 'chrome.exe'\" "
            "-ErrorAction SilentlyContinue; "
            "$match = $processes | Where-Object { "
            "$_.CommandLine -and $_.CommandLine.Contains($targetProfile) "
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
        log_message("Chrome process check failed: {}".format(exc))
        return None


def launch_chrome(chrome_exe, chrome_profile, url):
    browser_args = [
        chrome_exe,
        "--user-data-dir={}".format(chrome_profile),
        "--app={}".format(url),
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
    log_message("Chrome launcher process started: {}".format(process.pid))
    return process


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
        log_message("Server shutdown error:\n" + traceback.format_exc())


def monitor_application(server, chrome_profile):
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
            missing_since = None
        time.sleep(MONITOR_INTERVAL)


# ============================================================
# Streamlit startup with retries
# ============================================================

def start_streamlit_with_retry(app_path):
    for attempt in range(1, STARTUP_RETRIES + 1):
        port = find_free_port()
        cleanup_readiness_file()
        log_message(
            "Starting Streamlit attempt {}/{}, port={}, protocol_id={}".format(
                attempt, STARTUP_RETRIES, port, PROTOCOL_ID
            )
        )

        server = multiprocessing.Process(
            target=run_streamlit,
            args=(port, str(app_path), PROTOCOL_ID),
            name="HokamaERP-Streamlit",
            daemon=False,
        )
        server.start()
        log_message(
            "Streamlit process started: pid={} | protocol_id={} | port={}".format(
                server.pid, PROTOCOL_ID, port
            )
        )

        http_ready = wait_for_http_health(
            server, HOST, port, HTTP_STARTUP_TIMEOUT
        )
        if http_ready:
            log_message("Streamlit HTTP is healthy on port {}.".format(port))
            return server, port, None

        log_message(
            "Streamlit HTTP startup attempt {}/{} failed.".format(
                attempt, STARTUP_RETRIES
            )
        )
        stop_server(server)
        cleanup_readiness_file()
        if attempt < STARTUP_RETRIES:
            time.sleep(1)

    return None, None, "فشل تشغيل خادم Streamlit بعد عدة محاولات."


# ============================================================
# Main
# ============================================================

def main():
    server = None
    mutex_token = None
    owns_instance = False
    try:
        mutex_token, already_running, mutex_error = (
            acquire_single_instance_mutex()
        )

        if already_running:
            show_error(
                APP_NAME,
                "برنامج Hokama ERP يعمل بالفعل.\n\n"
                "يرجى إغلاق النظام الحالي أولاً قبل تشغيل نسخة أخرى.",
            )
            return 2

        if mutex_error:
            log_message("[MUTEX ERROR] " + str(mutex_error))
            show_error(
                APP_NAME,
                "تعذر التحقق من عدم تشغيل نسخة أخرى من النظام.\n\n"
                "تم إيقاف التشغيل لمنع فتح نسختين.\n\n"
                + str(mutex_error),
            )
            return 1

        # From this point, this launcher owns the single-instance slot.
        # Only its owner may clean up the shared readiness file.
        owns_instance = True

        log_message("=" * 60)
        log_message("Starting Hokama ERP Desktop (Google Chrome).")
        log_message(
            "[PROTOCOL CONFIG] protocol_id={} | protocol_version={} | "
            "readiness_file={}".format(
                PROTOCOL_ID, PROTOCOL_VERSION, get_readiness_file()
            )
        )

        cleanup_readiness_file()

        app_path = (get_base_path() / "app.py").resolve()
        if not app_path.is_file():
            message = (
                "لم يتم العثور على ملف التطبيق:\n{}\n\n"
                "تأكد من تضمين app.py عند بناء EXE.".format(app_path)
            )
            log_message("ERROR: " + message)
            show_error(APP_NAME, message)
            return 1

        chrome_exe = find_chrome()
        if not chrome_exe:
            message = (
                "لم يتم العثور على Google Chrome.\n"
                "ثبّت Google Chrome ثم أعد تشغيل Hokama ERP."
            )
            log_message("ERROR: " + message)
            show_error(APP_NAME, message)
            return 1

        data_dir = get_data_dir()
        chrome_profile = data_dir / "ChromeProfile"
        chrome_profile.mkdir(parents=True, exist_ok=True)
        logs_dir = get_logs_dir()

        log_message("Application: {}".format(app_path))
        log_message("Chrome: {}".format(chrome_exe))
        log_message("Chrome profile: {}".format(chrome_profile))

        server, port, error_msg = start_streamlit_with_retry(app_path)
        if server is None:
            detail = read_streamlit_log_tail()
            message = (
                "{}\n\nآخر سجل Streamlit:\n{}\n\nملفات السجل:\n{}".format(
                    error_msg, detail, logs_dir
                )
            )
            log_message("ERROR: " + message)
            show_error("تعذّر تشغيل Hokama ERP", message)
            return 1

        url = "http://{}:{}".format(HOST, port)
        log_message("Local URL: {}".format(url))
        launch_chrome(chrome_exe, chrome_profile, url)

        ready, readiness_error = wait_for_readiness(
            server=server,
            host=HOST,
            port=port,
            timeout=APP_READINESS_TIMEOUT,
        )
        if not ready:
            detail = read_streamlit_log_tail()
            message = (
                "تعذّر إكمال تهيئة التطبيق:\n\n{}\n\n"
                "آخر سجل Streamlit:\n{}\n\nملفات السجل:\n{}".format(
                    readiness_error, detail, logs_dir
                )
            )
            log_message("ERROR: " + message)
            show_error("تعذّر تشغيل Hokama ERP", message)
            return 1

        log_message("Application readiness confirmed successfully.")
        monitor_ok = monitor_application(server, chrome_profile)
        if not monitor_ok:
            detail = read_streamlit_log_tail()
            show_error(
                APP_NAME,
                "توقف خادم التطبيق.\n\nآخر سجل Streamlit:\n{}\n\n"
                "ملفات السجل:\n{}".format(detail, logs_dir),
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
            "حدث خطأ أثناء تشغيل التطبيق.\n\nراجع السجل:\n{}".format(
                get_logs_dir() / "startup.log"
            ),
        )
        return 1

    finally:
        stop_server(server)
        if owns_instance:
            try:
                cleanup_readiness_file()
            except Exception:
                pass
            log_message("Hokama ERP launcher stopped.")
        release_single_instance_mutex(mutex_token)


if __name__ == "__main__":
    raise SystemExit(main())
