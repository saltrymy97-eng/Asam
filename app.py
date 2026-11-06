# -*- coding: utf-8 -*-

import html
import json
import os
import sys
import traceback
import uuid

from pathlib import Path

from datetime import datetime

import streamlit as st

# ============================================================
# 1. إعداد الصفحة
# ============================================================

st.set_page_config(
    page_title="حوكمة ERP",
    page_icon="icon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 2. بروتوكول الجاهزية Readiness Protocol
# ============================================================

# يجب أن تتطابق هذه القيم مع app_desktop.py وstreamlit_runner.py.
READINESS_PROTOCOL_ID = "1111"
READINESS_PROTOCOL_VERSION = 1
READINESS_FILENAME = "readiness.json"


def _readiness_log(message):
    """Write readiness diagnostics to Streamlit stderr and startup.log."""
    text = "[APP.PY READINESS] {}".format(message)
    print(text, file=sys.stderr, flush=True)
    try:
        root = Path(os.getenv("LOCALAPPDATA") or Path.home())
        logs_dir = root / "HokamaERP" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        with (logs_dir / "startup.log").open("a", encoding="utf-8") as log:
            log.write(datetime.now().astimezone().isoformat() + " | " + text + "\n")
    except Exception:
        pass


def get_received_protocol_id():
    """Return the protocol ID exactly as received from the runner environment."""
    return os.environ.get("HOKAMA_PROTOCOL_ID", "MISSING")


def get_received_protocol_version():
    """Read the canonical environment representation of protocol version 1."""
    raw_version = os.environ.get("HOKAMA_READINESS_PROTOCOL", "MISSING")
    # Environment variables are text. Accept only the canonical representation;
    # preserve unexpected values so that the launcher can diagnose mismatches.
    if raw_version == "1":
        return 1
    return raw_version


def get_readiness_file():
    base = Path(os.getenv("LOCALAPPDATA") or Path.home())
    run_dir = base / "HokamaERP" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / READINESS_FILENAME


def write_readiness_signal(status, error_msg=None):
    """Atomically write the single, fixed readiness JSON record.

    The protocol values actually received from streamlit_runner.py are written
    unchanged (apart from the required text-to-int decoding of the canonical
    environment value "1"). This lets the desktop launcher report mismatches.
    """
    if status not in ("ready", "error"):
        _readiness_log("Rejected unsupported status={!r}".format(status))
        return False

    received_id = get_received_protocol_id()
    received_version = get_received_protocol_version()
    target_file = get_readiness_file()

    # Streamlit reruns app.py after interactions. Do not rewrite an identical
    # ready record for the same process on every rerun.
    if status == "ready" and target_file.is_file():
        try:
            with target_file.open("r", encoding="utf-8") as file:
                previous = json.load(file)
            if (
                isinstance(previous, dict)
                and previous.get("protocol_id") == received_id
                and previous.get("protocol_version") == received_version
                and previous.get("status") == "ready"
                and type(previous.get("pid")) is int
                and previous.get("pid") == os.getpid()
                and previous.get("source") == "app.py"
                and previous.get("error") is None
            ):
                return True
        except Exception:
            # A malformed or stale record is replaced atomically below.
            pass

    temp_file = target_file.with_name(
        "{}.{}.{}.tmp".format(target_file.stem, os.getpid(), uuid.uuid4().hex)
    )

    data = {
        "protocol_id": received_id,
        "protocol_version": received_version,
        "status": status,
        "pid": os.getpid(),
        "source": "app.py",
        "error": str(error_msg) if error_msg else None,
    }

    try:
        _readiness_log(
            "Writing signal | expected_id={!r} | received_id={!r} | "
            "expected_version={!r} | received_version={!r} | "
            "status={!r} | file={!r} | pid={}".format(
                READINESS_PROTOCOL_ID,
                received_id,
                READINESS_PROTOCOL_VERSION,
                received_version,
                status,
                str(target_file),
                os.getpid(),
            )
        )

        with temp_file.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_file, target_file)
        _readiness_log(
            "Signal written successfully | protocol_id={!r} | status={!r} | pid={}".format(
                received_id, status, os.getpid()
            )
        )
        return True

    except Exception:
        error_text = traceback.format_exc()
        _readiness_log(
            "FAILED to write readiness file {!r}:\n{}".format(
                str(target_file), error_text
            )
        )
        try:
            if temp_file.exists():
                temp_file.unlink()
        except Exception:
            pass
        return False


# Validate the environment at the beginning of the app run. If it is wrong,
# write an error record containing the received values for immediate diagnosis.
_received_protocol_id = get_received_protocol_id()
_received_protocol_version = get_received_protocol_version()

if (
    _received_protocol_id != READINESS_PROTOCOL_ID
    or _received_protocol_version != READINESS_PROTOCOL_VERSION
):
    _protocol_error = (
        "عدم تطابق بروتوكول التشغيل. "
        "المتوقع ID={!r}, VERSION={!r}; "
        "المستلم ID={!r}, VERSION={!r}."
    ).format(
        READINESS_PROTOCOL_ID,
        READINESS_PROTOCOL_VERSION,
        _received_protocol_id,
        _received_protocol_version,
    )
    _readiness_log(_protocol_error)
    write_readiness_signal("error", _protocol_error)
    st.error(_protocol_error)
    st.stop()
else:
    if not get_readiness_file().exists():
        _readiness_log(
            "Protocol received correctly | protocol_id={!r} | version={!r}".format(
                _received_protocol_id, _received_protocol_version
            )
        )

# ============================================================
# 3. عرض أخطاء بدء التشغيل
# ============================================================

def show_startup_error(title, error):
    st.markdown(
        """
        <div class="startup-error">
            <div style="font-size: 2rem;">⚠️</div>
            <h2>تعذر تشغيل النظام</h2>
            <p>حدث خطأ أثناء تجهيز التطبيق.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.error(title)
    st.code(str(error), language="text")
    with st.expander("تفاصيل الخطأ الكاملة"):
        st.code(str(error), language="python")


# ============================================================
# 4. استيراد قاعدة البيانات
# ============================================================

try:
    import database
except Exception:
    database_error = traceback.format_exc()
    write_readiness_signal("error", database_error)
    show_startup_error(
        "فشل استيراد أو تهيئة قاعدة البيانات.",
        database_error,
    )
    st.stop()

# ============================================================
# 5. التهيئة الأساسية
# ============================================================

@st.cache_resource(show_spinner=False)
def perform_initial_setup():
    try:
        from services.currency_service import create_default_currencies

        create_default_currencies()

        from services.roles_service import seed_default_roles

        seed_default_roles()

        return True, None
    except Exception:
        return False, traceback.format_exc()


# ============================================================
# 6. تنفيذ التهيئة
# ============================================================

with st.spinner("جاري تجهيز قاعدة البيانات وخدمات النظام..."):
    setup_success, setup_error = perform_initial_setup()

if not setup_success:
    write_readiness_signal("error", setup_error)
    show_startup_error(
        "فشلت تهيئة خدمات النظام.",
        setup_error,
    )
    st.stop()

# ============================================================
# 7. استيراد جميع وحدات النظام
# ============================================================

try:
    from services.auth_service import logout_session
    from services.roles_service import check_permission, get_allowed_modules
    from ui.auth_ui import show as auth_show

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

except Exception:
    import_error = traceback.format_exc()
    write_readiness_signal("error", import_error)
    show_startup_error(
        "فشل استيراد إحدى وحدات النظام. تحقق من ملفات مجلد ui.",
        import_error,
    )
    st.stop()

# ============================================================
# 8. إعلان جاهزية التهيئة والاستيرادات
# ============================================================

if not write_readiness_signal("ready"):
    readiness_error = "تعذرت كتابة إشارة الجاهزية readiness.json. راجع startup.log."
    _readiness_log(readiness_error)
    st.error(readiness_error)
    st.stop()

# ============================================================
# 9. أدوات مساعدة
# ============================================================

def safe_html(value, default=""):
    if value is None:
        value = default
    return html.escape(str(value))


# ============================================================
# 10. التصميم العام
# ============================================================

st.markdown(
    """
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 11. تهيئة الجلسة
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
# 12. أدوات الصلاحيات والتنقل
# ============================================================

def nav_button(label, page, key, icon, module=None):
    if module and not can_access(module):
        return

    is_active = st.session_state.current_page == page
    if st.button(
        label,
        key=key,
        icon=icon,
        type="primary" if is_active else "secondary",
        use_container_width=True,
    ):
        st.session_state.current_page = page
        st.rerun()


# ============================================================
# 13. شاشة تسجيل الدخول
# ============================================================

if not st.session_state.logged_in:
    try:
        auth_show()
    except Exception:
        st.error("حدث خطأ أثناء عرض شاشة تسجيل الدخول.")
        st.code(traceback.format_exc(), language="python")

else:
    user_data = st.session_state.get("user") or {}
    username = user_data.get("username", "")

    if username == "admin":
        allowed_modules = None
    else:
        try:
            allowed_modules = get_allowed_modules(username)
        except Exception:
            st.error("تعذر تحميل صلاحيات المستخدم.")
            st.code(traceback.format_exc(), language="python")
            st.stop()

    def can_access(module):
        if username == "admin":
            return True
        return module in allowed_modules if allowed_modules else False

    # ========================================================
    # 14. القائمة الجانبية
    # ========================================================

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div>apartment</div>
                <h2>حوكمة ERP</h2>
                <p>إدارة ذكية .. قرارات واثقة</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        display_name = (
            user_data.get("full_name")
            or user_data.get("username")
            or "مستخدم النظام"
        )

        st.markdown(
            """
            <div class="current-user">
                <div>المستخدم الحالي</div>
                <div>account_circle&nbsp;&nbsp; {}</div>
            </div>
            """.format(safe_html(display_name)),
            unsafe_allow_html=True,
        )

        st.divider()

        st.markdown("<div>home&nbsp;&nbsp; الرئيسية</div>", unsafe_allow_html=True)
        nav_button("لوحة المعلومات", "لوحة المعلومات", "dashboard", ":material/dashboard:")

        st.markdown("<div>inventory_2&nbsp;&nbsp; العمليات</div>", unsafe_allow_html=True)
        nav_button("مبيعات", "المبيعات", "sales", ":material/shopping_cart:", "المبيعات")
        nav_button("مشتريات", "المشتريات", "purchases", ":material/receipt_long:", "المشتريات")
        nav_button("مرتجعات", "مرتجعات البضاعة", "returns", ":material/assignment_return:", "مرتجعات البضاعة")
        nav_button("سندات قبض/صرف", "سندات القبض والصرف", "receipts", ":material/payments:", "سندات القبض والصرف")
        nav_button("مخزون", "المخزون", "inventory", ":material/inventory:", "المخزون")
        nav_button("تسويات مخزنية", "التسويات المخزنية", "adjustments", ":material/rule:", "التسويات المخزنية")
        nav_button("مصروفات", "المصروفات", "expenses", ":material/money_off:", "المصروفات")
        nav_button("CRM", "إدارة العملاء", "crm", ":material/people:", "إدارة العملاء")

        st.markdown("<div>account_balance&nbsp;&nbsp; المحاسبة والمالية</div>", unsafe_allow_html=True)
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

        st.markdown("<div>groups&nbsp;&nbsp; إدارة الأعمال</div>", unsafe_allow_html=True)
        nav_button("موارد بشرية", "الموارد البشرية", "hr", ":material/badge:", "الموارد البشرية")
        nav_button("رواتب", "كشف الرواتب", "payroll", ":material/payments:", "كشف الرواتب")
        nav_button("أصول ثابتة", "الأصول الثابتة", "assets", ":material/foundation:", "الأصول الثابتة")
        nav_button("مرفقات", "المرفقات", "attachments", ":material/attach_file:", "المرفقات")

        st.markdown("<div>admin_panel_settings&nbsp;&nbsp; النظام والأمان</div>", unsafe_allow_html=True)
        nav_button("صلاحيات", "الصلاحيات", "roles", ":material/security:", "الصلاحيات")
        nav_button("سجل تدقيق", "سجل التدقيق", "audit", ":material/history:", "سجل التدقيق")
        nav_button("نسخ احتياطي", "نسخ احتياطي", "backup", ":material/backup:", "نسخ احتياطي")

        if username == "admin":
            st.markdown("---")
            st.markdown("<div>code&nbsp;&nbsp; أدوات المطور</div>", unsafe_allow_html=True)
            seed_clicked = st.button(
                "حقن بيانات تجريبية",
                key="seed_data_btn",
                help="حذف كل البيانات ثم حقن بيانات تجريبية",
                type="primary",
                icon=":material/eco:",
                use_container_width=True,
            )
            if seed_clicked:
                st.session_state.run_seed = True
                st.rerun()

        st.markdown("<div>psychology&nbsp;&nbsp; الذكاء الاصطناعي</div>", unsafe_allow_html=True)
        nav_button("المساعد الذكي", "المساعد الذكي", "ai", ":material/psychology:", "المساعد الذكي")

        st.divider()
        st.markdown('<div class="logout-area">', unsafe_allow_html=True)
        logout_clicked = st.button(
            "تسجيل الخروج",
            key="logout",
            help="تسجيل الخروج من النظام",
            icon=":material/logout:",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if logout_clicked:
            try:
                current_user = st.session_state.get("user") or {}
                logout_session(
                    username=current_user.get("username"),
                    user_id=current_user.get("id"),
                )
                st.rerun()
            except Exception:
                st.error("حدث خطأ أثناء تسجيل الخروج.")
                st.code(traceback.format_exc(), language="python")

    # ========================================================
    # 15. تنفيذ الحقن التجريبي
    # ========================================================

    if st.session_state.get("run_seed", False):
        try:
            from services.seed_service import run_full_seed

            st.markdown(
                """
                <div class="seed-header">
                    <div>database</div>
                    <h2>حقن البيانات التجريبية</h2>
                    <p>جاري تجهيز النظام ببيانات واقعية...</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.spinner("جاري الحقن... قد يستغرق دقيقة إلى دقيقتين"):
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
                st.error("فشل الحقن: {}".format(result.get("error", "خطأ غير معروف")))

        except Exception:
            st.error("حدث خطأ أثناء تنفيذ الحقن التجريبي.")
            st.code(traceback.format_exc(), language="python")

        if st.button(
            "تم — العودة للنظام",
            type="primary",
            key="close_seed",
            use_container_width=True,
        ):
            st.session_state.run_seed = False
            st.rerun()

        st.stop()

    # ========================================================
    # 16. توجيه الصفحات
    # ========================================================

    page = st.session_state.current_page

    def show_if_permitted(module, show_func):
        if can_access(module):
            try:
                show_func()
            except Exception:
                st.error("حدث خطأ أثناء فتح وحدة: {}".format(module))
                st.code(traceback.format_exc(), language="python")
        else:
            st.markdown(
                """
                <div class="permission-denied">
                    <div>lock</div>
                    <h2>غير مصرح</h2>
                    <p>ليس لديك صلاحية للوصول إلى وحدة "{}".</p>
                </div>
                """.format(safe_html(module)),
                unsafe_allow_html=True,
            )

    # ========================================================
    # 17. الصفحات
    # ========================================================

    try:
        if page == "لوحة المعلومات":
            dashboard_show()
        elif page == "المخزون":
            show_if_permitted("المخزون", inventory_show)
        elif page == "التسويات المخزنية":
            show_if_permitted("التسويات المخزنية", inventory_adjustment_show)
        elif page == "المبيعات":
            show_if_permitted("المبيعات", sales_show)
        elif page == "المشتريات":
            show_if_permitted("المشتريات", purchases_show)
        elif page == "مرتجعات البضاعة":
            show_if_permitted("مرتجعات البضاعة", returns_show)
        elif page == "سندات القبض والصرف":
            show_if_permitted("سندات القبض والصرف", receipts_show)
        elif page == "المصروفات":
            show_if_permitted("المصروفات", expenses_show)
        elif page == "الأرصدة الافتتاحية":
            show_if_permitted("الأرصدة الافتتاحية", opening_show)
        elif page == "تقييم العملات":
            show_if_permitted("تقييم العملات", revaluation_show)
        elif page == "الحسابات":
            show_if_permitted("الحسابات", accounting_show)
        elif page == "الموارد البشرية":
            show_if_permitted("الموارد البشرية", hr_show)
        elif page == "إدارة العملاء":
            show_if_permitted("إدارة العملاء", crm_show)
        elif page == "الأصول الثابتة":
            show_if_permitted("الأصول الثابتة", assets_show)
        elif page == "شجرة الحسابات":
            show_if_permitted("شجرة الحسابات", chart_show)
        elif page == "القوائم المالية":
            show_if_permitted("القوائم المالية", financial_show)
        elif page == "العملات":
            show_if_permitted("العملات", currency_show)
        elif page == "التعاملات البنكية":
            show_if_permitted("التعاملات البنكية", bank_show)
        elif page == "مراكز التكلفة":
            show_if_permitted("مراكز التكلفة", cost_center_show)
        elif page == "المرفقات":
            show_if_permitted("المرفقات", attachment_show)
        elif page == "الصلاحيات":
            show_if_permitted("الصلاحيات", roles_show)
        elif page == "إغلاق الفترات":
            show_if_permitted("إغلاق الفترات", period_show)
        elif page == "إغلاق الحسابات":
            show_if_permitted("إغلاق الحسابات", closing_show)
        elif page == "FIFO المخزون":
            show_if_permitted("FIFO المخزون", fifo_show)
        elif page == "كشف الرواتب":
            show_if_permitted("كشف الرواتب", payroll_show)
        elif page == "الضريبة":
            show_if_permitted("الضريبة", vat_show)
        elif page == "المساعد الذكي":
            show_if_permitted("المساعد الذكي", ai_show)
        elif page == "سجل التدقيق":
            show_if_permitted("سجل التدقيق", audit_show)
        elif page == "نسخ احتياطي":
            show_if_permitted("نسخ احتياطي", backup_show)
        elif page == "التقارير المالية XBRL":
            show_if_permitted("التقارير المالية XBRL", pdf_show)
        elif page == "الصندوق":
            show_if_permitted("الصندوق", cash_show)
        else:
            st.warning("الصفحة المطلوبة غير موجودة.")
            if st.button("العودة إلى لوحة المعلومات"):
                st.session_state.current_page = "لوحة المعلومات"
                st.rerun()

    except Exception:
        st.error("حدث خطأ غير متوقع أثناء عرض الصفحة.")
        st.code(traceback.format_exc(), language="python")
