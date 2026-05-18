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

st.set_page_config(page_title="نظام ERP", layout="wide")

# 🆕 هذا السطر يضيف manifest.json للأيقونة الاحترافية
st.markdown('<link rel="manifest" href="manifest.json">', unsafe_allow_html=True)

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
