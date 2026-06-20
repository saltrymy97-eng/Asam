# ui/auth_ui.py
import streamlit as st
from database import init_db, get_connection
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
    """حقن نظام التصميم السيادي والـ Obsidian Glassmorphism لصفحة الدخول"""
    st.markdown(f"""
    <style>
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

        div[data-testid="stVerticalBlock"] > div:empty,
        div[data-testid="stHorizontalBlock"] > div:empty,
        div[data-testid="element-container"]:empty,
        div[data-testid="stMarkdownContainer"]:empty {{
            display: none !important;
            height: 0px !important;
            margin: 0px !important;
            padding: 0px !important;
        }}

        div[data-testid="stVerticalBlock"] > div > div > div[data-testid="stVerticalBlock"] {{
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.55) 0%, rgba(8, 13, 24, 0.75) 100%) !important;
            backdrop-filter: blur(50px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(50px) saturate(160%) !important;
            border: 1px solid rgba(255, 255, 255, 0.04) !important;
            border-top: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 40px !important;
            padding: 4rem 3.5rem !important;
            box-shadow: 0 50px 100px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255,255,255,0.02) !important;
        }}

        div[data-baseweb="input"] {{
            background: rgba(3, 7, 18, 0.5) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 20px !important;
            padding: 10px 18px !important;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            background: rgba(0, 0, 0, 0.7) !important;
            border-color: rgba(124, 58, 237, 0.6) !important;
            box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.6), 0 20px 40px rgba(0,0,0,0.5) !important;
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

        .stTextInput label p {{
            color: {S} !important;
            font-size: 0.92rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 12px !important;
            text-transform: uppercase;
        }}

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
            box-shadow: 0 15px 30px -5px rgba(124, 58, 237, 0.4), inset 0 -3px 0 rgba(0,0,0,0.15) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-4px) !important;
            box-shadow: 0 25px 50px -10px rgba(124, 58, 237, 0.6), inset 0 -3px 0 rgba(0,0,0,0.15) !important;
            filter: brightness(1.1) !important;
        }}

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
            border-color: rgba(255, 255, 255, 0.15) !important;
            transform: translateY(-2px);
        }}

        @keyframes executiveGlow {{
            0%, 100% {{ filter: drop-shadow(0 0 30px rgba(124, 58, 237, 0.3)); transform: translateY(0); }}
            50% {{ filter: drop-shadow(0 0 50px rgba(37, 99, 219, 0.45)); transform: translateY(-4px); }}
        }}
        .executive-logo-box {{
            animation: executiveGlow 6s ease-in-out infinite;
        }}
    </style>
    """, unsafe_allow_html=True)

def render_premium_header(is_change_password=False):
    """توليد الهيدر التنفيذي الفاخر"""
    if not is_change_password:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="executive-logo-box" style="
                width: 160px; height: 160px; margin: 0 auto 2rem auto;
                background: linear-gradient(135deg, rgba(124,58,237,0.1) 0%, rgba(37,99,235,0.05) 100%);
                backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px);
                border: 1px solid rgba(124, 58, 237, 0.3); 
                border-top: 1px solid rgba(124, 58, 237, 0.5);
                border-radius: 38px;
                display: flex; align-items: center; justify-content: center;
                box-shadow: 0 0 35px rgba(124, 58, 237, 0.15), inset 0 0 25px rgba(124, 58, 237, 0.1);
            ">
                <span style="font-size: 3.2rem; font-weight: 950; 
                    background: linear-gradient(135deg, #FFFFFF 20%, #A78BFA 70%, #7C3AED 100%);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    letter-spacing: 2px; display: inline-block;
                ">حوكمة</span>
            </div>
            <p style="color:{S}; margin-top: 0.9rem; font-size: 1.2rem; letter-spacing: 2px; font-weight: 600;">
                إدارة <span style="color:#A78BFA; font-weight:700;">ذكية</span> .. قرارات <span style="color:#60A5FA; font-weight:700;">واثقة</span>
            </p>
            <div style="width: 220px; height: 1px; background: linear-gradient(90deg, transparent, #A78BFA, transparent); margin: 0.6rem auto 0 auto;"></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom: 3rem; margin-top: 0.5rem;">
            <div class="executive-logo-box" style="
                width: 110px; height: 110px; margin: 0 auto 1.8rem auto;
                background: rgba(239, 68, 68, 0.03);
                border: 1px solid rgba(239, 68, 68, 0.1);
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
                # --- 🆕 تشخيص عملية تسجيل الدخول ---
                st.write("---")
                st.write("### 🩺 تشخيص عملية تسجيل الدخول")
                
                # 1. عرض المدخلات
                st.write(f"👤 **اسم المستخدم المدخل:** `{username}`")
                st.write(f"🔒 **طول كلمة المرور المدخلة:** `{len(password) if password else 0}` حرف")
                
                # 2. التحقق من وجود المستخدم في قاعدة البيانات
                try:
                    conn = get_connection()
                    conn.row_factory = __import__('sqlite3').Row
                    c = conn.cursor()
                    c.execute("SELECT username, password FROM users WHERE username=?", (username,))
                    user_row = c.fetchone()
                    conn.close()
                    
                    if user_row:
                        st.write(f"✅ **المستخدم موجود:** `{user_row['username']}`")
                        stored_hash = user_row['password']
                        st.write(f"🔑 **البصمة المخزنة تبدأ بـ:** `{stored_hash[:15]}...`")
                        
                        # 3. التحقق من تطابق كلمة المرور يدويًا
                        import bcrypt
                        # تحويل كلمة المرور المدخلة إلى bytes
                        input_password_bytes = password.encode('utf-8')
                        
                        # تحويل البصمة المخزنة إلى bytes (إذا كانت str)
                        if isinstance(stored_hash, str):
                            stored_hash_bytes = stored_hash.encode('utf-8')
                        else:
                            stored_hash_bytes = stored_hash
                        
                        # فحص التوافق
                        try:
                            is_match = bcrypt.checkpw(input_password_bytes, stored_hash_bytes)
                            if is_match:
                                st.success(f"✅ **كلمة المرور صحيحة!** سيتم تسجيل الدخول.")
                            else:
                                st.error(f"❌ **كلمة المرور غير متطابقة مع البصمة المخزنة!**")
                        except Exception as bcrypt_error:
                            st.error(f"❌ **خطأ في bcrypt:** `{bcrypt_error}`")
                    else:
                        st.error(f"❌ **المستخدم `{username}` غير موجود في قاعدة البيانات!**")
                except Exception as db_error:
                    st.error(f"❌ **خطأ في قراءة قاعدة البيانات:** `{db_error}`")
                
                # 4. استدعاء verify_user الأصلي للمقارنة
                st.write("---")
                st.write("**🔍 نتيجة `verify_user` الأصلية:**")
                user = verify_user(username, password)
                if user:
                    st.write("✅ **`verify_user` نجح!**")
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("❌ **`verify_user` فشل.**")
    
    st.markdown(f"""
    <div style="text-align:center; margin-top: 5rem; margin-bottom: 1rem;">
        <p style="color: rgba(255,255,255,0.15); font-size: 0.82rem; letter-spacing: 2px; font-weight: 400;">
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
                    # --- 🆕 قسم التشخيص ---
                    st.write("---")
                    st.write("### 🩺 تشخيص عملية تغيير كلمة المرور")
                    
                    # 1. عرض المدخلات (بدون كشف كلمة المرور)
                    st.write(f"👤 **اسم المستخدم:** `{username}`")
                    st.write(f"🔓 **طول كلمة المرور القديمة:** `{len(old_password) if old_password else 0}` حرف")
                    st.write(f"✨ **طول كلمة المرور الجديدة:** `{len(new_password) if new_password else 0}` حرف")
                    st.write(f"🔑 **التطابق:** {'✅ متطابقة' if new_password == confirm_password else '❌ غير متطابقة'}")
                    
                    # 2. التحقق من وجود المستخدم في قاعدة البيانات
                    try:
                        conn = get_connection()
                        conn.row_factory = __import__('sqlite3').Row
                        c = conn.cursor()
                        c.execute("SELECT username, password FROM users WHERE username=?", (username,))
                        user_row = c.fetchone()
                        conn.close()
                        
                        if user_row:
                            st.write(f"✅ **المستخدم موجود في قاعدة البيانات:** `{user_row['username']}`")
                            st.write(f"🔑 **كلمة المرور المخزنة تبدأ بـ:** `{user_row['password'][:10]}...`")
                        else:
                            st.error(f"❌ **المستخدم `{username}` غير موجود في قاعدة البيانات!**")
                    except Exception as db_error:
                        st.error(f"❌ **خطأ في قراءة قاعدة البيانات:** `{db_error}`")
                    
                    # 3. استدعاء دالة التغيير
                    if new_password == confirm_password and len(new_password) >= 4:
                        st.write("⏳ **جاري استدعاء `change_password`...**")
                        success, message = change_password(username, old_password, new_password)
                        
                        if success:
                            # التحقق من أن التغيير تم فعلاً
                            try:
                                conn2 = get_connection()
                                conn2.row_factory = __import__('sqlite3').Row
                                c2 = conn2.cursor()
                                c2.execute("SELECT password FROM users WHERE username=?", (username,))
                                updated_row = c2.fetchone()
                                conn2.close()
                                
                                if updated_row:
                                    st.write(f"🔑 **كلمة المرور الجديدة المخزنة تبدأ بـ:** `{updated_row['password'][:10]}...`")
                            except:
                                pass
                            
                            # 🆕 إظهار مربع نجاح مع زر للعودة (بدون st.rerun فوري)
                            st.success(f"✨ {message}")
                            if st.button("🔙 العودة إلى صفحة الدخول", key="goto_login_after_change"):
                                st.session_state.show_password_change = False
                                st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    elif not old_password or not new_password:
                        st.warning("⚠️ جميع الحقول مطلوبة.")
                    elif new_password != confirm_password:
                        st.error("❌ عدم تطابق في تأكيد رمز المرور الجديد.")
                    elif len(new_password) < 4:
                        st.error("⚠️ رمز المرور ضعيف (يجب ألا يقل عن 4 خانات).")
                    else:
                        st.error("❌ حالة غير معروفة.")
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
