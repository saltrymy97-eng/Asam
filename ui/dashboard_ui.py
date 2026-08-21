# ui/dashboard_ui.py – لوحة معلومات احترافية (تصميم زجاجي فاخر ومبهر ثلاثي الأبعاد)
import textwrap
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.dashboard_service import (
    get_alerts,
    get_inventory_by_category,
    get_kpi_cards,
    get_low_stock_products,
    get_monthly_sales,
    get_quick_stats,
    get_recent_activities,
    get_recent_invoices,
    get_top_products,
)

# ========== لوحة ألوان النيون الملكية ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"
PR = "#8B5CF6"      # بنفسجي إمبراطوري
BL = "#3B82F6"      # أزرق كهربائي
GN = "#10B981"      # أخضر زمردي
RD = "#EF4444"      # أحمر ياقوتي
OR = "#F59E0B"      # برتقالي متوهج
BG_CORE = "#030712" # كحلي فضائي عميق

def clean_html(html_str: str) -> str:
    """تنظيف نصوص HTML وإزالة المسافات البادئة لمنع ظهروها كـ Code Block في Streamlit"""
    return textwrap.dedent(html_str).strip()

def render_html(html_str: str):
    """عرض HTML آمن بدون تسريب للواجهة"""
    st.markdown(clean_html(html_str), unsafe_allow_html=True)

def inject_executive_css():
    """حقن نظام التصميم الفاخر والمؤثرات السينمائية"""
    css_code = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap');

    * {{
        font-family: 'Tajawal', sans-serif !important;
        box-sizing: border-box;
    }}

    /* خلفية فضائية عميقة */
    .stApp {{
        background: radial-gradient(circle at 10% 20%, #0f172a 0%, #030712 90%) !important;
        background-attachment: fixed !important;
        direction: rtl;
    }}

    /* إخفاء المساحات الفارغة الإضافية */
    div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

    /* أنيميشن الدخول */
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    div[data-testid="stVerticalBlock"] > div {{
        animation: fadeInUp 0.5s ease-out forwards;
    }}

    /* الجرم الثلاثي الأبعاد للهيدر */
    .dash-orb {{
        width: 85px;
        height: 85px;
        background: linear-gradient(135deg, rgba(139,92,246,0.3) 0%, rgba(59,130,246,0.1) 100%);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-top: 2px solid rgba(139, 92, 246, 0.8);
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        box-shadow: 0 0 30px rgba(139, 92, 246, 0.4), inset 0 0 15px rgba(139, 92, 246, 0.3);
        transition: transform 0.4s ease;
    }}

    .dash-orb:hover {{
        transform: scale(1.08) rotate(5deg);
    }}

    /* البطاقات الزجاجية Luxury Cards */
    .luxury-card {{
        background: rgba(15, 23, 42, 0.65) !important;
        backdrop-filter: blur(25px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(25px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 20px !important;
        padding: 1.4rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease-in-out;
        margin-bottom: 15px;
    }}

    .luxury-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 20px 45px rgba(0, 0, 0, 0.6), 0 0 15px rgba(139, 92, 246, 0.2);
        border-color: rgba(255, 255, 255, 0.25) !important;
    }}

    .mini-orb {{
        width: 52px;
        height: 52px;
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }}

    .pulse-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-left: 6px;
    }}
    </style>
    """
    render_html(css_code)

def make_premium_card(title, value, icon, accent_shadow_color, delta=""):
    """بناء البطاقات الفاخرة بشكل آمن وبدون تسريب HTML"""
    delta_html = ""
    if delta:
        d_color = GN if "↑" in delta else RD if "↓" in delta else TEXT_SECONDARY
        dot_bg = GN if "↑" in delta else RD if "↓" in delta else TEXT_MUTED
        delta_html = f"""
        <div style="display: flex; align-items: center; margin-top: 8px;">
            <span class="pulse-dot" style="background-color: {dot_bg}; box-shadow: 0 0 8px {dot_bg};"></span>
            <span style="color: {d_color}; font-size: 0.85rem; font-weight: 700;">{delta}</span>
        </div>
        """
    
    card_html = f"""
    <div class="luxury-card" style="border-bottom: 2px solid {accent_shadow_color}80;">
        <div style="flex: 1; text-align: right;">
            <div style="color: {TEXT_SECONDARY}; font-size: 0.9rem; margin-bottom: 6px; font-weight: 600;">{title}</div>
            <div style="color: {TEXT_PRIMARY}; font-size: 1.8rem; font-weight: 800; line-height: 1.2;">{value}</div>
            {delta_html}
        </div>
        <div class="mini-orb" style="box-shadow: 0 0 15px {accent_shadow_color}40; border-top: 2px solid {accent_shadow_color};">
            <span style="font-size: 1.5rem; filter: drop-shadow(0 0 5px {accent_shadow_color});">{icon}</span>
        </div>
    </div>
    """
    return card_html

def show():
    inject_executive_css()
    
    user_name = st.session_state.user.get("full_name", "المدير") if 'user' in st.session_state else "المدير التنفيذي"
    kpi = get_kpi_cards()
    quick = get_quick_stats()
    alerts = get_alerts()

    # ---------- هيدر اللوحة التنفيذي الفخم ----------
    header_html = f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(30px);
        -webkit-backdrop-filter: blur(30px);
        border-radius: 24px;
        padding: 30px 40px;
        margin-bottom: 30px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: 1px solid rgba(139, 92, 246, 0.5);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 20px;
    ">
        <div>
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span style="background: {PR}; width: 10px; height: 10px; border-radius: 3px; box-shadow: 0 0 10px {PR};"></span>
                <span style="color: {PR}; font-size: 0.85rem; font-weight: 800; letter-spacing: 2px; text-transform: uppercase;">Enterprise Core</span>
            </div>
            <h1 style="color: #FFFFFF; font-size: 2.3rem; margin: 0; font-weight: 800;">مرحباً، {user_name}</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 1rem; margin: 6px 0 0 0; font-weight: 500;">
                مؤشرات الأداء الحية والمباشرة اليوم، <span style="color:#A78BFA; font-weight:700;">{datetime.now().strftime('%A %d %B %Y')}</span>
            </p>
        </div>
        <div class="dash-orb">
            <span style="font-size: 2.5rem; filter: drop-shadow(0 0 10px rgba(255,255,255,0.8));">💎</span>
        </div>
    </div>
    """
    render_html(header_html)

    # ---------- الإحصائيات السريعة (Grid columns Streamlit) ----------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_html(make_premium_card("المبيعات اليومية", f"{quick['today_sales']:,.0f} ر.ي", "💸", GN, "↑ 12% نمو يومي"))
    with c2:
        render_html(make_premium_card("المشتريات اليومية", f"{quick['today_purchases']:,.0f} ر.ي", "🛍️", RD, "↓ 5% انخفاض"))
    with c3:
        stock_status = "تدخل عاجل" if quick['low_stock'] > 0 else "مستويات آمنة"
        stock_col = RD if quick['low_stock'] > 0 else GN
        render_html(make_premium_card("نواقص المخزون", str(quick['low_stock']), "⚠️", stock_col, stock_status))
    with c4:
        render_html(make_premium_card("إجمالي العملاء", str(quick['total_customers']), "🤝", BL, "+3 حديثاً"))

    # ---------- التنبيهات الذكية ----------
    if alerts:
        for alert in alerts:
            alert_html = f"""
            <div style="background: rgba(245, 158, 11, 0.08); 
                        border-right: 4px solid {OR}; border-radius: 12px; padding: 14px 20px; margin-bottom: 20px; 
                        color: {TEXT_PRIMARY}; font-size:0.95rem; display: flex; align-items: center; gap: 12px;
                        backdrop-filter: blur(10px);">
                <span style="font-size: 1.3rem;">{alert['icon']}</span>
                <span><b style="color: {OR}; font-weight: 700;">{alert['title']}</b>: {alert['message']}</span>
            </div>
            """
            render_html(alert_html)

    # ---------- الأداء العام والمالي ----------
    render_html(f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 30px 0 15px 0;">
        <span style="background: {PR}; width: 16px; height: 3px; border-radius: 2px; box-shadow: 0 0 10px {PR};"></span>
        <h3 style="color:{TEXT_PRIMARY}; font-weight:800; margin: 0; font-size:1.3rem;">الأداء المالي الاستراتيجي</h3>
    </div>
    """)
    
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        render_html(make_premium_card("إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "📈", GN))
    with k2:
        render_html(make_premium_card("إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📉", RD))
    with k3:
        net_val = kpi['net_income']
        render_html(make_premium_card("صافي الأرباح", f"{net_val:,.0f}", "🏆", GN if net_val >= 0 else RD))
    with k4:
        render_html(make_premium_card("عدد المنتجات", str(kpi['products_count']), "📦", BL))
    with k5:
        render_html(make_premium_card("قاعدة العملاء", str(kpi['customers_count']), "🌐", OR))

    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

    # ---------- الرسوم البيانية ----------
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        render_html(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:15px;'>📊 مؤشر التدفقات النقدية الشهري</h4>")
        sales_data = get_monthly_sales()
        if sales_data:
            df_sales = pd.DataFrame(sales_data).sort_values('month')
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_sales['month'], y=df_sales['total'],
                marker=dict(color=df_sales['total'], colorscale=[[0, '#3B82F6'], [1, '#8B5CF6']], 
                            line=dict(color='rgba(255,255,255,0.1)', width=1)),
                hovertemplate='%{y:,.0f} ر.ي', name='المبيعات'
            ))
            fig.add_trace(go.Scatter(
                x=df_sales['month'], y=df_sales['total'].rolling(2).mean(),
                mode='lines+markers', line=dict(color=OR, width=3, shape='spline'), 
                marker=dict(size=6, color=BG_CORE, line=dict(width=2, color=OR)),
                name='الاتجاه العام'
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=TEXT_PRIMARY, family='Tajawal'), 
                margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
                xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color=TEXT_SECONDARY),
                hoverlabel=dict(bgcolor="#0F172A", font_size=13, font_family="Tajawal")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        render_html(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:15px;'>🎯 التوزيع الهيكلي للمخازن</h4>")
        inv_data = get_inventory_by_category()
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            fig = px.pie(
                df_inv, names='category', values='total', hole=0.7,
                color_discrete_sequence=['#8B5CF6', '#3B82F6', '#06B6D4', '#10B981', '#F59E0B']
            )
            fig.update_traces(
                textinfo='percent', 
                marker=dict(line=dict(color='#030712', width=3)),
                hoverinfo='label+percent+value'
            )
            fig.add_annotation(dict(font=dict(size=28), x=0.5, y=0.5, showarrow=False, text="📦", xanchor='center', yanchor='middle'))
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', 
                font=dict(color=TEXT_PRIMARY, family='Tajawal'), 
                margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                legend=dict(font=dict(color=TEXT_SECONDARY, size=11), orientation="h", y=-0.1),
                hoverlabel=dict(bgcolor="#0F172A", font_size=13, font_family="Tajawal")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # ---------- القوائم السفلية ----------
    col_list1, col_list2 = st.columns(2)
    
    with col_list1:
        render_html(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:15px;'>🚨 رقابة المخزون والحدود الحرجة</h4>")
        low = get_low_stock_products()
        if low:
            for item in low:
                render_html(f"""
                <div style="background: rgba(239, 68, 68, 0.05); 
                            border-right: 3px solid {RD}; border-radius: 12px; padding: 14px 18px; margin-bottom: 12px; 
                            display: flex; justify-content: space-between; align-items: center;
                            box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                    <span style="color: {TEXT_PRIMARY}; font-weight: 600; font-size: 0.95rem;">{item['name']}</span>
                    <span style="background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #FCA5A5; padding: 4px 10px; border-radius: 8px; font-weight: 700; font-size: 0.8rem;">
                        المتبقي: {item['quantity']} / {item['reorder_level']}
                    </span>
                </div>
                """)
        else:
            render_html(f"""
            <div style="background: rgba(16, 185, 129, 0.05); border: 1px dashed rgba(16, 185, 129, 0.3); border-radius: 16px; padding: 20px; color: {GN}; font-weight: 600; text-align: center; font-size: 0.95rem;">
                🛡️ جميع أصناف المخزون بمستويات آمنة.
            </div>
            """)

    with col_list2:
        render_html(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:15px;'>⚡ سجل الأنشطة والعمليات الفورية</h4>")
        activities = get_recent_activities()
        if activities:
            for act in activities[:5]:
                act_str = str(act.get('action', ''))
                dot_color = PR if 'فاتورة' in act_str else BL if 'قيد' in act_str else GN if 'سداد' in act_str else OR
                time_value = act.get('time') or act.get('created_at') or act.get('timestamp') or ''
                
                render_html(f"""
                <div class="luxury-card" style="padding: 12px 18px; margin-bottom: 10px; border-radius: 12px;">
                    <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                        <div class="mini-orb" style="width: 28px; height: 28px; background: {dot_color}20; border-color: {dot_color}50;">
                            <span style="background: {dot_color}; width: 6px; height: 6px; border-radius: 50%;"></span>
                        </div>
                        <div style="flex: 1; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: {TEXT_PRIMARY}; font-weight: 600; font-size: 0.9rem;">{act_str}</span>
                            <span style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 6px; color: {TEXT_SECONDARY}; font-size: 0.75rem;">{time_value}</span>
                        </div>
                    </div>
                </div>
                """)
        else:
            render_html(f"""
            <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; color: {TEXT_SECONDARY}; text-align: center; font-size: 0.95rem;">
                ⏳ لا توجد مستجدات في سجل العمليات حالياً.
            </div>
            """)
