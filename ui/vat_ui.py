# ui/vat_ui.py – واجهة إدارة ضريبة القيمة المضافة (تصميم زجاجي فخم)
import streamlit as st
from datetime import date
import pandas as pd
from services.vat_service import (
    create_vat_table,
    get_vat_rate,
    update_vat_rate,
    calculate_vat,
    get_vat_report,
    get_vat_history
)

# ========== ألوان التصميم الزجاجي ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"

def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">إدارة ضريبة القيمة المضافة والتقارير</p>
    </div>""", unsafe_allow_html=True)

def h3(title, color=BL):
    st.markdown(f"""<h3 style="color:{color};text-align:right;margin-bottom:1rem;">{title}</h3>""", unsafe_allow_html=True)

def glass(content):
    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{T};font-size:1.1rem;">{content}</div>""", unsafe_allow_html=True)

def kpi_card(icon, title, value, color):
    return f"""<div style="background:rgba(255,255,255,0.10);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.20);border-radius:16px;padding:1.2rem;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.37);margin-bottom:0.8rem;">
        <div style="font-size:2rem;margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{S};font-size:0.8rem;">{title}</div>
        <div style="color:{color};font-size:1.6rem;font-weight:800;">{value}</div>
    </div>"""

def show():
    create_vat_table()
    h1("🧾 ضريبة القيمة المضافة (VAT)")

    tab1, tab2, tab3 = st.tabs(["⚙️ الإعدادات", "🧮 حاسبة الضريبة", "📊 التقارير"])

    # ---------- تبويب الإعدادات ----------
    with tab1:
        h3("إعدادات الضريبة", BL)
        current_rate = get_vat_rate()

        col1, col2 = st.columns(2)
        with col1:
            glass(f'النسبة الحالية: <span style="color:{GR};font-weight:800;">{current_rate * 100:.0f}%</span>')
        with col2:
            new_rate = st.number_input("تحديث النسبة (%)", min_value=0.0, max_value=100.0, value=current_rate * 100, step=0.5) / 100
            if st.button("💾 تحديث النسبة", type="primary"):
                update_vat_rate(new_rate)
                st.success(f"تم تحديث نسبة الضريبة إلى {new_rate * 100:.0f}%")
                st.rerun()

        st.markdown("---")
        h3("سجل التغييرات", PR)
        history = get_vat_history()
        if history:
            df = pd.DataFrame(history)
            df = df.rename(columns={"name": "الاسم", "rate": "النسبة", "is_active": "نشط", "created_at": "التاريخ"})
            df["النسبة"] = df["النسبة"].apply(lambda x: f"{x * 100:.0f}%")
            df["نشط"] = df["نشط"].apply(lambda x: "✅" if x else "❌")
            st.dataframe(df[["الاسم", "النسبة", "نشط", "التاريخ"]], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد تغييرات سابقة")

    # ---------- تبويب الحاسبة ----------
    with tab2:
        h3("حساب الضريبة على مبلغ", CY)
        amount = st.number_input("المبلغ (قبل الضريبة)", min_value=0.0, step=100.0)
        if st.button("🧮 احسب الضريبة"):
            vat_amount = calculate_vat(amount)
            total = amount + vat_amount
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(kpi_card("💰", "المبلغ الأساسي", f"{amount:,.2f}", BL), unsafe_allow_html=True)
            with col2:
                st.markdown(kpi_card("🧾", "قيمة الضريبة", f"{vat_amount:,.2f}", OR), unsafe_allow_html=True)
            with col3:
                st.markdown(kpi_card("💎", "الإجمالي", f"{total:,.2f}", GR), unsafe_allow_html=True)

    # ---------- تبويب التقارير ----------
    with tab3:
        h3("تقرير الضريبة", PR)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("من تاريخ", value=date.today().replace(day=1))
        with col2:
            end_date = st.date_input("إلى تاريخ", value=date.today())

        if st.button("📊 عرض التقرير"):
            report = get_vat_report(
                start_date.strftime("%Y-%m-%d") if start_date else None,
                end_date.strftime("%Y-%m-%d") if end_date else None
            )
            glass(f'نسبة الضريبة المعتمدة: <span style="color:{GR};font-weight:800;">{report["rate"] * 100:.0f}%</span>')
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(kpi_card("🛒", "إجمالي المبيعات", f"{report['total_sales']:,.2f}", BL), unsafe_allow_html=True)
            with col2:
                st.markdown(kpi_card("📤", "ضريبة المخرجات", f"{report['output_vat']:,.2f}", RD), unsafe_allow_html=True)
            with col3:
                st.markdown(kpi_card("📥", "ضريبة المدخلات", f"{report['input_vat']:,.2f}", OR), unsafe_allow_html=True)
            with col4:
                st.markdown(kpi_card("💎", "صافي الضريبة", f"{report['net_vat']:,.2f}", GR), unsafe_allow_html=True)
