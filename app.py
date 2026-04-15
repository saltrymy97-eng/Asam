import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import plotly.express as px
import re
import tempfile
import os
from paddleocr import PaddleOCR

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

st.markdown("""
<style>
    .main-header { background: linear-gradient(90deg, #1e3c72, #2a5298); padding: 1.5rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>العملة: ريال يمني 🇾🇪 | PaddleOCR-VL للخط اليدوي العربي</p></div>', unsafe_allow_html=True)

# ------------------- تحميل نموذج OCR (مرة واحدة) -------------------
@st.cache_resource
def load_ocr():
    # تحميل نموذج PaddleOCR-VL (يدعم العربية والخط اليدوي)
    ocr = PaddleOCR(lang='ar', use_angle_cls=True, show_log=False)
    return ocr

with st.spinner("جاري تحميل نموذج OCR... قد يستغرق 30 ثانية في أول مرة"):
    ocr_model = load_ocr()
st.success("✅ النموذج جاهز!")

# ------------------- قاعدة البيانات -------------------
conn = sqlite3.connect('debter_extra.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              amount REAL,
              transaction_date TEXT,
              created_at TEXT)''')
conn.commit()

# ------------------- دالة استخراج النص -------------------
def extract_from_image(image_path):
    """استخراج النص من الصورة باستخدام PaddleOCR"""
    result = ocr_model.ocr(image_path, cls=True)
    if not result or not result[0]:
        return ""
    # جمع النصوص المستخرجة
    texts = [line[1][0] for line in result[0]]
    full_text = " ".join(texts)
    return full_text

def parse_name_amount(text):
    """تحليل النص لاستخراج الاسم والمبلغ"""
    # البحث عن الأرقام (مبالغ)
    amounts = re.findall(r'\d+(?:[.,]\d+)?', text)
    amount = float(amounts[0].replace(',', '.')) if amounts else 0.0
    
    # البحث عن الكلمات العربية (اسم)
    arabic_words = re.findall(r'[\u0600-\u06FF]{3,}', text)
    name = " ".join(arabic_words[:2]) if arabic_words else "غير معروف"
    
    return name, amount

# ------------------- الواجهة -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 إضافة معاملات", "📊 تصنيف المدينين", "📋 المعاملات", "📈 إحصائيات"])

with tab1:
    st.subheader("رفع صور الدفتر - تلقائي بالكامل")
    uploaded_files = st.file_uploader("اختر الصور", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} صورة")
        if st.button("🚀 استخراج وحفظ الكل تلقائياً", type="primary"):
            progress_bar = st.progress(0)
            saved_count = 0
            
            for i, file in enumerate(uploaded_files):
                with st.status(f"معالجة {i+1}/{len(uploaded_files)}: {file.name}..."):
                    # حفظ الصورة مؤقتاً
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                        tmp.write(file.getvalue())
                        tmp_path = tmp.name
                    
                    # استخراج النص
                    raw_text = extract_from_image(tmp_path)
                    os.unlink(tmp_path)
                    
                    if raw_text:
                        name, amount = parse_name_amount(raw_text)
                        if amount > 0:
                            c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                                      (name, amount, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                            saved_count += 1
                            st.success(f"✅ {name} - {amount:,.0f} ريال")
                        else:
                            st.warning(f"⚠️ لم يتم العثور على مبلغ: {raw_text[:100]}")
                    else:
                        st.error("❌ لم يتم استخراج أي نص")
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            progress_bar.empty()
            st.success(f"🎉 تم الحفظ التلقائي لـ {saved_count} معاملة")
            st.balloons()
            st.rerun()

# ------------------- باقي التبويبات -------------------
with tab2:
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions", conn)
    if not df.empty:
        def classify(d):
            try:
                days = (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days
                if days <= 30: return "🟢 دين حديث (أقل من شهر)"
                elif days <= 90: return "🟡 دين متوسط (1-3 أشهر)"
                return "🔴 دين قديم (أكثر من 3 أشهر)"
            except:
                return "⚪ غير مصنف"
        df['التصنيف'] = df['transaction_date'].apply(classify)
        counts = df['التصنيف'].value_counts().reset_index()
        counts.columns = ['التصنيف', 'العدد']
        fig = px.pie(counts, values='العدد', names='التصنيف', title="نسبة الديون", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
        for cat in ["🟢 دين حديث (أقل من شهر)", "🟡 دين متوسط (1-3 أشهر)", "🔴 دين قديم (أكثر من 3 أشهر)"]:
            sub = df[df['التصنيف'] == cat]
            if not sub.empty:
                total = sub['amount'].sum()
                with st.expander(f"{cat} - {len(sub)} عميل | إجمالي: {total:,.0f} ريال"):
                    st.dataframe(sub[['name', 'amount', 'transaction_date']])
    else:
        st.info("لا توجد معاملات بعد")

with tab3:
    df = pd.read_sql_query("SELECT name, amount, transaction_date, created_at FROM transactions ORDER BY transaction_date DESC", conn)
    if not df.empty:
        st.dataframe(df.rename(columns={'name':'الاسم', 'amount':'المبلغ (ريال)', 'transaction_date':'تاريخ العملية', 'created_at':'تاريخ الإضافة'}))
        st.download_button("📥 تحميل CSV", df.to_csv(index=False).encode('utf-8'), "transactions.csv")
        if st.button("🗑️ حذف جميع المعاملات"):
            c.execute("DELETE FROM transactions")
            conn.commit()
            st.warning("تم الحذف")
            st.rerun()
    else:
        st.info("لا توجد معاملات")

with tab4:
    df = pd.read_sql_query("SELECT amount FROM transactions", conn)
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 إجمالي الديون", f"{df['amount'].sum():,.0f} ريال")
        col2.metric("📊 عدد المعاملات", len(df))
        col3.metric("📈 متوسط الدين", f"{df['amount'].mean():,.0f} ريال")
    else:
        st.info("لا توجد بيانات للإحصائيات")

conn.close()
