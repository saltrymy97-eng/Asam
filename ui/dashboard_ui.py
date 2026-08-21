# ui/dashboard_ui.py – لوحة معلومات احترافية (تصميم زجاجي فاخر ومبهر ثلاثي الأبعاد)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from services.dashboard_service import (
    get_kpi_cards,
    get_quick_stats,
    get_alerts,
    get_inventory_by_category,
    get_monthly_sales,
    get_low_stock_products,
    get_recent_activities
)

# ========== لوحة الألوان الملكية ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"
PR = "#8B5CF6"      # بنفسجي إمبراطوري
BL = "#3B82F6"      # أزرق كهربائي
GN = "#10B981"      # أخضر زمردي
RD = "#EF4444"      # أحمر ياقوتي
OR = "#F59E0B"      # برتقالي متوهج
BG_CORE = "#030712" # كحلي فضائي عميق

def render_clean_html(html_code: str):
    """دالة آمنة لعرض الـ HTML بدون تسريب نصوص الأكواد للواجهة"""
    clean_lines = [line.strip() for line in html_code.splitlines() if line.strip()]
    st.markdown("".join(clean_lines), unsafe_allow_html=True)

def inject_executive_css():
    """حقن تصميم الـ Glassmorphism والتنسيق الشامل المتجاوب مع الجوال"""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap');

    * {{
        font-family: 'Tajawal', sans-serif !important;
        box-sizing: border-box;
    }}

    /* تطبيق الخلفية على التطبيق بالكامل */
    .stApp {{
        background: radial-gradient(circle at top right, #0f172a 0%, #030712 80%) !important;
        background-attachment: fixed !important;
    }}

    /* حصر اتجاه RTL في المحتوى الرئيسي فقط لحماية القائمة الجانبية من التشوه */
    .block-container {{
        direction: rtl;
        text-align: right;
    }}

    div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

    /* شبكة البطاقات التكيفية (CSS Grid) متوافقة مع الجوال */
    .grid-container-4 {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 15px;
        margin-bottom: 25px;
        width: 100%;
    }}

    .grid-container-5 {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 12px;
        margin-bottom: 25px;
        width: 100%;
    }}

    /* البطاقة الزجاجية الفاخرة */
    .luxury-card {{
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 16px !important;
        padding: 1.1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}

    .luxury-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5), 0 0 15px rgba(139, 92, 246, 0.2);
        border-color: rgba(255, 255, 255, 0.25) !important;
    }}

    .dash-orb {{
        width: 65px;
        height: 65px;
        background: linear-gradient(135deg, rgba(139,92,246,0.3) 0%, rgba(59,130,246,0.1) 100%);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-top: 2px solid rgba(139, 92, 246, 0.8);
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
        flex-shrink: 0;
    }}

    .mini-orb {{
        width: 42px;
        height: 42px;
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        flex-shrink: 0;
    }}

    .pulse-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-left: 6px;
        flex-shrink: 0;
    }}
    
    /* استعلامات الشاشات الصغيرة (الموبايل) */
    @media (max-width: 768px) {{
        .header-container {{
            flex-direction: column-reverse;
            text-align: center;
            padding: 20px !important;
        }}
        .header-container > div {{
            align-items: center;
            justify-content: center;
        }}
        .header-title {{
            font-size: 1.6rem !important;
            text-align: center;
        }}
        .card-value {{
            font-size: 1.3rem !important;
        }}
        .card-title {{
            font-size: 0.8rem !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
    }}
    </style>
    """
    render_clean_html(css)

def build_card_html(title, value, icon, accent_color, delta=""):
    """إنشاء كود HTML ملائم للبطاقات متوافق مع كافة الشاشات"""
    delta_html = ""
    if delta:
        d_color = GN if "↑" in delta else RD if "↓" in delta else TEXT_SECONDARY
        dot_bg = GN if "↑" in delta else RD if "↓" in delta else TEXT_MUTED
        delta_html = f"""
        <div style="display: flex; align-items: center; margin-top: 6px; flex-wrap: nowrap;">
            <span class="pulse-dot" style="background-color: {dot_bg}; box-shadow: 0 0 8px {dot_bg};"></span>
            <span style="color: {d_color}; font-size: 0.8rem; font-weight: 700; white-space: nowrap;">{delta}</span>
        </div>
        """
    
    return f"""
    <div class="luxury-card" style="border-bottom: 2px solid {accent_color}80;">
        <div style="flex: 1; text-align: right; min-width: 0;">
            <div class="card-title" style="color: {TEXT_SECONDARY}; font-size: 0.88rem; margin-bottom: 4px; font-weight: 600;">{title}</div>
            <div class="card-value" style="color: {TEXT_PRIMARY}; font-size: 1.6rem; font-weight: 800; line-height: 1.2;">{value}</div>
            {delta_html}
        </div>
        <div class="mini-orb" style="box-shadow: 0 0 12px {accent_color}30; border-top: 2px solid {accent_color};">
            <span style="font-size: 1.3rem; filter: drop-shadow(0 0 4px {accent_color});">{icon}</span>
        </div>
    </div>
    """

def show():
    inject_executive_css()
    
    user_name = st.session_state.user.get("full_name", "المدير") if 'user' in st.session_state else "المدير التنفيذي"
    
    # محاكاة البيانات في حال عدم توفرها (لضمان عمل الواجهة أثناء الاختبار)
    kpi = get_kpi_cards() if 'get_kpi_cards' in globals() else {"net_income": 5000, "total_sales": 12000, "total_purchases": 7000, "products_count": 120, "customers_count": 45}
    quick = get_quick_stats() if 'get_quick_stats' in globals() else {"low_stock": 2, "today_sales": 1500, "today_purchases": 500, "total_customers": 45}
    alerts = get_alerts() if 'get_alerts' in globals() else []

    # 1. الهيدر الرئيسي
    header_html = f"""
    <div class="header-container" style="
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(25px);
        border-radius: 20px;
        padding: 24px 30px;
        margin-bottom: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: 1px solid rgba(139, 92, 246, 0.5);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
    ">
        <div style="flex: 1; min-width: 200px;">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span style="background: {PR}; width: 10px; height: 10px; border-radius: 3px; box-shadow: 0 0 10px {PR};"></span>
                <span style="color: {PR}; font-size: 0.8rem; font-weight: 800; letter-spacing: 1px;">ENTERPRISE CORE</span>
            </div>
            <h1 class="header-title" style="color: #FFFFFF; font-size: 2rem; margin: 0; font-weight: 800; line-height: 1.3;">مرحباً، {user_name}</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 0.9rem; margin: 8px 0 0 0; font-weight: 500; line-height: 1.5;">
                نظرة شاملة على مؤشرات الأداء الحية اليوم، <br/>
                <span style="color:#A78BFA; font-weight:700;">{datetime.now().strftime('%A %d %B %Y')}</span>
            </p>
        </div>
        <div class="dash-orb">
            <span style="font-size: 2rem;">💎</span>
        </div>
    </div>
    """
    render_clean_html(header_html)

    # 2. الإحصائيات السريعة 
    stock_status = "تدخل عاجل" if quick['low_stock'] > 0 else "مستويات آمنة"
    stock_col = RD if quick['low_stock'] > 0 else GN
    
    quick_cards_html = f"""
    <div class="grid-container-4">
        {build_card_html("تدفقات نقدية (مبيعات)", f"{quick['today_sales']:,.0f}", "💸", GN, "↑ 12% نمو")}
        {build_card_html("التزامات نقدية (مشتريات)", f"{quick['today_purchases']:,.0f}", "🛍️", RD, "↓ 5% انخفاض")}
        {build_card_html("نواقص المخزون", str(quick['low_stock']), "⚠️", stock_col, stock_status)}
        {build_card_html("شركاء النجاح", str(quick['total_customers']), "🤝", BL, "+3 انضمام")}
    </div>
    """
    render_clean_html(quick_cards_html)

    # 3. التنبيهات
    if alerts:
        for alert in alerts:
            alert_html = f"""
            <div style="background: rgba(245, 158, 11, 0.08); border-right: 4px solid {OR}; border-radius: 12px; padding: 12px 18px; margin-bottom: 20px; color: {TEXT_PRIMARY}; font-size: 0.9rem; display: flex; align-items: center; gap: 12px; line-height: 1.5;">
                <span style="font-size: 1.2rem; flex-shrink: 0;">{alert['icon']}</span>
                <span><b style="color: {OR}; font-weight: 700;">{alert['title']}</b>: {alert['message']}</span>
            </div>
            """
            render_clean_html(alert_html)

    # 4. المؤشرات المالية
    render_clean_html(f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 20px 0 15px 0;">
        <span style="background: {PR}; width: 12px; height: 4px; border-radius: 2px; box-shadow: 0 0 10px {PR};"></span>
        <h3 style="color:{TEXT_PRIMARY}; font-weight:800; margin: 0; font-size:1.15rem;">الأداء المالي الاستراتيجي</h3>
    </div>
    """)

    net_val = kpi['net_income']
    kpi_cards_html = f"""
    <div class="grid-container-5">
        {build_card_html("المبيعات", f"{kpi['total_sales']:,.0f}", "📈", GN)}
        {build_card_html("المشتريات", f"{kpi['total_purchases']:,.0f}", "📉", RD)}
        {build_card_html("الأرباح", f"{net_val:,.0f}", "🏆", GN if net_val >= 0 else RD)}
        {build_card_html("المنتجات", str(kpi['products_count']), "📦", BL)}
        {build_card_html("العملاء", str(kpi['customers_count']), "🌐", OR)}
    </div>
    """
    render_clean_html(kpi_cards_html)

    # 5. الرسوم البيانية
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        render_clean_html(f"""
        <div style="margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.2rem;">📊</span>
            <h4 style="color:{TEXT_PRIMARY}; font-weight:700; margin:0; font-size:1rem; line-height:1.4;">مؤشر التدفقات النقدية الشهري</h4>
        </div>
        """)
        sales_data = get_monthly_sales()
        if sales_data:
            df_sales = pd.DataFrame(sales_data).sort_values('month')
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_sales['month'], y=df_sales['total'],
                marker=dict(color=df_sales['total'], colorscale=[[0, '#3B82F6'], [1, '#8B5CF6']], line=dict(color='rgba(255,255,255,0.1)', width=1)),
                hovertemplate='%{y:,.0f} ر.ي', name='المبيعات'
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=TEXT_PRIMARY, family='Tajawal'),
                margin=dict(t=10, b=10, l=0, r=0), showlegend=False,
                xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color=TEXT_SECONDARY),
                hoverlabel=dict(bgcolor="#0F172A", font_size=13, font_family="Tajawal")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        render_clean_html(f"""
        <div style="margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.2rem;">🎯</span>
            <h4 style="color:{TEXT_PRIMARY}; font-weight:700; margin:0; font-size:1rem; line-height:1.4;">التوزيع الهيكلي للمخازن</h4>
        </div>
        """)
        inv_data = get_inventory_by_category()
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            fig = px.pie(
                df_inv, names='category', values='total', hole=0.7,
                color_discrete_sequence=['#8B5CF6', '#3B82F6', '#06B6D4', '#10B981', '#F59E0B']
            )
            fig.update_traces(
                textinfo='none', # إخفاء النسب من فوق الرسمة لتجنب الزحمة في الموبايل
                marker=dict(line=dict(color='#030712', width=2)),
                hoverinfo='label+percent+value'
            )
            fig.add_annotation(dict(font=dict(size=24), x=0.5, y=0.5, showarrow=False, text="📦", xanchor='center', yanchor='middle'))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color=TEXT_PRIMARY, family='Tajawal'),
                margin=dict(t=10, b=10, l=0, r=0), showlegend=True,
                legend=dict(font=dict(color=TEXT_SECONDARY, size=10), orientation="h", y=-0.2),
                hoverlabel=dict(bgcolor="#0F172A", font_size=13, font_family="Tajawal")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # 6. القوائم السفلية
    col_list1, col_list2 = st.columns(2)
    
    with col_list1:
        render_clean_html(f"""
        <div style="margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.2rem;">🚨</span>
            <h4 style="color:{TEXT_PRIMARY}; font-weight:700; margin:0; font-size:1rem; line-height:1.4;">رقابة المخزون والحدود الحرجة</h4>
        </div>
        """)
        low = get_low_stock_products()
        if low:
            for item in low:
                render_clean_html(f"""
                <div style="background: rgba(239, 68, 68, 0.05); border-right: 3px solid {RD}; border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; gap:10px;">
                    <span style="color: {TEXT_PRIMARY}; font-weight: 600; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item['name']}</span>
                    <span style="background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #FCA5A5; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; flex-shrink: 0;">
                        المتبقي: {item['quantity']} / {item['reorder_level']}
                    </span>
                </div>
                """)
        else:
            render_clean_html(f"""
            <div style="background: rgba(16, 185, 129, 0.05); border: 1px dashed rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 14px; color: {GN}; font-weight: 600; text-align: center; font-size: 0.85rem;">
                🛡️ جميع أصناف المخزون بمستويات آمنة.
            </div>
            """)

    with col_list2:
        render_clean_html(f"""
        <div style="margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span style="font-size:1.2rem;">⚡</span>
            <h4 style="color:{TEXT_PRIMARY}; font-weight:700; margin:0; font-size:1rem; line-height:1.4;">سجل الأنشطة والعمليات الفورية</h4>
        </div>
        """)
        activities = get_recent_activities()
        if activities:
            for act in activities[:5]:
                act_str = str(act.get('action', ''))
                dot_color = PR if 'فاتورة' in act_str else BL if 'قيد' in act_str else GN if 'سداد' in act_str else OR
                time_value = act.get('time') or act.get('created_at') or act.get('timestamp') or ''
                
                render_clean_html(f"""
                <div class="luxury-card" style="padding: 8px 12px; margin-bottom: 8px; border-radius: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px; width: 100%;">
                        <div class="mini-orb" style="width: 24px; height: 24px; background: {dot_color}20; border-color: {dot_color}50;">
                            <span style="background: {dot_color}; width: 6px; height: 6px; border-radius: 50%;"></span>
                        </div>
                        <div style="flex: 1; display: flex; justify-content: space-between; align-items: center; gap:5px; min-width: 0;">
                            <span style="color: {TEXT_PRIMARY}; font-weight: 600; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{act_str}</span>
                            <span style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 6px; color: {TEXT_SECONDARY}; font-size: 0.7rem; flex-shrink: 0;">{time_value}</span>
                        </div>
                    </div>
                </div>
                """)
        else:
            render_clean_html(f"""
            <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 10px; padding: 14px; color: {TEXT_SECONDARY}; text-align: center; font-size: 0.85rem;">
                ⏳ لا توجد مستجدات في سجل العمليات حالياً.
            </div>
            """)
