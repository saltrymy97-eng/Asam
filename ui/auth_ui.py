# ui/auth_ui.py - واجهة تسجيل الدخول وتغيير كلمة المرور (تصميم زجاجي فاخر ومبهر)
import streamlit as st
from database import init_db
from services.auth_service import (
    create_admin_if_needed,
    verify_user,
    change_password,
    logout_session
)

# ========== ألوان وتصميم فاخر ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"
GLASS_BG = "rgba(255, 255, 255, 0.08)"
GLASS_BORDER = "rgba(255, 255, 255, 0.2)"
GLASS_SHADOW = "0 15px 40px rgba(0,0,0,0.5)"

def login_form():
    """نموذج تسجيل الدخول بتصميم زجاجي فخم ومبهر"""
    
    # ---------- شعار XD ERP بتصميم أيقوني جذاب ----------
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:2.5rem;">
        <div style="
            width:130px; height:130px; margin:0 auto 1.8rem auto;
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(59, 130, 246, 0.3));
            backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
            border:2px solid {GLASS_BORDER}; border-radius:40px;
            display:flex; align-items:center; justify-content:center;
            box-shadow: 0 0 80px rgba(139, 92, 246, 0.5), 0 0 150px rgba(59, 130, 246, 0.3), {GLASS_SHADOW};
            animation: logoPulse 2.5s ease-in-out infinite;
        ">
            <span style="font-size:4rem; font-weight:900; 
                background:linear-gradient(135deg, {PR}, {BL}, {CY});
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;
            ">X</span>
        </div>
        <h1 style="color:{T}; font-size:3.5rem; margin:0; font-weight:900; letter-spacing:5px; 
            text-shadow:0 0 40px rgba(139, 92, 246, 0.6);">XD ERP</h1>
        <p style="color:{S}; margin-top:0.8rem; font-size:1.2rem; letter-spacing:2px; opacity:0.9;">نظام تخطيط موارد المؤسسات الذكي</p>
    </div>
    
    <style>
        @keyframes logoPulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 80px rgba(139, 92, 246, 0.5), 0 0 150px rgba(59, 130, 246, 0.3); }
            50% { transform: scale(1.02); box-shadow: 0 0 120px rgba(139, 92, 246, 0.7), 0 0 200px rgba(59, 130, 246, 0.5); }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ---------- بطاقة تسجيل الدخول الزجاجية ----------
    st.markdown(f"""
    <div style="
        background: {GLASS_BG}; backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
        border:1px solid {GLASS_BORDER}; border-radius:25px; padding:2.5rem 2rem;
        box-shadow: {GLASS_SHADOW}; max-width:450px; margin:0 auto;
    ">
    """, unsafe_allow_html=True)
    
    username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم", key="login_user")
    password = st.text_input("🔒 كلمة المرور", type="password", placeholder="أدخل كلمة المرور", key="login_pass")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        login_btn = st.button("🚀 تسجيل الدخول", use_container_width=True, type="primary")
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
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # ---------- تذييل ----------
    st.markdown(f"""
    <div style="text-align:center; margin-top:2rem;">
        <p style="color:{S}; font-size:0.8rem; opacity:0.6;">© 2026 XD ERP. جميع الحقوق محفوظة.</p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    """نموذج تغيير كلمة المرور بتصميم زجاجي فخم"""
    
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:2.5rem;">
        <div style="font-size:5rem; margin-bottom:1rem;">🔑</div>
        <h2 style="color:{T}; margin:0; font-weight:800; font-size:2.5rem;">تغيير كلمة المرور</h2>
        <p style="color:{S}; margin-top:0.5rem; font-size:1rem;">قم بتغيير كلمة المرور الافتراضية إلى كلمة مرور آمنة</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="
        background: {GLASS_BG}; backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
        border:1px solid {GLASS_BORDER}; border-radius:25px; padding:2.5rem 2rem;
        box-shadow: {GLASS_SHADOW}; max-width:450px; margin:0 auto;
    ">
    """, unsafe_allow_html=True)
    
    username = st.text_input("👤 اسم المستخدم", value="admin", disabled=True, key="change_user")
    old_password = st.text_input("🔒 كلمة المرور الحالية", type="password", placeholder="أدخل كلمة المرور الحالية", key="change_old")
    new_password = st.text_input("🆕 كلمة المرور الجديدة", type="password", placeholder="أدخل كلمة المرور الجديدة (4 أحرف على الأقل)", key="change_new")
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
    
    st.markdown("</div>", unsafe_allow_html=True)

def show():
    """الدالة الرئيسية لعرض صفحة الدخول"""
    init_db()
    create_admin_if_needed()
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    # ---------- خلفية متدرجة جذابة ----------
    st.markdown(f"""
    <style>
        .stApp {{
            background: linear-gradient(145deg, #0F172A 0%, #1E1B4B 40%, #172554 100%) !important;
        }}
        div[data-baseweb="input"] {{
            background: rgba(255,255,255,0.06) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            border-radius: 14px !important;
            padding: 4px 8px !important;
            transition: all 0.3s ease !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            border-color: {PR} !important;
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2) !important;
        }}
        div[data-baseweb="input"] input {{
            background: transparent !important;
            color: {T} !important;
            padding: 14px 12px !important;
            font-size: 1rem !important;
        }}
        button[kind="primary"] {{
            background: linear-gradient(135deg, {PR}, {BL}) !important;
            border: none !important;
            font-weight: 700 !important;
            padding: 12px 20px !important;
            border-radius: 14px !important;
            transition: all 0.3s ease !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4) !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
