import streamlit as st
from streamlit_option_menu import option_menu
import database

# تهيئة قاعدة البيانات
database.init_db()
database.create_default_admin()

# استيراد وحدات المصادقة الجديدة
from ui.auth_ui import show as auth_show
from services.auth_service import logout_session

# استيراد الوحدات القديمة
import dashboard
from ui.inventory_ui import show as inventory_show  # المخزون (منفصلة)
from ui.hr_ui import show as hr_show  # الموارد البشرية (منفصلة)

# استيراد الوحدات الجديدة
from ui.chart_ui import show as chart_show  # شجرة الحسابات (منفصلة)
from ui.financial_ui import show as financial_show  # القوائم المالية (منفصلة)
from ui.roles_ui import show as roles_show  # الصلاحيات (منفصلة)
from ui.period_ui import show as period_show  # إغلاق الفترات (منفصلة)
import fifo_inventory
from ui.payroll_ui import show as payroll_show  # كشف الرواتب (منفصلة)
import ai_assistant
from ui.closing_ui import show as closing_show  # 🆕 قيد إغلاق الحسابات (منفصلة)
from ui.returns import show as returns_show  # مرتجعات البضاعة
from ui.audit_log import show as audit_show  # سجل التدقيق
from ui.backup import show as backup_show    # النسخ الاحتياطي
from ui.pdf_reports import show as pdf_show  # تقارير PDF
from ui.accounting_ui import show as accounting_show  # الحسابات (منفصلة)
from ui.sales_ui import show as sales_show  # المبيعات (منفصلة)
from ui.purchases_ui import show as purchases_show  # المشتريات (منفصلة)

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
    auth_show()
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
                "سجل التدقيق",
                "نسخ احتياطي",
                "تقارير PDF",
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
                "shield-check",
                "cloud-upload",
                "file-earmark-pdf",
                "box-arrow-right"
            ],
            menu_icon="cast",
            default_index=0,
        )

    if selected == "لوحة المعلومات":
        dashboard.show()
    elif selected == "المخزون":
        inventory_show()
    elif selected == "المبيعات":
        sales_show()
    elif selected == "المشتريات":
        purchases_show()
    elif selected == "مرتجعات البضاعة":
        returns_show()
    elif selected == "الحسابات":
        accounting_show()
    elif selected == "الموارد البشرية":
        hr_show()
    elif selected == "شجرة الحسابات":
        chart_show()
    elif selected == "القوائم المالية":
        financial_show()
    elif selected == "الصلاحيات":
        roles_show()
    elif selected == "إغلاق الفترات":
        period_show()
    elif selected == "إغلاق الحسابات":
        closing_show()  # 🆕 تم الاستدعاء من الوحدة المنفصلة
    elif selected == "FIFO المخزون":
        fifo_inventory.show()
    elif selected == "كشف الرواتب":
        payroll_show()
    elif selected == "المساعد الذكي":
        ai_assistant.show()
    elif selected == "سجل التدقيق":
        audit_show()
    elif selected == "نسخ احتياطي":
        backup_show()
    elif selected == "تقارير PDF":
        pdf_show()
    elif selected == "تسجيل الخروج":
        logout_session()
