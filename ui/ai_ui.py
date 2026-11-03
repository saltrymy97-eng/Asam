# -*- coding: utf-8 -*-
"""ui/ai_ui.py - Hokama ERP local AI workspace.

AI-generated text is rendered with st.write()/st.text(), not st.markdown().
The HTML/CSS blocks below are limited to short, static presentation elements.
"""
from __future__ import annotations

import inspect
import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from services import ai_service as _ai_service
from services.ai_service import (
    LOCAL_AI_MODEL,
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
    get_financial_snapshot,
    get_inventory_snapshot,
    get_hr_snapshot,
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


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
LOCAL_MODEL_ID = LOCAL_AI_MODEL
LOCAL_MODEL_LABEL = "llama.cpp | نموذج محلي"
CHAT_CATEGORY = "مساعد"
DEFAULT_MAX_TOKENS = 256
MAX_CONTEXT_CHARS = 4500

SYSTEM_ROLE = """أنت المساعد المالي والإداري المحلي لنظام حوكمة ERP.
أجب بالعربية المهنية الواضحة وبعبارات مباشرة.
اعتمد على البيانات التي أرسلها النظام فقط، ولا تخترع أرقاماً أو أرصدة أو أسماء.
افصل بين البيانات الفعلية والتقديرات والتوصيات.
لا تدّعِ أنك نفذت قيداً أو عدّلت قاعدة البيانات.
إن لم تكفِ البيانات، اذكر ذلك بوضوح واطلب المعلومة الناقصة.
نموذجك صغير؛ اجعل الإجابة مركزة ومنظمة دون إطالة غير ضرورية."""

# Theme colors
BG = "#080C14"
PANEL = "#111A2B"
PANEL_ALT = "#172337"
GOLD = "#D4AF37"
GOLD_LIGHT = "#F0D98A"
TEXT = "#F8FAFC"
MUTED = "#A5B1C4"
GREEN = "#10B981"
BLUE = "#60A5FA"
RED = "#F87171"

CUSTOM_CSS = f"""
<style>
.stApp {{ background: radial-gradient(circle at 85% 0%, rgba(155,138,251,.07), transparent 28%), linear-gradient(145deg,{BG},#0D1422); color:{TEXT}; }}
html, body, [class*="css"] {{ font-family: "Segoe UI", Tahoma, Arial, sans-serif !important; }}
.main .block-container {{ max-width: 1500px; padding-top: 1.3rem; padding-bottom: 2.5rem; direction: rtl; text-align: right; }}
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg,#10192B,#0A101D); border-left:1px solid rgba(212,175,55,.16); direction:rtl; }}
.ai-hero {{ background:linear-gradient(115deg,#111A2B,#1B2940 58%,#26354C); border:1px solid rgba(212,175,55,.22); border-radius:20px; padding:25px 28px; margin-bottom:18px; direction:rtl; text-align:right; overflow-wrap:break-word; white-space:pre-wrap; }}
.ai-hero-title {{ font-size:27px; font-weight:900; color:{TEXT}; margin:5px 0; }}
.ai-hero-sub {{ font-size:13px; color:{MUTED}; line-height:1.9; }}
.ai-tag {{ display:inline-block; padding:5px 10px; border-radius:9px; color:{GOLD_LIGHT}; background:rgba(212,175,55,.10); border:1px solid rgba(212,175,55,.25); font-size:11px; font-weight:800; }}
.ai-metric {{ background:linear-gradient(145deg,{PANEL_ALT},{PANEL}); border:1px solid rgba(212,175,55,.18); border-radius:14px; padding:15px; min-height:96px; direction:rtl; text-align:right; overflow-wrap:break-word; }}
.ai-metric-label {{ color:{MUTED}; font-size:12px; margin-bottom:9px; }}
.ai-metric-value {{ color:{GOLD_LIGHT}; font-size:22px; font-weight:900; direction:ltr; text-align:right; }}
.ai-card {{ background:linear-gradient(145deg,rgba(23,35,55,.96),rgba(14,22,36,.98)); border:1px solid rgba(212,175,55,.18); border-radius:14px; padding:15px 17px; margin:9px 0; direction:rtl; text-align:right; overflow-wrap:break-word; white-space:pre-wrap; }}
.ai-title {{ color:{GOLD_LIGHT}; font-weight:800; font-size:15px; margin-bottom:5px; }}
.ai-caption {{ color:{MUTED}; font-size:12px; line-height:1.9; }}
.ai-info {{ border-right:4px solid {BLUE}; background:rgba(96,165,250,.08); border-radius:10px; padding:11px 14px; color:#D4E5FA; direction:rtl; text-align:right; overflow-wrap:break-word; white-space:pre-wrap; }}
.ai-warning {{ border-right:4px solid {GOLD}; background:rgba(212,175,55,.08); border-radius:10px; padding:11px 14px; color:#F0DEA7; direction:rtl; text-align:right; overflow-wrap:break-word; white-space:pre-wrap; }}
.stButton > button {{ border-radius:10px !important; border:1px solid rgba(212,175,55,.34) !important; background:linear-gradient(135deg,rgba(212,175,55,.15),rgba(212,175,55,.04)) !important; color:{GOLD_LIGHT} !important; font-weight:700 !important; min-height:40px; }}
.stButton > button[kind="primary"] {{ background:linear-gradient(110deg,#B58B29,{GOLD}) !important; color:#101522 !important; border:0 !important; font-weight:900 !important; }}
.stTextInput input, .stNumberInput input, .stTextArea textarea {{ background:{PANEL} !important; color:{TEXT} !important; border:1px solid #2A3952 !important; border-radius:9px !important; }}
[data-testid="stChatInput"] {{ border:1px solid rgba(212,175,55,.3) !important; border-radius:13px !important; background:{PANEL} !important; }}
[data-testid="stChatMessage"] {{ background:rgba(17,26,43,.82) !important; border:1px solid rgba(212,175,55,.13); border-radius:13px !important; padding:10px 14px !important; margin-bottom:9px !important; overflow-wrap:break-word; white-space:pre-wrap; }}
[data-testid="stChatMessage"] p {{ line-height:1.9; overflow-wrap:break-word; }}
div[data-baseweb="tab-list"] {{ gap:6px; border-bottom:1px solid rgba(212,175,55,.16); }}
button[data-baseweb="tab"] {{ border-radius:9px 9px 4px 4px !important; background:rgba(23,35,55,.8) !important; color:{MUTED} !important; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:{GOLD_LIGHT} !important; border-bottom:2px solid {GOLD} !important; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border:1px solid rgba(212,175,55,.15); border-radius:10px; overflow:hidden; }}
[data-testid="stExpander"] {{ background:rgba(17,26,43,.6); border:1px solid rgba(212,175,55,.13); border-radius:10px; }}
.stCaption {{ color:#8794A8 !important; }}
footer, #MainMenu {{ visibility:hidden; }}
@media(max-width:900px) {{ .ai-hero {{ padding:18px; }} .ai-hero-title {{ font-size:22px; }} .main .block-container {{ padding-left:.8rem; padding-right:.8rem; }} }}
</style>
"""


# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------
def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(value)


def _safe_html(value: Any) -> str:
    text = str(value or "")
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;")
            .replace("'", "&#x27;"))


def _money(value: Any) -> str:
    try:
        return f"{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _compact_json(data: Any, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    text = _safe_text(data)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[تم اختصار البيانات لتناسب النموذج المحلي]"
    return text


def _to_dataframe(data: Any) -> Optional[pd.DataFrame]:
    if data is None:
        return None
    try:
        if isinstance(data, pd.DataFrame):
            return data
        if isinstance(data, (list, tuple)):
            return pd.DataFrame(data)
        if isinstance(data, dict):
            return pd.DataFrame([data])
    except Exception:
        return None
    return None


def _display_data(data: Any, empty_message: str = "لا توجد بيانات متاحة للعرض.") -> None:
    if data is None:
        st.info(empty_message)
        return
    if isinstance(data, pd.DataFrame):
        st.dataframe(data, width="stretch", hide_index=True)
        return
    if isinstance(data, (list, tuple)):
        if not data:
            st.info(empty_message)
            return
        df = _to_dataframe(data)
        if df is not None and not df.empty:
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info(empty_message)
        return
    if isinstance(data, dict):
        if not data:
            st.info(empty_message)
            return
        st.json(data, expanded=False)
        return
    # Long/plain text and model output are never sent through st.markdown().
    st.write(str(data))


def _service_call(function, *args, default=None, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        st.error(f"تعذّر تنفيذ العملية: {exc}")
        return default


def _apply_design() -> None:
    # This markdown call contains CSS only, not user/model text.
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _section_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="ai-title">{_safe_html(title)}</div>'
        f'<div class="ai-caption">{_safe_html(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    status = _service_call(_ai_service.get_model_status, default={}) or {}
    model_name = os.path.basename(status.get("model_path", "TinyLlama model"))
    loaded = status.get("loaded", False)
    state = "تم تحميل النموذج" if loaded else "سيتم تحميل النموذج عند أول سؤال"
    st.markdown(
        '<div class="ai-hero">'
        '<span class="ai-tag">HOKAMA ERP · LOCAL AI</span>'
        '<div class="ai-hero-title">المساعد المالي الذكي</div>'
        '<div class="ai-hero-sub">تحليل مالي وتشغيلي محلي، مع إبقاء بيانات المنشأة داخل الجهاز. '
        'المخرجات استشارية وتحتاج إلى مراجعة بشرية قبل اتخاذ القرارات أو اعتماد القيود.</div>'
        f'<div class="ai-caption">النموذج: {_safe_html(model_name)} · {_safe_html(state)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    warning = status.get("quantization_warning")
    family_warning = status.get("model_family_warning")
    if warning:
        st.warning(
            "تنبيه جودة النموذج: " + warning + ". تحسين الكود لا يعوض فقدان الجودة الناتج عن الضغط الشديد."
        )
    if family_warning:
        st.warning("تنبيه نوع النموذج: " + family_warning)
    if not status.get("exists", False):
        st.error("لم يتم العثور على ملف النموذج. المسار المتوقع: " + str(status.get("model_path", "")))


def _render_metric(label: str, value: Any, note: str = "") -> None:
    st.markdown(
        f'<div class="ai-metric"><div class="ai-metric-label">{_safe_html(label)}</div>'
        f'<div class="ai-metric-value">{_safe_html(value)}</div>'
        f'<div class="ai-caption">{_safe_html(note)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_info(message: str, kind: str = "info") -> None:
    cls = "ai-warning" if kind == "warning" else "ai-info"
    st.markdown(f'<div class="{cls}">{_safe_html(message)}</div>', unsafe_allow_html=True)


def render_ai_response(content: Any) -> None:
    st.markdown('<div class="ai-title">نتيجة تحليل المساعد</div>', unsafe_allow_html=True)
    if content is None:
        st.info("لم يتم إنشاء نتيجة.")
        return
    # Important: render the complete AI response as plain Streamlit output.
    with st.container(border=True):
        st.write(_safe_text(content))


# ---------------------------------------------------------------------
# Inference wrapper / context assembly
# ---------------------------------------------------------------------
def query_local_ai(prompt: str, active_query: str = "", model: str = LOCAL_MODEL_ID,
                   max_tokens: int = DEFAULT_MAX_TOKENS, history=None) -> str:
    """Backward-compatible wrapper around ai_service.query_groq()."""
    try:
        if not callable(query_groq):
            return "دالة الاتصال بمحرك الذكاء الاصطناعي غير متاحة."
        result = query_groq(
            prompt or SYSTEM_ROLE,
            active_query or prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=0.2,
            history=history,
        )
        if result is None:
            return "لم يُرجع النموذج نتيجة."
        if isinstance(result, str):
            return result.strip()
        if isinstance(result, dict):
            for key in ("answer", "response", "content", "message", "text"):
                if result.get(key) is not None:
                    return str(result[key]).strip()
        return _safe_text(result)
    except Exception as exc:
        return f"حدث خطأ أثناء الاتصال بمحرك الذكاء الاصطناعي المحلي: {exc}"


def _make_prompt(data: Any, task: str, instructions: str) -> str:
    return (
        "بيانات نظام حوكمة ERP (قد تكون مختصرة):\n" + _compact_json(data)
        + "\n\nالمهمة: " + str(task)
        + "\n\nالمطلوب: " + str(instructions)
        + "\n\nاعتمد على البيانات أعلاه فقط، وصرّح بأي نقص."
    )


def _callable_service(name: str):
    return getattr(_ai_service, name, None)


def audio_to_text(audio_file) -> str:
    """Use an optional local transcription function if the service provides one."""
    if audio_file is None:
        return ""
    function = None
    for name in ("audio_to_text_local", "transcribe_audio_local", "transcribe_audio"):
        candidate = _callable_service(name)
        if callable(candidate):
            function = candidate
            break
    if function is None:
        return "التفريغ الصوتي غير مهيأ. يلزم ربط whisper.cpp محلياً داخل ai_service.py."
    suffix = os.path.splitext(str(getattr(audio_file, "name", "recording.wav")))[1] or ".wav"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            temp_path = handle.name
            handle.write(audio_file.getbuffer())
        parameters = inspect.signature(function).parameters
        result = function(temp_path) if parameters else function()
        if isinstance(result, dict):
            return str(result.get("text") or result.get("transcription") or result.get("content") or "")
        return str(result or "")
    except Exception as exc:
        return f"تعذر تفريغ الصوت محلياً: {exc}"
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def audio_input_widget(key: str = "assistant_audio") -> str:
    """Optional microphone widget; remains inactive until a local STT backend exists."""
    available = any(callable(_callable_service(name)) for name in
                    ("audio_to_text_local", "transcribe_audio_local", "transcribe_audio"))
    if not available or not hasattr(st, "audio_input"):
        st.caption("الإدخال الصوتي غير مفعّل حالياً؛ يمكن استخدام المحادثة النصية.")
        return ""
    audio = st.audio_input("تسجيل صوتي", key=key, label_visibility="collapsed")
    if audio is None:
        return ""
    with st.spinner("جاري التفريغ الصوتي محلياً..."):
        return audio_to_text(audio)


def _get_chat_context(question: str) -> str:
    """Fetch only a compact, relevant snapshot instead of the entire ERP DB."""
    q = (question or "").lower()
    parts: Dict[str, Any] = {}
    inventory_words = ("مخزون", "مخزن", "مخازن", "منتج", "منتجات", "كمية", "نفد", "الأصناف")
    finance_words = ("مالي", "مالية", "إيراد", "إيرادات", "مصروف", "مصروفات", "ربح", "ربحية", "أصول", "التزامات", "ميزانية", "مديونية", "حساب")
    business_words = ("عميل", "عملاء", "مورد", "موردين", "مبيعات", "مشتريات", "فاتورة")
    hr_words = ("موظف", "موظفين", "موارد بشرية", "رواتب", "راتب")

    try:
        if any(word in q for word in inventory_words):
            low, products = get_inventory_data()
            parts["الأصناف منخفضة المخزون"] = low[:8]
            parts["عينة المنتجات"] = products[:8]
        elif any(word in q for word in business_words):
            parts["ملخص العملاء والموردين"] = get_business_snapshot()
            parts["اتجاه المبيعات"] = get_trend_analysis()[:4]
        elif any(word in q for word in hr_words):
            parts["ملخص الموارد البشرية"] = get_hr_snapshot()
        elif any(word in q for word in finance_words):
            parts["المؤشرات المالية"] = get_financial_snapshot()
        else:
            financial = get_financial_snapshot()
            inventory = get_inventory_snapshot()
            business = get_business_snapshot()
            parts = {
                "ملخص مالي": {k: financial.get(k) for k in
                              ("revenue", "expenses", "net_income", "assets", "liabilities", "profit_margin", "debt_ratio")},
                "ملخص المخزون": {k: inventory.get(k) for k in
                                 ("total_products", "low_stock_count")},
                "ملخص الأعمال": {k: business.get(k) for k in
                                 ("total_customers", "total_suppliers")},
            }
    except Exception as exc:
        parts["تعذر استخراج السياق"] = str(exc)
    return _compact_json(parts, 3000)


# ---------------------------------------------------------------------
# Chat history/session management
# ---------------------------------------------------------------------
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


def _load_chat_history(session_id: str) -> List[Dict[str, str]]:
    try:
        raw = get_chat_history(session_id=session_id, limit=40)
    except Exception:
        return []
    result = []
    for item in raw or []:
        role = str(item.get("role", "assistant")).lower()
        content = str(item.get("content", ""))
        if role in ("user", "assistant") and content:
            result.append({"role": role, "content": content})
    return result


def _load_current_history() -> None:
    if not st.session_state.ai_history_loaded:
        st.session_state.ai_messages = _load_chat_history(st.session_state.active_session)
        st.session_state.ai_history_loaded = True


def _save_history(session_id: str, role: str, content: str) -> None:
    try:
        save_chat_history(session_id, role, content, LOCAL_MODEL_ID, CHAT_CATEGORY)
    except Exception as exc:
        st.warning(f"تعذّر حفظ المحادثة: {exc}")


def _get_sessions() -> List[Any]:
    try:
        return get_chat_sessions() or []
    except Exception:
        return []


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f'<div style="direction:rtl;text-align:right;padding:8px 3px 15px;">'
            f'<div style="color:{TEXT};font-size:24px;font-weight:900;">حوكمة '
            f'<span style="color:{GOLD}">AI</span></div>'
            f'<div style="color:#718096;font-size:10px;">LOCAL ENTERPRISE INTELLIGENCE</div></div>',
            unsafe_allow_html=True,
        )
        status = _service_call(_ai_service.get_model_status, default={}) or {}
        st.caption("النموذج: " + os.path.basename(status.get("model_path", "غير محدد")))
        st.caption("الحالة: محمّل" if status.get("loaded") else "الحالة: تحميل عند أول استخدام")
        if st.button("محادثة جديدة", key="new_ai_chat", width="stretch", type="primary"):
            _new_chat()
            st.rerun()
        st.markdown("---")
        st.markdown("**المحادثات السابقة**")
        sessions = _get_sessions()
        session_map: Dict[str, str] = {}
        for index, item in enumerate(sessions[:25]):
            if isinstance(item, dict):
                sid = str(item.get("session_id") or "")
                label = str(item.get("first_message") or f"محادثة {index + 1}")
            else:
                continue
            if sid:
                session_map[f"{label[:28]} · {sid[-6:]}"] = sid
        if session_map:
            selected = st.selectbox(
                "اختر محادثة محفوظة", list(session_map.keys()), index=None,
                placeholder="حدد محادثة...", label_visibility="collapsed",
                key="ai_old_session_selector",
            )
            if selected:
                sid = session_map[selected]
                if sid != st.session_state.active_session:
                    st.session_state.active_session = sid
                    st.session_state.ai_history_loaded = False
                    st.session_state.ai_messages = []
                    st.rerun()
        else:
            st.caption("لا توجد محادثات سابقة.")
        st.markdown("---")
        st.caption("تشغيل محلي عبر llama.cpp · لا يحتاج مفتاح API")


# ---------------------------------------------------------------------
# Chat tab
# ---------------------------------------------------------------------
def _render_chat_tab(model: str) -> None:
    _section_title("المساعد الذكي", "اسأل عن المؤشرات والبيانات التشغيلية بلغة طبيعية.")
    _load_current_history()
    st.markdown(
        '<div class="ai-card"><div class="ai-title">كيف يمكنني مساعدتك؟</div>'
        '<div class="ai-caption">التحليل المالي، المخزون، المبيعات، العملاء، الموردون، '
        'الموارد البشرية، ومراجعة المؤشرات المتاحة.</div></div>',
        unsafe_allow_html=True,
    )
    voice_text = audio_input_widget(key="assistant_audio")
    for message in st.session_state.ai_messages:
        role = message.get("role", "assistant")
        if role not in ("user", "assistant"):
            continue
        with st.chat_message(role):
            st.write(message.get("content", ""))

    question = st.chat_input("اكتب سؤالك المالي أو التشغيلي هنا...", key="ai-chat-input")
    active_query = (voice_text or question or "").strip()
    if not active_query:
        return
    st.session_state.ai_messages.append({"role": "user", "content": active_query})
    _save_history(st.session_state.active_session, "user", active_query)

    try:
        with st.spinner("يجري تجهيز البيانات والإجابة محلياً..."):
            context = _get_chat_context(active_query)
            user_payload = (
                "السياق المتاح من قاعدة بيانات النظام:\n" + context
                + "\n\nسؤال المستخدم:\n" + active_query
                + "\n\nأجب بإيجاز ودقة، واذكر إن كانت البيانات غير كافية."
            )
            history = st.session_state.ai_messages[-5:-1]
            answer = query_local_ai(SYSTEM_ROLE, user_payload, model, 240, history=history)
    except Exception as exc:
        answer = f"حدث خطأ أثناء تجهيز الإجابة: {exc}"

    st.session_state.ai_messages.append({"role": "assistant", "content": answer})
    _save_history(st.session_state.active_session, "assistant", answer)
    st.rerun()


# ---------------------------------------------------------------------
# Financial analysis
# ---------------------------------------------------------------------
def _render_financial_analysis_tab(model: str) -> None:
    _section_title("التحليل المالي والنسب", "مؤشرات مالية مستخرجة من قاعدة بيانات النظام.")
    if not st.button("بدء التحليل المالي", type="primary", width="stretch", key="run_financial_analysis"):
        return
    with st.spinner("جاري استخراج المؤشرات وتحليلها..."):
        data = get_financial_snapshot()
        ratios = get_financial_ratios()
        cols = st.columns(3)
        metrics = [("الإيرادات", data.get("revenue")), ("المصروفات", data.get("expenses")), ("صافي الدخل", data.get("net_income"))]
        for col, (label, value) in zip(cols, metrics):
            with col:
                _render_metric(label, _money(value))
        prompt = _make_prompt(
            {"المؤشرات": data, "النسب": ratios},
            "إعداد تحليل مالي مختصر",
            "اكتب خلاصة تنفيذية، واشرح النسب المتاحة، وحدد المخاطر والتوصيات. لا تضف معايير مقارنة من عندك.",
        )
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 300)
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------
def _render_inventory_tab(model: str) -> None:
    _section_title("تحليل المخزون", "تحديد الأصناف تحت حد إعادة الطلب ومراجعة كميات المخزون.")
    if not st.button("تحميل وتحليل المخزون", type="primary", width="stretch", key="inventory_analysis"):
        return
    with st.spinner("جاري تحميل بيانات المخزون..."):
        low, products = get_inventory_data()
    low, products = low or [], products or []
    cols = st.columns(2)
    with cols[0]:
        _render_metric("الأصناف في العينة", len(products))
    with cols[1]:
        _render_metric("أصناف تحت حد الطلب", len(low))
    if low:
        _render_info(f"يوجد {len(low)} صنفاً تحت حد إعادة الطلب.", "warning")
        st.write("الأصناف الحرجة")
        _display_data(low)
    else:
        st.success("لم تُرجع البيانات أصنافاً تحت حد إعادة الطلب.")
    if products:
        st.write("بيانات المنتجات")
        _display_data(products)
        prompt = _make_prompt(
            {"الأصناف منخفضة المخزون": low, "المنتجات": products},
            "تحليل المخزون",
            "حدد الأصناف التي تحتاج متابعة، ومخاطر نفاد المخزون، وتوصيات إعادة الطلب. لا تخترع معدل دوران أو قيمة مخزون.",
        )
        with st.spinner("جاري تحليل النتائج..."):
            answer = query_local_ai(SYSTEM_ROLE, prompt, model, 280)
        render_ai_response(answer)
    else:
        st.info("لا توجد بيانات منتجات كافية للتحليل.")


# ---------------------------------------------------------------------
# Human resources query
# ---------------------------------------------------------------------
def _render_hr_tab(model: str) -> None:
    _section_title("استعلامات الموارد البشرية", "بحث محدد في سجل موظف موجود بقاعدة البيانات.")
    col1, col2 = st.columns(2)
    with col1:
        employee_name = st.text_input("اسم الموظف", placeholder="اكتب اسم الموظف...", key="ai_employee_name")
    with col2:
        question = st.text_input("السؤال", placeholder="مثال: ما الراتب الأساسي المسجل؟", key="ai_employee_question")
    submitted = st.button("استعلام عن الموظف", type="primary", width="stretch", key="employee_query")
    if not submitted:
        return
    if not employee_name.strip() or not question.strip():
        st.warning("يرجى إدخال اسم الموظف والسؤال.")
        return
    with st.spinner("جاري البحث..."):
        employee, salary = get_employee_info(employee_name.strip())
    if not employee:
        st.error("لم يتم العثور على الموظف.")
        return
    employee_info = {
        "الاسم": employee.get("name", employee_name),
        "المسمى الوظيفي": employee.get("position", "غير متاح"),
        "الراتب الأساسي": (salary or {}).get("basic_salary", "غير متاح"),
    }
    prompt = _make_prompt(employee_info, question, "أجب على السؤال بالاعتماد على الحقول المتاحة فقط. لا تفترض استحقاقات أو تقييمات.")
    with st.spinner("جاري صياغة الإجابة..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 180)
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Entry templates
# ---------------------------------------------------------------------
def _render_entries_tab() -> None:
    _section_title("مسودات القيود المحاسبية", "توليد قيد من قالب ثابت؛ لا يتم ترحيل أو اعتماد أي قيد تلقائياً.")
    _render_info("راجع الحسابات والمبالغ والضريبة وسياسة المنشأة قبل الاعتماد. هذه الشاشة لا ترحّل القيد.", "warning")
    operations = get_available_operations()
    if not operations:
        st.warning("لا توجد قوالب عمليات متاحة.")
        return
    operation = st.selectbox("نوع العملية", operations, key="ai_entry_operation")
    st.caption(get_operation_description(operation))
    amount = st.number_input("المبلغ", min_value=0.0, step=100.0, key="ai_entry_amount")
    expense_name = None
    if operation == "سداد مصروف":
        expense_name = st.text_input("اسم حساب المصروف", value="مصروفات عمومية", key="ai_entry_expense")
    if st.button("توليد مسودة القيد", type="primary", width="stretch", key="generate_entry_btn"):
        entry, display, confidence, label, color = generate_template_entry(
            operation_type=operation, amount=amount, expense_name=expense_name
        )
        if entry:
            st.write("مسودة القيد")
            with st.container(border=True):
                st.text(display)
                st.caption(f"التقييم: {label} ({confidence}%) — ليس تصديقاً محاسبياً")
        else:
            st.error(display)


# ---------------------------------------------------------------------
# Fraud/anomaly screening
# ---------------------------------------------------------------------
def _render_fraud_tab(model: str) -> None:
    _section_title("مؤشرات العمليات غير المعتادة", "فحص استرشادي لآخر القيود، وليس حكماً بوجود احتيال.")
    if not st.button("بدء الفحص الاسترشادي", type="primary", width="stretch", key="ai_fraud_scan"):
        return
    entries = get_recent_entries()
    if not entries:
        st.info("لا توجد قيود حديثة للفحص.")
        return
    st.caption(f"عدد القيود المسترجعة: {len(entries)}")
    prompt = _make_prompt(
        entries[:80], "فحص مؤشرات غير معتادة في القيود",
        "أشر إلى الأنماط التي تستحق المراجعة فقط. اذكر رقم القيد والسبب إذا كانت الحقول موجودة. لا تصف أي عملية بأنها احتيال مؤكد.",
    )
    with st.spinner("جاري الفحص..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 300)
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------
def _render_forecast_tab(model: str) -> None:
    _section_title("التوجهات والتوقعات", "قراءة تاريخية واتجاهات استرشادية وليست توقعاً مضموناً.")
    if not st.button("توليد ملخص التوجهات", type="primary", width="stretch", key="ai_forecast"):
        return
    trends = get_trend_analysis()
    business = get_business_snapshot()
    prompt = _make_prompt(
        {"الاتجاهات": trends, "ملخص الأعمال": business},
        "تحليل اتجاهات المبيعات والمشتريات",
        "صف الاتجاه المرصود، واذكر محدودية البيانات، وقدّم توصيات. لا تخترع قيمة مستقبلية أو تدفقاً نقدياً غير محسوب.",
    )
    with st.spinner("جاري التحليل..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 280)
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Comprehensive report
# ---------------------------------------------------------------------
def _render_comprehensive_tab(model: str) -> None:
    _section_title("التقرير الشامل", "ملخص إداري ومالي مبني على اللقطات المتاحة من قاعدة البيانات.")
    if not st.button("إنشاء التقرير الشامل", type="primary", width="stretch", key="ai_comprehensive_report"):
        return
    with st.spinner("جاري تجميع البيانات..."):
        data = get_comprehensive_data()
    prompt = _make_prompt(
        data, "إعداد تقرير إداري ومالي موجز",
        "اكتب ملخصاً تنفيذياً، والمؤشرات الرئيسية، والمخاطر التي يمكن استنتاجها، وخمس توصيات قابلة للمراجعة. ميّز بين الحقائق والتوصيات.",
    )
    with st.spinner("جاري إنشاء التقرير..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 350)
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Cost centres
# ---------------------------------------------------------------------
def _render_cost_center_tab() -> None:
    _section_title("مراكز التكلفة", "تحليل أداء مركز محدد، أو مقارنة المراكز، أو مراجعة الانحرافات.")
    try:
        centers = ccs.get_all_cost_centers(active_only=True)
    except Exception as exc:
        st.error(f"تعذر تحميل مراكز التكلفة: {exc}")
        return
    if not centers:
        st.info("لا توجد مراكز تكلفة نشطة.")
        return
    options = {c["id"]: f"{c.get('code', '')} - {c.get('name', '')}" for c in centers}
    selected_id = st.selectbox(
        "اختر مركز التكلفة", list(options.keys()),
        format_func=lambda value: options[value], key="ai_cost_center_select",
    )
    col1, col2 = st.columns(2)
    with col1:
        run_analysis = st.button("تحليل أداء المركز", type="primary", width="stretch", key="ai_cost_center_analysis")
    with col2:
        run_compare = st.button("مقارنة المراكز", width="stretch", key="ai_cost_center_compare")
    if run_analysis:
        with st.spinner("جاري تحليل المركز..."):
            result = analyze_cost_center_performance(selected_id)
        render_ai_response(result)
    if run_compare:
        with st.spinner("جاري مقارنة المراكز..."):
            result = compare_cost_centers()
        render_ai_response(result)

    st.markdown("---")
    st.write("تحليل الموازنة والتوقعات")
    col3, col4 = st.columns(2)
    with col3:
        fiscal_year = st.number_input(
            "السنة المالية", min_value=2000, max_value=2100,
            value=datetime.now().year, step=1, key="ai_cc_fiscal_year",
        )
        budget_click = st.button("تحليل انحراف الموازنة", width="stretch", key="ai_cc_budget")
    with col4:
        months = st.selectbox("أفق التوقع", [1, 2, 3, 6], index=2, key="ai_cc_months")
        forecast_click = st.button("توقع المصروفات", width="stretch", key="ai_cc_forecast")
    if budget_click:
        with st.spinner("جاري تحليل الموازنة..."):
            result = get_cost_center_budget_analysis(selected_id, int(fiscal_year))
        render_ai_response(result)
    if forecast_click:
        with st.spinner("جاري إعداد التوقع الاسترشادي..."):
            result = predict_cost_center_expenses(selected_id, int(months))
        render_ai_response(result)


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def show() -> None:
    _ensure_session()
    _apply_design()
    # Ensure the local history table exists; this does not load the GGUF model.
    try:
        create_ai_tables()
    except Exception as exc:
        st.error(f"تعذر تهيئة سجل محادثات المساعد: {exc}")
    _render_sidebar()
    _render_hero()

    tabs = st.tabs([
        "مساعد", "تحليل مالي", "مخزون", "موظفون", "مسودات قيود",
        "فحص استرشادي", "التوجهات", "تقرير شامل", "مراكز التكلفة",
    ])
    with tabs[0]:
        _render_chat_tab(LOCAL_MODEL_ID)
    with tabs[1]:
        _render_financial_analysis_tab(LOCAL_MODEL_ID)
    with tabs[2]:
        _render_inventory_tab(LOCAL_MODEL_ID)
    with tabs[3]:
        _render_hr_tab(LOCAL_MODEL_ID)
    with tabs[4]:
        _render_entries_tab()
    with tabs[5]:
        _render_fraud_tab(LOCAL_MODEL_ID)
    with tabs[6]:
        _render_forecast_tab(LOCAL_MODEL_ID)
    with tabs[7]:
        _render_comprehensive_tab(LOCAL_MODEL_ID)
    with tabs[8]:
        _render_cost_center_tab()
