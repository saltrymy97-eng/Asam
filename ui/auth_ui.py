# ui/auth_ui.py
import streamlit as st
from database import init_db
from services.auth_service import (
    create_admin_if_needed,
    verify_user,
    change_password,
    logout_session
)

# ========== ألوان وتصميم فاخر ==========
T = "#FFFFFF"       # أبيض ناصع للنصوص الرئيسية
S = "#94A3B8"       # رمادي فضي للنصوص الفرعية
PR = "#8B5CF6"      # بنفسجي فخم
BL = "#3B82F6"      # أزرق ساطع
CY = "#06B6D4"      # سماوي للتوهج

def apply_ultra_premium_css():
    """حقن CSS متقدم لتصميم زجاجي فائق الفخامة (Ultra-Premium)"""
    st.markdown(f"""
    <style>
        /* 1. خلفية متدرجة ديناميكية تتحرك ببطء */
        @keyframes gradientBG {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .stApp {{
            background: linear-gradient(-45deg, #020617, #0f172a, #1e1b4b, #172554) !important;
            background-size: 400% 400% !important;
            animation: gradientBG 20s ease infinite !important;
            background-attachment: fixed !important;
        }}

        /* 🧹 إخفاء أي مستطيلات فارغة نهائياً */
        div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stHorizontalBlock"] > div:empty,
        div[data-testid="element-container"]:empty,
        div[data-testid="stMarkdownContainer"]:empty {{
            display: none !important;
            height: 0px !important;
            margin: 0px !important;
            padding: 0px !important;
        }}

        /* 2. بطاقة تسجيل الدخول (زجاج نقي ثلاثي الأبعاد) */
        div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
            background: rgba(15, 23, 42, 0.4) !important;
            backdrop-filter: blur(40px) saturate(150%) !important;
            -webkit-backdrop-filter: blur(40px) saturate(150%) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-top: 1px solid rgba(255, 255, 255, 0.2) !important; /* انعكاس الضوء من الأعلى */
            border-radius: 35px !important;
            padding: 3.5rem 3rem !important;
            box-shadow: 0 40px 80px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255,255,255,0.1) !important;
        }}

        /* 3. حقول الإدخال الفاخرة */
        div[data-baseweb="input"] {{
            background: rgba(0, 0, 0, 0.3) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 20px !important;
            padding: 8px 16px !important;
            transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            background: rgba(0, 0, 0, 0.5) !important;
            border-color: {PR} !important;
            box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.15), 0 15px 30px rgba(0,0,0,0.4) !important;
            transform: translateY(-3px);
        }}
        div[data-baseweb="input"] input {{
            background: transparent !important;
            color: {T} !important;
            font-size: 1.1rem !important;
            letter-spacing: 1px;
            font-weight: 500 !important;
        }}
        div[data-baseweb="input"] input::placeholder {{
            color: rgba(255, 255, 255, 0.2) !important;
            font-weight: 400 !important;
        }}

        /* 4. تنسيق العناوين فوق حقول الإدخال */
        .stTextInput label p {{
            color: {S} !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 10px !important;
        }}

        /* 5. زر الدخول الرئيسي (3D و Gradient) */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {PR} 0%, {BL} 100%) !important;
            border: none !important;
            font-weight: 800 !important;
            font-size: 1.15rem !important;
            letter-spacing: 1px !important;
            padding: 20px 24px !important;
            border-radius: 20px !important;
            color: white !important;
            transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
            box-shadow: 0 10px 20px -5px rgba(139, 92, 246, 0.5), inset 0 -3px 0 rgba(0,0,0,0.2) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-4px) !important;
            box-shadow: 0 20px 40px -10px rgba(139, 92, 246, 0.8), inset 0 -3px 0 rgba(0,0,0,0.2) !important;
            filter: brightness(1.15) !important;
        }}

        /* 6. الزر الثانوي (نسيت كلمة المرور) */
        button[kind="secondary"] {{
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: {S} !important;
            font-weight: 700 !important;
            font-size: 1.05rem !important;
            border-radius: 20px !important;
            padding: 20px 24px !important;
            transition: all 0.4s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border-color: rgba(255, 255, 255, 0.2) !important;
            transform: translateY(-2px);
        }}

        /* 7. أنيميشن شعار الهيدر */
        @keyframes glowPulse {{
            0%, 100% {{ filter: drop-shadow(0 0 25px rgba(139, 92, 246, 0.4)); transform: translateY(0); }}
            50% {{ filter: drop-shadow(0 0 45px rgba(59, 130, 246, 0.6)); transform: translateY(-5px); }}
        }}
    </style>
    """, unsafe_allow_html=True)

def render_premium_header(is_change_password=False):
    """هيدر فاخر مع تأثيرات بصرية متقدمة"""
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 2.5rem; margin-top: 1rem;">
            <div style="
                width: 130px; height: 130px; margin: 0 auto 1.8rem auto;
                background: linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.01));
                backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.1); 
                border-top: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 35px;
                display: flex; align-items: center; justify-content: center;
                animation: glowPulse 4s ease-in-out infinite;
                box-shadow: inset 0 0 20px rgba(139, 92, 246, 0.2);
            ">
                <span style="font-size: 4.5rem; font-weight: 900; 
                    background: linear-gradient(135deg, #FFFFFF, {PR}, {CY});
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                ">X</span>
            </div>
            <h1 style="color:{T}; font-size: 3.5rem; margin: 0; font-weight: 900; letter-spacing: 8px;">XD ERP</h1>
            <p style="color:{S}; margin-top: 0.8rem; font-size: 1.1rem; letter-spacing: 4px; font-weight: 300; text-transform: uppercase;">
                مرحباً بك مجدداً
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 2.5rem; margin-top: 1rem;">
            <div style="
                width: 100px; height: 100px; margin: 0 auto 1.5rem auto;
                display: flex; align-items: center; justify-content: center;
                animation: glowPulse 4s ease-in-out infinite;
            ">
                <span style="font-size: 4rem;">🛡️</span>
            </div>
            <h2 style="color:{T}; margin:0; font-weight:800; font-size:2.5rem; letter-spacing: 2px;">تأمين الحساب</h2>
            <p style="color:{S}; margin-top:0.8rem; font-size:1.1rem; letter-spacing: 1px;">الرجاء تعيين كلمة مرور قوية وجديدة</p>
        </div>
        """, unsafe_allow_html=True)

def login_form():
    render_premium_header(is_change_password=False)
    
    # نسبة 1:2:1 لمركزة البطاقة بأناقة (متجاوبة مع الشاشات)
    spacer_left, main_col, spacer_right = st.columns([1, 2, 1])
    
    with main_col:
        with st.container():
            username = st.text_input("👤 اسم المستخدم", placeholder="admin", key="login_user")
            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True) 
            
            password = st.text_input("🔒 كلمة المرور", type="password", placeholder="••••••••", key="login_pass")
            st.markdown("<div style='margin-bottom: 35px;'></div>", unsafe_allow_html=True)
            
            # ترتيب الأزرار لتبدو احترافية
            col1, col2 = st.columns([1.5, 1])
            with col1:
                login_btn = st.button("🚀 الدخول للنظام", use_container_width=True, type="primary")
            with col2:
                if st.button("🔑 نسيت الرمز", use_container_width=True):
                    st.session_state.show_password_change = True
                    st.rerun()
            
            if login_btn:
                user = verify_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("❌ بيانات الدخول غير صحيحة. يرجى المحاولة مجدداً.")
    
    st.markdown(f"""
    <div style="text-align:center; margin-top: 4rem; margin-bottom: 1rem;">
        <p style="color: rgba(255,255,255,0.2); font-size: 0.85rem; letter-spacing: 2px; font-weight: 300;">
            SECURE ENTERPRISE SYSTEM © 2026
        </p>
    </div>
    """, unsafe_allow_html=True)

def password_change_form():
    render_premium_header(is_change_password=True)
    
    spacer_left, main_col, spacer_right = st.columns([1, 2, 1])
    
    with main_col:
        with st.container():
            username = st.text_input("👤 اسم المستخدم", value="admin", disabled=True, key="change_user")
            st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
            
            old_password = st.text_input("🔓 كلمة المرور الحالية", type="password", placeholder="أدخل الرمز الحالي", key="change_old")
            st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
            
            new_password = st.text_input("✨ كلمة المرور الجديدة", type="password", placeholder="الرمز الجديد", key="change_new")
            st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
            
            confirm_password = st.text_input("✅ تأكيد كلمة المرور", type="password", placeholder="أعد إدخال الرمز للتأكيد", key="change_confirm")
            st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([1.5, 1])
            with col1:
                if st.button("💾 تأكيد وتحديث", use_container_width=True, type="primary"):
                    if not old_password or not new_password:
                        st.warning("⚠️ يرجى تعبئة جميع الحقول")
                    elif new_password != confirm_password:
                        st.error("❌ كلمتا المرور غير متطابقتين")
                    elif len(new_password) < 4:
                        st.error("⚠️ كلمة المرور قصيرة جداً (الحد الأدنى 4 أحرف)")
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
    
    # تطبيق التنسيق الفائق الفخامة
    apply_ultra_premium_css()
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
