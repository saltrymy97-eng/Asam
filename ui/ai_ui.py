# ui/ai_ui.py – واجهة المساعد الذكي المستقرة والمضمونة
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

# ألوان التصميم
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
    "Llama 3.3 70B": "llama-3.3-70b-versatile",
    "Mixtral 8x7B": "mixtral-8x7b-32768"
}

def show():
    st.title("🤖 المساعد الذكي XD")
    create_ai_tables()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("الرجاء إضافة مفتاح Groq API في إعدادات Streamlit Secrets.")
        return

    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")
        selected_model_name = st.selectbox("اختر النموذج", list(AVAILABLE_MODELS.keys()))
        selected_model = AVAILABLE_MODELS[selected_model_name]

    if "active_session" not in st.session_state:
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tabs = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال",
        "🔮 تنبؤات مستقبلية", "📈 تحليل عميق"
    ])

    # 1. مساعد محاسبي
    with tabs[0]:
        st.subheader("اسأل عن أي شيء في النظام")
        q = st.chat_input("اكتب سؤالك هنا...")
        if q:
            st.chat_message("user").write(q)
            data = get_comprehensive_data()
            data_str = json.dumps(data, ensure_ascii=False, default=str)[:3000]
            prompt = f"بيانات النظام:\n{data_str}\n\nأجب عن السؤال بالعربية: {q}"
            with st.spinner("🧠 التفكير..."):
                answer = query_groq(prompt, q, model=selected_model)
            st.chat_message("assistant").write(answer)

    # 2. محلل مالي
    with tabs[1]:
        st.subheader("تحليل القوائم المالية وتوصيات")
        if st.button("📈 حلل القوائم المالية"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            prompt = f"""حلل البيانات المالية التالية:
الإيرادات: {data.get('revenue', 0):,.2f}
المصروفات: {data.get('expenses', 0):,.2f}
صافي الدخل: {data.get('net_income', 0):,.2f}
الأصول: {data.get('assets', 0):,.2f}
الخصوم: {data.get('liabilities', 0):,.2f}
حقوق الملكية: {data.get('equity', 0):,.2f}
النسب: {json.dumps(ratios, ensure_ascii=False)}
قدم تحليلاً وتوصيات بالعربية."""
            with st.spinner("📊 التحليل..."):
                analysis = query_groq(prompt, "حلل", model=selected_model, max_tokens=2000)
            st.markdown(analysis)

    # 3. توقع المخزون
    with tabs[2]:
        st.subheader("المنتجات المتوقع نفادها")
        low, all_prods = get_inventory_data()
        if st.button("📦 توقع الطلب"):
            if all_prods:
                df = pd.DataFrame(all_prods)
                prompt = f"توقع المنتجات التي ستنفد قريباً:\n{df.to_string()}"
                with st.spinner("📦 التحليل..."):
                    prediction = query_groq(prompt, "توقع", model=selected_model)
                st.markdown(prediction)
        if low:
            st.warning("منتجات تحت الحد الأدنى حالياً:")
            st.dataframe(pd.DataFrame(low))

    # 4. شات الموظفين
    with tabs[3]:
        st.subheader("اسأل عن راتبك أو إجازاتك")
        emp_name = st.text_input("اسمك:", key="emp_name")
        emp_q = st.text_input("سؤالك:", placeholder="مثال: كم راتبي؟", key="emp_q")
        if st.button("💬 اسأل", key="ask_emp") and emp_name and emp_q:
            emp, sal = get_employee_info(emp_name)
            if emp:
                info = f"موظف: {emp['name']}, المنصب: {emp['position']}"
                if sal:
                    info += f", الراتب: {sal.get('basic_salary', 0):,.2f}"
                prompt = f"أنت مساعد موارد بشرية. بيانات الموظف: {info}. أجب بالعربية:"
                with st.spinner("💬 البحث..."):
                    ans = query_groq(prompt, emp_q, model=selected_model)
                st.success(ans)
            else:
                st.error("لم يتم العثور على الموظف.")

    # 5. قيود تلقائية
    with tabs[4]:
        st.subheader("إنشاء قيد محاسبي مركب")
        text = st.text_area("اكتب العملية:", placeholder="مثال: اشتريت بضاعة بـ 5000 نقداً", key="entry_text")
        if st.button("📝 إنشاء القيد", key="create_entry") and text:
            accounts = get_all_accounts()
            acc_list = "\n".join([f"{a['code']} - {a['name']}" for a in accounts]) if accounts else "لا توجد حسابات"
            prompt = f"""أنت محاسب خبير. حول العملية إلى قيد محاسبي مركب.
الحسابات المتاحة:
{acc_list}
أعد القيد بالصيغة:
مدين | اسم الحساب | المبلغ
دائن | اسم الحساب | المبلغ
العملية: {text}"""
            with st.spinner("📝 جاري إنشاء القيد..."):
                entry_text = query_groq(prompt, text, model=selected_model)
            st.code(entry_text)

    # 6. كشف الاحتيال
    with tabs[5]:
        st.subheader("فحص القيود المشبوهة")
        if st.button("🕵️ افحص القيود", key="audit"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"افحص القيود التالية وابحث عن شذوذ:\n{df.to_string()}"
                with st.spinner("🔍 الفحص..."):
                    audit = query_groq(prompt, "افحص", model=selected_model)
                st.markdown(audit)
            else:
                st.info("لا توجد قيود لفحصها.")

    # 7. تنبؤات مستقبلية
    with tabs[6]:
        st.subheader("🔮 تنبؤات مستقبلية")
        forecast_period = st.selectbox("فترة التنبؤ", ["الشهر القادم", "الـ 3 أشهر القادمة", "السنة القادمة"], key="forecast_period")
        if st.button("🔮 ابدأ التنبؤ", key="start_forecast"):
            data = get_comprehensive_data()
            data_str = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"قدم تنبؤات شاملة للفترة: {forecast_period}.\nبيانات النظام:\n{data_str}"
            with st.spinner("🔮 جاري التحليل..."):
                forecast = query_groq(prompt, "قدم تنبؤات", model=selected_model, max_tokens=2500)
            st.markdown(forecast)

    # 8. تحليل عميق
    with tabs[7]:
        st.subheader("📈 تحليل مالي عميق")
        if st.button("📊 عرض النسب المالية"):
            ratios = get_financial_ratios()
            for key, value in ratios.items():
                st.metric(key, value)
        if st.button("📈 تحليل الاتجاهات"):
            trends = get_trend_analysis()
            if trends:
                st.dataframe(pd.DataFrame(trends), use_container_width=True, hide_index=True)
            else:
                st.info("لا توجد بيانات اتجاهات")
