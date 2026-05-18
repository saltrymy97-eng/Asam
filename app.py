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

st.set_page_config(page_title="XD ERP", layout="wide")

# ========== 🆕 إعدادات الأيقونة الشاملة والمضمونة ==========
st.markdown("""
    <!-- أيقونة أساسية للأندرويد والويب -->
    <link rel="icon" type="image/png" sizes="192x192" href="https://placehold.co/192x192/0F172A/F59E0B?text=X&font=raleway">
    <link rel="shortcut icon" href="https://placehold.co/192x192/0F172A/F59E0B?text=X&font=raleway">
    
    <!-- آبل (أيفون) -->
    <link rel="apple-touch-icon" sizes="180x180" href="https://placehold.co/180x180/0F172A/F59E0B?text=X&font=raleway">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    
    <!-- شريط العنوان واللون -->
    <meta name="theme-color" content="#0F172A">
    <meta name="msapplication-TileColor" content="#0F172A">
    
    <!-- اختصار التطبيق -->
    <link rel="manifest" href="data:application/json;base64,ewogICJuYW1lIjogIlhEIEVSUCIsCiAgInNob3J0X25hbWUiOiAiWEQiLAogICJzdGFydF91cmwiOiAiLyIsCiAgImRpc3BsYXkiOiAic3RhbmRhbG9uZSIsCiAgImJhY2tncm91bmRfY29sb3IiOiAiIzB GMTcyQSIsCiAgInRoZW1lX2NvbG9yIjogIiMwRjE3MkEiLAogICJpY29ucyI6IFsKICAgIHsKICAgICAgInNyYyI6ICJodHRwczovL3BsYWNlaG9sZC5jby8xOTJ4MTkyLzB GMTcyQS9GNTlFMEI/dGV4dD1YJmZvbnQ9cmFsZXdheSIsCiAgICAgICJzaXplcyI6ICIxOTJ4MTkyIiwKICAgICAgInR5cGUiOiAiaW1hZ2UvcG5nIgogICAgfQogIF0KfQ==">
""", unsafe_allow_html=True)
# =============================================

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
                "الحسابات",
                "الموارد البشرية",
                "شجرة الحسابات",
                "القوائم المالية",
                "الصلاحيات",
                "إغلاق الفترات",
                "FIFO المخزون",
                "كشف الرواتب",
                "تسجيل الخروج"
            ],
            icons=[
                "speedometer2",
                "box",
                "cart",
                "truck",
                "calculator",
                "people",
                "diagram-3",
                "file-earmark-bar-graph",
                "shield-lock",
                "calendar-check",
                "boxes",
                "cash-coin",
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
    elif selected == "FIFO المخزون":
        fifo_inventory.show()
    elif selected == "كشف الرواتب":
        payroll.show()
    elif selected == "تسجيل الخروج":
        auth.logout()
