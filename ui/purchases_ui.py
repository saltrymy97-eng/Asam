# ui/purchases_ui.py – واجهة المشتريات (v4.0)
# ✅ قراءة مباشرة من الحقل بدون Enter أو زر تأكيد
import streamlit as st
import pandas as pd
from services.purchases_service import (
    get_suppliers,
    get_products_for_purchase,
    create_purchase_invoice,
    get_purchase_invoices,
    get_invoice_details,
    add_supplier,
    get_all_suppliers,
    create_payment_voucher_for_invoice,
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
# ✅ مساعد: قراءة مبلغ رقمي من حقل نصي (يعمل على الهاتف)
# ============================================================
def _read_amount_from_text(text_value, default=0.0, max_value=None):
    """
    تحويل نص إلى رقم بأمان.
    - يقبل الأرقام والفاصلات.
    - إذا كان النص فارغاً → default.
    - إذا تجاوز max_value → يُقيّد.
    """
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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🚚 إدارة المشتريات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إنشاء فواتير الشراء وإدارة الموردين</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 إنشاء فاتورة", "📋 فواتير المشتريات", "👥 الموردين"])

    # ============================================================
    # التبويب 1: إنشاء فاتورة
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>إنشاء فاتورة مشتريات جديدة</h3>",
                    unsafe_allow_html=True)

        suppliers = get_suppliers()
        if not suppliers:
            st.warning("لا يوجد موردون. أضف مورداً من تبويب 'الموردين' أولاً.")
            supplier_id = None
        else:
            supplier_names = [s['name'] for s in suppliers]
            selected_supplier = st.selectbox("اختر المورد", supplier_names)
            supplier_id = next(s['id'] for s in suppliers if s['name'] == selected_supplier)

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

        products = get_products_for_purchase()
        if not products:
            st.warning("لا توجد منتجات.")
            return

        if 'purchase_items' not in st.session_state:
            st.session_state.purchase_items = []

        col1, col2, col3 = st.columns(3)
        with col1:
            selected_product = st.selectbox("اختر المنتج",
                                            [p['name'] for p in products],
                                            key="pur_prod_sel")
        with col2:
            qty = st.number_input("الكمية", min_value=1, step=1, key="pur_qty_sel")
        with col3:
            default_price = next(p['purchase_price'] for p in products
                                 if p['name'] == selected_product)
            unit_price = st.number_input("سعر الشراء للوحدة",
                                          min_value=0.0, step=0.01,
                                          value=float(default_price or 0),
                                          key="pur_price_sel")

        if st.button("➕ أضف إلى الفاتورة"):
            product = next(p for p in products if p['name'] == selected_product)
            item = {
                "product_id": product['id'],
                "name": product['name'],
                "quantity": qty,
                "unit_price": unit_price,
                "total": qty * unit_price
            }
            st.session_state.purchase_items.append(item)
            st.success(f"تمت إضافة {selected_product}")
            st.rerun()

        if st.session_state.purchase_items:
            st.markdown("---")
            st.subheader("بنود الفاتورة")
            items_df = pd.DataFrame(st.session_state.purchase_items)
            st.dataframe(
                items_df[["name", "quantity", "unit_price", "total"]],
                use_container_width=True,
                hide_index=True
            )
            total_purchase = float(sum(item["total"] for item in st.session_state.purchase_items))
            st.markdown(f"### الإجمالي: {total_purchase:,.2f} {currency_code}")

            st.markdown("---")
            st.markdown(f"<h4 style='color:{ACCENT_ORANGE};'>💳 تفاصيل الدفع للمورد</h4>",
                        unsafe_allow_html=True)

            payment_options = {
                "نقدي (دفع كامل للمورد)": "cash",
                "آجل (لا دفع الآن)": "credit",
                "جزئي (دفعة + متبقي)": "partial"
            }
            selected_payment_label = st.radio(
                "طريقة الدفع للمورد",
                list(payment_options.keys()),
                horizontal=True,
                key="purchase_payment_method_radio"
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
                    "💵 من أي صندوق/بنك سيتم الدفع؟",
                    cash_labels,
                    key="purchase_cash_acc_sel"
                )
                cash_idx = cash_labels.index(selected_cash_label)
                cash_account = cash_accounts[cash_idx]['account_code']

                if payment_choice == 'cash':
                    paid_amount = total_purchase
                    st.info(f"💵 سيتم دفع {total_purchase:,.2f} {currency_code} للمورد فوراً")

                else:  # partial
                    # ✅ حقل نصي — لا قيمة افتراضية
                    st.markdown(f"**💵 المبلغ المدفوع الآن (من إجمالي {total_purchase:,.2f} {currency_code})**")
                    paid_text = st.text_input(
                        "اكتب المبلغ",
                        value="",
                        placeholder="0.00",
                        key="purchase_paid_amount_text",
                        label_visibility="collapsed"
                    )

                    # قراءة فورية للعرض
                    paid_amount = _read_amount_from_text(
                        paid_text,
                        default=0.0,
                        max_value=total_purchase
                    )

                    remaining = total_purchase - paid_amount
                    st.markdown(
                        f"<div style='padding:0.75rem; background:rgba(245,158,11,0.15); "
                        f"border-radius:8px; margin-top:0.5rem;'>"
                        f"💵 مدفوع للمورد: <b>{paid_amount:,.2f}</b> {currency_code} | "
                        f"🔴 متبقي: <b>{remaining:,.2f}</b> {currency_code}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info(f"📌 سيتم تسجيل المبلغ كاملاً ({total_purchase:,.2f} {currency_code}) على حساب المورد")

            # ============================================================
            # 5) زر الحفظ — قراءة مباشرة من الحقل
            # ============================================================
            if "saving_purchase" not in st.session_state:
                st.session_state.saving_purchase = False

            save_disabled = st.session_state.saving_purchase or supplier_id is None

            if st.button("💾 حفظ فاتورة المشتريات", type="primary",
                        disabled=save_disabled, key="save_purchase_btn"):
                # ✅ قراءة القيمة النهائية من session_state مباشرة
                if payment_choice == 'cash':
                    final_paid = total_purchase
                elif payment_choice == 'credit':
                    final_paid = 0.0
                else:  # partial
                    text_val = st.session_state.get("purchase_paid_amount_text", "")
                    final_paid = _read_amount_from_text(
                        text_val,
                        default=0.0,
                        max_value=total_purchase
                    )

                st.session_state.final_paid_to_save = final_paid
                st.session_state.saving_purchase = True
                st.rerun()

            if st.session_state.saving_purchase:
                try:
                    # ✅ القيمة النهائية
                    actual_paid = st.session_state.get("final_paid_to_save", 0.0)

                    invoice_id, total, error = create_purchase_invoice(
                        supplier_id=supplier_id,
                        items=st.session_state.purchase_items,
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
                            f"لكن **لم يُنشأ سند الصرف التلقائي**.\n\n"
                            f"**السبب:** {error}\n\n"
                            f"👉 اذهب لتبويب **'فواتير المشتريات'** واضغط **'إنشاء السند يدوياً'**."
                        )
                        st.session_state.purchase_items = []

                    else:
                        st.success(
                            f"✅ تم حفظ فاتورة المشتريات رقم {invoice_id} بنجاح "
                            f"— المدفوع: {actual_paid:,.2f} {currency_code}"
                        )
                        st.session_state.purchase_items = []
                        st.session_state.purchase_paid_amount_text = ""

                except Exception as e:
                    st.error(f"❌ خطأ غير متوقع: {e}")
                finally:
                    st.session_state.saving_purchase = False
                    st.rerun()

            if st.button("🗑️ مسح بنود المشتريات"):
                st.session_state.purchase_items = []
                st.session_state.purchase_paid_amount_text = ""
                st.rerun()

    # ============================================================
    # التبويب 2: فواتير المشتريات
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>فواتير المشتريات المسجلة</h3>",
                    unsafe_allow_html=True)

        all_invoices = get_purchase_invoices()

        invoices_with_warnings = [inv for inv in all_invoices if inv.get('has_warning')]
        if invoices_with_warnings:
            st.error(
                f"⚠️ يوجد **{len(invoices_with_warnings)}** فاتورة "
                f"لم يُنشأ لها سند صرف تلقائي. راجعها أدناه."
            )

        if all_invoices:
            df_invoices = pd.DataFrame(all_invoices)
            display_cols = ["id", "supplier", "invoice_date", "total",
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
                                        invoice_ids, key="pur_inv_sel")
            if selected_id:
                details = get_invoice_details(selected_id)
                if details:
                    df_details = pd.DataFrame(details)
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    total = sum(d['total'] for d in details)
                    st.markdown(f"**الإجمالي: {total:,.2f}**")

                inv_sel = next((i for i in all_invoices if i['id'] == selected_id), None)
                if inv_sel:
                    st.markdown("### حالة الدفع للمورد")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("الإجمالي", f"{float(inv_sel['total']):,.2f}")
                    c2.metric("المدفوع", f"{float(inv_sel.get('paid_amount', 0)):,.2f}")
                    c3.metric("المتبقي", f"{float(inv_sel.get('remaining_amount', 0)):,.2f}")

                    st.markdown(
                        f"**حالة الدفع:** {PAYMENT_STATUS_LABELS.get(inv_sel.get('payment_status'), '—')} "
                        f"| **طريقة الدفع:** {PAYMENT_METHOD_LABELS.get(inv_sel.get('payment_method'), '—')}"
                    )

                    if inv_sel.get('has_warning'):
                        st.warning(
                            f"⚠️ **تنبيه:** {inv_sel.get('reference', '')}"
                        )

                        if float(inv_sel.get('paid_amount', 0)) > 0:
                            if st.button(
                                f"🔧 إنشاء سند الصرف يدوياً للفاتورة #{selected_id}",
                                type="primary",
                                key=f"create_voucher_btn_{selected_id}"
                            ):
                                with st.spinner("جاري إنشاء سند الصرف..."):
                                    vid, verr = create_payment_voucher_for_invoice(
                                        invoice_id=selected_id,
                                        username=st.session_state.user.get('username', 'admin')
                                    )
                                    if verr:
                                        st.error(f"❌ فشل: {verr}")
                                    else:
                                        st.success(f"✅ تم إنشاء سند الصرف رقم {vid}")
                                        st.rerun()
        else:
            st.info("لا توجد فواتير مشتريات بعد")

    # ============================================================
    # التبويب 3: الموردين
    # ============================================================
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>إدارة الموردين</h3>",
                    unsafe_allow_html=True)

        st.markdown("### إضافة مورد جديد")
        name = st.text_input("اسم المورد", key="supp_name")
        col1, col2 = st.columns(2)
        phone = col1.text_input("رقم الهاتف", key="supp_phone")
        address = col2.text_input("العنوان", key="supp_addr")

        if st.button("➕ إضافة المورد", key="add_supp_btn"):
            if name:
                add_supplier(name, phone, address,
                             st.session_state.user.get('username', 'admin'))
                st.success(f"تمت إضافة المورد '{name}'")
                st.rerun()
            else:
                st.error("اسم المورد مطلوب")

        st.markdown("---")
        st.subheader("الموردين الحاليين")
        suppliers = get_all_suppliers()
        if suppliers:
            st.dataframe(pd.DataFrame(suppliers), use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد موردون بعد")
