import os
import sys
import time
import socket
import threading
import asyncio
import webview
from streamlit.web import cli as stcli

def find_free_port():
    """البحث عن منفذ فارغ لضمان عدم تداخل الشبكات"""
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
    """السر البرمجي: توجيه المسار إلى المجلد المؤقت الآمن الذي ينشئه الـ EXE"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def run_streamlit(port, app_path):
    """تشغيل سيرفر Streamlit داخلياً"""
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
    try:
        stcli.main()
    except SystemExit:
        pass  # تجاهل أمر الإغلاق التلقائي لمنع انهيار البرنامج

def main():
    base_path = get_base_path()
    
    # تحديد مسار app.py داخل المجلد المؤقت
    app_py_path = os.path.join(base_path, "app.py")

    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    # تشغيل السيرفر في الخلفية
    t = threading.Thread(target=run_streamlit, args=(port, app_py_path), daemon=True)
    t.start()

    # انتظار جاهزية السيرفر
    max_retries = 30
    retries = 0
    while not is_server_running(host, port) and retries < max_retries:
        time.sleep(0.5)
        retries += 1

    if retries >= max_retries:
        print("فشل تشغيل السيرفر.")
        return

    # فتح نافذة التطبيق
    window_title = "نظام حوكمة ERP - Asam"
    webview.create_window(
        title=window_title,
        url=url,
        width=1366,
        height=768,
        min_size=(1024, 600),
        resizable=True
    )
    webview.start(private_mode=False)

if __name__ == "__main__":
    main()
