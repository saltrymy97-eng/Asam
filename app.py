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

# إعدادات الصفحة الأساسية
st.set_page_config(page_title="XD ERP", layout="wide")

# ========== 🆕 إعدادات الأيقونة المُحسّنة ==========
st.markdown("""
    <link rel="manifest" href="manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <link rel="apple-touch-icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIj48ZGVmcz48bGluZWFyR3JhZGllbnQgaWQ9ImJnIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIxMDAlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMEYxNzJBIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMUUxQjRCIi8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9IngiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPjxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9IiNGNTlFMEIiLz48c3RvcCBvZmZzZXQ9IjQwJSIgc3RvcC1jb2xvcj0iI0VDNDg5OSIvPjxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzhCNUNGNSIvPjwvbGluZWFyR3JhZGllbnQ+PGZpbHRlciBpZD0iZ2xvdyI+PGZlR2F1c3NpYW5CbHVyIHN0ZERldmlhdGlvbj0iNiIvPjwvZmlsdGVyPjwvZGVmcz48cmVjdCB3aWR0aD0iNTEyIiBoZWlnaHQ9IjUxMiIgcng9IjEyOCIgZmlsbD0idXJsKCNiZykiLz48dGV4dCB4PSIyNTYiIHk9IjM1NSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1zaXplPSIzNDAiIGZvbnQtd2VpZ2h0PSI5MDAiIGZvbnQtZmFtaWx5PSJBcmlhbCBCbGFjayIgZmlsbD0idXJsKCN4KSIgZmlsdGVyPSJ1cmwoI2dsb3cpIj5YPC90ZXh0Pjwvc3ZnPg==">
    <meta name="theme-color" content="#0F172A">
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
