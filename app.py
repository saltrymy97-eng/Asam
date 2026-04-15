import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from google.cloud import vision
import io
import re

st.set_page_config(page_title="دفتر الحسابات", page_icon="📒")

# --- إعداد Google Vision من خلال Streamlit Secrets ---
# (شرح الخطوات بالأسفل)
if "gcp_key" not in st.secrets:
    st.error("الرجاء إضافة مفتاح Google Cloud في Streamlit Secrets")
    st.stop()

# حفظ المفتاح مؤقتاً
with open("/tmp/key.json", "w") as f:
    f.write(st.secrets["gcp_key"])
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/key.json"

@st.cache_resource
def get_vision_client():
    return vision.ImageAnnotatorClient()

def extract_text(image_file):
    client = get_vision_client()
    content = image_file.getvalue()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise Exception(response.error.message)
    return response.full_text_annotation.text

def parse_text(text):
    entries = []
    for line in text.split('\n'):
        nums = re.findall(r'\d+\.?\d*', line)
        if not nums:
            continue
        amount = float(nums[-1])
        entry_type = "💵 دخل" if any(k in line for k in ["راتب","دخل"]) else "💸 مصروف"
        category = "أخرى"
        for cat, kws in {"طعام":["غداء","عشاء"],"مواصلات":["بنزين","تاكسي"],"فواتير":["كهرباء","ماء"]}.items():
            if any(k in line for k in kws):
                category = cat
                break
        entries.append({
            "التاريخ": datetime.now().strftime("%Y-%m-%d"),
            "النوع": entry_type,
            "التصنيف": category,
            "المبلغ": amount,
            "الوصف": line[:50]
        })
    return entries

# --- إدارة البيانات ---
DATA_FILE = "ledger.csv"
def load(): return pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else pd.DataFrame(columns=["التاريخ","النوع","التصنيف","المبلغ","الوصف"])
def save(df): df.to_csv(DATA_FILE, index=False)

# --- واجهة المستخدم ---
st.title("📒 دفتر الحسابات + OCR")
tab1, tab2 = st.tabs(["✍️ يدوي", "📸 تصوير"])

with tab1:
    with st.form("form"):
        c1, c2 = st.columns(2)
        typ = c1.radio("النوع", ["💵 دخل", "💸 مصروف"])
        amt = c2.number_input("المبلغ", min_value=0.0)
        cat = st.selectbox("التصنيف", ["طعام","مواصلات","تسوق","فواتير","أخرى"])
        desc = st.text_input("الوصف")
        if st.form_submit_button("حفظ") and amt>0:
            df = load()
            df = pd.concat([df, pd.DataFrame([{
                "التاريخ": datetime.now().strftime("%Y-%m-%d"),
                "النوع": typ,
                "التصنيف": cat,
                "المبلغ": amt,
                "الوصف": desc or "-"
            }])], ignore_index=True)
            save(df)
            st.success("تمت الإضافة")
            st.rerun()

with tab2:
    img = st.camera_input("صورة الدفتر")
    if img:
        st.image(img)
        if st.button("تحليل"):
            with st.spinner("جاري التحليل..."):
                txt = extract_text(img)
                st.text_area("النص", txt)
                entries = parse_text(txt)
                if entries:
                    st.dataframe(pd.DataFrame(entries))
                    if st.button("حفظ العمليات"):
                        df = load()
                        df = pd.concat([df, pd.DataFrame(entries)], ignore_index=True)
                        save(df)
                        st.success("تم الحفظ")
                        st.rerun()
                else:
                    st.warning("لم نجد عمليات")

# --- عرض الرصيد ---
df = load()
if not df.empty:
    inc = df[df["النوع"]=="💵 دخل"]["المبلغ"].sum()
    exp = df[df["النوع"]=="💸 مصروف"]["المبلغ"].sum()
    c1,c2,c3 = st.columns(3)
    c1.metric("الرصيد", f"{inc-exp:.2f}")
    c2.metric("الدخل", f"{inc:.2f}")
    c3.metric("المصروف", f"{exp:.2f}")
    st.dataframe(df.sort_values("التاريخ", ascending=False).head(10), hide_index=True)
