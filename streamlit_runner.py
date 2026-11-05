# -*- coding: utf-8 -*-
"""Process entry point for running Streamlit in Hokama ERP.

This module is intentionally separate from app_desktop.py so Windows
multiprocessing (spawn) and PyInstaller can import the process target.
"""

import asyncio
import os
import sys
import traceback
from pathlib import Path

APP_DATA_DIR_NAME = "HokamaERP"
LOGS_DIR_NAME = "logs"
LOG_FILE_NAME = "streamlit.log"
STARTUP_LOG_NAME = "startup.log"
HOST = "127.0.0.1"

# Must match app_desktop.py and app.py.
PROTOCOL_ID = "1111"
PROTOCOL_VERSION = 1


def _get_logs_dir() -> Path:
    root = Path(os.getenv("LOCALAPPDATA") or Path.home())
    logs_dir = root / APP_DATA_DIR_NAME / LOGS_DIR_NAME
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _append_startup_log(message: str) -> None:
    try:
        with (_get_logs_dir() / STARTUP_LOG_NAME).open(
            "a", encoding="utf-8"
        ) as log:
            log.write(str(message).rstrip() + "\n")
    except Exception:
        # Logging must never mask the original startup exception.
        pass


def run_streamlit(port: int, app_path: str, protocol_id: str) -> None:
    """Run Streamlit in a child process and pass the fixed protocol identity."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_path = None

    try:
        received_id = str(protocol_id).strip()
        _append_startup_log(
            "[STREAMLIT_RUNNER] Received protocol_id={!r}; expected={!r}".format(
                received_id, PROTOCOL_ID
            )
        )
        if received_id != PROTOCOL_ID:
            raise RuntimeError(
                "Protocol ID mismatch in streamlit_runner.py: "
                "expected {!r}, received {!r}".format(PROTOCOL_ID, received_id)
            )

        os.environ["HOKAMA_PROTOCOL_ID"] = PROTOCOL_ID
        os.environ["HOKAMA_READINESS_PROTOCOL"] = str(PROTOCOL_VERSION)

        app_file = Path(app_path).expanduser().resolve()
        app_root = app_file.parent
        if not app_file.is_file():
            raise FileNotFoundError(
                "Streamlit app file does not exist: {}".format(app_file)
            )

        app_root_text = str(app_root)
        if app_root_text not in sys.path:
            sys.path.insert(0, app_root_text)
        os.chdir(app_root)

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy()
            )
        asyncio.set_event_loop(asyncio.new_event_loop())

        log_path = _get_logs_dir() / LOG_FILE_NAME
        with log_path.open("a", encoding="utf-8", buffering=1) as child_log:
            sys.stdout = child_log
            sys.stderr = child_log

            child_log.write("\n" + "=" * 70 + "\n")
            child_log.write("Streamlit child startup\n")
            child_log.write("Protocol ID: {}\n".format(PROTOCOL_ID))
            child_log.write("Protocol version: {}\n".format(PROTOCOL_VERSION))
            child_log.write("Port: {}\n".format(port))
            child_log.write("Host: {}\n".format(HOST))
            child_log.write("Application: {}\n".format(app_file))
            child_log.write("Working directory: {}\n".format(app_root))
            child_log.write("PID: {}\n".format(os.getpid()))
            child_log.write("=" * 70 + "\n")

            from streamlit.web import cli as stcli

            sys.argv = [
                "streamlit",
                "run",
                str(app_file),
                "--server.port={}".format(int(port)),
                "--server.address={}".format(HOST),
                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",
                "--browser.gatherUsageStats=false",
                "--global.developmentMode=false",
                "--theme.base=dark",
                "--client.toolbarMode=viewer",
            ]

            child_log.write("Starting Streamlit CLI.\n")
            child_log.flush()
            stcli.main()

    except SystemExit as exc:
        message = "[STREAMLIT_RUNNER] Streamlit CLI exited with code: {}".format(
            exc.code
        )
        _append_startup_log(message)
        try:
            with (_get_logs_dir() / LOG_FILE_NAME).open(
                "a", encoding="utf-8"
            ) as log:
                log.write(message + "\n")
        except Exception:
            pass

    except BaseException:
        error_text = traceback.format_exc()
        _append_startup_log(
            "[STREAMLIT_RUNNER] Fatal child error:\n" + error_text
        )
        try:
            target = log_path or (_get_logs_dir() / LOG_FILE_NAME)
            with target.open("a", encoding="utf-8") as log:
                log.write("[STREAMLIT_RUNNER] Fatal child error:\n")
                log.write(error_text + "\n")
        except Exception:
            pass
        raise

    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
