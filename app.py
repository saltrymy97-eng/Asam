import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import easyocr
import re
from datetime import datetime, date
import json
from fpdf import FPDF
import tempfile
import os
import numpy as np

# =========================
# إعدادات الصفحة
# =========================
st.set_page_config(
    page_title="دفتر الحسابات الذكي",
    page_icon="📒",
    layout="wide"
)

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
# تحميل easyocr مرة واحدة
# =========================
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ar', 'en'])

def extract_text_from_image(image_path):
    reader = load_ocr()
    result = reader.readtext(image_path, detail=0, paragraph=True)
    return ' '.join(result)

# =========================
# التصنيف حسب الفترة
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

# =========================
# تنظيف النص باستخدام Groq
# =========================
def clean_with_groq(raw_text, api_key):
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

# =========================
# إنشاء PDF
# =========================
def generate_pdf_report(dataframe):
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
# الواجهة الرئيسية
# =========================
st.markdown("# 📒 دفتر الحسابات الذكي")
st.markdown("إدارة ديون عملائك بالتصوير والتصنيف التلقائي")

# الشريط الجانبي
with st.sidebar:
    st.markdown("## 📊 الإحصائيات")
    stats_df = pd.read_sql("SELECT amount, category FROM debtors", conn)
    if not stats_df.empty:
        st.metric("👥 إجمالي المدينين", len(stats_df))
        st.metric(f"💰 إجمالي الديون", f"{stats_df['amount'].sum():,.2f} {CURRENCY}")

# التبويبات
tab1, tab2 = st.tabs(["📸 تصوير الدفتر", "📋 إدارة الديون"])

# تبويب التصوير
with tab1:
    groq_api_key = st.text_input("🔑 مفتاح Groq API", type="password")
    uploaded_file = st.file_uploader("اختر صورة الدفتر", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        with open("temp_image.jpg", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.image(uploaded_file, caption="الصورة", width=250)
        
        if st.button("استخراج الديون"):
            if not groq_api_key:
                st.error("الرجاء إدخال مفتاح Groq API")
            else:
                with st.spinner("جاري القراءة..."):
                    raw_text = extract_text_from_image("temp_image.jpg")
                    st.text_area("النص الخام", raw_text, height=100)
                    
                    cleaned_json = clean_with_groq(raw_text, groq_api_key)
                    st.text_area("النتيجة", cleaned_json, height=150)
                    
                    try:
                        json_match = re.search(r'\[.*\]', cleaned_json, re.DOTALL)
                        if json_match:
                            debts = json.loads(json_match.group())
                            st.session_state.extracted_debts = debts
                            st.success(f"تم استخراج {len(debts)} مدين")
                    except Exception as e:
                        st.error(f"خطأ: {e}")
    
    if 'extracted_debts' in st.session_state:
        for idx, debt in enumerate(st.session_state.extracted_debts):
            with st.container():
                st.markdown(f"**مدين {idx+1}**")
                col1, col2, col3 = st.columns([2,2,1])
                name = col1.text_input("الاسم", debt.get('الاسم', ''), key=f"name_{idx}")
                amount = col2.number_input("المبلغ", value=float(debt.get('المبلغ', 0)), key=f"amount_{idx}")
                debt_date = col3.date_input("التاريخ", key=f"date_{idx}")
                if st.button(f"حفظ", key=f"save_{idx}"):
                    date_str = debt_date.strftime("%Y-%m-%d")
                    category = categorize_by_period(date_str)
                    c.execute("INSERT INTO debtors (name, amount, debt_date, category) VALUES (?,?,?,?)",
                              (name, amount, date_str, category))
                    conn.commit()
                    st.success(f"تم حفظ {name}")
                    st.rerun()

# تبويب إدارة الديون
with tab2:
    debtors_df = pd.read_sql("SELECT id, name, amount, debt_date, category FROM debtors ORDER BY debt_date DESC", conn)
    
    if not debtors_df.empty:
        filter_cat = st.selectbox("تصفية", ["الكل", "🟢 دين حديث", "🟡 دين قديم", "🔴 دين منتهي"])
        if filter_cat != "الكل":
            debtors_df = debtors_df[debtors_df['category'].str.contains(filter_cat)]
        
        st.dataframe(debtors_df[['name', 'amount', 'category', 'debt_date']], use_container_width=True)
        
        if st.button("تنزيل PDF"):
            pdf_path = generate_pdf_report(debtors_df[['name', 'amount', 'debt_date', 'category']])
            with open(pdf_path, "rb") as f:
                st.download_button("تحميل", f, file_name="report.pdf")
            os.unlink(pdf_path)
        
        st.markdown("### تسديد دين")
        debtor_id = st.selectbox("اختر المدين", debtors_df['id'].tolist(),
                                 format_func=lambda x: f"{debtors_df[debtors_df['id']==x]['name'].iloc[0]} - {debtors_df[debtors_df['id']==x]['amount'].iloc[0]} {CURRENCY}")
        payment = st.number_input("المبلغ المسدد", min_value=0.0, step=100.0)
        
        if st.button("تسديد"):
            current = debtors_df[debtors_df['id']==debtor_id]['amount'].iloc[0]
            new = current - payment
            if new <= 0:
                c.execute("DELETE FROM debtors WHERE id=?", (debtor_id,))
                st.success("تم السداد بالكامل")
            else:
                c.execute("UPDATE debtors SET amount=? WHERE id=?", (new, debtor_id))
                st.success(f"المتبقي: {new} {CURRENCY}")
            conn.commit()
            st.rerun()
    else:
        st.info("لا يوجد مدينون")

conn.close()
