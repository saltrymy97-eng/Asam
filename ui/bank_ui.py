# ui/bank_ui.py – واجهة التعاملات البنكية (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from datetime import date
from services import bank_service as bank
from services.currency_service import get_all_currencies, get_base_currency

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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_BLUE};">🏦 التعاملات البنكية</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الحسابات البنكية والحركات والمصالحات</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🏛️ الحسابات", "💳 الحركات", "⚖️ مصالحة", "📊 ملخص"])

    # ---------- تبويب 1: الحسابات البنكية ----------
    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; box-shadow:{GLASS_SHADOW};">
                <h3 style="color:{TEXT_PRIMARY};">➕ إضافة حساب بنكي</h3>
            """, unsafe_allow_html=True)
            with st.form("add_bank_form"):
                bank_name = st.text_input("اسم البنك", placeholder="مثال: بنك الكريمي")
                account_number = st.text_input("رقم الحساب")
                account_name = st.text_input("اسم الحساب (اختياري)")
                currencies = get_all_currencies()
                base = get_base_currency()
                currency_list = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
                def_label = next((k for k, v in currency_list.items() if v == (base['code'] if base else 'YER')), list(currency_list.keys())[0])
                currency_choice = st.selectbox("العملة", list(currency_list.keys()), index=list(currency_list.keys()).index(def_label))
                opening_balance = st.number_input("الرصيد الافتتاحي", min_value=0.0, step=100.0, value=0.0)
                if st.form_submit_button("✅ إضافة"):
                    if not bank_name or not account_number:
                        st.error("اسم البنك ورقم الحساب مطلوبان")
                    else:
                        try:
                            bank.create_bank_account(bank_name, account_number, account_name, currency_list[currency_choice], opening_balance)
                            st.success("تمت إضافة الحساب البنكي")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; box-shadow:{GLASS_SHADOW};">
                <h3 style="color:{TEXT_PRIMARY};">📋 الحسابات البنكية</h3>
            """, unsafe_allow_html=True)
            accounts = bank.get_all_bank_accounts(active_only=False)
            if accounts:
                for acc in accounts:
                    active_badge = "🟢" if acc['is_active'] else "🔴"
                    st.markdown(f"""
                    <div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.1);">
                        <strong style="color:{TEXT_PRIMARY};">{acc['bank_name']}</strong> - {acc['account_number']}
                        <br><small style="color:{TEXT_SECONDARY};">{acc.get('account_name','')} | {acc['currency_code']} | الرصيد: {acc['current_balance']:,.2f} {active_badge}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("لا توجد حسابات بنكية")
            st.markdown("</div>", unsafe_allow_html=True)

    # ---------- تبويب 2: الحركات البنكية ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};\">تسجيل حركة بنكية</h3>", unsafe_allow_html=True)
        accounts = bank.get_all_bank_accounts()
        if not accounts:
            st.warning("أضف حساباً بنكياً أولاً")
        else:
            acc_options = {f"{a['bank_name']} - {a['account_number']}": a['id'] for a in accounts}
            selected_acc_label = st.selectbox("اختر الحساب", list(acc_options.keys()))
            acc_id = acc_options[selected_acc_label]

            with st.form("transaction_form"):
                col1, col2 = st.columns(2)
                with col1:
                    trans_date = st.date_input("التاريخ", value=date.today())
                    trans_type = st.selectbox("نوع الحركة", ["deposit", "withdrawal", "transfer_in", "transfer_out"],
                                              format_func=lambda x: {"deposit": "إيداع", "withdrawal": "سحب", "transfer_in": "تحويل وارد", "transfer_out": "تحويل صادر"}[x])
                with col2:
                    amount = st.number_input("المبلغ", min_value=0.01, step=0.01)
                    reference = st.text_input("المرجع (اختياري)")
                description = st.text_input("البيان")
                if st.form_submit_button("💾 حفظ الحركة"):
                    if not description:
                        st.error("البيان مطلوب")
                    else:
                        try:
                            bank.add_bank_transaction(acc_id, trans_date.strftime("%Y-%m-%d"), description, trans_type, amount, reference)
                            st.success("تم تسجيل الحركة")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

        st.markdown("---")
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};\">📋 الحركات البنكية</h3>", unsafe_allow_html=True)
        selected_filter = st.selectbox("تصفية حسب الحساب", ["الكل"] + [f"{a['bank_name']} - {a['account_number']}" for a in accounts])
        if selected_filter == "الكل":
            transactions = bank.get_bank_transactions()
        else:
            sel_id = next(a['id'] for a in accounts if f"{a['bank_name']} - {a['account_number']}" == selected_filter)
            transactions = bank.get_bank_transactions(bank_account_id=sel_id)
        if transactions:
            df = pd.DataFrame(transactions)
            df['type'] = df['type'].map({"deposit": "إيداع", "withdrawal": "سحب", "transfer_in": "تحويل وارد", "transfer_out": "تحويل صادر"})
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حركات")

    # ---------- تبويب 3: المصالحة البنكية ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};\">⚖️ المصالحة البنكية</h3>", unsafe_allow_html=True)
        accounts = bank.get_all_bank_accounts()
        if accounts:
            acc_options2 = {f"{a['bank_name']} - {a['account_number']}": a['id'] for a in accounts}
            sel_acc2_label = st.selectbox("اختر الحساب", list(acc_options2.keys()), key="reconcile_acc")
            acc_id2 = acc_options2[sel_acc2_label]
            acc_info = next(a for a in accounts if a['id'] == acc_id2)
            st.write(f"رصيد الدفاتر الحالي: **{acc_info['current_balance']:,.2f} {acc_info['currency_code']}**")

            with st.form("reconciliation_form"):
                stmt_date = st.date_input("تاريخ كشف البنك", value=date.today())
                stmt_balance = st.number_input("رصيد كشف البنك", min_value=0.0, step=0.01)
                if st.form_submit_button("🔍 تنفيذ المصالحة"):
                    try:
                        success, diff = bank.create_bank_reconciliation(acc_id2, stmt_date.strftime("%Y-%m-%d"), stmt_balance)
                        if success:
                            st.success(f"تمت المصالحة. الفرق: {diff:,.2f}")
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))

            # عرض الحركات غير المسواة
            unreconciled = bank.get_unreconciled_transactions(acc_id2)
            if unreconciled:
                st.markdown("**حركات غير مسواة:**")
                st.dataframe(pd.DataFrame(unreconciled), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حسابات")

    # ---------- تبويب 4: ملخص الأرصدة ----------
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_PURPLE};\">📊 ملخص الأرصدة البنكية</h3>", unsafe_allow_html=True)
        summary, total_base = bank.get_bank_balance_summary()
        if summary:
            df = pd.DataFrame(summary)
            st.dataframe(df, use_container_width=True, hide_index=True)
            base_cur = get_base_currency()
            base_code = base_cur['code'] if base_cur else 'YER'
            st.markdown(f"### إجمالي الأرصدة بالعملة الأساسية ({base_code}): {total_base:,.2f}")
            
            st.markdown("---")
            st.markdown(f"<h3 style='color:{TEXT_PRIMARY};\">📋 سجل المصالحات</h3>", unsafe_allow_html=True)
            reconciliations = bank.get_reconciliation_history()
            if reconciliations:
                st.dataframe(pd.DataFrame(reconciliations), use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد مصالحات سابقة")
        else:
            st.info("لا توجد حسابات بنكية نشطة")
