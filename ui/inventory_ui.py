# ui/inventory_ui.py – واجهة المخزون (v2.0)
# ✅ close_connection بدل conn.close() + بطاقة الرصيد + تحقق محسّن
import streamlit as st
import pandas as pd
from services.inventory_service import (
    get_all_products,
    add_product,
    record_stock_movement,
    get_stock_movements,
    get_low_stock_products,
    get_products_for_select,
    get_product_quantity,      # ✅ جديد — أخف من فتح اتصال
)
from services.purchases_service import create_purchase_invoice  # اختياري للشراء السريع

# ========== ألوان ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"


# ============================================================
# بطاقة عرض الرصيد
# ============================================================
def _render_qty_card(product_name: str, qty: float, reorder: float = 0):
    """بطاقة الرصيد الحالي مع تحذير لوني"""
    if qty <= 0:
        color = ACCENT_RED
        icon = "🔴"
        note = "نفد المخزون!"
    elif qty < reorder:
        color = ACCENT_ORANGE
        icon = "🟡"
        note = f"أقل من حد الطلب ({reorder:g})"
    else:
        color = ACCENT_GREEN
        icon = "🟢"
        note = "متوفر"

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg, rgba(59,130,246,0.15), rgba(139,92,246,0.10));
            border-right: 4px solid {color};
            border-radius: 8px; padding: 12px 16px; margin: 8px 0;
            text-align: right; direction: rtl;
        ">
            <span style="color:{TEXT_SECONDARY}; font-size:0.9rem;">{icon} {product_name}:</span>
            <b style="color:{color}; font-size:1.2rem; margin-right:8px;"> {qty:,.2f}</b>
            <span style="color:{TEXT_SECONDARY};"> — {note}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# الواجهة الرئيسية
# ============================================================
def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">📦 إدارة المخزون</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة المنتجات وحركات المخزون وتنبيهات النقص</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 المنتجات",
        "➕ إضافة منتج",
        "🔄 حركة المخزون",
        "⚠️ تنبيهات النقص"
    ])

    # ============================================================
    # التبويب 1: المنتجات
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>جميع المنتجات</h3>",
                    unsafe_allow_html=True)
        products = get_all_products()
        if products:
            df = pd.DataFrame(products)

            # ✅ فلترة سريعة
            col_search, col_filter = st.columns([3, 1])
            with col_search:
                search = st.text_input("🔍 بحث (اسم / باركود)",
                                       key="prod_search",
                                       placeholder="اكتب للبحث...")
            with col_filter:
                categories = ["الكل"] + sorted(
                    set(p.get("category") or "—" for p in products)
                )
                cat_filter = st.selectbox("الفئة", categories,
                                           key="prod_cat_filter")

            df_view = df.copy()
            if search:
                mask = (
                    df_view['name'].astype(str).str.contains(search, case=False, na=False) |
                    df_view.get('barcode', pd.Series(dtype=str)).astype(str).str.contains(search, case=False, na=False)
                )
                df_view = df_view[mask]
            if cat_filter != "الكل":
                df_view = df_view[df_view['category'] == cat_filter]

            # اختيار الأعمدة المهمة فقط
            display_cols = ['id', 'name', 'barcode', 'category',
                            'purchase_price', 'selling_price',
                            'quantity', 'reorder_level']
            display_cols = [c for c in display_cols if c in df_view.columns]

            st.dataframe(df_view[display_cols],
                         use_container_width=True,
                         hide_index=True)
            st.caption(f"📊 إجمالي المنتجات: {len(df_view)} من {len(df)}")
        else:
            st.info("لا توجد منتجات حالياً")

    # ============================================================
    # التبويب 2: إضافة منتج
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة منتج جديد</h3>",
                    unsafe_allow_html=True)

        with st.form("add_product_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم المنتج *")
            barcode = col2.text_input("الباركود (اختياري)")

            category = st.text_input("الفئة", value="عام")

            col3, col4 = st.columns(2)
            purchase_price = col3.number_input("سعر الشراء", min_value=0.0,
                                                step=0.01, format="%.2f")
            selling_price = col4.number_input("سعر البيع", min_value=0.0,
                                               step=0.01, format="%.2f")

            col5, col6 = st.columns(2)
            quantity = col5.number_input("الكمية الابتدائية", min_value=0.0,
                                          step=1.0, format="%.2f")
            reorder_level = col6.number_input("حد إعادة الطلب", min_value=0.0,
                                               value=10.0, step=1.0,
                                               format="%.2f")

            submit = st.form_submit_button("💾 إضافة المنتج", type="primary")

            if submit:
                if not name or not name.strip():
                    st.error("❌ اسم المنتج مطلوب")
                else:
                    username = st.session_state.get('user', {}).get('username', 'admin')
                    success, error = add_product(
                        name.strip(), barcode, category,
                        purchase_price, selling_price,
                        quantity, reorder_level,
                        username=username
                    )
                    if success:
                        st.success(f"✅ تمت إضافة المنتج «{name}» بنجاح")
                        st.rerun()
                    else:
                        st.error(f"❌ فشل: {error}")

    # ============================================================
    # التبويب 3: حركة المخزون
    # ============================================================
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>تسجيل حركة مخزون</h3>",
                    unsafe_allow_html=True)

        products_list = get_products_for_select()
        if not products_list:
            st.warning("⚠️ لا توجد منتجات — أضف منتجاً أولاً")
        else:
            product_options = {p['name']: p for p in products_list}
            selected_name = st.selectbox("اختر المنتج",
                                          list(product_options.keys()),
                                          key="move_product")
            product = product_options[selected_name]
            product_id = product['id']

            # ✅ استخدام get_product_quantity (لا فتح اتصال يدوي)
            current_qty = get_product_quantity(product_id) or 0.0

            # جلب حد الطلب لعرض التحذير اللوني
            products_all = get_all_products()
            this_prod = next((p for p in products_all if p['id'] == product_id), None)
            reorder = float(this_prod.get('reorder_level', 0) or 0) if this_prod else 0

            _render_qty_card(selected_name, current_qty, reorder)

            move_type = st.radio(
                "نوع الحركة",
                ["داخل (إضافة)", "خارج (صرف)"],
                horizontal=True,
                key="move_type"
            )

            quantity = st.number_input(
                "الكمية",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                key="move_qty"
            )

            # ✅ فحص فوري (لا نُعيد تعيين quantity — نعطّل الزر)
            is_out = "خارج" in move_type
            has_shortage = is_out and quantity > current_qty + 0.0001

            if has_shortage:
                shortage = quantity - current_qty
                st.error(
                    f"❌ لا يمكن صرف {quantity:,.2f} وحدة — "
                    f"الرصيد المتاح: {current_qty:,.2f} "
                    f"(نقص: {shortage:,.2f})"
                )
            elif is_out and quantity > 0:
                remaining = current_qty - quantity
                st.success(f"✅ سيتبقى بعد الصرف: {remaining:,.2f}")

            reference = st.text_input("المرجع (رقم الفاتورة أو الإذن)",
                                       key="move_ref")

            can_submit = (quantity > 0) and (not has_shortage)

            if st.button("💾 تسجيل الحركة",
                         type="primary",
                         key="save_movement",
                         disabled=not can_submit):
                username = st.session_state.get('user', {}).get('username', 'admin')
                success, error = record_stock_movement(
                    product_id, selected_name, move_type, quantity, reference,
                    username=username
                )
                if success:
                    st.success("✅ تم تسجيل الحركة بنجاح")
                    st.rerun()
                else:
                    st.error(f"❌ فشل: {error}")

        st.markdown("---")
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📋 سجل حركات المخزون</h4>",
                    unsafe_allow_html=True)
        movements = get_stock_movements()
        if movements:
            df_mv = pd.DataFrame(movements)
            # ترجمة النوع
            if 'type' in df_mv.columns:
                df_mv['type'] = df_mv['type'].apply(
                    lambda x: "🟢 داخل" if x == "in" else "🔴 خارج"
                )
            st.dataframe(df_mv, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حركات مخزون بعد")

    # ============================================================
    # التبويب 4: تنبيهات النقص
    # ============================================================
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>⚠️ منتجات تحت الحد الأدنى</h3>",
                    unsafe_allow_html=True)
        low_stock = get_low_stock_products()
        if low_stock:
            st.warning(f"يوجد **{len(low_stock)}** منتج تحت حد الطلب:")
            df_low = pd.DataFrame(low_stock)
            # عرض النقص أيضاً
            if 'quantity' in df_low.columns and 'reorder_level' in df_low.columns:
                df_low['النقص'] = df_low['reorder_level'].astype(float) - df_low['quantity'].astype(float)
            st.dataframe(df_low, use_container_width=True, hide_index=True)
        else:
            st.success("✅ جميع المنتجات بمستويات آمنة")
