import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import pytesseract
import cv2
import numpy as np
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
    page_title="دفتر الحسابات الذكي",
    page_icon="📒",
    layout="wide"
)

# =========================
# تنسيق CSS بسيط
# =========================
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #2E7D32 0%, #4CAF50 100%);
        padding: 1rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>📒 دفتر الحسابات الذكي</h1>
    <p>إدارة ديون عملائك بالتصوير والتصنيف التلقائي</p>
</div>
""", unsafe_allow_html=True)

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
# دوال التصنيف والقراءة
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

def extract_text_from_image(image_path):
    """استخراج النص من الصورة باستخدام pytesseract"""
    img = Image.open(image_path)
    img_np = np.array(img)
    
    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np
    
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    try:
        text = pytesseract.image_to_string(gray, lang='ara+eng')
    except:
        text = pytesseract.image_to_string(gray, lang='eng')
    
    return text

def clean_with_groq(raw_text, api_key):
    """تنظيف النص باستخدام Groq API"""
    from groq import Groq
    client = Groq(api_key=api_key)
    prompt = f"""
    أنت مساعد لاستخراج بيانات الديون من النص العربي.
    استخرج لي قائمة JSON تحتوي على: التاريخ (YYYY-MM-DD)، الاسم، المبلغ.
    النص: {raw_text}
    أخرج JSON فقط.
    """
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

def generate_pdf_report(dataframe):
    """إنشاء تقرير PDF"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, 'Debt Report', 0, 1, 'C')
    pdf.set_font('helvetica', '', 12)
    pdf.cell(0, 10, f'Date: {datetime.now().strftime("%Y-%m-%d")}', 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(60, 8, 'Name', 1, 0, 'C')
    pdf.cell(50, 8, f'Amount ({CURRENCY})', 1, 0, 'C')
    pdf.cell(40, 8, 'Date', 1, 0, 'C')
    pdf.cell(40, 8, 'Category', 1, 1, 'C')
    
    pdf.set_font('helvetica', '', 9)
    for _, row in dataframe.iterrows():
        pdf.cell(60, 7, row['name'], 1, 0, 'R')
        pdf.cell(50, 7, f"{row['amount']:.2f}", 1, 0, 'R')
        pdf.cell(40, 7, row['debt_date'], 1, 0, 'C')
        pdf.cell(40, 7, row['category'].split(' ')[0], 1, 1, 'R')
    
    pdf.ln(5)
    total = dataframe['amount'].sum()
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 10, f'Total: {total:.2f} {CURRENCY}', 0, 1, 'R')
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        pdf.output(tmp.name)
        return tmp.name

# =========================
# الشريط الجانبي
# =========================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.markdown("## 📊 الإحصائيات")
    
    stats_df = pd.read_sql("SELECT amount, category FROM debtors", conn)
    if not stats_df.empty:
        st.metric("👥 إجمالي المدينين", len(stats_df))
        st.metric(f"💰 إجمالي الديون", f"{stats_df['amount'].sum():,.2f} {CURRENCY}")
        
        st.markdown("---")
        st.markdown("### 🏷️ التصنيفات")
        cat_counts = stats_df['category'].value_counts()
        for cat, count in cat_counts.items():
            st.markdown(f"- {cat.split(' ')[0]}: **{count}**")
    else:
        st.info("لا توجد بيانات")

# =========================
# التبويبات
# =========================
tab1, tab2 = st.tabs(["📸 تصوير الدفتر", "📋 إدارة الديون"])

# =========================
# تبويب 1: تصوير الدفتر (مع زر حفظ الكل)
# =========================
with tab1:
    st.markdown("### 📸 تصوير دفتر الديون الورقي")
    
    groq_api_key = st.text_input("🔑 مفتاح Groq API", type="password", 
                                 help="احصل عليه من console.groq.com مجاناً")
    
    uploaded_file = st.file_uploader("اختر صورة الدفتر", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        with open("temp_image.jpg", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(uploaded_file, caption="الصورة المرفوعة", width=250)
        with col2:
            if st.button("🚀 استخراج الديون", use_container_width=True):
                if not groq_api_key:
                    st.error("❌ الرجاء إدخال مفتاح Groq API")
                else:
                    with st.spinner("جاري قراءة الدفتر..."):
                        raw_text = extract_text_from_image("temp_image.jpg")
                        st.text_area("النص الخام المستخرج", raw_text, height=100)
                        
                        cleaned_json = clean_with_groq(raw_text, groq_api_key)
                        st.text_area("النتيجة بعد الذكاء الاصطناعي", cleaned_json, height=150)
                        
                        try:
                            json_match = re.search(r'\[.*\]', cleaned_json, re.DOTALL)
                            if json_match:
                                debts = json.loads(json_match.group())
                                st.session_state.extracted_debts = debts
                                st.success(f"✅ تم استخراج {len(debts)} مدين")
                            else:
                                st.error("لم يتم العثور على بيانات JSON")
                        except Exception as e:
                            st.error(f"خطأ: {e}")
    
    # عرض المدينين المستخرجين مع إمكانية التعديل وحفظ الكل
    if 'extracted_debts' in st.session_state and st.session_state.extracted_debts:
        st.markdown("### ✏️ مراجعة وتعديل البيانات")
        st.info("تأكد من صحة البيانات ثم اضغط 'حفظ الكل' في الأسفل")
        
        # نسخ البيانات إلى session_state للتعديل
        if 'edited_debts' not in st.session_state:
            st.session_state.edited_debts = st.session_state.extracted_debts.copy()
        
        # عرض جدول قابل للتعديل
        for idx, debt in enumerate(st.session_state.edited_debts):
            with st.container():
                st.markdown(f"**مدين رقم {idx+1}**")
                col1, col2, col3 = st.columns([2, 2, 2])
                with col1:
                    st.session_state.edited_debts[idx]['الاسم'] = st.text_input(
                        "الاسم", 
                        value=debt.get('الاسم', ''), 
                        key=f"edit_name_{idx}"
                    )
                with col2:
                    st.session_state.edited_debts[idx]['المبلغ'] = st.number_input(
                        f"المبلغ ({CURRENCY})", 
                        value=float(debt.get('المبلغ', 0)), 
                        key=f"edit_amount_{idx}"
                    )
                with col3:
                    # معالجة التاريخ
                    current_date = debt.get('التاريخ', datetime.now().strftime("%Y-%m-%d"))
                    if isinstance(current_date, str):
                        current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
                    st.session_state.edited_debts[idx]['التاريخ'] = st.date_input(
                        "التاريخ", 
                        value=current_date, 
                        key=f"edit_date_{idx}"
                    ).strftime("%Y-%m-%d")
        
        # زر حفظ الكل (بدون st.rerun داخل الحلقة)
        if st.button("💾 حفظ جميع المدينين", type="primary", use_container_width=True):
            saved_count = 0
            for debt in st.session_state.edited_debts:
                name = debt.get('الاسم', '').strip()
                amount = float(debt.get('المبلغ', 0))
                debt_date = debt.get('التاريخ', datetime.now().strftime("%Y-%m-%d"))
                
                if name and amount > 0:
                    category = categorize_by_period(debt_date)
                    c.execute("INSERT INTO debtors (name, amount, debt_date, category) VALUES (?,?,?,?)",
                              (name, amount, debt_date, category))
                    saved_count += 1
            
            conn.commit()
            # مسح البيانات المؤقتة
            del st.session_state.extracted_debts
            del st.session_state.edited_debts
            st.success(f"✅ تم حفظ {saved_count} مدين بنجاح")
            st.rerun()

# =========================
# تبويب 2: إدارة الديون (مع تحديث آمن)
# =========================
with tab2:
    st.markdown("### 📋 إدارة الديون")
    
    debtors_df = pd.read_sql("SELECT id, name, amount, debt_date, category FROM debtors ORDER BY debt_date DESC", conn)
    
    if not debtors_df.empty:
        # فلترة
        filter_cat = st.selectbox("🔍 تصفية حسب التصنيف", 
                                   ["الكل", "🟢 دين حديث", "🟡 دين قديم", "🔴 دين منتهي"])
        if filter_cat != "الكل":
            debtors_df = debtors_df[debtors_df['category'].str.contains(filter_cat.split(' ')[0])]
        
        # عرض الجدول
        st.dataframe(
            debtors_df[['name', 'amount', 'category', 'debt_date']], 
            column_config={
                "name": "الاسم",
                "amount": st.column_config.NumberColumn(f"المبلغ ({CURRENCY})", format="%.2f"),
                "category": "التصنيف",
                "debt_date": "تاريخ الدين"
            },
            use_container_width=True,
            hide_index=True
        )
        
        # زر تنزيل PDF
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("📄 تنزيل التقرير", use_container_width=True):
                pdf_path = generate_pdf_report(debtors_df[['name', 'amount', 'debt_date', 'category']])
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📥 تحميل PDF",
                        data=f,
                        file_name=f"debt_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                os.unlink(pdf_path)
        
        # إحصائيات
        st.markdown("---")
        st.markdown("### 📊 إحصائيات التصنيفات")
        stats = debtors_df.groupby('category').agg({'amount': ['count', 'sum']}).round(2)
        stats.columns = ['العدد', f'الإجمالي ({CURRENCY})']
        st.dataframe(stats, use_container_width=True)
        
        # تسديد دين (بدون st.rerun مباشر)
        st.markdown("---")
        st.markdown("### 💰 تسديد دين")
        
        debtor_id = st.selectbox(
            "اختر المدين", 
            debtors_df['id'].tolist(),
            format_func=lambda x: f"{debtors_df[debtors_df['id']==x]['name'].iloc[0]} - {debtors_df[debtors_df['id']==x]['amount'].iloc[0]} {CURRENCY}",
            key="debtor_select"
        )
        
        payment = st.number_input(f"المبلغ المسدد ({CURRENCY})", min_value=0.0, step=100.0, key="payment_amount")
        
        if st.button("تسديد", type="primary", use_container_width=True):
            current_amount = debtors_df[debtors_df['id']==debtor_id]['amount'].iloc[0]
            new_amount = current_amount - payment
            
            if new_amount <= 0:
                c.execute("DELETE FROM debtors WHERE id=?", (debtor_id,))
                st.success("✅ تم سداد الدين بالكامل وحذف المدين")
            else:
                c.execute("UPDATE debtors SET amount=? WHERE id=?", (new_amount, debtor_id))
                st.success(f"✅ تم التسديد، المتبقي: {new_amount:,.2f} {CURRENCY}")
            
            conn.commit()
            # تحديث آمن بدون st.rerun مباشر (نستخدم st.rerun مرة واحدة)
            st.rerun()
    else:
        st.info("📭 لا يوجد مدينون حالياً. ابدأ بتصوير دفترك في التبويب الأول.")

# =========================
# إغلاق قاعدة البيانات
# =========================
conn.close()
