# ui/fifo_ui.py – واجهة FIFO للمخزون (تصميم Dark Mode احترافي ونظيف)
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

# ========== إعدادات التصميم (Dark Mode الفخم) ==========
def apply_custom_theme():
    st.markdown("""
    <style>
        /* خلفية التطبيق العامة */
        .stApp {
            background-color: #0F172A;
        }
        
        /* تخصيص النصوص */
        h1, h2, h3, h4, h5, h6, p, span, label {
            color: #F8FAFC !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* تخصيص التبويبات (Tabs) بشكل أنيق */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #1E293B;
            border-radius: 8px 8px 0px 0px;
            padding: 10px 20px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.2);
            border: 1px solid #334155;
            border-bottom: none;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2563EB !important;
            color: white !important;
            border-color: #2563EB;
        }
        
        /* تخصيص حقول الإدخال */
        .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
            background-color: #1E293B !important;
            color: #F8FAFC !important;
            border: 1px solid #334155 !important;
            border-radius: 6px !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox div[data-baseweb="select"]:focus {
            border-color: #3B82F6 !important;
            box-shadow: 0 0 0 1px #3B82F6 !important;
        }
        
        /* تخصيص الأزرار */
        .stButton button {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.39);
        }
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5);
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
        }
        
        /* تخصيص الجداول */
        [data-testid="stDataFrame"] {
            background-color: #1E293B;
            border-radius: 8px;
            padding: 10px;
            border: 1px solid #334155;
        }
    </style>
    """, unsafe_allow_html=True)

def show():
    # تفعيل الثيم المخصص
    apply_custom_theme()

    # ترويسة الصفحة
    st.markdown("""
    <div style="margin-bottom:2rem; padding-bottom:1rem; border-bottom: 1px solid #334155; text-align:right;">
        <h1 style="font-size:2.5rem; margin:0; display: flex; align-items: center; justify-content: flex-end; gap: 10px;">
            <span>📦</span> وحدة إدارة المخزون (FIFO)
        </h1>
        <p style="color:#94A3B8 !important; font-size:1.1rem; margin-top: 5px;">
            نظام متقدم لإدارة وتقييم المخزون بطريقة الوارد أولاً صادر أولاً
        </p>
    </div>
    """, unsafe_allow_html=True)

    create_fifo_tables()
    products = get_products_for_select()

    if not products:
        st.info("💡 النظام جاهز. يرجى إضافة منتجات من وحدة إدارة المواد للبدء.")
        return

    product_dict = {p['id']: p['name'] for p in products}
    product_ids = list(product_dict.keys())

    tab1, tab2, tab3 = st.tabs(["📥 تسجيل دفعة شراء", "📤 صرف مخزني", "📊 تقرير الدفعات المتبقية"])

    with tab1:
        st.markdown("<h3 style='color:#38BDF8 !important;'>إضافة دفعة واردة للمخزون</h3>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("تحديد المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_batch_prod")
        
        col1, col2 = st.columns(2)
        qty = col1.number_input("الكمية الواردة", min_value=0.0, step=1.0)
        cost = col2.number_input("تكلفة الوحدة الإفرادية", min_value=0.0, step=0.01)
        
        col3, col4 = st.columns(2)
        bdate = col3.date_input("تاريخ الدفعة", value=date.today())
        ref = col4.text_input("رقم المرجع / الفاتورة (اختياري)")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("حفظ الدفعة في المستودع", use_container_width=True):
            if qty > 0 and cost > 0:
                success, error = add_batch(prod_id, qty, cost, bdate.strftime("%Y-%m-%d"), ref)
                if success:
                    st.success("✅ تمت إضافة الدفعة بنجاح إلى رصيد المخزون!")
                    st.rerun()
                else:
                    st.error(f"❌ حدث خطأ أثناء الحفظ: {error}")
            else:
                st.warning("⚠️ يرجى التأكد من إدخال كمية وتكلفة أكبر من الصفر.")

    with tab2:
        st.markdown("<h3 style='color:#FBBF24 !important;'>تسجيل عملية صرف (استهلاك)</h3>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("تحديد المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_consume_prod")
        
        available = sum(b["remaining"] for b in get_available_batches(prod_id))
        st.info(f"📦 **الرصيد المخزني المتاح حالياً:** {available:,.2f}")
        
        col1, col2 = st.columns(2)
        qty_consume = col1.number_input("الكمية المطلوب صرفها", min_value=0.0, step=1.0)
        cons_date = col2.date_input("تاريخ الصرف الفعلي", value=date.today(), key="fifo_consume_date")
        
        cons_ref = st.text_input("مرجع الصرف (رقم إذن الصرف / طلب المواد)", key="fifo_consume_ref")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("اعتماد الصرف المخزني", use_container_width=True):
            if qty_consume <= 0:
                st.warning("⚠️ الكمية يجب أن تكون أكبر من صفر.")
            elif qty_consume > available:
                st.error("❌ الرصيد الحالي لا يغطي الكمية المطلوبة.")
            else:
                # التعديل هنا: تمرير التاريخ المختار من الواجهة بدقة
                total_cost, error = consume_fifo(
                    product_id=prod_id, 
                    quantity=qty_consume,
                    consumption_date=cons_date.strftime("%Y-%m-%d"),
                    reference=cons_ref
                )
                
                if error:
                    st.error(f"❌ حدث خطأ أثناء الصرف: {error}")
                else:
                    st.success(f"✅ تم تنفيذ الصرف بنجاح. إجمالي التكلفة المحتسبة (FIFO): {total_cost:,.2f}")
                    st.rerun()

    with tab3:
        st.markdown("<h3 style='color:#10B981 !important;'>تفاصيل الدفعات المتبقية (التقييم)</h3>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("تحديد المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_view_prod")
        
        batches = get_available_batches(prod_id)
        if batches:
            df = pd.DataFrame(batches)
            df = df.rename(columns={
                "batch_date": "تاريخ الدفعة", 
                "remaining": "الرصيد المتبقي",
                "unit_cost": "تكلفة الوحدة", 
                "reference": "المرجع"
            })
            df["إجمالي القيمة"] = df["الرصيد المتبقي"] * df["تكلفة الوحدة"]
            
            # ترتيب الأعمدة للعرض
            display_df = df[["تاريخ الدفعة", "الرصيد المتبقي", "تكلفة الوحدة", "إجمالي القيمة", "المرجع"]]
            
            st.dataframe(
                display_df,
                use_container_width=True, 
                hide_index=True
            )
            
            total_cost = df["إجمالي القيمة"].sum()
            st.markdown(f"""
            <div style="background-color: #1E293B; padding: 15px; border-radius: 8px; border: 1px solid #334155; margin-top: 15px; text-align: left;">
                <h4 style="margin: 0; color: #10B981 !important;">إجمالي قيمة المخزون المتبقي: <strong>{total_cost:,.2f}</strong></h4>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("📭 لا توجد أرصدة متبقية لهذا المنتج في المستودع.")
