# ui/expenses_ui.py – واجهة المصروفات التشغيلية (زجاجية فاخرة + حماية من التكرار)
import streamlit as st
import pandas as pd
from datetime import date
from services.expenses_service import (
    create_expenses_table,
    get_expense_categories,
    get_cash_accounts,
    get_suppliers_for_expense,
    create_expense,
    get_expenses
)

T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"

def show():
    create_expenses_table()
    
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">🧾 المصروفات التشغيلية</h1>
        <p style="color:{S}; font-size:1.2rem;">تسجيل المصروفات (إيجار، كهرباء، رواتب...) وربطها محاسبياً</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ تسجيل مصروف", "📋 سجل المصروفات"])

    # ---------- تبويب تسجيل المصروف ----------
    with tab1:
        st.markdown(f"<h3 style='color:{GR};'>تسجيل مصروف جديد</h3>", unsafe_allow_html=True)
        
        categories = get_expense_categories()
        cat_options = [c['code'] for c in categories]
        selected_cat = st.selectbox("نوع المصروف", cat_options)
        
        amount = st.number_input("المبلغ", min_value=0.01, step=0.01)
        expense_date = st.date_input("التاريخ", value=date.today())
        
        payment_method = st.radio("طريقة الدفع", ["نقدي (كاش)", "آجل (على المورد)"])
        
        if payment_method == "نقدي (كاش)":
            cash_accounts = get_cash_accounts()
            cash_options = [f"{a['code']} - {a['name']}" for a in cash_accounts]
            selected_cash = st.selectbox("حساب النقدية", cash_options)
            party_type = None
            party_id = None
        else:
            suppliers = get_suppliers_for_expense()
            if suppliers:
                supplier_options = {s['name']: s['id'] for s in suppliers}
                selected_supplier_name = st.selectbox("اختر المورد", list(supplier_options.keys()))
                party_type = 'supplier'
                party_id = supplier_options[selected_supplier_name]
            else:
                st.warning("لا يوجد موردين. أضف مورداً أولاً.")
                party_type = None
                party_id = None
        
        invoice_ref = st.text_input("رقم فاتورة المورد (اختياري)")
        notes = st.text_area("ملاحظات")
        
        # ✅ حماية من التكرار
        if "saving_expense" not in st.session_state:
            st.session_state.saving_expense = False
        
        if st.button("💾 حفظ المصروف", type="primary", disabled=st.session_state.saving_expense):
            st.session_state.saving_expense = True
            st.rerun()
        
        if st.session_state.saving_expense:
            if amount <= 0:
                st.error("المبلغ يجب أن يكون أكبر من صفر")
            else:
                if payment_method == "نقدي (كاش)":
                    account_code = selected_cash.split(" - ")[0]
                else:
                    account_code = ""
                
                eid, err = create_expense(
                    expense_date.strftime("%Y-%m-%d"),
                    selected_cat,
                    amount,
                    account_code,
                    'cash' if payment_method == "نقدي (كاش)" else 'credit',
                    party_type,
                    party_id,
                    invoice_ref,
                    notes,
                    st.session_state.user.get('username', 'admin')
                )
                if err:
                    st.error(f"فشل: {err}")
                else:
                    st.success(f"تم تسجيل المصروف رقم {eid}")
            st.session_state.saving_expense = False
            st.rerun()

    # ---------- سجل المصروفات ----------
    with tab2:
        st.markdown(f"<h3 style='color:{PR};\">سجل المصروفات</h3>", unsafe_allow_html=True)
        expenses = get_expenses()
        if expenses:
            df = pd.DataFrame(expenses)
            df['payment_method'] = df['payment_method'].apply(lambda x: 'نقدي' if x == 'cash' else 'آجل')
            df_display = df.rename(columns={
                'id': 'الرقم',
                'date': 'التاريخ',
                'category': 'النوع',
                'amount': 'المبلغ',
                'account_code': 'حساب النقدية',
                'payment_method': 'طريقة الدفع',
                'party_name': 'المورد',
                'invoice_ref': 'رقم الفاتورة',
                'notes': 'ملاحظات'
            })
            # ✅ تم إضافة 'ملاحظات' إلى قائمة الأعمدة
            st.dataframe(df_display[['الرقم', 'التاريخ', 'النوع', 'المبلغ', 'طريقة الدفع', 'حساب النقدية', 'المورد', 'رقم الفاتورة', 'ملاحظات']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد مصروفات مسجلة بعد")
