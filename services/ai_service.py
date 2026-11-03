# -*- coding: utf-8 -*-
"""Hokama ERP - cloud AI service (Groq API / GPT-OSS 20B).

Python 3.10 compatible. Uses only the standard library for HTTP and key storage.
Public database/helper names are preserved for compatibility with the existing UI.
The service never logs API keys or prompt contents.
"""
from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------
AI_PROVIDER = "Groq"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
GROQ_MODEL_ID = os.environ.get("ERP_AI_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
# Backward-compatible name: older UI code imports LOCAL_AI_MODEL.
LOCAL_AI_MODEL = GROQ_MODEL_ID
DEFAULT_MAX_TOKENS = 1400
MAX_COMPLETION_TOKENS = 8192  # App-side cap; Groq GPT-OSS 20B allows up to 65,536 output tokens.
MAX_PROMPT_CHARS = 15000
REQUEST_TIMEOUT_SECONDS = 100
CONNECT_TIMEOUT_SECONDS = 20
API_KEY_ENV_NAMES = ("GROQ_API_KEY", "ERP_GROQ_API_KEY")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parents[1]

DB_PATH = str(BASE_DIR / "data" / "erp.db")

# ---------------------------------------------------------------------
# Logging (never include user content, secrets, or authorization headers)
# ---------------------------------------------------------------------
def _get_log_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    path = root / "HokamaERP" / "logs"
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path / "ai_service.log"
    except OSError:
        fallback = BASE_DIR / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback / "ai_service.log"


_logger = logging.getLogger("hokama.ai_service")
_logger.setLevel(logging.INFO)
_logger.propagate = False
if not _logger.handlers:
    try:
        handler = RotatingFileHandler(_get_log_path(), maxBytes=1_500_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        _logger.addHandler(handler)
    except Exception:
        _logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------
# Secure local API-key storage (Windows DPAPI)
# ---------------------------------------------------------------------
_key_lock = threading.RLock()
_memory_api_key: Optional[str] = None


def _secret_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    path = root / "HokamaERP" / "secrets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _secret_path() -> Path:
    return _secret_dir() / "groq_api_key.dpapi"


def _dpapi_transform(data: bytes, protect: bool) -> bytes:
    """Encrypt/decrypt bytes with Windows Data Protection API (user-bound)."""
    if os.name != "nt":
        raise OSError("DPAPI متاح على Windows فقط")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    def to_blob(raw: bytes):
        buffer = ctypes.create_string_buffer(raw)
        return DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer

    in_blob, in_buffer = to_blob(data)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_ptr = ctypes.POINTER(DATA_BLOB)
    crypt32.CryptProtectData.argtypes = [blob_ptr, ctypes.c_wchar_p, blob_ptr, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_ulong, blob_ptr]
    crypt32.CryptProtectData.restype = ctypes.c_bool
    crypt32.CryptUnprotectData.argtypes = [blob_ptr, ctypes.c_void_p, blob_ptr, ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_ulong, blob_ptr]
    crypt32.CryptUnprotectData.restype = ctypes.c_bool
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(in_blob), "Hokama ERP Groq API Key", None, None, None, 0x1, ctypes.byref(out_blob))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0x1, ctypes.byref(out_blob))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        del in_buffer


def save_groq_api_key(api_key: str) -> Tuple[bool, str]:
    """Persist API key encrypted with Windows DPAPI and cache it in memory."""
    global _memory_api_key
    key = str(api_key or "").strip()
    if not key:
        return False, "أدخل مفتاح Groq أولاً."
    if len(key) < 20 or any(ch.isspace() for ch in key):
        return False, "صيغة المفتاح تبدو غير صحيحة؛ تحقق من نسخه كاملاً دون مسافات."
    with _key_lock:
        _memory_api_key = key
        if os.name != "nt":
            return True, "تم حفظ المفتاح في ذاكرة الجلسة فقط. للحفظ بين مرات التشغيل استخدم Windows."
        try:
            encrypted = _dpapi_transform(key.encode("utf-8"), True)
            target = _secret_path()
            temp = target.with_suffix(".tmp")
            temp.write_bytes(encrypted)
            try:
                os.replace(str(temp), str(target))
            finally:
                if temp.exists():
                    temp.unlink(missing_ok=True)
            return True, "تم حفظ المفتاح مشفراً على هذا المستخدم في Windows."
        except Exception as exc:
            _logger.warning("DPAPI key storage failed (%s)", type(exc).__name__)
            return True, "المفتاح متاح لهذه الجلسة، لكن تعذر حفظه المشفر؛ ستحتاج إلى إدخاله مجدداً بعد إعادة التشغيل."


def get_groq_api_key() -> Optional[str]:
    with _key_lock:
        if _memory_api_key:
            return _memory_api_key
        for env_name in API_KEY_ENV_NAMES:
            candidate = os.environ.get(env_name, "").strip()
            if candidate:
                return candidate
        if os.name == "nt":
            try:
                path = _secret_path()
                if path.is_file():
                    key = _dpapi_transform(path.read_bytes(), False).decode("utf-8").strip()
                    if key:
                        return key
            except Exception as exc:
                _logger.warning("Could not read protected API key (%s)", type(exc).__name__)
        return None


def get_api_key_status() -> Dict[str, Any]:
    present = bool(get_groq_api_key())
    # Report the durable source first even though the active key is also cached in memory.
    if os.name == "nt" and _secret_path().is_file():
        source = "windows_dpapi"
    elif any(os.environ.get(n, "").strip() for n in API_KEY_ENV_NAMES):
        source = "environment"
    elif _memory_api_key:
        source = "memory"
    else:
        source = "none"
    return {"configured": present, "source": source, "persistent": source in ("windows_dpapi", "environment")}


def delete_groq_api_key() -> Tuple[bool, str]:
    global _memory_api_key
    with _key_lock:
        _memory_api_key = None
        try:
            if os.name == "nt" and _secret_path().exists():
                _secret_path().unlink()
            return True, "تم حذف المفتاح المحفوظ محلياً. تحقق أيضاً من متغيرات البيئة إن كنت قد أضفته إليها."
        except Exception as exc:
            return False, "تعذر حذف الملف المحمي: " + str(exc)


# ---------------------------------------------------------------------
# Database bootstrap and connections
# ---------------------------------------------------------------------
_db_schema_ready = False
_db_schema_lock = threading.Lock()
_cache: Dict[str, tuple] = {}
_cache_lock = threading.RLock()
CACHE_TTL_SECONDS = 90


def _ensure_database_ready() -> None:
    global DB_PATH, _db_schema_ready
    if _db_schema_ready:
        return
    with _db_schema_lock:
        if _db_schema_ready:
            return
        try:
            import database as core_database
        except Exception as exc:
            raise RuntimeError("تعذر استيراد database.py لتهيئة قاعدة بيانات النظام: " + str(exc)) from exc
        DB_PATH = os.path.abspath(core_database.DB_PATH)
        core_database.init_db()
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            required = {"journal_lines", "journal_entries", "accounts", "invoices", "customers", "suppliers", "products", "employees", "employee_salaries"}
            missing = sorted(required - tables)
            if missing:
                raise RuntimeError("الجداول الأساسية غير موجودة: " + ", ".join(missing))
            columns = {row[1] for row in conn.execute("PRAGMA table_info(journal_lines)").fetchall()}
            missing_cols = sorted({"id", "entry_id", "account_name", "debit", "credit"} - columns)
            if missing_cols:
                raise RuntimeError("تنقص journal_lines الأعمدة: " + ", ".join(missing_cols))
        finally:
            conn.close()
        _db_schema_ready = True
        _logger.info("ERP database ready")
        create_ai_tables()


def get_conn() -> sqlite3.Connection:
    _ensure_database_ready()
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def create_ai_tables() -> None:
    conn = get_conn()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS ai_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model TEXT,
            tab_name TEXT,
            timestamp TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_chat_session_id ON ai_chat_history(session_id, id)")
        conn.commit()
    finally:
        conn.close()

# ---------------------------------------------------------------------
# Groq HTTP transport and prompts
# ---------------------------------------------------------------------
MASTER_FINANCIAL_PROMPT = """أنت المستشار المالي والإداري الذكي المدمج في Hokama ERP.
المهمة: تحويل بيانات النظام المرفقة إلى تفسير مهني دقيق ومفيد للإدارة والمحاسبة.
اللغة: أجب بالعربية الفصحى المهنية، مع الحفاظ على أسماء الحقول والحسابات كما وردت عند الحاجة.
الدقة: لا تخترع رقماً أو اسماً أو تاريخاً أو رصيداً أو سبباً. لا تستنتج معلومة غير موجودة باعتبارها حقيقة.
مصدر الحقيقة: بيانات النظام المقدمة فقط. إذا كان السؤال عاماً ولا يحتاج بيانات النظام، وضح ذلك ولا تزعم أنك بحثت في الإنترنت.
التحليل: فرّق بين (1) حقيقة ظاهرة في البيانات، (2) تفسير محتمل، (3) توصية مقترحة.
المحاسبة: لا تعتمد قيداً ولا تعدل قاعدة البيانات ولا تدّع تنفيذ أي إجراء. تحقق من الاتزان عند توافر المدين والدائن فقط.
الاحتيال: لا تصف أي عملية بأنها احتيال مؤكد؛ استخدم تعبير مؤشر يستحق الفحص وحدد سبب الاشتباه والبيانات الناقصة.
الخصوصية: لا تعيد عرض بيانات شخصية غير لازمة للإجابة.
الجودة: ابدأ بخلاصة تنفيذية، ثم تحليل منظم، ثم توصيات عملية ذات أولوية. اذكر القيود بوضوح.
التنسيق: استخدم عناوين قصيرة ونقاطاً واضحة وجداول نصية صغيرة عند فائدتها. لا تعرض سلسلة التفكير الداخلية؛ اعرض النتائج والمبررات المختصرة فقط."""


def unload_local_model() -> None:
    """Backward-compatible no-op; inference now runs remotely through Groq."""
    return None


def get_model_status() -> Dict[str, Any]:
    key_status = get_api_key_status()
    return {
        "provider": AI_PROVIDER,
        "model_name": GROQ_MODEL_ID,
        "model_path": GROQ_MODEL_ID,
        "exists": True,
        "loaded": False,
        "configured": key_status["configured"],
        "key_source": key_status["source"],
        "key_persistent": key_status["persistent"],
        "context_size": 131072,
        "max_output_tokens": 65536,  # Provider model limit
        "app_max_completion_tokens": MAX_COMPLETION_TOKENS,  # Local application cap
        "endpoint": GROQ_API_URL,
    }


def _normalize_messages(system_prompt: str, user_query: str,
                        history: Optional[Sequence[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    system_text = str(system_prompt or MASTER_FINANCIAL_PROMPT).strip()
    user_text = str(user_query or "").strip()
    if len(system_text) > 5000:
        user_text = "سياق المهمة والبيانات:\n" + system_text + "\n\nطلب المستخدم:\n" + user_text
        system_text = MASTER_FINANCIAL_PROMPT
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_text}]
    if history:
        for item in list(history)[-4:]:
            role = str(item.get("role", "")).lower()
            content = str(item.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                # A short rolling window controls spend and protects account-level TPM limits.
                messages.append({"role": role, "content": content[:1200]})
    if len(user_text) > MAX_PROMPT_CHARS:
        user_text = user_text[:MAX_PROMPT_CHARS] + "\n[اختُصر جزء من السياق لتقليل حجم الطلب]"
    messages.append({"role": "user", "content": user_text})
    return messages


def _friendly_http_error(code: int, body: str, retry_after: Optional[str] = None) -> str:
    try:
        parsed = json.loads(body or "{}")
        err = parsed.get("error", {}) if isinstance(parsed, dict) else {}
        detail = str(err.get("message") or err.get("type") or "")[:350] if isinstance(err, dict) else str(err)[:350]
    except Exception:
        detail = (body or "")[:250]
    if code == 400:
        return "رفضت Groq صيغة الطلب أو أحد إعداداته. راجع سجل التطبيق أو إعدادات النموذج. " + detail
    if code == 401:
        return "مفتاح Groq غير صحيح أو منتهي. أدخل مفتاحاً صالحاً من لوحة Groq."
    if code == 403:
        return "المفتاح لا يملك صلاحية استخدام هذا النموذج أو أن الوصول إليه غير متاح لحسابك. " + detail
    if code == 404:
        return "لم يتم العثور على النموذج أو نقطة الاتصال المطلوبة. تحقق من معرف النموذج."
    if code == 429:
        wait = f" مدة الانتظار المعلنة: {retry_after} ثانية." if retry_after else ""
        return "تم بلوغ حد الطلبات أو التوكنات في Groq. خفّض حجم السياق أو أعد المحاولة لاحقاً." + wait
    if code in (500, 502, 503, 504):
        return "خدمة Groq تواجه مشكلة مؤقتة. أعد المحاولة بعد قليل."
    return f"تعذر إكمال الطلب عبر Groq (HTTP {code}). " + detail


def _post_groq(payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        GROQ_API_URL,
        data=raw,
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "HokamaERP-AI/2.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(8 * 1024 * 1024).decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(64 * 1024).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        raise RuntimeError(_friendly_http_error(exc.code, body, retry_after)) from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        _logger.warning("Groq network connection failed (%s)", type(reason).__name__)
        raise RuntimeError("تعذر الاتصال بخدمة Groq. تحقق من الإنترنت أو إعدادات الجدار الناري ثم أعد المحاولة.") from None
    except TimeoutError:
        raise RuntimeError("انتهت مهلة الاتصال بخدمة Groq. أعد المحاولة أو قلل حجم التحليل.") from None
    except json.JSONDecodeError:
        raise RuntimeError("وصل رد غير مفهوم من خدمة Groq. أعد المحاولة.") from None


def test_groq_connection(api_key: Optional[str] = None) -> Tuple[bool, str]:
    key = str(api_key or get_groq_api_key() or "").strip()
    if not key:
        return False, "أدخل مفتاح Groq أولاً."
    payload = {
        "model": GROQ_MODEL_ID,
        "messages": [
            {"role": "system", "content": "أجب بكلمة واحدة فقط."},
            {"role": "user", "content": "اكتب: متصل"},
        ],
        "max_completion_tokens": 32,
        "reasoning_effort": "low",
        "include_reasoning": False,
        "temperature": 0.2,
        "stream": False,
    }
    try:
        response = _post_groq(payload, key)
        choices = response.get("choices") or []
        if choices and (choices[0].get("message") or {}).get("content"):
            return True, "الاتصال ناجح، والنموذج استجاب بنجاح."
        return False, "تم الاتصال لكن النموذج لم يرجع محتوى نصياً."
    except Exception as exc:
        return False, str(exc)


def query_groq(system_prompt: str, user_query: str, model: Optional[str] = None,
               max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = 0.35,
               history: Optional[Sequence[Dict[str, str]]] = None,
               reasoning_effort: str = "medium", api_key: Optional[str] = None,
               **kwargs) -> str:
    """Generate a final Arabic answer from Groq; compatible with the previous UI signature."""
    started = time.perf_counter()
    key = str(api_key or get_groq_api_key() or "").strip()
    if not key:
        return "مفتاح Groq غير مضاف. افتح إعدادات المساعد في الشريط الجانبي وأضف مفتاح API أولاً."
    messages = _normalize_messages(system_prompt, user_query, history)
    try:
        requested = int(max_tokens)
    except (TypeError, ValueError):
        requested = DEFAULT_MAX_TOKENS
    token_limit = max(128, min(requested, MAX_COMPLETION_TOKENS))
    try:
        temp = float(temperature)
    except (TypeError, ValueError):
        temp = 0.35
    temp = max(0.0, min(temp, 1.0))
    effort = str(reasoning_effort or "medium").lower()
    if effort not in ("low", "medium", "high"):
        effort = "medium"

    payload: Dict[str, Any] = {
        "model": str(model or GROQ_MODEL_ID),
        "messages": messages,
        "max_completion_tokens": token_limit,
        "temperature": temp,
        "top_p": 0.9,
        "reasoning_effort": effort,
        # Suppress chain-of-thought; users receive the answer and concise reasons only.
        "include_reasoning": False,
        "stream": False,
    }
    try:
        response = _post_groq(payload, key)
        choices = response.get("choices") or []
        if not choices:
            return "لم يرجع النموذج إجابة. حاول تقليل البيانات المرسلة أو إعادة صياغة السؤال."
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "\n".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
        content = str(content or "").strip()
        if not content:
            finish = (choices[0].get("finish_reason") or "").lower()
            if finish == "length":
                return "انتهى حد التوليد قبل اكتمال الإجابة. أعد المحاولة بحد توكن أعلى أو بسياق أقصر."
            return "لم ينتج النموذج نصاً نهائياً. أعد المحاولة مع طلب أكثر تحديداً."
        usage = response.get("usage") or {}
        _logger.info("Groq response completed in %.2fs | prompt=%s | completion=%s | model=%s",
                     time.perf_counter() - started, usage.get("prompt_tokens", "?"),
                     usage.get("completion_tokens", "?"), payload["model"])
        return content
    except Exception as exc:
        _logger.warning("Groq inference failed: %s", str(exc)[:300])
        return str(exc) if isinstance(exc, RuntimeError) else "حدث خطأ غير متوقع أثناء الاتصال بخدمة الذكاء الاصطناعي."


def query_local_ai(system_prompt, user_query, model=None, max_tokens=DEFAULT_MAX_TOKENS,
                   temperature=0.35, history=None, **kwargs):
    """Compatibility alias for older callers; inference is cloud-based now."""
    return query_groq(system_prompt, user_query, model=model, max_tokens=max_tokens,
                      temperature=temperature, history=history, **kwargs)

# ---------------------------------------------------------------------
# Chat history/session management
# ---------------------------------------------------------------------
def save_chat_history(session_id, role, content, model="", tab_name=""):
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO ai_chat_history
            (session_id, role, content, model, tab_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (str(session_id), str(role), str(content), model or GROQ_MODEL_ID,
             str(tab_name or ""), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    finally:
        conn.close()


def get_chat_history(session_id=None, limit=20):
    conn = get_conn()
    try:
        limit = max(1, min(int(limit), 500))
        if session_id:
            rows = conn.execute("SELECT * FROM ai_chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM ai_chat_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def get_chat_sessions():
    conn = get_conn()
    try:
        rows = conn.execute("""SELECT session_id, MIN(timestamp) AS first_message,
            COUNT(*) AS message_count FROM ai_chat_history GROUP BY session_id
            ORDER BY MAX(id) DESC LIMIT 25""").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def compress_chat_memory(session_id, model=None):
    history = get_chat_history(session_id, limit=8)
    if not history:
        return ""
    dialogue = "\n".join(f"{x['role']}: {x['content']}" for x in history)
    return query_groq("لخص المحادثة بالعربية في نقاط قصيرة دون إضافة معلومات.", dialogue,
                      max_tokens=350, temperature=0.2, reasoning_effort="low")

# ---------------------------------------------------------------------
# Cached, structured ERP snapshots (source of facts; AI only interprets)
# ---------------------------------------------------------------------
def _cache_get(key):
    with _cache_lock:
        item = _cache.get(key)
        if not item:
            return None
        data, timestamp = item
        if time.monotonic() - timestamp < CACHE_TTL_SECONDS:
            return data
        _cache.pop(key, None)
        return None


def _cache_set(key, data):
    with _cache_lock:
        _cache[key] = (data, time.monotonic())


def clear_snapshot_cache():
    with _cache_lock:
        _cache.clear()


def validate_financial_snapshot(snap):
    warnings = []
    if snap.get("revenue", 0) < 0:
        warnings.append("الإيرادات سالبة؛ تحقق من تصنيف الحسابات وترحيل القيود.")
    if snap.get("assets", 0) <= 0:
        warnings.append("الأصول صفر أو سالبة؛ قد تكون البيانات غير مكتملة أو التصنيفات بحاجة مراجعة.")
    if snap.get("profit_margin", 0) > 80:
        warnings.append("هامش الربح مرتفع بصورة تستحق التحقق من اكتمال تسجيل المصروفات.")
    return warnings


def get_financial_snapshot():
    cached = _cache_get("financial_snapshot")
    if cached is not None:
        return cached
    conn = get_conn()
    try:
        def scalar(sql):
            return float(conn.execute(sql).fetchone()[0] or 0)
        revenue = scalar("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'")
        expenses = scalar("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'")
        assets = scalar("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '1%'")
        liabilities = scalar("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '2%'")
        equity = scalar("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '3%'")
        top_customers = [dict(r) for r in conn.execute("""SELECT c.name, SUM(i.total) AS total FROM invoices i
            JOIN customers c ON i.customer_id=c.id WHERE i.type='sale' AND i.status='completed'
            GROUP BY c.id ORDER BY total DESC LIMIT 3""").fetchall()]
        top_suppliers = [dict(r) for r in conn.execute("""SELECT s.name, SUM(i.total) AS total FROM invoices i
            JOIN suppliers s ON i.supplier_id=s.id WHERE i.type='purchase' AND i.status='completed'
            GROUP BY s.id ORDER BY total DESC LIMIT 3""").fetchall()]
        sales_trend = [dict(r) for r in conn.execute("""SELECT strftime('%Y-%m', invoice_date) AS month, SUM(total) AS total
            FROM invoices WHERE type='sale' AND status='completed' GROUP BY month ORDER BY month DESC LIMIT 6""").fetchall()]
    finally:
        conn.close()
    net_income = revenue - expenses
    snap = {
        "revenue": round(revenue, 2), "expenses": round(expenses, 2),
        "net_income": round(net_income, 2), "assets": round(assets, 2),
        "liabilities": round(liabilities, 2), "equity": round(equity, 2),
        "profit_margin": round(net_income / revenue * 100, 1) if revenue > 0 else 0,
        "debt_ratio": round(liabilities / assets * 100, 1) if assets > 0 else 0,
        "roa": round(net_income / assets * 100, 1) if assets > 0 else 0,
        "top_customers": top_customers, "top_suppliers": top_suppliers,
        "sales_trend": sales_trend,
    }
    snap["warnings"] = validate_financial_snapshot(snap)
    _cache_set("financial_snapshot", snap)
    return snap


def get_inventory_snapshot():
    cached = _cache_get("inventory_snapshot")
    if cached is not None:
        return cached
    conn = get_conn()
    try:
        products = [dict(r) for r in conn.execute("""SELECT name, quantity, reorder_level, selling_price, purchase_price
            FROM products ORDER BY quantity ASC""").fetchall()]
    finally:
        conn.close()
    low_stock = [p for p in products if (p.get("quantity") or 0) < (p.get("reorder_level") or 0)]
    for p in products:
        selling, purchase = p.get("selling_price") or 0, p.get("purchase_price") or 0
        p["profit_margin"] = round((selling - purchase) / selling * 100, 1) if selling > 0 and purchase > 0 else 0
        qty, reorder = p.get("quantity") or 0, p.get("reorder_level") or 0
        if qty <= 0:
            p["recommendation"] = "نفد المخزون"
        elif qty < reorder:
            p["recommendation"] = f"طلب {reorder - qty} وحدة"
        elif qty < reorder * 2:
            p["recommendation"] = "مراقبة"
        else:
            p["recommendation"] = "مستوى مريح وفق حد إعادة الطلب المسجل"
    snap = {"total_products": len(products), "low_stock_count": len(low_stock),
            "low_stock_items": low_stock[:15],
            "top_products": sorted(products, key=lambda x: x.get("quantity") or 0, reverse=True)[:10],
            "all_products": products[:30]}
    _cache_set("inventory_snapshot", snap)
    return snap


def get_business_snapshot():
    cached = _cache_get("business_snapshot")
    if cached is not None:
        return cached
    conn = get_conn()
    try:
        top_customers = [dict(r) for r in conn.execute("""SELECT c.name, COUNT(i.id) AS invoice_count, SUM(i.total) AS total
            FROM invoices i JOIN customers c ON i.customer_id=c.id WHERE i.type='sale' AND i.status='completed'
            GROUP BY c.id ORDER BY total DESC LIMIT 5""").fetchall()]
        top_suppliers = [dict(r) for r in conn.execute("""SELECT s.name, COUNT(i.id) AS invoice_count, SUM(i.total) AS total
            FROM invoices i JOIN suppliers s ON i.supplier_id=s.id WHERE i.type='purchase' AND i.status='completed'
            GROUP BY s.id ORDER BY total DESC LIMIT 5""").fetchall()]
        total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        total_suppliers = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    finally:
        conn.close()
    snap = {"total_customers": total_customers, "total_suppliers": total_suppliers,
            "top_customers": top_customers, "top_suppliers": top_suppliers}
    _cache_set("business_snapshot", snap)
    return snap


def get_hr_snapshot():
    cached = _cache_get("hr_snapshot")
    if cached is not None:
        return cached
    conn = get_conn()
    try:
        employees = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        salary = conn.execute("SELECT COALESCE(SUM(basic_salary),0) FROM employee_salaries").fetchone()[0]
    finally:
        conn.close()
    snap = {"total_employees": employees, "total_monthly_salary": round(float(salary or 0), 2)}
    _cache_set("hr_snapshot", snap)
    return snap


def get_trend_snapshot():
    cached = _cache_get("trend_snapshot")
    if cached is not None:
        return cached
    conn = get_conn()
    try:
        rows = conn.execute("""SELECT strftime('%Y-%m', invoice_date) AS month,
            SUM(CASE WHEN type='sale' THEN total ELSE 0 END) AS sales,
            SUM(CASE WHEN type='purchase' THEN total ELSE 0 END) AS purchases
            FROM invoices WHERE status='completed' GROUP BY month ORDER BY month DESC LIMIT 12""").fetchall()
    finally:
        conn.close()
    snap = [dict(r) for r in rows]
    _cache_set("trend_snapshot", snap)
    return snap


def get_cost_center_snapshot():
    cached = _cache_get("cost_center_snapshot")
    if cached is not None:
        return cached
    from services import cost_center_service as ccs
    summary = []
    for center in ccs.get_all_cost_centers(active_only=True):
        balance = ccs.get_cost_center_balance(center["id"])
        summary.append({"code": center.get("code"), "name": center.get("name"), "net_balance": balance.get("net")})
    _cache_set("cost_center_snapshot", summary)
    return summary


def build_ai_context(include_cost_centers=True):
    ctx: Dict[str, Any] = {}
    ctx.update(get_financial_snapshot())
    ctx.update(get_inventory_snapshot())
    ctx.update(get_business_snapshot())
    ctx.update(get_hr_snapshot())
    ctx["trends"] = get_trend_snapshot()
    if include_cost_centers:
        try:
            ctx["cost_centers"] = get_cost_center_snapshot()
        except Exception as exc:
            _logger.warning("Cost centre snapshot unavailable (%s)", type(exc).__name__)
            ctx["cost_centers"] = []
    return ctx


def get_comprehensive_data():
    return build_ai_context()


def get_inventory_data():
    snap = get_inventory_snapshot()
    return snap["low_stock_items"], snap["all_products"]


def get_employee_info(name):
    conn = get_conn()
    try:
        emp = conn.execute("SELECT * FROM employees WHERE name LIKE ?", (f"%{name}%",)).fetchone()
        if not emp:
            return None, None
        salary = conn.execute("SELECT * FROM employee_salaries WHERE employee_id=?", (emp["id"],)).fetchone()
        return dict(emp), dict(salary) if salary else None
    finally:
        conn.close()


def get_recent_entries():
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 200").fetchall()]
    finally:
        conn.close()


def get_all_accounts():
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()]
    finally:
        conn.close()


def get_financial_ratios():
    fin = get_financial_snapshot()
    return {"هامش الربح": f"{fin['profit_margin']:.1f}%", "نسبة المديونية": f"{fin['debt_ratio']:.1f}%",
            "العائد على الأصول": f"{fin['roa']:.1f}%", "صافي الدخل": f"{fin['net_income']:,.2f}"}


def get_trend_analysis():
    return get_trend_snapshot()

# ---------------------------------------------------------------------
# Cost-centre analysis
# ---------------------------------------------------------------------
def analyze_cost_center_performance(center_id):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center:
        return "مركز التكلفة غير موجود."
    balance = ccs.get_cost_center_balance(center_id)
    income = ccs.get_cost_center_income_statement(center_id, "2020-01-01", datetime.now().strftime("%Y-%m-%d"))
    facts = {"المركز": center.get("name"), "إجمالي المدين": balance.get("total_debit"),
             "إجمالي الدائن": balance.get("total_credit"), "الصافي": balance.get("net"),
             "الإيرادات": income.get("income"), "المصروفات": income.get("expenses"), "صافي الربح": income.get("net_profit")}
    return query_groq(MASTER_FINANCIAL_PROMPT, "حلل مركز التكلفة اعتماداً على البيانات التالية فقط، وقدم خلاصة ومؤشرات ومخاطر وتوصيات.\n" + json.dumps(facts, ensure_ascii=False), max_tokens=1600)


def compare_cost_centers():
    summary = get_cost_center_snapshot()
    if not summary:
        return "لا توجد مراكز تكلفة أو بيانات كافية للمقارنة."
    return query_groq(MASTER_FINANCIAL_PROMPT, "قارن مراكز التكلفة الواردة في البيانات، واذكر أساس المقارنة وأي نقص يمنع حكماً عادلاً.\n" + json.dumps(summary, ensure_ascii=False), max_tokens=1800)


def predict_cost_center_expenses(center_id, months=3):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center:
        return "مركز التكلفة غير موجود."
    conn = get_conn()
    try:
        history = [dict(r) for r in conn.execute("""SELECT strftime('%Y-%m', je.date) AS month, SUM(cca.amount) AS total
            FROM cost_center_allocations cca JOIN journal_lines jl ON cca.journal_line_id=jl.id
            JOIN journal_entries je ON jl.entry_id=je.id WHERE cca.cost_center_id=? AND jl.debit>0
            GROUP BY month ORDER BY month DESC LIMIT 12""", (center_id,)).fetchall()]
    finally:
        conn.close()
    if not history:
        return "لا تتوفر بيانات تاريخية كافية لإعداد توقع لهذا المركز."
    task = {"مركز التكلفة": center.get("name"), "أفق التوقع بالأشهر": max(1, min(int(months), 12)), "التاريخ": history}
    return query_groq(MASTER_FINANCIAL_PROMPT, "قدم قراءة للاتجاه التاريخي وتوقعاً استرشادياً مشروطاً، ولا تقدم أرقاماً مستقبلية مصطنعة.\n" + json.dumps(task, ensure_ascii=False), max_tokens=1500, reasoning_effort="high")


def get_cost_center_budget_analysis(center_id, fiscal_year):
    from services import cost_center_service as ccs
    variance = ccs.get_budget_variance(center_id, fiscal_year)
    if not variance:
        return "لا توجد موازنة مسجلة أو لا تتوفر بيانات انحراف لهذا المركز والسنة."
    return query_groq(MASTER_FINANCIAL_PROMPT, "حلل انحرافات الموازنة للسنة المحددة. لا تفترض أسباب الانحراف غير المثبتة بالبيانات.\n" + json.dumps(variance, ensure_ascii=False, default=str), max_tokens=1500)

# ---------------------------------------------------------------------
# Journal entry extraction and safe templates (drafts only)
# ---------------------------------------------------------------------
def extract_entry_data(text, model=None):
    system = MASTER_FINANCIAL_PROMPT + "\nعند استخراج مسودة قيد: أخرج JSON صالحاً فقط بمفاتيح operation_type وlines؛ كل سطر يحوي account وamount وside (debit/credit). لا تخترع حساباً أو مبلغاً."
    response = query_groq(system, str(text), model=model, max_tokens=900, temperature=0.1, reasoning_effort="low")
    try:
        start, end = response.find("{"), response.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        data = json.loads(response[start:end])
        if not isinstance(data, dict) or not isinstance(data.get("lines"), list) or not data["lines"]:
            return None
        for line in data["lines"]:
            if not isinstance(line, dict) or line.get("side") not in ("debit", "credit"):
                return None
            amount = float(line.get("amount", 0))
            account = str(line.get("account") or "").strip()
            if amount <= 0 or not account:
                return None
            line["amount"] = round(amount, 2)
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def build_balanced_entry(extracted_data):
    if not extracted_data or not extracted_data.get("lines"):
        return None, "فشل استخراج بيانات القيد."
    lines = extracted_data["lines"]
    debit = sum(float(x.get("amount", 0)) for x in lines if x.get("side") == "debit")
    credit = sum(float(x.get("amount", 0)) for x in lines if x.get("side") == "credit")
    if not any(x.get("side") == "debit" for x in lines) or not any(x.get("side") == "credit" for x in lines):
        return None, "يجب أن يحتوي القيد على طرف مدين وطرف دائن على الأقل."
    if abs(debit - credit) >= 0.01:
        return None, f"القيد غير متوازن: المدين {debit:,.2f} والدائن {credit:,.2f}. صحح البيانات يدوياً."
    return {"lines": list(lines), "total_debit": round(debit, 2), "total_credit": round(credit, 2),
            "is_balanced": True, "has_auto_correction": False}, None


def format_entry_display(entry_data):
    if not entry_data:
        return "لا توجد بيانات"
    lines = []
    for line in entry_data.get("lines", []):
        side = "مدين" if line.get("side") == "debit" else "دائن"
        lines.append(f"{side} | {line.get('account', '')} | {float(line.get('amount', 0)):,.2f}")
    lines.append(f"\nالإجمالي: مدين {entry_data['total_debit']:,.2f} = دائن {entry_data['total_credit']:,.2f}")
    return "\n".join(lines)


def calculate_confidence(ext, bal):
    if not ext or not bal or not bal.get("lines") or not bal.get("is_balanced"):
        return 0
    return 60 if len(bal["lines"]) >= 2 else 35


def get_confidence_level(conf):
    if conf >= 90:
        return "مكتمل شكلياً — يحتاج مراجعة", "#10B981"
    if conf >= 60:
        return "مسودة أولية — تحتاج مراجعة", "#F59E0B"
    return "غير مكتمل — لا تعتمد", "#EF4444"


def generate_entry_safe(text, model=None):
    ext = extract_entry_data(text, model)
    if not ext:
        return None, "تعذر استخراج قيد صالح. أعد صياغة العملية وحدد الحسابات والمبالغ.", 0, "غير مكتمل", "#EF4444"
    entry, error = build_balanced_entry(ext)
    if error:
        return None, error, 0, "غير متوازن", "#EF4444"
    confidence = calculate_confidence(ext, entry)
    label, color = get_confidence_level(confidence)
    return entry, format_entry_display(entry) + f"\n\nالتقييم: {label}", confidence, label, color


ENTRY_TEMPLATES = {
    "بيع نقداً": {"description": "بيع بضاعة نقداً", "lines": [{"account": "النقدية", "side": "debit"}, {"account": "المبيعات", "side": "credit"}]},
    "بيع بالآجل": {"description": "بيع بضاعة بالآجل", "lines": [{"account": "العملاء", "side": "debit"}, {"account": "المبيعات", "side": "credit"}]},
    "شراء نقداً": {"description": "شراء بضاعة نقداً", "lines": [{"account": "المخزون", "side": "debit"}, {"account": "النقدية", "side": "credit"}]},
    "شراء بالآجل": {"description": "شراء بضاعة بالآجل", "lines": [{"account": "المخزون", "side": "debit"}, {"account": "الموردين", "side": "credit"}]},
    "قبض من عميل": {"description": "استلام دفعة من عميل", "lines": [{"account": "النقدية", "side": "debit"}, {"account": "العملاء", "side": "credit"}]},
    "دفع لمورد": {"description": "سداد دفعة لمورد", "lines": [{"account": "الموردين", "side": "debit"}, {"account": "النقدية", "side": "credit"}]},
    "سداد مصروف": {"description": "سداد مصروف نقداً", "lines": [{"account": "{expense_name}", "side": "debit"}, {"account": "النقدية", "side": "credit"}]},
}


def generate_template_entry(operation_type, amount, cash_amount=None, credit_amount=None,
                            expense_name=None, vat_rate=None, adjustment_side=None, inventory_side=None):
    template = ENTRY_TEMPLATES.get(operation_type)
    if not template:
        return None, "العملية غير مدعومة في القوالب الحالية", 0, "غير مدعوم", "#EF4444"
    try:
        value = round(float(amount), 2)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return None, "أدخل مبلغاً أكبر من صفر", 0, "غير مكتمل", "#EF4444"
    if "{expense_name}" in [x["account"] for x in template["lines"]] and not str(expense_name or "").strip():
        return None, "حدد اسم حساب المصروف قبل توليد المسودة.", 0, "غير مكتمل", "#EF4444"
    lines = []
    for item in template["lines"]:
        account = str(expense_name).strip() if item["account"] == "{expense_name}" else item["account"]
        lines.append({"account": account, "amount": value, "side": item["side"]})
    entry, error = build_balanced_entry({"lines": lines})
    if error:
        return None, error, 0, "غير متوازن", "#EF4444"
    return entry, format_entry_display(entry) + "\n\nقالب قياسي — راجع الحسابات والضريبة قبل الاعتماد.", 80, "قالب قياسي يحتاج مراجعة", "#F59E0B"


def get_available_operations():
    return list(ENTRY_TEMPLATES.keys())


def get_operation_description(operation):
    return ENTRY_TEMPLATES.get(operation, {}).get("description", "")


def is_mixed_operation(operation):
    return operation in ("بيع مختلط", "شراء مختلط")


def is_vat_operation(operation):
    return operation in ("بيع شامل الضريبة", "شراء شامل الضريبة")


def is_salary_operation(operation):
    return operation == "رواتب موظفين"


def is_inventory_adjustment(operation):
    return operation == "تسوية مخزنية (جرد)"
