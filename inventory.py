# modules/inventory.py - إدارة المخزون
import streamlit as st
import pandas as pd
from database import get_connection

def show():
    st.title("📦 إدارة المخزون")
    conn = get_connection()

    tab1, tab2, tab3, tab4 = st.tabs(["المنتجات", "إضافة منتج", "حركة المخزون", "تنبيهات النقص"])

    # ---------- التبويب 1: المنتجات ----------
    with tab1:
        st.subheader("جميع المنتجات")
        products_df = pd.read_sql_query("SELECT * FROM products", conn)
        if not products_df.empty:
            st.dataframe(products_df, use_container_width=True)
        else:
            st.info("لا توجد منتجات حالياً")

    # ---------- التبويب 2: إضافة منتج ----------
    with tab2:
        st.subheader("إضافة منتج جديد")
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
                    try:
                        conn.execute(
                            """INSERT INTO products (name, barcode, category, purchase_price, selling_price, quantity, reorder_level)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (name, barcode if barcode else None, category, purchase_price, selling_price, quantity, reorder_level)
                        )
                        conn.commit()
                        st.success(f"تمت إضافة المنتج '{name}' بنجاح")
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في إضافة المنتج: {e}")

    # ---------- التبويب 3: حركة المخزون ----------
    with tab3:
        st.subheader("تسجيل حركة مخزون")
        # جلب المنتجات لعرضها في قائمة منسدلة
        products_list = pd.read_sql_query("SELECT id, name FROM products", conn)
        if not products_list.empty:
            product_names = products_list["name"].tolist()
            selected_product = st.selectbox("اختر المنتج", product_names)
            product_id = int(products_list[products_list["name"] == selected_product]["id"].values[0])

            move_type = st.radio("نوع الحركة", ["داخل (إضافة)", "خارج (صرف)"])
            quantity = st.number_input("الكمية", min_value=1, step=1)
            reference = st.text_input("المرجع (رقم الفاتورة أو الإذن)")

            if st.button("تسجيل الحركة"):
                if quantity <= 0:
                    st.error("الكمية يجب أن تكون أكبر من صفر")
                else:
                    type_en = "in" if "داخل" in move_type else "out"
                    conn.execute(
                        "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, ?, ?, date('now'), ?)",
                        (product_id, type_en, quantity, reference)
                    )
                    # تحديث الكمية في جدول المنتجات
                    sign = 1 if type_en == "in" else -1
                    conn.execute(
                        "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                        (sign * quantity, product_id)
                    )
                    conn.commit()
                    st.success("تم تسجيل الحركة بنجاح")
                    st.rerun()
        else:
            st.warning("لا توجد منتجات، أضف منتجاً أولاً")

        # عرض حركات المخزون
        st.markdown("---")
        st.subheader("سجل حركات المخزون")
        movements_df = pd.read_sql_query("""
            SELECT sm.id, p.name as product, sm.type, sm.quantity, sm.date, sm.reference
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            ORDER BY sm.id DESC
            LIMIT 50
        """, conn)
        if not movements_df.empty:
            st.dataframe(movements_df, use_container_width=True)
        else:
            st.info("لا توجد حركات مخزون بعد")

    # ---------- التبويب 4: تنبيهات النقص ----------
    with tab4:
        st.subheader("⚠️ منتجات تحت الحد الأدنى")
        low_stock = pd.read_sql_query(
            "SELECT name, quantity, reorder_level FROM products WHERE quantity < reorder_level", conn
        )
        if not low_stock.empty:
            st.warning("المنتجات التالية اقتربت من النفاد:")
            st.dataframe(low_stock, use_container_width=True)
        else:
            st.success("جميع المنتجات بمستويات آمنة")

    conn.close()
