import streamlit as st
import sqlite3
import pandas as pd
from groq import Groq

DB_PATH = "erp.db"

# ========== دوال مساعدة ==========
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

# ========== واجهة المساعد الذكي ==========
def show():
    st.title("🤖 المساعد الذكي XD ERP")

    if "GROQ_API_KEY" not in st.secrets:
        st.error("❌ الرجاء إضافة `GROQ_API_KEY` في إعدادات Streamlit Cloud (Secrets).")
        return

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال"
    ])

    # ---------- 1. مساعد محاسبي ----------
    with tab1:
        st.subheader("اسأل عن أي شيء في حساباتك")
        question = st.text_input("سؤالك:", placeholder="مثال: كم صافي الربح هذا الشهر؟")
        if st.button("اسأل", key="ask_finance"):
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
                with st.spinner("جاري التفكير..."):
                    answer = query_groq(prompt, question)
                st.success(answer)

    # ---------- 2. محلل مالي ----------
    with tab2:
        st.subheader("تحليل القوائم المالية وتوصيات")
        if st.button("حلل القوائم المالية الآن", key="analyze_fin"):
            data = get_financial_summary()
            prompt = f"""أنت محلل مالي خبير. حلل البيانات التالية وقدم توصيات:
- الإيرادات: {data['revenue']:,.2f}
- المصروفات: {data['expenses']:,.2f}
- صافي الدخل: {data['net_income']:,.2f}
- الأصول: {data['assets']:,.2f}
- الخصوم: {data['liabilities']:,.2f}
- حقوق الملكية: {data['equity']:,.2f}
قدم تحليلاً شاملاً بالعربية مع نسب مالية رئيسية وتوصيات قابلة للتنفيذ."""
            with st.spinner("جاري التحليل..."):
                analysis = query_groq(prompt, "حلل هذه البيانات")
            st.markdown(analysis)

    # ---------- 3. توقع المخزون ----------
    with tab3:
        st.subheader("المنتجات المتوقع نفادها")
        low, all_prods = get_inventory_data()
        if st.button("توقع الطلب", key="predict_inv"):
            if all_prods:
                df = pd.DataFrame(all_prods)
                prompt = f"""أنت خبير مخزون. حلل بيانات المنتجات التالية وتوقع أيها سينفد قريباً:
{df.to_string()}
اذكر المنتجات المهددة بالنفاد، والكميات المقترح طلبها، وأي ملاحظات. أجب بالعربية."""
                with st.spinner("جاري التحليل..."):
                    prediction = query_groq(prompt, "توقع الطلب")
                st.markdown(prediction)
        if low:
            st.warning("منتجات تحت الحد الأدنى حالياً:")
            st.dataframe(pd.DataFrame(low))

    # ---------- 4. شات الموظفين ----------
    with tab4:
        st.subheader("اسأل عن راتبك أو إجازاتك")
        emp_name = st.text_input("اسمك:", placeholder="أدخل اسمك للبحث")
        emp_q = st.text_input("سؤالك:", placeholder="مثال: كم راتبي؟")
        if st.button("اسأل", key="ask_emp") and emp_name and emp_q:
            emp, sal = get_employee_info(emp_name)
            if emp:
                info = f"موظف: {emp['name']}, المنصب: {emp['position']}"
                if sal:
                    info += f", الراتب الأساسي: {sal['basic_salary']}, بدل السكن: {sal['housing_allowance']}, بدل النقل: {sal['transport_allowance']}, الخصومات: {sal['deductions']}"
                prompt = f"أنت مساعد موارد بشرية. بيانات الموظف: {info}. أجب عن السؤال التالي بالعربية:"
                with st.spinner("جاري البحث..."):
                    ans = query_groq(prompt, emp_q)
                st.success(ans)
            else:
                st.error("لم يتم العثور على الموظف.")

    # ---------- 5. قيود تلقائية ----------
    with tab5:
        st.subheader("إنشاء قيد محاسبي بلغة طبيعية")
        text = st.text_area("اكتب العملية:", placeholder="مثال: اشتريت بضاعة بمبلغ 5000 ريال نقداً")
        if st.button("إنشاء القيد", key="create_entry"):
            if text:
                accounts = get_all_accounts()
                acc_list = "\n".join([f"{a['code']} - {a['name']}" for a in accounts])
                prompt = f"""أنت محاسب خبير. حول العملية التالية إلى قيد محاسبي.
الحسابات المتاحة:
{acc_list}
أعد القيد بالصيغة التالية فقط (بدون أي نص آخر):
الحساب المدين | المبلغ | الحساب الدائن | المبلغ
مثال:
المخزون | 5000 | الصندوق | 5000
العملية: {text}"""
                with st.spinner("جاري إنشاء القيد..."):
                    entry = query_groq(prompt, text)
                st.code(entry)

    # ---------- 6. كشف الاحتيال ----------
    with tab6:
        st.subheader("فحص القيود المشبوهة")
        if st.button("افحص القيود", key="audit"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق حسابات. افحص القيود التالية وابحث عن أي شذوذ أو علامات احتيال:
{df.to_string()}
اذكر القيود المشبوهة (إن وجدت) مع ذكر السبب. أجب بالعربية."""
                with st.spinner("جاري الفحص..."):
                    audit = query_groq(prompt, "افحص هذه القيود")
                st.markdown(audit)
            else:
                st.info("لا توجد قيود لفحصها.")
