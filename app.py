import streamlit as st
import requests
import re
import socket

# ---------- إعداد الصفحة ----------
st.set_page_config(
    page_title="رفيق التلاوة | Quran Companion",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- أنماط CSS مخصصة ----------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');
    
    * {
        font-family: 'Tajawal', sans-serif;
    }
    
    .main-title {
        text-align: center;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 25px;
        border-radius: 20px;
        color: white;
        margin-bottom: 30px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .ayah-text {
        font-size: 32px;
        line-height: 2.2;
        text-align: right;
        direction: rtl;
        color: #1a1a1a;
        margin: 20px 0;
        padding: 20px;
        background: #fafbfc;
        border-radius: 15px;
        border-right: 5px solid #2e7d32;
    }
</style>
""", unsafe_allow_html=True)

# ---------- دالة فحص الاتصال بالإنترنت ----------
def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

# ---------- قاعدة بيانات الأحكام التجويدية ----------
TAJWEED_EXAMPLES = {
    "الضالين": "مد لازم 6 حركات",
    "المستقيم": "مد عارض للسكون + قلقلة في الطاء",
    "الرحمن": "إظهار حلقي (نون ساكنة قبل هاء)",
    "أنعمت": "إظهار حلقي (نون ساكنة قبل عين)",
    "عليهم": "إظهار شفوي (ميم ساكنة)",
    "إياك": "مد منفصل 4-5 حركات",
}

# ---------- جلب بيانات السور ----------
BASE_URL = "https://api.alquran.cloud/v1"

@st.cache_data(ttl=3600)
def get_surahs():
    """جلب جميع السور من API"""
    try:
        response = requests.get(f"{BASE_URL}/surah", timeout=10)
        data = response.json()
        if data['code'] == 200:
            surahs = {}
            for surah in data['data']:
                # استخدام الاسم الإنجليزي كمعرف، والاسم العربي للعرض
                surahs[surah['englishName'] + " - " + surah['name']] = surah['number']
            return surahs
        else:
            return {"الفاتحة": 1, "البقرة": 2, "آل عمران": 3}
    except:
        return {"الفاتحة": 1, "البقرة": 2, "آل عمران": 3, "النساء": 4, "المائدة": 5}

SURAHS = get_surahs()

# ---------- القراء المتاحون (معرفات مؤكدة) ----------
RECITERS = {
    "مشاري العفاسي": "ar.afasy",
    "عبد الباسط عبد الصمد (مرتل)": "ar.abdulsamad",
    "ماهر المعيقلي": "ar.maher",
    "فارس عباد": "ar.abbad",
    "علي الحذيفي": "ar.hudhaify",
    "محمد أيوب": "ar.ayyoub",
    "عبد الرحمن السديس": "ar.sudais",
    "سعود الشريم": "ar.shuraim",
    "محمود خليل الحصري": "ar.husary",
    "أحمد العجمي": "ar.ajamy",
    "ياسر الدوسري": "ar.yasser",
}

# ---------- واجهة المستخدم ----------
st.markdown("""
<div class="main-title">
    <h1>📖 رفيق التلاوة والتغني</h1>
    <p>استمع للآيات وتابع النص الكريم مع الترجمة والتفسير</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    selected_surah_display = st.selectbox("📌 اختر السورة", list(SURAHS.keys()))
with col2:
    selected_reciter_name = st.selectbox("🎙️ اختر القارئ", list(RECITERS.keys()))

surah_number = SURAHS[selected_surah_display]
reciter_id = RECITERS[selected_reciter_name]

# ---------- جلب بيانات السورة (مع معالجة الأخطاء) ----------
@st.cache_data(ttl=3600)
def fetch_surah(surah_num, reciter):
    """جلب بيانات السورة من API مع التعامل مع الأخطاء"""
    try:
        # النص العربي
        arabic_res = requests.get(f"{BASE_URL}/surah/{surah_num}", timeout=10)
        arabic_data = arabic_res.json()['data'] if arabic_res.status_code == 200 else None
        
        # الترجمة الإنجليزية
        trans_res = requests.get(f"{BASE_URL}/surah/{surah_num}/en.asad", timeout=10)
        trans_data = trans_res.json()['data'] if trans_res.status_code == 200 else None
        
        # تفسير الميسر
        tafsir_res = requests.get(f"{BASE_URL}/surah/{surah_num}/ar.muyassar", timeout=10)
        tafsir_data = tafsir_res.json()['data'] if tafsir_res.status_code == 200 else None
        
        # الصوت - نجرب القارئ، وإذا فشل نستخدم قارئاً افتراضياً
        audio_data = None
        try:
            audio_res = requests.get(f"{BASE_URL}/surah/{surah_num}/{reciter}", timeout=10)
            if audio_res.status_code == 200:
                audio_data = audio_res.json()['data']
        except:
            pass
        
        # إذا فشل تحميل الصوت للقارئ المختار، نستخدم مشاري العفاسي كافتراضي
        if audio_data is None and reciter != "ar.afasy":
            try:
                audio_res = requests.get(f"{BASE_URL}/surah/{surah_num}/ar.afasy", timeout=10)
                if audio_res.status_code == 200:
                    audio_data = audio_res.json()['data']
                    st.warning("⚠️ القارئ المختار غير متوفر لهذه السورة. تم استخدام مشاري العفاسي بدلاً عنه.")
            except:
                pass
        
        return arabic_data, trans_data, tafsir_data, audio_data
        
    except Exception as e:
        st.error(f"❌ فشل الاتصال بالإنترنت أو API: {e}")
        return None, None, None, None

# ---------- دوال مساعدة ----------
def clean_arabic_text(text):
    arabic_diacritics = re.compile(r'[َُِّْٰٓٔ]')
    text = re.sub(arabic_diacritics, '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def get_tajweed_hints(ayah_text):
    hints = []
    words = ayah_text.split()
    for word in words:
        clean_word = re.sub(r'[َُِّْٰٓٔ]', '', word)
        if clean_word in TAJWEED_EXAMPLES:
            hints.append(f"**{word}**: {TAJWEED_EXAMPLES[clean_word]}")
    return hints[:5]

# ---------- عرض الآيات ----------
internet_available = check_internet()

if not internet_available:
    st.error("📴 أنت غير متصل بالإنترنت. الرجاء الاتصال بالإنترنت لتحميل الآيات.")
else:
    with st.spinner("🔄 جاري تحميل الآيات..."):
        arabic_surah, trans_surah, tafsir_surah, audio_surah = fetch_surah(surah_number, reciter_id)
    
    if arabic_surah is None:
        st.error("❌ تعذر تحميل بيانات السورة. حاول مرة أخرى لاحقاً.")
    else:
        ayahs_arabic = arabic_surah['ayahs']
        total_ayahs = len(ayahs_arabic)
        
        ayah_range = st.slider("🎯 اختر نطاق الآيات", 1, total_ayahs, (1, min(5, total_ayahs)))
        start, end = ayah_range
        
        st.markdown("---")
        
        for i in range(start - 1, end):
            ayah_num = i + 1
            arabic_text = ayahs_arabic[i]['text']
            
            # الترجمة والتفسير (قد لا يكونان متوفرين)
            translation_text = trans_surah['ayahs'][i]['text'] if trans_surah else "الترجمة غير متوفرة"
            tafsir_text = tafsir_surah['ayahs'][i]['text'] if tafsir_surah else "التفسير غير متوفر"
            
            # الصوت
            audio_url = audio_surah['ayahs'][i]['audio'] if audio_surah else None
            
            with st.container():
                st.markdown(f"### الآية {ayah_num}")
                
                # النص العربي
                st.markdown(f"<div class='ayah-text'>{arabic_text}</div>", unsafe_allow_html=True)
                
                # الترجمة
                st.markdown(f"**الترجمة:** {translation_text}")
                
                # تبويب التفسير والتجويد
                tab1, tab2 = st.tabs(["📖 تفسير الميسر", "🎙️ دليل تجويدي"])
                with tab1:
                    st.markdown(f"<div style='text-align:right; direction:rtl;'>{tafsir_text}</div>", unsafe_allow_html=True)
                with tab2:
                    hints = get_tajweed_hints(arabic_text)
                    if hints:
                        for hint in hints:
                            st.markdown(f"- {hint}")
                    else:
                        st.info("لا توجد تلميحات خاصة بهذه الآية.")
                
                # مشغل الصوت
                if audio_url:
                    st.audio(audio_url, format="audio/mp3")
                else:
                    st.warning("⚠️ الصوت غير متوفر لهذه الآية")
                
                st.markdown("---")

st.markdown("---")
st.caption("🌿 صُنع بحب القرآن | البيانات من Quran Cloud API")
