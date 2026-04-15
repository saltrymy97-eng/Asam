import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import io
import re
import base64

# ------------------- إعداد الصفحة -------------------
st.set_page_config(page_title="دفتر الحسابات إكسترا", layout="wide")
st.title("📘 دفتر الحسابات إكسترا")
st.markdown("**الخطة:** انسخ النص من عدسة جوجل ← اضغط زر 'لصق' ← يحفظ تلقائياً + تنزيل صورة الدفتر اليومي")

# ------------------- قاعدة البيانات -------------------
conn = sqlite3.connect('debter.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              amount REAL,
              date TEXT)''')
conn.commit()

# ------------------- دالة حفظ الصورة في المعرض -------------------
def save_image_to_gallery(image_bytes, filename):
    """حفظ الصورة في مجلد 'Downloads' (محاكاة المعرض)"""
    with open(filename, "wb") as f:
        f.write(image_bytes)
    return filename

# ------------------- واجهة رئيسية -------------------
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📋 ألصق النص المستخرج من عدسة جوجل")
    
    # حقل نص لصق (يدوي أو تلقائي)
    pasted_text = st.text_area("النص", height=150, key="pasted_text")
    
    # زر لصق تلقائي من الحافظة باستخدام JavaScript
    st.markdown("""
        <script>
        function pasteFromClipboard() {
            navigator.clipboard.readText().then(text => {
                const textarea = parent.document.querySelector('textarea[data-testid="stTextArea"]');
                if (textarea) {
                    textarea.value = text;
                    textarea.dispatchEvent(new Event('input', {bubbles: true}));
                }
            }).catch(err => alert('الرجاء السماح بالوصول إلى الحافظة'));
        }
        </script>
        <button onclick="pasteFromClipboard()" style="background-color:#2a5298; color:white; padding:0.5rem 1rem; border:none; border-radius:8px; cursor:pointer;">📋 لصق من الحافظة</button>
    """, unsafe_allow_html=True)
    
    # رفع صورة الدفتر (اختياري)
    uploaded_img = st.file_uploader("📸 أو ارفع صورة الدفتر (سيتم حفظها تلقائياً)", type=["jpg", "jpeg", "png"])

with col2:
    st.subheader("📊 معاملة اليوم")
    
    if st.button("✅ تحليل ولصق وحفظ"):
        # 1. معالجة النص
        if pasted_text:
            amounts = re.findall(r'\d+(?:[.,]\d+)?', pasted_text)
            amount = float(amounts[0].replace(',', '.')) if amounts else 0.0
            arabic_words = re.findall(r'[\u0600-\u06FF]{3,}', pasted_text)
            name = " ".join(arabic_words[:2]) if arabic_words else "غير معروف"
            
            # 2. حفظ في قاعدة البيانات
            c.execute("INSERT INTO transactions (name, amount, date) VALUES (?,?,?)",
                      (name, amount, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            
            # 3. حفظ الصورة إذا وجدت (في مجلد التنزيلات)
            if uploaded_img:
                img_bytes = uploaded_img.getvalue()
                filename = f"دفتر_اليوم_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                save_image_to_gallery(img_bytes, filename)
                st.success(f"✅ تم حفظ الصورة في: {filename}")
            
            st.success(f"✅ تم حفظ: {name} - {amount:,.0f} ريال")
            # مسح الحقل بعد الحفظ
            st.experimental_rerun()
        else:
            st.warning("الرجاء لصق النص أولاً")

# ------------------- عرض آخر 5 معاملات -------------------
st.subheader("📋 آخر 5 معاملات")
df = pd.read_sql_query("SELECT name, amount, date FROM transactions ORDER BY date DESC LIMIT 5", conn)
st.dataframe(df)

# ------------------- رابط لتحميل صورة اليوم -------------------
if uploaded_img:
    img_bytes = uploaded_img.getvalue()
    b64 = base64.b64encode(img_bytes).decode()
    href = f'<a href="data:image/jpeg;base64,{b64}" download="دفتر_اليوم.jpg">📥 تنزيل صورة اليوم</a>'
    st.markdown(href, unsafe_allow_html=True)

conn.close()
