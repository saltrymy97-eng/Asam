# sales.py - إدارة المبيعات (مع سجل التدقيق)
import streamlit as st
import pandas as pd
from database import get_connection
from services.audit_service import log_action  # 🆕

def show():
    st.title("🛒 إدارة المبيعات")
    conn = get_connection()

    tab1, tab2, tab3 = st.tabs(["إنشاء فاتورة مبيعات", "فواتير المبيعات", "العملاء"])

    # ---------- التبويب 1: إنشاء فاتورة ----------
    with tab1:
        st.subheader("إنشاء فاتورة مبيعات جديدة")

        customers = pd.read_sql_query("SELECT id, name FROM customers", conn)
        if customers.empty:
            st.warning("لا يوجد عملاء. أضف عميلاً من تبويب 'العملاء' أولاً.")
            customer_id = None
        else:
            customer_name = st.selectbox("اختر العميل", customers["name"].tolist())
            customer_id = int(customers[customers["name"] == customer_name]["id"].values[0])

        products = pd.read_sql_query("SELECT id, name, selling_price, quantity FROM products", conn)
        if products.empty:
            st.warning("لا توجد منتجات. أضف منتجات من وحدة المخزون أولاً.")
            return

        if 'invoice_items' not in st.session_state:
            st.session_state.invoice_items = []

        col1, col2, col3 = st.columns(3)
        selected_product = col1.selectbox("اختر المنتج", products["name"].tolist(), key="prod_sel")
        qty = col2.number_input("الكمية", min_value=1, step=1, key="qty_sel")
        if col3.button("إضافة إلى الفاتورة", use_container_width=True):
            product_row = products[products["name"] == selected_product].iloc[0]
            if qty > product_row["quantity"]:
                st.error(f"المخزون غير كافٍ. المتاح: {product_row['quantity']}")
            else:
                item = {
                    "product_id": int(product_row["id"]),
                    "name": selected_product,
                    "quantity": qty,
                    "unit_price": float(product_row["selling_price"]),
                    "total": qty * float(product_row["selling_price"])
                }
                st.session_state.invoice_items.append(item)
                st.success(f"تمت إضافة {selected_product}")

        if st.session_state.invoice_items:
            st.markdown("---")
            st.subheader("بنود الفاتورة")
            items_df = pd.DataFrame(st.session_state.invoice_items)
            st.dataframe(items_df[["name", "quantity", "unit_price", "total"]], use_container_width=True)

            total_invoice = sum(item["total"] for item in st.session_state.invoice_items)
            st.markdown(f"### الإجمالي: {total_invoice:,.2f}")

            if st.button("💾 حفظ الفاتورة", type="primary"):
                if customer_id is None:
                    st.error("يجب اختيار عميل")
                else:
                    try:
                        cursor = conn.execute(
                            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('sale', ?, date('now'), ?, 'completed')",
                            (customer_id, total_invoice)
                        )
                        invoice_id = cursor.lastrowid

                        for item in st.session_state.invoice_items:
                            conn.execute(
                                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                                (invoice_id, item["product_id"], item["quantity"], item["unit_price"])
                            )
                            conn.execute(
                                "INSERT INTO stock_movements (product_id, type, quantity, date, reference) VALUES (?, 'out', ?, date('now'), ?)",
                                (item["product_id"], item["quantity"], f"فاتورة مبيعات #{invoice_id}")
                            )
                            conn.execute(
                                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                                (item["quantity"], item["product_id"])
                            )

                        conn.commit()
                        # 🆕 تسجيل في سجل التدقيق
                        log_action(
                            username=st.session_state.user.get('username', 'admin'),
                            action="فاتورة مبيعات",
                            table_name="invoices",
                            record_id=invoice_id,
                            new_value=f"العميل: {customer_name}, الإجمالي: {total_invoice:,.2f}"
                        )
                        st.success(f"تم حفظ الفاتورة رقم {invoice_id} بنجاح")
                        st.session_state.invoice_items = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في حفظ الفاتورة: {e}")

            if st.button("🗑️ مسح جميع البنود"):
                st.session_state.invoice_items = []
                st.rerun()

    # ---------- التبويب 2: فواتير المبيعات ----------
    with tab2:
        st.subheader("فواتير المبيعات المسجلة")
        invoices_df = pd.read_sql_query("""
            SELECT i.id, c.name as customer, i.invoice_date, i.total, i.status
            FROM invoices i
            LEFT JOIN customers c ON i.party_id = c.id
            WHERE i.type = 'sale'
            ORDER BY i.id DESC
        """, conn)
        if not invoices_df.empty:
            selected_invoice = st.selectbox("اختر فاتورة لعرض تفاصيلها", invoices_df["id"].tolist())
            details = pd.read_sql_query("""
                SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
                FROM invoice_items ii
                JOIN products p ON ii.product_id = p.id
                WHERE ii.invoice_id = ?
            """, conn, params=(selected_invoice,))
            if not details.empty:
                st.dataframe(details, use_container_width=True)
                st.markdown(f"**إجمالي الفاتورة: {details['total'].sum():,.2f}**")
            st.dataframe(invoices_df, use_container_width=True)
        else:
            st.info("لا توجد فواتير مبيعات بعد")

    # ---------- التبويب 3: العملاء ----------
    with tab3:
        st.subheader("إدارة العملاء")
        with st.form("add_customer"):
            col1, col2 = st.columns(2)
            name = col1.text_input("اسم العميل")
            phone = col2.text_input("رقم الهاتف")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة عميل"):
                if name:
                    conn.execute(
                        "INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)",
                        (name, phone, address)
                    )
                    conn.commit()
                    # 🆕 تسجيل في سجل التدقيق
                    log_action(
                        username=st.session_state.user.get('username', 'admin'),
                        action="إضافة عميل",
                        table_name="customers",
                        new_value=f"العميل: {name}, الهاتف: {phone}"
                    )
                    st.success(f"تمت إضافة العميل '{name}'")
                    st.rerun()
                else:
                    st.error("اسم العميل مطلوب")

        existing_customers = pd.read_sql_query("SELECT * FROM customers", conn)
        if not existing_customers.empty:
            st.dataframe(existing_customers, use_container_width=True)

    conn.close()
