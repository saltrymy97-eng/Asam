# ui/payroll_ui.py – واجهة كشف الرواتب (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from datetime import date
from services.payroll_service import (
    create_payroll_tables,
    get_employees,
    get_salary_config,
    save_salary_config,
    calculate_net,
    run_payroll,
    get_payroll_history
)
from services.audit_service import log_action

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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">💰 كشف الرواتب</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إعداد وتشغيل وسجل رواتب الموظفين</p>
    </div>
    """, unsafe_allow_html=True)

    create_payroll_tables()
    
    tab1, tab2, tab3 = st.tabs(["⚙️ إعداد الرواتب", "🚀 تشغيل كشف الراتب", "📋 سجل الرواتب"])
    
    employees = get_employees()
    if not employees:
        st.warning("لا يوجد موظفون. أضف موظفين من وحدة الموارد البشرية أولاً.")
        return
    
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>إعدادات الرواتب الشهرية</h3>", unsafe_allow_html=True)
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
                log_action(
                    username=st.session_state.user.get('username', 'admin'),
                    action="إعداد الراتب",
                    table_name="employee_salaries",
                    new_value=f"الموظف: {selected}, الأساسي: {basic:,.2f}"
                )
                st.success("تم حفظ إعدادات الراتب")
                st.rerun()
    
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تشغيل كشف راتب شهري</h3>", unsafe_allow_html=True)
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
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>سجل الرواتب الشهرية</h3>", unsafe_allow_html=True)
        history = get_payroll_history()
        if history:
            df = pd.DataFrame(history, columns=["id", "الموظف", "الشهر", "الأساسي", "البدلات", "الخصومات", "الصافي", "رقم القيد"])
            df = df.drop("id", axis=1)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد سجل رواتب بعد")
