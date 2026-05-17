import streamlit as st
from streamlit_option_menu import option_menu

# استيراد الوحدات مباشرة (بدون مجلد modules)
import auth
import dashboard
import inventory
import sales
import purchases
import accounting
import hr

st.set_page_config(page_title="نظام ERP", layout="wide", initial_sidebar_state="expanded")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.logged_in:
    auth.show()
else:
    with st.sidebar:
        st.markdown(f"### أهلاً، {st.session_state.user.get('full_name', '')}")
        selected = option_menu(
            menu_title="القائمة الرئيسية",
            options=["لوحة المعلومات", "المخزون", "المبيعات", "المشتريات", "الحسابات", "الموارد البشرية", "تسجيل الخروج"],
            icons=["speedometer2", "box", "cart", "truck", "calculator", "people", "box-arrow-right"],
            menu_icon="cast",
            default_index=0,
        )
    
    if selected == "لوحة المعلومات":
        dashboard.show()
    elif selected == "المخزون":
        inventory.show()
    elif selected == "المبيعات":
        sales.show()
    elif selected == "المشتريات":
        purchases.show()
    elif selected == "الحسابات":
        accounting.show()
    elif selected == "الموارد البشرية":
        hr.show()
    elif selected == "تسجيل الخروج":
        auth.logout()
