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

def query_groq(system_prompt, user_query, model="openai/gpt-oss-120b", max_tokens=4000, temperature=0.3):
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
            max_tokens=min(max_tokens, 5000)
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
    # استخدام نموذج مختص وأخف للتلخيص السريع
    history = get_chat_history(session_id, limit=10)
    if not history:
        return ""
    history_sorted = sorted(history, key=lambda x: x['timestamp'])
    dialogue = "\n".join([f"{h['role']}: {h['content']}" for h in history_sorted])
    prompt = f"""لخص الحوار التالي في جملة واحدة بالعربية تصف الموضوع الرئيسي والنتيجة:
{dialogue}
الملخص:"""
    try:
        return query_groq("أنت مساعد تلخيص محترف.", prompt, model=model, max_tokens=150)
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
    
    # بيانات إضافية
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
    # جلب جميع المنتجات مع أسعارها وكمياتها
    all_products = [dict(r) for r in conn.execute("""
        SELECT name, quantity, reorder_level, selling_price, purchase_price
        FROM products ORDER BY quantity ASC
    """).fetchall()]
    total_products = len(all_products)
    low_stock = [p for p in all_products if p['quantity'] < p['reorder_level']]
    
    # تحليل ذكي لكل منتج
    for p in all_products:
        if p['selling_price'] and p['purchase_price'] and p['purchase_price'] > 0:
            p['profit_margin'] = round((p['selling_price'] - p['purchase_price']) / p['selling_price'] * 100, 1)
        else:
            p['profit_margin'] = 0
        
        # توصية ذكية
        if p['quantity'] <= 0:
            p['recommendation'] = "⚠️ نفد المخزون - طلب عاجل"
        elif p['quantity'] < p['reorder_level']:
            p['recommendation'] = f"📉 تحت الحد الأدنى - طلب {p['reorder_level'] - p['quantity']} وحدة"
        elif p['quantity'] < p['reorder_level'] * 2:
            p['recommendation'] = "📊 راقب المخزون"
        else:
            p['recommendation'] = "✅ مخزون آمن"
    
    conn.close()
    snap = {
        "total_products": total_products,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:10],
        "top_products": sorted(all_products, key=lambda x: x['quantity'], reverse=True)[:10],
        "all_products": all_products[:20]  # أول 20 منتج للتحليل
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
    # بناء قاموس مسطح بالكامل
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
    
    trends = get_trend_snapshot()
    ctx["trends"] = trends
    
    if include_cost_centers:
        ctx["cost_centers"] = get_cost_center_snapshot()
    
    return ctx

# ===================== دوال عامة =====================
def get_comprehensive_data():
    return build_ai_context()

def get_inventory_data():
    snapshot = get_inventory_snapshot()
    return snapshot['low_stock_items'], snapshot['all_products'][:20]

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

def get_trend_analysis():
    return get_trend_snapshot()

def get_top_customers(limit=5):
    conn = get_conn()
    customers = conn.execute("""
        SELECT c.name, COUNT(i.id) as invoice_count, SUM(i.total) as total
        FROM invoices i JOIN customers c ON i.customer_id = c.id
        WHERE i.type='sale' AND i.status='completed'
        GROUP BY c.id ORDER BY total DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(c) for c in customers]

def get_top_suppliers(limit=5):
    conn = get_conn()
    suppliers = conn.execute("""
        SELECT s.name, COUNT(i.id) as invoice_count, SUM(i.total) as total
        FROM invoices i JOIN suppliers s ON i.supplier_id = s.id
        WHERE i.type='purchase' AND i.status='completed'
        GROUP BY s.id ORDER BY total DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(s) for s in suppliers]

# ===================== دوال مراكز التكلفة =====================
def get_cost_centers_summary_for_ai():
    return get_cost_center_snapshot()

def analyze_cost_center_performance(center_id):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center:
        return "مركز التكلفة غير موجود"
    balance = ccs.get_cost_center_balance(center_id)
    income_stmt = ccs.get_cost_center_income_statement(center_id, '2020-01-01', datetime.now().strftime('%Y-%m-%d'))
    transactions = ccs.get_center_transactions(center_id, limit=20)
    data_text = f"""
    مركز التكلفة: {center['code']} - {center['name']}
    الحالة: {'نشط' if center['is_active'] else 'غير نشط'}
    الملخص المالي:
    - إجمالي المدين: {balance['total_debit']:,.2f}
    - إجمالي الدائن: {balance['total_credit']:,.2f}
    - صافي التدفق: {balance['net']:,.2f}
    قائمة الدخل (منذ 2020):
    - الإيرادات: {income_stmt['income']:,.2f}
    - المصروفات: {income_stmt['expenses']:,.2f}
    - صافي الربح/الخسارة: {income_stmt['net_profit']:,.2f}
    آخر 20 معاملة:
    {json.dumps([dict(t) for t in transactions], ensure_ascii=False, indent=2)}
    """
    system_prompt = """أنت محلل مالي محترف متخصص في تحليل أداء مراكز التكلفة.
قم بتحليل البيانات المقدمة وقدم:
1. تقييم عام لأداء المركز
2. نقاط القوة والضعف
3. توصيات محددة لتحسين الأداء
4. مقارنة ضمنية مع المعايير المثالية
اجعل الرد باللغة العربية، منظماً وواضحاً، مع أرقام داعمة للتحليل."""
    return query_groq(system_prompt, data_text, max_tokens=1500)

def compare_cost_centers():
    summary = get_cost_center_snapshot()
    if not summary:
        return "لا توجد مراكز تكلفة نشطة للمقارنة"
    data_text = f"بيانات مراكز التكلفة للمقارنة:\n{json.dumps(summary, ensure_ascii=False, indent=2)}"
    system_prompt = """أنت محلل مالي استراتيجي. قارن بين مراكز التكلفة المقدمة وقدم:
1. ترتيب المراكز حسب الربحية
2. تحديد المركز الأفضل والأسوأ أداءً
3. تحليل توزيع الموارد بين المراكز
4. توصيات استراتيجية للشركة بناءً على هذه المقارنة
الرد بالعربية مع جداول مقارنة عند الإمكان."""
    return query_groq(system_prompt, data_text, max_tokens=1500)

def predict_cost_center_expenses(center_id, months=3):
    from services import cost_center_service as ccs
    center = ccs.get_cost_center_by_id(center_id)
    if not center:
        return "مركز التكلفة غير موجود"
    conn = get_conn()
    monthly_expenses = conn.execute("""
        SELECT strftime('%Y-%m', je.date) as month,
               SUM(cca.amount) as total
        FROM cost_center_allocations cca
        JOIN journal_lines jl ON cca.journal_line_id = jl.id
        JOIN journal_entries je ON jl.entry_id = je.id
        WHERE cca.cost_center_id = ? AND jl.debit > 0
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """, (center_id,)).fetchall()
    conn.close()
    if not monthly_expenses:
        return "لا توجد بيانات تاريخية كافية للتنبؤ"
    history = [dict(m) for m in monthly_expenses]
    data_text = f"""
    مركز التكلفة: {center['code']} - {center['name']}
    المصروفات الشهرية التاريخية (آخر 12 شهراً):
    {json.dumps(history, ensure_ascii=False, indent=2)}
    المطلوب: التنبؤ بالمصروفات للأشهر {months} القادمة.
    """
    system_prompt = """أنت خبير في التحليل المالي والتنبؤ بالمصروفات.
حلل الاتجاه التاريخي وقدم:
1. توقعات المصروفات لكل شهر من الأشهر القادمة
2. نسبة النمو أو الانخفاض المتوقعة
3. العوامل التي قد تؤثر على هذه التوقعات
4. توصيات للتحكم في المصروفات
الرد بالعربية مع أرقام واضحة."""
    return query_groq(system_prompt, data_text, max_tokens=1200)

def get_cost_center_budget_analysis(center_id, fiscal_year):
    from services import cost_center_service as ccs
    variance_data = ccs.get_budget_variance(center_id, fiscal_year)
    if not variance_data or not variance_data.get('details'):
        return "لا توجد موازنات مسجلة لهذا المركز في هذه السنة"
    center = ccs.get_cost_center_by_id(center_id)
    data_text = f"""
    مركز التكلفة: {center['code']} - {center['name']}
    السنة المالية: {fiscal_year}
    ملخص الموازنة:
    - إجمالي الموازنة: {variance_data['total_budget']:,.2f}
    - إجمالي الفعلي: {variance_data['total_actual']:,.2f}
    - الانحراف الإجمالي: {variance_data['total_variance']:,.2f} ({variance_data['total_variance_pct']}%)
    التفاصيل حسب الحساب:
    {json.dumps(variance_data['details'], ensure_ascii=False, indent=2)}
    """
    system_prompt = """أنت محلل موازنات محترف. حلل انحرافات الموازنة وقدم:
1. تحليل أسباب الانحرافات الرئيسية
2. الحسابات الأكثر انحرافاً عن الموازنة
3. تقييم عام لكفاءة إعداد الموازنة
4. توصيات لتحسين دقة الموازنات المستقبلية
الرد بالعربية مع التركيز على الانحرافات الجوهرية."""
    return query_groq(system_prompt, data_text, max_tokens=1500)

# ===================== محرك القيود الآلي (Automated Entry Engine) =====================
def extract_entry_data(text, model="openai/gpt-oss-120b"):
    """
    تستخدم الذكاء الاصطناعي لفهم العملية واستخراج البيانات منها فقط (بدون بناء القيد).
    ترجع قاموساً يحتوي على المفاتيح التالية:
    - operation_type: نوع العملية
    - lines: قائمة من الأسطر
    """
    system_prompt = """أنت محاسب قانوني محترف ومتخصص في تحويل أي عملية مالية إلى قيد محاسبي صحيح.
مهمتك هي تحليل العملية المالية ثم استخراج البيانات بصيغة JSON.
يجب أن تتبع القواعد الذهبية للمحاسبة بدقة:

**القواعد الذهبية (يجب الالتزام بها بدقة):**
1. عند البيع (بيع بضاعة) نقداً:
   المدين = النقدية أو البنك (بقيمة البيع)
   الدائن = المبيعات (بقيمة البيع)

2. عند الشراء (شراء بضاعة) نقداً:
   المدين = المخزون (بقيمة الشراء)
   الدائن = النقدية أو البنك (بقيمة الشراء)

3. عند البيع بالآجل:
   المدين = العملاء (بقيمة البيع)
   الدائن = المبيعات (بقيمة البيع)

4. عند الشراء بالآجل:
   المدين = المخزون (بقيمة الشراء)
   الدائن = الموردين (بقيمة الشراء)

5. عند البيع المختلط (نصف نقداً ونصف آجلاً):
   المدين = النقدية (بقيمة الجزء النقدي)
   المدين = العملاء (بقيمة الجزء الآجل)
   الدائن = المبيعات (بقيمة البيع الكاملة)

6. عند الشراء المختلط (نصف نقداً ونصف آجلاً):
   المدين = المخزون (بقيمة الشراء الكاملة)
   الدائن = النقدية (بقيمة الجزء النقدي)
   الدائن = الموردين (بقيمة الجزء الآجل)

7. عند قبض مبلغ من عميل:
   المدين = النقدية
   الدائن = العملاء

8. عند دفع مبلغ لمورد:
   المدين = الموردين
   الدائن = النقدية

9. عند سداد مصروف (كهرباء، إيجار، رواتب):
   المدين = المصروف
   الدائن = النقدية

10. الأصول تزيد بطرف مدين، والالتزامات تزيد بطرف دائن.

11. عند شراء أصل ثابت (سيارة، جهاز، أثاث) نقداً:
    المدين = الأصل الثابت (بقيمة الشراء)
    الدائن = النقدية أو البنك (بقيمة الشراء)

12. عند احتساب إهلاك أصل ثابت:
    المدين = مصروف الإهلاك (بقيمة الإهلاك)
    الدائن = مجمع الإهلاك (بقيمة الإهلاك)

13. عند تسجيل ضريبة القيمة المضافة على عملية بيع:
    المدين = النقدية أو العملاء (بقيمة البيع شامل الضريبة)
    الدائن = المبيعات (بقيمة البيع غير شامل الضريبة)
    الدائن = ضريبة القيمة المضافة المستحقة (بقيمة الضريبة)

14. عند احتساب رواتب الموظفين (مع خصومات):
    المدين = مصروف الرواتب (بقيمة إجمالي الرواتب)
    الدائن = التأمينات المستحقة (بقيمة خصم التأمينات)
    الدائن = السلف المستحقة (بقيمة خصم السلف)
    الدائن = البنك (بقيمة الصافي)

15. عند تسوية بنكية (رسوم بنكية):
    المدين = مصروف رسوم بنكية (بقيمة الرسوم)
    الدائن = البنك (بقيمة الرسوم)

16. عند إقفال حساب إيرادات في نهاية الفترة:
    المدين = الإيرادات (بقيمة الرصيد)
    الدائن = أرباح وخسائر (بقيمة الرصيد)

المطلوب هو استخراج البيانات التالية بصيغة JSON:
{
    "operation_type": "بيع، شراء، قبض، دفع، سداد مصروف، إهلاك، ضريبة، رواتب، إلخ",
    "lines": [
        {
            "account": "اسم الحساب بالعربية (مثلاً: النقدية، المخزون، المبيعات، الموردين، الرواتب، العملاء، إلخ)",
            "amount": المبلغ (رقم فقط بدون رموز),
            "side": "debit أو credit"
        }
    ]
}

تعليمات إضافية:
- استخرج الأرقام والمبالغ بدقة من النص.
- لا تقم بدمج الحسابات أو طرحها من بعضها.
- أعد JSON صالحاً فقط، بدون أي نص إضافي خارج الأقواس.
- إذا ذكرت العملية 'شامل الضريبة'، فافصل الضريبة في سطر منفصل.
- إذا كانت العملية مختلطة (نقداً وآجلاً)، استخدم الأسطر المنفصلة لكل جزء.
- تذكر: في البيع المختلط، النقدية + العملاء = المبيعات (كلها بنفس القيمة).
- تذكر: في الشراء المختلط، المخزون = النقدية + الموردين (كلها بنفس القيمة).
"""
    
    response = query_groq(system_prompt, text, model=model, max_tokens=800, temperature=0.1)
    
    try:
        # محاولة استخراج JSON من الرد
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end > start:
            json_str = response[start:end]
            data = json.loads(json_str)
            return data
        else:
            return None
    except json.JSONDecodeError:
        return None

def build_balanced_entry(extracted_data):
    """
    تبني قيداً متوازناً من البيانات المستخرجة باستخدام Python فقط.
    تضمن أن مجموع المدين يساوي مجموع الدائن.
    """
    if not extracted_data:
        return None, "فشل استخراج البيانات من العملية"
    
    lines = extracted_data.get('lines', [])
    if not lines:
        return None, "لم يتم العثور على أسطر قيد"
    
    total_debit = 0
    total_credit = 0
    entry_lines = []
    
    # حساب المجاميع
    for line in lines:
        try:
            amount = float(line.get('amount', 0))
        except (ValueError, TypeError):
            amount = 0
        
        if line.get('side') == 'debit':
            total_debit += amount
        else:
            total_credit += amount
        
        entry_lines.append(line)
    
    # التحقق من التوازن ومحاولة إصلاحه إن أمكن
    if abs(total_debit - total_credit) > 0.01:
        difference = total_debit - total_credit
        if difference > 0:
            # المدين أكبر: أضف فرق للدائن
            entry_lines.append({
                'account': 'حساب تسوية',
                'amount': round(difference, 2),
                'side': 'credit',
                'auto_correction': True
            })
            total_credit += difference
        else:
            # الدائن أكبر: أضف فرق للمدين
            entry_lines.append({
                'account': 'حساب تسوية',
                'amount': round(abs(difference), 2),
                'side': 'debit',
                'auto_correction': True
            })
            total_debit += abs(difference)
    
    return {
        'lines': entry_lines,
        'total_debit': round(total_debit, 2),
        'total_credit': round(total_credit, 2),
        'is_balanced': abs(total_debit - total_credit) < 0.01,
        'has_auto_correction': any(line.get('auto_correction') for line in entry_lines)
    }

def format_entry_display(entry_data):
    """
    تنسيق القيد للعرض على المستخدم.
    """
    if not entry_data:
        return "لا توجد بيانات لعرضها"
    
    lines = entry_data.get('lines', [])
    result = ""
    
    for line in lines:
        side = "مدين" if line.get('side') == 'debit' else "دائن"
        account = line.get('account', 'غير معروف')
        amount = line.get('amount', 0)
        auto = " (تسوية تلقائية)" if line.get('auto_correction') else ""
        result += f"{side} | {account} | {amount:,.2f}{auto}\n"
    
    result += f"\n✅ القيد متوازن: مدين {entry_data['total_debit']:,.2f} = دائن {entry_data['total_credit']:,.2f}"
    
    if entry_data.get('has_auto_correction'):
        result += "\n⚠️ تمت إضافة تسوية تلقائية لضمان التوازن."
    
    return result

def generate_entry(text, model="openai/gpt-oss-120b"):
    """
    الدالة الرئيسية لتوليد قيد محاسبي متوازن.
    تجمع بين استخراج البيانات (AI) وبناء القيد المتوازن (Python).
    """
    # الخطوة 1: استخراج البيانات من النص
    extracted = extract_entry_data(text, model=model)
    if not extracted:
        return None, "فشل استخراج بيانات العملية. حاول صياغة العملية بشكل أوضح."
    
    # الخطوة 2: بناء القيد المتوازن
    entry = build_balanced_entry(extracted)
    if not entry:
        return None, "فشل بناء القيد من البيانات المستخرجة."
    
    # الخطوة 3: تنسيق القيد للعرض
    display = format_entry_display(entry)
    
    return entry, display

# ===================== نظام الثقة في القيود (Entry Confidence System) =====================
def calculate_confidence(extracted_data, balanced_entry):
    """
    تحسب نسبة الثقة في القيد المُولَّد بناءً على عدة عوامل:
    ترجع نسبة مئوية (0-100).
    """
    if not extracted_data or not balanced_entry:
        return 0
    
    lines = balanced_entry.get('lines', [])
    if not lines:
        return 0
    
    has_correction = balanced_entry.get('has_auto_correction', False)
    
    if not has_correction:
        # لا توجد تسوية = ثقة 100%
        return 100
    
    # حساب الفرق الذي تمت تسويته
    correction_amount = 0
    total_before_correction = 0
    
    for line in lines:
        amount = line.get('amount', 0)
        if line.get('auto_correction'):
            correction_amount = amount
        else:
            total_before_correction += amount
    
    if total_before_correction == 0:
        return 0
    
    # حساب نسبة الفرق
    correction_pct = correction_amount / total_before_correction * 100
    
    if correction_pct < 2:
        return 90
    elif correction_pct < 5:
        return 70
    elif correction_pct < 10:
        return 50
    else:
        return 30


def get_confidence_level(confidence):
    """
    ترجع (label, color) بناءً على نسبة الثقة.
    """
    if confidence >= 90:
        return "موثوق", "#10B981"  # أخضر
    elif confidence >= 70:
        return "شبه موثوق", "#F59E0B"  # برتقالي
    elif confidence >= 40:
        return "مشكوك فيه", "#EF4444"  # أحمر
    else:
        return "غير موثوق", "#EF4444"  # أحمر غامق


def generate_entry_safe(text, model="openai/gpt-oss-120b"):
    """
    الدالة الرئيسية لتوليد قيد محاسبي آمن مع نسبة ثقة.
    """
    # الخطوة 1: استخراج البيانات من النص
    extracted = extract_entry_data(text, model=model)
    if not extracted:
        return None, "❌ فشل استخراج بيانات العملية. حاول صياغة العملية بشكل أوضح.", 0, "غير موثوق", "#EF4444"
    
    # الخطوة 2: بناء القيد المتوازن
    entry = build_balanced_entry(extracted)
    if not entry:
        return None, "❌ فشل بناء القيد من البيانات المستخرجة.", 0, "غير موثوق", "#EF4444"
    
    # الخطوة 3: حساب نسبة الثقة
    confidence = calculate_confidence(extracted, entry)
    confidence_label, confidence_color = get_confidence_level(confidence)
    
    # الخطوة 4: تنسيق القيد للعرض
    display = format_entry_display(entry)
    
    # إضافة سطر الثقة
    confidence_line = f"\n📊 نسبة الثقة: {confidence}% ({confidence_label})"
    display += confidence_line
    
    return entry, display, confidence, confidence_label, confidence_color

# ===================== محرك القيود بالقوالب =====================

# قوالب العمليات المالية
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
    "بيع مختلط": {
        "description": "بيع بضاعة (نقداً + آجلاً)",
        "lines": [
            {"account": "النقدية", "amount": "{cash}", "side": "debit"},
            {"account": "العملاء", "amount": "{credit}", "side": "debit"},
            {"account": "المبيعات", "amount": "{amount}", "side": "credit"}
        ]
    },
    "بيع شامل الضريبة": {
        "description": "بيع بضاعة شامل ضريبة القيمة المضافة",
        "lines": [
            {"account": "النقدية", "amount": "{amount}", "side": "debit"},
            {"account": "المبيعات", "amount": "{net}", "side": "credit"},
            {"account": "ضريبة القيمة المضافة المستحقة", "amount": "{vat}", "side": "credit"}
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
    "شراء مختلط": {
        "description": "شراء بضاعة (نقداً + آجلاً)",
        "lines": [
            {"account": "المخزون", "amount": "{amount}", "side": "debit"},
            {"account": "النقدية", "amount": "{cash}", "side": "credit"},
            {"account": "الموردين", "amount": "{credit}", "side": "credit"}
        ]
    },
    "شراء شامل الضريبة": {
        "description": "شراء بضاعة شامل ضريبة القيمة المضافة",
        "lines": [
            {"account": "المخزون", "amount": "{net}", "side": "debit"},
            {"account": "ضريبة القيمة المضافة المدخلة", "amount": "{vat}", "side": "debit"},
            {"account": "النقدية", "amount": "{amount}", "side": "credit"}
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
    },
    "شراء أصل ثابت": {
        "description": "شراء أصل ثابت نقداً",
        "lines": [
            {"account": "الأصل الثابت", "amount": "{amount}", "side": "debit"},
            {"account": "النقدية", "amount": "{amount}", "side": "credit"}
        ]
    },
    "شراء أصل ثابت بالآجل": {
        "description": "شراء أصل ثابت بالآجل",
        "lines": [
            {"account": "الأصل الثابت", "amount": "{amount}", "side": "debit"},
            {"account": "الموردين", "amount": "{amount}", "side": "credit"}
        ]
    },
    "إهلاك أصل": {
        "description": "احتساب إهلاك أصل ثابت",
        "lines": [
            {"account": "مصروف الإهلاك", "amount": "{amount}", "side": "debit"},
            {"account": "مجمع الإهلاك", "amount": "{amount}", "side": "credit"}
        ]
    },
    "تسوية بنكية": {
        "description": "رسوم بنكية",
        "lines": [
            {"account": "مصروف رسوم بنكية", "amount": "{amount}", "side": "debit"},
            {"account": "البنك", "amount": "{amount}", "side": "credit"}
        ]
    },
    "إقفال إيرادات": {
        "description": "إقفال حساب إيرادات في نهاية الفترة",
        "lines": [
            {"account": "المبيعات", "amount": "{amount}", "side": "debit"},
            {"account": "أرباح وخسائر", "amount": "{amount}", "side": "credit"}
        ]
    },
    "إقفال مصروفات": {
        "description": "إقفال حساب مصروفات في نهاية الفترة",
        "lines": [
            {"account": "أرباح وخسائر", "amount": "{amount}", "side": "debit"},
            {"account": "المصروف", "amount": "{amount}", "side": "credit"}
        ]
    },
    "تسوية مخزنية (جرد)": {
        "description": "تسوية مخزنية - جرد المخزون",
        "lines": [
            {"account": "تسوية مخزنية", "amount": "{amount}", "side": "{adjustment_side}"},
            {"account": "المخزون", "amount": "{amount}", "side": "{inventory_side}"}
        ]
    }
}

def generate_template_entry(operation_type, amount, cash_amount=None, credit_amount=None, expense_name=None, vat_rate=None, adjustment_side=None, inventory_side=None):
    """
    توليد قيد محاسبي متوازن باستخدام القوالب الجاهزة (دقة 100%).
    """
    template = ENTRY_TEMPLATES.get(operation_type)
    if not template:
        return None, f"❌ نوع العملية '{operation_type}' غير مدعوم", 0, "غير موثوق", "#EF4444"
    
    # بناء الأسطر مع استبدال المتغيرات
    lines = []
    for line in template["lines"]:
        account = line["account"]
        amount_str = line["amount"]
        
        # استبدال المتغيرات بالقيم الفعلية
        if amount_str == "{amount}":
            final_amount = amount
        elif amount_str == "{cash}":
            final_amount = cash_amount if cash_amount else amount / 2
        elif amount_str == "{credit}":
            final_amount = credit_amount if credit_amount else amount / 2
        elif amount_str == "{expense_name}":
            account = expense_name if expense_name else "مصروف"
            final_amount = amount
        elif amount_str == "{net}":
            final_amount = amount / (1 + vat_rate) if vat_rate else amount
        elif amount_str == "{vat}":
            final_amount = amount - (amount / (1 + vat_rate)) if vat_rate else 0
        elif amount_str == "{adjustment_side}":
            final_amount = amount
        elif amount_str == "{inventory_side}":
            final_amount = amount
        else:
            final_amount = amount
        
        # تحديد الطرف (مدين/دائن) - خاص بالتسوية المخزنية
        side = line["side"]
        if side == "{adjustment_side}":
            side = adjustment_side if adjustment_side else "debit"
        elif side == "{inventory_side}":
            side = inventory_side if inventory_side else "credit"
        
        lines.append({
            "account": account,
            "amount": round(final_amount, 2),
            "side": side
        })
    
    # بناء القيد المتوازن
    entry = build_balanced_entry({"operation_type": operation_type, "lines": lines})
    if not entry:
        return None, "❌ فشل بناء القيد", 0, "غير موثوق", "#EF4444"
    
    # تنسيق العرض
    display = format_entry_display(entry)
    display += f"\n📊 نسبة الثقة: 100% (موثوق - قالب جاهز)"
    
    return entry, display, 100, "موثوق", "#10B981"

def get_available_operations():
    """ترجع قائمة بأنواع العمليات المتاحة"""
    return list(ENTRY_TEMPLATES.keys())

def get_operation_description(operation_type):
    """ترجع وصف العملية"""
    template = ENTRY_TEMPLATES.get(operation_type)
    return template["description"] if template else ""

def is_mixed_operation(operation_type):
    """تتحقق مما إذا كانت العملية مختلطة (تحتاج نقداً وآجلاً)"""
    return operation_type in ["بيع مختلط", "شراء مختلط"]

def is_vat_operation(operation_type):
    """تتحقق مما إذا كانت العملية تشمل ضريبة"""
    return operation_type in ["بيع شامل الضريبة", "شراء شامل الضريبة"]

def is_salary_operation(operation_type):
    """تتحقق مما إذا كانت العملية متعلقة بالرواتب"""
    return operation_type == "رواتب موظفين"

def is_inventory_adjustment(operation_type):
    """تتحقق مما إذا كانت العملية تسوية مخزنية"""
    return operation_type == "تسوية مخزنية (جرد)"
