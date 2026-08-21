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
S = "#94A3B8"
PR = "#7C3AED"
BL = "#2563EB"
BG_CORE = "#020617"

def apply_ultra_premium_css():
    """حقن نظام التصميم السيادي - بدون أي مسافات بادئة لتجنب تحولها لكود"""
    css_code = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap');

/* تعميم الخط مع حماية أيقونات النظام من التشويه */
* {{
font-family: 'Tajawal', sans-serif !important;
}}

/* إصلاح مشكلة ظهور كلمة visibility بإعادة خط الأيقونات الأصلي */
.material-symbols-rounded, 
.material-icons,
[data-testid="stIconMaterial"],
span[class*="material"] {{
font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}}

@keyframes subtleOrbit {{
0% {{ background-position: 0% 50%; }}
50% {{ background-position: 100% 50%; }}
100% {{ background-position: 0% 50%; }}
}}
.stApp {{
background: radial-gradient(circle at top right, #1e1b4b 0%, #090d16 50%, {BG_CORE} 100%) !important;
background-size: 200% 200% !important;
animation: subtleOrbit 20s ease infinite !important;
background-attachment: fixed !important;
}}

div[data-testid="stVerticalBlock"] > div:empty,
div[data-testid="stHorizontalBlock"] > div:empty,
div[data-testid="element-container"]:empty,
div[data-testid="stMarkdownContainer"]:empty {{
display: none !important;
}}

/* حاوية تسجيل الدخول */
div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
background: linear-gradient(145deg, rgba(15, 23, 42, 0.75) 0%, rgba(8, 13, 24, 0.95) 100%) !important;
backdrop-filter: blur(40px) saturate(200%) !important;
-webkit-backdrop-filter: blur(40px) saturate(200%) !important;
border: 1px solid rgba(255, 255, 255, 0.08) !important;
border-top: 1px solid rgba(167, 139, 250, 0.3) !important;
border-bottom: 1px solid rgba(37, 99, 235, 0.2) !important;
border-radius: 40px !important;
padding: 3rem 2rem !important; 
box-shadow: 0 40px 100px rgba(0, 0, 0, 0.95), inset 0 1px 0 rgba(255,255,255,0.1), 0 0 50px rgba(124, 58, 237, 0.15) !important;
}}

/* مدخلات النصوص - تم تحسينها للحفاظ على أيقونة العين */
div[data-baseweb="input"] {{
background: rgba(3, 7, 18, 0.7) !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
border-radius: 18px !important;
transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1) !important;
box-shadow: inset 0 4px 10px rgba(0,0,0,0.6) !important;
}}
div[data-baseweb="input"]:focus-within {{
background: rgba(0, 0, 0, 0.9) !important;
border-color: #A78BFA !important;
box-shadow: 0 0 25px rgba(124, 58, 237, 0.5), inset 0 2px 5px rgba(0,0,0,0.9) !important;
transform: translateY(-2px);
}}
div[data-baseweb="input"] input {{
background: transparent !important;
color: {T} !important;
font-size: 1.1rem !important;
font-weight: 600 !important;
}}

/* تسميات الحقول */
.stTextInput label p {{
color: {S} !important;
font-size: 1rem !important;
font-weight: 700 !important;
letter-spacing: 0.5px !important;
margin-bottom: 12px !important;
}}

/* أزرار مخصصة */
button[kind="primary"] {{
background: linear-gradient(135deg, {PR} 0%, {BL} 100%) !important;
border: 1px solid rgba(167, 139, 250, 0.4) !important;
font-weight: 800 !important;
font-size: 1.15rem !important;
padding: 24px 30px !important;
border-radius: 20px !important;
color: white !important;
transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1) !important;
box-shadow: 0 15px 35px rgba(124, 58, 237, 0.6), inset 0 -4px 0 rgba(0,0,0,0.3), inset 0 4px 10px rgba(255,255,255,0.3) !important;
width: 100% !important;
}}
button[kind="primary"]:hover {{
transform: translateY(-4px) scale(1.02) !important;
box-shadow: 0 25px 50px rgba(124, 58, 237, 0.8), inset 0 -4px 0 rgba(0,0,0,0.3) !important;
filter: brightness(1.2) !important;
}}

button[kind="secondary"] {{
background: rgba(255, 255, 255, 0.04) !important;
border: 1px solid rgba(255, 255, 255, 0.1) !important;
color: {T} !important;
font-weight: 700 !important;
font-size: 1rem !important;
border-radius: 20px !important;
padding: 24px 30px !important;
transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1) !important;
width: 100% !important;
}}
button[kind="secondary"]:hover {{
background: rgba(255, 255, 255, 0.1) !important;
border-color: rgba(167, 139, 250, 0.5) !important;
transform: translateY(-3px);
box-shadow: 0 10px 25px rgba(0,0,0,0.5);
}}

/* ======================================================= */
/* 🔮 هندسة الجرم السيادي 🔮 */
/* ======================================================= */
@keyframes floatAndPulse {{
0% {{ transform: translateY(0) rotateX(5deg) rotateY(-5deg); box-shadow: 0 0 50px rgba(124, 58, 237, 0.4), inset 0 10px 30px rgba(124, 58, 237, 0.3), inset 0 -10px 30px rgba(37, 99, 235, 0.3); }}
50% {{ transform: translateY(-20px) rotateX(-5deg) rotateY(10deg); box-shadow: 0 0 100px rgba(167, 139, 250, 0.8), 0 30px 60px rgba(0,0,0,0.8), inset 0 20px 40px rgba(124, 58, 237, 0.6), inset 0 -20px 40px rgba(37, 99, 235, 0.5); }}
100% {{ transform: translateY(0) rotateX(5deg) rotateY(-5deg); box-shadow: 0 0 50px rgba(124, 58, 237, 0.4), inset 0 10px 30px rgba(124, 58, 237, 0.3), inset 0 -10px 30px rgba(37, 99, 235, 0.3); }}
}}

@keyframes laserSweep {{
0% {{ left: -200%; opacity: 0; }}
10% {{ opacity: 1; }}
90% {{ opacity: 1; }}
100% {{ left: 200%; opacity: 0; }}
}}

.hukma-orb {{
position: relative;
width: 230px; 
height: 230px; 
margin: 0 auto 2.5rem auto;
background: linear-gradient(135deg, rgba(124,58,237,0.2) 0%, rgba(37,99,235,0.1) 100%);
backdrop-filter: blur(20px); 
-webkit-backdrop-filter: blur(20px);
border: 3px solid rgba(167, 139, 250, 0.4); 
border-top: 4px solid rgba(255, 255, 255, 0.6);
border-bottom: 3px solid rgba(37, 99, 235, 0.3);
border-radius: 50%; 
display: flex; 
align-items: center; 
justify-content: center;
animation: floatAndPulse 6s ease-in-out infinite; 
transform-style: preserve-3d;
perspective: 1000px;
overflow: hidden; 
z-index: 10;
}}

.hukma-orb::after {{
content: '';
position: absolute;
top: -100%; left: -200%;
width: 200%; height: 200%;
background: linear-gradient(45deg, transparent 40%, rgba(255, 255, 255, 0.8) 50%, transparent 60%);
transform: rotate(-45deg);
animation: laserSweep 4.5s cubic-bezier(0.25, 1, 0.5, 1) infinite;
pointer-events: none;
z-index: 1;
}}

.hukma-text {{
font-size: 3.2rem; /* تم تصغير النص ليتناسب تماماً ويحتويه الجرم الدائري */
font-weight: 900;
background: linear-gradient(135deg, #FFFFFF 10%, #E9D5FF 50%, #7C3AED 100%);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
letter-spacing: 1px;
display: inline-block;
transform: translateZ(40px); 
filter: drop-shadow(0 15px 20px rgba(0,0,0,0.9));
z-index: 2;
position: relative;
}}

.dev-signature {{
text-align: center;
margin-top: 5rem;
font-size: 1.1rem;
color: rgba(255,255,255,0.5);
letter-spacing: 1px;
font-weight: 500;
position: relative;
z-index: 20;
}}
.dev-name {{
background: linear-gradient(135deg, #FDE68A 0%, #D4AF37 50%, #B45309 100%);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
font-weight: 900;
font-size: 1.2rem;
display: inline-block;
transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
position: relative;
}}
.dev-signature:hover .dev-name {{
filter: drop-shadow(0 0 20px rgba(212, 175, 55, 0.9)) drop-shadow(0 0 10px rgba(255, 255, 255, 0.8));
transform: scale(1.1) translateY(-3px);
}}
</style>"""
    st.markdown(css_code, unsafe_allow_html=True)


def render_premium_header(is_change_password=False):
    """توليد الهيدر التنفيذي الفاخر - بدون أي مسافات بادئة إطلاقاً"""
    if not is_change_password:
        html = f"""<div style="text-align:center; margin-bottom: 3.5rem; margin-top: 0.5rem; perspective: 1000px;">
<div class="hukma-orb">
<span class="hukma-text">حوكمة</span>
</div>
<p style="color:{S}; margin-top: 1.5rem; font-size: 1.4rem; letter-spacing: 1px; font-weight: 700;">
إدارة <span style="color:#A78BFA; font-weight:900; text-shadow: 0 0 20px rgba(167,139,250,0.6);">ذكية</span> .. 
قرارات <span style="color:#60A5FA; font-weight:900; text-shadow: 0 0 20px rgba(96,165,250,0.6);">واثقة</span>
</p>
<div style="width: 250px; height: 2px; background: linear-gradient(90deg, transparent, #A78BFA, transparent); margin: 1.5rem auto 0 auto; opacity: 0.8; box-shadow: 0 0 15px #A78BFA;"></div>
</div>"""
        st.markdown(html, unsafe_allow_html=True)
    else:
        html = f"""<div style="text-align:center; margin-bottom: 3.5rem; margin-top: 0.5rem; perspective: 1000px;">
<div class="hukma-orb" style="width: 150px; height: 150px; border-radius: 50%;">
<span style="font-size: 4rem; transform: translateZ(30px); filter: drop-shadow(0 10px 15px rgba(0,0,0,0.8));">🛡️</span>
</div>
<h2 style="color:{T}; margin:0; font-weight:900; font-size:2.5rem; letter-spacing: 0.5px;">تأمين الهوية الرقمية</h2>
<p style="color:{S}; margin-top:1rem; font-size:1.1rem; letter-spacing: 0.5px;">يرجى تحديث رمز الحماية الخاص بك للمتابعة بأمان</p>
</div>"""
        st.markdown(html, unsafe_allow_html=True)


def login_form():
    render_premium_header(is_change_password=False)
    
    spacer_left, main_col, spacer_right = st.columns([0.5, 3, 0.5])
    
    with main_col:
        with st.container():
            username = st.text_input("👤 معرف المستخدم (ID)", placeholder="أدخل اسم المستخدم", key="login_user")
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True) 
            
            password = st.text_input("🔒 رمز المرور السري", type="password", placeholder="••••••••", key="login_pass")
            st.markdown("<div style='margin-bottom: 45px;'></div>", unsafe_allow_html=True)
            
            login_btn = st.button("🚀 مصادقة والدخول", use_container_width=True, type="primary")
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            if st.button("🔑 تغيير الرمز", use_container_width=True, type="secondary"):
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
    
    dev_html = """<div class="dev-signature">
حوكمة ERP • نظام محاسبي متكامل<br>
<div style="margin-top: 10px;">تطوير: <span class="dev-name">سالم التريمي</span></div>
</div>"""
    st.markdown(dev_html, unsafe_allow_html=True)


def password_change_form():
    render_premium_header(is_change_password=True)
    
    spacer_left, main_col, spacer_right = st.columns([0.5, 3, 0.5])
    
    with main_col:
        with st.container():
            username = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم الخاص بك", key="change_user")
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            old_password = st.text_input("🔓 رمز المرور السري الحالي", type="password", placeholder="الرمز الحالي", key="change_old")
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            new_password = st.text_input("✨ رمز المرور السري الجديد", type="password", placeholder="الرمز الجديد القوي", key="change_new")
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            confirm_password = st.text_input("✅ تأكيد الرمز الجديد", type="password", placeholder="إعادة كتابة الرمز", key="change_confirm")
            st.markdown("<div style='margin-bottom: 40px;'></div>", unsafe_allow_html=True)
            
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
                        
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            if st.button("↩️ تراجع", use_container_width=True, type="secondary"):
                st.session_state.show_password_change = False
                st.rerun()
                    
    dev_html = """<div class="dev-signature">
<div style="margin-top: 10px;">تطوير: <span class="dev-name">سالم التريمي</span></div>
</div>"""
    st.markdown(dev_html, unsafe_allow_html=True)


def show():
    init_db()
    
    if 'show_password_change' not in st.session_state:
        st.session_state.show_password_change = False
    
    apply_ultra_premium_css()
    
    if st.session_state.show_password_change:
        password_change_form()
    else:
        login_form()
