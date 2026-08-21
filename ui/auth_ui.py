# ui/auth_ui.py
import streamlit as st
from database import init_db
from services.auth_service import (
    verify_user,
    change_password,
    logout_session
)

# ========== لوحة ألوان النخبة والفخامة المطلقة ==========
T = "#F8FAFC"
S = "#64748B"
PR = "#7C3AED"
BL = "#2563EB"
BG_CORE = "#020617"

def apply_ultra_premium_css():
    """حقن نظام التصميم السيادي، والـ 3D Glassmorphism، والتأثيرات الحركية الفاخرة"""
    st.markdown(f"""
    <style>
        /* 🌌 حركة الخلفية الفضائية البطيئة */
        @keyframes subtleOrbit {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .stApp {{
            background: radial-gradient(circle at top right, #1e1b4b 0%, #090d16 60%, {BG_CORE} 100%) !important;
            background-size: 200% 200% !important;
            animation: subtleOrbit 25s ease infinite !important;
            background-attachment: fixed !important;
        }}

        /* 🚫 إخفاء الحاويات الفارغة التي تسبب مساحات بيضاء */
        div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stHorizontalBlock"] > div:empty,
        div[data-testid="element-container"]:empty,
        div[data-testid="stMarkdownContainer"]:empty {{
            display: none !important;
            height: 0px !important;
            margin: 0px !important;
            padding: 0px !important;
        }}

        /* 🛡️ حاوية تسجيل الدخول الزجاجية الفاخرة */
        div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.65) 0%, rgba(8, 13, 24, 0.85) 100%) !important;
            backdrop-filter: blur(60px) saturate(180%) !important;
            -webkit-backdrop-filter: blur(60px) saturate(180%) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-top: 1px solid rgba(124, 58, 237, 0.25) !important;
            border-bottom: 1px solid rgba(37, 99, 235, 0.15) !important;
            border-radius: 45px !important;
            padding: 4.5rem 4rem !important;
            box-shadow: 0 60px 120px rgba(0, 0, 0, 0.95), inset 0 1px 0 rgba(255,255,255,0.05), 0 0 40px rgba(124, 58, 237, 0.1) !important;
        }}

        /* ✨ مدخلات النصوص */
        div[data-baseweb="input"] {{
            background: rgba(3, 7, 18, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 22px !important;
            padding: 12px 20px !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: inset 0 4px 10px rgba(0,0,0,0.5) !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            background: rgba(0, 0, 0, 0.8) !important;
            border-color: #A78BFA !important;
            box-shadow: 0 0 25px rgba(124, 58, 237, 0.4), inset 0 2px 5px rgba(0,0,0,0.8) !important;
            transform: translateY(-2px);
        }}
        div[data-baseweb="input"] input {{
            background: transparent !important;
            color: {T} !important;
            font-size: 1.15rem !important;
            font-weight: 600 !important;
        }}
        div[data-baseweb="input"] input::placeholder {{
            color: rgba(255, 255, 255, 0.2) !important;
        }}

        /* 🏷️ تسميات الحقول */
        .stTextInput label p {{
            color: {S} !important;
            font-size: 0.95rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 12px !important;
        }}

        /* 🚀 زر المصادقة الأساسي */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {PR} 0%, {BL} 100%) !important;
            border: 1px solid rgba(167, 139, 250, 0.3) !important;
            font-weight: 900 !important;
            font-size: 1.15rem !important;
            letter-spacing: 1px !important;
            padding: 24px 30px !important;
            border-radius: 22px !important;
            color: white !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: 0 15px 35px rgba(124, 58, 237, 0.5), inset 0 -4px 0 rgba(0,0,0,0.2), inset 0 4px 10px rgba(255,255,255,0.2) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-5px) scale(1.02) !important;
            box-shadow: 0 25px 50px rgba(124, 58, 237, 0.7), inset 0 -4px 0 rgba(0,0,0,0.2) !important;
            filter: brightness(1.15) !important;
        }}

        /* 🔑 زر فرعي */
        button[kind="secondary"] {{
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: {S} !important;
            font-weight: 800 !important;
            font-size: 1rem !important;
            border-radius: 22px !important;
            padding: 24px 30px !important;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }}
        button[kind="secondary"]:hover {{
            background: rgba(255, 255, 255, 0.08) !important;
            color: {T} !important;
            border-color: rgba(167, 139, 250, 0.4) !important;
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.4);
        }}

        /* ======================================================= */
        /* 🔮 هندسة الجرم السيادي (الشعار الدائري ثلاثي الأبعاد) 🔮 */
        /* ======================================================= */
        
        /* 1. حركة الطفو والنبض 3D */
        @keyframes floatAndPulse {{
            0% {{ 
                transform: translateY(0) rotateX(5deg) rotateY(-5deg); 
                box-shadow: 0 0 40px rgba(124, 58, 237, 0.3), inset 0 10px 20px rgba(124, 58, 237, 0.2), inset 0 -10px 20px rgba(37, 99, 235, 0.2); 
            }}
            50% {{ 
                transform: translateY(-18px) rotateX(-5deg) rotateY(10deg); 
                box-shadow: 0 0 70px rgba(167, 139, 250, 0.7), 0 25px 40px rgba(0,0,0,0.6), inset 0 15px 30px rgba(124, 58, 237, 0.5), inset 0 -15px 30px rgba(37, 99, 235, 0.4); 
            }}
            100% {{ 
                transform: translateY(0) rotateX(5deg) rotateY(-5deg); 
                box-shadow: 0 0 40px rgba(124, 58, 237, 0.3), inset 0 10px 20px rgba(124, 58, 237, 0.2), inset 0 -10px 20px rgba(37, 99, 235, 0.2); 
            }}
        }}

        /* 2. حركة شعاع الليزر (الانعكاس الزجاجي) */
        @keyframes laserSweep {{
            0% {{ left: -200%; }}
            100% {{ left: 200%; }}
        }}

        /* 3. حاوية الشعار (الدائرة المثالية) */
        .hukma-orb {{
            position: relative;
            width: 175px; 
            height: 175px; 
            margin: 0 auto 2.5rem auto;
            background: linear-gradient(135deg, rgba(124,58,237,0.15) 0%, rgba(37,99,235,0.08) 100%);
            backdrop-filter: blur(30px); 
            -webkit-backdrop-filter: blur(30px);
            border: 2px solid rgba(167, 139, 250, 0.3); 
            border-top: 2px solid rgba(255, 255, 255, 0.4);
            border-bottom: 2px solid rgba(37, 99, 235, 0.2);
            border-radius: 50%; /* 🎯 الشكل الدائري */
            display: flex; 
            align-items: center; 
            justify-content: center;
            animation: floatAndPulse 6s ease-in-out infinite; /* الطفو */
            transform-style: preserve-3d;
            perspective: 1000px;
            overflow: hidden; /* لاحتواء شعاع الليزر داخله */
            z-index: 10;
        }}

        /* 4. شعاع الليزر */
        .hukma-orb::after {{
            content: '';
            position: absolute;
            top: -150%; left: -150%;
            width: 300%; height: 300%;
            background: linear-gradient(45deg, transparent 40%, rgba(255, 255, 255, 0.7) 50%, transparent 60%);
            transform: rotate(-45deg);
            animation: laserSweep 3.5s cubic-bezier(0.3, 1, 0.2, 1) infinite;
            pointer-events: none;
            z-index: 1;
        }}

        /* 5. النص البارز (3D Text) */
        .hukma-text {{
            font-size: 3.8rem;
            font-weight: 900;
            background: linear-gradient(135deg, #FFFFFF 20%, #D8B4FE 60%, #7C3AED 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 2px;
            display: inline-block;
            transform: translateZ(40px); /* الدفع للأمام */
            filter: drop-shadow(0 15px 20px rgba(0,0,0,0.9));
            z-index: 2;
            position: relative;
        }}

        /* ======================================================= */
        /* 🥇 توقيع المطور (التوهج الذهبي) 🥇 */
        /* ======================================================= */
        .dev-signature {{
            text-align: center;
            margin-top: 4.5rem;
            font-size: 1.1rem;
            color: rgba(255,255,255,0.4);
            letter-spacing: 1px;
            font-weight: 600;
            transition: all 0.4s ease;
            position: relative;
            z-index: 20;
        }}
        .dev-name {{
            background: linear-gradient(135deg, #fdf2be 0%, #D4AF37 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
            display: inline-block;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
        }}
        .dev-signature:hover .dev-name {{
            filter: drop-shadow(0 0 15px rgba(212, 175, 55, 0.8)) drop-shadow(0 0 5px rgba(255, 255, 255, 0.6));
            transform: scale(1.08) translateY(-2px);
        }}
    </style>
    """, unsafe_allow_html=True)


def render_premium_header(is_change_password=False):
    """توليد الهيدر التنفيذي الفاخر"""
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3.5rem; margin-top: 0.5rem; perspective: 1000px;">
            
            <!-- 🔮 الجرم السيادي والشعار الدائري -->
            <div class="hukma-orb">
                <span class="hukma-text">حوكمة</span>
            </div>

            <!-- 📝 الشعار اللفظي -->
            <p style="color:{S}; margin-top: 1.2rem; font-size: 1.3rem; letter-spacing: 2.5px; font-weight: 700;">
                إدارة <span style="color:#A78BFA; font-weight:900; text-shadow: 0 0 15px rgba(167,139,250,0.5);">ذكية</span> .. 
                قرارات <span style="color:#60A5FA; font-weight:900; text-shadow: 0 0 15px rgba(96,165,250,0.5);">واثقة</span>
            </p>
            <div style="width: 250px; height: 1.5px; background: linear-gradient(90deg, transparent, #A78BFA, transparent); margin: 1rem auto 0 auto; opacity: 0.7;"></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="hukma-orb" style="width: 120px; height: 120px; border-radius: 50%;">
                <span style="font-size: 3.5rem; transform: translateZ(30px); filter: drop-shadow(0 10px 15px rgba(0,0,0,0.8));">🛡️</span>
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
            st.markdown("<div style='margin-bottom: 18px;'></div>", unsafe_allow_html=True) 
            
            password = st.text_input("🔒 رمز المرور السري", type="password", placeholder="••••••••", key="login_pass")
            st.markdown("<div style='margin-bottom: 45px;'></div>", unsafe_allow_html=True)
            
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
    
    # 🥇 توقيع المطور الفاخر
    st.markdown(f"""
    <div class="dev-signature">
        حوكمة ERP • نظام محاسبي متكامل<br>
        <div style="margin-top: 8px;">تطوير: <span class="dev-name">سالم التريمي</span></div>
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
                    
    # 🥇 توقيع المطور في شاشة تغيير كلمة المرور أيضاً
    st.markdown(f"""
    <div class="dev-signature">
        <div style="margin-top: 8px;">تطوير: <span class="dev-name">سالم التريمي</span></div>
    </div>
    """, unsafe_allow_html=True)


def show():
    init_db()
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    apply_ultra_premium_css()
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
