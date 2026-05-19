# ui/auth_ui.py - واجهة تسجيل الدخول وتغيير كلمة المرور (تصميم زجاجي فخم - بدون إطار الحقول)
import streamlit as st
from database import init_db
from services.auth_service import (
    create_admin_if_needed,
    verify_user,
    change_password,
    logout_session
)

# ========== ألوان التصميم ==========
BG_GRADIENT = "linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%)"
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

def login_form():
    """نموذج تسجيل الدخول بتصميم زجاجي فخم (بدون إطار حول الحقول)"""
    
    # شعار XD بتوهج فخم
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:2rem;">
        <div style="
            width:120px; height:120px; margin:0 auto 1.5rem auto;
            background:{GLASS_BG}; backdrop-filter:blur(20px);
            border:2px solid {GLASS_BORDER}; border-radius:35px;
            display:flex; align-items:center; justify-content:center;
            box-shadow:0 0 60px rgba(139, 92, 246, 0.4), 0 0 120px rgba(59, 130, 246, 0.2);
            animation: pulse 2s infinite;
        ">
            <span style="font-size:3.5rem; font-weight:900; 
                background:linear-gradient(135deg, {ACCENT_PURPLE}, {ACCENT_BLUE}, {ACCENT_GREEN});
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                text-shadow: none;
            ">X</span>
        </div>
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; font-weight:800; letter-spacing:3px; text-shadow:0 0 30px rgba(139, 92, 246, 0.5);">XD ERP</h1>
        <p style="color:{TEXT_SECONDARY}; margin-top:0.8rem; font-size:1.1rem; letter-spacing:1px;">نظام تخطيط موارد المؤسسات</p>
    </div>
    """, unsafe_allow_html=True)
    
    # حقول الإدخال بدون إطار محيط
    username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم", key="login_user")
    password = st.text_input("🔒 كلمة المرور", type="password", placeholder="أدخل كلمة المرور", key="login_pass")
    
    # أزرار متجاورة
    col1, col2 = st.columns([2, 1])
    with col1:
        login_btn = st.button("🚀 دخول", use_container_width=True, type="primary")
    with col2:
        if st.button("🔑 نسيت كلمة المرور", use_container_width=True):
            st.session_state.show_password_change = True
            st.rerun()
    
    if login_btn:
        user = verify_user(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.rerun()
        else:
            st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    # تذييل
    st.markdown(f"""
    <div style="text-align:center; margin-top:2rem;">
        <p style="color:{TEXT_SECONDARY}; font-size:0.8rem; opacity:0.7;">© 2026 XD ERP. جميع الحقوق محفوظة.</p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    """نموذج تغيير كلمة المرور بتصميم زجاجي (بدون إطار)"""
    
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:2rem;">
        <div style="font-size:4rem; margin-bottom:1rem;">🔑</div>
        <h2 style="color:{TEXT_PRIMARY}; margin:0; font-weight:700;">تغيير كلمة المرور</h2>
        <p style="color:{TEXT_SECONDARY}; margin-top:0.5rem;">قم بتغيير كلمة المرور الافتراضية إلى كلمة مرور جديدة</p>
    </div>
    """, unsafe_allow_html=True)
    
    username = st.text_input("👤 اسم المستخدم", value="admin", disabled=True, key="change_user")
    old_password = st.text_input("🔒 كلمة المرور الحالية", type="password", placeholder="أدخل كلمة المرور الحالية", key="change_old")
    new_password = st.text_input("🆕 كلمة المرور الجديدة", type="password", placeholder="أدخل كلمة المرور الجديدة", key="change_new")
    confirm_password = st.text_input("✅ تأكيد كلمة المرور الجديدة", type="password", placeholder="أعد إدخال كلمة المرور الجديدة", key="change_confirm")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 حفظ كلمة المرور الجديدة", use_container_width=True, type="primary"):
            if not old_password or not new_password:
                st.error("❌ جميع الحقول مطلوبة")
            elif new_password != confirm_password:
                st.error("❌ كلمة المرور الجديدة غير متطابقة")
            elif len(new_password) < 4:
                st.error("❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            else:
                success, message = change_password(username, old_password, new_password)
                if success:
                    st.success(f"✅ {message}")
                    st.session_state.show_password_change = False
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    with col2:
        if st.button("↩️ العودة لتسجيل الدخول", use_container_width=True):
            st.session_state.show_password_change = False
            st.rerun()

def show():
    """الدالة الرئيسية لعرض صفحة الدخول"""
    init_db()
    create_admin_if_needed()
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
