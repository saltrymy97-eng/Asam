
# ui/auth_ui.py
# Hukma ERP — Premium Authentication UI v3.0
# تحسين ثبات الألوان في Edge، وتحسين الواجهة مع الحفاظ على منطق المصادقة.

import streamlit as st

from database import init_db
from services.auth_service import (
    verify_user,
    change_password,
    logout_session,
)


# ============================================================
# لوحة الألوان
# ============================================================

T = "#F8FAFC"
S = "#A8A5C3"
PR = "#7C3AED"
BL = "#2563EB"
BG_CORE = "#070714"

PURPLE_LIGHT = "#C4B5FD"
PURPLE_MID = "#A78BFA"
GOLD = "#E8C766"


# ============================================================
# محاولة الحصول على IP العميل
# ============================================================

def _get_client_ip():
    """
    محاولة الحصول على IP العميل.

    في التشغيل المحلي تُعاد كلمة "محلي".
    في بيئة الإنتاج قد يتوفر عنوان العميل ضمن ترويسات الطلب.
    """
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers

            for header in (
                "X-Forwarded-For",
                "X-Real-IP",
                "Remote-Addr",
            ):
                value = headers.get(header)

                if value:
                    return value.split(",")[0].strip()

    except Exception:
        pass

    return "محلي"


# ============================================================
# CSS — تصميم فاخر مع تقليل الاعتماد على خصائص الرسم الحساسة
# ============================================================

def apply_ultra_premium_css():
    css_code = f"""
<style>
@import url(
    'https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;600;700;800;900&display=swap'
);


/* ==========================================================
   1. الخطوط الأساسية
   لا نفرض Tajawal على جميع العناصر حتى لا نفسد خطوط الأيقونات.
   ========================================================== */

.stApp,
.stApp input,
.stApp textarea,
.stApp button,
.stApp label,
.stApp p,
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp li,
.stApp [data-testid="stMarkdownContainer"] {{
    font-family: "Tajawal", "Segoe UI", Tahoma, Arial, sans-serif;
}}

.stApp {{
    color: {T};
    background:
        radial-gradient(
            ellipse at 88% 8%,
            rgba(124, 58, 237, 0.20) 0%,
            transparent 36%
        ),
        radial-gradient(
            ellipse at 10% 88%,
            rgba(37, 99, 235, 0.13) 0%,
            transparent 34%
        ),
        linear-gradient(
            145deg,
            #11102A 0%,
            #090B18 48%,
            {BG_CORE} 100%
        ) !important;
    background-attachment: fixed !important;
    -webkit-text-size-adjust: 100%;
}}

[data-testid="stAppViewContainer"] {{
    background: transparent !important;
}}

[data-testid="stHeader"] {{
    background: transparent !important;
}}

[data-testid="stToolbar"] {{
    background: transparent !important;
}}

.main .block-container {{
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}}


/* ==========================================================
   2. إزالة المساحات الفارغة غير الضرورية
   ========================================================== */

div[data-testid="stVerticalBlock"] > div:empty,
div[data-testid="stHorizontalBlock"] > div:empty,
div[data-testid="element-container"]:empty,
div[data-testid="stMarkdownContainer"]:empty {{
    display: none;
}}


/* ==========================================================
   3. بطاقة الواجهة
   ========================================================== */

div[data-testid="stVerticalBlock"] > div > div
> div[data-testid="stVerticalBlock"] {{
    border-radius: 28px;
}}

[data-testid="stForm"] {{
    background:
        linear-gradient(
            145deg,
            rgba(22, 20, 47, 0.96),
            rgba(9, 12, 27, 0.98)
        ) !important;

    border: 1px solid rgba(196, 181, 253, 0.16) !important;
    border-top: 1px solid rgba(196, 181, 253, 0.35) !important;
    border-radius: 24px !important;

    padding: 1.5rem !important;

    box-shadow:
        0 24px 65px rgba(0, 0, 0, 0.32),
        inset 0 1px 0 rgba(255, 255, 255, 0.035) !important;
}}


/* ==========================================================
   4. حقول الإدخال
   ========================================================== */

div[data-baseweb="input"] {{
    background: rgba(5, 8, 22, 0.82) !important;

    border: 1px solid rgba(196, 181, 253, 0.18) !important;
    border-radius: 14px !important;

    box-shadow: inset 0 2px 7px rgba(0, 0, 0, 0.18);

    transition:
        border-color 160ms ease,
        background-color 160ms ease,
        box-shadow 160ms ease;
}}

div[data-baseweb="input"]:hover {{
    border-color: rgba(196, 181, 253, 0.38) !important;
}}

div[data-baseweb="input"]:focus-within {{
    background: rgba(10, 8, 29, 0.98) !important;

    border-color: {PURPLE_MID} !important;

    box-shadow:
        0 0 0 3px rgba(139, 92, 246, 0.13),
        0 0 18px rgba(124, 58, 237, 0.13) !important;
}}

div[data-baseweb="input"] input {{
    background: transparent !important;
    color: {T} !important;

    font-size: 1rem !important;
    font-weight: 600 !important;
    caret-color: {PURPLE_LIGHT};
}}

div[data-baseweb="input"] input::placeholder {{
    color: #8986A6 !important;
    opacity: 1 !important;
}}

.stTextInput label,
.stTextInput label p {{
    color: #D5D1E8 !important;
    font-size: 0.98rem !important;
    font-weight: 700 !important;
    margin-bottom: 6px;
}}


/* ==========================================================
   5. الأزرار الرئيسية والثانوية
   ========================================================== */

.stButton > button,
.stFormSubmitButton > button,
button[kind="primary"],
button[kind="secondary"] {{
    width: 100%;
    min-height: 48px;

    border-radius: 14px !important;

    font-family: "Tajawal", "Segoe UI", Tahoma, Arial, sans-serif;
    font-weight: 800 !important;
    font-size: 1rem !important;

    transition:
        background-color 160ms ease,
        border-color 160ms ease,
        box-shadow 160ms ease,
        transform 160ms ease;
}}

button[kind="primary"] {{
    color: #FFFFFF !important;

    background: linear-gradient(
        120deg,
        #7C3AED 0%,
        #6D28D9 48%,
        #4F46E5 100%
    ) !important;

    border: 1px solid rgba(196, 181, 253, 0.42) !important;

    box-shadow:
        0 8px 22px rgba(109, 40, 217, 0.24),
        inset 0 1px 0 rgba(255, 255, 255, 0.15) !important;
}}

button[kind="primary"]:hover {{
    background: linear-gradient(
        120deg,
        #8B5CF6 0%,
        #7C3AED 50%,
        #6366F1 100%
    ) !important;

    border-color: rgba(221, 214, 254, 0.7) !important;

    box-shadow:
        0 10px 26px rgba(109, 40, 217, 0.30),
        inset 0 1px 0 rgba(255, 255, 255, 0.20) !important;
}}

button[kind="secondary"] {{
    color: #EAE7F8 !important;

    background: rgba(255, 255, 255, 0.035) !important;

    border: 1px solid rgba(196, 181, 253, 0.18) !important;

    box-shadow: none !important;
}}

button[kind="secondary"]:hover {{
    background: rgba(139, 92, 246, 0.10) !important;
    border-color: rgba(196, 181, 253, 0.42) !important;
}}

button:focus-visible {{
    outline: 2px solid {PURPLE_LIGHT} !important;
    outline-offset: 3px;
}}

button:disabled {{
    opacity: 0.55;
    cursor: not-allowed;
}}


/* ==========================================================
   6. الجرم البنفسجي
   توهج ثابت وحركة بسيطة دون فرض GPU أو تحريك الظلال باستمرار.
   ========================================================== */

@keyframes hukmaFloat {{
    0%, 100% {{
        transform: translateY(0);
    }}

    50% {{
        transform: translateY(-9px);
    }}
}}

@keyframes hukmaGleam {{
    0% {{
        transform: rotate(0deg);
    }}

    100% {{
        transform: rotate(360deg);
    }}
}}

.hukma-orb {{
    position: relative;

    width: 210px;
    height: 210px;

    margin: 0 auto 2rem auto;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 50%;

    background:
        radial-gradient(
            circle at 32% 25%,
            rgba(196, 181, 253, 0.22) 0%,
            rgba(124, 58, 237, 0.14) 26%,
            rgba(37, 45, 100, 0.24) 58%,
            rgba(8, 10, 26, 0.94) 100%
        );

    border: 1px solid rgba(196, 181, 253, 0.58);
    border-top: 3px solid rgba(255, 255, 255, 0.78);

    box-shadow:
        0 0 28px rgba(124, 58, 237, 0.22),
        0 0 60px rgba(124, 58, 237, 0.11),
        inset 0 0 28px rgba(124, 58, 237, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.14);

    overflow: hidden;
    isolation: isolate;

    animation: hukmaFloat 5s ease-in-out infinite;
}}

.hukma-orb::before {{
    content: "";

    position: absolute;
    inset: -50%;

    border-radius: 50%;

    background: conic-gradient(
        from 0deg,
        transparent 0deg,
        rgba(255, 255, 255, 0.02) 65deg,
        rgba(221, 214, 254, 0.23) 100deg,
        transparent 145deg,
        transparent 245deg,
        rgba(167, 139, 250, 0.12) 290deg,
        transparent 330deg
    );

    animation: hukmaGleam 18s linear infinite;

    pointer-events: none;
    z-index: 0;
}}

.hukma-orb::after {{
    content: "";

    position: absolute;

    top: 19%;
    left: 24%;

    width: 7px;
    height: 7px;

    border-radius: 50%;

    background: #FFFFFF;

    box-shadow:
        0 0 8px rgba(255, 255, 255, 0.75),
        0 0 18px rgba(196, 181, 253, 0.48);

    opacity: 0.75;

    pointer-events: none;
    z-index: 1;
}}


/* ==========================================================
   7. عنوان «حوكمة»
   اللون الأساسي معتم: لا يعتمد على background-clip:text.
   هذا يتجنب مشكلة ظهور النص بالأسود عند فشل رسم التدرج.
   ========================================================== */

.hukma-text {{
    position: relative;
    z-index: 2;

    display: inline-block;

    font-family: "Tajawal", "Segoe UI", Tahoma, Arial, sans-serif;

    font-size: clamp(2.7rem, 6vw, 3.8rem);
    font-weight: 900;
    line-height: 1.3;
    letter-spacing: 1px;

    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;

    background: none !important;
    background-image: none !important;
    background-clip: border-box !important;
    -webkit-background-clip: border-box !important;

    -webkit-text-stroke: 0 transparent;

    text-shadow:
        0 2px 0 rgba(91, 33, 182, 0.90),
        0 0 12px rgba(196, 181, 253, 0.32),
        0 5px 20px rgba(0, 0, 0, 0.35);

    filter: none !important;
    opacity: 1 !important;
}}


/* ==========================================================
   8. النصوص أسفل العنوان
   ========================================================== */

.hukma-tagline {{
    color: {S};

    margin-top: 1.2rem;

    font-size: clamp(1rem, 2.5vw, 1.3rem);
    font-weight: 700;
    line-height: 1.9;
    text-align: center;
}}

.hukma-accent-purple {{
    color: {PURPLE_LIGHT};
    font-weight: 900;
}}

.hukma-accent-blue {{
    color: #93C5FD;
    font-weight: 900;
}}

.hukma-divider {{
    width: min(250px, 70%);
    height: 2px;

    margin: 1.2rem auto 0 auto;

    background: linear-gradient(
        90deg,
        transparent,
        #A78BFA,
        #60A5FA,
        transparent
    );

    opacity: 0.8;
}}


/* ==========================================================
   9. توقيع المطور
   لون ذهبي ثابت لتجنب مشكلة التدرج في النص.
   ========================================================== */

.dev-signature {{
    position: relative;
    z-index: 2;

    margin-top: 3.5rem;

    text-align: center;

    color: rgba(226, 223, 244, 0.60);

    font-size: 0.95rem;
    font-weight: 500;
    line-height: 1.9;
    letter-spacing: 0.3px;
}}

.dev-name {{
    display: inline-block;

    color: {GOLD} !important;
    -webkit-text-fill-color: {GOLD} !important;

    background: none !important;
    background-image: none !important;
    -webkit-background-clip: border-box !important;
    background-clip: border-box !important;

    font-size: 1.1rem;
    font-weight: 900;

    text-shadow: 0 0 12px rgba(232, 199, 102, 0.16);
}}


/* ==========================================================
   10. التنبيهات
   ========================================================== */

[data-testid="stAlert"] {{
    border-radius: 12px;
}}

[data-testid="stAlert"] p {{
    line-height: 1.8;
}}


/* ==========================================================
   11. الشاشات الصغيرة
   ========================================================== */

@media (max-width: 700px) {{
    .main .block-container {{
        padding: 1.2rem 0.85rem 2rem;
    }}

    .hukma-orb {{
        width: 170px;
        height: 170px;
        margin-bottom: 1.6rem;
    }}

    .hukma-text {{
        font-size: 2.65rem;
        letter-spacing: 0;
    }}

    .dev-signature {{
        margin-top: 2.5rem;
    }}
}}


/* ==========================================================
   12. احترام إعداد تقليل الحركة
   ========================================================== */

@media (prefers-reduced-motion: reduce) {{
    .hukma-orb,
    .hukma-orb::before {{
        animation: none !important;
    }}

    *,
    *::before,
    *::after {{
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }}
}}

</style>
"""

    st.markdown(css_code, unsafe_allow_html=True)


# ============================================================
# الهيدر
# ============================================================

def render_premium_header(is_change_password=False):
    """عرض هوية حكمة في صفحة الدخول أو تغيير كلمة المرور."""

    if not is_change_password:
        html = f"""
<div style="
    text-align:center;
    margin-bottom:2.5rem;
    margin-top:0.5rem;
">
    <div class="hukma-orb">
        <span class="hukma-text">حوكمة</span>
    </div>

    <div class="hukma-tagline">
        إدارة
        <span class="hukma-accent-purple">ذكية</span>
        ..
        قرارات
        <span class="hukma-accent-blue">واثقة</span>
    </div>

    <div class="hukma-divider"></div>
</div>
"""

    else:
        html = f"""
<div style="
    text-align:center;
    margin-bottom:2.5rem;
    margin-top:0.5rem;
">
    <div
        class="hukma-orb"
        style="width:150px;height:150px;"
    >
        <span style="
            position:relative;
            z-index:2;
            font-size:3.6rem;
            line-height:1;
        ">🛡️</span>
    </div>

    <h2 style="
        color:{T};
        margin:0;
        font-weight:900;
        font-size:clamp(1.8rem, 5vw, 2.5rem);
    ">
        تأمين الهوية الرقمية
    </h2>

    <p style="
        color:{S};
        margin-top:1rem;
        font-size:1.05rem;
        line-height:1.9;
    ">
        يرجى تحديث رمز الحماية الخاص بك للمتابعة بأمان
    </p>

    <div class="hukma-divider"></div>
</div>
"""

    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# توقيع المطور
# ============================================================

def _render_dev_signature(change_password=False):
    if change_password:
        html = """
<div class="dev-signature">
    <div>
        تطوير:
        <span class="dev-name">سالم التريمي</span>
    </div>
</div>
"""
    else:
        html = """
<div class="dev-signature">
    حكمة ERP • نظام محاسبي متكامل
    <br>
    <div style="margin-top:8px;">
        تطوير:
        <span class="dev-name">سالم التريمي</span>
    </div>
</div>
"""

    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# نموذج تسجيل الدخول
# ============================================================

def login_form():
    render_premium_header(is_change_password=False)

    spacer_left, main_col, spacer_right = st.columns([0.5, 3, 0.5])

    with main_col:
        with st.container():
            username = st.text_input(
                "👤 معرف المستخدم (ID)",
                placeholder="أدخل اسم المستخدم",
                key="login_user",
            )

            st.markdown(
                "<div style='height:12px'></div>",
                unsafe_allow_html=True,
            )

            password = st.text_input(
                "🔒 رمز المرور السري",
                type="password",
                placeholder="أدخل رمز المرور",
                key="login_pass",
            )

            st.markdown(
                "<div style='height:25px'></div>",
                unsafe_allow_html=True,
            )

            login_btn = st.button(
                "🚀 مصادقة والدخول",
                use_container_width=True,
                type="primary",
            )

            st.markdown(
                "<div style='height:8px'></div>",
                unsafe_allow_html=True,
            )

            if st.button(
                "🔑 تغيير الرمز",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.show_password_change = True
                st.rerun()

            if login_btn:
                if not username.strip() or not password:
                    st.warning(
                        "⚠️ يرجى إدخال اسم المستخدم وكلمة المرور."
                    )
                else:
                    user = verify_user(
                        username.strip(),
                        password,
                        ip_address=_get_client_ip(),
                    )

                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error(
                            "❌ فشلت المصادقة. "
                            "يرجى مراجعة البيانات المدخلة."
                        )

    _render_dev_signature(change_password=False)


# ============================================================
# نموذج تغيير كلمة المرور
# ============================================================

def password_change_form():
    render_premium_header(is_change_password=True)

    spacer_left, main_col, spacer_right = st.columns([0.5, 3, 0.5])

    with main_col:
        with st.container():
            username = st.text_input(
                "👤 اسم المستخدم",
                placeholder="أدخل اسم المستخدم الخاص بك",
                key="change_user",
            )

            st.markdown(
                "<div style='height:8px'></div>",
                unsafe_allow_html=True,
            )

            old_password = st.text_input(
                "🔓 رمز المرور السري الحالي",
                type="password",
                placeholder="الرمز الحالي",
                key="change_old",
            )

            st.markdown(
                "<div style='height:8px'></div>",
                unsafe_allow_html=True,
            )

            new_password = st.text_input(
                "✨ رمز المرور السري الجديد",
                type="password",
                placeholder="الرمز الجديد",
                key="change_new",
            )

            st.markdown(
                "<div style='height:8px'></div>",
                unsafe_allow_html=True,
            )

            confirm_password = st.text_input(
                "✅ تأكيد الرمز الجديد",
                type="password",
                placeholder="أعد كتابة الرمز الجديد",
                key="change_confirm",
            )

            st.markdown(
                "<div style='height:22px'></div>",
                unsafe_allow_html=True,
            )

            if st.button(
                "💾 حفظ البيانات وتحديث",
                use_container_width=True,
                type="primary",
            ):
                if (
                    not username.strip()
                    or not old_password
                    or not new_password
                    or not confirm_password
                ):
                    st.warning("⚠️ جميع الحقول مطلوبة.")

                elif new_password != confirm_password:
                    st.error(
                        "❌ رمز المرور الجديد وتأكيده غير متطابقين."
                    )

                elif len(new_password) < 4:
                    st.error(
                        "⚠️ رمز المرور ضعيف؛ يجب ألا يقل عن 4 خانات."
                    )

                else:
                    current_user = (
                        st.session_state.user.get("username")
                        if st.session_state.get("user")
                        else username.strip()
                    )

                    success, message = change_password(
                        username.strip(),
                        old_password,
                        new_password,
                        changed_by=current_user,
                    )

                    if success:
                        st.success(f"✨ {message}")
                        st.session_state.show_password_change = False
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

            st.markdown(
                "<div style='height:8px'></div>",
                unsafe_allow_html=True,
            )

            if st.button(
                "↩️ تراجع",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.show_password_change = False
                st.rerun()

    _render_dev_signature(change_password=True)


# ============================================================
# نقطة الدخول الرئيسية للواجهة
# ============================================================

def show():
    init_db()

    if "show_password_change" not in st.session_state:
        st.session_state.show_password_change = False

    apply_ultra_premium_css()

    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
