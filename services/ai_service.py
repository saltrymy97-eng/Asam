# services/ai_service.py
# المساعد الذكي المحلي لنظام حوكمة ERP
# المحرك: llama.cpp
# النموذج: GGUF
# لا توجد اتصالات سحابية أو مفاتيح API

import sqlite3
import json
import os
from datetime import datetime, timedelta
from threading import Lock

# =========================================================
# إعدادات المحرك المحلي
# =========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "erp.db")

MODEL_PATH = os.environ.get(
    "ERP_AI_MODEL_PATH",
    os.path.join(BASE_DIR, "models", "ai-model.gguf")
)

LLAMA_CONTEXT_SIZE = int(os.environ.get("ERP_AI_CONTEXT", "2048"))
LLAMA_THREADS = int(os.environ.get(
    "ERP_AI_THREADS",
    str(max(1, (os.cpu_count() or 2) - 1))
))
LLAMA_GPU_LAYERS = int(os.environ.get("ERP_AI_GPU_LAYERS", "0"))
LLAMA_BATCH_SIZE = int(os.environ.get("ERP_AI_BATCH_SIZE", "128"))

_llm = None
_llm_lock = Lock()

# =========================================================
# موجه الذكاء الاصطناعي المالي
# =========================================================

MASTER_FINANCIAL_PROMPT = """أنت المساعد الذكي لنظام (حوكمة ERP)،
نظام محاسبي وإداري متقدم.

شخصيتك: احترافي جداً، دقيق، ولبق.
تتحدث كمدير مالي (CFO) أو مستشار محاسبة.

قواعدك الأساسية:
1. قدم إجابات وافية ومنظمة.
2. استخدم المصطلحات المحاسبية الصحيحة.
3. اشرح التأثير المالي للقرارات.
4. استخدم Markdown والعناوين والجداول.
5. لا تخترع أرقاماً أو بيانات غير موجودة.
"""

# =========================================================
# التخزين المؤقت
# =========================================================

_cache = {}
CACHE_TTL_SECONDS = 300


def _cache_get(key):
    entry = _cache.get(key)

    if entry:
        data, ts = entry

        if (datetime.now() - ts).total_seconds() < CACHE_TTL_SECONDS:
            return data

        del _cache[key]

    return None


def _cache_set(key, data):
    _cache[key] = (data, datetime.now())


# =========================================================
# الاتصال بقاعدة البيانات
# =========================================================

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def create_ai_tables():
    conn = get_conn()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                parent_id INTEGER,
                level INTEGER DEFAULT 1,
                is_debit TEXT DEFAULT 'debit',
                FOREIGN KEY (parent_id) REFERENCES accounts(id)
            )
        """)

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

        conn.commit()

    finally:
        conn.close()


# =========================================================
# محرك llama.cpp المحلي
# =========================================================

def _get_local_model():
    """
    تحميل النموذج مرة واحدة فقط.
    """

    global _llm

    if _llm is not None:
        return _llm

    with _llm_lock:

        if _llm is not None:
            return _llm

        if not os.path.isfile(MODEL_PATH):
            raise FileNotFoundError(
                "ملف نموذج الذكاء الاصطناعي غير موجود:\n"
                + MODEL_PATH
                + "\nضع نموذج GGUF داخل مجلد models باسم ai-model.gguf"
            )

        try:
            from llama_cpp import Llama

        except ImportError as exc:
            raise RuntimeError(
                "مكتبة llama-cpp-python غير مثبتة.\n"
                "نفذ الأمر: pip install llama-cpp-python"
            ) from exc

        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=LLAMA_CONTEXT_SIZE,
            n_threads=LLAMA_THREADS,
            n_gpu_layers=LLAMA_GPU_LAYERS,
            n_batch=LLAMA_BATCH_SIZE,
            verbose=False
        )

        return _llm


def query_local_ai(
    system_prompt,
    user_query,
    model=None,
    max_tokens=4096,
    temperature=0.3
):
    """
    تنفيذ الطلب محلياً باستخدام llama.cpp.
    لا يتم إرسال البيانات إلى الإنترنت.
    """

    try:
        llm = _get_local_model()

        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": str(system_prompt or MASTER_FINANCIAL_PROMPT)
                },
                {
                    "role": "user",
                    "content": str(user_query or "")
                }
            ],
            temperature=max(0.0, min(float(temperature), 2.0)),
            max_tokens=max(1, min(int(max_tokens), 2048))
        )

        choices = response.get("choices", [])

        if not choices:
            return "⚠️ لم يُرجع النموذج المحلي إجابة."

        content = choices[0].get("message", {}).get("content", "")

        return content.strip() or "⚠️ الإجابة فارغة."

    except FileNotFoundError as e:
        return f"⚠️ {e}"

    except Exception as e:
        return f"❌ تعذر تشغيل الذكاء الاصطناعي المحلي: {str(e)}"


# اسم قديم للتوافق مع الواجهة والدوال السابقة
def query_groq(
    system_prompt,
    user_query,
    model=None,
    max_tokens=4096,
    temperature=0.3
):
    return query_local_ai(
        system_prompt,
        user_query,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature
    )


# =========================================================
# سجل المحادثات
# =========================================================

def save_chat_history(session_id, role, content, model="", tab_name=""):
    conn = get_conn()

    try:
        conn.execute(
            """
            INSERT INTO ai_chat_history
            (session_id, role, content, model, tab_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                model or "llama.cpp-local",
                tab_name,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

        conn.commit()

    finally:
        conn.close()


def get_chat_history(session_id=None, limit=20):
    conn = get_conn()

    try:
        if session_id:
            rows = conn.execute(
                """
                SELECT * FROM ai_chat_history
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit)
            ).fetchall()

        else:
            rows = conn.execute(
                """
                SELECT * FROM ai_chat_history
                ORDER BY id DESC LIMIT ?
                """,
                (limit,)
            ).fetchall()

        return [dict(r) for r in rows]

    finally:
        conn.close()


def get_chat_sessions():
    conn = get_conn()

    try:
        rows = conn.execute("""
            SELECT session_id,
                   MIN(timestamp) AS first_message,
                   COUNT(*) AS message_count
            FROM ai_chat_history
            GROUP BY session_id
            ORDER BY first_message DESC
            LIMIT 10
        """).fetchall()

        return [dict(r) for r in rows]

    finally:
        conn.close()


# =========================================================
# ذاكرة المحادثة
# =========================================================

def compress_chat_memory(session_id, model=None):
    history = get_chat_history(session_id, limit=10)

    if not history:
        return ""

    history_sorted = sorted(
        history,
        key=lambda x: x["timestamp"]
    )

    dialogue = "\n".join([
        f"{h['role']}: {h['content']}"
        for h in history_sorted
    ])

    prompt = f"""
لخص الحوار التالي في جملة واحدة بالعربية
تصف الموضوع الرئيسي والنتيجة:

{dialogue}

الملخص:
"""

    result = query_local_ai(
        "أنت مساعد تلخيص محترف. اكتب جملة واحدة فقط.",
        prompt,
        max_tokens=150,
        temperature=0.2
    )

    if result.startswith("❌"):
        return "ملخص غير متاح"

    return result


# =========================================================
# التحقق من صحة البيانات
# =========================================================

def validate_financial_snapshot(snap):
    warnings = []

    if snap["revenue"] < 0:
        warnings.append(
            "الإيرادات سالبة – تحقق من ترحيل حسابات الإيرادات."
        )

    if snap["assets"] <= 0:
        warnings.append(
            "الأصول صفر أو سالبة – قد تكون القيود غير مكتملة."
        )

    if snap["profit_margin"] > 80:
        warnings.append(
            "هامش ربح مرتفع جداً (>80%) – تأكد من دقة بيانات المصروفات."
        )

    return warnings


# =========================================================
# اللقطات المالية
# =========================================================

def get_financial_snapshot():
    cache_key = "financial_snapshot"

    cached = _cache_get(cache_key)

    if cached is not None:
        return cached

    conn = get_conn()

    try:
        revenue = conn.execute("""
            SELECT COALESCE(SUM(credit)-SUM(debit),0)
            FROM journal_lines
            WHERE account_name LIKE '4%'
        """).fetchone()[0]

        expenses = conn.execute("""
            SELECT COALESCE(SUM(debit)-SUM(credit),0)
            FROM journal_lines
            WHERE account_name LIKE '5%'
        """).fetchone()[0]

        assets = conn.execute("""
            SELECT COALESCE(SUM(debit)-SUM(credit),0)
            FROM journal_lines
            WHERE account_name LIKE '1%'
        """).fetchone()[0]

        liabilities = conn.execute("""
            SELECT COALESCE(SUM(credit)-SUM(debit),0)
            FROM journal_lines
            WHERE account_name LIKE '2%'
        """).fetchone()[0]

        equity = conn.execute("""
            SELECT COALESCE(SUM(credit)-SUM(debit),0)
            FROM journal_lines
            WHERE account_name LIKE '3%'
        """).fetchone()[0]

        top_cust = [
            dict(r) for r in conn.execute("""
                SELECT c.name, SUM(i.total) AS total
                FROM invoices i
                JOIN customers c ON i.customer_id = c.id
                WHERE i.type='sale'
                AND i.status='completed'
                GROUP BY c.id
                ORDER BY total DESC
                LIMIT 3
            """).fetchall()
        ]

        top_supp = [
            dict(r) for r in conn.execute("""
                SELECT s.name, SUM(i.total) AS total
                FROM invoices i
                JOIN suppliers s ON i.supplier_id = s.id
                WHERE i.type='purchase'
                AND i.status='completed'
                GROUP BY s.id
                ORDER BY total DESC
                LIMIT 3
            """).fetchall()
        ]

        sales_trend = [
            dict(r) for r in conn.execute("""
                SELECT strftime('%Y-%m', invoice_date) AS month,
                       SUM(total) AS total
                FROM invoices
                WHERE type='sale'
                AND status='completed'
                GROUP BY month
                ORDER BY month DESC
                LIMIT 6
            """).fetchall()
        ]

    finally:
        conn.close()

    net_income = revenue - expenses

    profit_margin = (
        net_income / revenue * 100
        if revenue > 0 else 0
    )

    debt_ratio = (
        liabilities / assets * 100
        if assets > 0 else 0
    )

    roa = (
        net_income / assets * 100
        if assets > 0 else 0
    )

    snap = {
        "revenue": round(revenue, 2),
        "expenses": round(expenses, 2),
        "net_income": round(net_income, 2),
        "assets": round(assets, 2),
        "liabilities": round(liabilities, 2),
        "equity": round(equity, 2),
        "profit_margin": round(profit_margin, 1),
        "debt_ratio": round(debt_ratio, 1),
        "roa": round(roa, 1),
        "top_customers": top_cust,
        "top_suppliers": top_supp,
        "sales_trend": sales_trend
    }

    snap["warnings"] = validate_financial_snapshot(snap)

    _cache_set(cache_key, snap)

    return snap


# =========================================================
# لقطة المخزون
# =========================================================

def get_inventory_snapshot():
    cache_key = "inventory_snapshot"

    cached = _cache_get(cache_key)

    if cached is not None:
        return cached

    conn = get_conn()

    try:
        all_products = [
            dict(r) for r in conn.execute("""
                SELECT name, quantity, reorder_level,
                       selling_price, purchase_price
                FROM products
                ORDER BY quantity ASC
            """).fetchall()
        ]

    finally:
        conn.close()

    total_products = len(all_products)

    low_stock = [
        p for p in all_products
        if p["quantity"] < p["reorder_level"]
    ]

    for p in all_products:

        selling = p["selling_price"] or 0
        purchase = p["purchase_price"] or 0

        if selling > 0 and purchase > 0:
            p["profit_margin"] = round(
                (selling - purchase) / selling * 100, 1
            )
        else:
            p["profit_margin"] = 0

        if p["quantity"] <= 0:
            p["recommendation"] = "نفد المخزون"

        elif p["quantity"] < p["reorder_level"]:
            p["recommendation"] = (
                f"طلب {p['reorder_level'] - p['quantity']} وحدة"
            )

        elif p["quantity"] < p["reorder_level"] * 2:
            p["recommendation"] = "مراقبة"

        else:
            p["recommendation"] = "آمن"

    snap = {
        "total_products": total_products,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:10],
        "top_products": sorted(
            all_products,
            key=lambda x: x["quantity"],
            reverse=True
        )[:10],
        "all_products": all_products[:20]
    }

    _cache_set(cache_key, snap)

    return snap


# =========================================================
# لقطة الأعمال والعملاء والموردين
# =========================================================

def get_business_snapshot():
    cache_key = "business_snapshot"

    cached = _cache_get(cache_key)

    if cached is not None:
        return cached

    conn = get_conn()

    try:
        top_customers = [
            dict(r) for r in conn.execute("""
                SELECT c.name,
                       COUNT(i.id) AS invoice_count,
                       SUM(i.total) AS total
                FROM invoices i
                JOIN customers c ON i.customer_id = c.id
                WHERE i.type='sale'
                AND i.status='completed'
                GROUP BY c.id
                ORDER BY total DESC
                LIMIT 5
            """).fetchall()
        ]

        top_suppliers = [
            dict(r) for r in conn.execute("""
                SELECT s.name,
                       COUNT(i.id) AS invoice_count,
                       SUM(i.total) AS total
                FROM invoices i
                JOIN suppliers s ON i.supplier_id = s.id
                WHERE i.type='purchase'
                AND i.status='completed'
                GROUP BY s.id
                ORDER BY total DESC
                LIMIT 5
            """).fetchall()
        ]

        total_customers = conn.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]

        total_suppliers = conn.execute(
            "SELECT COUNT(*) FROM suppliers"
        ).fetchone()[0]

    finally:
        conn.close()

    snap = {
        "total_customers": total_customers,
        "total_suppliers": total_suppliers,
        "top_customers": top_customers,
        "top_suppliers": top_suppliers
    }

    _cache_set(cache_key, snap)

    return snap


# =========================================================
# لقطة الموارد البشرية
# =========================================================

def get_hr_snapshot():
    cache_key = "hr_snapshot"

    cached = _cache_get(cache_key)

    if cached is not None:
        return cached

    conn = get_conn()

    try:
        total_employees = conn.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]

        total_salary = conn.execute(
            "SELECT COALESCE(SUM(basic_salary),0) FROM employee_salaries"
        ).fetchone()[0]

    finally:
        conn.close()

    snap = {
        "total_employees": total_employees,
        "total_monthly_salary": round(total_salary, 2)
    }

    _cache_set(cache_key, snap)

    return snap


# =========================================================
# لقطة الاتجاهات
# =========================================================

def get_trend_snapshot():
    cache_key = "trend_snapshot"

    cached = _cache_get(cache_key)

    if cached is not None:
        return cached

    conn = get_conn()

    try:
        trends = conn.execute("""
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   SUM(CASE WHEN type='sale' THEN total ELSE 0 END) AS sales,
                   SUM(CASE WHEN type='purchase' THEN total ELSE 0 END) AS purchases
            FROM invoices
            WHERE status='completed'
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
        """).fetchall()

    finally:
        conn.close()

    snap = [dict(t) for t in trends]

    _cache_set(cache_key, snap)

    return snap


# =========================================================
# مراكز التكلفة
# =========================================================

def get_cost_center_snapshot():
    cache_key = "cost_center_snapshot"

    cached = _cache_get(cache_key)

    if cached is not None:
        return cached

    from services import cost_center_service as ccs

    centers = ccs.get_all_cost_centers(active_only=True)

    summary = []

    for c in centers:
        balance = ccs.get_cost_center_balance(c["id"])

        summary.append({
            "code": c["code"],
            "name": c["name"],
            "net_balance": balance["net"]
        })

    _cache_set(cache_key, summary)

    return summary


def build_ai_context(include_cost_centers=True):
    ctx = {}

    fin = get_financial_snapshot()

    for k, v in fin.items():
        ctx[k] = v

    inv = get_inventory_snapshot()

    for k, v in inv.items():
        if k not in ctx:
            ctx[k] = v

    biz = get_business_snapshot()

    for k, v in biz.items():
        if k not in ctx:
            ctx[k] = v

    hr = get_hr_snapshot()

    for k, v in hr.items():
        if k not in ctx:
            ctx[k] = v

    ctx["trends"] = get_trend_snapshot()

    if include_cost_centers:
        ctx["cost_centers"] = get_cost_center_snapshot()

    return ctx


# =========================================================
# الدوال العامة المستخدمة في الواجهة
# =========================================================

def get_comprehensive_data():
    return build_ai_context()


def get_inventory_data():
    snap = get_inventory_snapshot()

    return (
        snap["low_stock_items"],
        snap["all_products"][:20]
    )


def get_employee_info(name):
    conn = get_conn()

    try:
        emp = conn.execute(
            "SELECT * FROM employees WHERE name LIKE ?",
            (f"%{name}%",)
        ).fetchone()

        if emp:
            sal = conn.execute(
                "SELECT * FROM employee_salaries WHERE employee_id=?",
                (emp["id"],)
            ).fetchone()

            return dict(emp), dict(sal) if sal else None

        return None, None

    finally:
        conn.close()


def get_recent_entries():
    conn = get_conn()

    try:
        return [
            dict(r) for r in conn.execute("""
                SELECT * FROM journal_entries
                ORDER BY id DESC
                LIMIT 200
            """).fetchall()
        ]

    finally:
        conn.close()


def get_all_accounts():
    conn = get_conn()

    try:
        return [
            dict(r) for r in conn.execute("""
                SELECT code, name FROM accounts
                ORDER BY code
            """).fetchall()
        ]

    finally:
        conn.close()


def get_financial_ratios():
    fin = get_financial_snapshot()

    return {
        "هامش الربح": f"{fin['profit_margin']:.1f}%",
        "نسبة المديونية": f"{fin['debt_ratio']:.1f}%",
        "العائد على الأصول": f"{fin['roa']:.1f}%",
        "صافي الدخل": f"{fin['net_income']:,.2f}"
    }


def get_trend_analysis():
    return get_trend_snapshot()


# =========================================================
# تحليل مراكز التكلفة
# =========================================================

def analyze_cost_center_performance(center_id):
    from services import cost_center_service as ccs

    center = ccs.get_cost_center_by_id(center_id)

    if not center:
        return "مركز التكلفة غير موجود"

    balance = ccs.get_cost_center_balance(center_id)

    income_stmt = ccs.get_cost_center_income_statement(
        center_id,
        "2020-01-01",
        datetime.now().strftime("%Y-%m-%d")
    )

    data_text = f"""
المركز: {center['name']}
مدين: {balance['total_debit']}
دائن: {balance['total_credit']}
صافي: {balance['net']}
إيرادات: {income_stmt['income']}
مصروفات: {income_stmt['expenses']}
ربح: {income_stmt['net_profit']}
"""

    system_prompt = """
أنت مستشار مالي ومحاسب إداري خبير.
قدم تحليلاً مالياً شاملاً يتضمن:

1. النظرة التنفيذية.
2. التحليل الرقمي.
3. نقاط القوة والضعف.
4. توصيات استراتيجية قابلة للتنفيذ.
"""

    return query_local_ai(
        system_prompt,
        data_text,
        max_tokens=1500,
        temperature=0.4
    )


def compare_cost_centers():
    summary = get_cost_center_snapshot()

    if not summary:
        return "لا توجد بيانات"

    data_text = json.dumps(summary, ensure_ascii=False)

    system_prompt = """
أنت مدير مالي خبير.
قدم مقارنة تحليلية لمراكز التكلفة تشمل:

1. ملخص الأداء المقارن.
2. جدول المقارنة المالية.
3. تحليل الفجوات.
4. توصيات تحسين توزيع الموارد.
"""

    return query_local_ai(
        system_prompt,
        data_text,
        max_tokens=1800,
        temperature=0.4
    )


def predict_cost_center_expenses(center_id, months=3):
    from services import cost_center_service as ccs

    center = ccs.get_cost_center_by_id(center_id)

    if not center:
        return "المركز غير موجود"

    conn = get_conn()

    try:
        history = [
            dict(m) for m in conn.execute("""
                SELECT strftime('%Y-%m', je.date) AS month,
                       SUM(cca.amount) AS total
                FROM cost_center_allocations cca
                JOIN journal_lines jl
                    ON cca.journal_line_id = jl.id
                JOIN journal_entries je
                    ON jl.entry_id = je.id
                WHERE cca.cost_center_id = ?
                AND jl.debit > 0
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """, (center_id,)).fetchall()
        ]

    finally:
        conn.close()

    system_prompt = """
أنت محلل بيانات مالية وخبير في التنبؤ المالي.

حلل المصروفات التاريخية وقدم:
1. اتجاه المصروفات.
2. توقعات استرشادية للأشهر القادمة.
3. مؤشرات المخاطر.
4. توصيات التحوط المالي.

وضح أن التوقعات تقديرية وليست ضماناً.
"""

    return query_local_ai(
        system_prompt,
        json.dumps(history, ensure_ascii=False),
        max_tokens=1500,
        temperature=0.3
    )


def get_cost_center_budget_analysis(center_id, fiscal_year):
    from services import cost_center_service as ccs

    variance_data = ccs.get_budget_variance(
        center_id,
        fiscal_year
    )

    if not variance_data:
        return "لا توجد موازنات مسجلة"

    system_prompt = """
أنت خبير في التخطيط المالي وتحليل الموازنات.

حلل بيانات الانحراف بين المخطط والفعلي، وقدم:

1. الملخص التنفيذي.
2. تحليل الانحرافات الجوهرية.
3. الأسباب المحتملة.
4. التوجيهات التصحيحية.
"""

    return query_local_ai(
        system_prompt,
        json.dumps(
            variance_data["details"],
            ensure_ascii=False
        ),
        max_tokens=1500,
        temperature=0.3
    )


# =========================================================
# محرك القيود الآلي
# =========================================================

def extract_entry_data(text, model=None):
    system_prompt = """
أنت محاسب قانوني محترف.

حول النص إلى JSON فقط دون أي شرح أو Markdown.

الهيكل المطلوب:

{
    "operation_type": "نوع العملية",
    "lines": [
        {
            "account": "اسم الحساب",
            "amount": 1000,
            "side": "debit أو credit"
        }
    ]
}
"""

    response = query_local_ai(
        system_prompt,
        text,
        max_tokens=500,
        temperature=0.0
    )

    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end <= start:
            return None

        return json.loads(response[start:end])

    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def build_balanced_entry(extracted_data):
    if not extracted_data or not extracted_data.get("lines"):
        return None, "فشل استخراج البيانات"

    lines = extracted_data["lines"]

    total_debit = sum(
        float(l.get("amount", 0))
        for l in lines
        if l.get("side") == "debit"
    )

    total_credit = sum(
        float(l.get("amount", 0))
        for l in lines
        if l.get("side") == "credit"
    )

    entry_lines = list(lines)

    diff = round(total_debit - total_credit, 2)

    if diff > 0:
        entry_lines.append({
            "account": "حساب تسوية",
            "amount": diff,
            "side": "credit",
            "auto_correction": True
        })

        total_credit += diff

    elif diff < 0:
        entry_lines.append({
            "account": "حساب تسوية",
            "amount": abs(diff),
            "side": "debit",
            "auto_correction": True
        })

        total_debit += abs(diff)

    return {
        "lines": entry_lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": abs(total_debit - total_credit) < 0.01,
        "has_auto_correction": any(
            l.get("auto_correction")
            for l in entry_lines
        )
    }


def format_entry_display(entry_data):
    if not entry_data:
        return "لا توجد بيانات"

    res = "".join([
        f"{'مدين' if l.get('side') == 'debit' else 'دائن'} | "
        f"{l.get('account', '')} | "
        f"{l.get('amount', 0):,.2f}"
        f"{' (تسوية)' if l.get('auto_correction') else ''}\n"
        for l in entry_data.get("lines", [])
    ])

    res += (
        f"\n✅ متوازن: مدين "
        f"{entry_data['total_debit']:,.2f} "
        f"= دائن {entry_data['total_credit']:,.2f}"
    )

    return res


def calculate_confidence(ext, bal):
    if not ext or not bal or not bal.get("lines"):
        return 0

    if not bal.get("has_auto_correction"):
        return 100

    corr = sum(
        l.get("amount", 0)
        for l in bal["lines"]
        if l.get("auto_correction")
    )

    tot = sum(
        l.get("amount", 0)
        for l in bal["lines"]
        if not l.get("auto_correction")
    )

    if tot == 0:
        return 0

    pct = (corr / tot) * 100

    if pct < 2:
        return 90

    if pct < 5:
        return 70

    if pct < 10:
        return 50

    return 30


def get_confidence_level(conf):
    if conf >= 90:
        return "موثوق", "#10B981"

    if conf >= 70:
        return "شبه موثوق", "#F59E0B"

    return "مشكوك فيه/غير موثوق", "#EF4444"


def generate_entry_safe(text, model=None):
    ext = extract_entry_data(text, model)

    if not ext:
        return None, "❌ فشل الاستخراج.", 0, "غير موثوق", "#EF4444"

    ent = build_balanced_entry(ext)

    if not isinstance(ent, dict):
        return None, "❌ فشل بناء القيد.", 0, "غير موثوق", "#EF4444"

    conf = calculate_confidence(ext, ent)

    lbl, clr = get_confidence_level(conf)

    disp = format_entry_display(ent) + f"\n📊 الثقة: {conf}% ({lbl})"

    return ent, disp, conf, lbl, clr


# =========================================================
# محرك القيود بالقوالب
# =========================================================

ENTRY_TEMPLATES = {
    "بيع نقداً": {
        "description": "بيع بضاعة نقداً",
        "lines": [
            {"account": "النقدية", "amount": "{amount}", "side": "debit"},
            {"account": "المبيعات", "amount": "{amount}", "side": "credit"}
        ]
    },

    "بيع بالآجل": {
        "description": "بيع بضاعة بالآجل",
        "lines": [
            {"account": "العملاء", "amount": "{amount}", "side": "debit"},
            {"account": "المبيعات", "amount": "{amount}", "side": "credit"}
        ]
    },

    "شراء نقداً": {
        "description": "شراء بضاعة نقداً",
        "lines": [
            {"account": "المخزون", "amount": "{amount}", "side": "debit"},
            {"account": "النقدية", "amount": "{amount}", "side": "credit"}
        ]
    },

    "شراء بالآجل": {
        "description": "شراء بضاعة بالآجل",
        "lines": [
            {"account": "المخزون", "amount": "{amount}", "side": "debit"},
            {"account": "الموردين", "amount": "{amount}", "side": "credit"}
        ]
    },

    "قبض من عميل": {
        "description": "استلام دفعة من عميل",
        "lines": [
            {"account": "النقدية", "amount": "{amount}", "side": "debit"},
            {"account": "العملاء", "amount": "{amount}", "side": "credit"}
        ]
    },

    "دفع لمورد": {
        "description": "سداد دفعة لمورد",
        "lines": [
            {"account": "الموردين", "amount": "{amount}", "side": "debit"},
            {"account": "النقدية", "amount": "{amount}", "side": "credit"}
        ]
    },

    "سداد مصروف": {
        "description": "سداد مصروف نقداً",
        "lines": [
            {"account": "{expense_name}", "amount": "{amount}", "side": "debit"},
            {"account": "النقدية", "amount": "{amount}", "side": "credit"}
        ]
    }
}


def generate_template_entry(
    operation_type,
    amount,
    cash_amount=None,
    credit_amount=None,
    expense_name=None,
    vat_rate=None,
    adjustment_side=None,
    inventory_side=None
):
    template = ENTRY_TEMPLATES.get(operation_type)

    if not template:
        return None, "❌ العملية غير مدعومة", 0, "غير موثوق", "#EF4444"

    lines = []

    for l in template["lines"]:

        if l["account"] == "{expense_name}":
            account = expense_name or "مصروف"
        else:
            account = l["account"]

        lines.append({
            "account": account,
            "amount": round(float(amount), 2),
            "side": l["side"]
        })

    ent = build_balanced_entry({"lines": lines})

    if not isinstance(ent, dict):
        return None, "❌ فشل إنشاء القيد", 0, "غير موثوق", "#EF4444"

    disp = format_entry_display(ent) + "\n📊 الثقة: 100% (قالب)"

    return ent, disp, 100, "موثوق", "#10B981"


def get_available_operations():
    return list(ENTRY_TEMPLATES.keys())


def get_operation_description(op):
    return ENTRY_TEMPLATES.get(op, {}).get("description", "")


def is_mixed_operation(op):
    return op in ["بيع مختلط", "شراء مختلط"]


def is_vat_operation(op):
    return op in ["بيع شامل الضريبة", "شراء شامل الضريبة"]


def is_salary_operation(op):
    return op == "رواتب موظفين"


def is_inventory_adjustment(op):
    return op == "تسوية مخزنية (جرد)"
