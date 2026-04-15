import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import re
import base64
import io

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", layout="wide")
st.title("📘 دفتر الحسابات إكسترا")
st.markdown("انسخ النص من عدسة جوجل ← اضغط زر 'لصق' ← يحفظ تلقائياً + تنزيل الصورة")

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
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📋 النص المستخرج من عدسة جوجل")
    pasted_text = st.text_area("الصق النص هنا", height=150, key="pasted_text")
    
    # زر لصق باستخدام HTML/JavaScript (يعمل في المتصفح)
    st.markdown("""
        <button id="pasteBtn" style="background-color:#2a5298; color:white; padding:0.5rem 1rem; border:none; border-radius:8px; cursor:pointer;">
        📋 لصق من الحافظة
        </button>
        <script>
        document.getElementById('pasteBtn').onclick = async function() {
            try {
                const text = await navigator.clipboard.readText();
                const textarea = parent.document.querySelector('textarea');
                if (textarea) {
                    textarea.value = text;
                    textarea.dispatchEvent(new Event('input', {bubbles: true}));
                }
            } catch(e) { alert('الرجاء السماح بالوصول إلى الحافظة'); }
        };
        </script>
    """, unsafe_allow_html=True)
    
    uploaded_img = st.file_uploader("📸 ارفع صورة الدفتر (سيتم تنزيلها تلقائياً)", type=["jpg", "jpeg", "png"])

with col2:
    st.subheader("💾 حفظ المعاملة")
    if st.button("✅ تحليل وحفظ"):
        if pasted_text.strip():
            amounts = re.findall(r'\d+(?:[.,]\d+)?', pasted_text)
            amount = float(amounts[0].replace(',', '.')) if amounts else 0.0
            arabic_words = re.findall(r'[\u0600-\u06FF]{3,}', pasted_text)
            name = " ".join(arabic_words[:2]) if arabic_words else "غير معروف"
            
            c.execute("INSERT INTO transactions (name, amount, date) VALUES (?,?,?)",
                      (name, amount, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            st.success(f"✅ تم حفظ: {name} - {amount:,.0f} ريال")
            
            if uploaded_img:
                img_bytes = uploaded_img.getvalue()
                filename = f"دفتر_اليوم_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                with open(filename, "wb") as f:
                    f.write(img_bytes)
                st.success(f"✅ تم حفظ الصورة: {filename}")
            
            st.rerun()
        else:
            st.warning("الرجاء لصق النص أولاً")

# ------------------- عرض آخر المعاملات -------------------
st.subheader("📋 آخر 5 معاملات")
df = pd.read_sql_query("SELECT name, amount, date FROM transactions ORDER BY date DESC LIMIT 5", conn)
st.dataframe(df)

# ------------------- رابط تنزيل الصورة -------------------
if uploaded_img:
    b64 = base64.b64encode(uploaded_img.getvalue()).decode()
    href = f'<a href="data:image/jpeg;base64,{b64}" download="دفتر_اليوم.jpg">📥 تنزيل الصورة</a>'
    st.markdown(href, unsafe_allow_html=True)

conn.close()
