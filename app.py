import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
import re
import plotly.express as px
import time
import os
import urllib.request
import pytesseract

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
    .preview-box {
        border: 2px solid #2c5364;
        border-radius: 10px;
        padding: 15px;
        background-color: #f8f9fa;
        margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header"><h1>📘 دفتر الحسابات إكسترا</h1><p>العملة: ريال يمني 🇾🇪 | OCR دقيق للعربية</p></div>', unsafe_allow_html=True)

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

# ------------------- دالة استخراج النص باستخدام Tesseract -------------------
def extract_text_with_tesseract(image):
    # تحديد اللغة العربية
    # إذا كان Tesseract مثبتًا في مسار غير قياسي على السيرفر، قد نحتاج لتحديد المسار
    # لكن في Streamlit Cloud يكون مثبتًا في المسار الافتراضي
    try:
        text = pytesseract.image_to_string(image, lang='ara')
    except:
        # إذا فشل، جرب بدون تحديد لغة
        text = pytesseract.image_to_string(image)
    return text

def parse_name_amount_pairs(text):
    """محاولة استخراج أزواج (اسم، مبلغ) من النص المستخرج عبر OCR"""
    entries = []
    if not text:
        return entries
    
    # تنظيف النص: إزالة الأسطر الفارغة والمسافات الزائدة
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines:
        # محاولة إيجاد نمط: اسم ثم رقم
        # يدعم الأسماء العربية (أحرف ومسافات) ثم رقم
        match = re.search(r'([\u0600-\u06FF\w\s]+?)\s+(\d+(?:[.,]\d+)?)', line)
        if match:
            name = match.group(1).strip()
            amount_str = match.group(2).replace(',', '.')
            try:
                amount = float(amount_str)
                if name and amount > 0:
                    entries.append({"name": name, "amount": amount})
            except ValueError:
                continue
        
        # نمط آخر: رقم ثم اسم
        if not match:
            match = re.search(r'(\d+(?:[.,]\d+)?)\s+([\u0600-\u06FF\w\s]+)', line)
            if match:
                amount_str = match.group(1).replace(',', '.')
                name = match.group(2).strip()
                try:
                    amount = float(amount_str)
                    if name and amount > 0:
                        entries.append({"name": name, "amount": amount})
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
tab1, tab2, tab3, tab4 = st.tabs(["📸 معالجة OCR", "📊 لوحة التحكم", "📋 دفتر اليومية", "📈 الإحصائيات"])

# ================== التبويب 1: OCR + معاينة ==================
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚀 رفع صور الدفتر - OCR دقيق للعربية (Tesseract)")
    st.caption("ارفع الصورة، راجع البيانات المستخرجة، ثم احفظها")
    
    uploaded_files = st.file_uploader("اختر الصور", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} صورة")
        
        for idx, file in enumerate(uploaded_files):
            st.markdown(f"### 📄 الصورة {idx+1}: {file.name}")
            
            col_img, col_data = st.columns([1, 2])
            with col_img:
                image = Image.open(file)
                st.image(image, caption="الصورة المرفوعة", use_container_width=True)
            
            with col_data:
                if st.button(f"🔍 استخراج النص (OCR) {idx+1}", key=f"ocr_{idx}"):
                    with st.spinner("جاري تحليل الصورة بدقة..."):
                        try:
                            # استخدام Tesseract لاستخراج النص
                            extracted_text = extract_text_with_tesseract(image)
                            st.text_area("النص الخام المستخرج:", extracted_text, height=100)
                            
                            # محاولة تحليل الأسماء والمبالغ
                            entries = parse_name_amount_pairs(extracted_text)
                            
                            if entries:
                                st.success(f"تم اقتراح {len(entries)} مدين محتمل")
                                
                                st.markdown("**📋 البيانات المستخرجة (يمكنك تعديلها):**")
                                edited_entries = []
                                for i, entry in enumerate(entries):
                                    col1, col2, col3 = st.columns([3, 2, 1])
                                    with col1:
                                        new_name = st.text_input("الاسم", value=entry['name'], key=f"name_{idx}_{i}")
                                    with col2:
                                        new_amount = st.number_input("المبلغ", value=entry['amount'], min_value=0.0, key=f"amount_{idx}_{i}")
                                    with col3:
                                        keep = st.checkbox("حفظ", value=True, key=f"keep_{idx}_{i}")
                                    if keep:
                                        edited_entries.append({"name": new_name, "amount": new_amount})
                                
                                # إمكانية إضافة مدين يدوي
                                st.markdown("---")
                                st.markdown("**➕ إضافة مدين جديد يدوياً:**")
                                manual_name = st.text_input("اسم العميل", key=f"man_name_{idx}")
                                manual_amount = st.number_input("المبلغ", min_value=0.0, key=f"man_amount_{idx}")
                                if st.button("أضف إلى القائمة", key=f"add_man_{idx}"):
                                    if manual_name and manual_amount > 0:
                                        edited_entries.append({"name": manual_name, "amount": manual_amount})
                                        st.success(f"تمت إضافة {manual_name}")
                                
                                # زر تأكيد الحفظ
                                if edited_entries and st.button(f"💾 تأكيد وحفظ {len(edited_entries)} معاملة", key=f"save_{idx}"):
                                    saved = 0
                                    for e in edited_entries:
                                        if e['name'] and e['amount'] > 0:
                                            c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                                                      (e['name'], e['amount'], datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                                            conn.commit()
                                            saved += 1
                                    st.success(f"✅ تم حفظ {saved} معاملة")
                                    st.rerun()
                            else:
                                st.warning("⚠️ لم يتم التعرف على أسماء ومبالغ. يمكنك إضافتها يدوياً أدناه.")
                                # إضافة يدوية
                                manual_name = st.text_input("اسم العميل", key=f"man_name_only_{idx}")
                                manual_amount = st.number_input("المبلغ", min_value=0.0, key=f"man_amount_only_{idx}")
                                if st.button("حفظ يدوي", key=f"save_man_{idx}"):
                                    if manual_name and manual_amount > 0:
                                        c.execute("INSERT INTO transactions (name, amount, transaction_date, created_at) VALUES (?,?,?,?)",
                                                  (manual_name, manual_amount, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                                        conn.commit()
                                        st.success(f"تم حفظ {manual_name}")
                                        st.rerun()
                        except Exception as e:
                            st.error(f"❌ خطأ: {e}")
            st.divider()
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
