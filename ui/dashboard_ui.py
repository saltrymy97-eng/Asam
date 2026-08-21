# ui/dashboard_ui.py – لوحة معلومات ERP الفاخرة (مطابقة للهوية البصرية للنظام)
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

# ========== لوحة الألوان المعتمدة من الهوية ==========
BG_APP = "#0A0D14"          # لون الخلفية الداكن جداً
CARD_BG = "#131722"         # لون البطاقات
BORDER_COLOR = "rgba(255, 255, 255, 0.05)"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#8B92A5"
ACCENT_PURPLE = "#8A2BE2"   # لون التوهج البنفسجي

def render_clean_html(html_code: str):
    clean_lines = [line.strip() for line in html_code.splitlines() if line.strip()]
    st.markdown("".join(clean_lines), unsafe_allow_html=True)

def inject_dashboard_css():
    """CSS احترافي يطابق تصميم الواجهات المرفقة مع أنيميشن للـ 3D"""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');

    * {{ font-family: 'Tajawal', sans-serif !important; box-sizing: border-box; }}

    /* الخلفية العامة للتطبيق */
    .stApp {{
        background-color: {BG_APP} !important;
    }}

    .block-container {{ direction: rtl; text-align: right; padding-top: 2rem !important; padding-bottom: 2rem !important; }}
    div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

    /* ================= الأنيميشن (حركة الأيقونات) ================= */
    @keyframes float3d {{
        0% {{ transform: translateY(0px) scale(1); filter: drop-shadow(0px 10px 15px rgba(0,0,0,0.6)); }}
        50% {{ transform: translateY(-8px) scale(1.05); filter: drop-shadow(0px 20px 20px rgba(0,0,0,0.4)); }}
        100% {{ transform: translateY(0px) scale(1); filter: drop-shadow(0px 10px 15px rgba(0,0,0,0.6)); }}
    }}
    @keyframes pulse-glow {{
        0% {{ box-shadow: 0 0 10px rgba(138, 43, 226, 0.2); }}
        50% {{ box-shadow: 0 0 20px rgba(138, 43, 226, 0.5); }}
        100% {{ box-shadow: 0 0 10px rgba(138, 43, 226, 0.2); }}
    }}

    /* ================= بطاقة الترحيب (مطابقة لصورة 31487) ================= */
    .welcome-card {{
        background: linear-gradient(145deg, #1A1F2E 0%, {CARD_BG} 100%);
        border-radius: 20px;
        padding: 2rem;
        position: relative;
        overflow: hidden;
        border: 1px solid {BORDER_COLOR};
        box-shadow: 0 15px 35px rgba(0,0,0,0.3);
        margin-bottom: 2rem;
    }}
    
    .enterprise-badge {{
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(138, 43, 226, 0.1);
        padding: 6px 12px; border-radius: 8px;
        color: #B388FF; font-size: 0.8rem; font-weight: 700; letter-spacing: 1px;
        margin-bottom: 1rem;
    }}
    .enterprise-badge .dot {{
        width: 8px; height: 8px; background-color: #B388FF; border-radius: 50%;
        box-shadow: 0 0 8px #B388FF;
    }}
    
    .welcome-title {{
        color: {TEXT_PRIMARY}; font-size: 2.2rem; font-weight: 900; margin: 0 0 10px 0;
        text-shadow: 0 0 20px rgba(255,255,255,0.1);
    }}
    
    .welcome-subtitle {{
        color: {TEXT_SECONDARY}; font-size: 1rem; font-weight: 500; line-height: 1.6; margin: 0;
        max-width: 70%;
    }}
    
    .welcome-date {{ color: {TEXT_PRIMARY}; font-weight: 700; }}

    /* الأيقونة الزجاجية في بطاقة الترحيب */
    .glass-icon-wrapper {{
        position: absolute; bottom: 2rem; left: 2rem;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 15px;
        backdrop-filter: blur(10px);
        animation: pulse-glow 3s infinite;
    }}
    .glass-icon-wrapper img, .glass-icon-wrapper span {{
        font-size: 2.5rem; display: block;
    }}

    /* ================= بطاقات الإحصائيات (KPIs) ================= */
    .kpi-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;
    }}
    
    .kpi-card {{
        background-color: {CARD_BG};
        border-radius: 18px;
        padding: 1.5rem;
        position: relative;
        border: 1px solid {BORDER_COLOR};
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        display: flex; flex-direction: column;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        overflow: hidden;
    }}
    .kpi-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0,0,0,0.4);
        border-color: rgba(255,255,255,0.1);
    }}
    
    .kpi-title {{ color: {TEXT_SECONDARY}; font-size: 0.95rem; font-weight: 600; text-align: center; margin-bottom: 1rem; }}
    .kpi-value {{ color: {TEXT_PRIMARY}; font-size: 2rem; font-weight: 900; text-align: center; margin-bottom: 5px; }}
    .kpi-unit {{ color: {TEXT_SECONDARY}; font-size: 1rem; font-weight: 700; text-align: center; }}
    
    /* أيقونة 3D داخل البطاقة */
    .kpi-3d-icon {{
        position: absolute; bottom: 10px; left: 15px; /* وضعها في الزاوية اليسرى السفلية */
        font-size: 3rem;
        animation: float3d 4s ease-in-out infinite;
        z-index: 2;
    }}
    
    /* توهج زجاجي خلف الأيقونة */
    .kpi-glow-bg {{
        position: absolute; bottom: -10px; left: -10px;
        width: 80px; height: 80px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 70%);
        z-index: 1;
    }}

    .kpi-trend {{
        position: absolute; bottom: 15px; right: 15px;
        font-size: 0.85rem; font-weight: 800;
        padding: 4px 8px; border-radius: 6px;
        background: rgba(0,0,0,0.2);
    }}
    .trend-up {{ color: #00E676; }}
    .trend-down {{ color: #FF5252; }}

    @media (max-width: 768px) {{
        .welcome-title {{ font-size: 1.8rem; }}
        .welcome-subtitle {{ max-width: 100%; }}
        .glass-icon-wrapper {{ display: none; /* إخفاء في الشاشات الصغيرة لتوفير المساحة */ }}
        .kpi-grid {{ grid-template-columns: repeat(2, 1fr); gap: 1rem; }}
    }}
    </style>
    """
    render_clean_html(css)

def build_kpi_card(title, value, unit, icon, trend, is_up=True):
    """بناء بطاقة الإحصائيات مع الأيقونة الـ 3D المتحركة"""
    trend_class = "trend-up" if is_up else "trend-down"
    trend_arrow = "↑" if is_up else "↓"
    
    return f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-unit">{unit}</div>
        
        <div class="kpi-glow-bg"></div>
        <div class="kpi-3d-icon">{icon}</div>
        
        <div class="kpi-trend {trend_class}">{trend_arrow} {trend}</div>
    </div>
    """

def show():
    inject_dashboard_css()
    
    # محاكاة البيانات
    kpi = globals().get('get_kpi_cards', lambda: {"total_sales": 125000, "total_purchases": 45000})()
    quick = globals().get('get_quick_stats', lambda: {"today_sales": 0, "today_purchases": 0})()
    
    current_date = datetime.now().strftime("%A %d %B %Y")

    # 1. بطاقة الترحيب الفاخرة (مطابقة للصورة 31487)
    welcome_html = f"""
    <div class="welcome-card">
        <div class="enterprise-badge">
            <span class="dot"></span> ENTERPRISE HUB
        </div>
        <h1 class="welcome-title">مرحباً، مدير النظام</h1>
        <p class="welcome-subtitle">
            نظرة عامة على مؤشرات الأداء وجرد العمليات اليوم، <br>
            <span class="welcome-date">{current_date}</span>
        </p>
        <div class="glass-icon-wrapper">
            <span>📊</span>
        </div>
    </div>
    """
    render_clean_html(welcome_html)

    # 2. بطاقات الإحصائيات السريعة (3D Animated Icons)
    kpi_html = f"""
    <div class="kpi-grid">
        {build_kpi_card("مبيعات اليوم", f"{quick['today_sales']}", "ر.ي", "💰", "12%", True)}
        {build_kpi_card("مشتريات اليوم", f"{quick['today_purchases']}", "ر.ي", "🛒", "5%", False)}
        {build_kpi_card("إجمالي المبيعات", f"{kpi['total_sales']:,}", "ر.ي", "📈", "8%", True)}
        {build_kpi_card("المخزون الحالي", "342", "عنصر", "📦", "مستقر", True)}
    </div>
    """
    render_clean_html(kpi_html)

    # 3. الرسوم البيانية (متوافقة مع النسق الداكن)
    col1, col2 = st.columns(2)
    
    chart_layout_args = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TEXT_SECONDARY, family='Tajawal'),
        margin=dict(t=30, b=10, l=10, r=10)
    )

    with col1:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY}; font-size:1.2rem; margin-bottom:1rem;'>تحليل المبيعات</h3>", unsafe_allow_html=True)
        sales_data = [{'month':'يناير','total':4000}, {'month':'فبراير','total':7000}, {'month':'مارس','total':5500}]
        df_sales = pd.DataFrame(sales_data)
        fig_bar = go.Figure(data=[
            go.Bar(
                x=df_sales['month'], y=df_sales['total'],
                marker_color='#8A2BE2', # البنفسجي الخاص بالنظام
                marker_line_color='rgba(255,255,255,0.2)',
                marker_line_width=1.5,
                opacity=0.9
            )
        ])
        fig_bar.update_layout(**chart_layout_args, yaxis=dict(gridcolor=BORDER_COLOR))
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    with col2:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY}; font-size:1.2rem; margin-bottom:1rem;'>حالة المخزون</h3>", unsafe_allow_html=True)
        inv_data = [{'category':'إلكترونيات','count':120}, {'category':'أثاث','count':80}, {'category':'قرطاسية','count':142}]
        df_inv = pd.DataFrame(inv_data)
        fig_pie = px.pie(
            df_inv, names='category', values='count', hole=0.6,
            color_discrete_sequence=['#8A2BE2', '#4CAF50', '#64B5F6']
        )
        fig_pie.update_traces(
            hoverinfo='label+percent', textinfo='none',
            marker=dict(line=dict(color=CARD_BG, width=3))
        )
        fig_pie.update_layout(**chart_layout_args, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
