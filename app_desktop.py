# -*- coding: utf-8 -*-

"""Hokama ERP — Windows Desktop Launcher

Streamlit + Google Chrome App Mode
Fixed Readiness Protocol ID: 1111, version: 1
Single-instance protection: Windows named Mutex

HTTP readiness is checked through Streamlit's /_stcore/health endpoint.
Chrome window monitoring uses Chrome DevTools' local /json/list endpoint;
PowerShell/CIM process enumeration is deliberately not used.
"""

# multiprocessing bootstrap for PyInstaller: keep this early.
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
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
CHROME_CLOSE_GRACE = 20
CHROME_DETECTION_TIMEOUT = 60
CHROME_DEVTOOLS_FILENAME = "DevToolsActivePort"

_READINESS_LAST_DIAGNOSTIC = None
_HTTP_LAST_DIAGNOSTIC = None
_CHROME_LAST_DIAGNOSTIC = None


# ============================================================
# Paths
# ============================================================

def get_base_path():
    """Return the directory containing the app's bundled files."""
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
            return path.read_text(encoding="utf-8", errors="replace")[-max_chars:]
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


def log_once(global_name, message):
    """Write a repeated diagnostic only when its text changes."""
    global _READINESS_LAST_DIAGNOSTIC
    global _HTTP_LAST_DIAGNOSTIC
    global _CHROME_LAST_DIAGNOSTIC

    if global_name == "readiness":
        previous = _READINESS_LAST_DIAGNOSTIC
        if message != previous:
            log_message(message)
            _READINESS_LAST_DIAGNOSTIC = message
    elif global_name == "http":
        previous = _HTTP_LAST_DIAGNOSTIC
        if message != previous:
            log_message(message)
            _HTTP_LAST_DIAGNOSTIC = message
    elif global_name == "chrome":
        previous = _CHROME_LAST_DIAGNOSTIC
        if message != previous:
            log_message(message)
            _CHROME_LAST_DIAGNOSTIC = message


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
        create_mutex.argtypes = [
            ctypes.c_void_p,
            ctypes.c_bool,
            ctypes.c_wchar_p,
        ]
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

        # Keep the DLL object and handle alive for the full launcher lifetime.
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
        log_message("Mutex release error:\n" + traceback.format_exc())


# ============================================================
# Fixed readiness file and diagnostics
# ============================================================

def cleanup_readiness_file():
    """Remove the one readiness file before a fresh launch/attempt."""
    path = get_readiness_file()
    try:
        if path.exists():
            path.unlink()
            log_message("Removed stale readiness file: {}".format(path))
        else:
            log_message("No previous readiness file found: {}".format(path))
    except Exception as exc:
        log_message(
            "READINESS CLEANUP FAILED | path={} | error={!r}".format(path, exc)
        )
        raise


def _readiness_issue_once(message):
    log_once("readiness", message)


def read_readiness_file(expected_pid=None):
    """Return ('ready', None), ('error', text), or (None, None).

    The launcher accepts only the fixed protocol, exact JSON types, the
    app.py source marker, and the PID of the current Streamlit child process.
    """
    path = get_readiness_file()
    expected_id = PROTOCOL_ID
    expected_version = PROTOCOL_VERSION

    if not path.is_file():
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

    if not isinstance(data, dict):
        message = "ملف الجاهزية لا يحتوي على كائن JSON صالح: {}".format(path)
        log_message("[READINESS FORMAT ERROR] " + message)
        return "error", message

    received_id = data.get("protocol_id", "<MISSING>")
    received_version = data.get("protocol_version", "<MISSING>")
    status = data.get("status", "<MISSING>")
    source = data.get("source", "<MISSING>")
    received_pid = data.get("pid", "<MISSING>")
    received_error = data.get("error")

    diagnostic = (
        "[READINESS CHECK] expected_id={!r} | received_id={!r} | "
        "expected_version={!r} | received_version={!r} | "
        "expected_pid={!r} | received_pid={!r} | "
        "status={!r} | source={!r} | file={!r}"
    ).format(
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
    log_once("readiness", diagnostic)

    # Enforce exact field types as well as values. In particular, bool must
    # not be accepted as an integer protocol version or process identifier.
    if type(received_id) is not str or received_id != expected_id:
        message = (
            "عدم تطابق معرّف البروتوكول: المتوقع={!r}، المستلم={!r}. "
            "المصدر={!r}، الملف={!r}."
        ).format(expected_id, received_id, source, path)
        log_message("[READINESS ID MISMATCH] " + message)
        return "error", message

    if type(received_version) is not int or received_version != expected_version:
        message = (
            "عدم توافق إصدار البروتوكول: المتوقع={!r}، المستلم={!r}. "
            "المصدر={!r}، الملف={!r}."
        ).format(expected_version, received_version, source, path)
        log_message("[READINESS VERSION MISMATCH] " + message)
        return "error", message

    if type(received_pid) is not int:
        message = "حقل PID مفقود أو غير صحيح في ملف الجاهزية: {!r}.".format(
            received_pid
        )
        log_message("[READINESS PID FORMAT ERROR] " + message)
        return "error", message

    if expected_pid is not None and received_pid != expected_pid:
        message = (
            "إشارة الجاهزية صادرة من عملية مختلفة: PID المتوقع={!r}، "
            "PID المستلم={!r}. قد تكون الإشارة من عملية قديمة متبقية."
        ).format(expected_pid, received_pid)
        log_message("[READINESS PID MISMATCH] " + message)
        return "error", message

    if source != "app.py":
        message = "مصدر إشارة الجاهزية غير صحيح: المتوقع 'app.py' والمستلم {!r}.".format(
            source
        )
        log_message("[READINESS SOURCE MISMATCH] " + message)
        return "error", message

    if status == "ready":
        if received_error is not None:
            message = "إشارة ready يجب أن تحتوي على error=null، والمستلم={!r}.".format(
                received_error
            )
            log_message("[READINESS FIELD ERROR] " + message)
            return "error", message

        log_message(
            "[READINESS SUCCESS] protocol_id={} | protocol_version={} | "
            "source={} | pid={}".format(
                received_id, received_version, source, received_pid
            )
        )
        return "ready", None

    if status == "error":
        error_text = received_error or "خطأ غير معروف أثناء تهيئة التطبيق."
        if not isinstance(error_text, str):
            error_text = repr(error_text)
        message = (
            "أبلغ app.py عن فشل التهيئة. protocol_id={!r} | "
            "protocol_version={!r} | source={!r} | error={}"
        ).format(received_id, received_version, source, error_text)
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
    """GET a local URL directly, bypassing any configured system proxy."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 HokamaERP"}
    )
    # These URLs are loopback-only. Bypass system proxy settings so a proxy
    # cannot intercept requests to the local Streamlit/Chrome endpoints.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return response.status, response.read()


def is_streamlit_healthy(host, port):
    """Check Streamlit's health endpoint without hiding diagnostics."""
    url = "http://{}:{}/_stcore/health".format(host, port)

    try:
        status, health_body = http_get(url, timeout=3)
        health_text = health_body.decode("utf-8", errors="ignore").strip().lower()

        if status != 200:
            log_once(
                "http",
                "[HTTP HEALTH] Unexpected HTTP status {} from {}".format(
                    status, url
                ),
            )
            return False

        # Streamlit normally returns 'ok'. 'healthy' is accepted for
        # compatibility with builds that use that response body.
        if health_text not in ("ok", "healthy"):
            log_once(
                "http",
                "[HTTP HEALTH] Unexpected response from {}: {!r}".format(
                    url, health_text[:300]
                ),
            )
            return False

        global _HTTP_LAST_DIAGNOSTIC
        _HTTP_LAST_DIAGNOSTIC = None
        return True

    except Exception as exc:
        log_once(
            "http",
            "[HTTP HEALTH ERROR] {}: {} | url={}".format(
                type(exc).__name__, exc, url
            ),
        )
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
            log_message(
                "Streamlit HTTP health endpoint is healthy on port {}.".format(port)
            )
            return True

        time.sleep(HEALTH_CHECK_INTERVAL)

    log_message(
        "[HTTP HEALTH TIMEOUT] Streamlit did not answer successfully "
        "within {} seconds on {}:{}".format(timeout, host, port)
    )
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
                log_once(
                    "http",
                    "[HTTP HEALTH] Health check failed while waiting for "
                    "app.py readiness on {}:{}".format(host, port),
                )

        time.sleep(READY_CHECK_INTERVAL)

    path = get_readiness_file()
    message = (
        "انتهت مهلة انتظار إشارة الجاهزية من app.py.\n"
        "Protocol ID المتوقع: {}\n"
        "Protocol version المتوقع: {}\n"
        "ملف الجاهزية المتوقع: {}\n"
        "راجع startup.log وstreamlit.log لمعرفة المرحلة التي توقفت عندها التهيئة."
    ).format(PROTOCOL_ID, PROTOCOL_VERSION, path)
    log_message("[READINESS TIMEOUT] " + message.replace("\n", " | "))
    return False, message


# ============================================================
# Google Chrome discovery and DevTools monitoring
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


def get_chrome_devtools_port(chrome_profile):
    """Read the ephemeral debugging port written by Chrome on startup."""
    active_port_file = Path(chrome_profile) / CHROME_DEVTOOLS_FILENAME

    if not active_port_file.is_file():
        return None

    try:
        lines = active_port_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        if not lines:
            return None

        port = int(lines[0].strip())
        if 1 <= port <= 65535:
            return port
    except (OSError, ValueError, IndexError):
        return None

    return None


def chrome_devtools_request(chrome_profile, endpoint="/json/list", timeout=2):
    """Return (reachable, parsed_json, port) for this Chrome profile."""
    port = get_chrome_devtools_port(chrome_profile)
    if port is None:
        return False, None, None

    url = "http://127.0.0.1:{}{}".format(port, endpoint)
    try:
        status, body = http_get(url, timeout=timeout)
        if status != 200:
            return False, None, port

        parsed = json.loads(body.decode("utf-8", errors="replace"))
        return True, parsed, port
    except Exception:
        return False, None, port


def cleanup_stale_chrome_devtools_file(chrome_profile):
    """Remove a stale DevToolsActivePort file, but preserve a live endpoint."""
    active_port_file = Path(chrome_profile) / CHROME_DEVTOOLS_FILENAME
    if not active_port_file.exists():
        return

    reachable, version_data, port = chrome_devtools_request(
        chrome_profile, endpoint="/json/version", timeout=1.5
    )

    if reachable and isinstance(version_data, dict):
        if version_data.get("Browser") or version_data.get("webSocketDebuggerUrl"):
            log_message(
                "Existing Chrome DevTools endpoint is active on port {}. "
                "Keeping its active-port file.".format(port)
            )
            return

    try:
        active_port_file.unlink()
        log_message("Removed stale Chrome DevTools file: {}".format(active_port_file))
    except OSError as exc:
        log_message(
            "Could not remove Chrome DevTools file {}: {}".format(
                active_port_file, exc
            )
        )


def chrome_process_using_profile(chrome_profile, expected_url):
    """Return True if Hokama's page is open, False if absent, None if unknown.

    This checks Chrome's local DevTools target list and avoids invoking
    PowerShell/Get-CimInstance repeatedly.
    """
    reachable, targets, port = chrome_devtools_request(
        chrome_profile, endpoint="/json/list", timeout=2
    )

    if not reachable:
        return None

    if not isinstance(targets, list):
        log_once(
            "chrome",
            "[CHROME DEVTOOLS] Unexpected target-list response on port {}.".format(
                port
            ),
        )
        return None

    expected_prefix = expected_url.rstrip("/")

    for target in targets:
        if not isinstance(target, dict):
            continue

        target_url = str(target.get("url") or "").strip()
        target_type = str(target.get("type") or "").lower()

        url_matches = (
            target_url == expected_prefix
            or target_url.startswith(expected_prefix + "/")
            or target_url.startswith(expected_prefix + "?")
            or target_url.startswith(expected_prefix + "#")
        )

        if url_matches and target_type in ("page", "webview", ""):
            global _CHROME_LAST_DIAGNOSTIC
            _CHROME_LAST_DIAGNOSTIC = None
            return True

    # A successful DevTools response with no matching app page means the
    # Chrome debugging server is alive, but the Hokama page is not listed.
    return False


def launch_chrome(chrome_exe, chrome_profile, url):
    chrome_profile = Path(chrome_profile)
    chrome_profile.mkdir(parents=True, exist_ok=True)

    # Clear an old marker only if it does not point to a live debugging server.
    cleanup_stale_chrome_devtools_file(chrome_profile)

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
        # Chrome records a random local debugging port in DevToolsActivePort.
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
    ]

    chrome_log_path = get_logs_dir() / "chrome.log"
    log_message("Launching Google Chrome App Mode with local DevTools monitoring.")

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


def monitor_application(server, chrome_profile, app_url):
    """Keep Streamlit alive while the Hokama Chrome app page is open."""
    log_message("Monitoring Hokama ERP Chrome app through local DevTools.")
    first_detection = False
    missing_since = None
    detection_deadline = time.monotonic() + CHROME_DETECTION_TIMEOUT

    while True:
        if not server.is_alive():
            log_message("ERROR: Streamlit server process stopped.")
            return False

        chrome_state = chrome_process_using_profile(chrome_profile, app_url)

        if chrome_state is True:
            if not first_detection:
                log_message("Chrome Hokama app page detected through DevTools.")
            first_detection = True
            missing_since = None

        elif chrome_state is False:
            if first_detection:
                if missing_since is None:
                    missing_since = time.monotonic()
                    log_message(
                        "Chrome DevTools is reachable, but the Hokama app page "
                        "is no longer listed; starting close grace period."
                    )
                elif time.monotonic() - missing_since >= CHROME_CLOSE_GRACE:
                    log_message("Chrome Hokama app window closed.")
                    return True
            elif time.monotonic() >= detection_deadline:
                log_message(
                    "WARNING: Hokama app page has not yet been detected by "
                    "Chrome DevTools. Keeping Streamlit alive."
                )
                detection_deadline = time.monotonic() + CHROME_DETECTION_TIMEOUT

        else:
            # None means DevTools is not ready or temporarily unreachable.
            # Before first detection, never interpret that as a closed browser.
            # After detection, require a full grace period before shutdown.
            if first_detection:
                if missing_since is None:
                    missing_since = time.monotonic()
                    log_once(
                        "chrome",
                        "[CHROME DEVTOOLS] Endpoint became unreachable after "
                        "the Hokama page had been detected; checking close grace period.",
                    )
                elif time.monotonic() - missing_since >= CHROME_CLOSE_GRACE:
                    log_message(
                        "Chrome DevTools endpoint stayed unreachable; "
                        "treating the Hokama browser session as closed."
                    )
                    return True

        time.sleep(MONITOR_INTERVAL)


# ============================================================
# Streamlit startup with retries
# ============================================================

def start_streamlit_with_retry(app_path):
    """Start Streamlit and retry on HTTP or app readiness failures."""
    attempt_errors = []

    for attempt in range(1, STARTUP_RETRIES + 1):
        port = find_free_port()
        cleanup_readiness_file()
        log_message(
            "Starting Streamlit attempt {}/{}, port={}, protocol_id={}, "
            "protocol_version={}".format(
                attempt,
                STARTUP_RETRIES,
                port,
                PROTOCOL_ID,
                PROTOCOL_VERSION,
            )
        )

        server = multiprocessing.Process(
            target=run_streamlit,
            args=(port, str(app_path), PROTOCOL_ID, PROTOCOL_VERSION),
            name="HokamaERP-Streamlit",
            daemon=False,
        )
        server.start()
        log_message(
            "Streamlit process started: pid={} | protocol_id={} | "
            "protocol_version={} | port={}".format(
                server.pid, PROTOCOL_ID, PROTOCOL_VERSION, port
            )
        )

        http_ready = wait_for_http_health(
            server, HOST, port, HTTP_STARTUP_TIMEOUT
        )
        if not http_ready:
            attempt_error = (
                "فشل فحص HTTP في المحاولة {} من {} على المنفذ {}."
            ).format(attempt, STARTUP_RETRIES, port)
            attempt_errors.append(attempt_error)
            log_message("Streamlit HTTP startup attempt failed: " + attempt_error)
            stop_server(server)
            cleanup_readiness_file()
            if attempt < STARTUP_RETRIES:
                time.sleep(1)
            continue

        log_message("Streamlit HTTP is healthy on port {}.".format(port))
        app_ready, readiness_error = wait_for_readiness(
            server=server,
            host=HOST,
            port=port,
            timeout=APP_READINESS_TIMEOUT,
        )
        if app_ready:
            log_message(
                "Streamlit app readiness confirmed on attempt {}.".format(attempt)
            )
            return server, port, None

        attempt_error = "فشلت جاهزية التطبيق في المحاولة {} من {}: {}".format(
            attempt, STARTUP_RETRIES, readiness_error
        )
        attempt_errors.append(attempt_error)
        log_message("Streamlit app readiness attempt failed: " + attempt_error)
        stop_server(server)
        cleanup_readiness_file()
        if attempt < STARTUP_RETRIES:
            time.sleep(1)

    return (
        None,
        None,
        "فشل تشغيل Streamlit بعد {} محاولات.\n\n{}".format(
            STARTUP_RETRIES, "\n\n".join(attempt_errors)
        ),
    )


# ============================================================
# Main
# ============================================================

def main():
    server = None
    mutex_token = None
    owns_instance = False

    try:
        mutex_token, already_running, mutex_error = acquire_single_instance_mutex()

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
                "تم إيقاف التشغيل لمنع فتح نسختين.\n\n" + str(mutex_error),
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

        # The retry routine now verifies both HTTP health and app.py readiness.
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

        chrome_process = launch_chrome(chrome_exe, chrome_profile, url)
        log_message(
            "Chrome launch request submitted; launcher_pid={}".format(
                getattr(chrome_process, "pid", None)
            )
        )

        log_message("Application readiness confirmed successfully.")
        monitor_ok = monitor_application(server, chrome_profile, url)

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
