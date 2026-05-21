import streamlit as st
import pandas as pd
import json
from datetime import date, datetime
from services.ai_service import (
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
    get_top_customers,
    get_top_suppliers
)

# ========== ثوابت التصميم ==========
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

AVAILABLE_MODELS = {
    "Llama 3.3 70B (الأسرع)": "llama-3.3-70b-versatile",
    "Mixtral 8x7B (متوازن)": "mixtral-8x7b-32768",
    "Llama 2 70B (دقيق)": "llama2-70b-4096"
}

def show():
    # العنوان الرئيسي
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🤖 المساعد الذكي XD</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">ثمانية خبراء مع تحليلات عميقة وسجل محادثات</p>
    </div>
    """, unsafe_allow_html=True)

    create_ai_tables()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("الرجاء إضافة مفتاح `GROQ_API_KEY` في إعدادات Streamlit Secrets.")
        return

    # إعدادات الشريط الجانبي
    with st.sidebar:
        st.markdown("### ⚙️ إعدادات المساعد")
        selected_model_name = st.selectbox("اختر النموذج", list(AVAILABLE_MODELS.keys()))
        selected_model = AVAILABLE_MODELS[selected_model_name]

        st.markdown("---")
        st.markdown("### 📝 سجل المحادثات")
        sessions = get_chat_sessions()
        if sessions:
            for s in sessions:
                if st.button(f"{s['session_id']} ({s['message_count']} رسالة)", key=s['session_id']):
                    st.session_state.active_session = s['session_id']
        else:
            st.info("لا توجد محادثات سابقة")

    if "active_session" not in st.session_state:
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # تبويبات المساعد
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال",
        "🔮 تنبؤات مستقبلية", "📈 تحليل عميق"
    ])

    # ---------- 1. مساعد محاسبي ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>اسأل عن أي شيء في النظام</h3>", unsafe_allow_html=True)

        history = get_chat_history(st.session_state.active_session, 10)
        for h in reversed(history):
            if h['role'] == 'user':
                st.chat_message("user").write(h['content'])
            else:
                st.chat_message("assistant").write(h['content'])

        question = st.chat_input("اكتب سؤالك هنا...")
        if question:
            st.chat_message("user").write(question)
            save_chat_history(st.session_state.active_session, "user", question, selected_model, "مساعد محاسبي")

            data = get_comprehensive_data()
            data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            prompt = f"""أنت مساعد ذكي خبير في نظام ERP. لديك البيانات المالية والإدارية التالية:
{data_str}

أجب عن السؤال التالي بالعربية بناءً على هذه البيانات. إذا لم توجد إجابة، قل لا توجد معلومات كافية. لا تختلق بيانات."""

            with st.spinner("🧠 التفكير..."):
                answer = query_groq(prompt, question, model=selected_model)

            st.chat_message("assistant").write(answer)
            save_chat_history(st.session_state.active_session, "assistant", answer, selected_model, "مساعد محاسبي")

    # ---------- 2. محلل مالي ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تحليل القوائم المالية وتوصيات</h3>", unsafe_allow_html=True)
        if st.button("📈 حلل القوائم المالية الآن", key="analyze_fin"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()

            prompt = f"""أنت محلل مالي خبير. حلل البيانات التالية وقدم توصيات تفصيلية:
- الإيرادات: {data.get('revenue', 0):,.2f}
- المصروفات: {data.get('expenses', 0):,.2f}
- صافي الدخل: {data.get('net_income', 0):,.2f}
- الأصول: {data.get('assets', 0):,.2f}
- الخصوم: {data.get('liabilities', 0):,.2f}
- حقوق الملكية: {data.get('equity', 0):,.2f}
- النسب المالية: {json.dumps(ratios, ensure_ascii=False)}

قدم تحليلاً شاملاً بالعربية يشمل: تقييم الأداء المالي، تحليل النسب المالية، نقاط القوة والضعف، توصيات قابلة للتنفيذ."""

            with st.spinner("📊 التحليل..."):
                analysis = query_groq(prompt, "حلل", model=selected_model, max_tokens=2000)

            st.markdown(analysis)

    # ---------- 3. توقع المخزون ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>المنتجات المتوقع نفادها</h3>", unsafe_allow_html=True)
        low, all_prods = get_inventory_data()
        if st.button("📦 توقع الطلب", key="predict_inv"):
            if all_prods:
                df = pd.DataFrame(all_prods)
                prompt = f"أنت خبير مخزون. توقع المنتجات التي ستنفد قريباً:\n{df.to_string()}"
                with st.spinner("📦 التحليل..."):
                    prediction = query_groq(prompt, "توقع", model=selected_model)
                st.markdown(prediction)
        if low:
            st.warning("منتجات تحت الحد الأدنى حالياً:")
            st.dataframe(pd.DataFrame(low))

    # ---------- 4. شات الموظفين ----------
    with tab4:
        st.markdown(f"<h3 style='color:{ACCENT_PURPLE};'>اسأل عن راتبك أو إجازاتك</h3>", unsafe_allow_html=True)
        emp_name = st.text_input("اسمك:", key="emp_name")
        emp_q = st.text_input("سؤالك:", placeholder="مثال: كم راتبي؟", key="emp_q")
        if st.button("💬 اسأل", key="ask_emp") and emp_name and emp_q:
            emp, sal = get_employee_info(emp_name)
            if emp:
                info = f"موظف: {emp['name']}, المنصب: {emp['position']}"
                if sal:
                    info += f", الراتب: {sal.get('basic_salary', 0):,.2f}"
                prompt = f"أنت مساعد موارد بشرية. بيانات الموظف: {info}. أجب عن السؤال التالي بالعربية:"
                with st.spinner("💬 البحث..."):
                    ans = query_groq(prompt, emp_q, model=selected_model)
                st.success(ans)
            else:
                st.error("لم يتم العثور على الموظف.")

    # ---------- 5. قيود تلقائية ----------
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>إنشاء قيد محاسبي مركب</h3>", unsafe_allow_html=True)
        text = st.text_area("اكتب العملية:", placeholder="مثال: اشتريت بضاعة بـ 5000 نقداً", key="entry_text")

        if st.button("📝 إنشاء القيد", key="create_entry") and text:
            accounts = get_all_accounts()
            acc_list = "\n".join([f"{a['code']} - {a['name']}" for a in accounts]) if accounts else "لا توجد حسابات"
            prompt = f"""أنت محاسب خبير. حول العملية إلى قيد محاسبي مركب.\nالحسابات المتاحة:\n{acc_list}\nأعد القيد بالصيغة:\nمدين | اسم الحساب | المبلغ\nدائن | اسم الحساب | المبلغ\nالعملية: {text}"""
            with st.spinner("📝 جاري إنشاء القيد..."):
                entry_text = query_groq(prompt, text, model=selected_model)
            st.code(entry_text)

    # ---------- 6. كشف الاحتيال ----------
    with tab6:
        st.markdown(f"<h3 style='color:#EC4899;'>فحص القيود المشبوهة</h3>", unsafe_allow_html=True)
        if st.button("🕵️ افحص القيود", key="audit"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"أنت مدقق حسابات. افحص القيود التالية وابحث عن شذوذ:\n{df.to_string()}"
                with st.spinner("🔍 الفحص..."):
                    audit = query_groq(prompt, "افحص", model=selected_model)
                st.markdown(audit)
            else:
                st.info("لا توجد قيود لفحصها.")

    # ---------- 7. تنبؤات مستقبلية ----------
    with tab7:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>🔮 تنبؤات مستقبلية</h3>", unsafe_allow_html=True)
        forecast_period = st.selectbox("فترة التنبؤ", ["الشهر القادم", "الـ 3 أشهر القادمة", "السنة القادمة"], key="forecast_period")

        if st.button("🔮 ابدأ التنبؤ", key="start_forecast", type="primary"):
            data = get_comprehensive_data()
            data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            prompt = f"قدم تنبؤات شاملة للفترة: {forecast_period}.\nبيانات النظام:\n{data_str}"
            with st.spinner("🔮 جاري التحليل..."):
                forecast = query_groq(prompt, "قدم تنبؤات", model=selected_model, max_tokens=2500)
            st.markdown(forecast)

    # ---------- 8. تحليل عميق ----------
    with tab8:
        st.markdown(f"<h3 style='color:{ACCENT_PINK};'>📈 تحليل مالي عميق</h3>", unsafe_allow_html=True)

        if st.button("📊 عرض النسب المالية", use_container_width=True):
            ratios = get_financial_ratios()
            for key, value in ratios.items():
                st.metric(key, value)

        if st.button("📈 تحليل الاتجاهات", use_container_width=True):
            trends = get_trend_analysis()
            if trends:
                st.dataframe(pd.DataFrame(trends), use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد بيانات اتجاهات")
