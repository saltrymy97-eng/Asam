# app_desktop.py
# Hokama ERP — Windows Desktop Launcher
# Streamlit + Microsoft Edge App Mode

import asyncio
import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"


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
        with (log_dir / "startup.log").open("a", encoding="utf-8") as log:
            log.write(
                time.strftime("%Y-%m-%d %H:%M:%S")
                + " | " + str(message) + "\n"
            )
    except Exception:
        pass


def show_error(title, message):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass
    print(f"{title}: {message}", file=sys.stderr)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def is_streamlit_ready(host, port):
    url = f"http://{host}:{port}/_stcore/health"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, TimeoutError):
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
                "--server.address=127.0.0.1",
                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",
                "--browser.gatherUsageStats=false",
                "--global.developmentMode=false",
            ]

            stcli.main()

    except SystemExit:
        pass
    except Exception:
        log_message("Streamlit child error:\n" + traceback.format_exc())


def find_edge():
    candidates = []

    for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES", "ProgramW6432"):
        root = os.getenv(env_name)
        if root:
            candidates.append(
                Path(root) / "Microsoft" / "Edge"
                / "Application" / "msedge.exe"
            )

    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        candidates.append(
            Path(local_appdata) / "Microsoft" / "Edge"
            / "Application" / "msedge.exe"
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
        log_message("Server shutdown error:\n" + traceback.format_exc())


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
            show_error("Hokama ERP", message)
            return 1

        edge_exe = find_edge()

        if not edge_exe:
            message = (
                "لم يتم العثور على Microsoft Edge.\n"
                "ثبّت Edge ثم شغّل Hokama ERP مرة أخرى."
            )
            log_message("ERROR: " + message)
            show_error("Hokama ERP", message)
            return 1

        host = "127.0.0.1"
        port = find_free_port()
        url = f"http://{host}:{port}"

        data_dir = get_data_dir()
        logs_dir = data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        edge_profile = data_dir / "EdgeProfile"
        edge_profile.mkdir(parents=True, exist_ok=True)

        log_message("=" * 55)
        log_message("Starting Hokama ERP Desktop")
        log_message(f"Application: {app_path}")
        log_message(f"Edge: {edge_exe}")
        log_message(f"Local URL: {url}")

        server = multiprocessing.Process(
            target=run_streamlit,
            args=(port, str(app_path)),
            name="HokamaERP-Streamlit",
            daemon=True,
        )
        server.start()

        ready = False
        deadline = time.monotonic() + 60

        while time.monotonic() < deadline:
            if is_streamlit_ready(host, port):
                ready = True
                break

            if not server.is_alive():
                break

            time.sleep(0.4)

        if not ready:
            log_message("ERROR: Streamlit failed to become ready")

            detail = ""
            streamlit_log = logs_dir / "streamlit.log"

            try:
                if streamlit_log.exists():
                    detail = (
                        "\n\nآخر سجل Streamlit:\n"
                        + streamlit_log.read_text(
                            encoding="utf-8",
                            errors="replace"
                        )[-2500:]
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

        log_message("Streamlit health check passed")

        browser_args = [
            edge_exe,
            f"--user-data-dir={edge_profile}",
            f"--app={url}",
            "--start-maximized",
            "--no-first-run",
            "--disable-background-mode",
            "--disable-features=Translate",
            "--force-color-profile=srgb",
        ]

        edge_log_path = logs_dir / "edge.log"
        log_message("Launching Edge in app mode")

        with edge_log_path.open("a", encoding="utf-8") as edge_log:
            browser = subprocess.Popen(
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

        log_message(f"Edge process started: {browser.pid}")

        while browser.poll() is None:
            if not server.is_alive():
                log_message("ERROR: Streamlit process stopped")

                show_error(
                    "Hokama ERP",
                    "توقف خادم التطبيق. راجع ملفات السجل داخل:\n"
                    f"{logs_dir}",
                )
                break

            time.sleep(0.5)

        log_message(f"Edge exited with code {browser.poll()}")
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
            f"راجع السجل:\n{get_data_dir() / 'logs' / 'startup.log'}",
        )
        return 1

    finally:
        stop_server(server)
        log_message("Hokama ERP launcher stopped")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
