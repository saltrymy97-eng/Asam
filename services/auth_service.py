# services/auth_service.py - منطق المصادقة (v2.0)
# ✅ Connection Registry — لا conn.close()
import sqlite3
import bcrypt
from database import get_connection, close_connection
from services.audit_service import log_action


def verify_user(username, password):
    """التحقق من صحة بيانات المستخدم"""
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT password, full_name, role_id FROM users WHERE username=?",
            (username,)
        )
        row = c.fetchone()

        if not row:
            return None

        stored_password = row["password"]
        if isinstance(stored_password, str):
            stored_password = stored_password.encode('utf-8')

        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            return {
                "username": username,
                "full_name": row["full_name"],
                "role_id": row["role_id"]
            }
        return None
    finally:
        close_connection(conn)


def change_password(username, old_password, new_password):
    """تغيير كلمة مرور المستخدم"""
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 1. التحقق من وجود المستخدم
        c.execute("SELECT password FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if not row:
            return False, "المستخدم غير موجود"

        # 2. التحقق من كلمة المرور القديمة
        stored_password = row["password"]
        if isinstance(stored_password, str):
            stored_password = stored_password.encode('utf-8')

        if not bcrypt.checkpw(old_password.encode('utf-8'), stored_password):
            return False, "كلمة المرور الحالية غير صحيحة"

        # 3. تشفير كلمة المرور الجديدة وحفظها
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
        conn.execute("COMMIT")

    except Exception as e:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except Exception:
            pass
        return False, str(e)
    finally:
        close_connection(conn)

    # 4. تسجيل التغيير في سجل التدقيق (خارج Transaction)
    try:
        log_action(
            username=username,
            action="تغيير كلمة المرور",
            table_name="users",
            new_value=f"تم تغيير كلمة المرور للمستخدم: {username}"
        )
    except Exception:
        pass

    return True, "تم تغيير كلمة المرور بنجاح. يرجى تسجيل الخروج وإعادة الدخول."


def create_user(username, password, full_name, role_id=None):
    """إنشاء مستخدم جديد"""
    conn = get_connection()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO users (username, password, full_name, role_id) VALUES (?, ?, ?, ?)",
            (username, hashed, full_name, role_id)
        )

        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        user_id = user["id"] if user else None

        conn.execute("COMMIT")

        # log خارج Transaction
        if user_id:
            try:
                log_action(
                    username=username,
                    action="إنشاء مستخدم",
                    table_name="users",
                    record_id=user_id,
                    new_value=f"المستخدم: {username}, الاسم: {full_name}, الدور: {role_id}"
                )
            except Exception:
                pass

        return True, "تم إنشاء المستخدم بنجاح"

    except sqlite3.IntegrityError:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except Exception:
            pass
        return False, "اسم المستخدم موجود مسبقاً"
    except Exception as e:
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
        except Exception:
            pass
        return False, str(e)
    finally:
        close_connection(conn)


def logout_session():
    """مسح جلسة المستخدم"""
    import streamlit as st
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()
