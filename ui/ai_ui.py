# ui/ai_ui.py – واجهة المساعد الذكي المحسّنة (زجاجية فخمة + نماذج + سجل + تحليل عميق)
import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import html  # لتعقيم النصوص ومنع XSS
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

# ========== دالة مساعدة لعرض نص آمن داخل HTML ==========
def safe_html(content: str) -> str:
    """تعقيم النص ليكون آمنًا عند تضمينه في HTML مع الحفاظ على الأسطر الجديدة."""
    if not content:
        return ""
    escaped = html.escape(content)
    # تحويل الأسطر الجديدة إلى <br> للعرض داخل HTML
    return escaped.replace("\n", "<br>")

# ========== ألوان التصميم ==========
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
ACCENT_PINK = "#EC4899"

# ========== تعريف النماذج المتاحة ==========
AVAILABLE_MODELS = {
    "Llama 3.3 70B (الأسرع)": "llama-3.3-70b-versatile",
    "Mixtral 8x7B (متوازن)": "mixtral-8x7b-32768",
    "Llama 2 70B (دقيق)": "llama2-70b-4096"
}

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🤖 المساعد الذكي XD</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">سبعة خبراء مع تحليلات عميقة وسجل محادثات</p>
    </div>
    """, unsafe_allow_html=True)

    create_ai_tables()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("❌ الرجاء إضافة `GROQ_API_KEY` في إعدادات Streamlit Cloud (Secrets).")
        return

    # ---------- تخزين البيانات الشاملة مرة واحدة لكل دورة لتقليل الاستعلامات ----------
    if "comprehensive_data" not in st.session_state:
        st.session_state.comprehensive_data = get_comprehensive_data()

    # ---------- إعدادات النموذج والسجل ----------
    with st.sidebar:
        st.markdown(f"### ⚙️ إعدادات المساعد")
        selected_model_name = st.selectbox("اختر النموذج", list(AVAILABLE_MODELS.keys()))
        selected_model = AVAILABLE_MODELS[selected_model_name]

        st.markdown("---")
        st.markdown(f"### 📝 سجل المحادثات")
        if st.button("🆕 محادثة جديدة"):
            st.session_state.active_session = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            st.rerun()

        sessions = get_chat_sessions()
        if sessions:
            for s in sessions:
                if st.button(f"{s['session_id']} ({s['message_count']} رسالة)", key=s['session_id']):
                    st.session_state.active_session = s['session_id']
        else:
            st.info("لا توجد محادثات سابقة")

    # ---------- جلسة المحادثة النشطة ----------
    if "active_session" not in st.session_state:
        st.session_state.active_session = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال",
        "🔮 تنبؤات مستقبلية", "📈 تحليل عميق"
    ])

    # ---------- 1. مساعد محاسبي ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>اسأل عن أي شيء في النظام</h3>", unsafe_allow_html=True)

        # عرض السجل السابق بترتيب صحيح (الأقدم فالأحدث)
        history = get_chat_history(st.session_state.active_session, 10)
        # إذا كان get_chat_history تُرجع الأحدث أولاً، نعكس؛ وإلا نعرض كما هي
        # هنا نفترض أن البيانات تأتي تصاعديًا (الأقدم أولاً) – نعرض كما هي
        for h in history:
            if h['role'] == 'user':
                st.chat_message("user").write(h['content'])
            else:
                st.chat_message("assistant").write(h['content'])

        question = st.chat_input("اكتب سؤالك هنا...")
        if question:
            st.chat_message("user").write(question)
            save_chat_history(st.session_state.active_session, "user", question, selected_model, "مساعد محاسبي")

            data = st.session_state.comprehensive_data
            data_for_qa = {k: v for k, v in data.items() if k not in ["monthly_sales", "monthly_purchases"]}
            data_str = json.dumps(data_for_qa, ensure_ascii=False, indent=2, default=str)
            prompt = f"""أنت مساعد ذكي خبير في نظام ERP. لديك البيانات المالية والإدارية التالية:
{data_str}

أجب عن السؤال التالي بالعربية بناءً على هذه البيانات. إذا لم توجد إجابة، قل لا توجد معلومات كافية. لا تختلق بيانات."""

            try:
                with st.spinner("🧠 التفكير..."):
                    answer = query_groq(prompt, question, model=selected_model)
                st.chat_message("assistant").write(answer)
                save_chat_history(st.session_state.active_session, "assistant", answer, selected_model, "مساعد محاسبي")
            except Exception as e:
                st.error(f"❌ حدث خطأ أثناء الاتصال بالمساعد: {str(e)}")

    # ---------- 2. محلل مالي ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تحليل القوائم المالية وتوصيات</h3>", unsafe_allow_html=True)
        if st.button("📈 حلل القوائم المالية الآن", key="analyze_fin"):
            data = st.session_state.comprehensive_data
            ratios = get_financial_ratios()

            prompt = f"""أنت محلل مالي خبير. حلل البيانات التالية وقدم توصيات تفصيلية:
- الإيرادات: {data.get('revenue', 0):,.2f}
- المصروفات: {data.get('expenses', 0):,.2f}
- صافي الدخل: {data.get('net_income', 0):,.2f}
- الأصول: {data.get('assets', 0):,.2f}
- الخصوم: {data.get('liabilities', 0):,.2f}
- حقوق الملكية: {data.get('equity', 0):,.2f}
- النسب المالية: {json.dumps(ratios, ensure_ascii=False)}

قدم تحليلاً شاملاً بالعربية يشمل:
1. تقييم الأداء المالي
2. تحليل النسب المالية
3. نقاط القوة والضعف
4. توصيات قابلة للتنفيذ"""

            try:
                with st.spinner("📊 التحليل..."):
                    analysis = query_groq(prompt, "حلل", model=selected_model, max_tokens=2000)
                # عرض آمن داخل التصميم الزجاجي
                safe_analysis = safe_html(analysis)
                st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{safe_analysis}</div></div>""", unsafe_allow_html=True)
                save_chat_history(st.session_state.active_session, "assistant", analysis, selected_model, "محلل مالي")
            except Exception as e:
                st.error(f"❌ خطأ في التحليل المالي: {str(e)}")

    # ---------- 3. توقع المخزون ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>المنتجات المتوقع نفادها</h3>", unsafe_allow_html=True)
        low, all_prods = get_inventory_data()
        if st.button("📦 توقع الطلب", key="predict_inv"):
            if all_prods:
                df = pd.DataFrame(all_prods)
                prompt = f"""أنت خبير مخزون. حلل بيانات المنتجات التالية وتوقع أيها سينفد قريباً:\n{df.to_string()}\nاذكر المنتجات المهددة بالنفاد والكميات المقترح طلبها."""
                try:
                    with st.spinner("📦 التحليل..."):
                        prediction = query_groq(prompt, "توقع الطلب", model=selected_model)
                    safe_pred = safe_html(prediction)
                    st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{safe_pred}</div></div>""", unsafe_allow_html=True)
                    save_chat_history(st.session_state.active_session, "assistant", prediction, selected_model, "توقع المخزون")
                except Exception as e:
                    st.error(f"❌ خطأ في توقع المخزون: {str(e)}")
            else:
                st.info("لا توجد منتجات لتحليلها.")
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
                try:
                    with st.spinner("💬 البحث..."):
                        ans = query_groq(prompt, emp_q, model=selected_model)
                    safe_ans = safe_html(ans)
                    st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><p style="color:{TEXT_PRIMARY}; font-size:1.1rem; margin:0;">{safe_ans}</p></div>""", unsafe_allow_html=True)
                    save_chat_history(st.session_state.active_session, "user", f"{emp_name}: {emp_q}", selected_model, "شات الموظفين")
                    save_chat_history(st.session_state.active_session, "assistant", ans, selected_model, "شات الموظفين")
                except Exception as e:
                    st.error(f"❌ خطأ في شات الموظفين: {str(e)}")
            else:
                st.error("❌ لم يتم العثور على الموظف.")

    # ---------- 5. قيود تلقائية ----------
    with tab5:
        st.markdown(f"<h3 style='color:{ACCENT_RED};'>إنشاء قيد محاسبي مركب بلغة طبيعية</h3>", unsafe_allow_html=True)
        text = st.text_area("اكتب العملية:", placeholder="مثال: اشتريت بضاعة بـ 5000 ومصاريف شحن بـ 200، دفعت 3000 نقداً والباقي على الحساب", key="entry_text")

        if "generated_entry" not in st.session_state:
            st.session_state.generated_entry = None
        if "confirm_save" not in st.session_state:
            st.session_state.confirm_save = False

        col1, col2 = st.columns([1, 1])
        with col1:
            generate_btn = st.button("📝 إنشاء القيد المركب", key="create_entry")
        with col2:
            if st.session_state.generated_entry is not None and not st.session_state.confirm_save:
                if st.button("💾 تسجيل القيد في النظام", type="primary", key="save_entry"):
                    st.session_state.confirm_save = True
                    st.rerun()

        # تأكيد الحفظ
        if st.session_state.confirm_save and st.session_state.generated_entry is not None:
            st.warning("⚠️ هل أنت متأكد من تسجيل هذا القيد؟")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ نعم، سجل القيد", type="primary", key="confirm_yes"):
                    entry_data = st.session_state.generated_entry
                    conn = None
                    try:
                        conn = get_conn()
                        valid_lines = []
                        errors = []
                        for line in entry_data["lines"]:
                            account_name = line["account"]
                            # البحث عن الحساب بالاسم (تأكيد وجوده)
                            acc = conn.execute("SELECT name FROM accounts WHERE name = ?", (account_name,)).fetchone()
                            if acc:
                                # نخزن اسم الحساب كما هو موجود في القيد
                                valid_lines.append((acc["name"], line["debit"], line["credit"]))
                            else:
                                errors.append(f"الحساب '{account_name}' غير موجود في شجرة الحسابات.")

                        if errors:
                            for err in errors:
                                st.error(err)
                            st.session_state.confirm_save = False
                        else:
                            try:
                                conn.execute("BEGIN")
                                desc = f"قيد ذكي: {text[:50]}"
                                cur = conn.execute(
                                    "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
                                    (date.today().strftime("%Y-%m-%d"), desc, "")
                                )
                                entry_id = cur.lastrowid
                                for acc_name, debit, credit in valid_lines:
                                    conn.execute(
                                        "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                                        (entry_id, acc_name, debit, credit)
                                    )
                                conn.commit()
                                st.success(f"✅ تم تسجيل القيد رقم {entry_id} بنجاح!")
                                save_chat_history(st.session_state.active_session, "assistant", f"تم تسجيل القيد رقم {entry_id}: {text[:50]}", selected_model, "قيود تلقائية")
                                # إعادة تعيين الحالة
                                st.session_state.generated_entry = None
                                st.session_state.confirm_save = False
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"فشل التسجيل: {e}")
                                st.session_state.confirm_save = False
                    except Exception as e:
                        st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
                        st.session_state.confirm_save = False
                    finally:
                        if conn:
                            conn.close()
            with col2:
                if st.button("❌ إلغاء", key="confirm_no"):
                    st.session_state.confirm_save = False
                    st.rerun()

        # توليد القيد
        if generate_btn and text:
            accounts = get_all_accounts()
            acc_list = "\n".join([f"{a['code']} - {a['name']}" for a in accounts]) if accounts else "لا توجد حسابات مضافة بعد"
            prompt = f"""أنت محاسب خبير. حول العملية إلى قيد محاسبي مركب.\nالحسابات المتاحة:\n{acc_list}\nأعد القيد بالصيغة:\nمدين | اسم الحساب | المبلغ\nدائن | اسم الحساب | المبلغ\nيجب أن يتوازن القيد. العملية: {text}"""
            try:
                with st.spinner("📝 جاري إنشاء القيد..."):
                    entry_text = query_groq(prompt, text, model=selected_model)
                st.code(entry_text)
                save_chat_history(st.session_state.active_session, "assistant", entry_text, selected_model, "قيود تلقائية")

                # تحليل المخرجات
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
                    st.session_state.confirm_save = False
                    st.rerun()
                else:
                    st.error("لم يتم التعرف على أي سطور قيد صحيحة من رد النموذج.")
            except Exception as e:
                st.error(f"❌ خطأ في إنشاء القيد: {str(e)}")

        # عرض القيد المقترح
        if st.session_state.generated_entry is not None:
            lines = st.session_state.generated_entry["lines"]
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY}; margin-top:1rem;'>القيد المقترح</h4>", unsafe_allow_html=True)
            df = pd.DataFrame(lines)
            total_debit = df["debit"].sum()
            total_credit = df["credit"].sum()
            summary = pd.DataFrame([{"account": "المجموع", "debit": total_debit, "credit": total_credit}])
            df_display = pd.concat([df, summary], ignore_index=True)
            df_display = df_display.rename(columns={"account": "الحساب", "debit": "مدين", "credit": "دائن"})
            st.dataframe(
                df_display.style.format({"مدين": "{:,.2f}", "دائن": "{:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )

    # ---------- 6. كشف الاحتيال ----------
    with tab6:
        st.markdown(f"<h3 style='color:#EC4899;'>فحص القيود المشبوهة</h3>", unsafe_allow_html=True)
        if st.button("🕵️ افحص القيود", key="audit"):
            entries = get_recent_entries()
            if entries:
                df = pd.DataFrame(entries)
                prompt = f"""أنت مدقق حسابات. افحص القيود التالية وابحث عن أي شذوذ أو علامات احتيال:\n{df.to_string()}\nاذكر القيود المشبوهة مع السبب."""
                try:
                    with st.spinner("🔍 الفحص..."):
                        audit = query_groq(prompt, "افحص", model=selected_model)
                    safe_audit = safe_html(audit)
                    st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{safe_audit}</div></div>""", unsafe_allow_html=True)
                    save_chat_history(st.session_state.active_session, "assistant", audit, selected_model, "كشف الاحتيال")
                except Exception as e:
                    st.error(f"❌ خطأ في كشف الاحتيال: {str(e)}")
            else:
                st.info("ℹ️ لا توجد قيود لفحصها.")

    # ---------- 7. تنبؤات مستقبلية ----------
    with tab7:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>🔮 تنبؤات مستقبلية شاملة</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:{TEXT_SECONDARY};'>تحليل البيانات الحالية وتوقع المبيعات والتدفق النقدي والمخزون والأرباح للفترة القادمة</p>", unsafe_allow_html=True)

        forecast_period = st.selectbox("فترة التنبؤ", ["الشهر القادم", "الـ 3 أشهر القادمة", "الـ 6 أشهر القادمة", "السنة القادمة"], key="forecast_period")

        if st.button("🔮 ابدأ التنبؤ", key="start_forecast", type="primary"):
            data = st.session_state.comprehensive_data
            data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)

            prompt = f"""أنت خبير تحليل مالي وتخطيط أعمال. لديك جميع بيانات النظام التالية:\n{data_str}\nالمطلوب: تقديم تنبؤات شاملة للفترة: {forecast_period}.\nقم بتقديم التحليل التالي بالعربية، مع أرقام تقديرية مبنية على البيانات الحالية والاتجاهات:\n1. توقع المبيعات\n2. توقع التدفق النقدي\n3. توقع نفاد المخزون\n4. توقع الأرباح\n5. المخاطر والتحديات"""

            try:
                with st.spinner("🔮 جاري تحليل البيانات وتوليد التنبؤات..."):
                    forecast = query_groq(prompt, "قدم تنبؤات شاملة", model=selected_model, max_tokens=2500)
                safe_forecast = safe_html(forecast)
                st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:2rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1rem; line-height:1.8;">{safe_forecast}</div></div>""", unsafe_allow_html=True)
                save_chat_history(st.session_state.active_session, "assistant", forecast, selected_model, "تنبؤات مستقبلية")
            except Exception as e:
                st.error(f"❌ خطأ في التنبؤات: {str(e)}")

            # ملخص المؤشرات الحالية
            st.markdown("---")
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📊 ملخص المؤشرات الحالية</h4>", unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("الإيرادات الحالية", f"{data.get('revenue', 0):,.0f}")
            with col2:
                st.metric("صافي الدخل الحالي", f"{data.get('net_income', 0):,.0f}")
            with col3:
                st.metric("عدد المنتجات", len(data.get('products', [])))
            with col4:
                st.metric("عدد العملاء", len(data.get('customers', [])))

    # ---------- 8. تحليل عميق ----------
    with tab8:
        st.markdown(f"<h3 style='color:{ACCENT_PINK};'>📈 تحليل مالي عميق</h3>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 عرض النسب المالية", use_container_width=True):
                try:
                    ratios = get_financial_ratios()
                    for key, value in ratios.items():
                        st.metric(key, value)
                except Exception as e:
                    st.error(f"خطأ في جلب النسب: {e}")

        with col2:
            if st.button("📈 تحليل الاتجاهات", use_container_width=True):
                try:
                    trends = get_trend_analysis()
                    if trends:
                        df_trends = pd.DataFrame(trends)
                        st.dataframe(df_trends, use_container_width=True, hide_index=True)
                    else:
                        st.info("لا توجد بيانات اتجاهات")
                except Exception as e:
                    st.error(f"خطأ في تحليل الاتجاهات: {e}")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏆 أفضل العملاء", use_container_width=True):
                try:
                    top_cust = get_top_customers()
                    if top_cust:
                        st.dataframe(pd.DataFrame(top_cust), use_container_width=True, hide_index=True)
                    else:
                        st.info("لا توجد بيانات عملاء")
                except Exception as e:
                    st.error(f"خطأ: {e}")

        with col2:
            if st.button("🏢 أفضل الموردين", use_container_width=True):
                try:
                    top_supp = get_top_suppliers()
                    if top_supp:
                        st.dataframe(pd.DataFrame(top_supp), use_container_width=True, hide_index=True)
                    else:
                        st.info("لا توجد بيانات موردين")
                except Exception as e:
                    st.error(f"خطأ: {e}")
