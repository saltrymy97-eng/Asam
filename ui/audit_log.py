# ui/audit_log.py - سجل التدقيق (v3.0)
# ✅ حذف الأعمدة الفارغة تلقائياً
# ✅ رسوم بيانية للتوزيع
# ✅ لا حاجة لتعديل أي خدمة
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
TEXT_MUTED = "#94A3B8"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_RED = "#EF4444"
ACCENT_CYAN = "#06B6D4"


def _kpi_card(icon, title, value, color):
    """بطاقة KPI زجاجية"""
    return f"""
    <div style="background:{GLASS_BG}; backdrop-filter:blur(10px);
        border:1px solid {GLASS_BORDER}; border-radius:16px;
        padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
        <div style="font-size:2rem; color:{color};">{icon}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">{title}</div>
        <div style="color:{color}; font-size:1.6rem; font-weight:800;
             word-break:break-word;">{value}</div>
    </div>
    """


def _get_distinct_values(column):
    """جلب القيم المميزة لعمود معيّن"""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM audit_log "
            f"WHERE {column} IS NOT NULL AND {column} != '' "
            f"ORDER BY {column}"
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []
    finally:
        close_connection(conn)


def _is_meaningful_column(series):
    """
    ✅ هل العمود يحوي بيانات حقيقية أم أنه فارغ؟
    - يعتبر فارغاً إذا كانت كل القيم: None, '', 'None', '—', NaN
    """
    for val in series:
        if val is None:
            continue
        if pd.isna(val):
            continue
        s = str(val).strip().lower()
        if s in ("", "none", "—", "nan"):
            continue
        return True  # وجدنا قيمة حقيقية
    return False


def _drop_empty_columns(df, keep_always=("رقم", "المستخدم", "الإجراء", "التوقيت")):
    """
    ✅ حذف الأعمدة الفارغة تماماً.
    - الأعمدة في keep_always لا تُحذف حتى لو كانت فارغة.
    """
    cols_to_keep = []
    cols_dropped = []
    for col in df.columns:
        if col in keep_always or _is_meaningful_column(df[col]):
            cols_to_keep.append(col)
        else:
            cols_dropped.append(col)
    return df[cols_to_keep], cols_dropped


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
        st.markdown(_kpi_card("📋", "إجمالي السجلات",
                              stats['total'], ACCENT_BLUE),
                    unsafe_allow_html=True)
    with col2:
        st.markdown(_kpi_card("📅", "عمليات اليوم",
                              stats['today'], ACCENT_GREEN),
                    unsafe_allow_html=True)
    with col3:
        top_user = stats['top_users'][0]['username'] if stats['top_users'] else "-"
        st.markdown(_kpi_card("👤", "أكثر مستخدم نشاطاً",
                              top_user, ACCENT_ORANGE),
                    unsafe_allow_html=True)
    with col4:
        top_action = stats['top_actions'][0]['action'] if stats['top_actions'] else "-"
        if len(str(top_action)) > 20:
            top_action = str(top_action)[:18] + "..."
        st.markdown(_kpi_card("⚡", "أكثر إجراء",
                              top_action, ACCENT_PURPLE),
                    unsafe_allow_html=True)

    st.markdown("---")

    # ============================================================
    # الفلاتر
    # ============================================================
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        tables = ["الكل"] + _get_distinct_values("table_name")
        filter_table = st.selectbox(
            "📁 الجدول", tables, key="audit_filter_table"
        )

    with col2:
        users = ["الكل"] + _get_distinct_values("username")
        filter_user = st.selectbox(
            "👤 المستخدم", users, key="audit_filter_user"
        )

    with col3:
        date_range = st.selectbox(
            "📅 الفترة",
            ["الكل", "اليوم", "آخر 7 أيام", "آخر 30 يوماً"],
            key="audit_filter_date"
        )

    with col4:
        limit = st.number_input(
            "📊 الحد الأقصى",
            min_value=10, max_value=10000, value=500, step=50,
            key="audit_filter_limit"
        )

    # ✅ حساب المدى الزمني
    date_from = date_to = None
    today = date.today()
    if date_range == "اليوم":
        date_from = date_to = today.strftime("%Y-%m-%d")
    elif date_range == "آخر 7 أيام":
        date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")
    elif date_range == "آخر 30 يوماً":
        date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = today.strftime("%Y-%m-%d")

    # ✅ بحث نصي
    search_text = st.text_input(
        "🔍 بحث سريع (في الإجراء، الجدول، القيم)",
        placeholder="اكتب أي كلمة للبحث...",
        key="audit_search"
    )

    # ============================================================
    # جلب السجلات
    # ============================================================
    logs = get_audit_logs(
        filter_table=None if filter_table == "الكل" else filter_table,
        filter_user=None if filter_user == "الكل" else filter_user,
        limit=int(limit),
    )

    # ✅ الفلترة النصية
    if search_text.strip():
        pattern = search_text.strip().lower()
        logs = [
            log for log in logs
            if pattern in str(log.get("action", "")).lower()
            or pattern in str(log.get("table_name", "")).lower()
            or pattern in str(log.get("old_value", "")).lower()
            or pattern in str(log.get("new_value", "")).lower()
            or pattern in str(log.get("username", "")).lower()
        ]

    # ✅ الفلترة الزمنية
    if date_from:
        logs = [
            log for log in logs
            if str(log.get("timestamp", ""))[:10] >= date_from
            and str(log.get("timestamp", ""))[:10] <= date_to
        ]

    if not logs:
        st.info("ℹ️ لا توجد سجلات مطابقة للبحث.")
        return

    # ============================================================
    # تحويل البيانات إلى DataFrame
    # ============================================================
    df = pd.DataFrame(logs)

    # ✅ تعويض القيم الفارغة
    df["record_id"] = df["record_id"].apply(
        lambda x: "—" if pd.isna(x) or x is None else str(x)
    )
    df["old_value"] = df["old_value"].apply(
        lambda x: "—" if pd.isna(x) or not str(x).strip()
        or str(x).lower() == "none" else str(x)
    )
    df["new_value"] = df["new_value"].apply(
        lambda x: "—" if pd.isna(x) or not str(x).strip()
        or str(x).lower() == "none" else str(x)
    )
    df["username"] = df["username"].fillna("—").replace("", "—")
    df["action"] = df["action"].fillna("—")
    df["table_name"] = df["table_name"].fillna("—")

    # ✅ إعادة التسمية
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

    # ✅ ترتيب الأعمدة
    all_cols = ["رقم", "المستخدم", "الإجراء", "الجدول",
                "رقم السجل", "القيمة القديمة", "القيمة الجديدة", "التوقيت"]
    all_cols = [c for c in all_cols if c in df.columns]
    df = df[all_cols]

    # ============================================================
    # ✅ حذف الأعمدة الفارغة
    # ============================================================
    keep_always = ("رقم", "المستخدم", "الإجراء", "التوقيت")
    df_display, dropped = _drop_empty_columns(df, keep_always=keep_always)

    # إعلام المستخدم بالأعمدة المحذوفة
    hidden_msg = ""
    if dropped:
        hidden_msg = (
            f"ℹ️ تم إخفاء الأعمدة الفارغة تلقائياً: "
            f"**{', '.join(dropped)}** — لأنها لا تحتوي بيانات في السجلات المعروضة."
        )

    # ============================================================
    # العنوان
    # ============================================================
    st.markdown(
        f"<h3 style='color:{TEXT_PRIMARY};'>📋 سجل العمليات "
        f"<span style='color:{TEXT_MUTED}; font-size:1rem;'>"
        f"({len(df_display)} سجل)</span></h3>",
        unsafe_allow_html=True
    )

    if hidden_msg:
        st.info(hidden_msg)

    # ============================================================
    # عرض الجدول
    # ============================================================
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=450,
    )

    # ============================================================
    # ✅ تصدير CSV
    # ============================================================
    csv = df_display.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 تصدير السجل (CSV)",
        data=csv,
        file_name=f"audit_log_{date.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="audit_export_btn",
    )

    # ============================================================
    # ✅ الرسوم البيانية
    # ============================================================
    st.markdown("---")
    st.markdown(
        f"<h3 style='color:{TEXT_PRIMARY};'>📊 تحليلات بصرية</h3>",
        unsafe_allow_html=True
    )

    df_charts = pd.DataFrame(logs).copy()
    # استخراج التاريخ والساعة
    df_charts["date"] = df_charts["timestamp"].astype(str).str[:10]
    df_charts["hour"] = df_charts["timestamp"].astype(str).str[11:13]

    # صف أول: توزيع يومي + توزيع حسب الجدول
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown(
            f"<p style='color:{ACCENT_CYAN}; font-weight:600;'>"
            f"📅 العمليات حسب اليوم</p>",
            unsafe_allow_html=True
        )
        daily_counts = df_charts.groupby("date").size().reset_index(name="عدد")
        daily_counts = daily_counts.sort_values("date")
        if not daily_counts.empty:
            st.bar_chart(
                daily_counts.set_index("date")["عدد"],
                color=ACCENT_CYAN,
                height=250,
            )
        else:
            st.caption("لا توجد بيانات")

    with col_chart2:
        st.markdown(
            f"<p style='color:{ACCENT_BLUE}; font-weight:600;'>"
            f"📁 العمليات حسب الجدول</p>",
            unsafe_allow_html=True
        )
        table_counts = (
            df_charts.groupby("table_name").size()
            .reset_index(name="عدد")
            .sort_values("عدد", ascending=False)
            .head(10)
        )
        if not table_counts.empty:
            st.bar_chart(
                table_counts.set_index("table_name")["عدد"],
                color=ACCENT_BLUE,
                height=250,
            )
        else:
            st.caption("لا توجد بيانات")

    # صف ثاني: توزيع حسب الساعة + حسب المستخدم
    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        st.markdown(
            f"<p style='color:{ACCENT_ORANGE}; font-weight:600;'>"
            f"🕐 العمليات حسب الساعة</p>",
            unsafe_allow_html=True
        )
        hour_counts = df_charts.groupby("hour").size().reset_index(name="عدد")
        hour_counts = hour_counts.sort_values("hour")
        if not hour_counts.empty:
            st.bar_chart(
                hour_counts.set_index("hour")["عدد"],
                color=ACCENT_ORANGE,
                height=250,
            )
        else:
            st.caption("لا توجد بيانات")

    with col_chart4:
        st.markdown(
            f"<p style='color:{ACCENT_PURPLE}; font-weight:600;'>"
            f"👤 العمليات حسب المستخدم</p>",
            unsafe_allow_html=True
        )
        user_counts = (
            df_charts.groupby("username").size()
            .reset_index(name="عدد")
            .sort_values("عدد", ascending=False)
            .head(10)
        )
        if not user_counts.empty:
            st.bar_chart(
                user_counts.set_index("username")["عدد"],
                color=ACCENT_PURPLE,
                height=250,
            )
        else:
            st.caption("لا توجد بيانات")

    # ============================================================
    # ✅ أكثر 10 إجراءات (رسم أفقي)
    # ============================================================
    st.markdown(
        f"<p style='color:{ACCENT_GREEN}; font-weight:600;'>"
        f"⚡ أكثر 10 إجراءات تكراراً</p>",
        unsafe_allow_html=True
    )
    action_counts = (
        df_charts.groupby("action").size()
        .reset_index(name="عدد")
        .sort_values("عدد", ascending=False)
        .head(10)
    )
    if not action_counts.empty:
        st.bar_chart(
            action_counts.set_index("action")["عدد"],
            color=ACCENT_GREEN,
            height=300,
        )
    else:
        st.caption("لا توجد بيانات")

    # ============================================================
    # ✅ تفاصيل سجل واحد
    # ============================================================
    st.markdown("---")
    with st.expander("🔍 عرض تفاصيل سجل كامل", expanded=False):
        log_ids = df["رقم"].tolist()
        if log_ids:
            selected_id = st.selectbox(
                "اختر رقم السجل",
                log_ids,
                key="audit_detail_select"
            )
            selected = next(
                (log for log in logs if log["id"] == selected_id),
                None
            )
            if selected:
                st.markdown("**البيانات الكاملة:**")
                detail_df = pd.DataFrame([
                    {"الحقل": "المستخدم",
                     "القيمة": selected.get("username") or "—"},
                    {"الحقل": "الإجراء",
                     "القيمة": selected.get("action") or "—"},
                    {"الحقل": "الجدول",
                     "القيمة": selected.get("table_name") or "—"},
                    {"الحقل": "رقم السجل",
                     "القيمة": selected.get("record_id") or "—"},
                    {"الحقل": "القيمة القديمة",
                     "القيمة": selected.get("old_value") or "—"},
                    {"الحقل": "القيمة الجديدة",
                     "القيمة": selected.get("new_value") or "—"},
                    {"الحقل": "التوقيت",
                     "القيمة": selected.get("timestamp") or "—"},
                ])
                st.dataframe(detail_df, use_container_width=True,
                             hide_index=True)
