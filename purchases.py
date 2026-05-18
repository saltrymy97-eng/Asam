# purchases.py - إدارة المشتريات (إصدار نهائي - الموردين يعمل 100%)
import streamlit as st
import pandas as pd
from database import get_connection

def show():
    st.title("🚚 إدارة المشتريات")
    conn = get_connection()

    tab1, tab2, tab3 = st.tabs(["إنشاء فاتورة مشتريات", "فواتير المشتريات", "الموردين"])

    # ---------- التبويب 1: إنشاء فاتورة ----------
    with tab1:
        st.subheader("إنشاء فاتورة مشتريات جديدة")

        suppliers = pd.read_sql_query("SELECT id, name FROM suppliers", conn)
        if suppliers.empty:
            st.warning("لا يوجد موردون. أضف مورداً من تبويب 'الموردين' أولاً.")
            supplier_id = None
        else:
            supplier_name = st.selectbox("اختر المورد", suppliers["name"].tolist())
            supplier_id = int(suppliers[suppliers["name"] == supplier_name]["id"].values[0])

        products = pd.read_sql_query("SELECT id, name, purchase_price FROM products", conn)
        if products.empty:
            st.warning("لا توجد منتجات. أضف منتجات من وحدة المخزون أولاً.")
            conn.close()
            return

        if 'purchase_items' not in st.session_state:
            st.session_state.purchase_items = []

        col1, col2, col3 = st.columns(3)
        selected_product = col1.selectbox("اختر المنتج", products["name"].tolist(), key="pur_prod_sel")
        qty = col2.number_input("الكمية", min_value=1, step=1, key="pur_qty_sel")
        default_price = float(products[products["name"] == selected_product]["purchase_price"].values[0])
        unit_price = col3.number_input("سعر الشراء للوحدة", min_value=0.0, step=0.01, value=default_price, key="pur_price_sel")

        if st.button("➕ أضف إلى الفاتورة"):
            item = {
                "product_id": int(products[products["name"] == selected_product]["id"].values[0]),
                "name": selected_product,
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
                    try:
                        cursor = conn.execute(
                            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('purchase', ?, date('now'), ?, 'completed')",
                            (supplier_id, total_purchase)
                        )
                        invoice_id = cursor.lastrowid

                        for item in st.session_state.purchase_items:
                            conn.execute(
                                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                                (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
                            )
                            conn.execute(
                                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'in', ?, date('now'), ?)",
                                (item["product_id"], item["quantity"], f"فاتورة مشتريات #{invoice_id}")
                            )
                            conn.execute(
                                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                                (item["quantity"], item["product_id"])
                            )

                        conn.commit()
                        st.success(f"تم حفظ فاتورة المشتريات رقم {invoice_id} بنجاح")
                        st.session_state.purchase_items = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في حفظ الفاتورة: {e}")

            if st.button("🗑️ مسح بنود المشتريات"):
                st.session_state.purchase_items = []
                st.rerun()

    # ---------- التبويب 2: فواتير المشتريات ----------
    with tab2:
        st.subheader("فواتير المشتريات المسجلة")
        invoices_df = pd.read_sql_query("""
            SELECT i.id, s.name as supplier, i.invoice_date, i.total, i.status
            FROM invoices i
            LEFT JOIN suppliers s ON i.party_id = s.id
            WHERE i.type = 'purchase'
            ORDER BY i.id DESC
        """, conn)
        if not invoices_df.empty:
            selected = st.selectbox("اختر فاتورة لعرض تفاصيلها", invoices_df["id"].tolist(), key="pur_inv_sel")
            details = pd.read_sql_query("""
                SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
                FROM invoice_items ii
                JOIN products p ON ii.product_id = p.id
                WHERE ii.invoice_id = ?
            """, conn, params=(selected,))
            if not details.empty:
                st.dataframe(details, use_container_width=True)
                st.markdown(f"**الإجمالي: {details['total'].sum():,.2f}**")
            st.dataframe(invoices_df, use_container_width=True)
        else:
            st.info("لا توجد فواتير مشتريات بعد")

    # ---------- التبويب 3: الموردين (جديد كلياً - يعمل 100%) ----------
    with tab3:
        st.subheader("إدارة الموردين")
        
        # نموذج إضافة مورد
        st.markdown("### إضافة مورد جديد")
        name = st.text_input("اسم المورد", key="supp_name")
        col1, col2 = st.columns(2)
        phone = col1.text_input("رقم الهاتف", key="supp_phone")
        address = col2.text_input("العنوان", key="supp_addr")

        if st.button("➕ إضافة المورد", key="add_supp_btn"):
            if name:
                try:
                    conn.execute(
                        "INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)",
                        (name, phone, address)
                    )
                    conn.commit()
                    st.success(f"✅ تمت إضافة المورد '{name}' بنجاح")
                    st.rerun()
                except Exception as e:
                    st.error(f"فشل في إضافة المورد: {e}")
            else:
                st.error("⚠️ اسم المورد مطلوب")

        st.markdown("---")
        st.subheader("الموردين الحاليين")
        existing = pd.read_sql_query("SELECT * FROM suppliers ORDER BY id DESC", conn)
        if not existing.empty:
            st.dataframe(existing, use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد موردون بعد")

    conn.close()
