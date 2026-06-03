# ui/inventory_ui.py – واجهة المخزون (تصميم زجاجي فخم + حماية من الصرف الزائد)
import streamlit as st
import pandas as pd
from services.inventory_service import (
    get_all_products,
    add_product,
    record_stock_movement,
    get_stock_movements,
    get_low_stock_products,
    get_products_for_select
)
from database import get_connection

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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">📦 إدارة المخزون</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة المنتجات وحركات المخزون وتنبيهات النقص</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📋 المنتجات", "➕ إضافة منتج", "🔄 حركة المخزون", "⚠️ تنبيهات النقص"])

    # ---------- التبويب 1: المنتجات ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>جميع المنتجات</h3>", unsafe_allow_html=True)
        products = get_all_products()
        if products:
            st.dataframe(pd.DataFrame(products), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد منتجات حالياً")

    # ---------- التبويب 2: إضافة منتج ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة منتج جديد</h3>", unsafe_allow_html=True)
        with st.form("add_product_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم المنتج")
            barcode = col2.text_input("الباركود (اختياري)")
            category = st.selectbox("الفئة", ["مواد خام", "منتج نهائي", "قطع غيار", "أخرى"])
            col3, col4 = st.columns(2)
            purchase_price = col3.number_input("سعر الشراء", min_value=0.0, step=0.01)
            selling_price = col4.number_input("سعر البيع", min_value=0.0, step=0.01)
            quantity = st.number_input("الكمية الابتدائية", min_value=0, step=1)
            reorder_level = st.number_input("حد إعادة الطلب", min_value=0, value=10, step=1)
            submit = st.form_submit_button("إضافة المنتج")
            if submit:
                if not name:
                    st.error("الرجاء إدخال اسم المنتج")
                else:
                    success, error = add_product(
                        name, barcode, category, purchase_price, selling_price,
                        quantity, reorder_level,
                        st.session_state.user.get('username', 'admin')
                    )
                    if success:
                        st.success(f"تمت إضافة المنتج '{name}' بنجاح")
                        st.rerun()
                    else:
                        st.error(f"فشل في إضافة المنتج: {error}")

    # ---------- التبويب 3: حركة المخزون ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>تسجيل حركة مخزون</h3>", unsafe_allow_html=True)
        products_list = get_products_for_select()
        if products_list:
            product_names = [p['name'] for p in products_list]
            selected_product = st.selectbox("اختر المنتج", product_names)
            product_id = next(p['id'] for p in products_list if p['name'] == selected_product)

            # جلب الرصيد الحالي للمنتج وعرضه بوضوح
            conn = get_connection()
            current_qty_row = conn.execute("SELECT quantity FROM products WHERE id = ?", (product_id,)).fetchone()
            conn.close()
            current_qty = current_qty_row[0] if current_qty_row else 0
            st.info(f"📊 الرصيد الحالي: **{current_qty}**")

            move_type = st.radio("نوع الحركة", ["داخل (إضافة)", "خارج (صرف)"])
            quantity = st.number_input("الكمية", min_value=0, step=1)

            # إذا كانت الحركة صرف، نتحقق من الكمية قبل التفعيل
            if "خارج" in move_type and quantity > current_qty:
                st.error(f"❌ لا يمكن صرف {quantity} وحدة. الرصيد المتاح: {current_qty} فقط")
                quantity = 0  # نعيد تعيين الكمية لتجنب استمرار الخطأ

            reference = st.text_input("المرجع (رقم الفاتورة أو الإذن)")

            if st.button("تسجيل الحركة"):
                if quantity <= 0:
                    st.error("الكمية يجب أن تكون أكبر من صفر")
                else:
                    success, error = record_stock_movement(
                        product_id, selected_product, move_type, quantity, reference,
                        st.session_state.user.get('username', 'admin')
                    )
                    if success:
                        st.success("تم تسجيل الحركة بنجاح")
                        st.rerun()
                    else:
                        st.error(f"فشل في تسجيل الحركة: {error}")
        else:
            st.warning("لا توجد منتجات، أضف منتجاً أولاً")

        st.markdown("---")
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>سجل حركات المخزون</h4>", unsafe_allow_html=True)
        movements = get_stock_movements()
        if movements:
            st.dataframe(pd.DataFrame(movements), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حركات مخزون بعد")

    # ---------- التبويب 4: تنبيهات النقص ----------
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>⚠️ منتجات تحت الحد الأدنى</h3>", unsafe_allow_html=True)
        low_stock = get_low_stock_products()
        if low_stock:
            st.warning("المنتجات التالية اقتربت من النفاد:")
            st.dataframe(pd.DataFrame(low_stock), use_container_width=True, hide_index=True)
        else:
            st.success("جميع المنتجات بمستويات آمنة")
