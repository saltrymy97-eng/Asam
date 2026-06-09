# ui/audit_log.py - سجل التدقيق (واجهة زجاجية فخمة)
import streamlit as st
import pandas as pd
import sqlite3
import os
from services.audit_service import (
    create_audit_table,
    get_audit_logs,
    get_audit_stats
)

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

def show():
    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_GREEN};">🛡️ سجل التدقيق</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">كل ما يحدث في النظام مسجل هنا</p>
    </div>
    """, unsafe_allow_html=True)

    create_audit_table()

    # ---------- بطاقات إحصائية ----------
    stats = get_audit_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_BLUE};">📋</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">إجمالي السجلات</div>
            <div style="color:{ACCENT_BLUE}; font-size:1.8rem; font-weight:800;">{stats['total']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_GREEN};">📅</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">عمليات اليوم</div>
            <div style="color:{ACCENT_GREEN}; font-size:1.8rem; font-weight:800;">{stats['today']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        top_user = stats['top_users'][0]['username'] if stats['top_users'] else "-"
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_ORANGE};">👤</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">أكثر مستخدم نشاطاً</div>
            <div style="color:{ACCENT_ORANGE}; font-size:1.4rem; font-weight:800;">{top_user}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        top_action = stats['top_actions'][0]['action'] if stats['top_actions'] else "-"
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_PURPLE};">⚡</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">أكثر إجراء</div>
            <div style="color:{ACCENT_PURPLE}; font-size:1.2rem; font-weight:800;">{top_action}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ---------- فلاتر ----------
    col1, col2 = st.columns(2)
    with col1:
        filter_table = st.selectbox("تصفية حسب الجدول", ["الكل", "users", "products", "invoices", "journal_entries", "employees", "customers", "suppliers"], key="audit_filter_table")
    with col2:
        DB_PATH = os.path.join("data", "erp.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        users = [u["username"] for u in conn.execute("SELECT DISTINCT username FROM audit_log").fetchall()]
        conn.close()
        filter_user = st.selectbox("تصفية حسب المستخدم", ["الكل"] + users, key="audit_filter_user")

    # ---------- سجل التدقيق ----------
    logs = get_audit_logs(
        filter_table=None if filter_table == "الكل" else filter_table,
        filter_user=None if filter_user == "الكل" else filter_user
    )

    if logs:
        df = pd.DataFrame(logs)
        df = df.rename(columns={
            "id": "رقم",
            "username": "المستخدم",
            "action": "الإجراء",
            "table_name": "الجدول",
            "record_id": "رقم السجل",
            "old_value": "القيمة القديمة",
            "new_value": "القيمة الجديدة",
            "timestamp": "التوقيت"
        })
        df = df[["رقم", "المستخدم", "الإجراء", "الجدول", "رقم السجل", "القيمة القديمة", "القيمة الجديدة", "التوقيت"]]
        
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 سجل العمليات</h3>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ لا توجد سجلات تدقيق بعد.")
