import streamlit as st
import easyocr
import pandas as pd
import re
from PIL import Image
import numpy as np
from datetime import datetime

st.set_page_config(page_title="دفتر الحسابات الذكي", layout="centered")

st.title("📒 دفتر الحسابات الذكي (EasyOCR)")

uploaded_file = st.file_uploader("📸 ارفع صورة الدفتر", type=["jpg", "png", "jpeg"])

reader = easyocr.Reader(['ar', 'en'])

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
    st.image(image, caption="الصورة", use_container_width=True)

    img_array = np.array(image)

    results = reader.readtext(img_array, detail=0)

    text = "\n".join(results)

    st.subheader("📄 النص المستخرج")
    st.write(text)

    data = []

    for line in results:
        match = re.search(r"(.+)\s+(\d+)\s+(له|عليه)", line)
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
        st.warning("❌ لم يتم العثور على بيانات مطابقة")
