# services/roles_service.py – منطق الصلاحيات والأدوار (v2.0)
# ✅ Connection Registry — لا conn.close()
import sqlite3
from database import get_connection, close_connection
from services.audit_service import log_action


def create_roles_tables(conn=None):
    """إنشاء جداول الأدوار والصلاحيات"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                module TEXT NOT NULL,
                can_view INTEGER DEFAULT 1 CHECK(can_view IN (0,1)),
                can_add INTEGER DEFAULT 0 CHECK(can_add IN (0,1)),
                can_edit INTEGER DEFAULT 0 CHECK(can_edit IN (0,1)),
                can_delete INTEGER DEFAULT 0 CHECK(can_delete IN (0,1)),
                can_approve INTEGER DEFAULT 0 CHECK(can_approve IN (0,1)),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                UNIQUE(role_id, module)
            )
        """)
        if own_conn:
            conn.execute("COMMIT")
    finally:
        if own_conn:
            close_connection(conn)


def seed_default_roles(conn=None):
    """إنشاء الأدوار الافتراضية وصلاحياتها"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    roles = {
        "مدير": {
            "modules": ["لوحة المعلومات", "المخزون", "المبيعات", "المشتريات",
                        "الحسابات", "الموارد البشرية", "شجرة الحسابات",
                        "القوائم المالية", "الصلاحيات"],
            "full_access": True
        },
        "محاسب": {
            "modules": ["لوحة المعلومات", "الحسابات", "شجرة الحسابات", "القوائم المالية"],
            "full_access": False
        },
        "أمين مخزن": {
            "modules": ["لوحة المعلومات", "المخزون"],
            "full_access": False
        },
        "كاشير": {
            "modules": ["لوحة المعلومات", "المبيعات"],
            "full_access": False
        }
    }

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        for role_name, config in roles.items():
            conn.execute("INSERT OR IGNORE INTO roles (name) VALUES (?)", (role_name,))
            conn.row_factory = sqlite3.Row
            role = conn.execute("SELECT id FROM roles WHERE name=?", (role_name,)).fetchone()
            if role:
                for mod in config["modules"]:
                    if config["full_access"]:
                        conn.execute("""
                            INSERT OR IGNORE INTO role_permissions
                            (role_id, module, can_view, can_add, can_edit, can_delete, can_approve)
                            VALUES (?, ?, 1, 1, 1, 1, 1)
                        """, (role["id"], mod))
                    else:
                        conn.execute("""
                            INSERT OR IGNORE INTO role_permissions
                            (role_id, module, can_view, can_add, can_edit, can_delete, can_approve)
                            VALUES (?, ?, 1, 1, 0, 0, 0)
                        """, (role["id"], mod))

        admin_role = conn.execute("SELECT id FROM roles WHERE name='مدير'").fetchone()
        if admin_role:
            conn.execute(
                "UPDATE users SET role_id=? WHERE username='admin' AND role_id IS NULL",
                (admin_role["id"],)
            )

        if own_conn:
            conn.execute("COMMIT")
    except Exception:
        if own_conn:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        raise
    finally:
        if own_conn:
            close_connection(conn)


def check_permission(username, module, action="view", conn=None):
    """التحقق من صلاحية المستخدم"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        conn.row_factory = sqlite3.Row
        user = conn.execute(
            "SELECT role_id FROM users WHERE username=?", (username,)
        ).fetchone()

        if not user or not user["role_id"]:
            return False

        action_column = f"can_{action}"
        if action_column not in ["can_view", "can_add", "can_edit",
                                  "can_delete", "can_approve"]:
            action_column = "can_view"

        perm = conn.execute(
            f"SELECT {action_column} as allowed FROM role_permissions WHERE role_id=? AND module=?",
            (user["role_id"], module)
        ).fetchone()
        return perm["allowed"] == 1 if perm else False
    finally:
        if own_conn:
            close_connection(conn)


def get_allowed_modules(username, conn=None):
    """الوحدات المسموحة للمستخدم"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        conn.row_factory = sqlite3.Row
        user = conn.execute(
            "SELECT role_id FROM users WHERE username=?", (username,)
        ).fetchone()

        if not user or not user["role_id"]:
            return []

        modules = conn.execute(
            "SELECT module FROM role_permissions WHERE role_id=? AND can_view=1",
            (user["role_id"],)
        ).fetchall()
        return [m["module"] for m in modules]
    finally:
        if own_conn:
            close_connection(conn)


def get_all_roles(conn=None):
    """جلب جميع الأدوار"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        roles = conn.execute("SELECT * FROM roles").fetchall()
        return [dict(r) for r in roles]
    finally:
        if own_conn:
            close_connection(conn)


def get_role_permissions(role_id, conn=None):
    """صلاحيات دور محدد"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        perms = conn.execute(
            "SELECT module, can_view, can_add, can_edit, can_delete, can_approve "
            "FROM role_permissions WHERE role_id=?",
            (role_id,)
        ).fetchall()
        return [dict(p) for p in perms]
    finally:
        if own_conn:
            close_connection(conn)


def get_all_users_with_roles(conn=None):
    """جميع المستخدمين مع أدوارهم"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.row_factory = sqlite3.Row
        users = conn.execute("""
            SELECT u.id, u.username, u.full_name, r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
        """).fetchall()
        return [dict(u) for u in users]
    finally:
        if own_conn:
            close_connection(conn)


def assign_role_to_user(user_id, role_id, conn=None):
    """تعيين دور لمستخدم"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    username_str = None
    role_name = None

    try:
        conn.row_factory = sqlite3.Row

        user = conn.execute(
            "SELECT username FROM users WHERE id=?", (user_id,)
        ).fetchone()
        role = conn.execute(
            "SELECT name FROM roles WHERE id=?", (role_id,)
        ).fetchone()

        username_str = user["username"] if user else None
        role_name = role["name"] if role else None

        if own_conn:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE users SET role_id=? WHERE id=?", (role_id, user_id))
        if own_conn:
            conn.execute("COMMIT")
    except Exception:
        if own_conn:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        raise
    finally:
        if own_conn:
            close_connection(conn)

    # log_action خارج Transaction
    if username_str and role_name:
        try:
            log_action(
                username="admin",
                action="تعيين دور",
                table_name="users",
                record_id=user_id,
                new_value=f"المستخدم: {username_str}, الدور الجديد: {role_name}"
            )
        except Exception:
            pass

    return True
