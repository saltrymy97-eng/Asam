import streamlit as st
import pandas as pd
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
import zipfile
import io
from datetime import datetime
import time

# --- استيراد مكتبات LangChain و Groq ---
# سنقوم باستيراد المكتبات المطلوبة فقط عند الحاجة لتجنب الأخطاء إذا لم تكن مثبتة
try:
    from langchain_experimental.agents import create_pandas_dataframe_agent
    from langchain_groq import ChatGroq
    langchain_available = True
except ImportError:
    langchain_available = False
    st.error("⚠️ مكتبات LangChain و Groq غير مثبتة. يرجى تشغيل `pip install -r requirements.txt`")

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="مساعد مدير الفرع الذكي",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- دوال معالجة اللغة العربية (بدون تغيير) ---
def process_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

class ArabicPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        header_text = process_arabic_text("البنك الأهلي - إشعار تحويل راتب")
        self.cell(0, 10, header_text, 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        footer_text = process_arabic_text(f"تم الإنشاء تلقائياً - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self.cell(0, 10, footer_text, 0, 0, 'C')

def create_salary_letter(employee_name, account_number, salary_amount, month_name):
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    date_text = process_arabic_text(f"التاريخ: {datetime.now().strftime('%Y/%m/%d')}")
    pdf.cell(0, 10, date_text, 0, 1, 'R')
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
    greeting = process_arabic_text(f"السيد/ {employee_name}")
    pdf.cell(0, 10, greeting, 0, 1, 'R')
    pdf.ln(5)
    pdf.set_font('Arial', '', 12)
    message = f"تم تحويل راتبك لشهر {month_name} وقدره {salary_amount:,.2f} ريال إلى حسابك رقم {account_number}."
    arabic_message = process_arabic_text(message)
    pdf.multi_cell(0, 10, arabic_message, 0, 'R')
    pdf.ln(15)
    pdf.set_font('Arial', '', 12)
    signature = process_arabic_text("مع أطيب التحيات،")
    pdf.cell(0, 10, signature, 0, 1, 'R')
    pdf.cell(0, 10, process_arabic_text("مدير الفرع"), 0, 1, 'R')
    return pdf

# --- تهيئة حالة الجلسة (Session State) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "groq_agent" not in st.session_state:
    st.session_state.groq_agent = None
if "df" not in st.session_state:
    st.session_state.df = None

# --- واجهة المستخدم الرئيسية ---
st.title("🏦 مساعد مدير الفرع الذكي")
st.markdown("---")

# --- الشريط الجانبي (Sidebar) ---
with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    
    # 1. إعدادات الشهر ونموذج الملف
    months = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]
    selected_month = st.selectbox("اختر الشهر:", months)

    # تحميل نموذج Excel
    sample_data = pd.DataFrame({
        'الاسم': ['أحمد محمد', 'فاطمة علي', 'عمر خالد'],
        'رقم الحساب': ['SA1234567890', 'SA0987654321', 'SA1122334455'],
        'الراتب': [15000, 12000, 18000]
    })
    csv = sample_data.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 تحميل نموذج Excel",
        data=csv,
        file_name="نموذج_الرواتب.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # 2. قسم مساعد Groq الذكي
    st.header("🤖 مساعد Groq الذكي")
    
    if not langchain_available:
        st.warning("تأكد من تثبيت المتطلبات لاستخدام المساعد الذكي.")
    else:
        # إدخال مفتاح API
        groq_api_key = st.text_input("أدخل مفتاح Groq API:", type="password", help="يمكنك الحصول عليه من [Groq Console](https://console.groq.com/keys)")
        # اختيار النموذج
        model_name = st.selectbox(
            "اختر نموذج Groq:",
            [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it"
            ],
            help="نموذج `llama-3.3-70b-versatile` هو الأقوى، بينما `llama-3.1-8b-instant` أسرع وأقل استهلاكاً للموارد."
        )
        temperature = st.slider("الإبداعية (Temperature):", min_value=0.0, max_value=1.0, value=0.0, step=0.1, help="القيمة 0 تعطي إجابات دقيقة ومحددة، بينما القيم الأعلى تعطي إجابات أكثر إبداعاً.")

        # التحقق من تحميل البيانات
        if st.session_state.df is not None:
            st.success("✅ البيانات جاهزة للمحادثة")
            if st.button("🚀 تفعيل المساعد الذكي", use_container_width=True):
                if groq_api_key:
                    with st.spinner("جاري تهيئة مساعد Groq..."):
                        try:
                            # إنشاء نموذج Groq
                            llm = ChatGroq(
                                groq_api_key=groq_api_key,
                                model_name=model_name,
                                temperature=temperature
                            )
                            # إنشاء الوكيل الذكي
                            agent = create_pandas_dataframe_agent(
                                llm,
                                st.session_state.df,
                                agent_type="tool-calling",
                                verbose=False,
                                allow_dangerous_code=True,
                                max_iterations=5,
                                handle_parsing_errors=True
                            )
                            st.session_state.groq_agent = agent
                            st.success("🎉 المساعد الذكي جاهز!")
                        except Exception as e:
                            st.error(f"❌ فشل في تهيئة المساعد: {str(e)}")
                else:
                    st.warning("⚠️ يرجى إدخال مفتاح Groq API أولاً.")
        else:
            st.info("⬆️ يرجى رفع ملف البيانات أولاً لاستخدام المساعد الذكي.")

# --- المنطقة الرئيسية ---
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📁 رفع الملف")
    uploaded_file = st.file_uploader(
        "اختر ملف Excel يحتوي على بيانات الموظفين",
        type=['xlsx', 'xls', 'csv'],
        help="يجب أن يحتوي الملف على الأعمدة: الاسم، رقم الحساب، الراتب"
    )

with col2:
    if uploaded_file is not None:
        st.success("✅ تم رفع الملف بنجاح")
    else:
        st.info("⏳ في انتظار رفع الملف...")

# --- معالجة الملف المرفوع ---
if uploaded_file is not None:
    try:
        # قراءة الملف
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        else:
            df = pd.read_excel(uploaded_file)

        st.session_state.df = df  # حفظ البيانات في حالة الجلسة

        # عرض البيانات
        st.header("📊 معاينة البيانات")
        
        required_columns = ['الاسم', 'رقم الحساب', 'الراتب']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"❌ الأعمدة التالية مفقودة: {', '.join(missing_columns)}")
            st.info("الرجاء التأكد من أن الملف يحتوي على الأعمدة: الاسم، رقم الحساب، الراتب")
            st.session_state.groq_agent = None  # تعطيل المساعد إذا كانت البيانات غير صالحة
        else:
            st.dataframe(df, use_container_width=True)

            # إحصائيات سريعة
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("عدد الموظفين", len(df))
            with col2:
                st.metric("مجموع الرواتب", f"{df['الراتب'].sum():,.0f} ريال")
            with col3:
                st.metric("متوسط الراتب", f"{df['الراتب'].mean():,.0f} ريال")

            # زر إنشاء الرسائل
            if st.button("🚀 إنشاء رسائل تحويل الرواتب", type="primary"):
                with st.spinner("جاري إنشاء رسائل PDF..."):
                    pdf_files = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for index, row in df.iterrows():
                        progress = (index + 1) / len(df)
                        progress_bar.progress(progress)
                        status_text.text(f"جاري إنشاء رسالة للموظف: {row['الاسم']}")

                        pdf = create_salary_letter(
                            row['الاسم'],
                            str(row['رقم الحساب']),
                            float(row['الراتب']),
                            selected_month
                        )
                        pdf_content = pdf.output(dest='S').encode('latin-1')
                        pdf_files.append({
                            'name': f"{row['الاسم']}_{selected_month}.pdf",
                            'content': pdf_content
                        })

                    progress_bar.empty()
                    status_text.empty()

                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for pdf_file in pdf_files:
                            zip_file.writestr(pdf_file['name'], pdf_file['content'])
                    zip_buffer.seek(0)

                    st.success(f"✅ تم إنشاء {len(pdf_files)} رسالة PDF بنجاح!")
                    st.download_button(
                        label=f"📥 تحميل جميع الرسائل ({len(pdf_files)} ملف PDF)",
                        data=zip_buffer,
                        file_name=f"رسائل_الرواتب_{selected_month}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

                    with st.expander("📋 عرض قائمة الملفات التي تم إنشاؤها"):
                        for pdf_file in pdf_files:
                            st.write(f"📄 {pdf_file['name']}")

    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء معالجة الملف: {str(e)}")
        st.info("الرجاء التأكد من صحة تنسيق الملف والمحتوى")
        st.session_state.df = None
        st.session_state.groq_agent = None

# --- قسم واجهة المحادثة مع مساعد Groq ---
if st.session_state.df is not None and st.session_state.groq_agent is not None:
    st.markdown("---")
    st.header("💬 تحدث مع مساعد البيانات الذكي")
    
    # عرض سجل المحادثة
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # حقل الإدخال
    if prompt := st.chat_input("اسأل أي سؤال عن بيانات الموظفين والرواتب..."):
        # إضافة سؤال المستخدم إلى السجل
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # الحصول على رد المساعد
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            with st.spinner("جاري التفكير..."):
                try:
                    # استدعاء الوكيل
                    result = st.session_state.groq_agent.invoke({"input": prompt})
                    full_response = result['output']
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    full_response = f"عذراً، حدث خطأ أثناء معالجة طلبك: {str(e)}"
                    message_placeholder.error(full_response)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})

    # زر لمسح المحادثة
    if st.button("🗑️ مسح المحادثة"):
        st.session_state.messages = []
        st.rerun()
else:
    if st.session_state.df is not None and st.session_state.groq_agent is None:
        st.info("👈 اذهب إلى الشريط الجانبي وأدخل مفتاح Groq API، ثم اضغط على 'تفعيل المساعد الذكي' لبدء المحادثة.")
    elif st.session_state.df is None:
        st.info("⬆️ يرجى رفع ملف بيانات الموظفين أولاً.")

# --- تذييل الصفحة ---
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>تم التطوير بواسطة مساعد مدير الفرع الذكي v2.0 (مدعوم بـ Groq)</p>",
    unsafe_allow_html=True
)
