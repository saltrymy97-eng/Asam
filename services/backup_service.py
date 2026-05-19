# services/backup_service.py - منطق النسخ الاحتياطي
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = "erp.db"
BACKUP_DIR = "backups"

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
    """إنشاء نسخة احتياطية جديدة"""
    ensure_backup_dir()
    create_backup_table()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"erp_backup_{timestamp}.db"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    # نسخ قاعدة البيانات
    shutil.copy2(DB_PATH, filepath)
    
    # حجم الملف
    size_kb = os.path.getsize(filepath) / 1024
    
    # تسجيل في السجل
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO backup_history (filename, size_kb, created_at, type)
        VALUES (?, ?, ?, ?)
    """, (filename, size_kb, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), backup_type))
    conn.commit()
    conn.close()
    
    return filename, size_kb

def get_backup_list():
    """جلب قائمة النسخ الاحتياطية"""
    create_backup_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    backups = conn.execute("""
        SELECT * FROM backup_history ORDER BY id DESC LIMIT 50
    """).fetchall()
    conn.close()
    return [dict(b) for b in backups]

def restore_backup(filename):
    """استعادة نسخة احتياطية"""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return False
    
    # نسخ احتياطي للقاعدة الحالية قبل الاستعادة
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_backup = os.path.join(BACKUP_DIR, f"before_restore_{timestamp}.db")
    shutil.copy2(DB_PATH, safety_backup)
    
    # استعادة النسخة
    shutil.copy2(filepath, DB_PATH)
    return True

def get_backup_stats():
    """إحصائيات النسخ الاحتياطي"""
    create_backup_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    total = conn.execute("SELECT COUNT(*) as cnt FROM backup_history").fetchone()["cnt"]
    latest = conn.execute("SELECT created_at, size_kb FROM backup_history ORDER BY id DESC LIMIT 1").fetchone()
    
    conn.close()
    
    return {
        "total": total,
        "latest_time": latest["created_at"] if latest else "لا يوجد",
        "latest_size": latest["size_kb"] if latest else 0
    }
