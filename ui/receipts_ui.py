# ui/receipts_ui.py – واجهة سندات القبض والصرف (تصميم زجاجي فاخر)
# v2.0 — إضافة تبويب ربط السندات اليدوية بالفواتير + إلغاء الربط
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
    get_voucher_details,
    # ✅ دوال جديدة
    link_voucher_to_invoice,
    unlink_voucher_from_invoice,
    get_unlinked_vouchers,
    get_vouchers_by_party,
    get_party_invoices_with_status,
    get_voucher_linked_amount,
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


def show():
    create_vouchers_table()

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">💵 سندات القبض والصرف</h1>
        <p style="color:{S}; font-size:1.2rem;">إدارة المقبوضات والمدفوعات النقدية وربطها بالفواتير</p>
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
        st.markdown(f"<h3 style='color:{GR};'>إنشاء سند قبض (استلام نقدية)</h3>",
                    unsafe_allow_html=True)

        cash_accounts = get_cash_accounts()
        cash_options = [f"{a['code']} - {a['name']}" for a in cash_accounts]

        customers = get_customers_with_balances()
        if not customers:
            st.warning("لا يوجد عملاء")
        else:
            customer_options = {f"{c['name']} (الرصيد: {c['balance']:,.2f})": c
                                for c in customers}
            selected_cust_str = st.selectbox("اختر العميل",
                                              list(customer_options.keys()),
                                              key="receipt_cust")
            selected_cust = customer_options[selected_cust_str]

            invoices = get_invoices_for_party('customer', selected_cust['id'])
            invoice_options = {"بدون فاتورة (دفعة عامة)": None}
            for inv in invoices:
                label = f"فاتورة #{inv['id']} - المتبقي: {inv['remaining']:,.2f}"
                invoice_options[label] = inv

            selected_inv_str = st.selectbox("ربط بفاتورة (اختياري)",
                                             list(invoice_options.keys()),
                                             key="receipt_inv")
            selected_inv = invoice_options[selected_inv_str]

            default_amount = selected_inv['remaining'] if selected_inv else 0.0
            amount = st.number_input("المبلغ", min_value=0.0,
                                      value=float(default_amount),
                                      step=0.01, key="receipt_amount")

            col1, col2 = st.columns(2)
            with col1:
                voucher_date = st.date_input("التاريخ", value=date.today(),
                                              key="receipt_date")
            with col2:
                cash_selected = st.selectbox("حساب النقدية", cash_options,
                                              key="receipt_cash")

            reference = st.text_input("المرجع (اختياري)", key="receipt_ref")
            notes = st.text_area("ملاحظات", key="receipt_notes")

            if "saving_receipt" not in st.session_state:
                st.session_state.saving_receipt = False

            if st.button("💾 حفظ سند القبض", type="primary",
                        key="save_receipt",
                        disabled=st.session_state.saving_receipt):
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

    # ============================================================
    # تبويب 2: سند صرف
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{RD};'>إنشاء سند صرف (دفع نقدية)</h3>",
                    unsafe_allow_html=True)

        cash_accounts = get_cash_accounts()
        cash_options = [f"{a['code']} - {a['name']}" for a in cash_accounts]

        suppliers = get_suppliers_with_balances()
        if not suppliers:
            st.warning("لا يوجد موردين")
        else:
            supplier_options = {f"{s['name']} (الرصيد: {s['balance']:,.2f})": s
                                for s in suppliers}
            selected_sup_str = st.selectbox("اختر المورد",
                                             list(supplier_options.keys()),
                                             key="payment_sup")
            selected_sup = supplier_options[selected_sup_str]

            invoices = get_invoices_for_party('supplier', selected_sup['id'])
            invoice_options = {"بدون فاتورة (دفعة عامة)": None}
            for inv in invoices:
                label = f"فاتورة #{inv['id']} - المتبقي: {inv['remaining']:,.2f}"
                invoice_options[label] = inv

            selected_inv_str = st.selectbox("ربط بفاتورة (اختياري)",
                                             list(invoice_options.keys()),
                                             key="payment_inv")
            selected_inv = invoice_options[selected_inv_str]

            default_amount = selected_inv['remaining'] if selected_inv else 0.0
            amount = st.number_input("المبلغ", min_value=0.0,
                                      value=float(default_amount),
                                      step=0.01, key="payment_amount")

            col1, col2 = st.columns(2)
            with col1:
                voucher_date = st.date_input("التاريخ", value=date.today(),
                                              key="payment_date")
            with col2:
                cash_selected = st.selectbox("حساب النقدية", cash_options,
                                              key="payment_cash")

            reference = st.text_input("المرجع (اختياري)", key="payment_ref")
            notes = st.text_area("ملاحظات", key="payment_notes")

            if "saving_payment" not in st.session_state:
                st.session_state.saving_payment = False

            if st.button("💾 حفظ سند الصرف", type="primary",
                        key="save_payment",
                        disabled=st.session_state.saving_payment):
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

    # ============================================================
    # تبويب 3: سجل السندات
    # ============================================================
    with tab3:
        st.markdown(f"<h3 style='color:{PR};'>سجل السندات</h3>", unsafe_allow_html=True)
        vouchers = get_vouchers()
        if vouchers:
            df = pd.DataFrame(vouchers)

            # ✅ إضافة حالة الربط
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
                    # ✅ عرض منظم بدل JSON
                    st.markdown("### 📄 تفاصيل السند")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("الرقم", details['id'])
                    c2.metric("النوع",
                              "قبض" if details['type'] == 'receipt' else "صرف")
                    c3.metric("المبلغ", f"{float(details['amount']):,.2f}")
                    c4.metric("المربوط", f"{float(details.get('linked_amount', 0)):,.2f}")

                    st.markdown(f"**الطرف:** {details.get('party_name', '—')}")
                    st.markdown(f"**التاريخ:** {details.get('date', '—')}")
                    st.markdown(f"**حساب النقدية:** {details.get('account', '—')}")

                    # القيد المحاسبي
                    if details.get("lines"):
                        st.markdown("### 📊 القيد المحاسبي")
                        df_lines = pd.DataFrame(details["lines"])
                        st.dataframe(df_lines, use_container_width=True,
                                     hide_index=True)

                    # الدفعات المرتبطة
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
    # تبويب 4: ربط السندات بالفواتير (✅ جديد)
    # ============================================================
    with tab4:
        st.markdown(f"<h3 style='color:{BL};'>🔗 ربط السندات اليدوية بالفواتير</h3>",
                    unsafe_allow_html=True)
        st.caption("استخدم هذا التبويب لربط السندات التي أُنشئت بدون فاتورة، أو لتعديل الربط وإلغائه.")

        # ----- 4.1 اختيار الطرف -----
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

        # ----- 4.2 السندات غير المربوطة -----
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

        # ----- 4.3 الفواتير المعلقة -----
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
                    label = (f"#{inv['id']} | {inv['invoice_date']} | "
                             f"إجمالي: {float(inv['total']):,.2f} | "
                             f"متبقي: {float(inv['remaining_amount']):,.2f}")
                    inv_options[label] = inv

                selected_inv_str2 = st.selectbox(
                    "اختر فاتورة",
                    list(inv_options.keys()),
                    key="link_invoice_sel"
                )
                selected_invoice = inv_options[selected_inv_str2]

        # ----- 4.4 نموذج الربط -----
        st.markdown("---")
        if selected_voucher and selected_invoice:
            st.markdown(f"<h4 style='color:{BL};'>🔗 عملية الربط</h4>",
                        unsafe_allow_html=True)

            v_remaining = float(selected_voucher['amount']) - float(
                selected_voucher.get('linked_amount', 0)
            )
            i_remaining = float(selected_invoice['remaining_amount'])
            max_linkable = min(v_remaining, i_remaining)

            c1, c2, c3 = st.columns(3)
            c1.metric("المتبقي من السند", f"{v_remaining:,.2f}")
            c2.metric("المتبقي على الفاتورة", f"{i_remaining:,.2f}")
            c3.metric("أقصى مبلغ للربط", f"{max_linkable:,.2f}")

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
            st.info("اختر سنداً وفاتورة لعرض خيارات الربط")

        # ----- 4.5 إلغاء الربط -----
        st.markdown("---")
        st.markdown(f"<h4 style='color:{RD};'>🗑️ إلغاء ربط سابق</h4>",
                    unsafe_allow_html=True)
        st.caption("لتصحيح الأخطاء: اختر سنداً لعرض دفعاته المرتبطة وحذف أي منها.")

        # عرض سندات الطرف (جميعها) لإلغاء الربط
        party_vouchers = get_vouchers_by_party(party_type, selected_party['id'])
        if party_vouchers:
            voucher_opts2 = {}
            for v in party_vouchers:
                linked_amt = float(v.get('linked_amount', 0))
                if linked_amt > 0.01:  # فقط السندات المربوطة
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

                    # اختيار الدفعة للإلغاء
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
