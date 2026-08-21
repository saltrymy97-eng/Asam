# ui/ai_ui.py – واجهة المساعد الذكي بتصميم التقارير الذهبية (نسخة EXE)
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime
from services.ai_service import (
    GROQ_API_KEY, # تم استيراد المفتاح مباشرة ليعمل كـ EXE
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

# ========== ألوان التصميم الذهبي الفاخر (مطابقة لوحدة التقارير) ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(212, 175, 55, 0.3)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_CYAN = "#06B6D4"

# تحديث النماذج لتتوافق مع طبقة الخدمات الجديدة
AVAILABLE_MODELS = {
    "GPT OSS 120B (عالي الدقة)": "openai/gpt-oss-120b",
    "Mixtral 8x7B (سريع)": "mixtral-8x7b-32768",
}

# ========== 🎤 معالجة الصوت ==========
def audio_to_text(audio_file):
    if audio_file is None:
        return ""
    try:
        # استخدام المفتاح المضمن في الكود مباشرة
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
            if text and not text.startswith("❌"):
                st.success(f"✅ {text}")
                return text
            else:
                st.error(text)
    return ""

def glass_card(icon, title, desc, color):
    """بطاقة زجاجية بنفس تصميم وحدة التقارير"""
    return f"""
    <div style="
        background: linear-gradient(145deg, rgba(20, 30, 50, 0.8), rgba(10, 15, 30, 0.9));
        backdrop-filter:blur(10px);
        border:1px solid {GLASS_BORDER}; border-radius:20px;
        padding:1.5rem; text-align:center; box-shadow:{GLASS_SHADOW};
        margin-bottom:1rem;
    ">
        <div style="font-size:2.5rem; margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{color}; font-size:1.2rem; font-weight:700;">{title}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.85rem;">{desc}</div>
    </div>
    """

def show():
    # ===== تصميم ذهبي فاخر (مطابق لوحدة التقارير) =====
    st.markdown("""
    <style>
    .stButton > button {
        background: linear-gradient(135deg, rgba(212,175,55,0.2), rgba(212,175,55,0.05)) !important;
        border: 1px solid rgba(212,175,55,0.4) !important;
        color: #FCF6BA !important;
        font-weight: 700 !important;
        transition: all 0.3s ease !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #D4AF37, #AA771C) !important;
        color: #000 !important;
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(212,175,55,0.4) !important;
    }
    .report-download-btn > button {
        background: rgba(16, 185, 129, 0.2) !important;
        border: 1px solid rgba(16, 185, 129, 0.5) !important;
        color: #10B981 !important;
    }
    .report-download-btn > button:hover {
        background: #10B981 !important;
        color: #fff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    create_ai_tables()

    # تمت إزالة فحص st.secrets لأن المفتاح أصبح مضمناً للعمل كـ exe

    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")
        model_name = st.selectbox("اختر النموذج", list(AVAILABLE_MODELS.keys()))
        model = AVAILABLE_MODELS[model_name]

    if "active_session" not in st.session_state:
        st.session_state.active_session = f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ===== الهيدر الذهبي (مطابق للتقارير) =====
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{GOLD}; font-size:2.8rem; margin:0; text-shadow:0 0 20px rgba(212,175,55,0.3);">🤖 المساعد الذكي AI</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">تسعة خبراء مع تحليلات عميقة وتوصيات ذكية</p>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs([
        "🧠 مساعد", "📊 محلل", "📦 مخزون", "💬 موظفين", "📝 قيود", "🔍 احتيال", "🔮 تنبؤات", "📈 تحليل", "🎯 مراكز تكلفة"
    ])

    # ====== تبويب 1: المساعد ======
    with t1:
        st.markdown(f"<h3 style='color:{GOLD};'>اسأل عن أي شيء في نظامك</h3>", unsafe_allow_html=True)
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

    # ====== تبويب 2: المحلل ======
    with t2:
        st.markdown(f"<h3 style='color:{GOLD};'>تحليل مالي شامل وتوصيات</h3>", unsafe_allow_html=True)
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
            st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{ans}</div>""", unsafe_allow_html=True)

    # ====== تبويب 3: المخزون ======
    with t3:
        st.markdown(f"<h3 style='color:{GOLD};'>تحليل المخزون وتوقع النفاد</h3>", unsafe_allow_html=True)
        low, allp = get_inventory_data()
        if st.button("📦 تحليل المخزون", type="primary"):
            if allp:
                df = pd.DataFrame(allp)
                prompt = f"""أنت خبير إدارة مخزون. حلل البيانات:\n{df.to_string()}\nقدم تحليلاً بالعربية."""
                with st.spinner("📦 تحليل المخزون..."):
                    ans = query_groq(prompt, "حلل المخزون", model=model, max_tokens=1500)
                st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{ans}</div>""", unsafe_allow_html=True)
        if low:
            st.warning("⚠️ منتجات تحت الحد الأدنى:")
            st.dataframe(pd.DataFrame(low))

    # ====== تبويب 4: الموظفين ======
    with t4:
        st.markdown(f"<h3 style='color:{GOLD};'>استفسارات الموظفين</h3>", unsafe_allow_html=True)
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
                st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{ans}</div>""", unsafe_allow_html=True)
            else:
                st.error("غير موجود")

    # ====== تبويب 5: القيود ======
    with t5:
        st.markdown(f"<h3 style='color:{GOLD};'>توليد قيود محاسبية ذكية</h3>", unsafe_allow_html=True)
        operations = get_available_operations()
        selected_op = st.selectbox("🎯 اختر نوع العملية المالية", options=operations, key="template_op")
        st.caption(f"📌 {get_operation_description(selected_op)}")
        st.markdown("---")

        if is_mixed_operation(selected_op):
            c1, c2, c3 = st.columns(3)
            with c1: total_amount = st.number_input("💰 المبلغ الإجمالي", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with c2: cash_amount = st.number_input("💵 الجزء النقدي", min_value=0.0, step=100.0, format="%.2f", key="ca")
            with c3: credit_amount = st.number_input("📋 الجزء الآجل", min_value=0.0, step=100.0, format="%.2f", key="cra")
            vat_rate = expense_name = None
        elif is_vat_operation(selected_op):
            c1, c2 = st.columns(2)
            with c1: total_amount = st.number_input("💰 المبلغ شامل الضريبة", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with c2: vat_rate = st.number_input("📊 نسبة الضريبة (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="vr") / 100
            cash_amount = credit_amount = expense_name = None
        elif selected_op == "سداد مصروف":
            c1, c2 = st.columns(2)
            with c1: total_amount = st.number_input("💰 المبلغ", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with c2: expense_name = st.text_input("📝 اسم المصروف", value="كهرباء", key="en")
            cash_amount = credit_amount = vat_rate = None
        elif is_inventory_adjustment(selected_op):
            c1, c2 = st.columns(2)
            with c1: total_amount = st.number_input("💰 قيمة التسوية", min_value=0.0, step=100.0, format="%.2f", key="ta")
            with c2:
                adj_type = st.selectbox("📈 نوع التسوية", ["عجز (نقص)", "فائض (زيادة)"], key="adj")
                if adj_type == "عجز (نقص)": adjustment_side, inventory_side = "debit", "credit"
                else: adjustment_side, inventory_side = "credit", "debit"
            cash_amount = credit_amount = vat_rate = expense_name = None
        else:
            total_amount = st.number_input("💰 المبلغ", min_value=0.0, step=100.0, format="%.2f", key="ta")
            cash_amount = credit_amount = vat_rate = expense_name = adjustment_side = inventory_side = None

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🪄 توليد القيد المحاسبي", type="primary", use_container_width=True):
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
                    <div style="background:linear-gradient(145deg, rgba(212,175,55,0.15), rgba(212,175,55,0.05)); 
                                border:1px solid {confidence_color}; border-radius:16px; padding:16px 20px; 
                                margin-top:16px; display:flex; align-items:center; gap:14px;">
                        <div style="background:{confidence_color}; width:12px; height:12px; border-radius:50%;"></div>
                        <span style="color:{TEXT_PRIMARY}; font-weight:700;">📊 نسبة الثقة: {confidence}%</span>
                        <span style="background:{confidence_color}20; color:{confidence_color}; padding:4px 12px; 
                                     border-radius:20px; font-weight:700;">{confidence_label}</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(display)
            else:
                st.warning("⚠️ الرجاء إدخال المبلغ")

    # ====== تبويب 6: الاحتيال ======
    with t6:
        st.markdown(f"<h3 style='color:{GOLD};'>تدقيق وكشف الاحتيال</h3>", unsafe_allow_html=True)
        if st.button("🕵️ تدقيق شامل", type="primary"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق حسابات جنائي. افحص القيود:\n{df.to_string()}\nقدم تقريراً بالعربية."""
                with st.spinner("🔍 تدقيق..."):
                    ans = query_groq(prompt, "افحص", model=model, max_tokens=1500)
                st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{ans}</div>""", unsafe_allow_html=True)
            else:
                st.info("لا قيود")

    # ====== تبويب 7: التنبؤات ======
    with t7:
        st.markdown(f"<h3 style='color:{GOLD};'>🔮 تنبؤات وتخطيط مالي</h3>", unsafe_allow_html=True)
        period = st.selectbox("فترة التخطيط", ["الشهر القادم", "الربع القادم", "السنة القادمة"], key="fp")
        if st.button("🔮 ابدأ التخطيط", type="primary"):
            data = get_comprehensive_data()
            d = json.dumps(data, ensure_ascii=False, default=str)
            prompt = f"""أنت مخطط مالي استراتيجي. قدم توقعات للفترة: {period}.\nالبيانات:\n{d}\nقدم خطة بالعربية."""
            with st.spinner("🔮 تخطيط..."):
                ans = query_groq(prompt, "خطط", model=model, max_tokens=1500)
            st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{ans}</div>""", unsafe_allow_html=True)

    # ====== تبويب 8: التحليل ======
    with t8:
        st.markdown(f"<h3 style='color:{GOLD};'>📈 تحليل مالي وتشغيلي متقدم</h3>", unsafe_allow_html=True)
        st.caption("تقرير احترافي يولده الذكاء الاصطناعي بناءً على جميع بيانات النظام")
        analysis_scope = st.multiselect(
            "اختر جوانب التحليل",
            ["الأداء المالي", "تحليل النسب", "اتجاهات المبيعات", "تحليل العملاء", "مراكز التكلفة", "المخزون", "الموارد البشرية"],
            default=["الأداء المالي", "تحليل النسب"])
        if st.button("🚀 توليد التقرير", type="primary"):
            data = get_comprehensive_data()
            prompt = f"""أنت محلل أعمال. قدم تقريراً شاملاً بالعربية بناءً على:\n{json.dumps(data, ensure_ascii=False, default=str)}"""
            with st.spinner("🧠 تحليل..."):
                ans = query_groq(prompt, "قدم تحليلاً", model=model, max_tokens=1500)
            st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{ans}</div>""", unsafe_allow_html=True)

    # ====== تبويب 9: مراكز التكلفة ======
    with t9:
        st.markdown(f"<h3 style='color:{GOLD};'>🎯 تحليل مراكز التكلفة بالذكاء الاصطناعي</h3>", unsafe_allow_html=True)
        centers = ccs.get_all_cost_centers(active_only=True)
        if centers:
            center_options = {f"{c['code']} - {c['name']}": c['id'] for c in centers}
            selected = st.selectbox("اختر مركز التكلفة", list(center_options.keys()))
            center_id = center_options[selected]
            fiscal_year = st.number_input("السنة المالية لتحليل الموازنة", min_value=2020, max_value=2030, value=datetime.now().year)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📊 تحليل أداء المركز", type="primary"):
                    analysis = analyze_cost_center_performance(center_id)
                    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{analysis}</div>""", unsafe_allow_html=True)
            with c2:
                if st.button("🔍 مقارنة جميع المراكز", type="primary"):
                    comparison = compare_cost_centers()
                    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{comparison}</div>""", unsafe_allow_html=True)
            c3, c4 = st.columns(2)
            with c3:
                months_ahead = st.selectbox("عدد الأشهر للتنبؤ", [1, 3, 6], key="months_cc")
                if st.button("🔮 توقع المصروفات المستقبلية", type="primary"):
                    prediction = predict_cost_center_expenses(center_id, months=months_ahead)
                    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{prediction}</div>""", unsafe_allow_html=True)
            with c4:
                if st.button("💰 تحليل انحرافات الموازنة", type="primary"):
                    budget = get_cost_center_budget_analysis(center_id, fiscal_year)
                    st.markdown(f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{TEXT_PRIMARY};font-size:1.1rem;">{budget}</div>""", unsafe_allow_html=True)
        else:
            st.warning("لا توجد مراكز تكلفة نشطة")
