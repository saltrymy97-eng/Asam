# payroll.py - كشف الرواتب (مع سجل التدقيق)
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from services.audit_service import log_action  # 🆕

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_payroll_tables():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER UNIQUE,
            basic_salary REAL DEFAULT 0,
            housing_allowance REAL DEFAULT 0,
            transport_allowance REAL DEFAULT 0,
            other_allowances REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            month TEXT NOT NULL,
            basic_salary REAL,
            housing_allowance REAL,
            transport_allowance REAL,
            other_allowances REAL,
            total_allowances REAL,
            deductions REAL,
            net_salary REAL,
            journal_entry_id INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.commit()
    conn.close()

def get_employees():
    conn = get_conn()
    emps = conn.execute("SELECT id, name FROM employees").fetchall()
    conn.close()
    return emps

def get_salary_config(employee_id):
    conn = get_conn()
    conf = conn.execute("SELECT * FROM employee_salaries WHERE employee_id=?", (employee_id,)).fetchone()
    conn.close()
    return conf

def save_salary_config(employee_id, basic, housing, transport, other, deductions):
    conn = get_conn()
    exists = conn.execute("SELECT id FROM employee_salaries WHERE employee_id=?", (employee_id,)).fetchone()
    if exists:
        conn.execute("""
            UPDATE employee_salaries SET basic_salary=?, housing_allowance=?, transport_allowance=?,
            other_allowances=?, deductions=? WHERE employee_id=?
        """, (basic, housing, transport, other, deductions, employee_id))
    else:
        conn.execute("""
            INSERT INTO employee_salaries (employee_id, basic_salary, housing_allowance, transport_allowance, other_allowances, deductions)
            VALUES (?,?,?,?,?,?)
        """, (employee_id, basic, housing, transport, other, deductions))
    conn.commit()
    conn.close()

def calculate_net(basic, housing, transport, other, deductions):
    total_allowances = housing + transport + other
    net = basic + total_allowances - deductions
    return total_allowances, net

def run_payroll(employee_id, month):
    """تشغيل كشف الراتب لشهر محدد وإنشاء قيد محاسبي"""
    conf = get_salary_config(employee_id)
    if not conf:
        return None, "لا توجد إعدادات راتب للموظف"
    
    basic = conf["basic_salary"]
    housing = conf["housing_allowance"]
    transport = conf["transport_allowance"]
    other = conf["other_allowances"]
    deductions = conf["deductions"]
    total_allowances, net = calculate_net(basic, housing, transport, other, deductions)
    
    conn = get_conn()
    
    desc = f"راتب شهر {month}"
    cur = conn.execute("INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
                       (date.today().strftime("%Y-%m-%d"), desc, month))
    entry_id = cur.lastrowid
    
    conn.execute("INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, 'مصروف الرواتب', ?, 0)",
                 (entry_id, basic + total_allowances))
    conn.execute("INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, 'البنك', 0, ?)",
                 (entry_id, net))
    if deductions > 0:
        conn.execute("INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, 'خصومات الموظفين', 0, ?)",
                     (entry_id, deductions))
    
    conn.execute("""
        INSERT INTO payroll_runs (employee_id, month, basic_salary, housing_allowance, transport_allowance,
        other_allowances, total_allowances, deductions, net_salary, journal_entry_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (employee_id, month, basic, housing, transport, other, total_allowances, deductions, net, entry_id))
    
    conn.commit()
    conn.close()
    return net, None

def get_payroll_history(month=None):
    conn = get_conn()
    query = """
        SELECT pr.id, e.name, pr.month, pr.basic_salary, pr.total_allowances, pr.deductions, pr.net_salary, pr.journal_entry_id
        FROM payroll_runs pr
        JOIN employees e ON pr.employee_id = e.id
    """
    params = ()
    if month:
        query += " WHERE pr.month = ?"
        params = (month,)
    query += " ORDER BY pr.month DESC, e.name"
    records = conn.execute(query, params).fetchall()
    conn.close()
    return records

def show():
    st.title("💰 كشف الرواتب")
    create_payroll_tables()
    
    tab1, tab2, tab3 = st.tabs(["⚙️ إعداد الرواتب", "🚀 تشغيل كشف الراتب", "📋 سجل الرواتب"])
    
    employees = get_employees()
    if not employees:
        st.warning("لا يوجد موظفون. أضف موظفين من وحدة الموارد البشرية أولاً.")
        return
    
    with tab1:
        st.subheader("إعدادات الرواتب الشهرية")
        emp_names = [e["name"] for e in employees]
        selected = st.selectbox("اختر الموظف", emp_names, key="sal_conf_emp")
        emp_id = next(e["id"] for e in employees if e["name"] == selected)
        
        conf = get_salary_config(emp_id)
        with st.form("salary_config_form"):
            col1, col2 = st.columns(2)
            basic = col1.number_input("الراتب الأساسي", min_value=0.0, step=0.01,
                                      value=float(conf["basic_salary"]) if conf else 0.0)
            housing = col2.number_input("بدل السكن", min_value=0.0, step=0.01,
                                        value=float(conf["housing_allowance"]) if conf else 0.0)
            transport = col1.number_input("بدل النقل", min_value=0.0, step=0.01,
                                          value=float(conf["transport_allowance"]) if conf else 0.0)
            other = col2.number_input("بدلات أخرى", min_value=0.0, step=0.01,
                                      value=float(conf["other_allowances"]) if conf else 0.0)
            deductions = col1.number_input("الخصومات", min_value=0.0, step=0.01,
                                           value=float(conf["deductions"]) if conf else 0.0)
            
            total_allowances, net = calculate_net(basic, housing, transport, other, deductions)
            col2.metric("صافي الراتب", f"{net:,.2f}")
            
            if st.form_submit_button("💾 حفظ الإعدادات"):
                save_salary_config(emp_id, basic, housing, transport, other, deductions)
                # 🆕 تسجيل في سجل التدقيق
                log_action(
                    username=st.session_state.user.get('username', 'admin'),
                    action="إعداد الراتب",
                    table_name="employee_salaries",
                    new_value=f"الموظف: {selected}, الأساسي: {basic:,.2f}"
                )
                st.success("تم حفظ إعدادات الراتب")
                st.rerun()
    
    with tab2:
        st.subheader("تشغيل كشف راتب شهري")
        emp_names = [e["name"] for e in employees]
        selected = st.selectbox("اختر الموظف", emp_names, key="sal_run_emp")
        emp_id = next(e["id"] for e in employees if e["name"] == selected)
        month = st.text_input("الشهر (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        
        conf = get_salary_config(emp_id)
        if conf:
            total_allowances, net = calculate_net(
                conf["basic_salary"], conf["housing_allowance"],
                conf["transport_allowance"], conf["other_allowances"],
                conf["deductions"]
            )
            st.write("**تفاصيل الراتب:**")
            col1, col2, col3 = st.columns(3)
            col1.metric("الأساسي", f"{conf['basic_salary']:,.2f}")
            col2.metric("البدلات", f"{total_allowances:,.2f}")
            col3.metric("الخصومات", f"{conf['deductions']:,.2f}")
            st.metric("الصافي", f"{net:,.2f}")
            
            if st.button("🚀 تشغيل الكشف وإنشاء القيد"):
                net_amount, error = run_payroll(emp_id, month)
                if error:
                    st.error(error)
                else:
                    # 🆕 تسجيل في سجل التدقيق
                    log_action(
                        username=st.session_state.user.get('username', 'admin'),
                        action="تشغيل كشف راتب",
                        table_name="payroll_runs",
                        new_value=f"الموظف: {selected}, الشهر: {month}, الصافي: {net_amount:,.2f}"
                    )
                    st.success(f"تم تشغيل كشف راتب {month} للموظف {selected}، صافي الراتب: {net_amount:,.2f} وتم إنشاء القيد المحاسبي.")
                    st.rerun()
        else:
            st.warning("يرجى إعداد الراتب من التبويب الأول أولاً.")
    
    with tab3:
        st.subheader("سجل الرواتب الشهرية")
        history = get_payroll_history()
        if history:
            df = pd.DataFrame(history, columns=["id", "الموظف", "الشهر", "الأساسي", "البدلات", "الخصومات", "الصافي", "رقم القيد"])
            df = df.drop("id", axis=1)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد سجل رواتب بعد")
