# services/roles_service.py – منطق الصلاحيات والأدوار
import sqlite3
from database import get_connection

def create_roles_tables():
    """إنشاء جداول الأدوار والصلاحيات إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER,
            module TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    """)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id)")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def seed_default_roles():
    """إنشاء الأدوار الافتراضية وصلاحياتها"""
    conn = get_connection()
    roles = {
        "مدير": ["لوحة المعلومات", "المخزون", "المبيعات", "المشتريات", "الحسابات", "الموارد البشرية", "شجرة الحسابات", "القوائم المالية", "الصلاحيات"],
        "محاسب": ["لوحة المعلومات", "الحسابات", "شجرة الحسابات", "القوائم المالية"],
        "أمين مخزن": ["لوحة المعلومات", "المخزون"],
        "كاشير": ["لوحة المعلومات", "المبيعات"]
    }
    for role_name, modules in roles.items():
        conn.execute("INSERT OR IGNORE INTO roles (name) VALUES (?)", (role_name,))
        conn.row_factory = sqlite3.Row
        role = conn.execute("SELECT id FROM roles WHERE name=?", (role_name,)).fetchone()
        if role:
            for mod in modules:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, module) VALUES (?, ?)",
                    (role["id"], mod)
                )
    admin_role = conn.execute("SELECT id FROM roles WHERE name='مدير'").fetchone()
    if admin_role:
        conn.execute("UPDATE users SET role_id=? WHERE username='admin' AND role_id IS NULL", (admin_role["id"],))
    conn.commit()
    conn.close()

def check_permission(username, module):
    """التحقق من صلاحية المستخدم لدخول وحدة معينة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT role_id FROM users WHERE username=?", (username,)).fetchone()
    if not user or not user["role_id"]:
        conn.close()
        return False
    perm = conn.execute(
        "SELECT COUNT(*) as cnt FROM role_permissions WHERE role_id=? AND module=?",
        (user["role_id"], module)
    ).fetchone()
    conn.close()
    return perm["cnt"] > 0

def get_allowed_modules(username):
    """جلب قائمة الوحدات المسموحة للمستخدم"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT role_id FROM users WHERE username=?", (username,)).fetchone()
    if not user or not user["role_id"]:
        conn.close()
        return []
    modules = conn.execute(
        "SELECT module FROM role_permissions WHERE role_id=?",
        (user["role_id"],)
    ).fetchall()
    conn.close()
    return [m["module"] for m in modules]

def get_all_roles():
    """جلب جميع الأدوار"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    roles = conn.execute("SELECT * FROM roles").fetchall()
    conn.close()
    return [dict(r) for r in roles]

def get_role_permissions(role_id):
    """جلب صلاحيات دور محدد"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    perms = conn.execute("SELECT module FROM role_permissions WHERE role_id=?", (role_id,)).fetchall()
    conn.close()
    return [p["module"] for p in perms]

def get_all_users_with_roles():
    """جلب جميع المستخدمين مع أدوارهم"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    users = conn.execute("""
        SELECT u.id, u.username, u.full_name, u.role as old_role, r.name as role_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
    """).fetchall()
    conn.close()
    return [dict(u) for u in users]

def assign_role_to_user(user_id, role_id):
    """تعيين دور لمستخدم"""
    conn = get_connection()
    conn.execute("UPDATE users SET role_id=? WHERE id=?", (role_id, user_id))
    conn.commit()
    conn.close()
    return True
