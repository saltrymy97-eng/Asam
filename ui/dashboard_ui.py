# ui/dashboard_ui.py – لوحة معلومات احترافية (تصميم زجاجي فاخر ومبهر)
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
TEXT_SECONDARY = "#64748B"
TEXT_MUTED = "#475569"
PR = "#8B5CF6"      # بنفسجي إمبراطوري
BL = "#3B82F6"      # أزرق كهربائي
GN = "#10B981"      # أخضر زمردي مالي
RD = "#EF4444"      # أحمر ياقوتي حرج
OR = "#F59E0B"      # برتقالي متوهج

def inject_executive_css():
    """حقن نظام التصميم الفاخر والمؤثرات السينمائية للوحة التحكم"""
    st.markdown(f"""
    <style>
        /* 1. أنيميشن التدفق والظهور الفاخر */
        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(20px); filter: blur(5px); }}
            to {{ opacity: 1; transform: translateY(0); filter: blur(0); }}
        }}
        @keyframes pulseGlow {{
            0%, 100% {{ transform: scale(1); opacity: 0.6; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
        }}

        /* تطبيق الأنيميشن على حاوية لوحة التحكم */
        div[data-testid="stVerticalBlock"] > div {{
            animation: fadeInUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }}

        /* إخفاء التشوهات تماماً */
        div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}

        /* 2. حاوية الشبكة الفاخرة (Responsive Ultra-Grid) */
        .luxury-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 24px;
            margin-bottom: 30px;
            width: 100%;
        }}

        /* 3. هيكل البطاقة الملكية الزجاجية المجسمة */
        .luxury-card {{
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.45) 0%, rgba(30, 41, 59, 0.3) 100%) !important;
            backdrop-filter: blur(30px) saturate(170%) !important;
            -webkit-backdrop-filter: blur(30px) saturate(170%) !important;
            border: 1px solid rgba(255, 255, 255, 0.04) !important;
            border-top: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 24px !important;
            padding: 1.6rem 1.8rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.02);
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
            overflow: hidden;
        }}
        
        /* تأثير التوهج الخلفي الماكر عند تمرير الماوس */
        .luxury-card::before {{
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(circle at top right, rgba(255,255,255,0.06), transparent 60%);
            transition: opacity 0.5s ease; opacity: 0;
        }}

        .luxury-card:hover {{
            transform: translateY(-6px) scale(1.01);
            box-shadow: 0 40px 80px rgba(0, 0, 0, 0.6);
            border-color: rgba(255, 255, 255, 0.15) !important;
        }}
        .luxury-card:hover::before {{ opacity: 1; }}

        /* 4. تصميم نقاط الحالة المشعة (Pulse Dots) */
        .pulse-dot {{
            width: 8px; height: 8px; border-radius: 50%; display: inline-block;
            margin-left: 8px; animation: pulseGlow 2s infinite ease-in-out;
        }}

        /* تكييف شاشات الهواتف بذكاء لمنع الانضغاط */
        @media (max-width: 768px) {{
            .luxury-grid {{ grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 16px; }}
            .luxury-card {{ padding: 1.2rem; }}
            .luxury-card font {{ font-size: 1.4rem !important; }}
        }}
    </style>
    """, unsafe_allow_html=True)

def make_premium_card(title, value, icon, accent_shadow_color, delta=""):
    """بناء وتطهير كود البطاقة لمنع أي تسريب بصري على الواجهة"""
    delta_html = ""
    if delta:
        d_color = GN if "↑" in delta else RD if "↓" in delta else TEXT_SECONDARY
        dot_bg = GN if "↑" in delta else RD if "↓" in delta else TEXT_MUTED
        delta_html = f"""
        <div style="display: flex; align-items: center; margin-top: 8px;">
            <span class="pulse-dot" style="background-color: {dot_bg}; shadow: 0 0 8px {dot_bg};"></span>
            <span style="color: {d_color}; font-size: 0.82rem; font-weight: 700; letter-spacing:0.5px;">{delta}</span>
        </div>
        """
    
    card_html = f"""
    <div class="luxury-card" style="box-shadow: 0 20px 40px rgba(0,0,0,0.3), 0 0 30px {accent_shadow_color}05;">
        <div style="flex: 1; text-align: right; z-index: 2;">
            <div style="color: {TEXT_SECONDARY}; font-size: 0.85rem; margin-bottom: 6px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;">{title}</div>
            <div style="color: {TEXT_PRIMARY}; font-size: 1.9rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.5px;">{value}</div>
            {delta_html}
        </div>
        <div style="
            background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255,255,255,0.04); 
            border-radius: 20px; width: 54px; height: 54px; display: flex; 
            align-items: center; justify-content: center; font-size: 1.7rem; z-index: 2;
            box-shadow: inset 0 4px 12px rgba(0,0,0,0.4);
        ">{icon}</div>
    </div>
    """
    return card_html.strip().replace("\n", "").replace("    ", "")

def show():
    # تهيئة وحقن طابع الفخامة الملكي
    inject_executive_css()
    
    user_name = st.session_state.user.get("full_name", "المستخدم")
    kpi = get_kpi_cards()
    quick = get_quick_stats()
    alerts = get_alerts()

    # ---------- هيدر اللوحة التنفيذي الفخم ----------
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(23, 23, 37, 0.7) 0%, rgba(10, 10, 18, 0.9) 100%);
        backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px);
        border-radius: 30px; padding: 35px 45px; margin-bottom: 40px;
        border: 1px solid rgba(255,255,255,0.06); border-top: 1px solid rgba(255,255,255,0.15);
        box-shadow: 0 40px 80px rgba(0,0,0,0.5), inset 0 1px 1px rgba(255,255,255,0.05);
        display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 24px;
    ">
        <div>
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                <span style="background: {PR}; width: 12px; height: 12px; border-radius: 3px; display: inline-block; box-shadow: 0 0 12px {PR};"></span>
                <span style="color: {PR}; font-size: 0.85rem; font-weight: 800; letter-spacing: 2px; text-transform: uppercase;">Enterprise Hub</span>
            </div>
            <h1 style="color: white; font-size: 2.6rem; margin: 0; font-weight: 900; letter-spacing: -0.5px;">مرحباً، {user_name}</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 1.05rem; margin: 6px 0 0 0; font-weight: 400;">
                نظرة عامة على مؤشرات الأداء وجرد العمليات اليوم، <span style="font-weight:700; color:{TEXT_PRIMARY};">{datetime.now().strftime('%A %d %B %Y')}</span>
            </p>
        </div>
        <div style="
            background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);
            border-radius: 24px; width: 90px; height: 90px; display:flex; align-items:center; justify-content:center;
            font-size: 3rem; box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        ">📊</div>
    </div>
    """, unsafe_allow_html=True)

    # ---------- الإحصائيات السريعة (الشبكة المطهّرة) ----------
    html_quick = '<div class="luxury-grid">'
    html_quick += make_premium_card("مبيعات اليوم", f"{quick['today_sales']:,.0f} ر.ي", "💰", GN, "↑ 12% عن أمس")
    html_quick += make_premium_card("مشتريات اليوم", f"{quick['today_purchases']:,.0f} ر.ي", "🛒", RD, "↓ 5% عن أمس")
    
    stock_status = "بحتاج طلب عاجل" if quick['low_stock'] > 0 else "الكل آمن ومستقر"
    stock_col = RD if quick['low_stock'] > 0 else GN
    html_quick += make_premium_card("منتجات منخفضة", str(quick['low_stock']), "⚠️", stock_col, stock_status)
    html_quick += make_premium_card("شركاء جدد", str(quick['total_customers']), "👥", BL, "+3 هذا الشهر")
    html_quick += '</div>'
    st.markdown(html_quick, unsafe_allow_html=True)

    # ---------- التنبيهات الذكية ----------
    if alerts:
        for alert in alerts:
            st.markdown(f"""
            <div style="background: rgba(245, 158, 11, 0.06); border-right: 4px solid {OR}; border-radius: 12px; padding: 15px 20px; margin-bottom: 20px; color: {TEXT_PRIMARY}; font-size:0.95rem;">
                {alert['icon']} <b>{alert['title']}</b>: {alert['message']}
            </div>
            """, unsafe_allow_html=True)

    # ---------- الأداء العام والمالي ----------
    st.markdown(f"<h3 style='color:{TEXT_PRIMARY}; font-weight:800; margin: 35px 0 18px 0; font-size:1.4rem; letter-spacing: -0.3px;'>📊 الأداء العام والمالي للمنشأة</h3>", unsafe_allow_html=True)
    
    html_perf = '<div class="luxury-grid">'
    html_perf += make_premium_card("إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "💵", GN)
    html_perf += make_premium_card("إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📦", RD)
    
    net_val = kpi['net_income']
    html_perf += make_premium_card("صافي الأرباح", f"{net_val:,.0f}", "💎", GN if net_val >= 0 else RD)
    html_perf += make_premium_card("دليل المنتجات", str(kpi['products_count']), "🏷️", BL)
    html_perf += make_premium_card("قاعدة العملاء", str(kpi['customers_count']), "👥", OR)
    html_perf += '</div>'
    st.markdown(html_perf, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------- الرسوم البيانية الاستراتيجية ----------
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:18px;'>📈 التدفق المالي والاتجاه الشهري</h4>", unsafe_allow_html=True)
        sales_data = get_monthly_sales()
        if sales_data:
            df_sales = pd.DataFrame(sales_data).sort_values('month')
            fig = go.Figure()
            # البارات بتأثير الزجاج المضاء
            fig.add_trace(go.Bar(
                x=df_sales['month'], y=df_sales['total'],
                marker=dict(color=df_sales['total'], colorscale=[[0, '#3B82F6'], [1, '#8B5CF6']], line=dict(width=0)),
                hovertemplate='%{y:,.0f} ر.ي', name='المبيعات'
            ))
            # خط الاتجاه اللامع
            fig.add_trace(go.Scatter(
                x=df_sales['month'], y=df_sales['total'].rolling(2).mean(),
                mode='lines', line=dict(color=OR, width=4), name='الاتجاه العامة'
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=TEXT_PRIMARY, family='system-ui'), 
                margin=dict(t=5, b=5, l=5, r=5), showlegend=False,
                xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)', color=TEXT_SECONDARY)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("لا توجد سجلات مالية متوفرة حالياً")

    with col_chart2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:18px;'>🎯 هيكلة وتوزيع المخازن</h4>", unsafe_allow_html=True)
        inv_data = get_inventory_by_category()
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            fig = px.pie(
                df_inv, names='category', values='total', hole=0.72,
                color_discrete_sequence=['#8B5CF6', '#3B82F6', '#06B6D4', '#10B981', '#F59E0B']
            )
            fig.update_traces(
                textinfo='percent', 
                marker=dict(line=dict(color='#0f172a', width=3))
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', 
                font=dict(color=TEXT_PRIMARY, family='system-ui'), 
                margin=dict(t=5, b=5, l=5, r=5), showlegend=True,
                legend=dict(font=dict(color=TEXT_SECONDARY), orientation="h", y=-0.1)
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("المخازن فارغة حالياً")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ---------- القوائم والأوراق التنفيذية ----------
    col_list1, col_list2 = st.columns(2)
    
    with col_list1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:18px;'>⚠️ رقابة المخزون والحدود الحرجة</h4>", unsafe_allow_html=True)
        low = get_low_stock_products()
        if low:
            for item in low:
                st.markdown(f"""
                <div style="background: rgba(239, 68, 68, 0.04); border: 1px solid rgba(239, 68, 68, 0.1); border-radius: 16px; padding: 16px 20px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: {TEXT_PRIMARY}; font-weight: 600;">{item['name']}</span>
                    <span style="background: rgba(239,68,68,0.15); color: {RD}; padding: 4px 12px; border-radius: 8px; font-weight: 800; font-size: 0.85rem;">
                        المتبقي: {item['quantity']} / {item['reorder_level']}
                    </span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.03); border: 1px dashed rgba(16, 185, 129, 0.2); border-radius: 20px; padding: 24px; color: {GN}; font-weight: 600; text-align: center; font-size: 0.95rem;">
                🛡️ تأمين جرد المخازن مكتمل. جميع الأصناف بمستويات آمنة.
            </div>
            """, unsafe_allow_html=True)

    with col_list2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; font-weight:700; margin-bottom:18px;'>🕐 سجل العمليات والأنشطة الأخيرة</h4>", unsafe_allow_html=True)
        activities = get_recent_activities()
        if activities:
            for act in activities[:5]:
                # تحديد النقطة التفاعلية بناءً على نوع العملية
                dot_color = PR if 'فاتورة' in act['action'] else BL if 'قيد' in act['action'] else OR
                st.markdown(f"""
                <div class="luxury-card" style="padding: 14px 20px; margin-bottom: 10px; border-radius: 16px; box-shadow: none;">
                    <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                        <span style="background: {dot_color}; width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 10px {dot_color};"></span>
                        <div style="flex: 1; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <span style="color: {TEXT_PRIMARY}; font-weight: 500; font-size: 0.92rem;">{act['action']}</span>
                            <small style="color: {TEXT_SECONDARY}; font-size: 0.8rem; font-weight: 500;">{act['time']}</small>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.01); border: 1px dashed rgba(255,255,255,0.05); border-radius: 20px; padding: 24px; color: {TEXT_SECONDARY}; text-align: center; font-size: 0.95rem;">
                لا توجد مستجدات في سجل العمليات حالياً.
            </div>
            """, unsafe_allow_html=True)
