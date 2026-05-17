# dashboard.py - لوحة معلومات احترافية بوجه جميل
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from database import get_connection

# ========== إعدادات الألوان العامة ==========
BG_COLOR = "#F8FAFC"
CARD_COLOR = "#FFFFFF"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
TEXT_PRIMARY = "#1E293B"
TEXT_SECONDARY = "#64748B"

def show():
    conn = get_connection()

    # ---------- رأس الصفحة ----------
    user_name = st.session_state.user.get("full_name", "المستخدم")
    hour = datetime.now().hour
    greeting = "صباح الخير" if hour < 12 else "مساء الخير"
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <h1 style="margin:0; font-size: 2rem; color:{TEXT_PRIMARY};">{greeting}، {user_name} 👋</h1>
        <p style="margin:0; color:{TEXT_SECONDARY}; font-size: 1rem;">نظرة سريعة على أداء النظام اليوم</p>
    </div>
    """, unsafe_allow_html=True)

    # ---------- بطاقات إحصائية ----------
    products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_qty = conn.execute("SELECT SUM(quantity) FROM products").fetchone()[0] or 0
    total_sales = conn.execute("SELECT SUM(total) FROM invoices WHERE type='sale'").fetchone()[0] or 0
    total_purchases = conn.execute("SELECT SUM(total) FROM invoices WHERE type='purchase'").fetchone()[0] or 0

    col1, col2, col3, col4 = st.columns(4)

    cards_data = [
        (col1, "📦", "المنتجات", products_count, ACCENT_BLUE),
        (col2, "📋", "إجمالي الكميات", total_qty, ACCENT_GREEN),
        (col3, "💰", "إجمالي المبيعات", f"{total_sales:,.0f}", ACCENT_ORANGE),
        (col4, "🛒", "إجمالي المشتريات", f"{total_purchases:,.0f}", ACCENT_RED),
    ]

    for col, icon, title, value, color in cards_data:
        with col:
            st.markdown(f"""
            <div style="
                background: {CARD_COLOR};
                border-radius: 16px;
                padding: 1.2rem;
                box-shadow: 0 4px 12px rgba(0,0,0,0.03);
                border: 1px solid #F1F5F9;
                display: flex;
                align-items: center;
                gap: 1rem;
                margin-bottom: 1rem;
            ">
                <div style="
                    background: {color}15;
                    width: 48px;
                    height: 48px;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.5rem;
                ">{icon}</div>
                <div>
                    <div style="font-size: 0.8rem; color: {TEXT_SECONDARY}; margin-bottom: 0.2rem;">{title}</div>
                    <div style="font-size: 1.4rem; font-weight: 700; color: {TEXT_PRIMARY};">{value}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---------- رسم بياني: توزيع المخزون حسب الفئة ----------
    st.subheader("📊 توزيع المخزون حسب الفئة")
    df = pd.read_sql_query("SELECT category, SUM(quantity) as total FROM products GROUP BY category", conn)
    if not df.empty and df['total'].sum() > 0:
        colors_pie = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
        fig = px.pie(df, names='category', values='total', hole=0.45, color_discrete_sequence=colors_pie)
        fig.update_traces(textposition='outside', textinfo='percent+label')
        fig.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد منتجات لعرض توزيع المخزون.")

    st.markdown("---")

    # ---------- آخر الفواتير ----------
    st.subheader("📄 آخر الفواتير المسجلة")
    invoices_df = pd.read_sql_query(
        """SELECT id, type, invoice_date, total, status FROM invoices
           ORDER BY id DESC LIMIT 5""", conn
    )
    if not invoices_df.empty:
        # ترجمة الحالات وإضافة ألوان
        def status_badge(status):
            if status == 'completed': return "✅ مكتملة"
            if status == 'draft': return "📝 مسودة"
            return status

        def row_color(status):
            return "background-color: #F0FDF4;" if status == 'completed' else "background-color: #FFFBEB;"

        invoices_df["نوع"] = invoices_df["type"].map({"sale": "بيع", "purchase": "شراء"})
        invoices_df["التاريخ"] = invoices_df["invoice_date"]
        invoices_df["الإجمالي"] = invoices_df["total"]
        invoices_df["الحالة"] = invoices_df["status"].apply(status_badge)
        display_df = invoices_df[["id", "نوع", "التاريخ", "الإجمالي", "الحالة"]]
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "رقم الفاتورة",
                "نوع": st.column_config.TextColumn("نوع الفاتورة"),
                "التاريخ": st.column_config.DateColumn("تاريخ الفاتورة"),
                "الإجمالي": st.column_config.NumberColumn("إجمالي الفاتورة", format="%.2f"),
                "الحالة": st.column_config.TextColumn("حالة الفاتورة"),
            }
        )
    else:
        st.info("لا توجد فواتير بعد.")

    conn.close()
