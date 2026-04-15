import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
import google.generativeai as genai
import re

# ------------------- إعداد Gemini -------------------
# استخدم st.secrets أو أدخل المفتاح مباشرة (للتجربة فقط)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    GEMINI_API_KEY = st.text_input("أدخل مفتاح Google Gemini API:", type="password")
    if not GEMINI_API_KEY:
        st.stop()
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

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
st.set_page_config(page_title="دفتر الحسابات - Gemini Vision", layout="wide")
st.title("📒 دفتر الحسابات مع Google Gemini Vision")
st.markdown("استخراج اسم العميل والمبلغ من صور الدفتر الورقي (بما في ذلك الخط اليدوي)")

tab1, tab2 = st.tabs(["📸 إضافة معاملة", "📋 المعاملات"])

with tab1:
    uploaded_file = st.file_uploader("ارفع صورة الدفتر الورقي", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="الصورة المرفوعة", width=350)
        
        if st.button("🔍 استخراج البيانات بواسطة Gemini", type="primary"):
            with st.spinner("Gemini Vision يقرأ الصورة..."):
                try:
                    response = model.generate_content([
                        "استخرج من هذه الصورة اسم العميل والمبلغ فقط. أجب بهذا الشكل الدقيق:\nالاسم: [الاسم]\nالمبلغ: [الرقم]\nإذا لم تجد شيئًا، اكتب 'غير موجود'.",
                        image
                    ])
                    result_text = response.text
                    st.success("✅ تم الاستخراج بنجاح")
                    st.text_area("النص المستخرج من Gemini", result_text, height=150)
                    
                    name_match = re.search(r'الاسم:\s*(.+?)(?:\n|$)', result_text)
                    amount_match = re.search(r'المبلغ:\s*(\d+(?:[.,]\d+)?)', result_text)
                    
                    default_name = name_match.group(1).strip() if name_match else ""
                    default_amount = amount_match.group(1) if amount_match else ""
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        final_name = st.text_input("اسم العميل", value=default_name)
                    with col2:
                        final_amount = st.text_input("المبلغ", value=default_amount)
                    
                    if st.button("💾 حفظ المعاملة"):
                        if final_name and final_amount:
                            amount_float = float(final_amount.replace(',', '.'))
                            c.execute(
                                "INSERT INTO transactions (name, amount, date, raw_text) VALUES (?,?,?,?)",
                                (final_name, amount_float, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), result_text)
                            )
                            conn.commit()
                            st.success(f"تم حفظ معاملة {final_name} بمبلغ {amount_float}")
                            st.rerun()
                        else:
                            st.warning("يرجى إدخال اسم العميل والمبلغ")
                except Exception as e:
                    st.error(f"فشل الاتصال بـ Gemini: {e}")

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
