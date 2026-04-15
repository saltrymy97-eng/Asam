import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image
import base64
from io import BytesIO
import re
from groq import Groq
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import plotly.express as px

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

st.markdown("""
<style>
    .main-header { background: linear-gradient(90deg, #1e3c72, #2a5298); padding: 1.5rem; border-radius: 15px; color: white; text-align: center; margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1></div>', unsafe_allow_html=True)

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

# ------------------- دوال مساعدة -------------------
def classify_debt(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        days = (datetime.now() - d).days
        if days <= 30: return "🟢 حديثة (أقل من شهر)"
        elif days <= 90: return "🟡 متوسطة (1-3 أشهر)"
        else: return "🔴 قديمة (أكثر من 3 أشهر)"
    except:
        return "⚪ غير مصنف"

def compress_image(image, max_size=800):
    """ضغط الصورة قبل الإرسال لتسريع المعالجة"""
    img = image.copy()
    img.thumbnail((max_size, max_size))
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    return buffer.getvalue()

# ------------------- التبويبات -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 إضافة معاملة", "📊 التصنيف", "📋 المعاملات", "📈 إحصائيات"])

# ---------- التبويب 1: إضافة معاملة (تم إصلاح الحفظ) ----------
with tab1:
    uploaded = st.file_uploader("صورة الدفتر", type=["jpg", "jpeg", "png"])
    
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, width=250)
        
        # حالة حفظ البيانات
        if 'saved_success' not in st.session_state:
            st.session_state.saved_success = False
        
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("اسم العميل")
        with col2:
            amount = st.number_input("المبلغ", min_value=0.0, step=1.0, format="%.2f")
        
        transaction_date = st.date_input("تاريخ العملية", value=datetime.now())
        
        if st.button("🔍 استخراج من الصورة", type="primary"):
            with st.spinner("جاري معالجة الصورة..."):
                try:
                    # ضغط الصورة لتسريع المعالجة
                    img_bytes = compress_image(image)
                    img_base64 = base64.b64encode(img_bytes).decode()
                    
                    response = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "استخرج من هذه الصورة اسم العميل والمبلغ فقط. أجب: الاسم: ... المبلغ: ..."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                            ]
                        }],
                        temperature=0.1
                    )
                    result = response.choices[0].message.content
                    st.success("تم الاستخراج")
                    st.code(result)
                    
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', result)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', result)
                    
                    if name_match:
                        st.session_state['extracted_name'] = name_match.group(1).strip()
                    if amount_match:
                        st.session_state['extracted_amount'] = amount_match.group(1).strip()
                    
                except Exception as e:
                    st.error(f"خطأ: {e}")
        
        # استخدام القيم المستخرجة إذا وجدت
        if 'extracted_name' in st.session_state:
            customer_name = st.text_input("اسم العميل", value=st.session_state['extracted_name'])
        if 'extracted_amount' in st.session_state:
            amount = st.number_input("المبلغ", min_value=0.0, step=1.0, value=float(st.session_state['extracted_amount']))
        
        if st.button("💾 حفظ المعاملة", type="secondary"):
            if customer_name and amount > 0:
                c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                          (customer_name, amount, transaction_date.strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                st.success(f"✅ تم حفظ {customer_name} - {amount}")
                # مسح القيم المستخرجة
                st.session_state.pop('extracted_name', None)
                st.session_state.pop('extracted_amount', None)
                st.rerun()
            else:
                st.warning("أدخل الاسم والمبلغ")

# ---------- التبويب 2: التصنيف ----------
with tab2:
    st.subheader("تصنيف المدينين حسب التاريخ")
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions ORDER BY transaction_date DESC", conn)
    if not df.empty:
        df['التصنيف'] = df['transaction_date'].apply(classify_debt)
        counts = df['التصنيف'].value_counts().reset_index()
        counts.columns = ['التصنيف', 'العدد']
        fig = px.pie(counts, values='العدد', names='التصنيف', title="نسبة الديون", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
        
        for cat in ["🟢 حديثة (أقل من شهر)", "🟡 متوسطة (1-3 أشهر)", "🔴 قديمة (أكثر من 3 أشهر)"]:
            subset = df[df['التصنيف'] == cat]
            if not subset.empty:
                with st.expander(f"{cat} - {len(subset)} عميل"):
                    st.dataframe(subset[['name', 'amount', 'transaction_date']])
    else:
        st.info("لا توجد معاملات")

# ---------- التبويب 3: المعاملات ----------
with tab3:
    st.subheader("جميع المعاملات")
    df = pd.read_sql_query("SELECT name, amount, transaction_date, created_at FROM transactions ORDER BY transaction_date DESC", conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode()
        st.download_button("📥 تحميل CSV", csv, "transactions.csv")
    else:
        st.info("لا توجد معاملات")

# ---------- التبويب 4: إحصائيات ----------
with tab4:
    df = pd.read_sql_query("SELECT amount, transaction_date FROM transactions", conn)
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي الديون", f"{df['amount'].sum():,.2f}")
        col2.metric("عدد المعاملات", len(df))
        col3.metric("متوسط الدين", f"{df['amount'].mean():,.2f}")
        
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        monthly = df.groupby(df['transaction_date'].dt.to_period('M')).sum().reset_index()
        monthly['transaction_date'] = monthly['transaction_date'].astype(str)
        fig = px.bar(monthly, x='transaction_date', y='amount', title="الديون شهرياً")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات")

conn.close()
