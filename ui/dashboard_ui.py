# ui/dashboard_ui.py – لوحة معلومات احترافية (تصميم زجاجي فاخر ومبهر ثلاثي الأبعاد)
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from services.dashboard_service import (
    get_kpi_cards,
    get_quick_stats,
    get_alerts,
    get_inventory_by_category,
    get_monthly_sales,
    get_top_products,
    get_low_stock_products,
    get_recent_invoices,
    get_recent_activities
)

# ========== لوحة ألوان النيون الملكية ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#475569"
PR = "#8B5CF6"      # بنفسجي إمبراطوري
BL = "#3B82F6"      # أزرق كهربائي
GN = "#10B981"      # أخضر زمردي مالي
RD = "#EF4444"      # أحمر ياقوتي حرج
OR = "#F59E0B"      # برتقالي متوهج
BG_CORE = "#020617" # كحلي فضائي عميق

def inject_executive_css():
    """حقن نظام التصميم الفاخر والمؤثرات السينمائية والأجرام المضيئة"""
    css_code = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap');

/* تعميم الخط الملكي */
* {{
    font-family: 'Tajawal', sans-serif !important;
}}

/* إصلاح مشكلة الأيقونات */
.material-symbols-rounded, .material-icons, [data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}}

/* خلفية فضائية متحركة ببطء للوحة بأكملها */
@keyframes cosmicOrbit {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
.stApp {{
    background: radial-gradient(circle at top right, #1e1b4b 0%, #090d16 50%, {BG_CORE} 100%) !important;
    background-size: 200% 200% !important;
    animation: cosmicOrbit 25s ease infinite !important;
    background-attachment: fixed !important;
}}

/* إخفاء المساحات الفارغة */
div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

/* أنيميشن الدخول المتدفق */
@keyframes fadeInUp3D {{
    from {{ opacity: 0; transform: translateY(30px) translateZ(-50px) rotateX(10deg); filter: blur(10px); }}
    to {{ opacity: 1; transform: translateY(0) translateZ(0) rotateX(0); filter: blur(0); }}
}}

/* تطبيق الأنيميشن على حاويات اللوحة */
div[data-testid="stVerticalBlock"] > div {{
    animation: fadeInUp3D 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    perspective: 1000px;
}}

/* ========================================================= */
/* 🔮 هندسة الأجرام الثلاثية الأبعاد (للهيدر والبطاقات) 🔮 */
/* ========================================================= */

@keyframes spinGleam {{
    0% {{ transform: rotate(0deg); }}
    100% {{ transform: rotate(360deg); }}
}}
@keyframes floatOrb {{
    0%, 100% {{ transform: translateY(0) scale(1); }}
    50% {{ transform: translateY(-8px) scale(1.02); }}
}}

/* الجرم الكبير في الهيدر */
.dash-orb {{
    position: relative;
    width: 100px; height: 100px;
    background: linear-gradient(135deg, rgba(139,92,246,0.3) 0%, rgba(59,130,246,0.15) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 2px solid rgba(139, 92, 246, 0.5);
    border-top: 3px solid rgba(255, 255, 255, 0.8);
    border-bottom: 2px solid rgba(59, 130, 246, 0.4);
    border-radius: 50%;
    display: flex; justify-content: center; align-items: center;
    box-shadow: 0 0 40px rgba(139, 92, 246, 0.6), inset 0 10px 20px rgba(139, 92, 246, 0.4);
    animation: floatOrb 6s ease-in-out infinite;
    transform-style: preserve-3d;
    overflow: hidden;
    z-index: 10;
}}
.dash-orb::before {{
    content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
    background: conic-gradient(transparent, rgba(255, 255, 255, 0.25), transparent 40%);
    animation: spinGleam 5s linear infinite; pointer-events: none; z-index: 1;
}}
.dash-orb-icon {{
    font-size: 3rem; transform: translateZ(20px);
    filter: drop-shadow(0 0 15px rgba(255,255,255,0.6)); z-index: 2; position: relative;
}}

/* ========================================================= */
/* 🃏 هندسة البطاقات الزجاجية الفاخرة 🃏 */
/* ========================================================= */

.luxury-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 25px; margin-bottom: 35px; width: 100%;
}}

.luxury-card {{
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.6) 0%, rgba(8, 13, 24, 0.9) 100%) !important;
    backdrop-filter: blur(40px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(40px) saturate(200%) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-top: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 28px !important;
    padding: 1.8rem;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.1);
    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative; overflow: hidden; transform-style: preserve-3d;
}}

@keyframes laserSweep {{
    0% {{ left: -100%; opacity: 0; }}
    50% {{ opacity: 1; }}
    100% {{ left: 200%; opacity: 0; }}
}}

.luxury-card::after {{
    content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    transform: skewX(-20deg); transition: 0.5s; pointer-events: none;
}}

.luxury-card:hover {{
    transform: translateY(-8px) scale(1.02) rotateX(2deg);
    box-shadow: 0 40px 80px rgba(0, 0, 0, 0.8), inset 0 2px 10px rgba(255,255,255,0.1);
    border-color: rgba(255, 255, 255, 0.25) !important;
}}
.luxury-card:hover::after {{ animation: laserSweep 1.2s ease-out; }}

/* جرم صغير للأيقونات داخل البطاقات */
.mini-orb {{
    position: relative; width: 60px; height: 60px; border-radius: 50%;
    display: flex; justify-content: center; align-items: center;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1); border-top: 2px solid rgba(255, 255, 255, 0.5);
    transform-style: preserve-3d; overflow: hidden; transition: all 0.5s;
}}
.mini-orb::before {{
    content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
    background: conic-gradient(transparent, rgba(255, 255, 255, 0.3), transparent 30%);
    animation: spinGleam 4s linear infinite; pointer-events: none; opacity: 0.5; transition: 0.5s;
}}
.luxury-card:hover .mini-orb {{
    transform: scale(1.1) translateZ(20px);
}}
.luxury-card:hover .mini-orb::before {{ opacity: 1; }}

/* نقطة النبض */
@keyframes pulseDot {{
    0% {{ box-shadow: 0 0 0 0 var(--dot-color); }}
    70% {{ box-shadow: 0 0 0 10px transparent; }}
    100% {{ box-shadow: 0 0 0 0 transparent; }}
}}
.pulse-dot {{
    width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-left: 8px;
    animation: pulseDot 2s infinite; background-color: var(--dot-color);
}}
</style>"""
    st.markdown(css_code, unsafe_allow_html=True)

def make_premium_card(title, value, icon, accent_shadow_color, delta=""):
    """بناء البطاقة مع الأجرام المضيئة الديناميكية"""
    delta_html = ""
    if delta:
        d_color = GN if "↑" in delta else RD if "↓" in delta else TEXT_SECONDARY
        dot_bg = GN if "↑" in delta else RD if "↓" in delta else TEXT_MUTED
        delta_html = f"""
        <div style="display: flex; align-items: center; margin-top: 10px;">
            <span class="pulse-dot" style="--dot-color: {dot_bg}; background-color: {dot_bg};"></span>
            <span style="color: {d_color}; font-size: 0.9rem; font-weight: 800; letter-spacing:0.5px; text-shadow: 0 0 10px {d_color}40;">{delta}</span>
        </div>
        """
    
    card_html = f"""
    <div class="luxury-card" style="box-shadow: 0 20px 40px rgba(0,0,0,0.4), inset -20px 0 60px {accent_shadow_color}10;">
        <div style="flex: 1; text-align: right; z-index: 2; padding-left: 10px;">
            <div style="color: {TEXT_SECONDARY}; font-size: 0.95rem; margin-bottom: 8px; font-weight: 700; letter-spacing: 0.5px;">{title}</div>
            <div style="color: {TEXT_PRIMARY}; font-size: 2.1rem; font-weight: 900; line-height: 1.1; letter-spacing: -0.5px; text-shadow: 0 4px 15px rgba(0,0,0,0.5);">{value}</div>
            {delta_html}
        </div>
        <div class="mini-orb" style="
            box-shadow: 0 0 25px {accent_shadow_color}60, inset 0 0 15px {accent_shadow_color}40;
            border-bottom: 2px solid {accent_shadow_color}80;
        ">
            <span style="font-size: 1.8rem; filter: drop-shadow(0 0 8px {accent_shadow_color}); z-index: 2;">{icon}</span>
        </div>
    </div>
    """
    return card_html.strip().replace("\n", "")

def show():
    inject_executive_css()
    
    user_name = st.session_state.user.get("full_name", "المستخدم") if 'user' in st.session_state else "المدير"
    kpi = get_kpi_cards()
    quick = get_quick_stats()
    alerts = get_alerts()

    # ---------- هيدر اللوحة التنفيذي الفخم (مع الجرم المضيء) ----------
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(23, 23, 45, 0.75) 0%, rgba(10, 10, 20, 0.95) 100%);
        backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px);
        border-radius: 35px; padding: 40px 50px; margin-bottom: 45px;
        border: 1px solid rgba(255,255,255,0.08); border-top: 1px solid rgba(139, 92, 246, 0.4);
        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
        box-shadow: 0 40px 100px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.1), 0 0 40px rgba(139, 92, 246, 0.15);
        display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 24px;
        position: relative; overflow: hidden;
    ">
        <!-- إضاءة خلفية ماكرة للهيدر -->
        <div style="position: absolute; top: -50%; right: -10%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(139,92,246,0.2) 0%, transparent 70%); filter: blur(40px); pointer-events: none;"></div>
        
        <div style="z-index: 2;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <span style="background: linear-gradient(135deg, {PR}, {BL}); width: 14px; height: 14px; border-radius: 4px; display: inline-block; box-shadow: 0 0 15px {PR};"></span>
                <span style="color: {PR}; font-size: 0.95rem; font-weight: 900; letter-spacing: 3px; text-transform: uppercase; text-shadow: 0 0 15px {PR}80;">Enterprise Core</span>
            </div>
            <h1 style="color: white; font-size: 3rem; margin: 0; font-weight: 900; letter-spacing: -1px; text-shadow: 0 10px 20px rgba(0,0,0,0.8);">مرحباً، {user_name}</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 1.15rem; margin: 8px 0 0 0; font-weight: 500; letter-spacing: 0.5px;">
                نظرة شاملة على مؤشرات الأداء الحية اليوم، <span style="font-weight:800; color:#A78BFA; text-shadow: 0 0 10px rgba(167,139,250,0.5);">{datetime.now().strftime('%A %d %B %Y')}</span>
            </p>
        </div>
        
        <!-- الجرم السماوي بدلاً من الأيقونة المربعة -->
        <div class="dash-orb">
            <span class="dash-orb-icon">💎</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---------- الإحصائيات السريعة (الشبكة المطهّرة الفاخرة) ----------
    html_quick = '<div class="luxury-grid">'
    html_quick += make_premium_card("تدفقات نقدية (مبيعات)", f"{quick['today_sales']:,.0f} ر.ي", "💸", GN, "↑ 12% نمو يومي")
    html_quick += make_premium_card("التزامات نقدية (مشتريات)", f"{quick['today_purchases']:,.0f} ر.ي", "🛍️", RD, "↓ 5% انخفاض")
    
    stock_status = "تدخل عاجل مطلوب" if quick['low_stock'] > 0 else "مستويات التخزين آمنة"
    stock_col = RD if quick['low_stock'] > 0 else GN
    html_quick += make_premium_card("نواقص المخزون", str(quick['low_stock']), "⚠️", stock_col, stock_status)
    html_quick += make_premium_card("شركاء النجاح (عملاء)", str(quick['total_customers']), "🤝", BL, "+3 انضمام حديث")
    html_quick += '</div>'
    st.markdown(html_quick, unsafe_allow_html=True)

    # ---------- التنبيهات الذكية (بأسلوب النيون) ----------
    if alerts:
        for alert in alerts:
            st.markdown(f"""
            <div style="background: linear-gradient(90deg, rgba(245, 158, 11, 0.1) 0%, transparent 100%); 
                        border-right: 4px solid {OR}; border-radius: 16px; padding: 18px 24px; margin-bottom: 25px; 
                        color: {TEXT_PRIMARY}; font-size:1.05rem; display: flex; align-items: center; gap: 15px;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.3), inset 0 0 20px rgba(245, 158, 11, 0.05);
                        backdrop-filter: blur(10px);">
                <span style="font-size: 1.5rem; filter: drop-shadow(0 0 8px {OR});">{alert['icon']}</span>
                <span><b style="color: {OR}; font-weight: 800;">{alert['title']}</b>: {alert['message']}</span>
            </div>
            """, unsafe_allow_html=True)

    # ---------- الأداء العام والمالي ----------
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 15px; margin: 45px 0 25px 0;">
        <span style="background: {PR}; width: 24px; height: 4px; border-radius: 2px; box-shadow: 0 0 15px {PR};"></span>
        <h3 style="color:{TEXT_PRIMARY}; font-weight:900; margin: 0; font-size:1.6rem; text-shadow: 0 4px 10px rgba(0,0,0,0.5);">الأداء المالي الاستراتيجي</h3>
    </div>
    """, unsafe_allow_html=True)
    
    html_perf = '<div class="luxury-grid">'
    html_perf += make_premium_card("إجمالي المبيعات التراكمية", f"{kpi['total_sales']:,.0f}", "📈", GN)
    html_perf += make_premium_card("إجمالي المشتريات التراكمية", f"{kpi['total_purchases']:,.0f}", "📉", RD)
    
    net_val = kpi['net_income']
    html_perf += make_premium_card("صافي الأرباح المحققة", f"{net_val:,.0f}", "🏆", GN if net_val >= 0 else RD)
    html_perf += make_premium_card("حجم دليل المنتجات", str(kpi['products_count']), "📦", BL)
    html_perf += make_premium_card("قاعدة بيانات العملاء", str(kpi['customers_count']), "🌐", OR)
    html_perf += '</div>'
    st.markdown(html_perf, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

    # ---------- الرسوم البيانية الاستراتيجية (تم تحسين تناسقها مع الثيم) ----------
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin-bottom:20px; text-shadow: 0 2px 10px rgba(0,0,0,0.5);'>📊 مؤشر التدفقات النقدية الشهري</h4>", unsafe_allow_html=True)
        sales_data = get_monthly_sales()
        if sales_data:
            df_sales = pd.DataFrame(sales_data).sort_values('month')
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_sales['month'], y=df_sales['total'],
                marker=dict(color=df_sales['total'], colorscale=[[0, '#3B82F6'], [1, '#8B5CF6']], 
                            line=dict(color='rgba(255,255,255,0.2)', width=1)),
                hovertemplate='%{y:,.0f} ر.ي', name='المبيعات'
            ))
            fig.add_trace(go.Scatter(
                x=df_sales['month'], y=df_sales['total'].rolling(2).mean(),
                mode='lines+markers', line=dict(color=OR, width=4, shape='spline'), 
                marker=dict(size=8, color=BG_CORE, line=dict(width=2, color=OR)),
                name='الاتجاه العام'
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=TEXT_PRIMARY, family='Tajawal'), 
                margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
                xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color=TEXT_SECONDARY),
                hoverlabel=dict(bgcolor="rgba(15, 23, 42, 0.9)", font_size=14, font_family="Tajawal")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin-bottom:20px; text-shadow: 0 2px 10px rgba(0,0,0,0.5);'>🎯 التوزيع الهيكلي للمخازن</h4>", unsafe_allow_html=True)
        inv_data = get_inventory_by_category()
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            fig = px.pie(
                df_inv, names='category', values='total', hole=0.75,
                color_discrete_sequence=['#8B5CF6', '#3B82F6', '#06B6D4', '#10B981', '#F59E0B']
            )
            fig.update_traces(
                textinfo='percent', 
                marker=dict(line=dict(color=BG_CORE, width=4)),
                hoverinfo='label+percent+value'
            )
            # وضع أيقونة في منتصف الدائرة
            fig.add_annotation(dict(font=dict(size=35), x=0.5, y=0.5, showarrow=False, text="📦", xanchor='center', yanchor='middle'))
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', 
                font=dict(color=TEXT_PRIMARY, family='Tajawal'), 
                margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                legend=dict(font=dict(color=TEXT_SECONDARY, size=13), orientation="h", y=-0.1),
                hoverlabel=dict(bgcolor="rgba(15, 23, 42, 0.9)", font_size=14, font_family="Tajawal")
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<div style='margin-bottom: 2.5rem;'></div>", unsafe_allow_html=True)

    # ---------- القوائم والأوراق التنفيذية ----------
    col_list1, col_list2 = st.columns(2)
    
    with col_list1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin-bottom:20px;'>🚨 رقابة المخزون والحدود الحرجة</h4>", unsafe_allow_html=True)
        low = get_low_stock_products()
        if low:
            for item in low:
                st.markdown(f"""
                <div style="background: linear-gradient(90deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.02) 100%); 
                            border-right: 3px solid {RD}; border-radius: 16px; padding: 18px 22px; margin-bottom: 15px; 
                            display: flex; justify-content: space-between; align-items: center;
                            box-shadow: 0 8px 20px rgba(0,0,0,0.2), inset 0 0 15px rgba(239, 68, 68, 0.05);
                            transition: transform 0.3s ease; cursor: default;"
                            onmouseover="this.style.transform='translateX(-5px)';" onmouseout="this.style.transform='translateX(0)';">
                    <span style="color: {TEXT_PRIMARY}; font-weight: 700; font-size: 1.05rem;">{item['name']}</span>
                    <span style="background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #FCA5A5; padding: 6px 14px; border-radius: 10px; font-weight: 800; font-size: 0.85rem; box-shadow: 0 0 10px rgba(239,68,68,0.2);">
                        المتبقي: {item['quantity']} / {item['reorder_level']}
                    </span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.05); border: 1px dashed rgba(16, 185, 129, 0.3); border-radius: 24px; padding: 30px; color: {GN}; font-weight: 700; text-align: center; font-size: 1.1rem; box-shadow: inset 0 0 20px rgba(16, 185, 129, 0.05);">
                🛡️ تأمين جرد المخازن مكتمل. جميع الأصناف بمستويات آمنة.
            </div>
            """, unsafe_allow_html=True)

    with col_list2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin-bottom:20px;'>⚡ سجل الأنشطة والعمليات الفورية</h4>", unsafe_allow_html=True)
        activities = get_recent_activities()
        if activities:
            for act in activities[:5]:
                # تحديد لون المؤشر بناءً على نوع الحركة
                act_str = str(act.get('action', ''))
                dot_color = PR if 'فاتورة' in act_str else BL if 'قيد' in act_str else GN if 'سداد' in act_str else OR
                time_value = act.get('time') or act.get('created_at') or act.get('timestamp') or ''
                
                st.markdown(f"""
                <div class="luxury-card" style="padding: 16px 22px; margin-bottom: 15px; border-radius: 18px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border-top: 1px solid rgba(255,255,255,0.08) !important;">
                    <div style="display: flex; align-items: center; gap: 15px; width: 100%;">
                        <div class="mini-orb" style="width: 35px; height: 35px; background: {dot_color}15; border-color: {dot_color}40; box-shadow: 0 0 15px {dot_color}40;">
                            <span style="background: {dot_color}; width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 10px {dot_color}, 0 0 20px {dot_color};"></span>
                        </div>
                        <div style="flex: 1; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <span style="color: {TEXT_PRIMARY}; font-weight: 600; font-size: 1rem; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">{act_str}</span>
                            <span style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 8px; color: {TEXT_SECONDARY}; font-size: 0.8rem; font-weight: 600;">{time_value}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 24px; padding: 30px; color: {TEXT_SECONDARY}; text-align: center; font-size: 1.1rem; font-weight: 600;">
                ⏳ لا توجد مستجدات في سجل العمليات حالياً.
            </div>
            """, unsafe_allow_html=True)
