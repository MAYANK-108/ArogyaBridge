"""
ArogyaBridge - Bridge to Healthcare
SIH 2026 | PS ID: SIH26133
Full production-grade prototype: multi-role auth, AI triage, smart SOS dispatch,
notifications, diagnostics, walk-in queue, quality scorecards, area-wise analytics.
Run: pip install -r requirements.txt && streamlit run app.py
"""
import os, sqlite3, uuid, random, hashlib, secrets, re
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "sevasetu.db")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"

PRIORITY_COLORS = {"RED": "#e53935", "YELLOW": "#f9a825", "GREEN": "#2e7d32"}
PRIORITY_ORDER  = {"RED": 0, "YELLOW": 1, "GREEN": 2}
FACILITY_TYPES  = ["Sub-Centre", "Primary Health Centre (PHC)", "Rural / District Hospital"]
SPECIALITIES    = ["General Medicine","Cardiology","Pediatrics","Obstetrics & Gynaecology",
                   "Pulmonology","Neurology","Orthopedics","Gastroenterology"]
COMMON_TESTS    = ["CBC (Complete Blood Count)","Blood Sugar (Fasting)","Blood Sugar (PP)",
                   "Malaria RDT","Dengue NS1","Urine Routine","X-Ray Chest",
                   "Hb (Hemoglobin)","Widal (Typhoid)","COVID-19 RAT"]

st.set_page_config(page_title="ArogyaBridge", page_icon="🩺",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;font-size:16px}
.stButton>button{padding:.6rem 1.5rem;font-size:1rem;font-weight:600;border-radius:12px;min-height:3rem;transition:all .2s}
.stTextInput input,.stNumberInput input,.stTextArea textarea{font-size:1rem;padding:.6rem .8rem;border-radius:10px}
.stSelectbox>div>div{min-height:3rem;font-size:1rem;border-radius:10px}
.stTabs [data-baseweb="tab"]{font-size:.95rem;font-weight:600;padding:.5rem 1rem}
.stTabs [data-baseweb="tab-list"]{gap:4px}
.stRadio>div{gap:.4rem}.stRadio label{font-size:1rem}
[data-testid="stMetricValue"]{font-size:1.7rem;font-weight:700}
[data-testid="stMetricLabel"]{font-size:.85rem;font-weight:500;opacity:.8}
[data-testid="stMetricDelta"]{font-size:.8rem}
div[data-testid="stExpander"] details summary p{font-weight:600}
</style>""", unsafe_allow_html=True)

# ── I18N ─────────────────────────────────────────────────────
T = {
"en":{"app_title":"ArogyaBridge — Bridge to Healthcare","role":"Select your role",
  "patient_portal":"Patient Portal","asha":"ASHA / ANM Worker","doctor":"Doctor Dashboard",
  "facility":"Facility / Hospital","admin":"District Admin","medicine":"Medicine Availability",
  "login":"Login","register_tab":"Register","login_btn":"Login","name":"Full Name","age":"Age",
  "gender":"Gender","village":"Village / Ward","phone":"Phone Number","language":"Preferred Language",
  "aadhaar_id":"Aadhaar ID","password":"Password","confirm_password":"Confirm Password",
  "register_btn":"Register","invalid_login":"Invalid login details.",
  "welcome_back":"Welcome back","logout_btn":"Logout","symptoms":"Describe symptoms",
  "run_triage":"Run AI Triage","priority":"Priority","refer_btn":"Refer to Facility",
  "select_facility":"Refer to which facility?","queue":"Live Patient Queue",
  "no_referrals":"No referrals in queue.","prescription":"Prescription",
  "save_prescription":"Save & Complete Referral","teleconsult":"Start Teleconsultation",
  "book_appointment":"Book Appointment","sos":"Emergency SOS","my_health_record":"My Health Record",
  "my_triage_history":"Symptom History","my_referrals":"Referrals & Prescriptions",
  "no_records_yet":"No records yet.","create_login":"Create your login",
  "phone_login_hint":"Log in with your Aadhaar ID.","register_patient":"Register New Patient",
  "my_patients":"My Patients","all_patients":"All Patients","update_details":"Update My Details"},
"hi":{"app_title":"ArogyaBridge — स्वास्थ्य सेवा का पुल","role":"अपनी भूमिका चुनें",
  "patient_portal":"रोगी पोर्टल","asha":"आशा / एएनएम कार्यकर्ता","doctor":"डॉक्टर डैशबोर्ड",
  "facility":"सुविधा / अस्पताल","admin":"जिला प्रशासन","medicine":"दवा उपलब्धता",
  "login":"लॉगिन","register_tab":"पंजीकरण","login_btn":"लॉगिन करें","name":"पूरा नाम","age":"आयु",
  "gender":"लिंग","village":"गाँव / वार्ड","phone":"फ़ोन नंबर","language":"पसंदीदा भाषा",
  "aadhaar_id":"आधार आईडी","password":"पासवर्ड","confirm_password":"पासवर्ड की पुष्टि",
  "register_btn":"पंजीकरण करें","invalid_login":"गलत लॉगिन विवरण।",
  "welcome_back":"वापसी पर स्वागत है","logout_btn":"लॉगआउट","symptoms":"लक्षण बताएं",
  "run_triage":"AI ट्राइएज चलाएं","priority":"प्राथमिकता","refer_btn":"रेफर करें",
  "select_facility":"कहाँ रेफर करें?","queue":"लाइव रोगी कतार","no_referrals":"कोई रेफरल नहीं।",
  "prescription":"नुस्खा","save_prescription":"नुस्खा सहेजें","teleconsult":"टेलीकंसल्टेशन",
  "book_appointment":"अपॉइंटमेंट बुक करें","sos":"आपातकालीन SOS",
  "my_health_record":"मेरा स्वास्थ्य रिकॉर्ड","my_triage_history":"मेरा लक्षण इतिहास",
  "my_referrals":"मेरे रेफरल","no_records_yet":"अभी कोई रिकॉर्ड नहीं।",
  "create_login":"अपना लॉगिन बनाएं","phone_login_hint":"आधार आईडी से लॉगिन करें।",
  "register_patient":"नया रोगी पंजीकृत करें","my_patients":"मेरे मरीज़",
  "all_patients":"सभी मरीज़","update_details":"विवरण अपडेट करें"},
"mr":{"app_title":"ArogyaBridge — आरोग्यसेवेचा पूल","role":"तुमची भूमिका निवडा",
  "patient_portal":"रुग्ण पोर्टल","asha":"आशा / एएनएम कार्यकर्ता","doctor":"डॉक्टर डॅशबोर्ड",
  "facility":"सुविधा / रुग्णालय","admin":"जिल्हा प्रशासन","medicine":"औषध उपलब्धता",
  "login":"लॉगिन","register_tab":"नोंदणी","login_btn":"लॉगिन करा","name":"पूर्ण नाव","age":"वय",
  "gender":"लिंग","village":"गाव / वॉर्ड","phone":"फोन नंबर","language":"पसंतीची भाषा",
  "aadhaar_id":"आधार आयडी","password":"पासवर्ड","confirm_password":"पासवर्डची पुष्टी",
  "register_btn":"नोंदणी करा","invalid_login":"चुकीचे लॉगिन तपशील.",
  "welcome_back":"परत स्वागत","logout_btn":"लॉगआउट","symptoms":"लक्षणे सांगा",
  "run_triage":"AI ट्रायएज","priority":"प्राधान्य","refer_btn":"संदर्भित करा",
  "select_facility":"कुठे संदर्भित करायचे?","queue":"रुग्ण रांग","no_referrals":"रेफरल नाही.",
  "prescription":"प्रिस्क्रिप्शन","save_prescription":"जतन करा","teleconsult":"टेलिकन्सल्टेशन",
  "book_appointment":"अपॉइंटमेंट बुक करा","sos":"आणीबाणी SOS",
  "my_health_record":"माझी आरोग्य नोंद","my_triage_history":"माझा लक्षण इतिहास",
  "my_referrals":"माझे संदर्भ","no_records_yet":"नोंद नाही.","create_login":"लॉगिन तयार करा",
  "phone_login_hint":"तुमच्या आधार आयडीने लॉगिन करा.","register_patient":"नवीन रुग्ण नोंदणी",
  "my_patients":"माझे रुग्ण","all_patients":"सर्व रुग्ण","update_details":"तपशील अपडेट करा"},
"ta":{"app_title":"ArogyaBridge — சுகாதார சேவைக்கான பாலம்","role":"பாத்திரம் தேர்வு",
  "patient_portal":"நோயாளர் போர்ட்டல்","asha":"ஆஷா / ஏஎன்எம்","doctor":"மருத்துவர் டாஷ்போர்டு",
  "facility":"மையம் / மருத்துவமனை","admin":"மாவட்ட நிர்வாக டாஷ்போர்டு","medicine":"மருந்து கிடைக்கும் தன்மை",
  "login":"உள்நுழைய","register_tab":"பதிவு","login_btn":"உள்நுழையவும்","name":"பெயர்","age":"வயது",
  "gender":"பாலினம்","village":"கிராமம்","phone":"தொலைபேசி","language":"மொழி",
  "aadhaar_id":"ஆதார் ஐடி","password":"கடவுச்சொல்","confirm_password":"உறுதிப்படுத்தவும்",
  "register_btn":"பதிவு செய்யவும்","invalid_login":"தவறான உள்நுழைவு விவரங்கள்.",
  "welcome_back":"மீண்டும் வரவேற்கிறோம்","logout_btn":"வெளியேறு","symptoms":"அறிகுறிகள்",
  "run_triage":"AI முன்னுரிமை","priority":"முன்னுரிமை","refer_btn":"பரிந்துரைக்கவும்",
  "select_facility":"எந்த மையம்?","queue":"நோயாளர் வரிசை","no_referrals":"பரிந்துரைகள் இல்லை.",
  "prescription":"மருந்துச் சீட்டு","save_prescription":"சேமிக்கவும்","teleconsult":"தொலை ஆலோசனை",
  "book_appointment":"சந்திப்பு","sos":"அவசர SOS","my_health_record":"சுகாதார பதிவு",
  "my_triage_history":"அறிகுறி வரலாறு","my_referrals":"பரிந்துரைகள்",
  "no_records_yet":"பதிவுகள் இல்லை.","create_login":"லாக்இன் உருவாக்கவும்",
  "phone_login_hint":"உங்கள் ஆதார் ஐடியுடன் உள்நுழையவும்.","register_patient":"நோயாளர் பதிவு",
  "my_patients":"என் நோயாளர்கள்","all_patients":"அனைத்து நோயாளர்கள்","update_details":"விவரங்களை புதுப்பிக்கவும்"},
"te":{"app_title":"ArogyaBridge — ఆరోగ్య సేవకు వంతెన","role":"పాత్ర ఎంచుకోండి",
  "patient_portal":"రోగి పోర్టల్","asha":"ఆశా / ఏఎన్ఎం","doctor":"డాక్టర్ డాష్‌బోర్డ్",
  "facility":"సదుపాయం / ఆసుపత్రి","admin":"జిల్లా అడ్మిన్ డాష్‌బోర్డ్","medicine":"మందుల లభ్యత",
  "login":"లాగిన్","register_tab":"నమోదు","login_btn":"లాగిన్ చేయండి","name":"పూర్తి పేరు","age":"వయస్సు",
  "gender":"లింగం","village":"గ్రామం","phone":"ఫోన్","language":"భాష",
  "aadhaar_id":"ఆధార్ ఐడి","password":"పాస్‌వర్డ్","confirm_password":"నిర్ధారించండి",
  "register_btn":"నమోదు చేయండి","invalid_login":"తప్పు లాగిన్ వివరాలు.",
  "welcome_back":"తిరిగి స్వాగతం","logout_btn":"లాగ్ అవుట్","symptoms":"లక్షణాలు",
  "run_triage":"AI ట్రయాజ్","priority":"ప్రాధాన్యత","refer_btn":"రిఫర్ చేయండి",
  "select_facility":"ఏ సదుపాయం?","queue":"రోగి క్యూ","no_referrals":"రిఫరల్స్ లేవు.",
  "prescription":"ప్రిస్క్రిప్షన్","save_prescription":"సేవ్ చేయండి","teleconsult":"టెలికన్సల్టేషన్",
  "book_appointment":"అపాయింట్‌మెంట్","sos":"అత్యవసర SOS","my_health_record":"ఆరోగ్య రికార్డు",
  "my_triage_history":"లక్షణాల చరిత్ర","my_referrals":"రిఫరల్స్","no_records_yet":"రికార్డులు లేవు.",
  "create_login":"లాగిన్ సృష్టించండి","phone_login_hint":"మీ ఆధార్ ఐడితో లాగిన్ అవ్వండి.",
  "register_patient":"రోగి నమోదు","my_patients":"నా రోగులు","all_patients":"అందరు రోగులు",
  "update_details":"వివరాలు నవీకరించండి"},
"bn":{"app_title":"ArogyaBridge — স্বাস্থ্যসেবার সেতু","role":"ভূমিকা নির্বাচন",
  "patient_portal":"রোগী পোর্টাল","asha":"আশা / এএনএম","doctor":"ডাক্তার ড্যাশবোর্ড",
  "facility":"সুবিধা / হাসপাতাল","admin":"জেলা প্রশাসন","medicine":"ওষুধ প্রাপ্যতা",
  "login":"লগইন","register_tab":"নিবন্ধন","login_btn":"লগইন করুন","name":"পুরো নাম","age":"বয়স",
  "gender":"লিঙ্গ","village":"গ্রাম","phone":"ফোন","language":"ভাষা",
  "aadhaar_id":"আধার আইডি","password":"পাসওয়ার্ড","confirm_password":"নিশ্চিত করুন",
  "register_btn":"নিবন্ধন করুন","invalid_login":"ভুল লগইন বিবরণ।",
  "welcome_back":"আবার স্বাগতম","logout_btn":"লগআউট","symptoms":"লক্ষণ",
  "run_triage":"AI ট্রায়াজ","priority":"অগ্রাধিকার","refer_btn":"রেফার করুন",
  "select_facility":"কোন সুবিধা?","queue":"রোগীর সারি","no_referrals":"রেফারেল নেই।",
  "prescription":"প্রেসক্রিপশন","save_prescription":"সংরক্ষণ করুন","teleconsult":"টেলিকনসালটেশন",
  "book_appointment":"অ্যাপয়েন্টমেন্ট","sos":"জরুরি SOS","my_health_record":"স্বাস্থ্য রেকর্ড",
  "my_triage_history":"লক্ষণ ইতিহাস","my_referrals":"রেফারেল","no_records_yet":"রেকর্ড নেই।",
  "create_login":"লগইন তৈরি করুন","phone_login_hint":"আপনার আধার আইডি দিয়ে লগইন করুন।",
  "register_patient":"রোগী নিবন্ধন","my_patients":"আমার রোগী","all_patients":"সব রোগী",
  "update_details":"বিবরণ আপডেট করুন"},
}
def tr(k):
    lg=st.session_state.get("ui_lang","en")
    return T.get(lg,T["en"]).get(k,T["en"].get(k,k))

# ── DATABASE ─────────────────────────────────────────────────
def get_conn():
    c=sqlite3.connect(DB_PATH,check_same_thread=False)
    c.row_factory=sqlite3.Row; return c

def init_db():
    conn=get_conn(); c=conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS facilities(
      id TEXT PRIMARY KEY,name TEXT UNIQUE,type TEXT,village TEXT,
      phone TEXT UNIQUE,password_hash TEXT,salt TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS patients(
      abha_id TEXT PRIMARY KEY,name TEXT,age INTEGER,gender TEXT,
      village TEXT,phone TEXT,aadhaar_id TEXT UNIQUE,language TEXT,created_at TEXT,
      password_hash TEXT,salt TEXT,
      registered_by_type TEXT,registered_by_id TEXT,registered_by_name TEXT);
    CREATE TABLE IF NOT EXISTS asha_workers(
      id TEXT PRIMARY KEY,name TEXT,phone TEXT,facility_id TEXT,facility TEXT,
      password_hash TEXT,salt TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS doctors(
      id TEXT PRIMARY KEY,name TEXT,phone TEXT,facility_id TEXT,facility TEXT,
      speciality TEXT,password_hash TEXT,salt TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS triage(
      id TEXT PRIMARY KEY,abha_id TEXT,symptoms_text TEXT,
      priority TEXT,rationale TEXT,created_by TEXT,created_at TEXT,
      department TEXT,follow_up_due_date TEXT,follow_up_done INTEGER DEFAULT 0,
      temperature TEXT,spo2 TEXT,pulse TEXT,triggered_by TEXT DEFAULT 'asha');
    CREATE TABLE IF NOT EXISTS referrals(
      id TEXT PRIMARY KEY,abha_id TEXT,triage_id TEXT,facility TEXT,
      status TEXT,prescription TEXT,doctor_notes TEXT,
      created_at TEXT,completed_at TEXT,doctor_id TEXT);
    CREATE TABLE IF NOT EXISTS notifications(
      id TEXT PRIMARY KEY,recipient_role TEXT,recipient_id TEXT,
      message TEXT,priority TEXT,read INTEGER DEFAULT 0,created_at TEXT,
      triage_id TEXT,abha_id TEXT);
    CREATE TABLE IF NOT EXISTS sos_alerts(
      id TEXT PRIMARY KEY,abha_id TEXT,patient_name TEXT,village TEXT,
      triggered_at TEXT,status TEXT,resolved_at TEXT,resolved_by TEXT,
      accepted_by TEXT,notes TEXT,medical_summary TEXT,routing_log TEXT,
      cancelled INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS appointments(
      id TEXT PRIMARY KEY,abha_id TEXT,facility TEXT,
      appointment_date TEXT,time_slot TEXT,status TEXT,
      created_at TEXT,doctor_id TEXT,decline_reason TEXT);
    CREATE TABLE IF NOT EXISTS medicine_stock(
      id TEXT PRIMARY KEY,facility_id TEXT,facility TEXT,medicine_name TEXT,
      quantity INTEGER,unit TEXT,last_updated TEXT,updated_by TEXT);
    CREATE TABLE IF NOT EXISTS medicine_stock_log(
      id TEXT PRIMARY KEY,facility_id TEXT,facility TEXT,medicine_name TEXT,
      action TEXT,change_amount INTEGER,new_quantity INTEGER,
      changed_by TEXT,changed_at TEXT);
    CREATE TABLE IF NOT EXISTS diagnostics(
      id TEXT PRIMARY KEY,abha_id TEXT,referral_id TEXT,facility TEXT,
      test_name TEXT,status TEXT,ordered_by TEXT,ordered_at TEXT,
      result_notes TEXT,completed_at TEXT);
    CREATE TABLE IF NOT EXISTS queue_tokens(
      id TEXT PRIMARY KEY,abha_id TEXT,patient_name TEXT,facility TEXT,
      token_no INTEGER,token_date TEXT,status TEXT,
      created_at TEXT,called_at TEXT,done_at TEXT);
    """)
    conn.commit()
    def add_col(table,col,typ="TEXT"):
        cols=[r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols: c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    for col in ["temperature","spo2","pulse","triggered_by"]: add_col("triage",col)
    add_col("referrals","doctor_id")
    for col in ["doctor_id","decline_reason"]: add_col("appointments",col)
    for col in ["accepted_by","medical_summary","routing_log"]: add_col("sos_alerts",col)
    add_col("sos_alerts","cancelled","INTEGER DEFAULT 0")
    # Force-recreate notifications if old schema missing triage_id/abha_id columns
    notif_cols=[r[1] for r in c.execute("PRAGMA table_info(notifications)").fetchall()]
    if "triage_id" not in notif_cols or "abha_id" not in notif_cols:
        c.execute("DROP TABLE IF EXISTS notifications")
        c.execute("""CREATE TABLE notifications(
            id TEXT PRIMARY KEY,recipient_role TEXT,recipient_id TEXT,
            message TEXT,priority TEXT,read INTEGER DEFAULT 0,created_at TEXT,
            triage_id TEXT,abha_id TEXT)""")
    for col in ["triage_id","abha_id"]: add_col("notifications",col)
    for col in ["aadhaar_id","registered_by_type","registered_by_id","registered_by_name"]: add_col("patients",col)
    for col in ["facility_id"]: add_col("asha_workers",col)
    for col in ["facility_id"]: add_col("doctors",col)
    for col in ["facility_id","updated_by"]: add_col("medicine_stock",col)
    conn.commit(); conn.close()

# ── AUTH HELPERS ──────────────────────────────────────────────
def hash_pw(pw,salt=None):
    if not salt: salt=secrets.token_hex(16)
    h=hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),100_000).hex()
    return h,salt
def verify_pw(pw,salt,stored):
    if not salt or not stored: return False
    return hash_pw(pw,salt)[0]==stored
def gen_worker_id(prefix): return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
def gen_abha(): return "ABHA-"+str(uuid.uuid4())[:8].upper()
def gen_password():
    chars="0123456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(chars) for _ in range(8))
def mask_aadhaar(a):
    a=(a or "").strip()
    return ("XXXX-XXXX-"+a[-4:]) if len(a)>=4 else "—"
def valid_aadhaar(a): return bool(a) and a.isdigit() and len(a)==12
def valid_phone(p): return bool(re.fullmatch(r"[6-9]\d{9}",p.replace(" ","")))

# ── TRIAGE ENGINE ─────────────────────────────────────────────
RED_FLAGS=["chest pain","severe bleeding","unconscious","seizure","not breathing",
           "difficulty breathing","breathlessness","convulsion","high fever infant",
           "severe abdominal pain","stroke","paralysis","blue lips",
           "सीने में दर्द","बेहोश","दौरा","सांस लेने में तकलीफ","अत्यधिक रक्तस्राव","लकवा"]
YELLOW_FLAGS=["fever","vomiting","diarrhea","dehydration","moderate pain",
              "pregnancy bleeding","high blood pressure","persistent cough",
              "बुखार","उल्टी","दस्त","गर्भावस्था रक्तस्राव","उच्च रक्तचाप","लगातार खांसी"]
DEPT_KW=[
    ("Obstetrics & Gynaecology",["pregnan","labour","labor pain","pregnancy bleeding","missed period","गर्भ","प्रसव","गर्भावस्था"]),
    ("Pediatrics",["infant","newborn","child fever","baby not feeding","बच्चा","शिशु","नवजात"]),
    ("Cardiology",["chest pain","palpitations","heart","सीने में दर्द","दिल"]),
    ("Pulmonology",["breathless","difficulty breathing","asthma","persistent cough","सांस लेने में तकलीफ","खांसी","दमा"]),
    ("Orthopedics",["fracture","bone pain","joint pain","हड्डी","जोड़ों में दर्द"]),
    ("Neurology",["seizure","convulsion","stroke","paralysis","दौरा","लकवा"]),
    ("Gastroenterology",["vomiting","diarrhea","severe abdominal pain","उल्टी","दस्त","पेट में तेज़ दर्द"]),
]
def suggest_dept(text):
    t=text.lower()
    for dept,kws in DEPT_KW:
        for kw in kws:
            if kw in t: return dept
    return "General Medicine"
def rule_triage(text):
    t=text.lower()
    for f in RED_FLAGS:
        if f in t: return "RED",f"⚠️ Red-flag symptom: '{f}' — immediate escalation needed."
    for f in YELLOW_FLAGS:
        if f in t: return "YELLOW",f"Moderate risk: '{f}' — facility visit recommended."
    return "GREEN","No high-risk indicators found. Routine care advised."
def groq_triage(text):
    if not GROQ_API_KEY: return None
    try:
        from groq import Groq
        client=Groq(api_key=GROQ_API_KEY)
        prompt=(f"You are a clinical triage assistant for rural India. "
                f"Classify the symptoms as RED (emergency), YELLOW (needs visit soon), or GREEN (routine). "
                f"Symptoms may be in Hindi or English. Reply ONLY as: PRIORITY|one-sentence rationale.\n"
                f"Symptoms: {text}")
        resp=client.chat.completions.create(model=GROQ_MODEL,
             messages=[{"role":"user","content":prompt}],max_tokens=120,temperature=0.2)
        out=resp.choices[0].message.content.strip()
        if "|" in out:
            p,r=out.split("|",1); p=p.strip().upper()
            if p in PRIORITY_ORDER: return p,r.strip()
    except Exception: return None
def run_triage(text):
    res=groq_triage(text); priority,rationale=res if res else rule_triage(text)
    dept=suggest_dept(text); fud=None
    if priority=="RED": fud=(datetime.now()+timedelta(days=2)).strftime("%Y-%m-%d")
    elif priority=="YELLOW": fud=(datetime.now()+timedelta(days=7)).strftime("%Y-%m-%d")
    return priority,rationale,dept,fud

# ── NOTIFICATION HELPERS ──────────────────────────────────────
def _notif(conn,role,uid,msg,priority,tid=None,abha=None):
    conn.execute("INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) VALUES(?,?,?,?,?,0,?,?,?)",
                 (str(uuid.uuid4()),role,uid,msg,priority,datetime.now().isoformat(),tid,abha))
def notify_all_doctors(msg,priority,tid=None,abha=None):
    conn=get_conn()
    for d in conn.execute("SELECT id FROM doctors").fetchall(): _notif(conn,"doctor",d["id"],msg,priority,tid,abha)
    conn.commit(); conn.close()
def notify_all_asha(msg,priority,tid=None,abha=None):
    conn=get_conn()
    for a in conn.execute("SELECT id FROM asha_workers").fetchall(): _notif(conn,"asha",a["id"],msg,priority,tid,abha)
    conn.commit(); conn.close()
def get_unread(role,uid):
    conn=get_conn(); rows=conn.execute("SELECT * FROM notifications WHERE recipient_role=? AND recipient_id=? AND read=0 ORDER BY created_at DESC",(role,uid)).fetchall(); conn.close(); return rows
def mark_read(role,uid):
    conn=get_conn(); conn.execute("UPDATE notifications SET read=1 WHERE recipient_role=? AND recipient_id=?",(role,uid)); conn.commit(); conn.close()

# ── UTILS ─────────────────────────────────────────────────────
def priority_badge(p):
    c=PRIORITY_COLORS.get(p,"#999")
    emoji={"RED":"🔴","YELLOW":"🟡","GREEN":"🟢"}.get(p,"")
    return f"<span style='background:{c};color:white;padding:4px 14px;border-radius:20px;font-weight:700;font-size:.82em;letter-spacing:.5px'>{emoji} {p}</span>"
def qdf(sql,params=()):
    conn=get_conn(); d=pd.read_sql_query(sql,conn,params=params); conn.close(); return d
def cdf(df):
    if df is None or df.empty: return df
    return df.fillna("—")
def get_facility_names():
    d=qdf("SELECT name FROM facilities ORDER BY name"); return d["name"].tolist() if not d.empty else []
def get_village_names():
    d=qdf("SELECT DISTINCT village FROM patients WHERE village IS NOT NULL AND village!='' ORDER BY village"); return d["village"].tolist() if not d.empty else []
def next_token_no(facility,date_str):
    r=qdf("SELECT COALESCE(MAX(token_no),0) as m FROM queue_tokens WHERE facility=? AND token_date=?",(facility,date_str)); return int(r["m"][0])+1
def seed_stock(fid,fname):
    meds=[("Paracetamol 500mg","tablets",40),("ORS Sachets","sachets",20),
          ("Iron Folic Acid","tablets",100),("Amoxicillin 250mg","capsules",30),
          ("Antenatal Vitamin D","tablets",50),("Metformin 500mg","tablets",60)]
    now=datetime.now().isoformat(); conn=get_conn()
    for med,unit,qty in meds:
        conn.execute("INSERT OR IGNORE INTO medicine_stock(id,facility_id,facility,medicine_name,quantity,unit,last_updated,updated_by) VALUES(?,?,?,?,?,?,?,?)",
                     (str(uuid.uuid4()),fid,fname,med,qty,unit,now,"System (initial stock)"))
    conn.commit(); conn.close()

HEALTH_TIPS={
"en":{"Fever & Common Illness":["Drink fluids and rest — most viral fevers resolve in 2-3 days.",
      "See a doctor if fever exceeds 103°F, lasts 3+ days, or comes with breathlessness or rash.",
      "Never give aspirin to children — consult your ASHA worker first."],
      "Maternal & Child Care":["Register every pregnancy early and attend all antenatal check-ups.",
      "Exclusive breastfeeding for 6 months protects against most infant infections.",
      "Keep your child's immunization card updated — ask your ASHA worker for the schedule."],
      "Hygiene & Prevention":["Wash hands with soap before eating and after using the toilet.",
      "Use ORS immediately for diarrhea — it prevents dangerous dehydration in children.",
      "Keep drinking water covered; boil it if the source is uncertain."],
      "Know Your Services":["Every patient gets a free ABHA-linked ID — no charge beyond Aadhaar.",
      "All referrals through ArogyaBridge are tracked end-to-end — your case is never lost.",
      "Use Emergency SOS anytime — it instantly alerts nearby ASHA workers and doctors."]},
"hi":{"बुखार और सामान्य बीमारी":["खूब पानी पिएं — अधिकतर वायरल बुखार 2-3 दिनों में ठीक हो जाता है।",
      "103°F से ऊपर या 3 दिन से ज़्यादा बुखार पर डॉक्टर को दिखाएं।",
      "बच्चों को एस्पिरिन न दें — पहले आशा कार्यकर्ता से पूछें।"],
      "माँ और बच्चे की देखभाल":["गर्भावस्था जल्दी पंजीकृत करें और सभी जांच पूरी करें।",
      "पहले 6 महीने केवल स्तनपान कराएं।","बच्चे का टीकाकरण कार्ड अपडेट रखें।"],
      "स्वच्छता और रोकथाम":["खाने से पहले साबुन से हाथ धोएं।",
      "दस्त पर तुरंत ORS दें।","पीने का पानी ढककर रखें।"],
      "अपनी सेवाएं जानें":["हर रोगी को मुफ्त ABHA-linked ID मिलती है।",
      "इस ऐप से रेफरल पूरी तरह ट्रैक होते हैं।","किसी भी समय Emergency SOS बटन दबाएं।"]},
}
def get_tips(): return HEALTH_TIPS.get(st.session_state.get("ui_lang","en"),HEALTH_TIPS["en"])

def fire_sos(conn,abha_id,p,past_t,source_note):
    lines=[f"Patient: {p['name']}, Age: {p['age']}, Gender: {p['gender']}",
           f"Village/Location: {p['village']}, ABHA: {p['abha_id']}","── Recent Medical History ──"]
    for _,r in past_t.iterrows():
        lines.append(f"[{r['priority']}] {r.get('department','—')}: {str(r['symptoms_text'])[:60]} ({str(r['created_at'])[:10]})")
    if past_t.empty: lines.append("No prior visits on record.")
    med_sum="\n".join(lines)
    nt=datetime.now().strftime("%H:%M:%S")
    rlog="\n".join([f"[{nt}] SOS activated — {source_note}",
        f"[{nt}] Location packaged: {p['village']}",
        f"[{nt}] Medical history packaged ({len(past_t)} records)",
        "── LOCALIZED RESPONDERS ──",
        f"[{nt}] ✅ All ASHA/ANM workers notified",f"[{nt}] ✅ All duty doctors alerted",
        "── CENTRAL COMMAND ──",
        f"[{nt}] ✅ Dispatch center pinged — {p['village']}",
        f"[{nt}] ✅ Ambulance dispatch requested for {p['village']}"])
    sid=str(uuid.uuid4())
    conn.execute("INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid,abha_id,p["name"],p["village"],datetime.now().isoformat(),"ACTIVE",None,None,None,source_note,med_sum,rlog,0))
    return sid,med_sum,rlog

# ── INIT + SIDEBAR ────────────────────────────────────────────
init_db()
if "ui_lang" not in st.session_state: st.session_state.ui_lang="en"

with st.sidebar:
    st.markdown("## 🩺 ArogyaBridge")
    st.caption("Bridge to Healthcare · SIH26133")
    LANG_LABELS={"en":"🇬🇧 English","hi":"🇮🇳 हिंदी","mr":"🇮🇳 मराठी","ta":"🇮🇳 தமிழ்","te":"🇮🇳 తెలుగు","bn":"🇮🇳 বাংলা"}
    lc=st.selectbox("🌐 Language / भाषा",list(LANG_LABELS.values()),label_visibility="collapsed")
    st.session_state.ui_lang=next(k for k,v in LANG_LABELS.items() if v==lc)
    st.divider()
    if "active_role" not in st.session_state: st.session_state.active_role="patient_portal"
    ROLE_GROUPS=[("🌍 Community",["patient_portal"]),("🏥 Care Team",["asha","doctor"]),("🏛️ Oversight",["facility","admin","medicine"])]
    for grp,keys in ROLE_GROUPS:
        st.caption(grp)
        cols=st.columns(len(keys))
        for col,key in zip(cols,keys):
            is_active=st.session_state.active_role==key
            if col.button(tr(key),key=f"nav_{key}",type="primary" if is_active else "secondary",use_container_width=True):
                st.session_state.active_role=key; st.rerun()
    page=tr(st.session_state.active_role)
    st.divider()
    st.caption("🤖 AI: "+("🟢 Groq Llama 3.1 (live)" if GROQ_API_KEY else "🟡 Rule-based fallback"))
    st.caption(f"📅 {datetime.now().strftime('%d %b %Y, %H:%M')}")

st.title(tr("app_title"))

# ══════════════════════════════════════════════════════════════
# HELPER WIDGETS (reused across portals)
# ══════════════════════════════════════════════════════════════
def show_notifications_banner(role, uid):
    notifs=get_unread(role,uid)
    if not notifs: return
    reds=[n for n in notifs if n["priority"]=="RED"]
    others=[n for n in notifs if n["priority"]!="RED"]
    if reds:
        st.error(f"🚨 {len(reds)} Emergency Alert(s)")
        for n in reds: st.write(f"• {n['message']}")
    if others:
        st.warning(f"🔔 {len(others)} Notification(s)")
        for n in others: st.write(f"• {n['message']}")
    if notifs:
        if st.button("✅ Mark all as read",key=f"mark_read_{role}_{uid}"): mark_read(role,uid); st.rerun()

def show_patient_history_panel(abha_id):
    # Uses expanders instead of tabs — tabs cannot be nested inside other tabs in Streamlit
    with st.expander("📋 Past Visits", expanded=True):
        ph=qdf("SELECT symptoms_text,priority,department,temperature,spo2,pulse,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC",(abha_id,))
        st.dataframe(cdf(ph),use_container_width=True,hide_index=True) if not ph.empty else st.caption("No prior visits on record.")
    with st.expander("💊 Past Prescriptions", expanded=False):
        pr=qdf("SELECT facility,prescription,doctor_notes,completed_at FROM referrals WHERE abha_id=? AND status='COMPLETED' ORDER BY completed_at DESC",(abha_id,))
        st.dataframe(cdf(pr),use_container_width=True,hide_index=True) if not pr.empty else st.caption("No completed referrals on record.")

def vitals_form(key_prefix):
    v1,v2,v3=st.columns(3)
    vt=v1.text_input("🌡️ Temp (°F)",placeholder="e.g. 101.4",key=f"{key_prefix}_vt")
    vs=v2.text_input("🩸 SpO₂ (%)",placeholder="e.g. 96",key=f"{key_prefix}_vs")
    vp=v3.text_input("💓 Pulse (bpm)",placeholder="e.g. 88",key=f"{key_prefix}_vp")
    for val,lbl,check in [(vt,"Temperature",lambda x:x>=103),(vs,"SpO₂",lambda x:x<94),(vp,"Pulse",lambda x:x>100 or x<60)]:
        try:
            if check(float(val)): st.warning(f"⚠️ Abnormal {lbl}: {val}")
        except Exception: pass
    return vt or None, vs or None, vp or None

def triage_result_card(priority,rationale,dept,fud):
    color=PRIORITY_COLORS.get(priority,"#999")
    st.markdown(f"""<div style='border-left:5px solid {color};padding:14px 18px;border-radius:8px;background:{"#ffeaea" if priority=="RED" else "#fffbe6" if priority=="YELLOW" else "#f0fff4"}'>
    <div style='font-size:1.1rem;font-weight:700'>{priority_badge(priority)}</div>
    <div style='margin-top:8px;font-size:.95rem'>{rationale}</div>
    <div style='margin-top:8px;font-size:.9rem;opacity:.8'>🏥 Suggested department: <b>{dept}</b></div>
    {"<div style='margin-top:6px;font-size:.85rem;opacity:.7'>📅 Follow-up due: "+fud+"</div>" if fud else ""}
    </div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE: PATIENT PORTAL
# ══════════════════════════════════════════════════════════════
if page==tr("patient_portal"):
    sk="patient_user"
    if sk not in st.session_state: st.session_state[sk]=None

    if not st.session_state[sk]:
        st.markdown("### 🧑‍🦱 "+tr("patient_portal"))
        st.caption("Access your health records, book appointments, run a self-check, and reach emergency services — all in one place.")
        login_tab,reg_tab=st.tabs(["🔐 "+tr("login"),"📝 "+tr("register_tab")])
        with login_tab:
            with st.container(border=True):
                st.caption(tr("phone_login_hint"))
                aad=st.text_input(tr("aadhaar_id"),key="l_aad_p",placeholder="12-digit Aadhaar number")
                pw=st.text_input(tr("password"),type="password",key="l_pw_p")
                if st.button(tr("login_btn"),type="primary",use_container_width=True,key="l_btn_p"):
                    aad_c=(aad or "").strip().replace(" ","")
                    if not aad_c or not pw: st.warning("Enter Aadhaar ID and password.")
                    else:
                        conn=get_conn(); row=conn.execute("SELECT * FROM patients WHERE aadhaar_id=?",(aad_c,)).fetchone(); conn.close()
                        if row and verify_pw(pw,row["salt"],row["password_hash"]): st.session_state[sk]=dict(row); st.rerun()
                        else: st.error(tr("invalid_login"))
        with reg_tab:
            with st.container(border=True):
                st.caption("Register yourself to get a free ABHA-linked health ID.")
                with st.form("reg_patient_form"):
                    c1,c2=st.columns(2)
                    rn=c1.text_input(tr("name")); ra=c2.number_input(tr("age"),0,120,0)
                    rg=c1.selectbox(tr("gender"),["Female","Male","Other"]); rv=c2.text_input(tr("village"))
                    raad=c1.text_input(tr("aadhaar_id"),placeholder="12-digit Aadhaar number")
                    rph=c2.text_input(tr("phone")+" (optional)")
                    rl=c1.selectbox(tr("language"),["Marathi","Hindi","Tamil","Telugu","Bengali","English"])
                    rpw=c1.text_input(tr("password"),type="password"); rc=c2.text_input(tr("confirm_password"),type="password")
                    if st.form_submit_button("✅ "+tr("register_btn"),type="primary",use_container_width=True):
                        aad_c=(raad or "").strip().replace(" ","")
                        errs=[]
                        if not rn.strip(): errs.append("Full name is required.")
                        if not valid_aadhaar(aad_c): errs.append("Enter a valid 12-digit Aadhaar ID (digits only, no spaces).")
                        if not rpw or rpw!=rc: errs.append("Passwords do not match or are empty.")
                        if errs: [st.error(e) for e in errs]
                        else:
                            conn=get_conn()
                            if conn.execute("SELECT abha_id FROM patients WHERE aadhaar_id=?",(aad_c,)).fetchone():
                                st.error("This Aadhaar ID is already registered — please log in instead."); conn.close()
                            else:
                                h,s=hash_pw(rpw)
                                conn.execute("INSERT INTO patients(abha_id,name,age,gender,village,phone,aadhaar_id,language,created_at,password_hash,salt,registered_by_type) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                             (gen_abha(),rn.strip(),ra,rg,rv.strip(),rph.strip(),aad_c,rl,datetime.now().isoformat(),h,s,"self"))
                                conn.commit(); conn.close(); st.success("✅ Registered successfully! Please log in above.")
    else:
        u=st.session_state[sk]; abha_id=u["abha_id"]
        conn=get_conn(); p=conn.execute("SELECT * FROM patients WHERE abha_id=?",(abha_id,)).fetchone(); conn.close()

        with st.container(border=True):
            h1,h2=st.columns([4,1])
            h1.markdown(f"### 👋 {tr('welcome_back')}, **{p['name']}**")
            if h2.button(tr("logout_btn")): st.session_state[sk]=None; st.rerun()
            mc1,mc2,mc3,mc4=st.columns(4)
            mc1.metric("🪪 ABHA ID",p["abha_id"]); mc2.metric("🎂 "+tr("age"),int(p["age"]) if p["age"] else "—")
            mc3.metric("🏘️ "+tr("village"),p["village"] or "—"); mc4.metric("🔒 Aadhaar",mask_aadhaar(p["aadhaar_id"]))

        with st.expander("📚 Health Awareness & Useful Tips",expanded=False):
            tips=get_tips()
            tcols=st.columns(len(tips))
            for col,(cat,lines) in zip(tcols,tips.items()):
                col.markdown(f"**{cat}**")
                for l in lines: col.markdown(f"<div style='font-size:.88rem;margin-bottom:4px'>• {l}</div>",unsafe_allow_html=True)

        # Action row
        PANEL_KEYS=["show_appt","show_self_triage","show_update","show_token"]
        def _toggle_panel(key):
            val=not st.session_state.get(key,False)
            for k in PANEL_KEYS: st.session_state[k]=False
            st.session_state[key]=val

        qa1,qa2,qa3,qa4,qa5=st.columns(5)
        if qa1.button("📅 "+tr("book_appointment"),use_container_width=True): _toggle_panel("show_appt")
        if qa2.button("🤖 Self Triage",use_container_width=True): _toggle_panel("show_self_triage")
        if qa3.button("✏️ "+tr("update_details"),use_container_width=True): _toggle_panel("show_update")
        if qa4.button("🎫 Queue Token",use_container_width=True): _toggle_panel("show_token")
        if qa5.button("🆘 "+tr("sos"),type="primary",use_container_width=True):
            for k in PANEL_KEYS: st.session_state[k]=False
            st.session_state["sos_armed"]=True; st.session_state["sos_armed_at"]=datetime.now().isoformat()

        # ── Queue Token ──────────────────────────────────
        if st.session_state.get("show_token"):
            with st.container(border=True):
                st.markdown("#### 🎫 Walk-in Queue Token")
                st.caption("Get a number so you don't have to stand in line — check your position before leaving home.")
                facs=get_facility_names()
                if not facs: st.info("No facilities have registered yet. Please check back soon.")
                else:
                    tok_fac=st.selectbox("Select Facility",facs,key="tok_fac_p")
                    today=datetime.now().strftime("%Y-%m-%d")
                    my_tok=qdf("SELECT token_no,status FROM queue_tokens WHERE abha_id=? AND facility=? AND token_date=? AND status IN ('WAITING','CALLED') ORDER BY created_at DESC LIMIT 1",(abha_id,tok_fac,today))
                    if not my_tok.empty:
                        st.success(f"✅ You have Token **#{int(my_tok['token_no'][0])}** at {tok_fac} today — Status: `{my_tok['status'][0]}`")
                    else:
                        if st.button("🎫 Generate My Token",type="primary",key="gen_tok"):
                            tno=next_token_no(tok_fac,today); conn=get_conn()
                            conn.execute("INSERT INTO queue_tokens(id,abha_id,patient_name,facility,token_no,token_date,status,created_at) VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),abha_id,p["name"],tok_fac,tno,today,"WAITING",datetime.now().isoformat()))
                            conn.commit(); conn.close(); st.success(f"🎫 Token **#{tno}** issued at {tok_fac}."); st.rerun()
                    waiting=int(qdf("SELECT COUNT(*) as n FROM queue_tokens WHERE facility=? AND token_date=? AND status='WAITING'",(tok_fac,today))["n"][0])
                    ns=qdf("SELECT token_no FROM queue_tokens WHERE facility=? AND token_date=? AND status='CALLED' ORDER BY token_no DESC LIMIT 1",(tok_fac,today))
                    serving_txt=f"Token #{int(ns['token_no'][0])}" if not ns.empty else "—"
                    st.caption(f"🔢 Now serving: {serving_txt} · {waiting} patient(s) waiting at {tok_fac} today")

        # ── 5-Second SOS Cancel Window ───────────────────
        if st.session_state.get("sos_armed"):
            armed_at=datetime.fromisoformat(st.session_state["sos_armed_at"])
            remaining=max(0,5-int((datetime.now()-armed_at).total_seconds()))
            with st.container(border=True):
                st.markdown(f"""<div style='background:linear-gradient(135deg,#b71c1c,#e53935);color:white;border-radius:14px;padding:22px;text-align:center;box-shadow:0 4px 20px rgba(229,57,53,.4)'>
                <div style='font-size:2.5rem'>🚨</div>
                <h2 style='margin:6px 0;color:white;font-size:1.6rem'>SOS ARMING IN {remaining} SECOND{"S" if remaining!=1 else ""}</h2>
                <p style='margin:8px 0 0 0;font-size:1rem;opacity:.9'>Emergency services will be dispatched automatically.<br><b>Press CANCEL below if this was a mistake.</b></p>
                </div>""",unsafe_allow_html=True)
                cc1,cc2=st.columns(2)
                if cc1.button("❌ CANCEL — False Alarm",use_container_width=True,key="sos_cancel_btn"):
                    conn=get_conn()
                    conn.execute("INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (str(uuid.uuid4()),abha_id,p["name"],p["village"],st.session_state["sos_armed_at"],"CANCELLED",datetime.now().isoformat(),"Patient (self-cancel)",None,"Cancelled within 5s window — false alarm.",None,None,1))
                    conn.commit(); conn.close(); st.session_state["sos_armed"]=False
                    st.info("✅ SOS cancelled. A false-alarm log has been recorded for safety audit."); st.rerun()
                if remaining==0 or cc2.button("🚨 SEND NOW (skip timer)",type="primary",use_container_width=True,key="sos_send_now"):
                    past_t=qdf("SELECT priority,department,symptoms_text,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC LIMIT 5",(abha_id,))
                    conn=get_conn(); sid,med_sum,rlog=fire_sos(conn,abha_id,p,past_t,"Manual SOS button"); conn.commit(); conn.close()
                    notify_all_doctors(f"🚨 EMERGENCY SOS — {p['name']} ({p['village']}) | Age: {p['age']} | ABHA: {abha_id} | Full medical record attached.","RED",abha_id=abha_id)
                    notify_all_asha(f"🚨 SOS ALERT — {p['name']} ({p['village']}) needs immediate help. You are a nearby responder.","RED",abha_id=abha_id)
                    st.session_state["sos_armed"]=False; st.session_state["last_sos_id"]=sid
                    st.error("🚨 EMERGENCY SOS DISPATCHED SUCCESSFULLY")
                    rc1,rc2=st.columns(2)
                    with rc1:
                        st.markdown("**📍 Localized Responders**")
                        st.success("✅ All ASHA/ANM workers notified"); st.success("✅ Duty doctors alerted")
                    with rc2:
                        st.markdown("**🏥 Central Command**")
                        st.success("✅ Dispatch center pinged"); st.success("✅ Ambulance requested")
                    with st.expander("📋 Medical Package Dispatched"): st.code(med_sum)
                    st.rerun()
        if st.session_state.get("last_sos_id"):
            row=qdf("SELECT routing_log FROM sos_alerts WHERE id=?",(st.session_state["last_sos_id"],))
            if not row.empty and str(row.iloc[0]["routing_log"])!="nan":
                with st.expander("📡 SOS Routing Log"): st.code(row.iloc[0]["routing_log"])

        # ── Appointment ──────────────────────────────────
        if st.session_state.get("show_appt"):
            with st.container(border=True):
                st.markdown(f"#### 📅 {tr('book_appointment')}")
                facs=get_facility_names()
                if not facs: st.info("No facilities registered yet. Check back soon.")
                else:
                    af1,af2,af3=st.columns(3)
                    appt_fac=af1.selectbox("Facility",facs,key="appt_fac_p")
                    appt_date=af2.date_input("Preferred Date",min_value=datetime.now().date(),key="appt_date_p")
                    appt_slot=af3.selectbox("Time Slot",["9:00–10:00 AM","10:00–11:00 AM","11:00–12:00 PM","2:00–3:00 PM","3:00–4:00 PM","4:00–5:00 PM"],key="appt_slot_p")
                    if st.button("✅ Confirm Appointment Request",type="primary",key="book_appt_p"):
                        conn=get_conn()
                        conn.execute("INSERT INTO appointments(id,abha_id,facility,appointment_date,time_slot,status,created_at) VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),abha_id,appt_fac,str(appt_date),appt_slot,"REQUESTED",datetime.now().isoformat()))
                        conn.commit(); conn.close(); st.success(f"✅ Appointment requested at **{appt_fac}** on **{appt_date}** ({appt_slot}). Wait for doctor confirmation."); st.session_state["show_appt"]=False; st.rerun()

        # ── Self Triage ──────────────────────────────────
        if st.session_state.get("show_self_triage"):
            with st.container(border=True):
                st.markdown("#### 🤖 Self Symptom Check")
                st.caption("Describe how you're feeling in English or Hindi. The AI will assess severity and automatically alert the right people.")
                syms=st.text_area("Your Symptoms",placeholder="e.g. I have chest pain and I am finding it hard to breathe for the past 2 hours",height=100,key="self_syms_p")
                if st.button("🔍 Check My Symptoms",type="primary",key="self_triage_btn"):
                    if not syms.strip(): st.warning("Please describe your symptoms before checking.")
                    else:
                        with st.spinner("AI is analysing your symptoms..."): priority,rationale,dept,fud=run_triage(syms)
                        tid=str(uuid.uuid4()); conn=get_conn()
                        conn.execute("INSERT INTO triage(id,abha_id,symptoms_text,priority,rationale,created_by,created_at,department,follow_up_due_date,follow_up_done,triggered_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                     (tid,abha_id,syms,priority,rationale,p["name"],datetime.now().isoformat(),dept,fud,0,"patient"))
                        if priority=="RED":
                            past_t=qdf("SELECT priority,department,symptoms_text,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC LIMIT 5",(abha_id,))
                            sid,med_sum,rlog=fire_sos(conn,abha_id,p,past_t,"Auto-SOS: self-triage RED result")
                            notify_all_doctors(f"🚨 AUTO-SOS: {p['name']} ({p['village']}) self-reported RED symptoms: '{syms[:60]}...' Full medical record attached.","RED",tid,abha_id)
                            notify_all_asha(f"🚨 AUTO-SOS: {p['name']} ({p['village']}) is in emergency. You are a nearby responder.","RED",tid,abha_id)
                        elif priority=="YELLOW":
                            notify_all_doctors(f"⚠️ YELLOW: {p['name']} ({p['village']}) needs follow-up — '{syms[:60]}'.","YELLOW",tid,abha_id)
                            notify_all_asha(f"⚠️ YELLOW: {p['name']} ({p['village']}) reported symptoms. Please follow up.","YELLOW",tid,abha_id)
                        else:
                            notify_all_asha(f"ℹ️ GREEN: {p['name']} self-checked — no urgent action needed.","GREEN",tid,abha_id)
                        conn.commit(); conn.close()
                        triage_result_card(priority,rationale,dept,fud)
                        if priority=="RED":
                            st.error("🚨 Emergency SOS auto-triggered! All doctors + ASHA workers alerted. Ambulance requested.")
                            rc1,rc2=st.columns(2)
                            rc1.success("✅ ASHA/ANM workers notified"); rc1.success("✅ Duty doctors alerted")
                            rc2.success("✅ Dispatch center pinged"); rc2.success("✅ Ambulance requested")
                        elif priority=="YELLOW": st.warning("⚠️ Doctors and your ASHA worker have been notified. Please visit the nearest health centre soon.")
                        else: st.success("✅ Your ASHA worker has been informed. Routine care advised — rest and stay hydrated.")

        # ── Update Details ───────────────────────────────
        if st.session_state.get("show_update"):
            with st.container(border=True):
                st.markdown(f"#### ✏️ {tr('update_details')}")
                st.caption("Name and Aadhaar ID are fixed as your identity anchor. Update other details below.")
                with st.form("patient_update_form"):
                    uc1,uc2=st.columns(2)
                    new_age=uc1.number_input(tr("age"),0,120,int(p["age"]) if p["age"] else 0)
                    new_g=uc2.selectbox(tr("gender"),["Female","Male","Other"],index=["Female","Male","Other"].index(p["gender"]) if p["gender"] in ["Female","Male","Other"] else 0)
                    new_v=uc1.text_input(tr("village"),value=p["village"] or "")
                    new_ph=uc2.text_input(tr("phone"),value=p["phone"] or "")
                    new_l=uc1.selectbox(tr("language"),["Marathi","Hindi","Tamil","Telugu","Bengali","English"],
                                        index=["Marathi","Hindi","Tamil","Telugu","Bengali","English"].index(p["language"]) if p["language"] in ["Marathi","Hindi","Tamil","Telugu","Bengali","English"] else 0)
                    if st.form_submit_button("💾 Save Changes",type="primary"):
                        conn=get_conn(); conn.execute("UPDATE patients SET age=?,gender=?,village=?,phone=?,language=? WHERE abha_id=?",(new_age,new_g,new_v.strip(),new_ph.strip(),new_l,abha_id)); conn.commit(); conn.close()
                        st.success("✅ Details updated successfully."); st.rerun()

        st.divider()
        my_appts=qdf("SELECT facility,appointment_date,time_slot,status FROM appointments WHERE abha_id=? ORDER BY appointment_date DESC",(abha_id,))
        if not my_appts.empty:
            st.markdown("**📅 My Appointments**"); st.dataframe(cdf(my_appts),use_container_width=True,hide_index=True)
        active_sos=qdf("SELECT triggered_at FROM sos_alerts WHERE abha_id=? AND status='ACTIVE'",(abha_id,))
        if not active_sos.empty: st.error(f"🚨 {len(active_sos)} active SOS alert(s) — emergency response dispatched, help is on the way.")

        st.subheader("📋 "+tr("my_health_record"))
        ht1,ht2=st.tabs(["🩺 "+tr("my_triage_history"),"📨 "+tr("my_referrals")])
        with ht1:
            th=qdf("SELECT symptoms_text,priority,department,temperature,spo2,pulse,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC",(abha_id,))
            if th.empty: st.info(tr("no_records_yet"))
            else:
                for _,r in th.iterrows():
                    with st.container(border=True):
                        rc1,rc2=st.columns([3,1]); rc1.write(f"**{r['symptoms_text']}**"); rc2.markdown(priority_badge(r["priority"]),unsafe_allow_html=True)
                        rc1.caption(f"🏥 {r['department'] or '—'}  |  📅 {str(r['created_at'])[:10]}")
                        vitals=[(r.get("temperature"),f"🌡️ {r.get('temperature')}°F"),(r.get("spo2"),f"🩸 SpO₂ {r.get('spo2')}%"),(r.get("pulse"),f"💓 {r.get('pulse')} bpm")]
                        valid_v=[(v,l) for v,l in vitals if v and str(v) not in ["nan","None",""]]
                        if valid_v:
                            vc=st.columns(len(valid_v))
                            for col,(v,l) in zip(vc,valid_v): col.info(l)
        with ht2:
            rh=qdf("SELECT facility,status,prescription,doctor_notes,created_at FROM referrals WHERE abha_id=? ORDER BY created_at DESC",(abha_id,))
            if rh.empty: st.info(tr("no_records_yet"))
            else:
                for _,r in rh.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['facility']}** — `{r['status']}` · {str(r['created_at'])[:10]}")
                        if str(r.get("prescription","")) not in ["nan","—",""]: st.write(f"💊 **Prescription:** {r['prescription']}")
                        if str(r.get("doctor_notes","")) not in ["nan","—",""]: st.caption(f"📝 Notes: {r['doctor_notes']}")

# ══════════════════════════════════════════════════════════════
# PAGE: ASHA WORKER PORTAL
# ══════════════════════════════════════════════════════════════
elif page==tr("asha"):
    sk="asha_user"
    if sk not in st.session_state: st.session_state[sk]=None
    if not st.session_state[sk]:
        st.markdown("### 🚶‍♀️ "+tr("asha"))
        with st.container(border=True):
            st.caption("Log in with the Worker ID and password your facility issued you.")
            wid=st.text_input("Worker ID",key="l_id_asha",placeholder="e.g. ASHA-A1B2C3")
            pw=st.text_input(tr("password"),type="password",key="l_pw_asha")
            if st.button(tr("login_btn"),type="primary",use_container_width=True,key="l_btn_asha"):
                if not wid or not pw: st.warning("Enter your Worker ID and password.")
                else:
                    conn=get_conn(); row=conn.execute("SELECT * FROM asha_workers WHERE id=?",(wid.strip().upper(),)).fetchone(); conn.close()
                    if row and verify_pw(pw,row["salt"],row["password_hash"]): st.session_state[sk]=dict(row); st.rerun()
                    else: st.error(tr("invalid_login"))
        st.info("💡 No account? Ask your facility administrator to register you from the **Facility / Hospital** portal.")
    else:
        u=st.session_state[sk]
        with st.container(border=True):
            ah1,ah2=st.columns([4,1])
            ah1.markdown(f"### 🚶‍♀️ {u['name']} — {u['facility'] or '—'}")
            ah1.caption(f"Worker ID: `{u['id']}`")
            if ah2.button(tr("logout_btn")): st.session_state[sk]=None; st.rerun()
            show_notifications_banner("asha",u["id"])

        tab1,tab2,tab3,tab4=st.tabs(["📝 Register Patient","🤖 Triage & Referral","🔔 Follow-ups","📜 History"])

        with tab1:
            with st.form("asha_reg_form"):
                c1,c2=st.columns(2)
                rn=c1.text_input(tr("name")); ra=c2.number_input(tr("age"),0,120,30)
                rg=c1.selectbox(tr("gender"),["Female","Male","Other"]); rv=c2.text_input(tr("village"))
                raad=c1.text_input(tr("aadhaar_id")+" (patient's)",placeholder="12-digit Aadhaar number")
                rph=c2.text_input(tr("phone")+" (optional)")
                rl=c1.selectbox(tr("language"),["Marathi","Hindi","Tamil","Telugu","Bengali","English"])
                setup=st.checkbox("Set up patient app login now (so patient can self-access records)")
                rpw=st.text_input("Patient password",type="password",key="asha_reg_pw") if setup else ""
                if st.form_submit_button("✅ "+tr("register_btn"),type="primary",use_container_width=True):
                    aad_c=(raad or "").strip().replace(" ","")
                    errs=[]
                    if not rn.strip(): errs.append("Patient name is required.")
                    if not valid_aadhaar(aad_c): errs.append("Enter a valid 12-digit Aadhaar ID.")
                    if setup and not rpw: errs.append("Enter a password or uncheck the login setup option.")
                    if errs: [st.error(e) for e in errs]
                    else:
                        conn=get_conn()
                        if conn.execute("SELECT abha_id FROM patients WHERE aadhaar_id=?",(aad_c,)).fetchone():
                            st.error("A patient with this Aadhaar ID is already registered."); conn.close()
                        else:
                            h,s=(hash_pw(rpw) if setup else (None,None)); aid=gen_abha()
                            conn.execute("INSERT INTO patients(abha_id,name,age,gender,village,phone,aadhaar_id,language,created_at,password_hash,salt,registered_by_type,registered_by_id,registered_by_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                         (aid,rn.strip(),ra,rg,rv.strip(),rph.strip(),aad_c,rl,datetime.now().isoformat(),h,s,"asha",u["id"],u["name"]))
                            conn.commit(); conn.close()
                            st.success(f"✅ Patient registered! **ABHA ID: {aid}**")
                            if setup: st.info(f"Patient can now log in from the Patient Portal using **Aadhaar ID: {aad_c}**")
            st.divider()
            view=st.radio("View",["My Registered Patients","All Patients"],horizontal=True,key="asha_view")
            if view=="My Registered Patients":
                pts=qdf("SELECT name,age,gender,village,aadhaar_id,created_at FROM patients WHERE registered_by_id=? ORDER BY created_at DESC",(u["id"],))
            else:
                pts=qdf("SELECT name,age,gender,village,aadhaar_id,registered_by_name,created_at FROM patients ORDER BY created_at DESC")
            if not pts.empty and "aadhaar_id" in pts.columns:
                pts["aadhaar_id"]=pts["aadhaar_id"].apply(lambda x: mask_aadhaar(str(x)) if pd.notna(x) else "—")
            st.dataframe(cdf(pts),use_container_width=True,hide_index=True)

        with tab2:
            pts2=qdf("SELECT abha_id,name FROM patients ORDER BY name")
            if pts2.empty: st.info("Register a patient first from the previous tab.")
            else:
                opts={f"{r['name']} ({r['abha_id']})":r["abha_id"] for _,r in pts2.iterrows()}
                sel_p=st.selectbox("Select Patient",list(opts.keys()),key="asha_triage_sel")
                a2=opts[sel_p]
                syms=st.text_area(tr("symptoms"),placeholder="e.g. High fever for 3 days with breathlessness and vomiting",height=90,key="asha_syms")
                with st.expander("📊 Record Vitals (optional but recommended)",expanded=False):
                    st.caption("Fill if you have a BP monitor or pulse oximeter available.")
                    vt,vs,vp=vitals_form("asha")
                if st.button("🤖 "+tr("run_triage"),type="primary",key="asha_triage_btn",use_container_width=True):
                    if not syms.strip(): st.warning("Please enter symptoms before running triage.")
                    else:
                        with st.spinner("AI analysing symptoms..."): priority,rationale,dept,fud=run_triage(syms)
                        tid=str(uuid.uuid4()); conn=get_conn()
                        conn.execute("INSERT INTO triage(id,abha_id,symptoms_text,priority,rationale,created_by,created_at,department,follow_up_due_date,follow_up_done,temperature,spo2,pulse,triggered_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                     (tid,a2,syms,priority,rationale,u["name"],datetime.now().isoformat(),dept,fud,0,vt,vs,vp,"asha"))
                        conn.commit(); conn.close()
                        st.session_state["asha_last_tid"]=tid; st.session_state["asha_last_pri"]=priority
                        triage_result_card(priority,rationale,dept,fud)
                if st.session_state.get("asha_last_tid"):
                    pr=st.session_state.get("asha_last_pri","GREEN")
                    if pr in ("RED","YELLOW"):
                        st.divider(); st.warning("⚠️ This patient needs facility care.")
                        facs=get_facility_names()
                        if not facs: st.info("No facilities registered yet.")
                        else:
                            fac=st.selectbox(tr("select_facility"),facs,key="asha_ref_fac")
                            if st.button("🚑 "+tr("refer_btn"),type="primary",key="asha_refer_btn",use_container_width=True):
                                conn=get_conn(); conn.execute("INSERT INTO referrals VALUES(?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),a2,st.session_state["asha_last_tid"],fac,"PENDING","","",datetime.now().isoformat(),None,None)); conn.commit(); conn.close()
                                st.success(f"✅ Referral sent to **{fac}** with full patient record attached."); del st.session_state["asha_last_tid"]
                    else: st.info("✅ GREEN — routine care, no referral needed.")

        with tab3:
            st.caption("Patients auto-scheduled for follow-up based on triage priority (RED = 2 days, YELLOW = 7 days).")
            due=qdf("SELECT t.id as tid,p.name,p.phone,p.village,t.priority,t.department,t.follow_up_due_date FROM triage t JOIN patients p ON p.abha_id=t.abha_id WHERE t.follow_up_due_date IS NOT NULL AND (t.follow_up_done IS NULL OR t.follow_up_done=0) ORDER BY t.follow_up_due_date ASC")
            if due.empty: st.success("✅ No pending high-risk follow-ups right now.")
            else:
                today=datetime.now().strftime("%Y-%m-%d")
                for _,r in due.iterrows():
                    overdue=str(r["follow_up_due_date"])<today
                    with st.container(border=True):
                        dc1,dc2=st.columns([4,1])
                        dc1.markdown(f"{'🔴 **OVERDUE** —' if overdue else '🟡 **Due**'} **{r['follow_up_due_date']}** · {r['name']} ({r['village'] or '—'})")
                        dc1.caption(f"{r['priority']} · {r['department'] or '—'} · 📞 {r['phone'] or '—'}")
                        if dc2.button("✅ Done",key=f"fu_{r['tid']}",use_container_width=True):
                            conn=get_conn(); conn.execute("UPDATE triage SET follow_up_done=1 WHERE id=?",(r["tid"],)); conn.commit(); conn.close(); st.rerun()

        with tab4:
            st.subheader("🔴 Emergency Cases (All RED Triages)")
            em=qdf("SELECT p.name,p.village,t.symptoms_text,t.department,t.created_at FROM triage t JOIN patients p ON p.abha_id=t.abha_id WHERE t.priority='RED' ORDER BY t.created_at DESC")
            if em.empty: st.info("No RED priority cases recorded yet.")
            else:
                for _,r in em.iterrows():
                    with st.container(border=True):
                        st.write(f"🔴 **{r['name']}** ({r['village'] or '—'}) — {r['department'] or 'General'}")
                        st.caption(f"{str(r['symptoms_text'])[:80]} · {str(r['created_at'])[:10]}")
            st.divider()
            st.subheader("All Triage History (last 50)")
            ah=qdf("SELECT p.name,p.village,t.priority,t.symptoms_text,t.department,t.created_at FROM triage t JOIN patients p ON p.abha_id=t.abha_id ORDER BY t.created_at DESC LIMIT 50")
            st.dataframe(cdf(ah),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════
# PAGE: DOCTOR DASHBOARD
# ══════════════════════════════════════════════════════════════
elif page==tr("doctor"):
    sk="doctor_user"
    if sk not in st.session_state: st.session_state[sk]=None
    if not st.session_state[sk]:
        st.markdown("### 🩺 "+tr("doctor"))
        with st.container(border=True):
            st.caption("Log in with the Worker ID and password your facility issued you.")
            wid=st.text_input("Worker ID",key="l_id_doc",placeholder="e.g. DOC-A1B2C3")
            pw=st.text_input(tr("password"),type="password",key="l_pw_doc")
            if st.button(tr("login_btn"),type="primary",use_container_width=True,key="l_btn_doc"):
                if not wid or not pw: st.warning("Enter your Worker ID and password.")
                else:
                    conn=get_conn(); row=conn.execute("SELECT * FROM doctors WHERE id=?",(wid.strip().upper(),)).fetchone(); conn.close()
                    if row and verify_pw(pw,row["salt"],row["password_hash"]): st.session_state[sk]=dict(row); st.rerun()
                    else: st.error(tr("invalid_login"))
        st.info("💡 No account? Ask your facility administrator to register you from the **Facility / Hospital** portal.")
    else:
        u=st.session_state[sk]
        with st.container(border=True):
            dh1,dh2=st.columns([4,1])
            dh1.markdown(f"### 🩺 Dr. {u['name']} — {u['facility'] or '—'}")
            dh1.caption(f"Speciality: **{u['speciality'] or 'General Medicine'}** · Worker ID: `{u['id']}`")
            if dh2.button(tr("logout_btn")): st.session_state[sk]=None; st.rerun()
            show_notifications_banner("doctor",u["id"])
        mc1,mc2,mc3=st.columns(3)
        mc1.metric("✅ Patients Completed",int(qdf("SELECT COUNT(*) as n FROM referrals WHERE doctor_id=? AND status='COMPLETED'",(u["id"],))["n"][0]))
        mc2.metric("📋 Pending Referrals",int(qdf("SELECT COUNT(*) as n FROM referrals WHERE facility=? AND status='PENDING'",(u["facility"],))["n"][0]))
        mc3.metric("📅 Pending Appointments",int(qdf("SELECT COUNT(*) as n FROM appointments WHERE facility=? AND status='REQUESTED'",(u["facility"],))["n"][0]))

        dt1,dt2,dt3,dt4,dt5,dt6,dt7=st.tabs(["📋 Queue","🔍 Search Patient","📅 Appointments","📜 My History","🚨 SOS Alerts","🧪 Diagnostics","🎫 Walk-in Queue"])

        with dt1:
            queue=qdf("SELECT r.id as ref_id,p.abha_id,p.name,p.age,p.gender,p.village,t.symptoms_text,t.priority,t.rationale,t.department,t.created_by,r.status,r.created_at FROM referrals r JOIN patients p ON p.abha_id=r.abha_id JOIN triage t ON t.id=r.triage_id WHERE r.facility=? AND r.status='PENDING'",(u["facility"],))
            if queue.empty: st.info("✅ No pending referrals at this facility.")
            else:
                queue["_sort"]=queue["priority"].map(PRIORITY_ORDER); queue=queue.sort_values("_sort")
                st.caption(f"{len(queue)} patient(s) in queue — sorted by priority (RED first)")
                for _,row in queue.iterrows():
                    color=PRIORITY_COLORS.get(row["priority"],"#999")
                    with st.expander(f"{row['name']} · {row['age'] or '—'}y · {row['gender'] or '—'} · {row['department'] or 'General'} · {row['priority']}",expanded=False):
                        b1,b2=st.columns([3,1]); b1.markdown(priority_badge(row["priority"]),unsafe_allow_html=True); b2.markdown(f"**🏥 {row['department'] or 'General'}**")
                        st.write(f"**ABHA:** {row['abha_id']} | **Village:** {row['village'] or '—'} | **Referred by:** {row['created_by']}")
                        st.write(f"**Symptoms:** {row['symptoms_text']}")
                        st.caption(f"AI assessment: {row['rationale']}")
                        with st.container(border=True):
                            st.markdown("**📜 Full Patient History**")
                            show_patient_history_panel(row["abha_id"])
                        if st.button("📹 "+tr("teleconsult"),key=f"tc_{row['ref_id']}",use_container_width=True):
                            st.info("🔴 WebRTC teleconsultation would launch here via Daily.co integration.")
                        with st.container(border=True):
                            st.markdown("**🧪 Order Diagnostic Tests**")
                            tests=st.multiselect("Select test(s)",COMMON_TESTS,key=f"dx_{row['ref_id']}")
                            if st.button("📋 Order Tests",key=f"dxbtn_{row['ref_id']}"):
                                if not tests: st.warning("Select at least one test.")
                                else:
                                    conn=get_conn()
                                    for t in tests: conn.execute("INSERT INTO diagnostics(id,abha_id,referral_id,facility,test_name,status,ordered_by,ordered_at) VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),row["abha_id"],row["ref_id"],u["facility"],t,"ORDERED",u["name"],datetime.now().isoformat()))
                                    conn.commit(); conn.close(); st.success(f"✅ {len(tests)} test(s) ordered."); st.rerun()
                            ex_dx=qdf("SELECT test_name,status,result_notes FROM diagnostics WHERE referral_id=?",(row["ref_id"],))
                            if not ex_dx.empty: st.dataframe(cdf(ex_dx),use_container_width=True,hide_index=True)
                        with st.container(border=True):
                            st.markdown("**💊 Write Prescription & Complete**")
                            presc=st.text_area(tr("prescription"),placeholder="e.g. Tab. Paracetamol 500mg TDS × 5 days. ORS sachets as needed.",key=f"presc_{row['ref_id']}")
                            notes=st.text_input("Doctor notes (for record)",key=f"notes_{row['ref_id']}",placeholder="e.g. Review in 3 days if symptoms persist")
                            if st.button("✅ "+tr("save_prescription"),key=f"save_{row['ref_id']}",type="primary",use_container_width=True):
                                conn=get_conn(); conn.execute("UPDATE referrals SET status='COMPLETED',prescription=?,doctor_notes=?,completed_at=?,doctor_id=? WHERE id=?",(presc,notes,datetime.now().isoformat(),u["id"],row["ref_id"])); conn.commit(); conn.close()
                                st.success("✅ Referral completed. Prescription saved to patient record."); st.rerun()

        with dt2:
            st.subheader("🔍 Search Patient")
            search=st.text_input("Search by name or Aadhaar ID",placeholder="Type at least 2 characters...",key="doc_search")
            if search and len(search.strip())>=2:
                res=qdf("SELECT abha_id,name,age,gender,village,phone,aadhaar_id FROM patients WHERE name LIKE ? OR aadhaar_id LIKE ?",(f"%{search}%",f"%{search}%"))
                if res.empty: st.info("No patients found matching your search.")
                else:
                    st.caption(f"{len(res)} match(es) found")
                    opts={f"{r['name']} — {r['village'] or '—'} (Age {r['age'] or '—'})":r['abha_id'] for _,r in res.iterrows()}
                    picked=st.selectbox("Select a patient",list(opts.keys()),key="doc_search_pick")
                    sel=res[res["abha_id"]==opts[picked]].iloc[0]
                    with st.container(border=True):
                        sc1,sc2,sc3=st.columns(3)
                        sc1.write(f"**Age:** {sel['age'] or '—'} | **Gender:** {sel['gender'] or '—'}")
                        sc2.write(f"**Phone:** {sel['phone'] or '—'}")
                        sc3.write(f"**Aadhaar:** {mask_aadhaar(str(sel['aadhaar_id']))}")
                        show_patient_history_panel(sel["abha_id"])
            else: st.caption("Type 2+ characters to search.")

        with dt3:
            appts=qdf("SELECT a.id,p.name,p.phone,a.appointment_date,a.time_slot,a.status,a.decline_reason FROM appointments a JOIN patients p ON p.abha_id=a.abha_id WHERE a.facility=? ORDER BY a.appointment_date,a.time_slot",(u["facility"],))
            pending=appts[appts["status"]=="REQUESTED"] if not appts.empty else pd.DataFrame()
            if not pending.empty:
                st.markdown("**⏳ Pending Appointment Requests**")
                for _,a in pending.iterrows():
                    with st.container(border=True):
                        ac1,ac2,ac3=st.columns([3,1,1])
                        ac1.write(f"**{a['name']}** — {a['appointment_date']} at {a['time_slot']}")
                        ac1.caption(f"📞 {a['phone'] or '—'}")
                        if ac2.button("✅ Accept",key=f"acc_{a['id']}",use_container_width=True):
                            conn=get_conn(); conn.execute("UPDATE appointments SET status='CONFIRMED',doctor_id=? WHERE id=?",(u["id"],a["id"])); conn.commit(); conn.close(); st.rerun()
                        if ac3.button("❌ Decline",key=f"dec_btn_{a['id']}",use_container_width=True):
                            st.session_state[f"dec_{a['id']}"]=True
                    if st.session_state.get(f"dec_{a['id']}"):
                        reason=st.text_input("Reason for declining (required — patient will see this)",key=f"reason_{a['id']}",placeholder="e.g. Public holiday on that date / Doctor unavailable")
                        if st.button("Confirm Decline",key=f"confirm_dec_{a['id']}"):
                            if not reason.strip(): st.error("A reason is required before declining — the patient will be informed.")
                            else:
                                conn=get_conn(); conn.execute("UPDATE appointments SET status='DECLINED',decline_reason=? WHERE id=?",(reason.strip(),a["id"])); conn.commit(); conn.close()
                                del st.session_state[f"dec_{a['id']}"]; st.rerun()
            else: st.info("No pending appointment requests.")
            st.divider()
            for status,lbl in [("CONFIRMED","✅ Confirmed"),("COMPLETED","🏁 Completed"),("DECLINED","❌ Declined")]:
                grp=appts[appts["status"]==status] if not appts.empty else pd.DataFrame()
                if not grp.empty:
                    with st.expander(f"{lbl} ({len(grp)})"):
                        for _,a in grp.iterrows():
                            ac1,ac2=st.columns([4,1])
                            ac1.write(f"**{a['name']}** — {a['appointment_date']} at {a['time_slot']}")
                            dr=str(a.get("decline_reason",""))
                            if dr not in ["nan","—","",None]: ac1.caption(f"Reason: {dr}")
                            if status=="CONFIRMED":
                                if ac2.button("🏁 Mark Done",key=f"done_{a['id']}",use_container_width=True):
                                    conn=get_conn(); conn.execute("UPDATE appointments SET status='COMPLETED' WHERE id=?",(a["id"],)); conn.commit(); conn.close(); st.rerun()

        with dt4:
            st.subheader("📜 My Completed Cases")
            hist=qdf("SELECT p.name,p.village,t.priority,r.prescription,r.doctor_notes,r.completed_at FROM referrals r JOIN patients p ON p.abha_id=r.abha_id JOIN triage t ON t.id=r.triage_id WHERE r.doctor_id=? AND r.status='COMPLETED' ORDER BY r.completed_at DESC",(u["id"],))
            if hist.empty: st.info("No completed cases yet.")
            else:
                st.caption(f"{len(hist)} total completed cases")
                for _,r in hist.iterrows():
                    with st.container(border=True):
                        h1c,h2c=st.columns([3,1])
                        h1c.markdown(f"**{r['name']}** ({r['village'] or '—'}) {priority_badge(r['priority'])}",unsafe_allow_html=True)
                        h2c.caption(str(r.get("completed_at",""))[:10])
                        px=str(r.get("prescription",""))
                        if px not in ["nan","—",""]: st.write(f"💊 {px}")

        with dt5:
            st.subheader("🚨 Active SOS Alerts")
            sos=qdf("SELECT id,patient_name,village,triggered_at,accepted_by,medical_summary FROM sos_alerts WHERE status='ACTIVE' ORDER BY triggered_at DESC")
            if sos.empty: st.success("✅ No active SOS alerts right now.")
            else:
                for _,s in sos.iterrows():
                    with st.container(border=True):
                        sc1,sc2=st.columns([4,1])
                        sc1.write(f"🚨 **{s['patient_name']}** — {s['village'] or '—'}")
                        sc1.caption(f"Triggered: {str(s['triggered_at'])[:16]}")
                        ab=str(s.get("accepted_by",""))
                        if ab not in ["nan","",None]: sc1.info(f"✅ Being handled by {ab}")
                        else:
                            if sc2.button("🙋 Accept",key=f"asos_{s['id']}",type="primary",use_container_width=True):
                                conn=get_conn(); conn.execute("UPDATE sos_alerts SET accepted_by=? WHERE id=?",(f"Dr. {u['name']}",s["id"])); conn.commit(); conn.close()
                                notify_all_doctors(f"✅ SOS for {s['patient_name']} accepted by Dr. {u['name']}. No further action needed from other doctors.","GREEN"); st.rerun()
                        ms=str(s.get("medical_summary",""))
                        if ms not in ["nan","",None]:
                            with st.expander("📋 Medical record dispatched with SOS"): st.code(ms)

        with dt6:
            st.subheader("🧪 Diagnostics — Pending at " + (u["facility"] or "your facility"))
            pending_dx=qdf("SELECT d.id,p.name,p.village,d.test_name,d.status,d.ordered_at FROM diagnostics d JOIN patients p ON p.abha_id=d.abha_id WHERE d.facility=? AND d.status='ORDERED' ORDER BY d.ordered_at",(u["facility"],))
            if pending_dx.empty: st.info("No pending diagnostic tests.")
            else:
                for _,d in pending_dx.iterrows():
                    with st.container(border=True):
                        dc1,dc2=st.columns([3,1])
                        dc1.write(f"**{d['test_name']}** — {d['name']} ({d['village'] or '—'})")
                        dc1.caption(f"Ordered: {str(d['ordered_at'])[:16]}")
                        result=st.text_input("Result / notes (optional)",key=f"dxres_{d['id']}",label_visibility="collapsed",placeholder="Enter result notes (optional) then mark complete")
                        if dc2.button("✅ Done",key=f"dxdone_{d['id']}",use_container_width=True):
                            conn=get_conn(); conn.execute("UPDATE diagnostics SET status='COMPLETED',result_notes=?,completed_at=? WHERE id=?",(result,datetime.now().isoformat(),d["id"])); conn.commit(); conn.close(); st.rerun()
            done_dx=qdf("SELECT p.name,d.test_name,d.result_notes,d.completed_at FROM diagnostics d JOIN patients p ON p.abha_id=d.abha_id WHERE d.facility=? AND d.status='COMPLETED' ORDER BY d.completed_at DESC LIMIT 20",(u["facility"],))
            if not done_dx.empty: st.divider(); st.caption("Recently completed"); st.dataframe(cdf(done_dx),use_container_width=True,hide_index=True)

        with dt7:
            st.subheader("🎫 Today's Walk-in Queue — " + (u["facility"] or "your facility"))
            st.caption("Issue numbered tokens to walk-in patients. Patients can also self-generate tokens from the Patient Portal.")
            today=datetime.now().strftime("%Y-%m-%d")
            wc1,wc2=st.columns(2)
            with wc1:
                wn=st.text_input("Walk-in patient name",key="walkin_name",placeholder="Enter patient name to issue token")
                if st.button("🎫 Issue Token",key="walkin_issue",use_container_width=True):
                    if not wn.strip(): st.warning("Enter the patient's name.")
                    else:
                        tno=next_token_no(u["facility"],today); conn=get_conn()
                        conn.execute("INSERT INTO queue_tokens(id,abha_id,patient_name,facility,token_no,token_date,status,created_at) VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),None,wn.strip(),u["facility"],tno,today,"WAITING",datetime.now().isoformat()))
                        conn.commit(); conn.close(); st.success(f"🎫 Token **#{tno}** issued to {wn.strip()}."); st.rerun()
            with wc2:
                ns=qdf("SELECT patient_name,token_no FROM queue_tokens WHERE facility=? AND token_date=? AND status='CALLED' ORDER BY token_no DESC LIMIT 1",(u["facility"],today))
                if not ns.empty: st.success(f"✅ Now serving: **Token #{int(ns['token_no'][0])}** — {ns['patient_name'][0]}")
                else: st.info("No token currently being served.")
            waiting=qdf("SELECT id,token_no,patient_name,status,created_at FROM queue_tokens WHERE facility=? AND token_date=? AND status IN ('WAITING','CALLED') ORDER BY token_no",(u["facility"],today))
            if waiting.empty: st.info("Walk-in queue is empty.")
            else:
                st.dataframe(cdf(waiting[["token_no","patient_name","status","created_at"]]),use_container_width=True,hide_index=True)
                nxt=waiting[waiting["status"]=="WAITING"]
                if not nxt.empty:
                    n=nxt.iloc[0]
                    if st.button(f"📢 Call Next — Token #{int(n['token_no'])} ({n['patient_name']})",type="primary",key="call_next"):
                        conn=get_conn(); conn.execute("UPDATE queue_tokens SET status='CALLED',called_at=? WHERE id=?",(datetime.now().isoformat(),n["id"])); conn.commit(); conn.close(); st.rerun()
                called=waiting[waiting["status"]=="CALLED"]
                if not called.empty:
                    cur=called.iloc[0]
                    if st.button(f"🏁 Mark Token #{int(cur['token_no'])} — Done",key="tok_done"):
                        conn=get_conn(); conn.execute("UPDATE queue_tokens SET status='DONE',done_at=? WHERE id=?",(datetime.now().isoformat(),cur["id"])); conn.commit(); conn.close(); st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE: FACILITY / HOSPITAL PORTAL
# ══════════════════════════════════════════════════════════════
elif page==tr("facility"):
    sk="facility_user"
    if sk not in st.session_state: st.session_state[sk]=None
    if not st.session_state[sk]:
        st.markdown("### 🏥 "+tr("facility"))
        st.caption("Each Sub-Centre, PHC, or Hospital registers once here, then creates login IDs for its own ASHA workers and doctors.")
        login_tab,reg_tab=st.tabs(["🔐 "+tr("login"),"📝 "+tr("register_tab")])
        with login_tab:
            with st.container(border=True):
                ph=st.text_input(tr("phone"),key="l_ph_fac",placeholder="Registered facility phone number")
                pw=st.text_input(tr("password"),type="password",key="l_pw_fac")
                if st.button(tr("login_btn"),type="primary",use_container_width=True,key="l_btn_fac"):
                    if not ph or not pw: st.warning("Enter phone and password.")
                    else:
                        conn=get_conn(); row=conn.execute("SELECT * FROM facilities WHERE phone=?",(ph.strip(),)).fetchone(); conn.close()
                        if row and verify_pw(pw,row["salt"],row["password_hash"]): st.session_state[sk]=dict(row); st.rerun()
                        else: st.error(tr("invalid_login"))
        with reg_tab:
            with st.container(border=True):
                with st.form("reg_facility_form"):
                    c1,c2=st.columns(2)
                    fn=c1.text_input("Facility / Hospital Name",placeholder="e.g. PHC Ranjangaon")
                    ft=c2.selectbox("Facility Type",FACILITY_TYPES)
                    fv=c1.text_input("Village / Area Served",placeholder="e.g. Wagholi, Pune")
                    fph=c2.text_input(tr("phone"),placeholder="10-digit mobile number")
                    fpw=c1.text_input(tr("password"),type="password")
                    fc=c2.text_input(tr("confirm_password"),type="password")
                    if st.form_submit_button("✅ Register Facility",type="primary",use_container_width=True):
                        errs=[]
                        if not fn.strip(): errs.append("Facility name is required.")
                        if not fph.strip() or not valid_phone(fph.strip()): errs.append("Enter a valid 10-digit Indian mobile number.")
                        if not fpw or fpw!=fc: errs.append("Passwords do not match or are empty.")
                        if errs: [st.error(e) for e in errs]
                        else:
                            conn=get_conn()
                            if conn.execute("SELECT id FROM facilities WHERE name=? OR phone=?",(fn.strip(),fph.strip())).fetchone():
                                st.error("A facility with this name or phone number is already registered."); conn.close()
                            else:
                                h,s=hash_pw(fpw); fid=str(uuid.uuid4())
                                conn.execute("INSERT INTO facilities(id,name,type,village,phone,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?)",(fid,fn.strip(),ft,fv.strip(),fph.strip(),h,s,datetime.now().isoformat()))
                                conn.commit(); conn.close(); seed_stock(fid,fn.strip())
                                st.success("✅ Facility registered! Please log in above. Initial medicine stock has been seeded.")
    else:
        u=st.session_state[sk]
        with st.container(border=True):
            fh1,fh2=st.columns([4,1])
            fh1.markdown(f"### 🏥 {u['name']} — {u['type']}")
            fh1.caption(f"Area served: {u['village'] or '—'} · Phone: {u['phone']}")
            if fh2.button(tr("logout_btn")): st.session_state[sk]=None; st.rerun()
            fm1,fm2,fm3,fm4=st.columns(4)
            fm1.metric("🚶‍♀️ ASHA Workers",int(qdf("SELECT COUNT(*) as n FROM asha_workers WHERE facility_id=?",(u["id"],))["n"][0]))
            fm2.metric("🩺 Doctors",int(qdf("SELECT COUNT(*) as n FROM doctors WHERE facility_id=?",(u["id"],))["n"][0]))
            fm3.metric("📋 Pending Referrals",int(qdf("SELECT COUNT(*) as n FROM referrals WHERE facility=? AND status='PENDING'",(u["name"],))["n"][0]))
            fm4.metric("📅 Pending Appointments",int(qdf("SELECT COUNT(*) as n FROM appointments WHERE facility=? AND status='REQUESTED'",(u["name"],))["n"][0]))

        ft1,ft2=st.tabs(["👥 Staff Management","💊 Medicine Stock"])
        with ft1:
            sc1,sc2=st.columns(2)
            with sc1:
                st.markdown("#### ➕ Add ASHA / ANM Worker")
                with st.container(border=True):
                    with st.form("add_asha_form"):
                        an=st.text_input("Worker Full Name",key="new_asha_name")
                        aph=st.text_input("Phone (optional, for contact)",key="new_asha_ph",placeholder="Leave blank if not available")
                        if st.form_submit_button("Create ASHA Account",type="primary",use_container_width=True):
                            if not an.strip(): st.error("Worker name is required.")
                            elif aph.strip() and not valid_phone(aph.strip()): st.error("Enter a valid 10-digit phone number or leave blank.")
                            else:
                                conn=get_conn()
                                # BUG FIX: check name+facility to prevent duplicates on repeated clicks
                                if conn.execute("SELECT id FROM asha_workers WHERE name=? AND facility_id=?",(an.strip(),u["id"])).fetchone():
                                    st.error(f"An ASHA worker named '{an.strip()}' is already registered at this facility."); conn.close()
                                else:
                                    wid=gen_worker_id("ASHA"); pwd=gen_password(); h,s=hash_pw(pwd)
                                    ph_val=aph.strip() if aph.strip() else None
                                    conn.execute("INSERT INTO asha_workers(id,name,phone,facility_id,facility,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?)",(wid,an.strip(),ph_val,u["id"],u["name"],h,s,datetime.now().isoformat()))
                                    conn.commit(); conn.close()
                                    st.success(f"✅ ASHA account created for **{an.strip()}**")
                                    st.info(f"📋 Share these credentials with {an.strip()}:\n\n**Worker ID:** `{wid}`\n\n**Password:** `{pwd}`\n\n*(They log in from the ASHA / ANM Worker portal)*")
            with sc2:
                st.markdown("#### ➕ Add Doctor")
                with st.container(border=True):
                    with st.form("add_doctor_form"):
                        dn=st.text_input("Doctor Full Name",key="new_doc_name",placeholder="e.g. Dr. Priya Sharma")
                        dph=st.text_input("Phone (optional, for contact)",key="new_doc_ph",placeholder="Leave blank if not available")
                        dsp=st.selectbox("Speciality",SPECIALITIES,key="new_doc_spec")
                        if st.form_submit_button("Create Doctor Account",type="primary",use_container_width=True):
                            if not dn.strip(): st.error("Doctor name is required.")
                            elif dph.strip() and not valid_phone(dph.strip()): st.error("Enter a valid 10-digit phone or leave blank.")
                            else:
                                conn=get_conn()
                                # BUG FIX: check name+speciality+facility to prevent duplicates on repeated clicks
                                if conn.execute("SELECT id FROM doctors WHERE name=? AND speciality=? AND facility_id=?",(dn.strip(),dsp,u["id"])).fetchone():
                                    st.error(f"Dr. {dn.strip()} ({dsp}) is already registered at this facility."); conn.close()
                                else:
                                    wid=gen_worker_id("DOC"); pwd=gen_password(); h,s=hash_pw(pwd)
                                    ph_val=dph.strip() if dph.strip() else None
                                    conn.execute("INSERT INTO doctors(id,name,phone,facility_id,facility,speciality,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(wid,dn.strip(),ph_val,u["id"],u["name"],dsp,h,s,datetime.now().isoformat()))
                                    conn.commit(); conn.close()
                                    st.success(f"✅ Doctor account created for **Dr. {dn.strip()}**")
                                    st.info(f"📋 Share these credentials with Dr. {dn.strip()}:\n\n**Worker ID:** `{wid}`\n\n**Password:** `{pwd}`\n\n*(They log in from the Doctor Dashboard portal)*")
            st.divider()
            col_a,col_b=st.columns(2)
            with col_a:
                st.subheader("🚶‍♀️ My ASHA Workers")
                st.dataframe(cdf(qdf("SELECT id,name,phone,created_at FROM asha_workers WHERE facility_id=? ORDER BY name",(u["id"],))),use_container_width=True,hide_index=True)
            with col_b:
                st.subheader("🩺 My Doctors")
                st.dataframe(cdf(qdf("SELECT id,name,phone,speciality,created_at FROM doctors WHERE facility_id=? ORDER BY name",(u["id"],))),use_container_width=True,hide_index=True)

        with ft2:
            st.subheader("💊 Medicine Stock")
            stock=qdf("SELECT id,medicine_name,quantity,unit,last_updated,updated_by FROM medicine_stock WHERE facility_id=? ORDER BY medicine_name",(u["id"],))
            if stock.empty: st.info("No medicines recorded yet.")
            else:
                def hl_stock(row):
                    if row["quantity"]<10: return ["background-color:#ffcdd2;color:black"]*len(row)
                    return [""]*len(row)
                st.dataframe(cdf(stock).style.apply(hl_stock,axis=1),use_container_width=True,hide_index=True)
                st.caption("🔴 Red rows = low stock (below 10 units) — flag for restock request")
            upd_tab,add_tab,log_tab=st.tabs(["📝 Update Stock","➕ Add New Medicine","📜 Change Log"])
            with upd_tab:
                if stock.empty: st.caption("Add a medicine first.")
                else:
                    labels={f"{r['medicine_name']} — Now: {r['quantity']} {r['unit']}":r["id"] for _,r in stock.iterrows()}
                    chosen_label=st.selectbox("Select medicine to update",list(labels.keys()),key="upd_med_sel")
                    chosen_id=labels[chosen_label]
                    mode=st.radio("Action",["➕ Add stock (restock delivery received)","➖ Remove stock (dispensed to patients / damaged)","🔢 Set exact quantity (manual audit correction)"],key="upd_mode_sel")
                    amount=st.number_input("Quantity",min_value=0,value=10,step=1,key="upd_amount_val")
                    if st.button("✅ Apply Update",type="primary",key="upd_apply_btn",use_container_width=True):
                        conn=get_conn(); cur_row=conn.execute("SELECT quantity,medicine_name FROM medicine_stock WHERE id=?",(chosen_id,)).fetchone()
                        cur_qty=cur_row[0]; med_nm=cur_row[1]
                        if "Add" in mode: new_qty=cur_qty+amount; action="Restock received"; change=amount
                        elif "Remove" in mode: new_qty=max(0,cur_qty-amount); action="Dispensed/Damaged"; change=-amount
                        else: new_qty=amount; action="Manual audit correction"; change=amount-cur_qty
                        now_i=datetime.now().isoformat()
                        conn.execute("UPDATE medicine_stock SET quantity=?,last_updated=?,updated_by=? WHERE id=?",(new_qty,now_i,u["name"],chosen_id))
                        conn.execute("INSERT INTO medicine_stock_log VALUES(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),u["id"],u["name"],med_nm,action,change,new_qty,u["name"],now_i))
                        conn.commit(); conn.close(); st.success(f"✅ Updated. New quantity: **{new_qty} units**"); st.rerun()
            with add_tab:
                with st.form("facility_add_med_form"):
                    nm=st.text_input("Medicine name",placeholder="e.g. Amoxicillin 250mg"); nq=st.number_input("Starting quantity",0,value=50); nu=st.selectbox("Unit",["tablets","capsules","vials","sachets","units","bottles","strips"])
                    if st.form_submit_button("➕ Add Medicine",type="primary",use_container_width=True):
                        if not nm.strip(): st.error("Medicine name is required.")
                        else:
                            now_i=datetime.now().isoformat(); conn=get_conn()
                            conn.execute("INSERT INTO medicine_stock(id,facility_id,facility,medicine_name,quantity,unit,last_updated,updated_by) VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),u["id"],u["name"],nm.strip(),nq,nu,now_i,u["name"]))
                            conn.execute("INSERT INTO medicine_stock_log VALUES(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),u["id"],u["name"],nm.strip(),"Initial stock added",nq,nq,u["name"],now_i))
                            conn.commit(); conn.close(); st.success(f"✅ Added **{nm.strip()}** ({nq} {nu})."); st.rerun()
            with log_tab:
                log_df=qdf("SELECT medicine_name,action,change_amount,new_quantity,changed_by,changed_at FROM medicine_stock_log WHERE facility_id=? ORDER BY changed_at DESC LIMIT 30",(u["id"],))
                st.dataframe(cdf(log_df),use_container_width=True,hide_index=True) if not log_df.empty else st.caption("No changes logged yet.")

# ══════════════════════════════════════════════════════════════
# PAGE: DISTRICT ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════
elif page==tr("admin"):
    st.subheader("🏛️ "+tr("admin"))
    active_sos=qdf("SELECT id,patient_name,village,triggered_at FROM sos_alerts WHERE status='ACTIVE' ORDER BY triggered_at DESC")
    if not active_sos.empty:
        st.error(f"🚨 {len(active_sos)} ACTIVE EMERGENCY SOS ALERT(S) — Immediate Action Required")
        for _,s in active_sos.iterrows():
            sc1,sc2=st.columns([4,1])
            sc1.write(f"**{s['patient_name']}** — {s['village'] or '—'} · Triggered: {str(s['triggered_at'])[:16]}")
            if sc2.button("✅ Resolve",key=f"res_{s['id']}",use_container_width=True):
                conn=get_conn(); conn.execute("UPDATE sos_alerts SET status='RESOLVED',resolved_at=?,resolved_by='Admin' WHERE id=?",(datetime.now().isoformat(),s["id"])); conn.commit(); conn.close(); st.rerun()
        st.divider()

    total_p=int(qdf("SELECT COUNT(*) as n FROM patients")["n"][0])
    total_t=int(qdf("SELECT COUNT(*) as n FROM triage")["n"][0])
    total_r=int(qdf("SELECT COUNT(*) as n FROM referrals")["n"][0])
    comp_r=int(qdf("SELECT COUNT(*) as n FROM referrals WHERE status='COMPLETED'")["n"][0])
    comp_rate=round(comp_r/total_r*100,1) if total_r else 0
    pend_fu=int(qdf("SELECT COUNT(*) as n FROM triage WHERE follow_up_due_date IS NOT NULL AND (follow_up_done IS NULL OR follow_up_done=0)")["n"][0])
    pend_appts=int(qdf("SELECT COUNT(*) as n FROM appointments WHERE status='REQUESTED'")["n"][0])
    total_docs=int(qdf("SELECT COUNT(*) as n FROM doctors")["n"][0])
    total_asha=int(qdf("SELECT COUNT(*) as n FROM asha_workers")["n"][0])
    total_fac=int(qdf("SELECT COUNT(*) as n FROM facilities")["n"][0])
    pend_dx=int(qdf("SELECT COUNT(*) as n FROM diagnostics WHERE status='ORDERED'")["n"][0])
    today_str=datetime.now().strftime("%Y-%m-%d")
    waiting_q=int(qdf("SELECT COUNT(*) as n FROM queue_tokens WHERE token_date=? AND status IN ('WAITING','CALLED')",(today_str,))["n"][0])
    false_sos=int(qdf("SELECT COUNT(*) as n FROM sos_alerts WHERE cancelled=1")["n"][0])
    red_cases=int(qdf("SELECT COUNT(*) as n FROM triage WHERE priority='RED'")["n"][0])

    m1,m2,m3,m4=st.columns(4)
    m1.metric("👥 Patients",total_p); m2.metric("🤖 Triages Run",total_t)
    m3.metric("📋 Total Referrals",total_r); m4.metric("✅ Completion Rate",f"{comp_rate}%")
    m5,m6,m7,m8=st.columns(4)
    m5.metric("🔔 Follow-ups Due",pend_fu,"⚠️ action needed" if pend_fu>0 else "")
    m6.metric("📅 Appts Pending",pend_appts)
    m7.metric("🩺 Doctors",total_docs); m8.metric("🚶‍♀️ ASHA Workers",total_asha)
    m9,m10,m11,m12=st.columns(4)
    m9.metric("🏥 Facilities",total_fac); m10.metric("🧪 Diagnostics Pending",pend_dx)
    m11.metric("🎫 Queue Today",waiting_q); m12.metric("🔴 Emergency Cases",red_cases)

    st.divider()
    tab_fac,tab_area,tab_filter=st.tabs(["📊 Facility Analytics","🗺️ Village Risk Map","🔍 Advanced Records Filter"])

    with tab_fac:
        ch1,ch2=st.columns(2)
        with ch1:
            st.subheader("Triage by Priority")
            pr=qdf("SELECT priority,COUNT(*) as count FROM triage GROUP BY priority")
            if not pr.empty: st.bar_chart(pr.set_index("priority"),horizontal=True)
            else: st.info("No triage data yet.")
        with ch2:
            st.subheader("Referrals by Facility")
            rf=qdf("SELECT facility,COUNT(*) as count FROM referrals GROUP BY facility")
            if not rf.empty: st.bar_chart(rf.set_index("facility"),horizontal=True)
            else: st.info("No referral data yet.")
        ch3,ch4=st.columns(2)
        with ch3:
            st.subheader("Department-wise Case Load")
            dp=qdf("SELECT department,COUNT(*) as count FROM triage WHERE department IS NOT NULL GROUP BY department ORDER BY count DESC")
            if not dp.empty: st.bar_chart(dp.set_index("department"),horizontal=True)
        with ch4:
            st.subheader("Appointment Status Breakdown")
            ap=qdf("SELECT status,COUNT(*) as count FROM appointments GROUP BY status")
            if not ap.empty: st.bar_chart(ap.set_index("status"),horizontal=True)
        st.divider()
        st.subheader("🏥 Facility Quality Scorecard")
        st.caption("Auto-calculated from referral completion rate, low-stock items, and turnaround speed. Meant to identify which facilities need support.")
        fac_dir=qdf("SELECT id,name,type,village FROM facilities ORDER BY name")
        if fac_dir.empty: st.info("No facilities registered yet.")
        else:
            rows=[]
            for _,f in fac_dir.iterrows():
                fname=f["name"]
                ref=qdf("SELECT status,created_at,completed_at FROM referrals WHERE facility=?",(fname,))
                total_ref=len(ref); crate=0.0; avg_hrs=None
                if total_ref:
                    done=ref[ref["status"]=="COMPLETED"].copy(); crate=len(done)/total_ref*100
                    if not done.empty:
                        done["ca"]=pd.to_datetime(done["created_at"],errors="coerce")
                        done["co"]=pd.to_datetime(done["completed_at"],errors="coerce")
                        hrs=(done["co"]-done["ca"]).dt.total_seconds()/3600; hrs=hrs.dropna()
                        if not hrs.empty: avg_hrs=hrs.mean()
                low_n=int(qdf("SELECT COUNT(*) as n FROM medicine_stock WHERE facility=? AND quantity<10",(fname,))["n"][0])
                score=crate-min(low_n*4,30)
                if avg_hrs is not None: score-=min(avg_hrs/24*5,25)
                score=max(0,min(100,round(score)))
                rows.append({"Facility":fname,"Type":f["type"],"Area":f["village"] or "—",
                             "Referrals":total_ref,"Completion%":round(crate,1),
                             "Avg Turnaround (hrs)":round(avg_hrs,1) if avg_hrs else "—",
                             "Low Stock Items":low_n,"Quality Score":score})
            qdf_fac=pd.DataFrame(rows).sort_values("Quality Score",ascending=False)
            def _qc(row):
                s=row["Quality Score"]
                bg="#c8e6c9" if s>=80 else "#fff59d" if s>=50 else "#ffcdd2"
                return [f"background-color:{bg};color:#000"]*len(row)
            st.dataframe(cdf(qdf_fac).style.apply(_qc,axis=1),use_container_width=True,hide_index=True)

    with tab_area:
        st.subheader("🗺️ Village-level Risk Map")
        st.caption("Auto-coloured by risk level. Villages with RED cases are flagged for priority resource deployment.")
        vdf=qdf("""SELECT p.village,COUNT(DISTINCT p.abha_id) as patients,
                    SUM(CASE WHEN t.priority='RED' THEN 1 ELSE 0 END) as red_cases,
                    SUM(CASE WHEN t.priority='YELLOW' THEN 1 ELSE 0 END) as yellow_cases,
                    SUM(CASE WHEN t.priority='GREEN' THEN 1 ELSE 0 END) as green_cases
                    FROM patients p LEFT JOIN triage t ON t.abha_id=p.abha_id
                    WHERE p.village IS NOT NULL AND p.village!='' GROUP BY p.village ORDER BY red_cases DESC,patients DESC""")
        if vdf.empty: st.info("No village-linked patient records yet.")
        else:
            vdf["risk_score"]=vdf["red_cases"]*3+vdf["yellow_cases"]
            def _risk(row):
                if row["red_cases"]>=2 or row["risk_score"]>=6: return "🔴 Critical"
                if row["red_cases"]>=1 or row["risk_score"]>=3: return "🟠 High"
                if row["yellow_cases"]>=1: return "🟡 Moderate"
                return "🟢 Low"
            vdf["Risk Level"]=vdf.apply(_risk,axis=1); vdf=vdf.sort_values("risk_score",ascending=False)
            def _rc(row):
                lvl=row["Risk Level"]
                bg="#ff8a80" if "Critical" in lvl else "#ffcc80" if "High" in lvl else "#fff59d" if "Moderate" in lvl else "#c8e6c9"
                return [f"background-color:{bg};color:#000"]*len(row)
            disp=["village","Risk Level","patients","red_cases","yellow_cases","green_cases"]
            st.dataframe(cdf(vdf[disp]).style.apply(_rc,axis=1),use_container_width=True,hide_index=True)
            st.bar_chart(vdf.set_index("village")[["red_cases","yellow_cases","green_cases"]])
            st.divider()
            st.markdown("#### 🔍 Drill into a Single Village")
            opts=["— Select a village —"]+vdf["village"].tolist()
            pv=st.selectbox("Village",opts,key="area_v",label_visibility="collapsed")
            if pv!="— Select a village —":
                rv=vdf[vdf["village"]==pv].iloc[0]
                vc1,vc2,vc3,vc4,vc5=st.columns(5)
                vc1.metric("Risk",rv["Risk Level"]); vc2.metric("Patients",int(rv["patients"]))
                vc3.metric("🔴 RED",int(rv["red_cases"])); vc4.metric("🟡 YELLOW",int(rv["yellow_cases"])); vc5.metric("🟢 GREEN",int(rv["green_cases"]))
                cases=qdf("SELECT p.name,p.age,t.priority,t.department,t.symptoms_text,t.created_at,r.facility,r.status as ref_status FROM triage t JOIN patients p ON p.abha_id=t.abha_id LEFT JOIN referrals r ON r.triage_id=t.id WHERE p.village=? ORDER BY CASE t.priority WHEN 'RED' THEN 0 WHEN 'YELLOW' THEN 1 ELSE 2 END,t.created_at DESC",(pv,))
                st.markdown(f"**{len(cases)} case record(s) in {pv}**")
                if not cases.empty:
                    def _prc(row):
                        c={"RED":"#ffcdd2","YELLOW":"#fff3cd","GREEN":"#d4edda"}.get(row["priority"],"")
                        return [f"background-color:{c};color:#000" if c else ""]*len(row)
                    st.dataframe(cdf(cases).style.apply(_prc,axis=1),use_container_width=True,hide_index=True)

    with tab_filter:
        st.subheader("🔍 Advanced Patient Records Filter")
        with st.container(border=True):
            facs_f=["All"]+get_facility_names(); vils_f=["All"]+get_village_names()
            f0,f1,f2,f3=st.columns(4)
            vf=f0.selectbox("Village / Area",vils_f,key="af_vil")
            facf=f1.selectbox("Facility",facs_f,key="af_fac")
            prf=f2.selectbox("Priority",["All","RED","YELLOW","GREEN"],key="af_pri")
            deptf=f3.selectbox("Department",["All"]+[d for d,_ in DEPT_KW]+["General Medicine"],key="af_dept")
            sortf=st.selectbox("Sort by",["Date (newest first)","Date (oldest first)","Priority (urgent first)","Village A-Z"],key="af_sort")
            symf=st.text_input("🔎 Symptom keyword search",placeholder="e.g. fever, chest pain (type 2+ characters)",key="af_sym")
            sql="""SELECT p.name,p.village,t.priority,t.department,t.symptoms_text,
                          t.temperature,t.spo2,t.pulse,t.created_at,r.facility,r.status as ref_status
                   FROM triage t JOIN patients p ON p.abha_id=t.abha_id
                   LEFT JOIN referrals r ON r.triage_id=t.id WHERE 1=1"""
            params=[]
            if vf!="All": sql+=" AND p.village=?"; params.append(vf)
            if facf!="All": sql+=" AND r.facility=?"; params.append(facf)
            if prf!="All": sql+=" AND t.priority=?"; params.append(prf)
            if deptf!="All": sql+=" AND t.department=?"; params.append(deptf)
            if symf and len(symf.strip())>=2: sql+=" AND t.symptoms_text LIKE ?"; params.append(f"%{symf}%")
            sm={"Date (newest first)":"t.created_at DESC","Date (oldest first)":"t.created_at ASC","Priority (urgent first)":"CASE t.priority WHEN 'RED' THEN 0 WHEN 'YELLOW' THEN 1 ELSE 2 END","Village A-Z":"p.village"}
            sql+=f" ORDER BY {sm[sortf]}"
            adf=qdf(sql,tuple(params))
            st.caption(f"📊 {len(adf)} record(s) found")
            if not adf.empty:
                def _prc2(row):
                    c={"RED":"#ffcdd2","YELLOW":"#fff3cd","GREEN":"#d4edda"}.get(row["priority"],"")
                    return [f"background-color:{c};color:#000" if c else ""]*len(row)
                st.dataframe(cdf(adf).style.apply(_prc2,axis=1),use_container_width=True,hide_index=True)

    st.divider()
    st.subheader("⚠️ Symptom Outbreak Signal — Last 20 Triages")
    st.caption("Watch for repeated keywords across villages — early indicator of localised outbreaks.")
    st.dataframe(cdf(qdf("SELECT symptoms_text,priority,department,created_at FROM triage ORDER BY created_at DESC LIMIT 20")),use_container_width=True,hide_index=True)
    st.divider()
    st.subheader("💊 System-wide Low Stock Alerts")
    low=qdf("SELECT facility,medicine_name,quantity,unit FROM medicine_stock WHERE quantity<10 ORDER BY quantity ASC")
    if low.empty: st.success("✅ No low-stock alerts across any facility.")
    else: st.dataframe(cdf(low),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════
# PAGE: MEDICINE AVAILABILITY (public read-only)
# ══════════════════════════════════════════════════════════════
elif page==tr("medicine"):
    st.subheader("💊 "+tr("medicine"))
    st.caption("Public, searchable view — anyone can check medicine availability before travelling to a facility. To update stock levels, log in through the Facility portal.")
    facs=["All"]+get_facility_names(); s1,s2=st.columns(2)
    facf=s1.selectbox("Filter by Facility",facs,key="med_fac_f"); msearch=s2.text_input("Search medicine name",key="med_search",placeholder="e.g. Paracetamol, ORS...")
    sql="SELECT facility,medicine_name,quantity,unit,last_updated FROM medicine_stock WHERE 1=1"; params=[]
    if facf!="All": sql+=" AND facility=?"; params.append(facf)
    if msearch: sql+=" AND medicine_name LIKE ?"; params.append(f"%{msearch}%")
    sql+=" ORDER BY facility,medicine_name"; stock=qdf(sql,tuple(params))
    def hl_med(row):
        if row["quantity"]<10: return ["background-color:#ffcdd2;color:black"]*len(row)
        return [""]*len(row)
    if stock.empty: st.info("No medicines found matching your search.")
    else:
        st.dataframe(cdf(stock).style.apply(hl_med,axis=1),use_container_width=True,hide_index=True)
        st.caption("🔴 Red rows = low stock (below 10 units) — may not be available. Call the facility before travelling.")
        low_count=len(stock[stock["quantity"]<10])
        if low_count>0: st.warning(f"⚠️ {low_count} medicine(s) are low on stock — flagged for supply chain reorder.")
        else: st.success("✅ All displayed medicines are adequately stocked.")
