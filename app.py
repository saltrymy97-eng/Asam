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
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
import os

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

# ------------------- تحسينات CSS -------------------
st.markdown("""
<style>
    /* إعدادات عامة */
    .stApp { background-color: #f4f7f6; }
    
    /* ترويسة مخصصة */
    .app-header {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* تصميم البطاقات */
    .card {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #eee;
    }

    /* بطاقات الإحصائيات */
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

    /* أزرار مخصصة */
    .custom-button {
        background-color: #203a43;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-header"><h1>📘 دفتر الحسابات إكسترا بالذكاء الاصطناعي</h1><p>العملة: ريال يمني 🇾🇪 | تلقائي بالكامل</p></div>', unsafe_allow_html=True)

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

# ------------------- دالة إنشاء PDF منسق (جديد) -------------------
def generate_pdf(df):
    """توليد ملف PDF منسق بالعربية لدفتر الحسابات"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=20*mm, bottomMargin=20*mm)
    elements = []
    
    # تجهيز الخط العربي (نستخدم خط DejaVu المدمج مع fallback)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        alignment=1,  #居中
        textColor=colors.HexColor('#203a43'),
        spaceAfter=12
    )
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        alignment=1,
        textColor=colors.white
    )
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        alignment=1
    )
    
    # عنوان التقرير
    title_text = "تقرير دفتر الحسابات - إكسترا"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 10))
    
    # تاريخ الإصدار
    date_text = f"تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    elements.append(Paragraph(date_text, normal_style))
    elements.append(Spacer(1, 20))
    
    # إجماليات سريعة
    total_debt = df['amount'].sum()
    total_customers = df['name'].nunique()
    summary_data = [
        [Paragraph("إجمالي الديون", header_style), 
         Paragraph(f"{total_debt:,.0f} ريال", normal_style)],
        [Paragraph("عدد العملاء", header_style), 
         Paragraph(str(total_customers), normal_style)]
    ]
    summary_table = Table(summary_data, colWidths=[80*mm, 80*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#203a43')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.grey)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # جدول المعاملات
    # تحضير البيانات مع تشكيل عربي صحيح
    reshaped_headers = ['اسم العميل', 'المبلغ (ريال)', 'تاريخ العملية', 'تاريخ الإضافة']
    table_data = [reshaped_headers]
    
    for _, row in df.iterrows():
        table_data.append([
            row['name'],
            f"{row['amount']:,.0f}",
            row['transaction_date'],
            row['created_at']
        ])
    
    # إنشاء الجدول
    col_widths = [60*mm, 40*mm, 40*mm, 40*mm]
    trans_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    trans_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c5364')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
    ]))
    
    elements.append(trans_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ------------------- الواجهة -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 معالجة تلقائية", "📊 لوحة التحكم", "📋 دفتر اليومية", "📈 الإحصائيات"])

# ================== التبويب 1: إضافة معاملات ==================
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚀 رفع صور الدفتر - تلقائي بالكامل")
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
    st.markdown('</div>', unsafe_allow_html=True)

# ================== التبويب 2: لوحة التحكم (نظرة عامة) ==================
with tab2:
    df_dashboard = pd.read_sql_query("SELECT name, amount, transaction_date FROM transactions", conn)
    
    if not df_dashboard.empty:
        # بطاقات إحصائية سريعة
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

        st.markdown('</div>', unsafe_allow_html=True)
        
        # تصنيف الديون
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

# ================== التبويب 3: دفتر اليومية (جميع المعاملات) ==================
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
            # تحميل CSV
            csv = df_all.to_csv(index=False).encode('utf-8')
            st.download_button("📥 تحميل CSV", csv, "transactions.csv", "text/csv")
        with col3:
            # زر تصدير PDF
            if st.button("📄 تصدير PDF منسق"):
                with st.spinner("جاري إنشاء ملف PDF..."):
                    pdf_buffer = generate_pdf(df_all)
                    st.download_button(
                        label="📥 اضغط لتحميل PDF",
                        data=pdf_buffer,
                        file_name=f"دفتر_الحسابات_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                        mime="application/pdf"
                    )
        
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
        
        # تحويل عمود التاريخ من نص إلى تاريخ
        df_stats['transaction_date'] = pd.to_datetime(df_stats['transaction_date'], errors='coerce')
        df_stats = df_stats.dropna(subset=['transaction_date'])
        
        if not df_stats.empty:
            # تجميع شهري
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
