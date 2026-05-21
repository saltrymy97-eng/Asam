# ui/ai_ui.py – واجهة المساعد الذكي المطورة (تحليلات عميقة)
import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from services.ai_service import (
    create_ai_tables, query_groq, save_chat_history, get_chat_history,
    get_chat_sessions, get_comprehensive_data, get_inventory_data,
    get_employee_info, get_recent_entries, get_all_accounts, get_conn,
    get_financial_ratios, get_trend_analysis, get_top_customers, get_top_suppliers
)

# ========== ألوان التصميم ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"

AVAILABLE_MODELS = {
    "Llama 3.3 70B (الأسرع)": "llama-3.3-70b-versatile",
    "Mixtral 8x7B (متوازن)": "mixtral-8x7b-32768",
}

def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">ثمانية خبراء مع تحليلات عميقة وتوصيات ذكية</p>
    </div>""", unsafe_allow_html=True)

def h3(title, color=BL):
    st.markdown(f"""<h3 style="color:{color};text-align:right;">{title}</h3>""", unsafe_allow_html=True)

def glass(content):
    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{T};font-size:1.1rem;">{content}</div>""", unsafe_allow_html=True)

def show():
    h1("🤖 المساعد الذكي XD")
    create_ai_tables()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("الرجاء إضافة مفتاح Groq API")
        return

    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")
        model_name = st.selectbox("اختر النموذج", list(AVAILABLE_MODELS.keys()))
        model = AVAILABLE_MODELS[model_name]

    if "active_session" not in st.session_state:
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs([
        "🧠 مساعد", "📊 محلل", "📦 مخزون", "💬 موظفين", "📝 قيود", "🔍 احتيال", "🔮 تنبؤات", "📈 تحليل"
    ])

    # 1. مساعد محاسبي (محادثة عميقة)
    with t1:
        h3("اسأل عن أي شيء في نظامك", BL)
        q = st.chat_input("اكتب سؤالك هنا...")
        if q:
            st.chat_message("user").write(q)
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"""أنت خبير مالي ومحلل أعمال في نظام ERP. لديك البيانات التالية عن الشركة:
{d}

أجب عن السؤال التالي بالعربية بشكل مفصل وعميق. قدم أرقاماً محددة، وحلل الاتجاهات، وقدم توصيات قابلة للتنفيذ. إذا كانت البيانات غير كافية، اشرح ما هي البيانات الإضافية المطلوبة. لا تختلق معلومات غير موجودة."""
            with st.spinner("🧠 تحليل عميق..."):
                ans = query_groq(prompt, q, model=model, max_tokens=2500)
            st.chat_message("assistant").write(ans)
            save_chat_history(st.session_state.active_session, "user", q, model, "مساعد")
            save_chat_history(st.session_state.active_session, "assistant", ans, model, "مساعد")

    # 2. محلل مالي (تحليل شامل)
    with t2:
        h3("تحليل مالي شامل وتوصيات", GR)
        if st.button("📈 تحليل شامل"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            trends = get_trend_analysis()
            prompt = f"""أنت محلل مالي أول. قم بتحليل البيانات المالية التالية وقدم تقريراً شاملاً:
- الإيرادات: {data.get('revenue',0):,.2f}
- المصروفات: {data.get('expenses',0):,.2f}
- صافي الدخل: {data.get('net_income',0):,.2f}
- الأصول: {data.get('assets',0):,.2f}
- الخصوم: {data.get('liabilities',0):,.2f}
- حقوق الملكية: {data.get('equity',0):,.2f}
- النسب المالية: {json.dumps(ratios, ensure_ascii=False)}
- اتجاهات المبيعات: {json.dumps(trends, ensure_ascii=False, default=str)}

قدم تقريراً بالعربية يشمل:
1. تقييم الأداء المالي العام
2. تحليل النسب المالية ومقارنتها بالمعايير
3. تحليل الاتجاهات الشهرية
4. تحديد نقاط القوة والضعف
5. توصيات استراتيجية محددة"""
            with st.spinner("📊 تحليل شامل..."):
                ans = query_groq(prompt, "قدم تحليلاً شاملاً", model=model, max_tokens=3000)
            glass(ans)

    # 3. توقع المخزون (تحليل عميق)
    with t3:
        h3("تحليل المخزون وتوقع النفاد", OR)
        low, allp = get_inventory_data()
        if st.button("📦 تحليل المخزون"):
            if allp:
                df = pd.DataFrame(allp)
                prompt = f"""أنت خبير إدارة مخزون. حلل البيانات التالية:
{df.to_string()}

قدم تحليلاً بالعربية يشمل:
1. المنتجات المعرضة لخطر النفاد
2. الكميات المقترح طلبها لكل منتج
3. تقدير التكلفة الإجمالية للطلبيات المقترحة
4. نصائح لتحسين إدارة المخزون"""
                with st.spinner("📦 تحليل المخزون..."):
                    ans = query_groq(prompt, "حلل المخزون", model=model)
                glass(ans)
        if low:
            st.warning("⚠️ منتجات تحت الحد الأدنى:")
            st.dataframe(pd.DataFrame(low))

    # 4. شات الموظفين
    with t4:
        h3("استفسارات الموظفين", PR)
        nm = st.text_input("اسمك:", key="ename")
        eq = st.text_input("سؤالك:", key="eq")
        if st.button("💬 اسأل") and nm and eq:
            emp, sal = get_employee_info(nm)
            if emp:
                info = f"{emp['name']} - {emp['position']}"
                if sal: info += f" | راتب: {sal.get('basic_salary',0):,.2f}"
                prompt = f"أنت مسؤول موارد بشرية. بيانات الموظف: {info}. أجب بدقة عن: {eq}"
                with st.spinner("💬..."):
                    ans = query_groq(prompt, eq, model=model)
                glass(ans)
            else:
                st.error("غير موجود")

    # 5. قيود تلقائية (ذكية)
    with t5:
        h3("توليد قيود محاسبية ذكية", RD)
        txt = st.text_area("اكتب العملية:", key="etxt")
        if st.button("📝 توليد القيد") and txt:
            accs = get_all_accounts()
            alist = "\n".join([f"{a['code']} - {a['name']}" for a in accs]) if accs else "لا حسابات"
            prompt = f"""أنت محاسب محترف. حول العملية التالية إلى قيد محاسبي.
الحسابات المتاحة:
{alist}

أعد القيد بالصيغة التالية (كل سطر يمثل قيداً):
مدين | اسم الحساب | المبلغ
دائن | اسم الحساب | المبلغ

تأكد من توازن القيد (مجموع المدين = مجموع الدائن).
العملية: {txt}"""
            with st.spinner("📝..."):
                ans = query_groq(prompt, txt, model=model)
            st.code(ans)

    # 6. كشف احتيال (تدقيق عميق)
    with t6:
        h3("تدقيق وكشف الاحتيال", RD)
        if st.button("🕵️ تدقيق شامل"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق حسابات جنائي. افحص القيود التالية بحثاً عن احتيال أو أخطاء:
{df.to_string()}

قدم تقريراً بالعربية يشمل:
1. القيود المشبوهة (مع ذكر رقم القيد والسبب)
2. أنماط غير طبيعية
3. توصيات للتحقيق الإضافي"""
                with st.spinner("🔍 تدقيق..."):
                    ans = query_groq(prompt, "افحص", model=model)
                glass(ans)
            else:
                st.info("لا قيود")

    # 7. تنبؤات (تخطيط استراتيجي)
    with t7:
        h3("🔮 تنبؤات وتخطيط مالي", CY)
        period = st.selectbox("فترة التخطيط", ["الشهر القادم", "الربع القادم", "السنة القادمة"], key="fp")
        if st.button("🔮 ابدأ التخطيط"):
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"""أنت مخطط مالي استراتيجي. قدم توقعات للفترة: {period}.
البيانات الحالية:
{d}

قدم خطة بالعربية تشمل:
1. توقعات المبيعات والمصروفات
2. توقعات التدفق النقدي
3. احتياجات المخزون المتوقعة
4. المخاطر والفرص
5. توصيات استراتيجية"""
            with st.spinner("🔮 تخطيط..."):
                ans = query_groq(prompt, "خطط", model=model, max_tokens=3000)
            glass(ans)

    # 8. تحليل عميق (نسب واتجاهات)
    with t8:
        h3("📈 تحليلات متقدمة", PR)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📊 النسب المالية"):
                for k, v in get_financial_ratios().items():
                    st.metric(k, v)
        with c2:
            if st.button("📈 اتجاهات المبيعات"):
                tr = get_trend_analysis()
                if tr:
                    st.dataframe(pd.DataFrame(tr))
                else:
                    st.info("لا بيانات")
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏆 أفضل العملاء"):
                tc = get_top_customers()
                if tc:
                    st.dataframe(pd.DataFrame(tc))
                else:
                    st.info("لا بيانات")
        with c2:
            if st.button("🏢 أفضل الموردين"):
                ts = get_top_suppliers()
                if ts:
                    st.dataframe(pd.DataFrame(ts))
                else:
                    st.info("لا بيانات")
