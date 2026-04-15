import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import easyocr
from groq import Groq
import re
from datetime import datetime, date
import json
from fpdf import FPDF
import tempfile
import os

# =========================
# إعدادات الصفحة
# =========================
st.set_page_config(
    page_title="دفتر الحسابات الذكي | البقالة الذكية",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# CSS مخصص
# =========================
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #2E7D32 0%, #4CAF50 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
    }
    .main-header p {
        margin: 0.5rem 0 0;
        opacity: 0.9;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.5rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #2E7D32;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# =========================
# العناوين الرئيسية
# =========================
st.markdown("""
<div class="main-header">
    <h1>📒 دفتر الحسابات الذكي</h1>
    <p>إدارة ديون عملائك بذكاء وسرعة - بالتصوير والتصنيف التلقائي</p>
</div>
""", unsafe_allow_html=True)

# =========================
# العملة والإعدادات
# =========================
CURRENCY = "﷼"

# =========================
# قاعدة البيانات
# =========================
conn = sqlite3.connect('debts.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS debtors
             (id INTEGER PRIMARY KEY, 
              name TEXT, 
              amount REAL, 
              debt_date TEXT,
              category TEXT)''')
conn.commit()

# =========================
# دوال المساعدة
# =========================
def categorize_by_period(debt_date_str):
    try:
        debt_date = datetime.strptime(debt_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_diff = (today - debt_date).days
        
        if days_diff <= 15:
            return "🟢 دين حديث (أقل من 15 يوم)"
        elif days_diff <= 45:
            return "🟡 دين قديم (15-45 يوم)"
        else:
            return "🔴 دين منتهي (أكثر من 45 يوم)"
    except:
        return "⚪ تاريخ غير صحيح"

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ar', 'en'])

def extract_text_from_image(image_path):
    reader = load_ocr()
    result = reader.readtext(image_path, detail=0, paragraph=True)
    return ' '.join(result)

def clean_with_groq(raw_text, api_key):
    client = Groq(api_key=api_key)
    prompt = f"""
    أنت مساعد لاستخراج بيانات الديون من النص العربي المستخرج من دفتر يدوي.
    استخرج لي قائمة JSON تحتوي على: التاريخ (YYYY-MM-DD)، الاسم، المبلغ.
    النص: {raw_text}
    مثال: [{{"التاريخ": "2025-03-10", "الاسم": "محمد", "المبلغ": 5000}}]
    أخرج JSON فقط.
    """
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

# =========================
# دالة إنشاء PDF
# =========================
def generate_pdf_report(dataframe):
    class ArabicPDF(FPDF):
        def header(self):
            self.set_font('helvetica', 'B', 16)
            self.cell(0, 10, 'Debt Report - دفتر الحسابات', 0, 1, 'C')
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    pdf = ArabicPDF()
    pdf.add_page()
    pdf.set_font('helvetica', '', 12)
    
    # العنوان
    pdf.cell(0, 10, f'Report Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
    pdf.ln(5)
    
    # إضافة الجدول
    col_widths = [60, 50, 50, 40]
    headers = ['Name (الاسم)', 'Amount (المبلغ)', 'Date (التاريخ)', 'Category (التصنيف)']
    
    # رأس الجدول
    pdf.set_font('helvetica', 'B', 10)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, 1, 0, 'C')
    pdf.ln()
    
    # بيانات الجدول
    pdf.set_font('helvetica', '', 9)
    for _, row in dataframe.iterrows():
        pdf.cell(col_widths[0], 8, row['name'], 1, 0, 'R')
        pdf.cell(col_widths[1], 8, f"{row['amount']:.2f} {CURRENCY}", 1, 0, 'R')
        pdf.cell(col_widths[2], 8, row['debt_date'], 1, 0, 'C')
        pdf.cell(col_widths[3], 8, row['category'].split(' ')[0], 1, 0, 'R')
        pdf.ln()
    
    # إجمالي الديون
    pdf.ln(5)
    total = dataframe['amount'].sum()
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 10, f'Total Debts: {total:.2f} {CURRENCY}', 0, 1, 'R')
    
    # حفظ الملف المؤقت
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        pdf.output(tmp_file.name)
        return tmp_file.name

# =========================
# الشريط الجانبي
# =========================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
    st.markdown("## 📊 الإحصائيات")
    
    debtors_stats = pd.read_sql("SELECT amount, category FROM debtors", conn)
    if not debtors_stats.empty:
        total_debtors = len(debtors_stats)
        total_amount = debtors_stats['amount'].sum()
        
        st.metric("👥 إجمالي المدينين", total_debtors)
        st.metric(f"💰 إجمالي الديون ({CURRENCY})", f"{total_amount:,.2f}")
        
        st.markdown("---")
        st.markdown("### 🏷️ التصنيفات")
        cat_counts = debtors_stats['category'].value_counts()
        for cat, count in cat_counts.items():
            st.markdown(f"- {cat}: **{count}**")
    else:
        st.info("لا توجد بيانات بعد")
    
    st.markdown("---")
    st.markdown("### 💡 نصائح سريعة")
    st.info("1️⃣ صورت دفترك؟ ارفعه في قسم التصوير\n2️⃣ راجع البيانات قبل الحفظ\n3️⃣ استخدم التصفية لمتابعة المتأخرين")

# =========================
# الأقسام الرئيسية
# =========================
tab1, tab2, tab3 = st.tabs(["📸 تصوير الدفتر", "📋 إدارة الديون", "⚙️ إعدادات"])

# =========================
# تبويب 1: تصوير الدفتر
# =========================
with tab1:
    st.markdown("### 📸 تصوير دفتر الديون الورقي")
    st.markdown("قم بتصوير صفحة الدفتر التي تحتوي على **التاريخ، الاسم، المبلغ**")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        groq_api_key = st.text_input("🔑 مفتاح Groq API", type="password", 
                                     help="احصل عليه من console.groq.com مجاناً")
    with col2:
        st.markdown("")
        st.markdown("")
        st.markdown("[🔗 الحصول على مفتاح Groq](https://console.groq.com)")
    
    uploaded_file = st.file_uploader("📤 اختر صورة الدفتر", type=["jpg", "jpeg", "png"], 
                                     help="صورة واضحة للصفحة")
    
    if uploaded_file:
        with open("temp_image.jpg", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        col_img, col_info = st.columns([1, 1])
        with col_img:
            st.image(uploaded_file, caption="الصورة المرفوعة", width=300)
        
        with col_info:
            if st.button("🚀 استخراج الديون", use_container_width=True):
                if not groq_api_key:
                    st.error("❌ الرجاء إدخال مفتاح Groq API")
                else:
                    with st.spinner("جاري قراءة الدفتر..."):
                        raw_text = extract_text_from_image("temp_image.jpg")
                        cleaned_json = clean_with_groq(raw_text, groq_api_key)
                        
                        try:
                            json_match = re.search(r'\[.*\]', cleaned_json, re.DOTALL)
                            if json_match:
                                debts = json.loads(json_match.group())
                                st.session_state.extracted_debts = debts
                                st.success(f"✅ تم استخراج {len(debts)} مدين")
                            else:
                                st.error("لم يتم العثور على بيانات")
                        except Exception as e:
                            st.error(f"خطأ: {e}")
    
    if 'extracted_debts' in st.session_state and st.session_state.extracted_debts:
        st.markdown("### ✏️ مراجعة البيانات")
        st.info("تأكد من صحة البيانات وقم بتعديلها قبل الحفظ")
        
        for idx, debt in enumerate(st.session_state.extracted_debts):
            with st.container():
                st.markdown(f"#### مدين رقم {idx+1}")
                col1, col2, col3, col4 = st.columns([2,2,2,1])
                with col1:
                    name = st.text_input("الاسم", debt.get('الاسم', ''), key=f"name_{idx}")
                with col2:
                    amount = st.number_input(f"المبلغ ({CURRENCY})", value=float(debt.get('المبلغ', 0)), key=f"amount_{idx}")
                with col3:
                    debt_date = st.date_input("التاريخ", value=datetime.strptime(debt.get('التاريخ', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(), key=f"date_{idx}")
                with col4:
                    if st.button(f"💾 حفظ", key=f"save_{idx}"):
                        date_str = debt_date.strftime("%Y-%m-%d")
                        category = categorize_by_period(date_str)
                        c.execute("INSERT INTO debtors (name, amount, debt_date, category) VALUES (?,?,?,?)",
                                  (name, amount, date_str, category))
                        conn.commit()
                        st.success(f"تم حفظ {name}")
                        st.rerun()

# =========================
# تبويب 2: إدارة الديون
# =========================
with tab2:
    st.markdown("### 📋 إدارة الديون")
    
    debtors_df = pd.read_sql("SELECT id, name, amount, debt_date, category FROM debtors ORDER BY debt_date DESC", conn)
    
    if not debtors_df.empty:
        # فلترة
        filter_cat = st.selectbox("🔍 تصفية حسب التصنيف", ["الكل", "🟢 دين حديث (أقل من 15 يوم)", "🟡 دين قديم (15-45 يوم)", "🔴 دين منتهي (أكثر من 45 يوم)"])
        if filter_cat != "الكل":
            debtors_df = debtors_df[debtors_df['category'] == filter_cat]
        
        # عرض الجدول
        st.dataframe(debtors_df[['name', 'amount', 'category', 'debt_date']], 
                     column_config={
                         "name": "الاسم",
                         "amount": st.column_config.NumberColumn(f"المبلغ ({CURRENCY})", format="%.2f"),
                         "category": "التصنيف",
                         "debt_date": "تاريخ الدين"
                     },
                     use_container_width=True,
                     hide_index=True)
        
        # زر تنزيل PDF
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("📄 تنزيل التقرير كـ PDF", use_container_width=True):
                with st.spinner("جاري إنشاء ملف PDF..."):
                    pdf_path = generate_pdf_report(debtors_df[['name', 'amount', 'debt_date', 'category']])
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="📥 تحميل التقرير",
                            data=f,
                            file_name=f"debt_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    os.unlink(pdf_path)  # حذف الملف المؤقت
        
        # إحصائيات
        st.markdown("---")
        st.markdown("### 📊 إحصائيات التصنيفات")
        stats = debtors_df.groupby('category').agg({'amount': ['count', 'sum']}).round(2)
        stats.columns = ['العدد', f'الإجمالي ({CURRENCY})']
        st.dataframe(stats, use_container_width=True)
        
        # تسديد
        st.markdown("---")
        st.markdown("### 💰 تسديد دين")
        col1, col2 = st.columns([3, 1])
        with col1:
            debtor_id = st.selectbox("اختر المدين", debtors_df['id'].tolist(), 
                                     format_func=lambda x: f"{debtors_df[debtors_df['id']==x]['name'].iloc[0]} - {debtors_df[debtors_df['id']==x]['amount'].iloc[0]} {CURRENCY}")
        with col2:
            payment = st.number_input(f"المبلغ المسدد ({CURRENCY})", min_value=0.0, step=100.0)
        
        if st.button("تسديد", use_container_width=True):
            current_amount = debtors_df[debtors_df['id']==debtor_id]['amount'].iloc[0]
            new_amount = current_amount - payment
            if new_amount <= 0:
                c.execute("DELETE FROM debtors WHERE id=?", (debtor_id,))
                st.success("✅ تم سداد الدين بالكامل")
            else:
                c.execute("UPDATE debtors SET amount=? WHERE id=?", (new_amount, debtor_id))
                st.success(f"✅ تم التسديد، المتبقي: {new_amount} {CURRENCY}")
            conn.commit()
            st.rerun()
    else:
        st.info("📭 لا يوجد مدينون حالياً. ابدأ بتصوير دفترك في التبويب الأول.")

# =========================
# تبويب 3: إعدادات
# =========================
with tab3:
    st.markdown("### ⚙️ إعدادات النظام")
    st.info("هذه الإعدادات قيد التطوير. يمكنك تخصيصها لاحقاً.")
    st.markdown("**الميزات القادمة:**")
    st.markdown("- تغيير حدود التصنيف (15 و 45 يوماً)")
    st.markdown("- تصدير البيانات إلى Excel")
    st.markdown("- طباعة تقارير")
    st.markdown("- نسخ احتياطي لقاعدة البيانات")

conn.close()
