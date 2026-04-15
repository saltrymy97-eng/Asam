import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
import numpy as np
from paddleocr import PaddleOCR
import re

# --- إعداد الصفحة ---
st.set_page_config(page_title="دفتر الحسابات الذكي", page_icon="📒", layout="centered")

# --- تهيئة session_state للتحكم بالتحديث ---
if 'data_updated' not in st.session_state:
    st.session_state.data_updated = False

# --- تحميل PaddleOCR مع دعم اللغة العربية ---
@st.cache_resource
def load_ocr():
    try:
        return PaddleOCR(
            lang='ar',
            use_angle_cls=True,
            det_db_thresh=0.3,
            det_db_box_thresh=0.5,
            use_gpu=False
        )
    except Exception as e:
        st.error(f"خطأ في تحميل PaddleOCR: {e}")
        return None

# --- دالة استخراج النص من الصورة ---
def extract_text_from_image(image_file):
    image = Image.open(image_file)
    image_np = np.array(image)
    
    ocr = load_ocr()
    if ocr is None:
        return ""
    
    result = ocr.ocr(image_np, cls=True)
    
    extracted_lines = []
    if result and result[0]:
        for line in result[0]:
            text = line[1][0]
            confidence = line[1][1]
            if confidence > 0.5:
                extracted_lines.append(text)
    
    return "\n".join(extracted_lines)

# --- دالة تحليل النص العربي ---
def parse_arabic_ledger_text(text):
    entries = []
    lines = text.split('\n')
    
    categories_map = {
        "طعام": ["طعام", "غداء", "عشاء", "فطور", "مطعم", "اكل", "أكل", "قهوة", "شاي"],
        "مواصلات": ["مواصلات", "بنزين", "سيارة", "تاكسي", "أجرة"],
        "تسوق": ["تسوق", "شراء", "ملابس", "جهاز"],
        "فواتير": ["فاتورة", "كهرباء", "ماء", "انترنت", "جوال"],
        "ترفيه": ["ترفيه", "سينما", "سفر", "رحلة"],
        "راتب": ["راتب", "مكافأة", "دخل"],
        "أخرى": []
    }
    
    income_keywords = ["راتب", "دخل", "مردود", "حوالة", "وارد", "إيراد"]
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        numbers = re.findall(r'[\d\u0660-\u0669]+(?:[.,][\d\u0660-\u0669]+)?', line)
        if not numbers:
            continue
        
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
        
        entry_type = "💸 مصروف"
        for keyword in income_keywords:
            if keyword in line:
                entry_type = "💵 دخل"
                break
        
        category = "أخرى"
        for cat, keywords in categories_map.items():
            for keyword in keywords:
                if keyword in line:
                    category = cat
                    break
            if category != "أخرى":
                break
        
        description = line
        for num in numbers:
            description = description.replace(num, "")
        common_words = ["ريال", "ر.س", "رس", "سعودي", "دولار", "$"]
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

# --- واجهة التطبيق الرئيسية ---
st.title("📒 دفتر الحسابات الذكي")
st.caption("مصاريفك باختصار | مع مسح ضوئي آلي للنصوص العربية")

# --- القائمة الجانبية ---
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
            
            if submitted:
                if amount > 0:
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
                    st.session_state.data_updated = True
                    # استخدام experimental_rerun بدل rerun
                    st.experimental_rerun()
                else:
                    st.error("المبلغ يجب أن يكون أكبر من صفر")
    
    with tab2:
        st.subheader("📸 مسح ضوئي للدفتر اليدوي")
        st.caption("التقط صورة لصفحة الدفتر وسيتم تحليلها تلقائياً")
        st.info("💡 نصيحة: تأكد من الإضاءة الجيدة ووضوح الخط")
        
        img_file = st.camera_input("التقط صورة الآن")
        
        if img_file:
            st.image(img_file, caption="الصورة الملتقطة", use_container_width=True)
            
            if st.button("🔍 تحليل وإضافة تلقائياً", type="primary"):
                with st.spinner("جارٍ تحليل الصورة... قد تستغرق العملية 10-20 ثانية."):
                    try:
                        extracted_text = extract_text_from_image(img_file)
                        
                        if not extracted_text:
                            st.warning("لم يتم التعرف على أي نص. حاول مرة أخرى.")
                        else:
                            st.subheader("📝 النص المستخرج")
                            st.text_area("النص الخام:", extracted_text, height=150)
                            
                            parsed_entries = parse_arabic_ledger_text(extracted_text)
                            
                            if parsed_entries:
                                st.subheader(f"✅ تم التعرف على {len(parsed_entries)} عملية")
                                st.dataframe(pd.DataFrame(parsed_entries), use_container_width=True)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("💾 حفظ جميع العمليات", type="primary"):
                                        df = load_data()
                                        new_df = pd.DataFrame(parsed_entries)
                                        df = pd.concat([df, new_df], ignore_index=True)
                                        save_data(df)
                                        st.success(f"تم حفظ {len(parsed_entries)} عملية بنجاح!")
                                        st.session_state.data_updated = True
                                        st.experimental_rerun()
                                with col2:
                                    if st.button("🗑️ إلغاء"):
                                        st.experimental_rerun()
                            else:
                                st.warning("لم يتم التعرف على أي عمليات مالية.")
                            
                    except Exception as e:
                        st.error(f"حدث خطأ: {e}")

# --- عرض البيانات في الصفحة الرئيسية ---
df = load_data()

if not df.empty:
    df['المبلغ'] = pd.to_numeric(df['المبلغ'])
    
    income_df = df[df['النوع'] == '💵 دخل']
    expense_df = df[df['النوع'] == '💸 مصروف']
    
    total_income = income_df['المبلغ'].sum()
    total_expense = expense_df['المبلغ'].sum()
    balance = total_income - total_expense
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 الرصيد الحالي", f"{balance:,.2f} ر.س")
    with col2:
        st.metric("📈 إجمالي الدخل", f"{total_income:,.2f} ر.س")
    with col3:
        st.metric("📉 إجمالي المصروف", f"{total_expense:,.2f} ر.س")
    
    st.divider()
    
    st.subheader("📋 آخر العمليات")
    df_display = df.sort_values(by="التاريخ", ascending=False).head(10).copy()
    df_display['المبلغ'] = df_display['المبلغ'].apply(lambda x: f"{x:,.2f}")
    st.dataframe(
        df_display[["التاريخ", "النوع", "التصنيف", "المبلغ", "الوصف"]],
        use_container_width=True,
        hide_index=True
    )
    
    if not expense_df.empty:
        st.subheader("📊 توزيع المصروفات (الشهر الحالي)")
        expense_df_copy = expense_df.copy()
        expense_df_copy['التاريخ'] = pd.to_datetime(expense_df_copy['التاريخ'])
        current_month = datetime.now().month
        current_year = datetime.now().year
        monthly_expense = expense_df_copy[
            (expense_df_copy['التاريخ'].dt.month == current_month) & 
            (expense_df_copy['التاريخ'].dt.year == current_year)
        ]
        
        if not monthly_expense.empty:
            cat_sum = monthly_expense.groupby('التصنيف')['المبلغ'].sum().reset_index()
            st.bar_chart(cat_sum.set_index('التصنيف'), use_container_width=True)
        else:
            st.info("لا توجد مصروفات هذا الشهر")
else:
    st.info("📌 لا توجد عمليات بعد. ابدأ بإضافة دخل أو مصروف من القائمة الجانبية ➡️")

# --- تذييل الصفحة ---
st.divider()
st.caption("📱 تطبيق دفتر حسابات ذكي - يدعم المسح الضوئي للنصوص العربية")
