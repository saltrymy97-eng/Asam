import html
import streamlit as st
import database

# ============================================================
# إعداد الصفحة
# ============================================================
st.set_page_config(
    page_title="حوكمة ERP",
    page_icon="icon.ico",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# تهيئة قاعدة البيانات والنظام
# ============================================================
database.init_db()
database.create_default_admin()

from services.currency_service import create_default_currencies
create_default_currencies()

from ui.auth_ui import show as auth_show
from services.auth_service import logout_session

from services.roles_service import (
    seed_default_roles,
    check_permission,
    get_allowed_modules
)

seed_default_roles()

# ============================================================
# استيراد الوحدات
# ============================================================
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
from ui.cash_ui import show as cash_show

# ============================================================
# أدوات مساعدة
# ============================================================
def safe_html(value, default=""):
    if value is None:
        value = default
    return html.escape(str(value))

# ============================================================
# التصميم العام
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,500,1,0');

:root {
    --primary: #8B5CF6;
    --primary-light: #A78BFA;
    --primary-dark: #6D28D9;
    --surface: #17172B;
    --surface-light: #20203A;
    --text-main: #F8FAFC;
    --text-muted: #A1A1AA;
    --border: rgba(255,255,255,0.08);
}

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif !important;
}

.stApp {
    background: radial-gradient(circle at 85% 5%, rgba(109, 40, 217, 0.09), transparent 28%),
                linear-gradient(135deg, #0B0B18 0%, #101024 50%, #0B0B18 100%);
}

.material-icon {
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal;
    font-style: normal;
    font-size: 21px;
    line-height: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: middle;
    direction: ltr;
    white-space: nowrap;
    font-feature-settings: 'liga';
    -webkit-font-feature-settings: 'liga';
    font-variation-settings: 'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24;
}

.menu-section .material-icon { font-size: 20px; color: #A78BFA; }
.brand-icon .material-icon { font-size: 45px; color: #C4B5FD; }
.user-icon .material-icon { font-size: 19px; color: #A78BFA; }
.permission-icon .material-icon { font-size: 43px; color: #FCA5A5; }
.seed-icon .material-icon { font-size: 49px; color: #C4B5FD; }

#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 100%; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #17172D 0%, #111124 55%, #0D0D1D 100%);
    border-right: 1px solid rgba(167,139,250,0.15);
}
[data-testid="stSidebar"] > div:first-child { padding: 1.2rem 0.9rem 2rem 0.9rem; }

.menu-section {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 22px 4px 9px 4px;
    padding: 10px 13px;
    border-radius: 10px;
    background: linear-gradient(90deg, rgba(139,92,246,0.13), rgba(139,92,246,0.025));
    border-right: 3px solid #8B5CF6;
    color: #C4B5FD;
    font-size: 0.83rem;
    font-weight: 800;
    letter-spacing: 0.3px;
}

[data-testid="stSidebar"] .stButton { width: 100%; margin-bottom: 5px; }
[data-testid="stSidebar"] .stButton > button {
    width: 100%; min-height: 43px; display: flex; align-items: center; justify-content: flex-start;
    gap: 10px; padding: 9px 13px; border-radius: 10px; border: 1px solid transparent;
    background: rgba(255,255,255,0.025); color: #D4D4E0; font-family: 'Cairo', sans-serif !important;
    font-size: 0.91rem; font-weight: 600; text-align: right; transition: all 0.2s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(139,92,246,0.16); border-color: rgba(167,139,250,0.35); color: #FFFFFF; transform: translateX(-3px);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(100deg, #6D28D9, #8B5CF6);
    border: 1px solid rgba(196,181,253,0.45); color: #FFFFFF; font-weight: 800; box-shadow: 0 4px 14px rgba(109,40,217,0.25);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: linear-gradient(100deg, #7C3AED, #A78BFA); color: #FFFFFF;
}

.logout-area .stButton > button {
    margin-top: 12px; background: rgba(239,68,68,0.10); border: 1px solid rgba(239,68,68,0.25); color: #FCA5A5;
}
.logout-area .stButton > button:hover {
    background: rgba(239,68,68,0.25); border-color: rgba(239,68,68,0.55); color: #FFFFFF;
}

[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.09); margin: 18px 0; }

.brand-panel {
    text-align: center; padding: 22px 10px 17px 10px; margin-bottom: 12px; border-radius: 16px;
    background: linear-gradient(145deg, rgba(139,92,246,0.15), rgba(255,255,255,0.025));
    border: 1px solid rgba(167,139,250,0.15);
}
.brand-icon { display: flex; align-items: center; justify-content: center; min-height: 55px; }
.brand-title {
    margin: 5px 0 2px 0; font-size: 1.65rem; font-weight: 800; color: #FFFFFF;
    background: linear-gradient(110deg, #FFFFFF, #C4B5FD); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.brand-subtitle { color: #A78BFA; font-size: 0.78rem; font-weight: 600; margin: 0; }

.user-panel { padding: 12px 14px; margin: 12px 2px 15px 2px; border-radius: 12px; background: rgba(255,255,255,0.045); border: 1px solid rgba(255,255,255,0.075); }
.user-label { color: #A1A1AA; font-size: 0.72rem; margin-bottom: 5px; }
.user-name { display: flex; align-items: center; gap: 8px; color: #E9D5FF; font-size: 0.95rem; font-weight: 800; }

.permission-denied {
    background: linear-gradient(145deg, rgba(239,68,68,0.12), rgba(127,29,29,0.08));
    border: 1px solid rgba(239,68,68,0.35); border-radius: 16px; padding: 2.5rem 1.5rem; text-align: center; color: #FCA5A5; margin-top: 2rem;
}
.permission-icon { display: flex; justify-content: center; margin-bottom: 10px; }
.permission-denied h2 { color: #FCA5A5; font-weight: 800; }

.stButton > button { font-family: 'Cairo', sans-serif !important; border-radius: 10px; }
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius: 9px; }
[data-testid="stMetric"] { background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.07); border-radius: 13px; padding: 15px; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: 12px; overflow: hidden; }

@media (max-width: 768px) {
    .block-container { padding: 1rem 0.8rem 2rem 0.8rem; }
    .brand-title { font-size: 1.4rem; }
    .menu-section { font-size: 0.79rem; }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# تهيئة الجلسة
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "لوحة المعلومات"
if "run_seed" not in st.session_state:
    st.session_state.run_seed = False

# ============================================================
# دالة موحدة لأزرار القائمة
# ============================================================
def nav_button(label, page, key, icon, module=None):
    if module and not can_access(module):
        return
    is_active = st.session_state.current_page == page
    if st.button(
        label, key=key, icon=icon, type="primary" if is_active else "secondary", use_container_width=True
    ):
        st.session_state.current_page = page
        st.rerun()

# ============================================================
# شاشة تسجيل الدخول
# ============================================================
if not st.session_state.logged_in:
    auth_show()
else:
    user_data = st.session_state.get("user") or {}
    username = user_data.get("username", "")

    if username == "admin":
        allowed_modules = None
    else:
        allowed_modules = get_allowed_modules(username)

    def can_access(module):
        if username == "admin":
            return True
        return module in allowed_modules if allowed_modules else False

    # ========================================================
    # القائمة الجانبية
    # ========================================================
    with st.sidebar:
        st.markdown("""
        <div class="brand-panel">
            <div class="brand-icon"><span class="material-icon">apartment</span></div>
            <div class="brand-title">حوكمة ERP</div>
            <p class="brand-subtitle">إدارة ذكية .. قرارات واثقة</p>
        </div>
        """, unsafe_allow_html=True)

        display_name = user_data.get("full_name") or user_data.get("username") or "مستخدم النظام"
        st.markdown(f"""
        <div class="user-panel">
            <div class="user-label">المستخدم الحالي</div>
            <div class="user-name">
                <span class="material-icon user-icon">account_circle</span>
                <span>{safe_html(display_name)}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # 1. الرئيسية
        st.markdown('<div class="menu-section"><span class="material-icon">home</span><span>الرئيسية</span></div>', unsafe_allow_html=True)
        nav_button("لوحة المعلومات", "لوحة المعلومات", "dashboard", ":material/dashboard:")

        # 2. العمليات
        st.markdown('<div class="menu-section"><span class="material-icon">inventory_2</span><span>العمليات</span></div>', unsafe_allow_html=True)
        nav_button("مبيعات", "المبيعات", "sales", ":material/shopping_cart:", "المبيعات")
        nav_button("مشتريات", "المشتريات", "purchases", ":material/receipt_long:", "المشتريات")
        nav_button("مرتجعات", "مرتجعات البضاعة", "returns", ":material/assignment_return:", "مرتجعات البضاعة")
        nav_button("سندات قبض/صرف", "سندات القبض والصرف", "receipts", ":material/payments:", "سندات القبض والصرف")
        nav_button("مخزون", "المخزون", "inventory", ":material/inventory:", "المخزون")
        nav_button("تسويات مخزنية", "التسويات المخزنية", "adjustments", ":material/rule:", "التسويات المخزنية")
        nav_button("مصروفات", "المصروفات", "expenses", ":material/money_off:", "المصروفات")
        nav_button("CRM", "إدارة العملاء", "crm", ":material/people:", "إدارة العملاء")

        # 3. المحاسبة والمالية
        st.markdown('<div class="menu-section"><span class="material-icon">account_balance</span><span>المحاسبة والمالية</span></div>', unsafe_allow_html=True)
        nav_button("حسابات", "الحسابات", "accounting", ":material/edit_note:", "الحسابات")
        nav_button("شجرة الحسابات", "شجرة الحسابات", "chart", ":material/account_tree:", "شجرة الحسابات")
        nav_button("قوائم مالية", "القوائم المالية", "financial", ":material/analytics:", "القوائم المالية")
        nav_button("مراكز تكلفة", "مراكز التكلفة", "cost_center", ":material/request_quote:", "مراكز التكلفة")
        nav_button("عملات", "العملات", "currency", ":material/currency_exchange:", "العملات")
        nav_button("أرصدة افتتاحية", "الأرصدة الافتتاحية", "opening", ":material/book:", "الأرصدة الافتتاحية")
        nav_button("صندوق", "الصندوق", "cash", ":material/account_balance_wallet:", "الصندوق")
        nav_button("بنوك", "التعاملات البنكية", "bank", ":material/account_balance:", "التعاملات البنكية")
        nav_button("ضريبة", "الضريبة", "vat", ":material/receipt:", "الضريبة")
        nav_button("إغلاق حسابات", "إغلاق الحسابات", "closing", ":material/lock:", "إغلاق الحسابات")
        nav_button("إغلاق فترات", "إغلاق الفترات", "period", ":material/calendar_month:", "إغلاق الفترات")
        nav_button("FIFO", "FIFO المخزون", "fifo", ":material/swap_vert:", "FIFO المخزون")
        nav_button("تقييم عملات", "تقييم العملات", "revaluation", ":material/currency_exchange:", "تقييم العملات")
        nav_button("تقارير XBRL", "التقارير المالية XBRL", "pdf", ":material/language:", "التقارير المالية XBRL")

        # 4. إدارة الأعمال
        st.markdown('<div class="menu-section"><span class="material-icon">groups</span><span>إدارة الأعمال</span></div>', unsafe_allow_html=True)
        nav_button("موارد بشرية", "الموارد البشرية", "hr", ":material/badge:", "الموارد البشرية")
        nav_button("رواتب", "كشف الرواتب", "payroll", ":material/payments:", "كشف الرواتب")
        nav_button("أصول ثابتة", "الأصول الثابتة", "assets", ":material/foundation:", "الأصول الثابتة")
        nav_button("مرفقات", "المرفقات", "attachments", ":material/attach_file:", "المرفقات")

        # 5. النظام والأمان
        st.markdown('<div class="menu-section"><span class="material-icon">admin_panel_settings</span><span>النظام والأمان</span></div>', unsafe_allow_html=True)
        nav_button("صلاحيات", "الصلاحيات", "roles", ":material/security:", "الصلاحيات")
        nav_button("سجل تدقيق", "سجل التدقيق", "audit", ":material/history:", "سجل التدقيق")
        nav_button("نسخ احتياطي", "نسخ احتياطي", "backup", ":material/backup:", "نسخ احتياطي")

        # 6. أدوات المطور
        if username == "admin":
            st.markdown("---")
            st.markdown("""
            <div class="menu-section" style="color:#FCA5A5;">
                <span class="material-icon" style="color:#FCA5A5;">code</span>
                <span>أدوات المطور</span>
            </div>
            """, unsafe_allow_html=True)

            seed_clicked = st.button(
                "حقن بيانات تجريبية", key="seed_data_btn",
                help="حذف كل البيانات ثم حقن بيانات تجريبية",
                type="primary", icon=":material/eco:", use_container_width=True
            )
            if seed_clicked:
                st.session_state.run_seed = True
                st.rerun()

        # 7. الذكاء الاصطناعي
        st.markdown('<div class="menu-section"><span class="material-icon">psychology</span><span>الذكاء الاصطناعي</span></div>', unsafe_allow_html=True)
        nav_button("المساعد الذكي", "المساعد الذكي", "ai", ":material/psychology:", "المساعد الذكي")

        # 8. تسجيل الخروج
        st.divider()
        st.markdown('<div class="logout-area">', unsafe_allow_html=True)
        logout_clicked = st.button(
            "تسجيل الخروج", key="logout", help="تسجيل الخروج من النظام", icon=":material/logout:", use_container_width=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if logout_clicked:
            _user = st.session_state.get("user") or {}
            logout_session(username=_user.get("username"), user_id=_user.get("id"))
            st.rerun()

    # ========================================================
    # تنفيذ الحقن التجريبي
    # ========================================================
    if st.session_state.get("run_seed", False):
        from services.seed_service import run_full_seed

        st.markdown("""
        <div style="text-align:center; padding:3rem 1rem; border-radius:18px;
                    background:linear-gradient(145deg, rgba(139,92,246,0.14), rgba(255,255,255,0.025));
                    border:1px solid rgba(167,139,250,0.18); margin-bottom:25px;">
            <div class="seed-icon"><span class="material-icon">database</span></div>
            <h1 style="color:#F8FAFC;font-size:2.3rem;">حقن البيانات التجريبية</h1>
            <p style="color:#A1A1AA;font-size:1.05rem;">جاري تجهيز النظام ببيانات واقعية...</p>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("جاري الحقن... قد يستغرق دقيقة إلى دقيقتين"):
            try:
                result = run_full_seed(progress_callback=None)
                if result.get("success"):
                    st.success("تم حقن البيانات بنجاح!")
                    st.balloons()
                    st.markdown("### ملخص البيانات المحقونة")
                    summary = result.get("summary", {})
                    items = list(summary.items())
                    cols = st.columns(3)
                    for i, (key, value) in enumerate(items):
                        with cols[i % 3]:
                            st.metric(key, value)
                else:
                    st.error(f"فشل الحقن: {result.get('error', 'خطأ غير معروف')}")
            except Exception as e:
                st.error(f"خطأ غير متوقع: {e}")
                import traceback
                st.code(traceback.format_exc())

        if st.button("تم — العودة للنظام", type="primary", key="close_seed", use_container_width=True):
            st.session_state.run_seed = False
            st.rerun()
        st.stop()

    # ========================================================
    # توجيه الصفحات
    # ========================================================
    page = st.session_state.current_page

    def show_if_permitted(module, show_func):
        if can_access(module):
            show_func()
        else:
            st.markdown(f"""
            <div class="permission-denied">
                <div class="permission-icon"><span class="material-icon">lock</span></div>
                <h2>غير مصرح</h2>
                <p>ليس لديك صلاحية للوصول إلى وحدة "{safe_html(module)}".</p>
            </div>
            """, unsafe_allow_html=True)

    # ========================================================
    # الصفحات
    # ========================================================
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
    elif page == "التقارير المالية XBRL": show_if_permitted("التقارير المالية XBRL", pdf_show)
    elif page == "الصندوق": show_if_permitted("الصندوق", cash_show)
