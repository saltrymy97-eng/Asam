import streamlit as st
import database

# تهيئة قاعدة البيانات
database.init_db()
database.create_default_admin()

# استيراد وحدات المصادقة
from ui.auth_ui import show as auth_show
from services.auth_service import logout_session

# استيراد جميع الوحدات
from ui.dashboard_ui import show as dashboard_show
from ui.inventory_ui import show as inventory_show
from ui.sales_ui import show as sales_show
from ui.purchases_ui import show as purchases_show
from ui.returns import show as returns_show
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

st.set_page_config(page_title="XD ERP", layout="wide")

# ========== تصميم القائمة الجانبية الفاخرة ==========
st.markdown("""
<style>
    /* خلفية القائمة الجانبية بتدرج زجاجي */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(20,20,40,0.95) 0%, rgba(10,10,30,0.98) 100%);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255,255,255,0.1);
    }
    /* حاوية القسم */
    .menu-section {
        margin: 15px 10px 5px 10px;
        padding: 8px 12px;
        border-radius: 12px;
        background: rgba(255,255,255,0.03);
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 2px;
        color: #a78bfa;
        text-transform: uppercase;
    }
    /* أزرار القائمة */
    .stButton > button {
        width: 100%;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        color: #ddd;
        text-align: right;
        padding: 10px 15px;
        font-size: 0.95rem;
        transition: all 0.3s ease;
        margin-bottom: 3px;
    }
    .stButton > button:hover {
        background: rgba(139, 92, 246, 0.25);
        border-color: #a78bfa;
        color: white;
        transform: translateX(-5px);
    }
    /* زر الخروج */
    .logout-btn > button {
        background: rgba(239, 68, 68, 0.2);
        border-color: rgba(239, 68, 68, 0.4);
        color: #fca5a5;
        margin-top: 20px;
    }
    .logout-btn > button:hover {
        background: rgba(239, 68, 68, 0.4);
        color: white;
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
    with st.sidebar:
        # شعار النظام
        st.markdown("""
        <div style="text-align:center; padding:20px 0 10px 0;">
            <span style="font-size:2.5rem;">🏢</span>
            <h2 style="color:white; margin:5px 0; font-weight:700;">XD ERP</h2>
            <p style="color:#a78bfa; font-size:0.8rem; letter-spacing:3px;">ENTERPRISE</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"<p style='text-align:center; color:#ccc;'>أهلاً، {st.session_state.user.get('full_name', '')}</p>", unsafe_allow_html=True)
        st.divider()

        # المجموعة 1: الرئيسية
        st.markdown('<div class="menu-section">🏠 الرئيسية</div>', unsafe_allow_html=True)
        if st.button("📊 لوحة المعلومات", key="dashboard"):
            st.session_state.current_page = "لوحة المعلومات"

        # المجموعة 2: العمليات
        st.markdown('<div class="menu-section">📦 العمليات</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🛒 مبيعات", key="sales"): st.session_state.current_page = "المبيعات"
            if st.button("📋 مشتريات", key="purchases"): st.session_state.current_page = "المشتريات"
            if st.button("🔄 مرتجعات", key="returns"): st.session_state.current_page = "مرتجعات البضاعة"
        with col2:
            if st.button("📦 مخزون", key="inventory"): st.session_state.current_page = "المخزون"
            if st.button("👥 CRM", key="crm"): st.session_state.current_page = "إدارة العملاء"

        # المجموعة 3: المحاسبة والمالية
        st.markdown('<div class="menu-section">💰 المحاسبة والمالية</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧾 حسابات", key="accounting"): st.session_state.current_page = "الحسابات"
            if st.button("🌳 شجرة الحسابات", key="chart"): st.session_state.current_page = "شجرة الحسابات"
            if st.button("📈 قوائم مالية", key="financial"): st.session_state.current_page = "القوائم المالية"
            if st.button("🏢 مراكز تكلفة", key="cost_center"): st.session_state.current_page = "مراكز التكلفة"
            if st.button("💱 عملات", key="currency"): st.session_state.current_page = "العملات"
        with col2:
            if st.button("🏦 بنوك", key="bank"): st.session_state.current_page = "التعاملات البنكية"
            if st.button("🧾 ضريبة", key="vat"): st.session_state.current_page = "الضريبة"
            if st.button("🔒 إغلاق حسابات", key="closing"): st.session_state.current_page = "إغلاق الحسابات"
            if st.button("📅 إغلاق فترات", key="period"): st.session_state.current_page = "إغلاق الفترات"
            if st.button("📊 FIFO", key="fifo"): st.session_state.current_page = "FIFO المخزون"

        # المجموعة 4: إدارة الأعمال
        st.markdown('<div class="menu-section">👥 إدارة الأعمال</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👔 موارد بشرية", key="hr"): st.session_state.current_page = "الموارد البشرية"
            if st.button("💰 رواتب", key="payroll"): st.session_state.current_page = "كشف الرواتب"
        with col2:
            if st.button("🏗️ أصول ثابتة", key="assets"): st.session_state.current_page = "الأصول الثابتة"
            if st.button("📎 مرفقات", key="attachments"): st.session_state.current_page = "المرفقات"

        # المجموعة 5: النظام والأمان
        st.markdown('<div class="menu-section">⚙️ النظام والأمان</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🛡️ صلاحيات", key="roles"): st.session_state.current_page = "الصلاحيات"
            if st.button("📋 سجل تدقيق", key="audit"): st.session_state.current_page = "سجل التدقيق"
        with col2:
            if st.button("💾 نسخ احتياطي", key="backup"): st.session_state.current_page = "نسخ احتياطي"
            if st.button("📄 تقارير HTML", key="pdf"): st.session_state.current_page = "تقارير HTML"

        # المجموعة 6: الذكاء الاصطناعي
        st.markdown('<div class="menu-section">🤖 الذكاء الاصطناعي</div>', unsafe_allow_html=True)
        if st.button("🧠 المساعد الذكي", key="ai"):
            st.session_state.current_page = "المساعد الذكي"

        st.divider()
        # زر الخروج
        if st.button("🚪 تسجيل الخروج", key="logout", help="تسجيل الخروج من النظام"):
            logout_session()

    # ========== توجيه الصفحات ==========
    page = st.session_state.current_page
    if page == "لوحة المعلومات": dashboard_show()
    elif page == "المخزون": inventory_show()
    elif page == "المبيعات": sales_show()
    elif page == "المشتريات": purchases_show()
    elif page == "مرتجعات البضاعة": returns_show()
    elif page == "الحسابات": accounting_show()
    elif page == "الموارد البشرية": hr_show()
    elif page == "إدارة العملاء": crm_show()
    elif page == "الأصول الثابتة": assets_show()
    elif page == "شجرة الحسابات": chart_show()
    elif page == "القوائم المالية": financial_show()
    elif page == "العملات": currency_show()
    elif page == "التعاملات البنكية": bank_show()
    elif page == "مراكز التكلفة": cost_center_show()
    elif page == "المرفقات": attachment_show()
    elif page == "الصلاحيات": roles_show()
    elif page == "إغلاق الفترات": period_show()
    elif page == "إغلاق الحسابات": closing_show()
    elif page == "FIFO المخزون": fifo_show()
    elif page == "كشف الرواتب": payroll_show()
    elif page == "الضريبة": vat_show()
    elif page == "المساعد الذكي": ai_show()
    elif page == "سجل التدقيق": audit_show()
    elif page == "نسخ احتياطي": backup_show()
    elif page == "تقارير HTML": pdf_show()
