# app_desktop.py — مشغل نظام حوكمة ERP كتطبيق سطح مكتب (v4.0)
# ✅ Edge App Mode + منفذ ذكي + انتظار HTTP + مظهر تطبيق ويندوز كامل

from __future__ import annotations

import asyncio
import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional, Set, Tuple


# ---------------------------------------------------------------------------
# إعدادات
# ---------------------------------------------------------------------------
APP_TITLE = "Hukooma ERP"
PORT_START = 8501
PORT_END = 8600
MAX_PORT_ATTEMPTS = 8
SERVER_STARTUP_TIMEOUT = 45
HTTP_POLL_INTERVAL = 0.4
HTTP_REQUEST_TIMEOUT = 1.5
EDGE_WINDOW_SIZE = "1440,900"
EDGE_WINDOW_POSITION = "50,50"


# ---------------------------------------------------------------------------
# المسارات والتسجيل
# ---------------------------------------------------------------------------
def get_runtime_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_app_path() -> str:
    runtime_dir = get_runtime_dir()
    candidates = []
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "app.py"))
    candidates.append(os.path.join(runtime_dir, "app.py"))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(candidates[0])


def _log_candidates():
    yield os.path.join(get_runtime_dir(), "app_error_log.txt")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    yield os.path.join(local_app_data, "HukoomaERP", "logs", "app_error_log.txt")


def log_message(level: str, context: str, details: str = "") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = f"\n[{timestamp}] [{level}] {context}\n"
    if details:
        record += details.rstrip() + "\n"
    for path in _log_candidates():
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as log_file:
                log_file.write(record)
            return
        except OSError:
            continue


def log_exception(context: str) -> None:
    log_message("ERROR", context, traceback.format_exc())


def show_error(message: str, title: str = APP_TITLE) -> None:
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        else:
            sys.stderr.write(f"{title}: {message}\n")
    except Exception:
        log_message("ERROR", "تعذّر عرض رسالة الخطأ للمستخدم", message)


# ---------------------------------------------------------------------------
# المنفذ وفحص HTTP
# ---------------------------------------------------------------------------
def find_free_port(
    excluded_ports: Optional[Set[int]] = None,
    start: int = PORT_START,
    end: int = PORT_END,
) -> Optional[int]:
    excluded = excluded_ports or set()
    for port in range(start, end + 1):
        if port in excluded:
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    return None


def wait_for_streamlit(process: multiprocessing.Process, port: int, timeout: int) -> Tuple[bool, str]:
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.monotonic() + timeout
    last_error = "لم تصل استجابة HTTP ناجحة قبل انتهاء المهلة."

    while time.monotonic() < deadline:
        if process.exitcode is not None:
            return False, f"انتهت عملية Streamlit مبكراً برمز خروج: {process.exitcode}."
        try:
            request = urllib.request.Request(
                health_url,
                headers={"User-Agent": "HukoomaERP-DesktopLauncher/1.0"},
            )
            with urllib.request.urlopen(request, timeout=HTTP_REQUEST_TIMEOUT) as response:
                if response.status == 200:
                    return True, "Streamlit جاهز عبر HTTP."
                last_error = f"استجاب فحص الصحة برمز HTTP {response.status}."
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(HTTP_POLL_INTERVAL)

    if process.exitcode is not None:
        return False, f"انتهت عملية Streamlit برمز خروج: {process.exitcode}."
    return False, f"انتهت مهلة الانتظار ({timeout} ثانية). آخر نتيجة: {last_error}"


# ---------------------------------------------------------------------------
# عملية Streamlit
# ---------------------------------------------------------------------------
def run_streamlit(port: int, app_path: str) -> None:
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except OSError:
        pass

    try:
        runtime_dir = get_runtime_dir()
        os.chdir(runtime_dir)
        os.makedirs(os.path.join(runtime_dir, "data"), exist_ok=True)

        if not os.path.isfile(app_path):
            raise FileNotFoundError(f"لم يتم العثور على ملف التطبيق: {app_path}")

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.set_event_loop(asyncio.new_event_loop())

        from streamlit.web import cli as stcli

        sys.argv = [
            "streamlit", "run", app_path,
            f"--server.port={port}",
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--server.allowRunOnSave=false",
            "--server.fileWatcherType=none",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false",
        ]

        stcli.main()

    except SystemExit as exc:
        if exc.code not in (None, 0):
            log_message("ERROR", "انتهى Streamlit برمز خطأ", f"Exit code: {exc.code}")
        raise
    except BaseException:
        log_exception("حدث استثناء داخل عملية Streamlit")
        raise


def stop_process(process: Optional[multiprocessing.Process], timeout: float = 5.0) -> None:
    if process is None:
        return
    try:
        if process.is_alive():
            process.terminate()
            process.join(timeout=timeout)
        if process.is_alive():
            kill_method = getattr(process, "kill", None)
            if callable(kill_method):
                kill_method()
            else:
                process.terminate()
            process.join(timeout=2)
    except (AssertionError, OSError, ValueError):
        log_exception("حدث خطأ أثناء إيقاف عملية Streamlit")


def start_streamlit_with_retries(app_path: str) -> Tuple[Optional[multiprocessing.Process], Optional[int]]:
    tried_ports: Set[int] = set()

    for attempt in range(1, MAX_PORT_ATTEMPTS + 1):
        port = find_free_port(excluded_ports=tried_ports)
        if port is None:
            log_message(
                "ERROR", "لم يتم العثور على منفذ متاح",
                f"النطاق المفحوص: {PORT_START}-{PORT_END}; المحاولة: {attempt}/{MAX_PORT_ATTEMPTS}",
            )
            break

        tried_ports.add(port)
        process = multiprocessing.Process(
            target=run_streamlit,
            args=(port, app_path),
            name="HukoomaERP-Streamlit",
            daemon=False,
        )

        try:
            process.start()
        except Exception:
            log_exception(f"تعذّر إنشاء عملية Streamlit على المنفذ {port}")
            stop_process(process)
            continue

        ready, message = wait_for_streamlit(process, port, SERVER_STARTUP_TIMEOUT)
        if ready:
            log_message("INFO", "بدأ Streamlit بنجاح", f"Port: {port}\nURL: http://127.0.0.1:{port}")
            return process, port

        log_message(
            "WARNING",
            f"فشلت محاولة تشغيل Streamlit {attempt}/{MAX_PORT_ATTEMPTS} على المنفذ {port}",
            message,
        )
        stop_process(process)

    return None, None


# ---------------------------------------------------------------------------
# Microsoft Edge App Mode (لتطبيق ويندوز حقيقي)
# ---------------------------------------------------------------------------
def find_edge_executable() -> Optional[str]:
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")

    candidates = [
        os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    if local_app_data:
        candidates.append(
            os.path.join(local_app_data, "Microsoft", "Edge", "Application", "msedge.exe")
        )

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return shutil.which("msedge.exe") or shutil.which("msedge")


def launch_edge_app(url: str) -> Tuple[subprocess.Popen, str]:
    """
    ✅ فتح Edge App Mode كتطبيق مستقل.
    - --app: نافذة بدون شريط عناوين أو تبويبات.
    - --user-data-dir: جلسة معزولة (لا تتأثر بجلسات Edge الأخرى).
    - --disable-*: إخفاء قوائم المتصفح وميزات لا يحتاجها المستخدم.
    - --enable-features=UseOzonePlatform: عرض كتطبيق أصلي.
    """
    if sys.platform != "win32":
        raise OSError("مشغل Edge App Mode مخصص لنظام Windows.")

    edge_exe = find_edge_executable()
    if not edge_exe:
        raise FileNotFoundError(
            "لم يتم العثور على Microsoft Edge. ثبّت Edge ثم أعد تشغيل النظام."
        )

    profile_dir = tempfile.mkdtemp(prefix="HukoomaERP_Edge_")

    args = [
        edge_exe,
        f"--app={url}",
        f"--user-data-dir={profile_dir}",
        f"--window-size={EDGE_WINDOW_SIZE}",
        f"--window-position={EDGE_WINDOW_POSITION}",
        # ✅ مظهر تطبيق أصلي
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "--disable-features=Translate,TranslateUI,msEdgeIdentity,msImplicitSignin",
        "--disable-sync",
        "--disable-extensions",
        "--disable-plugins-discovery",
        "--disable-component-update",
        "--disable-popup-blocking",
        "--disable-pinch",
        "--disable-prompt-on-repost",
        "--disable-web-security",
        "--hide-crash-restore-bubble",
        "--no-service-autorun",
        "--password-store=basic",
        "--use-mock-keychain",
        # ✅ إخفاء كل ما يشير إلى أنه متصفح
        "--kiosk-printing",
        "--start-maximized",
        "--disable-tab-for-desktop-share",
        "--disable-default-apps",
        "--disable-client-side-phishing-detection",
    ]

    try:
        browser_process = subprocess.Popen(args, close_fds=True)
        log_message("INFO", "تم تشغيل Edge App Mode", f"Executable: {edge_exe}\nURL: {url}")
        return browser_process, profile_dir
    except Exception:
        log_exception("فشل تشغيل Microsoft Edge App Mode")
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise


def stop_edge_process_tree(process: Optional[subprocess.Popen]) -> None:
    if process is None or process.poll() is not None:
        return

    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            process.wait(timeout=3)
            return
        except Exception:
            log_exception("تعذّر إيقاف شجرة عمليات Edge باستخدام taskkill")

    try:
        process.terminate()
        process.wait(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            log_exception("تعذّر إيقاف عملية Edge")


# ---------------------------------------------------------------------------
# نقطة التشغيل الرئيسية
# ---------------------------------------------------------------------------
def main() -> int:
    if sys.platform != "win32":
        message = "هذا الملف مُعدّ لتشغيل نظام حوكمة ERP على Windows باستخدام Microsoft Edge."
        log_message("ERROR", "نظام تشغيل غير مدعوم", sys.platform)
        show_error(message)
        return 1

    runtime_dir = get_runtime_dir()
    app_path = get_app_path()

    if not os.path.isfile(app_path):
        message = (
            "لم يتم العثور على app.py.\n\n"
            f"المسار الذي تم فحصه:\n{app_path}\n\n"
            "تأكد من تضمين app.py في إعدادات بناء EXE أو وضعه بجانب المشغّل."
        )
        log_message("ERROR", "ملف app.py غير موجود", app_path)
        show_error(message)
        return 1

    try:
        os.chdir(runtime_dir)
        os.makedirs(os.path.join(runtime_dir, "data"), exist_ok=True)
    except OSError:
        log_exception("تعذّر تجهيز مجلد التشغيل أو مجلد data")

    server_process: Optional[multiprocessing.Process] = None
    edge_process: Optional[subprocess.Popen] = None
    edge_profile_dir: Optional[str] = None

    try:
        server_process, port = start_streamlit_with_retries(app_path)
        if server_process is None or port is None:
            message = (
                "تعذّر تشغيل خادم النظام بعد عدة محاولات.\n\n"
                "راجع ملف app_error_log.txt لمعرفة السبب."
            )
            show_error(message)
            return 1

        url = f"http://127.0.0.1:{port}"

        try:
            edge_process, edge_profile_dir = launch_edge_app(url)
        except Exception as exc:
            log_message("ERROR", "تعذّر فتح نافذة Edge", f"{type(exc).__name__}: {exc}")
            show_error(
                "تم تشغيل خادم النظام، لكن تعذّر فتح نافذة Microsoft Edge.\n\n"
                f"التفاصيل: {exc}\n\n"
                "تأكد من تثبيت Edge، ثم راجع app_error_log.txt."
            )
            return 1

        edge_process.wait()
        log_message("INFO", "أُغلقت نافذة Edge App Mode", f"Exit code: {edge_process.returncode}")
        return 0

    except KeyboardInterrupt:
        log_message("INFO", "تم طلب إيقاف المشغّل", "KeyboardInterrupt")
        return 0
    except Exception:
        log_exception("خطأ غير متوقع في المشغّل الرئيسي")
        show_error("حدث خطأ غير متوقع أثناء تشغيل النظام. راجع app_error_log.txt.")
        return 1
    finally:
        stop_edge_process_tree(edge_process)
        stop_process(server_process)

        if edge_profile_dir:
            for _ in range(5):
                try:
                    shutil.rmtree(edge_profile_dir)
                    break
                except OSError:
                    time.sleep(0.4)
            else:
                log_message(
                    "WARNING",
                    "تعذّر حذف مجلد Edge المؤقت بالكامل",
                    edge_profile_dir,
                )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
