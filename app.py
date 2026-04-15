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
    .stButton button { background-color: #2a5298; color: white; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>يعمل محلياً | العملة: ريال يمني 🇾🇪</p></div>', unsafe_allow_html=True)

# ------------------- إعداد Groq -------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    GROQ_API_KEY = st.text_input("🔑 مفتاح Groq API:", type="password")
    if not GROQ_API_KEY:
        st.stop()
client = Groq(api_key=GROQ_API_KEY)

# ------------------- قاعدة بيانات محلية -------------------
conn = sqlite3.connect('debter_extra.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              amount REAL,
              transaction_date TEXT,
              created_at TEXT,
              image_name TEXT)''')
conn.commit()

# ------------------- دالة ضغط الصورة -------------------
def compress_image(image, max_size=1024, quality=55):
    """ضغط الصورة من 6 ميجا إلى 200-300 كيلوبايت"""
    img = image.copy()
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()

# ------------------- دالة استخراج النص من صورة -------------------
def extract_from_image(image_bytes, image_name):
    """إرسال صورة إلى Groq واستخراج الاسم والمبلغ"""
    img_base64 = base64.b64encode(image_bytes).decode()
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "استخرج من هذه الصورة اسم العميل والمبلغ فقط. المبلغ بالريال اليمني. أجب بهذا الشكل:\nالاسم: ...\nالمبلغ: ..."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
        }],
        temperature=0.1
    )
    return response.choices[0].message.content

# ------------------- واجهة التبويبات -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 إضافة معاملات", "📊 تصنيف المدينين", "📋 جميع المعاملات", "📈 إحصائيات"])

# ---------- التبويب 1: رفع عدة صور ----------
with tab1:
    st.subheader("رفع صور الدفتر الورقي")
    st.caption("يمكنك رفع عدة صور معاً، وسيتم استخراج البيانات من كل صورة تلقائياً")
    
    uploaded_files = st.file_uploader("اختر صور الدفتر", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.info(f"✅ تم رفع {len(uploaded_files)} صورة")
        
        if st.button("🔍 استخراج البيانات من جميع الصور", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            for i, uploaded in enumerate(uploaded_files):
                status_text.text(f"جاري معالجة الصورة {i+1} من {len(uploaded_files)}...")
                
                # فتح الصورة
                image = Image.open(uploaded)
                
                # ضغط الصورة
                with st.spinner(f"ضغط الصورة {i+1}..."):
                    compressed = compress_image(image)
                
                # استخراج النص
                try:
                    result_text = extract_from_image(compressed, uploaded.name)
                    
                    # استخراج الاسم والمبلغ
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', result_text)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', result_text)
                    
                    name = name_match.group(1).strip() if name_match else ""
                    amount_str = amount_match.group(1) if amount_match else "0"
                    amount = float(amount_str.replace(',', '.'))
                    
                    results.append({
                        "image": uploaded.name,
                        "name": name,
                        "amount": amount,
                        "raw_text": result_text
                    })
                    
                    status_text.success(f"✅ تم استخراج: {name} - {amount} ريال")
                    
                except Exception as e:
                    st.error(f"خطأ في الصورة {uploaded.name}: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
                time.sleep(0.5)
            
            status_text.empty()
            st.session_state['batch_results'] = results
            st.success(f"تم استخراج {len(results)} معاملة بنجاح")
        
        # عرض النتائج والحفظ
        if 'batch_results' in st.session_state and st.session_state['batch_results']:
            st.subheader("📝 البيانات المستخرجة")
            
            for idx, res in enumerate(st.session_state['batch_results']):
                with st.expander(f"📸 {res['image']} - {res['name'] or 'غير معروف'}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        final_name = st.text_input(f"اسم العميل {idx+1}", value=res['name'])
                    with col2:
                        final_amount = st.number_input(f"المبلغ {idx+1} (ريال)", min_value=0.0, value=res['amount'], step=100.0, format="%.0f")
                    
                    trans_date = st.date_input(f"التاريخ {idx+1}", value=datetime.now())
                    
                    if st.button(f"💾 حفظ {final_name or 'المعاملة'}", key=f"save_{idx}"):
                        if final_name and final_amount > 0:
                            c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at, image_name) VALUES (?,?,?,?,?)",
                                      (final_name, final_amount, trans_date.strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), res['image']))
                            conn.commit()
                            st.success(f"✅ تم حفظ {final_name} - {final_amount:,.0f} ريال")
                            # إزالة من القائمة بعد الحفظ
                            st.session_state['batch_results'].pop(idx)
                            st.rerun()
                        else:
                            st.warning("يرجى إدخال الاسم والمبلغ")
            
            if st.button("🗑️ مسح جميع النتائج المؤقتة"):
                st.session_state.pop('batch_results', None)
                st.rerun()

# ---------- التبويب 2: تصنيف المدينين ----------
with tab2:
    st.subheader("📅 تصنيف المدينين حسب التاريخ")
    
    df = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions ORDER BY transaction_date DESC", conn)
    
    if not df.empty:
        def classify(date_str):
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                days = (datetime.now() - d).days
                if days <= 30: return "🟢 دين حديث (أقل من شهر)"
                elif days <= 90: return "🟡 دين متوسط (1-3 أشهر)"
                else: return "🔴 دين قديم (أكثر من 3 أشهر)"
            except:
                return "⚪ غير مصنف"
        
        df['التصنيف'] = df['transaction_date'].apply(classify)
        
        # رسم بياني
        counts = df['التصنيف'].value_counts().reset_index()
        counts.columns = ['التصنيف', 'العدد']
        fig = px.pie(counts, values='العدد', names='التصنيف', title="نسبة الديون (ريال يمني)", hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
        
        # عرض كل فئة
        for cat in ["🟢 دين حديث (أقل من شهر)", "🟡 دين متوسط (1-3 أشهر)", "🔴 دين قديم (أكثر من 3 أشهر)"]:
            subset = df[df['التصنيف'] == cat]
            if not subset.empty:
                total = subset['amount'].sum()
                with st.expander(f"{cat} - {len(subset)} عميل | إجمالي: {total:,.0f} ريال"):
                    st.dataframe(subset[['name', 'amount', 'transaction_date']], use_container_width=True)
    else:
        st.info("لا توجد معاملات بعد")

# ---------- التبويب 3: جميع المعاملات ----------
with tab3:
    st.subheader("سجل المعاملات")
    df = pd.read_sql_query("SELECT name, amount, transaction_date, created_at FROM transactions ORDER BY transaction_date DESC", conn)
    
    if not df.empty:
        st.dataframe(df.rename(columns={
            'name': 'اسم العميل',
            'amount': 'المبلغ (ريال)',
            'transaction_date': 'تاريخ العملية',
            'created_at': 'تاريخ الإضافة'
        }), use_container_width=True)
        
        total_all = df['amount'].sum()
        st.metric("إجمالي الديون", f"{total_all:,.0f} ريال يمني")
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 تحميل CSV", csv, "transactions.csv", "text/csv")
        
        if st.button("🗑️ حذف جميع المعاملات"):
            c.execute("DELETE FROM transactions")
            conn.commit()
            st.warning("تم حذف جميع المعاملات")
            st.rerun()
    else:
        st.info("لا توجد معاملات")

# ---------- التبويب 4: إحصائيات ----------
with tab4:
    st.subheader("📊 إحصائيات الديون (ريال يمني)")
    df = pd.read_sql_query("SELECT amount, transaction_date FROM transactions", conn)
    
    if not df.empty:
        total = df['amount'].sum()
        avg = df['amount'].mean()
        count = len(df)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("💵 إجمالي الديون", f"{total:,.0f} ريال")
        col2.metric("📊 متوسط الدين", f"{avg:,.0f} ريال")
        col3.metric("👥 عدد المعاملات", count)
        
        # رسم بياني شهري
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        monthly = df.groupby(df['transaction_date'].dt.to_period('M')).sum().reset_index()
        monthly['transaction_date'] = monthly['transaction_date'].astype(str)
        monthly['amount'] = monthly['amount']
        
        fig = px.bar(monthly, x='transaction_date', y='amount', title="إجمالي الديون شهرياً (ريال يمني)", 
                     labels={'transaction_date': 'الشهر', 'amount': 'المبلغ (ريال)'})
        st.plotly_chart(fig, use_container_width=True)
        
        # أعلى 5 مدينين
        top5 = pd.read_sql_query("SELECT name, SUM(amount) as total FROM transactions GROUP BY name ORDER BY total DESC LIMIT 5", conn)
        if not top5.empty:
            st.subheader("🏆 أعلى 5 مدينين")
            st.dataframe(top5.rename(columns={'name': 'الاسم', 'total': 'إجمالي الدين (ريال)'}), use_container_width=True)
    else:
        st.info("لا توجد بيانات")

conn.close()
st.caption("© 2025 دفتر الحسابات إكسترا | يعمل بالذكاء الاصطناعي Groq Vision | العملة: ريال يمني 🇾🇪")
