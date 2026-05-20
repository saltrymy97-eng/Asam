# ui/closing_ui.py – واجهة قيد إغلاق الحسابات (تصميم زجاجي فخم)
import streamlit as st
from datetime import date
from services.closing_service import create_closing_entry

# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 قيد إغلاق الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إنشاء قيد تلقائي لإغلاق الإيرادات والمصروفات وترحيل صافي الدخل</p>
    </div>
    """, unsafe_allow_html=True)

    year = st.number_input("السنة المالية", min_value=2000, max_value=2100, value=date.today().year)

    if st.button("🚀 إنشاء قيد الإغلاق", type="primary"):
        success, net_income, error = create_closing_entry(year)
        if error:
            st.warning(error)
        elif success:
            st.success(f"تم إنشاء قيد إغلاق السنة {year} بنجاح! صافي الدخل: {net_income:,.2f}")
            st.rerun()
        else:
            st.error("فشل في إنشاء قيد الإغلاق")
