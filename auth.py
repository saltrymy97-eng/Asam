# modules/auth.py - نظام المصادقة والصلاحيات
import streamlit as st
import bcrypt
from database import get_connection, init_db

def create_admin_if_needed():
    """إنشاء مستخدم مدير افتراضي إذا كانت قاعدة البيانات فارغة"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                  ("admin", hashed, "مدير النظام", "admin"))
        conn.commit()
    conn.close()

def login_form():
    st.title("🔐 تسجيل الدخول إلى نظام ERP")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT password, full_name, role FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if row and bcrypt.checkpw(password.encode(), row[0]):
            st.session_state.logged_in = True
            st.session_state.user = {
                "username": username,
                "full_name": row[1],
                "role": row[2]
            }
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

def logout():
    """مسح جلسة المستخدم والعودة إلى صفحة الدخول"""
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()

def show():
    """الدالة التي تستدعى من app.py لعرض صفحة الدخول"""
    init_db()  # التأكد من وجود قاعدة البيانات
    create_admin_if_needed()
    login_form()
