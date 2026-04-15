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
from reportlab.lib.utils import ImageReader
import plotly.express as px
import tempfile
import os

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

# ------------------- تخصيص الواجهة -------------------
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72, #2a5298);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    .badge-new {
        background-color: #28a745;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.8rem;
    }
    .badge-old {
        background-color: #dc3545;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>استخراج تلقائي للبيانات من صور الدفتر الورقي باستخدام Groq Vision</p></div>', unsafe_allow_html=True)

# ------------------- إعداد Groq -------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    GROQ_API_KEY = st.text_input("🔑 أدخل مفتاح Groq API:", type="password")
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
              created_at TEXT,
              raw_text TEXT)''')
conn.commit()

# ------------------- دوال مساعدة -------------------
def classify_debt(transaction_date_str):
    """تصنيف المديونية حسب التاريخ: حديثة، متوسطة، قديمة"""
    try:
        t_date = datetime.strptime(transaction_date_str, "%Y-%m-%d")
        today = datetime.now()
        diff = (today - t_date).days
        if diff <= 30:
            return "🟢 حديثة (أقل من شهر)"
        elif diff <= 90:
            return "🟡 متوسطة (1-3 أشهر)"
        else:
            return "🔴 قديمة (أكثر من 3 أشهر)"
    except:
        return "⚪ غير مصنف"

def generate_pdf(dataframe):
    """إنشاء ملف PDF بالمعاملات"""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "تقرير دفتر الحسابات إكسترا")
    p.setFont("Helvetica", 10)
    y = height - 100
    for index, row in dataframe.iterrows():
        p.drawString(50, y, f"العميل: {row['name']} | المبلغ: {row['amount']} | التاريخ: {row['transaction_date']} | التصنيف: {row['classification']}")
        y -= 20
        if y < 50:
            p.showPage()
            y = height - 50
    p.save()
    buffer.seek(0)
    return buffer

# ------------------- واجهة التبويبات -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 إضافة معاملة", "📊 التصنيف حسب التاريخ", "📋 جميع المعاملات", "📈 إحصائيات"])

# ---------- التبويب 1: إضافة معاملة ----------
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded = st.file_uploader("ارفع صورة الدفتر الورقي", type=["jpg", "jpeg", "png"])
    with col2:
        manual_date = st.date_input("📅 تاريخ العملية (اختياري)", value=datetime.now())
    
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, caption="الصورة المرفوعة", width=300)
        
        if st.button("🔍 استخراج البيانات بالذكاء الاصطناعي", type="primary"):
            # تحويل الصورة إلى base64
            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            with st.spinner("Groq Vision يقرأ الدفتر..."):
                try:
                    response = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "استخرج من هذه الصورة اسم العميل والمبلغ فقط. أجب بهذا الشكل:\nالاسم: ...\nالمبلغ: ...\nإذا لم تجد، اكتب 'غير موجود'."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                            ]
                        }],
                        temperature=0.1
                    )
                    result = response.choices[0].message.content
                    st.success("✅ تم الاستخراج")
                    st.text_area("النص المستخرج", result, height=100)
                    
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', result)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', result)
                    
                    default_name = name_match.group(1).strip() if name_match else ""
                    default_amount = amount_match.group(1) if amount_match else ""
                    
                    final_name = st.text_input("اسم العميل", default_name)
                    final_amount = st.text_input("المبلغ", default_amount)
                    final_date = st.date_input("تاريخ العملية (قابل للتعديل)", value=manual_date)
                    
                    if st.button("💾 حفظ المعاملة"):
                        if final_name and final_amount:
                            try:
                                amount_float = float(final_amount.replace(',', '.'))
                                c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at, raw_text) VALUES (?,?,?,?,?)",
                                          (final_name, amount_float, final_date.strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result))
                                conn.commit()
                                st.success(f"تم حفظ معاملة {final_name} بمبلغ {amount_float} بتاريخ {final_date}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"خطأ: {e}")
                        else:
                            st.warning("يرجى إدخال الاسم والمبلغ")
                except Exception as e:
                    st.error(f"فشل في Groq: {e}")

# ---------- التبويب 2: تصنيف حسب التاريخ ----------
with tab2:
    st.subheader("📅 تصنيف المدينين حسب أقدمية الديون")
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions ORDER BY transaction_date DESC", conn)
    if not df.empty:
        df['classification'] = df['transaction_date'].apply(classify_debt)
        col_counts = df['classification'].value_counts().reset_index()
        col_counts.columns = ['التصنيف', 'العدد']
        fig = px.pie(col_counts, values='العدد', names='التصنيف', title="نسبة الديون حسب الفئات", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### تفاصيل التصنيفات")
        for cat in ["🟢 حديثة (أقل من شهر)", "🟡 متوسطة (1-3 أشهر)", "🔴 قديمة (أكثر من 3 أشهر)"]:
            subset = df[df['classification'] == cat]
            if not subset.empty:
                with st.expander(f"{cat} - {len(subset)} عميل"):
                    st.dataframe(subset[['name', 'amount', 'transaction_date']], use_container_width=True)
    else:
        st.info("لا توجد معاملات لعرضها")

# ---------- التبويب 3: جميع المعاملات ----------
with tab3:
    st.subheader("📋 سجل المعاملات")
    df_all = pd.read_sql_query("SELECT id, name, amount, transaction_date, created_at FROM transactions ORDER BY transaction_date DESC", conn)
    if not df_all.empty:
        # إضافة عمود التصنيف
        df_all['التصنيف'] = df_all['transaction_date'].apply(classify_debt)
        st.dataframe(df_all, use_container_width=True)
        
        # أزرار التحميل
        col_a, col_b = st.columns(2)
        with col_a:
            csv = df_all.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل CSV", csv, "transactions.csv", "text/csv")
        with col_b:
            pdf_buffer = generate_pdf(df_all)
            st.download_button("📥 تحميل PDF", pdf_buffer, "transactions.pdf", "application/pdf")
        
        if st.button("🗑️ حذف جميع المعاملات"):
            c.execute("DELETE FROM transactions")
            conn.commit()
            st.warning("تم الحذف الكامل")
            st.rerun()
    else:
        st.info("لا توجد معاملات")

# ---------- التبويب 4: إحصائيات ----------
with tab4:
    st.subheader("📈 إحصائيات وأرقام")
    df_stats = pd.read_sql_query("SELECT amount, transaction_date FROM transactions", conn)
    if not df_stats.empty:
        total = df_stats['amount'].sum()
        avg = df_stats['amount'].mean()
        count = len(df_stats)
        latest = df_stats['transaction_date'].max()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("إجمالي الديون", f"{total:,.2f}")
        col2.metric("متوسط الدين", f"{avg:,.2f}")
        col3.metric("عدد المعاملات", count)
        col4.metric("آخر عملية", latest)
        
        # رسم بياني
        df_stats['transaction_date'] = pd.to_datetime(df_stats['transaction_date'])
        df_weekly = df_stats.groupby(df_stats['transaction_date'].dt.to_period('M')).sum().reset_index()
        df_weekly['transaction_date'] = df_weekly['transaction_date'].astype(str)
        fig2 = px.bar(df_weekly, x='transaction_date', y='amount', title="إجمالي الديون شهرياً")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("لا توجد بيانات للإحصائيات")

conn.close()
st.markdown("---")
st.caption("© 2025 دفتر الحسابات إكسترا - يعمل بالذكاء الاصطناعي Groq Vision")
