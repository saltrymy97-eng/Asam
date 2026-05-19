# services/auth_service.py - منطق المصادقة وتغيير كلمة المرور
import bcrypt
from database import get_connection

def create_admin_if_needed():
    """إنشاء مستخدم مدير افتراضي إذا كانت قاعدة البيانات فارغة"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("admin5000".encode(), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                  ("admin", hashed.decode(), "مدير النظام", "admin"))
        conn.commit()
    conn.close()

def verify_user(username, password):
    """التحقق من صحة بيانات المستخدم"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password, full_name, role FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row[0]):
        return {"username": username, "full_name": row[1], "role": row[2]}
    return None

def change_password(username, old_password, new_password):
    """تغيير كلمة مرور المستخدم"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    row = c.fetchone()
    if not row or not bcrypt.checkpw(old_password.encode(), row[0]):
        conn.close()
        return False, "كلمة المرور الحالية غير صحيحة"
    
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    c.execute("UPDATE users SET password=? WHERE username=?", (hashed.decode(), username))
    conn.commit()
    conn.close()
    return True, "تم تغيير كلمة المرور بنجاح"

def logout_session():
    """مسح جلسة المستخدم"""
    import streamlit as st
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()
