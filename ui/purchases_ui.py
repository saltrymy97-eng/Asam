# ui/purchases_ui.py – واجهة المشتريات (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from services.purchases_service import (
    get_suppliers,
    get_products_for_purchase,
    create_purchase_invoice,
    get_purchase_invoices,
    get_invoice_details,
    add_supplier,
    get_all_suppliers
)

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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🚚 إدارة المشتريات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إنشاء فواتير الشراء وإدارة الموردين</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 إنشاء فاتورة", "📋 فواتير المشتريات", "👥 الموردين"])

    # ---------- التبويب 1: إنشاء فاتورة ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>إنشاء فاتورة مشتريات جديدة</h3>", unsafe_allow_html=True)
        
        suppliers = get_suppliers()
        if not suppliers:
            st.warning("لا يوجد موردون. أضف مورداً من تبويب 'الموردين' أولاً.")
            supplier_id = None
        else:
            supplier_names = [s['name'] for s in suppliers]
            selected_supplier = st.selectbox("اختر المورد", supplier_names)
            supplier_id = next(s['id'] for s in suppliers if s['name'] == selected_supplier)

        products = get_products_for_purchase()
        if not products:
            st.warning("لا توجد منتجات.")
            return

        if 'purchase_items' not in st.session_state:
            st.session_state.purchase_items = []

        col1, col2, col3 = st.columns(3)
        with col1:
            selected_product = st.selectbox("اختر المنتج", [p['name'] for p in products], key="pur_prod_sel")
        with col2:
            qty = st.number_input("الكمية", min_value=1, step=1, key="pur_qty_sel")
        with col3:
            default_price = next(p['purchase_price'] for p in products if p['name'] == selected_product)
            unit_price = st.number_input("سعر الشراء للوحدة", min_value=0.0, step=0.01, value=default_price, key="pur_price_sel")

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
            st.dataframe(items_df[["name", "quantity", "unit_price", "total"]], use_container_width=True)
            total_purchase = sum(item["total"] for item in st.session_state.purchase_items)
            st.markdown(f"### الإجمالي: {total_purchase:,.2f}")

            if st.button("💾 حفظ فاتورة المشتريات", type="primary"):
                if supplier_id is None:
                    st.error("يجب اختيار مورد")
                else:
                    invoice_id, total, error = create_purchase_invoice(
                        supplier_id=supplier_id,
                        items=st.session_state.purchase_items,
                        username=st.session_state.user.get('username', 'admin')
                    )
                    if error:
                        st.error(f"فشل في حفظ الفاتورة: {error}")
                    else:
                        st.success(f"تم حفظ فاتورة المشتريات رقم {invoice_id} بنجاح")
                        st.session_state.purchase_items = []
                        st.rerun()

            if st.button("🗑️ مسح بنود المشتريات"):
                st.session_state.purchase_items = []
                st.rerun()

    # ---------- التبويب 2: فواتير المشتريات ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>فواتير المشتريات المسجلة</h3>", unsafe_allow_html=True)
        invoices = get_purchase_invoices()
        if invoices:
            df_invoices = pd.DataFrame(invoices)
            st.dataframe(df_invoices, use_container_width=True, hide_index=True)
            
            invoice_ids = [inv['id'] for inv in invoices]
            selected_id = st.selectbox("اختر فاتورة لعرض تفاصيلها", invoice_ids, key="pur_inv_sel")
            if selected_id:
                details = get_invoice_details(selected_id)
                if details:
                    df_details = pd.DataFrame(details)
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    total = sum(d['total'] for d in details)
                    st.markdown(f"**الإجمالي: {total:,.2f}**")
        else:
            st.info("لا توجد فواتير مشتريات بعد")

    # ---------- التبويب 3: الموردين ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>إدارة الموردين</h3>", unsafe_allow_html=True)
        
        st.markdown("### إضافة مورد جديد")
        name = st.text_input("اسم المورد", key="supp_name")
        col1, col2 = st.columns(2)
        phone = col1.text_input("رقم الهاتف", key="supp_phone")
        address = col2.text_input("العنوان", key="supp_addr")

        if st.button("➕ إضافة المورد", key="add_supp_btn"):
            if name:
                add_supplier(name, phone, address, st.session_state.user.get('username', 'admin'))
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
