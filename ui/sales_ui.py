# ui/sales_ui.py – واجهة المبيعات (تصميم زجاجي فخم + دعم العملات + دورة الدفع الكاملة)
# v2.0 — دعم: بيع نقدي / آجل / جزئي
import streamlit as st
import pandas as pd
from services.sales_service import (
    get_customers,
    get_products_for_sale,
    create_sale_invoice,
    get_sale_invoices,
    get_invoice_details,
    add_customer,
    get_all_customers
)
from services.currency_service import get_all_currencies, get_base_currency
from services.cash_service import get_all_cash_accounts


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


# ========== خريطة عرض حالة الدفع ==========
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

            # ✅ اختيار طريقة الدفع
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

            # ✅ إذا نقدي أو جزئي: نحتاج الصندوق/البنك
            cash_account = None
            paid_amount = 0.0

            if payment_choice in ('cash', 'partial'):
                # جلب الصناديق
                cash_accounts = get_all_cash_accounts(active_only=True)
                if not cash_accounts:
                    st.error("⚠️ لا يوجد صندوق أو حساب بنكي. أضف صندوقاً من وحدة الصندوق أولاً.")
                    return

                # اختيار الصندوق
                cash_labels = [f"{ca['name']} ({ca['currency_code']}) - الرصيد: {ca['current_balance']:,.2f}"
                               for ca in cash_accounts]
                selected_cash_label = st.selectbox(
                    "💵 من أي صندوق/بنك تم استلام المبلغ؟",
                    cash_labels,
                    key="cash_acc_sel"
                )
                cash_idx = cash_labels.index(selected_cash_label)
                cash_account = cash_accounts[cash_idx]['account_code']

                # إذا نقدي كامل: paid = total
                if payment_choice == 'cash':
                    paid_amount = total_invoice
                    st.info(f"💵 سيتم استلام {total_invoice:,.2f} {currency_code} نقداً")

                # إذا جزئي: حقل المبلغ المدفوع
                else:  # partial
                    paid_amount = st.number_input(
                        f"💵 المبلغ المدفوع الآن (من إجمالي {total_invoice:,.2f})",
                        min_value=0.0,
                        max_value=total_invoice,
                        value=round(total_invoice / 2, 2),
                        step=10.0,
                        key="paid_amount_input"
                    )
                    remaining = total_invoice - paid_amount
                    st.markdown(
                        f"<div style='padding:0.75rem; background:rgba(245,158,11,0.15); "
                        f"border-radius:8px; margin-top:0.5rem;'>"
                        f"💵 مدفوع: <b>{paid_amount:,.2f}</b> {currency_code} | "
                        f"🔴 متبقي: <b>{remaining:,.2f}</b> {currency_code}"
                        f"</div>",
                        unsafe_allow_html=True
                    )

            else:  # credit (آجل كامل)
                st.info(f"📌 سيتم تسجيل المبلغ كاملاً ({total_invoice:,.2f} {currency_code}) على حساب العميل")

            # 5) زر الحفظ
            if "saving_sale" not in st.session_state:
                st.session_state.saving_sale = False

            save_disabled = st.session_state.saving_sale or customer_id is None

            if st.button("💾 حفظ الفاتورة", type="primary",
                        disabled=save_disabled, key="save_sales_btn"):
                st.session_state.saving_sale = True
                st.rerun()

            # تنفيذ الحفظ
            if st.session_state.saving_sale:
                try:
                    # ✅ تمرير معاملات الدفع للـ service
                    invoice_id, total, error = create_sale_invoice(
                        customer_id=customer_id,
                        items=st.session_state.invoice_items,
                        username=st.session_state.user.get('username', 'admin'),
                        currency_code=currency_code,
                        paid_amount=paid_amount,               # ← جديد
                        payment_method=(
                            'cash' if payment_choice == 'cash'
                            else 'credit' if payment_choice == 'credit'
                            else 'mixed'
                        ),                                      # ← جديد
                        cash_account=cash_account               # ← جديد
                    )
                    if error:
                        st.error(f"فشل في حفظ الفاتورة: {error}")
                    else:
                        st.success(f"✅ تم حفظ الفاتورة رقم {invoice_id} بنجاح")
                        st.session_state.invoice_items = []
                finally:
                    st.session_state.saving_sale = False
                    st.rerun()

            if st.button("🗑️ مسح جميع البنود"):
                st.session_state.invoice_items = []
                st.rerun()

    # ============================================================
    # التبويب 2: فواتير المبيعات
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>فواتير المبيعات المسجلة</h3>",
                    unsafe_allow_html=True)
        invoices = get_sale_invoices()
        if invoices:
            # ✅ تجهيز عرض مُحسّن مع حالة الدفع
            df_invoices = pd.DataFrame(invoices)
            display_cols = ["id", "customer", "invoice_date", "total",
                            "paid_amount", "remaining_amount", "payment_status"]
            display_cols = [c for c in display_cols if c in df_invoices.columns]

            df_display = df_invoices[display_cols].copy()
            if "payment_status" in df_display.columns:
                df_display["payment_status"] = df_display["payment_status"].map(
                    PAYMENT_STATUS_LABELS
                ).fillna(df_display["payment_status"])

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # تفاصيل فاتورة
            invoice_ids = [inv['id'] for inv in invoices]
            selected_id = st.selectbox("اختر فاتورة لعرض تفاصيلها", invoice_ids)
            if selected_id:
                details = get_invoice_details(selected_id)
                if details:
                    df_details = pd.DataFrame(details)
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    total = sum(d['total'] for d in details)
                    st.markdown(f"**إجمالي الفاتورة: {total:,.2f}**")

                # ✅ عرض حالة الدفع للفاتورة المختارة
                inv_sel = next((i for i in invoices if i['id'] == selected_id), None)
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
