import os
import sys
import time
import socket
import subprocess
import webview

def find_free_port():
    """البحث عن منفذ (Port) فارغ لتشغيل سيرفر Streamlit دون تضارب"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]

def is_server_running(host, port):
    """التحقق التلقائي المستمر من جاهزية السيرفر للاستجابة"""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (SocketError, OverflowError, OSError):
        return False

def get_base_path():
    """تحديد المسار الرئيسي للمشروع سواء كان كوداً مصدرياً أو ملف EXE مجمعاً"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def start_streamlit_process(port, base_path):
    """تشغيل سيرفر Streamlit في الخلفية بأعلى درجات الأمان والعزل"""
    app_py_path = os.path.join(base_path, "app.py")
    
    # تحضير أمر التشغيل للوضع الصامت (Headless)
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

    # إخفاء شاشة الأوامر السوداء عند التشغيل على الويندوز
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

    # 1. تشغيل المحرك المالي في الخلفية
    streamlit_process = start_streamlit_process(port, base_path)

    # 2. الانتظار الذكي المعتمد على الاستجابة الحقيقية وليس الوقت الثابت
    max_retries = 40
    retries = 0
    while not is_server_running(host, port) and retries < max_retries:
        time.sleep(0.25)
        retries += 1

    # 3. تكوين نافذة تطبيق الويندوز (Native Window)
    window_title = "نظام حوكمة ERP - Asam"
    
    # إنشاء النافذة مع تحديد الحجم الأدنى والخصائص المتقدمة
    window = webview.create_window(
        title=window_title,
        url=url,
        width=1366,
        height=768,
        min_size=(1024, 600),
        resizable=True,
        confirm_close=True,  # تأكيد الإغلاق لمنع فقدان البيانات غير المحفوظة
        text_select=True
    )

    try:
        # 4. بدء تشغيل النافذة المباشرة
        webview.start(private_mode=False)
    finally:
        # 5. تنظيف وتنظيف شامل عند الإغلاق لمنع بقاء أي عملية في الخلفية
        if streamlit_process and streamlit_process.poll() is None:
            streamlit_process.terminate()
            try:
                streamlit_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                streamlit_process.kill()

if __name__ == "__main__":
    main()
