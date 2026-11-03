# -*- coding: utf-8 -*-
"""ui/ai_ui.py - Hokama ERP cloud AI workspace (Groq / GPT-OSS 20B).

The UI preserves the existing ERP AI tabs and database helpers while moving
inference to Groq. Cloud transfer of ERP context is opt-in per app session.
User/model text is rendered with st.write(), never as unsafe HTML.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

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
# Configuration and visual design
# ---------------------------------------------------------------------
CHAT_MODEL_ID = LOCAL_AI_MODEL  # Backward-compatible service constant; now points to Groq model.
CHAT_CATEGORY = "مساعد Groq"
DEFAULT_CHAT_TOKENS = 1400
MAX_CONTEXT_CHARS = 12000

SYSTEM_ROLE = """أنت المستشار المالي والإداري الذكي في نظام Hokama ERP.
أجب باللغة العربية الفصحى المهنية، وبأسلوب واضح ومنظم وقابل للاستخدام الإداري.
استخدم بيانات ERP المرفقة فقط عند تحليل المنشأة، ولا تخترع أرقاماً أو أسماء أو أرصدة أو تواريخ.
افصل بين الحقائق الظاهرة، والتفسير المحتمل، والتوصية المقترحة.
اشرح الأثر المالي أو التشغيلي بقدر ما تسمح به البيانات، واذكر حدود التحليل.
لا تدّع تنفيذ قيد أو تعديل قاعدة البيانات أو اعتماد قرار.
في الاشتباه بالاحتيال، اذكر مؤشرات تستحق الفحص ولا تصدر حكماً قطعياً.
قدم خلاصة تنفيذية ثم التحليل ثم التوصيات مرتبة بالأولوية. لا تعرض سلسلة التفكير الداخلية."""

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
.main .block-container {{ max-width: 1500px; padding-top: 1.25rem; padding-bottom: 2.5rem; direction: rtl; text-align: right; }}
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg,#10192B,#0A101D); border-left:1px solid rgba(212,175,55,.16); direction:rtl; }}
.ai-hero {{ background:linear-gradient(115deg,#111A2B,#1B2940 58%,#26354C); border:1px solid rgba(212,175,55,.22); border-radius:20px; padding:25px 28px; margin-bottom:18px; direction:rtl; text-align:right; overflow-wrap:break-word; }}
.ai-hero-title {{ font-size:27px; font-weight:900; color:{TEXT}; margin:7px 0; }}
.ai-hero-sub {{ font-size:13px; color:{MUTED}; line-height:1.9; }}
.ai-tag {{ display:inline-block; padding:5px 10px; border-radius:9px; color:{GOLD_LIGHT}; background:rgba(212,175,55,.10); border:1px solid rgba(212,175,55,.25); font-size:11px; font-weight:800; }}
.ai-metric {{ background:linear-gradient(145deg,{PANEL_ALT},{PANEL}); border:1px solid rgba(212,175,55,.18); border-radius:14px; padding:15px; min-height:96px; direction:rtl; text-align:right; overflow-wrap:break-word; }}
.ai-metric-label {{ color:{MUTED}; font-size:12px; margin-bottom:9px; }}
.ai-metric-value {{ color:{GOLD_LIGHT}; font-size:22px; font-weight:900; direction:ltr; text-align:right; }}
.ai-card {{ background:linear-gradient(145deg,rgba(23,35,55,.96),rgba(14,22,36,.98)); border:1px solid rgba(212,175,55,.18); border-radius:14px; padding:15px 17px; margin:9px 0; direction:rtl; text-align:right; overflow-wrap:break-word; white-space:pre-wrap; }}
.ai-title {{ color:{GOLD_LIGHT}; font-weight:800; font-size:15px; margin-bottom:5px; }}
.ai-caption {{ color:{MUTED}; font-size:12px; line-height:1.9; }}
.ai-info {{ border-right:4px solid {BLUE}; background:rgba(96,165,250,.08); border-radius:10px; padding:11px 14px; color:#D4E5FA; direction:rtl; text-align:right; overflow-wrap:break-word; }}
.ai-warning {{ border-right:4px solid {GOLD}; background:rgba(212,175,55,.08); border-radius:10px; padding:11px 14px; color:#F0DEA7; direction:rtl; text-align:right; overflow-wrap:break-word; }}
.stButton > button {{ border-radius:10px !important; border:1px solid rgba(212,175,55,.34) !important; background:linear-gradient(135deg,rgba(212,175,55,.15),rgba(212,175,55,.04)) !important; color:{GOLD_LIGHT} !important; font-weight:700 !important; min-height:40px; }}
.stButton > button[kind="primary"] {{ background:linear-gradient(110deg,#B58B29,{GOLD}) !important; color:#101522 !important; border:0 !important; font-weight:900 !important; }}
.stTextInput input, .stNumberInput input, .stTextArea textarea {{ background:{PANEL} !important; color:{TEXT} !important; border:1px solid #2A3952 !important; border-radius:9px !important; }}
[data-testid="stChatInput"] {{ border:1px solid rgba(212,175,55,.3) !important; border-radius:13px !important; background:{PANEL} !important; }}
[data-testid="stChatMessage"] {{ background:rgba(17,26,43,.82) !important; border:1px solid rgba(212,175,55,.13); border-radius:13px !important; padding:10px 14px !important; margin-bottom:9px !important; overflow-wrap:break-word; }}
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
# General helpers
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
        text = text[:max_chars] + "\n[اختُصر جزء من البيانات لتقليل حجم الطلب]"
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
        if data.empty:
            st.info(empty_message)
        else:
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
        else:
            st.json(data, expanded=False)
        return
    st.write(str(data))


def _service_call(function, *args, default=None, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        st.error("تعذّر تنفيذ العملية: " + str(exc))
        return default


def _apply_design() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _section_title(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="ai-title">{_safe_html(title)}</div>'
        f'<div class="ai-caption">{_safe_html(subtitle)}</div>',
        unsafe_allow_html=True,
    )


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


def _render_hero() -> None:
    status = _service_call(_ai_service.get_model_status, default={}) or {}
    configured = bool(status.get("configured"))
    state = "مفتاح API مضاف" if configured else "بانتظار إضافة مفتاح Groq"
    st.markdown(
        '<div class="ai-hero">'
        '<span class="ai-tag">HOKAMA ERP · CLOUD INTELLIGENCE</span>'
        '<div class="ai-hero-title">المستشار المالي والإداري الذكي</div>'
        '<div class="ai-hero-sub">تحليلات ومحادثات مدعومة بنموذج GPT-OSS 20B عبر Groq. '
        'تُرسل البيانات التي تختار تحليلها إلى الخدمة السحابية؛ لا تُرسل قاعدة البيانات كاملة تلقائياً.</div>'
        f'<div class="ai-caption">المزود: Groq · النموذج: {_safe_html(status.get("model_name", CHAT_MODEL_ID))} · {_safe_html(state)}</div>'
        '</div>', unsafe_allow_html=True,
    )
    if not configured:
        st.warning("أضف مفتاح Groq من إعدادات المساعد في الشريط الجانبي قبل تشغيل التحليلات.")


def render_ai_response(content: Any) -> None:
    st.markdown('<div class="ai-title">نتيجة تحليل المساعد</div>', unsafe_allow_html=True)
    if content is None:
        st.info("لم يتم إنشاء نتيجة.")
        return
    with st.container(border=True):
        st.write(_safe_text(content))


def _require_cloud_key() -> bool:
    if not _ai_service.get_api_key_status().get("configured"):
        st.warning("لم تتم إضافة مفتاح Groq. افتح إعدادات المساعد في الشريط الجانبي.")
        return False
    return True


def _require_data_consent() -> bool:
    if not st.session_state.get("ai_cloud_data_consent", False):
        st.warning("هذه العملية تحتاج إلى إرسال ملخص بيانات من ERP إلى Groq. فعّل خيار الموافقة في الشريط الجانبي أولاً.")
        return False
    return True


# ---------------------------------------------------------------------
# Inference wrapper / context assembly
# ---------------------------------------------------------------------
def query_local_ai(prompt: str, active_query: str = "", model: str = CHAT_MODEL_ID,
                   max_tokens: int = DEFAULT_CHAT_TOKENS, history=None,
                   reasoning_effort: str = "medium") -> str:
    """Compatibility wrapper name; the provider is now Groq cloud."""
    try:
        result = query_groq(
            prompt or SYSTEM_ROLE,
            active_query or prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=0.35,
            history=history,
            reasoning_effort=reasoning_effort,
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
        return "حدث خطأ أثناء الاتصال بخدمة Groq: " + str(exc)


def _make_prompt(data: Any, task: str, instructions: str) -> str:
    return (
        "بيانات نظام Hokama ERP (مصدر الحقائق):\n" + _compact_json(data)
        + "\n\nالمهمة: " + str(task)
        + "\n\nالمطلوب: " + str(instructions)
        + "\n\nاعرض الحقائق كما هي، وميّز الاستنتاجات والتوصيات، وصرّح بأي نقص في البيانات."
    )


def _callable_service(name: str):
    return getattr(_ai_service, name, None)


def audio_to_text(audio_file) -> str:
    """Optional transcription adapter; remains inactive unless a backend exists."""
    if audio_file is None:
        return ""
    function = None
    for name in ("audio_to_text_local", "transcribe_audio_local", "transcribe_audio"):
        candidate = _callable_service(name)
        if callable(candidate):
            function = candidate
            break
    if function is None:
        return "التفريغ الصوتي غير مهيأ حالياً؛ استخدم المحادثة النصية."
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
        return "تعذر تفريغ الصوت: " + str(exc)
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def audio_input_widget(key: str = "assistant_audio") -> str:
    available = any(callable(_callable_service(name)) for name in
                    ("audio_to_text_local", "transcribe_audio_local", "transcribe_audio"))
    if not available or not hasattr(st, "audio_input"):
        return ""
    audio = st.audio_input("تسجيل صوتي", key=key, label_visibility="collapsed")
    if audio is None:
        return ""
    with st.spinner("جاري تفريغ التسجيل..."):
        return audio_to_text(audio)


def _get_chat_context(question: str) -> str:
    """Prepare a small, task-relevant snapshot; never dump the entire database."""
    q = (question or "").lower()
    parts: Dict[str, Any] = {}
    inventory_words = ("مخزون", "مخزن", "مخازن", "منتج", "منتجات", "كمية", "نفد", "الأصناف")
    finance_words = ("مالي", "مالية", "إيراد", "إيرادات", "مصروف", "مصروفات", "ربح", "ربحية", "أصول", "التزامات", "ميزانية", "مديونية", "حساب")
    business_words = ("عميل", "عملاء", "مورد", "موردين", "مبيعات", "مشتريات", "فاتورة")
    hr_words = ("موظف", "موظفين", "موارد بشرية", "رواتب", "راتب")
    try:
        if any(word in q for word in inventory_words):
            low, products = get_inventory_data()
            parts = {"الأصناف منخفضة المخزون": low[:12], "عينة المنتجات": products[:12]}
        elif any(word in q for word in business_words):
            parts = {"ملخص العملاء والموردين": get_business_snapshot(), "اتجاه المبيعات والمشتريات": get_trend_analysis()[:8]}
        elif any(word in q for word in hr_words):
            parts = {"ملخص الموارد البشرية": get_hr_snapshot()}
        elif any(word in q for word in finance_words):
            parts = {"المؤشرات المالية": get_financial_snapshot(), "النسب المالية": get_financial_ratios()}
        else:
            financial = get_financial_snapshot()
            inventory = get_inventory_snapshot()
            business = get_business_snapshot()
            parts = {
                "ملخص مالي": {k: financial.get(k) for k in ("revenue", "expenses", "net_income", "assets", "liabilities", "profit_margin", "debt_ratio")},
                "ملخص المخزون": {k: inventory.get(k) for k in ("total_products", "low_stock_count")},
                "ملخص الأعمال": {k: business.get(k) for k in ("total_customers", "total_suppliers")},
            }
    except Exception:
        parts = {"حالة البيانات": "تعذر استخراج لقطة بيانات مرتبطة بالسؤال؛ لا تستنتج أرقاماً غير متاحة."}
    return _compact_json(parts, 7000)


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
    if "ai_cloud_data_consent" not in st.session_state:
        st.session_state.ai_cloud_data_consent = False
    if "ai_voice_pending_id" not in st.session_state:
        st.session_state.ai_voice_pending_id = ""


def _new_chat() -> None:
    st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    st.session_state.ai_messages = []
    st.session_state.ai_history_loaded = True
    st.session_state.ai_voice_pending_id = ""


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
        save_chat_history(session_id, role, content, CHAT_MODEL_ID, CHAT_CATEGORY)
    except Exception as exc:
        st.warning("تعذّر حفظ المحادثة محلياً: " + str(exc))


def _get_sessions() -> List[Any]:
    try:
        return get_chat_sessions() or []
    except Exception:
        return []


def _render_api_settings() -> None:
    status = _ai_service.get_api_key_status()
    configured = bool(status.get("configured"))
    with st.expander("إعداد اتصال Groq ومفتاح API", expanded=not configured):
        st.caption("أدخل مفتاح Groq. على Windows يُحفظ مشفراً باستخدام حماية حساب المستخدم، ولا يُعرض بعد الحفظ.")
        st.caption("أنشئ المفتاح من لوحة Groq الرسمية، ولا ترسله إلى أي شخص أو تضعه داخل ملفات Python.")
        with st.form("groq_api_key_form", clear_on_submit=True):
            entered_key = st.text_input("Groq API Key", type="password", placeholder="gsk_…", help="سيُحفظ مشفراً محلياً على Windows عند نجاح الحفظ.")
            save_clicked = st.form_submit_button("حفظ المفتاح", type="primary", use_container_width=True)
            test_clicked = st.form_submit_button("حفظ المفتاح واختبار الاتصال", use_container_width=True)
        if save_clicked or test_clicked:
            ok, message = _ai_service.save_groq_api_key(entered_key)
            if ok:
                st.success(message)
                if test_clicked:
                    with st.spinner("يتم اختبار الاتصال بالنموذج..."):
                        test_ok, test_message = _ai_service.test_groq_connection()
                    (st.success if test_ok else st.error)(test_message)
            else:
                st.error(message)
        col1, col2 = st.columns(2)
        with col1:
            st.caption("الحالة: " + ("مفتاح مضاف" if configured else "غير مهيأ"))
        with col2:
            if st.button("حذف المفتاح المحفوظ", key="delete_groq_key", width="stretch"):
                ok, message = _ai_service.delete_groq_api_key()
                (st.success if ok else st.error)(message)
                st.rerun()
        if configured:
            source = status.get("source")
            source_label = {"windows_dpapi": "تخزين Windows المشفر", "environment": "متغير بيئة", "memory": "ذاكرة العملية"}.get(source, "غير معروف")
            st.caption("مصدر المفتاح: " + source_label)


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f'<div style="direction:rtl;text-align:right;padding:8px 3px 15px;">'
            f'<div style="color:{TEXT};font-size:24px;font-weight:900;">حوكمة <span style="color:{GOLD}">AI</span></div>'
            '<div style="color:#718096;font-size:10px;">GROQ CLOUD · GPT-OSS 20B</div></div>',
            unsafe_allow_html=True,
        )
        status = _service_call(_ai_service.get_model_status, default={}) or {}
        st.caption("النموذج: " + str(status.get("model_name", CHAT_MODEL_ID)))
        st.caption("الاتصال: " + ("جاهز للمصادقة" if status.get("configured") else "يتطلب مفتاح API"))
        _render_api_settings()
        st.markdown("---")
        consent = st.checkbox(
            "أوافق على إرسال ملخصات البيانات التي أطلب تحليلها إلى Groq",
            key="ai_cloud_data_consent",
            help="لا تُرسل قاعدة البيانات كاملة. ترسل الوحدة فقط الحقول والسجلات اللازمة للمهمة المختارة.",
        )
        if consent:
            _render_info("تم تفعيل إرسال السياق المحدد إلى Groq لهذه الجلسة.")
        else:
            _render_info("إرسال بيانات ERP معطل. يمكنك استخدام المحادثة العامة، لكن التحليلات التي تحتاج بيانات ستتطلب الموافقة.", "warning")
        with st.expander("إعدادات المحادثة والصوت", expanded=False):
            st.checkbox("نطق إجابة المساعد تلقائياً", value=True, key="ai_voice_autoplay",
                        help="يستخدم صوتاً عربياً مثبتاً على هذا الجهاز داخل المتصفح.")
            st.slider("سرعة النطق", min_value=0.7, max_value=1.3, value=1.0, step=0.1, key="ai_voice_rate")
            st.slider("الحد الأقصى لطول إجابة المحادثة (Token)", min_value=512, max_value=8192,
                      value=2560, step=256, key="ai_chat_max_tokens",
                      help="رفع الحد يسمح بإجابات أطول وقد يزيد زمن التوليد واستهلاك الرصيد.")
        st.markdown("---")
        if st.button("محادثة جديدة", key="new_ai_chat", width="stretch", type="primary"):
            _new_chat()
            st.rerun()
        st.markdown("**المحادثات السابقة**")
        sessions = _get_sessions()
        session_map: Dict[str, str] = {}
        for index, item in enumerate(sessions[:25]):
            if isinstance(item, dict):
                sid = str(item.get("session_id") or "")
                label = str(item.get("first_message") or f"محادثة {index + 1}")
                if sid:
                    session_map[f"{label[:26]} · {sid[-6:]} "] = sid
        if session_map:
            selected = st.selectbox("اختر محادثة محفوظة", list(session_map.keys()), index=None,
                                    placeholder="حدد محادثة...", label_visibility="collapsed", key="ai_old_session_selector")
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
        st.caption("يتطلب اتصال إنترنت ومفتاح Groq صالحاً. قد تُطبق حدود استخدام أو رسوم وفق خطة حسابك.")



# ---------------------------------------------------------------------
# Local browser speech (no external TTS service; uses installed Arabic voices)
# ---------------------------------------------------------------------
def _render_voice_player(answer: str, autoplay: bool = False, rate: float = 1.0) -> None:
    """Render a local Arabic speech player for one assistant answer."""
    answer_text = str(answer or "").strip()
    if not answer_text:
        return

    # JSON-encode and neutralize HTML script-closing characters. The answer is
    # data, never executable markup, even if the model emits HTML-like text.
    text_js = json.dumps(answer_text, ensure_ascii=False)
    text_js = (text_js.replace("<", "\\u003c")
                      .replace(">", "\\u003e")
                      .replace("&", "\\u0026"))
    auto_js = "true" if autoplay else "false"
    try:
        initial_rate = max(0.7, min(float(rate), 1.3))
    except (TypeError, ValueError):
        initial_rate = 1.0

    html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 7px 2px; background: transparent; color: #e8edf5;
       font-family: Segoe UI, Tahoma, Arial, sans-serif; font-size: 12px; }}
.voice-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 7px;
              padding: 8px 10px; border: 1px solid rgba(212,175,55,.25);
              border-radius: 10px; background: rgba(17,26,43,.78); }}
button, select {{ border: 1px solid #526078; border-radius: 7px; padding: 6px 9px;
                  background: #172337; color: #f0d98a; font: inherit; }}
button {{ cursor: pointer; }} button:disabled, select:disabled {{ opacity: .55; cursor: not-allowed; }}
.rate {{ display: inline-flex; align-items: center; gap: 5px; color: #c5cedb; }}
input {{ width: 76px; accent-color: #d4af37; }}
.status {{ flex: 1 1 100%; min-height: 16px; color: #a5b1c4; line-height: 1.5; }}
</style></head>
<body>
<div class="voice-row">
  <button id="play" type="button" disabled>▶ تشغيل الصوت</button>
  <button id="stop" type="button">■ إيقاف</button>
  <select id="voice" aria-label="الصوت العربي"><option>جارٍ تحميل الأصوات العربية...</option></select>
  <label class="rate">السرعة <input id="rate" type="range" min="0.7" max="1.3" step="0.1" value="{initial_rate}"><span id="rateValue">{initial_rate:.1f}×</span></label>
  <span id="status" class="status">الرد النصي محفوظ؛ يجري التحقق من توفر صوت عربي محلي.</span>
</div>
<script>
(() => {{
  const originalText = {text_js};
  const autoplay = {auto_js};
  const playButton = document.getElementById('play');
  const stopButton = document.getElementById('stop');
  const voiceSelect = document.getElementById('voice');
  const rateInput = document.getElementById('rate');
  const rateValue = document.getElementById('rateValue');
  const status = document.getElementById('status');
  let arabicVoices = [];

  function speechText(value) {{
    return String(value)
      .replace(/```[\\s\\S]*?```/g, ' كتلة برمجية ')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^)]+)\\)/g, '$1')
      .replace(/https?:\\/\\/\\S+/g, ' رابط ')
      .replace(/^\\s*#{1,6}\\s*/gm, '')
      .replace(/[>*_~|]/g, ' ')
      .replace(/^\\s*[-+•]\\s+/gm, '')
      .replace(/\\s+/g, ' ')
      .trim();
  }}

  function refreshVoices() {{
    if (!('speechSynthesis' in window)) {{
      status.textContent = 'هذا المتصفح لا يدعم النطق الصوتي.';
      playButton.disabled = true;
      return false;
    }}
    arabicVoices = window.speechSynthesis.getVoices().filter(v => /^ar([_-]|$)/i.test(v.lang || '') && v.localService === true);
    voiceSelect.innerHTML = '';
    if (!arabicVoices.length) {{
      const option = document.createElement('option');
      option.textContent = 'لا يوجد صوت عربي مثبت';
      option.value = '';
      voiceSelect.appendChild(option);
      playButton.disabled = true;
      status.textContent = 'لم نعثر على صوت عربي محلي. ثبّت صوتاً عربياً في Windows ثم أعد فتح التطبيق.';
      return false;
    }}
    arabicVoices.forEach((voice, index) => {{
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = `${{voice.name}} (${{voice.lang}})${{voice.default ? ' · افتراضي' : ''}}`;
      voiceSelect.appendChild(option);
    }});
    playButton.disabled = false;
    status.textContent = 'الصوت العربي المحلي جاهز.';
    return true;
  }}

  function speak() {{
    if (!refreshVoices()) return;
    const selected = arabicVoices[Number(voiceSelect.value)] || arabicVoices[0];
    const spoken = speechText(originalText);
    if (!spoken) {{ status.textContent = 'لا يوجد نص مناسب للنطق.'; return; }}
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(spoken);
    utterance.voice = selected;
    utterance.lang = selected.lang || 'ar-SA';
    utterance.rate = Number(rateInput.value) || 1.0;
    utterance.onstart = () => {{ status.textContent = 'يجري نطق الإجابة...'; }};
    utterance.onend = () => {{ status.textContent = 'اكتمل نطق الإجابة.'; }};
    utterance.onerror = (event) => {{
      status.textContent = 'تعذر تشغيل الصوت (' + (event.error || 'خطأ بالمتصفح') + '). استخدم زر التشغيل مجدداً.';
    }};
    // A short delay after cancel avoids occasional Chrome/Edge queue races.
    window.setTimeout(() => window.speechSynthesis.speak(utterance), 80);
  }}

  playButton.addEventListener('click', speak);
  stopButton.addEventListener('click', () => {{
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    status.textContent = 'تم إيقاف النطق.';
  }});
  rateInput.addEventListener('input', () => {{ rateValue.textContent = Number(rateInput.value).toFixed(1) + '×'; }});
  if ('speechSynthesis' in window) {{
    window.speechSynthesis.onvoiceschanged = refreshVoices;
    refreshVoices();
    if (autoplay) {{
      // Voices can arrive asynchronously from the operating system.
      let tries = 0;
      const autoTimer = window.setInterval(() => {{
        tries += 1;
        if (refreshVoices()) {{ window.clearInterval(autoTimer); speak(); }}
        else if (tries >= 8) {{
          window.clearInterval(autoTimer);
          status.textContent = 'تعذر التشغيل التلقائي: لا يوجد صوت عربي جاهز. استخدم زر التشغيل بعد تثبيت صوت عربي.';
        }}
      }}, 350);
    }}
  }} else {{
    status.textContent = 'هذا المتصفح لا يدعم النطق الصوتي.';
  }}
}})();
</script>
</body></html>"""
    # st.iframe executes this controlled HTML in the browser. The model answer
    # is JSON-escaped above; it is not inserted as raw HTML.
    st.iframe(html, width="stretch", height=112)


# ---------------------------------------------------------------------
# Chat tab
# ---------------------------------------------------------------------
def _render_chat_tab(model: str) -> None:
    _section_title("المساعد الذكي", "محادثة عربية تفهم الأسئلة المالية والإدارية وتستند إلى بيانات ERP عند السماح بذلك.")
    _load_current_history()
    st.markdown(
        '<div class="ai-card"><div class="ai-title">مستشارك داخل النظام</div>'
        '<div class="ai-caption">اسأل عن المؤشرات المالية، المخزون، المبيعات، المشتريات، العملاء، الموردين، أو السياسات والإجراءات. '
        'عند تفعيل الموافقة، سيُرفق سياق محدود ومرتبط بسؤالك من قاعدة بيانات ERP.</div></div>',
        unsafe_allow_html=True,
    )
    pending_voice_id = st.session_state.get("ai_voice_pending_id", "")
    last_index = len(st.session_state.ai_messages) - 1
    for index, message in enumerate(st.session_state.ai_messages):
        role = message.get("role", "assistant")
        if role in ("user", "assistant"):
            with st.chat_message(role):
                message_text = str(message.get("content", ""))
                st.write(message_text)
                if role == "assistant":
                    digest = hashlib.sha256(message_text.encode("utf-8")).hexdigest()[:16]
                    should_autoplay = (index == last_index and bool(pending_voice_id) and digest == pending_voice_id)
                    _render_voice_player(
                        message_text,
                        autoplay=should_autoplay,
                        rate=st.session_state.get("ai_voice_rate", 1.0),
                    )
                    if should_autoplay:
                        st.session_state.ai_voice_pending_id = ""
    question = st.chat_input("اكتب سؤالك المالي أو التشغيلي هنا...", key="ai-chat-input")
    active_query = (question or "").strip()
    if not active_query:
        return
    if not _require_cloud_key():
        return
    st.session_state.ai_messages.append({"role": "user", "content": active_query})
    _save_history(st.session_state.active_session, "user", active_query)
    try:
        with st.spinner("يجري تجهيز السياق وصياغة الإجابة..."):
            if st.session_state.ai_cloud_data_consent:
                context = _get_chat_context(active_query)
                context_note = "السياق المحدد من بيانات ERP (استخدمه كمصدر للحقائق):\n" + context
            else:
                context_note = "لم يُرفق أي سياق من قاعدة بيانات ERP. أجب عن السؤال العام فقط، ولا تزعم معرفة أرقام المنشأة."
            payload = context_note + "\n\nسؤال المستخدم:\n" + active_query
            history = st.session_state.ai_messages[-9:-1]
            chat_limit = int(st.session_state.get("ai_chat_max_tokens", 2560))
            answer = query_local_ai(SYSTEM_ROLE, payload, model, chat_limit, history=history, reasoning_effort="medium")
    except Exception as exc:
        answer = "حدث خطأ أثناء تجهيز الإجابة: " + str(exc)
    st.session_state.ai_messages.append({"role": "assistant", "content": answer})
    _save_history(st.session_state.active_session, "assistant", answer)
    if st.session_state.get("ai_voice_autoplay", True):
        st.session_state.ai_voice_pending_id = hashlib.sha256(answer.encode("utf-8")).hexdigest()[:16]
    else:
        st.session_state.ai_voice_pending_id = ""
    st.rerun()


# ---------------------------------------------------------------------
# Financial analysis
# ---------------------------------------------------------------------
def _render_financial_analysis_tab(model: str) -> None:
    _section_title("التحليل المالي والنسب", "مؤشرات مالية مستخرجة حسابياً من قاعدة البيانات ثم تفسيرها بواسطة النموذج.")
    if not st.button("بدء التحليل المالي", type="primary", width="stretch", key="run_financial_analysis"):
        return
    if not _require_cloud_key() or not _require_data_consent():
        return
    with st.spinner("جاري استخراج المؤشرات وتحليلها..."):
        data = get_financial_snapshot()
        ratios = get_financial_ratios()
        cols = st.columns(3)
        for col, (label, value) in zip(cols, [("الإيرادات", data.get("revenue")), ("المصروفات", data.get("expenses")), ("صافي الدخل", data.get("net_income"))]):
            with col:
                _render_metric(label, _money(value))
        prompt = _make_prompt(
            {"المؤشرات": data, "النسب": ratios}, "إعداد تحليل مالي تنفيذي",
            "اكتب خلاصة تنفيذية، ثم حلل النسب والمعاني الممكنة، وحدد المخاطر ونقاط القوة والتوصيات. لا تضف معيار مقارنة أو سبباً غير موجود. اذكر أن النسب تعتمد على تصنيف الحسابات في النظام.",
        )
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 2200, reasoning_effort="high")
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------
def _render_inventory_tab(model: str) -> None:
    _section_title("تحليل المخزون", "تحديد الأصناف تحت حد إعادة الطلب ومراجعة مستويات المخزون المسجلة.")
    if not st.button("تحميل وتحليل المخزون", type="primary", width="stretch", key="inventory_analysis"):
        return
    if not _require_cloud_key() or not _require_data_consent():
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
        _render_info(f"يوجد {len(low)} صنفاً تحت حد إعادة الطلب المسجل.", "warning")
        st.write("الأصناف الحرجة")
        _display_data(low)
    else:
        st.success("لم تُرجع البيانات أصنافاً تحت حد إعادة الطلب.")
    if products:
        st.write("بيانات المنتجات")
        _display_data(products)
        prompt = _make_prompt(
            {"الأصناف منخفضة المخزون": low, "المنتجات": products}, "تحليل المخزون",
            "حدد أولويات المتابعة ومخاطر النفاد استناداً إلى الكميات وحدود إعادة الطلب. لا تخترع مبيعات أو معدل دوران أو قيمة مخزون. اقترح بيانات إضافية لتحسين التخطيط.",
        )
        with st.spinner("جاري تحليل النتائج..."):
            answer = query_local_ai(SYSTEM_ROLE, prompt, model, 1800, reasoning_effort="medium")
        render_ai_response(answer)
    else:
        st.info("لا توجد بيانات منتجات كافية للتحليل.")


# ---------------------------------------------------------------------
# Human resources query
# ---------------------------------------------------------------------
def _render_hr_tab(model: str) -> None:
    _section_title("استعلامات الموارد البشرية", "بحث محدد في سجل موظف. لا يتم إرسال كل ملفات الموظفين.")
    st.warning("قد تتضمن الإجابة بيانات راتب وظيفية. لا تتابع إلا إذا كنت مخولاً، وبموافقة إرسال هذه البيانات إلى Groq.")
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
    if not _require_cloud_key() or not _require_data_consent():
        return
    with st.spinner("جاري البحث في سجل الموظف..."):
        employee, salary = get_employee_info(employee_name.strip())
    if not employee:
        st.error("لم يتم العثور على الموظف.")
        return
    # Data minimization: send only fields needed to answer the selected question.
    employee_info = {
        "الاسم": employee.get("name", employee_name),
        "المسمى الوظيفي": employee.get("position", "غير متاح"),
    }
    if any(term in question for term in ("راتب", "أجر", "salary", "أساسي")):
        employee_info["الراتب الأساسي"] = (salary or {}).get("basic_salary", "غير متاح")
    prompt = _make_prompt(employee_info, question, "أجب اعتماداً على الحقول المتاحة فقط. لا تفترض استحقاقات أو خصومات أو تقييمات أو معلومات شخصية غير مرفقة.")
    with st.spinner("جاري صياغة الإجابة..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 1000, reasoning_effort="low")
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Entry templates - no AI or cloud call is required
# ---------------------------------------------------------------------
def _render_entries_tab() -> None:
    _section_title("مسودات القيود المحاسبية", "توليد قيد من قالب ثابت. لا يتم ترحيل أو اعتماد أي قيد تلقائياً.")
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
                st.caption(f"التقييم: {label} ({confidence}%) — تقييم اكتمال شكلي وليس اعتماداً محاسبياً")
        else:
            st.error(display)


# ---------------------------------------------------------------------
# Fraud/anomaly screening
# ---------------------------------------------------------------------
def _render_fraud_tab(model: str) -> None:
    _section_title("مؤشرات العمليات غير المعتادة", "فحص استرشادي للقيود. النتائج مؤشرات مراجعة وليست إثباتاً للاحتيال.")
    if not st.button("بدء الفحص الاسترشادي", type="primary", width="stretch", key="ai_fraud_scan"):
        return
    if not _require_cloud_key() or not _require_data_consent():
        return
    entries = get_recent_entries()
    if not entries:
        st.info("لا توجد قيود حديثة للفحص.")
        return
    st.caption(f"عدد القيود المسترجعة: {min(len(entries), 80)} من أصل {len(entries)} قيداً متاحاً.")
    prompt = _make_prompt(
        entries[:80], "فحص مؤشرات غير معتادة في القيود",
        "أعد جدولاً موجزاً يتضمن رقم القيد إذا كان الحقل موجوداً، والمؤشر المرصود، وسبب الحاجة للمراجعة، وأولوية الفحص. لا تصف أي عملية بأنها احتيال مؤكد، ولا تستنتج نية أو فاعلاً.",
    )
    with st.spinner("يجري تحليل القيود بحثاً عن مؤشرات تستحق المراجعة..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 2200, reasoning_effort="high")
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------
def _render_forecast_tab(model: str) -> None:
    _section_title("التوجهات والتوقعات", "قراءة تاريخية واتجاهات استرشادية مع توضيح قيود البيانات.")
    if not st.button("توليد ملخص التوجهات", type="primary", width="stretch", key="ai_forecast"):
        return
    if not _require_cloud_key() or not _require_data_consent():
        return
    trends = get_trend_analysis()
    business = get_business_snapshot()
    if not trends:
        st.info("لا توجد فترات تاريخية كافية لإجراء تحليل اتجاهات.")
        return
    prompt = _make_prompt(
        {"الاتجاهات": trends, "ملخص الأعمال": business}, "تحليل اتجاهات المبيعات والمشتريات",
        "صف الاتجاهات الظاهرة والفروقات بين الفترات، واذكر محدودية البيانات. قدم توصيات عملية. لا تخترع قيمة مستقبلية أو تدفقاً نقدياً أو سبباً للتغير.",
    )
    with st.spinner("جاري التحليل..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 1800, reasoning_effort="high")
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Comprehensive report
# ---------------------------------------------------------------------
def _render_comprehensive_tab(model: str) -> None:
    _section_title("التقرير الشامل", "ملخص إداري ومالي مبني على اللقطات المتاحة من قاعدة بيانات النظام.")
    if not st.button("إنشاء التقرير الشامل", type="primary", width="stretch", key="ai_comprehensive_report"):
        return
    if not _require_cloud_key() or not _require_data_consent():
        return
    with st.spinner("جاري تجميع مؤشرات النظام..."):
        data = get_comprehensive_data()
    prompt = _make_prompt(
        data, "إعداد تقرير إداري ومالي تنفيذي",
        "اكتب تقريراً منظماً: (1) ملخص تنفيذي، (2) المؤشرات الرئيسية، (3) نقاط القوة، (4) المخاطر والفجوات، (5) خمس توصيات مرتبة بالأولوية، (6) البيانات الإضافية التي يحتاجها تحليل أدق. ميز الحقائق من التوصيات ولا تكرر الأرقام بلا داعٍ.",
    )
    with st.spinner("جاري إنشاء التقرير..."):
        answer = query_local_ai(SYSTEM_ROLE, prompt, model, 3000, reasoning_effort="high")
    render_ai_response(answer)


# ---------------------------------------------------------------------
# Cost centres
# ---------------------------------------------------------------------
def _render_cost_center_tab() -> None:
    _section_title("مراكز التكلفة", "تحليل أداء مركز، أو مقارنة المراكز، أو مراجعة انحرافات الموازنة.")
    try:
        centers = ccs.get_all_cost_centers(active_only=True)
    except Exception as exc:
        st.error("تعذر تحميل مراكز التكلفة: " + str(exc))
        return
    if not centers:
        st.info("لا توجد مراكز تكلفة نشطة.")
        return
    options = {c["id"]: f"{c.get('code', '')} - {c.get('name', '')}" for c in centers}
    selected_id = st.selectbox("اختر مركز التكلفة", list(options.keys()), format_func=lambda value: options[value], key="ai_cost_center_select")
    col1, col2 = st.columns(2)
    with col1:
        run_analysis = st.button("تحليل أداء المركز", type="primary", width="stretch", key="ai_cost_center_analysis")
    with col2:
        run_compare = st.button("مقارنة المراكز", width="stretch", key="ai_cost_center_compare")
    if run_analysis:
        if _require_cloud_key() and _require_data_consent():
            with st.spinner("جاري تحليل المركز..."):
                result = analyze_cost_center_performance(selected_id)
            render_ai_response(result)
    if run_compare:
        if _require_cloud_key() and _require_data_consent():
            with st.spinner("جاري مقارنة المراكز..."):
                result = compare_cost_centers()
            render_ai_response(result)
    st.markdown("---")
    st.write("تحليل الموازنة والتوقعات")
    col3, col4 = st.columns(2)
    with col3:
        fiscal_year = st.number_input("السنة المالية", min_value=2000, max_value=2100, value=datetime.now().year, step=1, key="ai_cc_fiscal_year")
        budget_click = st.button("تحليل انحراف الموازنة", width="stretch", key="ai_cc_budget")
    with col4:
        months = st.selectbox("أفق التوقع", [1, 2, 3, 6], index=2, key="ai_cc_months")
        forecast_click = st.button("توقع المصروفات", width="stretch", key="ai_cc_forecast")
    if budget_click and _require_cloud_key() and _require_data_consent():
        with st.spinner("جاري تحليل الموازنة..."):
            result = get_cost_center_budget_analysis(selected_id, int(fiscal_year))
        render_ai_response(result)
    if forecast_click and _require_cloud_key() and _require_data_consent():
        with st.spinner("جاري إعداد التوقع الاسترشادي..."):
            result = predict_cost_center_expenses(selected_id, int(months))
        render_ai_response(result)


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def show() -> None:
    _ensure_session()
    _apply_design()
    try:
        create_ai_tables()
    except Exception as exc:
        st.error("تعذر تهيئة سجل محادثات المساعد: " + str(exc))
    _render_sidebar()
    _render_hero()
    st.warning("تنبيه خصوصية: عند الموافقة على التحليل السحابي، تُرسل البيانات المرتبطة بالمهمة إلى Groq عبر اتصال مشفر. لا ترسل كلمات مرور أو مفاتيح أو بيانات لا تملك صلاحية مشاركتها.")
    tabs = st.tabs([
        "مساعد", "تحليل مالي", "مخزون", "موظفون", "مسودات قيود",
        "فحص استرشادي", "التوجهات", "تقرير شامل", "مراكز التكلفة",
    ])
    with tabs[0]:
        _render_chat_tab(CHAT_MODEL_ID)
    with tabs[1]:
        _render_financial_analysis_tab(CHAT_MODEL_ID)
    with tabs[2]:
        _render_inventory_tab(CHAT_MODEL_ID)
    with tabs[3]:
        _render_hr_tab(CHAT_MODEL_ID)
    with tabs[4]:
        _render_entries_tab()
    with tabs[5]:
        _render_fraud_tab(CHAT_MODEL_ID)
    with tabs[6]:
        _render_forecast_tab(CHAT_MODEL_ID)
    with tabs[7]:
        _render_comprehensive_tab(CHAT_MODEL_ID)
    with tabs[8]:
        _render_cost_center_tab()
