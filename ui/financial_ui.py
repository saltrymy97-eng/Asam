# ui/financial_ui.py - واجهة القوائم المالية (تصميم زجاجي فخم + فلترة مراكز التكلفة)
import streamlit as st
import pandas as pd
from services.financial_service import get_income_statement, get_balance_sheet
from services import cost_center_service as ccs

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
ACCENT_CYAN = "#06B6D4"

def glass_card(title, icon, value, color, subtitle=""):
    return f"""
    <div style="
        background:{GLASS_BG}; backdrop-filter:blur(10px);
        border:1px solid {GLASS_BORDER}; border-radius:20px;
        padding:1.5rem; text-align:center; box-shadow:{GLASS_SHADOW};
        margin-bottom:1rem;
    ">
        <div style="font-size:2.5rem; margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">{title}</div>
        <div style="color:{color}; font-size:1.8rem; font-weight:800;">{value}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.8rem;">{subtitle}</div>
    </div>
    """

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">📊 القوائم المالية</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">قائمة الدخل والميزانية العمومية</p>
    </div>
    """, unsafe_allow_html=True)

    # 🆕 فلتر مراكز التكلفة
    centers = ccs.get_all_cost_centers(active_only=True)
    center_options = {0: "كل الشركة (بدون تصفية)"}
    if centers:
        for c in centers:
            center_options[c['id']] = f"{c['code']} - {c['name']}"
    
    selected_center = st.selectbox(
        "🏢 تصفية حسب مركز التكلفة",
        options=list(center_options.keys()),
        format_func=lambda x: center_options[x]
    )
    cost_center_id = selected_center if selected_center != 0 else None

    tab1, tab2 = st.tabs(["📈 قائمة الدخل", "⚖️ الميزانية العمومية"])

    # ========== قائمة الدخل ==========
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>قائمة الدخل</h3>", unsafe_allow_html=True)
        
        income = get_income_statement(cost_center_id)
        
        # تشخيص
        st.write("تشخيص الدخل:", income)
        
        # رسالة توضيحية إذا تم التصفية
        if cost_center_id:
            center_name = next((f"{c['code']} - {c['name']}" for c in centers if c['id'] == cost_center_id), "")
            st.info(f"يتم عرض بيانات مركز التكلفة: {center_name}")

        if income['total_revenue'] == 0 and income['total_expenses'] == 0:
            st.warning("لا توجد بيانات مالية للفترة/المركز المحدد. سجل قيوداً مع توزيعات مراكز تكلفة.")
            return
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(glass_card("الإيرادات", "📈", f"{income['total_revenue']:,.2f}", ACCENT_GREEN), unsafe_allow_html=True)
        with col2:
            st.markdown(glass_card("المصروفات", "📉", f"{income['total_expenses']:,.2f}", ACCENT_RED), unsafe_allow_html=True)
        with col3:
            net = income['net_income']
            st.markdown(glass_card("صافي الدخل", "💎", f"{net:,.2f}", ACCENT_GREEN if net >= 0 else ACCENT_RED, "ربح ✅" if net >= 0 else "خسارة ⚠️"), unsafe_allow_html=True)

        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<h4 style='color:{ACCENT_GREEN};'>الإيرادات</h4>", unsafe_allow_html=True)
            if income['revenue']:
                df_r = pd.DataFrame(income['revenue']).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})
                st.dataframe(df_r, use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد إيرادات مسجلة")
        
        with col2:
            st.markdown(f"<h4 style='color:{ACCENT_RED};'>المصروفات</h4>", unsafe_allow_html=True)
            if income['expenses']:
                df_e = pd.DataFrame(income['expenses']).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})
                st.dataframe(df_e, use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد مصروفات مسجلة")

    # ========== الميزانية العمومية ==========
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>الميزانية العمومية</h3>", unsafe_allow_html=True)
        
        balance = get_balance_sheet(cost_center_id)
        
        if cost_center_id and balance['total_assets'] == 0 and balance['total_liabilities'] == 0:
            st.warning("لا توجد بيانات ميزانية لهذا المركز. المراكز التكلفة تعرض عادة الإيرادات والمصروفات فقط.")
            return

        if balance['total_assets'] == 0 and balance['total_liabilities'] == 0 and not cost_center_id:
            st.warning("لا توجد بيانات للميزانية العمومية. سجل قيوداً على الحسابات (1،2،3).")
            return
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(glass_card("الأصول", "🏢", f"{balance['total_assets']:,.2f}", ACCENT_BLUE), unsafe_allow_html=True)
        with col2:
            st.markdown(glass_card("الخصوم", "📋", f"{balance['total_liabilities']:,.2f}", ACCENT_ORANGE), unsafe_allow_html=True)
        with col3:
            st.markdown(glass_card("حقوق الملكية", "👑", f"{balance['total_equity']:,.2f}", ACCENT_PURPLE), unsafe_allow_html=True)

        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<h4 style='color:{ACCENT_BLUE};'>الأصول</h4>", unsafe_allow_html=True)
            if balance['assets']:
                df_a = pd.DataFrame(balance['assets']).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})
                st.dataframe(df_a, use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد أصول مسجلة")
        
        with col2:
            st.markdown(f"<h4 style='color:{ACCENT_ORANGE};'>الخصوم وحقوق الملكية</h4>", unsafe_allow_html=True)
            combined = balance['liabilities'] + balance['equity']
            if combined:
                df_c = pd.DataFrame(combined).rename(columns={"code": "الكود", "name": "الحساب", "amount": "المبلغ"})
                st.dataframe(df_c, use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد خصوم أو حقوق ملكية مسجلة")

        st.markdown("---")
        col3, col4 = st.columns(2)
        with col3:
            st.metric("إجمالي الأصول", f"{balance['total_assets']:,.2f}")
        with col4:
            st.metric("إجمالي الخصوم + حقوق الملكية", f"{balance['total_liab_equity']:,.2f}")
        
        if abs(balance['total_assets'] - balance['total_liab_equity']) < 0.01:
            st.success("الميزانية متوازنة ✅")
        else:
            st.error("الميزانية غير متوازنة ⚠️")
