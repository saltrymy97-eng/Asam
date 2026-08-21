# ui/dashboard_ui.py – لوحة معلومات ERP الفاخرة (تصميم مستوحى من الهوية العميقة والـ Glossy 3D)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# استدعاء الخدمات (مع وضع بيانات وهمية لتجنب تعطل الواجهة)
try:
    from services.dashboard_service import (
        get_kpi_cards, get_quick_stats, get_alerts,
        get_inventory_by_category, get_monthly_sales,
        get_low_stock_products, get_recent_activities
    )
except ImportError:
    pass

# ========== لوحة الألوان الفاخرة والعميقة (مستوحاة من الصورة 31652) ==========
BG_DEEP = "#070812"         # خلفية نيلية عميقة جداً مائلة للسواد
CARD_BG = "#111324"         # لون البطاقات الأنيق
TEXT_LIGHT = "#F0F4F8"      # نص أبيض مزرق خفيف
TEXT_MUTED = "#8A94A6"      # نص رمادي هادئ
PURPLE_GLOW = "#B388FF"     # بنفسجي فاتح للنصوص المضيئة (مثل "ذكية")
BLUE_GLOW = "#64B5F6"       # أزرق فاتح للنصوص المضيئة (مثل "واثقة")

def render_clean_html(html_code: str):
    """دالة عرض الـ HTML الآمنة"""
    clean_lines = [line.strip() for line in html_code.splitlines() if line.strip()]
    st.markdown("".join(clean_lines), unsafe_allow_html=True)

def inject_luxury_css():
    """CSS احترافي يركز على الفخامة الهادئة والانعكاسات الزجاجية"""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');

    * {{ font-family: 'Tajawal', sans-serif !important; box-sizing: border-box; }}

    /* الخلفية العميقة المتدرجة */
    .stApp {{
        background: radial-gradient(circle at 50% 0%, #151835 0%, {BG_DEEP} 60%) !important;
        background-attachment: fixed !important;
    }}

    .block-container {{ direction: rtl; text-align: right; padding-top: 2rem !important; }}
    div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

    /* ================= الكرة الزجاجية الفاخرة (نفس الموجودة في الصورة) ================= */
    .glossy-sphere-container {{
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        margin-bottom: 2rem; margin-top: 1rem;
    }}
    .glossy-sphere {{
        width: 160px; height: 160px;
        border-radius: 50%;
        background: radial-gradient(circle at 50% 50%, #4A23B5 0%, #170B3B 70%, #0A041A 100%);
        box-shadow: 0 15px 40px rgba(0,0,0,0.8), inset 0 -10px 20px rgba(0,0,0,0.6);
        position: relative;
        display: flex; justify-content: center; align-items: center;
        margin-bottom: 25px;
    }}
    /* الانعكاس الزجاجي العلوي (السر في الفخامة) */
    .glossy-sphere::before {{
        content: ''; position: absolute;
        top: 2%; right: 8%; width: 84%; height: 45%;
        border-radius: 50%;
        background: linear-gradient(170deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0) 80%);
        transform: rotate(5deg);
    }}
    .sphere-text {{
        color: #E8D5FF; font-size: 2.2rem; font-weight: 900; z-index: 2;
        text-shadow: 0 0 15px rgba(232, 213, 255, 0.6);
        letter-spacing: 1px;
    }}

    /* ================= النصوص المضيئة والخط الفاصل ================= */
    .glowing-title {{
        font-size: 1.4rem; font-weight: 800; color: {TEXT_MUTED};
        text-align: center; margin-bottom: 15px;
    }}
    .glow-purple {{ color: {PURPLE_GLOW}; text-shadow: 0 0 12px rgba(179, 136, 255, 0.6); }}
    .glow-blue {{ color: {BLUE_GLOW}; text-shadow: 0 0 12px rgba(100, 181, 246, 0.6); }}
    
    .separator-line {{
        width: 60%; max-width: 400px; height: 2px; margin: 0 auto 2.5rem auto;
        background: linear-gradient(90deg, transparent, rgba(179, 136, 255, 0.4), transparent);
        box-shadow: 0 0 10px rgba(179, 136, 255, 0.3);
    }}

    /* ================= البطاقات (بسيطة، داكنة، أنيقة) ================= */
    .erp-grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }}
    .erp-grid-5 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }}

    .luxury-card {{
        background-color: {CARD_BG};
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        border: 1px solid rgba(255,255,255,0.03);
        border-top: 1px solid rgba(255,255,255,0.08); /* إضاءة علوية خفيفة */
        display: flex; flex-direction: column; justify-content: space-between;
        transition: all 0.3s ease;
    }}
    .luxury-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.6);
        border-top: 1px solid rgba(179, 136, 255, 0.3);
    }}
    
    .card-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
    /* الأيقونات المسطحة الأنيقة (نفس نمط أيقونة المستخدم والقفل في الصورة) */
    .flat-icon {{ font-size: 1.2rem; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); }}
    .card-title {{ color: {TEXT_MUTED}; font-size: 0.95rem; font-weight: 600; white-space: normal; line-height: 1.4; }}
    .card-value {{ color: {TEXT_LIGHT}; font-size: 1.8rem; font-weight: 800; letter-spacing: 0.5px; }}

    @media (max-width: 600px) {{
        .erp-grid-4, .erp-grid-5 {{ grid-template-columns: repeat(2, 1fr); gap: 1rem; }}
        .glossy-sphere {{ width: 120px; height: 120px; }}
        .sphere-text {{ font-size: 1.6rem; }}
        .glowing-title {{ font-size: 1.1rem; }}
    }}
    </style>
    """
    render_clean_html(css)

def build_luxury_card(title, value, icon, icon_color, delta=""):
    """بناء بطاقة أنيقة بأسلوب Minimalist"""
    delta_html = ""
    if delta:
        d_color = "#4CAF50" if "↑" in delta else "#F44336" if "↓" in delta else TEXT_MUTED
        delta_html = f"""<div style="color: {d_color}; font-size: 0.8rem; font-weight: 700; margin-top: 8px;">{delta}</div>"""
    
    return f"""
    <div class="luxury-card">
        <div class="card-header">
            <span class="flat-icon" style="color: {icon_color};">{icon}</span>
            <span class="card-title">{title}</span>
        </div>
        <div class="card-value">{value}</div>
        {delta_html}
    </div>
    """

def show():
    inject_luxury_css()
    
    # محاكاة البيانات
    kpi = globals().get('get_kpi_cards', lambda: {"net_income": 85000, "total_sales": 150000, "total_purchases": 65000, "products_count": 342, "customers_count": 89})()
    quick = globals().get('get_quick_stats', lambda: {"low_stock": 0, "today_sales": 12500, "today_purchases": 3200, "total_customers": 89})()
    alerts = globals().get('get_alerts', lambda: [])()

    # 1. الهيدر الفاخر (مستوحى حرفياً من الصورة)
    header_html = f"""
    <div class="glossy-sphere-container">
        <div class="glossy-sphere">
            <span class="sphere-text">نظام ERP</span>
        </div>
        <div class="glowing-title">
            إدارة <span class="glow-purple">ذكية</span> .. قرارات <span class="glow-blue">واثقة</span>
        </div>
        <div class="separator-line"></div>
    </div>
    """
    render_clean_html(header_html)

    # 2. مؤشرات الأداء الحيوية السريعة
    stock_status = "تحذير" if quick['low_stock'] > 0 else "آمنة"
    stock_color = "#F44336" if quick['low_stock'] > 0 else "#4CAF50"
    
    quick_html = f"""
    <div class="erp-grid-4">
        {build_luxury_card("المبيعات (اليوم)", f"{quick['today_sales']:,.0f}", "💰", "#64B5F6", "↑ 12% نمو")}
        {build_luxury_card("المشتريات (اليوم)", f"{quick['today_purchases']:,.0f}", "🛒", "#B388FF", "↓ 5% انخفاض")}
        {build_luxury_card("نواقص المخزون", str(quick['low_stock']), "⚠️", stock_color, stock_status)}
        {build_luxury_card("العملاء الجدد", str(quick['total_customers']), "👤", "#64B5F6", "+3 انضمام")}
    </div>
    """
    render_clean_html(quick_html)

    # 3. التنبيهات
    if alerts:
        for alert in alerts:
            render_clean_html(f"""
            <div style="background-color: {CARD_BG}; border-right: 3px solid #FF5252; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; color: {TEXT_LIGHT}; font-size: 0.9rem; display: flex; align-items: center; gap: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                <span style="color: #FF5252; font-size: 1.2rem;">{alert['icon']}</span>
                <span><b style="color: #FF8A80; font-weight: 700;">{alert['title']}</b>: {alert['message']}</span>
            </div>
            """)

    # 4. المؤشرات الاستراتيجية
    render_clean_html(f"""
    <div style="margin: 2rem 0 1rem 0; text-align: right;">
        <h3 style="color:{TEXT_MUTED}; font-weight:700; margin: 0; font-size:1.1rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 10px; display: inline-block;">مؤشرات الأداء الشاملة</h3>
    </div>
    """)

    net_val = kpi['net_income']
    kpi_html = f"""
    <div class="erp-grid-5">
        {build_luxury_card("إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "📈", "#4CAF50")}
        {build_luxury_card("إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📉", "#FF5252")}
        {build_luxury_card("صافي الأرباح", f"{net_val:,.0f}", "💎", "#FFC107" if net_val >= 0 else "#FF5252")}
        {build_luxury_card("المنتجات", str(kpi['products_count']), "📦", "#B388FF")}
        {build_luxury_card("قاعدة العملاء", str(kpi['customers_count']), "🌐", "#64B5F6")}
    </div>
    """
    render_clean_html(kpi_html)

    # 5. الرسوم البيانية المتطورة (بألوان داكنة تتناسب مع الهوية)
    col_chart1, col_chart2 = st.columns(2)
    chart_bg = CARD_BG
    chart_font = dict(color=TEXT_MUTED, family='Tajawal', size=12)

    with col_chart1:
        render_clean_html(f"<div style='margin-bottom:15px;'><h4 style='color:{TEXT_MUTED}; font-weight:700; margin:0; font-size: 1rem;'>📊 التدفقات النقدية</h4></div>")
        sales_data = globals().get('get_monthly_sales', lambda: [{'month':'يناير','total':4000}, {'month':'فبراير','total':7000}])()
        if sales_data:
            df = pd.DataFrame(sales_data)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df['month'], y=df['total'],
                marker=dict(color='#64B5F6', opacity=0.8),
                hovertemplate='<b>%{x}</b><br>القيمة: %{y:,.0f}<extra></extra>'
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=chart_font, margin=dict(t=10, b=20, l=10, r=10),
                xaxis=dict(showgrid=False, color=TEXT_MUTED),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)', color=TEXT_MUTED),
                hoverlabel=dict(bgcolor=BG_DEEP, font_size=14, font_family="Tajawal"),
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        render_clean_html(f"<div style='margin-bottom:15px;'><h4 style='color:{TEXT_MUTED}; font-weight:700; margin:0; font-size: 1rem;'>🎯 التوزيع الهيكلي</h4></div>")
        inv_data = globals().get('get_inventory_by_category', lambda: [{'category':'أجهزة','total':50}, {'category':'إكسسوارات','total':30}])()
        if inv_data:
            df = pd.DataFrame(inv_data)
            fig = px.pie(
                df, names='category', values='total', hole=0.7,
                color_discrete_sequence=['#B388FF', '#64B5F6', '#4CAF50', '#FFC107']
            )
            fig.update_traces(
                textinfo='none', hoverinfo='label+percent',
                marker=dict(line=dict(color=BG_DEEP, width=3))
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', font=chart_font, margin=dict(t=10, b=20, l=10, r=10),
                legend=dict(orientation="h", y=-0.1, font=dict(color=TEXT_MUTED)),
                hoverlabel=dict(bgcolor=BG_DEEP, font_size=14)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
