import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from database import get_connection

# ========== ألوان التصميم ==========
BG_GRADIENT = "linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%)"
GLASS_BG = "rgba(255, 255, 255, 0.15)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
CARD_RADIUS = "20px"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

def show():
    conn = get_connection()

    # ---------- تحية ----------
    user_name = st.session_state.user.get("full_name", "المستخدم")
    hour = datetime.now().hour
    greeting = "صباح الخير" if hour < 12 else "مساء الخير"

    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.5rem; margin:0; text-shadow:0 2px 5px rgba(0,0,0,0.3);">{greeting}، {user_name} ✨</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.1rem;">نظرة عامة على أداء مؤسستك</p>
    </div>
    """, unsafe_allow_html=True)

    # ---------- بطاقات زجاجية ----------
    products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_qty = conn.execute("SELECT SUM(quantity) FROM products").fetchone()[0] or 0
    total_sales = conn.execute("SELECT SUM(total) FROM invoices WHERE type='sale'").fetchone()[0] or 0
    total_purchases = conn.execute("SELECT SUM(total) FROM invoices WHERE type='purchase'").fetchone()[0] or 0

    cols = st.columns(4)
    cards = [
        ("📦", "المنتجات", products_count, ACCENT_BLUE),
        ("📋", "الكميات", total_qty, ACCENT_GREEN),
        ("💰", "المبيعات", f"{total_sales:,.0f}", ACCENT_ORANGE),
        ("🛒", "المشتريات", f"{total_purchases:,.0f}", ACCENT_RED),
    ]

    for col, (icon, title, value, color) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div style="
                background:{GLASS_BG};
                backdrop-filter:blur(10px);
                -webkit-backdrop-filter:blur(10px);
                border:1px solid {GLASS_BORDER};
                border-radius:{CARD_RADIUS};
                padding:1.5rem 1rem;
                box-shadow:{GLASS_SHADOW};
                text-align:center;
                transition:transform 0.2s;
            ">
                <div style="font-size:2.2rem; margin-bottom:0.5rem;">{icon}</div>
                <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">{title}</div>
                <div style="color:{color}; font-size:1.8rem; font-weight:800;">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------- مخطط المخزون ----------
    st.markdown(f"""
    <h3 style="color:{TEXT_PRIMARY};">📊 توزيع المخزون حسب الفئة</h3>
    """, unsafe_allow_html=True)

    df = pd.read_sql_query("SELECT category, SUM(quantity) as total FROM products GROUP BY category", conn)
    if not df.empty and df['total'].sum() > 0:
        colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
        fig = px.pie(df, names='category', values='total', hole=0.5, color_discrete_sequence=colors)
        fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#1E1B4B', width=2)))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=TEXT_PRIMARY),
            margin=dict(t=0, b=0, l=0, r=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد منتجات لعرضها.")

    st.markdown("---")

    # ---------- آخر الفواتير ----------
    st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📄 آخر الفواتير</h3>", unsafe_allow_html=True)

    invoices_df = pd.read_sql_query(
        "SELECT id, type, invoice_date, total, status FROM invoices ORDER BY id DESC LIMIT 5", conn
    )
    if not invoices_df.empty:
        invoices_df["نوع"] = invoices_df["type"].map({"sale": "بيع", "purchase": "شراء"})
        invoices_df["التاريخ"] = invoices_df["invoice_date"]
        invoices_df["الإجمالي"] = invoices_df["total"]
        invoices_df["الحالة"] = invoices_df["status"].map({"completed": "✅ مكتملة", "draft": "📝 مسودة"})
        st.dataframe(
            invoices_df[["id", "نوع", "التاريخ", "الإجمالي", "الحالة"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("لا توجد فواتير بعد.")

    conn.close()
