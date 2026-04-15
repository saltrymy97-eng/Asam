import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
import re
from groq import Groq
import plotly.express as px
import time
import os
import urllib.request

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

# ------------------- تحميل الخط العربي للصورة -------------------
@st.cache_resource
def load_arabic_font_for_image():
    font_path = "NotoSansArabic.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf"
        st.info("جاري تحميل الخط العربي لأول مرة... قد يستغرق بضع ثوان.")
        urllib.request.urlretrieve(url, font_path)
    return font_path

# ------------------- تحسينات CSS -------------------
st.markdown("""
<style>
    .stApp { background-color: #f4f7f6; }
    .app-header {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .card {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #eee;
    }
    .stat-card {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    .stat-value { font-size: 24px; font-weight: bold; color: #203a43; }
    .stat-label { font-size: 14px; color: #666; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>العملة: ريال يمني 🇾🇪 | يدعم الصفحات الكاملة</p></div>', unsafe_allow_html=True)

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
    max_dimension = 1200  # زيادة الحجم قليلاً لصفحات كاملة
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

# ------------------- دالة استخراج البيانات (معدلة للصفحات الكاملة) -------------------
def extract_all_entries_from_image(image_bytes):
    """ترسل الصورة إلى Groq وتطلب قائمة بكل الأسماء والمبالغ"""
    img_base64 = base64.b64encode(image_bytes).decode()
    
    # الموجه الجديد: يطلب استخراج جميع المدينين
    prompt_text = """
    هذه صورة لدفتر حسابات مكتوب باللغة العربية. استخرج جميع أسماء العملاء والمبالغ المستحقة عليهم.
    قم بإرجاع قائمة بالصيغة التالية (كل سطر يحتوي على اسم ومبلغ):
    الاسم: [اسم العميل] المبلغ: [المبلغ بالأرقام]
    الاسم: [اسم العميل] المبلغ: [المبلغ بالأرقام]
    ...
    لا تكتب أي شيء آخر غير القائمة. إذا لم تجد أي أسماء، اكتب "لا يوجد".
    """
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
        }],
        temperature=0.1,
        max_tokens=1024  # زيادة الحد الأقصى لاستيعاب قوائم طويلة
    )
    return response.choices[0].message.content

def parse_entries_from_text(text):
    """تحليل النص المسترجع من Groq واستخراج قائمة من (الاسم، المبلغ)"""
    entries = []
    if not text or text.strip() == "لا يوجد":
        return entries
    
    # نبحث عن جميع الأسطر التي تحتوي على "الاسم:" و "المبلغ:"
    lines = text.split('\n')
    for line in lines:
        # تجاهل الأسطر الفارغة
        if not line.strip():
            continue
            
        # استخدام regex مرن لاستخراج الاسم والمبلغ
        name_match = re.search(r'الاسم\s*[:：]\s*(.+?)(?:\s+المبلغ|\s*$)', line)
        amount_match = re.search(r'المبلغ\s*[:：]\s*(\d+(?:[.,]\d+)?)', line)
        
        if name_match and amount_match:
            name = name_match.group(1).strip()
            # إزالة أي نقاط زائدة أو رموز من الاسم
            name = re.sub(r'[^\w\s\u0600-\u06FF]', '', name).strip()
            amount_str = amount_match.group(1).replace(',', '.')
            try:
                amount = float(amount_str)
                if name and amount > 0:
                    entries.append((name, amount))
            except ValueError:
                continue
    return entries

# ------------------- دالة إنشاء صورة الدفتر -------------------
def generate_ledger_image(df):
    font_path = load_arabic_font_for_image()
    
    row_height = 40
    header_height = 50
    col_widths = [180, 100, 130, 150]
    table_width = sum(col_widths)
    table_height = header_height + (len(df) + 1) * row_height + 80
    
    img = Image.new('RGB', (table_width + 40, table_height + 100), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype(font_path, 24)
        font_header = ImageFont.truetype(font_path, 18)
        font_cell = ImageFont.truetype(font_path, 16)
    except:
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_cell = ImageFont.load_default()
    
    title = "دفتر الحسابات - إكسترا"
    draw.text((table_width//2, 20), title, font=font_title, fill='#203a43', anchor='mt')
    
    date_str = f"تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((table_width//2, 55), date_str, font=font_cell, fill='#555555', anchor='mt')
    
    y_start = 100
    x_start = 20
    
    headers = ['اسم العميل', 'المبلغ (ريال)', 'تاريخ العملية', 'تاريخ الإضافة']
    for i, header in enumerate(headers):
        x = x_start + sum(col_widths[:i])
        draw.rectangle([x, y_start, x + col_widths[i], y_start + header_height], fill='#2c5364')
        draw.text((x + col_widths[i]//2, y_start + header_height//2), header,
                 font=font_header, fill='white', anchor='mm')
    
    for i, row in df.iterrows():
        y = y_start + header_height + (i + 1) * row_height
        row_data = [
            row['name'],
            f"{row['amount']:,.0f}",
            row['transaction_date'],
            row['created_at']
        ]
        for j, cell in enumerate(row_data):
            x = x_start + sum(col_widths[:j])
            if i % 2 == 0:
                draw.rectangle([x, y, x + col_widths[j], y + row_height], fill='#f8f9fa')
            draw.text((x + 10, y + row_height//2), str(cell),
                     font=font_cell, fill='#333333', anchor='lm')
    
    total = df['amount'].sum()
    total_text = f"إجمالي الديون: {total:,.0f} ريال يمني"
    y_total = y_start + header_height + (len(df) + 1) * row_height + 20
    draw.text((x_start + table_width - 10, y_total), total_text,
             font=font_header, fill='#203a43', anchor='ra')
    
    for i in range(len(headers) + 1):
        x = x_start + (sum(col_widths[:i]) if i < len(headers) else table_width)
        draw.line([(x, y_start), (x, y_start + header_height + (len(df) + 1) * row_height)],
                 fill='#cccccc', width=1)
    
    draw.line([(x_start, y_start + header_height), (x_start + table_width, y_start + header_height)],
             fill='#cccccc', width=2)
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

# ------------------- الواجهة -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 معالجة تلقائية", "📊 لوحة التحكم", "📋 دفتر اليومية", "📈 الإحصائيات"])

# ================== التبويب 1: إضافة معاملات (يدعم الصفحات الكاملة) ==================
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚀 رفع صور الدفتر - يدعم الصفحات الكاملة")
    st.caption("ارفع صورة أو أكثر، وسيتم استخراج جميع المدينين الموجودين في كل صورة تلقائياً")
    
    uploaded_files = st.file_uploader("اختر الصور", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} صورة")
        
        if st.button("🚀 استخراج وحفظ الكل تلقائياً", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_saved = 0
            total_images = len(uploaded_files)
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"🔍 معالجة الصورة {i+1}/{total_images}: {file.name}")
                
                try:
                    # فتح وضغط الصورة
                    image = Image.open(file)
                    compressed = compress_image(image)
                    
                    # استخراج النص من الصورة
                    result_text = extract_all_entries_from_image(compressed)
                    
                    # تحليل النص إلى قائمة مدينين
                    entries = parse_entries_from_text(result_text)
                    
                    if entries:
                        saved_in_this_image = 0
                        for name, amount in entries:
                            c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                                      (name, amount, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit()
                            saved_in_this_image += 1
                            total_saved += 1
                        
                        status_text.success(f"✅ الصورة {i+1}: تم استخراج {saved_in_this_image} مدين | {file.name}")
                    else:
                        status_text.warning(f"⚠️ الصورة {i+1}: لم يتم العثور على مدينين | {file.name}")
                
                except Exception as e:
                    status_text.error(f"❌ خطأ في معالجة {file.name}: {e}")
                
                progress_bar.progress((i + 1) / total_images)
                time.sleep(0.5)
            
            progress_bar.empty()
            if total_saved > 0:
                st.success(f"🎉 تم حفظ {total_saved} معاملة من {total_images} صورة")
                st.balloons()
            else:
                st.warning("لم يتم حفظ أي معاملات")
            time.sleep(2)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ================== التبويب 2: لوحة التحكم ==================
with tab2:
    df_dashboard = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions", conn)
    
    if not df_dashboard.empty:
        total_debt = df_dashboard['amount'].sum()
        total_customers = df_dashboard['name'].nunique()
        avg_debt = df_dashboard['amount'].mean()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{total_debt:,.0f} ريال</div>
                <div class="stat-label">إجمالي الديون</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{total_customers}</div>
                <div class="stat-label">عدد العملاء</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{avg_debt:,.0f} ريال</div>
                <div class="stat-label">متوسط الدين</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 تصنيف الديون حسب العمر")
        
        def classify(d):
            try:
                days = (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days
                if days <= 30: return "🟢 حديث (أقل من شهر)"
                elif days <= 90: return "🟡 متوسط (1-3 أشهر)"
                return "🔴 قديم (أكثر من 3 أشهر)"
            except:
                return "⚪ غير مصنف"
        
        df_dashboard['التصنيف'] = df_dashboard['transaction_date'].apply(classify)
        
        counts = df_dashboard['التصنيف'].value_counts().reset_index()
        counts.columns = ['التصنيف', 'العدد']
        fig = px.pie(counts, values='العدد', names='التصنيف', title="نسبة الديون", hole=0.3,
                    color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
        
        for cat in ["🟢 حديث (أقل من شهر)", "🟡 متوسط (1-3 أشهر)", "🔴 قديم (أكثر من 3 أشهر)"]:
            sub = df_dashboard[df_dashboard['التصنيف'] == cat]
            if not sub.empty:
                total = sub['amount'].sum()
                with st.expander(f"{cat} - {len(sub)} عميل | إجمالي: {total:,.0f} ريال"):
                    st.dataframe(sub[['name', 'amount', 'transaction_date']], use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("لا توجد معاملات بعد")

# ================== التبويب 3: دفتر اليومية ==================
with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    df_all = pd.read_sql_query("SELECT name, amount, transaction_date, created_at FROM transactions ORDER BY transaction_date DESC", conn)
    if not df_all.empty:
        st.dataframe(df_all.rename(columns={
            'name': 'اسم العميل',
            'amount': 'المبلغ (ريال)',
            'transaction_date': 'تاريخ العملية',
            'created_at': 'تاريخ الإضافة'
        }), use_container_width=True, height=300)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            total = df_all['amount'].sum()
            st.metric("💵 إجمالي الديون", f"{total:,.0f} ريال يمني")
        with col2:
            if st.button("📸 تحميل صورة الدفتر"):
                with st.spinner("جاري إنشاء صورة الدفتر..."):
                    img_buffer = generate_ledger_image(df_all)
                    st.download_button(
                        label="📥 اضغط لتحميل الصورة",
                        data=img_buffer,
                        file_name=f"دفتر_الحسابات_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                        mime="image/png"
                    )
        with col3:
            if st.button("🗑️ حذف جميع المعاملات", type="secondary"):
                c.execute("DELETE FROM transactions")
                conn.commit()
                st.warning("تم حذف جميع المعاملات")
                st.rerun()
    else:
        st.info("لا توجد معاملات")
    st.markdown('</div>', unsafe_allow_html=True)

# ================== التبويب 4: إحصائيات ==================
with tab4:
    df_stats = pd.read_sql_query("SELECT amount, transaction_date FROM transactions", conn)
    if not df_stats.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 إجمالي الديون", f"{df_stats['amount'].sum():,.0f} ريال")
        col2.metric("📊 عدد المعاملات", len(df_stats))
        col3.metric("📈 متوسط الدين", f"{df_stats['amount'].mean():,.0f} ريال")
        
        df_stats['transaction_date'] = pd.to_datetime(df_stats['transaction_date'], errors='coerce')
        df_stats = df_stats.dropna(subset=['transaction_date'])
        
        if not df_stats.empty:
            df_stats['month'] = df_stats['transaction_date'].dt.to_period('M')
            monthly = df_stats.groupby('month')['amount'].sum().reset_index()
            monthly['month'] = monthly['month'].astype(str)
            fig = px.bar(monthly, x='month', y='amount', title="إجمالي الديون شهرياً (ريال يمني)",
                        color_discrete_sequence=['#203a43'])
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
