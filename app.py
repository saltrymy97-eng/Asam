# app.py
# ------------------------------------------------------------
# تطبيق: مساعد مدير الفرع الذكي – للمؤسسات المالية والبنوك
# المطور: سالم التريمي – 2026
# ملاحظة: المساعد الذكي يعمل عبر Groq API السحابي فقط.
# ------------------------------------------------------------

import streamlit as st
st.set_page_config(
    page_title="مساعد مدير الفرع الذكي",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import numpy as np
import os
from io import BytesIO
import zipfile
from datetime import date

from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

import plotly.express as px
import plotly.graph_objects as go

from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

# ----------------- إعداد قاعدة بيانات الجلسة ----------------
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["الاسم", "رقم_الحساب", "الراتب", "القسم"])
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ----------------- أنماط CSS المخصصة ------------------------
def apply_custom_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0a1929; }
        h1, h2, h3, h4, h5, h6 { color: #ffd700 !important; font-family: 'Segoe UI', sans-serif; }
        .stButton > button {
            background: linear-gradient(135deg, #b8860b 0%, #ffd700 100%);
            color: #0a1929; font-weight: bold; border: none; border-radius: 8px;
            padding: 0.5rem 1.5rem; transition: all 0.3s ease;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #ffd700 0%, #b8860b 100%);
            color: white; transform: scale(1.02); box-shadow: 0 4px 15px rgba(255,215,0,0.4);
        }
        .metric-card {
            background: linear-gradient(135deg, #132f4c 0%, #0a1929 100%);
            border: 1px solid #ffd700; border-radius: 12px; padding: 20px;
            text-align: center; color: #ffd700; font-size: 1.3rem; font-weight: bold;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .metric-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(255,215,0,0.3); }
        .metric-card .label { font-size: 0.9rem; color: #b8860b; margin-bottom: 10px; }
        [data-testid="stSidebar"] { background-color: #0d2137; }
        .stTextInput > div > div > input { background-color: #132f4c; color: white; border: 1px solid #ffd700; }
        .stDataFrame { background: #0d2137; color: white; }
        .stDataFrame table { background: #0d2137; color: white; }
        .footer {
            position: fixed; bottom: 0; left: 0; width: 100%; background: #0a1929;
            color: #ffd700; text-align: center; padding: 10px; font-size: 0.9rem;
            border-top: 2px solid #ffd700;
        }
    </style>
    """, unsafe_allow_html=True)

apply_custom_css()

# ----------------- دوال مساعدة ----------------------------
def arabic_text(text):
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def generate_salary_slip(employee, month, year=date.today().year):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    font_path = os.path.join(os.path.dirname(__file__), 'DejaVuSans.ttf')
    try:
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.set_font('DejaVu', '', 14)
        use_unicode = True
    except:
        st.warning("⚠️ خط DejaVuSans.ttf غير موجود. قد لا تظهر العربية بشكل صحيح في PDF.")
        pdf.set_font('Helvetica', '', 14)
        use_unicode = False

    pdf.image('https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Bank_Performance_Logo.png', x=10, y=8, w=33)
    pdf.ln(20)

    title = arabic_text(f"كشف راتب شهر {month} - {year}")
    if use_unicode: pdf.set_font('DejaVu', '', 18)
    pdf.cell(0, 10, txt=title, ln=True, align='C')
    pdf.ln(10)

    data_lines = [
        f"الاسم: {employee['الاسم']}",
        f"رقم الحساب: {employee['رقم_الحساب']}",
        f"القسم: {employee['القسم']}",
        f"المبلغ المستحق: {employee['الراتب']:,} ريال"
    ]
    for line in data_lines:
        ar_line = arabic_text(line)
        if use_unicode: pdf.set_font('DejaVu', '', 14)
        pdf.cell(0, 10, txt=ar_line, ln=True, align='R' if use_unicode else 'L')
        pdf.ln(5)
    pdf.ln(20)
    footer = arabic_text("هذا المستند صادر آلياً من مساعد مدير الفرع الذكي - 2026")
    pdf.set_font('DejaVu', '', 10) if use_unicode else pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 10, txt=footer, ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1')

def create_zip_with_slips(df, month):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for _, row in df.iterrows():
            emp = row.to_dict()
            pdf_bytes = generate_salary_slip(emp, month)
            file_name = f"{emp['الاسم']}_{emp['رقم_الحساب']}.pdf"
            zf.writestr(file_name, pdf_bytes)
    zip_buffer.seek(0)
    return zip_buffer

# ----------------- الشريط الجانبي --------------------------
st.sidebar.markdown("# 🏦 مساعد مدير الفرع الذكي")
st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader("📁 ارفع ملف Excel (xlsx/csv)", type=["xlsx", "csv"])
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        required_cols = ["الاسم", "رقم_الحساب", "الراتب", "القسم"]
        if all(col in df.columns for col in required_cols):
            st.session_state.df = df
            st.sidebar.success(f"✅ تم تحميل {len(df)} سجل")
        else:
            st.sidebar.error("❌ يجب أن يحتوي الملف على: الاسم، رقم_الحساب، الراتب، القسم")
    except Exception as e:
        st.sidebar.error(f"فشل قراءة الملف: {e}")

# نموذج فارغ
empty_df = pd.DataFrame(columns=["الاسم", "رقم_حساب", "الراتب", "القسم"])
output = BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    empty_df.to_excel(writer, index=False, sheet_name='Sheet1')
output.seek(0)
st.sidebar.download_button(
    label="📥 تحميل نموذج Excel فارغ",
    data=output,
    file_name="نموذج_الرواتب.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
          "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
selected_month = st.sidebar.selectbox("📅 اختر الشهر", months, index=date.today().month-1)

groq_api_key = st.sidebar.text_input("🔑 مفتاح Groq API (للمساعد الذكي)", type="password")

st.sidebar.markdown("---")
st.sidebar.markdown("☁️ المساعد الذكي يعمل حصراً عبر Groq API السحابي.")

# ----------------- الصفحة الرئيسية -------------------------
st.title("🏦 مساعد مدير الفرع الذكي")
st.markdown("### لوحة تحكم شاملة لإدارة رواتب الموظفين وتحليلات مالية متقدمة")

if not st.session_state.df.empty:
    st.dataframe(st.session_state.df, use_container_width=True)
else:
    st.info("الرجاء رفع ملف Excel من الشريط الجانبي لبدء التحليل.")

if not st.session_state.df.empty:
    df = st.session_state.df
    col1, col2, col3 = st.columns(3)
    total_employees = df.shape[0]
    total_salary = df['الراتب'].sum()
    avg_salary = df['الراتب'].mean()

    col1.markdown(f"""<div class="metric-card"><div class="label">👥 عدد الموظفين</div>{total_employees}</div>""", unsafe_allow_html=True)
    col2.markdown(f"""<div class="metric-card"><div class="label">💰 مجموع الرواتب</div>{total_salary:,.0f} ريال</div>""", unsafe_allow_html=True)
    col3.markdown(f"""<div class="metric-card"><div class="label">📊 متوسط الراتب</div>{avg_salary:,.0f} ريال</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📊 توزيع الرواتب حسب الأقسام")
    dept_salary = df.groupby("القسم")["الراتب"].sum().reset_index()
    fig_pie = px.pie(dept_salary, names='القسم', values='الراتب', color_discrete_sequence=px.colors.sequential.Blugrn, hole=0.3)
    fig_pie.update_layout(paper_bgcolor='#0a1929', font=dict(color='#ffd700'), title_font=dict(color='#ffd700'))
    st.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("📈 تحليلات تنبؤية (Trend Line)"):
        df_forecast = df.copy()
        df_forecast['index'] = np.arange(len(df_forecast))
        X = df_forecast[['index']]
        y = df_forecast['الراتب']
        lin_reg = LinearRegression()
        lin_reg.fit(X, y)
        y_pred = lin_reg.predict(X)

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=X['index'], y=y, mode='markers+lines', name='الراتب الفعلي', marker=dict(color='#ffd700')))
        fig_trend.add_trace(go.Scatter(x=X['index'], y=y_pred, mode='lines', name='خط الاتجاه', line=dict(color='#b8860b', dash='dash')))
        fig_trend.update_layout(paper_bgcolor='#0a1929', plot_bgcolor='#0a1929', font=dict(color='#ffd700'),
                                xaxis_title="الترتيب الإداري", yaxis_title="الراتب (ريال)")
        st.plotly_chart(fig_trend, use_container_width=True)
        st.metric("معامل التحديد (R²)", f"{r2_score(y, y_pred):.2%}")

    st.markdown("---")
    st.subheader("📄 إنشاء كشوف الرواتب الشهرية")
    if st.button("🚀 توليد كشوف PDF لكل الموظفين وتحميل ZIP"):
        with st.spinner("جارٍ إنشاء الملفات..."):
            try:
                zip_data = create_zip_with_slips(df, selected_month)
                st.success(f"تم إنشاء {len(df)} كشف راتب بنجاح!")
                st.download_button(
                    label="⬇️ تحميل ملف ZIP",
                    data=zip_data,
                    file_name=f"كشوف_رواتب_{selected_month}_{date.today().year}.zip",
                    mime="application/zip"
                )
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# ----------------- المساعد الذكي (Groq API) ----------------
st.markdown("---")
st.subheader("🤖 المساعد الذكي للبيانات (Groq)")

llm_available = False
agent = None
try:
    from langchain_groq import ChatGroq
    from langchain_experimental.agents import create_pandas_dataframe_agent

    if groq_api_key and not st.session_state.df.empty:
        llm = ChatGroq(
            temperature=0,
            groq_api_key=groq_api_key,
            model_name="llama3-70b-8192"
        )
        agent = create_pandas_dataframe_agent(
            llm,
            st.session_state.df,
            verbose=True,
            allow_dangerous_code=True,
            handle_parsing_errors=True
        )
        llm_available = True
        st.success("🧠 المساعد الذكي مفعل وجاهز لتحليل البيانات")
    elif not groq_api_key:
        st.warning("⚠️ أدخل مفتاح Groq API في الشريط الجانبي لتفعيل المساعد الذكي.")
    else:
        st.info("📭 لا توجد بيانات لتحليلها. ارفع ملف Excel أولاً.")
except ImportError:
    st.warning("⚠️ مكتبات LangChain/Groq غير مثبتة. تم تعطيل المساعد الذكي.")
except Exception as e:
    st.error(f"❌ فشل تهيئة المساعد: {e}")

if llm_available and agent:
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("اسأل عن البيانات (مثال: ما هو مجموع الرواتب حسب القسم؟)"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("🤔 جاري التحليل..."):
                try:
                    response = agent.run(prompt)
                    st.markdown(response)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"فشل في الحصول على رد: {e}")

# ----------------- التذييل --------------------------------
st.markdown("""
<div class="footer">
    🏦 تم التطوير بواسطة <strong>سالم التريمي</strong> - 2026 | مساعد مدير الفرع الذكي
</div>
""", unsafe_allow_html=True)
