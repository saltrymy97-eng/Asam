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
import urllib.request

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", page_icon="📘", layout="wide")

# ------------------- تحميل الخط العربي (مرة واحدة) -------------------
@st.cache_resource
def load_arabic_font():
    """تحميل خط عربي لاستخدامه في PDF"""
    font_path = "NotoSansArabic.ttf"
    if not os.path.exists(font_path):
        # تحميل الخط من الإنترنت (رابط مباشر لخط Noto Sans Arabic)
        url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf"
        st.info("جاري تحميل الخط العربي لأول مرة... قد يستغرق بضع ثوان.")
        urllib.request.urlretrieve(url, font_path)
    pdfmetrics.registerFont(TTFont('NotoSansArabic', font_path))
    return True

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

# ------------------- دالة تجهيز النص العربي للـ PDF -------------------
def reshape_arabic(text):
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

# ------------------- دالة إنشاء PDF منسق (دعم كامل للعربية) -------------------
def generate_pdf(df):
    # تحميل الخط العربي
    load_arabic_font()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=20*mm, bottomMargin=20*mm)
    elements = []
    
    # إنشاء نمط يستخدم الخط العربي
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontName='NotoSansArabic',
        fontSize=18,
        alignment=1,
        textColor=colors.HexColor('#203a43'),
        spaceAfter=12
    )
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName='NotoSansArabic',
        fontSize=10,
        alignment=1
    )
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontName='NotoSansArabic',
        fontSize=12,
        alignment=1,
        textColor=colors.white
    )
    
    # عنوان التقرير
    title_text = reshape_arabic("تقرير دفتر الحسابات - إكسترا")
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 10))
    
    # تاريخ الإصدار
    date_text = reshape_arabic(f"تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    elements.append(Paragraph(date_text, normal_style))
    elements.append(Spacer(1, 20))
    
    # إجماليات سريعة
    total_debt = df['amount'].sum()
    total_customers = df['name'].nunique()
    summary_data = [
        [Paragraph(reshape_arabic("إجمالي الديون"), header_style), 
         Paragraph(f"{total_debt:,.0f} ريال", normal_style)],
        [Paragraph(reshape_arabic("عدد العملاء"), header_style), 
         Paragraph(str(total_customers), normal_style)]
    ]
    summary_table = Table(summary_data, colWidths=[80*mm, 80*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#203a43')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'NotoSansArabic'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.grey)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # جدول المعاملات
    headers = ['اسم العميل', 'المبلغ (ريال)', 'تاريخ العملية', 'تاريخ الإضافة']
    reshaped_headers = [reshape_arabic(h) for h in headers]
    table_data = [reshaped_headers]
    
    for _, row in df.iterrows():
        table_data.append([
            reshape_arabic(row['name']),
            f"{row['amount']:,.0f}",
            row['transaction_date'],
            row['created_at']
        ])
    
    col_widths = [60*mm, 40*mm, 40*mm, 40*mm]
    trans_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    trans_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c5364')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'NotoSansArabic'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,1), (-1,-1), 'NotoSansArabic'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
    ]))
    
    elements.append(trans_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ------------------- الواجهة -------------------
tab1, tab2, tab3, tab4 = st.tabs(["📸 معالجة تلقائية", "📊 لوحة التحكم", "📋 دفتر اليومية", "📈 الإحصائيات"])

# ... (باقي الكود كما هو دون تغيير)
