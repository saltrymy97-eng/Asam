# ui/dashboard_ui.py – لوحة معلومات ERP مؤسسية فاخرة (Modern Enterprise SaaS)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# ================= إعدادات الصفحة =================
st.set_page_config(page_title="ERP Dashboard", layout="wide", initial_sidebar_state="expanded")

# محاولة استدعاء الخدمات (مع وضع بيانات وهمية ذكية كبديل)
try:
    from services.dashboard_service import (
        get_kpi_cards, get_quick_stats, get_alerts,
        get_inventory_by_category, get_monthly_sales,
        get_low_stock_products, get_recent_activities
    )
except ImportError:
    pass

# ================= الألوان المؤسسية الفاخرة =================
# تم اختيار ألوان مريحة للعين ومناسبة لبيئة العمل (Modern Slate Dark Theme)
BG_MAIN = "#0F172A"       # خلفية رئيسية كحلية داكنة جداً
BG_CARD = "#1E293B"       # خلفية البطاقات
BORDER_COLOR = "#334155"  # لون الحدود
TEXT_PRIMARY = "#F8FAFC"  # أبيض ناصع للنصوص الأساسية
TEXT_MUTED = "#94A3B8"    # رمادي فاتح للنصوص الثانوية

# ألوان الدلالات (Semantic Colors) هادئة واحترافية
ACCENT_BLUE = "#3B82F6"   # أزرق مؤسسي
ACCENT_GREEN = "#10B981"  # أخضر للنجاح والنمو
ACCENT_RED = "#EF4444"    # أحمر للتنبيهات
ACCENT_AMBER = "#F59E0B"  # برتقالي للتحذيرات
ACCENT_PURPLE = "#8B5CF6" # بنفسجي هادئ

def render_html(html_code: str):
    st.markdown(html_code, unsafe_allow_html=True)

def inject_enterprise_css():
    """CSS مؤسسي فاخر: نظيف، هادئ، يركز على البيانات دون تشتيت"""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');

    /* الخط الأساسي وإعدادات عامة */
    * {{
        font-family: 'Tajawal', sans-serif !important;
        box-sizing: border-box;
    }}

    /* التخلص من المسافات العلوية الزائدة في Streamlit */
    .block-container {{
        direction: rtl;
        text-align: right;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px;
    }}
    
    /* إخفاء عناصر Streamlit الافتراضية للظهور بشكل تطبيق مستقل */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}

    /* الشبكات (Grids) */
    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1.2rem;
        margin-bottom: 1.5rem;
    }}

    /* تصميم البطاقة المؤسسية */
    .enterprise-card {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 12px;
        padding: 1.25rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }}
    
    .enterprise-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        border-color: #475569;
    }}

    /* ترويسة البطاقة */
    .card-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
    }}
    
    .card-title {{
        color: {TEXT_MUTED};
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0px;
    }}
    
    .card-icon-wrapper {{
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
    }}

    /* قيمة البطاقة */
    .card-value {{
        color: {TEXT_PRIMARY};
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }}

    /* شارة التغير (Trend Badge) */
    .trend-badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    .trend-positive {{ background-color: rgba(16, 185, 129, 0.1); color: {ACCENT_GREEN}; }}
    .trend-negative {{ background-color: rgba(239, 68, 68, 0.1); color: {ACCENT_RED}; }}
    .trend-neutral {{ background-color: rgba(148, 163, 184, 0.1); color: {TEXT_MUTED}; }}

    /* القوائم والتنبيهات */
    .list-item {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 0;
        border-bottom: 1px solid {BORDER_COLOR};
    }}
    .list-item:last-child {{ border-bottom: none; padding-bottom: 0; }}
    
    .alert-box {{
        background-color: rgba(239, 68, 68, 0.05);
        border-right: 3px solid {ACCENT_RED};
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }}
    </style>
    """
    render_html(css)

def build_kpi_card(title, value, icon, trend_text="", trend_type="neutral"):
    """دالة لإنشاء بطاقة عرض بيانات هادئة واحترافية"""
    trend_html = ""
    if trend_text:
        trend_class = f"trend-{trend_type}"
        trend_html = f'<div class="trend-badge {trend_class}">{trend_text}</div>'
        
    return f"""
    <div class="enterprise-card">
        <div class="card-header">
            <span class="card-title">{title}</span>
            <div class="card-icon-wrapper">{icon}</div>
        </div>
        <div class="card-value">{value}</div>
        {trend_html}
    </div>
    """

def show():
    # 1. تهيئة التصميم والبيانات الوهمية
    inject_enterprise_css()
    user_name = st.session_state.user.get("full_name", "إدارة النظام") if 'user' in st.session_state else "إدارة النظام"
    
    # Fallback Data
    kpi = globals().get('get_kpi_cards', lambda: {"net_income": 125000, "total_sales": 240000, "total_purchases": 85000, "products_count": 1240, "customers_count": 312})()
    quick = globals().get('get_quick_stats', lambda: {"low_stock": 3, "today_sales": 18500, "today_purchases": 4200, "total_customers": 312})()
    alerts = globals().get('get_alerts', lambda: [{"title": "تنبيه سيولة", "message": "الرصيد النقدي في الصندوق الرئيسي أقل من الحد المسموح به.", "icon": "⚠️"}])()

    # 2. منطقة الترحيب (Header) - نظيفة ومباشرة
    render_html(f"""
    <div style="margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: flex-end;">
        <div>
            <h1 style="color: {TEXT_PRIMARY}; font-size: 2rem; font-weight: 700; margin: 0 0 0.2rem 0;">نظرة عامة على النظام</h1>
            <p style="color: {TEXT_MUTED}; font-size: 0.95rem; margin: 0;">مرحباً بك مجدداً، {user_name} • {datetime.now().strftime('%d %B %Y')}</p>
        </div>
        <div>
            <span style="background-color: {ACCENT_BLUE}; color: white; padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; cursor: pointer;">
                + تقرير جديد
            </span>
        </div>
    </div>
    """)

    # 3. عرض التنبيهات (إن وجدت)
    if alerts:
        for alert in alerts:
            render_html(f"""
            <div class="alert-box">
                <div style="font-size: 1.2rem;">{alert['icon']}</div>
                <div>
                    <h4 style="color: {TEXT_PRIMARY}; margin: 0 0 4px 0; font-size: 0.95rem;">{alert['title']}</h4>
                    <p style="color: {TEXT_MUTED}; margin: 0; font-size: 0.85rem;">{alert['message']}</p>
                </div>
            </div>
            """)

    # 4. المؤشرات المالية والتشغيلية (KPIs)
    st.markdown(f"<h3 style='color: {TEXT_PRIMARY}; font-size: 1.2rem; margin-bottom: 1rem;'>المؤشرات المالية (اليوم)</h3>", unsafe_allow_html=True)
    
    kpi_html = f"""
    <div class="kpi-grid">
        {build_kpi_card("إجمالي المبيعات", f"{quick['today_sales']:,.0f} ﷼", "📈", "↑ 8.2% مقارنة بالأمس", "positive")}
        {build_kpi_card("المصروفات والمشتريات", f"{quick['today_purchases']:,.0f} ﷼", "📉", "↓ 2.1% مقارنة بالأمس", "positive")}
        {build_kpi_card("صافي الدخل السنوي", f"{kpi['net_income']:,.0f} ﷼", "🏦", "↑ 14% النمو السنوي", "positive")}
        {build_kpi_card("تنبيهات المخزون", str(quick['low_stock']), "📦", "أصناف بحاجة للطلب", "negative" if quick['low_stock'] > 0 else "neutral")}
    </div>
    """
    render_html(kpi_html)

    st.write("---") # فاصل خفيف

    # 5. الرسوم البيانية (Charts) - تم تنظيف الألوان وجعلها احترافية
    col_chart1, col_chart2 = st.columns([6, 4]) # تقسيم المساحة ليكون الرسم البياني الخطي أكبر

    chart_font = dict(color=TEXT_MUTED, family='Tajawal', size=12)

    with col_chart1:
        st.markdown(f"<h3 style='color: {TEXT_PRIMARY}; font-size: 1.1rem;'>التدفقات النقدية (آخر 6 أشهر)</h3>", unsafe_allow_html=True)
        sales_data = globals().get('get_monthly_sales', lambda: [{'month':'مارس','total':45000}, {'month':'أبريل','total':52000}, {'month':'مايو','total':48000}, {'month':'يونيو','total':61000}])()
        if sales_data:
            df = pd.DataFrame(sales_data)
            fig = px.area(
                df, x='month', y='total', 
                color_discrete_sequence=[ACCENT_BLUE]
            )
            # إضافة خط مستقيم مع التعبئة ليعطي طابعاً مالياً احترافياً
            fig.update_traces(mode='lines+markers', line=dict(width=3), fill='tozeroy', marker=dict(size=8, color=BG_CARD, line=dict(width=2, color=ACCENT_BLUE)))
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=chart_font, margin=dict(t=10, b=30, l=10, r=10),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor=BORDER_COLOR, title="", tickformat=",.0f"),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        st.markdown(f"<h3 style='color: {TEXT_PRIMARY}; font-size: 1.1rem;'>توزيع قيمة المخزون</h3>", unsafe_allow_html=True)
        inv_data = globals().get('get_inventory_by_category', lambda: [{'category':'مواد خام','total':40}, {'category':'منتجات نهائية','total':35}, {'category':'تغليف','total':25}])()
        if inv_data:
            df = pd.DataFrame(inv_data)
            fig = px.pie(
                df, names='category', values='total', hole=0.6,
                color_discrete_sequence=[ACCENT_BLUE, ACCENT_PURPLE, ACCENT_GREEN, ACCENT_AMBER]
            )
            fig.update_traces(
                textposition='inside', textinfo='percent',
                marker=dict(line=dict(color=BG_MAIN, width=3)),
                hovertemplate="<b>%{label}</b><br>القيمة: %{value}%<extra></extra>"
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=chart_font, margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # 6. الجداول والقوائم السفلية (Data Lists)
    col_list1, col_list2 = st.columns(2)

    with col_list1:
        render_html(f"""
        <div class="enterprise-card" style="height: 100%;">
            <h3 style="color: {TEXT_PRIMARY}; font-size: 1.1rem; margin-top: 0; margin-bottom: 1rem; border-bottom: 1px solid {BORDER_COLOR}; padding-bottom: 0.5rem;">
                النواقص (إعادة الطلب)
            </h3>
        """)
        low = globals().get('get_low_stock_products', lambda: [{'name': 'ورق طباعة A4', 'quantity': 5, 'reorder_level': 20}, {'name': 'حبر طابعة HP', 'quantity': 1, 'reorder_level': 5}])()
        if low:
            for item in low:
                render_html(f"""
                <div class="list-item">
                    <div>
                        <div style="color: {TEXT_PRIMARY}; font-weight: 500; font-size: 0.9rem;">{item['name']}</div>
                        <div style="color: {ACCENT_RED}; font-size: 0.75rem;">الحد الأدنى: {item['reorder_level']}</div>
                    </div>
                    <div style="background-color: rgba(239, 68, 68, 0.1); color: {ACCENT_RED}; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.85rem;">
                        المتبقي {item['quantity']}
                    </div>
                </div>
                """)
        else:
            render_html(f"<div style='color: {TEXT_MUTED}; font-size: 0.9rem; text-align: center; padding: 2rem 0;'>لا توجد نواقص في المخزون حالياً</div>")
        render_html("</div>")

    with col_list2:
        render_html(f"""
        <div class="enterprise-card" style="height: 100%;">
            <h3 style="color: {TEXT_PRIMARY}; font-size: 1.1rem; margin-top: 0; margin-bottom: 1rem; border-bottom: 1px solid {BORDER_COLOR}; padding-bottom: 0.5rem;">
                سجل النشاطات الحديثة
            </h3>
        """)
        activities = globals().get('get_recent_activities', lambda: [{'action': 'تم إصدار فاتورة مبيعات #INV-0012', 'time': 'منذ 10 دقائق'}, {'action': 'اعتماد قيد محاسبي بواسطة أحمد', 'time': 'منذ ساعتين'}])()
        if activities:
            for act in activities:
                render_html(f"""
                <div class="list-item">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 6px; height: 6px; border-radius: 50%; background-color: {ACCENT_BLUE}; display: inline-block;"></span>
                        <span style="color: {TEXT_PRIMARY}; font-size: 0.9rem;">{act['action']}</span>
                    </div>
                    <span style="color: {TEXT_MUTED}; font-size: 0.75rem;">{act['time']}</span>
                </div>
                """)
        else:
            render_html(f"<div style='color: {TEXT_MUTED}; font-size: 0.9rem; text-align: center; padding: 2rem 0;'>لا توجد نشاطات حديثة</div>")
        render_html("</div>")
