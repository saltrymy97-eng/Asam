import streamlit as st
import requests
import re
import socket
import json
from collections import Counter
from streamlit_mic_recorder import mic_recorder
from groq import Groq

# ---------- إعداد الصفحة ----------
st.set_page_config(
    page_title="رفيق التلاوة | Quran Companion",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- أنماط CSS مخصصة لواجهة جميلة ----------
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
    
    .ayah-box {
        background: linear-gradient(145deg, #f8f9fa 0%, #ffffff 100%);
        border-radius: 25px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 15px 40px rgba(0,0,0,0.08);
        border: 1px solid rgba(46, 125, 50, 0.1);
        transition: transform 0.2s, box-shadow 0.2s;
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
    
    .ayah-number {
        font-size: 1.2rem;
        color: #2e7d32;
        font-weight: bold;
    }
    
    .stButton button {
        background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%);
        color: white;
        border: none;
        padding: 10px 25px;
        border-radius: 10px;
        font-weight: bold;
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

# ---------- إعداد Groq API ----------
if 'groq_api_key' not in st.session_state:
    st.session_state.groq_api_key = ""

# ---------- قاعدة بيانات مصغرة للأحكام التجويدية ----------
TAJWEED_RULES = {
    "مد لازم": "يمد 6 حركات. مثال: 'الضالين'، 'الصاخة'",
    "مد متصل": "يمد 4-5 حركات إذا جاءت همزة بعد حرف المد في نفس الكلمة. مثال: 'جاء'، 'سوء'",
    "مد منفصل": "يمد 4-5 حركات إذا جاءت همزة بعد حرف المد في كلمة منفصلة. مثال: 'إنا أعطيناك'",
    "مد طبيعي": "يمد حركتين. مثال: 'قال'، 'قيل'، 'يقول'",
    "مد عارض للسكون": "يمد 2-4-6 حركات عند الوقف. مثال: 'العالمين'",
    "إظهار حلقي": "تظهر النون الساكنة أو التنوين عند حروف الحلق (ء هـ ع ح غ خ). مثال: 'من آمن'",
    "إدغام بغنة": "تدغم النون أو التنوين مع حروف (ي ن م و) مع غنة. مثال: 'من يقول'",
    "إقلاب": "تقلب النون أو التنوين ميماً مع غنة عند الباء. مثال: 'من بعد'",
    "قلقلة": "اضطراب الصوت عند حروف (قطب جد). مثال: 'أحد'، 'لهب'",
}

TAJWEED_EXAMPLES = {
    "الضالين": "مد لازم 6 حركات",
    "المستقيم": "مد عارض للسكون + قلقلة في الطاء",
    "الرحمن": "إظهار حلقي (نون ساكنة قبل هاء)",
    "أنعمت": "إظهار حلقي (نون ساكنة قبل عين)",
    "عليهم": "إظهار شفوي (ميم ساكنة)",
    "إياك": "مد منفصل 4-5 حركات",
}

# ---------- الشريط الجانبي للإعدادات ----------
with st.sidebar:
    st.header("⚙️ الإعدادات")
    internet_available = check_internet()
    if internet_available:
        st.success("🌐 الإنترنت متصل")
    else:
        st.warning("📴 أنت غير متصل بالإنترنت")
    
    with st.expander("📚 قاموس الأحكام التجويدية"):
        for rule, explanation in TAJWEED_RULES.items():
            st.markdown(f"**{rule}**: {explanation}")
    
    st.markdown("---")
    if internet_available:
        api_key = st.text_input("🔑 أدخل مفتاح Groq API", type="password")
        if api_key:
            st.session_state.groq_api_key = api_key
            st.success("✅ تم حفظ المفتاح!")

# ---------- جلب بيانات السور ----------
BASE_URL = "https://api.alquran.cloud/v1"

@st.cache_data(ttl=3600)
def get_surahs():
    try:
        response = requests.get(f"{BASE_URL}/surah", timeout=5)
        return {surah['name']: surah['number'] for surah in response.json()['data']}
    except:
        return {"الفاتحة": 1, "البقرة": 2, "آل عمران": 3, "النساء": 4, "المائدة": 5}

SURAHS = get_surahs()

# تم إضافة القارئين المطلوبين (مع استخدام معرفات متوقعة)
RECITERS = {
    "مشاري العفاسي": "ar.afasy",
    "عبد الباسط عبد الصمد": "ar.abdulsamad",
    "ماهر المعيقلي": "ar.maher",
    "سعد الغامدي": "ar.ghamdi",
    "فارس عباد": "ar.abbad",
    "محمود خليل الحصري": "ar.husary",
    "عبد الرحمن السديس": "ar.sudais",
    "يوسف الصقير": "ar.yousufalsuqair",  # معرف تقديري (قد يحتاج للتأكيد)
    "محمد اللحيدان": "ar.muhammadalluhaidan",  # معرف تقديري
}

# ---------- واجهة المستخدم ----------
st.markdown("""
<div class="main-title">
    <h1>📖 رفيق التلاوة والتغني</h1>
    <p>استمع للآيات وتابع النص الكريم مع الترجمة والتفسير واختبر حفظك</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    selected_surah_name = st.selectbox("📌 اختر السورة", list(SURAHS.keys()))
with col2:
    selected_reciter_name = st.selectbox("🎙️ اختر القارئ", list(RECITERS.keys()))

surah_number = SURAHS[selected_surah_name]
reciter_id = RECITERS[selected_reciter_name]

internet_available = check_internet()
teacher_mode = st.toggle("🧑‍🏫 تفعيل وضع المعلم (اختبر حفظك)")

# ---------- جلب بيانات السورة ----------
@st.cache_data(ttl=3600)
def fetch_surah(surah_num, reciter):
    try:
        arabic_data = requests.get(f"{BASE_URL}/surah/{surah_num}", timeout=10).json()
        translation_data = requests.get(f"{BASE_URL}/surah/{surah_num}/en.asad", timeout=10).json()
        tafsir_data = requests.get(f"{BASE_URL}/surah/{surah_num}/ar.muyassar", timeout=10).json()
        audio_data = requests.get(f"{BASE_URL}/surah/{surah_num}/{reciter}", timeout=10).json()
        return arabic_data['data'], translation_data['data'], tafsir_data['data'], audio_data['data']
    except Exception as e:
        st.error(f"❌ فشل جلب البيانات: {e}")
        st.stop()

# ---------- دوال مساعدة ----------
def clean_arabic_text(text):
    arabic_diacritics = re.compile(r'[َُِّْٰٓٔ]')
    text = re.sub(arabic_diacritics, '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def compare_texts(original, spoken):
    orig_clean = clean_arabic_text(original)
    spoken_clean = clean_arabic_text(spoken)
    if orig_clean == spoken_clean:
        return True, "✅ **أحسنت! تلاوتك صحيحة تماماً.**"
    orig_words = orig_clean.split()
    spoken_words = spoken_clean.split()
    omissions = [word for word in orig_words if word not in spoken_words]
    additions = [word for word in spoken_words if word not in orig_words]
    return False, (additions, omissions)

def transcribe_audio(audio_bytes):
    if not check_internet() or not st.session_state.groq_api_key:
        return None, "⚠️ لا يوجد اتصال بالإنترنت أو مفتاح API غير موجود"
    try:
        client = Groq(api_key=st.session_state.groq_api_key)
        with open("temp_audio.webm", "wb") as f:
            f.write(audio_bytes)
        with open("temp_audio.webm", "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=("temp_audio.webm", f),
                language="ar",
                response_format="text"
            )
        return str(transcription), None
    except Exception as e:
        return None, f"❌ خطأ: {str(e)}"

def get_tajweed_hints(ayah_text):
    hints = []
    words = ayah_text.split()
    for word in words:
        clean_word = re.sub(r'[َُِّْٰٓٔ]', '', word)
        if clean_word in TAJWEED_EXAMPLES:
            hints.append(f"**{word}**: {TAJWEED_EXAMPLES[clean_word]}")
    return hints[:5]

# ---------- عرض الآيات ----------
try:
    with st.spinner("🔄 جاري تحميل الآيات..."):
        arabic_surah, translation_surah, tafsir_surah, audio_surah = fetch_surah(surah_number, reciter_id)

    ayahs_arabic = arabic_surah['ayahs']
    total_ayahs = len(ayahs_arabic)
    ayah_range = st.slider("🎯 اختر نطاق الآيات", 1, total_ayahs, (1, min(5, total_ayahs)))
    start, end = ayah_range

    for i in range(start - 1, end):
        ayah_num = i + 1
        arabic_text = ayahs_arabic[i]['text']
        translation_text = translation_surah['ayahs'][i]['text']
        tafsir_text = tafsir_surah['ayahs'][i]['text']
        audio_url = audio_surah['ayahs'][i]['audio']

        with st.container():
            st.markdown(f"### الآية {ayah_num}")
            
            if teacher_mode:
                with st.expander("📜 اضغط هنا لكشف الآية"):
                    st.markdown(f"<div class='ayah-text'>{arabic_text}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='ayah-text'>{arabic_text}</div>", unsafe_allow_html=True)
            
            st.markdown(f"**الترجمة:** {translation_text}")
            
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
            
            st.audio(audio_url, format="audio/mp3")
            
            if teacher_mode and internet_available and st.session_state.groq_api_key:
                st.markdown("---")
                st.markdown("### 🎙️ اختبر تلاوتك")
                audio_data = mic_recorder(start_prompt="🎤 ابدأ التسجيل", stop_prompt="⏹️ توقف", key=f"mic_{ayah_num}", format="webm")
                if audio_data and 'bytes' in audio_data:
                    with st.spinner("🧠 الذكاء الاصطناعي يحلل تلاوتك..."):
                        transcribed_text, error = transcribe_audio(audio_data['bytes'])
                        if error:
                            st.error(error)
                        elif transcribed_text:
                            st.markdown("**📝 النص الذي تعرف عليه الذكاء الاصطناعي:**")
                            st.info(transcribed_text)
                            is_correct, result = compare_texts(arabic_text, transcribed_text)
                            if is_correct:
                                st.success(result)
                                st.balloons()
                            else:
                                additions, omissions = result
                                st.warning("⚠️ **وجدت بعض الاختلافات:**")
                                if omissions:
                                    st.markdown(f"**🔴 كلمات نسيتها:** <span style='color:red'>{' '.join(omissions)}</span>", unsafe_allow_html=True)
                                if additions:
                                    st.markdown(f"**🟡 كلمات زائدة قلتها:** <span style='color:orange'>{' '.join(additions)}</span>", unsafe_allow_html=True)
                                st.markdown("**📖 النص الصحيح:**")
                                st.markdown(f"<div style='font-size:20px; text-align:right; direction:rtl;'>{arabic_text}</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"❌ حدث خطأ: {e}")

st.markdown("---")
st.caption("🌿 صُنع بحب القرآن | البيانات من Quran Cloud API | التصحيح عبر Groq Whisper")
