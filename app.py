import streamlit as st
import pytesseract
from PIL import Image
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="دفتر الحسابات", layout="centered")

st.title("📒 دفتر الحسابات الذكي")

uploaded_file = st.file_uploader("📸 ارفع صورة", type=["jpg", "png", "jpeg"])

def classify_debt(date):
    days = (datetime.now() - date).days
    if days <= 30:
        return "🟢 حديث"
    elif days <= 90:
        return "🟡 متوسط"
    else:
        return "🔴 متأخر"

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, use_column_width=True)

    text = pytesseract.image_to_string(image, lang='eng')

    st.subheader("📄 النص المستخرج")
    st.write(text)

    data = []
    lines = text.split("\n")

    for line in lines:
        match = re.search(r"(\w+)\s+(\d+)\s+(له|عليه)", line)
        if match:
            name = match.group(1)
            amount = float(match.group(2))
            type_ = match.group(3)

            date = datetime.now()
            category = classify_debt(date)

            data.append({
                "الاسم": name,
                "المبلغ": amount,
                "النوع": type_,
                "التصنيف": category
            })

    if data:
        df = pd.DataFrame(data)
        st.subheader("📊 النتائج")
        st.dataframe(df)
    else:
        st.warning("❌ لا توجد بيانات مطابقة")
