# ui/returns.py - واجهة مرتجعات البضاعة (تصميم زجاجي فخم)
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

# ========== ألوان التصميم ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"

def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">إدارة مرتجعات المبيعات والمشتريات</p>
    </div>""", unsafe_allow_html=True)

def h3(title, color=BL):
    st.markdown(f"""<h3 style="color:{color};text-align:right;margin-bottom:1rem;">{title}</h3>""", unsafe_allow_html=True)

def glass(content):
    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{T};font-size:1.1rem;">{content}</div>""", unsafe_allow_html=True)

def show():
    h1("🔄 مرتجعات البضاعة")
    
    tab1, tab2, tab3 = st.tabs(["مرتجع مبيعات", "مرتجع مشتريات", "سجل المرتجعات"])
    
    # ---------- مرتجع مبيعات ----------
    with tab1:
        h3("إرجاع بضاعة من عميل", GR)
        invoices = get_sales_invoices()
        
        if not invoices:
            st.info("لا توجد فواتير مبيعات مكتملة")
        else:
            invoice_options = {f"فاتورة #{inv['id']} - {inv['customer']} ({inv['invoice_date']})": inv for inv in invoices}
            selected = st.selectbox("اختر الفاتورة", list(invoice_options.keys()), key="sales_return_inv")
            
            if selected:
                inv = invoice_options[selected]
                items = get_invoice_items(inv["id"])
                
                if items:
                    st.markdown("**بنود الفاتورة:**")
                    items_df = pd.DataFrame(items)
                    st.dataframe(items_df, use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                    h3("اختر المنتجات المرتجعة", OR)
                    
                    return_items = []
                    for item in items:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(f"**{item['name']}** - المتاح: {item['quantity']}")
                        with col2:
                            qty_str = st.text_input(
                                "الكمية",
                                value="0",
                                key=f"ret_{inv['id']}_{item['id']}",
                                label_visibility="collapsed"
                            )
                            try:
                                qty = int(qty_str) if qty_str else 0
                            except:
                                qty = 0
                            if qty < 0:
                                qty = 0
                            if qty > int(item["quantity"]):
                                qty = int(item["quantity"])
                            if qty > 0:
                                return_items.append((item["name"], qty))
                    
                    if return_items:
                        return_date = st.date_input("تاريخ المرتجع", value=date.today())
                        reason = st.text_area("سبب الإرجاع (اختياري)")
                        
                        if st.button("✅ تأكيد مرتجع المبيعات", key="confirm_sale_return", type="primary"):
                            success, result, total = process_return(
                                "sale", inv["id"], return_items,
                                return_date.strftime("%Y-%m-%d"), reason
                            )
                            if success:
                                glass(f"✅ تم تسجيل المرتجع رقم {result} - الإجمالي: {total:,.2f}")
                                st.rerun()
                            else:
                                st.error(f"فشل العملية: {result}")
    
    # ---------- مرتجع مشتريات ----------
    with tab2:
        h3("إرجاع بضاعة للمورد", BL)
        invoices = get_purchase_invoices()
        
        if not invoices:
            st.info("لا توجد فواتير مشتريات مكتملة")
        else:
            invoice_options = {f"فاتورة #{inv['id']} - {inv['supplier']} ({inv['invoice_date']})": inv for inv in invoices}
            selected = st.selectbox("اختر الفاتورة", list(invoice_options.keys()), key="purchase_return_inv")
            
            if selected:
                inv = invoice_options[selected]
                items = get_invoice_items(inv["id"])
                
                if items:
                    st.markdown("**بنود الفاتورة:**")
                    items_df = pd.DataFrame(items)
                    st.dataframe(items_df, use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                    h3("اختر المنتجات المرتجعة", OR)
                    
                    return_items = []
                    for item in items:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(f"**{item['name']}** - المتاح: {item['quantity']}")
                        with col2:
                            qty_str = st.text_input(
                                "الكمية",
                                value="0",
                                key=f"pret_{inv['id']}_{item['id']}",
                                label_visibility="collapsed"
                            )
                            try:
                                qty = int(qty_str) if qty_str else 0
                            except:
                                qty = 0
                            if qty < 0:
                                qty = 0
                            if qty > int(item["quantity"]):
                                qty = int(item["quantity"])
                            if qty > 0:
                                return_items.append((item["name"], qty))
                    
                    if return_items:
                        return_date = st.date_input("تاريخ المرتجع", value=date.today(), key="purchase_ret_date")
                        reason = st.text_area("سبب الإرجاع (اختياري)", key="purchase_ret_reason")
                        
                        if st.button("✅ تأكيد مرتجع المشتريات", key="confirm_purchase_return", type="primary"):
                            success, result, total = process_return(
                                "purchase", inv["id"], return_items,
                                return_date.strftime("%Y-%m-%d"), reason
                            )
                            if success:
                                glass(f"✅ تم تسجيل المرتجع رقم {result} - الإجمالي: {total:,.2f}")
                                st.rerun()
                            else:
                                st.error(f"فشل العملية: {result}")
    
    # ---------- سجل المرتجعات ----------
    with tab3:
        h3("سجل عمليات المرتجعات", PR)
        returns = get_return_history()
        if returns:
            df = pd.DataFrame(returns)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد مرتجعات بعد")
