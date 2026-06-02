# ui/sales_ui.py – واجهة المبيعات (تصميم زجاجي فخم + دعم العملات)
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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🛒 إدارة المبيعات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إنشاء فواتير البيع وإدارة العملاء</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 إنشاء فاتورة", "📋 فواتير المبيعات", "👥 العملاء"])

    # ---------- التبويب 1: إنشاء فاتورة ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>إنشاء فاتورة مبيعات جديدة</h3>", unsafe_allow_html=True)
        
        customers = get_customers()
        if not customers:
            st.warning("لا يوجد عملاء. أضف عميلاً من تبويب 'العملاء' أولاً.")
            customer_id = None
        else:
            customer_names = [c['name'] for c in customers]
            selected_customer = st.selectbox("اختر العميل", customer_names)
            customer_id = next(c['id'] for c in customers if c['name'] == selected_customer)

        # 🆕 اختيار العملة
        currencies = get_all_currencies()
        base_currency = get_base_currency()
        currency_options = {f"{c['code']} - {c['name']}": c['code'] for c in currencies}
        default_currency = base_currency['code'] if base_currency else 'YER'
        default_label = next((k for k, v in currency_options.items() if v == default_currency), list(currency_options.keys())[0])
        selected_currency_label = st.selectbox("💱 العملة", list(currency_options.keys()), index=list(currency_options.keys()).index(default_label))
        currency_code = currency_options[selected_currency_label]

        products = get_products_for_sale()
        if not products:
            st.warning("لا توجد منتجات متاحة للبيع.")
            return

        if 'invoice_items' not in st.session_state:
            st.session_state.invoice_items = []

        col1, col2, col3 = st.columns(3)
        with col1:
            selected_product = st.selectbox("اختر المنتج", [p['name'] for p in products], key="prod_sel")
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

        if st.session_state.invoice_items:
            st.markdown("---")
            st.subheader("بنود الفاتورة")
            items_df = pd.DataFrame(st.session_state.invoice_items)
            st.dataframe(items_df[["name", "quantity", "unit_price", "total"]], use_container_width=True)
            total_invoice = sum(item["total"] for item in st.session_state.invoice_items)
            st.markdown(f"### الإجمالي: {total_invoice:,.2f} {currency_code}")

            if st.button("💾 حفظ الفاتورة", type="primary"):
                if customer_id is None:
                    st.error("يجب اختيار عميل")
                else:
                    invoice_id, total, error = create_sale_invoice(
                        customer_id=customer_id,
                        items=st.session_state.invoice_items,
                        username=st.session_state.user.get('username', 'admin'),
                        currency_code=currency_code
                    )
                    if error:
                        st.error(f"فشل في حفظ الفاتورة: {error}")
                    else:
                        st.success(f"تم حفظ الفاتورة رقم {invoice_id} بنجاح")
                        st.session_state.invoice_items = []
                        st.rerun()

            if st.button("🗑️ مسح جميع البنود"):
                st.session_state.invoice_items = []
                st.rerun()

    # ---------- التبويب 2: فواتير المبيعات ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>فواتير المبيعات المسجلة</h3>", unsafe_allow_html=True)
        invoices = get_sale_invoices()
        if invoices:
            df_invoices = pd.DataFrame(invoices)
            st.dataframe(df_invoices, use_container_width=True, hide_index=True)
            
            invoice_ids = [inv['id'] for inv in invoices]
            selected_id = st.selectbox("اختر فاتورة لعرض تفاصيلها", invoice_ids)
            if selected_id:
                details = get_invoice_details(selected_id)
                if details:
                    df_details = pd.DataFrame(details)
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    total = sum(d['total'] for d in details)
                    st.markdown(f"**إجمالي الفاتورة: {total:,.2f}**")
        else:
            st.info("لا توجد فواتير مبيعات بعد")

    # ---------- التبويب 3: العملاء ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>إدارة العملاء</h3>", unsafe_allow_html=True)
        
        st.markdown("### إضافة عميل جديد")
        with st.form("add_customer"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم العميل")
            phone = col2.text_input("رقم الهاتف")
            address = st.text_input("العنوان")
            if st.form_submit_button("➕ إضافة عميل"):
                if name:
                    add_customer(name, phone, address, st.session_state.user.get('username', 'admin'))
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
