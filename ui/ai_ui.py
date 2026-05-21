import streamlit as st
from services.ai_service import create_ai_tables, get_comprehensive_data, query_groq
import json

def show():
    st.title("🤖 المساعد الذكي XD")
    create_ai_tables()
    
    if "GROQ_API_KEY" not in st.secrets:
        st.error("أضف مفتاح Groq")
        return
    
    q = st.text_input("سؤالك:")
    if st.button("اسأل") and q:
        data = get_comprehensive_data()
        data_str = json.dumps(data, ensure_ascii=False, default=str)[:2000]
        prompt = f"بيانات:\n{data_str}\n\nالسؤال: {q}\nأجب بالعربية."
        with st.spinner("..."):
            answer = query_groq(prompt, q)
        st.success(answer)
