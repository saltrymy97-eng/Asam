# ui/auth_ui.py – شاشة دخول حوكمة ERP (جلاسي فاخر)
import streamlit as st
from database import init_db
from services.auth_service import (
    create_admin_if_needed,
    verify_user,
    change_password,
    logout_session
)

# ========== ألوان هوية حوكمة ERP ==========
T = "#F8FAFC"        # أبيض ناصع
S = "#94A3B8"        # رمادي فضي
CY = "#06B6D4"       # Cyan سماوي
NB = "#0F172A"       # Navy Blue
GLD = "#F59E0B"      # ذهبي للتدرج
BG_CORE = "#020617"  # أسود عميق

def apply_ultra_premium_css():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

        @keyframes subtleOrbit {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .stApp {{
            background: radial-gradient(circle at top right, {NB} 0%, #020617 80%) !important;
            background-size: 200% 200% !important;
            animation: subtleOrbit 25s ease infinite !important;
            font-family: 'Cairo', sans-serif;
        }}

        div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stHorizontalBlock"] > div:empty {{
            display: none !important;
        }}

        div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.7) 0%, rgba(2, 6, 23, 0.9) 100%) !important;
            backdrop-filter: blur(40px) !important;
            -webkit-backdrop-filter: blur(40px) !important;
            border: 1px solid rgba(6, 182, 212, 0.15) !important;
            border-top: 1px solid rgba(6, 182, 212, 0.3) !important;
            border-radius: 32px !important;
            padding: 3rem 2.5rem !important;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(6, 182, 212, 0.1) !important;
        }}

        div[data-baseweb="input"] {{
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(6, 182, 212, 0.15) !important;
            border-radius: 16px !important;
            transition: all 0.3s ease;
        }}
        div[data-baseweb="input"]:focus-within {{
            border-color: rgba(6, 182, 212, 0.6) !important;
            box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.2) !important;
        }}
        div[data-baseweb="input"] input {{
            color: {T} !important;
            font-family: 'Cairo', sans-serif;
        }}

        button[kind="primary"] {{
            background: linear-gradient(135deg, {CY} 0%, #0891B2 100%) !important;
            border: none !important;
            font-weight: 700 !important;
            font-family: 'Cairo', sans-serif;
            border-radius: 16px !important;
            box-shadow: 0 10px 25px -5px rgba(6, 182, 212, 0.4) !important;
        }}

        button[kind="secondary"] {{
            background: rgba(255,255,255,0.03) !important;
            border: 1px solid rgba(6, 182, 212, 0.2) !important;
            color: {CY} !important;
            font-family: 'Cairo', sans-serif;
            border-radius: 16px !important;
        }}

        @keyframes executiveGlow {{
            0%, 100% {{ filter: drop-shadow(0 0 20px rgba(6, 182, 212, 0.3)); }}
            50% {{ filter: drop-shadow(0 0 40px rgba(6, 182, 212, 0.6)); }}
        }}
        .executive-logo-box {{
            animation: executiveGlow 6s ease-in-out infinite;
        }}
    </style>
    """, unsafe_allow_html=True)

def render_premium_header(is_change_password=False):
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 2.5rem;">
            <!-- أيقونة حوكمة الفاخرة -->
            <div class="executive-logo-box" style="
                width: 150px; height: 150px; margin: 0 auto 1.5rem auto;
                background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(15, 23, 42, 0.5) 100%);
                backdrop-filter: blur(20px);
                border: 1px solid rgba(6, 182, 212, 0.3);
                border-radius: 40px;
                display: flex; align-items: center; justify-content: center;
            ">
                <span style="font-size: 4rem; font-weight: 900;
                    background: linear-gradient(180deg, #FFFFFF 0%, {CY} 60%, {GLD} 100%);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    text-shadow: 0 0 30px rgba(6,182,212,0.5);
                ">ح</span>
            </div>
            
            <!-- اسم النظام -->
            <h1 style="color:{T}; font-size: 3rem; margin: 0; font-weight: 900; letter-spacing: 4px;
                background: linear-gradient(135deg, #FFFFFF 20%, {CY} 60%, {GLD} 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                filter: drop-shadow(0 0 10px rgba(6,182,212,0.3));
            ">حوكمة</h1>
            <h2 style="color:{T}; font-size: 1.5rem; margin: 0; font-weight: 700; letter-spacing: 8px;
                background: linear-gradient(135deg, #FFFFFF 0%, {CY} 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            ">ERP</h2>
            
            <!-- الشعار الفرعي -->
            <p style="color:{CY}; margin-top: 1rem; font-size: 1rem; font-weight: 600; letter-spacing: 3px;
                text-shadow: 0 0 10px rgba(6,182,212,0.3);
            ">
                إدارة ذكية • قرارات واثقة
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 2.5rem;">
            <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🛡️</div>
            <h2 style="color:{T}; margin:0; font-weight:800; font-size:2rem;">تأمين الحساب</h2>
            <p style="color:{S};">تحديث كلمة المرور لحسابك</p>
        </div>
        """, unsafe_allow_html=True)

def login_form():
    render_premium_header(is_change_password=False)
    
    _, main_col, _ = st.columns([1, 2.2, 1])
    
    with main_col:
        username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم", key="login_user")
        password = st.text_input("🔒 كلمة المرور", type="password", placeholder="••••••••", key="login_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([1.6, 1])
        with col1:
            login_btn = st.button("🚀 دخول", use_container_width=True, type="primary")
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
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة.")
    
    st.markdown(f"""
    <div style="text-align:center; margin-top: 4rem;">
        <p style="color: rgba(6, 182, 212, 0.2); font-size: 0.8rem; letter-spacing: 2px;">
            حوكمة ERP • نظام محاسبي متكامل
        </p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    render_premium_header(is_change_password=True)
    
    _, main_col, _ = st.columns([1, 2.2, 1])
    
    with main_col:
        username = st.text_input("👤 اسم المستخدم", key="change_user")
        old_password = st.text_input("🔓 كلمة المرور الحالية", type="password", key="change_old")
        new_password = st.text_input("✨ كلمة المرور الجديدة", type="password", key="change_new")
        confirm_password = st.text_input("✅ تأكيد كلمة المرور", type="password", key="change_confirm")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([1.6, 1])
        with col1:
            if st.button("💾 حفظ", use_container_width=True, type="primary"):
                if not username or not old_password or not new_password:
                    st.warning("⚠️ جميع الحقول مطلوبة.")
                elif new_password != confirm_password:
                    st.error("❌ كلمة المرور غير متطابقة.")
                elif len(new_password) < 4:
                    st.error("⚠️ كلمة المرور ضعيفة جداً.")
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

def show():
    init_db()
    create_admin_if_needed()
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    apply_ultra_premium_css()
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
