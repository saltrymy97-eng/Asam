# ui/auth_ui.py - شاشة الدخول الفاخرة (إصدار التصميم الأسطوري)
import streamlit as st
from database import init_db
from services.auth_service import (
    verify_user,
    change_password,
    logout_session
)

# ========== لوحة ألوان القصر الذهبي ==========
T = "#F8FAFC"
S = "#94A3B8"
GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"
GOLD_DARK = "#AA771C"
BG_DEEP = "#0A0A0A"
BG_CARD = "rgba(10, 10, 10, 0.8)"

def apply_imperial_css():
    """حقن نظام التصميم الإمبراطوري الفاخر"""
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
        
        .stApp {{
            background: radial-gradient(ellipse at top, #1a1a0a 0%, #0a0a05 40%, #000000 100%) !important;
            background-attachment: fixed !important;
        }}

        /* إطار التاج الذهبي */
        .imperial-frame {{
            background: linear-gradient(145deg, rgba(20, 20, 10, 0.85), rgba(10, 10, 5, 0.95));
            backdrop-filter: blur(60px) saturate(180%);
            -webkit-backdrop-filter: blur(60px) saturate(180%);
            border: 1px solid rgba(212, 175, 55, 0.25);
            border-top: 1px solid rgba(212, 175, 55, 0.5);
            border-radius: 40px;
            padding: 3.5rem 3rem;
            box-shadow: 0 60px 120px rgba(0,0,0,0.9), 0 0 40px rgba(212,175,55,0.08), inset 0 1px 0 rgba(212,175,55,0.1);
            position: relative;
            overflow: hidden;
        }}
        .imperial-frame::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(circle at top right, rgba(212,175,55,0.04), transparent 60%);
            pointer-events: none;
        }}

        /* تأثير النبض للتاج */
        @keyframes crownGlow {{
            0%, 100% {{ filter: drop-shadow(0 0 30px rgba(212,175,55,0.3)); transform: translateY(0); }}
            50% {{ filter: drop-shadow(0 0 60px rgba(212,175,55,0.5)); transform: translateY(-5px); }}
        }}
        .crown-icon {{
            animation: crownGlow 4s ease-in-out infinite;
            display: inline-block;
        }}

        /* حقول الإدخال الذهبية */
        div[data-baseweb="input"] {{
            background: rgba(0, 0, 0, 0.4) !important;
            border: 1px solid rgba(212, 175, 55, 0.15) !important;
            border-radius: 16px !important;
            padding: 12px 18px !important;
            transition: all 0.4s ease !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            background: rgba(0, 0, 0, 0.7) !important;
            border-color: rgba(212, 175, 55, 0.6) !important;
            box-shadow: 0 0 30px rgba(212, 175, 55, 0.15), 0 20px 40px rgba(0,0,0,0.5) !important;
            transform: translateY(-2px);
        }}
        div[data-baseweb="input"] input {{
            background: transparent !important;
            color: {T} !important;
            font-size: 1.1rem !important;
            font-weight: 500 !important;
        }}
        div[data-baseweb="input"] input::placeholder {{
            color: rgba(255, 255, 255, 0.12) !important;
        }}

        /* زر الدخول الذهبي */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {GOLD_DARK} 0%, {GOLD} 50%, {GOLD_LIGHT} 100%) !important;
            border: none !important;
            font-weight: 800 !important;
            font-size: 1.1rem !important;
            letter-spacing: 0.5px !important;
            padding: 20px 28px !important;
            border-radius: 16px !important;
            color: #0a0a05 !important;
            transition: all 0.4s ease !important;
            box-shadow: 0 20px 40px -10px rgba(212, 175, 55, 0.4), inset 0 -2px 0 rgba(0,0,0,0.2) !important;
            text-transform: uppercase;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-4px) !important;
            box-shadow: 0 30px 60px -10px rgba(212, 175, 55, 0.6), inset 0 -2px 0 rgba(0,0,0,0.2) !important;
            filter: brightness(1.1) !important;
        }}

        /* الزر الثانوي */
        button[kind="secondary"] {{
            background: rgba(212, 175, 55, 0.05) !important;
            border: 1px solid rgba(212, 175, 55, 0.2) !important;
            color: {GOLD_LIGHT} !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
            border-radius: 16px !important;
            padding: 20px 28px !important;
            transition: all 0.4s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: rgba(212, 175, 55, 0.12) !important;
            color: {T} !important;
            border-color: rgba(212, 175, 55, 0.5) !important;
            transform: translateY(-2px);
        }}

        /* نقاط زخرفية */
        .gold-dot {{
            width: 6px; height: 6px; border-radius: 50%;
            background: {GOLD};
            display: inline-block;
            box-shadow: 0 0 10px {GOLD};
            margin: 0 6px;
        }}
    </style>
    """, unsafe_allow_html=True)

def render_header(is_change_password=False):
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 2.5rem;">
            <div class="crown-icon" style="font-size:4rem; margin-bottom:0.5rem;">👑</div>
            <h1 style="color:{T}; font-size:3rem; font-weight:900; margin:0; letter-spacing:2px;
                background: linear-gradient(135deg, {T} 20%, {GOLD} 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            ">حوكمة</h1>
            <p style="color:{GOLD}; font-size:1.1rem; letter-spacing:3px; font-weight:700; margin-top:0.5rem;">
                <span class="gold-dot"></span> إدارة ذكية .. قرارات واثقة <span class="gold-dot"></span>
            </p>
            <div style="width:200px; height:1px; background:linear-gradient(90deg, transparent, {GOLD}, transparent); margin:1rem auto;"></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 2.5rem;">
            <div class="crown-icon" style="font-size:3.5rem; margin-bottom:0.5rem;">🛡️</div>
            <h2 style="color:{T}; font-size:2.5rem; font-weight:900; margin:0;">تأمين الهوية</h2>
            <p style="color:{S}; margin-top:0.5rem;">تحديث رمز الحماية الخاص بك</p>
            <div style="width:150px; height:1px; background:linear-gradient(90deg, transparent, {GOLD}, transparent); margin:1rem auto;"></div>
        </div>
        """, unsafe_allow_html=True)

def login_form():
    render_header()
    
    _, main, _ = st.columns([1, 2, 1])
    with main:
        st.markdown('<div class="imperial-frame">', unsafe_allow_html=True)
        username = st.text_input("👤 معرف المستخدم", placeholder="أدخل اسم المستخدم", key="login_user")
        password = st.text_input("🔒 رمز المرور", type="password", placeholder="••••••••", key="login_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([1.6, 1])
        with col1:
            login_btn = st.button("🚀 دخول إلى النظام", use_container_width=True, type="primary")
        with col2:
            if st.button("🔑 تغيير كلمة المرور", use_container_width=True):
                st.session_state.show_password_change = True
                st.rerun()
        
        if login_btn:
            user = verify_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("❌ فشلت المصادقة. يرجى مراجعة البيانات.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="text-align:center; margin-top:4rem;">
        <p style="color:rgba(255,255,255,0.1); font-size:0.8rem; letter-spacing:1px;">
            حوكمة ERP • نظام محاسبي متكامل
        </p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    render_header(is_change_password=True)
    
    _, main, _ = st.columns([1, 2, 1])
    with main:
        st.markdown('<div class="imperial-frame">', unsafe_allow_html=True)
        username = st.text_input("👤 اسم المستخدم", placeholder="اسم المستخدم الخاص بك", key="change_user")
        old_password = st.text_input("🔓 كلمة المرور الحالية", type="password", placeholder="الرمز الحالي", key="change_old")
        new_password = st.text_input("✨ كلمة المرور الجديدة", type="password", placeholder="الرمز الجديد", key="change_new")
        confirm_password = st.text_input("✅ تأكيد كلمة المرور", type="password", placeholder="إعادة كتابة الرمز", key="change_confirm")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([1.6, 1])
        with col1:
            if st.button("💾 حفظ التغييرات", use_container_width=True, type="primary"):
                if not username or not old_password or not new_password:
                    st.warning("⚠️ جميع الحقول مطلوبة.")
                elif new_password != confirm_password:
                    st.error("❌ كلمة المرور الجديدة وتأكيدها غير متطابقين.")
                elif len(new_password) < 4:
                    st.error("⚠️ كلمة المرور يجب أن تكون 4 أحرف على الأقل.")
                else:
                    success, message = change_password(username, old_password, new_password)
                    if success:
                        st.success(f"✨ {message}")
                        st.session_state.show_password_change = False
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        with col2:
            if st.button("↩️ إلغاء", use_container_width=True):
                st.session_state.show_password_change = False
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

def show():
    init_db()
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    apply_imperial_css()
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
