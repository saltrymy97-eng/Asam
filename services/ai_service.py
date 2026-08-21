# services/ai_service.py – المساعد الذكي (AI Data Layer + Cache + Memory + Validation)
import sqlite3
import json
import os
from datetime import datetime, timedelta
from groq import Groq, BadRequestError

# ========== مفتاح الـ API للنسخة التنفيذية (exe) ==========
GROQ_API_KEY = "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"

DB_PATH = os.path.join("data", "erp.db")

# ========== طبقة تخزين مؤقت بسيطة (Cache Layer) ==========
_cache = {}          # { key: (data, timestamp) }
CACHE_TTL_SECONDS = 300  # 5 دقائق

def _cache_get(key):
    entry = _cache.get(key)
    if entry:
        data, ts = entry
        if (datetime.now() - ts).total_seconds() < CACHE_TTL_SECONDS:
            return data
        else:
            del _cache[key]
    return None

def _cache_set(key, data):
    _cache[key] = (data, datetime.now())

# ========== اتصال قاعدة البيانات ==========
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_ai_tables():
    conn = get_conn()
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
    conn.close()

def query_groq(system_prompt, user_query, model="openai/gpt-oss-120b", max_tokens=4096, temperature=0.3):
    """
    إرسال استعلام إلى Groq API مع معالجة الخطأ باستخدام النموذج الجديد.
    """
    client = Groq(api_key=GROQ_API_KEY)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=temperature,
            max_tokens=min(max_tokens, 4096)
        )
        return response.choices[0].message.content
    except BadRequestError as e:
        return f"⚠️ خطأ في طلب الذكاء الاصطناعي: {str(e)}. حاول تقليل طول النص أو استخدام نموذج آخر."
    except Exception as e:
        return f"❌ فشل الاتصال بالمساعد الذكي: {str(e)}"

def save_chat_history(session_id, role, content, model="", tab_name=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ai_chat_history (session_id, role, content, model, tab_name, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, role, content, model, tab_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_chat_history(session_id=None, limit=20):
    conn = get_conn()
    if session_id:
        rows = conn.execute("SELECT * FROM ai_chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ai_chat_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_chat_sessions():
    conn = get_conn()
    sessions = conn.execute("""
        SELECT session_id, MIN(timestamp) as first_message, COUNT(*) as message_count
        FROM ai_chat_history GROUP BY session_id ORDER BY first_message DESC LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(s) for s in sessions]

# ===================== ذاكرة المحادثة (Memory Compression) =====================
def compress_chat_memory(session_id,model="qwen/qwen3.6-27b"):
    history = get_chat_history(session_id, limit=10)
    if not history:
        return ""
    history_sorted = sorted(history, key=lambda x: x['timestamp'])
    dialogue = "\n".join([f"{h['role']}: {h['content']}" for h in history_sorted])
    prompt = f"""لخص الحوار التالي في جملة واحدة بالعربية تصف الموضوع الرئيسي والنتيجة:
{dialogue}
الملخص:"""
    try:
        return query_groq("أنت مساعد تلخيص محترف. اكتب جملة واحدة فقط.", prompt, model=model, max_tokens=150)
    except Exception:
        return "ملخص غير متاح"

# ===================== التحقق من صحة البيانات (Validation) =====================
def validate_financial_snapshot(snap):
    warnings = []
    if snap['revenue'] < 0:
        warnings.append("الإيرادات سالبة – تحقق من ترحيل حسابات الإيرادات.")
    if snap['assets'] <= 0:
        warnings.append("الأصول صفر أو سالبة – قد تكون القيود غير مكتملة.")
    if snap['profit_margin'] > 80:
        warnings.append("هامش ربح مرتفع جداً (>80%) – تأكد من دقة بيانات المصروفات.")
    return warnings

# ===================== AI Data Layer (Snapshots) =====================
def get_financial_snapshot():
    cache_key = "financial_snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    conn = get_conn()
    revenue = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    assets = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '3%'").fetchone()[0]
    
    top_cust = [dict(r) for r in conn.execute("""
        SELECT c.name, SUM(i.total) as total FROM invoices i JOIN customers c ON i.customer_id = c.id WHERE i.type='sale' AND i.status='completed' GROUP BY c.id ORDER BY total DESC LIMIT 3
    """).fetchall()]
    top_supp = [dict(r) for r in conn.execute("""
        SELECT s.name, SUM(i.total) as total FROM invoices i JOIN suppliers s ON i.supplier_id = s.id WHERE i.type='purchase' AND i.status='completed' GROUP BY s.id ORDER BY total DESC LIMIT 3
    """).fetchall()]
    sales_trend = [dict(r) for r in conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total FROM invoices WHERE type='sale' AND status='completed' GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()]
    
    conn.close()
    net_income = revenue - expenses
    profit_margin = (net_income / revenue * 100) if revenue > 0 else 0
    debt_ratio = (liabilities / assets * 100) if assets > 0 else 0
    roa = (net_income / assets * 100) if assets > 0 else 0
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
        "sales_trend": sales_trend,
        "warnings": validate_financial_snapshot({
            "revenue": revenue, "expenses": expenses, "net_income": net_income,
            "assets": assets, "liabilities": liabilities, "equity": equity,
            "profit_margin": profit_margin, "debt_ratio": debt_ratio, "roa": roa
        })
    }
    _cache_set(cache_key, snap)
    return snap

def get_inventory_snapshot():
    cache_key = "inventory_snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    conn = get_conn()
    all_products = [dict(r) for r in conn.execute("""
        SELECT name, quantity, reorder_level, selling_price, purchase_price
        FROM products ORDER BY quantity ASC
    """).fetchall()]
    total_products = len(all_products)
    low_stock = [p for p in all_products if p['quantity'] < p['reorder_level']]
    
    for p in all_products:
        if p['selling_price'] and p['purchase_price'] and p['purchase_price'] > 0:
            p['profit_margin'] = round((p['selling_price'] - p['purchase_price']) / p['selling_price'] * 100, 1)
        else:
            p['profit_margin'] = 0
        
        if p['quantity'] <= 0:
            p['recommendation'] = "نفد المخزون"
        elif p['quantity'] < p['reorder_level']:
            p['recommendation'] = f"طلب {p['reorder_level'] - p['quantity']} وحدة"
        elif p['quantity'] < p['reorder_level'] * 2:
            p['recommendation'] = "مراقبة"
        else:
            p['recommendation'] = "آمن"
    
    conn.close()
    snap = {
        "total_products": total_products,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:10],
        "top_products": sorted(all_products, key=lambda x: x['quantity'], reverse=True)[:10],
        "all_products": all_products[:20]
    }
    _cache_set(cache_key, snap)
    return snap

def get_business_snapshot():
    cache_key = "business_snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    conn = get_conn()
    top_customers = [dict(r) for r in conn.execute("""
        SELECT c.name, COUNT(i.id) as invoice_count, SUM(i.total) as total
        FROM invoices i JOIN customers c ON i.customer_id = c.id
        WHERE i.type='sale' AND i.status='completed'
        GROUP BY c.id ORDER BY total DESC LIMIT 5
    """).fetchall()]
    top_suppliers = [dict(r) for r in conn.execute("""
        SELECT s.name, COUNT(i.id) as invoice_count, SUM(i.total) as total
        FROM invoices i JOIN suppliers s ON i.supplier_id = s.id
        WHERE i.type='purchase' AND i.status='completed'
        GROUP BY s.id ORDER BY total DESC LIMIT 5
    """).fetchall()]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    total_suppliers = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    conn.close()
    snap = {
        "total_customers": total_customers,
        "total_suppliers": total_suppliers,
        "top_customers": top_customers,
        "top_suppliers": top_suppliers
    }
    _cache_set(cache_key, snap)
    return snap

def get_hr_snapshot():
    cache_key = "hr_snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    conn = get_conn()
    total_employees = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    total_salary = conn.execute("SELECT COALESCE(SUM(basic_salary),0) FROM employee_salaries").fetchone()[0]
    conn.close()
    snap = {
        "total_employees": total_employees,
        "total_monthly_salary": round(total_salary, 2)
    }
    _cache_set(cache_key, snap)
    return snap

def get_trend_snapshot():
    cache_key = "trend_snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    conn = get_conn()
    trends = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month,
               SUM(CASE WHEN type='sale' THEN total ELSE 0 END) as sales,
               SUM(CASE WHEN type='purchase' THEN total ELSE 0 END) as purchases
        FROM invoices WHERE status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()
    conn.close()
    snap = [dict(t) for t in trends]
    _cache_set(cache_key, snap)
    return snap

def get_cost_center_snapshot():
    cache_key = "cost_center_snapshot"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    from services import cost_center_service as ccs
    centers = ccs.get_all_cost_centers(active_only=True)
    summary = []
    for c in centers:
        balance = ccs.get_cost_center_balance(c['id'])
        summary.append({
            "code": c['code'],
            "name": c['name'],
            "net_balance": balance['net']
        })
    _cache_set(cache_key, summary)
    return summary

def build_ai_context(include_cost_centers=True):
    ctx = {}
    fin = get_financial_snapshot()
    for k, v in fin.items(): ctx[k] = v
    inv = get_inventory_snapshot()
    for k, v in inv.items(): 
        if k not in ctx: ctx[k] = v
    biz = get_business_snapshot()
    for k, v in biz.items(): 
        if k not in ctx: ctx[k] = v
    hr = get_hr_snapshot()
    for k, v in hr.items(): 
        if k not in ctx: ctx[k] = v
    ctx["trends"] = get_trend_snapshot()
    if include_cost_centers:
        ctx["cost_centers"] = get_cost_center_snapshot()
    return ctx

# ===================== دوال عامة =====================
def get_comprehensive_data(): return build_ai_context()
def get_inventory_data(): 
    snap = get_inventory_snapshot()
    return snap['low_stock_items'], snap['all_products'][:20]
def get_employee_info(name):
    conn = get_conn()
    emp = conn.execute("SELECT * FROM employees WHERE name LIKE ?", (f"%{name}%",)).fetchone()
    if emp:
        sal = conn.execute("SELECT * FROM employee_salaries WHERE employee_id=?", (emp["id"],)).fetchone()
        conn.close()
        return dict(emp), dict(sal) if sal else None
    conn.close()
    return None, None
def get_recent_entries():
    conn = get_conn()
    entries = [dict(r) for r in conn.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 200").fetchall()]
    conn.close()
    return entries
def get_all_accounts():
    conn = get_conn()
    accounts = [dict(r) for r in conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()]
    conn.close()
    return accounts
def get_financial_ratios():
    fin = get_financial_snapshot()
    return {
        "هامش الربح": f"{fin['profit_margin']:.1f}%",
        "نسبة المديونية": f"{fin['debt_ratio']:.1f}%",
        "العائد على الأصول": f"{fin['roa']:.1f}%",
        "صافي الدخل": f"{fin['net_income']:,.2f}"
    }
def get_trend_analysis(): return get_trend_snapshot()

# ===================== دوال مراكز التكلفة (مُعدّلة للاختصار) =====================
def analyze_cost_center_performance(center_id):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center: return "مركز التكلفة غير موجود"
    balance = ccs.get_cost_center_balance(center_id)
    income_stmt = ccs.get_cost_center_income_statement(center_id, '2020-01-01', datetime.now().strftime('%Y-%m-%d'))
    data_text = f"""المركز: {center['name']} | مدين: {balance['total_debit']} | دائن: {balance['total_credit']} | صافي: {balance['net']} | إيرادات: {income_stmt['income']} | مصروفات: {income_stmt['expenses']} | ربح: {income_stmt['net_profit']}"""
    
    system_prompt = """أنت محلل مالي. قدم تحليلك بشكل مختصر جداً ومباشر.
استخدم الجداول والنقاط (Bullet points) فقط. يمنع منعاً باتاً استخدام المقدمات أو الخاتمات.
المطلوب:
1. جدول ملخص الأداء.
2. نقاط القوة والضعف (نقاط سريعة).
3. توصيات محددة لتحسين الأداء."""
    return query_groq(system_prompt, data_text, max_tokens=1000)

def compare_cost_centers():
    summary = get_cost_center_snapshot()
    if not summary: return "لا توجد بيانات"
    data_text = json.dumps(summary, ensure_ascii=False)
    
    system_prompt = """أنت محلل مالي. قدم المقارنة باختصار شديد.
يمنع استخدام أي مقدمات أو خاتمات إنشائية.
المطلوب:
1. جدول مقارنة مباشر للترتيب والربحية.
2. نقطة واحدة لأفضل مركز ونقطة لأسوأ مركز.
3. توصيتين استراتيجيتين فقط في شكل نقاط."""
    return query_groq(system_prompt, data_text, max_tokens=1000)

def predict_cost_center_expenses(center_id, months=3):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center: return "المركز غير موجود"
    conn = get_conn()
    history = [dict(m) for m in conn.execute("SELECT strftime('%Y-%m', je.date) as month, SUM(cca.amount) as total FROM cost_center_allocations cca JOIN journal_lines jl ON cca.journal_line_id = jl.id JOIN journal_entries je ON jl.entry_id = je.id WHERE cca.cost_center_id = ? AND jl.debit > 0 GROUP BY month ORDER BY month DESC LIMIT 12", (center_id,)).fetchall()]
    conn.close()
    
    system_prompt = """أنت خبير مالي. اكتب التوقعات مباشرة بدون مقدمات.
المطلوب:
1. جدول التوقعات (الشهر، القيمة المتوقعة، نسبة التغير).
2. ثلاث نقاط مختصرة جداً عن العوامل المؤثرة والتوصيات."""
    return query_groq(system_prompt, json.dumps(history), max_tokens=800)

def get_cost_center_budget_analysis(center_id, fiscal_year):
    from services import cost_center_service as ccs
    variance_data = ccs.get_budget_variance(center_id, fiscal_year)
    if not variance_data: return "لا توجد موازنات مسجلة"
    
    system_prompt = """أنت محلل موازنات. ادخل في صلب الموضوع مباشرة.
المطلوب:
1. جدول مباشر يوضح الانحرافات الرئيسية فقط.
2. 3 نقاط مختصرة لتفسير الانحرافات والتوصيات. بدون أي كلام إنشائي."""
    return query_groq(system_prompt, json.dumps(variance_data['details']), max_tokens=1000)

# ===================== محرك القيود الآلي (Automated Entry Engine) =====================
def extract_entry_data(text, model="openai/gpt-oss-120b"):
    system_prompt = """أنت محاسب قانوني محترف. مهمتك تحويل النص إلى JSON دقيق وصالح بنسبة 100%.
**هام جداً: يجب أن يكون الرد عبارة عن كود JSON فقط بدون أي نص قبله أو بعده أو علامات Markdown.**

الهيكل المطلوب حصراً:
{
    "operation_type": "نوع العملية",
    "lines": [
        {"account": "اسم الحساب", "amount": 1000, "side": "debit أو credit"}
    ]
}"""
    response = query_groq(system_prompt, text, model=model, max_tokens=500, temperature=0.0)
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        return json.loads(response[start:end]) if start != -1 else None
    except:
        return None

def build_balanced_entry(extracted_data):
    if not extracted_data or not extracted_data.get('lines'): return None, "فشل استخراج البيانات"
    lines = extracted_data['lines']
    total_debit = sum(float(l.get('amount', 0)) for l in lines if l.get('side') == 'debit')
    total_credit = sum(float(l.get('amount', 0)) for l in lines if l.get('side') == 'credit')
    entry_lines = list(lines)
    
    diff = round(total_debit - total_credit, 2)
    if diff > 0:
        entry_lines.append({'account': 'حساب تسوية', 'amount': diff, 'side': 'credit', 'auto_correction': True})
        total_credit += diff
    elif diff < 0:
        entry_lines.append({'account': 'حساب تسوية', 'amount': abs(diff), 'side': 'debit', 'auto_correction': True})
        total_debit += abs(diff)
        
    return {
        'lines': entry_lines, 'total_debit': total_debit, 'total_credit': total_credit,
        'is_balanced': abs(total_debit - total_credit) < 0.01,
        'has_auto_correction': any(l.get('auto_correction') for l in entry_lines)
    }

def format_entry_display(entry_data):
    if not entry_data: return "لا توجد بيانات"
    res = "".join([f"{'مدين' if l.get('side')=='debit' else 'دائن'} | {l.get('account','')} | {l.get('amount',0):,.2f}{' (تسوية)' if l.get('auto_correction') else ''}\n" for l in entry_data.get('lines',[])])
    res += f"\n✅ متوازن: مدين {entry_data['total_debit']:,.2f} = دائن {entry_data['total_credit']:,.2f}"
    return res

def calculate_confidence(ext, bal):
    if not ext or not bal or not bal.get('lines'): return 0
    if not bal.get('has_auto_correction'): return 100
    corr = sum(l.get('amount',0) for l in bal['lines'] if l.get('auto_correction'))
    tot = sum(l.get('amount',0) for l in bal['lines'] if not l.get('auto_correction'))
    if tot == 0: return 0
    pct = (corr / tot) * 100
    if pct < 2: return 90
    if pct < 5: return 70
    if pct < 10: return 50
    return 30

def get_confidence_level(conf):
    if conf >= 90: return "موثوق", "#10B981"
    if conf >= 70: return "شبه موثوق", "#F59E0B"
    return "مشكوك فيه/غير موثوق", "#EF4444"

def generate_entry_safe(text, model="openai/gpt-oss-120b"):
    ext = extract_entry_data(text, model)
    if not ext: return None, "❌ فشل الاستخراج.", 0, "غير موثوق", "#EF4444"
    ent = build_balanced_entry(ext)
    conf = calculate_confidence(ext, ent)
    lbl, clr = get_confidence_level(conf)
    disp = format_entry_display(ent) + f"\n📊 الثقة: {conf}% ({lbl})"
    return ent, disp, conf, lbl, clr

# ===================== محرك القيود بالقوالب =====================
ENTRY_TEMPLATES = {
    "بيع نقداً": {"description": "بيع بضاعة نقداً", "lines": [{"account": "النقدية", "amount": "{amount}", "side": "debit"}, {"account": "المبيعات", "amount": "{amount}", "side": "credit"}]},
    "بيع بالآجل": {"description": "بيع بضاعة بالآجل", "lines": [{"account": "العملاء", "amount": "{amount}", "side": "debit"}, {"account": "المبيعات", "amount": "{amount}", "side": "credit"}]},
    "شراء نقداً": {"description": "شراء بضاعة نقداً", "lines": [{"account": "المخزون", "amount": "{amount}", "side": "debit"}, {"account": "النقدية", "amount": "{amount}", "side": "credit"}]},
    "شراء بالآجل": {"description": "شراء بضاعة بالآجل", "lines": [{"account": "المخزون", "amount": "{amount}", "side": "debit"}, {"account": "الموردين", "amount": "{amount}", "side": "credit"}]},
    "قبض من عميل": {"description": "استلام دفعة من عميل", "lines": [{"account": "النقدية", "amount": "{amount}", "side": "debit"}, {"account": "العملاء", "amount": "{amount}", "side": "credit"}]},
    "دفع لمورد": {"description": "سداد دفعة لمورد", "lines": [{"account": "الموردين", "amount": "{amount}", "side": "debit"}, {"account": "النقدية", "amount": "{amount}", "side": "credit"}]},
    "سداد مصروف": {"description": "سداد مصروف نقداً", "lines": [{"account": "{expense_name}", "amount": "{amount}", "side": "debit"}, {"account": "النقدية", "amount": "{amount}", "side": "credit"}]}
}

def generate_template_entry(operation_type, amount, cash_amount=None, credit_amount=None, expense_name=None, vat_rate=None, adjustment_side=None, inventory_side=None):
    template = ENTRY_TEMPLATES.get(operation_type)
    if not template: return None, "❌ العملية غير مدعومة", 0, "غير موثوق", "#EF4444"
    
    lines = []
    for l in template["lines"]:
        amt = amount if l["amount"] == "{amount}" else amount
        if l["amount"] == "{expense_name}": account = expense_name or "مصروف"; amt = amount
        else: account = l["account"]
        lines.append({"account": account, "amount": round(amt, 2), "side": l["side"]})
        
    ent = build_balanced_entry({"lines": lines})
    disp = format_entry_display(ent) + f"\n📊 الثقة: 100% (قالب)"
    return ent, disp, 100, "موثوق", "#10B981"

def get_available_operations(): return list(ENTRY_TEMPLATES.keys())
def get_operation_description(op): return ENTRY_TEMPLATES.get(op, {}).get("description", "")
def is_mixed_operation(op): return op in ["بيع مختلط", "شراء مختلط"]
def is_vat_operation(op): return op in ["بيع شامل الضريبة", "شراء شامل الضريبة"]
def is_salary_operation(op): return op == "رواتب موظفين"
def is_inventory_adjustment(op): return op == "تسوية مخزنية (جرد)"
