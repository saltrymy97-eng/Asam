# app_desktop.py — Hokama ERP v44.0 (Developer Edition + Manual Firefox)
# Firefox + Persistent Profile + DevTools Enabled + Right-Click Enabled
# لا يغيّر الواجهات أو الخدمات أو قاعدة البيانات

import os
import sys
import time
import socket
import multiprocessing
import asyncio
import traceback
import urllib.request
import subprocess
import webbrowser
from pathlib import Path

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

from streamlit.web import cli as stcli


def get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        path = Path(local_appdata) / "HokamaERP"
    else:
        path = Path.home() / "HokamaERP"

    path.mkdir(parents=True, exist_ok=True)
    return path


def log_message(message):
    try:
        log_dir = get_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        with open(
            log_dir / "startup.log",
            "a",
            encoding="utf-8"
        ) as log:
            log.write(
                time.strftime("%Y-%m-%d %H:%M:%S")
                + " | " + str(message) + "\n"
            )
    except Exception:
        pass


def find_free_port():
    with socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def is_streamlit_ready(host, port):
    try:
        url = f"http://{host}:{port}/_stcore/health"
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def run_streamlit(port, app_path):
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass

    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        asyncio.set_event_loop(asyncio.new_event_loop())

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

    except SystemExit:
        pass
    except Exception:
        log_message("Streamlit error:\n" + traceback.format_exc())


def find_firefox(base_path):
    candidates = [
        # 🎯 1. البحث في مجلد _internal (الذي سنضع فيه Firefox يدوياً)
        os.path.join(base_path, "_internal", "firefox_portable", "firefox.exe"),
        # 🎯 2. البحث في المجلد الرئيسي (خطة بديلة)
        os.path.join(base_path, "firefox_portable", "firefox.exe"),
        # 🎯 3. البحث في مسارات التثبيت العادية
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ]

    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        candidates.append(
            os.path.join(
                local_appdata,
                "Mozilla Firefox",
                "firefox.exe"
            )
        )

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


def main():
    base_path = get_base_path()
    app_dir = get_app_dir()
    app_path = os.path.join(base_path, "app.py")

    if not os.path.isfile(app_path):
        log_message(f"ERROR: app.py not found: {app_path}")
        raise FileNotFoundError(
            f"لم يتم العثور على app.py: {app_path}"
        )

    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    log_message("Starting Hokama ERP (Manual Firefox Edition)")
    log_message(f"App path: {app_path}")
    log_message(f"URL: {url}")

    server = multiprocessing.Process(
        target=run_streamlit,
        args=(port, app_path),
        daemon=True
    )
    server.start()

    ready = False
    for _ in range(120):
        if is_streamlit_ready(host, port):
            ready = True
            break

        if not server.is_alive():
            break

        time.sleep(0.5)

    if not ready:
        log_message("ERROR: Streamlit did not become ready")
        if server.is_alive():
            server.terminate()
            server.join(timeout=3)
        raise RuntimeError(
            "لم يبدأ خادم النظام. راجع startup.log"
        )

    log_message("Streamlit is ready")

    browser_exe = find_firefox(base_path)

    if not browser_exe:
        log_message(
            "Firefox not found; opening default browser"
        )
        webbrowser.open(url)

        try:
            while server.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            if server.is_alive():
                server.terminate()
                server.join(timeout=3)
        return

    # ملف تعريف ثابت ودائم لهذا المستخدم
    profile_dir = get_data_dir() / "FirefoxProfile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    # 🎯 إعدادات ملف التعريف (أدوات المطور + النقر بزر الفأرة الأيمن)
    user_js = profile_dir / "user.js"
    preferences = [
        'user_pref("browser.shell.checkDefaultBrowser", false);',
        'user_pref("browser.startup.homepage_override.mstone", "ignore");',
        'user_pref("startup.homepage_welcome_url", "");',
        'user_pref("startup.homepage_welcome_url.additional", "");',
        'user_pref("browser.aboutwelcome.enabled", false);',
        'user_pref("browser.startup.firstrunSkipsHomepage", true);',
        # 🎯 تفعيل أدوات المطور (DevTools)
        'user_pref("devtools.chrome.enabled", true);',
        'user_pref("devtools.debugger.remote-enabled", true);',
        'user_pref("devtools.selfxss.count", 100);',
        'user_pref("devtools.inspector.enabled", true);',
        # 🎯 تفعيل قائمة النقر بزر الفأرة الأيمن
        'user_pref("dom.event.contextmenu.enabled", true);',
        'user_pref("browser.tabs.loadInBackground", true);',
        'user_pref("privacy.popups.disable_from_plugins", 3);',
    ]

    try:
        user_js.write_text(
            "\n".join(preferences) + "\n",
            encoding="utf-8"
        )
    except Exception:
        log_message("WARNING: Could not write user.js")

    browser_args = [
        browser_exe,
        "-no-remote",
        "-profile", str(profile_dir),
        # 🎯 تم حذف -kiosk لكي يعمل النقر بزر الفأرة الأيمن و F12
        url,
    ]

    try:
        log_message(f"Launching Firefox: {browser_exe}")

        with open(
            get_data_dir() / "logs" / "firefox.log",
            "a",
            encoding="utf-8"
        ) as browser_log:
            browser = subprocess.Popen(
                browser_args,
                cwd=os.path.dirname(browser_exe),
                stdout=browser_log,
                stderr=subprocess.STDOUT,
            )

        log_message(f"Firefox process started: {browser.pid}")

        # إبقاء التطبيق حيًا ما دامت نافذة Firefox تعمل
        while browser.poll() is None:
            if not server.is_alive():
                log_message("ERROR: Streamlit process stopped")
                break
            time.sleep(1)

        log_message(
            f"Firefox exited with code: {browser.poll()}"
        )

    except Exception:
        log_message("Firefox launch error:\n" + traceback.format_exc())
        raise
    finally:
        if server.is_alive():
            server.terminate()
            server.join(timeout=3)
        log_message("Hokama ERP launcher stopped")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
