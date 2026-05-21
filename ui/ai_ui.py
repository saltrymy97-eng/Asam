# ui/ai_ui.py – واجهة المساعد الذكي (زجاجية فخمة + تأكيد تسجيل القيد)
import streamlit as st
import pandas as pd
from datetime import date
import json
from services.ai_service import (
    create_accounts_table,
    query_groq,
    get_comprehensive_data,
    get_inventory_data,
    get_employee_info,
    get_recent_entries,
    get_all_accounts,
    get_conn
)

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

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🤖 المساعد الذكي XD</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">سبعة خبراء في مكان واحد لخدمة أعمالك</p>
    </div>
    """, unsafe_allow_html=True)

    create_accounts_table()

    if "GROQ_API_KEY" not in st.secrets:
        st.error("❌ الرجاء إضافة `GROQ_API_KEY` في إعدادات Streamlit Cloud (Secrets).")
        return

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🧠 مساعد محاسبي", "📊 محلل مالي", "📦 توقع المخزون",
        "💬 شات الموظفين", "📝 قيود تلقائية", "🔍 كشف الاحتيال",
        "🔮 تنبؤات مستقبلية"
    ])

    # ---------- 1. مساعد محاسبي ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>اسأل عن أي شيء في النظام</h3>", unsafe_allow_html=True)
        question = st.text_input("سؤالك:", placeholder="مثال: كم مخزون جالكسي؟", key="q1")
        if st.button("🔮 اسأل الخبير", key="ask_finance"):
            if question:
                data = get_comprehensive_data()
                data_for_qa = {k: v for k, v in data.items() if k not in ["monthly_sales", "monthly_purchases", "stock_consumption"]}
                data_str = json.dumps(data_for_qa, ensure_ascii=False, indent=2, default=str)
                prompt = f"""أنت مساعد ذكي خبير في نظام ERP. لديك البيانات التالية:\n{data_str}\nأجب عن السؤال بالعربية بناءً على هذه البيانات. إذا لم توجد إجابة، قل لا توجد معلومات كافية."""
                with st.spinner("🧠 التفكير..."):
                    answer = query_groq(prompt, question)
                st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><p style="color:{TEXT_PRIMARY}; font-size:1.1rem; margin:0;">{answer}</p></div>""", unsafe_allow_html=True)

    # ---------- 2. محلل مالي ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>تحليل القوائم المالية وتوصيات</h3>", unsafe_allow_html=True)
        if st.button("📈 حلل القوائم المالية الآن", key="analyze_fin"):
            data = get_comprehensive_data()
            prompt = f"""أنت محلل مالي خبير. حلل: الإيرادات {data['revenue']:,.2f} المصروفات {data['expenses']:,.2f} صافي الدخل {data['net_income']:,.2f} الأصول {data['assets']:,.2f} الخصوم {data['liabilities']:,.2f} حقوق الملكية {data['equity']:,.2f}. قدم تحليلاً بالعربية مع توصيات."""
            with st.spinner("📊 التحليل..."):
                analysis = query_groq(prompt, "حلل")
            st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{analysis}</div></div>""", unsafe_allow_html=True)

    # ---------- 3. توقع المخزون ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>المنتجات المتوقع نفادها</h3>", unsafe_allow_html=True)
        low, all_prods = get_inventory_data()
        if st.button("📦 توقع الطلب", key="predict_inv"):
            if all_prods:
                df = pd.DataFrame(all_prods)
                prompt = f"""أنت خبير مخزون. حلل بيانات المنتجات التالية وتوقع أيها سينفد قريباً:\n{df.to_string()}\nاذكر المنتجات المهددة بالنفاد والكميات المقترح طلبها."""
                with st.spinner("📦 التحليل..."):
                    prediction = query_groq(prompt, "توقع الطلب")
                st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{prediction}</div></div>""", unsafe_allow_html=True)
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
                with st.spinner("💬 البحث..."):
                    ans = query_groq(prompt, emp_q)
                st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><p style="color:{TEXT_PRIMARY}; font-size:1.1rem; margin:0;">{ans}</p></div>""", unsafe_allow_html=True)
            else:
                st.error("❌ لم يتم العثور على الموظف.")

    # ---------- 5. قيود تلقائية (مع زر تأكيد) ----------
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

        # 🆕 زر التأكيد النهائي
        if st.session_state.confirm_save and st.session_state.generated_entry is not None:
            st.warning("⚠️ هل أنت متأكد من تسجيل هذا القيد؟")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ نعم، سجل القيد", type="primary", key="confirm_yes"):
                    entry_data = st.session_state.generated_entry
                    conn = get_conn()
                    valid_lines = []
                    errors = []
                    for line in entry_data["lines"]:
                        account_name = line["account"]
                        acc = conn.execute("SELECT code FROM accounts WHERE name = ?", (account_name,)).fetchone()
                        if acc:
                            valid_lines.append((acc["code"], line["debit"], line["credit"]))
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
                            for code, debit, credit in valid_lines:
                                conn.execute(
                                    "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                                    (entry_id, code, debit, credit)
                                )
                            conn.commit()
                            st.success(f"✅ تم تسجيل القيد رقم {entry_id} بنجاح!")
                            st.session_state.generated_entry = None
                            st.session_state.confirm_save = False
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"فشل التسجيل: {e}")
                            st.session_state.confirm_save = False
                    finally:
                        conn.close()
            with col2:
                if st.button("❌ إلغاء", key="confirm_no"):
                    st.session_state.confirm_save = False
                    st.rerun()

        if generate_btn and text:
            accounts = get_all_accounts()
            acc_list = "\n".join([f"{a['code']} - {a['name']}" for a in accounts]) if accounts else "لا توجد حسابات مضافة بعد"
            prompt = f"""أنت محاسب خبير. حول العملية إلى قيد محاسبي مركب.\nالحسابات المتاحة:\n{acc_list}\nأعد القيد بالصيغة:\nمدين | اسم الحساب | المبلغ\nدائن | اسم الحساب | المبلغ\nيجب أن يتوازن القيد. العملية: {text}"""
            with st.spinner("📝 جاري إنشاء القيد..."):
                entry_text = query_groq(prompt, text)
            st.code(entry_text)

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
                prompt = f"""أنت مدقق حسابات. افحص القيود التالية وابحث عن أي شذوذ:\n{df.to_string()}\nاذكر القيود المشبوهة مع السبب."""
                with st.spinner("🔍 الفحص..."):
                    audit = query_groq(prompt, "افحص")
                st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1.1rem;">{audit}</div></div>""", unsafe_allow_html=True)
            else:
                st.info("ℹ️ لا توجد قيود لفحصها.")

    # ---------- 7. 🔮 تنبؤات مستقبلية ----------
    with tab7:
        st.markdown(f"<h3 style='color:{ACCENT_CYAN};'>🔮 تنبؤات مستقبلية شاملة</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:{TEXT_SECONDARY};'>تحليل البيانات الحالية وتوقع المبيعات والتدفق النقدي والمخزون والأرباح للفترة القادمة</p>", unsafe_allow_html=True)
        
        forecast_period = st.selectbox("فترة التنبؤ", ["الشهر القادم", "الـ 3 أشهر القادمة", "الـ 6 أشهر القادمة", "السنة القادمة"], key="forecast_period")
        
        if st.button("🔮 ابدأ التنبؤ", key="start_forecast", type="primary"):
            data = get_comprehensive_data()
            data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
            
            prompt = f"""أنت خبير تحليل مالي وتخطيط أعمال. لديك جميع بيانات النظام التالية:\n{data_str}\nالمطلوب: تقديم تنبؤات شاملة للفترة: {forecast_period}.\nقم بتقديم التحليل التالي بالعربية، مع أرقام تقديرية مبنية على البيانات الحالية والاتجاهات:\n1. توقع المبيعات\n2. توقع التدفق النقدي\n3. توقع نفاد المخزون\n4. توقع الأرباح\n5. المخاطر والتحديات"""
            
            with st.spinner("🔮 جاري تحليل البيانات وتوليد التنبؤات..."):
                forecast = query_groq(prompt, "قدم تنبؤات شاملة", max_tokens=2500)
            
            st.markdown(f"""<div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:2rem; margin-top:1rem; box-shadow:{GLASS_SHADOW};"><div style="color:{TEXT_PRIMARY}; font-size:1rem; line-height:1.8;">{forecast}</div></div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown(f"<h4 style='color:{TEXT_PRIMARY};'>📊 ملخص المؤشرات الحالية</h4>", unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("الإيرادات الحالية", f"{data['revenue']:,.0f}")
            with col2:
                st.metric("صافي الدخل الحالي", f"{data['net_income']:,.0f}")
            with col3:
                st.metric("عدد المنتجات", len(data['products']))
            with col4:
                st.metric("عدد العملاء", len(data['customers']))
