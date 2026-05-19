# ui/auth_ui.py - واجهة تسجيل الدخول وتغيير كلمة المرور (تصميم زجاجي فخم)
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
    """نموذج تسجيل الدخول بتصميم زجاجي فخم"""
    
    # شعار XD بتوهج
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:0.5rem;">
        <div style="
            width:100px; height:100px; margin:0 auto 1rem auto;
            background:{GLASS_BG}; backdrop-filter:blur(10px);
            border:2px solid {GLASS_BORDER}; border-radius:30px;
            display:flex; align-items:center; justify-content:center;
            box-shadow:0 0 40px rgba(139, 92, 246, 0.3);
        ">
            <span style="font-size:3rem; font-weight:900; 
                background:linear-gradient(135deg, {ACCENT_PURPLE}, {ACCENT_BLUE});
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;
            ">X</span>
        </div>
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.2rem; margin:0; letter-spacing:2px;">XD ERP</h1>
        <p style="color:{TEXT_SECONDARY}; margin-top:0.5rem;">نظام تخطيط موارد المؤسسات</p>
    </div>
    """, unsafe_allow_html=True)
    
    # بطاقة تسجيل الدخول الزجاجية
    st.markdown(f"""
    <div style="
        background:{GLASS_BG}; backdrop-filter:blur(15px);
        border:1px solid {GLASS_BORDER}; border-radius:24px;
        padding:2rem; margin:1rem 0;
        box-shadow:{GLASS_SHADOW};
    ">
    """, unsafe_allow_html=True)
    
    username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم")
    password = st.text_input("🔒 كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        login_btn = st.button("🚀 دخول", use_container_width=True, type="primary")
    with col2:
        if st.button("🔑 نسيت كلمة المرور", use_container_width=True):
            st.session_state.show_password_change = True
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
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
    <div style="text-align:center; margin-top:1rem;">
        <p style="color:{TEXT_SECONDARY}; font-size:0.8rem;">© 2026 XD ERP. جميع الحقوق محفوظة.</p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    """نموذج تغيير كلمة المرور بتصميم زجاجي"""
    
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:1.5rem;">
        <div style="font-size:3rem; margin-bottom:0.5rem;">🔑</div>
        <h2 style="color:{TEXT_PRIMARY}; margin:0;">تغيير كلمة المرور</h2>
        <p style="color:{TEXT_SECONDARY};">قم بتغيير كلمة المرور الافتراضية</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="
        background:{GLASS_BG}; backdrop-filter:blur(15px);
        border:1px solid {GLASS_BORDER}; border-radius:24px;
        padding:2rem; margin:1rem 0;
        box-shadow:{GLASS_SHADOW};
    ">
    """, unsafe_allow_html=True)
    
    username = st.text_input("👤 اسم المستخدم", value="admin", disabled=True)
    old_password = st.text_input("🔒 كلمة المرور الحالية", type="password", placeholder="أدخل كلمة المرور الحالية")
    new_password = st.text_input("🆕 كلمة المرور الجديدة", type="password", placeholder="أدخل كلمة المرور الجديدة")
    confirm_password = st.text_input("✅ تأكيد كلمة المرور الجديدة", type="password", placeholder="أعد إدخال كلمة المرور الجديدة")
    
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
    
    st.markdown("</div>", unsafe_allow_html=True)

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
