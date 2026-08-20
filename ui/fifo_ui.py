# ui/fifo_ui.py – واجهة FIFO للمخزون (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
from datetime import date
from services.fifo_service import (
    create_fifo_tables,
    add_batch,
    get_available_batches,
    consume_fifo,
    get_products_for_select
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
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">📦 FIFO للمخزون</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة المخزون بطريقة الوارد أولاً صادر أولاً</p>
    </div>
    """, unsafe_allow_html=True)

    create_fifo_tables()
    products = get_products_for_select()

    if not products:
        st.warning("لا توجد منتجات. أضف منتجات من وحدة المخزون أولاً.")
        return

    # بناء قاموس للمنتجات (الـ ID هو المفتاح، والاسم هو القيمة) لضمان دقة العمليات
    product_dict = {p['id']: p['name'] for p in products}
    product_ids = list(product_dict.keys())

    tab1, tab2, tab3 = st.tabs(["➕ دفعات شراء", "🔄 استهلاك FIFO", "📋 الدفعات المتبقية"])

    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة دفعة شراء</h3>", unsafe_allow_html=True)
        
        # استخدام format_func لعرض الاسم برمجياً والتعامل بالـ ID
        prod_id = st.selectbox("المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_batch_prod")
        
        col1, col2 = st.columns(2)
        qty = col1.number_input("الكمية", min_value=0.0, step=1.0)
        cost = col2.number_input("تكلفة الوحدة", min_value=0.0, step=0.01)
        bdate = st.date_input("تاريخ الدفعة", value=date.today())
        ref = st.text_input("مرجع (اختياري)")
        
        if st.button("إضافة الدفعة"):
            if qty > 0 and cost > 0:
                success, error = add_batch(prod_id, qty, cost, bdate.strftime("%Y-%m-%d"), ref)
                if success:
                    st.success("تمت إضافة الدفعة بنجاح!")
                    st.rerun()
                else:
                    st.error(f"فشل: {error}")
            else:
                st.error("الكمية والتكلفة يجب أن تكون أكبر من صفر")

    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>استهلاك المخزون (FIFO)</h3>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_consume_prod")
        
        available = sum(b["remaining"] for b in get_available_batches(prod_id))
        st.write(f"**الكمية المتاحة:** {available:.2f}")
        
        qty_consume = st.number_input("الكمية المطلوب صرفها", min_value=0.0, step=1.0)
        
        # إبقاء حقل التاريخ في الواجهة لأغراض العرض أو التطوير المستقبلي،
        # علماً أن دالة الخدمة الحالية تسجل تاريخ الصرف تلقائياً بوقت العملية الفعلي.
        cons_date = st.date_input("تاريخ الصرف", value=date.today(), key="fifo_consume_date")
        cons_ref = st.text_input("مرجع الصرف", key="fifo_consume_ref")
        
        if st.button("تسجيل الصرف"):
            if qty_consume <= 0:
                st.error("الكمية يجب أن تكون أكبر من صفر")
            elif qty_consume > available:
                st.error("الكمية المطلوبة أكبر من المتاح")
            else:
                # الاستدعاء الاحترافي باستخدام Keyword Arguments لتفادي تمرير القيم بالترتيب الخاطئ
                total_cost, error = consume_fifo(
                    product_id=prod_id, 
                    quantity=qty_consume,
                    reference=cons_ref
                )
                
                if error:
                    st.error(f"فشل: {error}")
                else:
                    st.success(f"تم الصرف بنجاح. التكلفة الإجمالية المحتسبة: {total_cost:,.2f}")
                    st.rerun()

    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>الدفعات المتبقية</h3>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_view_prod")
        
        batches = get_available_batches(prod_id)
        if batches:
            df = pd.DataFrame(batches)
            df = df.rename(columns={
                "batch_date": "التاريخ", 
                "remaining": "الكمية المتبقية",
                "unit_cost": "تكلفة الوحدة", 
                "reference": "المرجع"
            })
            df["القيمة"] = df["الكمية المتبقية"] * df["تكلفة الوحدة"]
            
            st.dataframe(
                df[["التاريخ", "الكمية المتبقية", "تكلفة الوحدة", "القيمة", "المرجع"]],
                use_container_width=True, 
                hide_index=True
            )
            total_cost = df["القيمة"].sum()
            st.markdown(f"**إجمالي قيمة المخزون المتبقي: {total_cost:,.2f}**")
        else:
            st.info("لا توجد دفعات متبقية لهذا المنتج في المخزون.")
