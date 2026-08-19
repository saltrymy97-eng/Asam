# ui/currency_revaluation_ui.py – واجهة فروق أسعار الصرف (زجاجية فاخرة + حماية من التكرار)
import streamlit as st
import pandas as pd
from datetime import date
from services.currency_revaluation_service import (
    get_accounts_with_foreign_currency,
    get_foreign_balance,
    perform_revaluation,
    get_revaluation_history
)
from services.currency_service import get_base_currency

T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">💱 فروق أسعار الصرف</h1>
        <p style="color:{S}; font-size:1.2rem;">إعادة تقييم الأرصدة بالعملات الأجنبية ومعالجة الفروق</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔄 إعادة تقييم", "📋 سجل العمليات"])

    with tab1:
        st.markdown(f"<h3 style='color:{BL};'>إعادة تقييم الأرصدة بالعملات الأجنبية</h3>", unsafe_allow_html=True)
        
        accounts = get_accounts_with_foreign_currency()
        if not accounts:
            st.info("لا توجد حسابات لديها معاملات بعملات أجنبية")
        else:
            # ✅ التعديل الاحترافي: عرض الكود والاسم معاً
            account_options = {f"{a['account_code']} - {a['account_name']}": a for a in accounts}
            selected_display = st.selectbox("اختر الحساب", list(account_options.keys()))
            
            account_data = account_options[selected_display]
            account_id = account_data['account_id']
            account_name = account_data['account_name']
            currency = account_data['currency_code']
            
            foreign_bal, current_local = get_foreign_balance(account_id, currency)
            
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:15px; margin:10px 0;">
                <p><b>العملة:</b> {currency} | <b>الرصيد بالعملة الأجنبية:</b> {foreign_bal:,.2f}</p>
                <p><b>القيمة المحلية الحالية (بأسعار الصرف التاريخية):</b> {current_local:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if abs(foreign_bal) < 0.001:
                st.warning("الرصيد صفر، لا حاجة لإعادة التقييم")
            else:
                new_rate = st.number_input("سعر الصرف الجديد", min_value=0.01, value=1.0, step=0.01)
                
                if new_rate > 0:
                    new_local = foreign_bal * new_rate
                    diff = new_local - current_local
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("القيمة الجديدة", f"{new_local:,.2f}")
                    with col2:
                        st.metric("الفرق", f"{diff:,.2f}", delta=f"{diff:,.2f}" if diff != 0 else "0")
                    
                    if abs(diff) < 0.01:
                        st.info("لا يوجد فرق جوهري")
                    else:
                        st.markdown(f"**الحالة:** {'ربح فروق عملة' if diff > 0 else 'خسارة فروق عملة'}")
                        
                        rev_date = st.date_input("تاريخ إعادة التقييم", value=date.today())
                        
                        # ✅ حماية من التكرار
                        if "saving_revaluation" not in st.session_state:
                            st.session_state.saving_revaluation = False
                        
                        if st.button("💾 تنفيذ إعادة التقييم", type="primary", disabled=st.session_state.saving_revaluation):
                            st.session_state.saving_revaluation = True
                            st.rerun()
                        
                        if st.session_state.saving_revaluation:
                            entry_id, err = perform_revaluation(
                                account_id, currency, new_rate,
                                rev_date.strftime("%Y-%m-%d"),
                                st.session_state.user.get('username', 'admin')
                            )
                            if err:
                                st.error(f"فشل: {err}")
                            else:
                                st.success(f"تم إنشاء قيد إعادة التقييم رقم {entry_id}")
                            st.session_state.saving_revaluation = False
                            st.rerun()

    with tab2:
        st.markdown(f"<h3 style='color:{PR};'>سجل عمليات إعادة التقييم</h3>", unsafe_allow_html=True)
        history = get_revaluation_history()
        if history:
            df = pd.DataFrame(history)
            df_display = df.rename(columns={
                'id': 'الرقم',
                'date': 'التاريخ',
                'account_name': 'الحساب',
                'currency_code': 'العملة',
                'new_rate': 'السعر الجديد',
                'foreign_balance': 'الرصيد الأجنبي',
                'old_local_value': 'قيمة قديمة',
                'new_local_value': 'قيمة جديدة',
                'difference': 'الفرق',
                'journal_entry_id': 'رقم القيد'
            })
            st.dataframe(df_display[['الرقم', 'التاريخ', 'الحساب', 'العملة', 'السعر الجديد', 'الرصيد الأجنبي', 'الفرق', 'رقم القيد']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد عمليات سابقة")
