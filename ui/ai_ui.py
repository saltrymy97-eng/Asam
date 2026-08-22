# ui/ai_ui.py – واجهة المساعد الذكي بتصميم فاخر (Enterprise Dark/Gold Theme)
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime
from services.ai_service import (
    GROQ_API_KEY, create_ai_tables, query_groq, save_chat_history, get_chat_history,
    get_chat_sessions, get_comprehensive_data, get_inventory_data,
    get_employee_info, get_recent_entries, get_all_accounts, get_conn,
    get_financial_ratios, get_trend_analysis, get_business_snapshot,
    analyze_cost_center_performance, compare_cost_centers,
    predict_cost_center_expenses, get_cost_center_budget_analysis,
    generate_template_entry, get_available_operations, get_operation_description,
    is_mixed_operation, is_vat_operation, is_inventory_adjustment,
    is_salary_operation
)
from services import cost_center_service as ccs
from groq import Groq

# ========== ألوان التصميم الليلي الفاخر (Dark Enterprise) ==========
BG_COLOR = "#0B0F19"
CARD_BG = "linear-gradient(145deg, #111827, #0B0F19)"
CARD_BORDER = "rgba(212, 175, 55, 0.15)"
GLOW_SHADOW = "0 8px 32px 0 rgba(0, 0, 0, 0.5)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
GOLD = "#D4AF37"
GOLD_GLOW = "rgba(212, 175, 55, 0.4)"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_GREEN = "#10B981"
ACCENT_RED = "#EF4444"

# النماذج المتاحة
AVAILABLE_MODELS = {
    "GPT OSS 20B (عالي الدقة)": "openai/gpt-oss-20b",
    "compound-mini (سريع)": "groq/compound-mini",
}

# ========== 🎤 معالجة الصوت ==========
def audio_to_text(audio_file):
    if audio_file is None: return ""
    try:
        client = Groq(api_key=GROQ_API_KEY)
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
    audio_value = st.audio_input("🎤", key=key, label_visibility="collapsed")
    if audio_value:
        with st.spinner("🎙️ جاري تحويل الصوت إلى نص..."):
            text = audio_to_text(audio_value)
            return text
    return ""

def render_ai_response(content):
    """تغليف رد الذكاء الاصطناعي في بطاقة زجاجية فاخرة"""
    st.markdown(f"""
    <div style="  
        background: {CARD_BG};  
        backdrop-filter: blur(12px);  
        border: 1px solid {CARD_BORDER};  
        border-radius: 16px;  
        padding: 1.8rem;  
        margin: 1.5rem 0;  
        box-shadow: {GLOW_SHADOW};  
        color: {TEXT_PRIMARY};  
        font-size: 1.05rem;  
        line-height: 1.7;  
        direction: rtl;  
        text-align: right;  
    ">
    {content}
    </div>
    """, unsafe_allow_html=True)

def show():
    # ===== حقن CSS المعدل مع Media Queries وإصلاح التبويبات =====
    st.markdown(f"""
    <style>
    /* 1. تغيير لون الخلفية للتطبيق بالكامل */
    .stApp {{
        background-color: {BG_COLOR};
    }}

    /* 2. تطبيق اتجاه اليمين لليسار على منطقة المحتوى الرئيسية */  
    .block-container {{  
        direction: rtl;  
        text-align: right;  
    }}  
      
    /* تصميم الأزرار */  
    .stButton > button {{  
        background: linear-gradient(135deg, rgba(212,175,55,0.15), rgba(212,175,55,0.05)) !important;  
        border: 1px solid rgba(212,175,55,0.3) !important;  
        color: {GOLD} !important;  
        font-weight: 700 !important;  
        border-radius: 12px !important;  
        padding: 10px 24px !important;  
        transition: all 0.3s ease-in-out !important;  
        text-transform: uppercase;  
        letter-spacing: 0.5px;  
    }}  
    .stButton > button:hover {{  
        background: linear-gradient(135deg, rgba(212,175,55,0.3), rgba(212,175,55,0.1)) !important;  
        box-shadow: 0 0 15px {GOLD_GLOW} !important;  
        transform: translateY(-2px);  
        color: #FFF !important;  
    }}  

    /* =========================================================
       Streamlit Tabs - ترتيب ثابت من اليسار إلى اليمين
       ========================================================= */
    div[data-baseweb="tab-list"] {{
        display: flex !important;
        flex-direction: row !important;
        justify-content: flex-start !important;
        align-items: stretch !important;
        direction: ltr !important;
        unicode-bidi: isolate !important;
        gap: 8px !important;
        width: 100% !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        background: transparent !important; /* مهم جداً */
        transform: none !important;
    }}

    /* جميع عناصر التبويب */
    div[data-baseweb="tab-list"] > div {{
        flex: 0 0 auto !important;
        order: unset !important;
        direction: ltr !important;
    }}

    /* التبويب */
    button[data-baseweb="tab"] {{
        flex: 0 0 auto !important;
        direction: rtl !important;
        unicode-bidi: isolate !important;
        white-space: nowrap !important;
        text-align: center !important;
        background-color: #1F2937 !important;
        color: #94A3B8 !important;
        border: 1px solid transparent !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 10px 16px !important;
    }}

    /* التبويب النشط */
    button[data-baseweb="tab"][aria-selected="true"] {{
        background-color: #111827 !important;
        color: #F8FAFC !important;
        border-bottom: 2px solid #EF4444 !important;
    }}

    /* Hover */
    button[data-baseweb="tab"]:hover {{
        background-color: #273449 !important;
        color: #F8FAFC !important;
    }}

    /* النص داخل التبويب */
    button[data-baseweb="tab"] > div,
    button[data-baseweb="tab"] p,
    button[data-baseweb="tab"] span {{
        direction: rtl !important;
        unicode-bidi: plaintext !important;
        white-space: nowrap !important;
    }}

    /* Scrollbar */
    div[data-baseweb="tab-list"]::-webkit-scrollbar {{
        height: 4px;
    }}
    div[data-baseweb="tab-list"]::-webkit-scrollbar-track {{
        background: transparent;
    }}
    div[data-baseweb="tab-list"]::-webkit-scrollbar-thumb {{
        background: #374151;
        border-radius: 10px;
    }}

    /* الحقول والإدخالات */  
    .stTextInput input, .stNumberInput input, .stSelectbox [data-baseweb="select"] {{  
        background-color: #1F2937 !important;  
        color: {TEXT_PRIMARY} !important;  
        border: 1px solid #374151 !important;  
        border-radius: 8px !important;  
        direction: rtl;  
    }}  
      
    /* إصلاح عرض حاوية إدخال الصوت لتبدو أفضل */  
    [data-testid="stAudioInput"] {{  
        min-width: 100px;  
    }}

    /* =========================================================
       Media Queries للاستجابة (الهواتف المحمولة)
       ========================================================= */
    .ai-main-title {{
        font-size: 2.8rem;
        line-height: 1.2;
    }}
    
    @media (max-width: 768px) {{
        .block-container {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }}
        .ai-main-title {{
            font-size: 2rem !important;
            line-height: 1.35 !important;
        }}
    }}
    </style>  
    """, unsafe_allow_html=True)  

    create_ai_tables()  

    with st.sidebar:  
        st.markdown(f"<h3 style='color:{GOLD}; text-align: right; direction: rtl;'>⚙️ إعدادات الذكاء الاصطناعي</h3>", unsafe_allow_html=True)  
        model_name = st.selectbox("اختر المحرك:", list(AVAILABLE_MODELS.keys()))  
        model = AVAILABLE_MODELS[model_name]  

    if "active_session" not in st.session_state:  
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"  

    # تعديل العنوان ليستخدم كلاس ai-main-title بدلاً من style المباشر لحجم الخط
    st.markdown(f"""  
    <div style="background: {CARD_BG}; border-radius: 20px; padding: 2rem; margin-bottom: 2rem; border: 1px solid #1F2937; box-shadow: {GLOW_SHADOW}; direction: rtl;">  
        <div style="display: inline-block; background: rgba(139, 92, 246, 0.15); padding: 6px 12px; border-radius: 8px; margin-bottom: 1rem;">  
            <span style="color: {ACCENT_PURPLE}; font-weight: 800; font-size: 0.9rem; letter-spacing: 1px;">🪐 AI ENTERPRISE HUB</span>  
        </div>  
        <h1 class="ai-main-title" style="color: {TEXT_PRIMARY}; margin: 0 0 10px 0; font-weight: 900;">المساعد المالي الذكي</h1>  
        <p style="color: {TEXT_SECONDARY}; font-size: 1.1rem; margin: 0;">نظرة عامة على مؤشرات الأداء، التحليلات، وتوليد القيود الآلية</p>  
    </div>  
    """, unsafe_allow_html=True)  

    # الترتيب الطبيعي للتبويبات
    t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs([  
        "🧠 مساعد", "📊 محلل", "📦 مخزون", "💬 موظفين", "📝 قيود", "🔍 احتيال", "🔮 تنبؤات", "📈 تقرير شامل", "🎯 مراكز تكلفة"  
    ])  

    # ====== تبويب 1: المساعد ======  
    with t1:  
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>💬 اسأل عن أي شيء في نظامك</h3>", unsafe_allow_html=True)  
        mic_col, chat_col = st.columns([2, 10])  
        with mic_col: voice_text = audio_input_widget("assistant_audio")  
        with chat_col: q = st.chat_input("اطرح سؤالك المالي أو التشغيلي هنا...", key="ai-chat-input")  
          
        active_query = voice_text if voice_text and not voice_text.startswith("❌") else (q if q else "")  
        if active_query:  
            st.chat_message("user").write(active_query)  
            data = get_comprehensive_data()  
            d = json.dumps(data, ensure_ascii=False, default=str)  
              
            prompt = f"""أنت مستشار مالي ومدير مالي (CFO) خبير تعمل ضمن نظام ERP. البيانات الحالية للشركة:

{d}
المطلوب:
1. قدم إجابة وافية، دقيقة، ومنظمة مهنياً.
2. استخدم العناوين العريضة والجداول لتوضيح الأرقام.
3. اشرح التأثير المالي والتشغيلي بوضوح.
4. حافظ على نبرة احترافية، رصينة، وداعمة لاتخاذ القرار (استخدم تنسيق Markdown)."""

            with st.spinner("🧠 جاري المعالجة والتحليل..."):  
                ans = query_groq(prompt, active_query, model=model, max_tokens=2048)  
            st.chat_message("assistant").write(ans)  
            save_chat_history(st.session_state.active_session, "user", active_query, model, "مساعد")  
            save_chat_history(st.session_state.active_session, "assistant", ans, model, "مساعد")

    # ====== تبويب 2: المحلل ======
    with t2:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📊 التحليل المالي والنسب</h3>", unsafe_allow_html=True)
        if st.button("🚀 بدء التحليل المالي الشامل", type="primary"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            prompt = f"""أنت محلل مالي أول ومستشار استراتيجي. الأرقام:
الإيرادات: {data.get('revenue',0):,.2f} | المصروفات: {data.get('expenses',0):,.2f} | صافي الدخل: {data.get('net_income',0):,.2f}
النسب: {json.dumps(ratios, ensure_ascii=False)}

المطلوب تقديم تقرير تحليل مالي مهيكل كالتالي:
1. الملخص التنفيذي: قراءة احترافية لأداء الشركة المالي.
2. تحليل النسب: تفصيل لمعنى النسب المالية ومدى كفاءتها وصحتها.
3. نقاط القوة والضعف (SWOT Analysis): تحليل متعمق للوضع المالي.
4. التوصيات الاستراتيجية: خطوات عملية ومحددة لتحسين الربحية وتقليل المخاطر."""
            with st.spinner("📊 جاري تحليل البيانات المالية واستخراج الرؤى..."):
                ans = query_groq(prompt, "قدم التحليل المالي الشامل", model=model, max_tokens=2048)
                render_ai_response(ans)

    # ====== تبويب 3: المخزون ======
    with t3:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📦 تحليل المخزون واكتشاف العجز</h3>", unsafe_allow_html=True)
        low, allp = get_inventory_data()
        if st.button("📦 تحليل حالة المخزون", type="primary"):
            if allp:
                df = pd.DataFrame(allp)
                prompt = f"""أنت خبير متمرس في إدارة سلاسل الإمداد والمخزون. البيانات:\n{df.to_string()}
المطلوب تقديم تحليل شامل لحالة المخزون:
1. التقييم العام: قراءة لحالة المخزون وكفاءة إدارته.
2. الأصناف الحرجة (Hot Items): تحليل العناصر التي شارفت على النفاد وتأثيرها.
3. المخاطر التشغيلية والمالية: ما الذي يسببه التكدس أو النقص الحالي؟
4. الإجراءات التصحيحية: توصيات استراتيجية لتحسين معدل دوران المخزون وتفادي الخسائر."""
                with st.spinner("📦 جاري تحليل سلاسل الإمداد..."):
                    ans = query_groq(prompt, "حلل المخزون وقدم تقريراً إدارياً", model=model, max_tokens=2048)
                    render_ai_response(ans)
        if low:
            st.error(f"⚠️ يوجد {len(low)} منتجات تحت الحد الأدنى للطلب!")
            st.dataframe(pd.DataFrame(low), use_container_width=True)

    # ====== تبويب 4: الموظفين ======
    with t4:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>💬 استعلامات الموارد البشرية الذكية</h3>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: nm = st.text_input("اسم الموظف:")
        with c2: eq = st.text_input("السؤال (مثل: ما هو تقييم أدائي؟):")
        if st.button("استعلام", type="primary") and nm and eq:
            emp, sal = get_employee_info(nm)
            if emp:
                info = f"{emp['name']} - {emp['position']} | الراتب الأساسي: {sal.get('basic_salary',0) if sal else 0}"
                prompt = f"""أنت مدير موارد بشرية (HR Manager) محترف ولبق.
بيانات الموظف المستعلم: {info}.
المطلوب: أجب على استفسار الموظف ({eq}) بأسلوب مهني، داعم، وواضح. قدم الإجابة بتفصيل كافٍ يشرح الوضع ويقدم التوجيه اللازم والتطوير المستقبلي."""
                with st.spinner("⏳ جاري صياغة الرد الوظيفي..."):
                    ans = query_groq(prompt, eq, model=model, max_tokens=1000)
                    render_ai_response(ans)
            else:
                st.error("❌ الموظف غير موجود في قاعدة البيانات.")

    # ====== تبويب 5: القيود ======
    with t5:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>🪄 محرك القيود المحاسبية الذكي</h3>", unsafe_allow_html=True)
        operations = get_available_operations()
        selected_op = st.selectbox("🎯 اختر نوع العملية المالية", options=operations)
        st.caption(f"📌 {get_operation_description(selected_op)}")
        st.markdown("<hr style='border-color: #374151;'>", unsafe_allow_html=True)

        if is_mixed_operation(selected_op):  
            c1, c2, c3 = st.columns(3)  
            with c1: total_amount = st.number_input("المبلغ الإجمالي", min_value=0.0, step=10.0)  
            with c2: cash_amount = st.number_input("الجزء النقدي", min_value=0.0, step=10.0)  
            with c3: credit_amount = st.number_input("الجزء الآجل", min_value=0.0, step=10.0)  
            vat_rate = expense_name = adjustment_side = inventory_side = None  
        elif is_vat_operation(selected_op):  
            c1, c2 = st.columns(2)  
            with c1: total_amount = st.number_input("المبلغ شامل الضريبة", min_value=0.0, step=10.0)  
            with c2: vat_rate = st.number_input("نسبة الضريبة (%)", value=15.0) / 100  
            cash_amount = credit_amount = expense_name = adjustment_side = inventory_side = None  
        elif selected_op == "سداد مصروف":  
            c1, c2 = st.columns(2)  
            with c1: total_amount = st.number_input("المبلغ", min_value=0.0, step=10.0)  
            with c2: expense_name = st.text_input("اسم المصروف", value="كهرباء")  
            cash_amount = credit_amount = vat_rate = adjustment_side = inventory_side = None  
        elif is_inventory_adjustment(selected_op):  
            c1, c2 = st.columns(2)  
            with c1: total_amount = st.number_input("قيمة التسوية", min_value=0.0, step=10.0)  
            with c2:  
                adj_type = st.selectbox("نوع التسوية", ["عجز (نقص)", "فائض (زيادة)"])  
                if adj_type == "عجز (نقص)": 
                    adjustment_side, inventory_side = "debit", "credit"  
                else: 
                    adjustment_side, inventory_side = "credit", "debit"  
            cash_amount = credit_amount = vat_rate = expense_name = None  
        else:  
            total_amount = st.number_input("المبلغ", min_value=0.0, step=10.0)  
            cash_amount = credit_amount = vat_rate = expense_name = adjustment_side = inventory_side = None  

        if st.button("✨ توليد القيد المحاسبي", type="primary", use_container_width=True):  
            if total_amount > 0:  
                with st.spinner("⚙️ معالجة التوجيه المحاسبي..."):  
                    entry, display, confidence, confidence_label, confidence_color = generate_template_entry(  
                        operation_type=selected_op, amount=total_amount,  
                        cash_amount=cash_amount, credit_amount=credit_amount,  
                        expense_name=expense_name, vat_rate=vat_rate,  
                        adjustment_side=adjustment_side, inventory_side=inventory_side  
                    )  
                if entry:  
                    st.markdown("### 🧾 القيد المحاسبي المولد:")  
                    st.code(display, language="text")  
                    st.markdown(f"""  
                    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid {confidence_color}; padding: 12px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">  
                        <strong style="color: #FFF;">مستوى الثقة في التوجيه الآلي:</strong>  
                        <span style="background: {confidence_color}; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold;">{confidence}% - {confidence_label}</span>  
                    </div>  
                    """, unsafe_allow_html=True)  
                else:  
                    st.error(display)  
            else:  
                st.warning("⚠️ يرجى إدخال مبلغ صحيح أكبر من الصفر.")

    # ====== تبويب 6: الاحتيال ======
    with t6:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>🕵️ نظام كشف الاحتيال والتشوهات</h3>", unsafe_allow_html=True)
        if st.button("🔍 فحص القيود الأخيرة", type="primary"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق مالي جنائي ومراجع داخلي (Forensic Auditor).
افحص هذه القيود الأخيرة للكشف عن أي شذوذ، تلاعب، أو توجيه محاسبي غير منطقي:\n{df.to_string()}
المطلوب تقديم تقرير تدقيق مهيكل:
1. نتيجة الفحص الأولية: التقييم العام لسلامة القيود.
2. الملاحظات والتشوهات (إن وجدت): تحديد القيود المشكوك فيها مع شرح السبب المالي.
3. مؤشرات الخطر الإداري: دلالات هذه التشوهات على الرقابة.
4. التوصيات الرقابية: خطوات عملية لضبط الرقابة الداخلية ومنع الاحتيال مستقبلاً."""
                with st.spinner("🔍 جاري الفحص الجنائي العميق للقيود..."):
                    ans = query_groq(prompt, "افحص القيود واستخرج تقريراً", model=model, max_tokens=2048)
                    render_ai_response(ans)
            else:
                st.info("لا توجد قيود كافية للفحص.")

    # ====== تبويب 7: التنبؤات ======
    with t7:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>🔮 التخطيط المالي والتنبؤ</h3>", unsafe_allow_html=True)
        period = st.selectbox("حدد الأفق الزمني:", ["الشهر القادم", "الربع القادم", "نهاية العام"])
        if st.button("🚀 توليد التنبؤ المالي", type="primary"):
            data = get_comprehensive_data()
            prompt = f"""أنت خبير تخطيط مالي واستشراف أعمال (FP&A Manager). بناءً على البيانات الشاملة: {json.dumps(data, ensure_ascii=False)}
المطلوب إعداد خطة استشرافية للفترة ({period}) مهيكلة كالتالي:
1. التوقعات المالية: تحليل احترافي للاتجاهات المتوقعة (الإيرادات والنفقات).
2. جدول السيناريوهات: تقديرات متوقعة رقمية (محافظة ومتفائلة).
3. المخاطر المحتملة (Risk Factors): التحديات الاقتصادية والتشغيلية القادمة.
4. استراتيجيات التحوط والنمو: توجيهات مالية وإدارية للحفاظ على استقرار التدفقات النقدية وتعظيم الأرباح."""
            with st.spinner("🔮 جاري محاكاة التوقعات المستقبلية..."):
                ans = query_groq(prompt, "قم بتوليد التنبؤ المالي", model=model, max_tokens=2048)
                render_ai_response(ans)

    # ====== تبويب 8: التحليل الشامل ======
    with t8:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📑 تقرير مجلس الإدارة الآلي</h3>", unsafe_allow_html=True)
        if st.button("📄 إصدار التقرير الشامل", type="primary", use_container_width=True):
            data = get_comprehensive_data()
            prompt = f"""أنت مستشار استراتيجي ومالي لمجلس الإدارة. بناءً على: {json.dumps(data, ensure_ascii=False)}
المطلوب إعداد تقرير مجلس إدارة (Board Report) احترافي وشامل، مهيكل كالتالي:
1. الملخص التنفيذي: نظرة عامة ورؤية ثاقبة لوضع الشركة.
2. الأداء المالي (Financials): تحليل معمق مدعوم بالأرقام والجداول لأهم المؤشرات.
3. الأداء التشغيلي (Operations): تحليل لسلاسل الإمداد، المبيعات، والكوادر البشرية.
4. تقييم المخاطر (Risk Assessment): تسليط الضوء على أبرز العقبات والمخاطر المحدقة.
5. القرارات الاستراتيجية المقترحة: توصيات حاسمة موجهة للإدارة العليا لاتخاذها لضمان استدامة الأعمال ونموها."""
            with st.spinner("🧠 يتم الآن تجميع وتوليد التقرير الشامل..."):
                ans = query_groq(prompt, "أصدر تقرير مجلس الإدارة", model=model, max_tokens=3000)
                render_ai_response(ans)

    # ====== تبويب 9: مراكز التكلفة ======
    with t9:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>🏢 تحليل أداء قطاعات الأعمال</h3>", unsafe_allow_html=True)
        centers = ccs.get_all_cost_centers(active_only=True)
        if centers:
            c_options = {f"{c['code']} - {c['name']}": c['id'] for c in centers}
            selected_cc = st.selectbox("حدد مركز التكلفة (القطاع):", list(c_options.keys()))
            cc_id = c_options[selected_cc]

            col1, col2, col3 = st.columns(3)  
            with col1:  
                if st.button("📊 تقييم الأداء", type="primary", use_container_width=True):  
                    with st.spinner("جاري التقييم التحليلي..."):  
                        analysis = analyze_cost_center_performance(cc_id)  
                        render_ai_response(analysis)  
            with col2:  
                if st.button("⚖️ مقارنة القطاعات", type="primary", use_container_width=True):  
                    with st.spinner("جاري مقارنة المراكز..."):  
                        comp = compare_cost_centers()  
                        render_ai_response(comp)  
            with col3:  
                if st.button("📉 تحليل الانحرافات", type="primary", use_container_width=True):  
                    with st.spinner("جاري تحليل الموازنة..."):  
                        budget = get_cost_center_budget_analysis(cc_id, datetime.now().year)  
                        render_ai_response(budget)  
        else:  
            st.warning("⚠️ لا توجد مراكز تكلفة معرفة أو نشطة في النظام.")
