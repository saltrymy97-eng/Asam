# ui/cash_ui.py – واجهة الصندوق متعدد العملات (v4.1)
# 🔧 v4.1 — إصلاح إضافي:
#   ✅ حل مشكلة Streamlit: الاحتفاظ بقيمة قديمة في قائمة "إلى"
# 🔧 v4.0 — الإصلاحات السابقة:
#   ✅ حل مشكلة الرقم الثابت في st.number_input
#   ✅ قائمة المصدر/الوجهة بهوية (kind, id)
#   ✅ آخر التحويلات تُجمّع الحركتين في عملية واحدة بـ transfer_reference
#   ✅ عرض جميع الصناديق النشطة
#   ✅ تمرير amount الصحيح من الواجهة إلى الخدمة

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

# ========== ألوان التصميم ==========
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


def _build_transfer_options():
    bank_accounts = bank_service.get_all_bank_accounts(active_only=True)
    cash_accounts = get_all_cash_accounts(active_only=True)

    options = []
    options_map = {}

    for b in bank_accounts:
        key = ("bank", b['id'])
        options.append(key)
        options_map[key] = {
            "kind": "bank",
            "id": b['id'],
            "name": b['bank_name'],
            "account_number": b.get('account_number', ''),
            "currency": b.get('currency_code') or '',
            "balance": float(b.get('current_balance') or 0),
        }

    for c in cash_accounts:
        key = ("cash", c['id'])
        options.append(key)
        options_map[key] = {
            "kind": "cash",
            "id": c['id'],
            "name": c['name'],
            "account_number": '',
            "currency": c.get('currency_code') or '',
            "balance": float(c.get('current_balance') or 0),
        }

    return options, options_map


def _format_transfer_option(key, options_map):
    info = options_map.get(key)
    if not info:
        return "?"
    icon = "🏦" if info["kind"] == "bank" else "💵"
    return (
        f"{icon} {info['name']} ({info['currency']}) — "
        f"{info['balance']:,.2f}"
    )


def _render_recent_transfers():
    conn = get_connection()
    try:
        rows = []

        try:
            bank_rows = conn.execute("""
                SELECT 
                    bt.reference, bt.transaction_date, bt.type, bt.amount,
                    bt.description, bt.journal_id,
                    ba.bank_name as acc_name,
                    ba.currency_code as currency,
                    'bank' as acc_kind
                FROM bank_transactions bt
                JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                WHERE bt.reference LIKE 'TR-%'
            """).fetchall()
            for r in bank_rows:
                rows.append(dict(r))
        except Exception:
            pass

        try:
            cash_rows = conn.execute("""
                SELECT 
                    ct.reference, ct.transaction_date, ct.type, ct.amount,
                    ct.description, ct.journal_id,
                    ca.name as acc_name,
                    ca.currency_code as currency,
                    'cash' as acc_kind
                FROM cash_transactions ct
                JOIN cash_accounts ca ON ct.cash_account_id = ca.id
                WHERE ct.reference LIKE 'TR-%'
            """).fetchall()
            for r in cash_rows:
                rows.append(dict(r))
        except Exception:
            pass

        if not rows:
            st.info("لا توجد تحويلات سابقة")
            return

        grouped = {}
        for r in rows:
            ref = r['reference']
            if ref not in grouped:
                grouped[ref] = {
                    'reference': ref,
                    'date': r['transaction_date'],
                    'journal_id': r['journal_id'],
                    'source': None,
                    'destination': None,
                    'amount': None,
                    'currency': r['currency'],
                }
            if r['type'] in ('transfer_out', 'withdrawal'):
                grouped[ref]['source'] = r['acc_name']
                grouped[ref]['amount'] = r['amount']
            elif r['type'] in ('transfer_in', 'deposit'):
                grouped[ref]['destination'] = r['acc_name']

        sorted_refs = sorted(
            grouped.values(),
            key=lambda x: (x['date'] or '', x['reference']),
            reverse=True
        )[:20]

        display_rows = []
        for g in sorted_refs:
            display_rows.append({
                "المرجع": g['reference'],
                "التاريخ": g['date'],
                "من": g['source'] or "—",
                "إلى": g['destination'] or "—",
                "المبلغ": f"{g['amount']:,.2f} {g['currency']}" if g['amount'] else "—",
                "القيد": g['journal_id'] or "—",
            })

        st.dataframe(
            pd.DataFrame(display_rows),
            use_container_width=True,
            hide_index=True
        )
    finally:
        close_connection(conn)


def show():
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
            opening_balance = col2.number_input(
                "الرصيد الافتتاحي",
                min_value=0.0,
                step=100.0,
                key="add_cash_opening"
            )

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
                selected_acc = st.selectbox(
                    "اختر الصندوق",
                    list(acc_options.keys()),
                    key="cash_tx_acc"
                )
                col1, col2 = st.columns(2)
                trans_type = col1.selectbox(
                    "نوع الحركة",
                    ["إيداع", "سحب"],
                    key="cash_tx_type"
                )
                amount = col2.number_input(
                    "المبلغ",
                    min_value=0.01,
                    step=100.0,
                    key="cash_tx_amount"
                )
                trans_date = st.date_input(
                    "التاريخ",
                    value=date.today(),
                    key="cash_tx_date"
                )
                description = st.text_input(
                    "الوصف",
                    placeholder="سبب الحركة",
                    key="cash_tx_desc"
                )

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

            active_accounts = get_all_cash_accounts(active_only=True)
            selected_filter = st.selectbox(
                "تصفية حسب الصندوق",
                ["الكل"] + [a['name'] for a in active_accounts],
                key="cash_tx_filter"
            )
            filter_id = None if selected_filter == "الكل" else next(
                a['id'] for a in active_accounts if a['name'] == selected_filter
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

    # ========== تبويب 4: تحويل ==========
    with tab4:
        st.markdown(f"<h3 style='color:{GOLD};'>🔄 تحويل بين الحسابات</h3>",
                    unsafe_allow_html=True)

        options, options_map = _build_transfer_options()

        if not options:
            st.warning("لا توجد حسابات بنكية أو صناديق. أضف حساباً أولاً.")
        else:
            with st.form("transfer_form_cash"):
                col1, col2 = st.columns(2)

                with col1:
                    from_key = st.selectbox(
                        "📤 من (المصدر)",
                        options,
                        format_func=lambda k: _format_transfer_option(k, options_map),
                        key="cash_transfer_from_key"
                    )

                with col2:
                    # 🔧 v4.1: قائمة "إلى" + إصلاح احتفاظ Streamlit
                    to_options = [k for k in options if k != from_key]
                    if not to_options:
                        st.warning("لا يوجد حساب هدف متاح")
                        to_key = None
                    else:
                        # 🔧 v4.1: إذا كانت القيمة المحفوظة تساوي from_key، صفّرها
                        current_to = st.session_state.get("cash_transfer_to_key")
                        if current_to == from_key or current_to not in to_options:
                            st.session_state["cash_transfer_to_key"] = to_options[0]

                        to_key = st.selectbox(
                            "📥 إلى (الهدف)",
                            to_options,
                            format_func=lambda k: _format_transfer_option(k, options_map),
                            key="cash_transfer_to_key"
                        )

                col3, col4 = st.columns(2)
                with col3:
                    amount = st.number_input(
                        "💰 المبلغ",
                        min_value=0.01,
                        step=100.0,
                        value=None,
                        placeholder="أدخل المبلغ",
                        key="cash_transfer_amount_input"
                    )
                    transfer_date = st.date_input(
                        "📅 التاريخ",
                        value=date.today(),
                        key="cash_transfer_date_input"
                    )
                with col4:
                    description = st.text_input(
                        "📝 البيان",
                        value="تحويل بين الحسابات",
                        key="cash_transfer_desc_input"
                    )
                    reference = st.text_input(
                        "🔖 المرجع (اختياري — يُولّد تلقائيًا إن تُرك فارغًا)",
                        key="cash_transfer_ref_input"
                    )

                submitted = st.form_submit_button(
                    "🔄 تنفيذ التحويل",
                    type="primary",
                    use_container_width=True
                )

                if submitted:
                    if to_key is None:
                        st.error("اختر حساب الهدف.")
                    elif amount is None or amount <= 0:
                        st.error("أدخل مبلغًا صحيحًا أكبر من صفر.")
                    else:
                        from_info = options_map[from_key]
                        to_info = options_map[to_key]

                        if from_info["currency"] != to_info["currency"]:
                            st.error(
                                f"❌ لا يمكن التحويل بين عملتين مختلفتين.\n\n"
                                f"المصدر: {from_info['currency']} — "
                                f"الهدف: {to_info['currency']}"
                            )
                        elif amount > from_info["balance"] + 0.001:
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
                                    amount=float(amount),
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
                                        f"**المبلغ**: {amount:,.2f} {from_info['currency']}\n\n"
                                        f"**رقم القيد**: {journal_id}"
                                    )
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ خطأ غير متوقع: {e}")

            st.markdown("---")
            st.markdown(
                f"<h4 style='color:{TEXT_PRIMARY};'>📋 آخر التحويلات</h4>",
                unsafe_allow_html=True
            )
            _render_recent_transfers()

    # ========== تبويب 5: كشف حساب ==========
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>كشف حساب الصندوق</h3>",
                    unsafe_allow_html=True)
        accounts = get_all_cash_accounts()
        if accounts:
            acc_options = {f"{a['name']} ({a['currency_code']})": a['id'] for a in accounts}
            selected_acc = st.selectbox(
                "اختر الصندوق",
                list(acc_options.keys()),
                key="statement_acc"
            )
            col1, col2 = st.columns(2)
            from_date = col1.date_input(
                "من تاريخ",
                value=date.today().replace(day=1),
                key="statement_from_date"
            )
            to_date = col2.date_input(
                "إلى تاريخ",
                value=date.today(),
                key="statement_to_date"
            )

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
