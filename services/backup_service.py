# services/backup_service.py - منطق النسخ الاحتياطي (محلي + شبكة)
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = os.path.join("data", "erp.db")
BACKUP_DIR = "backups"

# ---------- إعدادات قابلة للتعديل ----------
NETWORK_BACKUP_PATH = None   # مثال: "\\\\192.168.1.10\\Shared\\Backups" أو "/mnt/backups"

def ensure_backup_dir():
    """إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجوداً"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def create_backup_table():
    """إنشاء جدول سجل النسخ الاحتياطي"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            size_kb REAL,
            created_at TEXT NOT NULL,
            type TEXT DEFAULT 'يدوي'
        )
    """)
    conn.commit()
    conn.close()

def create_backup(backup_type="يدوي"):
    """إنشاء نسخة احتياطية جديدة (محلياً + اختيارياً على مجلد الشبكة)"""
    ensure_backup_dir()
    create_backup_table()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"erp_backup_{timestamp}.db"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    # نسخ قاعدة البيانات الأساسية
    shutil.copy2(DB_PATH, filepath)
    size_kb = os.path.getsize(filepath) / 1024
    
    # تسجيل العملية في السجل
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO backup_history (filename, size_kb, created_at, type)
        VALUES (?, ?, ?, ?)
    """, (filename, size_kb, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), backup_type))
    conn.commit()
    conn.close()
    
    # نسخ إضافي إلى مجلد الشبكة إذا تم ضبطه
    if NETWORK_BACKUP_PATH:
        try:
            # تأكد من وجود المجلد الشبكي
            if not os.path.exists(NETWORK_BACKUP_PATH):
                os.makedirs(NETWORK_BACKUP_PATH, exist_ok=True)
            dest = os.path.join(NETWORK_BACKUP_PATH, filename)
            shutil.copy2(filepath, dest)
        except Exception as e:
            # فشل النسخ الشبكي لا يوقف العملية الأساسية
            print(f"تنبيه: تعذر النسخ إلى مجلد الشبكة - {e}")
    
    return filename, size_kb

def get_backup_list():
    """جلب قائمة النسخ الاحتياطية من السجل"""
    create_backup_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    backups = conn.execute(
        "SELECT * FROM backup_history ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(b) for b in backups]

def restore_backup(filename):
    """استعادة نسخة احتياطية مع أمان إضافي"""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return False
    
    # التحقق من صلاحية ملف النسخة
    if not is_valid_backup(filepath):
        return False
    
    # نسخة أمان من القاعدة الحالية قبل الاستعادة
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_file = os.path.join(BACKUP_DIR, f"pre_restore_{timestamp}.db")
    try:
        shutil.copy2(DB_PATH, safety_file)
    except Exception:
        return False
    
    # استعادة النسخة المحددة
    shutil.copy2(filepath, DB_PATH)
    return True

def is_valid_backup(filepath):
    """التحقق من أن الملف قاعدة بيانات SQLite صالحة"""
    try:
        conn = sqlite3.connect(filepath)
        conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        conn.close()
        return True
    except Exception:
        return False

def get_backup_stats():
    """إحصائيات سريعة عن النسخ الاحتياطية"""
    create_backup_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    total = conn.execute("SELECT COUNT(*) as cnt FROM backup_history").fetchone()["cnt"]
    latest = conn.execute(
        "SELECT created_at, size_kb FROM backup_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    
    conn.close()
    
    return {
        "total": total,
        "latest_time": latest["created_at"] if latest else "لا يوجد",
        "latest_size": latest["size_kb"] if latest else 0
    }
