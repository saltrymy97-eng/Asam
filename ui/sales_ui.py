# ui/sales_ui.py – واجهة المبيعات (v6.0)
# ✅ إصلاح StreamlitWidgetAlreadyInstantiatedError
# ✅ لا نُعدّل key الـ widget مباشرة
import streamlit as st
import pandas as pd
from services.sales_service import (
    get_customers,
    get_products_for_sale,
    create_sale_invoice,
    get_sale_invoices,
    get_invoice_details,
    add_customer,
    get_all_customers,
    create_receipt_voucher_for_invoice,
)
from services.currency_service import get_all_currencies, get_base_currency
from services.cash_service import get_all_cash_accounts


# ========== ألوان التصميم ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"


PAYMENT_STATUS_LABELS = {
    "unpaid":  "🔴 غير مدفوعة",
    "partial": "🟡 مدفوعة جزئياً",
    "paid":    "🟢 مدفوعة بالكامل"
}

PAYMENT_METHOD_LABELS = {
    "cash":   "نقدي",
    "bank":   "بنكي",
    "credit": "آجل",
    "mixed":  "مختلط"
}


# ============================================================
# ✅ مساعد: قراءة مبلغ رقمي من حقل نصي
# ============================================================
def _read_amount_from_text(text_value, default=0.0, max_value=None):
    """تحويل نص إلى رقم بأمان."""
    if text_value is None:
        return default
    text = str(text_value).strip().replace(",", "").replace(" ", "")
    if text == "":
        return default
    try:
        value = float(text)
    except (ValueError, TypeError):
        return default
    if value < 0:
        return default
    if max_value is not None and value > max_value:
        return max_value
    return value


def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🛒 إدارة المبيعات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إنشاء فواتير البيع وإدارة العملاء</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 إنشاء فاتورة", "📋 فواتير المبيعات", "👥 العملاء"])

    # ============================================================
    # التبويب 1: إنشاء فاتورة
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>إنشاء فاتورة مبيعات جديدة</h3>",
                    unsafe_allow_html=True)

        # 1) العملاء
        customers = get_customers()
        if not customers:
            st.warning("لا يوجد عملاء. أضف عميلاً من تبويب 'العملاء' أولاً.")
            customer_id = None
        else:
            customer_names = [c['name'] for c in customers]
            selected_customer = st.selectbox("اختر العميل", customer_names)
            customer_id = next(c['id'] for c in customers if c['name'] == selected_customer)

        # 2) العملة
        currencies = get_all_currencies()
        base_currency = get_base_currency()
        currency_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
        default_currency = base_currency['code'] if base_currency else 'YER'
        default_label = next(
            (k for k, v in currency_options.items() if v == default_currency),
            list(currency_options.keys())[0]
        )
        selected_currency_label = st.selectbox(
            "💱 العملة",
            list(currency_options.keys()),
            index=list(currency_options.keys()).index(default_label)
        )
        currency_code = currency_options[selected_currency_label]

        # 3) المنتجات
        products = get_products_for_sale()
        if not products:
            st.warning("لا توجد منتجات متاحة للبيع.")
            return

        if 'invoice_items' not in st.session_state:
            st.session_state.invoice_items = []

        col1, col2, col3 = st.columns(3)
        with col1:
            selected_product = st.selectbox("اختر المنتج",
                                            [p['name'] for p in products],
                                            key="prod_sel")
        with col2:
            qty = st.number_input("الكمية", min_value=1, step=1, key="qty_sel")
        with col3:
            if st.button("➕ أضف إلى الفاتورة", use_container_width=True):
                product = next(p for p in products if p['name'] == selected_product)
                if qty > product['quantity']:
                    st.error(f"المخزون غير كافٍ. المتاح: {product['quantity']}")
                else:
                    item = {
                        "product_id": product['id'],
                        "name": product['name'],
                        "quantity": qty,
                        "unit_price": product['selling_price'],
                        "total": qty * product['selling_price']
                    }
                    st.session_state.invoice_items.append(item)
                    st.success(f"تمت إضافة {selected_product}")
                    st.rerun()

        # 4) عرض البنود + قسم الدفع
        if st.session_state.invoice_items:
            st.markdown("---")
            st.subheader("بنود الفاتورة")
            items_df = pd.DataFrame(st.session_state.invoice_items)
            st.dataframe(
                items_df[["name", "quantity", "unit_price", "total"]],
                use_container_width=True,
                hide_index=True
            )
            total_invoice = float(sum(item["total"] for item in st.session_state.invoice_items))
            st.markdown(f"### الإجمالي: {total_invoice:,.2f} {currency_code}")

            st.markdown("---")
            st.markdown(f"<h4 style='color:{ACCENT_GREEN};'>💰 تفاصيل الدفع</h4>",
                        unsafe_allow_html=True)

            payment_options = {
                "نقدي (دفع كامل الآن)": "cash",
                "آجل (بدون دفع الآن)": "credit",
                "جزئي (دفعة + متبقي)": "partial"
            }
            selected_payment_label = st.radio(
                "طريقة الدفع",
                list(payment_options.keys()),
                horizontal=True,
                key="payment_method_radio"
            )
            payment_choice = payment_options[selected_payment_label]

            cash_account = None
            paid_amount = 0.0

            if payment_choice in ('cash', 'partial'):
                cash_accounts = get_all_cash_accounts(active_only=True)
                if not cash_accounts:
                    st.error("⚠️ لا يوجد صندوق أو حساب بنكي. أضف صندوقاً من وحدة الصندوق أولاً.")
                    return

                cash_labels = [
                    f"{ca['name']} ({ca['currency_code']}) - الرصيد: {ca['current_balance']:,.2f}"
                    for ca in cash_accounts
                ]
                selected_cash_label = st.selectbox(
                    "💵 من أي صندوق/بنك تم استلام المبلغ؟",
                    cash_labels,
                    key="cash_acc_sel"
                )
                cash_idx = cash_labels.index(selected_cash_label)
                cash_account = cash_accounts[cash_idx]['account_code']

                if payment_choice == 'cash':
                    paid_amount = total_invoice
                    st.info(f"💵 سيتم استلام {total_invoice:,.2f} {currency_code} نقداً")

                else:  # partial
                    st.markdown(f"**💵 المبلغ المدفوع الآن (من إجمالي {total_invoice:,.2f} {currency_code})**")

                    # ✅ on_change callback — يُنفّذ مع كل ضغطة
                    def _on_paid_change():
                        txt = st.session_state.get("paid_amount_text", "")
                        val = _read_amount_from_text(txt, 0.0, total_invoice)
                        st.session_state["paid_amount_final"] = val

                    st.text_input(
                        "اكتب المبلغ",
                        placeholder="0.00",
                        key="paid_amount_text",
                        label_visibility="collapsed",
                        on_change=_on_paid_change
                    )

                    # ✅ قراءة من القيمة المخزّنة
                    paid_amount = st.session_state.get("paid_amount_final", 0.0)

                    remaining = total_invoice - paid_amount
                    st.markdown(
                        f"<div style='padding:0.75rem; background:rgba(245,158,11,0.15); "
                        f"border-radius:8px; margin-top:0.5rem;'>"
                        f"💵 مدفوع: <b>{paid_amount:,.2f}</b> {currency_code} | "
                        f"🔴 متبقي: <b>{remaining:,.2f}</b> {currency_code}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info(f"📌 سيتم تسجيل المبلغ كاملاً ({total_invoice:,.2f} {currency_code}) على حساب العميل")

            # 5) زر الحفظ
            if "saving_sale" not in st.session_state:
                st.session_state.saving_sale = False

            save_disabled = st.session_state.saving_sale or customer_id is None

            if st.button("💾 حفظ الفاتورة", type="primary",
                        disabled=save_disabled, key="save_sales_btn"):
                # ✅ قراءة القيمة النهائية من session_state
                if payment_choice == 'cash':
                    final_paid = total_invoice
                elif payment_choice == 'credit':
                    final_paid = 0.0
                else:  # partial — نقرأ من final
                    final_paid = st.session_state.get("paid_amount_final", 0.0)

                st.session_state.final_paid_to_save = final_paid
                st.session_state.saving_sale = True
                st.rerun()

            if st.session_state.saving_sale:
                try:
                    actual_paid = st.session_state.get("final_paid_to_save", 0.0)

                    invoice_id, total, error = create_sale_invoice(
                        customer_id=customer_id,
                        items=st.session_state.invoice_items,
                        username=st.session_state.user.get('username', 'admin'),
                        currency_code=currency_code,
                        paid_amount=actual_paid,
                        payment_method=(
                            'cash' if payment_choice == 'cash'
                            else 'credit' if payment_choice == 'credit'
                            else 'mixed'
                        ),
                        cash_account=cash_account
                    )

                    if error and invoice_id is None:
                        st.error(f"❌ فشل في حفظ الفاتورة: {error}")

                    elif error and invoice_id is not None:
                        st.warning(
                            f"⚠️ **تم حفظ الفاتورة رقم {invoice_id} بنجاح** "
                            f"لكن **لم يُنشأ سند القبض التلقائي**.\n\n"
                            f"**السبب:** {error}\n\n"
                            f"👉 اذهب لتبويب **'فواتير المبيعات'** واضغط **'إنشاء السند يدوياً'**."
                        )
                        st.session_state.invoice_items = []

                    else:
                        st.success(
                            f"✅ تم حفظ الفاتورة رقم {invoice_id} بنجاح "
                            f"— المدفوع: {actual_paid:,.2f} {currency_code}"
                        )
                        st.session_state.invoice_items = []
                        st.session_state.paid_amount_final = 0.0

                except Exception as e:
                    st.error(f"❌ خطأ غير متوقع: {e}")
                finally:
                    st.session_state.saving_sale = False
                    st.rerun()

            # ✅ زر مسح — بدون لمس key الـ widget
            if st.button("🗑️ مسح جميع البنود"):
                st.session_state.invoice_items = []
                st.session_state.paid_amount_final = 0.0
                st.rerun()

    # ============================================================
    # التبويب 2: فواتير المبيعات
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>فواتير المبيعات المسجلة</h3>",
                    unsafe_allow_html=True)

        all_invoices = get_sale_invoices()

        invoices_with_warnings = [inv for inv in all_invoices if inv.get('has_warning')]
        if invoices_with_warnings:
            st.error(
                f"⚠️ يوجد **{len(invoices_with_warnings)}** فاتورة "
                f"لم يُنشأ لها سند قبض تلقائي. راجعها أدناه."
            )

        if all_invoices:
            df_invoices = pd.DataFrame(all_invoices)
            display_cols = ["id", "customer", "invoice_date", "total",
                            "paid_amount", "remaining_amount", "payment_status"]
            display_cols = [c for c in display_cols if c in df_invoices.columns]

            df_display = df_invoices[display_cols].copy()
            if "payment_status" in df_display.columns:
                df_display["payment_status"] = df_display["payment_status"].map(
                    PAYMENT_STATUS_LABELS
                ).fillna(df_display["payment_status"])

            if "has_warning" in df_invoices.columns:
                df_display["⚠️"] = df_invoices["has_warning"].apply(
                    lambda x: "⚠️" if x else "✅"
                )

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            invoice_ids = [inv['id'] for inv in all_invoices]
            selected_id = st.selectbox("اختر فاتورة لعرض تفاصيلها",
                                        invoice_ids, key="sale_inv_sel")
            if selected_id:
                details = get_invoice_details(selected_id)
                if details:
                    df_details = pd.DataFrame(details)
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    total = sum(d['total'] for d in details)
                    st.markdown(f"**إجمالي الفاتورة: {total:,.2f}**")

                inv_sel = next((i for i in all_invoices if i['id'] == selected_id), None)
                if inv_sel:
                    st.markdown("### حالة الدفع")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("الإجمالي", f"{float(inv_sel['total']):,.2f}")
                    c2.metric("المدفوع", f"{float(inv_sel.get('paid_amount', 0)):,.2f}")
                    c3.metric("المتبقي", f"{float(inv_sel.get('remaining_amount', 0)):,.2f}")

                    st.markdown(
                        f"**حالة الدفع:** {PAYMENT_STATUS_LABELS.get(inv_sel.get('payment_status'), '—')} "
                        f"| **طريقة الدفع:** {PAYMENT_METHOD_LABELS.get(inv_sel.get('payment_method'), '—')}"
                    )

                    if inv_sel.get('has_warning'):
                        st.warning(f"⚠️ **تنبيه:** {inv_sel.get('reference', '')}")

                        if float(inv_sel.get('paid_amount', 0)) > 0:
                            if st.button(
                                f"🔧 إنشاء سند القبض يدوياً للفاتورة #{selected_id}",
                                type="primary",
                                key=f"create_receipt_btn_{selected_id}"
                            ):
                                with st.spinner("جاري إنشاء سند القبض..."):
                                    vid, verr = create_receipt_voucher_for_invoice(
                                        invoice_id=selected_id,
                                        username=st.session_state.user.get('username', 'admin')
                                    )
                                    if verr:
                                        st.error(f"❌ فشل: {verr}")
                                    else:
                                        st.success(f"✅ تم إنشاء سند القبض رقم {vid}")
                                        st.rerun()
        else:
            st.info("لا توجد فواتير مبيعات بعد")

    # ============================================================
    # التبويب 3: العملاء
    # ============================================================
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>إدارة العملاء</h3>",
                    unsafe_allow_html=True)

        st.markdown("### إضافة عميل جديد")
        with st.form("add_customer"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم العميل")
            phone = col2.text_input("رقم الهاتف")
            address = st.text_input("العنوان")
            if st.form_submit_button("➕ إضافة عميل"):
                if name:
                    add_customer(name, phone, address,
                                 st.session_state.user.get('username', 'admin'))
                    st.success(f"تمت إضافة العميل '{name}'")
                    st.rerun()
                else:
                    st.error("اسم العميل مطلوب")

        st.markdown("---")
        st.subheader("العملاء الحاليين")
        customers = get_all_customers()
        if customers:
            st.dataframe(pd.DataFrame(customers), use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد عملاء بعد")
