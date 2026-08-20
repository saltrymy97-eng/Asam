# ui/fifo_ui.py – واجهة FIFO للمخزون (متوافقة مع هوية Enterprise Hub)
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

def apply_enterprise_theme():
    """تطبيق الهوية البصرية الفاخرة المطابقة لباقي النظام"""
    st.markdown("""
    <style>
        /* إخفاء خلفية التبويبات الافتراضية المزعجة وجعلها شفافة مع خط سفلي */
        .stTabs [data-baseweb="tab-list"] {
            gap: 30px;
            background-color: transparent !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent !important;
            border: none !important;
            border-radius: 0 !important;
            padding: 10px 5px !important;
            color: #94A3B8 !important;
            font-weight: 600;
            box-shadow: none !important;
        }
        /* تصميم التبويب النشط ليطابق شاشة التسويات ومراكز التكلفة */
        .stTabs [aria-selected="true"] {
            color: #F8FAFC !important;
            border-bottom: 2px solid #EF4444 !important; /* خط سفلي أحمر/برتقالي أنيق */
        }
        .stTabs [aria-selected="true"] p {
            color: #F8FAFC !important;
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.2);
        }
        
        /* تخصيص حقول الإدخال لتكون ناعمة وداكنة */
        .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
            background-color: rgba(30, 41, 59, 0.5) !important;
            color: #F8FAFC !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 8px !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox div[data-baseweb="select"]:focus {
            border-color: #8B5CF6 !important;
            box-shadow: 0 0 0 1px rgba(139, 92, 246, 0.5) !important;
        }
        
        /* تصميم الجداول لتندمج مع الخلفية */
        [data-testid="stDataFrame"] {
            background-color: rgba(30, 41, 59, 0.3);
            border-radius: 12px;
            padding: 15px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
    """, unsafe_allow_html=True)

def show():
    # تفعيل الثيم المتناسق
    apply_enterprise_theme()

    # إنشاء بطاقة الترويسة الفاخرة (مطابقة لشاشة مراكز التكلفة)
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(26, 26, 64, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%); 
                padding: 40px 20px; 
                border-radius: 20px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.4); 
                text-align: center; 
                margin-bottom: 40px; 
                border: 1px solid rgba(139, 92, 246, 0.15);
                position: relative;
                overflow: hidden;">
        
        <!-- تأثير توهج في الخلفية -->
        <div style="position: absolute; top: -50px; left: 50%; transform: translateX(-50%); width: 200px; height: 200px; background: radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, rgba(0,0,0,0) 70%); border-radius: 50%; z-index: 0;"></div>
        
        <div style="position: relative; z-index: 1;">
            <h1 style="color: #F8FAFC; font-size: 3rem; margin: 0 0 10px 0; font-weight: bold; text-shadow: 0 0 25px rgba(139, 92, 246, 0.7);">📦 وحدة المخزون (FIFO)</h1>
            <p style="color: #94A3B8; font-size: 1.1rem; margin: 0;">نظام متقدم لإدارة وتقييم المخزون المالي بذكاء ودقة</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    create_fifo_tables()
    products = get_products_for_select()

    if not products:
        st.warning("⚠️ يرجى إضافة منتجات إلى النظام للبدء في إدارة المخزون.")
        return

    product_dict = {p['id']: p['name'] for p in products}
    product_ids = list(product_dict.keys())

    # تم تغيير الأيقونات لتكون أنظف وأكثر احترافية
    tab1, tab2, tab3 = st.tabs(["📥 تسجيل دفعة شراء", "📤 صرف مخزني", "📊 تفاصيل الدفعات (التقييم)"])

    with tab1:
        st.markdown("<h4 style='color:#38BDF8;'>إضافة رصيد وارد جديد</h4><br>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("تحديد المنتج", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_batch_prod")
        
        col1, col2 = st.columns(2)
        qty = col1.number_input("الكمية الواردة", min_value=0.0, step=1.0)
        cost = col2.number_input("تكلفة الوحدة", min_value=0.0, step=0.01)
        
        col3, col4 = st.columns(2)
        bdate = col3.date_input("تاريخ الدفعة", value=date.today())
        ref = col4.text_input("رقم المرجع (اختياري)")
        
        st.markdown("<br>", unsafe_allow_html=True)
        # زر بتصميم يتناسب مع النظام
        st.markdown("""
        <style>
        div[data-testid="stButton"] button {
            background-color: rgba(59, 130, 246, 0.1);
            color: #38BDF8;
            border: 1px solid rgba(59, 130, 246, 0.5);
            border-radius: 8px;
            padding: 10px 0;
            transition: all 0.3s ease;
        }
        div[data-testid="stButton"] button:hover {
            background-color: rgba(59, 130, 246, 0.2);
            border-color: #38BDF8;
            color: white;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if st.button("حفظ الدفعة في المستودع", use_container_width=True):
            if qty > 0 and cost > 0:
                success, error = add_batch(prod_id, qty, cost, bdate.strftime("%Y-%m-%d"), ref)
                if success:
                    st.success("✅ تمت العملية بنجاح.")
                    st.rerun()
                else:
                    st.error(f"❌ خطأ: {error}")
            else:
                st.warning("الكمية والتكلفة يجب أن تكون أكبر من الصفر.")

    with tab2:
        st.markdown("<h4 style='color:#FBBF24;'>تسجيل استهلاك / صرف</h4><br>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("تحديد المنتج للصرف", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_consume_prod")
        
        available = sum(b["remaining"] for b in get_available_batches(prod_id))
        st.info(f"📦 **الرصيد المتاح حالياً:** {available:,.2f} وحدة")
        
        col1, col2 = st.columns(2)
        qty_consume = col1.number_input("الكمية المطلوب صرفها", min_value=0.0, step=1.0)
        cons_date = col2.date_input("تاريخ الصرف", value=date.today(), key="fifo_consume_date")
        
        cons_ref = st.text_input("مرجع الصرف (رقم إذن الصرف)", key="fifo_consume_ref")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("اعتماد الصرف حسب (FIFO)", use_container_width=True):
            if qty_consume <= 0:
                st.warning("الكمية يجب أن تكون أكبر من صفر.")
            elif qty_consume > available:
                st.error("الكمية المطلوبة تتجاوز الرصيد المتاح.")
            else:
                total_cost, error = consume_fifo(
                    product_id=prod_id, 
                    quantity=qty_consume,
                    consumption_date=cons_date.strftime("%Y-%m-%d"),
                    reference=cons_ref
                )
                if error:
                    st.error(f"❌ خطأ: {error}")
                else:
                    st.success(f"✅ تم الصرف بنجاح. تكلفة البضاعة المباعة/المنصرفة: {total_cost:,.2f}")
                    st.rerun()

    with tab3:
        st.markdown("<h4 style='color:#10B981;'>تقييم الدفعات المتبقية بالمخزن</h4><br>", unsafe_allow_html=True)
        
        prod_id = st.selectbox("استعراض منتج معين", options=product_ids, format_func=lambda x: product_dict[x], key="fifo_view_prod")
        
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
            
            st.dataframe(
                df[["تاريخ الدفعة", "الرصيد المتبقي", "تكلفة الوحدة", "إجمالي القيمة", "المرجع"]],
                use_container_width=True, 
                hide_index=True
            )
            
            total_cost = df["إجمالي القيمة"].sum()
            # بطاقة إجمالي فخمة
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 20px; border-radius: 12px; margin-top: 20px; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #94A3B8; font-size: 1.2rem;">إجمالي القيمة الدفترية للمخزون:</span>
                <span style="color: #10B981; font-size: 1.8rem; font-weight: bold;">{total_cost:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("لا توجد أرصدة حالية لهذا المنتج.")
