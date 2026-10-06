# ui/cash_ui.py – واجهة الصندوق متعدد العملات (v3.0)
# ✅ v3.0: إضافة تبويب "تحويل" مع دعم 4 حالات
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
    get_cash_balance_summary,
)
from services import bank_service
from services.bank_service import transfer_funds
from services.currency_service import get_all_currencies
from database import get_connection, close_connection

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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 الأرصدة", "➕ إضافة صندوق", "💵 حركات", "🔄 تحويل", "📋 كشف حساب"
    ])

    # ========== تبويب 1: الأرصدة ==========
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>أرصدة الصناديق</h3>", unsafe_allow_html=True)
        summary, total_base = get_cash_balance_summary()
        if summary:
            cols = st.columns(len(summary))
            for col, acc in zip(cols, summary):
                with col:
                    st.markdown(glass_card(
                        acc['name'], "💵",
                        f"{acc['balance']:,.2f} {acc['currency']}",
                        ACCENT_GREEN if acc['balance'] >= 0 else ACCENT_RED
                    ), unsafe_allow_html=True)
            st.markdown(
                f"<h4 style='color:{GOLD}; text-align:center;'>"
                f"إجمالي الأرصدة (بالعملة الأساسية): {total_base:,.2f}</h4>",
                unsafe_allow_html=True
            )
        else:
            st.info("لا توجد حسابات صندوق. أضف حساباً جديداً من التبويب الثاني.")

    # ========== تبويب 2: إضافة صندوق ==========
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة حساب صندوق جديد</h3>",
                    unsafe_allow_html=True)
        currencies = get_all_currencies()
        currency_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}

        with st.form("add_cash_form", clear_on_submit=True):
            name = st.text_input("اسم الصندوق", placeholder="مثال: صندوق الدولار")
            col1, col2 = st.columns(2)
            currency_label = col1.selectbox("العملة", list(currency_options.keys()))
            opening_balance = col2.number_input("الرصيد الافتتاحي",
                                                  min_value=0.0, step=100.0)

            submitted = st.form_submit_button("💾 حفظ الصندوق")
            if submitted:
                if not name:
                    st.error("اسم الصندوق مطلوب")
                else:
                    currency_code = currency_options[currency_label]
                    success, msg = create_cash_account(name, currency_code,
                                                        opening_balance)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # ========== تبويب 3: حركات ==========
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>حركات الصندوق</h3>",
                    unsafe_allow_html=True)
        accounts = get_all_cash_accounts()
        if not accounts:
            st.warning("لا توجد حسابات صندوق.")
        else:
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

            st.markdown("---")
            st.subheader("سجل الحركات")
            selected_filter = st.selectbox(
                "تصفية حسب الصندوق",
                ["الكل"] + [a['name'] for a in accounts]
            )
            filter_id = None if selected_filter == "الكل" else next(
                a['id'] for a in accounts if a['name'] == selected_filter
            )
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
                df["النوع"] = df["النوع"].replace({"deposit": "إيداع",
                                                     "withdrawal": "سحب"})
                st.dataframe(
                    df[["التاريخ", "الصندوق", "النوع", "المبلغ", "العملة", "الوصف"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("لا توجد حركات مسجلة")

    # ========== ✅ تبويب 4: تحويل (جديد v3.0) ==========
    with tab4:
        st.markdown(f"<h3 style='color:{GOLD};'>🔄 تحويل بين الحسابات</h3>",
                    unsafe_allow_html=True)

        # 1. جلب قائمة موحّدة — بنوك + صناديق
        bank_accounts = bank_service.get_all_bank_accounts(active_only=True)
        cash_accounts = get_all_cash_accounts(active_only=True)

        if not bank_accounts and not cash_accounts:
            st.warning("لا توجد حسابات بنكية أو صناديق. أضف حساباً أولاً.")
        else:
            # بناء قائمة الخيارات الموحّدة
            options = []
            options_map = {}

            for b in bank_accounts:
                label = f"🏦 {b['bank_name']} ({b['currency_code']}) — {b['current_balance']:,.2f}"
                options.append(label)
                options_map[label] = {
                    "kind": "bank",
                    "id": b['id'],
                    "name": b['bank_name'],
                    "currency": b['currency_code'],
                    "balance": b['current_balance'],
                }

            for c in cash_accounts:
                label = f"💵 {c['name']} ({c['currency_code']}) — {c['current_balance']:,.2f}"
                options.append(label)
                options_map[label] = {
                    "kind": "cash",
                    "id": c['id'],
                    "name": c['name'],
                    "currency": c['currency_code'],
                    "balance": c['current_balance'],
                }

            # النموذج
            with st.form("transfer_form_cash"):
                col1, col2 = st.columns(2)

                with col1:
                    from_label = st.selectbox(
                        "📤 من (المصدر)",
                        options,
                        key="cash_transfer_from"
                    )

                with col2:
                    to_options = [o for o in options if o != from_label]
                    to_label = st.selectbox(
                        "📥 إلى (الهدف)",
                        to_options,
                        key="cash_transfer_to"
                    )

                col3, col4 = st.columns(2)
                with col3:
                    amount = st.number_input(
                        "💰 المبلغ",
                        min_value=0.01,
                        step=100.0,
                        value=1000.0,
                        key="cash_transfer_amount"
                    )
                    transfer_date = st.date_input(
                        "📅 التاريخ",
                        value=date.today(),
                        key="cash_transfer_date"
                    )
                with col4:
                    description = st.text_input(
                        "📝 البيان",
                        value="تحويل بين الحسابات",
                        key="cash_transfer_desc"
                    )
                    reference = st.text_input(
                        "🔖 المرجع (اختياري)",
                        key="cash_transfer_ref"
                    )

                submitted = st.form_submit_button(
                    "🔄 تنفيذ التحويل",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    from_info = options_map[from_label]
                    to_info = options_map[to_label]

                    if amount > from_info["balance"] + 0.001:
                        st.error(
                            f"❌ الرصيد غير كافٍ\n\n"
                            f"المتاح في **{from_info['name']}**: "
                            f"**{from_info['balance']:,.2f}** {from_info['currency']}\n\n"
                            f"المطلوب: **{amount:,.2f}** {from_info['currency']}"
                        )
                    else:
                        try:
                            journal_id, err = transfer_funds(
                                from_kind=from_info["kind"],
                                from_id=from_info["id"],
                                to_kind=to_info["kind"],
                                to_id=to_info["id"],
                                amount=amount,
                                transfer_date=transfer_date.strftime("%Y-%m-%d"),
                                description=description,
                                reference=reference,
                            )

                            if err:
                                st.error(f"❌ فشل التحويل: {err}")
                            else:
                                st.success(
                                    f"✅ تم التحويل بنجاح\n\n"
                                    f"**من**: {from_info['name']}\n\n"
                                    f"**إلى**: {to_info['name']}\n\n"
                                    f"**المبلغ**: {amount:,.2f} {from_info['currency']}"
                                )
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ خطأ غير متوقع: {e}")

            # ✅ عرض آخر التحويلات
            st.markdown("---")
            st.markdown(
                f"<h4 style='color:{TEXT_PRIMARY};'>📋 آخر التحويلات</h4>",
                unsafe_allow_html=True
            )

            try:
                conn = get_connection()
                try:
                    # جلب من bank_transactions
                    bank_transfers = conn.execute("""
                        SELECT 
                            bt.id, bt.transaction_date, bt.type, bt.amount,
                            bt.reference, bt.description,
                            ba.bank_name as source_name,
                            ba.currency_code as currency,
                            'bank' as source_kind
                        FROM bank_transactions bt
                        JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                        WHERE bt.type IN ('transfer_in', 'transfer_out')
                        ORDER BY bt.id DESC
                        LIMIT 15
                    """).fetchall()

                    # جلب من cash_transactions
                    cash_transfers = conn.execute("""
                        SELECT 
                            ct.id, ct.transaction_date, ct.type, ct.amount,
                            ct.reference, ct.description,
                            ca.name as source_name,
                            ca.currency_code as currency,
                            'cash' as source_kind
                        FROM cash_transactions ct
                        JOIN cash_accounts ca ON ct.cash_account_id = ca.id
                        WHERE ct.reference LIKE 'TR-%'
                        ORDER BY ct.id DESC
                        LIMIT 15
                    """).fetchall()

                    all_transfers = list(bank_transfers) + list(cash_transfers)

                    if all_transfers:
                        # ترتيب حسب ID عكسي
                        all_transfers_sorted = sorted(
                            all_transfers,
                            key=lambda x: x['id'],
                            reverse=True
                        )[:20]

                        rows = []
                        for t in all_transfers_sorted:
                            if t['type'] == 'transfer_out':
                                type_label = "↗️ صادر"
                            elif t['type'] == 'transfer_in':
                                type_label = "↘️ وارد"
                            elif t['type'] == 'withdrawal':
                                type_label = "↗️ صادر"
                            else:
                                type_label = "↘️ وارد"

                            icon = "🏦" if t['source_kind'] == 'bank' else "💵"

                            rows.append({
                                "التاريخ": t['transaction_date'],
                                "النوع": type_label,
                                "الحساب": f"{icon} {t['source_name']}",
                                "المبلغ": f"{t['amount']:,.2f} {t['currency']}",
                                "المرجع": t['reference'] or "—",
                                "البيان": t['description'] or "—",
                            })

                        df_transfers = pd.DataFrame(rows)
                        st.dataframe(df_transfers,
                                     use_container_width=True,
                                     hide_index=True)
                    else:
                        st.info("لا توجد تحويلات سابقة")
                finally:
                    close_connection(conn)
            except Exception as e:
                st.info("لا توجد تحويلات سابقة")

    # ========== تبويب 5: كشف حساب ==========
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>كشف حساب الصندوق</h3>",
                    unsafe_allow_html=True)
        accounts = get_all_cash_accounts()
        if accounts:
            acc_options = {f"{a['name']} ({a['currency_code']})": a['id'] for a in accounts}
            selected_acc = st.selectbox("اختر الصندوق", list(acc_options.keys()),
                                          key="statement_acc")
            col1, col2 = st.columns(2)
            from_date = col1.date_input("من تاريخ", value=date.today().replace(day=1))
            to_date = col2.date_input("إلى تاريخ", value=date.today())

            if st.button("📋 عرض كشف الحساب"):
                acc_id = acc_options[selected_acc]
                statement, error = get_cash_statement(
                    acc_id,
                    from_date.strftime("%Y-%m-%d"),
                    to_date.strftime("%Y-%m-%d")
                )
                if error:
                    st.error(error)
                else:
                    st.markdown(
                        f"<h4 style='color:{GOLD};'>رصيد افتتاحي: "
                        f"{statement['opening_balance']:,.2f}</h4>",
                        unsafe_allow_html=True
                    )
                    if statement['transactions']:
                        df = pd.DataFrame(statement['transactions'])
                        df = df.rename(columns={
                            "transaction_date": "التاريخ",
                            "description": "الوصف",
                            "type": "النوع",
                            "amount": "المبلغ"
                        })
                        df["النوع"] = df["النوع"].replace({
                            "deposit": "إيداع",
                            "withdrawal": "سحب"
                        })
                        st.dataframe(
                            df[["التاريخ", "النوع", "المبلغ", "الوصف"]],
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.info("لا توجد حركات في هذه الفترة")
                    st.markdown(
                        f"<h4 style='color:{GOLD};'>رصيد ختامي: "
                        f"{statement['closing_balance']:,.2f}</h4>",
                        unsafe_allow_html=True
                    )
        else:
            st.warning("لا توجد حسابات صندوق.")
