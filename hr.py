# modules/hr.py - إدارة الموارد البشرية
import streamlit as st
import pandas as pd
from database import get_connection

def show():
    st.title("👥 الموارد البشرية")
    conn = get_connection()

    tab1, tab2, tab3 = st.tabs(["الموظفين", "إضافة موظف", "الحضور والانصراف"])

    # ---------- الموظفين ----------
    with tab1:
        st.subheader("قائمة الموظفين")
        employees_df = pd.read_sql_query("SELECT * FROM employees", conn)
        if not employees_df.empty:
            st.dataframe(employees_df, use_container_width=True)
        else:
            st.info("لا يوجد موظفون بعد")

    # ---------- إضافة موظف ----------
    with tab2:
        st.subheader("إضافة موظف جديد")
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
                    conn.execute(
                        "INSERT INTO employees (name, position, salary, join_date) VALUES (?, ?, ?, ?)",
                        (name, position, salary, join_date.strftime("%Y-%m-%d"))
                    )
                    conn.commit()
                    st.success(f"تمت إضافة الموظف '{name}'")
                    st.rerun()

    # ---------- الحضور والانصراف ----------
    with tab3:
        st.subheader("تسجيل الحضور اليومي")
        employees_list = pd.read_sql_query("SELECT id, name FROM employees", conn)
        if not employees_list.empty:
            emp_names = employees_list["name"].tolist()
            selected_emp = st.selectbox("اختر الموظف", emp_names)
            emp_id = int(employees_list[employees_list["name"] == selected_emp]["id"].values[0])

            date = st.date_input("التاريخ")
            status = st.selectbox("الحالة", ["حاضر", "غائب", "إجازة", "مريض"])

            if st.button("تسجيل الحضور"):
                conn.execute(
                    "INSERT INTO attendance (employee_id, date, status) VALUES (?, ?, ?)",
                    (emp_id, date.strftime("%Y-%m-%d"), status)
                )
                conn.commit()
                st.success("تم تسجيل الحضور")

            st.markdown("---")
            st.subheader("سجل الحضور")
            attendance_df = pd.read_sql_query(
                """SELECT a.date, e.name, a.status 
                   FROM attendance a
                   JOIN employees e ON a.employee_id = e.id
                   ORDER BY a.date DESC, e.name""",
                conn
            )
            if not attendance_df.empty:
                st.dataframe(attendance_df, use_container_width=True)
        else:
            st.warning("أضف موظفين أولاً")

    conn.close()
