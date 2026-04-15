import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
import numpy as np
import easyocr
import re

# --- إعداد الصفحة ---
st.set_page_config(page_title="دفتر الحسابات الذكي", page_icon="📒", layout="centered")

# --- تحميل EasyOCR مع إعدادات محسنة للعربية ---
@st.cache_resource
def load_arabic_reader():
    return easyocr.Reader(
        ['ar'],
        gpu=False,
        verbose=False,
        detector='DB',
        recognizer='arabic_cnn'
    )

def extract_text_from_image(image_file):
    image = Image.open(image_file)
    image_np = np.array(image)
    
    reader = load_arabic_reader()
    # استخدام معلمات دقيقة لاكتشاف النص العربي
    results = reader.readtext(
        image_np,
        detail=0,
        paragraph=False,
        contrast_ths=0.3,
        adjust_contrast=0.7,
        text_threshold=0.6,
        low_text=0.4,
        width_ths=0.8
    )
    
    # دمج النتائج في نص واحد مع فواصل أسطر
    return "\n".join(results)

def parse_arabic_ledger_text(text):
    entries = []
    lines = text.split('\n')
    
    categories_map = {
        "طعام": ["طعام", "غداء", "عشاء", "فطور", "مطعم", "اكل", "أكل", "قهوة", "شاي", "عصير"],
        "مواصلات": ["مواصلات", "بنزين", "ديزل", "سيارة", "قطار", "تاكسي", "أجرة", "موقف"],
        "تسوق": ["تسوق", "شراء", "ملابس", "حذاء", "جهاز", "هدية"],
        "فواتير": ["فاتورة", "كهرباء", "ماء", "غاز", "انترنت", "جوال", "اشتراك"],
        "ترفيه": ["ترفيه", "سينما", "مسرح", "رحلة", "سفر", "فندق"],
        "راتب": ["راتب", "مكافأة", "بدل", "عمولة", "دخل شهري"],
        "صحة": ["صحة", "دواء", "طبيب", "مستشفى", "صيدلية"],
        "تعليم": ["تعليم", "مدرسة", "جامعة", "دورة", "كتاب"]
    }
    
    income_keywords = ["راتب", "دخل", "مردود", "حوالة", "وارد", "إيراد", "مبيعات", "أجرة", "بدل", "مكافأة"]
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # استخراج الأرقام (عربية وهندية)
        numbers = re.findall(r'[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)?', line)
        if not numbers:
            continue
        
        # تحويل الأرقام العربية إلى إنجليزية
        def convert_arabic_numbers(text):
            arabic_numbers = '٠١٢٣٤٥٦٧٨٩'
            english_numbers = '0123456789'
            trans_table = str.maketrans(arabic_numbers, english_numbers)
            return text.translate(trans_table)
        
        amount_str = convert_arabic_numbers(numbers[-1])
        amount_str = amount_str.replace(',', '.')
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        
        if amount < 0.01 or amount > 1000000:
            continue
        
        # تحديد النوع
        entry_type = "💸 مصروف"
        for kw in income_keywords:
            if kw in line:
                entry_type = "💵 دخل"
                break
        
        # تحديد التصنيف
        category = "أخرى"
        for cat, keywords in categories_map.items():
            if any(kw in line for kw in keywords):
                category = cat
                break
        
        # تنظيف الوصف
        description = line
        for num in numbers:
            description = description.replace(num, "")
        common_words = ["ريال", "ر.س", "رس", "سعودي", "دولار", "$", "دفع", "سداد"]
        for word in common_words:
            description = description.replace(word, "")
        description = re.sub(r'\s+', ' ', description).strip()
        if not description or len(description) < 2:
            description = line[:30]
        
        entries.append({
            "التاريخ": datetime.now().strftime("%Y-%m-%d"),
            "النوع": entry_type,
            "التصنيف": category,
            "المبلغ": amount,
            "الوصف": description
        })
    
    return entries

# --- دوال إدارة البيانات ---
DATA_FILE = "ledger_data.csv"

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["التاريخ", "النوع", "التصنيف", "المبلغ", "الوصف"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# --- واجهة التطبيق ---
st.title("📒 دفتر الحسابات الذكي")
st.caption("مصاريفك باختصار | مع مسح ضوئي آلي للنصوص العربية")

with st.sidebar:
    st.header("➕ إضافة عملية جديدة")
    tab1, tab2 = st.tabs(["✍️ يدوي", "📸 مسح ضوئي"])
    
    with tab1:
        with st.form("entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                entry_type = st.radio("النوع", ["💵 دخل", "💸 مصروف"], horizontal=True)
            with col2:
                amount = st.number_input("المبلغ (ريال)", min_value=0.0, step=10.0, value=0.0)
            
            category = st.selectbox("التصنيف", ["طعام", "مواصلات", "تسوق", "فواتير", "ترفيه", "راتب", "صحة", "تعليم", "أخرى"])
            description = st.text_input("الوصف (اختياري)")
            date = st.date_input("التاريخ", datetime.now())
            
            submitted = st.form_submit_button("💾 حفظ العملية")
            if submitted and amount > 0:
                df = load_data()
                new_row = pd.DataFrame({
                    "التاريخ": [date.strftime("%Y-%m-%d")],
                    "النوع": [entry_type],
                    "التصنيف": [category],
                    "المبلغ": [amount],
                    "الوصف": [description if description else "-"]
                })
                df = pd.concat([df, new_row], ignore_index=True)
                save_data(df)
                st.success("تمت الإضافة بنجاح!")
                st.rerun()
            elif submitted:
                st.error("المبلغ يجب أن يكون أكبر من صفر")
    
    with tab2:
        st.subheader("📸 مسح ضوئي للدفتر اليدوي")
        img_file = st.camera_input("التقط صورة الآن")
        if img_file:
            st.image(img_file, use_container_width=True)
            if st.button("🔍 تحليل وإضافة تلقائياً"):
                with st.spinner("جارٍ تحليل الصورة..."):
                    try:
                        extracted_text = extract_text_from_image(img_file)
                        if not extracted_text:
                            st.warning("لم يتم التعرف على نص")
                        else:
                            st.text_area("النص المستخرج:", extracted_text, height=150)
                            parsed = parse_arabic_ledger_text(extracted_text)
                            if parsed:
                                st.dataframe(pd.DataFrame(parsed))
                                if st.button("💾 حفظ العمليات"):
                                    df = load_data()
                                    df = pd.concat([df, pd.DataFrame(parsed)], ignore_index=True)
                                    save_data(df)
                                    st.success(f"تم حفظ {len(parsed)} عملية!")
                                    st.rerun()
                            else:
                                st.warning("لم يتم العثور على عمليات مالية")
                    except Exception as e:
                        st.error(f"خطأ: {e}")

# --- عرض البيانات الرئيسية ---
df = load_data()
if not df.empty:
    df['المبلغ'] = pd.to_numeric(df['المبلغ'])
    income = df[df['النوع'] == '💵 دخل']['المبلغ'].sum()
    expense = df[df['النوع'] == '💸 مصروف']['المبلغ'].sum()
    balance = income - expense
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 الرصيد", f"{balance:,.2f} ر.س")
    col2.metric("📈 الدخل", f"{income:,.2f} ر.س")
    col3.metric("📉 المصروف", f"{expense:,.2f} ر.س")
    
    st.divider()
    st.subheader("📋 آخر العمليات")
    st.dataframe(df.sort_values("التاريخ", ascending=False).head(10), use_container_width=True, hide_index=True)
else:
    st.info("أضف أول عملية من القائمة الجانبية")
