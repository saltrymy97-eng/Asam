# -*- coding: utf-8 -*-
"""
ui/ai_ui.py
=========================================================
حوكمة ERP | AI Enterprise Hub
واجهة المساعد المالي الذكي المحلي.

المحرك:
    llama.cpp

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

try:
    from services import ai_service as _ai_service
    LOCAL_MODEL_ID = getattr(_ai_service, "LOCAL_AI_MODEL", LOCAL_MODEL_ID)
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
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,500,1,0');

/* أساسيات الصفحة */
.stApp {{
    background: radial-gradient(circle at 85% 0%, rgba(155, 138, 251, .075), transparent 28%),
                radial-gradient(circle at 5% 20%, rgba(212, 175, 55, .055), transparent 30%),
                linear-gradient(145deg, {BG_COLOR}, {BG_SECONDARY});
    color: {TEXT_PRIMARY};
}}
html, body, [class*="css"] {{
    font-family: "Segoe UI", "Tahoma", "Arial", sans-serif !important;
}}
.main .block-container {{
    max-width: 1600px;
    padding-top: 1.7rem;
    padding-bottom: 3rem;
}}
[data-testid="stAppViewContainer"] {{ background: transparent; }}

/* Material Icons */
.material-icon {{
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal;
    font-style: normal;
    font-size: 20px;
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
}}

/* الشريط الجانبي */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #10192B 0%, #0A101D 100%);
    border-left: 1px solid rgba(212,175,55,.14);
}}
section[data-testid="stSidebar"] > div {{ padding-top: 1.4rem; }}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{ direction: rtl; text-align: right; }}
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p {{ color: {TEXT_SECONDARY} !important; }}

/* الهيدر الرئيسي */
.ai-hero {{
    position: relative;
    overflow: hidden;
    background: linear-gradient(115deg, #111A2B 0%, #1B2940 58%, #26354C 100%);
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

/* بطاقات المؤشرات */
.ai-metric {{
    background: linear-gradient(145deg, {CARD_BG_LIGHT}, {CARD_BG});
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

/* البطاقات العامة */
.ai-card {{
    background: linear-gradient(145deg, rgba(23,35,55,.97), rgba(14,22,36,.98));
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
    background: linear-gradient(90deg, transparent, rgba(212,175,55,.3), transparent);
    margin: 18px 0;
}}

/* رسائل الحالة */
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

/* الأزرار */
.stButton > button {{
    border-radius: 11px !important;
    border: 1px solid rgba(212,175,55,.32) !important;
    background: linear-gradient(135deg, rgba(212,175,55,.14), rgba(212,175,55,.045)) !important;
    color: {GOLD_LIGHT} !important;
    font-weight: 700 !important;
    min-height: 42px;
    transition: all .22s ease-in-out !important;
}}
.stButton > button:hover {{
    background: linear-gradient(135deg, rgba(212,175,55,.27), rgba(212,175,55,.10)) !important;
    border-color: rgba(212,175,55,.65) !important;
    box-shadow: 0 0 17px {GOLD_GLOW} !important;
    transform: translateY(-1px);
}}
.stButton > button:focus {{
    box-shadow: 0 0 0 2px rgba(212,175,55,.18) !important;
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(110deg, #B58B29, #D4AF37) !important;
    border: 0 !important;
    color: #101522 !important;
    font-weight: 900 !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: linear-gradient(110deg, #D4AF37, #F0D98A) !important;
    color: #080C14 !important;
}}

/* التبويبات */
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

/* الحقول */
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
[data-testid="stChatInput"] textarea {{ color: {TEXT_PRIMARY} !important; }}

/* المحادثة */
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
    background: linear-gradient(145deg, rgba(23,35,55,.9), rgba(14,22,36,.95));
    border: 1px solid {CARD_BORDER};
    border-radius: 18px;
    padding: 28px 20px;
    text-align: center;
    direction: rtl;
    margin: 16px 0;
}}
.ai-chat-empty-icon {{ color: {GOLD}; font-size: 34px; }}
.ai-chat-empty-title {{ color: {TEXT_PRIMARY}; font-weight: 900; font-size: 19px; margin-top: 9px; }}
.ai-chat-empty-text {{ color: {TEXT_SECONDARY}; font-size: 13px; line-height: 2; margin-top: 9px; }}

/* الجداول */
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
hr {{ border-color: rgba(212,175,55,.15) !important; }}
.stCaption {{ color: {TEXT_MUTED} !important; }}
[data-testid="stExpander"] {{
    background: rgba(17,26,43,.65);
    border: 1px solid rgba(212,175,55,.13);
    border-radius: 12px;
}}
.stProgress > div > div {{ background: {GOLD} !important; }}
footer {{ visibility: hidden; }}
#MainMenu {{ visibility: hidden; }}

/* دعم RTL */
.main .block-container {{ direction: rtl; text-align: right; }}
section[data-testid="stSidebar"] {{ direction: rtl; text-align: right; }}
.stMarkdown, .stCaption {{ text-align: right; }}

@media(max-width: 900px) {{
    .ai-hero {{ padding: 22px 19px; }}
    .ai-hero-title {{ font-size: 23px; }}
    .main .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
}}
</style>
"""

# =========================================================
# 4. أدوات عامة
# =========================================================

def _safe_text(value: Any) -> str:
    if value is None: return ""
    if isinstance(value, str): return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(value)

def _safe_html(value: Any) -> str:
    text = str(value or "")
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#x27;"))

def _safe_color(value: Any, default: str = GOLD) -> str:
    value = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", value): return value
    return default

def _money(value: Any) -> str:
    try: return f"{float(value or 0):,.2f}"
    except (TypeError, ValueError): return "—"

def _callable(name: str):
    return getattr(_ai_service, name, None) if _ai_service else None

def _is_empty(value: Any) -> bool:
    if value is None: return True
    if isinstance(value, (list, tuple, dict, str)): return len(value) == 0
    return False

def _to_dataframe(data: Any) -> Optional[pd.DataFrame]:
    if data is None: return None
    try:
        if isinstance(data, pd.DataFrame): return data
        if isinstance(data, (list, tuple)):
            if len(data) == 0: return pd.DataFrame()
            return pd.DataFrame(data)
        if isinstance(data, dict): return pd.DataFrame([data])
    except Exception: return None
    return None

def _display_data(data: Any, empty_message: str = "لا توجد بيانات متاحة للعرض.") -> None:
    if _is_empty(data):
        st.info(empty_message)
        return
    if isinstance(data, pd.DataFrame):
        st.dataframe(data, use_container_width=True, hide_index=True)
        return
    if isinstance(data, (list, tuple)):
        df = _to_dataframe(data)
        if df is not None:
            if not df.empty: st.dataframe(df, use_container_width=True, hide_index=True)
            else: st.info(empty_message)
        else: st.write(data)
        return
    if isinstance(data, dict):
        df = _to_dataframe(data)
        if df is not None and len(data) > 0: st.json(data, expanded=False)
        else: st.write(data)
        return
    st.markdown(_safe_text(data))

def _service_call(function, *args, default=None, **kwargs):
    try: return function(*args, **kwargs)
    except Exception as exc:
        st.error(f"تعذّر تنفيذ العملية: {exc}")
        return default

def _apply_design() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================================================
# 5. مكونات التصميم
# =========================================================

def _render_hero() -> None:
    st.markdown(f"""
<div class="ai-hero">
<div class="ai-hero-badge"><span class="material-icon">auto_awesome</span> AI ENTERPRISE HUB</div>
<div class="ai-hero-title">المساعد المالي الذكي</div>
<div class="ai-hero-subtitle">منصة تحليل ومساعدة مالية متكاملة داخل نظام حوكمة ERP. استكشف مؤشرات الأداء، حلّل الحسابات والمخزون، أنشئ مسودات القيود، وادرس مراكز التكلفة.</div>
<div class="ai-hero-status"><span class="ai-status-dot"></span> يعمل محليًا عبر llama.cpp</div>
</div>
""", unsafe_allow_html=True)

def _section_title(title: str, subtitle: str = "") -> None:
    st.markdown(f"""
<div class="ai-section-title">{_safe_html(title)}</div>
<div class="ai-section-subtitle">{_safe_html(subtitle)}</div>
""", unsafe_allow_html=True)

def _render_metric(label: str, value: Any, note: str = "") -> None:
    st.markdown(f"""
<div class="ai-metric">
<div class="ai-metric-label">{_safe_html(label)}</div>
<div class="ai-metric-value">{_safe_html(value)}</div>
<div class="ai-metric-note">{_safe_html(note)}</div>
</div>
""", unsafe_allow_html=True)

def _render_info(message: str, kind: str = "info") -> None:
    classes = {"info": "ai-info", "success": "ai-success", "warning": "ai-warning"}
    css_class = classes.get(kind, "ai-info")
    st.markdown(f"""
<div class="{css_class}">{_safe_html(message)}</div>
""", unsafe_allow_html=True)

def render_ai_response(content: Any) -> None:
    st.markdown(f"""
<div class="ai-card">
<div class="ai-card-title"><span class="material-icon">analytics</span> تحليل المساعد الذكي</div>
</div>
""", unsafe_allow_html=True)
    if isinstance(content, dict): content = _safe_text(content)
    if content is None:
        st.info("لم يتم إنشاء نتيجة.")
        return
    with st.container(border=True):
        st.markdown(str(content))

# =========================================================
# 6. الاتصال بمحرك الذكاء الاصطناعي المحلي
# =========================================================

def query_local_ai(prompt: str, active_query: str, model: str = LOCAL_MODEL_ID, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    try:
        if not callable(query_groq):
            return "دالة الاتصال بالذكاء الاصطناعي غير متاحة. تحقق من services/ai_service.py."
        result = query_groq(prompt, active_query, model=LOCAL_MODEL_ID, max_tokens=max_tokens)
        if result is None: return "لم يُرجع النموذج نتيجة."
        if isinstance(result, str): return result.strip()
        if isinstance(result, dict):
            for key in ("answer", "response", "content", "message", "text"):
                if result.get(key) is not None: return str(result[key]).strip()
        return _safe_text(result)
    except FileNotFoundError:
        return "لم يتم العثور على ملفات تشغيل llama.cpp أو ملف النموذج. تحقق من المسارات داخل services/ai_service.py."
    except ConnectionError as exc:
        return f"تعذّر الاتصال بمحرك llama.cpp المحلي: {exc}"
    except TimeoutError:
        return "انتهت مهلة انتظار النموذج. جرّب تقليل طول السؤال أو استخدام نموذج أصغر."
    except Exception as exc:
        return f"حدث خطأ أثناء الاتصال بمحرك الذكاء الاصطناعي: {exc}"

def _make_prompt(data: Any, task: str, instructions: str) -> str:
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
    if "active_session" not in st.session_state:
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []
    if "ai_history_loaded" not in st.session_state:
        st.session_state.ai_history_loaded = False

def _new_chat() -> None:
    st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    st.session_state.ai_messages = []
    st.session_state.ai_history_loaded = True

def _normalize_history_item(item: Any) -> Optional[Dict[str, str]]:
    role = None
    content = None
    if isinstance(item, dict):
        role = item.get("role") or item.get("sender") or item.get("message_role") or "assistant"
        content = item.get("content") or item.get("message") or item.get("text") or item.get("response") or ""
    elif isinstance(item, (tuple, list)):
        if len(item) >= 2:
            role = item[-2]
            content = item[-1]
    if content is None: return None
    role = str(role or "assistant").lower().strip()
    if role not in ("user", "assistant", "system"): role = "assistant"
    return {"role": role, "content": str(content)}

def _load_chat_history(session_id: str) -> List[Dict[str, str]]:
    try:
        raw_history = get_chat_history(session_id)
    except TypeError:
        try: raw_history = get_chat_history(session_id=session_id)
        except Exception: return []
    except Exception: return []
    messages = []
    if isinstance(raw_history, dict):
        raw_history = raw_history.get("messages", raw_history.get("data", []))
    if not isinstance(raw_history, (list, tuple)): return []
    for item in raw_history:
        normalized = _normalize_history_item(item)
        if normalized: messages.append(normalized)
    return messages

def _load_current_history() -> None:
    if st.session_state.ai_history_loaded: return
    session_id = st.session_state.active_session
    st.session_state.ai_messages = _load_chat_history(session_id)
    st.session_state.ai_history_loaded = True

def _save_history(session_id: str, role: str, content: str, model: str = LOCAL_MODEL_ID, category: str = CHAT_CATEGORY) -> None:
    try:
        save_chat_history(session_id, role, content, model, category)
    except TypeError:
        try: save_chat_history(session_id, role, content)
        except Exception as exc: st.warning(f"تعذّر حفظ المحادثة: {exc}")
    except Exception as exc:
        st.warning(f"تعذّر حفظ المحادثة: {exc}")

def _get_sessions() -> List[Any]:
    try:
        sessions = get_chat_sessions()
        if isinstance(sessions, list): return sessions
        if isinstance(sessions, tuple): return list(sessions)
        return []
    except Exception:
        return []

def _session_details(item: Any, index: int) -> Tuple[str, str]:
    if isinstance(item, dict):
        session_id = item.get("session_id") or item.get("chat_id") or item.get("id")
        title = item.get("title") or item.get("name") or item.get("first_message") or f"محادثة {index + 1}"
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
    with st.sidebar:
        st.markdown(f"""
<div style="direction:rtl;text-align:right;padding:8px 4px 19px;">
<div style="color:{TEXT_PRIMARY};font-size:26px;font-weight:900;">حوكمة <span style="color:{GOLD}">AI</span></div>
<div style="color:{TEXT_MUTED};font-size:11px;margin-top:5px;">ENTERPRISE INTELLIGENCE</div>
</div>
""", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"""
<div style="color:{GOLD_LIGHT};font-size:14px;font-weight:800;text-align:right;direction:rtl;margin-bottom:10px;">
<span class="material-icon">settings</span> إعدادات المحرك
</div>
""", unsafe_allow_html=True)
        st.selectbox("المحرك المستخدم", options=[LOCAL_MODEL_LABEL], index=0, disabled=True, key="local_ai_engine")
        st.caption(f"معرف النموذج المحلي: {LOCAL_MODEL_ID}")
        st.markdown("---")
        if st.button("محادثة جديدة", key="new_ai_chat", use_container_width=True, type="primary", icon=":material/add:"):
            _new_chat()
            st.rerun()
        st.markdown(f"""
<div style="color:{TEXT_PRIMARY};font-weight:800;font-size:13px;text-align:right;direction:rtl;margin:18px 0 10px;">
<span class="material-icon">chat</span> المحادثات السابقة
</div>
""", unsafe_allow_html=True)
        sessions = _get_sessions()
        if not sessions:
            st.caption("لا توجد محادثات سابقة.")
        else:
            session_map = {}
            for index, item in enumerate(sessions[:25]):
                session_id, title = _session_details(item, index)
                if not session_id: continue
                short_title = title[:34]
                session_map[f"{short_title} · {session_id[-6:]}"] = session_id
            if session_map:
                labels = list(session_map.keys())
                selected_label = st.selectbox("اختر محادثة", options=labels, index=None, placeholder="حدد محادثة سابقة...", label_visibility="collapsed", key="ai_old_session_selector")
                if selected_label:
                    selected_session = session_map[selected_label]
                    if selected_session != st.session_state.active_session:
                        st.session_state.active_session = selected_session
                        st.session_state.ai_history_loaded = False
                        st.session_state.ai_messages = []
                        st.rerun()
        st.markdown("---")
        st.markdown(f"""
<div style="direction:rtl;text-align:right;line-height:2;font-size:11px;color:{TEXT_MUTED};">
<b style="color:{GOLD_LIGHT}">حالة التشغيل</b><br>
<span style="color:{ACCENT_GREEN}">●</span> محرك محلي<br>
لا يوجد اتصال بـ Groq من هذه الواجهة.<br>
لا يلزم مفتاح API سحابي.
</div>
""", unsafe_allow_html=True)

# =========================================================
# 9. معالجة الصوت محليًا
# =========================================================

def audio_to_text(audio_file) -> str:
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
            extension = os.path.splitext(str(audio_file.name))[1]
            if extension:
                suffix = extension

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
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

    with st.spinner("جاري التفريغ الصوتي محليًا..."):
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

    st.markdown("""
<div class="ai-card">
<div class="ai-card-title"><span class="material-icon">lightbulb</span> كيف يمكنني مساعدتك؟</div>
<div class="ai-card-caption">
تحليل الأداء المالي، تفسير النسب، متابعة المصروفات، فهم المخزون، مراجعة القيود، ودراسة المؤشرات التشغيلية.
</div>
</div>
""", unsafe_allow_html=True)

    voice_text = audio_input_widget(key="assistant_audio")

    for message in st.session_state.ai_messages:
        role = message.get("role", "assistant")
        content = message.get("content", "")

        if role not in ("user", "assistant"):
            continue

        avatar = "👤" if role == "user" else "✦"

        with st.chat_message(role, avatar=avatar):
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

    st.session_state.ai_messages.append({"role": "user", "content": active_query})

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
        with st.spinner("جاري تحليل البيانات محليًا..."):

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

    st.session_state.ai_messages.append({"role": "assistant", "content": answer})

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

    st.markdown("""
<div class="ai-card">
<div class="ai-card-title"><span class="material-icon">bar_chart</span> التحليل المالي الشامل</div>
<div class="ai-card-caption">
يستخدم التحليل الإيرادات والمصروفات وصافي الدخل والنسب المالية المتاحة في قاعدة البيانات.
</div>
</div>
""", unsafe_allow_html=True)

    if st.button(
        "بدء التحليل المالي الشامل",
        type="primary",
        use_container_width=True,
        key="run_financial_analysis",
        icon=":material/rocket_launch:",
    ):

        with st.spinner("جاري استخراج المؤشرات وتحليلها..."):

            data = get_comprehensive_data()
            ratios = get_financial_ratios()

            revenue = data.get("revenue", 0) if isinstance(data, dict) else 0
            expenses = data.get("expenses", 0) if isinstance(data, dict) else 0
            net_income = data.get("net_income", 0) if isinstance(data, dict) else 0

            st.markdown("### المؤشرات الأساسية")

            c1, c2, c3 = st.columns(3)

            with c1:
                _render_metric("الإيرادات", _money(revenue), "وفق البيانات المتاحة")

            with c2:
                _render_metric("المصروفات", _money(expenses), "وفق البيانات المتاحة")

            with c3:
                _render_metric("صافي الدخل", _money(net_income), "وفق البيانات المتاحة")

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
        "تحميل وتحليل المخزون",
        type="primary",
        use_container_width=True,
        key="inventory_analysis",
        icon=":material/inventory_2:",
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
            _render_metric("عدد الأصناف المتاحة في البيانات", len(all_products), "إجمالي المنتجات المسترجعة")

        with c2:
            _render_metric("الأصناف تحت الحد الأدنى", len(low), "تحتاج إلى مراجعة")

        if low:
            _render_info(f"يوجد {len(low)} صنفًا تحت الحد الأدنى للطلب.", "warning")
            st.markdown("#### الأصناف الحرجة")
            _display_data(low)
        else:
            _render_info("لم يتم إرجاع أصناف تحت الحد الأدنى من المخزون.", "success")

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

            with st.spinner("جاري تحليل المخزون..."):
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
            icon=":material/search:",
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

    if not isinstance(employee, dict): employee = {}
    if not isinstance(salary, dict): salary = {}

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
        "المخرجات مسودة للمراجعة فقط. لا يتم اعتماد القيد أو ترحيله إلى الأستاذ العام تلقائيًا من هذه الواجهة.",
        "warning",
    )

    operations = get_available_operations()

    if not operations:
        st.warning("لا توجد أنواع عمليات متاحة في الخدمة.")
        return

    selected_op = st.selectbox(
        "اختر نوع العملية المالية",
        options=operations,
        key="ai_entry_operation",
    )

    operation_description = get_operation_description(selected_op)

    st.markdown(f"""
<div class="ai-info">
<b>وصف العملية</b><br>
{_safe_html(operation_description)}
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    total_amount = 0.0
    cash_amount = None
    credit_amount = None
    vat_rate = None
    expense_name = None
    adjustment_side = None
    inventory_side = None

    if is_mixed_operation(selected_op):
        st.markdown("#### تفاصيل العملية المختلطة")
        c1, c2, c3 = st.columns(3)
        with c1:
            total_amount = st.number_input("إجمالي المبلغ", min_value=0.0, step=100.0, key="mixed_total")
        with c2:
            cash_amount = st.number_input("المبلغ النقدي", min_value=0.0, step=100.0, key="mixed_cash")
        with c3:
            credit_amount = st.number_input("المبلغ الآجل", min_value=0.0, step=100.0, key="mixed_credit")
            
    elif is_vat_operation(selected_op):
        st.markdown("#### تفاصيل العملية مع الضريبة")
        c1, c2 = st.columns(2)
        with c1:
            total_amount = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=100.0, key="vat_total")
        with c2:
            vat_rate = st.number_input("نسبة الضريبة (%)", min_value=0.0, value=15.0, step=1.0, key="vat_rate")
            
    elif is_inventory_adjustment(selected_op):
        st.markdown("#### تفاصيل التسوية المخزنية")
        c1, c2 = st.columns(2)
        with c1:
            total_amount = st.number_input("قيمة التسوية", min_value=0.0, step=100.0, key="adj_amount")
        with c2:
            adjustment_side = st.selectbox("نوع التسوية", ["زيادة (جرد)", "نقص (عجز)"], key="adj_side")
            
    elif is_salary_operation(selected_op):
        st.markdown("#### تفاصيل الرواتب")
        c1, c2 = st.columns(2)
        with c1:
            total_amount = st.number_input("إجمالي الرواتب", min_value=0.0, step=100.0, key="salary_total")
        with c2:
            expense_name = st.text_input("اسم حساب الرواتب", value="مصروف الرواتب", key="salary_expense")
            
    else:
        st.markdown("#### تفاصيل العملية")
        total_amount = st.number_input("المبلغ", min_value=0.0, step=100.0, key="simple_amount")
        if selected_op == "سداد مصروف":
            expense_name = st.text_input("اسم حساب المصروف", value="مصروفات عمومية", key="simple_expense")

    st.markdown("---")

    if st.button("توليد القيد", type="primary", use_container_width=True, key="generate_entry_btn", icon=":material/receipt_long:"):
        with st.spinner("جاري توليد القيد..."):
            entry_data, display_text, confidence, conf_label, conf_color = generate_template_entry(
                operation_type=selected_op,
                amount=total_amount,
                cash_amount=cash_amount,
                credit_amount=credit_amount,
                expense_name=expense_name,
                vat_rate=vat_rate,
                adjustment_side=adjustment_side,
                inventory_side=inventory_side
            )

            if entry_data:
                st.markdown("### مسودة القيد")
                st.markdown(f"""
<div class="ai-card">
<div class="ai-card-title">نتيجة التوليد</div>
<div class="ai-card-caption" style="white-space: pre-wrap; font-family: monospace; direction: ltr; text-align: left;">
{_safe_html(display_text)}
</div>
<div style="margin-top: 15px;">
<span style="background: {conf_color}22; color: {conf_color}; padding: 5px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;">
مستوى الثقة: {confidence}% ({conf_label})
</span>
</div>
</div>
""", unsafe_allow_html=True)
            else:
                st.error(display_text)


# =========================================================
# 15. الدالة الرئيسية للواجهة
# =========================================================

def show() -> None:
    _ensure_session()
    _apply_design()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        ":material/psychology: المساعد الذكي",
        ":material/bar_chart: المحلل المالي",
        ":material/inventory_2: المخزون",
        ":material/badge: الموظفون",
        ":material/edit_note: توليد القيود",
    ])

    with tab1:
        _render_hero()
        _render_sidebar()
        _render_chat_tab(LOCAL_MODEL_ID)

    with tab2:
        _render_sidebar()
        _render_financial_analysis_tab(LOCAL_MODEL_ID)

    with tab3:
        _render_sidebar()
        _render_inventory_tab(LOCAL_MODEL_ID)

    with tab4:
        _render_sidebar()
        _render_hr_tab(LOCAL_MODEL_ID)

    with tab5:
        _render_sidebar()
        _render_entries_tab()
