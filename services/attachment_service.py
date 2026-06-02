# services/attachment_service.py – منطق المرفقات (رفع، تخزين، جلب، حذف)
import os
import uuid
import sqlite3
from datetime import datetime
import database

ATTACHMENTS_DIR = "attachments"

def get_conn():
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_dir():
    if not os.path.exists(ATTACHMENTS_DIR):
        os.makedirs(ATTACHMENTS_DIR)

def upload_attachment(uploaded_file, linked_table, linked_id, username="admin"):
    """رفع ملف وحفظه على القرص وفي قاعدة البيانات"""
    _ensure_dir()
    
    # إنشاء اسم فريد للملف
    ext = os.path.splitext(uploaded_file.name)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(ATTACHMENTS_DIR, unique_name)
    
    # حفظ الملف على القرص
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    
    file_size = os.path.getsize(file_path)
    
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT INTO attachments (filename, original_name, file_path, file_size, file_type, linked_table, linked_id, uploaded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (unique_name, uploaded_file.name, file_path, file_size, uploaded_file.type, linked_table, linked_id, username)
        )
        conn.commit()
        return True, unique_name
    except Exception as e:
        conn.rollback()
        # حذف الملف إذا فشل الحفظ في القاعدة
        if os.path.exists(file_path):
            os.remove(file_path)
        raise e
    finally:
        conn.close()

def get_attachments(linked_table=None, linked_id=None):
    """جلب قائمة المرفقات مع إمكانية التصفية"""
    conn = get_conn()
    query = "SELECT * FROM attachments WHERE 1=1"
    params = []
    if linked_table:
        query += " AND linked_table = ?"
        params.append(linked_table)
    if linked_id:
        query += " AND linked_id = ?"
        params.append(linked_id)
    query += " ORDER BY uploaded_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_attachment_by_id(attachment_id):
    """جلب مرفق واحد"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_attachment(attachment_id):
    """حذف مرفق من القرص ومن قاعدة البيانات"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT file_path FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
        if not row:
            return False
        
        conn.execute("BEGIN")
        conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.commit()
        
        # حذف الملف من القرص بعد نجاح الحذف من القاعدة
        file_path = row["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
