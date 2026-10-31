# -*- coding: utf-8 -*-
"""
ui/ai_ui.py
=========================================================
حوكمة ERP | AI Enterprise Hub
واجهة المساعد المالي الذكي المحلي.

المحرك:
    llama.cpp

الاتصال:
    services.ai_service.query_groq
    (اسم توافق قديم، ويجب أن تنفذ الخدمة الاتصال المحلي)

ملاحظات:
    - لا يوجد اعتماد على Groq SDK.
    - لا يوجد مفتاح API سحابي.
    - لا يتم إرسال الصوت إلى خدمة خارجية.
    - لا يتم اعتماد القيود المحاسبية أو حفظها تلقائيًا.
=========================================================
"""

from __future__ import annotations

import inspect
import json
import re
import tempfile
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from services.ai_service import (
    create_ai_tables,
    query_groq,
    save_chat_history,
    get_chat_history,
    get_chat_sessions,
    get_comprehensive_data,
    get_inventory_data,
    get_employee_info,
    get_recent_entries,
    get_all_accounts,
    get_conn,
    get_financial_ratios,
    get_trend_analysis,
    get_business_snapshot,
    analyze_cost_center_performance,
    compare_cost_centers,
    predict_cost_center_expenses,
    get_cost_center_budget_analysis,
    generate_template_entry,
    get_available_operations,
    get_operation_description,
    is_mixed_operation,
    is_vat_operation,
    is_inventory_adjustment,
    is_salary_operation,
)

from services import cost_center_service as ccs


# =========================================================
# 1. إعدادات الواجهة
# =========================================================

LOCAL_MODEL_ID = "local-model"

# نقرأ اسم النموذج من الخدمة إن كان متاحًا.
# لا نضع هنا أسماء نماذج Groq أو أي نماذج سحابية.
try:
    from services import ai_service as _ai_service

    LOCAL_MODEL_ID = getattr(
        _ai_service,
        "LOCAL_AI_MODEL",
        LOCAL_MODEL_ID,
    )
except Exception:
    _ai_service = None


LOCAL_MODEL_LABEL = "llama.cpp | تشغيل محلي"

DEFAULT_MAX_TOKENS = 2048

CHAT_CATEGORY = "مساعد"

SYSTEM_ROLE = """
أنت المساعد المالي الذكي لنظام حوكمة ERP.

تعمل كمستشار مالي ومحاسبي وإداري محترف.

قواعد أساسية:
1. أجب باللغة العربية المهنية والواضحة.
2. اعتمد على البيانات التي يرسلها النظام إليك.
3. لا تخترع أرقامًا أو أرصدة أو أسماء حسابات.
4. ميّز بين البيانات الفعلية والتوقعات والتوصيات.
5. إذا كانت البيانات غير كافية، وضح ذلك صراحة.
6. عند تحليل الأرقام، اشرح طريقة الحساب والافتراضات.
7. لا تدّعِ تنفيذ أي قيد أو عملية داخل قاعدة البيانات.
8. لا تعتبر التوصيات بديلًا عن المراجعة المحاسبية.
9. استخدم Markdown والجداول عند الحاجة.
10. اجعل الإجابة منظمة بعناوين واضحة ونقاط مختصرة.
"""


# =========================================================
# 2. لوحة الألوان
# =========================================================

BG_COLOR = "#080C14"
BG_SECONDARY = "#0D1422"

CARD_BG = "#111A2B"
CARD_BG_LIGHT = "#172337"

CARD_BORDER = "rgba(212, 175, 55, 0.19)"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#A5B1C4"
TEXT_MUTED = "#718096"

GOLD = "#D4AF37"
GOLD_LIGHT = "#F0D98A"
GOLD_DARK = "#A98520"
GOLD_GLOW = "rgba(212, 175, 55, 0.22)"

ACCENT_PURPLE = "#9B8AFB"
ACCENT_GREEN = "#10B981"
ACCENT_RED = "#F87171"
ACCENT_BLUE = "#60A5FA"
ACCENT_CYAN = "#42D5CC"

BORDER_COLOR = "#253248"

SHADOW = "0 12px 35px rgba(0, 0, 0, .28)"


# =========================================================
# 3. CSS - التصميم الفاخر
# =========================================================

CUSTOM_CSS = f"""
<style>

/* -------------------------------------------------------
   أساسيات الصفحة
------------------------------------------------------- */

.stApp {{
    background:
        radial-gradient(
            circle at 85% 0%,
            rgba(155, 138, 251, .075),
            transparent 28%
        ),
        radial-gradient(
            circle at 5% 20%,
            rgba(212, 175, 55, .055),
            transparent 30%
        ),
        linear-gradient(
            145deg,
            {BG_COLOR},
            {BG_SECONDARY}
        );

    color: {TEXT_PRIMARY};
}}

html, body, [class*="css"] {{
    font-family:
        "Segoe UI",
        "Tahoma",
        "Arial",
        sans-serif !important;
}}

.main .block-container {{
    max-width: 1600px;
    padding-top: 1.7rem;
    padding-bottom: 3rem;
}}

/* لا نغيّر ترتيب عناصر Streamlit الأساسية */
[data-testid="stAppViewContainer"] {{
    background: transparent;
}}

/* -------------------------------------------------------
   الشريط الجانبي
------------------------------------------------------- */

section[data-testid="stSidebar"] {{
    background:
        linear-gradient(
            180deg,
            #10192B 0%,
            #0A101D 100%
        );

    border-left: 1px solid rgba(212,175,55,.14);
}}

section[data-testid="stSidebar"] > div {{
    padding-top: 1.4rem;
}}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
    direction: rtl;
    text-align: right;
}}

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {{
    color: {TEXT_SECONDARY} !important;
}}

/* -------------------------------------------------------
   الهيدر الرئيسي
------------------------------------------------------- */

.ai-hero {{
    position: relative;
    overflow: hidden;

    background:
        linear-gradient(
            115deg,
            #111A2B 0%,
            #1B2940 58%,
            #26354C 100%
        );

    border: 1px solid {CARD_BORDER};
    border-radius: 23px;

    padding: 29px 32px;
    margin-bottom: 23px;

    box-shadow: {SHADOW};

    direction: rtl;
    text-align: right;
}}

.ai-hero::before {{
    content: "";
    position: absolute;

    width: 280px;
    height: 280px;

    left: -85px;
    top: -145px;

    border-radius: 50%;

    border: 1px solid rgba(212,175,55,.22);
    background: rgba(212,175,55,.035);
}}

.ai-hero::after {{
    content: "";
    position: absolute;

    width: 180px;
    height: 180px;

    left: 70px;
    bottom: -130px;

    border-radius: 50%;
    background: rgba(155,138,251,.08);
}}

.ai-hero-badge {{
    display: inline-block;

    background: rgba(212,175,55,.10);
    color: {GOLD_LIGHT};

    border: 1px solid rgba(212,175,55,.25);
    border-radius: 9px;

    padding: 7px 13px;

    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;

    margin-bottom: 13px;
}}

.ai-hero-title {{
    font-size: 31px;
    font-weight: 900;

    color: {TEXT_PRIMARY};

    margin: 0 0 9px 0;
    line-height: 1.5;
}}

.ai-hero-subtitle {{
    color: {TEXT_SECONDARY};
    font-size: 14px;
    line-height: 2;
    max-width: 850px;
}}

.ai-hero-status {{
    display: inline-flex;
    align-items: center;
    gap: 8px;

    margin-top: 17px;
    padding: 7px 12px;

    color: #B9F3DB;
    background: rgba(16,185,129,.09);

    border: 1px solid rgba(16,185,129,.2);
    border-radius: 30px;

    font-size: 11px;
    font-weight: 700;
}}

.ai-status-dot {{
    width: 8px;
    height: 8px;

    display: inline-block;
    border-radius: 50%;

    background: {ACCENT_GREEN};
    box-shadow: 0 0 10px rgba(16,185,129,.7);
}}

/* -------------------------------------------------------
   بطاقات المؤشرات
------------------------------------------------------- */

.ai-metric {{
    background:
        linear-gradient(
            145deg,
            {CARD_BG_LIGHT},
            {CARD_BG}
        );

    border: 1px solid {CARD_BORDER};
    border-radius: 17px;

    padding: 19px 20px;

    min-height: 115px;

    box-shadow: 0 8px 25px rgba(0,0,0,.16);
    direction: rtl;
    text-align: right;
}}

.ai-metric-label {{
    font-size: 12px;
    color: {TEXT_SECONDARY};
    margin-bottom: 13px;
}}

.ai-metric-value {{
    font-size: 24px;
    font-weight: 900;
    color: {GOLD_LIGHT};
    direction: ltr;
    text-align: right;
}}

.ai-metric-note {{
    margin-top: 7px;
    color: {TEXT_MUTED};
    font-size: 11px;
}}

/* -------------------------------------------------------
   البطاقات العامة
------------------------------------------------------- */

.ai-card {{
    background:
        linear-gradient(
            145deg,
            rgba(23,35,55,.97),
            rgba(14,22,36,.98)
        );

    border: 1px solid {CARD_BORDER};
    border-radius: 17px;

    padding: 18px 20px;
    margin: 12px 0;

    box-shadow: 0 8px 25px rgba(0,0,0,.17);
    direction: rtl;
    text-align: right;
}}

.ai-card-title {{
    color: {GOLD_LIGHT};
    font-size: 15px;
    font-weight: 800;
    margin-bottom: 8px;
}}

.ai-card-caption {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
    line-height: 1.9;
}}

.ai-section-title {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 800;

    direction: rtl;
    text-align: right;

    margin: 12px 0 5px;
}}

.ai-section-subtitle {{
    color: {TEXT_MUTED};
    font-size: 12px;
    line-height: 1.9;

    direction: rtl;
    text-align: right;

    margin-bottom: 15px;
}}

.ai-divider {{
    height: 1px;
    border: 0;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(212,175,55,.3),
        transparent
    );

    margin: 18px 0;
}}

/* -------------------------------------------------------
   رسائل الحالة
------------------------------------------------------- */

.ai-info {{
    background: rgba(96,165,250,.08);
    border: 1px solid rgba(96,165,250,.2);
    border-right: 4px solid {ACCENT_BLUE};

    border-radius: 12px;
    padding: 13px 16px;

    color: #C7DDFA;
    font-size: 13px;
    line-height: 1.9;

    direction: rtl;
    text-align: right;

    margin: 10px 0;
}}

.ai-success {{
    background: rgba(16,185,129,.08);
    border: 1px solid rgba(16,185,129,.2);
    border-right: 4px solid {ACCENT_GREEN};

    border-radius: 12px;
    padding: 13px 16px;

    color: #B9F3DB;
    font-size: 13px;
    line-height: 1.9;

    direction: rtl;
    text-align: right;

    margin: 10px 0;
}}

.ai-warning {{
    background: rgba(212,175,55,.075);
    border: 1px solid rgba(212,175,55,.22);
    border-right: 4px solid {GOLD};

    border-radius: 12px;
    padding: 13px 16px;

    color: #F0DEA7;
    font-size: 13px;
    line-height: 1.9;

    direction: rtl;
    text-align: right;

    margin: 10px 0;
}}

/* -------------------------------------------------------
   الأزرار
------------------------------------------------------- */

.stButton > button {{
    border-radius: 11px !important;

    border: 1px solid rgba(212,175,55,.32) !important;

    background:
        linear-gradient(
            135deg,
            rgba(212,175,55,.14),
            rgba(212,175,55,.045)
        ) !important;

    color: {GOLD_LIGHT} !important;

    font-weight: 700 !important;
    min-height: 42px;

    transition: all .22s ease-in-out !important;
}}

.stButton > button:hover {{
    background:
        linear-gradient(
            135deg,
            rgba(212,175,55,.27),
            rgba(212,175,55,.10)
        ) !important;

    border-color: rgba(212,175,55,.65) !important;

    box-shadow: 0 0 17px {GOLD_GLOW} !important;

    transform: translateY(-1px);
}}

.stButton > button:focus {{
    box-shadow: 0 0 0 2px rgba(212,175,55,.18) !important;
}}

.stButton > button[kind="primary"] {{
    background:
        linear-gradient(
            110deg,
            #B58B29,
            #D4AF37
        ) !important;

    border: 0 !important;
    color: #101522 !important;
    font-weight: 900 !important;
}}

.stButton > button[kind="primary"]:hover {{
    background:
        linear-gradient(
            110deg,
            #D4AF37,
            #F0D98A
        ) !important;

    color: #080C14 !important;
}}

/* -------------------------------------------------------
   التبويبات
------------------------------------------------------- */

div[data-baseweb="tab-list"] {{
    background: transparent !important;
    gap: 7px !important;

    border-bottom: 1px solid rgba(212,175,55,.15);
    padding-bottom: 6px;
}}

button[data-baseweb="tab"] {{
    background: rgba(23,35,55,.82) !important;

    color: {TEXT_SECONDARY} !important;

    border: 1px solid rgba(255,255,255,.045) !important;
    border-radius: 10px 10px 5px 5px !important;

    padding: 10px 14px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
}}

button[data-baseweb="tab"][aria-selected="true"] {{
    color: {GOLD_LIGHT} !important;

    background: rgba(212,175,55,.09) !important;

    border-color: rgba(212,175,55,.28) !important;
    border-bottom: 2px solid {GOLD} !important;
}}

/* -------------------------------------------------------
   الحقول
------------------------------------------------------- */

.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stDateInput input {{
    background: #111A2B !important;
    color: {TEXT_PRIMARY} !important;

    border: 1px solid #2A3952 !important;
    border-radius: 10px !important;
}}

.stSelectbox div[data-baseweb="select"],
.stMultiSelect div[data-baseweb="select"] {{
    background: #111A2B !important;
    border-color: #2A3952 !important;
    border-radius: 10px !important;
}}

.stTextInput label,
.stNumberInput label,
.stTextArea label,
.stSelectbox label,
.stDateInput label {{
    color: {TEXT_SECONDARY} !important;
    font-size: 13px !important;
    direction: rtl;
}}

[data-testid="stChatInput"] {{
    border: 1px solid rgba(212,175,55,.3) !important;
    border-radius: 15px !important;
    background: #111A2B !important;
}}

[data-testid="stChatInput"] textarea {{
    color: {TEXT_PRIMARY} !important;
}}

/* -------------------------------------------------------
   المحادثة
------------------------------------------------------- */

[data-testid="stChatMessage"] {{
    background: rgba(17,26,43,.82) !important;

    border: 1px solid rgba(212,175,55,.12);
    border-radius: 15px !important;

    padding: 13px 16px !important;
    margin-bottom: 11px !important;
}}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li {{
    color: {TEXT_PRIMARY};
    line-height: 1.9;
}}

.ai-chat-empty {{
    background:
        linear-gradient(
            145deg,
            rgba(23,35,55,.9),
            rgba(14,22,36,.95)
        );

    border: 1px solid {CARD_BORDER};
    border-radius: 18px;

    padding: 28px 20px;

    text-align: center;
    direction: rtl;

    margin: 16px 0;
}}

.ai-chat-empty-icon {{
    color: {GOLD};
    font-size: 34px;
}}

.ai-chat-empty-title {{
    color: {TEXT_PRIMARY};
    font-weight: 900;
    font-size: 19px;
    margin-top: 9px;
}}

.ai-chat-empty-text {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
    line-height: 2;
    margin-top: 9px;
}}

/* -------------------------------------------------------
   الجداول
------------------------------------------------------- */

[data-testid="stDataFrame"] {{
    border: 1px solid rgba(212,175,55,.15);
    border-radius: 12px;
    overflow: hidden;
}}

[data-testid="stTable"] {{
    border: 1px solid rgba(212,175,55,.15);
    border-radius: 12px;
    overflow: hidden;
}}

/* -------------------------------------------------------
   عناصر أخرى
------------------------------------------------------- */

hr {{
    border-color: rgba(212,175,55,.15) !important;
}}

.stCaption {{
    color: {TEXT_MUTED} !important;
}}

[data-testid="stExpander"] {{
    background: rgba(17,26,43,.65);
    border: 1px solid rgba(212,175,55,.13);
    border-radius: 12px;
}}

.stProgress > div > div {{
    background: {GOLD} !important;
}}

footer {{
    visibility: hidden;
}}

#MainMenu {{
    visibility: hidden;
}}

/* -------------------------------------------------------
   دعم RTL دون التأثير على ترتيب عناصر Streamlit
------------------------------------------------------- */

.main .block-container {{
    direction: rtl;
    text-align: right;
}}

section[data-testid="stSidebar"] {{
    direction: rtl;
    text-align: right;
}}

.stMarkdown,
.stCaption {{
    text-align: right;
}}

@media(max-width: 900px) {{
    .ai-hero {{
        padding: 22px 19px;
    }}

    .ai-hero-title {{
        font-size: 23px;
    }}

    .main .block-container {{
        padding-left: 1rem;
        padding-right: 1rem;
    }}
}}

</style>
"""


# =========================================================
# 4. أدوات عامة
# =========================================================

def _safe_text(value: Any) -> str:
    """تحويل القيمة إلى نص دون كسر الواجهة."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception:
        return str(value)


def _safe_html(value: Any) -> str:
    """تحويل النص إلى HTML آمن."""
    text = str(value or "")

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _safe_color(value: Any, default: str = GOLD) -> str:
    """قبول لون CSS بصيغة Hex فقط."""
    value = str(value or "").strip()

    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", value):
        return value

    return default


def _money(value: Any) -> str:
    """تنسيق مبلغ مالي."""
    try:
        return f"{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _callable(name: str):
    """الحصول على دالة من خدمة الذكاء الاصطناعي."""
    return getattr(_ai_service, name, None) if _ai_service else None


def _is_empty(value: Any) -> bool:
    """التحقق من كون النتيجة فارغة."""
    if value is None:
        return True

    if isinstance(value, (list, tuple, dict, str)):
        return len(value) == 0

    return False


def _to_dataframe(data: Any) -> Optional[pd.DataFrame]:
    """تحويل البيانات إلى DataFrame عند الإمكان."""
    if data is None:
        return None

    try:
        if isinstance(data, pd.DataFrame):
            return data

        if isinstance(data, (list, tuple)):
            if len(data) == 0:
                return pd.DataFrame()

            return pd.DataFrame(data)

        if isinstance(data, dict):
            return pd.DataFrame([data])

    except Exception:
        return None

    return None


def _display_data(
    data: Any,
    empty_message: str = "لا توجد بيانات متاحة للعرض.",
) -> None:
    """عرض قائمة أو قاموس أو DataFrame أو نص."""
    if _is_empty(data):
        st.info(empty_message)
        return

    if isinstance(data, pd.DataFrame):
        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
        )
        return

    if isinstance(data, (list, tuple)):
        df = _to_dataframe(data)

        if df is not None:
            if not df.empty:
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(empty_message)
        else:
            st.write(data)

        return

    if isinstance(data, dict):
        df = _to_dataframe(data)

        if df is not None and len(data) > 0:
            st.json(data, expanded=False)
        else:
            st.write(data)

        return

    st.markdown(_safe_text(data))


def _service_call(
    function,
    *args,
    default=None,
    **kwargs,
):
    """استدعاء دالة مع معالجة الاستثناءات."""
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        st.error(f"تعذّر تنفيذ العملية: {exc}")
        return default


def _apply_design() -> None:
    """تحميل CSS."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================================================
# 5. مكونات التصميم
# =========================================================

def _render_hero() -> None:
    """رأس الصفحة."""
    st.markdown(
        f"""
        <div class="ai-hero">

            <div class="ai-hero-badge">
                ✦ AI ENTERPRISE HUB
            </div>

            <div class="ai-hero-title">
                المساعد المالي الذكي
            </div>

            <div class="ai-hero-subtitle">
                منصة تحليل ومساعدة مالية متكاملة داخل نظام حوكمة ERP.
                استكشف مؤشرات الأداء، حلّل الحسابات والمخزون،
                أنشئ مسودات القيود، وادرس مراكز التكلفة.
            </div>

            <div class="ai-hero-status">
                <span class="ai-status-dot"></span>
                يعمل محليًا عبر llama.cpp
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="ai-section-title">{_safe_html(title)}</div>
        <div class="ai-section-subtitle">{_safe_html(subtitle)}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_metric(
    label: str,
    value: Any,
    note: str = "",
) -> None:
    st.markdown(
        f"""
        <div class="ai-metric">
            <div class="ai-metric-label">{_safe_html(label)}</div>
            <div class="ai-metric-value">{_safe_html(value)}</div>
            <div class="ai-metric-note">{_safe_html(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_info(message: str, kind: str = "info") -> None:
    classes = {
        "info": "ai-info",
        "success": "ai-success",
        "warning": "ai-warning",
    }

    css_class = classes.get(kind, "ai-info")

    st.markdown(
        f"""
        <div class="{css_class}">
            {_safe_html(message)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_response(content: Any) -> None:
    """
    عرض رد الذكاء الاصطناعي.

    لا نضع نص النموذج داخل HTML باستخدام unsafe_allow_html.
    نستخدم Markdown العادي حتى لا يستطيع الرد إدخال HTML
    مباشر إلى الصفحة.
    """
    st.markdown(
        """
        <div class="ai-card">
            <div class="ai-card-title">✦ تحليل المساعد الذكي</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if isinstance(content, dict):
        content = _safe_text(content)

    if content is None:
        st.info("لم يتم إنشاء نتيجة.")
        return

    with st.container(border=True):
        st.markdown(str(content))


# =========================================================
# 6. الاتصال بمحرك الذكاء الاصطناعي المحلي
# =========================================================

def query_local_ai(
    prompt: str,
    active_query: str,
    model: str = LOCAL_MODEL_ID,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """
    تنفيذ الاستعلام عبر الخدمة.

    query_groq هنا اسم توافق موجود في الخدمة القديمة،
    لكن يجب أن يكون تنفيذها في ai_service.py محليًا عبر llama.cpp.

    لا نستخدم Groq SDK أو مفتاحًا سحابيًا.
    """

    try:
        if not callable(query_groq):
            return (
                "دالة الاتصال بالذكاء الاصطناعي غير متاحة. "
                "تحقق من services/ai_service.py."
            )

        result = query_groq(
            prompt,
            active_query,
            model=LOCAL_MODEL_ID,
            max_tokens=max_tokens,
        )

        if result is None:
            return "لم يُرجع النموذج نتيجة."

        if isinstance(result, str):
            return result.strip()

        if isinstance(result, dict):
            for key in (
                "answer",
                "response",
                "content",
                "message",
                "text",
            ):
                if result.get(key) is not None:
                    return str(result[key]).strip()

        return _safe_text(result)

    except FileNotFoundError:
        return (
            "لم يتم العثور على ملفات تشغيل llama.cpp أو ملف النموذج. "
            "تحقق من المسارات داخل services/ai_service.py."
        )

    except ConnectionError as exc:
        return f"تعذّر الاتصال بمحرك llama.cpp المحلي: {exc}"

    except TimeoutError:
        return (
            "انتهت مهلة انتظار النموذج. "
            "جرّب تقليل طول السؤال أو استخدام نموذج أصغر."
        )

    except Exception as exc:
        return f"حدث خطأ أثناء الاتصال بمحرك الذكاء الاصطناعي: {exc}"


def _make_prompt(
    data: Any,
    task: str,
    instructions: str,
) -> str:
    """إنشاء Prompt موحد للتحليلات."""
    data_text = _safe_text(data)

    return f"""
{SYSTEM_ROLE}

## البيانات الحالية من نظام حوكمة ERP

{data_text}

## المهمة

{task}

## المطلوب

{instructions}

يجب أن تعتمد على البيانات المتاحة فقط.
لا تفترض أرقامًا أو معلومات غير موجودة.
استخدم Markdown، والعناوين، والجداول عندما يكون ذلك مناسبًا.
"""


# =========================================================
# 7. إدارة المحادثات
# =========================================================

def _ensure_session() -> None:
    """إنشاء جلسة محادثة عند الحاجة."""
    if "active_session" not in st.session_state:
        st.session_state.active_session = (
            f"s_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        )

    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    if "ai_history_loaded" not in st.session_state:
        st.session_state.ai_history_loaded = False


def _new_chat() -> None:
    """إنشاء محادثة جديدة."""
    st.session_state.active_session = (
        f"s_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    )

    st.session_state.ai_messages = []
    st.session_state.ai_history_loaded = True


def _normalize_history_item(item: Any) -> Optional[Dict[str, str]]:
    """تطبيع سجل المحادثة إلى role/content."""
    role = None
    content = None

    if isinstance(item, dict):
        role = (
            item.get("role")
            or item.get("sender")
            or item.get("message_role")
            or "assistant"
        )

        content = (
            item.get("content")
            or item.get("message")
            or item.get("text")
            or item.get("response")
            or ""
        )

    elif isinstance(item, (tuple, list)):
        if len(item) >= 2:
            role = item[-2]
            content = item[-1]

    if content is None:
        return None

    role = str(role or "assistant").lower().strip()

    if role not in ("user", "assistant", "system"):
        role = "assistant"

    return {
        "role": role,
        "content": str(content),
    }


def _load_chat_history(session_id: str) -> List[Dict[str, str]]:
    """استرجاع سجل محادثة."""
    try:
        raw_history = get_chat_history(session_id)
    except TypeError:
        try:
            raw_history = get_chat_history(
                session_id=session_id
            )
        except Exception:
            return []
    except Exception:
        return []

    messages = []

    if isinstance(raw_history, dict):
        raw_history = raw_history.get(
            "messages",
            raw_history.get("data", []),
        )

    if not isinstance(raw_history, (list, tuple)):
        return []

    for item in raw_history:
        normalized = _normalize_history_item(item)

        if normalized:
            messages.append(normalized)

    return messages


def _load_current_history() -> None:
    """تحميل المحادثة الحالية مرة واحدة."""
    if st.session_state.ai_history_loaded:
        return

    session_id = st.session_state.active_session

    st.session_state.ai_messages = _load_chat_history(
        session_id
    )

    st.session_state.ai_history_loaded = True


def _save_history(
    session_id: str,
    role: str,
    content: str,
    model: str = LOCAL_MODEL_ID,
    category: str = CHAT_CATEGORY,
) -> None:
    """
    حفظ الرسالة بالتوقيع المتوافق مع الواجهة الأصلية:

    save_chat_history(
        session_id,
        role,
        content,
        model,
        category
    )
    """
    try:
        save_chat_history(
            session_id,
            role,
            content,
            model,
            category,
        )

    except TypeError:
        # توافق مع إصدارات الخدمة التي قد تستخدم توقيعًا أبسط.
        try:
            save_chat_history(
                session_id,
                role,
                content,
            )
        except Exception as exc:
            st.warning(f"تعذّر حفظ المحادثة: {exc}")

    except Exception as exc:
        st.warning(f"تعذّر حفظ المحادثة: {exc}")


def _get_sessions() -> List[Any]:
    """الحصول على قائمة المحادثات."""
    try:
        sessions = get_chat_sessions()

        if isinstance(sessions, list):
            return sessions

        if isinstance(sessions, tuple):
            return list(sessions)

        return []

    except Exception:
        return []


def _session_details(item: Any, index: int) -> Tuple[str, str]:
    """استخراج معرف المحادثة وعنوانها."""
    if isinstance(item, dict):
        session_id = (
            item.get("session_id")
            or item.get("chat_id")
            or item.get("id")
        )

        title = (
            item.get("title")
            or item.get("name")
            or item.get("first_message")
            or f"محادثة {index + 1}"
        )

        return str(session_id or ""), str(title)

    if isinstance(item, (tuple, list)):
        session_id = item[0] if len(item) > 0 else ""
        title = item[1] if len(item) > 1 else f"محادثة {index + 1}"

        return str(session_id or ""), str(title)

    return "", f"محادثة {index + 1}"


# =========================================================
# 8. الشريط الجانبي
# =========================================================

def _render_sidebar() -> None:
    """إعدادات المحرك وسجل المحادثات."""
    with st.sidebar:

        st.markdown(
            f"""
            <div style="
                direction:rtl;
                text-align:right;
                padding:8px 4px 19px;
            ">
                <div style="
                    color:{TEXT_PRIMARY};
                    font-size:26px;
                    font-weight:900;
                ">
                    حوكمة
                    <span style="color:{GOLD}">AI</span>
                </div>

                <div style="
                    color:{TEXT_MUTED};
                    font-size:11px;
                    margin-top:5px;
                ">
                    ENTERPRISE INTELLIGENCE
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        st.markdown(
            f"""
            <div style="
                color:{GOLD_LIGHT};
                font-size:14px;
                font-weight:800;
                text-align:right;
                direction:rtl;
                margin-bottom:10px;
            ">
                ⚙️ إعدادات المحرك
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.selectbox(
            "المحرك المستخدم",
            options=[LOCAL_MODEL_LABEL],
            index=0,
            disabled=True,
            key="local_ai_engine",
        )

        st.caption(
            f"معرف النموذج المحلي: {LOCAL_MODEL_ID}"
        )

        st.markdown("---")

        if st.button(
            "＋ محادثة جديدة",
            key="new_ai_chat",
            use_container_width=True,
            type="primary",
        ):
            _new_chat()
            st.rerun()

        st.markdown(
            f"""
            <div style="
                color:{TEXT_PRIMARY};
                font-weight:800;
                font-size:13px;
                text-align:right;
                direction:rtl;
                margin:18px 0 10px;
            ">
                💬 المحادثات السابقة
            </div>
            """,
            unsafe_allow_html=True,
        )

        sessions = _get_sessions()

        if not sessions:
            st.caption("لا توجد محادثات سابقة.")
        else:
            session_map = {}

            for index, item in enumerate(sessions[:25]):
                session_id, title = _session_details(
                    item,
                    index,
                )

                if not session_id:
                    continue

                short_title = title[:34]

                session_map[
                    f"{short_title} · {session_id[-6:]}"
                ] = session_id

            if session_map:
                labels = list(session_map.keys())

                selected_label = st.selectbox(
                    "اختر محادثة",
                    options=labels,
                    index=None,
                    placeholder="حدد محادثة سابقة...",
                    label_visibility="collapsed",
                    key="ai_old_session_selector",
                )

                if selected_label:
                    selected_session = session_map[selected_label]

                    if (
                        selected_session
                        != st.session_state.active_session
                    ):
                        st.session_state.active_session = (
                            selected_session
                        )

                        st.session_state.ai_history_loaded = False
                        st.session_state.ai_messages = []

                        st.rerun()

        st.markdown("---")

        st.markdown(
            f"""
            <div style="
                direction:rtl;
                text-align:right;
                line-height:2;
                font-size:11px;
                color:{TEXT_MUTED};
            ">
                <b style="color:{GOLD_LIGHT}">
                    حالة التشغيل
                </b>
                <br>

                <span style="color:{ACCENT_GREEN}">
                    ●
                </span>
                محرك محلي

                <br>
                لا يوجد اتصال بـ Groq من هذه الواجهة.
                <br>
                لا يلزم مفتاح API سحابي.
            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# 9. معالجة الصوت محليًا
# =========================================================

def audio_to_text(audio_file) -> str:
    """
    التفريغ الصوتي المحلي فقط.

    لا يوجد استخدام لـ Groq أو Whisper API سحابي.

    يمكن لهذه الواجهة استخدام إحدى الدوال التالية
    إذا أضيفت لاحقًا إلى ai_service.py:
        audio_to_text_local
        transcribe_audio_local
        transcribe_audio
    """
    if audio_file is None:
        return ""

    local_functions = (
        "audio_to_text_local",
        "transcribe_audio_local",
        "transcribe_audio",
    )

    local_function = None

    for function_name in local_functions:
        candidate = _callable(function_name)

        if callable(candidate):
            local_function = candidate
            break

    if local_function is None:
        return (
            "التفريغ الصوتي المحلي غير مهيأ في الخدمة حاليًا. "
            "أضف محرك whisper.cpp محليًا وربط دالته في ai_service.py."
        )

    try:
        suffix = ".wav"

        if hasattr(audio_file, "name"):
            extension = os.path.splitext(
                str(audio_file.name)
            )[1]

            if extension:
                suffix = extension

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:

            temp_path = temp_file.name
            temp_file.write(audio_file.getbuffer())

        try:
            signature = inspect.signature(local_function)
            params = list(signature.parameters.keys())

            if params:
                result = local_function(temp_path)
            else:
                result = local_function()

        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        if isinstance(result, dict):
            return str(
                result.get("text")
                or result.get("transcription")
                or result.get("content")
                or ""
            )

        return str(result or "")

    except Exception as exc:
        return f"تعذّر تفريغ الصوت محليًا: {exc}"


def audio_input_widget(key: str = "assistant_audio") -> str:
    """عنصر صوت يستخدم محركًا محليًا عند توفره."""
    local_audio_available = any(
        callable(_callable(name))
        for name in (
            "audio_to_text_local",
            "transcribe_audio_local",
            "transcribe_audio",
        )
    )

    if not hasattr(st, "audio_input"):
        st.caption("إدخال الصوت غير مدعوم في إصدار Streamlit الحالي.")
        return ""

    if not local_audio_available:
        st.caption(
            "الميكروفون غير مفعّل حتى يتم ربط whisper.cpp محليًا."
        )
        return ""

    audio_value = st.audio_input(
        "تسجيل صوتي",
        key=key,
        label_visibility="collapsed",
    )

    if audio_value is None:
        return ""

    with st.spinner("🎙️ جاري التفريغ الصوتي محليًا..."):
        result = audio_to_text(audio_value)

    if result.startswith("تعذّر"):
        st.error(result)
        return ""

    return result


# =========================================================
# 10. تبويب المساعد الذكي
# =========================================================

def _render_chat_tab(model: str) -> None:

    _section_title(
        "المساعد الذكي",
        "اسأل باللغة الطبيعية عن حساباتك وبياناتك المالية والتشغيلية.",
    )

    _load_current_history()

    st.markdown(
        """
        <div class="ai-card">
            <div class="ai-card-title">
                ✦ كيف يمكنني مساعدتك؟
            </div>
            <div class="ai-card-caption">
                تحليل الأداء المالي، تفسير النسب، متابعة المصروفات،
                فهم المخزون، مراجعة القيود، ودراسة المؤشرات التشغيلية.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    voice_text = audio_input_widget(
        key="assistant_audio"
    )

    # عرض تاريخ المحادثة.
    for message in st.session_state.ai_messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")

        if role not in ("user", "assistant"):
            continue

        avatar = "👤" if role == "user" else "✦"

        with st.chat_message(
            role,
            avatar=avatar,
        ):
            st.markdown(content)

    question = st.chat_input(
        "اكتب سؤالك المالي أو التشغيلي هنا...",
        key="ai-chat-input",
    )

    active_query = ""

    if voice_text:
        active_query = voice_text.strip()
    elif question:
        active_query = question.strip()

    if not active_query:
        return

    if not st.session_state.ai_messages:
        st.session_state.ai_messages = []

    # إضافة رسالة المستخدم إلى السجل.
    st.session_state.ai_messages.append(
        {
            "role": "user",
            "content": active_query,
        }
    )

    _save_history(
        st.session_state.active_session,
        "user",
        active_query,
        model,
        CHAT_CATEGORY,
    )

    with st.chat_message("user", avatar="👤"):
        st.markdown(active_query)

    try:
        with st.spinner("✦ جاري تحليل البيانات محليًا..."):

            data = get_comprehensive_data()

            prompt = _make_prompt(
                data=data,
                task=active_query,
                instructions="""
قدم إجابة وافية ودقيقة ومنظمة مهنيًا.

1. ابدأ بخلاصة مباشرة.
2. اعرض الأرقام ذات الصلة إن كانت متاحة.
3. اشرح التأثير المالي والتشغيلي.
4. وضح أي نقص أو غموض في البيانات.
5. قدم توصيات عملية قابلة للمراجعة.
""",
            )

            answer = query_local_ai(
                prompt,
                active_query,
                model=model,
                max_tokens=2048,
            )

    except Exception as exc:
        answer = f"حدث خطأ أثناء تجهيز بيانات السؤال: {exc}"

    with st.chat_message("assistant", avatar="✦"):
        st.markdown(answer)

    st.session_state.ai_messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )

    _save_history(
        st.session_state.active_session,
        "assistant",
        answer,
        model,
        CHAT_CATEGORY,
    )

    st.rerun()


# =========================================================
# 11. تبويب التحليل المالي
# =========================================================

def _render_financial_analysis_tab(model: str) -> None:

    _section_title(
        "التحليل المالي والنسب",
        "تحليل الأداء المالي، تقييم النسب والمؤشرات، ودراسة نقاط القوة والمخاطر.",
    )

    st.markdown(
        """
        <div class="ai-card">
            <div class="ai-card-title">
                📊 التحليل المالي الشامل
            </div>
            <div class="ai-card-caption">
                يستخدم التحليل الإيرادات والمصروفات وصافي الدخل
                والنسب المالية المتاحة في قاعدة البيانات.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "🚀 بدء التحليل المالي الشامل",
        type="primary",
        use_container_width=True,
        key="run_financial_analysis",
    ):

        with st.spinner("📊 جاري استخراج المؤشرات وتحليلها..."):

            data = get_comprehensive_data()
            ratios = get_financial_ratios()

            revenue = (
                data.get("revenue", 0)
                if isinstance(data, dict)
                else 0
            )

            expenses = (
                data.get("expenses", 0)
                if isinstance(data, dict)
                else 0
            )

            net_income = (
                data.get("net_income", 0)
                if isinstance(data, dict)
                else 0
            )

            st.markdown("### المؤشرات الأساسية")

            c1, c2, c3 = st.columns(3)

            with c1:
                _render_metric(
                    "الإيرادات",
                    _money(revenue),
                    "وفق البيانات المتاحة",
                )

            with c2:
                _render_metric(
                    "المصروفات",
                    _money(expenses),
                    "وفق البيانات المتاحة",
                )

            with c3:
                _render_metric(
                    "صافي الدخل",
                    _money(net_income),
                    "وفق البيانات المتاحة",
                )

            st.markdown("---")

            prompt = f"""
أنت محلل مالي أول ومستشار استراتيجي.

الأرقام الأساسية:
الإيرادات: {_money(revenue)}
المصروفات: {_money(expenses)}
صافي الدخل: {_money(net_income)}

النسب والمؤشرات:
{_safe_text(ratios)}

المطلوب إعداد تقرير احترافي يتضمن:

1. الملخص التنفيذي.
2. تحليل الإيرادات والمصروفات وصافي الدخل.
3. تحليل النسب المالية وشرح معنى كل نسبة متاحة.
4. نقاط القوة والضعف المالية.
5. المخاطر المالية المحتملة.
6. توصيات عملية لتحسين الربحية والسيولة.

لا تصدر حكمًا على نسبة غير متاحة.
لا تخترع قيمًا أو معايير مقارنة غير موجودة.
"""

            answer = query_local_ai(
                prompt,
                "قدم التحليل المالي الشامل",
                model,
                2048,
            )

        render_ai_response(answer)


# =========================================================
# 12. تبويب المخزون
# =========================================================

def _render_inventory_tab(model: str) -> None:

    _section_title(
        "تحليل المخزون واكتشاف العجز",
        "مراجعة الأصناف، تحديد المنتجات الحرجة، واكتشاف مؤشرات النقص أو التكدس.",
    )

    if st.button(
        "📦 تحميل وتحليل المخزون",
        type="primary",
        use_container_width=True,
        key="inventory_analysis",
    ):

        with st.spinner("جاري تحميل بيانات المخزون..."):
            result = get_inventory_data()

        if isinstance(result, tuple) and len(result) >= 2:
            low, all_products = result[0], result[1]
        else:
            low, all_products = [], result

        low = low or []
        all_products = all_products or []

        st.markdown("### حالة المخزون")

        c1, c2 = st.columns(2)

        with c1:
            _render_metric(
                "عدد الأصناف المتاحة في البيانات",
                len(all_products),
                "إجمالي المنتجات المسترجعة",
            )

        with c2:
            _render_metric(
                "الأصناف تحت الحد الأدنى",
                len(low),
                "تحتاج إلى مراجعة",
            )

        if low:
            _render_info(
                f"يوجد {len(low)} صنفًا تحت الحد الأدنى للطلب.",
                "warning",
            )

            st.markdown("#### الأصناف الحرجة")
            _display_data(low)
        else:
            _render_info(
                "لم يتم إرجاع أصناف تحت الحد الأدنى من المخزون.",
                "success",
            )

        if all_products:
            st.markdown("#### بيانات المخزون")
            _display_data(all_products)

            df = _to_dataframe(all_products)

            if df is not None:
                inventory_text = df.to_string(index=False)
            else:
                inventory_text = _safe_text(all_products)

            prompt = f"""
أنت خبير في إدارة المخزون وسلاسل الإمداد.

بيانات المخزون:
{inventory_text}

الأصناف التي ظهرت تحت الحد الأدنى:
{_safe_text(low)}

قدم تحليلًا يتضمن:

1. التقييم العام لحالة المخزون.
2. المنتجات التي قد تتعرض للنفاد.
3. الأصناف المحتمل تكدسها إذا كانت البيانات تسمح بذلك.
4. المخاطر المالية والتشغيلية.
5. توصيات تحسين معدل دوران المخزون.
6. قائمة بالإجراءات التي تتطلب مراجعة الإدارة.

لا تستنتج معدل دوران أو قيمة مخزون غير متاحة.
"""

            with st.spinner("🧠 جاري تحليل المخزون..."):
                answer = query_local_ai(
                    prompt,
                    "حلل المخزون وقدم تقريرًا إداريًا",
                    model,
                    2048,
                )

            render_ai_response(answer)

        else:
            st.info("لا توجد بيانات مخزون كافية للتحليل.")


# =========================================================
# 13. تبويب الموارد البشرية
# =========================================================

def _render_hr_tab(model: str) -> None:

    _section_title(
        "استعلامات الموارد البشرية",
        "استرجاع بيانات الموظف وتوليد إجابات إدارية بناءً على البيانات المتاحة.",
    )

    with st.container(border=True):

        c1, c2 = st.columns(2)

        with c1:
            employee_name = st.text_input(
                "اسم الموظف",
                placeholder="اكتب اسم الموظف...",
                key="ai_employee_name",
            )

        with c2:
            question = st.text_input(
                "السؤال",
                placeholder="مثال: ما بيانات وظيفتي؟",
                key="ai_employee_question",
            )

        submitted = st.button(
            "استعلام عن الموظف",
            type="primary",
            use_container_width=True,
            key="employee_query",
        )

    if not submitted:
        return

    if not employee_name.strip() or not question.strip():
        st.warning("يرجى إدخال اسم الموظف والسؤال.")
        return

    with st.spinner("جاري البحث عن بيانات الموظف..."):
        result = get_employee_info(employee_name.strip())

    if not isinstance(result, tuple) or len(result) < 2:
        st.error("لم يتم استرجاع بيانات الموظف بالشكل المتوقع.")
        return

    employee, salary = result[0], result[1]

    if not employee:
        st.error("الموظف غير موجود في قاعدة البيانات.")
        return

    employee = employee or {}
    salary = salary or {}

    if not isinstance(employee, dict):
        employee = {}

    if not isinstance(salary, dict):
        salary = {}

    employee_info = f"""
اسم الموظف: {employee.get('name', employee_name)}
المسمى الوظيفي: {employee.get('position', 'غير متاح')}
الراتب الأساسي: {salary.get('basic_salary', 0)}
"""

    prompt = f"""
أنت مدير موارد بشرية محترف.

بيانات الموظف:
{employee_info}

سؤال الموظف:
{question}

أجب بأسلوب مهني وواضح.
اعتمد على المعلومات المتاحة فقط.
لا تفترض تقييم أداء أو استحقاقات أو معلومات غير موجودة.
إذا لم تكن البيانات كافية، اذكر ذلك.
"""

    with st.spinner("جاري صياغة الإجابة..."):
        answer = query_local_ai(
            prompt,
            question,
            model,
            1200,
        )

    st.markdown("### نتيجة الاستعلام")
    render_ai_response(answer)


# =========================================================
# 14. تبويب القيود المحاسبية
# =========================================================

def _render_entries_tab() -> None:

    _section_title(
        "محرك القيود المحاسبية الذكي",
        "توليد مسودة قيد محاسبي باستخدام قوالب الخدمة وقواعد التوجيه المحاسبي.",
    )

    _render_info(
        "المخرجات مسودة للمراجعة فقط. لا يتم اعتماد القيد أو ترحيله "
        "إلى الأستاذ العام تلقائيًا من هذه الواجهة.",
        "warning",
    )

    operations = get_available_operations()

    if not operations:
        st.warning("لا توجد أنواع عمليات متاحة في الخدمة.")
        return

    selected_op = st.selectbox(
        "🎯 اختر نوع العملية المالية",
        options=operations,
        key="ai_entry_operation",
    )

    operation_description = get_operation_description(
        selected_op
    )

    st.markdown(
        f"""
        <div class="ai-info">
            <b>وصف العملية</b><br>
            {_safe_html(operation_description)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # تعيين القيم الافتراضية لمنع المتغيرات غير المعرفة.
    total_amount = 0.0
    cash_amount = None
    credit_amount = None
    vat_rate = None
    expense_name = None
    adjustment_side = None
    inventory_side = None

    # ---------------------------------------------
    # عملية نقدية وآجلة مختلطة
    # ---------------------------------------------
    if is_mixed_operation(selected_op):

        st.markdown("#### تفاصيل العملية المختلطة")

        c1, c2, c3 = st.columns(3)

        with c1:
            total_amount = st.number_input(
                "المبلغ الإجمالي",
                min_value=0.0,
                step=10.0,
                key="entry_total_mixed",
            )

        with c2:
            cash_amount = st.number_input(
                "الجزء النقدي",
                min_value=0.0,
                step=10.0,
                key="entry_cash_mixed",
            )

        with c3:
            credit_amount = st.number_input(
                "الجزء الآجل",
                min_value=0.0,
                step=10.0,
                key="entry_credit_mixed",
            )

        if (
            cash_amount + credit_amount
            and abs((cash_amount + credit_amount) - total_amount) > 0.01
        ):
            st.warning(
                "تأكد من أن مجموع الجزء النقدي والآجل يساوي المبلغ الإجمالي."
            )

    # ---------------------------------------------
    # عمليات ضريبة القيمة المضافة
    # ---------------------------------------------
    elif is_vat_operation(selected_op):

        st.markdown("#### بيانات الضريبة")

        c1, c2 = st.columns(2)

        with c1:
            total_amount = st.number_input(
                "المبلغ شامل الضريبة",
                min_value=0.0,
                step=10.0,
                key="entry_vat_total",
            )

        with c2:
            vat_rate = st.number_input(
                "نسبة الضريبة (%)",
                min_value=0.0,
                max_value=100.0,
                value=15.0,
                step=0.5,
                key="entry_vat_rate",
            ) / 100

    # ---------------------------------------------
    # المصروفات
    # ---------------------------------------------
    elif selected_op == "سداد مصروف":

        st.markdown("#### بيانات المصروف")

        c1, c2 = st.columns(2)

        with c1:
            total_amount = st.number_input(
                "المبلغ",
                min_value=0.0,
                step=10.0,
                key="entry_expense_amount",
            )

        with c2:
            expense_name = st.text_input(
                "اسم المصروف",
                value="كهرباء",
                key="entry_expense_name",
            )

    # ---------------------------------------------
    # تسويات المخزون
    # ---------------------------------------------
    elif is_inventory_adjustment(selected_op):

        st.markdown("#### بيانات تسوية المخزون")

        c1, c2 = st.columns(2)

        with c1:
            total_amount = st.number_input(
                "قيمة التسوية",
                min_value=0.0,
                step=10.0,
                key="entry_inventory_amount",
            )

        with c2:
            adjustment_type = st.selectbox(
                "نوع التسوية",
                ["عجز (نقص)", "فائض (زيادة)"],
                key="entry_inventory_type",
            )

            if adjustment_type == "عجز (نقص)":
                adjustment_side = "debit"
                inventory_side = "credit"
            else:
                adjustment_side = "credit"
                inventory_side = "debit"

    # ---------------------------------------------
    # عمليات الرواتب
    # ---------------------------------------------
    elif is_salary_operation(selected_op):

        st.markdown("#### بيانات الرواتب")

        total_amount = st.number_input(
            "مبلغ عملية الرواتب",
            min_value=0.0,
            step=10.0,
            key="entry_salary_amount",
        )

        st.caption(
            "سيتم استخدام قالب الرواتب الموجود في خدمة القيود."
        )

    # ---------------------------------------------
    # العمليات العامة
    # ---------------------------------------------
    else:

        total_amount = st.number_input(
            "المبلغ",
            min_value=0.0,
            step=10.0,
            key="entry_general_amount",
        )

    st.markdown("---")

    if st.button(
        "✨ توليد القيد المحاسبي",
        type="primary",
        use_container_width=True,
        key="generate_ai_entry",
    ):

        if total_amount <= 0:
            st.warning("يرجى إدخال مبلغ صحيح أكبر من الصفر.")
            return

        if is_mixed_operation(selected_op):
            if (
                cash_amount is not None
                and credit_amount is not None
                and abs(
                    cash_amount + credit_amount - total_amount
                ) > 0.01
            ):
                st.error(
                    "مجموع الجزء النقدي والآجل لا يساوي المبلغ الإجمالي."
                )
                return

        with st.spinner("⚙️ جاري إنشاء مسودة القيد..."):

            result = generate_template_entry(
                operation_type=selected_op,
                amount=total_amount,
                cash_amount=cash_amount,
                credit_amount=credit_amount,
                expense_name=expense_name,
                vat_rate=vat_rate,
                adjustment_side=adjustment_side,
                inventory_side=inventory_side,
            )

        if not isinstance(result, (tuple, list)) or len(result) < 5:
            st.error(
                "لم تُرجع خدمة القيود النتيجة بالتنسيق المتوقع."
            )
            return

        entry, display, confidence, confidence_label, confidence_color = (
            result[:5]
        )

        if entry:
            st.markdown("### 🧾 مسودة القيد المحاسبي")

            st.code(
                str(display),
                language="text",
            )

            safe_color = _safe_color(
                confidence_color,
                ACCENT_GREEN,
            )

            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                confidence_value = 0

            confidence_value = max(
                0,
                min(100, confidence_value),
            )

            st.markdown(
                f"""
                <div style="
                    background:rgba(16,185,129,.07);
                    border:1px solid {safe_color};
                    border-radius:13px;
                    padding:15px 17px;
                    margin-top:12px;
                    direction:rtl;
                ">
                    <div style="
                        color:{TEXT_PRIMARY};
                        font-weight:800;
                        margin-bottom:9px;
                    ">
                        مستوى الثقة في التوجيه الآلي
                    </div>

                    <div style="
                        color:{safe_color};
                        font-size:20px;
                        font-weight:900;
                    ">
                        {confidence_value:.1f}%
                    </div>

                    <div style="
                        color:{TEXT_SECONDARY};
                        font-size:12px;
                        margin-top:5px;
                    ">
                        {_safe_html(confidence_label)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            _render_info(
                "تم إنشاء المسودة. راجع الحسابات والمبالغ والبيان "
                "قبل اعتماد القيد في النظام.",
                "success",
            )

        else:
            st.error(str(display))


# =========================================================
# 15. تبويب كشف الاحتيال والشذوذ
# =========================================================

def _render_fraud_tab(model: str) -> None:

    _section_title(
        "كشف الشذوذ والملاحظات الرقابية",
        "فحص القيود الحديثة وإبراز الحالات التي تستحق مراجعة بشرية.",
    )

    _render_info(
        "نتائج التحليل مؤشرات أولية للمراجعة وليست إثباتًا لوقوع احتيال.",
        "warning",
    )

    if st.button(
        "🔍 فحص القيود الأخيرة",
        type="primary",
        use_container_width=True,
        key="fraud_scan_button",
    ):

        with st.spinner("جاري استرجاع القيود الأخيرة..."):
            entries = get_recent_entries()

        if not entries:
            st.info("لا توجد قيود كافية للفحص.")
            return

        df = _to_dataframe(entries)

        if df is not None:
            entries_text = df.to_string(index=False)
            st.markdown("### عينة القيود المسترجعة")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            entries_text = _safe_text(entries)

        prompt = f"""
أنت مراجع داخلي متخصص في فحص القيود المالية.

افحص البيانات التالية:
{entries_text}

المطلوب إعداد تقرير مراجعة أولي:

1. ملخص عام للقيود المتاحة.
2. القيود التي تحتوي على بيانات غير مكتملة.
3. القيود التي تستحق مراجعة إضافية مع ذكر سبب ذلك.
4. مؤشرات التوقيت أو التكرار غير المعتاد إذا كانت البيانات تسمح.
5. ملاحظات على التوجيه المحاسبي إذا ظهرت من البيانات.
6. توصيات لتحسين الرقابة الداخلية.

قواعد مهمة:
- لا تصف أي قيد بأنه احتيال مؤكد.
- لا تفترض وجود تلاعب دون دليل.
- وضح أن كل ملاحظة تحتاج إلى تحقق بشري ومستندات داعمة.
"""

        with st.spinner("🕵️ جاري تحليل القيود..."):
            answer = query_local_ai(
                prompt,
                "افحص القيود واستخرج تقرير المراجعة",
                model,
                2048,
            )

        render_ai_response(answer)


# =========================================================
# 16. تبويب التنبؤات
# =========================================================

def _render_forecast_tab(model: str) -> None:

    _section_title(
        "التخطيط المالي والتنبؤ",
        "دراسة الاتجاهات والسيناريوهات المستقبلية بالاعتماد على البيانات المتاحة.",
    )

    period = st.selectbox(
        "حدد الأفق الزمني",
        [
            "الشهر القادم",
            "الربع القادم",
            "نهاية العام",
        ],
        key="ai_forecast_period",
    )

    forecast_type = st.selectbox(
        "نوع التنبؤ",
        [
            "تنبؤ مالي شامل",
            "توقع الإيرادات والمصروفات",
            "تحليل التدفقات النقدية",
            "توقع المخاطر المالية",
        ],
        key="ai_forecast_type",
    )

    if st.button(
        "🔮 توليد التنبؤ المالي",
        type="primary",
        use_container_width=True,
        key="run_ai_forecast",
    ):

        with st.spinner("جاري إعداد بيانات التنبؤ..."):
            data = get_comprehensive_data()

            trend_data = get_trend_analysis()

        prompt = f"""
أنت خبير تخطيط مالي وتحليل أعمال.

بيانات المنشأة:
{_safe_text(data)}

بيانات الاتجاهات:
{_safe_text(trend_data)}

الفترة المستهدفة:
{period}

نوع التنبؤ:
{forecast_type}

المطلوب:

1. توضيح المؤشرات التاريخية المتاحة.
2. قراءة الاتجاهات الحالية.
3. إعداد سيناريو محافظ وسيناريو متفائل إذا كانت البيانات تسمح.
4. توضيح الافتراضات المستخدمة.
5. تحليل المخاطر المحتملة.
6. وضع توصيات للإدارة.

لا تنشئ توقعات رقمية دقيقة من فراغ.
إذا لم توجد بيانات زمنية كافية، اذكر أن التوقع سيكون نوعيًا أو محدود الدقة.
"""

        with st.spinner("🔮 جاري تحليل السيناريوهات..."):
            answer = query_local_ai(
                prompt,
                "قم بتوليد التنبؤ المالي",
                model,
                2048,
            )

        render_ai_response(answer)


# =========================================================
# 17. التقرير الشامل لمجلس الإدارة
# =========================================================

def _render_board_report_tab(model: str) -> None:

    _section_title(
        "تقرير مجلس الإدارة",
        "إنشاء تقرير إداري شامل يدعم متابعة الأداء واتخاذ القرار.",
    )

    report_period = st.selectbox(
        "الفترة التي تريد إعداد التقرير عنها",
        [
            "الفترة الحالية",
            "الشهر الحالي",
            "الربع الحالي",
            "السنة الحالية",
        ],
        key="board_report_period",
    )

    if st.button(
        "📑 إصدار التقرير الشامل",
        type="primary",
        use_container_width=True,
        key="generate_board_report",
    ):

        with st.spinner("جاري تجميع البيانات..."):
            data = get_comprehensive_data()

            inventory = get_inventory_data()

            employees = None
            trends = get_trend_analysis()

        prompt = f"""
أنت مستشار مالي واستراتيجي لمجلس إدارة شركة.

الفترة:
{report_period}

بيانات الشركة:
{_safe_text(data)}

بيانات المخزون:
{_safe_text(inventory)}

بيانات الاتجاهات:
{_safe_text(trends)}

المطلوب إعداد تقرير مجلس إدارة منظم:

1. الملخص التنفيذي.
2. الأداء المالي.
3. الإيرادات والمصروفات وصافي الدخل.
4. الأداء التشغيلي والمخزون.
5. الموارد البشرية إذا كانت بياناتها متاحة.
6. المخاطر والملاحظات.
7. القرارات التي تحتاج إلى مراجعة الإدارة.
8. التوصيات الاستراتيجية.

اجعل التقرير واضحًا ومنظمًا.
لا تستخدم أرقامًا لم ترد في البيانات.
ميّز بين الوقائع والتوصيات والتوقعات.
"""

        with st.spinner("🧠 جاري إعداد تقرير مجلس الإدارة..."):
            answer = query_local_ai(
                prompt,
                "أصدر تقرير مجلس الإدارة الشامل",
                model,
                3000,
            )

        render_ai_response(answer)

        st.download_button(
            "⬇️ تنزيل التقرير",
            data=answer,
            file_name="تقرير_مجلس_الإدارة.txt",
            mime="text/plain",
            use_container_width=True,
            key="download_board_report",
        )


# =========================================================
# 18. تبويب مراكز التكلفة
# =========================================================

def _render_cost_center_tab(model: str) -> None:

    _section_title(
        "تحليل مراكز التكلفة",
        "دراسة أداء القطاعات، مقارنة المراكز، وتحليل انحرافات الموازنات.",
    )

    try:
        centers = ccs.get_all_cost_centers(
            active_only=True
        )
    except Exception as exc:
        st.error(
            f"تعذّر تحميل مراكز التكلفة: {exc}"
        )
        return

    if not centers:
        st.warning(
            "لا توجد مراكز تكلفة معرفة أو نشطة في النظام."
        )
        return

    options = {}

    for center in centers:
        try:
            label = (
                f"{center['code']} - {center['name']}"
            )

            options[label] = center["id"]

        except (KeyError, TypeError):
            continue

    if not options:
        st.warning("لم يتم العثور على مراكز تكلفة صالحة.")
        return

    selected_center = st.selectbox(
        "حدد مركز التكلفة",
        list(options.keys()),
        key="selected_cost_center",
    )

    cc_id = options[selected_center]

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    # ---------------------------------------------
    # تقييم الأداء
    # ---------------------------------------------
    with col1:
        performance_button = st.button(
            "📊 تقييم الأداء",
            type="primary",
            use_container_width=True,
            key="cc_performance",
        )

    # ---------------------------------------------
    # مقارنة القطاعات
    # ---------------------------------------------
    with col2:
        comparison_button = st.button(
            "⚖️ مقارنة القطاعات",
            use_container_width=True,
            key="cc_comparison",
        )

    # ---------------------------------------------
    # تحليل الموازنة
    # ---------------------------------------------
    with col3:
        budget_button = st.button(
            "📉 تحليل الانحرافات",
            use_container_width=True,
            key="cc_budget",
        )

    if performance_button:

        with st.spinner("جاري تقييم أداء مركز التكلفة..."):
            result = analyze_cost_center_performance(
                cc_id
            )

        st.markdown("### نتيجة تقييم الأداء")
        render_ai_response(result)

    if comparison_button:

        with st.spinner("جاري مقارنة مراكز التكلفة..."):
            result = compare_cost_centers()

        st.markdown("### مقارنة مراكز التكلفة")
        render_ai_response(result)

    if budget_button:

        year = st.number_input(
            "السنة المالية",
            min_value=2000,
            max_value=2200,
            value=datetime.now().year,
            step=1,
            key="cc_budget_year",
        )

        with st.spinner("جاري تحليل الموازنة..."):
            result = get_cost_center_budget_analysis(
                cc_id,
                int(year),
            )

        st.markdown("### تحليل الموازنة والانحرافات")
        render_ai_response(result)

    st.markdown("---")

    with st.expander("توقع مصروفات مراكز التكلفة"):
        st.markdown(
            "توقع المصروفات بناءً على البيانات المتاحة في الخدمة."
        )

        if st.button(
            "إنشاء التوقع",
            key="cc_predict_expenses",
        ):
            with st.spinner("جاري التنبؤ بالمصروفات..."):
                result = predict_cost_center_expenses()

            render_ai_response(result)


# =========================================================
# 19. نقطة الدخول الرئيسية
# =========================================================

def show() -> None:
    """
    نقطة الدخول الأساسية للواجهة.

    تحافظ على اسم الدالة show() المستخدم في النسخة الأصلية.
    """

    _apply_design()

    # إنشاء جداول المحادثات إذا لم تكن موجودة.
    try:
        create_ai_tables()
    except Exception as exc:
        st.error(
            f"تعذّر تهيئة جداول المساعد الذكي: {exc}"
        )

    _ensure_session()

    _render_sidebar()
    _render_hero()

    # النموذج محلي فقط.
    model = LOCAL_MODEL_ID

    # التبويبات التسعة الأصلية.
    (
        t1,
        t2,
        t3,
        t4,
        t5,
        t6,
        t7,
        t8,
        t9,
    ) = st.tabs(
        [
            "🧠 المساعد",
            "📊 المحلل المالي",
            "📦 المخزون",
            "👥 الموظفون",
            "📝 القيود",
            "🔍 المراجعة",
            "🔮 التنبؤات",
            "📑 التقرير الشامل",
            "🎯 مراكز التكلفة",
        ]
    )

    # -----------------------------------------------------
    # 1. المساعد الذكي
    # -----------------------------------------------------
    with t1:
        _render_chat_tab(model)

    # -----------------------------------------------------
    # 2. التحليل المالي
    # -----------------------------------------------------
    with t2:
        _render_financial_analysis_tab(model)

    # -----------------------------------------------------
    # 3. المخزون
    # -----------------------------------------------------
    with t3:
        _render_inventory_tab(model)

    # -----------------------------------------------------
    # 4. الموظفون
    # -----------------------------------------------------
    with t4:
        _render_hr_tab(model)

    # -----------------------------------------------------
    # 5. القيود المحاسبية
    # -----------------------------------------------------
    with t5:
        _render_entries_tab()

    # -----------------------------------------------------
    # 6. كشف الشذوذ والمراجعة
    # -----------------------------------------------------
    with t6:
        _render_fraud_tab(model)

    # -----------------------------------------------------
    # 7. التنبؤات
    # -----------------------------------------------------
    with t7:
        _render_forecast_tab(model)

    # -----------------------------------------------------
    # 8. التقرير الشامل
    # -----------------------------------------------------
    with t8:
        _render_board_report_tab(model)

    # -----------------------------------------------------
    # 9. مراكز التكلفة
    # -----------------------------------------------------
    with t9:
        _render_cost_center_tab(model)

    # -----------------------------------------------------
    # التذييل
    # -----------------------------------------------------
    st.markdown(
        f"""
        <div style="
            direction:rtl;
            text-align:center;
            color:{TEXT_MUTED};
            font-size:11px;
            padding:30px 5px 8px;
            border-top:1px solid rgba(212,175,55,.09);
            margin-top:28px;
        ">
            <span style="color:{GOLD}">
                ✦
            </span>
            حوكمة ERP
            <span style="padding:0 7px">|</span>
            المساعد المالي الذكي المحلي
            <span style="padding:0 7px">|</span>
            llama.cpp
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 20. أسماء تشغيل بديلة
# =========================================================

def render_ai_ui() -> None:
    show()


def show_ai_page() -> None:
    show()


def render_ai_page() -> None:
    show()


def ai_page() -> None:
    show()


def main() -> None:
    show()


if __name__ == "__main__":
    show()
