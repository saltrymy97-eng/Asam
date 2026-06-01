import streamlit as st
from streamlit_option_menu import option_menu
import database

# تهيئة قاعدة البيانات
database.init_db()
database.create_default_admin()

# استيراد وحدات المصادقة الجديدة
from ui.auth_ui import show as auth_show
from services.auth_service import logout_session

# استيراد الوحدات المفصولة كاملة (Services + UI)
from ui.dashboard_ui import show as dashboard_show
from ui.inventory_ui import show as inventory_show
from ui.hr_ui import show as hr_show
from ui.chart_ui import show as chart_show
from ui.financial_ui import show as financial_show
from ui.roles_ui import show as roles_show
from ui.period_ui import show as period_show
from ui.fifo_ui import show as fifo_show
from ui.payroll_ui import show as payroll_show
from ui.closing_ui import show as closing_show
from ui.returns import show as returns_show
from ui.audit_log import show as audit_show
from ui.backup import show as backup_show
from ui.pdf_reports import show as pdf_show
from ui.accounting_ui import show as accounting_show
from ui.sales_ui import show as sales_show
from ui.purchases_ui import show as purchases_show
from ui.ai_ui import show as ai_show
from ui.vat_ui import show as vat_show
from ui.crm_ui import show as crm_show
from ui.assets_ui import show as assets_show
from ui.cost_center_ui import show as cost_center_show  # 🆕 مراكز التكلفة

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
                "إدارة العملاء",          # CRM
                "الأصول الثابتة",         # الأصول الثابتة
                "شجرة الحسابات",
                "القوائم المالية",
                "مراكز التكلفة",          # 🆕 مراكز التكلفة
                "الصلاحيات",
                "إغلاق الفترات",
                "إغلاق الحسابات",
                "FIFO المخزون",
                "كشف الرواتب",
                "الضريبة",
                "المساعد الذكي",
                "سجل التدقيق",
                "نسخ احتياطي",
                "تقارير HTML",
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
                "people-fill",            # CRM
                "building",               # الأصول الثابتة
                "diagram-3",              # شجرة الحسابات
                "file-earmark-bar-graph", # القوائم المالية
                "pie-chart",              # 🆕 أيقونة مراكز التكلفة
                "shield-lock",            # الصلاحيات
                "calendar-check",
                "journal-x",
                "boxes",
                "cash-coin",
                "receipt-cutoff",
                "robot",
                "shield-check",
                "cloud-upload",
                "file-earmark-code",
                "box-arrow-right"
            ],
            menu_icon="cast",
            default_index=0,
        )

    if selected == "لوحة المعلومات":
        dashboard_show()
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
    elif selected == "إدارة العملاء":
        crm_show()
    elif selected == "الأصول الثابتة":
        assets_show()
    elif selected == "شجرة الحسابات":
        chart_show()
    elif selected == "القوائم المالية":
        financial_show()
    elif selected == "مراكز التكلفة":      # 🆕
        cost_center_show()
    elif selected == "الصلاحيات":
        roles_show()
    elif selected == "إغلاق الفترات":
        period_show()
    elif selected == "إغلاق الحسابات":
        closing_show()
    elif selected == "FIFO المخزون":
        fifo_show()
    elif selected == "كشف الرواتب":
        payroll_show()
    elif selected == "الضريبة":
        vat_show()
    elif selected == "المساعد الذكي":
        ai_show()
    elif selected == "سجل التدقيق":
        audit_show()
    elif selected == "نسخ احتياطي":
        backup_show()
    elif selected == "تقارير HTML":
        pdf_show()
    elif selected == "تسجيل الخروج":
        logout_session()
