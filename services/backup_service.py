# services/backup_service.py - منطق النسخ الاحتياطي الاحترافي (إصدار إنتاجي)
import sqlite3
import shutil
import os
import zipfile
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import threading
import time

DB_PATH = os.path.join("data", "erp.db")
BACKUP_DIR = "backups"
METADATA_DIR = os.path.join(BACKUP_DIR, "metadata")

# ---------- إعدادات قابلة للتعديل ----------
ENCRYPTION_KEY = Fernet.generate_key()  # يجب حفظ هذا المفتاح في مكان آمن (st.secrets)
fernet = Fernet(ENCRYPTION_KEY)
NETWORK_BACKUP_PATH = None   # مثال: "\\\\192.168.1.10\\Shared\\Backups"
SCHEDULE_ENABLED = False     # تفعيل النسخ التلقائي
SCHEDULE_INTERVAL_HOURS = 24  # كل 24 ساعة
AUTO_DELETE_DAYS = 30        # حذف النسخ الأقدم من 30 يومًا
ALERT_DAYS_NO_BACKUP = 7     # تنبيه إذا مر 7 أيام بدون نسخ

# ---------- دوال مساعدة ----------

def ensure_directories():
    """إنشاء المجلدات المطلوبة"""
    for d in [BACKUP_DIR, METADATA_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

def create_backup_table():
    """إنشاء جدول سجل النسخ الاحتياطي مع معلومات المستخدم"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            size_kb REAL,
            created_at TEXT NOT NULL,
            type TEXT DEFAULT 'يدوي',
            user TEXT DEFAULT 'غير معروف',
            tables_count INTEGER DEFAULT 0,
            is_encrypted INTEGER DEFAULT 0,
            is_compressed INTEGER DEFAULT 0,
            notes TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

def is_valid_backup(filepath):
    """التحقق من أن الملف قاعدة بيانات SQLite صالحة"""
    try:
        conn = sqlite3.connect(filepath)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        conn.close()
        return True
    except Exception:
        return False

def get_all_tables():
    """جلب أسماء جميع الجداول في قاعدة البيانات"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables

def check_alert():
    """فحص ما إذا كان الوقت قد حان للتنبيه بعدم وجود نسخة حديثة"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    latest = conn.execute(
        "SELECT created_at FROM backup_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    
    if not latest:
        return True, "لم يتم إنشاء أي نسخة احتياطية بعد!"
    
    last_time = datetime.strptime(latest["created_at"], "%Y-%m-%d %H:%M:%S")
    days_since = (datetime.now() - last_time).days
    
    if days_since >= ALERT_DAYS_NO_BACKUP:
        return True, f"آخر نسخة احتياطية منذ {days_since} يومًا!"
    
    return False, None

# ---------- النسخ الاحتياطي ----------

def create_backup(user="غير معروف", backup_type="يدوي", tables=None, encrypt=False, compress=True, notes=""):
    """
    إنشاء نسخة احتياطية جديدة (محلياً + اختيارياً على مجلد الشبكة).
    
    Parameters:
    - user: اسم المستخدم الذي قام بالنسخ.
    - backup_type: نوع النسخة ('يدوي', 'تلقائي', 'قبل تحديث').
    - tables: قائمة بأسماء الجداول المطلوب نسخها (None = كل الجداول).
    - encrypt: هل يتم تشفير الملف؟
    - compress: هل يتم ضغط الملف؟
    - notes: ملاحظات إضافية.
    """
    ensure_directories()
    create_backup_table()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"erp_backup_{timestamp}.db"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    # --- النسخ الانتقائي (Selective Backup) ---
    if tables is None:
        # نسخ جميع الجداول
        shutil.copy2(DB_PATH, filepath)
        tables_count = len(get_all_tables())
    else:
        # نسخ جداول محددة فقط
        tables_count = len(tables)
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(filepath)
        
        for table in tables:
            try:
                # نسخ هيكل الجدول
                src_cur = src_conn.cursor()
                src_cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
                create_sql = src_cur.fetchone()[0]
                dst_conn.execute(create_sql)
                
                # نسخ البيانات
                src_cur.execute(f"SELECT * FROM \"{table}\"")
                rows = src_cur.fetchall()
                cols = [desc[0] for desc in src_cur.description]
                placeholders = ','.join(['?' for _ in cols])
                cols_str = '","'.join(cols)
                dst_conn.executemany(f'INSERT INTO "{table}" ("{cols_str}") VALUES ({placeholders})', rows)
            except Exception as e:
                print(f"⚠️ فشل نسخ جدول {table}: {e}")
        
        src_conn.close()
        dst_conn.commit()
        dst_conn.close()
    
    # --- ضغط الملف (Compression) ---
    is_compressed = 0
    if compress:
        zip_filename = filename.replace('.db', '.zip')
        zip_filepath = os.path.join(BACKUP_DIR, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(filepath, filename)
        os.remove(filepath)  # حذف الملف الأصلي بعد الضغط
        filepath = zip_filepath
        filename = zip_filename
        is_compressed = 1
    
    # --- تشفير الملف (Encryption) ---
    is_encrypted = 0
    if encrypt:
        with open(filepath, 'rb') as f:
            data = f.read()
        encrypted_data = fernet.encrypt(data)
        enc_filename = filename + '.enc'
        enc_filepath = os.path.join(BACKUP_DIR, enc_filename)
        with open(enc_filepath, 'wb') as f:
            f.write(encrypted_data)
        os.remove(filepath)  # حذف الملف غير المشفر
        filepath = enc_filepath
        filename = enc_filename
        is_encrypted = 1
    
    size_kb = os.path.getsize(filepath) / 1024
    
    # --- حفظ البيانات الوصفية (Metadata) ---
    metadata = {
        "original_filename": filename,
        "created_by": user,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": backup_type,
        "tables_count": tables_count,
        "tables": tables if tables else "كل الجداول",
        "is_encrypted": bool(encrypt),
        "is_compressed": bool(compress),
        "size_kb": round(size_kb, 2),
        "notes": notes
    }
    meta_filename = filename + '.meta.json'
    meta_filepath = os.path.join(METADATA_DIR, meta_filename)
    with open(meta_filepath, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # --- تسجيل العملية في سجل النسخ الاحتياطي ---
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO backup_history (filename, size_kb, created_at, type, user, tables_count, is_encrypted, is_compressed, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (filename, size_kb, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), backup_type, user, tables_count, is_encrypted, is_compressed, notes))
    conn.commit()
    conn.close()
    
    # --- نسخ إضافي إلى مجلد الشبكة (Network Backup) ---
    if NETWORK_BACKUP_PATH:
        try:
            if not os.path.exists(NETWORK_BACKUP_PATH):
                os.makedirs(NETWORK_BACKUP_PATH, exist_ok=True)
            dest = os.path.join(NETWORK_BACKUP_PATH, filename)
            shutil.copy2(filepath, dest)
        except Exception as e:
            print(f"تنبيه: تعذر النسخ إلى مجلد الشبكة - {e}")
    
    return filename, size_kb

# ---------- استعادة النسخة ----------

def restore_backup(filename):
    """استعادة نسخة احتياطية مع أمان إضافي"""
    filepath = os.path.join(BACKUP_DIR, filename)
    
    # --- فك التشفير إذا كان مشفرًا ---
    if filename.endswith('.enc'):
        with open(filepath, 'rb') as f:
            encrypted_data = f.read()
        try:
            data = fernet.decrypt(encrypted_data)
        except Exception:
            return False, "فشل فك التشفير. المفتاح غير صحيح."
        temp_filename = filename.replace('.enc', '')
        temp_filepath = os.path.join(BACKUP_DIR, temp_filename)
        with open(temp_filepath, 'wb') as f:
            f.write(data)
        filepath = temp_filepath
        filename = temp_filename
    
    # --- فك الضغط إذا كان مضغوطًا ---
    if filename.endswith('.zip'):
        with zipfile.ZipFile(filepath, 'r') as zf:
            db_filename = [f for f in zf.namelist() if f.endswith('.db')][0]
            zf.extract(db_filename, BACKUP_DIR)
        filepath = os.path.join(BACKUP_DIR, db_filename)
        filename = db_filename
    
    if not os.path.exists(filepath):
        return False, "الملف غير موجود"
    
    if not is_valid_backup(filepath):
        return False, "الملف تالف أو ليس قاعدة بيانات صالحة"
    
    # --- نسخة أمان من القاعدة الحالية قبل الاستعادة ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_file = os.path.join(BACKUP_DIR, f"pre_restore_{timestamp}.db")
    try:
        shutil.copy2(DB_PATH, safety_file)
    except Exception:
        return False, "فشل إنشاء نسخة أمان قبل الاستعادة"
    
    # --- استعادة النسخة المحددة ---
    shutil.copy2(filepath, DB_PATH)
    return True, f"تمت الاستعادة بنجاح. نسخة أمان محفوظة في: {safety_file}"

# ---------- القوائم والإحصائيات ----------

def get_backup_list(limit=50):
    """جلب قائمة النسخ الاحتياطية من السجل"""
    create_backup_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    backups = conn.execute(
        "SELECT * FROM backup_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(b) for b in backups]

def get_backup_stats():
    """إحصائيات سريعة عن النسخ الاحتياطية"""
    create_backup_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    total = conn.execute("SELECT COUNT(*) as cnt FROM backup_history").fetchone()["cnt"]
    latest = conn.execute(
        "SELECT created_at, size_kb, user FROM backup_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    
    conn.close()
    
    alert, alert_msg = check_alert()
    
    return {
        "total": total,
        "latest_time": latest["created_at"] if latest else "لا يوجد",
        "latest_size": latest["size_kb"] if latest else 0,
        "latest_user": latest["user"] if latest else "غير معروف",
        "alert": alert,
        "alert_msg": alert_msg
    }

# ---------- الحذف التلقائي للنسخ القديمة ----------

def delete_old_backups():
    """حذف النسخ الاحتياطية الأقدم من AUTO_DELETE_DAYS يومًا"""
    cutoff_date = datetime.now() - timedelta(days=AUTO_DELETE_DAYS)
    
    # حذف من السجل
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "DELETE FROM backup_history WHERE created_at < ?", (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)
    )
    conn.commit()
    conn.close()
    
    # حذف الملفات القديمة من المجلد
    for folder in [BACKUP_DIR, METADATA_DIR]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_time < cutoff_date:
                        os.remove(filepath)
    
    return True

# ---------- النسخ التلقائي المجدول ----------

_scheduler_thread = None

def _run_scheduler():
    """خيط النسخ التلقائي المجدول"""
    while SCHEDULE_ENABLED:
        time.sleep(SCHEDULE_INTERVAL_HOURS * 3600)
        if SCHEDULE_ENABLED:
            create_backup(user="النظام", backup_type="تلقائي", compress=True)

def start_scheduler():
    """تشغيل المجدول التلقائي"""
    global _scheduler_thread, SCHEDULE_ENABLED
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        SCHEDULE_ENABLED = True
        _scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
        _scheduler_thread.start()
        return True
    return False

def stop_scheduler():
    """إيقاف المجدول التلقائي"""
    global SCHEDULE_ENABLED
    SCHEDULE_ENABLED = False
    return True
