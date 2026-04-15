import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import base64
from io import BytesIO
import re
from groq import Groq
import plotly.express as px
import time

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

st.markdown("""
<style>
    .main-header { background: linear-gradient(90deg, #1e3c72, #2a5298); padding: 1.5rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>العملة: ريال يمني 🇾🇪</p></div>', unsafe_allow_html=True)

# ------------------- إعداد Groq -------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    GROQ_API_KEY = st.text_input("🔑 مفتاح Groq API:", type="password")
    if not GROQ_API_KEY:
        st.stop()
client = Groq(api_key=GROQ_API_KEY)

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

# ------------------- دالة ضغط قوية -------------------
def compress_image(image, target_size_kb=250):
    """ضغط الصورة بقوة من 5.6 ميجا إلى أقل من 250KB"""
    img = image.copy()
    
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    # تقليل الأبعاد إلى 800 بكسل كحد أقصى
    max_dimension = 800
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # ضغط تدريجي
    quality = 50
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    
    # استمر في الضغط حتى يصبح الحجم أقل من المطلوب
    while len(buffer.getvalue()) / 1024 > target_size_kb and quality > 15:
        quality -= 10
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
    
    compressed_size = len(buffer.getvalue()) / 1024
    st.caption(f"📦 {compressed_size:.0f} KB (تم ضغط {(5.6*1024 - compressed_size)/1024:.0f} MB)")
    
    return buffer.getvalue()

# ------------------- دالة الاستخراج -------------------
def extract_from_image(image_bytes):
    img_base64 = base64.b64encode(image_bytes).decode()
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "استخرج اسم العميل والمبلغ فقط. أجب: الاسم: ... المبلغ: ..."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
        }],
        temperature=0.1
    )
    return response.choices[0].message.content

# ------------------- الواجهة -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 إضافة معاملات", "📊 تصنيف المدينين", "📋 المعاملات", "📈 إحصائيات"])

with tab1:
    st.subheader("رفع صور الدفتر")
    uploaded_files = st.file_uploader("اختر الصور", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.info(f"{len(uploaded_files)} صورة")
        
        if st.button("🔍 استخراج البيانات"):
            progress = st.progress(0)
            results = []
            
            for i, file in enumerate(uploaded_files):
                image = Image.open(file)
                
                # ضغط الصورة
                with st.spinner(f"ضغط الصورة {i+1}..."):
                    compressed = compress_image(image)
                
                # استخراج النص
                try:
                    text = extract_from_image(compressed)
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', text)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', text)
                    
                    name = name_match.group(1).strip() if name_match else ""
                    amount = float(amount_match.group(1).replace(',', '.')) if amount_match else 0
                    
                    results.append({"name": name, "amount": amount, "raw": text})
                    st.success(f"✅ {name or 'غير معروف'}: {amount:,.0f} ريال")
                    
                except Exception as e:
                    st.error(f"خطأ: {e}")
                
                progress.progress((i + 1) / len(uploaded_files))
                time.sleep(0.3)
            
            st.session_state['results'] = results
        
        # عرض النتائج والحفظ
        if 'results' in st.session_state and st.session_state['results']:
            for idx, r in enumerate(st.session_state['results']):
                with st.expander(f"معاملة {idx+1}: {r['name'] or 'غير مسمى'}"):
                    col1, col2 = st.columns(2)
                    name = col1.text_input(f"الاسم", r['name'], key=f"name_{idx}")
                    amount = col2.number_input(f"المبلغ (ريال)", value=r['amount'], step=100, key=f"amount_{idx}")
                    date = st.date_input(f"التاريخ", datetime.now(), key=f"date_{idx}")
                    
                    if st.button(f"💾 حفظ", key=f"save_{idx}"):
                        if name and amount > 0:
                            c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                                      (name, amount, date.strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                            st.success(f"تم حفظ {name} - {amount:,.0f} ريال")
                            st.session_state['results'].pop(idx)
                            st.rerun()
                        else:
                            st.warning("أدخل الاسم والمبلغ")

# ------------------- باقي التبويبات -------------------
with tab2:
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions", conn)
    if not df.empty:
        def classify(d):
            days = (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days
            if days <= 30: return "🟢 حديث"
            elif days <= 90: return "🟡 متوسط"
            return "🔴 قديم"
        df['التصنيف'] = df['transaction_date'].apply(classify)
        for cat in ["🟢 حديث", "🟡 متوسط", "🔴 قديم"]:
            sub = df[df['التصنيف'] == cat]
            if not sub.empty:
                with st.expander(f"{cat} - {len(sub)} عميل | {sub['amount'].sum():,.0f} ريال"):
                    st.dataframe(sub[['name', 'amount', 'transaction_date']])
    else:
        st.info("لا توجد معاملات")

with tab3:
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions ORDER BY transaction_date DESC", conn)
    if not df.empty:
        st.dataframe(df.rename(columns={'name':'الاسم', 'amount':'المبلغ(ريال)', 'transaction_date':'التاريخ'}))
        st.download_button("تحميل CSV", df.to_csv(index=False).encode(), "transactions.csv")
    else:
        st.info("لا توجد معاملات")

with tab4:
    df = pd.read_sql_query("SELECT amount FROM transactions", conn)
    if not df.empty:
        st.metric("إجمالي الديون", f"{df['amount'].sum():,.0f} ريال")
        st.metric("عدد المعاملات", len(df))
        st.metric("متوسط الدين", f"{df['amount'].mean():,.0f} ريال")
    else:
        st.info("لا توجد بيانات")

conn.close()
