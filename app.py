# ui/auth_ui.py - بوابة الدخول الفاخرة لنظام حوكمة ERP
import streamlit as st
from database import init_db
from services.auth_service import (
    create_admin_if_needed,
    verify_user,
    change_password,
    logout_session
)

# ========== لوحة ألوان النخبة والفخامة المطلقة (النسخة السماوية الزجاجية) ==========
T = "#F8FAFC"        # أبيض بلاتيني ناصع للنصوص القيادية
S = "#94A3B8"        # رمادي فضي خافت للنصوص الثانوية
PR = "#00d2ff"       # سماوي نيون (Neon Cyan)
BL = "#0052d4"       # أزرق محيطي (Ocean Blue)
BG_CORE = "#020617"  # أسود بركاني عميق للخلفية الأساسية

def apply_ultra_premium_css():
    """حقن نظام التصميم السيادي والـ Cyan Glassmorphism لصفحة الدخول"""
    st.markdown(f"""
    <style>
        /* 1. خلفية كونية متحركة بنعومة متناهية دون تشتيت */
        @keyframes subtleOrbit {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .stApp {{
            background: radial-gradient(circle at top right, #081229 0%, #030814 60%, {BG_CORE} 100%) !important;
            background-size: 200% 200% !important;
            animation: subtleOrbit 25s ease infinite !important;
            background-attachment: fixed !important;
        }}

        /* 🧹 تطهير تام للواجهة لمنع قفزات العناصر أو الفراغات الهيكلية */
        div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stHorizontalBlock"] > div:empty,
        div[data-testid="element-container"]:empty,
        div[data-testid="stMarkdownContainer"]:empty {{
            display: none !important;
            height: 0px !important;
            margin: 0px !important;
            padding: 0px !important;
        }}

        /* 2. حاوية الزجاج البركاني (Obsidian Luxury Card) */
        div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.55) 0%, rgba(8, 13, 24, 0.75) 100%) !important;
            backdrop-filter: blur(50px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(50px) saturate(160%) !important;
            border: 1px solid rgba(0, 210, 255, 0.08) !important;
            border-top: 1px solid rgba(0, 210, 255, 0.20) !important;
            border-radius: 40px !important;
            padding: 4rem 3.5rem !important;
            box-shadow: 0 50px 100px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(0, 210, 255, 0.05) !important;
        }}

        /* 3. حقول الإدخال الأنيقة والذكية */
        div[data-baseweb="input"] {{
            background: rgba(3, 7, 18, 0.5) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 20px !important;
            padding: 10px 18px !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            background: rgba(0, 0, 0, 0.7) !important;
            border-color: rgba(0, 210, 255, 0.6) !important;
            box-shadow: 0 0 0 1px rgba(0, 210, 255, 0.6), 0 20px 40px rgba(0,0,0,0.5) !important;
            transform: translateY(-2px);
        }}
        div[data-baseweb="input"] input {{
            background: transparent !important;
            color: {T} !important;
            font-size: 1.15rem !important;
            font-weight: 500 !important;
        }}
        div[data-baseweb="input"] input::placeholder {{
            color: rgba(255, 255, 255, 0.15) !important;
        }}

        /* عناوين الحقول السلوكية */
        .stTextInput label p {{
            color: {S} !important;
            font-size: 0.92rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 12px !important;
            text-transform: uppercase;
        }}

        /* 4. زر الدخول التنفيذي المتدرج (Executive Call-to-Action) */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {PR} 0%, {BL} 100%) !important;
            border: none !important;
            font-weight: 800 !important;
            font-size: 1.15rem !important;
            letter-spacing: 0.5px !important;
            padding: 22px 28px !important;
            border-radius: 20px !important;
            color: white !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: 0 15px 30px -5px rgba(0, 210, 255, 0.4), inset 0 -3px 0 rgba(0,0,0,0.15) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-4px) !important;
            box-shadow: 0 25px 50px -10px rgba(0, 210, 255, 0.6), inset 0 -3px 0 rgba(0,0,0,0.15) !important;
            filter: brightness(1.1) !important;
        }}

        /* 5. الزر الثانوي المحيد والمعزز */
        button[kind="secondary"] {{
            background: rgba(255, 255, 255, 0.02) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            color: {S} !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
            border-radius: 20px !important;
            padding: 22px 28px !important;
            transition: all 0.4s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: rgba(255, 255, 255, 0.06) !important;
            color: {T} !important;
            border-color: rgba(0, 210, 255, 0.3) !important;
            transform: translateY(-2px);
        }}

        /* 6. تأثير النبض الضوئي المستقر للشعار */
        @keyframes executiveGlow {{
            0%, 100% {{ filter: drop-shadow(0 0 30px rgba(0, 210, 255, 0.3)); transform: translateY(0); }}
            50% {{ filter: drop-shadow(0 0 50px rgba(0, 82, 212, 0.45)); transform: translateY(-4px); }}
        }}
        .executive-logo-box {{
            animation: executiveGlow 6s ease-in-out infinite;
        }}
    </style>
    """, unsafe_allow_html=True)

def render_premium_header(is_change_password=False):
    """توليد الهيدر التنفيذي الفاخر وتثبيت شعار حوكمة ERP الأيقوني"""
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="executive-logo-box" style="
                width: 140px; height: 140px; margin: 0 auto 2rem auto;
                background: linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%);
                backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
                border: 1px solid rgba(0, 210, 255, 0.15); 
                border-top: 1px solid rgba(0, 210, 255, 0.4);
                border-radius: 38px;
                display: flex; align-items: center; justify-content: center;
                box-shadow: inset 0 0 25px rgba(0, 210, 255, 0.15);
            ">
                <span style="font-size: 3.2rem; font-weight: 950; 
                    background: linear-gradient(135deg, #FFFFFF 20%, #00d2ff 70%, #0052d4 100%);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    letter-spacing: -1px; display: inline-block; padding-right: 2px;
                ">ERP</span>
            </div>
            <h1 style="color:{T}; font-size: 3rem; margin: 0; font-weight: 900; letter-spacing: 2px;">نظام حوكمة</h1>
            <p style="color:{S}; margin-top: 0.9rem; font-size: 1.05rem; letter-spacing: 3px; font-weight: 500; text-transform: uppercase;">
                بوابة الوصول الآمن والموثوق
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="executive-logo-box" style="
                width: 110px; height: 110px; margin: 0 auto 1.8rem auto;
                background: rgba(0, 210, 255, 0.05);
                border: 1px solid rgba(0, 210, 255, 0.2);
                border-radius: 32px;
                display: flex; align-items: center; justify-content: center;
            ">
                <span style="font-size: 3.5rem;">🛡️</span>
            </div>
            <h2 style="color:{T}; margin:0; font-weight:900; font-size:2.4rem; letter-spacing: 1px;">تأمين الهوية الرقمية</h2>
            <p style="color:{S}; margin-top:0.8rem; font-size:1.05rem; letter-spacing: 0.5px;">يرجى تحديث رمز الحماية الخاص بك للمتابعة</p>
        </div>
        """, unsafe_allow_html=True)

def login_form():
    render_premium_header(is_change_password=False)
    
    spacer_left, main_col, spacer_right = st.columns([1, 2.2, 1])
    
    with main_col:
        with st.container():
            username = st.text_input("👤 معرف المستخدم (ID)", placeholder="أدخل اسم المستخدم", key="login_user")
            st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True) 
            
            password = st.text_input("🔒 رمز المرور السري", type="password", placeholder="••••••••", key="login_pass")
            st.markdown("<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([1.6, 1])
            with col1:
                login_btn = st.button("🚀 مصادقة والدخول", use_container_width=True, type="primary")
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
                    st.error("❌ فشلت المصادقة المباشرة. يرجى مراجعة البيانات المدخلة.")
    
    st.markdown(f"""
    <div style="text-align:center; margin-top: 5rem; margin-bottom: 1rem;">
        <p style="color: rgba(255,255,255,0.15); font-size: 0.82rem; letter-spacing: 2px; font-weight: 400;">
            POWERED BY HAWKAMA SYSTEMS HUB • SECURE LAYER © 2026
        </p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    render_premium_header(is_change_password=True)
    
    spacer_left, main_col, spacer_right = st.columns([1, 2.2, 1])
    
    with main_col:
        with st.container():
            username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم الخاص بك", key="change_user")
            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
            
            old_password = st.text_input("🔓 رمز المرور السري الحالي", type="password", placeholder="الرمز الحالي", key="change_old")
            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
            
            new_password = st.text_input("✨ رمز المرور السري الجديد", type="password", placeholder="الرمز الجديد القوي", key="change_new")
            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
            
            confirm_password = st.text_input("✅ تأكيد الرمز الجديد", type="password", placeholder="إعادة كتابة الرمز", key="change_confirm")
            st.markdown("<div style='margin-bottom: 35px;'></div>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([1.6, 1])
            with col1:
                if st.button("💾 حفظ البيانات وتحديث", use_container_width=True, type="primary"):
                    if not username or not old_password or not new_password:
                        st.warning("⚠️ جميع الحقول مطلوبة.")
                    elif new_password != confirm_password:
                        st.error("❌ عدم تطابق في تأكيد رمز المرور الجديد.")
                    elif len(new_password) < 4:
                        st.error("⚠️ رمز المرور ضعيف (يجب ألا يقل عن 4 خانات).")
                    else:
                        success, message = change_password(username, old_password, new_password)
                        if success:
                            st.success(f"✨ {message}")
                            st.session_state.show_password_change = False
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
            with col2:
                if st.button("↩️ إلغاء العملية", use_container_width=True):
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
