import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import re
import base64

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", layout="wide")
st.title("📘 دفتر الحسابات إكسترا")
st.markdown("انسخ النص من عدسة جوجل ← الصقه هنا ← اضغط حفظ")

# ------------------- قاعدة البيانات -------------------
conn = sqlite3.connect('debter.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              amount REAL,
              date TEXT)''')
conn.commit()

# ------------------- واجهة -------------------
tab1, tab2 = st.tabs(["📝 إضافة معاملة", "📋 المعاملات"])

with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1️⃣ الصق النص من عدسة جوجل")
        pasted_text = st.text_area("النص", height=150)
        
        # رفع الصورة
        uploaded_img = st.file_uploader("2️⃣ (اختياري) ارفع صورة الدفتر", type=["jpg", "jpeg", "png"])
    
    with col2:
        st.subheader("3️⃣ النتيجة")
        if st.button("✅ تحليل وحفظ", type="primary"):
            if pasted_text.strip():
                # استخراج الاسم والمبلغ
                amounts = re.findall(r'\d+(?:[.,]\d+)?', pasted_text)
                amount = float(amounts[0].replace(',', '.')) if amounts else 0.0
                arabic_words = re.findall(r'[\u0600-\u06FF]{3,}', pasted_text)
                name = " ".join(arabic_words[:2]) if arabic_words else "غير معروف"
                
                # حفظ في قاعدة البيانات
                c.execute("INSERT INTO transactions (name, amount, date) VALUES (?,?,?)",
                          (name, amount, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                
                # حفظ الصورة إذا وجدت
                if uploaded_img:
                    filename = f"دفتر_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    with open(filename, "wb") as f:
                        f.write(uploaded_img.getvalue())
                    st.success(f"✅ تم حفظ الصورة: {filename}")
                
                st.success(f"✅ تم حفظ: {name} - {amount:,.0f} ريال")
                
                # عرض النتيجة للنسخ
                result_text = f"الاسم: {name}\nالمبلغ: {amount:,.0f} ريال\nالتاريخ: {datetime.now().strftime('%Y-%m-%d')}"
                st.code(result_text, language="text")
                
                # زر نسخ النتيجة
                st.markdown(f"""
                    <textarea id="copyText" style="position:absolute;left:-9999px">{result_text}</textarea>
                    <button onclick="copyToClipboard()" style="background-color:#28a745; color:white; padding:0.5rem 1rem; border:none; border-radius:8px; cursor:pointer; margin-top:10px">
                    📋 نسخ النتيجة إلى الحافظة
                    </button>
                    <script>
                    function copyToClipboard() {{
                        var text = document.getElementById("copyText");
                        text.select();
                        document.execCommand("copy");
                        alert("تم نسخ النتيجة");
                    }}
                    </script>
                """, unsafe_allow_html=True)
            else:
                st.warning("الرجاء لصق النص أولاً")

with tab2:
    st.subheader("جميع المعاملات")
    df = pd.read_sql_query("SELECT name, amount, date FROM transactions ORDER BY date DESC", conn)
    if not df.empty:
        st.dataframe(df.rename(columns={'name':'الاسم', 'amount':'المبلغ(ريال)', 'date':'التاريخ'}))
        st.download_button("📥 تحميل CSV", df.to_csv(index=False).encode(), "transactions.csv")
    else:
        st.info("لا توجد معاملات")

conn.close()
