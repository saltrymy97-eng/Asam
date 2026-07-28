import os
import sys
import time
import socket
import threading
import asyncio
import webview
import traceback
from streamlit.web import cli as stcli

# 1. الحل الجذري لمشكلة الشاشة المخفية:
# نوجه أي محاولة طباعة من Streamlit إلى "العدم" حتى لا ينهار السيرفر
sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")

def find_free_port():
    """البحث عن منفذ شبكة فارغ"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]

def is_server_running(host, port):
    """التحقق من أن السيرفر استيقظ وأصبح جاهزاً"""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (socket.error, TimeoutError, OSError):
        return False

def get_base_path():
    """المسار الآمن للملفات المدمجة داخل الـ EXE"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def run_streamlit(port, app_path):
    """تشغيل السيرفر في الخلفية بأمان"""
    try:
        # 2. حل مشكلة شبكات ويندوز للعمليات الخلفية
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
        # ميزة الصندوق الأسود: تسجيل أي خطأ في ملف نصي بجانب الـ EXE لمعرفته
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        with open(os.path.join(exe_dir, "server_error_log.txt"), "w", encoding="utf-8") as f:
            f.write("حدث خطأ أثناء تشغيل سيرفر Streamlit:\n")
            f.write(str(e) + "\n")
            f.write(traceback.format_exc())
    except SystemExit:
        pass

def main():
    base_path = get_base_path()
    app_py_path = os.path.join(base_path, "app.py")

    host = "127.0.0.1"
    port = find_free_port()
    url = f"http://{host}:{port}"

    # تشغيل السيرفر في Thread خلفي
    t = threading.Thread(target=run_streamlit, args=(port, app_py_path), daemon=True)
    t.start()

    # 3. زيادة المهلة الزمنية إلى 40 ثانية لإعطاء EXE وقتاً كافياً لفك الضغط
    max_retries = 80
    retries = 0
    while not is_server_running(host, port) and retries < max_retries:
        time.sleep(0.5)
        retries += 1

    if retries >= max_retries:
        # إذا انتهى الوقت ولم يعمل، نسجل ذلك في ملف الأخطاء
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        with open(os.path.join(exe_dir, "server_error_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"\nانتهى الوقت (Timeout): السيرفر لم يستجب بعد {max_retries/2} ثانية.")

    # فتح نافذة التطبيق
    window_title = "ERP Governance System - Asam"
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
