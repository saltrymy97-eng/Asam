# ui/dashboard_ui.py – لوحة معلومات تنفيذية فاخرة (زجاج نيون ثلاثي الأبعاد)
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
    get_recent_invoices,
    get_top_products,
)

# ========== نظام الألوان الفاخر الملكي ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"
PR = "#8B5CF6"  # بنفسجي إمبراطوري
BL = "#3B82F6"  # أزرق كهربائي
GN = "#10B981"  # أخضر زمردي
RD = "#EF4444"  # أحمر ياقوتي
OR = "#F59E0B"  # ذهبي توهجي
BG_CORE = "#030712"  # كحلي فضائي عميق


def inject_executive_css():
  """حقن نظام التصميم الزجاجي والمؤثرات البصرية الفاخرة"""
  css_code = textwrap.dedent(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap');

    * {{
        font-family: 'Tajawal', sans-serif !important;
        box-sizing: border-box;
    }}

    /* خلفية متدرجة سينمائية متحركة */
    @keyframes cosmicOrbit {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    .stApp {{
        background: radial-gradient(circle at 80% 20%, #1e1b4b 0%, #090d16 45%, {BG_CORE} 100%) !important;
        background-size: 200% 200% !important;
        animation: cosmicOrbit 20s ease infinite !important;
        background-attachment: fixed !important;
        direction: rtl;
        text-align: right;
    }}

    /* إخفاء المساحات الميتة في Streamlit */
    div[data-testid="stVerticalBlock"] > div:empty {{ display: none !important; }}
    
    /* أنيميشن دخول العناصر بثلاثية الأبعاد */
    @keyframes fadeInUp3D {{
        from {{ opacity: 0; transform: translateY(20px) scale(0.98); filter: blur(8px); }}
        to {{ opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }}
    }}
    .element-container, div[data-testid="stColumn"] {{
        animation: fadeInUp3D 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}

    /* تصميم البطاقات الزجاجية Luxury Glassmorphism */
    .luxury-card {{
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.01) 100%) !important;
        backdrop-filter: blur(25px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(25px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 20px !important;
        padding: 22px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
        transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }}
    
    .luxury-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.6), 0 0 20px rgba(139, 92, 246, 0.2);
        border-color: rgba(255, 255, 255, 0.25) !important;
    }}

    /* الأجرام المضيئة المرفقة بالأيقونات */
    .mini-orb {{
        width: 54px; height: 54px;
        border-radius: 50%;
        display: flex; justify-content: center; align-items: center;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: inset 0 0 15px rgba(255, 255, 255, 0.05);
        flex-shrink: 0;
    }}

    /* نقطة النبض التفاعلية */
    @keyframes pulseDot {{
        0% {{ box-shadow: 0 0 0 0 var(--dot-color); }}
        70% {{ box-shadow: 0 0 0 8px transparent; }}
        100% {{ box-shadow: 0 0 0 0 transparent; }}
    }}
    .pulse-dot {{
        width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-left: 8px;
        animation: pulseDot 2s infinite; background-color: var(--dot-color);
    }}
    </style>
    """)
  st.markdown(css_code, unsafe_allow_html=True)


def make_premium_card(title, value, icon, accent_color, delta=""):
  """إنشاء بطاقة إحصائية فاخرة بدون مشاكل التنسيق"""
  delta_html = ""
  if delta:
    d_color = GN if "↑" in delta else RD if "↓" in delta else TEXT_SECONDARY
    dot_bg = GN if "↑" in delta else RD if "↓" in delta else TEXT_MUTED
    delta_html = f"""
        <div style="display: flex; align-items: center; margin-top: 8px;">
            <span class="pulse-dot" style="--dot-color: {dot_bg}; background-color: {dot_bg};"></span>
            <span style="color: {d_color}; font-size: 0.85rem; font-weight: 700; text-shadow: 0 0 8px {d_color}40;">{delta}</span>
        </div>
        """

  html_content = textwrap.dedent(f"""
    <div class="luxury-card" style="border-right: 4px solid {accent_color} !important;">
        <div style="flex: 1; text-align: right;">
            <div style="color: {TEXT_SECONDARY}; font-size: 0.9rem; font-weight: 600; margin-bottom: 4px;">{title}</div>
            <div style="color: {TEXT_PRIMARY}; font-size: 1.8rem; font-weight: 900; letter-spacing: -0.5px;">{value}</div>
            {delta_html}
        </div>
        <div class="mini-orb" style="box-shadow: 0 0 20px {accent_color}40, inset 0 0 10px {accent_color}20; border-color: {accent_color}60;">
            <span style="font-size: 1.6rem; filter: drop-shadow(0 0 6px {accent_color});">{icon}</span>
        </div>
    </div>
    """)
  return html_content.strip()


def show():
  inject_executive_css()

  user_name = (
      st.session_state.user.get("full_name", "المدير التنفيذي")
      if "user" in st.session_state
      else "المدير التنفيذي"
  )
  kpi = get_kpi_cards()
  quick = get_quick_stats()
  alerts = get_alerts()

  # ---------- الهيدر التنفيذي التفاعلي ----------
  header_html = textwrap.dedent(f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(30px);
        border-radius: 24px; padding: 32px 40px; margin-bottom: 30px;
        border: 1px solid rgba(255,255,255,0.1); border-top: 1px solid rgba(139, 92, 246, 0.4);
        box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 20px;
    ">
        <div>
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                <span style="background: {PR}; width: 10px; height: 10px; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px {PR};"></span>
                <span style="color: {PR}; font-size: 0.85rem; font-weight: 800; letter-spacing: 2px; text-transform: uppercase;">ENTERPRISE EXECUTIVE DASHBOARD</span>
            </div>
            <h1 style="color: white; font-size: 2.4rem; margin: 0; font-weight: 900;">مرحباً بك، {user_name} 👋</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 1rem; margin: 6px 0 0 0; font-weight: 500;">
                مؤشرات الأداء المباشرة ليوم <span style="font-weight:700; color:#A78BFA;">{datetime.now().strftime('%A %d %B %Y')}</span>
            </p>
        </div>
        <div style="
            width: 70px; height: 70px; border-radius: 20px;
            background: linear-gradient(135deg, rgba(139,92,246,0.2) 0%, rgba(59,130,246,0.1) 100%);
            border: 1px solid rgba(139,92,246,0.4); display: flex; justify-content: center; align-items: center;
            font-size: 2.2rem; box-shadow: 0 0 30px rgba(139,92,246,0.3);
        ">💎</div>
    </div>
    """)
  st.markdown(header_html, unsafe_allow_html=True)

  # ---------- شبكة الإحصائيات السريعة (4 أعمدة متناسبة) ----------
  c1, c2, c3, c4 = st.columns(4)
  with c1:
    st.markdown(
        make_premium_card(
            "المبيعات اليومية",
            f"{quick['today_sales']:,.0f} ر.ي",
            "💸",
            GN,
            "↑ 12% نمو يومي",
        ),
        unsafe_allow_html=True,
    )
  with c2:
    st.markdown(
        make_premium_card(
            "المشتريات اليومية",
            f"{quick['today_purchases']:,.0f} ر.ي",
            "🛍️",
            RD,
            "↓ 5% انخفاض",
        ),
        unsafe_allow_html=True,
    )
  with c3:
    stock_status = (
        "تدخل عاجل مطلوب" if quick["low_stock"] > 0 else "المستويات آمنة"
    )
    stock_col = RD if quick["low_stock"] > 0 else GN
    st.markdown(
        make_premium_card(
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
        make_premium_card(
            "العملاء والشركاء",
            str(quick["total_customers"]),
            "🤝",
            BL,
            "+3 انضمام جديد",
        ),
        unsafe_allow_html=True,
    )

  st.markdown(
      "<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True
  )

  # ---------- التنبيهات الذكية ----------
  if alerts:
    for alert in alerts:
      alert_html = textwrap.dedent(f"""
            <div style="background: linear-gradient(90deg, rgba(245, 158, 11, 0.15) 0%, transparent 100%); 
                        border-right: 4px solid {OR}; border-radius: 12px; padding: 14px 20px; margin-bottom: 15px; 
                        color: {TEXT_PRIMARY}; font-size: 0.95rem; display: flex; align-items: center; gap: 12px;
                        backdrop-filter: blur(10px); border: 1px solid rgba(245, 158, 11, 0.2);">
                <span style="font-size: 1.3rem;">{alert['icon']}</span>
                <span><b style="color: {OR}; font-weight: 700;">{alert['title']}</b>: {alert['message']}</span>
            </div>
            """)
      st.markdown(alert_html, unsafe_allow_html=True)

  # ---------- الأداء المالي التراكمي ----------
  st.markdown(
      textwrap.dedent(f"""
    <div style="display: flex; align-items: center; gap: 10px; margin: 20px 0 15px 0;">
        <span style="background: {PR}; width: 16px; height: 4px; border-radius: 2px; box-shadow: 0 0 10px {PR};"></span>
        <h3 style="color:{TEXT_PRIMARY}; font-weight:800; margin: 0; font-size:1.3rem;">الأداء المالي والاستراتيجي</h3>
    </div>
    """),
      unsafe_allow_html=True,
  )

  p1, p2, p3, p4, p5 = st.columns(5)
  with p1:
    st.markdown(
        make_premium_card(
            "إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "📈", GN
        ),
        unsafe_allow_html=True,
    )
  with p2:
    st.markdown(
        make_premium_card(
            "إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📉", RD
        ),
        unsafe_allow_html=True,
    )
  with p3:
    net_val = kpi["net_income"]
    st.markdown(
        make_premium_card(
            "صافي الأرباح", f"{net_val:,.0f}", "🏆", GN if net_val >= 0 else RD
        ),
        unsafe_allow_html=True,
    )
  with p4:
    st.markdown(
        make_premium_card(
            "دليل المنتجات", str(kpi["products_count"]), "📦", BL
        ),
        unsafe_allow_html=True,
    )
  with p5:
    st.markdown(
        make_premium_card(
            "قاعدة العملاء", str(kpi["customers_count"]), "🌐", OR
        ),
        unsafe_allow_html=True,
    )

  st.markdown(
      "<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True
  )

  # ---------- الرسوم البيانية التفاعلية ----------
  col_chart1, col_chart2 = st.columns(2)

  with col_chart1:
    st.markdown(
        f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin-bottom:15px;'>📊"
        " اتجاه التدفقات النقدية الشهري</h4>",
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
                  colorscale=[[0, "#3B82F6"], [1, "#8B5CF6"]],
                  line=dict(color="rgba(255,255,255,0.2)", width=1),
              ),
              hovertemplate="%{y:,.0f} ر.ي",
              name="المبيعات",
          )
      )
      fig.add_trace(
          go.Scatter(
              x=df_sales["month"],
              y=df_sales["total"].rolling(2, min_periods=1).mean(),
              mode="lines+markers",
              line=dict(color=OR, width=3, shape="spline"),
              marker=dict(
                  size=7, color=BG_CORE, line=dict(width=2, color=OR)
              ),
              name="المتوسط المتحرك",
          )
      )
      fig.update_layout(
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color=TEXT_PRIMARY, family="Tajawal"),
          margin=dict(t=10, b=10, l=10, r=10),
          showlegend=False,
          height=300,
          xaxis=dict(showgrid=False, color=TEXT_SECONDARY),
          yaxis=dict(
              showgrid=True, gridcolor="rgba(255,255,255,0.05)", color=TEXT_SECONDARY
          ),
          hoverlabel=dict(
              bgcolor="rgba(15, 23, 42, 0.95)",
              font_size=13,
              font_family="Tajawal",
          ),
      )
      st.plotly_chart(
          fig, use_container_width=True, config={"displayModeBar": False}
      )

  with col_chart2:
    st.markdown(
        f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800; margin-bottom:15px;'>🎯"
        " التوزيع الهيكلي للمخزون</h4>",
        unsafe_allow_html=True,
    )
    inv_data = get_inventory_by_category()
    if inv_data:
      df_inv = pd.DataFrame(inv_data)
      fig = px.pie(
          df_inv,
          names="category",
          values="total",
          hole=0.7,
          color_discrete_sequence=[
              "#8B5CF6",
              "#3B82F6",
              "#06B6D4",
              "#10B981",
              "#F59E0B",
          ],
      )
      fig.update_traces(
          textinfo="percent",
          marker=dict(line=dict(color=BG_CORE, width=3)),
          hoverinfo="label+percent+value",
      )
      fig.add_annotation(
          dict(
              font=dict(size=28),
              x=0.5,
              y=0.5,
              showarrow=False,
              text="📦",
              xanchor="center",
              yanchor="middle",
          )
      )
      fig.update_layout(
          paper_bgcolor="rgba(0,0,0,0)",
          font=dict(color=TEXT_PRIMARY, family="Tajawal"),
          margin=dict(t=10, b=10, l=10, r=10),
          showlegend=True,
          height=300,
          legend=dict(
              font=dict(color=TEXT_SECONDARY, size=12),
              orientation="h",
              y=-0.1,
          ),
          hoverlabel=dict(
              bgcolor="rgba(15, 23, 42, 0.95)",
              font_size=13,
              font_family="Tajawal",
          ),
      )
      st.plotly_chart(
          fig, use_container_width=True, config={"displayModeBar": False}
      )

  st.markdown(
      "<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True
  )

  # ---------- القوائم وسجل العمليات ----------
  col_list1, col_list2 = st.columns(2)

  with col_list1:
    st.markdown(
        f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800;"
        " margin-bottom:15px;'>🚨 الأصناف ذات الحد الحرج</h4>",
        unsafe_allow_html=True,
    )
    low = get_low_stock_products()
    if low:
      for item in low:
        item_html = textwrap.dedent(f"""
                <div style="background: rgba(239, 68, 68, 0.08); 
                            border-right: 3px solid {RD}; border-radius: 12px; padding: 14px 18px; margin-bottom: 10px; 
                            display: flex; justify-content: space-between; align-items: center;
                            border: 1px solid rgba(239, 68, 68, 0.15);">
                    <span style="color: {TEXT_PRIMARY}; font-weight: 700; font-size: 0.95rem;">{item['name']}</span>
                    <span style="background: rgba(239,68,68,0.2); border: 1px solid rgba(239,68,68,0.4); color: #FCA5A5; padding: 4px 10px; border-radius: 8px; font-weight: 800; font-size: 0.8rem;">
                        المتبقي: {item['quantity']} / {item['reorder_level']}
                    </span>
                </div>
                """)
        st.markdown(item_html, unsafe_allow_html=True)
    else:
      st.markdown(
          textwrap.dedent(f"""
            <div style="background: rgba(16, 185, 129, 0.05); border: 1px dashed rgba(16, 185, 129, 0.3); border-radius: 16px; padding: 20px; color: {GN}; font-weight: 700; text-align: center; font-size: 0.95rem;">
                🛡️ لا توجد نواقص. جميع الأصناف بمستويات آمنة.
            </div>
            """),
          unsafe_allow_html=True,
      )

  with col_list2:
    st.markdown(
        f"<h4 style='color:{TEXT_PRIMARY}; font-weight:800;"
        " margin-bottom:15px;'>⚡ سجل الأنشطة الفورية</h4>",
        unsafe_allow_html=True,
    )
    activities = get_recent_activities()
    if activities:
      for act in activities[:5]:
        act_str = str(act.get("action", ""))
        dot_color = (
            PR
            if "فاتورة" in act_str
            else BL
            if "قيد" in act_str
            else GN
            if "سداد" in act_str
            else OR
        )
        time_value = (
            act.get("time")
            or act.get("created_at")
            or act.get("timestamp")
            or ""
        )

        act_html = textwrap.dedent(f"""
                <div class="luxury-card" style="padding: 12px 18px; margin-bottom: 10px; border-radius: 14px;">
                    <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                        <div class="mini-orb" style="width: 32px; height: 32px; background: {dot_color}15; border-color: {dot_color}40;">
                            <span style="background: {dot_color}; width: 6px; height: 6px; border-radius: 50%; box-shadow: 0 0 8px {dot_color};"></span>
                        </div>
                        <div style="flex: 1; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: {TEXT_PRIMARY}; font-weight: 600; font-size: 0.9rem;">{act_str}</span>
                            <span style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 6px; color: {TEXT_SECONDARY}; font-size: 0.75rem;">{time_value}</span>
                        </div>
                    </div>
                </div>
                """)
        st.markdown(act_html, unsafe_allow_html=True)
    else:
      st.markdown(
          textwrap.dedent(f"""
            <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; color: {TEXT_SECONDARY}; text-align: center; font-size: 0.95rem; font-weight: 600;">
                ⏳ لا توجد أنشطة مسجلة مؤخراً.
            </div>
            """),
          unsafe_allow_html=True,
      )
