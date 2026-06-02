# ui/currency_ui.py – واجهة العملات وأسعار الصرف (تصميم زجاجي)
import streamlit as st
import pandas as pd
from datetime import date
from services import currency_service as cur

# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_PURPLE = "#8B5CF6"

def show():
    # تهيئة العملات الافتراضية في أول تشغيل
    cur.create_default_currencies()
    
    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_ORANGE};">💱 العملات وأسعار الصرف</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة العملات وتحويل الأموال بأسعار الصرف اليومية</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["💵 العملات", "📈 أسعار الصرف", "🔄 تحويل العملات"])

    # ---------- تبويب 1: العملات ----------
    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; box-shadow:{GLASS_SHADOW};">
                <h3 style="color:{TEXT_PRIMARY};">➕ إضافة عملة جديدة</h3>
            """, unsafe_allow_html=True)
            with st.form("add_currency_form"):
                code = st.text_input("رمز العملة", placeholder="مثال: USD, SAR, EUR")
                name = st.text_input("اسم العملة", placeholder="دولار أمريكي")
                symbol = st.text_input("الرمز (اختياري)", placeholder="$")
                is_base = st.checkbox("عملة أساسية (للتقارير المالية)")
                if st.form_submit_button("✅ إضافة"):
                    if not code or not name:
                        st.error("الرمز والاسم مطلوبان")
                    else:
                        try:
                            cur.create_currency(code, name, symbol, is_base)
                            st.success(f"تمت إضافة {code}")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; box-shadow:{GLASS_SHADOW};">
                <h3 style="color:{TEXT_PRIMARY};">📋 العملات المتاحة</h3>
            """, unsafe_allow_html=True)
            currencies = cur.get_all_currencies(active_only=False)
            if currencies:
                for c in currencies:
                    base_badge = "⭐ أساسية" if c['is_base'] else ""
                    active_badge = "🟢" if c['is_active'] else "🔴"
                    st.markdown(f"""
                    <div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.1);">
                        <strong style="color:{TEXT_PRIMARY};">{c['code']} - {c['name']}</strong> {c.get('symbol','')}
                        <span style="color:{TEXT_SECONDARY};">{base_badge} {active_badge}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("لا توجد عملات مضافة")
            st.markdown("</div>", unsafe_allow_html=True)

    # ---------- تبويب 2: أسعار الصرف ----------
    with tab2:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; box-shadow:{GLASS_SHADOW};">
            <h3 style="color:{TEXT_PRIMARY};">📈 تسجيل سعر صرف جديد</h3>
        """, unsafe_allow_html=True)
        
        currencies_list = cur.get_all_currencies()
        if len(currencies_list) < 2:
            st.warning("تحتاج عملتين على الأقل لإدارة أسعار الصرف")
        else:
            currency_codes = [c['code'] for c in currencies_list]
            with st.form("exchange_rate_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    from_cur = st.selectbox("من عملة", currency_codes)
                with col2:
                    to_cur = st.selectbox("إلى عملة", currency_codes, index=min(1, len(currency_codes)-1))
                with col3:
                    rate = st.number_input("سعر الصرف", min_value=0.0001, value=1.0, step=0.01, format="%.4f")
                rate_date = st.date_input("التاريخ", value=date.today())
                if st.form_submit_button("💾 حفظ"):
                    if from_cur == to_cur:
                        st.error("يجب اختيار عملتين مختلفتين")
                    else:
                        cur.set_exchange_rate(from_cur, to_cur, rate, rate_date.strftime("%Y-%m-%d"))
                        st.success(f"تم حفظ سعر {from_cur} → {to_cur}: {rate}")
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # عرض آخر الأسعار
        st.markdown("---")
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 آخر أسعار الصرف</h3>", unsafe_allow_html=True)
        if len(currencies_list) >= 2:
            from_c = st.selectbox("من", currency_codes, key="hist_from")
            to_c = st.selectbox("إلى", currency_codes, key="hist_to", index=min(1, len(currency_codes)-1))
            history = cur.get_exchange_rate_history(from_c, to_c)
            if history:
                df = pd.DataFrame(history)
                df = df.rename(columns={"date": "التاريخ", "rate": "السعر"})
                st.dataframe(df[["التاريخ", "السعر"]], use_container_width=True, hide_index=True)
            else:
                st.info("لا يوجد سجل أسعار")

    # ---------- تبويب 3: تحويل العملات ----------
    with tab3:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; box-shadow:{GLASS_SHADOW};">
            <h3 style="color:{TEXT_PRIMARY};">🔄 حاسبة تحويل العملات</h3>
        """, unsafe_allow_html=True)
        
        if len(currencies_list) >= 2:
            col1, col2, col3 = st.columns(3)
            with col1:
                amount = st.number_input("المبلغ", min_value=0.01, value=1.0, step=0.01)
            with col2:
                from_c2 = st.selectbox("من", currency_codes, key="conv_from")
            with col3:
                to_c2 = st.selectbox("إلى", currency_codes, key="conv_to", index=min(1, len(currency_codes)-1))
            
            if st.button("🔄 تحويل", use_container_width=True):
                try:
                    result = cur.convert_amount(amount, from_c2, to_c2)
                    st.success(f"✅ {amount:,.2f} {from_c2} = {result:,.2f} {to_c2}")
                except ValueError as e:
                    st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)
