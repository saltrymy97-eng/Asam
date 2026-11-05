# -*- coding: utf-8 -*-
"""Process entry point for running Streamlit in Hokama ERP.

Keep run_streamlit at module scope. On Windows, multiprocessing uses spawn;
the child process must be able to import this module and resolve the process
 target without depending on a function defined in the frozen __main__ module.
"""

import asyncio
import os
import sys
import traceback
from pathlib import Path

APP_DATA_DIR_NAME = "HokamaERP"
LOGS_DIR_NAME = "logs"
LOG_FILE_NAME = "streamlit.log"
HOST = "127.0.0.1"
PROTOCOL_VERSION = 1


def _get_logs_dir() -> Path:
    """Return the same per-user log directory used by app_desktop.py."""
    root = Path(os.getenv("LOCALAPPDATA") or Path.home())
    logs_dir = root / APP_DATA_DIR_NAME / LOGS_DIR_NAME
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _append_startup_log(message: str) -> None:
    """Write child-process details to the launcher's startup log."""
    try:
        root = Path(os.getenv("LOCALAPPDATA") or Path.home())
        logs_dir = root / APP_DATA_DIR_NAME / LOGS_DIR_NAME
        logs_dir.mkdir(parents=True, exist_ok=True)

        with (logs_dir / "startup.log").open("a", encoding="utf-8") as log:
            log.write(str(message).rstrip() + "\n")

    except Exception:
        # Logging must never mask the original startup exception.
        pass


def run_streamlit(port: int, app_path: str, startup_id: str) -> None:
    """Run the Streamlit app in a dedicated multiprocessing child process."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        # Set readiness identity before importing Streamlit or executing app.py.
        os.environ["HOKAMA_STARTUP_ID"] = str(startup_id)
        os.environ["HOKAMA_READINESS_PROTOCOL"] = str(PROTOCOL_VERSION)

        app_file = Path(app_path).expanduser().resolve()
        app_root = app_file.parent

        if not app_file.is_file():
            raise FileNotFoundError(
                f"Streamlit app file does not exist: {app_file}"
            )

        # app.py imports project modules such as database, ui, and services.
        app_root_text = str(app_root)
        if app_root_text not in sys.path:
            sys.path.insert(0, app_root_text)

        # Preserve the launcher's relative-path behavior.
        os.chdir(app_root)

        # Streamlit/Tornado on Windows should use the selector event loop policy.
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )

        asyncio.set_event_loop(asyncio.new_event_loop())

        log_path = _get_logs_dir() / LOG_FILE_NAME

        with log_path.open(
            "a",
            encoding="utf-8",
            buffering=1,
        ) as child_log:
            sys.stdout = child_log
            sys.stderr = child_log

            child_log.write("\n" + "=" * 70 + "\n")
            child_log.write(f"Streamlit child startup: {startup_id}\n")
            child_log.write(f"Port: {port}\n")
            child_log.write(f"Host: {HOST}\n")
            child_log.write(f"Application: {app_file}\n")
            child_log.write(f"Working directory: {app_root}\n")
            child_log.write("=" * 70 + "\n")

            from streamlit.web import cli as stcli

            sys.argv = [
                "streamlit",
                "run",
                str(app_file),
                f"--server.port={int(port)}",
                f"--server.address={HOST}",
                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",
                "--browser.gatherUsageStats=false",
                "--global.developmentMode=false",
                # Dark is the default; the user can still change the theme
                # from Streamlit's settings menu when the UI exposes it.
                "--theme.base=dark",
                # Keep the viewer toolbar mode from the launcher version.
                "--client.toolbarMode=viewer",
            ]

            child_log.write("Starting Streamlit CLI.\n")
            child_log.flush()
            stcli.main()

    except SystemExit as exc:
        # Streamlit's CLI can terminate through SystemExit. Log its status;
        # the parent notices a stopped child if startup did not complete.
        message = f"Streamlit CLI exited with code: {exc.code}"
        _append_startup_log(message)

        try:
            log_path = _get_logs_dir() / LOG_FILE_NAME
            with log_path.open("a", encoding="utf-8") as log:
                log.write(message + "\n")
        except Exception:
            pass

    except BaseException:
        error_text = traceback.format_exc()
        _append_startup_log(
            "Streamlit child fatal error:\n" + error_text
        )

        try:
            log_path = _get_logs_dir() / LOG_FILE_NAME
            with log_path.open("a", encoding="utf-8") as log:
                log.write("Streamlit child fatal error:\n")
                log.write(error_text + "\n")
        except Exception:
            pass

        raise

    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
