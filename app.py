import streamlit as st
import pandas as pd
from groq import Groq
import base64
from PIL import Image
import io
import json
import os

# --- إعدادات الصفحة ---
st.set_page_config(page_title="دفتر الحسابات الذكي عبر Groq", layout="wide")

# --- إعداد Groq API ---
# احصل على مفتاحك من: https://console.groq.com/
GROQ_API_KEY = "ضغ_مفتاح_GROQ_الخاص_بك_هنا"
client = Groq(api_key=GROQ_API_KEY)

# --- دوال المعالجة ---
def init_db():
    if not os.path.exists('ledger_groq.csv'):
        df = pd.DataFrame(columns=['التاريخ', 'الاسم', 'له (دائن)', 'عليه (مدين)', 'البيان'])
        df.to_csv('ledger_groq.csv', index=False, encoding='utf-8-sig')

def encode_image(image_file):
    """تحويل الصورة إلى Base64 لإرسالها إلى Groq"""
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def process_image_with_groq(base64_image):
    """تحليل الصورة باستخدام نموذج Llama 3.2 Vision عبر Groq"""
    completion = client.chat.completions.create(
        model="llama-3.2-11b-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": "حلل صورة دفتر الحسابات اليدوي واستخرج العمليات المالية. "
                                "أريد النتيجة كقائمة JSON فقط بتنسيق: "
                                '[{"الاسم": "...", "المبلغ": 0, "النوع": "له" أو "عليه", "البيان": "..."}]'
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                        },
                    },
                ],
            }
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

# --- واجهة المستخدم ---
st.title("⚡ دفتر الحسابات الذكي (Groq Speed)")
init_db()

tabs = st.tabs(["📊 كشف الحساب", "📸 مسح بالذكاء الاصطناعي"])

with tabs[0]:
    if os.path.exists('ledger_groq.csv'):
        df = pd.read_csv('ledger_groq.csv')
        st.dataframe(df, use_container_width=True)

with tabs[1]:
    st.header("أتمتة إدخال البيانات")
    uploaded_file = st.file_uploader("ارفع صورة صفحة الدفتر...", type=['jpg', 'jpeg', 'png'])
    
    if uploaded_file:
        st.image(uploaded_file, caption="المعطيات المرئية", width=300)
        
        if st.button("تحليل عبر Groq"):
            with st.spinner("جاري المعالجة بسرعة البرق..."):
                try:
                    # تحويل الصورة ومعالجتها
                    base64_img = encode_image(uploaded_file)
                    result = process_image_with_groq(base64_img)
                    
                    # استخراج البيانات (قد تكون تحت مفتاح معين في الـ JSON)
                    if isinstance(result, dict) and 'transactions' in result:
                        entries = result['transactions']
                    elif isinstance(result, list):
                        entries = result
                    else:
                        entries = list(result.values())[0] if isinstance(result, dict) else []

                    # تنسيق البيانات وحفظها
                    new_data = []
                    for item in entries:
                        new_data.append({
                            'التاريخ': pd.Timestamp.now().strftime('%Y-%m-%d'),
                            'الاسم': item.get('الاسم', 'غير معروف'),
                            'له (دائن)': item.get('المبلغ', 0) if item.get('النوع') == 'له' else 0,
                            'عليه (مدين)': item.get('المبلغ', 0) if item.get('النوع') == 'عليه' else 0,
                            'البيان': item.get('البيان', '')
                        })
                    
                    new_df = pd.DataFrame(new_data)
                    st.table(new_df)
                    
                    if st.button("تأكيد وحفظ في السجل"):
                        main_df = pd.read_csv('ledger_groq.csv')
                        final_df = pd.concat([main_df, new_df], ignore_index=True)
                        final_df.to_csv('ledger_groq.csv', index=False, encoding='utf-8-sig')
                        st.success("تم التحديث!")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"خطأ في الاتصال بـ Groq: {e}")
                        
