import os
import sys
import time
import socket
import subprocess
import webview

def find_free_port():
    """البحث عن منفذ (Port) فارغ"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]

def is_server_running(host, port):
    """التحقق من جاهزية السيرفر"""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (socket.error, TimeoutError, OSError):
        return False

def get_base_path():
    """تحديد المسار الصحيح سواء أثناء التطوير أو داخل الـ EXE"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def start_streamlit_process(port, base_path):
    """تشغيل سيرفر Streamlit"""
    # البحث عن app.py سواء في المجلد المترجم أو بجانبه
    app_py_path = os.path.join(base_path, "app.py")
    if not os.path.exists(app_py_path):
        app_py_path = os.path.join(os.path.dirname(sys.executable), "app.py")

    cmd = [
        sys.executable,
        "-m", "streamlit", "run",
        app_py_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--server.allowRunOnSave=false",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false"
    ]

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        cmd,
        cwd=base_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags
    )
    return process

def main():
    base_path = get_base_path()
    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    streamlit_process = start_streamlit_process(port, base_path)

    # حد أقصى للانتظار 15 ثانية فقط لتفادي تعليق الجهاز
    max_retries = 30
    retries = 0
    while not is_server_running(host, port) and retries < max_retries:
        time.sleep(0.5)
        retries += 1

    # إذا لم يشتغل السيرفر، يتم إغلاق العملية فوراً ومسح الذاكرة
    if retries >= max_retries:
        if streamlit_process:
            streamlit_process.kill()
        print("فشل تشغيل السيرفر.")
        return

    window_title = "نظام حوكمة ERP - Asam"
    
    window = webview.create_window(
        title=window_title,
        url=url,
        width=1366,
        height=768,
        min_size=(1024, 600),
        resizable=True
    )

    try:
        webview.start(private_mode=False)
    finally:
        if streamlit_process and streamlit_process.poll() is None:
            streamlit_process.terminate()
            try:
                streamlit_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                streamlit_process.kill()

if __name__ == "__main__":
    main()
