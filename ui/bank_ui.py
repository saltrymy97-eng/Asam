# ui/bank_ui.py – واجهة التعاملات البنكية (v4.1)
# 🔧 v4.1 — إصلاح إضافي:
#   ✅ حل مشكلة Streamlit: الاحتفاظ بقيمة قديمة في قائمة "إلى"
#      (كان يعرض نفس الحساب المختار في "من" مؤقتًا)
# 🔧 v4.0 — الإصلاحات السابقة:
#   ✅ حل مشكلة الرقم الثابت في st.number_input
#   ✅ قائمة المصدر/الوجهة بهوية (kind, id) وليس بالاسم
#   ✅ آخر التحويلات تُجمّع الحركتين في عملية واحدة بـ transfer_reference
#   ✅ عرض جميع البنوك/النقديات النشطة
#   ✅ تمرير amount الصحيح من الواجهة إلى الخدمة

import streamlit as st
import pandas as pd
from datetime import date
from services import bank_service as bank
from services import cash_service
from services.bank_service import transfer_funds
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


def _build_transfer_options():
    bank_accounts = bank.get_all_bank_accounts(active_only=True)
    cash_accounts = cash_service.get_all_cash_accounts(active_only=True)

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
    from database import get_connection, close_connection
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
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_BLUE};">🏦 التعاملات البنكية</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الحسابات البنكية والحركات والمصالحات والتحويلات</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏛️ الحسابات", "💳 الحركات", "🔄 تحويل", "⚖️ مصالحة", "📊 ملخص"
    ])

    # ---------- تبويب 1: الحسابات ----------
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
                def_label = next(
                    (k for k, v in currency_list.items() if v == (base['code'] if base else 'YER')),
                    list(currency_list.keys())[0]
                )
                currency_choice = st.selectbox(
                    "العملة",
                    list(currency_list.keys()),
                    index=list(currency_list.keys()).index(def_label)
                )
                opening_balance = st.number_input(
                    "الرصيد الافتتاحي",
                    min_value=0.0,
                    step=100.0,
                    value=0.0,
                    key="add_bank_opening"
                )
                if st.form_submit_button("✅ إضافة"):
                    if not bank_name or not account_number:
                        st.error("اسم البنك ورقم الحساب مطلوبان")
                    else:
                        try:
                            bank.create_bank_account(
                                bank_name, account_number, account_name,
                                currency_list[currency_choice], opening_balance
                            )
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

    # ---------- تبويب 2: الحركات ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تسجيل حركة بنكية</h3>", unsafe_allow_html=True)
        accounts = bank.get_all_bank_accounts()
        if not accounts:
            st.warning("أضف حساباً بنكياً أولاً")
        else:
            acc_options = {f"{a['bank_name']} - {a['account_number']}": a['id'] for a in accounts}
            selected_acc_label = st.selectbox(
                "اختر الحساب",
                list(acc_options.keys()),
                key="bank_tx_acc_select"
            )
            acc_id = acc_options[selected_acc_label]

            with st.form("transaction_form"):
                col1, col2 = st.columns(2)
                with col1:
                    trans_date = st.date_input(
                        "التاريخ",
                        value=date.today(),
                        key="bank_tx_date"
                    )
                    trans_type = st.selectbox(
                        "نوع الحركة",
                        ["deposit", "withdrawal", "transfer_in", "transfer_out"],
                        format_func=lambda x: {
                            "deposit": "إيداع",
                            "withdrawal": "سحب",
                            "transfer_in": "تحويل وارد",
                            "transfer_out": "تحويل صادر"
                        }[x],
                        key="bank_tx_type"
                    )
                with col2:
                    amount = st.number_input(
                        "المبلغ",
                        min_value=0.01,
                        step=0.01,
                        key="bank_tx_amount"
                    )
                    reference = st.text_input(
                        "المرجع (اختياري)",
                        key="bank_tx_ref"
                    )
                description = st.text_input(
                    "البيان",
                    key="bank_tx_desc"
                )
                if st.form_submit_button("💾 حفظ الحركة"):
                    if not description:
                        st.error("البيان مطلوب")
                    else:
                        try:
                            bank.add_bank_transaction(
                                acc_id, trans_date.strftime("%Y-%m-%d"),
                                description, trans_type, amount, reference
                            )
                            st.success("تم تسجيل الحركة")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

        st.markdown("---")
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 الحركات البنكية</h3>", unsafe_allow_html=True)

        active_accounts = bank.get_all_bank_accounts(active_only=True)
        filter_options = ["الكل"] + [
            f"{a['bank_name']} - {a['account_number']}" for a in active_accounts
        ]
        selected_filter = st.selectbox(
            "تصفية حسب الحساب",
            filter_options,
            key="bank_tx_filter"
        )
        if selected_filter == "الكل":
            transactions = bank.get_bank_transactions()
        else:
            sel_id = next(
                a['id'] for a in active_accounts
                if f"{a['bank_name']} - {a['account_number']}" == selected_filter
            )
            transactions = bank.get_bank_transactions(bank_account_id=sel_id)

        if transactions:
            df = pd.DataFrame(transactions)
            df['type'] = df['type'].map({
                "deposit": "إيداع",
                "withdrawal": "سحب",
                "transfer_in": "تحويل وارد",
                "transfer_out": "تحويل صادر"
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حركات")

    # ---------- تبويب 3: تحويل ----------
    with tab3:
        st.markdown(
            f"<h3 style='color:{ACCENT_BLUE};'>🔄 تحويل بين الحسابات</h3>",
            unsafe_allow_html=True
        )

        options, options_map = _build_transfer_options()

        if not options:
            st.warning("لا توجد حسابات بنكية أو صناديق. أضف حساباً أولاً.")
        else:
            with st.form("transfer_form"):
                col1, col2 = st.columns(2)

                with col1:
                    from_key = st.selectbox(
                        "📤 من (المصدر)",
                        options,
                        format_func=lambda k: _format_transfer_option(k, options_map),
                        key="transfer_from_key"
                    )

                with col2:
                    # 🔧 v4.1: قائمة "إلى" بدون from_key + إصلاح احتفاظ Streamlit
                    to_options = [k for k in options if k != from_key]
                    if not to_options:
                        st.warning("لا يوجد حساب هدف متاح")
                        to_key = None
                    else:
                        # 🔧 v4.1: إذا كانت القيمة المحفوظة تساوي from_key،
                        # نُصفّرها قبل عرض الـ widget — يمنع ظهور نفس الحساب.
                        current_to = st.session_state.get("transfer_to_key")
                        if current_to == from_key or current_to not in to_options:
                            st.session_state["transfer_to_key"] = to_options[0]

                        to_key = st.selectbox(
                            "📥 إلى (الهدف)",
                            to_options,
                            format_func=lambda k: _format_transfer_option(k, options_map),
                            key="transfer_to_key"
                        )

                col3, col4 = st.columns(2)
                with col3:
                    amount = st.number_input(
                        "💰 المبلغ",
                        min_value=0.01,
                        step=100.0,
                        value=None,
                        placeholder="أدخل المبلغ",
                        key="transfer_amount_input"
                    )
                    transfer_date = st.date_input(
                        "📅 التاريخ",
                        value=date.today(),
                        key="transfer_date_input"
                    )
                with col4:
                    description = st.text_input(
                        "📝 البيان",
                        value="تحويل بين الحسابات",
                        key="transfer_desc_input"
                    )
                    reference = st.text_input(
                        "🔖 المرجع (اختياري — يُولّد تلقائيًا إن تُرك فارغًا)",
                        key="transfer_ref_input"
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

    # ---------- تبويب 4: المصالحة ----------
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>⚖️ المصالحة البنكية</h3>", unsafe_allow_html=True)
        accounts = bank.get_all_bank_accounts()
        if accounts:
            acc_options2 = {f"{a['bank_name']} - {a['account_number']}": a['id'] for a in accounts}
            sel_acc2_label = st.selectbox(
                "اختر الحساب",
                list(acc_options2.keys()),
                key="reconcile_acc"
            )
            acc_id2 = acc_options2[sel_acc2_label]
            acc_info = next(a for a in accounts if a['id'] == acc_id2)
            st.write(f"رصيد الدفاتر الحالي: **{acc_info['current_balance']:,.2f} {acc_info['currency_code']}**")

            with st.form("reconciliation_form"):
                stmt_date = st.date_input("تاريخ كشف البنك", value=date.today())
                stmt_balance = st.number_input(
                    "رصيد كشف البنك",
                    min_value=0.0,
                    step=0.01,
                    key="reconcile_balance"
                )

                notes = st.text_area(
                    "ملاحظات المصالحة (اختياري)",
                    placeholder="اكتب أي ملاحظات تفسر الفرق بين رصيد الدفاتر وكشف البنك...",
                    height=100,
                    key="reconciliation_notes"
                )

                if st.form_submit_button("🔍 تنفيذ المصالحة"):
                    try:
                        success, diff = bank.create_bank_reconciliation(
                            acc_id2,
                            stmt_date.strftime("%Y-%m-%d"),
                            stmt_balance,
                            notes=notes
                        )
                        if success:
                            st.success(f"✅ تمت المصالحة. الفرق: {diff:,.2f}")
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))

            unreconciled = bank.get_unreconciled_transactions(acc_id2)
            if unreconciled:
                st.markdown("**حركات غير مسواة:**")
                st.dataframe(pd.DataFrame(unreconciled), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حسابات")

    # ---------- تبويب 5: ملخص ----------
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_PURPLE};'>📊 ملخص الأرصدة البنكية</h3>", unsafe_allow_html=True)
        summary, total_base = bank.get_bank_balance_summary()
        if summary:
            df = pd.DataFrame(summary)
            st.dataframe(df, use_container_width=True, hide_index=True)
            base_cur = get_base_currency()
            base_code = base_cur['code'] if base_cur else 'YER'
            st.markdown(f"### إجمالي الأرصدة بالعملة الأساسية ({base_code}): {total_base:,.2f}")

            st.markdown("---")
            st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 سجل المصالحات</h3>", unsafe_allow_html=True)
            reconciliations = bank.get_reconciliation_history()
            if reconciliations:
                df_rec = pd.DataFrame(reconciliations)
                display_cols = ['id', 'reconciliation_date', 'statement_balance',
                                'book_balance', 'difference', 'notes']
                display_cols = [c for c in display_cols if c in df_rec.columns]
                st.dataframe(df_rec[display_cols], use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد مصالحات سابقة")
        else:
            st.info("لا توجد حسابات بنكية نشطة")
