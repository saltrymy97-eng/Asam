# ui/dashboard_ui.py – لوحة معلومات تنفيذية فاخرة (Dark Obsidian Glassmorphism)
from datetime import datetime
import textwrap
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
)

# ========== لوحة الألوان الملكية ==========
TEXT_MAIN = "#F9FAFB"
TEXT_MUTED = "#9CA3AF"
COLOR_PURPLE = "#8B5CF6"
COLOR_BLUE = "#3B82F6"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_AMBER = "#F59E0B"
BG_CARD = "rgba(17, 24, 39, 0.75)"


def inject_custom_theme():
  """حقن التنسيقات الفاخرة بشكل آمن دون إرباك تخطيط Streamlit"""
  css = textwrap.dedent("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;600;700;800;900&display=swap');

    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl;
        text-align: right;
    }

    /* خلفية فاخرة بتدرج داكن عميق */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 50%, #030712 100%) !important;
        background-attachment: fixed !important;
    }

    /* حماية عناصر القائمة الجانبية من التداخل */
    section[data-testid="stSidebar"] {
        z-index: 100 !important;
    }

    /* تحسين مظهر التمرير */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(139, 92, 246, 0.3);
        border-radius: 10px;
    }
    </style>
    """)
  st.markdown(css, unsafe_allow_html=True)


def create_kpi_card(title, value, icon, accent_color, subtitle=""):
  """إنشاء بطاقة إحصائية زجاجية ونقية بدون أخطاء Markdown"""
  sub_html = (
      f'<div style="font-size: 0.8rem; font-weight: 700; color:'
      f' {accent_color}; margin-top: 6px;">{subtitle}</div>'
      if subtitle
      else ""
  )

  card_html = textwrap.dedent(f"""
    <div style="
        background: {BG_CARD};
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-right: 4px solid {accent_color};
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="color: {TEXT_MUTED}; font-size: 0.85rem; font-weight: 600; margin-bottom: 4px;">{title}</div>
                <div style="color: {TEXT_MAIN}; font-size: 1.7rem; font-weight: 800; letter-spacing: -0.5px;">{value}</div>
                {sub_html}
            </div>
            <div style="
                width: 50px; height: 50px; border-radius: 14px;
                background: {accent_color}1F;
                border: 1px solid {accent_color}40;
                display: flex; align-items: center; justify-content: center;
                font-size: 1.5rem;
                box-shadow: inset 0 0 12px {accent_color}20;
            ">{icon}</div>
        </div>
    </div>
    """).strip()
  return card_html


def show():
  inject_custom_theme()

  user_name = (
      st.session_state.get("user", {}).get("full_name", "مدير النظام")
      if "user" in st.session_state
      else "مدير النظام"
  )

  # جلب البيانات
  kpi = get_kpi_cards()
  quick = get_quick_stats()
  alerts = get_alerts()

  # ---------- الهيدر التنفيذي الرئاسي ----------
  header_html = textwrap.dedent(f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: 1px solid rgba(139, 92, 246, 0.5);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 25px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;
    ">
        <div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="background: {COLOR_PURPLE}; width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 10px {COLOR_PURPLE};"></span>
                <span style="color: {COLOR_PURPLE}; font-size: 0.8rem; font-weight: 800; letter-spacing: 1.5px;">ENTERPRISE EXECUTIVE DASHBOARD</span>
            </div>
            <h1 style="color: {TEXT_MAIN}; font-size: 2.1rem; margin: 0; font-weight: 900;">مرحباً بك، {user_name} 👋</h1>
            <p style="color: {TEXT_MUTED}; font-size: 0.95rem; margin: 4px 0 0 0;">
                مؤشرات الأداء المباشرة ليوم <span style="color: #A78BFA; font-weight: 700;">{datetime.now().strftime('%A, %d %B %Y')}</span>
            </p>
        </div>
        <div style="
            width: 60px; height: 60px; border-radius: 16px;
            background: linear-gradient(135deg, rgba(139,92,246,0.3) 0%, rgba(59,130,246,0.1) 100%);
            border: 1px solid rgba(139,92,246,0.4);
            display: flex; align-items: center; justify-content: center;
            font-size: 2rem; box-shadow: 0 0 25px rgba(139,92,246,0.25);
        ">💎</div>
    </div>
    """).strip()
  st.markdown(header_html, unsafe_allow_html=True)

  # ---------- الإحصائيات السريعة (4 أعمدة متناسبة) ----------
  c1, c2, c3, c4 = st.columns(4)
  with c1:
    st.markdown(
        create_kpi_card(
            "المبيعات اليومية",
            f"{quick['today_sales']:,.0f} ر.ي",
            "💸",
            COLOR_GREEN,
            "↑ 12% نمو يومي",
        ),
        unsafe_allow_html=True,
    )
  with c2:
    st.markdown(
        create_kpi_card(
            "المشتريات اليومية",
            f"{quick['today_purchases']:,.0f} ر.ي",
            "🛍️",
            COLOR_RED,
            "↓ 5% انخفاض",
        ),
        unsafe_allow_html=True,
    )
  with c3:
    stock_status = (
        "تدخل عاجل مطلوب" if quick["low_stock"] > 0 else "المستويات آمنة"
    )
    stock_col = COLOR_RED if quick["low_stock"] > 0 else COLOR_GREEN
    st.markdown(
        create_kpi_card(
            "نواقص المخزون",
            str(quick["low_stock"]),
            "⚠️",
            stock_col,
            stock_status,
        ),
        unsafe_allow_html=True,
    )
  with c4:
    st.markdown(
        create_kpi_card(
            "العملاء والشركاء",
            str(quick["total_customers"]),
            "🤝",
            COLOR_BLUE,
            "+3 انضمام جديد",
        ),
        unsafe_allow_html=True,
    )

  # ---------- التنبيهات الذكية ----------
  if alerts:
    for alert in alerts:
      alert_html = textwrap.dedent(f"""
            <div style="
                background: rgba(245, 158, 11, 0.1);
                border-right: 4px solid {COLOR_AMBER};
                border-radius: 12px; padding: 12px 18px; margin-bottom: 12px;
                color: {TEXT_MAIN}; font-size: 0.9rem;
                display: flex; align-items: center; gap: 10px;
                border: 1px solid rgba(245, 158, 11, 0.2);
            ">
                <span style="font-size: 1.2rem;">{alert['icon']}</span>
                <span><b style="color: {COLOR_AMBER};">{alert['title']}:</b> {alert['message']}</span>
            </div>
            """).strip()
      st.markdown(alert_html, unsafe_allow_html=True)

  # ---------- المؤشرات المالية الاستراتيجية ----------
  st.markdown(
      f"<h3 style='color: {TEXT_MAIN}; font-weight: 800; font-size: 1.2rem;"
      " margin: 20px 0 15px 0;'>📊 الأداء المالي التراكمي</h3>",
      unsafe_allow_html=True,
  )

  p1, p2, p3, p4, p5 = st.columns(5)
  with p1:
    st.markdown(
        create_kpi_card(
            "إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "📈", COLOR_GREEN
        ),
        unsafe_allow_html=True,
    )
  with p2:
    st.markdown(
        create_kpi_card(
            "إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📉", COLOR_RED
        ),
        unsafe_allow_html=True,
    )
  with p3:
    net_val = kpi["net_income"]
    st.markdown(
        create_kpi_card(
            "صافي الأرباح",
            f"{net_val:,.0f}",
            "🏆",
            COLOR_GREEN if net_val >= 0 else COLOR_RED,
        ),
        unsafe_allow_html=True,
    )
  with p4:
    st.markdown(
        create_kpi_card(
            "دليل المنتجات", str(kpi["products_count"]), "📦", COLOR_BLUE
        ),
        unsafe_allow_html=True,
    )
  with p5:
    st.markdown(
        create_kpi_card(
            "قاعدة العملاء", str(kpi["customers_count"]), "🌐", COLOR_AMBER
        ),
        unsafe_allow_html=True,
    )

  # ---------- الرسوم البيانية التفاعلية ----------
  col_chart1, col_chart2 = st.columns(2)

  with col_chart1:
    st.markdown(
        f"<h4 style='color: {TEXT_MAIN}; font-weight: 700; margin-bottom:"
        " 12px;'>📊 حركة التدفقات النقدية الشهري</h4>",
        unsafe_allow_html=True,
    )
    sales_data = get_monthly_sales()
    if sales_data:
      df_sales = pd.DataFrame(sales_data).sort_values("month")
      fig = go.Figure()
      fig.add_trace(
          go.Bar(
              x=df_sales["month"],
              y=df_sales["total"],
              marker=dict(
                  color=df_sales["total"],
                  colorscale=[[0, COLOR_BLUE], [1, COLOR_PURPLE]],
                  line=dict(color="rgba(255,255,255,0.1)", width=1),
              ),
              hovertemplate="%{y:,.0f} ر.ي",
              name="المبيعات",
          )
      )
      fig.update_layout(
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color=TEXT_MAIN, family="Tajawal"),
          margin=dict(t=10, b=10, l=10, r=10),
          height=280,
          xaxis=dict(showgrid=False, color=TEXT_MUTED),
          yaxis=dict(
              showgrid=True,
              gridcolor="rgba(255,255,255,0.05)",
              color=TEXT_MUTED,
          ),
      )
      st.plotly_chart(
          fig, use_container_width=True, config={"displayModeBar": False}
      )

  with col_chart2:
    st.markdown(
        f"<h4 style='color: {TEXT_MAIN}; font-weight: 700; margin-bottom:"
        " 12px;'>🎯 توزيع المخزون حسب الفئات</h4>",
        unsafe_allow_html=True,
    )
    inv_data = get_inventory_by_category()
    if inv_data:
      df_inv = pd.DataFrame(inv_data)
      fig = px.pie(
          df_inv,
          names="category",
          values="total",
          hole=0.65,
          color_discrete_sequence=[
              COLOR_PURPLE,
              COLOR_BLUE,
              "#06B6D4",
              COLOR_GREEN,
              COLOR_AMBER,
          ],
      )
      fig.update_traces(
          textinfo="percent",
          marker=dict(line=dict(color="#030712", width=2)),
      )
      fig.update_layout(
          paper_bgcolor="rgba(0,0,0,0)",
          font=dict(color=TEXT_MAIN, family="Tajawal"),
          margin=dict(t=10, b=10, l=10, r=10),
          height=280,
          legend=dict(
              font=dict(color=TEXT_MUTED, size=11),
              orientation="h",
              y=-0.1,
          ),
      )
      st.plotly_chart(
          fig, use_container_width=True, config={"displayModeBar": False}
      )

  # ---------- القوائم وسجل الأنشطة ----------
  col_list1, col_list2 = st.columns(2)

  with col_list1:
    st.markdown(
        f"<h4 style='color: {TEXT_MAIN}; font-weight: 700; margin-bottom:"
        " 12px;'>🚨 المنتجات القريبة من الحد الحرج</h4>",
        unsafe_allow_html=True,
    )
    low = get_low_stock_products()
    if low:
      for item in low:
        item_html = textwrap.dedent(f"""
                <div style="
                    background: rgba(239, 68, 68, 0.08);
                    border-right: 3px solid {COLOR_RED};
                    border-radius: 10px; padding: 12px 16px; margin-bottom: 8px;
                    display: flex; justify-content: space-between; align-items: center;
                    border: 1px solid rgba(239, 68, 68, 0.15);
                ">
                    <span style="color: {TEXT_MAIN}; font-weight: 600; font-size: 0.9rem;">{item['name']}</span>
                    <span style="background: rgba(239,68,68,0.2); color: #FCA5A5; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">
                        المتبقي: {item['quantity']}
                    </span>
                </div>
                """).strip()
        st.markdown(item_html, unsafe_allow_html=True)

  with col_list2:
    st.markdown(
        f"<h4 style='color: {TEXT_MAIN}; font-weight: 700; margin-bottom:"
        " 12px;'>⚡ سجل الأنشطة الأخير</h4>",
        unsafe_allow_html=True,
    )
    activities = get_recent_activities()
    if activities:
      for act in activities[:4]:
        act_str = str(act.get("action", ""))
        time_val = (
            act.get("time")
            or act.get("created_at")
            or act.get("timestamp")
            or ""
        )

        act_html = textwrap.dedent(f"""
                <div style="
                    background: {BG_CARD};
                    border: 1px solid rgba(255,255,255,0.05);
                    border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;
                    display: flex; justify-content: space-between; align-items: center;
                ">
                    <span style="color: {TEXT_MAIN}; font-weight: 500; font-size: 0.88rem;">{act_str}</span>
                    <span style="color: {TEXT_MUTED}; font-size: 0.75rem;">{time_val}</span>
                </div>
                """).strip()
        st.markdown(act_html, unsafe_allow_html=True)
