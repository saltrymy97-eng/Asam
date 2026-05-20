# ui/period_ui.py – واجهة إغلاق الفترات المالية (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from services.period_service import (
    create_periods_table,
    close_period,
    reopen_period,
    get_closed_periods,
    get_available_months,
    get_available_years
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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">📅 إغلاق الفترات المالية</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إغلاق وإعادة فتح الشهور والسنوات المالية</p>
    </div>
    """, unsafe_allow_html=True)

    create_periods_table()

    tab1, tab2 = st.tabs(["🔒 إغلاق / فتح", "📋 الفترات المغلقة"])

    with tab1:
        username = st.session_state.user.get("username", "غير معروف") if st.session_state.user else "غير معروف"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"<h4 style='color:{ACCENT_GREEN};'>إغلاق شهر</h4>", unsafe_allow_html=True)
            months = get_available_months()
            if months:
                month_to_close = st.selectbox("اختر الشهر", months, key="close_month")
                if st.button("🔒 إغلاق الشهر", key="btn_close_month"):
                    close_period("month", month_to_close, username)
                    st.success(f"تم إغلاق شهر {month_to_close}")
                    st.rerun()
            else:
                st.info("لا توجد شهور متاحة (لا توجد قيود)")
        
        with col2:
            st.markdown(f"<h4 style='color:{ACCENT_BLUE};'>إغلاق سنة</h4>", unsafe_allow_html=True)
            years = get_available_years()
            if years:
                year_to_close = st.selectbox("اختر السنة", years, key="close_year")
                if st.button("🔒 إغلاق السنة", key="btn_close_year"):
                    close_period("year", year_to_close, username)
                    st.success(f"تم إغلاق سنة {year_to_close}")
                    st.rerun()
            else:
                st.info("لا توجد سنوات متاحة")

        st.markdown("---")
        st.markdown(f"<h4 style='color:{ACCENT_ORANGE};'>🔓 إعادة فتح فترة</h4>", unsafe_allow_html=True)
        periods = get_closed_periods()
        if periods:
            period_options = [f"{'شهر' if p['period_type']=='month' else 'سنة'}: {p['period_value']} (أغلقها {p['closed_by']} في {p['closed_at']})" for p in periods]
            selected_period = st.selectbox("اختر الفترة لإعادة فتحها", period_options)
            if st.button("🔓 إعادة فتح الفترة"):
                idx = period_options.index(selected_period)
                p = periods[idx]
                reopen_period(p["period_type"], p["period_value"])
                st.success(f"تم إعادة فتح {p['period_type']}: {p['period_value']}")
                st.rerun()
        else:
            st.info("لا توجد فترات مغلقة")

    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>الفترات المغلقة حالياً</h3>", unsafe_allow_html=True)
        periods = get_closed_periods()
        if periods:
            df = pd.DataFrame(periods)
            df = df.drop("id", axis=1) if "id" in df.columns else df
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد فترات مغلقة")
