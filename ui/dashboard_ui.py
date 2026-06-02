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

# ========== ألوان وتأثيرات فاخرة ==========
GLASS_BG = "rgba(255, 255, 255, 0.06)"
GLASS_BORDER = "rgba(255, 255, 255, 0.15)"
GLASS_SHADOW = "0 15px 35px rgba(0,0,0,0.4)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_CYAN = "#06B6D4"
GRADIENT_PURPLE = "linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)"

def kpi_card(title, value, icon, color, delta="", delta_color="normal"):
    """بطاقة KPI زجاجية بتصميم عصري"""
    return f"""
    <div style="
        background: {GLASS_BG}; backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid {GLASS_BORDER}; border-radius: 20px; padding: 1.5rem 1.8rem;
        box-shadow: {GLASS_SHADOW}; display: flex; align-items: center; justify-content: space-between;
        transition: all 0.3s ease; height: 100%;
    ">
        <div>
            <div style="color: {TEXT_SECONDARY}; font-size: 0.85rem; margin-bottom: 8px; font-weight: 500;">{title}</div>
            <div style="color: {TEXT_PRIMARY}; font-size: 2rem; font-weight: 800; line-height: 1.2;">{value}</div>
            <div style="color: {'#10B981' if '↑' in delta else '#EF4444' if '↓' in delta else TEXT_SECONDARY}; font-size: 0.8rem; margin-top: 5px;">
                {delta}
            </div>
        </div>
        <div style="
            background: rgba(255,255,255,0.05); border-radius: 16px; width: 55px; height: 55px;
            display: flex; align-items: center; justify-content: center; font-size: 2rem;
        ">{icon}</div>
    </div>
    """

def show():
    user_name = st.session_state.user.get("full_name", "المستخدم")
    kpi = get_kpi_cards()
    quick = get_quick_stats()
    alerts = get_alerts()

    # ---------- رأس الصفحة مع تحية فاخرة ----------
    st.markdown(f"""
    <div style="
        background: {GRADIENT_PURPLE}; backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border-radius: 24px; padding: 30px 35px; margin-bottom: 35px;
        border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: space-between;
    ">
        <div>
            <h1 style="color: white; font-size: 2.4rem; margin: 0; font-weight: 800;">مرحباً، {user_name} 👋</h1>
            <p style="color: rgba(255,255,255,0.8); font-size: 1.1rem; margin: 8px 0 0 0;">إليك ملخص أداء أعمالك اليوم، {datetime.now().strftime('%A %d %B %Y')}</p>
        </div>
        <div style="font-size: 4rem; opacity: 0.6;">📊</div>
    </div>
    """, unsafe_allow_html=True)

    # ---------- إحصائيات سريعة (4 بطاقات) ----------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(kpi_card("مبيعات اليوم", f"{quick['today_sales']:,.0f} ر.ي", "💰", ACCENT_GREEN, "↑ 12% عن أمس"), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_card("مشتريات اليوم", f"{quick['today_purchases']:,.0f} ر.ي", "🛒", ACCENT_RED, "↓ 5% عن أمس"), unsafe_allow_html=True)
    with col3:
        st.markdown(kpi_card("منتجات منخفضة", str(quick['low_stock']), "⚠️", ACCENT_ORANGE if quick['low_stock'] > 0 else ACCENT_GREEN, "يحتاج إعادة طلب" if quick['low_stock'] > 0 else "الكل آمن"), unsafe_allow_html=True)
    with col4:
        st.markdown(kpi_card("العملاء", str(quick['total_customers']), "👥", ACCENT_BLUE, "+3 هذا الشهر"), unsafe_allow_html=True)

    # ---------- تنبيهات فورية (إن وجدت) ----------
    if alerts:
        st.markdown("<br>", unsafe_allow_html=True)
        alert_cols = st.columns(len(alerts))
        for i, alert in enumerate(alerts):
            with alert_cols[i]:
                st.warning(f"{alert['icon']} **{alert['title']}**\n\n{alert['message']}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------- مؤشرات الأداء الرئيسية (5 بطاقات) ----------
    st.markdown(f"<h3 style='color:{TEXT_PRIMARY}; margin-bottom:15px;'>📊 الأداء العام</h3>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(kpi_card("إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "💵", ACCENT_GREEN), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card("إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📦", ACCENT_RED), unsafe_allow_html=True)
    with c3:
        net = kpi['net_income']
        st.markdown(kpi_card("صافي الدخل", f"{net:,.0f}", "💎", ACCENT_GREEN if net >=0 else ACCENT_RED), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card("المنتجات", kpi['products_count'], "🏷️", ACCENT_BLUE), unsafe_allow_html=True)
    with c5:
        st.markdown(kpi_card("العملاء", kpi['customers_count'], "👥", ACCENT_ORANGE), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------- الرسوم البيانية الرئيسية ----------
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📈 المبيعات الشهرية</h4>", unsafe_allow_html=True)
        sales_data = get_monthly_sales()
        if sales_data:
            df_sales = pd.DataFrame(sales_data).sort_values('month')
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_sales['month'], y=df_sales['total'],
                                 marker=dict(color=df_sales['total'], colorscale='Blues', line=dict(width=0)),
                                 hovertemplate='%{y:,.0f} ر.ي', name='المبيعات'))
            fig.add_trace(go.Scatter(x=df_sales['month'], y=df_sales['total'].rolling(2).mean(),
                                     mode='lines+markers', line=dict(color='#F59E0B', width=3), name='المتوسط'))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              font=dict(color=TEXT_PRIMARY), margin=dict(t=0, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات")

    with col_chart2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>🎯 توزيع المخزون</h4>", unsafe_allow_html=True)
        inv_data = get_inventory_by_category()
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            fig = px.pie(df_inv, names='category', values='total', hole=0.6,
                         color_discrete_sequence=px.colors.sequential.Blugrn)
            fig.update_traces(textinfo='percent+label', marker=dict(line=dict(color='rgba(0,0,0,0)', width=0)))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_PRIMARY), margin=dict(t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد منتجات")

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------- القوائم السفلية ----------
    col_list1, col_list2 = st.columns(2)
    with col_list1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>⚠️ منتجات على وشك النفاد</h4>", unsafe_allow_html=True)
        low = get_low_stock_products()
        if low:
            for item in low:
                st.error(f"📦 **{item['name']}** - المتبقي: {item['quantity']} (الحد الأدنى: {item['reorder_level']})")
        else:
            st.success("جميع المنتجات بمستويات آمنة ✅")

    with col_list2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>🕐 آخر الأنشطة</h4>", unsafe_allow_html=True)
        activities = get_recent_activities()
        if activities:
            for act in activities[:5]:
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;color:{TEXT_SECONDARY};">
                    <span style="font-size:1.2rem;">{'📄' if 'فاتورة' in act['action'] else '🔄' if 'قيد' in act['action'] else '👤'}</span>
                    <span style="flex:1;">{act['action']} - <small>{act['time']}</small></span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("لا توجد أنشطة")
