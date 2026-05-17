import streamlit as st
import sqlite3
import bcrypt
import pandas as pd

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_roles_tables():
    conn = get_conn()
    # جدول الأدوار
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    # جدول صلاحيات الأدوار
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER,
            module TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    """)
    # إضافة عمود role_id لجدول users إذا لم يكن موجوداً
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id)")
    except sqlite3.OperationalError:
        pass  # العمود موجود مسبقاً
    conn.commit()
    conn.close()

def seed_default_roles():
    conn = get_conn()
    roles = {
        "مدير": ["لوحة المعلومات", "المخزون", "المبيعات", "المشتريات", "الحسابات", "الموارد البشرية", "شجرة الحسابات", "القوائم المالية", "الصلاحيات"],
        "محاسب": ["لوحة المعلومات", "الحسابات", "شجرة الحسابات", "القوائم المالية"],
        "أمين مخزن": ["لوحة المعلومات", "المخزون"],
        "كاشير": ["لوحة المعلومات", "المبيعات"]
    }
    for role_name, modules in roles.items():
        conn.execute("INSERT OR IGNORE INTO roles (name) VALUES (?)", (role_name,))
        role = conn.execute("SELECT id FROM roles WHERE name=?", (role_name,)).fetchone()
        for mod in modules:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, module) VALUES (?, ?)",
                (role["id"], mod)
            )
    # جعل المستخدم admin مديراً إذا لم يكن له دور
    admin_role = conn.execute("SELECT id FROM roles WHERE name='مدير'").fetchone()
    if admin_role:
        conn.execute("UPDATE users SET role_id=? WHERE username='admin' AND role_id IS NULL", (admin_role["id"],))
    conn.commit()
    conn.close()

def check_permission(username, module):
    """التحقق من صلاحية المستخدم لدخول وحدة معينة"""
    conn = get_conn()
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
    conn = get_conn()
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

def show():
    st.title("🛡️ الصلاحيات والأدوار")
    create_roles_tables()
    seed_default_roles()

    tab1, tab2, tab3 = st.tabs(["الأدوار والصلاحيات", "المستخدمين", "تعيين دور"])

    with tab1:
        conn = get_conn()
        roles = conn.execute("SELECT * FROM roles").fetchall()
        for role in roles:
            with st.expander(f"🔑 {role['name']}"):
                perms = conn.execute(
                    "SELECT module FROM role_permissions WHERE role_id=?",
                    (role["id"],)
                ).fetchall()
                st.write("الصلاحيات:")
                for p in perms:
                    st.write(f"- {p['module']}")
        conn.close()

    with tab2:
        conn = get_conn()
        users = conn.execute("""
            SELECT u.username, u.full_name, u.role as old_role, r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
        """).fetchall()
        if users:
            df = pd.DataFrame(users, columns=["المستخدم", "الاسم", "الدور القديم", "الدور الحالي"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        conn.close()

    with tab3:
        conn = get_conn()
        users = conn.execute("SELECT id, username, full_name FROM users").fetchall()
        roles = conn.execute("SELECT id, name FROM roles").fetchall()

        if users and roles:
            user_names = [u["username"] for u in users]
            role_names = [r["name"] for r in roles]

            selected_user = st.selectbox("اختر المستخدم", user_names)
            selected_role = st.selectbox("اختر الدور", role_names)

            if st.button("💾 تعيين الدور"):
                user_id = next(u["id"] for u in users if u["username"] == selected_user)
                role_id = next(r["id"] for r in roles if r["name"] == selected_role)
                conn.execute("UPDATE users SET role_id=? WHERE id=?", (role_id, user_id))
                conn.commit()
                st.success(f"تم تعيين {selected_user} كـ {selected_role}")
                st.rerun()
        else:
            st.info("لا يوجد مستخدمون أو أدوار كافية")
        conn.close()
