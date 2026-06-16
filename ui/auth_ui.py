# ui/auth_ui.py – شاشة الدخول الذهبية الفاخرة
import streamlit as st
from database import init_db
from services.auth_service import (
    verify_user,
    change_password,
    logout_session
)

# ========== لوحة ألوان ذهبية ملكية ==========
T = "#F8FAFC"        # أبيض بلاتيني ناصع للنصوص القيادية
S = "#CBD5E1"        # رمادي فضي خافت للنصوص الثانوية
GOLD = "#D4AF37"     # ذهبي ملكي
GOLD_LIGHT = "#FCF6BA"  # ذهبي فاتح
GOLD_DARK = "#AA771C"   # ذهبي داكن
BG_CORE = "#020617"  # أسود بركاني عميق للخلفية الأساسية

def apply_ultra_premium_css():
    """حقن نظام التصميم الذهبي الملكي لصفحة الدخول"""
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
        * {{ font-family: 'Cairo', sans-serif; }}

        /* 1. خلفية كونية متحركة بنعومة متناهية */
        @keyframes subtleOrbit {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .stApp {{
            background: radial-gradient(circle at top right, #1a1a0a 0%, #0a0d06 60%, {BG_CORE} 100%) !important;
            background-size: 200% 200% !important;
            animation: subtleOrbit 25s ease infinite !important;
            background-attachment: fixed !important;
        }}

        /* 🧹 تطهير تام للواجهة */
        div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stHorizontalBlock"] > div:empty,
        div[data-testid="element-container"]:empty,
        div[data-testid="stMarkdownContainer"]:empty {{
            display: none !important;
            height: 0px !important;
            margin: 0px !important;
            padding: 0px !important;
        }}

        /* 2. حاوية الزجاج الذهبي */
        div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
            background: linear-gradient(145deg, rgba(20, 20, 10, 0.7) 0%, rgba(10, 10, 5, 0.85) 100%) !important;
            backdrop-filter: blur(50px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(50px) saturate(160%) !important;
            border: 1px solid rgba(212, 175, 55, 0.2) !important;
            border-top: 1px solid rgba(212, 175, 55, 0.4) !important;
            border-radius: 40px !important;
            padding: 4rem 3.5rem !important;
            box-shadow: 0 50px 100px rgba(0, 0, 0, 0.85), 0 0 30px rgba(212, 175, 55, 0.05), inset 0 1px 0 rgba(255,255,255,0.02) !important;
        }}

        /* 3. حقول الإدخال الذهبية */
        div[data-baseweb="input"] {{
            background: rgba(10, 10, 5, 0.6) !important;
            border: 1px solid rgba(212, 175, 55, 0.2) !important;
            border-radius: 20px !important;
            padding: 10px 18px !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            background: rgba(0, 0, 0, 0.8) !important;
            border-color: rgba(212, 175, 55, 0.8) !important;
            box-shadow: 0 0 0 1px rgba(212, 175, 55, 0.6), 0 20px 40px rgba(0,0,0,0.5), 0 0 20px rgba(212, 175, 55, 0.2) !important;
            transform: translateY(-2px);
        }}
        div[data-baseweb="input"] input {{
            background: transparent !important;
            color: {T} !important;
            font-size: 1.15rem !important;
            font-weight: 500 !important;
            -webkit-text-fill-color: {T} !important;
            caret-color: {GOLD} !important;
            box-shadow: none !important;
        }}
        div[data-baseweb="input"] input:-webkit-autofill,
        div[data-baseweb="input"] input:-webkit-autofill:hover,
        div[data-baseweb="input"] input:-webkit-autofill:focus,
        div[data-baseweb="input"] input:-webkit-autofill:active {{
            -webkit-box-shadow: 0 0 0 30px rgba(10, 10, 5, 0.9) inset !important;
            -webkit-text-fill-color: {T} !important;
            caret-color: {GOLD} !important;
            transition: background-color 5000s ease-in-out 0s;
        }}
        div[data-baseweb="input"] input::placeholder {{
            color: rgba(255, 255, 255, 0.25) !important;
            font-weight: 400;
        }}

        /* عناوين الحقول السلوكية */
        .stTextInput label p {{
            color: {GOLD_LIGHT} !important;
            font-size: 0.92rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 12px !important;
            text-transform: uppercase;
        }}

        /* 4. زر الدخول الذهبي */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {GOLD} 0%, {GOLD_DARK} 100%) !important;
            border: none !important;
            font-weight: 800 !important;
            font-size: 1.15rem !important;
            letter-spacing: 0.5px !important;
            padding: 22px 28px !important;
            border-radius: 20px !important;
            color: #000 !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: 0 15px 30px -5px rgba(212, 175, 55, 0.4), inset 0 -3px 0 rgba(0,0,0,0.15) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-4px) !important;
            box-shadow: 0 25px 50px -10px rgba(212, 175, 55, 0.6), 0 0 30px rgba(212, 175, 55, 0.3), inset 0 -3px 0 rgba(0,0,0,0.15) !important;
            filter: brightness(1.2) !important;
            color: #000 !important;
        }}

        /* 5. الزر الثانوي الذهبي */
        button[kind="secondary"] {{
            background: rgba(212, 175, 55, 0.05) !important;
            border: 1px solid rgba(212, 175, 55, 0.3) !important;
            color: {GOLD_LIGHT} !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
            border-radius: 20px !important;
            padding: 22px 28px !important;
            transition: all 0.4s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: rgba(212, 175, 55, 0.15) !important;
            color: {GOLD} !important;
            border-color: rgba(212, 175, 55, 0.6) !important;
            transform: translateY(-2px);
        }}

        /* 6. تأثير النبض الضوئي الذهبي للشعار */
        @keyframes executiveGlow {{
            0%, 100% {{ filter: drop-shadow(0 0 30px rgba(212, 175, 55, 0.3)); transform: translateY(0); }}
            50% {{ filter: drop-shadow(0 0 50px rgba(212, 175, 55, 0.5)); transform: translateY(-4px); }}
        }}
        .executive-logo-box {{
            animation: executiveGlow 6s ease-in-out infinite;
        }}

        /* 7. رسائل الخطأ والنجاح */
        .stAlert {{
            background: rgba(212, 175, 55, 0.1) !important;
            border: 1px solid rgba(212, 175, 55, 0.3) !important;
            color: {GOLD_LIGHT} !important;
            border-radius: 12px !important;
        }}
    </style>
    """, unsafe_allow_html=True)

def render_premium_header(is_change_password=False):
    """توليد الهيدر الذهبي الفاخر"""
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="executive-logo-box" style="
                width: 160px; height: 160px; margin: 0 auto 2rem auto;
                background: linear-gradient(135deg, rgba(212,175,55,0.1) 0%, rgba(170,119,28,0.05) 100%);
                backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
                border: 1px solid rgba(212, 175, 55, 0.4); 
                border-top: 1px solid rgba(212, 175, 55, 0.7);
                border-radius: 38px;
                display: flex; align-items: center; justify-content: center;
                box-shadow: 0 0 35px rgba(212, 175, 55, 0.2), inset 0 0 25px rgba(212, 175, 55, 0.1);
            ">
                <span style="font-size: 3.2rem; font-weight: 950; 
                    background: linear-gradient(135deg, #FFFFFF 20%, #FCF6BA 70%, {GOLD} 100%);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    letter-spacing: 2px; display: inline-block;
                ">حوكمة</span>
            </div>
            <p style="color:{S}; margin-top: 0.9rem; font-size: 1.2rem; letter-spacing: 2px; font-weight: 600;">
                إدارة <span style="color:{GOLD_LIGHT}; font-weight:700;">ذكية</span> .. قرارات <span style="color:{GOLD}; font-weight:700;">واثقة</span>
            </p>
            <div style="width: 220px; height: 1px; background: linear-gradient(90deg, transparent, {GOLD}, transparent); margin: 0.6rem auto 0 auto;"></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="executive-logo-box" style="
                width: 110px; height: 110px; margin: 0 auto 1.8rem auto;
                background: rgba(212, 175, 55, 0.05);
                border: 1px solid rgba(212, 175, 55, 0.2);
                border-radius: 32px;
                display: flex; align-items: center; justify-content: center;
            ">
                <span style="font-size: 3.5rem;">🛡️</span>
            </div>
            <h2 style="color:{GOLD}; margin:0; font-weight:900; font-size:2.4rem; letter-spacing: 1px;">تأمين الهوية الرقمية</h2>
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
        <p style="color: rgba(212,175,55,0.3); font-size: 0.82rem; letter-spacing: 2px; font-weight: 400;">
            حوكمة ERP • نظام محاسبي متكامل
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
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    apply_ultra_premium_css()
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
