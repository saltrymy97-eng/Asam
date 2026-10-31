import html
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from services.dashboard_service import (
    get_kpi_cards,
    get_quick_stats,
    get_alerts,
    get_inventory_by_category,
    get_monthly_sales,
    get_top_products,
    get_low_stock_products,
    get_recent_invoices,
    get_recent_activities,
)


# =========================================================
# الألوان والثوابت
# =========================================================

TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED = "#94A3B8"

PR = "#8B5CF6"
BL = "#3B82F6"
GN = "#10B981"
RD = "#EF4444"
OR = "#F59E0B"

BG_MAIN = "#0B1120"
BG_CARD = "rgba(15, 23, 42, 0.78)"
BORDER_COLOR = "rgba(148, 163, 184, 0.13)"


# =========================================================
# أدوات مساعدة
# =========================================================

def safe_text(value, default="—"):
    """تحويل القيم إلى نص آمن للعرض داخل HTML."""
    if value is None:
        return default

    value = str(value).strip()

    if not value or value.lower() in ("none", "nan"):
        return default

    return html.escape(value)


def get_value(item, key, default=None):
    """قراءة قيمة من قاموس أو كائن يدعم الوصول بالمفاتيح."""
    if item is None:
        return default

    if isinstance(item, dict):
        return item.get(key, default)

    try:
        return item[key]
    except (KeyError, TypeError, IndexError):
        return getattr(item, key, default)


def format_number(value, decimals=0):
    """تنسيق الأرقام مع معالجة القيم غير الصالحة."""
    try:
        if value is None:
            number = 0
        else:
            number = float(value)

        if pd.isna(number):
            number = 0

        if decimals:
            return f"{number:,.{decimals}f}"

        return f"{number:,.0f}"

    except (ValueError, TypeError):
        return "0"


def safe_float(value, default=0):
    try:
        number = float(value)

        if pd.isna(number):
            return default

        return number

    except (ValueError, TypeError):
        return default


def section_heading(title, subtitle=""):
    """عنوان موحد للأقسام."""
    safe_title = safe_text(title)
    safe_subtitle = safe_text(subtitle, "")

    st.markdown(
        f"""
        <div class="section-heading">
            <div class="section-title">{safe_title}</div>
            <div class="section-subtitle">{safe_subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# CSS - التصميم العام
# =========================================================

def inject_executive_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap');

        :root {
            --dashboard-bg: #0B1120;
            --dashboard-card: rgba(15, 23, 42, 0.78);
            --dashboard-border: rgba(148, 163, 184, 0.13);
            --dashboard-text: #F1F5F9;
            --dashboard-muted: #94A3B8;
        }

        html, body, [class*="css"] {
            font-family: 'Cairo', sans-serif !important;
        }

        .stApp {
            background:
                radial-gradient(
                    circle at 90% 0%,
                    rgba(59, 130, 246, 0.09),
                    transparent 30%
                ),
                radial-gradient(
                    circle at 0% 30%,
                    rgba(139, 92, 246, 0.08),
                    transparent 28%
                ),
                #0B1120;
            color: var(--dashboard-text);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stMain"] {
            background: transparent;
        }

        .block-container {
            max-width: 1500px;
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }

        .dashboard-header {
            position: relative;
            overflow: hidden;
            padding: 27px 30px;
            margin-bottom: 25px;
            border: 1px solid var(--dashboard-border);
            border-radius: 22px;
            background:
                linear-gradient(
                    115deg,
                    rgba(30, 41, 59, 0.96),
                    rgba(15, 23, 42, 0.92)
                );
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.18);
        }

        .dashboard-header::after {
            content: "";
            position: absolute;
            width: 230px;
            height: 230px;
            left: -80px;
            top: -130px;
            border-radius: 50%;
            background: rgba(139, 92, 246, 0.13);
            filter: blur(8px);
            pointer-events: none;
        }

        .dashboard-title {
            color: #F8FAFC;
            font-size: 1.75rem;
            font-weight: 900;
            margin: 0;
            line-height: 1.6;
        }

        .dashboard-subtitle {
            color: #A5B4C8;
            font-size: 0.91rem;
            margin-top: 5px;
        }

        .dashboard-welcome {
            color: #C4B5FD;
            font-size: 0.9rem;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .section-heading {
            margin: 28px 0 15px 0;
            padding-right: 12px;
            border-right: 3px solid #8B5CF6;
        }

        .section-title {
            color: #F1F5F9;
            font-size: 1.08rem;
            font-weight: 900;
        }

        .section-subtitle {
            color: #94A3B8;
            font-size: 0.78rem;
            margin-top: 3px;
        }

        .luxury-card {
            position: relative;
            overflow: hidden;
            min-height: 135px;
            padding: 17px 18px;
            border-radius: 17px;
            border: 1px solid var(--dashboard-border);
            background: var(--dashboard-card);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.13);
            transition:
                transform 0.22s ease,
                border-color 0.22s ease,
                box-shadow 0.22s ease;
            direction: rtl;
            text-align: right;
        }

        .luxury-card:hover {
            transform: translateY(-4px);
            border-color: rgba(148, 163, 184, 0.30);
            box-shadow: 0 17px 35px rgba(0, 0, 0, 0.22);
        }

        .luxury-card::after {
            content: "";
            position: absolute;
            width: 95px;
            height: 95px;
            left: -35px;
            bottom: -48px;
            border-radius: 50%;
            background: var(--card-accent);
            opacity: 0.10;
            filter: blur(4px);
            pointer-events: none;
        }

        .card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }

        .card-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 39px;
            height: 39px;
            border-radius: 12px;
            background: var(--icon-bg);
            font-size: 1.2rem;
            flex-shrink: 0;
        }

        .card-label {
            color: #A8B5C8;
            font-size: 0.79rem;
            font-weight: 600;
        }

        .card-value {
            color: #F8FAFC;
            font-size: 1.45rem;
            font-weight: 900;
            margin-top: 13px;
            line-height: 1.5;
            overflow-wrap: anywhere;
        }

        .card-delta {
            color: #94A3B8;
            font-size: 0.70rem;
            margin-top: 4px;
        }

        .list-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 13px 15px;
            margin-bottom: 9px;
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 13px;
            background: rgba(15, 23, 42, 0.68);
            direction: rtl;
            text-align: right;
            transition: background 0.2s ease, border-color 0.2s ease;
        }

        .list-card:hover {
            background: rgba(30, 41, 59, 0.82);
            border-color: rgba(148, 163, 184, 0.25);
        }

        .list-name {
            color: #E2E8F0;
            font-size: 0.86rem;
            font-weight: 800;
            overflow-wrap: anywhere;
        }

        .list-description {
            color: #94A3B8;
            font-size: 0.75rem;
            margin-top: 4px;
            line-height: 1.7;
        }

        .list-value {
            color: #93C5FD;
            background: rgba(59, 130, 246, 0.11);
            padding: 6px 10px;
            border-radius: 8px;
            font-size: 0.82rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .empty-state {
            padding: 24px 15px;
            border: 1px dashed rgba(148, 163, 184, 0.23);
            border-radius: 14px;
            color: #94A3B8;
            background: rgba(15, 23, 42, 0.45);
            text-align: center;
            font-size: 0.85rem;
        }

        .alert-card {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 14px 15px;
            margin-bottom: 10px;
            border: 1px solid rgba(245, 158, 11, 0.18);
            border-radius: 13px;
            background: rgba(245, 158, 11, 0.055);
            direction: rtl;
            text-align: right;
        }

        .alert-icon {
            font-size: 1.25rem;
            flex-shrink: 0;
        }

        .alert-title {
            color: #FDE68A;
            font-size: 0.84rem;
            font-weight: 800;
        }

        .alert-message {
            color: #CBD5E1;
            font-size: 0.76rem;
            margin-top: 4px;
            line-height: 1.7;
        }

        .activity-time {
            color: #64748B;
            font-size: 0.70rem;
            white-space: nowrap;
        }

        .invoice-type {
            font-size: 0.72rem;
            font-weight: 700;
            margin-right: 5px;
        }

        .dashboard-footer {
            color: #64748B;
            text-align: center;
            font-size: 0.72rem;
            padding: 22px 0 5px;
        }

        [data-testid="stPlotlyChart"] {
            border: 1px solid rgba(148, 163, 184, 0.11);
            border-radius: 15px;
            background: rgba(15, 23, 42, 0.42);
            padding: 7px;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .dashboard-header {
                padding: 20px;
            }

            .dashboard-title {
                font-size: 1.35rem;
            }

            .card-value {
                font-size: 1.2rem;
            }

            .luxury-card {
                min-height: 120px;
                padding: 14px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# البطاقات
# =========================================================

def make_premium_card(
    title,
    value,
    icon,
    accent_shadow_color,
    delta=""
):
    safe_title = safe_text(title)
    safe_value = safe_text(value, "0")
    safe_icon = safe_text(icon, "📊")
    safe_delta = safe_text(delta, "")

    st.markdown(
        f"""
        <div class="luxury-card"
             style="
                --card-accent:{accent_shadow_color};
                --icon-bg:{accent_shadow_color}1C;
             ">
            <div class="card-top">
                <div class="card-label">{safe_title}</div>
                <div class="card-icon">{safe_icon}</div>
            </div>

            <div class="card-value">{safe_value}</div>
            <div class="card-delta">{safe_delta}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# رأس لوحة التحكم
# =========================================================

def render_dashboard_header(user_name=""):
    name = safe_text(user_name, "المستخدم")

    st.markdown(
        f"""
        <div class="dashboard-header">
            <div class="dashboard-welcome">
                مرحباً بك، {name} 👋
            </div>

            <div class="dashboard-title">
                لوحة التحكم الرئيسية
            </div>

            <div class="dashboard-subtitle">
                نظرة شاملة على أداء النظام والمبيعات والمخزون
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# الإحصائيات السريعة
# =========================================================

def render_quick_stats(stats):
    stats = stats or {}

    section_heading(
        "⚡ نظرة سريعة",
        "ملخص أهم المؤشرات اليومية"
    )

    cards = [
        (
            "مبيعات اليوم",
            format_number(stats.get("today_sales", 0)),
            "💰",
            GN,
            "إجمالي مبيعات اليوم"
        ),
        (
            "مشتريات اليوم",
            format_number(stats.get("today_purchases", 0)),
            "🛒",
            BL,
            "إجمالي مشتريات اليوم"
        ),
        (
            "منتجات منخفضة المخزون",
            format_number(stats.get("low_stock", 0)),
            "📦",
            OR,
            "تحتاج إلى متابعة"
        ),
        (
            "إجمالي العملاء",
            format_number(stats.get("total_customers", 0)),
            "👥",
            PR,
            "عدد العملاء المسجلين"
        ),
    ]

    columns = st.columns(4)

    for column, card in zip(columns, cards):
        with column:
            make_premium_card(*card)


# =========================================================
# التنبيهات
# =========================================================

def render_alerts(alerts):
    if not alerts:
        return

    section_heading(
        "🔔 التنبيهات",
        "أهم الملاحظات التي تحتاج إلى انتباهك"
    )

    for item in alerts:
        icon = safe_text(get_value(item, "icon", "🔔"))
        title = safe_text(get_value(item, "title", "تنبيه"))
        message = safe_text(get_value(item, "message", ""))

        st.markdown(
            f"""
            <div class="alert-card">
                <div class="alert-icon">{icon}</div>
                <div>
                    <div class="alert-title">{title}</div>
                    <div class="alert-message">{message}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================================================
# مؤشرات الأداء الرئيسية
# =========================================================

def render_kpi_cards(kpis):
    kpis = kpis or {}

    section_heading(
        "📊 مؤشرات الأداء",
        "ملخص الأداء المالي والتشغيلي"
    )

    cards = [
        (
            "إجمالي المبيعات",
            format_number(kpis.get("total_sales", 0)),
            "💰",
            GN,
            "إجمالي قيمة المبيعات"
        ),
        (
            "إجمالي المشتريات",
            format_number(kpis.get("total_purchases", 0)),
            "🛍️",
            BL,
            "إجمالي قيمة المشتريات"
        ),
        (
            "صافي الدخل",
            format_number(kpis.get("net_income", 0)),
            "📈",
            PR,
            "صافي الدخل المسجل"
        ),
        (
            "عدد المنتجات",
            format_number(kpis.get("products_count", 0)),
            "📦",
            OR,
            "المنتجات المسجلة"
        ),
        (
            "عدد العملاء",
            format_number(kpis.get("customers_count", 0)),
            "👥",
            "#06B6D4",
            "العملاء المسجلون"
        ),
    ]

    columns = st.columns(5)

    for column, card in zip(columns, cards):
        with column:
            make_premium_card(*card)


# =========================================================
# إعدادات الرسوم البيانية
# =========================================================

def apply_chart_theme(fig, height=330):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Cairo",
            color="#CBD5E1",
            size=12
        ),
        margin=dict(
            l=15,
            r=15,
            t=35,
            b=15
        ),
        hoverlabel=dict(
            bgcolor="#1E293B",
            font=dict(
                family="Cairo",
                color="#F8FAFC"
            ),
            bordercolor="#475569"
        ),
        legend=dict(
            font=dict(color="#CBD5E1"),
            bgcolor="rgba(0,0,0,0)"
        )
    )

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color="#94A3B8",
        linecolor="rgba(148,163,184,0.15)"
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.10)",
        zeroline=False,
        color="#94A3B8"
    )

    return fig


# =========================================================
# مخطط المبيعات الشهرية
# =========================================================

def render_monthly_sales():
    section_heading(
        "📈 حركة المبيعات",
        "تحليل المبيعات حسب الأشهر"
    )

    try:
        data = get_monthly_sales()
    except Exception:
        data = []

    if data is None:
        data = []

    df = pd.DataFrame(data)

    if df.empty or not {"month", "total"}.issubset(df.columns):
        st.markdown(
            '<div class="empty-state">لا توجد بيانات مبيعات كافية لعرض المخطط</div>',
            unsafe_allow_html=True
        )
        return

    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
    df["month"] = df["month"].fillna("غير محدد").astype(str)

    df = df.sort_values("month")

    df["average"] = df["total"].rolling(
        window=2,
        min_periods=1
    ).mean()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["month"],
            y=df["total"],
            name="المبيعات",
            marker=dict(
                color=df["total"],
                colorscale=[
                    [0, "#4338CA"],
                    [0.5, "#6366F1"],
                    [1, "#A78BFA"]
                ],
                line=dict(width=0)
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "المبيعات: %{y:,.0f} ر.ي"
                "<extra></extra>"
            )
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["month"],
            y=df["average"],
            name="متوسط متحرك",
            mode="lines+markers",
            line=dict(
                color="#34D399",
                width=2.5
            ),
            marker=dict(size=6),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "المتوسط: %{y:,.0f} ر.ي"
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        barmode="group",
        yaxis_title="القيمة بالريال اليمني",
        xaxis_title="الشهر"
    )

    apply_chart_theme(fig, height=350)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )


# =========================================================
# توزيع المخزون حسب الفئة
# =========================================================

def render_inventory_chart():
    section_heading(
        "📦 توزيع المخزون",
        "توزيع المنتجات حسب التصنيفات"
    )

    try:
        data = get_inventory_by_category()
    except Exception:
        data = []

    if data is None:
        data = []

    df = pd.DataFrame(data)

    if df.empty or not {"category", "total"}.issubset(df.columns):
        st.markdown(
            '<div class="empty-state">لا توجد بيانات مخزون لعرضها</div>',
            unsafe_allow_html=True
        )
        return

    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
    df["category"] = df["category"].fillna("غير مصنف").astype(str)

    df = df[df["total"] > 0]

    if df.empty:
        st.markdown(
            '<div class="empty-state">لا توجد كميات مخزون مسجلة حالياً</div>',
            unsafe_allow_html=True
        )
        return

    fig = px.pie(
        df,
        names="category",
        values="total",
        hole=0.65,
        color_discrete_sequence=[
            "#8B5CF6",
            "#3B82F6",
            "#10B981",
            "#F59E0B",
            "#EC4899",
            "#06B6D4",
            "#F87171"
        ]
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        marker=dict(
            line=dict(
                color="#0B1120",
                width=3
            )
        ),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "الكمية: %{value:,.0f}<br>"
            "النسبة: %{percent}"
            "<extra></extra>"
        )
    )

    apply_chart_theme(fig, height=350)

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )


# =========================================================
# المنتجات منخفضة المخزون
# =========================================================

def render_low_stock_products():
    section_heading(
        "⚠️ المنتجات منخفضة المخزون",
        "المنتجات التي وصلت إلى مستوى إعادة الطلب"
    )

    try:
        products = get_low_stock_products()
    except Exception:
        products = []

    if not products:
        st.markdown(
            '<div class="empty-state">لا توجد منتجات منخفضة المخزون حالياً</div>',
            unsafe_allow_html=True
        )
        return

    for item in products[:7]:
        name = safe_text(get_value(item, "name", "منتج غير محدد"))

        quantity = safe_float(
            get_value(item, "quantity", 0)
        )

        reorder_level = safe_float(
            get_value(item, "reorder_level", 0)
        )

        if reorder_level > 0:
            ratio = min(quantity / reorder_level, 1)
        else:
            ratio = 0

        if quantity <= 0:
            status = "نفد المخزون"
            color = RD
        else:
            status = "مخزون منخفض"
            color = OR

        st.markdown(
            f"""
            <div class="list-card">
                <div style="flex:1;min-width:0;">
                    <div class="list-name">{name}</div>
                    <div class="list-description">
                        حد إعادة الطلب: {format_number(reorder_level)}
                    </div>
                </div>

                <div style="text-align:left;min-width:90px;">
                    <div style="
                        color:{color};
                        font-size:0.78rem;
                        font-weight:800;
                    ">
                        {status}
                    </div>

                    <div style="
                        color:#E2E8F0;
                        font-size:0.82rem;
                        margin-top:4px;
                    ">
                        الكمية: {format_number(quantity)}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================================================
# أحدث الفواتير
# =========================================================

def render_recent_invoices():
    section_heading(
        "🧾 أحدث الفواتير",
        "آخر الفواتير المسجلة في النظام"
    )

    try:
        invoices = get_recent_invoices()
    except Exception:
        invoices = []

    if invoices is None or len(invoices) == 0:
        st.markdown(
            '<div class="empty-state">لا توجد فواتير حديثة لعرضها</div>',
            unsafe_allow_html=True
        )
        return

    for item in invoices[:5]:
        invoice_number = safe_text(
            get_value(item, "id", default="—")
        )

        party = safe_text(
            get_value(item, "party_name", default="غير محدد")
        )

        total = format_number(
            get_value(item, "total", default=0)
        )

        inv_type = get_value(item, "type", "")

        if inv_type == "sale":
            type_label = "مبيعات"
            type_color = "#60A5FA"
        elif inv_type == "purchase":
            type_label = "مشتريات"
            type_color = "#F87171"
        else:
            type_label = "فاتورة"
            type_color = "#A78BFA"

        st.markdown(
            f"""
            <div class="list-card">
                <div style="flex:1;min-width:0;">
                    <div class="list-name">
                        فاتورة #{invoice_number}
                        <span class="invoice-type"
                              style="color:{type_color};">
                            ({type_label})
                        </span>
                    </div>

                    <div class="list-description">
                        {party}
                    </div>
                </div>

                <div class="list-value">
                    {total} ر.ي
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================================================
# أحدث الأنشطة
# =========================================================

def render_recent_activities():
    section_heading(
        "🕘 أحدث الأنشطة",
        "آخر العمليات التي تمت داخل النظام"
    )

    try:
        activities = get_recent_activities()
    except Exception:
        activities = []

    if not activities:
        st.markdown(
            '<div class="empty-state">لا توجد أنشطة حديثة لعرضها</div>',
            unsafe_allow_html=True
        )
        return

    for item in activities[:7]:
        action = safe_text(
            get_value(item, "action", "نشاط جديد")
        )

        activity_time = get_value(
            item,
            "time",
            get_value(
                item,
                "created_at",
                get_value(item, "timestamp", "")
            )
        )

        activity_time = safe_text(activity_time, "")

        st.markdown(
            f"""
            <div class="list-card">
                <div style="
                    display:flex;
                    align-items:center;
                    gap:10px;
                    min-width:0;
                    flex:1;
                ">
                    <div class="card-icon"
                         style="
                            width:34px;
                            height:34px;
                            font-size:1rem;
                            color:#C4B5FD;
                            background:rgba(139,92,246,0.13);
                         ">
                        ⚡
                    </div>

                    <div class="list-name">
                        {action}
                    </div>
                </div>

                <div class="activity-time">
                    {activity_time}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================================================
# الصفحة الرئيسية
# =========================================================

def show():
    inject_executive_css()

    # بيانات المستخدم
    user_name = "المستخدم"

    try:
        if hasattr(st, "session_state"):
            user_data = st.session_state.get("user", {})

            if isinstance(user_data, dict):
                user_name = user_data.get(
                    "full_name",
                    user_data.get("name", "المستخدم")
                )
            elif user_data:
                user_name = getattr(
                    user_data,
                    "full_name",
                    getattr(user_data, "name", "المستخدم")
                )
    except Exception:
        user_name = "المستخدم"

    # تحميل بيانات لوحة التحكم
    try:
        quick_stats = get_quick_stats() or {}
    except Exception:
        quick_stats = {}

    try:
        kpis = get_kpi_cards() or {}
    except Exception:
        kpis = {}

    try:
        alerts = get_alerts() or []
    except Exception:
        alerts = []

    # رأس الصفحة
    render_dashboard_header(user_name)

    # الإحصائيات السريعة
    render_quick_stats(quick_stats)

    # التنبيهات
    render_alerts(alerts)

    # مؤشرات الأداء
    render_kpi_cards(kpis)

    # الرسوم البيانية
    section_heading(
        "📉 التحليلات والرسوم البيانية",
        "قراءة مرئية لأداء المبيعات والمخزون"
    )

    chart_col1, chart_col2 = st.columns(
        [1.5, 1],
        gap="large"
    )

    with chart_col1:
        render_monthly_sales()

    with chart_col2:
        render_inventory_chart()

    # المنتجات منخفضة المخزون والفواتير
    section_heading(
        "📋 متابعة العمليات",
        "المخزون والفواتير المسجلة مؤخراً"
    )

    col1, col2 = st.columns(
        2,
        gap="large"
    )

    with col1:
        render_low_stock_products()

    with col2:
        render_recent_invoices()

    # الأنشطة الأخيرة
    render_recent_activities()

    # التذييل
    st.markdown(
        """
        <div class="dashboard-footer">
            لوحة التحكم الرئيسية · جميع الحقوق محفوظة
        </div>
        """,
        unsafe_allow_html=True
    )
