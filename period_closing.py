import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_periods_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS closed_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_type TEXT NOT NULL,
            period_value TEXT NOT NULL,
            closed_at TEXT NOT NULL,
            closed_by TEXT NOT NULL,
            UNIQUE(period_type, period_value)
        )
    """)
    conn.commit()
    conn.close()

def is_period_closed(date_str):
    """التحقق مما إذا كان التاريخ يقع ضمن فترة مغلقة"""
    conn = get_conn()
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        # إذا كان التاريخ بصيغة مختلفة، حاول صيغة أخرى
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            conn.close()
            return False
    
    month_key = dt.strftime("%Y-%m")
    year_key = dt.strftime("%Y")
    
    # مغلق على مستوى الشهر أو السنة؟
    month_closed = conn.execute(
        "SELECT COUNT(*) as cnt FROM closed_periods WHERE period_type='month' AND period_value=?",
        (month_key,)
    ).fetchone()["cnt"] > 0
    
    year_closed = conn.execute(
        "SELECT COUNT(*) as cnt FROM closed_periods WHERE period_type='year' AND period_value=?",
        (year_key,)
    ).fetchone()["cnt"] > 0
    
    conn.close()
    return month_closed or year_closed

def close_period(period_type, period_value, username):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO closed_periods (period_type, period_value, closed_at, closed_by) VALUES (?, ?, datetime('now'), ?)",
        (period_type, period_value, username)
    )
    conn.commit()
    conn.close()

def reopen_period(period_type, period_value):
    conn = get_conn()
    conn.execute(
        "DELETE FROM closed_periods WHERE period_type=? AND period_value=?",
        (period_type, period_value)
    )
    conn.commit()
    conn.close()

def get_closed_periods():
    conn = get_conn()
    periods = conn.execute("SELECT * FROM closed_periods ORDER BY period_value DESC").fetchall()
    conn.close()
    return periods

def get_available_months():
    """جلب قائمة الشهور التي لديها قيود"""
    conn = get_conn()
    months = conn.execute(
        "SELECT DISTINCT strftime('%Y-%m', date) as month FROM journal_entries ORDER BY month DESC"
    ).fetchall()
    conn.close()
    return [m["month"] for m in months]

def get_available_years():
    """جلب قائمة السنوات التي لديها قيود"""
    conn = get_conn()
    years = conn.execute(
        "SELECT DISTINCT strftime('%Y', date) as year FROM journal_entries ORDER BY year DESC"
    ).fetchall()
    conn.close()
    return [y["year"] for y in years]

def show():
    st.title("📅 إغلاق الفترات المالية")
    create_periods_table()

    tab1, tab2 = st.tabs(["🔒 إغلاق / فتح الفترات", "📋 الفترات المغلقة"])

    with tab1:
        username = st.session_state.user.get("username", "غير معروف") if st.session_state.user else "غير معروف"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("إغلاق شهر")
            months = get_available_months()
            if months:
                month_to_close = st.selectbox("اختر الشهر", months, key="close_month")
                if st.button("🔒 إغلاق الشهر", key="btn_close_month"):
                    close_period("month", month_to_close, username)
                    st.success(f"تم إغلاق شهر {month_to_close}")
                    st.rerun()
            else:
                st.info("لا توجد شهور متاحة (لا توجد قيود)")
        
        with col2:
            st.subheader("إغلاق سنة")
            years = get_available_years()
            if years:
                year_to_close = st.selectbox("اختر السنة", years, key="close_year")
                if st.button("🔒 إغلاق السنة", key="btn_close_year"):
                    close_period("year", year_to_close, username)
                    st.success(f"تم إغلاق سنة {year_to_close}")
                    st.rerun()
            else:
                st.info("لا توجد سنوات متاحة")

        st.markdown("---")
        st.subheader("🔓 إعادة فتح فترة")
        periods = get_closed_periods()
        if periods:
            period_options = [f"{'شهر' if p['period_type']=='month' else 'سنة'}: {p['period_value']} (أغلقها {p['closed_by']} في {p['closed_at']})" for p in periods]
            selected_period = st.selectbox("اختر الفترة لإعادة فتحها", period_options)
            if st.button("🔓 إعادة فتح الفترة"):
                idx = period_options.index(selected_period)
                p = periods[idx]
                reopen_period(p["period_type"], p["period_value"])
                st.success(f"تم إعادة فتح {p['period_type']}: {p['period_value']}")
                st.rerun()
        else:
            st.info("لا توجد فترات مغلقة")

    with tab2:
        st.subheader("الفترات المغلقة حالياً")
        periods = get_closed_periods()
        if periods:
            df = pd.DataFrame(periods, columns=["id", "النوع", "القيمة", "تاريخ الإغلاق", "أغلقها"])
            df = df.drop("id", axis=1)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد فترات مغلقة")
