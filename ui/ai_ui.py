# ui/ai_ui.py – واجهة المساعد الذكي بتصميم فاخر (Enterprise Dark/Gold Theme)
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime
from services.ai_service import (
    GROQ_API_KEY, 
    create_ai_tables, query_groq, save_chat_history, get_chat_history,
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
    "GPT OSS 120B (عالي الدقة)": "openai/gpt-oss-120b",
    "GPT OSS 20B (سريع)": "openai/gpt-oss-20b",
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
    # إزالة رسالة st.success من هنا لمنع تشوه التصميم في العمود الضيق
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
    # ===== حقن CSS للتصميم الليلي الفاخر (مطابق للصور) =====
    st.markdown(f"""
    <style>
    /* دعم الاتجاه من اليمين لليسار */
    .stApp {{
        background-color: {BG_COLOR};
        direction: rtl;
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

    /* تصميم التبويبات (Tabs) */
    div[data-baseweb="tab-list"] {{
        background-color: transparent !important;
        gap: 8px;
    }}
    div[data-baseweb="tab"] {{
        background-color: #1F2937 !important;
        border-radius: 8px 8px 0 0 !important;
        color: {TEXT_SECONDARY} !important;
        border: 1px solid transparent;
        padding: 10px 16px !important;
    }}
    div[aria-selected="true"] {{
        background-color: #111827 !important;
        color: {TEXT_PRIMARY} !important;
        border-bottom: 2px solid {ACCENT_RED} !important;
    }}

    /* الحقول والإدخالات */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {{
        background-color: #1F2937 !important;
        color: {TEXT_PRIMARY} !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
    }}
    
    /* إصلاح عرض حاوية إدخال الصوت لتبدو أفضل على اللابتوب */
    [data-testid="stAudioInput"] {{
        min-width: 100px;
    }}
    </style>
    """, unsafe_allow_html=True)

    create_ai_tables()

    with st.sidebar:
        st.markdown(f"<h3 style='color:{GOLD};'>⚙️ إعدادات الذكاء الاصطناعي</h3>", unsafe_allow_html=True)
        model_name = st.selectbox("اختر المحرك:", list(AVAILABLE_MODELS.keys()))
        model = AVAILABLE_MODELS[model_name]

    if "active_session" not in st.session_state:
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ===== الهيدر الفاخر المطابق لتصميم ENTERPRISE HUB =====
    st.markdown(f"""
    <div style="background: {CARD_BG}; border-radius: 20px; padding: 2rem; margin-bottom: 2rem; border: 1px solid #1F2937; box-shadow: {GLOW_SHADOW}; direction: rtl;">
        <div style="display: inline-block; background: rgba(139, 92, 246, 0.15); padding: 6px 12px; border-radius: 8px; margin-bottom: 1rem;">
            <span style="color: {ACCENT_PURPLE}; font-weight: 800; font-size: 0.9rem; letter-spacing: 1px;">🪐 AI ENTERPRISE HUB</span>
        </div>
        <h1 style="color: {TEXT_PRIMARY}; font-size: 2.8rem; margin: 0 0 10px 0; font-weight: 900;">المساعد المالي الذكي</h1>
        <p style="color: {TEXT_SECONDARY}; font-size: 1.1rem; margin: 0;">نظرة عامة على مؤشرات الأداء، التحليلات، وتوليد القيود الآلية</p>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs([
        "🧠 مساعد", "📊 محلل", "📦 مخزون", "💬 موظفين", "📝 قيود", "🔍 احتيال", "🔮 تنبؤات", "📈 تقرير شامل", "🎯 مراكز تكلفة"
    ])

    # ====== تبويب 1: المساعد ======
    with t1:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>💬 اسأل عن أي شيء في نظامك</h3>", unsafe_allow_html=True)
        
        # تعديل مساحة الأعمدة لتناسب اللابتوب وتمنع تشوه التصميم
        mic_col, chat_col = st.columns([2, 10])
        
        with mic_col:
            voice_text = audio_input_widget("assistant_audio")
            
        with chat_col:
            q = st.chat_input("اطرح سؤالك المالي أو التشغيلي هنا...", key="ai-chat-input")
        
        # معالجة المدخلات (صوت أو نص)
        active_query = ""
        if voice_text:
            if voice_text.startswith("❌"):
                st.error(voice_text)
            else:
                active_query = voice_text
        elif q:
            active_query = q

        if active_query:
            # الآن النص المستخرج من الصوت سيظهر بعرض الشاشة الكامل كرسالة دردشة
            st.chat_message("user").write(active_query)
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            # أمر صارم لمنع الإنشائيات
            prompt = f"""أنت خبير مالي ومحلل أعمال في نظام ERP. البيانات الحالية للشركة:
{d}
**تعليمات صارمة جداً:**
1. أجب بشكل مباشر وبدون أي مقدمات أو ترحيب.
2. استخدم الجداول لعرض الأرقام، والنقاط (Bullet points) المباشرة للتوصيات.
3. يمنع منعاً باتاً كتابة أي خاتمة إنشائية."""
            
            with st.spinner("🧠 جاري المعالجة..."):
                ans = query_groq(prompt, active_query, model=model, max_tokens=1500)
            st.chat_message("assistant").write(ans)
            save_chat_history(st.session_state.active_session, "user", active_query, model, "مساعد")
            save_chat_history(st.session_state.active_session, "assistant", ans, model, "مساعد")

    # ====== تبويب 2: المحلل ======
    with t2:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📊 التحليل المالي والنسب</h3>", unsafe_allow_html=True)
        if st.button("🚀 بدء التحليل المالي الشامل", type="primary"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            prompt = f"""أنت محلل مالي أول. الأرقام:
- الإيرادات: {data.get('revenue',0):,.2f} | المصروفات: {data.get('expenses',0):,.2f} | صافي الدخل: {data.get('net_income',0):,.2f}
- النسب: {json.dumps(ratios, ensure_ascii=False)}

**تعليمات صارمة:**
1. لا تستخدم أي مقدمة (مثل "بناءً على الأرقام...").
2. قدم جدولاً واحداً يلخص الأداء المالي.
3. قدم 3 نقاط مختصرة جداً كنقاط قوة وضعف.
4. قدم توصيتين فقط للتحسين. لا تكتب خاتمة."""
            with st.spinner("📊 جاري تحليل البيانات المالية..."):
                ans = query_groq(prompt, "قدم التحليل", model=model, max_tokens=1500)
            render_ai_response(ans)

    # ====== تبويب 3: المخزون ======
    with t3:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📦 تحليل المخزون واكتشاف العجز</h3>", unsafe_allow_html=True)
        low, allp = get_inventory_data()
        if st.button("📦 تحليل حالة المخزون", type="primary"):
            if allp:
                df = pd.DataFrame(allp)
                prompt = f"""أنت خبير إدارة مخزون. البيانات:\n{df.to_string()}
**تعليمات صارمة:**
1. بدون مقدمات.
2. استخدم جدولاً لعرض العناصر الحرجة.
3. اذكر 3 نقاط سريعة كإجراءات تصحيحية.
4. لا تكتب أي خاتمة."""
                with st.spinner("📦 جاري تحليل الأصناف..."):
                    ans = query_groq(prompt, "حلل المخزون", model=model, max_tokens=1000)
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
                info = f"{emp['name']} - {emp['position']} | راتب: {sal.get('basic_salary',0) if sal else 0}"
                prompt = f"أنت مدير موارد بشرية. بيانات الموظف: {info}. **تعليمات:** أجب على السؤال ({eq}) في جملتين مباشرتين فقط دون أي ترحيب."
                with st.spinner("⏳..."):
                    ans = query_groq(prompt, eq, model=model, max_tokens=300)
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

        # تجهيز الحقول الديناميكية
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
                if adj_type == "عجز (نقص)": adjustment_side, inventory_side = "debit", "credit"
                else: adjustment_side, inventory_side = "credit", "debit"
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
                prompt = f"""أنت مدقق جنائي داخلي. افحص هذه القيود:\n{df.to_string()}
**تعليمات صارمة:**
1. بدون مقدمات ولا خاتمات.
2. إذا لم تجد شذوذاً، اكتب "لا توجد مؤشرات احتيال قوية".
3. إذا وجدت شكوكاً، اذكرها في نقاط قصيرة جداً ومباشرة فقط."""
                with st.spinner("🔍 جاري الفحص الجنائي..."):
                    ans = query_groq(prompt, "افحص القيود", model=model, max_tokens=1000)
                render_ai_response(ans)
            else:
                st.info("لا توجد قيود كافية للفحص.")

    # ====== تبويب 7: التنبؤات ======
    with t7:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>🔮 التخطيط المالي والتنبؤ</h3>", unsafe_allow_html=True)
        period = st.selectbox("حدد الأفق الزمني:", ["الشهر القادم", "الربع القادم", "نهاية العام"])
        if st.button("🚀 توليد التنبؤ المالي", type="primary"):
            data = get_comprehensive_data()
            prompt = f"""أنت مخطط مالي. بناءً على البيانات: {json.dumps(data, ensure_ascii=False)}
**تعليمات صارمة:**
1. بدون أي مقدمة.
2. قدم التوقعات للفترة ({period}) في جدول.
3. اذكر 3 مخاطر محتملة في نقاط فقط. لا تكتب خاتمة."""
            with st.spinner("🔮 جاري الحساب..."):
                ans = query_groq(prompt, "تنبأ", model=model, max_tokens=1000)
            render_ai_response(ans)

    # ====== تبويب 8: التحليل الشامل ======
    with t8:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📑 تقرير مجلس الإدارة الآلي</h3>", unsafe_allow_html=True)
        if st.button("📄 إصدار التقرير الشامل", type="primary", use_container_width=True):
            data = get_comprehensive_data()
            prompt = f"""أنت مستشار إداري. بناءً على: {json.dumps(data, ensure_ascii=False)}
**تعليمات صارمة جداً:**
1. اكتب التقرير مقسماً إلى 3 أقسام فقط (المالية، التشغيل، التوصيات).
2. استخدم الجداول لعرض أي بيانات رقمية.
3. استخدم النقاط (Bullet points) لعرض الملاحظات والتوصيات.
4. يمنع منعاً باتاً كتابة مقدمات مثل "إليك التقرير" أو خاتمات مثل "أتمنى أن يكون هذا مفيداً"."""
            with st.spinner("🧠 يتم الآن تجميع التقرير الشامل..."):
                ans = query_groq(prompt, "أصدر التقرير", model=model, max_tokens=2000)
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
                    with st.spinner("جاري التقييم..."):
                        analysis = analyze_cost_center_performance(cc_id)
                        render_ai_response(analysis)
            with col2:
                if st.button("⚖️ مقارنة القطاعات", type="primary", use_container_width=True):
                    with st.spinner("جاري المقارنة..."):
                        comp = compare_cost_centers()
                        render_ai_response(comp)
            with col3:
                if st.button("📉 تحليل الانحرافات", type="primary", use_container_width=True):
                    with st.spinner("جاري التحليل..."):
                        budget = get_cost_center_budget_analysis(cc_id, datetime.now().year)
                        render_ai_response(budget)
        else:
            st.warning("⚠️ لا توجد مراكز تكلفة معرفة أو نشطة في النظام.")
