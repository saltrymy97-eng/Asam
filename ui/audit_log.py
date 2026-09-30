# ui/audit_log.py - سجل التدقيق (v2.0)
# ✅ بحث نصي + فلاتر زمنية + تصدير CSV + استخدام Connection Registry
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from services.audit_service import (
    create_audit_table,
    get_audit_logs,
    get_audit_stats,
)
from database import get_connection, close_connection


# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_RED = "#EF4444"


def _kpi_card(icon, title, value, color):
    """بطاقة KPI زجاجية"""
    return f"""
    <div style="background:{GLASS_BG}; backdrop-filter:blur(10px);
        border:1px solid {GLASS_BORDER}; border-radius:16px;
        padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
        <div style="font-size:2rem; color:{color};">{icon}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">{title}</div>
        <div style="color:{color}; font-size:1.6rem; font-weight:800; word-break:break-word;">{value}</div>
    </div>
    """


def _get_distinct_values(column):
    """جلب القيم المميزة لعمود معيّن باستخدام Connection Registry"""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM audit_log "
            f"WHERE {column} IS NOT NULL AND {column} != '' "
            f"ORDER BY {column}"
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        close_connection(conn)


def show():
    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_GREEN};">🛡️ سجل التدقيق</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">كل ما يحدث في النظام مسجل هنا</p>
    </div>
    """, unsafe_allow_html=True)

    create_audit_table()

    # ============================================================
    # بطاقات إحصائية
    # ============================================================
    stats = get_audit_stats()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(_kpi_card("📋", "إجمالي السجلات", stats['total'], ACCENT_BLUE),
                    unsafe_allow_html=True)
    with col2:
        st.markdown(_kpi_card("📅", "عمليات اليوم", stats['today'], ACCENT_GREEN),
                    unsafe_allow_html=True)
    with col3:
        top_user = stats['top_users'][0]['username'] if stats['top_users'] else "-"
        st.markdown(_kpi_card("👤", "أكثر مستخدم نشاطاً", top_user, ACCENT_ORANGE),
                    unsafe_allow_html=True)
    with col4:
        top_action = stats['top_actions'][0]['action'] if stats['top_actions'] else "-"
        # ✅ قص النص الطويل
        if len(str(top_action)) > 20:
            top_action = str(top_action)[:18] + "..."
        st.markdown(_kpi_card("⚡", "أكثر إجراء", top_action, ACCENT_PURPLE),
                    unsafe_allow_html=True)

    st.markdown("---")

    # ============================================================
    # ✅ البحث النصي الشامل
    # ============================================================
    search_text = st.text_input(
        "🔍 بحث نصي شامل (يشمل: الإجراء، الجدول، القيم، المستخدم)",
        placeholder="اكتب أي شيء للبحث...",
        key="audit_search"
    )

    # ============================================================
    # ✅ الفلاتر
    # ============================================================
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        tables = ["الكل"] + _get_distinct_values("table_name")
        filter_table = st.selectbox(
            "📁 الجدول",
            tables,
            key="audit_filter_table"
        )

    with col2:
        users = ["الكل"] + _get_distinct_values("username")
        filter_user = st.selectbox(
            "👤 المستخدم",
            users,
            key="audit_filter_user"
        )

    with col3:
        date_range_option = st.selectbox(
            "📅 الفترة",
            ["الكل", "اليوم", "آخر 7 أيام", "آخر 30 يوماً", "مخصص"],
            key="audit_filter_date"
        )

    with col4:
        limit = st.number_input(
            "📊 الحد الأقصى",
            min_value=10, max_value=10000, value=100, step=10,
            key="audit_filter_limit"
        )

    # ✅ تحديد المدى الزمني
    date_from = None
    date_to = None
    today = date.today()

    if date_range_option == "اليوم":
        date_from = date_to = today.strftime("%Y-%m-%d")
    elif date_range_option == "آخر 7 أيام":
        date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
    elif date_range_option == "آخر 30 يوماً":
        date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
    elif date_range_option == "مخصص":
        col_d1, col_d2 = st.columns(2)
        d1 = col_d1.date_input("من", value=today - timedelta(days=30),
                                key="audit_date_from")
        d2 = col_d2.date_input("إلى", value=today, key="audit_date_to")
        date_from = d1.strftime("%Y-%m-%d")
        date_to = d2.strftime("%Y-%m-%d")

    # ============================================================
    # جلب السجلات
    # ============================================================
    logs = get_audit_logs(
        filter_table=None if filter_table == "الكل" else filter_table,
        filter_user=None if filter_user == "الكل" else filter_user,
        date_from=date_from,
        date_to=date_to,
        search_text=search_text if search_text.strip() else None,
        limit=int(limit),
    )

    st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 سجل العمليات ({len(logs)} سجل)</h3>",
                unsafe_allow_html=True)

    if logs:
        df = pd.DataFrame(logs)

        # ✅ تعويض القيم الفارغة بنص واضح
        df["record_id"] = df["record_id"].fillna("-").astype(str).replace("None", "-")
        df["old_value"] = df["old_value"].fillna("-").replace({None: "-", "": "-"})
        df["new_value"] = df["new_value"].fillna("-").replace({None: "-", "": "-"})
        df["username"] = df["username"].fillna("-")

        df = df.rename(columns={
            "id": "رقم",
            "username": "المستخدم",
            "action": "الإجراء",
            "table_name": "الجدول",
            "record_id": "رقم السجل",
            "old_value": "القيمة القديمة",
            "new_value": "القيمة الجديدة",
            "timestamp": "التوقيت",
        })

        display_cols = ["رقم", "المستخدم", "الإجراء", "الجدول",
                        "رقم السجل", "القيمة القديمة", "القيمة الجديدة", "التوقيت"]
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        # ============================================================
        # ✅ تصدير CSV
        # ============================================================
        csv = df[display_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 تصدير السجل (CSV)",
            data=csv,
            file_name=f"audit_log_{date.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="audit_export_btn",
        )

    else:
        st.info("ℹ️ لا توجد سجلات مطابقة لبحثك.")
