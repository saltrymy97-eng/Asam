import streamlit as st
from streamlit_option_menu import option_menu
import database

# تهيئة قاعدة البيانات
database.init_db()
database.create_default_admin()

# استيراد الوحدات القديمة
import auth
import dashboard
import inventory
import sales
import purchases
import accounting
import hr

# استيراد الوحدات الجديدة
import chart_of_accounts
import financial_reports
import roles_permissions
import period_closing
import fifo_inventory
import payroll
import ai_assistant
import closing_entries  # قيد إغلاق الحسابات
from ui.returns import show as returns_show  # مرتجعات البضاعة (من مجلد ui)
from ui.audit_log import show as audit_show  # 🆕 سجل التدقيق

st.set_page_config(page_title="XD ERP", layout="wide")

# ========== إعدادات الأيقونة ==========
st.markdown("""
    <link rel="icon" href="https://streamlit.io/favicon.svg">
""", unsafe_allow_html=True)
# =====================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.logged_in:
    auth.show()
else:
    with st.sidebar:
        st.markdown(f"### أهلاً، {st.session_state.user.get('full_name', '')}")
        selected = option_menu(
            menu_title="القائمة الرئيسية",
            options=[
                "لوحة المعلومات",
                "المخزون",
                "المبيعات",
                "المشتريات",
                "مرتجعات البضاعة",
                "الحسابات",
                "الموارد البشرية",
                "شجرة الحسابات",
                "القوائم المالية",
                "الصلاحيات",
                "إغلاق الفترات",
                "إغلاق الحسابات",
                "FIFO المخزون",
                "كشف الرواتب",
                "المساعد الذكي",
                "سجل التدقيق",          # 🆕
                "تسجيل الخروج"
            ],
            icons=[
                "speedometer2",
                "box",
                "cart",
                "truck",
                "arrow-repeat",
                "calculator",
                "people",
                "diagram-3",
                "file-earmark-bar-graph",
                "shield-lock",
                "calendar-check",
                "journal-x",
                "boxes",
                "cash-coin",
                "robot",
                "shield-check",        # 🆕 أيقونة سجل التدقيق
                "box-arrow-right"
            ],
            menu_icon="cast",
            default_index=0,
        )

    if selected == "لوحة المعلومات":
        dashboard.show()
    elif selected == "المخزون":
        inventory.show()
    elif selected == "المبيعات":
        sales.show()
    elif selected == "المشتريات":
        purchases.show()
    elif selected == "مرتجعات البضاعة":
        returns_show()
    elif selected == "الحسابات":
        accounting.show()
    elif selected == "الموارد البشرية":
        hr.show()
    elif selected == "شجرة الحسابات":
        chart_of_accounts.show()
    elif selected == "القوائم المالية":
        financial_reports.show()
    elif selected == "الصلاحيات":
        roles_permissions.show()
    elif selected == "إغلاق الفترات":
        period_closing.show()
    elif selected == "إغلاق الحسابات":
        closing_entries.show()
    elif selected == "FIFO المخزون":
        fifo_inventory.show()
    elif selected == "كشف الرواتب":
        payroll.show()
    elif selected == "المساعد الذكي":
        ai_assistant.show()
    elif selected == "سجل التدقيق":     # 🆕
        audit_show()
    elif selected == "تسجيل الخروج":
        auth.logout()
