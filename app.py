import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import pytesseract
import cv2
import numpy as np
import re
from datetime import datetime, date
from fpdf import FPDF
import tempfile
import os

st.set_page_config(page_title="دفتر الديون التلقائي", page_icon="📒", layout="wide")

st.title("📒 دفتر الديون التلقائي")
st.caption("استخراج البيانات من الصورة تلقائيًا (بدون ذكاء اصطناعي) وتصنيف الديون حسب الفترة")

CURRENCY = "﷼"

# =========================
# قاعدة البيانات
# =========================
conn = sqlite3.connect('debts.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS debtors
             (id INTEGER PRIMARY KEY, name TEXT, amount REAL, debt_date TEXT, category TEXT)''')
conn.commit()

# =========================
# دالة التصنيف حسب الفترة
# =========================
def categorize_by_period(debt_date_str):
    try:
        debt_date = datetime.strptime(debt_date_str, "%Y-%m-%d").date()
        days_diff = (date.today() - debt_date).days
        if days_diff <= 15:
            return "🟢 دين حديث (أقل من 15 يوم)"
        elif days_diff <= 45:
            return "🟡 دين قديم (15-45 يوم)"
        else:
            return "🔴 دين منتهي (أكثر من 45 يوم)"
    except:
        return "⚪ تاريخ غير صحيح"

# =========================
# استخراج النص من الصورة (بدون Groq)
# =========================
def extract_text_from_image(image_path):
    img = Image.open(image_path)
    img_np = np.array(img)
    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    try:
        text = pytesseract.image_to_string(gray, lang='ara')
    except:
        text = pytesseract.image_to_string(gray, lang='eng')
    return text

# =========================
# تحليل النص باستخدام regex (استخراج التواريخ والأسماء والمبالغ)
# =========================
def parse_debts_from_text(text):
    """
    يبحث عن أنماط مثل:
    10-2-2025 محمد 5000
    15/2/2025 فاطمة 3000
    2025-03-01 يوسف 12000
    """
    lines = text.split('\n')
    debts = []
    
    # نمط للتاريخ (يدعم صيغ متعددة)
    date_pattern = r'(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})|(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})'
    # نمط للمبلغ (أرقام)
    amount_pattern = r'\b(\d+(?:\.\d+)?)\b'
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # البحث عن التاريخ
        date_match = re.search(date_pattern, line)
        if not date_match:
            continue
        date_str = date_match.group()
        # توحيد الصيغة إلى YYYY-MM-DD
        try:
            if '-' in date_str or '/' in date_str:
                parts = re.split('[-/]', date_str)
                if len(parts) == 3:
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        y, m, d = parts
                    else:  # DD-MM-YYYY
                        d, m, y = parts
                    if len(y) == 2:
                        y = '20' + y
                    debt_date = f"{y}-{int(m):02d}-{int(d):02d}"
                else:
                    continue
            else:
                continue
        except:
            continue
        
        # البحث عن المبلغ (أكبر رقم في السطر عادة)
        amounts = re.findall(amount_pattern, line)
        if not amounts:
            continue
        amount = float(amounts[-1])  # خذ آخر رقم كالمبلغ
        
        # الاسم هو ما تبقى بعد إزالة التاريخ والمبلغ
        name_part = line
        name_part = re.sub(date_pattern, '', name_part)
        name_part = re.sub(amount_pattern, '', name_part)
        name_part = re.sub(r'[^\w\s]', '', name_part).strip()
        if not name_part:
            name_part = "غير معروف"
        
        debts.append({
            'التاريخ': debt_date,
            'الاسم': name_part,
            'المبلغ': amount
        })
    
    return debts

# =========================
# الشريط الجانبي
# =========================
with st.sidebar:
    st.header("📊 الإحصائيات")
    stats_df = pd.read_sql("SELECT amount FROM debtors", conn)
    if not stats_df.empty:
        st.metric("إجمالي المدينين", len(stats_df))
        st.metric(f"إجمالي الديون", f"{stats_df['amount'].sum():,.2f} {CURRENCY}")

# =========================
# التبويبات
# =========================
tab1, tab2 = st.tabs(["📸 رفع الصورة واستخراج الديون", "📋 إدارة الديون"])

# =========================
# تبويب رفع الصورة
# =========================
with tab1:
    st.subheader("ارفع صورة دفتر الديون")
    uploaded_file = st.file_uploader("اختر صورة", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        with open("temp_image.jpg", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.image(uploaded_file, caption="الصورة المرفوعة", width=300)
        
        if st.button("🚀 استخراج الديون تلقائيًا (بدون ذكاء اصطناعي)"):
            with st.spinner("جاري قراءة الصورة وتحليلها..."):
                raw_text = extract_text_from_image("temp_image.jpg")
                st.text_area("النص الخام المستخرج", raw_text, height=150)
                
                debts = parse_debts_from_text(raw_text)
                if debts:
                    st.session_state.extracted_debts = debts
                    st.success(f"✅ تم استخراج {len(debts)} مدين")
                else:
                    st.error("لم يتم العثور على بيانات. تأكد من وضوح الصورة وتنسيق الدفتر (تاريخ - اسم - مبلغ)")
    
    if 'extracted_debts' in st.session_state:
        st.subheader("✅ الديون المستخرجة (راجعها قبل الحفظ)")
        edited_debts = []
        for idx, debt in enumerate(st.session_state.extracted_debts):
            col1, col2, col3 = st.columns([2,2,2])
            with col1:
                name = st.text_input("الاسم", debt['الاسم'], key=f"name_{idx}")
            with col2:
                amount = st.number_input(f"المبلغ ({CURRENCY})", value=debt['المبلغ'], key=f"amount_{idx}")
            with col3:
                debt_date = st.date_input("التاريخ", value=datetime.strptime(debt['التاريخ'], "%Y-%m-%d").date(), key=f"date_{idx}")
            edited_debts.append({
                'الاسم': name,
                'المبلغ': amount,
                'التاريخ': debt_date.strftime("%Y-%m-%d")
            })
        
        if st.button("💾 حفظ جميع المدينين"):
            saved = 0
            for debt in edited_debts:
                if debt['الاسم'].strip() and debt['المبلغ'] > 0:
                    cat = categorize_by_period(debt['التاريخ'])
                    c.execute("INSERT INTO debtors (name, amount, debt_date, category) VALUES (?,?,?,?)",
                              (debt['الاسم'], debt['المبلغ'], debt['التاريخ'], cat))
                    saved += 1
            conn.commit()
            del st.session_state.extracted_debts
            st.success(f"تم حفظ {saved} مدين")
            st.rerun()

# =========================
# تبويب إدارة الديون (مثل السابق)
# =========================
with tab2:
    st.subheader("قائمة المدينين")
    df = pd.read_sql("SELECT id, name, amount, debt_date, category FROM debtors ORDER BY debt_date DESC", conn)
    if not df.empty:
        filter_cat = st.selectbox("تصفية حسب التصنيف", ["الكل", "🟢 دين حديث", "🟡 دين قديم", "🔴 دين منتهي"])
        if filter_cat != "الكل":
            df = df[df['category'] == filter_cat]
        st.dataframe(df[['name', 'amount', 'category', 'debt_date']], use_container_width=True, hide_index=True)
        
        if st.button("📄 تصدير PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('helvetica', 'B', 16)
            pdf.cell(0, 10, 'Debt Report', 0, 1, 'C')
            pdf.set_font('helvetica', '', 12)
            pdf.cell(0, 10, f'Date: {date.today()}', 0, 1, 'L')
            pdf.ln(5)
            pdf.set_font('helvetica', 'B', 10)
            pdf.cell(60, 8, 'Name', 1, 0, 'C')
            pdf.cell(50, 8, 'Amount', 1, 0, 'C')
            pdf.cell(40, 8, 'Date', 1, 0, 'C')
            pdf.cell(40, 8, 'Category', 1, 1, 'C')
            pdf.set_font('helvetica', '', 9)
            for _, row in df.iterrows():
                pdf.cell(60, 7, row['name'], 1, 0, 'R')
                pdf.cell(50, 7, f"{row['amount']:.2f}", 1, 0, 'R')
                pdf.cell(40, 7, row['debt_date'], 1, 0, 'C')
                pdf.cell(40, 7, row['category'].split(' ')[0], 1, 1, 'R')
            total = df['amount'].sum()
            pdf.set_font('helvetica', 'B', 11)
            pdf.cell(0, 10, f'Total: {total:.2f} {CURRENCY}', 0, 1, 'R')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                pdf.output(tmp.name)
                with open(tmp.name, 'rb') as f:
                    st.download_button("تحميل PDF", f, file_name="debts.pdf")
                os.unlink(tmp.name)
        
        st.markdown("---")
        st.subheader("💰 تسديد دين")
        debtor_id = st.selectbox("اختر المدين", df['id'].tolist(), format_func=lambda x: f"{df[df['id']==x]['name'].iloc[0]} - {df[df['id']==x]['amount'].iloc[0]} {CURRENCY}")
        payment = st.number_input(f"المبلغ المسدد ({CURRENCY})", min_value=0.0, step=100.0)
        if st.button("تسديد"):
            current = df[df['id']==debtor_id]['amount'].iloc[0]
            new_amt = current - payment
            if new_amt <= 0:
                c.execute("DELETE FROM debtors WHERE id=?", (debtor_id,))
                st.success("تم سداد الدين بالكامل")
            else:
                c.execute("UPDATE debtors SET amount=? WHERE id=?", (new_amt, debtor_id))
                st.success(f"المتبقي: {new_amt:.2f} {CURRENCY}")
            conn.commit()
            st.rerun()
    else:
        st.info("لا يوجد مدينون حالياً")

conn.close()
