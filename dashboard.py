# modules/dashboard.py - لوحة المعلومات الرئيسية
import streamlit as st
import pandas as pd
import plotly.express as px
from database import get_connection

def show():
    st.title("📊 لوحة المعلومات")

    conn = get_connection()

    # --- بطاقات إحصائية سريعة ---
    col1, col2, col3, col4 = st.columns(4)

    # عدد المنتجات
    products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    col1.metric("📦 المنتجات", products_count)

    # إجمالي المخزون
    total_qty = conn.execute("SELECT SUM(quantity) FROM products").fetchone()[0] or 0
    col2.metric("📋 إجمالي الكميات", total_qty)

    # إجمالي المبيعات
    total_sales = conn.execute("SELECT SUM(total) FROM invoices WHERE type='sale'").fetchone()[0] or 0
    col3.metric("💰 إجمالي المبيعات", f"{total_sales:,.2f}")

    # إجمالي المشتريات
    total_purchases = conn.execute("SELECT SUM(total) FROM invoices WHERE type='purchase'").fetchone()[0] or 0
    col4.metric("🛒 إجمالي المشتريات", f"{total_purchases:,.2f}")

    st.markdown("---")

    # --- رسم بياني: توزيع المخزون حسب الفئة ---
    st.subheader("📊 توزيع المخزون حسب الفئة")
    df = pd.read_sql_query("SELECT category, SUM(quantity) as total FROM products GROUP BY category", conn)
    if not df.empty:
        fig = px.pie(df, names='category', values='total', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد منتجات حالياً")

    st.markdown("---")

    # --- آخر 5 فواتير ---
    st.subheader("📄 آخر الفواتير")
    invoices_df = pd.read_sql_query(
        """SELECT id, type, invoice_date, total, status 
           FROM invoices ORDER BY id DESC LIMIT 5""", conn
    )
    if not invoices_df.empty:
        st.dataframe(invoices_df, use_container_width=True)
    else:
        st.info("لا توجد فواتير بعد")

    conn.close()
