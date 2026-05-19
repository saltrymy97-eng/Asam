# ai_assistant.py – مساعد ذكي بواجهة زجاجية فخمة وألوان زاهية
# يدعم القيود المركبة وتسجيل القيد مباشرة في قاعدة البيانات
# المساعد المحاسبي الآن يرى كل بيانات النظام
# 🆕 تبويب التنبؤ بالمستقبل (مبيعات، تدفق نقدي، مخزون، أرباح)
import streamlit as st
import sqlite3
import pandas as pd
from groq import Groq
from datetime import date
import json

DB_PATH = "erp.db"

# ========== ألوان التصميم ==========
BG_GRADIENT = "linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%)"
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_CYAN = "#06B6D4"
ACCENT_PINK = "#EC4899"

# ========== دوال مساعدة ==========
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_accounts_table():
    """إنشاء جدول الحسابات إذا لم يكن موجوداً"""
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
    conn.commit()
    conn.close()

def query_groq(system_prompt, user_query, max_tokens=1500):
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0.3,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def get_comprehensive_data():
    """جمع جميع بيانات النظام للمساعد المحاسبي والتنبؤات"""
    conn = get_conn()
    
    # 1. الملخص المالي
    revenue = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines jl WHERE jl.account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(jl.debit)-SUM(jl.credit),0) FROM journal_lines jl WHERE jl.account_name LIKE '5%'").fetchone()[0]
    assets = conn.execute("SELECT COALESCE(SUM(jl.debit)-SUM(jl.credit),0) FROM journal_lines jl WHERE jl.account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines jl WHERE jl.account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines jl WHERE jl.account_name LIKE '3%'").fetchone()[0]
    
    # 2. المنتجات
    products = conn.execute("SELECT name, quantity, reorder_level, selling_price, purchase_price FROM products").fetchall()
    products_list = [dict(p) for p in products]
    
    # 3. العملاء
    customers = conn.execute("SELECT name, phone FROM customers").fetchall()
    customers_list = [dict(c) for c in customers]
    
    # 4. الموردين
    suppliers = conn.execute("SELECT name, phone FROM suppliers").fetchall()
    suppliers_list = [dict(s) for s in suppliers]
    
    # 5. الموظفين
    employees = conn.execute("""
        SELECT e.name, e.position, es.basic_salary, es.housing_allowance, es.transport_allowance, es.deductions
        FROM employees e
        LEFT JOIN employee_salaries es ON e.id = es.employee_id
    """).fetchall()
    employees_list = [dict(emp) for emp in employees]
    
    # 6. آخر الفواتير
    invoices = conn.execute("""
        SELECT i.type, i.invoice_date, i.total, i.status
        FROM invoices i
        ORDER BY i.id DESC LIMIT 10
    """).fetchall()
    invoices_list = [dict(inv) for inv in invoices]
    
    # 7. حركات المخزون الأخيرة
    stock = conn.execute("""
        SELECT sm.type, sm.quantity, sm.date, p.name
        FROM stock_movements sm
        JOIN products p ON sm.product_id = p.id
        ORDER BY sm.id DESC LIMIT 10
    """).fetchall()
    stock_list = [dict(s) for s in stock]
    
    # 8. آخر القيود
    entries = conn.execute("SELECT date, description FROM journal_entries ORDER BY id DESC LIMIT 5").fetchall()
    entries_list = [dict(e) for e in entries]
    
    # 9. بيانات إضافية للتنبؤات
    # الفواتير حسب الشهر (آخر 12 شهر)
    monthly_sales = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total
        FROM invoices WHERE type='sale' AND status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()
    monthly_sales_list = [dict(m) for m in monthly_sales]
    
    monthly_purchases = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total
        FROM invoices WHERE type='purchase' AND status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()
    monthly_purchases_list = [dict(m) for m in monthly_purchases]
    
    # معدل استهلاك المخزون
    stock_consumption = conn.execute("""
        SELECT p.name, 
               COALESCE(SUM(CASE WHEN sm.type='out' THEN sm.quantity ELSE 0 END), 0) as total_out,
               COUNT(DISTINCT strftime('%Y-%m', sm.date)) as months_count
        FROM products p
        LEFT JOIN stock_movements sm ON p.id = sm.product_id
        GROUP BY p.id
    """).fetchall()
    consumption_list = [dict(s) for s in stock_consumption]
    
    conn.close()
    
    return {
        "revenue": revenue, "expenses": expenses, "net_income": revenue - expenses,
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "products": products_list,
        "customers": customers_list,
        "suppliers": suppliers_list,
        "employees": employees_list,
        "recent_invoices": invoices_list,
        "recent_stock": stock_list,
        "recent_entries": entries_list,
        "monthly_sales": monthly_sales_list,
        "monthly_purchases": monthly_purchases_list,
        "stock_consumption": consumption_list
    }

def get_inventory_data():
    conn = get_conn()
    low_stock = [dict(r) for r in conn.execute("SELECT name, quantity, reorder_level FROM products WHERE quantity < reorder_level").fetchall()]
    all_products = [dict(r) for r in conn.execute("SELECT name, quantity, reorder_level FROM products").fetchall()]
    conn.close()
    return low_stock, all_products

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
    entries = [dict(r) for r in conn.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 20").fetchall()]
    conn.close()
    return entries

def get_all_accounts():
    conn = get_conn()
    accounts = [dict(r) for r in conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()]
    conn.close()
    return accounts

# ========== واجهة المساعد الذكي – تصميم زجاجي فخم ==========
def show():
    # ---------- رأس الصفحة ----------
    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🤖 المساعد الذكي XD</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">سبعة خبراء في مكان واحد لخدمة أعمالك</p>
    </div>
    """, unsafe_allow_html=True)

    create_accounts_table()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("❌ الرجاء إضافة `GROQ_API_KEY` في إعدادات Streamlit Cloud (Secrets).")
        return

    # ---------- تبويبات زجاجية ----------
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال",
        "🔮 تنبؤات مستقبلية"  # 🆕
    ])

    # ---------- 1. مساعد محاسبي (يرى كل البيانات الآن) ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>اسأل عن أي شيء في النظام</h3>", unsafe_allow_html=True)
        question = st.text_input("سؤالك:", placeholder="مثال: كم مخزون جالكسي؟ أو من هم الموردين؟", key="q1")
        if st.button("🔮 اسأل الخبير", key="ask_finance"):
            if question:
                data = get_comprehensive_data()
                # إزالة بيانات التنبؤ الثقيلة من prompt المساعد المحاسبي
                data_for_qa = {k: v for k, v in data.items() if k not in ["monthly_sales", "monthly_purchases", "stock_consumption"]}
                data_str = json.dumps(data_for_qa, ensure_ascii=False, indent=2, default=str)
                prompt = f"""أنت مساعد ذكي خبير في نظام ERP. لديك إمكانية الوصول إلى جميع بيانات النظام التالية:
{data_str}

أجب عن السؤال التالي بالعربية بناءً على هذه البيانات. إذا كانت البيانات لا تحتوي على إجابة، فقل "لا توجد معلومات كافية في النظام للإجابة على هذا السؤال." لا تختلق أي بيانات غير موجودة."""
                with st.spinner("🧠 التفكير..."):
                    answer = query_groq(prompt, question)
                st.markdown(f"""
                <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};">
                    <p style="color:{TEXT_PRIMARY}; font-size:1.1rem; margin:0;">{answer}</p>
                </div>
                """, unsafe_allow_html=True)

    # ---------- 2. محلل مالي ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تحليل القوائم المالية وتوصيات</h3>", unsafe_allow_html=True)
        if st.button("📈 حلل القوائم المالية الآن", key="analyze_fin"):
            data = get_comprehensive_data()
            prompt = f"""أنت محلل مالي خبير. حلل البيانات التالية وقدم توصيات:
- الإيرادات: {data['revenue']:,.2f}
- المصروفات: {data['expenses']:,.2f}
- صافي الدخل: {data['net_income']:,.2f}
- الأصول: {data['assets']:,.2f}
- الخصوم: {data['liabilities']:,.2f}
- حقوق الملكية: {data['equity']:,.2f}
قدم تحليلاً شاملاً بالعربية مع نسب مالية رئيسية وتوصيات قابلة للتنفيذ."""
            with st.spinner("📊 التحليل..."):
                analysis = query_groq(prompt, "حلل هذه البيانات")
            st.markdown(f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};">
                <div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{analysis}</div>
            </div>
            """, unsafe_allow_html=True)

    # ---------- 3. توقع المخزون ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>المنتجات المتوقع نفادها</h3>", unsafe_allow_html=True)
        low, all_prods = get_inventory_data()
        if st.button("📦 توقع الطلب", key="predict_inv"):
            if all_prods:
                df = pd.DataFrame(all_prods)
                prompt = f"""أنت خبير مخزون. حلل بيانات المنتجات التالية وتوقع أيها سينفد قريباً:
{df.to_string()}
اذكر المنتجات المهددة بالنفاد، والكميات المقترح طلبها، وأي ملاحظات. أجب بالعربية."""
                with st.spinner("📦 التحليل..."):
                    prediction = query_groq(prompt, "توقع الطلب")
                st.markdown(f"""
                <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};">
                    <div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{prediction}</div>
                </div>
                """, unsafe_allow_html=True)
        if low:
            st.warning("⚠️ منتجات تحت الحد الأدنى حالياً:")
            st.dataframe(pd.DataFrame(low))

    # ---------- 4. شات الموظفين ----------
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_PURPLE};'>اسأل عن راتبك أو إجازاتك</h3>", unsafe_allow_html=True)
        emp_name = st.text_input("اسمك:", placeholder="أدخل اسمك للبحث", key="emp_name")
        emp_q = st.text_input("سؤالك:", placeholder="مثال: كم راتبي؟", key="emp_q")
        if st.button("💬 اسأل", key="ask_emp") and emp_name and emp_q:
            emp, sal = get_employee_info(emp_name)
            if emp:
                info = f"موظف: {emp['name']}, المنصب: {emp['position']}"
                if sal:
                    info += f", الراتب الأساسي: {sal['basic_salary']}, بدل السكن: {sal['housing_allowance']}, بدل النقل: {sal['transport_allowance']}, الخصومات: {sal['deductions']}"
                prompt = f"أنت مساعد موارد بشرية. بيانات الموظف: {info}. أجب عن السؤال التالي بالعربية:"
                with st.spinner("💬 البحث..."):
                    ans = query_groq(prompt, emp_q)
                st.markdown(f"""
                <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};">
                    <p style="color:{TEXT_PRIMARY}; font-size:1.1rem; margin:0;">{ans}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error("❌ لم يتم العثور على الموظف.")

    # ---------- 5. قيود تلقائية (دعم القيود المركبة + تسجيل) ----------
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>إنشاء قيد محاسبي مركب بلغة طبيعية</h3>", unsafe_allow_html=True)
        text = st.text_area("اكتب العملية:", placeholder="مثال: اشتريت بضاعة بـ 5000 ومصاريف شحن بـ 200، دفعت 3000 نقداً والباقي على الحساب", key="entry_text")
        
        if "generated_entry" not in st.session_state:
            st.session_state.generated_entry = None

        col1, col2 = st.columns([1, 1])
        with col1:
            generate_btn = st.button("📝 إنشاء القيد المركب", key="create_entry")
        with col2:
            if st.session_state.generated_entry is not None:
                if st.button("💾 تسجيل القيد في النظام", type="primary", key="save_entry"):
                    entry_data = st.session_state.generated_entry
                    if not entry_data["lines"]:
                        st.error("لا توجد أسطر لتسجيلها.")
                    else:
                        conn = get_conn()
                        valid_lines = []
                        errors = []
                        for line in entry_data["lines"]:
                            account_name = line["account"]
                            acc = conn.execute("SELECT code FROM accounts WHERE name = ?", (account_name,)).fetchone()
                            if acc:
                                valid_lines.append((acc["code"], line["debit"], line["credit"]))
                            else:
                                errors.append(f"الحساب '{account_name}' غير موجود في شجرة الحسابات.")
                        conn.close()

                        if errors:
                            for err in errors:
                                st.error(err)
                        else:
                            try:
                                conn = get_conn()
                                desc = f"قيد ذكي: {text[:50]}"
                                cur = conn.execute(
                                    "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
                                    (date.today().strftime("%Y-%m-%d"), desc, "")
                                )
                                entry_id = cur.lastrowid
                                for code, debit, credit in valid_lines:
                                    conn.execute(
                                        "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                                        (entry_id, code, debit, credit)
                                    )
                                conn.commit()
                                conn.close()
                                st.success(f"✅ تم تسجيل القيد رقم {entry_id} بنجاح!")
                                st.session_state.generated_entry = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"فشل التسجيل: {e}")

        if generate_btn and text:
            accounts = get_all_accounts()
            acc_list = "\n".join([f"{a['code']} - {a['name']}" for a in accounts]) if accounts else "لا توجد حسابات مضافة بعد"
            prompt = f"""أنت محاسب خبير. حول العملية التالية إلى قيد محاسبي مركب (قد يحتوي على عدة حسابات مدينة وعدة حسابات دائنة).
الحسابات المتاحة:
{acc_list}

أعد القيد بالصيغة التالية فقط، بحيث كل سطر يمثل جزءاً من القيد، ويكون أول كلمة في السطر "مدين" أو "دائن":
مدين | اسم الحساب | المبلغ
دائن | اسم الحساب | المبلغ

يمكنك تكرار السطور حسب الحاجة. يجب أن يتوازن القيد (مجموع المدين = مجموع الدائن). استخدم أسماء الحسابات كما هي.
العملية: {text}"""
            with st.spinner("📝 جاري إنشاء القيد المركب..."):
                entry_text = query_groq(prompt, text)
            st.code(entry_text)

            lines = [l.strip() for l in entry_text.splitlines() if l.strip()]
            entry_lines = []
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3 and (parts[0].startswith("مدين") or parts[0].startswith("دائن")):
                    side = "debit" if parts[0].startswith("مدين") else "credit"
                    account = parts[1]
                    try:
                        amount = float(parts[2].replace(",", ""))
                    except ValueError:
                        continue
                    entry_lines.append({
                        "account": account,
                        "debit": amount if side == "debit" else 0.0,
                        "credit": amount if side == "credit" else 0.0
                    })
            if entry_lines:
                st.session_state.generated_entry = {"lines": entry_lines}
                st.rerun()

        if st.session_state.generated_entry is not None:
            lines = st.session_state.generated_entry["lines"]
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; margin-top:1rem;'>القيد المقترح</h4>", unsafe_allow_html=True)
            df = pd.DataFrame(lines)
            total_debit = df["debit"].sum()
            total_credit = df["credit"].sum()
            summary = pd.DataFrame([{"account": "المجموع", "debit": total_debit, "credit": total_credit}])
            df_display = pd.concat([df, summary], ignore_index=True)
            df_display = df_display.rename(columns={"account": "الحساب", "debit": "مدين", "credit": "دائن"})
            st.dataframe(
                df_display.style.format({"مدين": "{:,.2f}", "دائن": "{:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )

    # ---------- 6. كشف الاحتيال ----------
    with tab6:
        st.markdown(f"<h3 style='color:#EC4899;'>فحص القيود المشبوهة</h3>", unsafe_allow_html=True)
        if st.button("🕵️ افحص القيود", key="audit"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق حسابات. افحص القيود التالية وابحث عن أي شذوذ أو علامات احتيال:
{df.to_string()}
اذكر القيود المشبوهة (إن وجدت) مع ذكر السبب. أجب بالعربية."""
                with st.spinner("🔍 الفحص..."):
                    audit = query_groq(prompt, "افحص هذه القيود")
                st.markdown(f"""
                <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};">
                    <div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{audit}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ لا توجد قيود لفحصها.")

    # ---------- 7. 🔮 تنبؤات مستقبلية (جديد) ----------
    with tab7:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>🔮 تنبؤات مستقبلية شاملة</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:{TEXT_SECONDARY};'>تحليل البيانات الحالية وتوقع المبيعات والتدفق النقدي والمخزون والأرباح للفترة القادمة</p>", unsafe_allow_html=True)
        
        forecast_period = st.selectbox("فترة التنبؤ", ["الشهر القادم", "الـ 3 أشهر القادمة", "الـ 6 أشهر القادمة", "السنة القادمة"], key="forecast_period")
        
        if st.button("🔮 ابدأ التنبؤ", key="start_forecast", type="primary"):
            data = get_comprehensive_data()
            
            # تحويل البيانات إلى نص
            data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            
            prompt = f"""أنت خبير تحليل مالي وتخطيط أعمال. لديك جميع بيانات النظام التالية:
{data_str}

المطلوب: تقديم تنبؤات شاملة للفترة: {forecast_period}.

قم بتقديم التحليل التالي بالعربية، مع أرقام تقديرية مبنية على البيانات الحالية والاتجاهات:

1. 📈 **توقع المبيعات**: توقع إجمالي المبيعات للفترة القادمة بناءً على اتجاهات المبيعات السابقة.

2. 💰 **توقع التدفق النقدي**: توقع النقدية المتدفقة الداخلة والخارجة، وصافي التدفق النقدي.

3. 📦 **توقع نفاد المخزون**: أي المنتجات ستنفد خلال هذه الفترة؟ وما هي الكميات المقترح شراؤها؟

4. 💎 **توقع الأرباح**: توقع صافي الدخل للفترة القادمة بناءً على تقديرات الإيرادات والمصروفات.

5. ⚠️ **المخاطر والتحديات**: ما هي المخاطر المحتملة التي يجب الانتباه لها؟

قدم إجابتك بشكل منظم وواضح، مع أرقام محددة (حتى لو كانت تقديرية). لا تختلق بيانات غير موجودة، ولكن يمكنك استخدام البيانات الحالية لحساب تقديرات منطقية."""
            
            with st.spinner("🔮 جاري تحليل البيانات وتوليد التنبؤات..."):
                forecast = query_groq(prompt, "قدم تنبؤات شاملة", max_tokens=2500)
            
            st.markdown(f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:2rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};">
                <div style="color:{TEXT_PRIMARY}; font-size:1rem; line-height:1.8;">{forecast}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # ملخص سريع بالأرقام
            st.markdown("---")
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📊 ملخص المؤشرات الحالية</h4>", unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("الإيرادات الحالية", f"{data['revenue']:,.0f}")
            with col2:
                st.metric("صافي الدخل الحالي", f"{data['net_income']:,.0f}")
            with col3:
                st.metric("عدد المنتجات", len(data['products']))
            with col4:
                st.metric("عدد العملاء", len(data['customers']))
