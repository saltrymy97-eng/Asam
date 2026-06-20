# services/auth_service.py - منطق المصادقة وتغيير كلمة المرور (حوكمة ERP)
import sqlite3
import bcrypt
from database import get_connection
from services.audit_service import log_action

def verify_user(username, password):
    """التحقق من صحة بيانات المستخدم"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT password, full_name, role_id FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        stored_password = row["password"]
        # تحويل إلى bytes إذا كانت str
        if isinstance(stored_password, str):
            stored_password = stored_password.encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            return {"username": username, "full_name": row["full_name"], "role_id": row["role_id"]}
    return None

def change_password(username, old_password, new_password):
    """تغيير كلمة مرور المستخدم"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. التحقق من وجود المستخدم
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "المستخدم غير موجود"

    # 2. التحقق من كلمة المرور القديمة
    stored_password = row["password"]
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')

    if not bcrypt.checkpw(old_password.encode('utf-8'), stored_password):
        conn.close()
        return False, "كلمة المرور الحالية غير صحيحة"

    # 3. تشفير كلمة المرور الجديدة وحفظها
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    # 🆕 تخزين كـ bytes مباشرة، دون فك تشفير
    c.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
    conn.commit()
    conn.close()
    
    # 4. تسجيل تغيير كلمة المرور في سجل التدقيق
    log_action(
        username=username,
        action="تغيير كلمة المرور",
        table_name="users",
        new_value=f"تم تغيير كلمة المرور للمستخدم: {username}"
    )
    
    return True, "تم تغيير كلمة المرور بنجاح. يرجى تسجيل الخروج وإعادة الدخول."

def create_user(username, password, full_name, role_id=None):
    """إنشاء مستخدم جديد"""
    conn = get_connection()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        # 🆕 تخزين كـ bytes مباشرة
        conn.execute(
            "INSERT INTO users (username, password, full_name, role_id) VALUES (?, ?, ?, ?)",
            (username, hashed, full_name, role_id)
        )
        conn.commit()
        
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if user:
            log_action(
                username=username,
                action="إنشاء مستخدم",
                table_name="users",
                record_id=user["id"],
                new_value=f"المستخدم: {username}, الاسم: {full_name}, الدور: {role_id}"
            )
        
        return True, "تم إنشاء المستخدم بنجاح"
    except sqlite3.IntegrityError:
        return False, "اسم المستخدم موجود مسبقاً"
    finally:
        conn.close()

def logout_session():
    """مسح جلسة المستخدم"""
    import streamlit as st
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()
