# ui/cash_ui.py – واجهة الصندوق متعدد العملات (زجاجية فخمة بلمسات ذهبية)
import streamlit as st
import pandas as pd
from datetime import date
from services.cash_service import (
    create_cash_tables,
    create_cash_account,
    get_all_cash_accounts,
    add_cash_transaction,
    get_cash_transactions,
    get_cash_statement,
    get_cash_balance_summary
)
from services.currency_service import get_all_currencies

# ========== ألوان التصميم الزجاجي الفاخر ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(212, 175, 55, 0.3)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_CYAN = "#06B6D4"

def glass_card(title, icon, value, color, subtitle=""):
    return f"""
    <div style="
        background: linear-gradient(145deg, rgba(20, 30, 50, 0.8), rgba(10, 15, 30, 0.9));
        backdrop-filter:blur(10px);
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
    # ===== تصميم ذهبي فاخر =====
    st.markdown("""
    <style>
    div[data-testid="stTabs"] button {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        border-radius: 15px !important;
        transition: all 0.3s ease !important;
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        color: #CBD5E1 !important;
    }
    div[data-testid="stTabs"] button:hover {
        background: linear-gradient(135deg, rgba(212,175,55,0.2), rgba(212,175,55,0.05)) !important;
        border-color: #d4af37 !important;
        color: #FCF6BA !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: linear-gradient(135deg, rgba(212,175,55,0.3), rgba(212,175,55,0.1)) !important;
        border-color: #d4af37 !important;
        color: #FCF6BA !important;
        box-shadow: 0 0 15px rgba(212,175,55,0.2) !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, rgba(212,175,55,0.2), rgba(212,175,55,0.05)) !important;
        border: 1px solid rgba(212,175,55,0.4) !important;
        color: #FCF6BA !important;
        font-weight: 700 !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #D4AF37, #AA771C) !important;
        color: #000 !important;
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(212,175,55,0.4) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{GOLD}; font-size:2.8rem; margin:0; text-shadow:0 0 20px rgba(212,175,55,0.3);">💰 إدارة الصندوق</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">حسابات النقدية متعددة العملات</p>
    </div>
    """, unsafe_allow_html=True)

    create_cash_tables()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 الأرصدة", "➕ إضافة صندوق", "💵 حركات", "📋 كشف حساب"])

    # ========== تبويب 1: الأرصدة ==========
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>أرصدة الصناديق</h3>", unsafe_allow_html=True)
        summary, total_base = get_cash_balance_summary()
        if summary:
            cols = st.columns(len(summary))
            for col, acc in zip(cols, summary):
                with col:
                    st.markdown(glass_card(acc['name'], "💵", f"{acc['balance']:,.2f} {acc['currency']}", ACCENT_GREEN if acc['balance'] >= 0 else ACCENT_RED), unsafe_allow_html=True)
            st.markdown(f"<h4 style='color:{GOLD}; text-align:center;'>إجمالي الأرصدة (بالعملة الأساسية): {total_base:,.2f}</h4>", unsafe_allow_html=True)
        else:
            st.info("لا توجد حسابات صندوق. أضف حساباً جديداً من التبويب الثاني.")

    # ========== تبويب 2: إضافة صندوق ==========
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة حساب صندوق جديد</h3>", unsafe_allow_html=True)
        currencies = get_all_currencies()
        currency_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
        
        with st.form("add_cash_form", clear_on_submit=True):
            name = st.text_input("اسم الصندوق", placeholder="مثال: صندوق الدولار")
            col1, col2 = st.columns(2)
            currency_label = col1.selectbox("العملة", list(currency_options.keys()))
            opening_balance = col2.number_input("الرصيد الافتتاحي", min_value=0.0, step=100.0)
            
            submitted = st.form_submit_button("💾 حفظ الصندوق")
            if submitted:
                if not name:
                    st.error("اسم الصندوق مطلوب")
                else:
                    currency_code = currency_options[currency_label]
                    success, msg = create_cash_account(name, currency_code, opening_balance)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # ========== تبويب 3: حركات ==========
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>حركات الصندوق</h3>", unsafe_allow_html=True)
        accounts = get_all_cash_accounts()
        if not accounts:
            st.warning("لا توجد حسابات صندوق.")
        else:
            # نموذج إضافة حركة
            with st.form("add_transaction_form", clear_on_submit=True):
                acc_options = {f"{a['name']} ({a['currency_code']})": a['id'] for a in accounts}
                selected_acc = st.selectbox("اختر الصندوق", list(acc_options.keys()))
                col1, col2 = st.columns(2)
                trans_type = col1.selectbox("نوع الحركة", ["إيداع", "سحب"])
                amount = col2.number_input("المبلغ", min_value=0.01, step=100.0)
                trans_date = st.date_input("التاريخ", value=date.today())
                description = st.text_input("الوصف", placeholder="سبب الحركة")
                
                submitted = st.form_submit_button("💾 تسجيل الحركة")
                if submitted:
                    if amount <= 0:
                        st.error("المبلغ يجب أن يكون أكبر من صفر")
                    else:
                        acc_id = acc_options[selected_acc]
                        t_type = "deposit" if trans_type == "إيداع" else "withdrawal"
                        success, msg = add_cash_transaction(
                            acc_id,
                            trans_date.strftime("%Y-%m-%d"),
                            description,
                            t_type,
                            amount
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            # عرض الحركات
            st.markdown("---")
            st.subheader("سجل الحركات")
            selected_filter = st.selectbox("تصفية حسب الصندوق", ["الكل"] + [a['name'] for a in accounts])
            filter_id = None if selected_filter == "الكل" else next(a['id'] for a in accounts if a['name'] == selected_filter)
            transactions = get_cash_transactions(filter_id)
            if transactions:
                df = pd.DataFrame(transactions)
                df = df.rename(columns={
                    "transaction_date": "التاريخ",
                    "description": "الوصف",
                    "type": "النوع",
                    "amount": "المبلغ",
                    "account_name": "الصندوق",
                    "currency_code": "العملة"
                })
                df["النوع"] = df["النوع"].replace({"deposit": "إيداع", "withdrawal": "سحب"})
                st.dataframe(df[["التاريخ", "الصندوق", "النوع", "المبلغ", "العملة", "الوصف"]], use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد حركات مسجلة")

    # ========== تبويب 4: كشف حساب ==========
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>كشف حساب الصندوق</h3>", unsafe_allow_html=True)
        accounts = get_all_cash_accounts()
        if accounts:
            acc_options = {f"{a['name']} ({a['currency_code']})": a['id'] for a in accounts}
            selected_acc = st.selectbox("اختر الصندوق", list(acc_options.keys()), key="statement_acc")
            col1, col2 = st.columns(2)
            from_date = col1.date_input("من تاريخ", value=date.today().replace(day=1))
            to_date = col2.date_input("إلى تاريخ", value=date.today())
            
            if st.button("📋 عرض كشف الحساب"):
                acc_id = acc_options[selected_acc]
                statement, error = get_cash_statement(acc_id, from_date.strftime("%Y-%m-%d"), to_date.strftime("%Y-%m-%d"))
                if error:
                    st.error(error)
                else:
                    st.markdown(f"<h4 style='color:{GOLD};'>رصيد افتتاحي: {statement['opening_balance']:,.2f}</h4>", unsafe_allow_html=True)
                    if statement['transactions']:
                        df = pd.DataFrame(statement['transactions'])
                        df = df.rename(columns={"transaction_date": "التاريخ", "description": "الوصف", "type": "النوع", "amount": "المبلغ"})
                        df["النوع"] = df["النوع"].replace({"deposit": "إيداع", "withdrawal": "سحب"})
                        st.dataframe(df[["التاريخ", "النوع", "المبلغ", "الوصف"]], use_container_width=True, hide_index=True)
                    else:
                        st.info("لا توجد حركات في هذه الفترة")
                    st.markdown(f"<h4 style='color:{GOLD};'>رصيد ختامي: {statement['closing_balance']:,.2f}</h4>", unsafe_allow_html=True)
        else:
            st.warning("لا توجد حسابات صندوق.")
