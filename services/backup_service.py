# services/backup_service.py - النسخ الاحتياطي (v2.0)
# ✅ Connection Registry + مسار مطلق بجانب EXE
import sqlite3
import shutil
import os
import sys
import zipfile
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import threading
import time

from database import get_connection, close_connection, DB_PATH as _DB_PATH


# ============================================================
# ✅ المسارات المطلقة — تعمل في EXE وفي Python
# ============================================================
def _get_app_base():
    """مجلد التطبيق (جانب EXE أو المشروع)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_BASE = _get_app_base()
DB_PATH = _DB_PATH   # ✅ من database.py مباشرة

BACKUP_DIR = os.path.join(APP_BASE, "backups")
METADATA_DIR = os.path.join(BACKUP_DIR, "metadata")
KEY_FILE_PATH = os.path.join(APP_BASE, "data", "backup_encryption.key")


# ---------- إعدادات التشفير ----------
def load_or_generate_key():
    """تحميل أو إنشاء مفتاح التشفير"""
    data_dir = os.path.dirname(KEY_FILE_PATH)
    os.makedirs(data_dir, exist_ok=True)

    if os.path.exists(KEY_FILE_PATH):
        with open(KEY_FILE_PATH, 'rb') as key_file:
            return key_file.read()
    else:
        new_key = Fernet.generate_key()
        with open(KEY_FILE_PATH, 'wb') as key_file:
            key_file.write(new_key)

        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(KEY_FILE_PATH, 2)
            except Exception:
                pass

        return new_key


ENCRYPTION_KEY = load_or_generate_key()
fernet = Fernet(ENCRYPTION_KEY)


# ---------- إعدادات قابلة للتعديل ----------
NETWORK_BACKUP_PATH = None
SCHEDULE_ENABLED = False
SCHEDULE_INTERVAL_HOURS = 24
AUTO_DELETE_DAYS = 30
ALERT_DAYS_NO_BACKUP = 7


# ---------- دوال مساعدة ----------
def ensure_directories():
    """إنشاء المجلدات المطلوبة"""
    for d in [BACKUP_DIR, METADATA_DIR, os.path.dirname(DB_PATH)]:
        os.makedirs(d, exist_ok=True)


def create_backup_table(conn=None):
    """إنشاء جدول سجل النسخ الاحتياطي"""
    ensure_directories()

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        if own_conn:
            conn.execute("COMMIT")
    finally:
        if own_conn:
            close_connection(conn)


def is_valid_backup(filepath):
    """التحقق من أن الملف قاعدة بيانات SQLite صالحة"""
    try:
        conn = sqlite3.connect(filepath)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        conn.close()
        return True
    except Exception:
        return False


def get_all_tables(conn=None):
    """أسماء جميع الجداول"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row[0] for row in cur.fetchall()]
        return tables
    finally:
        if own_conn:
            close_connection(conn)


def check_alert(conn=None):
    """فحص إنذار عدم وجود نسخة حديثة"""
    create_backup_table(conn=conn)

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        latest = conn.execute(
            "SELECT created_at FROM backup_history ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if not latest:
            return True, "لم يتم إنشاء أي نسخة احتياطية بعد!"

        last_time = datetime.strptime(latest["created_at"], "%Y-%m-%d %H:%M:%S")
        days_since = (datetime.now() - last_time).days

        if days_since >= ALERT_DAYS_NO_BACKUP:
            return True, f"آخر نسخة احتياطية منذ {days_since} يوماً!"

        return False, None
    finally:
        if own_conn:
            close_connection(conn)


# ---------- النسخ الاحتياطي ----------
def create_backup(user="غير معروف", backup_type="يدوي", tables=None,
                  encrypt=False, compress=True, notes=""):
    """إنشاء نسخة احتياطية"""
    ensure_directories()
    create_backup_table()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"erp_backup_{timestamp}.db"
    filepath = os.path.join(BACKUP_DIR, filename)

    if tables is None:
        shutil.copy2(DB_PATH, filepath)
        tables_count = len(get_all_tables())
    else:
        tables_count = len(tables)
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(filepath)

        for table in tables:
            try:
                src_cur = src_conn.cursor()
                src_cur.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                row = src_cur.fetchone()
                if not row:
                    continue
                create_sql = row[0]
                dst_conn.execute(create_sql)

                src_cur.execute(f'SELECT * FROM "{table}"')
                rows = src_cur.fetchall()
                cols = [desc[0] for desc in src_cur.description]
                placeholders = ','.join(['?' for _ in cols])
                cols_str = '","'.join(cols)
                dst_conn.executemany(
                    f'INSERT INTO "{table}" ("{cols_str}") VALUES ({placeholders})',
                    rows
                )
            except Exception as e:
                print(f"فشل نسخ جدول {table}: {e}")

        src_conn.close()
        dst_conn.commit()
        dst_conn.close()

    is_compressed = 0
    if compress:
        zip_filename = filename.replace('.db', '.zip')
        zip_filepath = os.path.join(BACKUP_DIR, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(filepath, filename)
        os.remove(filepath)
        filepath = zip_filepath
        filename = zip_filename
        is_compressed = 1

    is_encrypted = 0
    if encrypt:
        with open(filepath, 'rb') as f:
            data = f.read()
        encrypted_data = fernet.encrypt(data)
        enc_filename = filename + '.enc'
        enc_filepath = os.path.join(BACKUP_DIR, enc_filename)
        with open(enc_filepath, 'wb') as f:
            f.write(encrypted_data)
        os.remove(filepath)
        filepath = enc_filepath
        filename = enc_filename
        is_encrypted = 1

    size_kb = os.path.getsize(filepath) / 1024

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

    # ✅ تسجيل في قاعدة البيانات — باستخدام Registry
    conn = get_connection()
    try:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            INSERT INTO backup_history
            (filename, size_kb, created_at, type, user,
             tables_count, is_encrypted, is_compressed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (filename, size_kb,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              backup_type, user, tables_count,
              is_encrypted, is_compressed, notes))
        conn.execute("COMMIT")
    except Exception as e:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except Exception:
            pass
        print(f"فشل تسجيل النسخة: {e}")
    finally:
        close_connection(conn)

    if NETWORK_BACKUP_PATH:
        try:
            if not os.path.exists(NETWORK_BACKUP_PATH):
                os.makedirs(NETWORK_BACKUP_PATH, exist_ok=True)
            dest = os.path.join(NETWORK_BACKUP_PATH, filename)
            shutil.copy2(filepath, dest)
        except Exception as e:
            print(f"تنبيه: تعذر النسخ إلى مجلد الشبكة - {e}")

    return filename, size_kb


# ---------- الاستعادة ----------
def restore_backup(filename):
    """
    استعادة نسخة احتياطية.
    ✅ المسارات مطلقة — تعمل في EXE.
    """
    filepath = os.path.join(BACKUP_DIR, filename)

    # 1) فك التشفير إن كان
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

    # 2) فك ضغط ZIP إن كان
    if filename.endswith('.zip'):
        with zipfile.ZipFile(filepath, 'r') as zf:
            db_files = [f for f in zf.namelist() if f.endswith('.db')]
            if not db_files:
                return False, "لم يُعثر على ملف قاعدة بيانات في الأرشيف"
            db_filename = db_files[0]
            zf.extract(db_filename, BACKUP_DIR)
        filepath = os.path.join(BACKUP_DIR, db_filename)
        filename = db_filename

    # 3) التحقق
    if not os.path.exists(filepath):
        return False, "الملف غير موجود"
    if not is_valid_backup(filepath):
        return False, "الملف تالف أو ليس قاعدة بيانات صالحة"

    # 4) نسخة أمان قبل الاستعادة
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_file = os.path.join(BACKUP_DIR, f"pre_restore_{timestamp}.db")
    try:
        shutil.copy2(DB_PATH, safety_file)
    except Exception:
        return False, "فشل إنشاء نسخة أمان قبل الاستعادة"

    # 5) الاستعادة — باستخدام مسار مطلق
    try:
        shutil.copy2(filepath, DB_PATH)
    except Exception as e:
        return False, f"فشل النسخ: {e}"

    return True, f"تمت الاستعادة بنجاح. نسخة أمان محفوظة في: {safety_file}"


# ---------- القوائم والإحصائيات ----------
def get_backup_list(limit=50, conn=None):
    """قائمة النسخ الاحتياطية"""
    create_backup_table(conn=conn)

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        backups = conn.execute(
            "SELECT * FROM backup_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(b) for b in backups]
    finally:
        if own_conn:
            close_connection(conn)


def get_backup_stats(conn=None):
    """إحصائيات النسخ الاحتياطي"""
    create_backup_table(conn=conn)

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row

        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM backup_history"
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        latest = conn.execute(
            "SELECT created_at, size_kb, user FROM backup_history "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()

        alert, alert_msg = check_alert(conn=conn)

        return {
            "total": total,
            "latest_time": latest["created_at"] if latest else "لا يوجد",
            "latest_size": latest["size_kb"] if latest else 0,
            "latest_user": latest["user"] if latest else "غير معروف",
            "alert": alert,
            "alert_msg": alert_msg
        }
    finally:
        if own_conn:
            close_connection(conn)


# ---------- الحذف التلقائي ----------
def delete_old_backups():
    """حذف النسخ القديمة"""
    cutoff_date = datetime.now() - timedelta(days=AUTO_DELETE_DAYS)

    conn = get_connection()
    try:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM backup_history WHERE created_at < ?",
            (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        conn.execute("COMMIT")
    except Exception:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        close_connection(conn)

    for folder in [BACKUP_DIR, METADATA_DIR]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_date:
                            os.remove(filepath)
                    except Exception:
                        pass
    return True


# ---------- المجدول ----------
_scheduler_thread = None


def _run_scheduler():
    while SCHEDULE_ENABLED:
        time.sleep(SCHEDULE_INTERVAL_HOURS * 3600)
        if SCHEDULE_ENABLED:
            create_backup(user="النظام", backup_type="تلقائي", compress=True)


def start_scheduler():
    global _scheduler_thread, SCHEDULE_ENABLED
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        SCHEDULE_ENABLED = True
        _scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
        _scheduler_thread.start()
        return True
    return False


def stop_scheduler():
    global SCHEDULE_ENABLED
    SCHEDULE_ENABLED = False
    return True
