# ui/ai_ui.py – واجهة المساعد الذكي المطورة مع التسجيل الصوتي (st.audio_input)
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime
from services.ai_service import (
    create_ai_tables, query_groq, save_chat_history, get_chat_history,
    get_chat_sessions, get_comprehensive_data, get_inventory_data,
    get_employee_info, get_recent_entries, get_all_accounts, get_conn,
    get_financial_ratios, get_trend_analysis, get_top_customers, get_top_suppliers,
    analyze_cost_center_performance, compare_cost_centers,
    predict_cost_center_expenses, get_cost_center_budget_analysis,
    get_cost_centers_summary_for_ai,
    generate_entry_safe
)
from services import cost_center_service as ccs
from groq import Groq

# ========== ألوان التصميم ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"
GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"

AVAILABLE_MODELS = {
    "Llama 3.3 70B": "llama-3.3-70b-versatile",
    "Llama 3.1 8B (أسرع)": "llama-3.1-8b-instant",
}

# ========== 🎤 معالجة الصوت ==========
def audio_to_text(audio_file):
    """تحويل ملف صوتي إلى نص باستخدام Groq Whisper"""
    if audio_file is None:
        return ""
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        # حفظ الملف المؤقت
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_file.getbuffer())
        with open("temp_audio.wav", "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=("temp_audio.wav", f.read()),
                language="ar"
            )
        os.remove("temp_audio.wav")
        return transcription.text
    except Exception as e:
        return f"❌ خطأ في التعرف على الصوت: {str(e)}"

def audio_input_widget(key="audio"):
    """عنصر إدخال صوتي أنيق مع استخراج النص"""
    audio_value = st.audio_input("🎤 تحدث الآن", key=key, label_visibility="collapsed")
    if audio_value:
        with st.spinner("🎙️ جاري تحويل الصوت إلى نص..."):
            text = audio_to_text(audio_value)
            if text and not text.startswith("❌"):
                st.success(f"✅ النص المستخرج: {text}")
                return text
            else:
                st.error(text)
    return ""

def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">تسعة خبراء مع تحليلات عميقة وتوصيات ذكية</p>
    </div>""", unsafe_allow_html=True)

def h3(title, color=BL):
    st.markdown(f"""<h3 style="color:{color};text-align:right;">{title}</h3>""", unsafe_allow_html=True)

def glass(content):
    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{T};font-size:1.1rem;">{content}</div>""", unsafe_allow_html=True)

def show():
    h1("🤖 المساعد الذكي AI")
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

    t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs([
        "🧠 مساعد", "📊 محلل", "📦 مخزون", "💬 موظفين", "📝 قيود", "🔍 احتيال", "🔮 تنبؤات", "📈 تحليل",
        "🎯 مراكز تكلفة"
    ])

    # ====== تبويب 1: المساعد (تسجيل صوتي) ======
    with t1:
        h3("اسأل عن أي شيء في نظامك", BL)
        col1, col2 = st.columns([1, 5])
        with col1:
            voice_text = audio_input_widget("assistant_audio")
        with col2:
            manual_text = st.text_area("أو اكتب سؤالك هنا", height=68, key="assistant_text", label_visibility="collapsed", placeholder="اكتب سؤالك هنا...")
        
        submit = st.button("إرسال", key="assistant_submit", type="primary")
        if submit:
            q = voice_text or manual_text
            if q:
                st.chat_message("user").write(q)
                data = get_comprehensive_data()
                d = json.dumps(data, ensure_ascii=False, default=str)
                prompt = f"""أنت خبير مالي ومحلل أعمال في نظام ERP. لديك البيانات التالية عن الشركة:
{d}

أجب عن السؤال التالي بالعربية بشكل مفصل وعميق. قدم أرقاماً محددة، وحلل الاتجاهات، وقدم توصيات قابلة للتنفيذ. إذا كانت البيانات غير كافية، اشرح ما هي البيانات الإضافية المطلوبة. لا تختلق معلومات غير موجودة."""
                with st.spinner("🧠 تحليل عميق..."):
                    ans = query_groq(prompt, q, model=model, max_tokens=1500)
                st.chat_message("assistant").write(ans)
                save_chat_history(st.session_state.active_session, "user", q, model, "مساعد")
                save_chat_history(st.session_state.active_session, "assistant", ans, model, "مساعد")
            else:
                st.warning("الرجاء إدخال سؤال")

    # ====== تبويب 2: المحلل (بدون تسجيل صوتي) ======
    with t2:
        h3("تحليل مالي شامل وتوصيات", GR)
        if st.button("📈 تحليل شامل"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            trends = get_trend_analysis()
            prompt = f"""أنت محلل مالي أول. الأرقام المالية موجودة في السطور التالية. لا تقل "لا توجد بيانات". استخدم هذه الأرقام حصراً لتحليل الأداء:
- الإيرادات: {data.get('revenue',0):,.2f}
- المصروفات: {data.get('expenses',0):,.2f}
- صافي الدخل: {data.get('net_income',0):,.2f}
- الأصول: {data.get('assets',0):,.2f}
- الخصوم: {data.get('liabilities',0):,.2f}
- حقوق الملكية: {data.get('equity',0):,.2f}
- النسب المالية: {json.dumps(ratios, ensure_ascii=False)}
- اتجاهات المبيعات: {json.dumps(trends, ensure_ascii=False, default=str)}

قدم تقريراً بالعربية يشمل:
1. تقييم الأداء المالي العام (مع ذكر الأرقام)
2. تحليل النسب المالية ومقارنتها بالمعايير
3. تحليل الاتجاهات الشهرية
4. تحديد نقاط القوة والضعف
5. توصيات استراتيجية محددة"""
            with st.spinner("📊 تحليل شامل..."):
                ans = query_groq(prompt, "قدم تحليلاً شاملاً", model=model, max_tokens=1500)
            glass(ans)

    # ====== تبويب 3: المخزون (بدون تسجيل صوتي) ======
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
                    ans = query_groq(prompt, "حلل المخزون", model=model, max_tokens=1500)
                glass(ans)
        if low:
            st.warning("⚠️ منتجات تحت الحد الأدنى:")
            st.dataframe(pd.DataFrame(low))

    # ====== تبويب 4: الموظفين (تسجيل صوتي) ======
    with t4:
        h3("استفسارات الموظفين", PR)
        col1, col2 = st.columns([1, 5])
        with col1:
            voice_name = audio_input_widget("employee_name_audio")
        with col2:
            nm = st.text_input("اسمك:", key="ename", value=voice_name)
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

    # ====== تبويب 5: القيود (تسجيل صوتي) ======
    with t5:
        h3("توليد قيود محاسبية ذكية", RD)
        col1, col2 = st.columns([1, 5])
        with col1:
            voice_entry = audio_input_widget("entry_audio")
        with col2:
            txt = st.text_area("اكتب العملية:", key="etxt", value=voice_entry, height=100)
        if st.button("📝 توليد القيد") and txt:
            with st.spinner("📝 جاري توليد قيد متوازن..."):
                entry, display, confidence, confidence_label, confidence_color = generate_entry_safe(txt, model=model)
            
            if entry:
                st.code(display)
                
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.05); border:1px solid {confidence_color}; border-radius:12px; padding:12px 16px; margin-top:12px; display:flex; align-items:center; gap:12px;">
                    <div style="background:{confidence_color}; width:12px; height:12px; border-radius:50%; box-shadow:0 0 10px {confidence_color};"></div>
                    <span style="color:#F8FAFC; font-weight:600;">📊 نسبة الثقة: {confidence}%</span>
                    <span style="background:{confidence_color}20; color:{confidence_color}; padding:4px 12px; border-radius:8px; font-weight:700; font-size:0.85rem;">{confidence_label}</span>
                </div>
                """, unsafe_allow_html=True)
                
                if confidence < 70:
                    st.warning("⚠️ الثقة منخفضة في هذا القيد. يرجى مراجعة القيد يدوياً قبل الاعتماد عليه.")
            else:
                st.error(display)

    # ====== تبويب 6: الاحتيال (بدون تسجيل صوتي) ======
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
                    ans = query_groq(prompt, "افحص", model=model, max_tokens=1500)
                glass(ans)
            else:
                st.info("لا قيود")

    # ====== تبويب 7: التنبؤات (بدون تسجيل صوتي) ======
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
                ans = query_groq(prompt, "خطط", model=model, max_tokens=1500)
            glass(ans)

    # ====== تبويب 8: التحليل الشامل (بدون تسجيل صوتي) ======
    with t8:
        h3("📈 تحليل مالي وتشغيلي متقدم", PR)
        st.caption("تقرير احترافي يولده الذكاء الاصطناعي بناءً على جميع بيانات النظام")
        
        analysis_scope = st.multiselect(
            "اختر جوانب التحليل",
            ["الأداء المالي", "تحليل النسب", "اتجاهات المبيعات", "تحليل العملاء والموردين",
             "تحليل مراكز التكلفة", "المخزون والمشتريات", "الموارد البشرية"],
            default=["الأداء المالي", "تحليل النسب", "اتجاهات المبيعات"]
        )
        
        if st.button("🚀 توليد تقرير تحليلي شامل", use_container_width=True):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            trends = get_trend_analysis()
            top_cust = get_top_customers()
            top_supp = get_top_suppliers()
            cc_data = get_cost_centers_summary_for_ai()
            
            data_parts = []
            if "الأداء المالي" in analysis_scope:
                data_parts.append(f"""الأداء المالي:
- الإيرادات: {data.get('revenue',0):,.2f}
- المصروفات: {data.get('expenses',0):,.2f}
- صافي الدخل: {data.get('net_income',0):,.2f}
- الأصول: {data.get('assets',0):,.2f}
- الخصوم: {data.get('liabilities',0):,.2f}
- حقوق الملكية: {data.get('equity',0):,.2f}""")
            
            if "تحليل النسب" in analysis_scope:
                data_parts.append(f"النسب المالية: {json.dumps(ratios, ensure_ascii=False)}")
            
            if "اتجاهات المبيعات" in analysis_scope:
                data_parts.append(f"اتجاهات المبيعات الشهرية: {json.dumps(trends, ensure_ascii=False, default=str)}")
            
            if "تحليل العملاء والموردين" in analysis_scope:
                data_parts.append(f"أفضل العملاء: {json.dumps(top_cust, ensure_ascii=False, default=str)}")
                data_parts.append(f"أفضل الموردين: {json.dumps(top_supp, ensure_ascii=False, default=str)}")
            
            if "تحليل مراكز التكلفة" in analysis_scope and cc_data:
                data_parts.append(f"ملخص مراكز التكلفة: {json.dumps(cc_data, ensure_ascii=False)}")
            
            if "المخزون والمشتريات" in analysis_scope:
                low_stock = data.get('low_stock', [])
                products = data.get('products', [])
                data_parts.append(f"المنتجات تحت الحد الأدنى: {json.dumps(low_stock, ensure_ascii=False, default=str)}")
                data_parts.append(f"كل المنتجات: {json.dumps(products, ensure_ascii=False, default=str)}")
            
            if "الموارد البشرية" in analysis_scope:
                employees = data.get('employees', [])
                data_parts.append(f"الموظفون: {json.dumps(employees, ensure_ascii=False, default=str)}")
            
            full_data = "\n\n".join(data_parts)
            
            prompt = f"""أنت محلل أعمال أول ومستشار مالي. بناءً على البيانات التالية، قدم تقريراً تحليلياً احترافياً شاملاً.
البيانات:
{full_data}

المطلوب:
1. تحليل نقاط القوة والضعف الرئيسية
2. مقارنة الأداء بالمعايير المثالية للصناعة
3. اكتشاف الأنماط والاتجاهات الخفية
4. تحديد الفرص والمخاطر
5. توصيات استراتيجية محددة وقابلة للتنفيذ مع تقدير الأثر المالي لكل توصية
6. خريطة طريق للتحسين خلال الـ 6 أشهر القادمة

اجعل الرد باللغة العربية، منظماً ومفصلاً."""
            with st.spinner("🧠 تحليل عميق..."):
                ans = query_groq(prompt, "قدم تحليلاً شاملاً", model=model, max_tokens=1500)
            glass(ans)

    # ====== تبويب 9: مراكز التكلفة (بدون تسجيل صوتي) ======
    with t9:
        h3("🎯 تحليل مراكز التكلفة بالذكاء الاصطناعي", CY)
        
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            st.warning("لا توجد مراكز تكلفة نشطة. أضف مراكز من وحدة مراكز التكلفة أولاً.")
        else:
            center_options = {f"{c['code']} - {c['name']}": c['id'] for c in centers}
            selected_center_label = st.selectbox("اختر مركز التكلفة", list(center_options.keys()))
            center_id = center_options[selected_center_label]
            
            fiscal_year = st.number_input("السنة المالية لتحليل الموازنة", min_value=2020, max_value=2030, value=datetime.now().year)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📊 تحليل أداء المركز", use_container_width=True):
                    with st.spinner("🧠 تحليل أداء المركز..."):
                        analysis = analyze_cost_center_performance(center_id)
                    glass(analysis)
            
            with col2:
                if st.button("🔍 مقارنة جميع المراكز", use_container_width=True):
                    with st.spinner("📈 مقارنة المراكز..."):
                        comparison = compare_cost_centers()
                    glass(comparison)
            
            col3, col4 = st.columns(2)
            
            with col3:
                months_ahead = st.selectbox("عدد الأشهر للتنبؤ", [1, 3, 6], key="months_cc")
                if st.button("🔮 توقع المصروفات المستقبلية", use_container_width=True):
                    with st.spinner("🔮 التنبؤ بالمصروفات..."):
                        prediction = predict_cost_center_expenses(center_id, months=months_ahead)
                    glass(prediction)
            
            with col4:
                if st.button("💰 تحليل انحرافات الموازنة", use_container_width=True):
                    with st.spinner("📉 تحليل الانحرافات..."):
                        budget_analysis = get_cost_center_budget_analysis(center_id, fiscal_year)
                    glass(budget_analysis)
