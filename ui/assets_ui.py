# ui/assets_ui.py – واجهة الأصول الثابتة والإهلاكات (تصميم زجاجي فخم + حماية من التكرار)
import streamlit as st
import pandas as pd
from datetime import date, datetime
from services.assets_service import (
    create_assets_tables,
    add_asset,
    get_all_assets,
    run_depreciation,
    run_all_depreciations,
    get_depreciation_history,
    get_assets_summary
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
        <p style="color:{S};font-size:1.2rem;">إدارة الأصول الثابتة وجدولة الإهلاكات</p>
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
    create_assets_tables()
    h1("🏢 الأصول الثابتة والإهلاكات")

    tab1, tab2, tab3, tab4 = st.tabs(["📋 الأصول", "➕ إضافة أصل", "📉 تشغيل الإهلاك", "📊 لوحة التحكم"])

    # ---------- تبويب الأصول ----------
    with tab1:
        h3("قائمة الأصول الثابتة", BL)
        assets = get_all_assets()
        if assets:
            df = pd.DataFrame(assets)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أصول ثابتة بعد")

        st.markdown("---")
        h3("سجل الإهلاكات", PR)
        history = get_depreciation_history()
        if history:
            df = pd.DataFrame(history)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد إهلاكات مسجلة بعد")

    # ---------- تبويب إضافة أصل ----------
    with tab2:
        h3("إضافة أصل ثابت جديد", GR)
        with st.form("add_asset_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم الأصل")
            category = col2.selectbox("الفئة", ["أثاث ومعدات", "مباني", "آلات", "مركبات", "أجهزة كمبيوتر", "أخرى"])
            col1, col2 = st.columns(2)
            purchase_date = col1.date_input("تاريخ الشراء", value=date.today())
            purchase_cost = col2.number_input("تكلفة الشراء", min_value=0.0, step=100.0)
            col1, col2 = st.columns(2)
            salvage_value = col1.number_input("قيمة الخردة (الإنقاذ)", min_value=0.0, step=100.0, value=0.0)
            useful_life = col2.number_input("العمر الإنتاجي (سنوات)", min_value=1, value=5)
            method = st.selectbox("طريقة الإهلاك", ["قسط ثابت", "متناقص"])
            notes = st.text_area("ملاحظات")
            if st.form_submit_button("💾 حفظ الأصل"):
                if name and purchase_cost > 0:
                    add_asset(name, category, purchase_date.strftime("%Y-%m-%d"), purchase_cost, salvage_value, useful_life, method, notes)
                    st.success(f"تم إضافة الأصل '{name}'")
                    st.rerun()
                else:
                    st.error("الاسم وتكلفة الشراء مطلوبان")

    # ---------- تبويب تشغيل الإهلاك ----------
    with tab3:
        h3("تشغيل الإهلاك الشهري", OR)
        assets = get_all_assets()
        active_assets = [a for a in assets if a['status'] == 'نشط' and a['monthly_depreciation'] > 0]

        # ✅ حماية من التكرار - تشغيل الكل
        if "saving_all_dep" not in st.session_state:
            st.session_state.saving_all_dep = False
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 تشغيل إهلاك جميع الأصول النشطة", type="primary", disabled=st.session_state.saving_all_dep):
                st.session_state.saving_all_dep = True
                st.rerun()
            
            if st.session_state.saving_all_dep:
                results = run_all_depreciations()
                success_count = sum(1 for r in results if r[1])
                st.success(f"تم تشغيل الإهلاك لـ {success_count} أصل")
                st.session_state.saving_all_dep = False
                st.rerun()

        # ✅ حماية من التكرار - تشغيل فردي
        if "saving_single_dep" not in st.session_state:
            st.session_state.saving_single_dep = False
        
        with col2:
            if active_assets:
                asset_names = [f"{a['name']} (إهلاك شهري: {a['monthly_depreciation']:,.2f})" for a in active_assets]
                selected = st.selectbox("اختر أصلاً للتشغيل الفردي", asset_names)
                if st.button("📉 تشغيل إهلاك هذا الأصل", disabled=st.session_state.saving_single_dep):
                    st.session_state.saving_single_dep = True
                    st.rerun()
                
                if st.session_state.saving_single_dep:
                    idx = asset_names.index(selected)
                    success, msg = run_depreciation(active_assets[idx]['id'])
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.session_state.saving_single_dep = False
                    st.rerun()

    # ---------- تبويب لوحة التحكم ----------
    with tab4:
        h3("ملخص الأصول الثابتة", CY)
        summary = get_assets_summary()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(kpi_card("🏢", "إجمالي الأصول", summary['total_count'], BL), unsafe_allow_html=True)
        with col2:
            st.markdown(kpi_card("💰", "تكلفة الشراء", f"{summary['total_cost']:,.0f}", GR), unsafe_allow_html=True)
        with col3:
            st.markdown(kpi_card("📉", "الإهلاك المتراكم", f"{summary['total_depreciation']:,.0f}", OR), unsafe_allow_html=True)
        with col4:
            st.markdown(kpi_card("📊", "القيمة الدفترية", f"{summary['total_book_value']:,.0f}", PR), unsafe_allow_html=True)

        st.markdown("---")
        h3("الأصول النشطة", GR)
        assets = get_all_assets()
        active = [a for a in assets if a['status'] == 'نشط']
        if active:
            df = pd.DataFrame(active)
            st.dataframe(df[['name', 'category', 'purchase_cost', 'monthly_depreciation', 'accumulated_depreciation', 'book_value']], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أصول نشطة")
