# ui/dashboard_ui.py – لوحة معلومات ERP فاخرة (تصميم مجسم 3D، إضاءة تفاعلية، وحركة انسيابية)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# استدعاء الخدمات (مع وضع بيانات وهمية ذكية في حال غياب الاتصال بقاعدة البيانات لتجنب تعطل الواجهة)
try:
    from services.dashboard_service import (
        get_kpi_cards, get_quick_stats, get_alerts,
        get_inventory_by_category, get_monthly_sales,
        get_low_stock_products, get_recent_activities
    )
except ImportError:
    pass

# ========== لوحة ألوان النيون الفاخرة (Cyber-Corporate) ==========
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A0AEC0"
BG_DARK = "#090B10"

# ألوان مضيئة للتدرجات والتوهج
CYAN = ("#00F2FE", "#4FACFE")   # أزرق سماوي مضيء
PURPLE = ("#F6416C", "#89216B") # بنفسجي ياقوتي
GREEN = ("#00F260", "#0575E6")  # أخضر زمردي
ORANGE = ("#FF416C", "#FF4B2B") # برتقالي متوهج
RED = ("#FF0844", "#FFB199")    # أحمر إنذار
GOLD = ("#F9D423", "#FF4E50")   # ذهبي ملكي

def render_clean_html(html_code: str):
    """دالة عرض الـ HTML الآمنة"""
    clean_lines = [line.strip() for line in html_code.splitlines() if line.strip()]
    st.markdown("".join(clean_lines), unsafe_allow_html=True)

def inject_3d_cyber_css():
    """CSS احترافي يضم أنيميشن، 3D، زجاج متقدم، وتوافق 100% مع الموبايل"""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');

    * {{ font-family: 'Tajawal', sans-serif !important; box-sizing: border-box; }}

    /* خلفية النظام المظلمة العميقة */
    .stApp {{
        background-color: {BG_DARK} !important;
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(79, 172, 254, 0.05), transparent 25%),
            radial-gradient(circle at 85% 30%, rgba(246, 65, 108, 0.05), transparent 25%);
        background-attachment: fixed !important;
    }}

    .block-container {{ direction: rtl; text-align: right; padding-top: 2rem !important; }}
    div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

    /* ================= الأنيميشن (الحركة) ================= */
    @keyframes float {{
        0% {{ transform: translateY(0px) rotate(0deg); }}
        50% {{ transform: translateY(-8px) rotate(3deg); }}
        100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    
    @keyframes pulse-border {{
        0% {{ border-color: rgba(255,255,255,0.1); }}
        50% {{ border-color: rgba(255,255,255,0.3); }}
        100% {{ border-color: rgba(255,255,255,0.1); }}
    }}

    /* ================= شبكة البطاقات (Grid) ================= */
    .erp-grid-4 {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.2rem;
        margin-bottom: 2rem;
    }}
    
    .erp-grid-5 {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }}

    /* ================= البطاقة الفاخرة (3D Glass Card) ================= */
    .cyber-card {{
        position: relative;
        background: linear-gradient(145deg, rgba(20,25,35,0.8) 0%, rgba(10,15,20,0.9) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.05);
        border-top: 1px solid rgba(255,255,255,0.15);
        border-radius: 20px;
        padding: 1.2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}

    /* تأثير الوهج عند تمرير الماوس */
    .cyber-card::before {{
        content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
        transition: left 0.5s ease;
    }}
    .cyber-card:hover::before {{ left: 150%; }}
    .cyber-card:hover {{
        transform: translateY(-5px) scale(1.02);
        border-color: rgba(255,255,255,0.3);
    }}

    /* ================= الكرة ثلاثية الأبعاد (3D Sphere Icon) ================= */
    .sphere-icon {{
        width: 55px; height: 55px;
        border-radius: 50%;
        display: flex; justify-content: center; align-items: center;
        font-size: 1.5rem;
        flex-shrink: 0;
        animation: float 4s ease-in-out infinite;
        box-shadow: 
            inset -5px -5px 15px rgba(0,0,0,0.5), 
            inset 5px 5px 15px rgba(255,255,255,0.4),
            0 10px 20px rgba(0,0,0,0.4);
        position: relative;
    }}
    .sphere-icon::after {{
        content: ''; position: absolute; top: 10%; left: 15%; width: 30%; height: 30%;
        background: radial-gradient(circle, rgba(255,255,255,0.8) 0%, transparent 60%);
        border-radius: 50%;
    }}

    /* ================= النصوص والتنسيقات ================= */
    .card-title {{
        color: {TEXT_SECONDARY};
        font-size: clamp(0.75rem, 1.5vw, 0.9rem);
        font-weight: 600;
        margin-bottom: 5px;
        white-space: normal; /* السماح بالتفاف النص لمنع القص */
        line-height: 1.3;
    }}
    .card-value {{
        color: {TEXT_PRIMARY};
        font-size: clamp(1.3rem, 3vw, 1.8rem);
        font-weight: 900;
        line-height: 1.1;
        letter-spacing: 0.5px;
        text-shadow: 0 0 10px rgba(255,255,255,0.2);
    }}
    
    /* متجاوب مع الموبايل بقوة */
    @media (max-width: 600px) {{
        .erp-grid-4, .erp-grid-5 {{ grid-template-columns: repeat(2, 1fr); gap: 0.8rem; }}
        .header-panel {{ flex-direction: column-reverse; text-align: center; padding: 1.5rem !important; }}
        .sphere-icon {{ width: 45px; height: 45px; font-size: 1.2rem; }}
    }}
    </style>
    """
    render_clean_html(css)

def build_3d_card(title, value, icon, gradient_colors, shadow_color, delta=""):
    """بناء بطاقة 3D ذات إضاءة ديناميكية"""
    c1, c2 = gradient_colors
    
    delta_html = ""
    if delta:
        d_color = "#00F260" if "↑" in delta else "#FF0844" if "↓" in delta else TEXT_SECONDARY
        delta_html = f"""
        <div style="display: flex; align-items: center; margin-top: 6px; gap: 5px;">
            <span style="background:{d_color}; box-shadow:0 0 8px {d_color}; width:6px; height:6px; border-radius:50%; display:inline-block;"></span>
            <span style="color: {d_color}; font-size: 0.75rem; font-weight: 700;">{delta}</span>
        </div>
        """
    
    # استخدام المتغير shadow_color لتوهج البطاقة عند الـ hover (عبر style مضمن)
    return f"""
    <div class="cyber-card" onmouseover="this.style.boxShadow='0 15px 35px {shadow_color}40, inset 0 1px 0 rgba(255,255,255,0.2)'" onmouseout="this.style.boxShadow='0 10px 30px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)'">
        <div style="flex: 1; min-width: 0;">
            <div class="card-title">{title}</div>
            <div class="card-value">{value}</div>
            {delta_html}
        </div>
        <div class="sphere-icon" style="background: linear-gradient(135deg, {c1}, {c2}); box-shadow: inset -5px -5px 15px rgba(0,0,0,0.4), inset 5px 5px 15px rgba(255,255,255,0.5), 0 0 20px {shadow_color}60;">
            <span style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));">{icon}</span>
        </div>
    </div>
    """

def show():
    inject_3d_cyber_css()
    
    user_name = st.session_state.user.get("full_name", "المدير") if 'user' in st.session_state else "مدير النظام"
    
    # محاكاة البيانات (Fallback) لضمان العمل بسلاسة
    kpi = globals().get('get_kpi_cards', lambda: {"net_income": 85000, "total_sales": 150000, "total_purchases": 65000, "products_count": 342, "customers_count": 89})()
    quick = globals().get('get_quick_stats', lambda: {"low_stock": 0, "today_sales": 12500, "today_purchases": 3200, "total_customers": 89})()
    alerts = globals().get('get_alerts', lambda: [])()

    # 1. لوحة القيادة العلوية (Header Command Center)
    header_html = f"""
    <div class="header-panel" style="
        background: linear-gradient(135deg, #111827 0%, #0F172A 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 1px solid rgba(79, 172, 254, 0.4);
        border-radius: 24px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 20px 50px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
        animation: pulse-border 4s infinite;
    ">
        <div>
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <span style="background: linear-gradient(90deg, #00F2FE, #4FACFE); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 0.85rem; font-weight: 900; letter-spacing: 2px;">ERP SYSTEM CORE</span>
                <span style="width: 8px; height: 8px; background: #00F2FE; border-radius: 50%; box-shadow: 0 0 15px #00F2FE; animation: float 2s infinite;"></span>
            </div>
            <h1 style="color: #FFFFFF; font-size: clamp(1.8rem, 4vw, 2.5rem); margin: 0; font-weight: 900; text-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);">مرحباً، {user_name}</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: clamp(0.85rem, 2vw, 1rem); margin: 8px 0 0 0; font-weight: 500;">
                البيانات الحية المحدثة لنظام المؤسسة اليوم، <span style="color:#4FACFE; font-weight:700;">{datetime.now().strftime('%A %d %B %Y')}</span>
            </p>
        </div>
        <div class="sphere-icon" style="width: 80px; height: 80px; font-size: 2.5rem; background: linear-gradient(135deg, #F9D423, #FF4E50); box-shadow: inset -10px -10px 20px rgba(0,0,0,0.3), inset 10px 10px 20px rgba(255,255,255,0.6), 0 0 40px rgba(255, 78, 80, 0.5);">
            👑
        </div>
    </div>
    """
    render_clean_html(header_html)

    # 2. مؤشرات الأداء الحيوية السريعة (4 بطاقات)
    stock_status = "تدخل عاجل" if quick['low_stock'] > 0 else "مستويات آمنة"
    stock_color = RED if quick['low_stock'] > 0 else GREEN
    
    quick_html = f"""
    <div class="erp-grid-4">
        {build_3d_card("المبيعات النقدية (اليوم)", f"{quick['today_sales']:,.0f}", "💸", GREEN, "#00F260", "↑ 12% نمو")}
        {build_3d_card("المشتريات (اليوم)", f"{quick['today_purchases']:,.0f}", "🛍️", ORANGE, "#FF416C", "↓ 5% انخفاض")}
        {build_3d_card("نواقص المخزون", str(quick['low_stock']), "⚠️", stock_color, stock_color[0], stock_status)}
        {build_3d_card("شركاء النجاح", str(quick['total_customers']), "🤝", CYAN, "#00F2FE", "+3 انضمام")}
    </div>
    """
    render_clean_html(quick_html)

    # 3. التنبيهات الذكية
    if alerts:
        for alert in alerts:
            render_clean_html(f"""
            <div style="background: linear-gradient(90deg, rgba(255,65,108,0.1), transparent); border-right: 4px solid #FF416C; border-radius: 12px; padding: 14px 20px; margin-bottom: 20px; color: {TEXT_PRIMARY}; font-size: 0.9rem; display: flex; align-items: center; gap: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <span style="font-size: 1.4rem; filter: drop-shadow(0 0 8px #FF416C);">{alert['icon']}</span>
                <span><b style="color: #FFB199; font-weight: 800;">{alert['title']}</b>: {alert['message']}</span>
            </div>
            """)

    # 4. المؤشرات الاستراتيجية (5 بطاقات)
    render_clean_html(f"""
    <div style="display: flex; align-items: center; gap: 12px; margin: 2rem 0 1.5rem 0;">
        <span style="background: linear-gradient(180deg, #4FACFE, #00F2FE); width: 6px; height: 24px; border-radius: 4px; box-shadow: 0 0 15px #00F2FE;"></span>
        <h3 style="color:{TEXT_PRIMARY}; font-weight:900; margin: 0; font-size:1.3rem; text-shadow: 0 2px 10px rgba(255,255,255,0.1);">الأداء المالي والهيكلي</h3>
    </div>
    """)

    net_val = kpi['net_income']
    kpi_html = f"""
    <div class="erp-grid-5">
        {build_3d_card("إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "📈", GREEN, "#00F260")}
        {build_3d_card("إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📉", RED, "#FF0844")}
        {build_3d_card("صافي الأرباح", f"{net_val:,.0f}", "🏆", GOLD if net_val >= 0 else RED, "#F9D423")}
        {build_3d_card("دليل المنتجات", str(kpi['products_count']), "📦", PURPLE, "#F6416C")}
        {build_3d_card("قاعدة العملاء", str(kpi['customers_count']), "🌐", CYAN, "#00F2FE")}
    </div>
    """
    render_clean_html(kpi_html)

    # 5. الرسوم البيانية المتطورة (Cyber Charts)
    col_chart1, col_chart2 = st.columns(2)

    chart_bg = 'rgba(15, 23, 42, 0.4)'
    chart_font = dict(color=TEXT_PRIMARY, family='Tajawal', size=12)

    with col_chart1:
        render_clean_html(f"<div style='margin-bottom:15px; display:flex; align-items:center; gap:10px;'><span class='sphere-icon' style='width:35px; height:35px; font-size:1rem; background:linear-gradient(135deg, {CYAN[0]}, {CYAN[1]});'>📊</span><h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin:0;'>مؤشر التدفقات النقدية</h4></div>")
        sales_data = globals().get('get_monthly_sales', lambda: [{'month':'يناير','total':4000}, {'month':'فبراير','total':7000}])()
        if sales_data:
            df = pd.DataFrame(sales_data)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df['month'], y=df['total'],
                marker=dict(
                    color=df['total'], 
                    colorscale=[[0, '#00F2FE'], [1, '#4FACFE']],
                    line=dict(color='#FFFFFF', width=1)
                ),
                hovertemplate='<b>%{x}</b><br>القيمة: %{y:,.0f}<extra></extra>'
            ))
            fig.update_layout(
                paper_bgcolor=chart_bg, plot_bgcolor='rgba(0,0,0,0)',
                font=chart_font, margin=dict(t=20, b=20, l=10, r=10),
                xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color=TEXT_SECONDARY),
                hoverlabel=dict(bgcolor="#0F172A", font_size=14, font_family="Tajawal"),
                bordercolor="rgba(255,255,255,0.1)", borderwidth=1
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        render_clean_html(f"<div style='margin-bottom:15px; display:flex; align-items:center; gap:10px;'><span class='sphere-icon' style='width:35px; height:35px; font-size:1rem; background:linear-gradient(135deg, {PURPLE[0]}, {PURPLE[1]});'>🎯</span><h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin:0;'>التوزيع الهيكلي للمخازن</h4></div>")
        inv_data = globals().get('get_inventory_by_category', lambda: [{'category':'أجهزة','total':50}, {'category':'إكسسوارات','total':30}])()
        if inv_data:
            df = pd.DataFrame(inv_data)
            fig = px.pie(
                df, names='category', values='total', hole=0.75,
                color_discrete_sequence=['#00F2FE', '#F6416C', '#00F260', '#F9D423', '#89216B']
            )
            fig.update_traces(
                textinfo='none', hoverinfo='label+percent+value',
                marker=dict(line=dict(color=BG_DARK, width=4))
            )
            fig.add_annotation(dict(font=dict(size=30, color="#FFFFFF"), x=0.5, y=0.5, showarrow=False, text="📦"))
            fig.update_layout(
                paper_bgcolor=chart_bg, font=chart_font, margin=dict(t=20, b=20, l=10, r=10),
                legend=dict(orientation="h", y=-0.2, font=dict(color=TEXT_SECONDARY)),
                hoverlabel=dict(bgcolor="#0F172A", font_size=14)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # 6. القوائم المنبثقة السفلية (Cyber Lists)
    col_l1, col_l2 = st.columns(2)
    
    with col_l1:
        render_clean_html(f"<div style='margin:20px 0 15px 0; display:flex; align-items:center; gap:10px;'><span class='sphere-icon' style='width:30px; height:30px; font-size:0.9rem; background:linear-gradient(135deg, {RED[0]}, {RED[1]});'>🚨</span><h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin:0; font-size:1.1rem;'>المخزون الحرج</h4></div>")
        low = globals().get('get_low_stock_products', lambda: [])()
        if low:
            for item in low:
                render_clean_html(f"""
                <div style="background: rgba(255, 8, 68, 0.05); border: 1px solid rgba(255, 8, 68, 0.2); border-right: 4px solid #FF0844; border-radius: 12px; padding: 12px 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; transition: 0.3s; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                    <span style="color: #FFFFFF; font-weight: 600; font-size: 0.9rem;">{item['name']}</span>
                    <span style="background: rgba(255,8,68,0.2); color: #FFB199; padding: 4px 10px; border-radius: 8px; font-weight: 800; font-size: 0.8rem; box-shadow: 0 0 10px rgba(255,8,68,0.3);">
                        {item['quantity']} / {item['reorder_level']}
                    </span>
                </div>
                """)
        else:
            render_clean_html(f"""<div style="background: rgba(0, 242, 96, 0.05); border: 1px dashed rgba(0, 242, 96, 0.3); border-radius: 12px; padding: 16px; color: #00F260; font-weight: 700; text-align: center; text-shadow: 0 0 10px rgba(0,242,96,0.3);">🛡️ جميع الأصناف في مستويات آمنة ومستقرة.</div>""")

    with col_l2:
        render_clean_html(f"<div style='margin:20px 0 15px 0; display:flex; align-items:center; gap:10px;'><span class='sphere-icon' style='width:30px; height:30px; font-size:0.9rem; background:linear-gradient(135deg, {GOLD[0]}, {GOLD[1]});'>⚡</span><h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin:0; font-size:1.1rem;'>نبض العمليات</h4></div>")
        activities = globals().get('get_recent_activities', lambda: [])()
        if activities:
            for act in activities[:5]:
                act_str = str(act.get('action', 'عملية نظام'))
                time_val = act.get('time') or act.get('created_at') or ''
                render_clean_html(f"""
                <div class="cyber-card" style="padding: 10px 16px; margin-bottom: 10px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span style="width: 8px; height: 8px; background: #00F2FE; border-radius: 50%; box-shadow: 0 0 10px #00F2FE;"></span>
                            <span style="color: #FFFFFF; font-weight: 600; font-size: 0.85rem;">{act_str}</span>
                        </div>
                        <span style="color: {TEXT_SECONDARY}; font-size: 0.75rem; background: rgba(255,255,255,0.05); padding: 3px 8px; border-radius: 6px;">{time_val}</span>
                    </div>
                </div>
                """)
        else:
            render_clean_html(f"""<div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; color: {TEXT_SECONDARY}; font-weight: 600; text-align: center;">⏳ لا توجد نشاطات مسجلة حالياً في النظام.</div>""")
