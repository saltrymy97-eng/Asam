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
import os

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

# ------------------- قاعدة البيانات (تم الإصلاح) -------------------
def init_database():
    """إنشاء قاعدة البيانات والجدول إذا لم يكن موجوداً"""
    conn = sqlite3.connect('debter_extra.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  amount REAL,
                  transaction_date TEXT,
                  created_at TEXT)''')
    conn.commit()
    return conn, c

conn, c = init_database()

# ------------------- دالة ضغط قوية -------------------
def compress_image(image, target_size_kb=250):
    """ضغط الصورة بقوة من 5.6 ميجا إلى أقل من 250KB"""
    img = image.copy()
    
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    max_dimension = 800
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    quality = 50
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    
    while len(buffer.getvalue()) / 1024 > target_size_kb and quality > 15:
        quality -= 10
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
    
    compressed_size = len(buffer.getvalue()) / 1024
    st.caption(f"📦 {compressed_size:.0f} KB")
    
    return buffer.getvalue()

# ------------------- دالة الاستخراج -------------------
def extract_from_image(image_bytes):
    img_base64 = base64.b64encode(image_bytes).decode()
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "استخرج اسم العميل والمبلغ فقط. أجب بهذا الشكل:\nالاسم: ...\nالمبلغ: ..."},
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
                
                with st.spinner(f"معالجة الصورة {i+1}..."):
                    compressed = compress_image(image)
                
                try:
                    text = extract_from_image(compressed)
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', text)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', text)
                    
                    name = name_match.group(1).strip() if name_match else ""
                    amount_str = amount_match.group(1).replace(',', '.') if amount_match else "0"
                    amount = float(amount_str)
                    
                    results.append({"name": name, "amount": amount, "raw": text})
                    st.success(f"✅ {name or 'غير معروف'}: {amount:,.0f} ريال")
                    
                except Exception as e:
                    st.error(f"خطأ في الصورة {i+1}: {e}")
                
                progress.progress((i + 1) / len(uploaded_files))
                time.sleep(0.3)
            
            st.session_state['results'] = results
        
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

with tab2:
    try:
        df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions", conn)
        if not df.empty and 'transaction_date' in df.columns:
            def classify(d):
                try:
                    days = (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days
                    if days <= 30: return "🟢 حديث (أقل من شهر)"
                    elif days <= 90: return "🟡 متوسط (1-3 أشهر)"
                    return "🔴 قديم (أكثر من 3 أشهر)"
                except:
                    return "⚪ غير مصنف"
            df['التصنيف'] = df['transaction_date'].apply(classify)
            for cat in ["🟢 حديث (أقل من شهر)", "🟡 متوسط (1-3 أشهر)", "🔴 قديم (أكثر من 3 أشهر)"]:
                sub = df[df['التصنيف'] == cat]
                if not sub.empty:
                    with st.expander(f"{cat} - {len(sub)} عميل | {sub['amount'].sum():,.0f} ريال"):
                        st.dataframe(sub[['name', 'amount', 'transaction_date']])
        else:
            st.info("لا توجد معاملات بعد")
    except Exception as e:
        st.info("لا توجد معاملات بعد. أضف معاملات أولاً.")

with tab3:
    try:
        df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions ORDER BY transaction_date DESC", conn)
        if not df.empty:
            st.dataframe(df.rename(columns={'name':'الاسم', 'amount':'المبلغ(ريال)', 'transaction_date':'التاريخ'}))
            st.download_button("📥 تحميل CSV", df.to_csv(index=False).encode(), "transactions.csv")
        else:
            st.info("لا توجد معاملات")
    except Exception as e:
        st.info("لا توجد معاملات بعد")

with tab4:
    try:
        df = pd.read_sql_query("SELECT amount FROM transactions", conn)
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 إجمالي الديون", f"{df['amount'].sum():,.0f} ريال")
            col2.metric("📊 عدد المعاملات", len(df))
            col3.metric("📈 متوسط الدين", f"{df['amount'].mean():,.0f} ريال")
        else:
            st.info("لا توجد بيانات للإحصائيات")
    except Exception as e:
        st.info("لا توجد بيانات بعد")

# ------------------- إغلاق قاعدة البيانات عند الخروج -------------------
def on_close():
    conn.close()
    
# تسجيل دالة الإغلاق
import atexit
atexit.register(on_close)
