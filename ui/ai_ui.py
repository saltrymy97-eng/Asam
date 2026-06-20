# ui/ai_ui.py – واجهة المساعد الذكي المطورة بتصميم زجاجي ذهبي ملكي
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
    generate_template_entry, get_available_operations, get_operation_description,
    is_mixed_operation, is_vat_operation, is_inventory_adjustment,
    is_salary_operation
)
from services import cost_center_service as ccs
from groq import Groq

# ========== ألوان التصميم الملكي ==========
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
GOLD_DARK = "#AA771C"

AVAILABLE_MODELS = {
    "Llama 3.3 70B": "llama-3.3-70b-versatile",
    "Llama 3.1 8B (أسرع)": "llama-3.1-8b-instant",
}

# ========== 🎤 معالجة الصوت ==========
def audio_to_text(audio_file):
    if audio_file is None:
        return ""
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
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
            if text and not text.startswith("❌"):
                st.success(f"✅ {text}")
                return text
            else:
                st.error(text)
    return ""

def h1(title, color=GOLD):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{GOLD};font-size:2.8rem;margin:0;text-shadow:0 0 20px {GOLD}40;">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">تسعة خبراء مع تحليلات عميقة وتوصيات ذكية</p>
    </div>""", unsafe_allow_html=True)

def h3(title, color=GOLD):
    st.markdown(f"""<h3 style="color:{color};text-align:right;font-weight:700;">{title}</h3>""", unsafe_allow_html=True)

def glass(content):
    st.markdown(f"""<div style="background:rgba(20,20,10,0.7);backdrop-filter:blur(25px);-webkit-backdrop-filter:blur(25px);
        border:1px solid rgba(212,175,55,0.2);border-top:1px solid rgba(212,175,55,0.35);border-radius:20px;
        padding:1.5rem;margin:1rem 0;box-shadow:0 25px 50px rgba(0,0,0,0.5),0 0 15px rgba(212,175,55,0.05);
        color:{T};font-size:1.1rem;">{content}</div>""", unsafe_allow_html=True)

def show():
    # ====== CSS الزجاج الذهبي الموحد ======
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
        
        /* الخلفية العامة */
        .stApp {{
            background: linear-gradient(180deg, #0a0a05 0%, #050505 100%) !important;
        }}
        
        /* الحاوية الزجاجية الذهبية لكل تبويب */
        .golden-tab-container {{
            background: linear-gradient(145deg, rgba(20, 20, 10, 0.75), rgba(10, 10, 5, 0.9));
            backdrop-filter: blur(30px) saturate(180%);
            -webkit-backdrop-filter: blur(30px) saturate(180%);
            border: 1px solid rgba(212, 175, 55, 0.2);
            border-top: 1px solid rgba(212, 175, 55, 0.35);
            border-radius: 24px;
            padding: 2rem;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.5), 0 0 20px rgba(212, 175, 55, 0.08);
            margin-bottom: 1.5rem;
            position: relative;
            overflow: hidden;
        }}
        .golden-tab-container::before {{
            content: '';
            position: absolute;
            top: 0; right: 0;
            width: 250px; height: 250px;
            background: radial-gradient(circle, rgba(212, 175, 55, 0.04) 0%, transparent 70%);
            pointer-events: none;
        }}
        
        /* ترويسة ذهبية */
        .golden-section-title {{
            text-align: right;
            margin-bottom: 1.5rem;
            position: relative;
        }}
        .golden-section-title h3 {{
            color: {GOLD};
            font-weight: 800;
            font-size: 1.5rem;
            margin: 0;
            text-shadow: 0 0 15px {GOLD}30;
        }}
        .golden-section-title p {{
            color: {GOLD_LIGHT};
            font-size: 0.85rem;
            margin: 0;
        }}
        .golden-section-title::after {{
            content: '';
            display: block;
            width: 60px;
            height: 2px;
            background: linear-gradient(90deg, {GOLD}, transparent);
            margin-top: 8px;
        }}
        
        /* بطاقة النتيجة */
        .golden-result-card {{
            background: linear-gradient(145deg, rgba(212, 175, 55, 0.1), rgba(212, 175, 55, 0.02));
            border: 1px solid rgba(212, 175, 55, 0.3);
            border-radius: 16px;
            padding: 16px 20px;
            margin-top: 16px;
            display: flex;
            align-items: center;
            gap: 14px;
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.3);
        }}
        .golden-dot {{
            width: 12px; height: 12px;
            border-radius: 50%;
            animation: goldenPulse 2s ease-in-out infinite;
        }}
        @keyframes goldenPulse {{
            0%, 100% {{ box-shadow: 0 0 10px #10B981; }}
            50% {{ box-shadow: 0 0 20px #10B981, 0 0 30px rgba(16, 185, 129, 0.3); }}
        }}
        
        /* العناوين داخل التبويبات */
        .tab-inner-title {{
            color: {GOLD};
            font-weight: 700;
            font-size: 1.2rem;
            margin-bottom: 1rem;
        }}
        
        /* زر ذهبي */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {GOLD_DARK} 0%, {GOLD} 50%, {GOLD_LIGHT} 100%) !important;
            border: none !important;
            font-weight: 800 !important;
            font-size: 1.05rem !important;
            padding: 14px 24px !important;
            border-radius: 14px !important;
            color: #0a0a05 !important;
            transition: all 0.4s ease !important;
            box-shadow: 0 15px 30px -5px rgba(212, 175, 55, 0.3), inset 0 -2px 0 rgba(0,0,0,0.15) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-3px) !important;
            box-shadow: 0 25px 50px -5px rgba(212, 175, 55, 0.5), inset 0 -2px 0 rgba(0,0,0,0.15) !important;
            filter: brightness(1.15) !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    # ====== الهيدر الرئيسي ======
    st.markdown(f"""
    <div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{GOLD};font-size:2.8rem;margin:0;text-shadow:0 0 25px {GOLD}40;">🤖 المساعد الذكي AI</h1>
        <p style="color:{S};font-size:1.2rem;">تسعة خبراء مع تحليلات عميقة وتوصيات ذكية</p>
    </div>
    """, unsafe_allow_html=True)

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

    # ====== تبويب 1: المساعد ======
    with t1:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>💬 المساعد الذكي</h3><p>اسأل عن أي شيء في نظامك</p></div>', unsafe_allow_html=True)
        
        mic_col, chat_col = st.columns([1, 11])
        with mic_col:
            voice_text = audio_input_widget("assistant_audio")
        with chat_col:
            q = st.chat_input("اكتب سؤالك هنا...", key="ai-chat-input")
        
        if voice_text:
            q = voice_text
        
        if q:
            st.chat_message("user").write(q)
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"""أنت خبير مالي ومحلل أعمال في نظام ERP. لديك البيانات التالية عن الشركة:
{d}
أجب عن السؤال التالي بالعربية بشكل مفصل وعميق. قدم أرقاماً محددة، وحلل الاتجاهات، وقدم توصيات قابلة للتنفيذ."""
            with st.spinner("🧠 تحليل عميق..."):
                ans = query_groq(prompt, q, model=model, max_tokens=1500)
            st.chat_message("assistant").write(ans)
            save_chat_history(st.session_state.active_session, "user", q, model, "مساعد")
            save_chat_history(st.session_state.active_session, "assistant", ans, model, "مساعد")
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 2: المحلل ======
    with t2:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>📊 المحلل المالي</h3><p>تحليل مالي شامل وتوصيات</p></div>', unsafe_allow_html=True)
        if st.button("📈 تحليل شامل", type="primary"):
            data = get_comprehensive_data()
            ratios = get_financial_ratios()
            trends = get_trend_analysis()
            prompt = f"""أنت محلل مالي أول. حلل الأداء المالي بناءً على هذه الأرقام:
- الإيرادات: {data.get('revenue',0):,.2f}
- المصروفات: {data.get('expenses',0):,.2f}
- صافي الدخل: {data.get('net_income',0):,.2f}
- النسب المالية: {json.dumps(ratios, ensure_ascii=False)}
قدم تقريراً بالعربية يشمل تقييم الأداء وتحليل النسب وتوصيات."""
            with st.spinner("📊 تحليل شامل..."):
                ans = query_groq(prompt, "قدم تحليلاً شاملاً", model=model, max_tokens=1500)
            glass(ans)
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 3: المخزون ======
    with t3:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>📦 تحليل المخزون</h3><p>توقع النفاد وتحليل المنتجات</p></div>', unsafe_allow_html=True)
        low, allp = get_inventory_data()
        if st.button("📦 تحليل المخزون", type="primary"):
            if allp:
                df = pd.DataFrame(allp)
                prompt = f"""أنت خبير إدارة مخزون. حلل البيانات التالية:\n{df.to_string()}\nقدم تحليلاً بالعربية يشمل المنتجات المعرضة للنفاد والكميات المقترحة."""
                with st.spinner("📦 تحليل المخزون..."):
                    ans = query_groq(prompt, "حلل المخزون", model=model, max_tokens=1500)
                glass(ans)
        if low:
            st.warning("⚠️ منتجات تحت الحد الأدنى:")
            st.dataframe(pd.DataFrame(low))
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 4: الموظفين ======
    with t4:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>💼 استفسارات الموظفين</h3><p>استفسارات الرواتب والمعلومات الشخصية</p></div>', unsafe_allow_html=True)
        nm = st.text_input("اسمك:", key="ename")
        eq = st.text_input("سؤالك:", key="eq")
        if st.button("💬 اسأل", type="primary") and nm and eq:
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
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 5: القيود ======
    with t5:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>📝 مركز القيود المحاسبية</h3><p>قوالب ذهبية جاهزة بدقة 100%</p></div>', unsafe_allow_html=True)
        
        operations = get_available_operations()
        selected_op = st.selectbox("🎯 اختر نوع العملية المالية", options=operations, key="template_op")
        st.caption(f"📌 {get_operation_description(selected_op)}")
        st.markdown("---")
        
        if is_mixed_operation(selected_op):
            col1, col2, col3 = st.columns(3)
            with col1: total_amount = st.number_input("💰 المبلغ الإجمالي", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with col2: cash_amount = st.number_input("💵 الجزء النقدي", min_value=0.0, step=100.0, format="%.2f", key="ca")
            with col3: credit_amount = st.number_input("📋 الجزء الآجل", min_value=0.0, step=100.0, format="%.2f", key="cra")
            vat_rate = expense_name = None
        elif is_vat_operation(selected_op):
            col1, col2 = st.columns(2)
            with col1: total_amount = st.number_input("💰 المبلغ شامل الضريبة", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with col2: vat_rate = st.number_input("📊 نسبة الضريبة (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="vr") / 100
            cash_amount = credit_amount = expense_name = None
        elif selected_op == "سداد مصروف":
            col1, col2 = st.columns(2)
            with col1: total_amount = st.number_input("💰 المبلغ", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with col2: expense_name = st.text_input("📝 اسم المصروف", value="كهرباء", key="en")
            cash_amount = credit_amount = vat_rate = None
        elif is_inventory_adjustment(selected_op):
            col1, col2 = st.columns(2)
            with col1: total_amount = st.number_input("💰 قيمة التسوية", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with col2:
                adj_type = st.selectbox("📈 نوع التسوية", ["عجز (نقص)", "فائض (زيادة)"], key="adj")
                if adj_type == "عجز (نقص)": adjustment_side, inventory_side = "debit", "credit"
                else: adjustment_side, inventory_side = "credit", "debit"
            cash_amount = credit_amount = vat_rate = expense_name = None
        else:
            total_amount = st.number_input("💰 المبلغ", min_value=0.0, step=100.0, format="%.2f", key="ta")
            cash_amount = credit_amount = vat_rate = expense_name = adjustment_side = inventory_side = None
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🪄 توليد القيد المحاسبي", use_container_width=True, type="primary"):
            if total_amount > 0:
                with st.spinner("✨ جاري توليد القيد..."):
                    entry, display, confidence, confidence_label, confidence_color = generate_template_entry(
                        operation_type=selected_op, amount=total_amount,
                        cash_amount=cash_amount, credit_amount=credit_amount,
                        expense_name=expense_name, vat_rate=vat_rate,
                        adjustment_side=adjustment_side, inventory_side=inventory_side
                    )
                if entry:
                    st.markdown("---")
                    st.markdown("### ✨ القيد المحاسبي")
                    st.code(display, language="text")
                    st.markdown(f"""
                    <div class="golden-result-card">
                        <div class="golden-dot" style="background:{confidence_color};"></div>
                        <div>
                            <span style="color:#F8FAFC; font-weight:700;">📊 نسبة الثقة: {confidence}%</span>
                            <span style="background:{confidence_color}20; color:{confidence_color}; padding:4px 12px; border-radius:20px; font-weight:700; margin-right:10px;">{confidence_label}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(display)
            else:
                st.warning("⚠️ الرجاء إدخال المبلغ")
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 6: الاحتيال ======
    with t6:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>🔍 تدقيق وكشف الاحتيال</h3><p>فحص القيود واكتشاف الأنماط المشبوهة</p></div>', unsafe_allow_html=True)
        if st.button("🕵️ تدقيق شامل", type="primary"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق حسابات جنائي. افحص القيود التالية بحثاً عن احتيال:\n{df.to_string()}\nقدم تقريراً بالعربية."""
                with st.spinner("🔍 تدقيق..."):
                    ans = query_groq(prompt, "افحص", model=model, max_tokens=1500)
                glass(ans)
            else:
                st.info("لا قيود")
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 7: التنبؤات ======
    with t7:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>🔮 تنبؤات وتخطيط مالي</h3><p>توقعات المبيعات والتدفقات النقدية</p></div>', unsafe_allow_html=True)
        period = st.selectbox("فترة التخطيط", ["الشهر القادم", "الربع القادم", "السنة القادمة"], key="fp")
        if st.button("🔮 ابدأ التخطيط", type="primary"):
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"""أنت مخطط مالي استراتيجي. قدم توقعات للفترة: {period}.\nالبيانات:\n{d}\nقدم خطة بالعربية."""
            with st.spinner("🔮 تخطيط..."):
                ans = query_groq(prompt, "خطط", model=model, max_tokens=1500)
            glass(ans)
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 8: التحليل ======
    with t8:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>📈 تحليل متقدم</h3><p>تقرير احترافي يشمل جميع جوانب النظام</p></div>', unsafe_allow_html=True)
        analysis_scope = st.multiselect(
            "اختر جوانب التحليل",
            ["الأداء المالي", "تحليل النسب", "اتجاهات المبيعات", "تحليل العملاء", "مراكز التكلفة", "المخزون", "الموارد البشرية"],
            default=["الأداء المالي", "تحليل النسب"])
        if st.button("🚀 توليد التقرير", type="primary"):
            data = get_comprehensive_data()
            prompt = f"""أنت محلل أعمال. قدم تقريراً شاملاً بالعربية بناءً على هذه البيانات:\n{json.dumps(data, ensure_ascii=False, default=str)}"""
            with st.spinner("🧠 تحليل..."):
                ans = query_groq(prompt, "قدم تحليلاً", model=model, max_tokens=1500)
            glass(ans)
        st.markdown('</div>', unsafe_allow_html=True)

    # ====== تبويب 9: مراكز التكلفة ======
    with t9:
        st.markdown('<div class="golden-tab-container">', unsafe_allow_html=True)
        st.markdown('<div class="golden-section-title"><h3>🎯 مراكز التكلفة</h3><p>تحليل أداء المراكز والموازنات</p></div>', unsafe_allow_html=True)
        centers = ccs.get_all_cost_centers(active_only=True)
        if centers:
            center_options = {f"{c['code']} - {c['name']}": c['id'] for c in centers}
            selected = st.selectbox("اختر مركز التكلفة", list(center_options.keys()))
            center_id = center_options[selected]
            fiscal_year = st.number_input("السنة المالية", min_value=2020, max_value=2030, value=datetime.now().year)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📊 تحليل المركز", type="primary"):
                    analysis = analyze_cost_center_performance(center_id)
                    glass(analysis)
            with c2:
                if st.button("🔍 مقارنة المراكز", type="primary"):
                    comparison = compare_cost_centers()
                    glass(comparison)
            c3, c4 = st.columns(2)
            with c3:
                if st.button("🔮 توقع المصروفات", type="primary"):
                    prediction = predict_cost_center_expenses(center_id, 3)
                    glass(prediction)
            with c4:
                if st.button("💰 تحليل الموازنة", type="primary"):
                    budget = get_cost_center_budget_analysis(center_id, fiscal_year)
                    glass(budget)
        else:
            st.warning("لا توجد مراكز تكلفة نشطة")
        st.markdown('</div>', unsafe_allow_html=True)
