# ui/dashboard_ui.py
# لوحة معلومات حوكمة ERP – تصميم تنفيذي زجاجي احترافي

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from datetime import datetime
from html import escape

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

# ============================================================
# ألوان النظام
# ============================================================
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

PR = "#8B5CF6"
BL = "#3B82F6"
GN = "#10B981"
RD = "#EF4444"
OR = "#F59E0B"
CY = "#06B6D4"

# ============================================================
# أدوات مساعدة آمنة
# ============================================================
def safe_number(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def format_number(value):
    return f"{safe_number(value):,.0f}"

def safe_text(value, default=""):
    if value is None:
        return default
    return escape(str(value))

def get_value(data, *keys, default=0):
    if not isinstance(data, dict):
        return default
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default

# ============================================================
# نظام التصميم
# ============================================================
def inject_executive_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap');

    :root {
        --primary: #8B5CF6;
        --blue: #3B82F6;
        --green: #10B981;
        --red: #EF4444;
        --orange: #F59E0B;
        --cyan: #06B6D4;
    }

    .main, .main p, .main span, .main div, .main h1, .main h2, .main h3, .main h4 {
        font-family: 'Cairo', sans-serif;
    }

    @keyframes dashboardFade {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes pulseGlow {
        0%, 100% { opacity: 0.65; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.15); }
    }

    .dashboard-section {
        animation: dashboardFade 0.45s ease-out;
    }

    .section-heading {
        color: #F8FAFC;
        font-size: 1.35rem;
        font-weight: 800;
        margin: 28px 0 18px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .section-subtitle {
        color: #94A3B8;
        font-size: 0.85rem;
        margin-top: -12px;
        margin-bottom: 20px;
    }

    .luxury-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 17px;
        margin-bottom: 24px;
        width: 100%;
    }

    .luxury-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.68), rgba(15, 23, 42, 0.78));
        border: 1px solid rgba(255,255,255,0.075);
        border-top: 1px solid rgba(255,255,255,0.15);
        border-radius: 20px;
        padding: 23px 21px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 115px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 12px 30px rgba(0,0,0,0.20), inset 0 1px 0 rgba(255,255,255,0.025);
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    }

    .luxury-card::before {
        content: "";
        position: absolute;
        top: 0;
        right: 0;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle at top right, rgba(255,255,255,0.055), transparent 65%);
        pointer-events: none;
    }

    .luxury-card:hover {
        transform: translateY(-4px);
        border-color: rgba(167,139,250,0.35);
        box-shadow: 0 18px 38px rgba(0,0,0,0.30), 0 0 18px rgba(139,92,246,0.06);
    }

    .card-content {
        flex: 1;
        min-width: 0;
        position: relative;
        z-index: 2;
    }

    .card-title {
        color: #94A3B8;
        font-size: 0.88rem;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .card-value {
        color: #F8FAFC;
        font-size: 1.75rem;
        font-weight: 900;
        line-height: 1.3;
        overflow-wrap: anywhere;
    }

    .card-delta {
        margin-top: 7px;
        font-size: 0.78rem;
        font-weight: 700;
    }

    .card-icon {
        width: 55px;
        height: 55px;
        min-width: 55px;
        border-radius: 17px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.7rem;
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.07);
        margin-right: 13px;
        position: relative;
        z-index: 2;
    }

    .dashboard-header {
        background: linear-gradient(120deg, rgba(76,29,149,0.30), rgba(30,41,59,0.78), rgba(15,23,42,0.90));
        border: 1px solid rgba(255,255,255,0.10);
        border-top: 1px solid rgba(255,255,255,0.18);
        border-radius: 26px;
        padding: 30px 34px;
        margin-bottom: 28px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 20px;
        flex-wrap: wrap;
        box-shadow: 0 22px 50px rgba(0,0,0,0.25);
        animation: dashboardFade 0.5s ease-out;
    }

    .header-label {
        color: #A78BFA;
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        margin-bottom: 7px;
    }

    .header-title {
        color: #FFFFFF;
        font-size: 2.15rem;
        font-weight: 900;
        margin: 0;
        line-height: 1.5;
    }

    .header-description {
        color: #94A3B8;
        font-size: 0.93rem;
        margin-top: 8px;
    }

    .header-icon {
        width: 82px;
        height: 82px;
        display: flex;
        justify-content: center;
        align-items: center;
        border-radius: 23px;
        font-size: 2.7rem;
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.08);
    }

    .alert-card {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 15px 18px;
        margin-bottom: 12px;
        border-radius: 14px;
        background: rgba(245,158,11,0.065);
        border: 1px solid rgba(245,158,11,0.18);
        border-right: 4px solid #F59E0B;
        color: #F8FAFC;
    }

    .alert-title {
        font-weight: 800;
        color: #FCD34D;
        margin-bottom: 3px;
    }

    .alert-message {
        color: #CBD5E1;
        font-size: 0.9rem;
    }

    .list-card {
        background: rgba(30,41,59,0.45);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 15px;
        padding: 14px 16px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        transition: 0.2s ease;
    }

    .list-card:hover {
        border-color: rgba(139,92,246,0.30);
        background: rgba(30,41,59,0.68);
    }

    .list-name {
        color: #F8FAFC;
        font-weight: 600;
        font-size: 0.9rem;
        overflow-wrap: anywhere;
    }

    .list-value {
        color: #FCA5A5;
        background: rgba(239,68,68,0.13);
        padding: 5px 11px;
        border-radius: 8px;
        font-weight: 800;
        font-size: 0.78rem;
        white-space: nowrap;
    }

    .activity-card {
        background: rgba(30,41,59,0.40);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 13px 15px;
        margin-bottom: 9px;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .activity-dot {
        width: 9px;
        height: 9px;
        min-width: 9px;
        border-radius: 50%;
        animation: pulseGlow 2s infinite;
    }

    .activity-text {
        color: #E2E8F0;
        font-size: 0.88rem;
        font-weight: 500;
        overflow-wrap: anywhere;
    }

    .activity-time {
        color: #94A3B8;
        font-size: 0.75rem;
        white-space: nowrap;
    }

    .empty-state {
        background: rgba(255,255,255,0.018);
        border: 1px dashed rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 25px 15px;
        text-align: center;
        color: #94A3B8;
        font-size: 0.9rem;
    }

    .success-state {
        background: rgba(16,185,129,0.045);
        border: 1px dashed rgba(16,185,129,0.25);
        border-radius: 18px;
        padding: 24px;
        text-align: center;
        color: #6EE7B7;
        font-weight: 700;
    }

    @media (max-width: 768px) {
        .luxury-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 11px;
        }
        .luxury-card {
            padding: 15px 12px;
            min-height: 100px;
        }
        .card-value {
            font-size: 1.25rem;
        }
        .card-title {
            font-size: 0.75rem;
        }
        .card-icon {
            width: 40px;
            height: 40px;
            min-width: 40px;
            font-size: 1.3rem;
            margin-right: 8px;
        }
        .header-title {
            font-size: 1.55rem;
        }
        .dashboard-header {
            padding: 23px 19px;
        }
        .header-icon {
            width: 60px;
            height: 60px;
            font-size: 2rem;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .dashboard-section, .activity-dot {
            animation: none !important;
        }
        .luxury-card {
            transition: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def make_premium_card(title, value, icon, accent_color, delta=""):
    delta_html = ""
    if delta:
        delta_color = TEXT_SECONDARY
        if "↑" in delta:
            delta_color = GN
        elif "↓" in delta:
            delta_color = RD
        delta_html = f'<div class="card-delta" style="color:{delta_color};">{safe_text(delta)}</div>'

    return f"""
    <div class="luxury-card">
        <div class="card-content">
            <div class="card-title">{safe_text(title)}</div>
            <div class="card-value">{safe_text(value)}</div>
            {delta_html}
        </div>
        <div class="card-icon" style="color:{accent_color}; box-shadow:0 0 20px {accent_color}12;">
            {icon}
        </div>
    </div>
    """

def section_heading(title, subtitle=None):
    st.markdown(f'<div class="section-heading">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{safe_text(subtitle)}</div>', unsafe_allow_html=True)

# ============================================================
# دوال العرض
# ============================================================
def render_alerts(alerts):
    if not alerts: return
    section_heading("🔔 التنبيهات الذكية", "الملاحظات التي تحتاج إلى متابعة")
    for alert in alerts:
        if not isinstance(alert, dict): continue
        icon = safe_text(alert.get("icon", "⚠️"))
        title = safe_text(alert.get("title", "تنبيه"))
        message = safe_text(alert.get("message", ""))
        
        st.markdown(f"""
            <div class="alert-card">
                <div style="font-size:1.35rem;">{icon}</div>
                <div>
                    <div class="alert-title">{title}</div>
                    <div class="alert-message">{message}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_sales_chart():
    section_heading("📈 الأداء المالي", "اتجاه المبيعات الشهرية")
    sales_data = get_monthly_sales()
    
    if not sales_data:
        st.markdown('<div class="empty-state">لا توجد سجلات مالية متوفرة حالياً</div>', unsafe_allow_html=True)
        return

    df_sales = pd.DataFrame(sales_data)
    if not {"month", "total"}.issubset(df_sales.columns):
        st.warning("بيانات المبيعات لا تحتوي على الحقول المطلوبة.")
        return

    df_sales["total"] = pd.to_numeric(df_sales["total"], errors="coerce").fillna(0)
    df_sales = df_sales.sort_values("month")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_sales["month"], y=df_sales["total"], name="المبيعات",
        marker=dict(color=df_sales["total"], colorscale=[[0, "#3B82F6"], [1, "#8B5CF6"]], line=dict(width=0)),
        hovertemplate="%{y:,.0f} ر.ي<extra></extra>"
    ))

    if len(df_sales) >= 2:
        rolling = df_sales["total"].rolling(window=2, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df_sales["month"], y=rolling, mode="lines", name="متوسط الاتجاه",
            line=dict(color=OR, width=3, shape="spline"),
            hovertemplate="%{y:,.0f} ر.ي<extra></extra>"
        ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_PRIMARY, family="Cairo"),
        margin=dict(t=15, b=15, l=10, r=10), height=330, showlegend=False,
        xaxis=dict(showgrid=False, color=TEXT_SECONDARY, title=None),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", color=TEXT_SECONDARY, title=None),
        hoverlabel=dict(bgcolor="#1E293B", font_color="#FFFFFF", font_family="Cairo")
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})

def render_inventory_chart():
    section_heading("🎯 توزيع المخزون", "توزيع الكميات حسب التصنيف")
    inv_data = get_inventory_by_category()
    
    if not inv_data:
        st.markdown('<div class="empty-state">لا توجد بيانات مخزون لعرضها حالياً</div>', unsafe_allow_html=True)
        return

    df_inv = pd.DataFrame(inv_data)
    if not {"category", "total"}.issubset(df_inv.columns):
        st.warning("بيانات المخزون لا تحتوي على الحقول المطلوبة.")
        return

    df_inv["total"] = pd.to_numeric(df_inv["total"], errors="coerce").fillna(0)
    df_inv = df_inv[df_inv["total"] > 0]

    if df_inv.empty:
        st.markdown('<div class="empty-state">لا توجد كميات متاحة للتصنيف حالياً</div>', unsafe_allow_html=True)
        return

    fig = px.pie(
        df_inv, names="category", values="total", hole=0.68,
        color_discrete_sequence=["#8B5CF6", "#3B82F6", "#06B6D4", "#10B981", "#F59E0B", "#EC4899"]
    )
    fig.update_traces(
        textinfo="percent", textfont=dict(color="#FFFFFF", size=12),
        marker=dict(line=dict(color="#0F172A", width=3)),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{percent}<extra></extra>"
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_PRIMARY, family="Cairo"),
        margin=dict(t=10, b=10, l=10, r=10), height=330,
        legend=dict(font=dict(color=TEXT_SECONDARY, family="Cairo"), orientation="h", y=-0.13),
        hoverlabel=dict(bgcolor="#1E293B", font_color="#FFFFFF", font_family="Cairo")
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})

def render_low_stock():
    section_heading("⚠️ رقابة المخزون", "الأصناف التي وصلت إلى حد إعادة الطلب")
    low = get_low_stock_products()

    if not low:
        st.markdown('<div class="success-state">🛡️ حالة المخزون مستقرة<br>جميع الأصناف ضمن مستويات المخزون الآمنة.</div>', unsafe_allow_html=True)
        return

    for item in low:
        name = safe_text(item.get("name", "صنف غير معروف"))
        quantity = format_number(item.get("quantity", 0))
        reorder = format_number(item.get("reorder_level", 0))
        
        st.markdown(f"""
            <div class="list-card">
                <div class="list-name">📦 {name}</div>
                <div class="list-value">المتبقي: {quantity} / {reorder}</div>
            </div>
            """, unsafe_allow_html=True)

def render_activities():
    section_heading("🕐 آخر العمليات", "أحدث الأنشطة المسجلة في النظام")
    activities = get_recent_activities()

    if not activities:
        st.markdown('<div class="empty-state">لا توجد أنشطة مسجلة حتى الآن</div>', unsafe_allow_html=True)
        return

    for act in activities[:6]:
        action = safe_text(act.get("action", "عملية"))
        time_value = safe_text(act.get("time") or act.get("created_at") or act.get("timestamp") or "")

        if "فاتورة" in action:
            dot_color = PR
        elif "قيد" in action:
            dot_color = BL
        else:
            dot_color = OR

        st.markdown(f"""
            <div class="activity-card">
                <span class="activity-dot" style="background:{dot_color}; box-shadow:0 0 10px {dot_color};"></span>
                <div style="flex:1; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                    <span class="activity-text">{action}</span>
                    <span class="activity-time">{time_value}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_top_products():
    section_heading("🏆 المنتجات الأكثر مبيعاً", "الأصناف الأعلى أداءً وفق بيانات المبيعات")
    try:
        products = get_top_products()
    except Exception:
        products = []

    if not products:
        st.markdown('<div class="empty-state">لا توجد بيانات كافية لعرض المنتجات الأكثر مبيعاً</div>', unsafe_allow_html=True)
        return

    for index, item in enumerate(products[:5], start=1):
        name = safe_text(get_value(item, "name", "product_name", "item_name", default="منتج"))
        quantity = format_number(get_value(item, "quantity", "total_quantity", "sold_quantity", default=0))
        
        st.markdown(f"""
            <div class="list-card">
                <div class="list-name"><span style="color:#A78BFA;font-weight:900;">{index}.</span> {name}</div>
                <div style="color:#6EE7B7; background:rgba(16,185,129,0.10); padding:5px 11px; border-radius:8px; font-size:0.8rem; font-weight:800; white-space:nowrap;">
                    المباع: {quantity}
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_recent_invoices():
    section_heading("🧾 أحدث الفواتير", "آخر الفواتير المسجلة في النظام")
    try:
        invoices = get_recent_invoices()
    except Exception:
        invoices = []

    if not invoices:
        st.markdown('<div class="empty-state">لا توجد فواتير حديثة لعرضها</div>', unsafe_allow_html=True)
        return

    for item in invoices[:5]:
        # ✅ قراءة المفاتيح من الخدمة
        invoice_number = safe_text(get_value(item, "id", default="—"))
        party = safe_text(get_value(item, "party_name", default="غير محدد"))
        total = format_number(get_value(item, "total", default=0))
        
        inv_type = item.get("type", "")
        type_label = "مبيعات" if inv_type == "sale" else "مشتريات"
        type_color = "#60A5FA" if inv_type == "sale" else "#F87171"

        st.markdown(f"""
            <div class="list-card">
                <div style="flex:1;min-width:0;">
                    <div class="list-name">
                        فاتورة #{invoice_number} 
                        <span style="color:{type_color}; font-size:0.75rem; margin-right:5px;">({type_label})</span>
                    </div>
                    <div style="color:#94A3B8; font-size:0.78rem; margin-top:4px;">{party}</div>
                </div>
                <div style="color:#93C5FD; background:rgba(59,130,246,0.11); padding:6px 10px; border-radius:8px; font-size:0.82rem; font-weight:800; white-space:nowrap;">
                    {total} ر.ي
                </div>
            </div>
            """, unsafe_allow_html=True)

# ============================================================
# الدالة الرئيسية
# ============================================================
def show():
    inject_executive_css()
    
    user = st.session_state.get("user") or {}
    user_name = safe_text(user.get("full_name") or user.get("username") or "المستخدم")

    try:
        kpi = get_kpi_cards() or {}
        quick = get_quick_stats() or {}
        alerts = get_alerts() or []
    except Exception as error:
        st.error(f"تعذر تحميل بيانات لوحة المعلومات: {error}")
        return

    current_date = datetime.now().strftime("%Y-%m-%d")

    # 1. الهيدر
    st.markdown(f"""
        <div class="dashboard-header">
            <div>
                <div class="header-label">✦ ENTERPRISE MANAGEMENT HUB</div>
                <h1 class="header-title">مرحباً، {user_name}</h1>
                <div class="header-description">
                    إليك نظرة عامة على أداء منشأتك ومؤشرات العمليات.<br>
                    <span style="color:#C4B5FD; font-weight:700;">📅 {current_date}</span>
                </div>
            </div>
            <div class="header-icon">📊</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. ملخص اليوم
    section_heading("⚡ ملخص اليوم", "مؤشرات العمليات اليومية")
    
    html_quick = '<div class="luxury-grid">'
    html_quick += make_premium_card("مبيعات اليوم", f"{format_number(quick.get('today_sales', 0))} ر.ي", "💰", GN)
    html_quick += make_premium_card("مشتريات اليوم", f"{format_number(quick.get('today_purchases', 0))} ر.ي", "🛒", RD)
    
    low_stock_count = safe_number(quick.get("low_stock", 0))
    stock_status = "تحتاج إلى إعادة طلب" if low_stock_count > 0 else "المخزون مستقر"
    
    html_quick += make_premium_card("منتجات منخفضة", format_number(low_stock_count), "⚠️", RD if low_stock_count > 0 else GN, stock_status)
    html_quick += make_premium_card("إجمالي العملاء", format_number(quick.get("total_customers", 0)), "👥", BL)
    html_quick += "</div>"
    
    st.markdown(html_quick, unsafe_allow_html=True) # ✅ إضافة unsafe_allow_html

    # 3. التنبيهات
    render_alerts(alerts)

    # 4. الأداء المالي
    section_heading("💎 الأداء العام والمالي", "المؤشرات الإجمالية للمنشأة")
    
    html_perf = '<div class="luxury-grid">'
    html_perf += make_premium_card("إجمالي المبيعات", format_number(kpi.get("total_sales", 0)), "💵", GN)
    html_perf += make_premium_card("إجمالي المشتريات", format_number(kpi.get("total_purchases", 0)), "📦", RD)
    
    net_income = safe_number(kpi.get("net_income", 0))
    html_perf += make_premium_card("صافي الأرباح", format_number(net_income), "💎", GN if net_income >= 0 else RD)
    
    html_perf += make_premium_card("عدد المنتجات", format_number(kpi.get("products_count", 0)), "🏷️", BL)
    html_perf += make_premium_card("قاعدة العملاء", format_number(kpi.get("customers_count", 0)), "👥", OR)
    html_perf += "</div>"
    
    st.markdown(html_perf, unsafe_allow_html=True) # ✅ إضافة unsafe_allow_html

    # 5. التحليل المرئي
    section_heading("📊 التحليل المرئي", "قراءة الاتجاهات المالية وتوزيع المخزون")
    col_chart1, col_chart2 = st.columns(2, gap="large")
    with col_chart1:
        render_sales_chart()
    with col_chart2:
        render_inventory_chart()

    # 6. إدارة المخزون
    section_heading("📦 إدارة المخزون والمنتجات", "مراقبة مستويات المخزون وأداء الأصناف")
    col_stock, col_products = st.columns(2, gap="large")
    with col_stock:
        render_low_stock()
    with col_products:
        render_top_products()

    # 7. النشاط التشغيلي
    section_heading("🧾 النشاط التشغيلي", "متابعة آخر الحركات والفواتير")
    col_activity, col_invoices = st.columns(2, gap="large")
    with col_activity:
        render_activities()
    with col_invoices:
        render_recent_invoices()

    # 8. التذييل
    st.markdown("""
        <div style="margin-top:35px; padding:18px 10px; border-top:1px solid rgba(255,255,255,0.07); text-align:center; color:#64748B; font-size:0.78rem;">
            حوكمة ERP <span style="color:#8B5CF6;">✦</span> نظام الإدارة الذكية
        </div>
        """, unsafe_allow_html=True)
