# ui/receipts_ui.py – واجهة سندات القبض والصرف (v4.0)
# ✅ دعم البنك + الصندوق + عرض الرصيد + فحص فوري
import streamlit as st
import pandas as pd
from datetime import date
from services.receipts_service import (
    create_vouchers_table,
    get_payment_accounts,           # ✅ موحّدة: صناديق + بنوك
    get_customers_with_balances,
    get_suppliers_with_balances,
    get_invoices_for_party,
    create_voucher,
    get_vouchers,
    get_voucher_details,
    link_voucher_to_invoice,
    unlink_voucher_from_invoice,
    get_unlinked_vouchers,
    get_vouchers_by_party,
    get_party_invoices_with_status,
)


# ========== ألوان ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"

PAYMENT_STATUS_LABELS = {
    "unpaid":  "🔴 غير مدفوعة",
    "partial": "🟡 مدفوعة جزئياً",
    "paid":    "🟢 مدفوعة بالكامل",
}


# ============================================================
# مساعدات
# ============================================================
def _get_value(d, *keys, default=0):
    """استخراج قيمة من قاموس بأحد المفاتيح المحتملة"""
    if d is None:
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _account_icon(acc_type: str) -> str:
    """أيقونة حسب نوع الحساب"""
    return "🏦" if acc_type == "bank" else "💵"


def _account_label(acc: dict) -> str:
    """تسمية موحّدة للحساب"""
    icon = _account_icon(acc.get("type", "cash"))
    name = acc.get("name", "—")
    bal = float(acc.get("balance", 0) or 0)
    cur = acc.get("currency", "YER")
    return f"{icon} {acc.get('code', '')} - {name}  |  الرصيد: {bal:,.2f} {cur}"


def _render_account_info(acc: dict):
    """بطاقة معلومات الحساب المختار"""
    if not acc:
        return
    icon = _account_icon(acc.get("type", "cash"))
    kind = "بنك" if acc.get("type") == "bank" else "صندوق"
    bal = float(acc.get("balance", 0) or 0)
    cur = acc.get("currency", "YER")
    color = GR if bal > 0 else RD

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg, rgba(59,130,246,0.15), rgba(139,92,246,0.10));
            border-right: 4px solid {BL};
            border-radius: 8px; padding: 12px 16px; margin: 6px 0;
            text-align: right; direction: rtl;
        ">
            <span style="color:{S}; font-size:0.9rem;">{icon} {kind} مختار:</span>
            <b style="color:{T}; margin-right:8px;">{acc.get('name','—')}</b>
            <span style="color:{S};">({acc.get('code','')})</span>
            &nbsp;|&nbsp;
            <span style="color:{S};">الرصيد المتاح:</span>
            <b style="color:{color}; font-size:1.05rem;"> {bal:,.2f} {cur}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_party_card(name: str, balance: float, currency: str = "YER"):
    """بطاقة الطرف والرصيد المستحق"""
    color = RD if balance > 0 else GR
    st.markdown(
        f"""
        <div style="
            background: rgba(16,185,129,0.10);
            border-right: 4px solid {color};
            border-radius: 8px; padding: 10px 16px; margin: 6px 0;
            text-align: right; direction: rtl;
        ">
            <span style="color:{S};">الطرف:</span>
            <b style="color:{T};"> {name} </b>
            &nbsp;|&nbsp;
            <span style="color:{S};">الرصيد المستحق:</span>
            <b style="color:{color};"> {balance:,.2f} {currency}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# نموذج سند موحّد (قبض / صرف)
# ============================================================
def _render_voucher_form(voucher_type: str):
    """
    voucher_type: 'receipt' أو 'payment'
    """
    is_receipt = voucher_type == 'receipt'
    party_type = 'customer' if is_receipt else 'supplier'
    title = "سند قبض" if is_receipt else "سند صرف"
    icon = "🧾" if is_receipt else "📤"
    color = GR if is_receipt else RD

    st.markdown(f"<h3 style='color:{color};'>{icon} {title}</h3>",
                unsafe_allow_html=True)

    # 1) الحسابات (صناديق + بنوك)
    accounts = get_payment_accounts()
    if not accounts:
        st.error("⚠️ لا توجد صناديق أو بنوك نشطة. أضف حساباً أولاً.")
        return

    # 2) الأطراف
    if is_receipt:
        parties = get_customers_with_balances()
        party_label = "العميل"
    else:
        parties = get_suppliers_with_balances()
        party_label = "المورد"

    if not parties:
        st.warning(f"لا يوجد {party_label}ون")
        return

    # -------- الصف الأول: الطرف + الحساب --------
    col_a, col_b = st.columns(2)

    with col_a:
        party_options = {
            f"{p['name']} (رصيد: {float(p['balance']):,.2f})": p
            for p in parties
        }
        party_sel_str = st.selectbox(
            f"اختر {party_label}",
            list(party_options.keys()),
            key=f"{voucher_type}_party"
        )
        party = party_options[party_sel_str]
        _render_party_card(party['name'], float(party['balance']))

    with col_b:
        account_options = {_account_label(a): a for a in accounts}
        account_sel_str = st.selectbox(
            "حساب الدفع (صندوق / بنك)",
            list(account_options.keys()),
            key=f"{voucher_type}_account"
        )
        account = account_options[account_sel_str]
        _render_account_info(account)

    # -------- الفواتير المعلقة --------
    invoices = get_invoices_for_party(party_type, party['id'])
    invoice_options = {"بدون فاتورة (دفعة عامة)": None}
    for inv in invoices:
        remaining = _get_value(inv, 'remaining_amount', 'remaining')
        label = f"فاتورة #{inv['id']} | المتبقي: {float(remaining):,.2f}"
        invoice_options[label] = inv

    inv_sel_str = st.selectbox(
        "ربط بفاتورة (اختياري)",
        list(invoice_options.keys()),
        key=f"{voucher_type}_invoice"
    )
    selected_inv = invoice_options[inv_sel_str]

    # -------- المبلغ + التاريخ --------
    col_c, col_d, col_e = st.columns(3)

    with col_c:
        default_amount = 0.0
        if selected_inv:
            default_amount = float(
                _get_value(selected_inv, 'remaining_amount', 'remaining') or 0
            )
        amount = st.number_input(
            "المبلغ",
            min_value=0.0,
            value=default_amount,
            step=0.01,
            key=f"{voucher_type}_amount"
        )

    with col_d:
        voucher_date = st.date_input(
            "التاريخ",
            value=date.today(),
            key=f"{voucher_type}_date"
        )

    with col_e:
        st.write("")  # placeholder
        st.write("")
        # فحص الرصيد الفوري (سند صرف فقط)
        if not is_receipt and amount > 0:
            available = float(account.get("balance", 0) or 0)
            if amount > available + 0.01:
                shortage = amount - available
                st.error(f"❌ نقص: {shortage:,.2f}")
            else:
                st.success("✅ الرصيد كافٍ")

    # -------- المرجع + الملاحظات --------
    reference = st.text_input("المرجع (اختياري)", key=f"{voucher_type}_ref")
    notes = st.text_area("ملاحظات", key=f"{voucher_type}_notes")

    # -------- فحص نهائي + زر الحفظ --------
    can_save = True
    reason = ""

    if amount <= 0:
        can_save = False
        reason = "المبلغ يجب أن يكون أكبر من صفر"
    elif not is_receipt:
        available = float(account.get("balance", 0) or 0)
        if amount > available + 0.01:
            can_save = False
            reason = f"الرصيد غير كافٍ — المتاح: {available:,.2f} {account.get('currency', 'YER')}"

    if not can_save:
        st.warning(f"⚠️ {reason}")

    if st.button(
        f"💾 حفظ {title}",
        type="primary",
        key=f"save_{voucher_type}",
        disabled=not can_save
    ):
        account_code = account.get("code", "")
        if not account_code:
            st.error("❌ لم يتم تحديد كود الحساب")
            return

        inv_id = selected_inv['id'] if selected_inv else None
        username = st.session_state.get('user', {}).get('username', 'admin')

        vid, err = create_voucher(
            voucher_type=voucher_type,
            party_type=party_type,
            party_id=party['id'],
            amount=amount,
            account=account_code,
            invoice_id=inv_id,
            reference=reference,
            notes=notes,
            created_by=username,
            voucher_date=voucher_date.strftime("%Y-%m-%d")
        )

        if err:
            st.error(f"❌ فشل الحفظ: {err}")
        else:
            acc_icon = _account_icon(account.get("type", "cash"))
            st.success(
                f"✅ تم إنشاء {title} رقم **#{vid}** "
                f"({acc_icon} {account.get('name','')})"
            )
            st.rerun()


# ============================================================
# الواجهة الرئيسية
# ============================================================
def show():
    create_vouchers_table()

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">💵 سندات القبض والصرف</h1>
        <p style="color:{S}; font-size:1.2rem;">إدارة المقبوضات والمدفوعات (نقدي + بنكي) مع حماية الرصيد</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🧾 سند قبض",
        "📤 سند صرف",
        "📋 سجل السندات",
        "🔗 ربط السندات بالفواتير"
    ])

    # ============================================================
    # تبويب 1: سند قبض
    # ============================================================
    with tab1:
        _render_voucher_form('receipt')

    # ============================================================
    # تبويب 2: سند صرف
    # ============================================================
    with tab2:
        _render_voucher_form('payment')

    # ============================================================
    # تبويب 3: سجل السندات
    # ============================================================
    with tab3:
        st.markdown(f"<h3 style='color:{PR};'>سجل السندات</h3>",
                    unsafe_allow_html=True)
        vouchers = get_vouchers()
        if vouchers:
            df = pd.DataFrame(vouchers)
            df['linked_amount'] = df['linked_amount'].fillna(0).astype(float)
            df['unlinked'] = df['amount'].astype(float) - df['linked_amount']
            df['ربط'] = df.apply(
                lambda r: "✅ مربوط بالكامل" if r['unlinked'] < 0.01
                else ("🟡 مربوط جزئياً" if r['linked_amount'] > 0.01
                      else "🔴 غير مربوط"),
                axis=1
            )

            df_display = pd.DataFrame({
                'الرقم': df['id'],
                'النوع': df['type'].apply(lambda x: 'قبض' if x == 'receipt' else 'صرف'),
                'التاريخ': df['date'],
                'الطرف': df['party_name'],
                'المبلغ': df['amount'],
                'المربوط': df['linked_amount'],
                'غير المربوط': df['unlinked'],
                'الحالة': df['ربط'],
                'المرجع': df['reference']
            })
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            voucher_ids = [v['id'] for v in vouchers]
            selected_vid = st.selectbox("اختر سند لعرض التفاصيل",
                                         voucher_ids, key="voucher_details_sel")

            if selected_vid:
                details = get_voucher_details(selected_vid)
                if details:
                    st.markdown("### 📄 تفاصيل السند")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("الرقم", details['id'])
                    c2.metric("النوع",
                              "قبض" if details['type'] == 'receipt' else "صرف")
                    c3.metric("المبلغ", f"{float(details['amount']):,.2f}")
                    c4.metric("المربوط", f"{float(details.get('linked_amount', 0)):,.2f}")

                    st.markdown(f"**الطرف:** {details.get('party_name', '—')}")
                    st.markdown(f"**التاريخ:** {details.get('date', '—')}")
                    st.markdown(f"**حساب الدفع:** {details.get('account', '—')}")

                    if details.get("lines"):
                        st.markdown("### 📊 القيد المحاسبي")
                        df_lines = pd.DataFrame(details["lines"])
                        st.dataframe(df_lines, use_container_width=True,
                                     hide_index=True)

                    if details.get("linked_payments"):
                        st.markdown("### 🔗 الدفعات المرتبطة بفواتير")
                        df_pay = pd.DataFrame(details["linked_payments"])
                        cols = ['id', 'invoice_id', 'amount', 'payment_date',
                                'payment_method', 'notes']
                        cols = [c for c in cols if c in df_pay.columns]
                        st.dataframe(df_pay[cols], use_container_width=True,
                                     hide_index=True)
                    else:
                        st.info("🔴 هذا السند غير مربوط بأي فاتورة بعد.")
        else:
            st.info("لا توجد سندات بعد")

    # ============================================================
    # تبويب 4: ربط السندات بالفواتير
    # ============================================================
    with tab4:
        st.markdown(f"<h3 style='color:{BL};'>🔗 ربط السندات اليدوية بالفواتير</h3>",
                    unsafe_allow_html=True)
        st.caption("استخدم هذا التبويب لربط السندات التي أُنشئت بدون فاتورة، أو لتعديل الربط وإلغائه.")

        party_kind = st.radio(
            "نوع الطرف",
            ["عميل", "مورد"],
            horizontal=True,
            key="link_party_kind"
        )
        party_type = 'customer' if party_kind == "عميل" else 'supplier'

        if party_type == 'customer':
            parties = get_customers_with_balances()
        else:
            parties = get_suppliers_with_balances()

        if not parties:
            st.warning("لا يوجد أطراف")
            st.stop()

        party_options = {f"{p['name']} (رصيد: {p['balance']:,.2f})": p
                         for p in parties}
        selected_party_str = st.selectbox("اختر الطرف",
                                           list(party_options.keys()),
                                           key="link_party_sel")
        selected_party = party_options[selected_party_str]

        st.markdown("---")

        col_left, col_right = st.columns([1, 1])

        # ----- السندات غير المربوطة -----
        with col_left:
            st.markdown(f"<h4 style='color:{OR};'>📄 السندات غير المربوطة</h4>",
                        unsafe_allow_html=True)
            unlinked = get_unlinked_vouchers(
                party_type=party_type,
                party_id=selected_party['id']
            )
            if not unlinked:
                st.info("لا توجد سندات غير مربوطة لهذا الطرف")
                selected_voucher = None
            else:
                voucher_options = {}
                for v in unlinked:
                    unlinked_amt = float(v['amount']) - float(v.get('linked_amount', 0))
                    label = (f"#{v['id']} | {v['date']} | "
                             f"مبلغ: {float(v['amount']):,.2f} | "
                             f"متبقي: {unlinked_amt:,.2f}")
                    voucher_options[label] = v

                selected_voucher_str = st.selectbox(
                    "اختر سنداً",
                    list(voucher_options.keys()),
                    key="link_voucher_sel"
                )
                selected_voucher = voucher_options[selected_voucher_str]

        # ----- الفواتير المعلقة -----
        with col_right:
            st.markdown(f"<h4 style='color:{GR};'>📋 الفواتير المعلقة</h4>",
                        unsafe_allow_html=True)
            pending_invoices = get_party_invoices_with_status(
                party_type, selected_party['id'], only_pending=True
            )
            if not pending_invoices:
                st.info("لا توجد فواتير معلقة لهذا الطرف")
                selected_invoice = None
            else:
                inv_options = {}
                for inv in pending_invoices:
                    remaining = _get_value(inv, 'remaining_amount', 'remaining')
                    inv_date = _get_value(inv, 'invoice_date', 'date')
                    total = _get_value(inv, 'total')
                    label = (f"#{inv['id']} | {inv_date} | "
                             f"إجمالي: {float(total):,.2f} | "
                             f"متبقي: {float(remaining):,.2f}")
                    inv_options[label] = inv

                selected_inv_str2 = st.selectbox(
                    "اختر فاتورة",
                    list(inv_options.keys()),
                    key="link_invoice_sel"
                )
                selected_invoice = inv_options[selected_inv_str2]

        # ----- نموذج الربط -----
        st.markdown("---")
        if selected_voucher and selected_invoice:
            st.markdown(f"<h4 style='color:{BL};'>🔗 عملية الربط</h4>",
                        unsafe_allow_html=True)

            v_remaining = float(selected_voucher['amount']) - float(
                selected_voucher.get('linked_amount', 0)
            )
            i_remaining = float(_get_value(selected_invoice, 'remaining_amount', 'remaining'))
            max_linkable = min(v_remaining, i_remaining)

            c1, c2, c3 = st.columns(3)
            c1.metric("المتبقي من السند", f"{v_remaining:,.2f}")
            c2.metric("المتبقي على الفاتورة", f"{i_remaining:,.2f}")
            c3.metric("أقصى مبلغ للربط", f"{max_linkable:,.2f}")

            if max_linkable > 0:
                link_amount = st.number_input(
                    "المبلغ المراد ربطه",
                    min_value=0.01,
                    max_value=float(max_linkable),
                    value=float(max_linkable),
                    step=0.01,
                    key="link_amount_input"
                )

                if st.button("🔗 ربط السند بالفاتورة", type="primary", key="do_link_btn"):
                    ok, err = link_voucher_to_invoice(
                        voucher_id=selected_voucher['id'],
                        invoice_id=selected_invoice['id'],
                        amount=link_amount
                    )
                    if ok:
                        st.success(
                            f"✅ تم ربط {link_amount:,.2f} من السند "
                            f"#{selected_voucher['id']} بالفاتورة "
                            f"#{selected_invoice['id']}"
                        )
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")
            else:
                st.warning("⚠️ لا يمكن الربط — أحد الطرفين بلا رصيد متبقٍ.")
        else:
            st.info("اختر سنداً وفاتورة لعرض خيارات الربط")

        # ----- إلغاء الربط -----
        st.markdown("---")
        st.markdown(f"<h4 style='color:{RD};'>🗑️ إلغاء ربط سابق</h4>",
                    unsafe_allow_html=True)
        st.caption("لتصحيح الأخطاء: اختر سنداً لعرض دفعاته المرتبطة وحذف أي منها.")

        party_vouchers = get_vouchers_by_party(party_type, selected_party['id'])
        if party_vouchers:
            voucher_opts2 = {}
            for v in party_vouchers:
                linked_amt = float(v.get('linked_amount', 0))
                if linked_amt > 0.01:
                    label = (f"#{v['id']} | {v['date']} | "
                             f"مبلغ: {float(v['amount']):,.2f} | "
                             f"مربوط: {linked_amt:,.2f}")
                    voucher_opts2[label] = v

            if not voucher_opts2:
                st.info("لا توجد سندات مربوطة لهذا الطرف")
            else:
                sel_v_str = st.selectbox(
                    "اختر سنداً مربوطاً",
                    list(voucher_opts2.keys()),
                    key="unlink_voucher_sel"
                )
                sel_v = voucher_opts2[sel_v_str]

                details = get_voucher_details(sel_v['id'])
                linked = details.get('linked_payments', [])

                if linked:
                    df_linked = pd.DataFrame(linked)
                    display_cols = ['id', 'invoice_id', 'amount',
                                    'payment_date', 'payment_method']
                    display_cols = [c for c in display_cols
                                    if c in df_linked.columns]
                    st.dataframe(df_linked[display_cols],
                                 use_container_width=True, hide_index=True)

                    payment_opts = {
                        f"دفعة #{p['id']} - فاتورة #{p['invoice_id']} - "
                        f"{float(p['amount']):,.2f}": p
                        for p in linked
                    }
                    sel_pay_str = st.selectbox(
                        "اختر الدفعة لإلغاء ربطها",
                        list(payment_opts.keys()),
                        key="unlink_payment_sel"
                    )
                    sel_pay = payment_opts[sel_pay_str]

                    if st.button("🗑️ إلغاء الربط", key="do_unlink_btn"):
                        ok, err = unlink_voucher_from_invoice(sel_pay['id'])
                        if ok:
                            st.success(
                                f"✅ تم إلغاء ربط الدفعة #{sel_pay['id']}"
                            )
                            st.rerun()
                        else:
                            st.error(f"❌ {err}")
                else:
                    st.info("لا توجد دفعات مرتبطة بهذا السند")
        else:
            st.info("لا توجد سندات لهذا الطرف")
