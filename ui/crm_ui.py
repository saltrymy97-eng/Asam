# ui/crm_ui.py – واجهة إدارة علاقات العملاء CRM (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from datetime import date, datetime
from services.crm_service import (
    create_crm_tables,
    add_lead,
    update_lead,
    get_all_leads,
    convert_lead_to_customer,
    add_opportunity,
    get_opportunities,
    get_pipeline_summary,
    add_interaction,
    get_interactions,
    get_crm_summary
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
        <p style="color:{S};font-size:1.2rem;">إدارة العملاء المحتملين والفرص البيعية والتفاعلات</p>
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
    create_crm_tables()
    h1("🤝 إدارة علاقات العملاء (CRM)")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 العملاء المحتملين", "💼 الفرص البيعية", "📞 التفاعلات",
        "📊 لوحة التحكم", "🔄 تحويل لعميل"
    ])

    # ---------- تبويب العملاء المحتملين ----------
    with tab1:
        h3("العملاء المحتملين (Leads)", BL)
        
        with st.expander("➕ إضافة عميل محتمل جديد"):
            with st.form("add_lead_form"):
                col1, col2 = st.columns(2)
                name = col1.text_input("الاسم")
                company = col2.text_input("الشركة")
                phone = col1.text_input("الهاتف")
                email = col2.text_input("البريد الإلكتروني")
                source = st.selectbox("المصدر", ["موقع إلكتروني", "إحالة", "معرض", "وسائل تواصل", "بارد", "أخرى"])
                status = st.selectbox("الحالة", ["جديد", "مؤهل", "قيد المتابعة", "غير مهتم", "تحول لعميل"])
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("💾 حفظ"):
                    if name:
                        add_lead(name, company, phone, email, source, status, notes)
                        st.success(f"تم إضافة {name}")
                        st.rerun()
                    else:
                        st.error("الاسم مطلوب")

        st.markdown("---")
        leads = get_all_leads()
        if leads:
            df = pd.DataFrame(leads)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد عملاء محتملون بعد")

    # ---------- تبويب الفرص البيعية ----------
    with tab2:
        h3("الفرص البيعية (Opportunities)", GR)
        
        with st.expander("➕ إضافة فرصة بيعية"):
            leads = get_all_leads()
            lead_options = {l['name']: l['id'] for l in leads}
            with st.form("add_opp_form"):
                lead_name = st.selectbox("العميل المحتمل", list(lead_options.keys()))
                title = st.text_input("عنوان الفرصة")
                amount = st.number_input("القيمة المتوقعة", min_value=0.0, step=100.0)
                stage = st.selectbox("المرحلة", ["مؤهل", "عرض سعر", "تفاوض", "مغلق ناجح", "مغلق خاسر"])
                probability = st.slider("نسبة الإغلاق (%)", 0, 100, 50)
                expected_date = st.date_input("تاريخ الإغلاق المتوقع")
                if st.form_submit_button("💾 حفظ"):
                    if title:
                        add_opportunity(lead_options[lead_name], title, amount, stage, probability, expected_date.strftime("%Y-%m-%d"))
                        st.success("تمت الإضافة")
                        st.rerun()

        st.markdown("---")
        opportunities = get_opportunities()
        if opportunities:
            df = pd.DataFrame(opportunities)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد فرص بيعية بعد")

    # ---------- تبويب التفاعلات ----------
    with tab3:
        h3("سجل التفاعلات", OR)
        
        with st.expander("➕ تسجيل تفاعل"):
            leads = get_all_leads()
            lead_options = {l['name']: l['id'] for l in leads}
            with st.form("add_interaction_form"):
                lead_name = st.selectbox("العميل", list(lead_options.keys()))
                itype = st.selectbox("نوع التفاعل", ["اتصال", "بريد إلكتروني", "اجتماع", "رسالة", "أخرى"])
                idate = st.date_input("التاريخ", value=date.today())
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("💾 حفظ"):
                    add_interaction(lead_options[lead_name], itype, idate.strftime("%Y-%m-%d"), notes)
                    st.success("تم التسجيل")
                    st.rerun()

        st.markdown("---")
        interactions = get_interactions()
        if interactions:
            df = pd.DataFrame(interactions)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد تفاعلات بعد")

    # ---------- تبويب لوحة التحكم ----------
    with tab4:
        h3("ملخص CRM", PR)
        summary = get_crm_summary()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(kpi_card("👥", "إجمالي العملاء المحتملين", summary['total_leads'], BL), unsafe_allow_html=True)
        with col2:
            st.markdown(kpi_card("🆕", "جديد", summary['new_leads'], GR), unsafe_allow_html=True)
        with col3:
            st.markdown(kpi_card("💼", "الفرص", summary['total_opportunities'], OR), unsafe_allow_html=True)
        with col4:
            st.markdown(kpi_card("💰", "قيمة الخط أنابيب", f"{summary['pipeline_value']:,.0f}", PR), unsafe_allow_html=True)

        st.markdown("---")
        h3("خط أنابيب المبيعات", CY)
        pipeline = get_pipeline_summary()
        if pipeline:
            df = pd.DataFrame(pipeline)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد فرص بعد")

    # ---------- تبويب تحويل لعميل ----------
    with tab5:
        h3("تحويل عميل محتمل إلى عميل فعلي", CY)
        leads = get_all_leads()
        unconverted = [l for l in leads if l['status'] != 'تحول لعميل']
        if unconverted:
            lead_names = [f"{l['name']} ({l['company'] or 'لا شركة'})" for l in unconverted]
            selected = st.selectbox("اختر العميل للتحويل", lead_names)
            if st.button("🔄 تحويل إلى عميل فعلي"):
                idx = lead_names.index(selected)
                customer_id = convert_lead_to_customer(unconverted[idx]['id'])
                if customer_id:
                    st.success(f"تم التحويل بنجاح! رقم العميل: {customer_id}")
                    st.rerun()
                else:
                    st.error("فشل التحويل")
        else:
            st.info("جميع العملاء المحتملين تم تحويلهم بالفعل")
