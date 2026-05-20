# ui/hr_ui.py – واجهة الموارد البشرية (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from datetime import date
from services.hr_service import (
    get_all_employees,
    add_employee,
    get_employees_for_select,
    record_attendance,
    get_attendance_history
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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">👥 الموارد البشرية</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الموظفين والحضور والانصراف</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["👥 الموظفين", "➕ إضافة موظف", "📅 الحضور والانصراف"])

    # ---------- الموظفين ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>قائمة الموظفين</h3>", unsafe_allow_html=True)
        employees = get_all_employees()
        if employees:
            st.dataframe(pd.DataFrame(employees), use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد موظفون بعد")

    # ---------- إضافة موظف ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة موظف جديد</h3>", unsafe_allow_html=True)
        with st.form("add_employee"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم الموظف")
            position = col2.text_input("المسمى الوظيفي")
            salary = st.number_input("الراتب", min_value=0.0, step=0.01)
            join_date = st.date_input("تاريخ الالتحاق")
            if st.form_submit_button("إضافة"):
                if not name:
                    st.error("الاسم مطلوب")
                else:
                    success, error = add_employee(
                        name, position, salary,
                        join_date.strftime("%Y-%m-%d"),
                        st.session_state.user.get('username', 'admin')
                    )
                    if success:
                        st.success(f"تمت إضافة الموظف '{name}'")
                        st.rerun()
                    else:
                        st.error(f"فشل في إضافة الموظف: {error}")

    # ---------- الحضور والانصراف ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>تسجيل الحضور اليومي</h3>", unsafe_allow_html=True)
        employees_list = get_employees_for_select()
        if employees_list:
            emp_names = [e['name'] for e in employees_list]
            selected_emp = st.selectbox("اختر الموظف", emp_names)
            emp_id = next(e['id'] for e in employees_list if e['name'] == selected_emp)

            att_date = st.date_input("التاريخ", value=date.today())
            status = st.selectbox("الحالة", ["حاضر", "غائب", "إجازة", "مريض"])

            if st.button("تسجيل الحضور"):
                success, error = record_attendance(
                    emp_id, selected_emp,
                    att_date.strftime("%Y-%m-%d"), status,
                    st.session_state.user.get('username', 'admin')
                )
                if success:
                    st.success("تم تسجيل الحضور")
                    st.rerun()
                else:
                    st.error(f"فشل في تسجيل الحضور: {error}")

            st.markdown("---")
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>سجل الحضور</h4>", unsafe_allow_html=True)
            attendance = get_attendance_history()
            if attendance:
                st.dataframe(pd.DataFrame(attendance), use_container_width=True, hide_index=True)
        else:
            st.warning("أضف موظفين أولاً")
