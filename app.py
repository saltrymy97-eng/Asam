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

st.markdown('<div class="main-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>العملة: ريال يمني 🇾🇪 | تلقائي بالكامل</p></div>', unsafe_allow_html=True)

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

# ------------------- دالة ضغط الصورة -------------------
def compress_image(image, target_size_kb=250):
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
    
    return buffer.getvalue()

# ------------------- دالة استخراج البيانات -------------------
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

# ================== التبويب 1: تلقائي بالكامل ==================
with tab1:
    st.subheader("رفع صور الدفتر - تلقائي بالكامل")
    st.caption("ارفع الصور، اضغط زر واحد، وسيتم الاستخراج والحفظ تلقائياً")
    
    uploaded_files = st.file_uploader("اختر الصور", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} صورة")
        
        if st.button("🚀 استخراج وحفظ الكل تلقائياً", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            saved_count = 0
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"معالجة {i+1}/{len(uploaded_files)}: {file.name}")
                
                try:
                    image = Image.open(file)
                    compressed = compress_image(image)
                    result = extract_from_image(compressed)
                    
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', result)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', result)
                    
                    name = name_match.group(1).strip() if name_match else ""
                    amount_str = amount_match.group(1).replace(',', '.') if amount_match else "0"
                    amount = float(amount_str)
                    
                    if name and amount > 0:
                        c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                                  (name, amount, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit()
                        saved_count += 1
                        status_text.success(f"✅ {i+1}/{len(uploaded_files)}: {name} - {amount:,.0f} ريال")
                    else:
                        status_text.warning(f"⚠️ {i+1}/{len(uploaded_files)}: لم يتم العثور على بيانات")
                
                except Exception as e:
                    status_text.error(f"❌ خطأ في {file.name}: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
                time.sleep(0.5)
            
            progress_bar.empty()
            st.success(f"🎉 تم الحفظ التلقائي لـ {saved_count} معاملة")
            st.balloons()
            time.sleep(2)
            st.rerun()

# ================== التبويب 2: التصنيف ==================
with tab2:
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions", conn)
    if not df.empty:
        def classify(d):
            try:
                days = (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days
                if days <= 30: return "🟢 حديث (أقل من شهر)"
                elif days <= 90: return "🟡 متوسط (1-3 أشهر)"
                return "🔴 قديم (أكثر من 3 أشهر)"
            except:
                return "⚪ غير مصنف"
        
        df['التصنيف'] = df['transaction_date'].apply(classify)
        
        counts = df['التصنيف'].value_counts().reset_index()
        counts.columns = ['التصنيف', 'العدد']
        fig = px.pie(counts, values='العدد', names='التصنيف', title="نسبة الديون", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
        
        for cat in ["🟢 حديث (أقل من شهر)", "🟡 متوسط (1-3 أشهر)", "🔴 قديم (أكثر من 3 أشهر)"]:
            sub = df[df['التصنيف'] == cat]
            if not sub.empty:
                total = sub['amount'].sum()
                with st.expander(f"{cat} - {len(sub)} عميل | إجمالي: {total:,.0f} ريال"):
                    st.dataframe(sub[['name', 'amount', 'transaction_date']], use_container_width=True)
    else:
        st.info("لا توجد معاملات بعد")

# ================== التبويب 3: جميع المعاملات ==================
with tab3:
    df = pd.read_sql_query("SELECT name, amount, transaction_date, created_at FROM transactions ORDER BY transaction_date DESC", conn)
    if not df.empty:
        st.dataframe(df.rename(columns={
            'name': 'اسم العميل',
            'amount': 'المبلغ (ريال)',
            'transaction_date': 'تاريخ العملية',
            'created_at': 'تاريخ الإضافة'
        }), use_container_width=True)
        
        total = df['amount'].sum()
        st.metric("💵 إجمالي الديون", f"{total:,.0f} ريال يمني")
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 تحميل CSV", csv, "transactions.csv", "text/csv")
        
        if st.button("🗑️ حذف جميع المعاملات"):
            c.execute("DELETE FROM transactions")
            conn.commit()
            st.warning("تم حذف جميع المعاملات")
            st.rerun()
    else:
        st.info("لا توجد معاملات")

# ================== التبويب 4: إحصائيات (تم الإصلاح) ==================
with tab4:
    df = pd.read_sql_query("SELECT amount, transaction_date FROM transactions", conn)
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 إجمالي الديون", f"{df['amount'].sum():,.0f} ريال")
        col2.metric("📊 عدد المعاملات", len(df))
        col3.metric("📈 متوسط الدين", f"{df['amount'].mean():,.0f} ريال")
        
        # تحويل عمود التاريخ من نص إلى تاريخ (الإصلاح الأساسي)
        df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
        df = df.dropna(subset=['transaction_date'])
        
        if not df.empty:
            # تجميع شهري
            df['month'] = df['transaction_date'].dt.to_period('M')
            monthly = df.groupby('month')['amount'].sum().reset_index()
            monthly['month'] = monthly['month'].astype(str)
            fig = px.bar(monthly, x='month', y='amount', title="إجمالي الديون شهرياً (ريال يمني)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد تواريخ صالحة للرسم البياني")
    else:
        st.info("لا توجد بيانات للإحصائيات")

# ------------------- إغلاق الاتصال -------------------
def on_close():
    conn.close()

import atexit
atexit.register(on_close)
