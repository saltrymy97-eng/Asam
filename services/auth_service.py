# services/auth_service.py - منطق المصادقة (v2.1)
# ✅ Connection Registry — لا conn.close()
# ✅ v2.1: تسجيل كامل لأحداث الأمان
import sqlite3
import bcrypt
from database import get_connection, close_connection
from services.audit_service import log_action


def verify_user(username, password, ip_address=None):
    """
    التحقق من صحة بيانات المستخدم.
    ✅ يسجّل محاولات الدخول (ناجحة/فاشلة) في سجل التدقيق.
    """
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT id, password, full_name, role_id FROM users WHERE username=?",
            (username,)
        )
        row = c.fetchone()

        # ❌ المستخدم غير موجود
        if not row:
            _log_login_attempt(
                username=username,
                success=False,
                reason="المستخدم غير موجود",
                ip_address=ip_address,
            )
            return None

        stored_password = row["password"]
        if isinstance(stored_password, str):
            stored_password = stored_password.encode('utf-8')

        # ✅ كلمة المرور صحيحة
        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            _log_login_attempt(
                username=username,
                success=True,
                user_id=row["id"],
                ip_address=ip_address,
            )
            return {
                "username": username,
                "full_name": row["full_name"],
                "role_id": row["role_id"],
            }

        # ❌ كلمة المرور خاطئة
        _log_login_attempt(
            username=username,
            success=False,
            reason="كلمة مرور خاطئة",
            user_id=row["id"],
            ip_address=ip_address,
        )
        return None

    finally:
        close_connection(conn)


def _log_login_attempt(username, success, user_id=None,
                       reason=None, ip_address=None):
    """
    ✅ تسجيل محاولة دخول (موحّد لتفادي التكرار).
    """
    try:
        if success:
            log_action(
                username=username,
                action="🔓 تسجيل دخول ناجح",
                table_name="users",
                record_id=user_id,
                new_value={
                    "ip": ip_address or "محلي",
                    "status": "success",
                },
                user_id=user_id,
                ip_address=ip_address,
            )
        else:
            log_action(
                username=username,
                action="🔒 محاولة دخول فاشلة",
                table_name="users",
                record_id=user_id,
                new_value={
                    "ip": ip_address or "محلي",
                    "reason": reason or "غير معروف",
                    "status": "failed",
                },
                user_id=user_id,
                ip_address=ip_address,
            )
    except Exception as e:
        print(f"⚠️ فشل تسجيل محاولة الدخول: {e}")


def change_password(username, old_password, new_password, changed_by=None):
    """
    تغيير كلمة مرور المستخدم.
    ✅ v2.1: تسجيل كامل مع user_id
    """
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 1. التحقق من وجود المستخدم
        c.execute(
            "SELECT id, password FROM users WHERE username=?",
            (username,)
        )
        row = c.fetchone()
        if not row:
            return False, "المستخدم غير موجود"

        user_id = row["id"]

        # 2. التحقق من كلمة المرور القديمة
        stored_password = row["password"]
        if isinstance(stored_password, str):
            stored_password = stored_password.encode('utf-8')

        if not bcrypt.checkpw(old_password.encode('utf-8'), stored_password):
            # ✅ تسجيل محاولة فاشلة
            try:
                log_action(
                    username=changed_by or username,
                    action="⚠️ محاولة تغيير كلمة مرور فاشلة",
                    table_name="users",
                    record_id=user_id,
                    new_value=f"سبب: كلمة المرور الحالية خاطئة للمستخدم {username}",
                )
            except Exception:
                pass
            return False, "كلمة المرور الحالية غير صحيحة"

        # 3. تشفير كلمة المرور الجديدة
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        c.execute(
            "UPDATE users SET password=? WHERE username=?",
            (hashed, username)
        )
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

    # 4. تسجيل ناجح
    try:
        log_action(
            username=changed_by or username,
            action="🔑 تغيير كلمة مرور",
            table_name="users",
            record_id=user_id,
            old_value="كلمة مرور سابقة",
            new_value=f"تم تغيير كلمة مرور المستخدم: {username}",
            user_id=user_id,
        )
    except Exception:
        pass

    return True, "تم تغيير كلمة المرور بنجاح. يرجى تسجيل الخروج وإعادة الدخول."


def create_user(username, password, full_name, role_id=None,
                created_by="admin"):
    """
    إنشاء مستخدم جديد.
    ✅ v2.1: created_by يحدد مَن أنشأ (وليس اسم المستخدم الجديد).
    """
    conn = get_connection()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO users (username, password, full_name, role_id) "
            "VALUES (?, ?, ?, ?)",
            (username, hashed, full_name, role_id)
        )

        conn.row_factory = sqlite3.Row
        user = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        user_id = user["id"] if user else None

        conn.execute("COMMIT")

        # ✅ log خارج Transaction — بـ created_by
        if user_id:
            try:
                log_action(
                    username=created_by,
                    action="👤 إنشاء مستخدم جديد",
                    table_name="users",
                    record_id=user_id,
                    new_value={
                        "username": username,
                        "full_name": full_name,
                        "role_id": role_id,
                        "created_by": created_by,
                    },
                    user_id=user_id,
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


def logout_session(username=None, user_id=None):
    """
    مسح جلسة المستخدم.
    ✅ v2.1: تسجيل خروج في سجل التدقيق.
    """
    import streamlit as st

    # ✅ سجّل الخروج قبل المسح
    if username:
        try:
            log_action(
                username=username,
                action="🚪 تسجيل خروج",
                table_name="users",
                record_id=user_id,
                new_value="انتهت الجلسة",
                user_id=user_id,
            )
        except Exception:
            pass

    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()
