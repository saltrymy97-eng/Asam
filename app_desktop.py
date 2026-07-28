import os
import sys
import time
import socket
import multiprocessing
import asyncio
import webview
import traceback
from streamlit.web import cli as stcli

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]

def is_server_running(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (socket.error, TimeoutError, OSError):
        return False

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def run_streamlit(port, app_path):
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.set_event_loop(asyncio.new_event_loop())
        
        sys.argv = [
            "streamlit",
            "run",
            app_path,
            f"--server.port={port}",
            "--server.headless=true",
            "--server.allowRunOnSave=false",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false"
        ]
        stcli.main()
    except Exception as e:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        with open(os.path.join(exe_dir, "server_error_log.txt"), "w", encoding="utf-8") as f:
            f.write(str(e) + "\n" + traceback.format_exc())
    except SystemExit:
        pass

def main():
    base_path = get_base_path()
    app_py_path = os.path.join(base_path, "app.py")

    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    p = multiprocessing.Process(target=run_streamlit, args=(port, app_py_path), daemon=True)
    p.start()

    max_retries = 80
    retries = 0
    while not is_server_running(host, port) and retries < max_retries:
        time.sleep(0.5)
        retries += 1

    window_title = "ERP Governance System - Asam"
    icon_path = os.path.join(base_path, "icon.ico")

    window_args = {
        "title": window_title,
        "url": url,
        "width": 1366,
        "height": 768,
        "min_size": (1024, 600),
        "resizable": True
    }
    if os.path.exists(icon_path):
        window_args["icon"] = icon_path

    webview.create_window(**window_args)
    webview.start(private_mode=False)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
