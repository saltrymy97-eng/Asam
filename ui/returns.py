# ui/returns.py - واجهة مرتجعات البضاعة
import streamlit as st
import pandas as pd
from datetime import date
from services.returns_service import (
    get_sales_invoices,
    get_purchase_invoices,
    get_invoice_items,
    process_return,
    get_return_history
)

def show():
    st.title("🔄 مرتجعات البضاعة")

    tab1, tab2, tab3 = st.tabs(["مرتجع مبيعات", "مرتجع مشتريات", "سجل المرتجعات"])

    # ---------- مرتجع مبيعات ----------
    with tab1:
        st.subheader("إرجاع بضاعة من عميل")
        invoices = get_sales_invoices()
        if not invoices:
            st.info("لا توجد فواتير مبيعات مكتملة")
            return
        invoice_options = {f"فاتورة #{inv['id']} - {inv['customer']} ({inv['invoice_date']})": inv for inv in invoices}
        selected = st.selectbox("اختر الفاتورة", list(invoice_options.keys()), key="sales_return_inv")
        if selected:
            inv = invoice_options[selected]
            items = get_invoice_items(inv["id"])
            if items:
                st.markdown("**بنود الفاتورة:**")
                items_df = pd.DataFrame(items)
                st.dataframe(items_df[["name", "quantity", "unit_price"]], use_container_width=True)
                st.markdown("---")
                st.subheader("اختر المنتجات المرتجعة")
                return_items = []
                for item in items:
                    col1, col2 = st.columns([3, 1])
                    max_qty = int(item["quantity"])
                    qty = col2.number_input(f"كمية {item['name']}", min_value=0, max_value=max_qty, value=0, key=f"ret_{item['id']}")
                    col1.write(f"**{item['name']}** - المتاح: {max_qty}")
                    if qty > 0:
                        return_items.append((item["name"], qty))
                if return_items:
                    return_date = st.date_input("تاريخ المرتجع", value=date.today())
                    reason = st.text_area("سبب الإرجاع (اختياري)")
                    if st.button("✅ تأكيد مرتجع المبيعات", key="confirm_sale_return"):
                        success, result, total = process_return("sale", inv["id"], return_items, return_date.strftime("%Y-%m-%d"), reason)
                        if success:
                            st.success(f"تم تسجيل المرتجع رقم {result} - الإجمالي: {total:,.2f}")
                            st.rerun()
                        else:
                            st.error(f"فشل العملية: {result}")

    # ---------- مرتجع مشتريات ----------
    with tab2:
        st.subheader("إرجاع بضاعة للمورد")
        invoices = get_purchase_invoices()
        if not invoices:
            st.info("لا توجد فواتير مشتريات مكتملة")
            return
        invoice_options = {f"فاتورة #{inv['id']} - {inv['supplier']} ({inv['invoice_date']})": inv for inv in invoices}
        selected = st.selectbox("اختر الفاتورة", list(invoice_options.keys()), key="purchase_return_inv")
        if selected:
            inv = invoice_options[selected]
            items = get_invoice_items(inv["id"])
            if items:
                st.markdown("**بنود الفاتورة:**")
                items_df = pd.DataFrame(items)
                st.dataframe(items_df[["name", "quantity", "unit_price"]], use_container_width=True)
                st.markdown("---")
                st.subheader("اختر المنتجات المرتجعة")
                return_items = []
                for item in items:
                    col1, col2 = st.columns([3, 1])
                    max_qty = int(item["quantity"])
                    qty = col2.number_input(f"كمية {item['name']}", min_value=0, max_value=max_qty, value=0, key=f"pret_{item['id']}")
                    col1.write(f"**{item['name']}** - المتاح: {max_qty}")
                    if qty > 0:
                        return_items.append((item["name"], qty))
                if return_items:
                    return_date = st.date_input("تاريخ المرتجع", value=date.today(), key="purchase_ret_date")
                    reason = st.text_area("سبب الإرجاع (اختياري)", key="purchase_ret_reason")
                    if st.button("✅ تأكيد مرتجع المشتريات", key="confirm_purchase_return"):
                        success, result, total = process_return("purchase", inv["id"], return_items, return_date.strftime("%Y-%m-%d"), reason)
                        if success:
                            st.success(f"تم تسجيل المرتجع رقم {result} - الإجمالي: {total:,.2f}")
                            st.rerun()
                        else:
                            st.error(f"فشل العملية: {result}")

    # ---------- سجل المرتجعات ----------
    with tab3:
        st.subheader("سجل عمليات المرتجعات")
        returns = get_return_history()
        if returns:
            df = pd.DataFrame(returns)
            df["type"] = df["type"].map({"sale_return": "مرتجع مبيعات", "purchase_return": "مرتجع مشتريات"})
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد مرتجعات بعد")
