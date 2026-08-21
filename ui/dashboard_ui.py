# ui/dashboard_ui.py – لوحة التحكم الفاخرة (متوافقة مع الهاتف + القائمة الجانبية الأصلية)
import pandas as pd
import plotly.express as px
import streamlit as st

def inject_premium_mobile_css():
    """CSS احترافي يضمن تجاوب الهاتف واستنساخ تصميم القائمة الجانبية بدقة"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');

    * { font-family: 'Tajawal', sans-serif !important; box-sizing: border-box; }

    /* ================= الخلفية الرئيسية ================= */
    .stApp {
        background-color: #05070A !important;
        background-image: 
            radial-gradient(circle at 50% 0%, rgba(147, 51, 234, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 50% 100%, rgba(212, 175, 55, 0.1) 0%, transparent 50%) !important;
        background-attachment: fixed;
    }

    .block-container {
        direction: rtl; text-align: right;
        padding: 1rem 0.8rem !important;
        max-width: 1400px;
    }
    #MainMenu, footer, header { visibility: hidden; display: none; }

    /* ================= تصميم القائمة الجانبية (مطابق للصورة 31583.png) ================= */
    [data-testid="stSidebar"] {
        background-color: #0A0D14 !important; /* لون الخلفية الكحلي الداكن */
        border-left: 1px solid rgba(255,255,255,0.05);
    }
    
    /* تنسيق صناديق القائمة الجانبية (Expanders) */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #121723 !important; /* لون الصندوق الداكن */
        border: 1px solid rgba(255,255,255,0.03) !important;
        border-radius: 16px !important;
        margin-bottom: 0.8rem;
        overflow: hidden;
    }
    
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: transparent !important;
        color: #A855F7 !important; /* لون النص البنفسجي */
        font-weight: 700;
        font-size: 1rem;
        padding: 0.8rem 1rem !important;
    }
    
    /* تنسيق الأزرار داخل القائمة الجانبية */
    [data-testid="stSidebar"] .stButton > button {
        background-color: rgba(255,255,255,0.05) !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px;
        text-align: right;
        justify-content: flex-start;
        padding: 0.5rem 1rem;
        margin-bottom: 5px;
        transition: all 0.3s ease;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: rgba(147, 51, 234, 0.3) !important;
        border-color: #A855F7 !important;
    }
    
    /* زر مفعل (Active) في القائمة */
    .sidebar-active-btn > button {
        background-color: rgba(147, 51, 234, 0.15) !important;
        border: 1px solid rgba(147, 51, 234, 0.5) !important;
        color: #FFFFFF !important;
    }

    /* ================= تصميم محتوى الصفحة والتجاوب مع الهاتف ================= */
    .dash-title {
        color: #FFFFFF;
        font-size: clamp(1.5rem, 5vw, 2.8rem); /* تصغير تلقائي في الهاتف */
        font-weight: 900;
        margin: 0 0 5px 0;
    }
    .dash-subtitle { color: #D4AF37; font-size: clamp(0.9rem, 3vw, 1.1rem); margin-bottom: 20px; }

    /* شريط الأزرار السريعة */
    .quick-nav {
        display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px;
    }
    .quick-btn {
        flex: 1 1 calc(50% - 8px); /* زرين في كل صف على الهاتف */
        background: rgba(18, 23, 35, 0.6);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px; padding: 12px;
        color: #FFF; font-weight: 700; text-align: center;
        font-size: 0.9rem; transition: 0.3s; cursor: pointer;
    }
    .quick-btn.active {
        background: linear-gradient(135deg, #D4AF37, #B48600);
        color: #000; box-shadow: 0 0 15px rgba(212, 175, 55, 0.3);
    }

    /* شبكة البطاقات المالية */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); /* تتكيف مع الهاتف */
        gap: 12px; margin-bottom: 20px;
    }
    .kpi-card {
        background: rgba(18, 23, 35, 0.55);
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px; padding: 16px;
    }

    /* الجداول في الهاتف تصبح بطاقات عمودية */
    .record-row {
        display: flex; flex-direction: column; gap: 8px;
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 12px; padding: 15px; margin-bottom: 10px;
    }

    /* شاشات الكمبيوتر والتابلت */
    @media (min-width: 768px) {
        .quick-btn { flex: 0 1 auto; min-width: 150px; }
        .kpi-grid { grid-template-columns: repeat(4, 1fr); gap: 20px; }
        .record-row { flex-direction: row; justify-content: space-between; align-items: center; }
    }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    """هيكلة القائمة الجانبية بناءً على الصورة المرفقة"""
    with st.sidebar:
        # ترويسة النظام
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h1 style="color: #FFFFFF; margin:0; font-size: 2rem; font-weight: 900; text-shadow: 0 0 10px rgba(168,85,247,0.5);">ERP حوكمة</h1>
            <p style="color: #64748B; font-size: 0.9rem; margin-top: 5px;">إدارة ذكية .. قرارات واثقة</p>
        </div>
        <hr style="border-color: rgba(255,255,255,0.1); margin-bottom: 1.5rem;">
        """, unsafe_allow_html=True)

        # 1. الرئيسية
        with st.expander("🏠 الرئيسية", expanded=True):
            st.markdown('<div class="sidebar-active-btn">', unsafe_allow_html=True)
            st.button("📊 لوحة المعلومات", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # 2. العمليات
        with st.expander("📦 العمليات"):
            st.button("سجل العمليات", use_container_width=True)
            st.button("الاعتمادات", use_container_width=True)

        # 3. مخزون (هنا تم إضافة إدارة الوحدات)
        with st.expander("📦 مخزون"):
            st.button("إدارة الأصناف", use_container_width=True)
            st.button("📐 إدارة الوحدات", use_container_width=True) # <-- المكان المطلوب
            st.button("التسويات الجردية", use_container_width=True)

        # 4. المحاسبة والمالية
        with st.expander("💰 المحاسبة والمالية"):
            st.button("الصندوق والخزينة", use_container_width=True)
            st.button("فروق الصرف", use_container_width=True)

        # 5. إدارة الأعمال
        with st.expander("👥 إدارة الأعمال"):
            st.button("الموظفين", use_container_width=True)

        # 6. النظام والأمان
        with st.expander("⚙️ النظام والأمان"):
            st.button("الصلاحيات", use_container_width=True)

        # 7. الذكاء الاصطناعي
        with st.expander("🤖 الذكاء الاصطناعي"):
            st.button("المساعد الذكي", use_container_width=True)

def show():
    inject_premium_mobile_css()
    render_sidebar()

    # محتوى الصفحة الرئيسية مجهز للهاتف والكمبيوتر
    st.markdown("""
    <div>
        <h1 class="dash-title">مركز التحكم الاستراتيجي</h1>
        <div class="dash-subtitle">نظرة مالية ومخزنية شاملة • 2026</div>
    </div>
    
    <div class="quick-nav">
        <div class="quick-btn active">💰 الصندوق</div>
        <div class="quick-btn">📦 التسويات</div>
        <div class="quick-btn">🔀 فروق الصرف</div>
        <div class="quick-btn">🏛️ الحوكمة</div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div style="color: #64748B; font-size: 0.8rem; font-weight: 700;">السيولة المتاحة</div>
            <div style="color: #FFF; font-size: 1.4rem; font-weight: 900; margin: 5px 0;">185,400 <span style="font-size:0.8rem; color:#D4AF37;">YER</span></div>
            <div style="color: #10B981; font-size: 0.75rem;">↑ 5.4% نمو</div>
        </div>
        <div class="kpi-card">
            <div style="color: #64748B; font-size: 0.8rem; font-weight: 700;">عمليات اليوم</div>
            <div style="color: #FFF; font-size: 1.4rem; font-weight: 900; margin: 5px 0;">24 <span style="font-size:0.8rem; color:#A855F7;">عملية</span></div>
            <div style="color: #3B82F6; font-size: 0.75rem;">معدل طبيعي</div>
        </div>
        <div class="kpi-card">
            <div style="color: #64748B; font-size: 0.8rem; font-weight: 700;">تسويات معلقة</div>
            <div style="color: #EF4444; font-size: 1.4rem; font-weight: 900; margin: 5px 0;">3 <span style="font-size:0.8rem; color:#EF4444;">أصناف</span></div>
            <div style="color: #EF4444; font-size: 0.75rem;">إجراء فوري</div>
        </div>
        <div class="kpi-card">
            <div style="color: #64748B; font-size: 0.8rem; font-weight: 700;">فروق العملات</div>
            <div style="color: #FFF; font-size: 1.4rem; font-weight: 900; margin: 5px 0;">-5,450 <span style="font-size:0.8rem; color:#D4AF37;">SAR</span></div>
            <div style="color: #A855F7; font-size: 0.75rem;">معالجة آلية</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # رسم بياني يتكيف مع الهاتف (نصغّر الارتفاع على الشاشات الصغيرة)
    st.markdown("<h4 style='color:#FFF; font-weight:800; font-size:1.1rem; margin-top:1rem;'>📈 التدفقات النقدية</h4>", unsafe_allow_html=True)
    df = pd.DataFrame({'اليوم': ['السبت', 'الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء'], 'المبلغ': [12, 19, 15, 28, 34]})
    fig = px.line(df, x='اليوم', y='المبلغ', markers=True)
    fig.update_traces(line=dict(color='#A855F7', width=3), marker=dict(size=8, color='#D4AF37'))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#64748B', size=11), margin=dict(t=10, b=10, l=0, r=0), height=200,
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # جدول العمليات (مبني بـ CSS Flexbox ليتغير شكله تلقائياً في الهاتف)
    st.markdown("""
    <div style="margin-top: 1rem;">
        <h4 style="color:#FFF; font-weight:800; font-size:1.1rem; margin-bottom:15px;">سجل العمليات الحديثة</h4>
        
        <div class="record-row">
            <div style="color: #64748B; font-size: 0.85rem;">#REC-010000</div>
            <div style="color: #FFF; font-weight: 700;">تسوية عجز مخزني</div>
            <div style="color: #EF4444; font-weight: 800; direction: ltr;">- 100.00 SAR</div>
        </div>

        <div class="record-row">
            <div style="color: #64748B; font-size: 0.85rem;">#REC-010002</div>
            <div style="color: #FFF; font-weight: 700;">إعادة تقييم عملة</div>
            <div style="color: #10B981; font-weight: 800; direction: ltr;">+ 450.00 USD</div>
        </div>
        
        <div class="record-row">
            <div style="color: #64748B; font-size: 0.85rem;">#REC-010005</div>
            <div style="color: #FFF; font-weight: 700;">حركة صندوق منصرفة</div>
            <div style="color: #D4AF37; font-weight: 800; direction: ltr;">- 5,000.00 YER</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
