import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import base64
from io import BytesIO
import re
from groq import Groq

# إعداد Groq
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    GROQ_API_KEY = st.text_input("أدخل مفتاح Groq API:", type="password")
    if not GROQ_API_KEY:
        st.stop()

client = Groq(api_key=GROQ_API_KEY)

# قاعدة البيانات
conn = sqlite3.connect('debter.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              amount REAL,
              date TEXT,
              raw_text TEXT)''')
conn.commit()

st.set_page_config(page_title="دفتر الحسابات - Groq", layout="wide")
st.title("دفتر الحسابات مع Groq Vision")

tab1, tab2 = st.tabs(["إضافة معاملة", "المعاملات"])

with tab1:
    uploaded = st.file_uploader("صورة الدفتر", type=["jpg", "jpeg", "png"])
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, width=300)
        if st.button("استخراج البيانات"):
            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            with st.spinner("جارٍ الاستخراج..."):
                try:
                    response = client.chat.completions.create(
                        model="llama-3.2-11b-vision-preview",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "استخرج اسم العميل والمبلغ من هذه الصورة. أجب بهذا الشكل:\nالاسم: ...\nالمبلغ: ..."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                            ]
                        }],
                        temperature=0.1
                    )
                    result = response.choices[0].message.content
                    st.success("تم الاستخراج")
                    st.text_area("النص المستخرج", result, height=150)
                    name_match = re.search(r'الاسم:\s*(.+)', result)
                    amount_match = re.search(r'المبلغ:\s*(\d+)', result)
                    default_name = name_match.group(1) if name_match else ""
                    default_amount = amount_match.group(1) if amount_match else ""
                    name = st.text_input("اسم العميل", default_name)
                    amount = st.text_input("المبلغ", default_amount)
                    if st.button("حفظ"):
                        if name and amount:
                            c.execute("INSERT INTO transactions (name, amount, date, raw_text) VALUES (?,?,?,?)",
                                      (name, float(amount), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result))
                            conn.commit()
                            st.success("تم الحفظ")
                            st.rerun()
                except Exception as e:
                    st.error(f"خطأ: {e}")

with tab2:
    df = pd.read_sql_query("SELECT name, amount, date FROM transactions ORDER BY date DESC", conn)
    if not df.empty:
        st.dataframe(df)
        csv = df.to_csv(index=False).encode()
        st.download_button("تحميل CSV", csv, "transactions.csv", "text/csv")
    else:
        st.info("لا توجد معاملات")

conn.close()
