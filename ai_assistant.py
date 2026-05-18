# ai_assistant.py – مساعد ذكي بواجهة زجاجية فخمة وألوان زاهية
# يدعم القيود المركبة وتسجيل القيد مباشرة في قاعدة البيانات
import streamlit as st
import sqlite3
import pandas as pd
from groq import Groq
from datetime import date

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

def query_groq(system_prompt, user_query):
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    return response.choices[0].message.content

def get_financial_summary():
    conn = get_conn()
    revenue = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines jl WHERE jl.account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(jl.debit)-SUM(jl.credit),0) FROM journal_lines jl WHERE jl.account_name LIKE '5%'").fetchone()[0]
    assets = conn.execute("SELECT COALESCE(SUM(jl.debit)-SUM(jl.credit),0) FROM journal_lines jl WHERE jl.account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines jl WHERE jl.account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(jl.credit)-SUM(jl.debit),0) FROM journal_lines jl WHERE jl.account_name LIKE '3%'").fetchone()[0]
    products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    conn.close()
    return {
        "revenue": revenue, "expenses": expenses, "net_income": revenue - expenses,
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "products_count": products, "customers_count": customers
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
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">ستة خبراء في مكان واحد لخدمة أعمالك</p>
    </div>
    """, unsafe_allow_html=True)

    create_accounts_table()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("❌ الرجاء إضافة `GROQ_API_KEY` في إعدادات Streamlit Cloud (Secrets).")
        return

    # ---------- تبويبات زجاجية ----------
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال"
    ])

    # ---------- 1. مساعد محاسبي ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>اسأل عن أي شيء في حساباتك</h3>", unsafe_allow_html=True)
        question = st.text_input("سؤالك:", placeholder="مثال: كم صافي الربح هذا الشهر؟", key="q1")
        if st.button("🔮 اسأل الخبير", key="ask_finance"):
            if question:
                data = get_financial_summary()
                prompt = f"""أنت مساعد محاسبي خبير. استخدم البيانات التالية للإجابة:
الإيرادات: {data['revenue']:,.2f}
المصروفات: {data['expenses']:,.2f}
صافي الدخل: {data['net_income']:,.2f}
الأصول: {data['assets']:,.2f}
الخصوم: {data['liabilities']:,.2f}
حقوق الملكية: {data['equity']:,.2f}
أجب بالعربية على السؤال التالي:"""
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
            data = get_financial_summary()
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

    # ---------- 5. قيود تلقائية (دعم القيود المركبة + زر تسجيل) ----------
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>إنشاء قيد محاسبي مركب بلغة طبيعية</h3>", unsafe_allow_html=True)
        text = st.text_area("اكتب العملية:", placeholder="مثال: اشتريت بضاعة بـ 5000 ومصاريف شحن بـ 200، دفعت 3000 نقداً والباقي على الحساب", key="entry_text")
        
        # حالة مؤقتة لتخزين القيد الذي تم إنشاؤه
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
                        # التحقق من وجود الحسابات
                        conn = get_conn()
                        valid_lines = []
                        errors = []
                        for line in entry_data["lines"]:
                            account_name = line["account"]
                            # البحث عن كود الحساب
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

            # تحليل النص المسترجع إلى قائمة أسطر
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

        # عرض القيد المحفوظ بشكل جميل
        if st.session_state.generated_entry is not None:
            lines = st.session_state.generated_entry["lines"]
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; margin-top:1rem;'>القيد المقترح</h4>", unsafe_allow_html=True)
            html = f"""
            <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin:1rem 0; box-shadow:{GLASS_SHADOW}; color:{TEXT_PRIMARY};">
            <table style="width:100%; border-collapse:collapse;">
            <tr style="border-bottom:1px solid {GLASS_BORDER};">
                <th style="text-align:right; padding:8px;">الحساب</th>
                <th style="text-align:right; padding:8px;">مدين</th>
                <th style="text-align:right; padding:8px;">دائن</th>
            </tr>
            """
            total_debit = total_credit = 0.0
            for line in lines:
                debit = line['debit']
                credit = line['credit']
                total_debit += debit
                total_credit += credit
                html += f"""
                <tr>
                    <td style="padding:8px; text-align:right;">{line['account']}</td>
                    <td style="padding:8px; text-align:right;">{debit:,.2f}</td>
                    <td style="padding:8px; text-align:right;">{credit:,.2f}</td>
                </tr>
                """
            html += f"""
            <tr style="border-top:1px solid {GLASS_BORDER}; font-weight:bold;">
                <td style="padding:8px; text-align:right;">المجموع</td>
                <td style="padding:8px; text-align:right;">{total_debit:,.2f}</td>
                <td style="padding:8px; text-align:right;">{total_credit:,.2f}</td>
            </tr>
            </table>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

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
