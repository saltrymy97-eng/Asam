# ui/roles_ui.py – واجهة الصلاحيات والأدوار (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from services.roles_service import (
    create_roles_tables,
    seed_default_roles,
    get_all_roles,
    get_role_permissions,
    get_all_users_with_roles,
    assign_role_to_user
)

# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🛡️ الصلاحيات والأدوار</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الأدوار والمستخدمين والصلاحيات</p>
    </div>
    """, unsafe_allow_html=True)

    create_roles_tables()
    seed_default_roles()

    tab1, tab2, tab3 = st.tabs(["🔑 الأدوار والصلاحيات", "👥 المستخدمين", "⚙️ تعيين دور"])

    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>الأدوار والصلاحيات</h3>", unsafe_allow_html=True)
        roles = get_all_roles()
        if roles:
            for role in roles:
                with st.expander(f"🔑 {role['name']}"):
                    perms = get_role_permissions(role["id"])
                    if perms:
                        for p in perms:
                            st.write(f"- {p}")
                    else:
                        st.write("لا توجد صلاحيات")
        else:
            st.info("لا توجد أدوار")

    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>المستخدمين وأدوارهم</h3>", unsafe_allow_html=True)
        users = get_all_users_with_roles()
        if users:
            df = pd.DataFrame(users)
            df = df.rename(columns={
                "username": "المستخدم",
                "full_name": "الاسم",
                "old_role": "الدور القديم",
                "role_name": "الدور الحالي"
            })
            st.dataframe(df[["المستخدم", "الاسم", "الدور القديم", "الدور الحالي"]], use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد مستخدمون")

    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>تعيين دور لمستخدم</h3>", unsafe_allow_html=True)
        users = get_all_users_with_roles()
        roles = get_all_roles()

        if users and roles:
            user_names = [u["username"] for u in users]
            role_names = [r["name"] for r in roles]

            selected_user = st.selectbox("اختر المستخدم", user_names)
            selected_role = st.selectbox("اختر الدور", role_names)

            if st.button("💾 تعيين الدور"):
                user_id = next(u["id"] for u in users if u["username"] == selected_user)
                role_id = next(r["id"] for r in roles if r["name"] == selected_role)
                assign_role_to_user(user_id, role_id)
                st.success(f"تم تعيين {selected_user} كـ {selected_role}")
                st.rerun()
        else:
            st.info("لا يوجد مستخدمون أو أدوار كافية")
