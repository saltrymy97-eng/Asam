import streamlit as st
import database

# تهيئة قاعدة البيانات
database.init_db()
database.create_default_admin()

# 🆕 تهيئة العملات الافتراضية (يجب أن تكون قبل استيراد الوحدات التي تستخدمها)
from services.currency_service import create_default_currencies
create_default_currencies()

# استيراد وحدات المصادقة
from ui.auth_ui import show as auth_show
from services.auth_service import logout_session

# استيراد وحدات الصلاحيات
from services.roles_service import (
    seed_default_roles,
    check_permission,
    get_allowed_modules
)

# تهيئة الأدوار والصلاحيات الافتراضية
seed_default_roles()

# استيراد جميع الوحدات
from ui.dashboard_ui import show as dashboard_show
from ui.inventory_ui import show as inventory_show
from ui.inventory_adjustment_ui import show as inventory_adjustment_show
from ui.sales_ui import show as sales_show
from ui.purchases_ui import show as purchases_show
from ui.returns import show as returns_show
from ui.receipts_ui import show as receipts_show
from ui.expenses_ui import show as expenses_show
from ui.opening_balances_ui import show as opening_show
from ui.currency_revaluation_ui import show as revaluation_show
from ui.accounting_ui import show as accounting_show
from ui.chart_ui import show as chart_show
from ui.financial_ui import show as financial_show
from ui.cost_center_ui import show as cost_center_show
from ui.currency_ui import show as currency_show
from ui.bank_ui import show as bank_show
from ui.vat_ui import show as vat_show
from ui.closing_ui import show as closing_show
from ui.period_ui import show as period_show
from ui.fifo_ui import show as fifo_show
from ui.crm_ui import show as crm_show
from ui.hr_ui import show as hr_show
from ui.assets_ui import show as assets_show
from ui.attachment_ui import show as attachment_show
from ui.payroll_ui import show as payroll_show
from ui.roles_ui import show as roles_show
from ui.audit_log import show as audit_show
from ui.backup import show as backup_show
from ui.pdf_reports import show as pdf_show
from ui.ai_ui import show as ai_show

st.set_page_config(page_title="حوكمة ERP", layout="wide")

# ========== تصميم القائمة الجانبية الفاخرة ==========
st.markdown("""
<style>
    /* استيراد خط 29LT Bukra Bold للشعار وخط Cairo للواجهة */
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #020617 100%);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(6, 182, 212, 0.15);
    }
    .menu-section {
        margin: 15px 10px 5px 10px;
        padding: 8px 12px;
        border-radius: 12px;
        background: rgba(6, 182, 212, 0.05);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 2px;
        color: #06B6D4;
        text-transform: uppercase;
    }
    .stButton > button {
        width: 100%;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        color: #CBD5E1;
        text-align: right;
        padding: 10px 15px;
        font-size: 0.95rem;
        font-family: 'Cairo', sans-serif;
        transition: all 0.3s ease;
        margin-bottom: 3px;
    }
    .stButton > button:hover {
        background: rgba(6, 182, 212, 0.15);
        border-color: rgba(6, 182, 212, 0.3);
        color: #FFFFFF;
        transform: translateX(-5px);
    }
    .logout-btn > button {
        background: rgba(239, 68, 68, 0.15);
        border-color: rgba(239, 68, 68, 0.3);
        color: #FCA5A5;
        margin-top: 20px;
    }
    .logout-btn > button:hover {
        background: rgba(239, 68, 68, 0.3);
        color: white;
    }
    .permission-denied {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid #EF4444;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        color: #FCA5A5;
        margin-top: 2rem;
        font-family: 'Cairo', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "لوحة المعلومات"

if not st.session_state.logged_in:
    auth_show()
else:
    username = st.session_state.user.get('username', '')
    # المدير يرى كل شيء
    if username == 'admin':
        allowed_modules = None  # None يعني كل الوحدات
    else:
        allowed_modules = get_allowed_modules(username)

    def can_access(module):
        if username == 'admin':
            return True
        return module in allowed_modules if allowed_modules else False

    with st.sidebar:
        # شعار النظام - هوية حوكمة ERP الجديدة
        st.markdown("""
        <div style="text-align:center; padding:25px 0 15px 0;">
            <div style="
                background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(6, 182, 212, 0.25);
                border-top: 1px solid rgba(6, 182, 212, 0.4);
                border-radius: 24px;
                padding: 20px 15px;
                margin-bottom: 10px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05);
            ">
                <span style="font-size:2.2rem; filter: drop-shadow(0 0 15px rgba(6, 182, 212, 0.5));">🏛️</span>
                <h1 style="
                    color: #FFFFFF;
                    font-family: 'Cairo', sans-serif;
                    font-size: 1.8rem;
                    font-weight: 800;
                    margin: 8px 0 2px 0;
                    letter-spacing: 1px;
                    background: linear-gradient(135deg, #FFFFFF 0%, #06B6D4 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    text-shadow: none;
                ">حوكمة ERP</h1>
                <p style="
                    color: #06B6D4;
                    font-family: 'Cairo', sans-serif;
                    font-size: 0.7rem;
                    letter-spacing: 3px;
                    font-weight: 600;
                    margin: 0;
                    text-transform: uppercase;
                ">إدارة ذكية • قرارات واثقة</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"<p style='text-align:center; color:#94A3B8; font-family: Cairo, sans-serif;'>أهلاً، {st.session_state.user.get('full_name', '')}</p>", unsafe_allow_html=True)
        st.divider()

        # المجموعة 1: الرئيسية
        st.markdown('<div class="menu-section">🏠 الرئيسية</div>', unsafe_allow_html=True)
        if st.button("📊 لوحة المعلومات", key="dashboard"):
            st.session_state.current_page = "لوحة المعلومات"

        # المجموعة 2: العمليات
        st.markdown('<div class="menu-section">📦 العمليات</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if can_access("المبيعات") and st.button("🛒 مبيعات", key="sales"): st.session_state.current_page = "المبيعات"
            if can_access("المشتريات") and st.button("📋 مشتريات", key="purchases"): st.session_state.current_page = "المشتريات"
            if can_access("مرتجعات البضاعة") and st.button("🔄 مرتجعات", key="returns"): st.session_state.current_page = "مرتجعات البضاعة"
            if can_access("سندات القبض والصرف") and st.button("💵 سندات قبض/صرف", key="receipts"): st.session_state.current_page = "سندات القبض والصرف"
        with col2:
            if can_access("المخزون") and st.button("📦 مخزون", key="inventory"): st.session_state.current_page = "المخزون"
            if can_access("التسويات المخزنية") and st.button("📦 تسويات مخزنية", key="adjustments"): st.session_state.current_page = "التسويات المخزنية"
            if can_access("المصروفات") and st.button("🧾 مصروفات", key="expenses"): st.session_state.current_page = "المصروفات"
            if can_access("إدارة العملاء") and st.button("👥 CRM", key="crm"): st.session_state.current_page = "إدارة العملاء"

        # المجموعة 3: المحاسبة والمالية
        st.markdown('<div class="menu-section">💰 المحاسبة والمالية</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if can_access("الحسابات") and st.button("🧾 حسابات", key="accounting"): st.session_state.current_page = "الحسابات"
            if can_access("شجرة الحسابات") and st.button("🌳 شجرة الحسابات", key="chart"): st.session_state.current_page = "شجرة الحسابات"
            if can_access("القوائم المالية") and st.button("📈 قوائم مالية", key="financial"): st.session_state.current_page = "القوائم المالية"
            if can_access("مراكز التكلفة") and st.button("🏢 مراكز تكلفة", key="cost_center"): st.session_state.current_page = "مراكز التكلفة"
            if can_access("العملات") and st.button("💱 عملات", key="currency"): st.session_state.current_page = "العملات"
            if can_access("الأرصدة الافتتاحية") and st.button("📋 أرصدة افتتاحية", key="opening"): st.session_state.current_page = "الأرصدة الافتتاحية"
        with col2:
            if can_access("التعاملات البنكية") and st.button("🏦 بنوك", key="bank"): st.session_state.current_page = "التعاملات البنكية"
            if can_access("الضريبة") and st.button("🧾 ضريبة", key="vat"): st.session_state.current_page = "الضريبة"
            if can_access("إغلاق الحسابات") and st.button("🔒 إغلاق حسابات", key="closing"): st.session_state.current_page = "إغلاق الحسابات"
            if can_access("إغلاق الفترات") and st.button("📅 إغلاق فترات", key="period"): st.session_state.current_page = "إغلاق الفترات"
            if can_access("FIFO المخزون") and st.button("📊 FIFO", key="fifo"): st.session_state.current_page = "FIFO المخزون"
            if can_access("تقييم العملات") and st.button("💱 تقييم عملات", key="revaluation"): st.session_state.current_page = "تقييم العملات"

        # المجموعة 4: إدارة الأعمال
        st.markdown('<div class="menu-section">👥 إدارة الأعمال</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if can_access("الموارد البشرية") and st.button("👔 موارد بشرية", key="hr"): st.session_state.current_page = "الموارد البشرية"
            if can_access("كشف الرواتب") and st.button("💰 رواتب", key="payroll"): st.session_state.current_page = "كشف الرواتب"
        with col2:
            if can_access("الأصول الثابتة") and st.button("🏗️ أصول ثابتة", key="assets"): st.session_state.current_page = "الأصول الثابتة"
            if can_access("المرفقات") and st.button("📎 مرفقات", key="attachments"): st.session_state.current_page = "المرفقات"

        # المجموعة 5: النظام والأمان
        st.markdown('<div class="menu-section">⚙️ النظام والأمان</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if can_access("الصلاحيات") and st.button("🛡️ صلاحيات", key="roles"): st.session_state.current_page = "الصلاحيات"
            if can_access("سجل التدقيق") and st.button("📋 سجل تدقيق", key="audit"): st.session_state.current_page = "سجل التدقيق"
        with col2:
            if can_access("نسخ احتياطي") and st.button("💾 نسخ احتياطي", key="backup"): st.session_state.current_page = "نسخ احتياطي"
            if can_access("تقارير HTML") and st.button("📄 تقارير HTML", key="pdf"): st.session_state.current_page = "تقارير HTML"

        # المجموعة 6: الذكاء الاصطناعي
        st.markdown('<div class="menu-section">🤖 الذكاء الاصطناعي</div>', unsafe_allow_html=True)
        if can_access("المساعد الذكي") and st.button("🧠 المساعد الذكي", key="ai"):
            st.session_state.current_page = "المساعد الذكي"

        st.divider()
        # زر الخروج
        if st.button("🚪 تسجيل الخروج", key="logout", help="تسجيل الخروج من النظام"):
            logout_session()

    # ========== توجيه الصفحات مع التحقق من الصلاحية ==========
    page = st.session_state.current_page

    # دوال عرض مخصصة مع التحقق
    def show_if_permitted(module, show_func):
        if can_access(module):
            show_func()
        else:
            st.markdown(f"""
            <div class="permission-denied">
                <h2>⛔ غير مصرح</h2>
                <p>ليس لديك صلاحية للوصول إلى وحدة "{module}".</p>
            </div>
            """, unsafe_allow_html=True)

    if page == "لوحة المعلومات": dashboard_show()
    elif page == "المخزون": show_if_permitted("المخزون", inventory_show)
    elif page == "التسويات المخزنية": show_if_permitted("التسويات المخزنية", inventory_adjustment_show)
    elif page == "المبيعات": show_if_permitted("المبيعات", sales_show)
    elif page == "المشتريات": show_if_permitted("المشتريات", purchases_show)
    elif page == "مرتجعات البضاعة": show_if_permitted("مرتجعات البضاعة", returns_show)
    elif page == "سندات القبض والصرف": show_if_permitted("سندات القبض والصرف", receipts_show)
    elif page == "المصروفات": show_if_permitted("المصروفات", expenses_show)
    elif page == "الأرصدة الافتتاحية": show_if_permitted("الأرصدة الافتتاحية", opening_show)
    elif page == "تقييم العملات": show_if_permitted("تقييم العملات", revaluation_show)
    elif page == "الحسابات": show_if_permitted("الحسابات", accounting_show)
    elif page == "الموارد البشرية": show_if_permitted("الموارد البشرية", hr_show)
    elif page == "إدارة العملاء": show_if_permitted("إدارة العملاء", crm_show)
    elif page == "الأصول الثابتة": show_if_permitted("الأصول الثابتة", assets_show)
    elif page == "شجرة الحسابات": show_if_permitted("شجرة الحسابات", chart_show)
    elif page == "القوائم المالية": show_if_permitted("القوائم المالية", financial_show)
    elif page == "العملات": show_if_permitted("العملات", currency_show)
    elif page == "التعاملات البنكية": show_if_permitted("التعاملات البنكية", bank_show)
    elif page == "مراكز التكلفة": show_if_permitted("مراكز التكلفة", cost_center_show)
    elif page == "المرفقات": show_if_permitted("المرفقات", attachment_show)
    elif page == "الصلاحيات": show_if_permitted("الصلاحيات", roles_show)
    elif page == "إغلاق الفترات": show_if_permitted("إغلاق الفترات", period_show)
    elif page == "إغلاق الحسابات": show_if_permitted("إغلاق الحسابات", closing_show)
    elif page == "FIFO المخزون": show_if_permitted("FIFO المخزون", fifo_show)
    elif page == "كشف الرواتب": show_if_permitted("كشف الرواتب", payroll_show)
    elif page == "الضريبة": show_if_permitted("الضريبة", vat_show)
    elif page == "المساعد الذكي": show_if_permitted("المساعد الذكي", ai_show)
    elif page == "سجل التدقيق": show_if_permitted("سجل التدقيق", audit_show)
    elif page == "نسخ احتياطي": show_if_permitted("نسخ احتياطي", backup_show)
    elif page == "تقارير HTML": show_if_permitted("تقارير HTML", pdf_show)
