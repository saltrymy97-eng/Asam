import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import base64
from io import BytesIO
import re
from groq import Groq

# ------------------- إعداد Groq -------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    GROQ_API_KEY = st.text_input("أدخل مفتاح Groq API:", type="password")
    if not GROQ_API_KEY:
        st.stop()

client = Groq(api_key=GROQ_API_KEY)

# ------------------- قاعدة البيانات -------------------
conn = sqlite3.connect('debter.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              amount REAL,
              date TEXT,
              raw_text TEXT)''')
conn.commit()

# ------------------- واجهة Streamlit -------------------
st.set_page_config(page_title="دفتر الحسابات - Groq", layout="wide")
st.title("📒 دفتر الحسابات مع Groq Vision (Llama 4)")

tab1, tab2 = st.tabs(["📸 إضافة معاملة", "📋 المعاملات"])

with tab1:
    uploaded = st.file_uploader("صورة الدفتر الورقي", type=["jpg", "jpeg", "png"])
    if uploaded:
        image = Image.open(uploaded)
        st.image(image, width=350)
        
        if st.button("🔍 استخراج البيانات"):
            # تحويل الصورة إلى base64
            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            with st.spinner("Groj يقرأ الصورة..."):
                try:
                    response = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",  # النموذج الجديد
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "استخرج من هذه الصورة اسم العميل والمبلغ فقط. أجب بهذا الشكل:\nالاسم: ...\nالمبلغ: ...\nإذا لم تجد، اكتب 'غير موجود'."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{img_base64}"
                                        }
                                    }
                                ]
                            }
                        ],
                        temperature=0.1
                    )
                    
                    result = response.choices[0].message.content
                    st.success("✅ تم الاستخراج بنجاح")
                    st.text_area("النص المستخرج", result, height=150)
                    
                    # استخراج الاسم والمبلغ
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', result)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', result)
                    
                    default_name = name_match.group(1).strip() if name_match else ""
                    default_amount = amount_match.group(1) if amount_match else ""
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        final_name = st.text_input("اسم العميل", value=default_name)
                    with col2:
                        final_amount = st.text_input("المبلغ", value=default_amount)
                    
                    if st.button("💾 حفظ المعاملة"):
                        if final_name and final_amount:
                            try:
                                amount_float = float(final_amount.replace(',', '.'))
                                c.execute(
                                    "INSERT INTO transactions (name, amount, date, raw_text) VALUES (?,?,?,?)",
                                    (final_name, amount_float, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result)
                                )
                                conn.commit()
                                st.success(f"تم حفظ معاملة {final_name} بمبلغ {amount_float}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في الحفظ: {e}")
                        else:
                            st.warning("يرجى إدخال اسم العميل والمبلغ")
                            
                except Exception as e:
                    st.error(f"فشل الاتصال بـ Groq: {e}")

with tab2:
    st.subheader("جميع المعاملات المسجلة")
    df = pd.read_sql_query("SELECT id, name, amount, date FROM transactions ORDER BY date DESC", conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 تحميل CSV", csv, "transactions.csv", "text/csv")
        if st.button("🗑️ حذف جميع المعاملات"):
            c.execute("DELETE FROM transactions")
            conn.commit()
            st.warning("تم حذف جميع المعاملات")
            st.rerun()
    else:
        st.info("لا توجد معاملات بعد")

conn.close()
