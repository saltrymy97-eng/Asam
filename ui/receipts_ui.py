# ui/receipts_ui.py – واجهة سندات القبض والصرف (تصميم زجاجي فاخر - قوائم قابلة للبحث)
import streamlit as st
import pandas as pd
from datetime import date
from services.receipts_service import (
    create_vouchers_table,
    get_cash_accounts,
    get_customers_with_balances,
    get_suppliers_with_balances,
    get_invoices_for_party,
    create_voucher,
    get_vouchers,
    get_voucher_details
)

# ========== ألوان الزجاج ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"

def show():
    create_vouchers_table()
    
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">💵 سندات القبض والصرف</h1>
        <p style="color:{S}; font-size:1.2rem;">إدارة المقبوضات والمدفوعات النقدية</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🧾 سند قبض", "📤 سند صرف", "📋 سجل السندات"])

    # ---------- تبويب سند قبض ----------
    with tab1:
        st.markdown(f"<h3 style='color:{GR};'>إنشاء سند قبض (استلام نقدية)</h3>", unsafe_allow_html=True)
        
        cash_accounts = get_cash_accounts()
        cash_options = [f"{a['code']} - {a['name']}" for a in cash_accounts]
        
        customers = get_customers_with_balances()
        if not customers:
            st.warning("لا يوجد عملاء")
        else:
            # --- قائمة العملاء القابلة للبحث ---
            customer_options = {f"{c['name']} (الرصيد: {c['balance']:,.2f})": c for c in customers}
            cust_df = pd.DataFrame(list(customer_options.keys()), columns=["العميل"])
            edited_cust = st.data_editor(cust_df, hide_index=True, use_container_width=True, key="receipt_cust_editor")
            selected_cust_label = edited_cust.iloc[0]["العميل"] if not edited_cust.empty and len(edited_cust) > 0 else list(customer_options.keys())[0]
            selected_cust = customer_options[selected_cust_label]
            
            invoices = get_invoices_for_party('customer', selected_cust['id'])
            
            # --- قائمة الفواتير القابلة للبحث ---
            invoice_options = {"بدون فاتورة (دفعة عامة)": None}
            for inv in invoices:
                label = f"فاتورة #{inv['id']} - المتبقي: {inv['remaining']:,.2f}"
                invoice_options[label] = inv
            
            inv_df = pd.DataFrame(list(invoice_options.keys()), columns=["الفاتورة"])
            edited_inv = st.data_editor(inv_df, hide_index=True, use_container_width=True, key="receipt_inv_editor")
            selected_inv_label = edited_inv.iloc[0]["الفاتورة"] if not edited_inv.empty and len(edited_inv) > 0 else list(invoice_options.keys())[0]
            selected_inv = invoice_options[selected_inv_label]
            
            default_amount = selected_inv['remaining'] if selected_inv else 0.0
            amount = st.number_input("المبلغ", min_value=0.0, value=float(default_amount), step=0.01, key="receipt_amount")
            
            col1, col2 = st.columns(2)
            with col1:
                voucher_date = st.date_input("التاريخ", value=date.today(), key="receipt_date")
            with col2:
                cash_selected = st.selectbox("حساب النقدية", cash_options, key="receipt_cash")
                
            reference = st.text_input("المرجع (اختياري)", key="receipt_ref")
            notes = st.text_area("ملاحظات", key="receipt_notes")
            
            # ✅ حماية من التكرار
            if "saving_receipt" not in st.session_state:
                st.session_state.saving_receipt = False
            
            if st.button("💾 حفظ سند القبض", type="primary", key="save_receipt", disabled=st.session_state.saving_receipt):
                st.session_state.saving_receipt = True
                st.rerun()
            
            if st.session_state.saving_receipt:
                if amount <= 0:
                    st.error("المبلغ يجب أن يكون أكبر من صفر")
                else:
                    account_code = cash_selected.split(" - ")[0]
                    inv_id = selected_inv['id'] if selected_inv else None
                    vid, err = create_voucher(
                        'receipt', 'customer', selected_cust['id'], amount,
                        account_code, inv_id, reference, notes,
                        st.session_state.user.get('username', 'admin'),
                        voucher_date.strftime("%Y-%m-%d")
                    )
                    if err:
                        st.error(f"فشل: {err}")
                    else:
                        st.success(f"تم إنشاء سند القبض رقم {vid}")
                st.session_state.saving_receipt = False
                st.rerun()

    # ---------- تبويب سند صرف ----------
    with tab2:
        st.markdown(f"<h3 style='color:{RD};'>إنشاء سند صرف (دفع نقدية)</h3>", unsafe_allow_html=True)
        
        cash_accounts = get_cash_accounts()
        cash_options = [f"{a['code']} - {a['name']}" for a in cash_accounts]
        
        suppliers = get_suppliers_with_balances()
        if not suppliers:
            st.warning("لا يوجد موردين")
        else:
            # --- قائمة الموردين القابلة للبحث ---
            supplier_options = {f"{s['name']} (الرصيد: {s['balance']:,.2f})": s for s in suppliers}
            sup_df = pd.DataFrame(list(supplier_options.keys()), columns=["المورد"])
            edited_sup = st.data_editor(sup_df, hide_index=True, use_container_width=True, key="payment_sup_editor")
            selected_sup_label = edited_sup.iloc[0]["المورد"] if not edited_sup.empty and len(edited_sup) > 0 else list(supplier_options.keys())[0]
            selected_sup = supplier_options[selected_sup_label]
            
            invoices = get_invoices_for_party('supplier', selected_sup['id'])
            
            # --- قائمة الفواتير القابلة للبحث ---
            invoice_options = {"بدون فاتورة (دفعة عامة)": None}
            for inv in invoices:
                label = f"فاتورة #{inv['id']} - المتبقي: {inv['remaining']:,.2f}"
                invoice_options[label] = inv
            
            inv_df = pd.DataFrame(list(invoice_options.keys()), columns=["الفاتورة"])
            edited_inv = st.data_editor(inv_df, hide_index=True, use_container_width=True, key="payment_inv_editor")
            selected_inv_label = edited_inv.iloc[0]["الفاتورة"] if not edited_inv.empty and len(edited_inv) > 0 else list(invoice_options.keys())[0]
            selected_inv = invoice_options[selected_inv_label]
            
            default_amount = selected_inv['remaining'] if selected_inv else 0.0
            amount = st.number_input("المبلغ", min_value=0.0, value=float(default_amount), step=0.01, key="payment_amount")
            
            col1, col2 = st.columns(2)
            with col1:
                voucher_date = st.date_input("التاريخ", value=date.today(), key="payment_date")
            with col2:
                cash_selected = st.selectbox("حساب النقدية", cash_options, key="payment_cash")
                
            reference = st.text_input("المرجع (اختياري)", key="payment_ref")
            notes = st.text_area("ملاحظات", key="payment_notes")
            
            # ✅ حماية من التكرار
            if "saving_payment" not in st.session_state:
                st.session_state.saving_payment = False
            
            if st.button("💾 حفظ سند الصرف", type="primary", key="save_payment", disabled=st.session_state.saving_payment):
                st.session_state.saving_payment = True
                st.rerun()
            
            if st.session_state.saving_payment:
                if amount <= 0:
                    st.error("المبلغ يجب أن يكون أكبر من صفر")
                else:
                    account_code = cash_selected.split(" - ")[0]
                    inv_id = selected_inv['id'] if selected_inv else None
                    vid, err = create_voucher(
                        'payment', 'supplier', selected_sup['id'], amount,
                        account_code, inv_id, reference, notes,
                        st.session_state.user.get('username', 'admin'),
                        voucher_date.strftime("%Y-%m-%d")
                    )
                    if err:
                        st.error(f"فشل: {err}")
                    else:
                        st.success(f"تم إنشاء سند الصرف رقم {vid}")
                st.session_state.saving_payment = False
                st.rerun()

    # ---------- سجل السندات ----------
    with tab3:
        st.markdown(f"<h3 style='color:{PR};\">سجل السندات</h3>", unsafe_allow_html=True)
        vouchers = get_vouchers()
        if vouchers:
            df = pd.DataFrame(vouchers)
            df['type'] = df['type'].apply(lambda x: 'قبض' if x=='receipt' else 'صرف')
            df = df.rename(columns={
                'id': 'الرقم',
                'type': 'النوع',
                'date': 'التاريخ',
                'party_name': 'الطرف',
                'amount': 'المبلغ',
                'account': 'حساب النقدية',
                'reference': 'المرجع'
            })
            st.dataframe(df[['الرقم', 'النوع', 'التاريخ', 'الطرف', 'المبلغ', 'حساب النقدية', 'المرجع']],
                         use_container_width=True, hide_index=True)
            
            voucher_ids = [v['id'] for v in vouchers]
            selected_vid = st.selectbox("اختر سند لعرض التفاصيل", voucher_ids)
            if selected_vid:
                details = get_voucher_details(selected_vid)
                if details:
                    st.json(details)
        else:
            st.info("لا توجد سندات بعد")
