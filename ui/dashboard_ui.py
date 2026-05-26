# ui/dashboard_ui.py – لوحة معلومات احترافية (تصميم زجاجي فخم + KPIs + تنبيهات فورية)
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

# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.10)"
GLASS_BORDER = "rgba(255, 255, 255, 0.20)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_CYAN = "#06B6D4"
ACCENT_PINK = "#EC4899"

def kpi_card(icon, title, value, color, subtitle=""):
    """بطاقة KPI زجاجية"""
    return f"""
    <div style="
        background:{GLASS_BG}; backdrop-filter:blur(12px);
        border:1px solid {GLASS_BORDER}; border-radius:16px;
        padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};
        margin-bottom:0.8rem; transition: transform 0.2s;
    ">
        <div style="font-size:2rem; margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.8rem;">{title}</div>
        <div style="color:{color}; font-size:1.6rem; font-weight:800;">{value}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.7rem;">{subtitle}</div>
    </div>
    """

def alert_card(alert):
    """بطاقة تنبيه زجاجية"""
    colors = {
        "warning": ACCENT_ORANGE,
        "danger": ACCENT_RED,
        "info": ACCENT_BLUE,
        "success": ACCENT_GREEN
    }
    color = colors.get(alert['type'], ACCENT_BLUE)
    return f"""
    <div style="
        background:{GLASS_BG}; backdrop-filter:blur(12px);
        border:1px solid {color}; border-radius:12px;
        padding:1rem; margin-bottom:0.5rem;
        box-shadow:{GLASS_SHADOW}; display:flex; align-items:center; gap:0.8rem;
    ">
        <div style="font-size:1.5rem;">{alert['icon']}</div>
        <div style="flex:1;">
            <div style="color:{color}; font-weight:700; font-size:0.9rem;">{alert['title']}</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.8rem;">{alert['message']}</div>
        </div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.7rem;">{alert['time']}</div>
    </div>
    """

def show():
    kpi = get_kpi_cards()
    quick = get_quick_stats()
    alerts = get_alerts()

    # ---------- تحية ----------
    user_name = st.session_state.user.get("full_name", "المستخدم")
    hour = datetime.now().hour
    greeting = "صباح الخير" if hour < 12 else "مساء الخير"

    st.markdown(f"""
    <div style="margin-bottom:1.5rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.5rem; margin:0; text-shadow:0 0 15px {ACCENT_PURPLE};">{greeting}، {user_name} ✨</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.1rem;">لوحة المعلومات والمؤشرات الرئيسية</p>
    </div>
    """, unsafe_allow_html=True)

    # ---------- 🆕 إحصائيات اليوم السريعة ----------
    st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; margin-bottom:0.5rem;'>📅 ملخص اليوم</h4>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(kpi_card("💰", "مبيعات اليوم", f"{quick['today_sales']:,.0f}", ACCENT_GREEN), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_card("🛒", "مشتريات اليوم", f"{quick['today_purchases']:,.0f}", ACCENT_RED), unsafe_allow_html=True)
    with col3:
        st.markdown(kpi_card("📦", "منتجات منخفضة", quick['low_stock'], ACCENT_ORANGE if quick['low_stock'] > 0 else ACCENT_GREEN), unsafe_allow_html=True)
    with col4:
        st.markdown(kpi_card("👥", "إجمالي العملاء", quick['total_customers'], ACCENT_BLUE), unsafe_allow_html=True)

    # ---------- 🆕 التنبيهات الفورية ----------
    if alerts:
        st.markdown("---")
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; margin-bottom:0.5rem;'>🔔 التنبيهات الفورية</h4>", unsafe_allow_html=True)
        cols = st.columns(min(len(alerts), 3))
        for i, alert in enumerate(alerts):
            with cols[i % 3]:
                st.markdown(alert_card(alert), unsafe_allow_html=True)

    st.markdown("---")

    # ---------- الصف الأول: بطاقات KPI رئيسية ----------
    st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; margin-bottom:0.5rem;'>📊 المؤشرات الرئيسية</h4>", unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(kpi_card("💰", "المبيعات", f"{kpi['total_sales']:,.0f}", ACCENT_GREEN, "إجمالي المبيعات"), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_card("🛒", "المشتريات", f"{kpi['total_purchases']:,.0f}", ACCENT_RED, "إجمالي المشتريات"), unsafe_allow_html=True)
    with col3:
        net = kpi['net_income']
        st.markdown(kpi_card("💎", "صافي الدخل", f"{net:,.0f}", ACCENT_GREEN if net >= 0 else ACCENT_RED, "الإيرادات - المصروفات"), unsafe_allow_html=True)
    with col4:
        st.markdown(kpi_card("📦", "المنتجات", kpi['products_count'], ACCENT_BLUE, "عدد المنتجات"), unsafe_allow_html=True)
    with col5:
        st.markdown(kpi_card("👥", "العملاء", kpi['customers_count'], ACCENT_ORANGE, "عدد العملاء"), unsafe_allow_html=True)

    # ---------- الصف الثاني: بطاقات إضافية ----------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(kpi_card("🏢", "الموردين", kpi['suppliers_count'], ACCENT_PURPLE), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_card("👤", "الموظفين", kpi['employees_count'], ACCENT_CYAN), unsafe_allow_html=True)
    with col3:
        st.markdown(kpi_card("📋", "إجمالي الكميات", kpi['total_qty'], ACCENT_BLUE), unsafe_allow_html=True)
    with col4:
        growth = ((kpi['total_sales'] - kpi['total_purchases']) / (kpi['total_purchases'] or 1)) * 100
        st.markdown(kpi_card("📈", "نمو الإيرادات", f"{growth:.1f}%", ACCENT_GREEN if growth > 0 else ACCENT_RED), unsafe_allow_html=True)

    st.markdown("---")

    # ---------- الصف الثالث: رسوم بيانية ----------
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📊 توزيع المخزون حسب الفئة</h4>", unsafe_allow_html=True)
        inv_data = get_inventory_by_category()
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            if df_inv['total'].sum() > 0:
                fig = px.pie(df_inv, names='category', values='total', hole=0.5,
                            color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'])
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color=TEXT_PRIMARY), margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد منتجات لعرضها")
        else:
            st.info("لا توجد منتجات")
    
    with col2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📈 المبيعات الشهرية</h4>", unsafe_allow_html=True)
        sales_data = get_monthly_sales()
        if sales_data:
            df_sales = pd.DataFrame(sales_data)
            df_sales = df_sales.sort_values('month')
            fig = px.bar(df_sales, x='month', y='total', color_discrete_sequence=['#3B82F6'])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color=TEXT_PRIMARY), margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات مبيعات")

    st.markdown("---")

    # ---------- الصف الرابع: أفضل المنتجات + المنتجات المنخفضة ----------
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>🏆 أفضل المنتجات مبيعاً</h4>", unsafe_allow_html=True)
        top = get_top_products()
        if top:
            df_top = pd.DataFrame(top)
            st.dataframe(df_top, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد بيانات مبيعات بعد")
    
    with col2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>⚠️ منتجات منخفضة المخزون</h4>", unsafe_allow_html=True)
        low = get_low_stock_products()
        if low:
            df_low = pd.DataFrame(low)
            st.dataframe(df_low, use_container_width=True, hide_index=True)
        else:
            st.success("جميع المنتجات بمستويات آمنة")

    st.markdown("---")

    # ---------- الصف الخامس: آخر الفواتير + آخر الأنشطة ----------
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📄 آخر الفواتير</h4>", unsafe_allow_html=True)
        invoices = get_recent_invoices()
        if invoices:
            df_inv = pd.DataFrame(invoices)
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد فواتير بعد")
    
    with col2:
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>🕐 آخر الأنشطة</h4>", unsafe_allow_html=True)
        activities = get_recent_activities()
        if activities:
            df_act = pd.DataFrame(activities)
            st.dataframe(df_act, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أنشطة مسجلة")
