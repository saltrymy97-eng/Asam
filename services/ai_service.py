# -*- coding: utf-8 -*-
"""Hokama ERP - local AI service (llama.cpp / GGUF).

- Local-only inference; no cloud/API calls.
- Lazy, process-wide model loading.
- Serialized inference because a single llama.cpp context must not be
  concurrently mutated by Streamlit sessions.
- Backward-compatible query_groq() alias retained for the existing UI.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------
# Paths and configuration
# ---------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parents[1]

LOCAL_AI_MODEL = "TinyLlama-local"
MODEL_FILENAME = "TinyLlama_v1.1.Q2_K.gguf"


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


_CPU_COUNT = os.cpu_count() or 2
# The i3-3120M has two physical cores. Default to two worker threads;
# compare 2 and 4 on the target machine rather than assuming more is faster.
LLAMA_THREADS = _env_int("ERP_AI_THREADS", min(2, _CPU_COUNT), 1, 16)
LLAMA_BATCH_THREADS = _env_int("ERP_AI_BATCH_THREADS", LLAMA_THREADS, 1, 16)
LLAMA_CONTEXT_SIZE = _env_int("ERP_AI_CONTEXT", 1024, 512, 2048)
LLAMA_BATCH_SIZE = _env_int("ERP_AI_BATCH_SIZE", 64, 16, 256)
LLAMA_GPU_LAYERS = _env_int("ERP_AI_GPU_LAYERS", 0, 0, 128)
DEFAULT_MAX_TOKENS = _env_int("ERP_AI_MAX_TOKENS", 256, 64, 768)
MAX_PROMPT_CHARS = _env_int("ERP_AI_MAX_PROMPT_CHARS", 6500, 1000, 20000)

_model_override = os.environ.get("ERP_AI_MODEL_PATH", "").strip()
_model_candidates = []
if _model_override:
    _model_candidates.append(Path(_model_override).expanduser())
_model_candidates.extend([
    BASE_DIR / "models" / "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    BASE_DIR / "models" / MODEL_FILENAME,
    BASE_DIR / "models" / "ai-model.gguf",  # backwards-compatible deployed name
    BASE_DIR / MODEL_FILENAME,
])
MODEL_PATH = next((p.resolve() for p in _model_candidates if p.is_file()), _model_candidates[0].resolve())

# Leave chat_format unset by default: llama-cpp-python will use the GGUF
# tokenizer.chat_template metadata when available. An explicit override is
# available for a known chat-tuned model: ERP_AI_CHAT_FORMAT=zephyr, etc.
CHAT_FORMAT = os.environ.get("ERP_AI_CHAT_FORMAT", "").strip() or None

DB_PATH = str(BASE_DIR / "data" / "erp.db")
_llm = None
_llm_lock = threading.Lock()
_inference_lock = threading.Lock()
_db_schema_ready = False
_db_schema_lock = threading.Lock()
_cache: Dict[str, tuple] = {}
_cache_lock = threading.RLock()
CACHE_TTL_SECONDS = 180


# ---------------------------------------------------------------------
# Logging
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
        handler = RotatingFileHandler(
            _get_log_path(), maxBytes=1_500_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        _logger.addHandler(handler)
    except Exception:
        _logger.addHandler(logging.NullHandler())


def _log_exception(message: str) -> None:
    _logger.exception(message)


# ---------------------------------------------------------------------
# Database bootstrap and connections
# ---------------------------------------------------------------------
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
            raise RuntimeError(
                "تعذر استيراد database.py لتهيئة قاعدة بيانات النظام: " + str(exc)
            ) from exc

        DB_PATH = os.path.abspath(core_database.DB_PATH)
        core_database.init_db()

        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required_tables = {
                "journal_lines", "journal_entries", "accounts", "invoices",
                "customers", "suppliers", "products", "employees",
                "employee_salaries",
            }
            missing = sorted(required_tables - tables)
            if missing:
                raise RuntimeError(
                    f"الجداول الأساسية غير موجودة في {DB_PATH}: {', '.join(missing)}"
                )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(journal_lines)").fetchall()
            }
            required_columns = {"id", "entry_id", "account_name", "debit", "credit"}
            missing_columns = sorted(required_columns - columns)
            if missing_columns:
                raise RuntimeError(
                    "تنقص journal_lines الأعمدة: " + ", ".join(missing_columns)
                )
        finally:
            conn.close()
        _db_schema_ready = True
        _logger.info("Central database ready: %s", DB_PATH)
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT,
                tab_name TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_chat_session_id ON ai_chat_history(session_id, id)"
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Prompts and model lifecycle
# ---------------------------------------------------------------------
MASTER_FINANCIAL_PROMPT = """أنت مساعد حوكمة ERP المحلي.
أجب بالعربية الواضحة والمباشرة، وبأسلوب مهني.
استخدم البيانات المرفقة فقط ولا تخترع أرقاماً أو أسماء أو عمليات.
ميّز بوضوح بين الحقيقة المحسوبة والتقدير والتوصية.
لا تدّعِ تنفيذ عملية أو ترحيل قيد إلى قاعدة البيانات.
عند نقص المعلومات، اطلب توضيحاً بدلاً من التخمين.
اجعل الإجابة مناسبة لنموذج صغير: ابدأ بالخلاصة ثم أهم النقاط والتوصية."""


def get_model_status() -> Dict[str, Any]:
    """Lightweight status check; does not load the model."""
    exists = MODEL_PATH.is_file()
    return {
        "model_name": LOCAL_AI_MODEL,
        "model_path": str(MODEL_PATH),
        "exists": exists,
        "loaded": _llm is not None,
        "context_size": LLAMA_CONTEXT_SIZE,
        "threads": LLAMA_THREADS,
        "batch_threads": LLAMA_BATCH_THREADS,
        "batch_size": LLAMA_BATCH_SIZE,
        "chat_format_override": CHAT_FORMAT or "GGUF metadata / library auto-detection",
        "quantization_warning": "Q2_K قد يسبب فقداً واضحاً في جودة النصوص" if "Q2_K" in MODEL_PATH.name.upper() else "",
        "model_family_warning": (
            "اسم الملف لا يشير إلى إصدار Chat/Instruct؛ قد يكون نموذج Base غير مهيأ للمحادثة. "
            "تحقق من بطاقة النموذج ومعلومات GGUF قبل اعتماد الإجابات."
            if "TINYLLAMA" in MODEL_PATH.name.upper()
            and not any(tag in MODEL_PATH.name.upper() for tag in ("CHAT", "INSTRUCT"))
            else ""
        ),
    }


def _get_local_model():
    global _llm
    if _llm is not None:
        return _llm
    with _llm_lock:
        if _llm is not None:
            return _llm
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(
                "ملف نموذج الذكاء الاصطناعي غير موجود. المسار الذي تم فحصه:\n"
                + str(MODEL_PATH)
                + "\nضع الملف داخل مجلد models أو عيّن ERP_AI_MODEL_PATH."
            )
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "مكتبة llama-cpp-python غير متاحة في بيئة التشغيل الحالية."
            ) from exc

        kwargs = {
            "model_path": str(MODEL_PATH),
            "n_ctx": LLAMA_CONTEXT_SIZE,
            "n_threads": LLAMA_THREADS,
            "n_threads_batch": LLAMA_BATCH_THREADS,
            "n_batch": LLAMA_BATCH_SIZE,
            "n_gpu_layers": LLAMA_GPU_LAYERS,
            "use_mmap": True,
            "use_mlock": False,
            "verbose": False,
        }
        if CHAT_FORMAT:
            kwargs["chat_format"] = CHAT_FORMAT

        started = time.perf_counter()
        try:
            _llm = Llama(**kwargs)
        except TypeError as exc:
            # Older llama-cpp-python builds may not expose n_threads_batch.
            if "n_threads_batch" not in str(exc):
                raise
            kwargs.pop("n_threads_batch", None)
            _llm = Llama(**kwargs)
        elapsed = time.perf_counter() - started
        metadata = getattr(_llm, "metadata", {}) or {}
        has_chat_template = bool(metadata.get("tokenizer.chat_template")) if isinstance(metadata, dict) else False
        _logger.info(
            "Model loaded path=%s ctx=%s threads=%s batch_threads=%s batch=%s elapsed=%.2fs chat_template_metadata=%s",
            MODEL_PATH, LLAMA_CONTEXT_SIZE, LLAMA_THREADS, LLAMA_BATCH_THREADS,
            LLAMA_BATCH_SIZE, elapsed, has_chat_template,
        )
        if not has_chat_template and not CHAT_FORMAT:
            _logger.warning(
                "GGUF metadata did not expose tokenizer.chat_template; llama-cpp-python may use its fallback chat format."
            )
        return _llm


def unload_local_model() -> None:
    """Explicitly release the model, for maintenance/testing only."""
    global _llm
    with _inference_lock:
        with _llm_lock:
            old_model, _llm = _llm, None
            if old_model is not None:
                try:
                    old_model.close()
                except Exception:
                    pass
            del old_model


def _normalize_messages(system_prompt: str, user_query: str,
                        history: Optional[Sequence[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    system_text = str(system_prompt or MASTER_FINANCIAL_PROMPT).strip()
    user_text = str(user_query or "").strip()
    # Existing callers used to pass their complete long report as the system
    # prompt. Keep compatibility, but move oversized task/data blocks to the
    # user message to avoid teaching the small model that data is instruction.
    if len(system_text) > 1200:
        user_text = f"السياق والبيانات والتعليمات الخاصة بالمهمة:\n{system_text}\n\nطلب المستخدم:\n{user_text}"
        system_text = MASTER_FINANCIAL_PROMPT

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_text}]
    if history:
        # A tiny model benefits from a short rolling context, not the full DB log.
        for item in list(history)[-4:]:
            role = str(item.get("role", "")).lower()
            content = str(item.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content[:1200]})
    if len(user_text) > MAX_PROMPT_CHARS:
        user_text = user_text[:MAX_PROMPT_CHARS] + "\n[تم اختصار السياق لتناسب ذاكرة النموذج]"
    messages.append({"role": "user", "content": user_text})
    return messages


def query_local_ai(system_prompt, user_query, model=None, max_tokens=DEFAULT_MAX_TOKENS,
                   temperature=0.2, history=None, top_p=0.85, top_k=40,
                   repeat_penalty=1.12):
    """Generate a local chat response. Retains legacy positional arguments."""
    try:
        llm = _get_local_model()
        messages = _normalize_messages(system_prompt, user_query, history)
        try:
            requested_tokens = int(max_tokens)
        except (TypeError, ValueError):
            requested_tokens = DEFAULT_MAX_TOKENS
        token_limit = max(32, min(requested_tokens, 768))
        temp = max(0.0, min(float(temperature), 1.0))
        started = time.perf_counter()
        # Serialize use of this Llama context across concurrent Streamlit users.
        with _inference_lock:
            response = llm.create_chat_completion(
                messages=messages,
                max_tokens=token_limit,
                temperature=temp,
                top_p=max(0.1, min(float(top_p), 1.0)),
                top_k=max(1, min(int(top_k), 100)),
                repeat_penalty=max(1.0, min(float(repeat_penalty), 1.3)),
            )
        elapsed = time.perf_counter() - started
        choices = response.get("choices") or []
        if not choices:
            _logger.warning("Empty model response after %.2fs", elapsed)
            return "لم يُرجع النموذج إجابة. جرّب سؤالاً أقصر."
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage = response.get("usage") or {}
        _logger.info(
            "Inference complete elapsed=%.2fs prompt_tokens=%s completion_tokens=%s",
            elapsed, usage.get("prompt_tokens", "?"), usage.get("completion_tokens", "?"),
        )
        content = str(content).strip()
        if not content:
            return "الإجابة فارغة. تحقق من نوع النموذج وقالب المحادثة داخل ملف GGUF."
        return content
    except FileNotFoundError as exc:
        _logger.error("Model file missing: %s", exc)
        return f"⚠️ {exc}"
    except Exception as exc:
        _log_exception("Local AI inference failed")
        return "تعذر تشغيل الذكاء الاصطناعي المحلي: " + str(exc)


def query_groq(system_prompt, user_query, model=None, max_tokens=DEFAULT_MAX_TOKENS,
               temperature=0.2, **kwargs):
    """Legacy compatibility alias. No Groq or cloud connection is used."""
    return query_local_ai(
        system_prompt, user_query, model=model, max_tokens=max_tokens,
        temperature=temperature, **kwargs
    )


# ---------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------
def save_chat_history(session_id, role, content, model="", tab_name=""):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO ai_chat_history
               (session_id, role, content, model, tab_name, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(session_id), str(role), str(content), model or LOCAL_AI_MODEL,
             str(tab_name or ""), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(session_id=None, limit=20):
    conn = get_conn()
    try:
        limit = max(1, min(int(limit), 500))
        if session_id:
            rows = conn.execute(
                "SELECT * FROM ai_chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ai_chat_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def get_chat_sessions():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT session_id, MIN(timestamp) AS first_message,
                   COUNT(*) AS message_count
            FROM ai_chat_history GROUP BY session_id
            ORDER BY MAX(id) DESC LIMIT 25
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def compress_chat_memory(session_id, model=None):
    history = get_chat_history(session_id, limit=8)
    if not history:
        return ""
    dialogue = "\n".join(f"{x['role']}: {x['content']}" for x in history)
    return query_local_ai(
        "لخص المحادثة بالعربية في جملة أو جملتين. لا تضف معلومات غير موجودة.",
        dialogue, max_tokens=100, temperature=0.1,
    )


# ---------------------------------------------------------------------
# Cached database snapshots
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
        warnings.append("الإيرادات سالبة – تحقق من ترحيل حسابات الإيرادات.")
    if snap.get("assets", 0) <= 0:
        warnings.append("الأصول صفر أو سالبة – قد تكون القيود غير مكتملة.")
    if snap.get("profit_margin", 0) > 80:
        warnings.append("هامش ربح مرتفع جداً (>80%) – تحقق من المصروفات.")
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
        top_cust = [dict(r) for r in conn.execute("""
            SELECT c.name, SUM(i.total) AS total FROM invoices i
            JOIN customers c ON i.customer_id=c.id
            WHERE i.type='sale' AND i.status='completed'
            GROUP BY c.id ORDER BY total DESC LIMIT 3
        """).fetchall()]
        top_supp = [dict(r) for r in conn.execute("""
            SELECT s.name, SUM(i.total) AS total FROM invoices i
            JOIN suppliers s ON i.supplier_id=s.id
            WHERE i.type='purchase' AND i.status='completed'
            GROUP BY s.id ORDER BY total DESC LIMIT 3
        """).fetchall()]
        sales_trend = [dict(r) for r in conn.execute("""
            SELECT strftime('%Y-%m', invoice_date) AS month, SUM(total) AS total
            FROM invoices WHERE type='sale' AND status='completed'
            GROUP BY month ORDER BY month DESC LIMIT 6
        """).fetchall()]
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
        "top_customers": top_cust, "top_suppliers": top_supp,
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
        products = [dict(r) for r in conn.execute("""
            SELECT name, quantity, reorder_level, selling_price, purchase_price
            FROM products ORDER BY quantity ASC
        """).fetchall()]
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
            p["recommendation"] = "آمن"
    snap = {
        "total_products": len(products), "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:10],
        "top_products": sorted(products, key=lambda x: x.get("quantity") or 0, reverse=True)[:10],
        "all_products": products[:20],
    }
    _cache_set("inventory_snapshot", snap)
    return snap


def get_business_snapshot():
    cached = _cache_get("business_snapshot")
    if cached is not None:
        return cached
    conn = get_conn()
    try:
        top_customers = [dict(r) for r in conn.execute("""
            SELECT c.name, COUNT(i.id) AS invoice_count, SUM(i.total) AS total
            FROM invoices i JOIN customers c ON i.customer_id=c.id
            WHERE i.type='sale' AND i.status='completed'
            GROUP BY c.id ORDER BY total DESC LIMIT 5
        """).fetchall()]
        top_suppliers = [dict(r) for r in conn.execute("""
            SELECT s.name, COUNT(i.id) AS invoice_count, SUM(i.total) AS total
            FROM invoices i JOIN suppliers s ON i.supplier_id=s.id
            WHERE i.type='purchase' AND i.status='completed'
            GROUP BY s.id ORDER BY total DESC LIMIT 5
        """).fetchall()]
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
        rows = conn.execute("""
            SELECT strftime('%Y-%m', invoice_date) AS month,
                SUM(CASE WHEN type='sale' THEN total ELSE 0 END) AS sales,
                SUM(CASE WHEN type='purchase' THEN total ELSE 0 END) AS purchases
            FROM invoices WHERE status='completed'
            GROUP BY month ORDER BY month DESC LIMIT 6
        """).fetchall()
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
        summary.append({"code": center["code"], "name": center["name"], "net_balance": balance["net"]})
    _cache_set("cost_center_snapshot", summary)
    return summary


def build_ai_context(include_cost_centers=True):
    ctx = {}
    ctx.update(get_financial_snapshot())
    ctx.update(get_inventory_snapshot())
    ctx.update(get_business_snapshot())
    ctx.update(get_hr_snapshot())
    ctx["trends"] = get_trend_snapshot()
    if include_cost_centers:
        try:
            ctx["cost_centers"] = get_cost_center_snapshot()
        except Exception as exc:
            _logger.warning("Cost centre context unavailable: %s", exc)
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
    return {
        "هامش الربح": f"{fin['profit_margin']:.1f}%",
        "نسبة المديونية": f"{fin['debt_ratio']:.1f}%",
        "العائد على الأصول": f"{fin['roa']:.1f}%",
        "صافي الدخل": f"{fin['net_income']:,.2f}",
    }


def get_trend_analysis():
    return get_trend_snapshot()


# ---------------------------------------------------------------------
# Cost-centre analysis
# ---------------------------------------------------------------------
def analyze_cost_center_performance(center_id):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center:
        return "مركز التكلفة غير موجود"
    balance = ccs.get_cost_center_balance(center_id)
    income = ccs.get_cost_center_income_statement(center_id, "2020-01-01", datetime.now().strftime("%Y-%m-%d"))
    user_text = (
        f"المركز: {center['name']}\nمدين: {balance['total_debit']}\n"
        f"دائن: {balance['total_credit']}\nصافي: {balance['net']}\n"
        f"إيرادات: {income['income']}\nمصروفات: {income['expenses']}\nربح: {income['net_profit']}"
    )
    return query_local_ai(
        "أنت مستشار مالي ومحاسب إداري. حلل المؤشرات المتاحة وحدد ما لا يمكن استنتاجه.",
        user_text + "\nقدم خلاصة ونقاط قوة وضعف وتوصيات عملية.", max_tokens=350, temperature=0.2,
    )


def compare_cost_centers():
    summary = get_cost_center_snapshot()
    if not summary:
        return "لا توجد بيانات"
    return query_local_ai(
        "أنت مدير مالي. قارن المراكز اعتماداً على البيانات فقط.",
        json.dumps(summary, ensure_ascii=False) + "\nقدم ملخص مقارنة وتحليل فجوات وتوصيات.",
        max_tokens=350, temperature=0.2,
    )


def predict_cost_center_expenses(center_id, months=3):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center:
        return "المركز غير موجود"
    conn = get_conn()
    try:
        history = [dict(r) for r in conn.execute("""
            SELECT strftime('%Y-%m', je.date) AS month, SUM(cca.amount) AS total
            FROM cost_center_allocations cca
            JOIN journal_lines jl ON cca.journal_line_id=jl.id
            JOIN journal_entries je ON jl.entry_id=je.id
            WHERE cca.cost_center_id=? AND jl.debit>0
            GROUP BY month ORDER BY month DESC LIMIT 12
        """, (center_id,)).fetchall()]
    finally:
        conn.close()
    return query_local_ai(
        "أنت محلل مالي. قدم توقعاً استرشادياً فقط ولا تدّعِ دقة إحصائية غير متاحة.",
        f"مركز التكلفة: {center['name']}\nالفترة المطلوبة: {months} أشهر\nالبيانات التاريخية:\n"
        + json.dumps(history, ensure_ascii=False), max_tokens=300, temperature=0.15,
    )


def get_cost_center_budget_analysis(center_id, fiscal_year):
    from services import cost_center_service as ccs
    variance = ccs.get_budget_variance(center_id, fiscal_year)
    if not variance:
        return "لا توجد موازنات مسجلة"
    return query_local_ai(
        "أنت خبير تخطيط مالي. حلل الانحرافات دون افتراض أسباب غير مثبتة.",
        json.dumps(variance.get("details", []), ensure_ascii=False),
        max_tokens=300, temperature=0.15,
    )


# ---------------------------------------------------------------------
# Journal entry extraction and templates (drafts only)
# ---------------------------------------------------------------------
def extract_entry_data(text, model=None):
    system = "أنت مساعد لاستخراج مسودة قيد محاسبي. أخرج JSON صالحاً فقط بمفاتيح operation_type وlines، وكل سطر يحوي account وamount وside (debit/credit). لا تخترع حسابات أو مبالغ؛ استخدم null/اطلب توضيحاً عند النقص."
    response = query_local_ai(system, str(text), max_tokens=220, temperature=0.0)
    try:
        start, end = response.find("{"), response.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        data = json.loads(response[start:end])
        if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
            return None
        for line in data["lines"]:
            if line.get("side") not in ("debit", "credit"):
                return None
            amount = float(line.get("amount", 0))
            if amount <= 0:
                return None
            line["amount"] = round(amount, 2)
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def build_balanced_entry(extracted_data):
    if not extracted_data or not extracted_data.get("lines"):
        return None, "فشل استخراج البيانات"
    lines = extracted_data["lines"]
    debit = sum(float(x.get("amount", 0)) for x in lines if x.get("side") == "debit")
    credit = sum(float(x.get("amount", 0)) for x in lines if x.get("side") == "credit")
    # Do not silently create a fictitious suspense account to force balance.
    if abs(debit - credit) >= 0.01:
        return None, f"القيد غير متوازن: المدين {debit:,.2f} والدائن {credit:,.2f}. يلزم تصحيح البيانات يدوياً."
    return {"lines": list(lines), "total_debit": round(debit, 2),
            "total_credit": round(credit, 2), "is_balanced": True,
            "has_auto_correction": False}, None


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
    # This is structural completeness, not AI certainty or audit assurance.
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
    "بيع نقداً": {"description": "بيع بضاعة نقداً", "lines": [
        {"account": "النقدية", "side": "debit"}, {"account": "المبيعات", "side": "credit"}]},
    "بيع بالآجل": {"description": "بيع بضاعة بالآجل", "lines": [
        {"account": "العملاء", "side": "debit"}, {"account": "المبيعات", "side": "credit"}]},
    "شراء نقداً": {"description": "شراء بضاعة نقداً", "lines": [
        {"account": "المخزون", "side": "debit"}, {"account": "النقدية", "side": "credit"}]},
    "شراء بالآجل": {"description": "شراء بضاعة بالآجل", "lines": [
        {"account": "المخزون", "side": "debit"}, {"account": "الموردين", "side": "credit"}]},
    "قبض من عميل": {"description": "استلام دفعة من عميل", "lines": [
        {"account": "النقدية", "side": "debit"}, {"account": "العملاء", "side": "credit"}]},
    "دفع لمورد": {"description": "سداد دفعة لمورد", "lines": [
        {"account": "الموردين", "side": "debit"}, {"account": "النقدية", "side": "credit"}]},
    "سداد مصروف": {"description": "سداد مصروف نقداً", "lines": [
        {"account": "{expense_name}", "side": "debit"}, {"account": "النقدية", "side": "credit"}]},
}


def generate_template_entry(operation_type, amount, cash_amount=None, credit_amount=None,
                            expense_name=None, vat_rate=None, adjustment_side=None,
                            inventory_side=None):
    template = ENTRY_TEMPLATES.get(operation_type)
    if not template:
        return None, "العملية غير مدعومة في القوالب الحالية", 0, "غير مدعوم", "#EF4444"
    try:
        value = round(float(amount), 2)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return None, "أدخل مبلغاً أكبر من صفر", 0, "غير مكتمل", "#EF4444"
    lines = []
    for item in template["lines"]:
        account = expense_name or "مصروف" if item["account"] == "{expense_name}" else item["account"]
        lines.append({"account": account, "amount": value, "side": item["side"]})
    entry, error = build_balanced_entry({"lines": lines})
    if error:
        return None, error, 0, "غير متوازن", "#EF4444"
    # A balanced standard template is structurally consistent; not an audit opinion.
    return entry, format_entry_display(entry) + "\n\nقالب قياسي — راجع الحسابات قبل الاعتماد.", 80, "قالب قياسي يحتاج مراجعة", "#F59E0B"


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
