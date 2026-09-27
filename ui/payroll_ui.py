# ui/payroll_ui.py – واجهة كشف الرواتب (v2.0)
# ✅ قائمة موحّدة للدفع + فحص الرصيد + عرض فوري
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
    get_payroll_history,
)
from services.expenses_service import get_payment_accounts
from services.audit_service import log_action


# ========== ألوان التصميم ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"


def _format_account_label(acc):
    """تنسيق عرض الحساب مع الرصيد والنوع"""
    icon = "💵" if acc["type"] == "cash" else "🏦"
    return (
        f"{icon} {acc['name']} "
        f"({acc['currency']}) — الرصيد: {acc['balance']:,.2f}"
    )


def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">💰 كشف الرواتب</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إعداد وتشغيل وسجل رواتب الموظفين</p>
    </div>
    """, unsafe_allow_html=True)

    create_payroll_tables()

    tab1, tab2, tab3 = st.tabs([
        "⚙️ إعداد الرواتب",
        "🚀 تشغيل كشف الراتب",
        "📋 سجل الرواتب",
    ])

    employees = get_employees()
    if not employees:
        st.warning("لا يوجد موظفون. أضف موظفين من وحدة الموارد البشرية أولاً.")
        return

    # ============================================================
    # تبويب 1: إعداد الرواتب
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>إعدادات الرواتب الشهرية</h3>",
                    unsafe_allow_html=True)

        emp_names = [e["name"] for e in employees]
        selected = st.selectbox("اختر الموظف", emp_names, key="sal_conf_emp")
        emp_id = next(e["id"] for e in employees if e["name"] == selected)

        conf = get_salary_config(emp_id)

        with st.form("salary_config_form"):
            col1, col2 = st.columns(2)
            basic = col1.number_input(
                "الراتب الأساسي", min_value=0.0, step=0.01,
                value=float(conf["basic_salary"]) if conf else 0.0
            )
            housing = col2.number_input(
                "بدل السكن", min_value=0.0, step=0.01,
                value=float(conf["housing_allowance"]) if conf else 0.0
            )
            transport = col1.number_input(
                "بدل النقل", min_value=0.0, step=0.01,
                value=float(conf["transport_allowance"]) if conf else 0.0
            )
            other = col2.number_input(
                "بدلات أخرى", min_value=0.0, step=0.01,
                value=float(conf["other_allowances"]) if conf else 0.0
            )
            deductions = col1.number_input(
                "الخصومات", min_value=0.0, step=0.01,
                value=float(conf["deductions"]) if conf else 0.0
            )

            total_allowances, net = calculate_net(
                basic, housing, transport, other, deductions
            )
            col2.metric("صافي الراتب", f"{net:,.2f}")

            if st.form_submit_button("💾 حفظ الإعدادات"):
                ok, err = save_salary_config(
                    emp_id, basic, housing, transport, other, deductions
                )
                if err:
                    st.error(f"فشل: {err}")
                else:
                    log_action(
                        username=st.session_state.user.get('username', 'admin'),
                        action="إعداد الراتب",
                        table_name="employee_salaries",
                        new_value=f"الموظف: {selected}, الأساسي: {basic:,.2f}"
                    )
                    st.success("✅ تم حفظ إعدادات الراتب")
                    st.rerun()

    # ============================================================
    # تبويب 2: تشغيل كشف الراتب
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تشغيل كشف راتب شهري</h3>",
                    unsafe_allow_html=True)

        emp_names = [e["name"] for e in employees]
        selected = st.selectbox("اختر الموظف", emp_names, key="sal_run_emp")
        emp_id = next(e["id"] for e in employees if e["name"] == selected)
        month = st.text_input("الشهر (YYYY-MM)",
                              value=date.today().strftime("%Y-%m"))

        conf = get_salary_config(emp_id)
        if not conf:
            st.warning("⚠️ يرجى إعداد الراتب من التبويب الأول أولاً.")
            return

        total_allowances, net = calculate_net(
            float(conf["basic_salary"] or 0),
            float(conf["housing_allowance"] or 0),
            float(conf["transport_allowance"] or 0),
            float(conf["other_allowances"] or 0),
            float(conf["deductions"] or 0),
        )

        # عرض تفاصيل الراتب
        st.write("**تفاصيل الراتب:**")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("الأساسي", f"{float(conf['basic_salary']):,.2f}")
        col2.metric("البدلات", f"{total_allowances:,.2f}")
        col3.metric("الخصومات", f"{float(conf['deductions']):,.2f}")
        col4.metric("الصافي", f"{net:,.2f}")

        # ============================================================
        # ✅ اختيار حساب الدفع + فحص الرصيد
        # ============================================================
        st.markdown("---")
        st.markdown(f"<h4 style='color:{ACCENT_ORANGE};'>حساب الدفع</h4>",
                    unsafe_allow_html=True)

        payment_accounts = get_payment_accounts()
        if not payment_accounts:
            st.error("⚠️ لا يوجد صندوق أو بنك نشط. أضف واحداً أولاً.")
            return

        # قائمة موحّدة
        labels = [_format_account_label(a) for a in payment_accounts]
        selected_label = st.selectbox(
            "من أي حساب سيتم صرف الرواتب؟",
            labels,
            key="payroll_account_sel"
        )
        idx = labels.index(selected_label)
        selected_acc = payment_accounts[idx]

        # ✅ فحص فوري
        balance_ok = True
        if net > selected_acc["balance"]:
            st.error(
                f"⚠️ **الرصيد غير كافٍ في {selected_acc['name']}**\n\n"
                f"المتاح: **{selected_acc['balance']:,.2f}** {selected_acc['currency']}\n\n"
                f"المطلوب: **{net:,.2f}** {selected_acc['currency']}\n\n"
                f"❌ لن تتم العملية"
            )
            balance_ok = False
        else:
            st.info(
                f"✅ الرصيد كافٍ — سيتبقى "
                f"**{selected_acc['balance'] - net:,.2f}** {selected_acc['currency']}"
            )

        # ============================================================
        # زر التشغيل
        # ============================================================
        if "saving_payroll" not in st.session_state:
            st.session_state.saving_payroll = False

        can_run = (
            not st.session_state.saving_payroll
            and balance_ok
            and net > 0
        )

        if st.button(
            "🚀 تشغيل الكشف وإنشاء القيد",
            type="primary",
            disabled=not can_run,
            key="run_payroll_btn"
        ):
            st.session_state.saving_payroll = True
            st.session_state.payroll_args = {
                "emp_id": emp_id,
                "emp_name": selected,
                "month": month,
                "account_code": selected_acc["code"],
                "payment_method": selected_acc["type"],
            }
            st.rerun()

        if st.session_state.saving_payroll:
            try:
                args = st.session_state.get("payroll_args", {})
                net_amount, error = run_payroll(
                    args.get("emp_id"),
                    args.get("month"),
                    payment_account_code=args.get("account_code"),
                    payment_method=args.get("payment_method"),
                )
                if error:
                    st.error(f"❌ {error}")
                else:
                    log_action(
                        username=st.session_state.user.get('username', 'admin'),
                        action="تشغيل كشف راتب",
                        table_name="payroll_runs",
                        new_value=(
                            f"الموظف: {args.get('emp_name')}, "
                            f"الشهر: {args.get('month')}, "
                            f"الصافي: {net_amount:,.2f}"
                        )
                    )
                    st.success(
                        f"✅ تم تشغيل كشف راتب **{args.get('month')}** "
                        f"للموظف **{args.get('emp_name')}** "
                        f"— الصافي: **{net_amount:,.2f}**"
                    )
            except Exception as e:
                st.error(f"❌ خطأ غير متوقع: {e}")
            finally:
                st.session_state.saving_payroll = False
                st.session_state.pop("payroll_args", None)
                st.rerun()

    # ============================================================
    # تبويب 3: سجل الرواتب
    # ============================================================
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>سجل الرواتب الشهرية</h3>",
                    unsafe_allow_html=True)

        history = get_payroll_history()
        if history:
            df = pd.DataFrame(history)
            df_display = df.rename(columns={
                "id": "الرقم",
                "name": "الموظف",
                "month": "الشهر",
                "basic_salary": "الأساسي",
                "total_allowances": "البدلات",
                "deductions": "الخصومات",
                "net_salary": "الصافي",
                "journal_entry_id": "رقم القيد",
            })
            cols = ["الرقم", "الموظف", "الشهر", "الأساسي",
                    "البدلات", "الخصومات", "الصافي", "رقم القيد"]
            cols = [c for c in cols if c in df_display.columns]

            # ✅ إجمالي
            total = df["net_salary"].sum()
            st.markdown(
                f"<div style='background:rgba(16,185,129,0.15); "
                f"padding:0.75rem; border-radius:8px; text-align:right; "
                f"color:{TEXT_PRIMARY};'>"
                f"💰 **إجمالي الرواتب المصروفة:** {total:,.2f}"
                f"</div>",
                unsafe_allow_html=True
            )

            st.dataframe(df_display[cols],
                         use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد سجل رواتب بعد")
