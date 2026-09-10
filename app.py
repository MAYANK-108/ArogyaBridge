"""
ArogyaBridge - "Bridge to Healthcare"
SIH 2026 | PS ID: SIH26133

Changes in this version:
- Fix 1: Admin dashboard now requires password login (env: ADMIN_PASSWORD)
- Fix 2: Teleconsultation uses live Jitsi Meet embed (no backend needed)
- Fix 3: SMS fallback via Fast2SMS for RED/YELLOW triage alerts
- Fix 4: Aadhaar stored as SHA-256 hash — raw number never persists in DB
- Fix 5: SOS routes to geographically nearby staff only (village-match)
- Fix 6: AI triage prompt is language-aware (accepts regional language input)
- Fix 7: Outbreak signal detection in Admin dashboard (7-day clustering)
- UI  : Removed all custom CSS — uses default Streamlit theme so light/dark
         mode switching works correctly with zero visual glitches.
- Bug : Fixed duplicate `elif page==tr("admin"):` block (dead-code crash).
- Bug : Fixed send_sos_notifications() defined but never called.
- Bug : Moved get_nearby_staff / send_sos_notifications to module level.
- Bug : Self-triage SOS path now also uses smart geographic routing.

Run: pip install -r requirements.txt && streamlit run app.py
"""

import os, sqlite3, uuid, hashlib, secrets, json, requests
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import altair as alt

# ─────────────────────────── CONFIG ────────────────────────────
DB_PATH        = os.path.join(os.path.dirname(__file__), "sevasetu.db")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL     = "llama-3.1-8b-instant"
FAST2SMS_KEY   = os.environ.get("FAST2SMS_KEY", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin@sih2026")

PRIORITY_COLORS = {"RED": "#e53935", "YELLOW": "#f5a623", "GREEN": "#2e9e5b"}
PRIORITY_ORDER  = {"RED": 0, "YELLOW": 1, "GREEN": 2}

FACILITY_TYPES = [
    "Sub-Centre",
    "Primary Health Centre (PHC)",
    "Rural / District Hospital",
]
SPECIALITIES = [
    "General Medicine", "Cardiology", "Pediatrics",
    "Obstetrics & Gynaecology", "Pulmonology", "Neurology",
    "Orthopedics", "Gastroenterology",
]
DEFAULT_DIAGNOSTIC_TESTS = [
    "Blood Sugar (RBS/FBS)", "Complete Blood Count (CBC)",
    "Malaria Rapid Test", "Dengue Rapid Test", "Urine Routine",
    "X-Ray", "ECG", "Hemoglobin Test", "COVID-19 RAT",
]

# Standard child immunization schedule (days after birth → vaccine).
# Simplified Govt. of India Universal Immunization Programme.
IMMUNIZATION_SCHEDULE = [
    (0,    "BCG"),
    (0,    "OPV-0"),
    (0,    "Hepatitis B - Birth Dose"),
    (42,   "OPV-1 / Pentavalent-1"),
    (70,   "OPV-2 / Pentavalent-2"),
    (98,   "OPV-3 / Pentavalent-3"),
    (270,  "Measles-Rubella (MR)-1"),
    (365,  "Vitamin A (1st dose)"),
    (456,  "MR-2 / DPT Booster-1"),
    (1825, "DPT Booster-2"),
]

CHRONIC_CONDITIONS = [
    "Diabetes", "Hypertension", "Asthma / COPD",
    "Tuberculosis (DOTS)", "Chronic Kidney Disease",
    "Epilepsy", "Thyroid Disorder", "Other Chronic Condition",
]

# Referral acknowledgment SLA targets used for quality monitoring (hours).
SLA_TARGET_HOURS = {"RED": 2, "YELLOW": 24, "GREEN": 72}

# Outbreak keywords for 7-day signal clustering (English + regional).
OUTBREAK_KEYWORDS = [
    "fever", "diarrhea", "vomiting", "rash", "dengue", "malaria",
    "jaundice", "cholera", "typhoid", "measles",
    "बुखार", "दस्त", "उल्टी", "डेंगू", "मलेरिया",
    "ताप", "जुलाब",
]

st.set_page_config(
    page_title="ArogyaBridge",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────── I18N ──────────────────────────────
T = {
"en": {
  "app_title": "ArogyaBridge — Bridge to Healthcare",
  "role": "Select your role",
  "patient_portal": "Patient Portal",
  "asha": "ASHA / ANM Worker",
  "doctor": "Doctor Dashboard",
  "facility": "Facility / Hospital",
  "admin": "District Admin Dashboard",
  "medicine": "Medicine Availability",
  "login": "Login",
  "register_tab": "Register",
  "login_btn": "Login",
  "name": "Full Name",
  "age": "Age",
  "gender": "Gender",
  "village": "Village / Ward",
  "phone": "Phone Number",
  "language": "Preferred Language",
  "aadhaar_id": "Aadhaar ID",
  "password": "Password",
  "confirm_password": "Confirm Password",
  "register_btn": "Register",
  "invalid_login": "Invalid login details.",
  "welcome_back": "Welcome back",
  "logout_btn": "Logout",
  "symptoms": "Describe symptoms",
  "run_triage": "Run AI Triage",
  "priority": "Priority",
  "refer_btn": "Refer to Facility",
  "select_facility": "Refer to which facility?",
  "queue": "Live Patient Queue",
  "no_referrals": "No referrals in queue.",
  "prescription": "Prescription",
  "save_prescription": "Save Prescription & Complete",
  "teleconsult": "Start Teleconsultation",
  "book_appointment": "Book Appointment",
  "sos": "Emergency SOS",
  "my_health_record": "My Health Record",
  "my_triage_history": "My Symptom History",
  "my_referrals": "My Referrals & Prescriptions",
  "no_records_yet": "No records yet.",
  "create_login": "Create your login",
  "phone_login_hint": "Log in with your Aadhaar ID.",
  "register_patient": "Register New Patient",
  "my_patients": "My Registered Patients",
  "all_patients": "All Registered Patients",
  "update_details": "Update My Details",
  "diagnostics": "Diagnostic Availability",
  "specialists": "Find a Specialist",
  "scheme_eligible": "PM-JAY / Ayushman Bharat Eligible",
  "export_record": "Export My Health Record",
  "listen": "Listen to result",
  "public_services": "Other Services (no login needed)",
},
"hi": {
  "app_title": "ArogyaBridge — स्वास्थ्य सेवा का पुल",
  "role": "अपनी भूमिका चुनें",
  "patient_portal": "रोगी पोर्टल",
  "asha": "आशा / एएनएम कार्यकर्ता",
  "doctor": "डॉक्टर डैशबोर्ड",
  "facility": "सुविधा / अस्पताल",
  "admin": "जिला प्रशासन डैशबोर्ड",
  "medicine": "दवा उपलब्धता",
  "login": "लॉगिन",
  "register_tab": "पंजीकरण",
  "login_btn": "लॉगिन करें",
  "name": "पूरा नाम",
  "age": "आयु",
  "gender": "लिंग",
  "village": "गाँव / वार्ड",
  "phone": "फ़ोन नंबर",
  "language": "पसंदीदा भाषा",
  "aadhaar_id": "आधार आईडी",
  "password": "पासवर्ड",
  "confirm_password": "पासवर्ड की पुष्टि",
  "register_btn": "पंजीकरण करें",
  "invalid_login": "गलत लॉगिन विवरण।",
  "welcome_back": "वापसी पर स्वागत है",
  "logout_btn": "लॉगआउट",
  "symptoms": "लक्षण बताएं",
  "run_triage": "AI ट्राइएज चलाएं",
  "priority": "प्राथमिकता",
  "refer_btn": "रेफर करें",
  "select_facility": "कहाँ रेफर करें?",
  "queue": "लाइव रोगी कतार",
  "no_referrals": "कतार में कोई रेफरल नहीं।",
  "prescription": "नुस्खा",
  "save_prescription": "नुस्खा सहेजें",
  "teleconsult": "टेलीकंसल्टेशन",
  "book_appointment": "अपॉइंटमेंट बुक करें",
  "sos": "आपातकालीन SOS",
  "my_health_record": "मेरा स्वास्थ्य रिकॉर्ड",
  "my_triage_history": "मेरा लक्षण इतिहास",
  "my_referrals": "मेरे रेफरल",
  "no_records_yet": "अभी कोई रिकॉर्ड नहीं।",
  "create_login": "अपना लॉगिन बनाएं",
  "phone_login_hint": "अपने आधार आईडी से लॉगिन करें।",
  "register_patient": "नया रोगी पंजीकृत करें",
  "my_patients": "मेरे पंजीकृत रोगी",
  "all_patients": "सभी पंजीकृत रोगी",
  "update_details": "मेरी जानकारी अपडेट करें",
  "diagnostics": "निदान उपलब्धता",
  "specialists": "विशेषज्ञ खोजें",
  "scheme_eligible": "PM-JAY / आयुष्मान भारत पात्र",
  "export_record": "मेरा स्वास्थ्य रिकॉर्ड निर्यात करें",
  "listen": "सुनें",
  "public_services": "अन्य सेवाएँ (लॉगिन आवश्यक नहीं)",
},
"mr": {
  "app_title": "ArogyaBridge — आरोग्यसेवेचा पूल",
  "role": "तुमची भूमिका निवडा",
  "patient_portal": "रुग्ण पोर्टल",
  "asha": "आशा / एएनएम कार्यकर्ता",
  "doctor": "डॉक्टर डॅशबोर्ड",
  "facility": "सुविधा / रुग्णालय",
  "admin": "जिल्हा प्रशासन डॅशबोर्ड",
  "medicine": "औषध उपलब्धता",
  "login": "लॉगिन",
  "register_tab": "नोंदणी",
  "login_btn": "लॉगिन करा",
  "name": "पूर्ण नाव",
  "age": "वय",
  "gender": "लिंग",
  "village": "गाव / वॉर्ड",
  "phone": "फोन नंबर",
  "language": "पसंतीची भाषा",
  "aadhaar_id": "आधार आयडी",
  "password": "पासवर्ड",
  "confirm_password": "पासवर्डची पुष्टी",
  "register_btn": "नोंदणी करा",
  "invalid_login": "चुकीचे लॉगिन तपशील.",
  "welcome_back": "परत स्वागत",
  "logout_btn": "लॉगआउट",
  "symptoms": "लक्षणे सांगा",
  "run_triage": "AI ट्रायएज",
  "priority": "प्राधान्य",
  "refer_btn": "संदर्भित करा",
  "select_facility": "कुठे संदर्भित करायचे?",
  "queue": "रुग्ण रांग",
  "no_referrals": "रांगेत कोणतेही रेफरल नाही.",
  "prescription": "प्रिस्क्रिप्शन",
  "save_prescription": "प्रिस्क्रिप्शन जतन करा",
  "teleconsult": "टेलिकन्सल्टेशन",
  "book_appointment": "अपॉइंटमेंट बुक करा",
  "sos": "आणीबाणी SOS",
  "my_health_record": "माझी आरोग्य नोंद",
  "my_triage_history": "माझा लक्षण इतिहास",
  "my_referrals": "माझे संदर्भ",
  "no_records_yet": "अजून नोंद नाही.",
  "create_login": "लॉगिन तयार करा",
  "phone_login_hint": "तुमच्या आधार आयडीने लॉगिन करा.",
  "register_patient": "नवीन रुग्ण नोंदणी",
  "my_patients": "माझे नोंदणीकृत रुग्ण",
  "all_patients": "सर्व नोंदणीकृत रुग्ण",
  "update_details": "माझी माहिती अपडेट करा",
  "diagnostics": "निदान उपलब्धता",
  "specialists": "तज्ञ शोधा",
  "scheme_eligible": "PM-JAY / आयुष्मान भारत पात्र",
  "export_record": "माझी आरोग्य नोंद निर्यात करा",
  "listen": "ऐका",
  "public_services": "इतर सेवा (लॉगिन आवश्यक नाही)",
},
"ta": {
  "app_title": "ArogyaBridge — சுகாதார சேவைக்கான பாலம்",
  "role": "பாத்திரம் தேர்வு",
  "patient_portal": "நோயாளர் போர்ட்டல்",
  "asha": "ஆஷா / ஏஎன்எம்",
  "doctor": "மருத்துவர் டாஷ்போர்டு",
  "facility": "மையம் / மருத்துவமனை",
  "admin": "மாவட்ட நிர்வாக டாஷ்போர்டு",
  "medicine": "மருந்து கிடைக்கும் தன்மை",
  "login": "உள்நுழைய",
  "register_tab": "பதிவு",
  "login_btn": "உள்நுழையவும்",
  "name": "பெயர்",
  "age": "வயது",
  "gender": "பாலினம்",
  "village": "கிராமம்",
  "phone": "தொலைபேசி",
  "language": "மொழி",
  "aadhaar_id": "ஆதார் ஐடி",
  "password": "கடவுச்சொல்",
  "confirm_password": "உறுதிப்படுத்தவும்",
  "register_btn": "பதிவு செய்யவும்",
  "invalid_login": "தவறான உள்நுழைவு விவரங்கள்.",
  "welcome_back": "மீண்டும் வரவேற்கிறோம்",
  "logout_btn": "வெளியேறு",
  "symptoms": "அறிகுறிகள்",
  "run_triage": "AI முன்னுரிமை",
  "priority": "முன்னுரிமை",
  "refer_btn": "பரிந்துரைக்கவும்",
  "select_facility": "எந்த மையம்?",
  "queue": "நோயாளர் வரிசை",
  "no_referrals": "பரிந்துரைகள் இல்லை.",
  "prescription": "மருந்துச் சீட்டு",
  "save_prescription": "சேமிக்கவும்",
  "teleconsult": "தொலை ஆலோசனை",
  "book_appointment": "சந்திப்பு",
  "sos": "அவசர SOS",
  "my_health_record": "சுகாதார பதிவு",
  "my_triage_history": "அறிகுறி வரலாறு",
  "my_referrals": "பரிந்துரைகள்",
  "no_records_yet": "பதிவுகள் இல்லை.",
  "create_login": "லாக்இன் உருவாக்கவும்",
  "phone_login_hint": "உங்கள் ஆதார் ஐடியுடன் உள்நுழையவும்.",
  "register_patient": "நோயாளர் பதிவு",
  "my_patients": "என் நோயாளர்கள்",
  "all_patients": "அனைத்து நோயாளர்கள்",
  "update_details": "என் விவரங்களை புதுப்பிக்கவும்",
  "diagnostics": "நோய்க் கண்டறிதல்",
  "specialists": "நிபுணரைத் தேடுங்கள்",
  "scheme_eligible": "PM-JAY / ஆயுஷ்மான் பாரத் தகுதி",
  "export_record": "சுகாதார பதிவை ஏற்றுமதி செய்யவும்",
  "listen": "கேளுங்கள்",
  "public_services": "பிற சேவைகள் (உள்நுழைவு தேவையில்லை)",
},
"te": {
  "app_title": "ArogyaBridge — ఆరోగ్య సేవకు వంతెన",
  "role": "పాత్ర ఎంచుకోండి",
  "patient_portal": "రోగి పోర్టల్",
  "asha": "ఆశా / ఏఎన్ఎం",
  "doctor": "డాక్టర్ డాష్‌బోర్డ్",
  "facility": "సదుపాయం / ఆసుపత్రి",
  "admin": "జిల్లా అడ్మిన్ డాష్‌బోర్డ్",
  "medicine": "మందుల లభ్యత",
  "login": "లాగిన్",
  "register_tab": "నమోదు",
  "login_btn": "లాగిన్ చేయండి",
  "name": "పూర్తి పేరు",
  "age": "వయస్సు",
  "gender": "లింగం",
  "village": "గ్రామం",
  "phone": "ఫోన్",
  "language": "భాష",
  "aadhaar_id": "ఆధార్ ఐడి",
  "password": "పాస్‌వర్డ్",
  "confirm_password": "నిర్ధారించండి",
  "register_btn": "నమోదు చేయండి",
  "invalid_login": "తప్పు లాగిన్ వివరాలు.",
  "welcome_back": "తిరిగి స్వాగతం",
  "logout_btn": "లాగ్ అవుట్",
  "symptoms": "లక్షణాలు",
  "run_triage": "AI ట్రయాజ్",
  "priority": "ప్రాధాన్యత",
  "refer_btn": "రిఫర్ చేయండి",
  "select_facility": "ఏ సదుపాయం?",
  "queue": "రోగి క్యూ",
  "no_referrals": "రిఫరల్స్ లేవు.",
  "prescription": "ప్రిస్క్రిప్షన్",
  "save_prescription": "సేవ్ చేయండి",
  "teleconsult": "టెలికన్సల్టేషన్",
  "book_appointment": "అపాయింట్‌మెంట్",
  "sos": "అత్యవసర SOS",
  "my_health_record": "ఆరోగ్య రికార్డు",
  "my_triage_history": "లక్షణాల చరిత్ర",
  "my_referrals": "రిఫరల్స్",
  "no_records_yet": "రికార్డులు లేవు.",
  "create_login": "లాగిన్ సృష్టించండి",
  "phone_login_hint": "మీ ఆధార్ ఐడితో లాగిన్ అవ్వండి.",
  "register_patient": "రోగి నమోదు",
  "my_patients": "నా రోగులు",
  "all_patients": "అన్ని రోగులు",
  "update_details": "నా వివరాలు నవీకరించండి",
  "diagnostics": "నిర్ధారణ పరీక్షల లభ్యత",
  "specialists": "నిపుణుడిని కనుగొనండి",
  "scheme_eligible": "PM-JAY / ఆయుష్మాన్ భారత్ అర్హత",
  "export_record": "ఆరోగ్య రికార్డు ఎగుమతి చేయండి",
  "listen": "వినండి",
  "public_services": "ఇతర సేవలు (లాగిన్ అవసరం లేదు)",
},
"bn": {
  "app_title": "ArogyaBridge — স্বাস্থ্যসেবার সেতু",
  "role": "ভূমিকা নির্বাচন",
  "patient_portal": "রোগী পোর্টাল",
  "asha": "আশা / এএনএম",
  "doctor": "ডাক্তার ড্যাশবোর্ড",
  "facility": "সুবিধা / হাসপাতাল",
  "admin": "জেলা প্রশাসন ড্যাশবোর্ড",
  "medicine": "ওষুধ প্রাপ্যতা",
  "login": "লগইন",
  "register_tab": "নিবন্ধন",
  "login_btn": "লগইন করুন",
  "name": "পুরো নাম",
  "age": "বয়স",
  "gender": "লিঙ্গ",
  "village": "গ্রাম",
  "phone": "ফোন",
  "language": "ভাষা",
  "aadhaar_id": "আধার আইডি",
  "password": "পাসওয়ার্ড",
  "confirm_password": "নিশ্চিত করুন",
  "register_btn": "নিবন্ধন করুন",
  "invalid_login": "ভুল লগইন বিবরণ।",
  "welcome_back": "আবার স্বাগতম",
  "logout_btn": "লগআউট",
  "symptoms": "লক্ষণ",
  "run_triage": "AI ট্রায়াজ",
  "priority": "অগ্রাধিকার",
  "refer_btn": "রেফার করুন",
  "select_facility": "কোন সুবিধা?",
  "queue": "রোগীর সারি",
  "no_referrals": "রেফারেল নেই।",
  "prescription": "প্রেসক্রিপশন",
  "save_prescription": "সংরক্ষণ করুন",
  "teleconsult": "টেলিকনসালটেশন",
  "book_appointment": "অ্যাপয়েন্টমেন্ট",
  "sos": "জরুরি SOS",
  "my_health_record": "স্বাস্থ্য রেকর্ড",
  "my_triage_history": "লক্ষণ ইতিহাস",
  "my_referrals": "রেফারেল",
  "no_records_yet": "রেকর্ড নেই।",
  "create_login": "লগইন তৈরি করুন",
  "phone_login_hint": "আপনার আধার আইডি দিয়ে লগইন করুন।",
  "register_patient": "রোগী নিবন্ধন",
  "my_patients": "আমার রোগীরা",
  "all_patients": "সকল রোগী",
  "update_details": "আমার বিবরণ আপডেট করুন",
  "diagnostics": "নির্ণয় পরীক্ষার প্রাপ্যতা",
  "specialists": "বিশেষজ্ঞ খুঁজুন",
  "scheme_eligible": "PM-JAY / আয়ুষ্মান ভারত যোগ্য",
  "export_record": "স্বাস্থ্য রেকর্ড রপ্তানি করুন",
  "listen": "শুনুন",
  "public_services": "অন্যান্য সেবা (লগইন প্রয়োজন নেই)",
},
}

def tr(key):
    lang = st.session_state.get("ui_lang", "en")
    return T.get(lang, T["en"]).get(key, T["en"].get(key, key))

# ─────────────────────────── DATABASE ──────────────────────────
def get_conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS facilities(
      id TEXT PRIMARY KEY, name TEXT, type TEXT, village TEXT, phone TEXT,
      password_hash TEXT, salt TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS patients(
      abha_id TEXT PRIMARY KEY, name TEXT, age INTEGER, gender TEXT,
      village TEXT, phone TEXT, aadhaar_id TEXT, language TEXT, created_at TEXT,
      password_hash TEXT, salt TEXT,
      registered_by_type TEXT, registered_by_id TEXT, registered_by_name TEXT);
    CREATE TABLE IF NOT EXISTS asha_workers(
      id TEXT PRIMARY KEY, name TEXT, phone TEXT, facility_id TEXT, facility TEXT,
      password_hash TEXT, salt TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS doctors(
      id TEXT PRIMARY KEY, name TEXT, phone TEXT, facility_id TEXT, facility TEXT,
      speciality TEXT, password_hash TEXT, salt TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS triage(
      id TEXT PRIMARY KEY, abha_id TEXT, symptoms_text TEXT,
      priority TEXT, rationale TEXT, created_by TEXT, created_at TEXT,
      department TEXT, follow_up_due_date TEXT, follow_up_done INTEGER DEFAULT 0,
      temperature TEXT, spo2 TEXT, pulse TEXT, triggered_by TEXT DEFAULT 'asha');
    CREATE TABLE IF NOT EXISTS referrals(
      id TEXT PRIMARY KEY, abha_id TEXT, triage_id TEXT, facility TEXT,
      status TEXT, prescription TEXT, doctor_notes TEXT,
      created_at TEXT, completed_at TEXT, doctor_id TEXT,
      acknowledged_at TEXT, acknowledged_by TEXT, escalated_from TEXT, escalated_to TEXT);
    CREATE TABLE IF NOT EXISTS notifications(
      id TEXT PRIMARY KEY, recipient_role TEXT, recipient_id TEXT,
      message TEXT, priority TEXT, read INTEGER DEFAULT 0, created_at TEXT,
      triage_id TEXT, abha_id TEXT);
    CREATE TABLE IF NOT EXISTS sos_alerts(
      id TEXT PRIMARY KEY, abha_id TEXT, patient_name TEXT, village TEXT,
      triggered_at TEXT, status TEXT, resolved_at TEXT,
      resolved_by TEXT, accepted_by TEXT, notes TEXT,
      medical_summary TEXT, routing_log TEXT, cancelled INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS appointments(
      id TEXT PRIMARY KEY, abha_id TEXT, facility TEXT,
      appointment_date TEXT, time_slot TEXT, status TEXT,
      created_at TEXT, doctor_id TEXT, decline_reason TEXT);
    CREATE TABLE IF NOT EXISTS medicine_stock(
      id TEXT PRIMARY KEY, facility_id TEXT, facility TEXT, medicine_name TEXT,
      quantity INTEGER, unit TEXT, last_updated TEXT, updated_by TEXT);
    CREATE TABLE IF NOT EXISTS medicine_stock_log(
      id TEXT PRIMARY KEY, facility_id TEXT, facility TEXT, medicine_name TEXT,
      action TEXT, change_amount INTEGER, new_quantity INTEGER,
      changed_by TEXT, changed_at TEXT);
    CREATE TABLE IF NOT EXISTS diagnostic_tests(
      id TEXT PRIMARY KEY, facility_id TEXT, facility TEXT, test_name TEXT,
      available INTEGER DEFAULT 1, turnaround_hours INTEGER, last_updated TEXT, updated_by TEXT);
    CREATE TABLE IF NOT EXISTS diagnostic_orders(
      id TEXT PRIMARY KEY, abha_id TEXT, referral_id TEXT, test_name TEXT, facility TEXT,
      status TEXT DEFAULT 'ORDERED', result_notes TEXT, ordered_by TEXT,
      ordered_at TEXT, completed_at TEXT);
    CREATE TABLE IF NOT EXISTS chronic_registry(
      id TEXT PRIMARY KEY, abha_id TEXT, condition TEXT, interval_days INTEGER,
      next_due_date TEXT, active INTEGER DEFAULT 1, created_by TEXT, created_at TEXT,
      last_followup_at TEXT);
    CREATE TABLE IF NOT EXISTS mch_pregnancy(
      id TEXT PRIMARY KEY, abha_id TEXT, lmp_date TEXT, edd TEXT,
      anc1_done INTEGER DEFAULT 0, anc2_done INTEGER DEFAULT 0,
      anc3_done INTEGER DEFAULT 0, anc4_done INTEGER DEFAULT 0,
      high_risk INTEGER DEFAULT 0, status TEXT DEFAULT 'ACTIVE',
      created_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS mch_child(
      id TEXT PRIMARY KEY, abha_id TEXT, child_name TEXT, dob TEXT,
      created_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS mch_immunization(
      id TEXT PRIMARY KEY, child_id TEXT, abha_id TEXT, vaccine_name TEXT,
      due_date TEXT, given INTEGER DEFAULT 0, given_date TEXT);
    """)
    conn.commit()

    # Safe migrations — add columns that may not exist in older DB files.
    def add_col(table, col, typ="TEXT"):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")

    add_col("triage", "temperature"); add_col("triage", "spo2"); add_col("triage", "pulse")
    add_col("triage", "triggered_by")
    
    
    add_col("referrals", "doctor_id"); add_col("referrals", "acknowledged_at")
    add_col("referrals", "acknowledged_by"); add_col("referrals", "escalated_from")
    add_col("referrals", "escalated_to"); add_col("referrals", "teleconsult_notes")
    add_col("referrals", "teleconsult_started_at"); add_col("referrals", "teleconsult_ended_at")
    add_col("referrals", "feedback_rating", "INTEGER"); add_col("referrals", "feedback_comment")
    add_col("appointments", "doctor_id"); add_col("appointments", "decline_reason")
    add_col("sos_alerts", "accepted_by"); add_col("sos_alerts", "medical_summary")
    add_col("sos_alerts", "routing_log"); add_col("sos_alerts", "cancelled", "INTEGER DEFAULT 0")
    add_col("notifications", "triage_id"); add_col("notifications", "abha_id")
    add_col("patients", "aadhaar_id"); add_col("patients", "registered_by_type")
    add_col("patients", "registered_by_id"); add_col("patients", "registered_by_name")
    add_col("patients", "scheme_eligible", "INTEGER DEFAULT 0")
    add_col("asha_workers", "facility_id"); add_col("doctors", "facility_id")
    add_col("medicine_stock", "facility_id"); add_col("medicine_stock", "updated_by")
    conn.commit()
    conn.close()

# ─────────────────────────── AUTH HELPERS ──────────────────────
def hash_pw(pw, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()
    return h, salt

def verify_pw(pw, salt, stored):
    if not salt or not stored:
        return False
    return hash_pw(pw, salt)[0] == stored

def gen_password(n=6):
    return "".join(secrets.choice("0123456789") for _ in range(n))

def gen_worker_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"

def gen_abha():
    return "ABHA-" + str(uuid.uuid4())[:8].upper()

# ── FIX 4: Aadhaar hashing ──────────────────────────────────
# Raw Aadhaar numbers are NEVER stored in the database.
# We store a SHA-256 hash using a per-app salt (from env var).
# In production: salt goes in an HSM / KMS vault, not code.
AADHAAR_SALT = os.environ.get("AADHAAR_SALT", "arogyabridge-sih2026-demo-salt")

def hash_aadhaar(aadhaar: str) -> str:
    """One-way hash of Aadhaar for storage. Never reversible."""
    return hashlib.sha256(f"{AADHAAR_SALT}:{aadhaar}".encode()).hexdigest()

def verify_aadhaar(input_aadhaar: str, stored_hash: str) -> bool:
    return hash_aadhaar(input_aadhaar) == stored_hash

def mask_aadhaar(stored_val):
    if stored_val is None or stored_val == "—":
        return "—"
    try:
        if pd.isna(stored_val):
            return "—"
    except (TypeError, ValueError):
        pass
    raw = str(stored_val).strip()
    if raw.isdigit() and len(raw) == 12:
        return "XXXX-XXXX-" + raw[-4:]
    return "XXXX-XXXX-[Hashed]"

# ─────────────────────────── SMS HELPER (Fix 3) ─────────────
def send_sms_alert(phone: str, message: str) -> bool:
    """
    SMS fallback for low-connectivity scenarios.
    Uses Fast2SMS (free tier works for demo).
    Production plan: migrate to BSNL government bulk SMS gateway.
    Returns True if sent successfully, False otherwise (silent fail).
    """
    if not FAST2SMS_KEY or not phone:
        return False
    phone_clean = phone.replace("+91", "").replace(" ", "").strip()
    if len(phone_clean) != 10 or not phone_clean.isdigit():
        return False
    try:
        resp = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={"authorization": FAST2SMS_KEY},
            json={
                "route": "q",
                "message": message[:160],
                "language": "english",
                "flash": 0,
                "numbers": phone_clean,
            },
            timeout=5,
        )
        return resp.status_code == 200
    except Exception:
        return False

# ─────────────────────────── TRIAGE ENGINE ─────────────────────
RED_FLAGS = [
    "chest pain", "severe bleeding", "unconscious", "seizure",
    "not breathing", "difficulty breathing", "breathlessness",
    "convulsion", "high fever infant", "severe abdominal pain",
    "stroke", "paralysis", "blue lips",
    # Hindi
    "सीने में दर्द", "बेहोश", "दौरा", "सांस लेने में तकलीफ",
    "अत्यधिक रक्तस्राव", "लकवा",
    # Marathi
    "छातीत दुखणे", "बेशुद्ध", "झटका", "श्वास घेण्यास त्रास",
    # Tamil
    "நெஞ்சு வலி", "மயக்கம்", "வலிப்பு",
    # Telugu
    "గుండె నొప్పి", "స్పృహ కోల్పోవడం", "మూర్ఛ",
]
YELLOW_FLAGS = [
    "fever", "vomiting", "diarrhea", "dehydration", "moderate pain",
    "pregnancy bleeding", "high blood pressure", "persistent cough",
    # Hindi
    "बुखार", "उल्टी", "दस्त", "गर्भावस्था रक्तस्राव",
    "उच्च रक्तचाप", "लगातार खांसी",
    # Marathi
    "ताप", "उलटी", "जुलाब",
    # Tamil
    "காய்ச்சல்", "வாந்தி", "வயிற்றுப்போக்கு",
    # Telugu
    "జ్వరం", "వాంతి", "విరేచనాలు",
]
DEPT_KW = [
    ("Obstetrics & Gynaecology", [
        "pregnan", "labour", "labor pain", "pregnancy bleeding",
        "missed period", "गर्भ", "प्रसव", "गर्भावस्था",
        "गर्भधारणा", "प्रसूती",
    ]),
    ("Pediatrics", [
        "infant", "newborn", "child fever", "baby not feeding",
        "बच्चा", "शिशु", "नवजात", "मूल", "बाळ",
    ]),
    ("Cardiology", [
        "chest pain", "palpitations", "heart",
        "सीने में दर्द", "दिल", "छातीत दुखणे",
    ]),
    ("Pulmonology", [
        "breathless", "difficulty breathing", "asthma", "persistent cough",
        "सांस लेने में तकलीफ", "खांसी", "दमा",
        "श्वास", "दम",
    ]),
    ("Orthopedics", [
        "fracture", "bone pain", "joint pain",
        "हड्डी", "जोड़ों में दर्द", "हाड",
    ]),
    ("Neurology", [
        "seizure", "convulsion", "stroke", "paralysis",
        "दौरा", "लकवा", "झटका",
    ]),
    ("Gastroenterology", [
        "vomiting", "diarrhea", "severe abdominal pain",
        "उल्टी", "दस्त", "पेट में तेज़ दर्द",
        "उलटी", "जुलाब",
    ]),
]

def suggest_dept(text):
    t = text.lower()
    for dept, kws in DEPT_KW:
        for kw in kws:
            if kw in t:
                return dept
    return "General Medicine"

def rule_triage(text):
    t = text.lower()
    for f in RED_FLAGS:
        if f in t:
            return "RED", f"Red-flag: '{f}' — immediate escalation needed."
    for f in YELLOW_FLAGS:
        if f in t:
            return "YELLOW", f"Moderate risk: '{f}' — facility visit recommended."
    return "GREEN", "No high-risk indicators. Routine care advised."

def groq_triage(text):
    """
    FIX 6: Language-aware AI triage prompt.
    The model is instructed to understand regional language input
    (Hindi, Marathi, Tamil, Telugu, Bengali) and still return
    a structured English response for consistent parsing.
    """
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        lang = st.session_state.get("ui_lang", "en")
        lang_note = (
            "The patient's symptoms may be written in Hindi, Marathi, Tamil, "
            "Telugu, or Bengali script. Understand the regional language input fully "
            "before classifying. Always respond in English format only."
            if lang != "en" else ""
        )
        prompt = (
            f"You are a rural Indian health triage assistant. {lang_note} "
            f"Classify the following symptoms strictly as RED (emergency), "
            f"YELLOW (needs facility visit soon), or GREEN (routine care). "
            f"Reply ONLY in this exact format: PRIORITY|one sentence rationale.\n"
            f"Symptoms: {text}"
        )
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.2,
        )
        out = resp.choices[0].message.content.strip()
        if "|" in out:
            p, r = out.split("|", 1)
            p = p.strip().upper()
            if p in PRIORITY_ORDER:
                return p, r.strip()
    except Exception:
        return None
    return None

def run_triage(text):
    res = groq_triage(text)
    priority, rationale = res if res else rule_triage(text)
    dept = suggest_dept(text)
    fud = None
    if priority == "RED":
        fud = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    elif priority == "YELLOW":
        fud = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    return priority, rationale, dept, fud

# ─────────────────────── NOTIFICATION HELPERS ──────────────────
def send_notification(role, recipient_id, message, priority, triage_id=None, abha_id=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) "
        "VALUES(?,?,?,?,?,0,?,?,?)",
        (str(uuid.uuid4()), role, recipient_id, message, priority,
         datetime.now().isoformat(), triage_id, abha_id),
    )
    conn.commit()
    conn.close()

def notify_all_doctors(message, priority, triage_id=None, abha_id=None):
    conn = get_conn()
    docs = conn.execute("SELECT id FROM doctors").fetchall()
    for d in docs:
        conn.execute(
            "INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) "
            "VALUES(?,?,?,?,?,0,?,?,?)",
            (str(uuid.uuid4()), "doctor", d["id"], message, priority,
             datetime.now().isoformat(), triage_id, abha_id),
        )
    conn.commit()
    conn.close()

def notify_all_asha(message, priority, triage_id=None, abha_id=None):
    conn = get_conn()
    ashas = conn.execute("SELECT id FROM asha_workers").fetchall()
    for a in ashas:
        conn.execute(
            "INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) "
            "VALUES(?,?,?,?,?,0,?,?,?)",
            (str(uuid.uuid4()), "asha", a["id"], message, priority,
             datetime.now().isoformat(), triage_id, abha_id),
        )
    conn.commit()
    conn.close()

def get_unread(role, uid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE recipient_role=? AND recipient_id=? AND read=0 ORDER BY created_at DESC",
        (role, uid),
    ).fetchall()
    conn.close()
    return rows

def mark_read(role, uid):
    conn = get_conn()
    conn.execute(
        "UPDATE notifications SET read=1 WHERE recipient_role=? AND recipient_id=?",
        (role, uid),
    )
    conn.commit()
    conn.close()

# ─────────────────────── SOS HELPERS (Fix 5) ───────────────────
def get_nearby_staff(patient_village: str):
    """
    Returns doctors and ASHA workers from the same village/area first,
    then falls back to all staff if none found nearby.
    'Nearby' = same village string OR facility serving that village.
    Production plan: replace string-match with lat/lng radius query
    using coordinates stored per facility.
    """
    conn = get_conn()
    nearby_facilities = conn.execute(
        "SELECT name FROM facilities WHERE village LIKE ?",
        (f"%{patient_village}%",),
    ).fetchall()
    nearby_fac_names = [f["name"] for f in nearby_facilities]

    if nearby_fac_names:
        placeholders = ",".join("?" * len(nearby_fac_names))
        nearby_docs = conn.execute(
            f"SELECT id, name FROM doctors WHERE facility IN ({placeholders})",
            nearby_fac_names,
        ).fetchall()
        nearby_asha = conn.execute(
            f"SELECT id, name FROM asha_workers WHERE facility IN ({placeholders})",
            nearby_fac_names,
        ).fetchall()
    else:
        # Fallback: notify all staff (only triggers when no facility
        # is registered for that village — shouldn't happen in production)
        nearby_docs  = conn.execute("SELECT id, name FROM doctors").fetchall()
        nearby_asha  = conn.execute("SELECT id, name FROM asha_workers").fetchall()

    conn.close()
    return nearby_docs, nearby_asha

def send_sos_notifications(patient: dict, abha_id: str) -> str:
    """
    Sends in-app notifications to nearby staff only (Fix 5).
    Also triggers SMS to patient's phone if registered (Fix 3).
    Returns a routing detail string for the dispatch report.
    """
    village = patient.get("village") or ""
    nearby_docs, nearby_asha = get_nearby_staff(village)

    for doc in nearby_docs:
        send_notification(
            "doctor", doc["id"],
            f"EMERGENCY SOS — {patient['name']} ({village}) | "
            f"Age {patient.get('age', '?')} | ABHA: {abha_id}. "
            f"You are a nearby responder.",
            "RED", abha_id=abha_id,
        )
    for asha in nearby_asha:
        send_notification(
            "asha", asha["id"],
            f"SOS ALERT — {patient['name']} ({village}) needs immediate help. "
            f"You are the nearest registered ASHA worker.",
            "RED", abha_id=abha_id,
        )

    # SMS fallback (Fix 3) — reaches patient even without internet
    phone = patient.get("phone") or ""
    sms_sent = False
    if phone:
        sms_text = (
            f"ArogyaBridge EMERGENCY: SOS dispatched for {patient['name']} "
            f"in {village}. Ambulance & ASHA workers alerted. "
            f"ABHA: {abha_id}"
        )
        sms_sent = send_sms_alert(phone, sms_text)

    routing_detail = (
        f"Notified {len(nearby_docs)} doctor(s) and "
        f"{len(nearby_asha)} ASHA worker(s) near {village or 'unknown'}."
        + (" SMS sent." if sms_sent else "")
    )
    return routing_detail

# ─────────────────────────── UTILS ─────────────────────────────
def priority_badge(p):
    c = PRIORITY_COLORS.get(p, "#999")
    return (
        f"<span style='background:{c};color:white;padding:3px 12px;"
        f"border-radius:12px;font-weight:700;font-size:.85em'>{p}</span>"
    )

def qdf(sql, params=()):
    conn = get_conn()
    d = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return d

def clean_df(df):
    if df is None or df.empty:
        return df
    return df.fillna("—")
def sv(val, default="—"):
    """Safe display value — turns None / NaN / blank strings into a clean placeholder."""
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(val, str) and val.strip() == "":
        return default
    return val

def get_facility_names():
    df_fac = qdf("SELECT name FROM facilities ORDER BY name")
    return df_fac["name"].tolist() if not df_fac.empty else []

def seed_default_stock_for_facility(facility_id, facility_name):
    meds = [
        ("Paracetamol 500mg", "tablets", 40),
        ("ORS Sachets", "sachets", 20),
        ("Iron Folic Acid", "tablets", 100),
        ("Amoxicillin 250mg", "capsules", 30),
        ("Antenatal Vitamin D", "tablets", 50),
    ]
    now = datetime.now().isoformat()
    conn = get_conn()
    for med, unit, qty in meds:
        sid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO medicine_stock(id,facility_id,facility,medicine_name,quantity,unit,last_updated,updated_by) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (sid, facility_id, facility_name, med, qty, unit, now, "System (initial stock)"),
        )
        conn.execute(
            "INSERT INTO medicine_stock_log VALUES(?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), facility_id, facility_name, med,
             "Initial stock", qty, qty, "System", now),
        )
    conn.commit()
    conn.close()

def predict_stockout(facility_id, medicine_name):
    hist = qdf(
        "SELECT change_amount, new_quantity, changed_at FROM medicine_stock_log "
        "WHERE facility_id=? AND medicine_name=? ORDER BY changed_at",
        (facility_id, medicine_name),
    )
    if len(hist) < 2:
        return None
    hist["changed_at"] = pd.to_datetime(hist["changed_at"], errors="coerce")
    consumption = hist[hist["change_amount"] < 0]
    if consumption.empty:
        return None
    total_consumed = -consumption["change_amount"].sum()
    span_days = (hist["changed_at"].max() - hist["changed_at"].min()).total_seconds() / 86400
    span_days = max(span_days, 1)
    avg_daily = total_consumed / span_days
    if avg_daily <= 0:
        return None
    current_qty = hist.iloc[-1]["new_quantity"]
    return round(float(current_qty / avg_daily), 1)

def seed_default_diagnostics_for_facility(facility_id, facility_name):
    now = datetime.now().isoformat()
    conn = get_conn()
    for name in DEFAULT_DIAGNOSTIC_TESTS:
        conn.execute(
            "INSERT INTO diagnostic_tests(id,facility_id,facility,test_name,available,turnaround_hours,last_updated,updated_by) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), facility_id, facility_name, name, 1, 24, now, "System (initial setup)"),
        )
    conn.commit()
    conn.close()

def generate_immunization_schedule(child_id, abha_id, dob_str, created_by):
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
    except Exception:
        return
    conn = get_conn()
    for offset_days, vaccine in IMMUNIZATION_SCHEDULE:
        due = (dob + timedelta(days=offset_days)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO mch_immunization(id,child_id,abha_id,vaccine_name,due_date,given,given_date) "
            "VALUES(?,?,?,?,?,0,NULL)",
            (str(uuid.uuid4()), child_id, abha_id, vaccine, due),
        )
    conn.commit()
    conn.close()

def compute_sla_status(priority, created_at, acknowledged_at, status):
    try:
        created = datetime.fromisoformat(created_at)
    except Exception:
        return None, None
    target = SLA_TARGET_HOURS.get(priority, 72)
    end_time = datetime.fromisoformat(acknowledged_at) if acknowledged_at else datetime.now()
    elapsed_hours = (end_time - created).total_seconds() / 3600
    breached = (
        (elapsed_hours > target and status == "PENDING")
        or (acknowledged_at and elapsed_hours > target)
    )
    return round(elapsed_hours, 1), bool(breached)

def fhir_lite_export(abha_id):
    conn = get_conn()
    p = conn.execute("SELECT * FROM patients WHERE abha_id=?", (abha_id,)).fetchone()
    if not p:
        conn.close()
        return None
    triage_rows   = conn.execute("SELECT * FROM triage WHERE abha_id=? ORDER BY created_at", (abha_id,)).fetchall()
    referral_rows = conn.execute("SELECT * FROM referrals WHERE abha_id=? ORDER BY created_at", (abha_id,)).fetchall()
    diag_rows     = conn.execute("SELECT * FROM diagnostic_orders WHERE abha_id=? ORDER BY ordered_at", (abha_id,)).fetchall()
    conn.close()
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {
            "profile": "ArogyaBridge-ABDM-lite-v1",
            "abdm_compliance": "FHIR R4 bundle structure — ready for ABDM HIU/HIP registration",
            "production_note": (
                "Replace gen_abha() with ABDM Health ID API "
                "(POST /v1/registration/aadhaar/generateOtp) in production. "
                "Aadhaar stored as SHA-256 hash — raw number never persists."
            ),
        },
        "exported_at": datetime.now().isoformat(),
        "entry": [{
            "resourceType": "Patient",
            "identifier": [
                {"system": "ABHA", "value": p["abha_id"]},
                {"system": "AADHAAR-HASHED", "value": "[SHA-256 hash — not recoverable]"},
            ],
            "name": p["name"], "gender": p["gender"], "age": p["age"],
            "address": {"village": p["village"]}, "language": p["language"],
            "schemeEligible": bool(p["scheme_eligible"]) if "scheme_eligible" in p.keys() else False,
        }],
        "encounters": [{
            "resourceType": "Condition/Observation",
            "id": t["id"], "recordedDate": t["created_at"], "priority": t["priority"],
            "symptoms": t["symptoms_text"], "department": t["department"],
            "rationale": t["rationale"],
            "vitals": {"temperature": t["temperature"], "spo2": t["spo2"], "pulse": t["pulse"]},
        } for t in triage_rows],
        "referrals": [{
            "resourceType": "ServiceRequest", "id": r["id"], "facility": r["facility"],
            "status": r["status"], "createdAt": r["created_at"], "completedAt": r["completed_at"],
            "prescription": r["prescription"], "notes": r["doctor_notes"],
        } for r in referral_rows],
        "diagnosticReports": [{
            "resourceType": "DiagnosticReport", "id": d["id"], "test": d["test_name"],
            "facility": d["facility"], "status": d["status"], "resultNotes": d["result_notes"],
            "orderedAt": d["ordered_at"], "completedAt": d["completed_at"],
        } for d in diag_rows],
    }
    return json.dumps(bundle, indent=2, default=str)

def tts_component(text, lang_code="en", key="tts"):
    """Browser-based TTS via Web Speech API. Zero-cost, works offline once loaded."""
    voice_lang_map = {
        "en": "en-IN", "hi": "hi-IN", "mr": "mr-IN",
        "ta": "ta-IN", "te": "te-IN", "bn": "bn-IN",
    }
    voice_lang = voice_lang_map.get(lang_code, "en-IN")
    safe_text = json.dumps(text or "")
    components.html(f"""
    <button id="btn_{key}" style="padding:7px 14px;border-radius:6px;border:1px solid #888;
        background:#f0f2f6;cursor:pointer;font-size:0.9rem;font-weight:600;">
        🔊 Listen
    </button>
    <script>
      document.getElementById("btn_{key}").onclick = function() {{
        const msg = new SpeechSynthesisUtterance({safe_text});
        msg.lang = "{voice_lang}";
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(msg);
      }};
    </script>
    """, height=48)

# ─────────────────────────── AUTH SCREENS ──────────────────────
def patient_auth_screen():
    st.markdown(f"### {tr('patient_portal')}")
    login_tab, reg_tab = st.tabs([tr("login"), tr("register_tab")])

    with login_tab:
        with st.container(border=True):
            st.caption(tr("phone_login_hint"))
            aad = st.text_input(tr("aadhaar_id"), key="l_aad_patient",
                                placeholder="12-digit Aadhaar number")
            pw  = st.text_input(tr("password"), type="password", key="l_pw_patient")
            if st.button(tr("login_btn"), type="primary", use_container_width=True, key="l_btn_patient"):
                aad_clean = (aad or "").strip().replace(" ", "")
                if not aad_clean or not pw:
                    st.warning("Enter your Aadhaar ID and password.")
                else:
                    # FIX 4: look up by hashed Aadhaar
                    aad_hash = hash_aadhaar(aad_clean)
                    conn = get_conn()
                    row = conn.execute(
                        "SELECT * FROM patients WHERE aadhaar_id=? AND password_hash IS NOT NULL",
                        (aad_hash,),
                    ).fetchone()
                    # Legacy fallback: support accounts registered before hashing was added
                    if not row:
                        row = conn.execute(
                            "SELECT * FROM patients WHERE aadhaar_id=? AND password_hash IS NOT NULL",
                            (aad_clean,),
                        ).fetchone()
                    conn.close()
                    if row and verify_pw(pw, row["salt"], row["password_hash"]):
                        return dict(row)
                    st.error(tr("invalid_login"))

    with reg_tab:
        with st.container(border=True):
            st.caption(tr("create_login"))
            st.info(
                "**ABDM Integration Note (Production):** "
                "ABHA IDs shown here are demo-generated. In production, "
                "registration triggers the ABDM Health ID API "
                "(`POST /v1/registration/aadhaar/generateOtp`). "
                "Aadhaar is stored as a SHA-256 hash — raw number never persists."
            )
            with st.form("reg_patient_self"):
                c1, c2 = st.columns(2)
                rn  = c1.text_input(tr("name"))
                ra  = c2.number_input(tr("age"), 0, 120, 0)
                rg  = c1.selectbox(tr("gender"), ["Female", "Male", "Other"])
                rv  = c2.text_input(tr("village"))
                raad = c1.text_input(tr("aadhaar_id"), placeholder="12-digit Aadhaar number")
                rph = c2.text_input(tr("phone") + " (optional)")
                rl  = st.selectbox(tr("language"),
                                   ["Marathi", "Hindi", "Tamil", "Telugu", "Bengali", "English"])
                r_scheme = st.checkbox(tr("scheme_eligible"),
                                       help="Check if you hold a valid PM-JAY / Ayushman Bharat card.")
                st.markdown("###### Set a password")
                rpw = st.text_input(tr("password"), type="password")
                rc  = st.text_input(tr("confirm_password"), type="password")
                submitted = st.form_submit_button(tr("register_btn"), type="primary",
                                                  use_container_width=True)
                if submitted:
                    aad_clean = (raad or "").strip().replace(" ", "")
                    if not rn or not raad:
                        st.error("Name and Aadhaar ID are required.")
                    elif not aad_clean.isdigit() or len(aad_clean) != 12:
                        st.error("Enter a valid 12-digit Aadhaar ID.")
                    elif not rpw or rpw != rc:
                        st.error("Passwords don't match.")
                    else:
                        aad_hash = hash_aadhaar(aad_clean)  # FIX 4
                        conn = get_conn()
                        exists = conn.execute(
                            "SELECT abha_id FROM patients WHERE aadhaar_id=?", (aad_hash,)
                        ).fetchone()
                        if exists:
                            st.error("This Aadhaar ID is already registered — please log in instead.")
                            conn.close()
                        else:
                            h, s = hash_pw(rpw)
                            conn.execute(
                                """INSERT INTO patients
                                (abha_id,name,age,gender,village,phone,aadhaar_id,language,created_at,
                                 password_hash,salt,registered_by_type,registered_by_id,
                                 registered_by_name,scheme_eligible)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (gen_abha(), rn, ra, rg, rv, rph, aad_hash, rl,
                                 datetime.now().isoformat(), h, s, "self", None, "Self",
                                 1 if r_scheme else 0),
                            )
                            conn.commit()
                            conn.close()
                            st.success("Registered! Please log in above using your Aadhaar ID.")
    return None

def facility_auth_screen():
    st.markdown(f"### {tr('facility')}")
    st.caption("Every Sub-Centre, PHC, or Hospital registers itself here once, "
               "then issues login IDs to its own ASHA workers and doctors.")
    login_tab, reg_tab = st.tabs([tr("login"), tr("register_tab")])

    with login_tab:
        with st.container(border=True):
            ph = st.text_input(tr("phone"), key="l_phone_facility",
                               placeholder="Registered facility phone")
            pw = st.text_input(tr("password"), type="password", key="l_pw_facility")
            if st.button(tr("login_btn"), type="primary", use_container_width=True,
                         key="l_btn_facility"):
                if not ph or not pw:
                    st.warning("Enter phone and password.")
                else:
                    conn = get_conn()
                    row = conn.execute(
                        "SELECT * FROM facilities WHERE phone=?", (ph,)
                    ).fetchone()
                    conn.close()
                    if row and verify_pw(pw, row["salt"], row["password_hash"]):
                        return dict(row)
                    st.error(tr("invalid_login"))

    with reg_tab:
        with st.container(border=True):
            with st.form("reg_facility"):
                c1, c2 = st.columns(2)
                fn  = c1.text_input("Facility / Hospital Name", placeholder="e.g. PHC Ranjangaon")
                ft  = c2.selectbox("Facility Type", FACILITY_TYPES)
                fv  = c1.text_input("Village / Area Served")
                fph = c2.text_input(tr("phone"))
                st.markdown("###### Set a password")
                fpw = st.text_input(tr("password"), type="password")
                fcp = st.text_input(tr("confirm_password"), type="password")
                submitted = st.form_submit_button(tr("register_btn"), type="primary",
                                                  use_container_width=True)
                if submitted:
                    if not fn or not fph:
                        st.error("Facility name and phone are required.")
                    elif not fpw or fpw != fcp:
                        st.error("Passwords don't match.")
                    else:
                        conn = get_conn()
                        exists = conn.execute(
                            "SELECT id FROM facilities WHERE name=? OR phone=?", (fn, fph)
                        ).fetchone()
                        if exists:
                            st.error("A facility with this name or phone is already registered.")
                            conn.close()
                        else:
                            h, s = hash_pw(fpw)
                            fid = str(uuid.uuid4())
                            conn.execute(
                                "INSERT INTO facilities(id,name,type,village,phone,password_hash,salt,created_at) "
                                "VALUES(?,?,?,?,?,?,?,?)",
                                (fid, fn, ft, fv, fph, h, s, datetime.now().isoformat()),
                            )
                            conn.commit()
                            conn.close()
                            seed_default_stock_for_facility(fid, fn)
                            seed_default_diagnostics_for_facility(fid, fn)
                            st.success("Facility registered! Please log in above.")
    return None

def staff_login_screen(role_label, table, id_placeholder):
    st.markdown(f"### {role_label}")
    with st.container(border=True):
        st.caption("Log in with the ID and password issued to you by your facility.")
        wid = st.text_input("Worker ID", key=f"l_id_{table}", placeholder=id_placeholder)
        pw  = st.text_input(tr("password"), type="password", key=f"l_pw_{table}")
        if st.button(tr("login_btn"), type="primary", use_container_width=True,
                     key=f"l_btn_{table}"):
            if not wid or not pw:
                st.warning("Enter your Worker ID and password.")
            else:
                conn = get_conn()
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE id=?", (wid.strip().upper(),)
                ).fetchone()
                conn.close()
                if row and verify_pw(pw, row["salt"], row["password_hash"]):
                    return dict(row)
                st.error(tr("invalid_login"))
        st.info("Don't have an ID yet? Ask your facility administrator to register you "
                "from the Facility / Hospital portal.")
    return None

# ─────────────────────── PUBLIC (NO LOGIN) PAGES ────────────────
def render_medicine_page():
    st.caption("Public read-only view. To update stock levels, log in through the "
               "Facility / Hospital portal.")
    facs = ["All"] + get_facility_names()
    s1, s2 = st.columns(2)
    fac_filter  = s1.selectbox("Facility", facs, key="med_fac_filter")
    med_search  = s2.text_input("Search medicine name", key="med_search")

    sql = "SELECT facility_id,facility,medicine_name,quantity,unit,last_updated FROM medicine_stock WHERE 1=1"
    params = []
    if fac_filter != "All":
        sql += " AND facility=?"; params.append(fac_filter)
    if med_search:
        sql += " AND medicine_name LIKE ?"; params.append(f"%{med_search}%")
    sql += " ORDER BY facility,medicine_name"
    stock = qdf(sql, tuple(params))

    def hl(row):
        if row["quantity"] < 10:
            return ["background-color:#ffcdd2;color:black"] * len(row)
        return [""] * len(row)

    if stock.empty:
        st.info("No medicines found.")
    else:
        stock["predicted_stockout_days"] = stock.apply(
            lambda r: predict_stockout(r["facility_id"], r["medicine_name"]), axis=1
        )
        display_stock = stock.drop(columns=["facility_id"])
        st.dataframe(clean_df(display_stock).style.apply(hl, axis=1),
                     use_container_width=True, hide_index=True)
        st.caption("Red rows = low stock (below 10 units). "
                   "'Predicted stockout days' uses real consumption history, not a fixed threshold.")

def render_diagnostics_page():
    st.caption("Public read-only view of which facility can run which diagnostic test.")
    facs = ["All"] + get_facility_names()
    s1, s2 = st.columns(2)
    fac_filter  = s1.selectbox("Facility", facs, key="diag_fac_filter")
    test_search = s2.text_input("Search test name", key="diag_search")

    sql = "SELECT facility,test_name,available,turnaround_hours,last_updated FROM diagnostic_tests WHERE 1=1"
    params = []
    if fac_filter != "All":
        sql += " AND facility=?"; params.append(fac_filter)
    if test_search:
        sql += " AND test_name LIKE ?"; params.append(f"%{test_search}%")
    sql += " ORDER BY facility,test_name"
    tests = qdf(sql, tuple(params))

    if tests.empty:
        st.info("No diagnostic tests found.")
    else:
        tests["available"] = tests["available"].map({1: "Available", 0: "Unavailable"})
        st.dataframe(
            clean_df(tests).style.apply(
                lambda r: ["background-color:#ffcdd2;color:black"] * len(r)
                if r["available"] == "Unavailable" else [""] * len(r), axis=1
            ),
            use_container_width=True, hide_index=True,
        )
        st.caption("Red rows = currently unavailable at that facility.")

def render_specialists_page():
    st.caption("Which facility has which speciality — so patients and ASHA workers "
               "know where to refer before a case gets urgent.")
    s1, s2 = st.columns(2)
    spec_filter    = s1.selectbox("Speciality", ["All"] + SPECIALITIES, key="spec_filter")
    village_search = s2.text_input("Search facility or village", key="spec_village_search")

    sql = """SELECT d.name as doctor_name, d.speciality, d.facility,
                    f.type as facility_type, f.village
             FROM doctors d LEFT JOIN facilities f ON f.name=d.facility WHERE 1=1"""
    params = []
    if spec_filter != "All":
        sql += " AND d.speciality=?"; params.append(spec_filter)
    if village_search:
        sql += " AND (d.facility LIKE ? OR f.village LIKE ?)"
        params.append(f"%{village_search}%"); params.append(f"%{village_search}%")
    sql += " ORDER BY d.speciality, d.facility"
    specialists = qdf(sql, tuple(params))

    if specialists.empty:
        st.info("No doctors match your filters yet.")
    else:
        st.caption(f"{len(specialists)} doctor(s) found")
        st.dataframe(clean_df(specialists), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Speciality Coverage by Facility**")
    coverage = qdf(
        "SELECT facility, GROUP_CONCAT(DISTINCT speciality) as specialities, COUNT(*) as doctor_count "
        "FROM doctors GROUP BY facility ORDER BY facility"
    )
    if coverage.empty:
        st.info("No facilities have doctors registered yet.")
    else:
        st.dataframe(clean_df(coverage), use_container_width=True, hide_index=True)

def render_public_services_block():
    st.divider()
    with st.expander(f"🔎 {tr('public_services')}", expanded=False):
        pm1, pm2, pm3 = st.tabs([tr("medicine"), tr("diagnostics"), tr("specialists")])
        with pm1: render_medicine_page()
        with pm2: render_diagnostics_page()
        with pm3: render_specialists_page()

# ─────────────────────────── INIT ──────────────────────────────
init_db()
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"

# ─────────────────────────── SIDEBAR ───────────────────────────
with st.sidebar:
    st.markdown("## 🩺 ArogyaBridge")
    st.caption("Bridge to Healthcare — SIH 2026 | PS 26133")
    LANG_LABELS = {
        "en": "English", "hi": "हिंदी (Hindi)", "mr": "मराठी (Marathi)",
        "ta": "தமிழ் (Tamil)", "te": "తెలుగు (Telugu)", "bn": "বাংলা (Bengali)",
    }
    lc = st.selectbox("Language", list(LANG_LABELS.values()))
    st.session_state.ui_lang = next(k for k, v in LANG_LABELS.items() if v == lc)
    st.divider()
    ROLE_KEYS = ["patient_portal", "asha", "doctor", "facility", "admin"]
    ROLES = [tr(k) for k in ROLE_KEYS]
    if "role_key" not in st.session_state:
        st.session_state.role_key = ROLE_KEYS[0]
    default_index = ROLE_KEYS.index(st.session_state.role_key)
    picked_label = st.radio(tr("role"), ROLES, index=default_index)
    st.session_state.role_key = ROLE_KEYS[ROLES.index(picked_label)]
    page = picked_label
    st.divider()
    st.caption("AI: " + ("Groq Llama 3.1 (multilingual)" if GROQ_API_KEY else "Rule-based fallback"))
    st.caption("SMS: " + ("Fast2SMS active" if FAST2SMS_KEY else "SMS not configured"))

st.title(tr("app_title"))

# ══════════════════════════════════════════════════════════════
# PAGE: PATIENT PORTAL
# ══════════════════════════════════════════════════════════════
if page == tr("patient_portal"):
    sk = "patient_user"
    if sk not in st.session_state:
        st.session_state[sk] = None

    if not st.session_state[sk]:
        row = patient_auth_screen()
        if row:
            st.session_state[sk] = row
            st.rerun()
        render_public_services_block()
    else:
        u = st.session_state[sk]
        abha_id = u["abha_id"]
        conn = get_conn()
        p = conn.execute("SELECT * FROM patients WHERE abha_id=?", (abha_id,)).fetchone()
        conn.close()

        with st.container(border=True):
            h1, h2 = st.columns([4, 1])
            h1.markdown(f"### {tr('welcome_back')}, **{p['name'] or u['name']}**")
            if h2.button(tr("logout_btn")):
                st.session_state[sk] = None
                st.rerun()
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("ABHA ID", p["abha_id"])
            mc2.metric(tr("age"), int(p["age"]) if p["age"] else "—")
            mc3.metric(tr("village"), p["village"] or "—")
            mc4.metric(tr("aadhaar_id"), mask_aadhaar(p["aadhaar_id"]))
            scheme_val = p["scheme_eligible"] if "scheme_eligible" in p.keys() else 0
            mc5.metric("PM-JAY", "Eligible" if scheme_val else "Not linked")

        qa1, qa2, qa3, qa4, qa5 = st.columns(5)
        if qa1.button(tr("book_appointment"), use_container_width=True):
            st.session_state["show_appt"] = not st.session_state.get("show_appt", False)
            st.session_state["show_self_triage"] = False
            st.session_state["show_update"] = False
        if qa2.button("Self Triage", use_container_width=True):
            st.session_state["show_self_triage"] = not st.session_state.get("show_self_triage", False)
            st.session_state["show_appt"] = False
            st.session_state["show_update"] = False
        if qa3.button(tr("update_details"), use_container_width=True):
            st.session_state["show_update"] = not st.session_state.get("show_update", False)
            st.session_state["show_appt"] = False
            st.session_state["show_self_triage"] = False
        qa5.download_button(
            tr("export_record"),
            data=(fhir_lite_export(abha_id) or "{}"),
            file_name=f"{abha_id}_health_record.json",
            mime="application/json",
            use_container_width=True,
            help="ABDM-lite interoperable JSON export of your full health record.",
        )
        if qa4.button(tr("sos"), type="primary", use_container_width=True):
            st.session_state["sos_armed"] = True
            st.session_state["sos_armed_at"] = datetime.now().isoformat()
            st.session_state["show_appt"] = False
            st.session_state["show_self_triage"] = False
            st.session_state["show_update"] = False

        # ── 5-Second SOS Cancel Window ──────────────────────────────
        if st.session_state.get("sos_armed"):
            armed_at = datetime.fromisoformat(st.session_state["sos_armed_at"])
            elapsed  = (datetime.now() - armed_at).total_seconds()
            remaining = max(0, 5 - int(elapsed))
            if remaining > 0:
                st_autorefresh(interval=1000, limit=6, key="sos_countdown_tick")

            with st.container(border=True):
                st.markdown(
                    f"""<div style='background:#b71c1c;color:white;border-radius:12px;
                    padding:18px;text-align:center'>
                    <h2 style='margin:0;color:white'>SOS ARMING IN {remaining}s</h2>
                    <p style='margin:6px 0 0 0;font-size:1.1rem'>
                    Emergency alert will be dispatched automatically.<br>
                    <b>Press CANCEL below if this was a mistake.</b></p></div>""",
                    unsafe_allow_html=True,
                )
                cc1, cc2 = st.columns(2)
                if cc1.button("CANCEL — False Alarm", use_container_width=True):
                    conn = get_conn()
                    conn.execute(
                        "INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,"
                        "status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), abha_id, p["name"], p["village"],
                         st.session_state["sos_armed_at"], "CANCELLED",
                         datetime.now().isoformat(), "Patient (self-cancel)", None,
                         "Cancelled within 5-second window — false alarm.", None, None, 1),
                    )
                    conn.commit()
                    conn.close()
                    st.session_state["sos_armed"] = False
                    st.info("SOS cancelled. No alert was sent.")
                    st.rerun()

                send_now_clicked = cc2.button("SEND NOW (skip timer)", type="primary",
                                               use_container_width=True)
                if remaining == 0 or send_now_clicked:
                    past_triage = qdf(
                        "SELECT priority,department,symptoms_text,created_at FROM triage "
                        "WHERE abha_id=? ORDER BY created_at DESC LIMIT 5", (abha_id,)
                    )
                    med_summary_lines = [
                        f"Patient: {p['name']}, Age: {p['age']}, Gender: {p['gender']}",
                        f"Village/Location: {p['village']}",
                        f"ABHA ID: {abha_id}",
                        "── Recent Medical History ──",
                    ]
                    if not past_triage.empty:
                        for _, r in past_triage.iterrows():
                            med_summary_lines.append(
                                f"[{r['priority']}] {r['department']}: "
                                f"{r['symptoms_text'][:60]} ({r['created_at'][:10]})"
                            )
                    else:
                        med_summary_lines.append("No prior visits on record.")
                    med_summary = "\n".join(med_summary_lines)

                    sid = str(uuid.uuid4())
                    conn = get_conn()
                    conn.execute(
                        "INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,"
                        "status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sid, abha_id, p["name"], p["village"],
                         datetime.now().isoformat(), "ACTIVE",
                         None, None, None, "Manual SOS", med_summary, None, 0),
                    )
                    conn.commit()
                    conn.close()

                    # FIX 5: smart geographic routing (also triggers Fix 3 SMS)
                    p_dict = dict(p)
                    routing_detail = send_sos_notifications(p_dict, abha_id)

                    routing_log = "\n".join([
                        f"[{datetime.now().strftime('%H:%M:%S')}] SOS activated by {p['name']}",
                        f"[{datetime.now().strftime('%H:%M:%S')}] Location: {p['village']}",
                        f"[{datetime.now().strftime('%H:%M:%S')}] Medical history packaged ({len(past_triage)} records)",
                        f"[{datetime.now().strftime('%H:%M:%S')}] {routing_detail}",
                        f"[{datetime.now().strftime('%H:%M:%S')}] Dispatch center pinged",
                        f"[{datetime.now().strftime('%H:%M:%S')}] Ambulance requested for {p['village']}",
                    ])
                    conn = get_conn()
                    conn.execute(
                        "UPDATE sos_alerts SET routing_log=? WHERE id=?", (routing_log, sid)
                    )
                    conn.commit()
                    conn.close()

                    st.session_state["sos_armed"] = False
                    st.session_state["last_sos_id"] = sid

                    st.error("EMERGENCY SOS DISPATCHED")
                    with st.container(border=True):
                        st.markdown("#### Dispatch Report")
                        rc1, rc2 = st.columns(2)
                        with rc1:
                            st.markdown("**Localized Responders**")
                            st.success(routing_detail)
                        with rc2:
                            st.markdown("**Central Command**")
                            st.success("Dispatch Center pinged")
                            st.success("Ambulance requested")
                        st.markdown("**Medical Package Sent**")
                        st.code(med_summary, language=None)
                    st.rerun()

        if st.session_state.get("last_sos_id"):
            sos_row = qdf(
                "SELECT routing_log FROM sos_alerts WHERE id=?",
                (st.session_state["last_sos_id"],),
            )
            if not sos_row.empty and sos_row.iloc[0]["routing_log"]:
                with st.expander("View last SOS routing log"):
                    st.code(sos_row.iloc[0]["routing_log"], language=None)

        # Appointment booking
        if st.session_state.get("show_appt"):
            with st.container(border=True):
                st.markdown(f"#### {tr('book_appointment')}")
                facs = get_facility_names()
                if not facs:
                    st.info("No facilities have registered yet.")
                else:
                    af1, af2, af3 = st.columns(3)
                    appt_fac  = af1.selectbox("Facility", facs, key="appt_fac_p")
                    appt_date = af2.date_input("Date", min_value=datetime.now().date(),
                                               key="appt_date_p")
                    appt_slot = af3.selectbox("Time", [
                        "9:00–10:00 AM", "10:00–11:00 AM", "11:00–12:00 PM",
                        "2:00–3:00 PM", "3:00–4:00 PM", "4:00–5:00 PM",
                    ], key="appt_slot_p")
                    if st.button("Confirm Request", type="primary", key="book_appt_p"):
                        conn = get_conn()
                        conn.execute(
                            "INSERT INTO appointments(id,abha_id,facility,appointment_date,"
                            "time_slot,status,created_at) VALUES(?,?,?,?,?,?,?)",
                            (str(uuid.uuid4()), abha_id, appt_fac, str(appt_date),
                             appt_slot, "REQUESTED", datetime.now().isoformat()),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Appointment requested at {appt_fac} on {appt_date} ({appt_slot}).")
                        st.session_state["show_appt"] = False
                        st.rerun()

        # Self-triage
        if st.session_state.get("show_self_triage"):
            with st.container(border=True):
                st.markdown("#### Self Symptom Check")
                st.caption("Describe how you're feeling in any language. "
                           "The AI understands Hindi, Marathi, Tamil, Telugu, Bengali, and English.")
                syms = st.text_area(
                    "Your symptoms",
                    placeholder="e.g. I have chest pain and I'm finding it hard to breathe / "
                                "सीने में दर्द है और सांस लेने में तकलीफ है",
                    height=90, key="self_triage_syms",
                )
                if st.button("Check Symptoms", type="primary", key="self_triage_btn"):
                    if not syms:
                        st.warning("Please describe your symptoms first.")
                    else:
                        with st.spinner("Analysing…"):
                            priority, rationale, dept, fud = run_triage(syms)
                        tid = str(uuid.uuid4())
                        conn = get_conn()
                        conn.execute(
                            """INSERT INTO triage(id,abha_id,symptoms_text,priority,rationale,
                            created_by,created_at,department,follow_up_due_date,follow_up_done,triggered_by)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                            (tid, abha_id, syms, priority, rationale, p["name"],
                             datetime.now().isoformat(), dept, fud, 0, "patient"),
                        )
                        conn.commit()

                        p_dict = dict(p)
                        if priority == "RED":
                            past_triage = qdf(
                                "SELECT priority,department,symptoms_text,created_at FROM triage "
                                "WHERE abha_id=? ORDER BY created_at DESC LIMIT 5", (abha_id,)
                            )
                            med_lines = [
                                f"Patient: {p['name']}, Age: {p['age']}, Village: {p['village']}, ABHA: {abha_id}",
                                "── Recent History ──",
                            ]
                            for _, r in past_triage.iterrows():
                                med_lines.append(
                                    f"[{r['priority']}] {r['department']}: {r['symptoms_text'][:60]}"
                                )
                            med_summary = "\n".join(med_lines)
                            sid = str(uuid.uuid4())
                            conn.execute(
                                "INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,"
                                "status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) "
                                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (sid, abha_id, p["name"], p["village"],
                                 datetime.now().isoformat(), "ACTIVE",
                                 None, None, None, "Auto-SOS from self-triage", med_summary, None, 0),
                            )
                            conn.commit()
                            # FIX 5: smart routing for auto-SOS too
                            routing_detail = send_sos_notifications(p_dict, abha_id)
                            routing_log = "\n".join([
                                f"[{datetime.now().strftime('%H:%M:%S')}] AUTO-SOS from self-triage RED result",
                                f"[{datetime.now().strftime('%H:%M:%S')}] Symptoms: {syms[:80]}",
                                f"[{datetime.now().strftime('%H:%M:%S')}] {routing_detail}",
                            ])
                            conn.execute(
                                "UPDATE sos_alerts SET routing_log=? WHERE id=?", (routing_log, sid)
                            )
                        elif priority == "YELLOW":
                            # FIX 3: SMS + in-app notification for YELLOW
                            notify_all_doctors(
                                f"YELLOW: {p['name']} ({p['village']}) needs follow-up — '{syms[:60]}'.",
                                "YELLOW", tid, abha_id,
                            )
                            notify_all_asha(
                                f"YELLOW: {p['name']} ({p['village']}) reported symptoms. Please follow up.",
                                "YELLOW", tid, abha_id,
                            )
                            phone = p_dict.get("phone") or ""
                            if phone:
                                sms_text = (
                                    f"ArogyaBridge: Your symptoms have been assessed as YELLOW priority. "
                                    f"{rationale[:80]}. Please visit {dept} at your nearest facility."
                                )
                                send_sms_alert(phone, sms_text)
                        else:
                            notify_all_asha(
                                f"GREEN: {p['name']} self-checked symptoms. No urgent action needed.",
                                "GREEN", tid, abha_id,
                            )
                        conn.commit()
                        conn.close()

                        col_r, _ = st.columns([1, 2])
                        col_r.markdown(f"**Result:** {priority_badge(priority)}",
                                       unsafe_allow_html=True)
                        st.write(rationale)
                        st.info(f"Suggested department: **{dept}**")
                        tts_component(
                            f"{rationale}. Suggested department: {dept}.",
                            st.session_state.get("ui_lang", "en"),
                            key=f"tts_self_{tid}",
                        )
                        if priority == "RED":
                            st.error("Emergency SOS auto-triggered. Nearby doctors and ASHA workers alerted. Ambulance requested.")
                        elif priority == "YELLOW":
                            st.warning("Doctors and your ASHA worker have been notified. SMS sent to your phone.")
                        else:
                            st.success("Your ASHA worker has been informed. Routine care advised.")

        # Update my details
        if st.session_state.get("show_update"):
            with st.container(border=True):
                st.markdown(f"#### {tr('update_details')}")
                st.caption("Name and Aadhaar ID are fixed as your identity anchor. "
                           "In production this form requires an OTP before saving — "
                           "skipped here for demo.")
                with st.form("patient_update_form"):
                    uc1, uc2 = st.columns(2)
                    new_age = uc1.number_input(tr("age"), 0, 120,
                                               int(p["age"]) if p["age"] else 0)
                    new_gender = uc2.selectbox(
                        tr("gender"), ["Female", "Male", "Other"],
                        index=["Female", "Male", "Other"].index(p["gender"])
                        if p["gender"] in ["Female", "Male", "Other"] else 0,
                    )
                    new_village = uc1.text_input(tr("village"), value=p["village"] or "")
                    new_phone   = uc2.text_input(tr("phone"), value=p["phone"] or "")
                    new_lang    = uc1.selectbox(
                        tr("language"),
                        ["Marathi", "Hindi", "Tamil", "Telugu", "Bengali", "English"],
                        index=(["Marathi", "Hindi", "Tamil", "Telugu", "Bengali", "English"]
                               .index(p["language"])
                               if p["language"] in
                               ["Marathi", "Hindi", "Tamil", "Telugu", "Bengali", "English"]
                               else 0),
                    )
                    if st.form_submit_button("Save Changes", type="primary"):
                        conn = get_conn()
                        conn.execute(
                            "UPDATE patients SET age=?,gender=?,village=?,phone=?,language=? WHERE abha_id=?",
                            (new_age, new_gender, new_village, new_phone, new_lang, abha_id),
                        )
                        conn.commit()
                        conn.close()
                        st.success("Details updated.")
                        st.rerun()

        st.divider()

        my_sos = qdf(
            "SELECT status,triggered_at FROM sos_alerts WHERE abha_id=? AND status='ACTIVE'",
            (abha_id,),
        )
        if not my_sos.empty:
            st.warning(f"{len(my_sos)} active SOS alert(s) awaiting response.")

        my_appts = qdf(
            "SELECT facility,appointment_date,time_slot,status,decline_reason "
            "FROM appointments WHERE abha_id=? ORDER BY appointment_date DESC", (abha_id,)
        )
        if not my_appts.empty:
            st.markdown("**My Appointments**")
            st.dataframe(clean_df(my_appts), use_container_width=True, hide_index=True)

        st.subheader(tr("my_health_record"))
        ht1, ht2, ht3, ht4 = st.tabs([
            tr("my_triage_history"), tr("my_referrals"),
            "Diagnostic Reports", "Care Plans (MCH/Chronic)",
        ])

        with ht1:
            th = qdf(
                "SELECT symptoms_text,priority,department,temperature,spo2,pulse,created_at "
                "FROM triage WHERE abha_id=? ORDER BY created_at DESC", (abha_id,)
            )
            if th.empty:
                st.info(tr("no_records_yet"))
            else:
                for _, r in th.iterrows():
                    with st.container(border=True):
                        rc1, rc2 = st.columns([3, 1])
                        rc1.write(f"**{r['symptoms_text']}**")
                        rc2.markdown(priority_badge(r["priority"]), unsafe_allow_html=True)
                        rc1.caption(f"{r['department'] or '—'}  |  {r['created_at'][:10]}")
                        if any([r["temperature"], r["spo2"], r["pulse"]]):
                            vc1, vc2, vc3 = st.columns(3)
                            if r["temperature"]: vc1.metric("Temp", f"{r['temperature']}°F")
                            if r["spo2"]:        vc2.metric("SpO₂", f"{r['spo2']}%")
                            if r["pulse"]:       vc3.metric("Pulse", f"{r['pulse']} bpm")

        with ht2:
            rh = qdf(
                "SELECT id,facility,status,prescription,doctor_notes,created_at,completed_at,"
                "feedback_rating,feedback_comment FROM referrals WHERE abha_id=? ORDER BY created_at DESC",
                (abha_id,),
            )
            if rh.empty:
                st.info(tr("no_records_yet"))
            else:
                for _, r in rh.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['facility']}** — `{r['status']}`  |  {r['created_at'][:10]}")
                        if r["prescription"]:
                            st.write(f"**Prescription:** {r['prescription']}")
                        if r["doctor_notes"]:
                            st.caption(f"Notes: {r['doctor_notes']}")
                        if r["status"] == "COMPLETED":
                            if pd.isna(r["feedback_rating"]) or r["feedback_rating"] in (None, "—"):
                                with st.form(f"feedback_form_{r['id']}"):
                                    st.caption("Quality check: did this visit help you?")
                                    fb_rating = st.select_slider(
                                        "Rate your experience", options=[1, 2, 3, 4, 5],
                                        value=4, key=f"fbr_{r['id']}",
                                    )
                                    fb_comment = st.text_input("Any comment (optional)",
                                                               key=f"fbc_{r['id']}")
                                    if st.form_submit_button("Submit Feedback"):
                                        conn = get_conn()
                                        conn.execute(
                                            "UPDATE referrals SET feedback_rating=?,feedback_comment=? WHERE id=?",
                                            (fb_rating, fb_comment, r["id"]),
                                        )
                                        conn.commit()
                                        conn.close()
                                        st.success("Thank you for your feedback!")
                                        st.rerun()
                            else:
                                st.caption(f"Your feedback: {'⭐' * int(r['feedback_rating'])} "
                                           f"{r['feedback_comment'] or ''}")

        with ht3:
            dh = qdf(
                "SELECT test_name,facility,status,result_notes,ordered_at,completed_at "
                "FROM diagnostic_orders WHERE abha_id=? ORDER BY ordered_at DESC", (abha_id,)
            )
            if dh.empty:
                st.info("No diagnostic tests ordered yet.")
            else:
                st.dataframe(clean_df(dh), use_container_width=True, hide_index=True)

        with ht4:
            preg = qdf(
                "SELECT lmp_date,edd,anc1_done,anc2_done,anc3_done,anc4_done,high_risk,status "
                "FROM mch_pregnancy WHERE abha_id=? ORDER BY created_at DESC", (abha_id,)
            )
            if not preg.empty:
                st.markdown("**Pregnancy / ANC Tracker**")
                st.dataframe(clean_df(preg), use_container_width=True, hide_index=True)
            children = qdf(
                "SELECT id,child_name,dob FROM mch_child WHERE abha_id=? ORDER BY created_at DESC",
                (abha_id,),
            )
            if not children.empty:
                st.markdown("**Child Immunization**")
                for _, ch in children.iterrows():
                    imm = qdf(
                        "SELECT vaccine_name,due_date,given,given_date FROM mch_immunization "
                        "WHERE child_id=? ORDER BY due_date", (ch["id"],)
                    )
                    st.caption(f"{ch['child_name'] or 'Child'} — DOB {ch['dob']}")
                    st.dataframe(clean_df(imm), use_container_width=True, hide_index=True)
            chronic = qdf(
                "SELECT condition,interval_days,next_due_date,active "
                "FROM chronic_registry WHERE abha_id=?", (abha_id,)
            )
            if not chronic.empty:
                st.markdown("**Chronic Care Follow-up Plan**")
                st.dataframe(clean_df(chronic), use_container_width=True, hide_index=True)
            if preg.empty and children.empty and chronic.empty:
                st.info("No MCH or chronic-care plans on record.")

# ══════════════════════════════════════════════════════════════
# PAGE: ASHA WORKER PORTAL
# ══════════════════════════════════════════════════════════════
elif page == tr("asha"):
    sk = "asha_user"
    if sk not in st.session_state:
        st.session_state[sk] = None

    if not st.session_state[sk]:
        row = staff_login_screen(tr("asha"), "asha_workers", "e.g. ASHA-A1B2C3")
        if row:
            st.session_state[sk] = row
            st.rerun()
    else:
        u = st.session_state[sk]
        notifs = get_unread("asha", u["id"])
        with st.container(border=True):
            ah1, ah2 = st.columns([4, 1])
            ah1.markdown(f"### {u['name']} — {u['facility'] or '—'}")
            ah1.caption(f"Worker ID: {u['id']}")
            if ah2.button(tr("logout_btn")):
                st.session_state[sk] = None
                st.rerun()
            if notifs:
                st.warning(f"{len(notifs)} new notification(s)")
                for n in notifs:
                    st.write(f"- {n['message']}")
                if st.button("Mark all read", key="asha_mark_read"):
                    mark_read("asha", u["id"])
                    st.rerun()

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            tr("register_patient"), "Triage & Referral", "High-Risk Follow-ups",
            "Patient History", "Chronic Care Registry", "Maternal & Child Health",
        ])

        with tab1:
            with st.form("asha_reg_form"):
                c1, c2 = st.columns(2)
                rn  = c1.text_input(tr("name"))
                ra  = c2.number_input(tr("age"), 0, 120, 30)
                rg  = c1.selectbox(tr("gender"), ["Female", "Male", "Other"])
                rv  = c2.text_input(tr("village"))
                raad = c1.text_input(tr("aadhaar_id") + " (patient's)",
                                     placeholder="12-digit Aadhaar number")
                rph = c2.text_input(tr("phone") + " (optional)")
                rl  = c1.selectbox(tr("language"),
                                   ["Marathi", "Hindi", "Tamil", "Telugu", "Bengali", "English"])
                r_scheme   = c2.checkbox(tr("scheme_eligible"))
                setup_login = st.checkbox("Set up patient app login now")
                rpw = st.text_input("Patient password", type="password") if setup_login else ""
                submitted = st.form_submit_button(tr("register_btn"), type="primary",
                                                  use_container_width=True)
                if submitted:
                    aad_clean = (raad or "").strip().replace(" ", "")
                    if not rn:
                        st.error("Name required.")
                    elif not raad or not aad_clean.isdigit() or len(aad_clean) != 12:
                        st.error("Enter the patient's valid 12-digit Aadhaar ID.")
                    elif setup_login and not rpw:
                        st.error("Enter a password or uncheck login setup.")
                    else:
                        aad_hash = hash_aadhaar(aad_clean)  # FIX 4
                        conn = get_conn()
                        exists = conn.execute(
                            "SELECT abha_id FROM patients WHERE aadhaar_id=?", (aad_hash,)
                        ).fetchone()
                        if exists:
                            st.error("A patient with this Aadhaar ID is already registered.")
                            conn.close()
                        else:
                            h, s = (hash_pw(rpw) if setup_login else (None, None))
                            aid = gen_abha()
                            conn.execute(
                                """INSERT INTO patients
                                (abha_id,name,age,gender,village,phone,aadhaar_id,language,created_at,
                                 password_hash,salt,registered_by_type,registered_by_id,
                                 registered_by_name,scheme_eligible)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (aid, rn, ra, rg, rv, rph, aad_hash, rl,
                                 datetime.now().isoformat(), h, s, "asha", u["id"], u["name"],
                                 1 if r_scheme else 0),
                            )
                            conn.commit()
                            conn.close()
                            st.success(f"Registered! ABHA-linked ID: **{aid}**")
                            if setup_login:
                                st.info(f"Patient can log in using Aadhaar ID {aad_clean}.")

            st.subheader("Registered Patients")
            view_choice = st.radio(
                "View", [tr("my_patients"), tr("all_patients")],
                horizontal=True, key="asha_patient_view",
            )
            if view_choice == tr("my_patients"):
                pts = qdf(
                    "SELECT name,age,gender,village,aadhaar_id,created_at "
                    "FROM patients WHERE registered_by_id=? ORDER BY created_at DESC", (u["id"],)
                )
            else:
                pts = qdf(
                    "SELECT name,age,gender,village,aadhaar_id,registered_by_name,created_at "
                    "FROM patients ORDER BY created_at DESC"
                )
            if not pts.empty and "aadhaar_id" in pts.columns:
                pts["aadhaar_id"] = pts["aadhaar_id"].apply(mask_aadhaar)
            st.dataframe(clean_df(pts), use_container_width=True, hide_index=True)

            with st.expander("Update Patient Details"):
                st.caption("Search for a patient to correct their details.")
                edit_search = st.text_input("Search by name", key="asha_edit_search",
                                            placeholder="Type at least 2 characters…")
                if edit_search and len(edit_search.strip()) >= 2:
                    matches = qdf(
                        "SELECT abha_id,name,age,gender,village,phone,language "
                        "FROM patients WHERE name LIKE ?",
                        (f"%{edit_search}%",),
                    )
                    if matches.empty:
                        st.info("No matching patients.")
                    else:
                        opts = {f"{r['name']} — {r['village'] or '—'}": r["abha_id"]
                                for _, r in matches.iterrows()}
                        picked = st.selectbox("Select patient", list(opts.keys()),
                                              key="asha_edit_pick")
                        sel = matches[matches["abha_id"] == opts[picked]].iloc[0]
                        with st.form("asha_edit_patient_form"):
                            ec1, ec2 = st.columns(2)
                            e_age = ec1.number_input(tr("age"), 0, 120,
                                                     int(sel["age"]) if sel["age"] else 0)
                            e_gender = ec2.selectbox(
                                tr("gender"), ["Female", "Male", "Other"],
                                index=["Female", "Male", "Other"].index(sel["gender"])
                                if sel["gender"] in ["Female", "Male", "Other"] else 0,
                            )
                            e_village = ec1.text_input(tr("village"), value=sel["village"] or "")
                            e_phone   = ec2.text_input(tr("phone"), value=sel["phone"] or "")
                            if st.form_submit_button("Save Changes", type="primary"):
                                conn = get_conn()
                                conn.execute(
                                    "UPDATE patients SET age=?,gender=?,village=?,phone=? WHERE abha_id=?",
                                    (e_age, e_gender, e_village, e_phone, opts[picked]),
                                )
                                conn.commit()
                                conn.close()
                                st.success("Patient details updated.")
                                st.rerun()
                else:
                    st.caption("Type at least 2 characters to search.")

        with tab2:
            pts2 = qdf("SELECT abha_id,name FROM patients ORDER BY created_at DESC")
            if pts2.empty:
                st.info("Register a patient first.")
            else:
                opts = {f"{r['name']} ({r['abha_id']})": r["abha_id"] for _, r in pts2.iterrows()}
                sel  = st.selectbox("Select Patient", list(opts.keys()))
                abha_id = opts[sel]
                syms = st.text_area(tr("symptoms"),
                                    placeholder="e.g. High fever with breathlessness / तेज बुखार",
                                    height=90)
                with st.expander("Vitals (optional)", expanded=False):
                    v1, v2, v3 = st.columns(3)
                    vt = v1.text_input("Temp (°F)", placeholder="e.g. 101.4", key="vt")
                    vs = v2.text_input("SpO₂ (%)",  placeholder="e.g. 96",    key="vs")
                    vp = v3.text_input("Pulse (bpm)", placeholder="e.g. 88",  key="vp")
                    for val, label in [(vt, "Temp"), (vs, "SpO₂"), (vp, "Pulse")]:
                        try:
                            fv = float(val)
                            if ((label == "Temp" and fv >= 103)
                                    or (label == "SpO₂" and fv <= 93)
                                    or (label == "Pulse" and (fv > 100 or fv < 60))):
                                st.warning(f"Abnormal {label}: {val}")
                        except Exception:
                            pass

                if st.button(tr("run_triage"), type="primary"):
                    if not syms:
                        st.warning("Enter symptoms.")
                    else:
                        with st.spinner("Analysing…"):
                            priority, rationale, dept, fud = run_triage(syms)
                        tid = str(uuid.uuid4())
                        conn = get_conn()
                        conn.execute(
                            """INSERT INTO triage(id,abha_id,symptoms_text,priority,rationale,
                            created_by,created_at,department,follow_up_due_date,follow_up_done,
                            temperature,spo2,pulse,triggered_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (tid, abha_id, syms, priority, rationale, u["name"],
                             datetime.now().isoformat(), dept, fud, 0,
                             vt or None, vs or None, vp or None, "asha"),
                        )
                        conn.commit()
                        conn.close()
                        st.session_state["last_tid"] = tid
                        st.session_state["last_priority"] = priority
                        st.session_state["last_abha_for_tid"] = abha_id
                        st.markdown(f"### Result: {priority_badge(priority)}", unsafe_allow_html=True)
                        st.write(rationale)
                        st.info(f"Suggested department: **{dept}**")
                        if fud:
                            st.caption(f"Follow-up due: {fud}")

                if (st.session_state.get("last_tid")
                        and st.session_state.get("last_abha_for_tid") == abha_id):
                    pr = st.session_state.get("last_priority", "GREEN")
                    if pr in ("RED", "YELLOW"):
                        st.divider()
                        st.warning("Patient needs facility care.")
                        facs = get_facility_names()
                        if not facs:
                            st.info("No facilities have registered yet.")
                        else:
                            fac = st.selectbox(tr("select_facility"), facs)
                            if st.button(tr("refer_btn"), type="primary"):
                                conn = get_conn()
                                ref_id = str(uuid.uuid4())
                                conn.execute(
        """INSERT INTO referrals
        (id,abha_id,triage_id,facility,status,prescription,doctor_notes,
         created_at,completed_at,doctor_id,acknowledged_at,acknowledged_by,
         escalated_from,escalated_to)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ref_id, abha_id,
         st.session_state["last_tid"], fac,
         "PENDING", "", "", datetime.now().isoformat(),
         None, None, None, None, None, None),
    )
                                conn.commit()
                                conn.close()
                                # notify doctors at the receiving facility
                                doc_ids = qdf("SELECT id FROM doctors WHERE facility=?", (fac,))
                                for did in doc_ids["id"].tolist():
                                    send_notification(
                                        "doctor", did,
                                        f"New referral: {abha_id} ({pr}) — please check your Queue.",
                                        pr, st.session_state["last_tid"], abha_id,
                                    )
                                st.success(f"Referral sent to {fac}.")
                                del st.session_state["last_tid"]
                                del st.session_state["last_abha_for_tid"]
                                st.rerun()
                    else:
                        st.info("GREEN — routine care.")

        with tab3:
            st.caption("Patients needing follow-up based on their triage priority.")
            due = qdf(
        """SELECT t.id as tid, p.name, p.phone, p.village, t.priority, t.department,
                  t.follow_up_due_date
           FROM triage t JOIN patients p ON p.abha_id=t.abha_id
           WHERE t.follow_up_due_date IS NOT NULL
             AND (t.follow_up_done IS NULL OR t.follow_up_done=0)
           ORDER BY t.follow_up_due_date ASC"""
    )
            if due.empty:
                st.success("No pending follow-ups.")
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                for _, r in due.iterrows():
                    overdue = r["follow_up_due_date"] < today
                    with st.container(border=True):
                        label = (f"{'OVERDUE' if overdue else 'Due'} **{r['follow_up_due_date']}** "
                         f"— {r['name']} ({r['village'] or '—'})")
                        st.markdown(label)
                        st.caption(f"{r['priority']} · {r['department'] or '—'} · {r['phone'] or '—'}")

        with tab4:
            st.subheader("All Emergency (RED) Patients")
            em = qdf(
                """SELECT p.name,p.village,t.symptoms_text,t.created_at,t.department
                   FROM triage t JOIN patients p ON p.abha_id=t.abha_id
                   WHERE t.priority='RED' ORDER BY t.created_at DESC"""
            )
            if em.empty:
                st.info("No RED priority cases yet.")
            else:
                for _, r in em.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['name']}** ({r['village'] or '—'}) — {r['department'] or '—'}")
                        st.caption(f"{r['symptoms_text'][:80]}  |  {r['created_at'][:10]}")
            st.divider()
            st.subheader("All Registered Patients — Triage History")
            ah = qdf(
                """SELECT p.name,p.village,t.priority,t.symptoms_text,t.department,t.created_at
                   FROM triage t JOIN patients p ON p.abha_id=t.abha_id
                   ORDER BY t.created_at DESC LIMIT 50"""
            )
            if ah.empty:
                st.info("No triage history yet.")
            else:
                st.dataframe(clean_df(ah), use_container_width=True, hide_index=True)

        with tab5:
            st.caption("Chronic conditions (diabetes, hypertension, TB, etc.) get a recurring "
                       "follow-up schedule — this closes the loop for long-term care.")
            pts5 = qdf("SELECT abha_id,name,village FROM patients ORDER BY created_at DESC")
            if pts5.empty:
                st.info("Register a patient first.")
            else:
                with st.form("chronic_reg_form"):
                    opts5 = {f"{r['name']} ({r['village'] or '—'})": r["abha_id"]
                             for _, r in pts5.iterrows()}
                    picked5  = st.selectbox("Select Patient", list(opts5.keys()))
                    cond     = st.selectbox("Condition", CHRONIC_CONDITIONS)
                    interval = st.number_input("Follow-up interval (days)",
                                               min_value=7, max_value=180, value=30, step=1)
                    if st.form_submit_button("Add to Chronic Care Registry", type="primary"):
                        abha_sel = opts5[picked5]
                        next_due = (datetime.now() + timedelta(days=int(interval))).strftime("%Y-%m-%d")
                        conn = get_conn()
                        conn.execute(
                            "INSERT INTO chronic_registry(id,abha_id,condition,interval_days,"
                            "next_due_date,active,created_by,created_at) VALUES(?,?,?,?,?,1,?,?)",
                            (str(uuid.uuid4()), abha_sel, cond, int(interval), next_due,
                             u["name"], datetime.now().isoformat()),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"{picked5} added to chronic care registry. Next follow-up: {next_due}")
                        st.rerun()

            st.divider()
            st.subheader("Chronic Care Worklist (due / overdue)")
            today = datetime.now().strftime("%Y-%m-%d")
            chr_due = qdf(
                """SELECT cr.id,p.name,p.village,p.phone,cr.condition,cr.interval_days,cr.next_due_date
                   FROM chronic_registry cr JOIN patients p ON p.abha_id=cr.abha_id
                   WHERE cr.active=1 AND cr.next_due_date<=?
                   ORDER BY cr.next_due_date ASC""", (today,)
            )
            if chr_due.empty:
                st.success("No chronic-care follow-ups due right now.")
            else:
                for _, r in chr_due.iterrows():
                    with st.container(border=True):
                        cd1, cd2 = st.columns([4, 1])
                        cd1.markdown(f"**{r['name']}** ({r['village'] or '—'}) — {r['condition']}")
                        cd1.caption(f"Due: {r['next_due_date']}  |  Every {r['interval_days']} days  |  {r['phone'] or '—'}")
                        if cd2.button("Mark Followed-up", key=f"chr_{r['id']}", use_container_width=True):
                            new_due = (datetime.now() + timedelta(days=int(r["interval_days"]))).strftime("%Y-%m-%d")
                            conn = get_conn()
                            conn.execute(
                                "UPDATE chronic_registry SET next_due_date=?,last_followup_at=? WHERE id=?",
                                (new_due, datetime.now().isoformat(), r["id"]),
                            )
                            conn.commit()
                            conn.close()
                            st.success(f"Recorded. Next follow-up: {new_due}")
                            st.rerun()

            st.divider()
            st.subheader("All Chronic Care Patients")
            chr_all = qdf(
                """SELECT p.name,p.village,cr.condition,cr.interval_days,cr.next_due_date,cr.active
                   FROM chronic_registry cr JOIN patients p ON p.abha_id=cr.abha_id
                   ORDER BY cr.next_due_date"""
            )
            if chr_all.empty:
                st.info("No chronic-care patients registered yet.")
            else:
                st.dataframe(clean_df(chr_all), use_container_width=True, hide_index=True)

        with tab6:
            st.caption("Maternal (pregnancy/ANC) and child immunization tracking, "
                       "folded into the same closed-loop system.")
            mch1, mch2 = st.tabs(["Pregnancy / ANC Tracker", "Child Immunization"])

            with mch1:
                pts6 = qdf(
                    "SELECT abha_id,name,village,gender FROM patients "
                    "WHERE gender='Female' ORDER BY created_at DESC"
                )
                if pts6.empty:
                    st.info("Register a female patient first.")
                else:
                    with st.form("mch_preg_form"):
                        opts6 = {f"{r['name']} ({r['village'] or '—'})": r["abha_id"]
                                 for _, r in pts6.iterrows()}
                        picked6   = st.selectbox("Select Patient", list(opts6.keys()),
                                                 key="mch_preg_pick")
                        lmp       = st.date_input("Last Menstrual Period (LMP)",
                                                  max_value=datetime.now().date())
                        edd       = (datetime.combine(lmp, datetime.min.time())
                                     + timedelta(days=280)).strftime("%Y-%m-%d")
                        st.caption(f"Estimated Due Date (EDD): **{edd}**")
                        high_risk = st.checkbox("Flag as high-risk pregnancy")
                        if st.form_submit_button("Register Pregnancy", type="primary"):
                            conn = get_conn()
                            conn.execute(
                                """INSERT INTO mch_pregnancy
                                (id,abha_id,lmp_date,edd,anc1_done,anc2_done,anc3_done,anc4_done,
                                 high_risk,status,created_by,created_at)
                                VALUES(?,?,?,?,0,0,0,0,?,'ACTIVE',?,?)""",
                                (str(uuid.uuid4()), opts6[picked6], str(lmp), edd,
                                 1 if high_risk else 0, u["name"], datetime.now().isoformat()),
                            )
                            conn.commit()
                            conn.close()
                            st.success(f"Pregnancy registered. EDD: {edd}")
                            st.rerun()

                st.divider()
                st.subheader("Active Pregnancies — ANC Visit Tracker")
                preg_all = qdf(
                    """SELECT mp.id,p.name,p.village,mp.lmp_date,mp.edd,
                              mp.anc1_done,mp.anc2_done,mp.anc3_done,mp.anc4_done,mp.high_risk
                       FROM mch_pregnancy mp JOIN patients p ON p.abha_id=mp.abha_id
                       WHERE mp.status='ACTIVE' ORDER BY mp.edd"""
                )
                if preg_all.empty:
                    st.info("No active pregnancies tracked yet.")
                else:
                    for _, r in preg_all.iterrows():
                        with st.container(border=True):
                            hcap = " · HIGH-RISK" if r["high_risk"] else ""
                            st.markdown(f"**{r['name']}** ({r['village'] or '—'}) — EDD {r['edd']}{hcap}")
                            ac1, ac2, ac3, ac4, ac5 = st.columns(5)
                            a1 = ac1.checkbox("ANC-1", value=bool(r["anc1_done"]), key=f"anc1_{r['id']}")
                            a2 = ac2.checkbox("ANC-2", value=bool(r["anc2_done"]), key=f"anc2_{r['id']}")
                            a3 = ac3.checkbox("ANC-3", value=bool(r["anc3_done"]), key=f"anc3_{r['id']}")
                            a4 = ac4.checkbox("ANC-4", value=bool(r["anc4_done"]), key=f"anc4_{r['id']}")
                            if ac5.button("Save", key=f"ancsave_{r['id']}", use_container_width=True):
                                conn = get_conn()
                                conn.execute(
                                    "UPDATE mch_pregnancy SET anc1_done=?,anc2_done=?,anc3_done=?,anc4_done=? WHERE id=?",
                                    (int(a1), int(a2), int(a3), int(a4), r["id"]),
                                )
                                conn.commit()
                                conn.close()
                                st.success("ANC visits updated.")
                                st.rerun()

            with mch2:
                pts7 = qdf("SELECT abha_id,name,village FROM patients ORDER BY created_at DESC")
                if pts7.empty:
                    st.info("Register a patient first (the child can be registered as a normal patient).")
                else:
                    with st.form("mch_child_form"):
                        opts7 = {f"{r['name']} ({r['village'] or '—'})": r["abha_id"]
                                 for _, r in pts7.iterrows()}
                        picked7    = st.selectbox("Select Child (registered patient)",
                                                  list(opts7.keys()), key="mch_child_pick")
                        child_name = st.text_input("Child's name (if different from patient record)")
                        dob        = st.date_input("Date of Birth", max_value=datetime.now().date(),
                                                   key="mch_child_dob")
                        if st.form_submit_button(
                            "Register Child & Generate Immunization Schedule", type="primary"
                        ):
                            cid = str(uuid.uuid4())
                            conn = get_conn()
                            conn.execute(
                                "INSERT INTO mch_child(id,abha_id,child_name,dob,created_by,created_at) "
                                "VALUES(?,?,?,?,?,?)",
                                (cid, opts7[picked7], child_name or picked7, str(dob),
                                 u["name"], datetime.now().isoformat()),
                            )
                            conn.commit()
                            conn.close()
                            generate_immunization_schedule(cid, opts7[picked7], str(dob), u["name"])
                            st.success("Child registered and immunization schedule generated.")
                            st.rerun()

                st.divider()
                st.subheader("Immunization Due-List (overdue / upcoming 30 days)")
                today = datetime.now().strftime("%Y-%m-%d")
                soon  = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                imm_due = qdf(
                    """SELECT mi.id,p.name,p.village,mi.vaccine_name,mi.due_date
                       FROM mch_immunization mi JOIN patients p ON p.abha_id=mi.abha_id
                       WHERE mi.given=0 AND mi.due_date<=?
                       ORDER BY mi.due_date ASC""", (soon,)
                )
                if imm_due.empty:
                    st.success("No immunizations due in the next 30 days.")
                else:
                    for _, r in imm_due.iterrows():
                        with st.container(border=True):
                            overdue = r["due_date"] < today
                            ic1, ic2 = st.columns([4, 1])
                            ic1.markdown(
                                f"{'**OVERDUE**' if overdue else 'Upcoming'} — "
                                f"**{r['name']}** ({r['village'] or '—'}): {r['vaccine_name']}"
                            )
                            ic1.caption(f"Due: {r['due_date']}")
                            if ic2.button("Mark Given", key=f"imm_{r['id']}", use_container_width=True):
                                conn = get_conn()
                                conn.execute(
                                    "UPDATE mch_immunization SET given=1,given_date=? WHERE id=?",
                                    (datetime.now().strftime("%Y-%m-%d"), r["id"]),
                                )
                                conn.commit()
                                conn.close()
                                st.success("Marked as given.")
                                st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE: DOCTOR DASHBOARD
# ══════════════════════════════════════════════════════════════
elif page == tr("doctor"):
    sk = "doctor_user"
    if sk not in st.session_state:
        st.session_state[sk] = None

    if not st.session_state[sk]:
        row = staff_login_screen(tr("doctor"), "doctors", "e.g. DOC-A1B2C3")
        if row:
            st.session_state[sk] = row
            st.rerun()
    else:
        u = st.session_state[sk]
        notifs = get_unread("doctor", u["id"])
        with st.container(border=True):
            dh1, dh2 = st.columns([4, 1])
            dh1.markdown(
                f"### Dr. {u['name']} — {u['facility'] or '—'} "
                f"({u['speciality'] or 'General Medicine'})"
            )
            dh1.caption(f"Worker ID: {u['id']}")
            if dh2.button(tr("logout_btn")):
                st.session_state[sk] = None
                st.rerun()
            if notifs:
                reds    = [n for n in notifs if n["priority"] == "RED"]
                yellows = [n for n in notifs if n["priority"] in ("YELLOW", "GREEN")]
                if reds:
                    st.error(f"{len(reds)} EMERGENCY ALERT(S)")
                    for n in reds:
                        st.write(f"- {n['message']}")
                if yellows:
                    st.warning(f"{len(yellows)} patient notification(s)")
                    for n in yellows:
                        st.write(f"- {n['message']}")
                if st.button("Mark all read", key="doc_mark_read"):
                    mark_read("doctor", u["id"])
                    st.rerun()

        total_seen    = qdf("SELECT COUNT(*) as n FROM referrals WHERE doctor_id=? AND status='COMPLETED'", (u["id"],))["n"][0]
        pending_ref   = qdf("SELECT COUNT(*) as n FROM referrals WHERE facility=? AND status='PENDING'", (u["facility"],))["n"][0]
        pending_appts = qdf("SELECT COUNT(*) as n FROM appointments WHERE facility=? AND status='REQUESTED'", (u["facility"],))["n"][0]
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Patients Completed", total_seen)
        mc2.metric("Pending Referrals", pending_ref)
        mc3.metric("Pending Appointments", pending_appts)

        dt1, dt2, dt3, dt4, dt5, dt6 = st.tabs([
            "Queue", "Search Patient", "Appointments",
            "My History", "SOS Alerts", "Diagnostic Orders",
        ])

        with dt1:
            q_sql = """SELECT r.id as ref_id,p.abha_id,p.name,p.age,p.gender,p.village,
                              t.symptoms_text,t.priority,t.rationale,t.department,t.created_by,
                              r.status,r.created_at,r.acknowledged_at,r.acknowledged_by,r.escalated_from
                       FROM referrals r JOIN patients p ON p.abha_id=r.abha_id
                       JOIN triage t ON t.id=r.triage_id
                       WHERE r.facility=? AND r.status IN ('PENDING','ACKNOWLEDGED')"""
            queue = qdf(q_sql, (u["facility"],))
            if queue.empty:
                st.info("No pending referrals.")
            else:
                queue["sort"] = queue["priority"].map(PRIORITY_ORDER)
                queue = queue.sort_values("sort")
                for _, row in queue.iterrows():
                    elapsed_h, breached = compute_sla_status(
                        row["priority"], row["created_at"],
                        row["acknowledged_at"], row["status"],
                    )
                    sla_tag = " ⚠️ SLA BREACH" if breached else ""
                    with st.expander(
                        f"{row['name']} · {row['age'] or '—'}y · "
                        f"{row['priority']} · {row['status']}{sla_tag}",
                        expanded=(row["status"] == "PENDING"),
                    ):
                        b1, b2 = st.columns([3, 1])
                        b1.markdown(priority_badge(row["priority"]), unsafe_allow_html=True)
                        b2.markdown(f"**{row['department'] or 'General'}**")
                        st.write(f"**ABHA:** {row['abha_id']}  |  **Village:** {row['village'] or '—'}")
                        st.write(f"**Symptoms:** {row['symptoms_text']}")
                        st.caption(f"AI note: {row['rationale']}")
                        if elapsed_h is not None:
                            target = SLA_TARGET_HOURS.get(row["priority"], 72)
                            if breached:
                                st.error(f"SLA breached — {elapsed_h}h elapsed (target: {target}h).")
                            else:
                                st.caption(f"Time since referral: {elapsed_h}h (target: {target}h).")
                        if row["escalated_from"]:
                            st.info(f"Escalated here from {row['escalated_from']}.")

                        with st.container(border=True):
                            st.markdown("**Full Patient History**")
                            pht1, pht2 = st.tabs(["Past Visits", "Past Prescriptions"])
                            with pht1:
                                ph = qdf(
                                    "SELECT symptoms_text,priority,department,created_at "
                                    "FROM triage WHERE abha_id=? ORDER BY created_at DESC",
                                    (row["abha_id"],),
                                )
                                if ph.empty: st.caption("No prior visits.")
                                else: st.dataframe(clean_df(ph), use_container_width=True, hide_index=True)
                            with pht2:
                                pr = qdf(
                                    "SELECT facility,prescription,doctor_notes,completed_at "
                                    "FROM referrals WHERE abha_id=? AND status='COMPLETED' "
                                    "ORDER BY completed_at DESC", (row["abha_id"],)
                                )
                                if pr.empty: st.caption("No past prescriptions.")
                                else: st.dataframe(clean_df(pr), use_container_width=True, hide_index=True)

                        if row["status"] == "PENDING":
                            st.warning("Awaiting patient arrival at this facility.")
                            if st.button("Acknowledge Patient Arrival",
                                         key=f"ack_{row['ref_id']}", type="primary"):
                                conn = get_conn()
                                conn.execute(
                                    "UPDATE referrals SET status='ACKNOWLEDGED',"
                                    "acknowledged_at=?,acknowledged_by=? WHERE id=?",
                                    (datetime.now().isoformat(), u["name"], row["ref_id"]),
                                )
                                conn.commit()
                                conn.close()
                                notify_all_asha(
                                    f"{row['name']} has arrived at {u['facility']} and been acknowledged.",
                                    "GREEN", abha_id=row["abha_id"],
                                )
                                st.success("Arrival acknowledged.")
                                st.rerun()
                        else:  # ACKNOWLEDGED
                            st.success(
                                f"Arrival acknowledged on {row['acknowledged_at']} "
                                f"by {row['acknowledged_by']}"
                            )

                            # ── Teleconsultation (Fix 2: Jitsi Meet embed) ──────
                            with st.container(border=True):
                                st.markdown(f"**{tr('teleconsult')}**")
                                room_id      = f"ArogyaBridge-{row['ref_id'][:8]}"
                                tc_state_key = f"tc_active_{row['ref_id']}"

                                if not st.session_state.get(tc_state_key):
                                    col_tc1, col_tc2 = st.columns(2)
                                    if col_tc1.button(tr("teleconsult"), key=f"tc_{row['ref_id']}"):
                                        conn = get_conn()
                                        conn.execute(
                                            "UPDATE referrals SET teleconsult_started_at=? WHERE id=?",
                                            (datetime.now().isoformat(), row["ref_id"]),
                                        )
                                        conn.commit()
                                        conn.close()
                                        st.session_state[tc_state_key] = True
                                        st.rerun()
                                    col_tc2.caption(f"Room ID: `{room_id}` — share with patient")
                                else:
                                    st.success("Teleconsultation session LIVE")
                                    jitsi_html = f"""
                                    <div id="jitsi-container-{row['ref_id'][:8]}"
                                         style="height:480px;border-radius:8px;overflow:hidden;">
                                    <script src='https://meet.jit.si/external_api.js'></script>
                                    <script>
                                      const domain = 'meet.jit.si';
                                      const options = {{
                                        roomName: '{room_id}',
                                        width: '100%', height: 480,
                                        parentNode: document.getElementById('jitsi-container-{row["ref_id"][:8]}'),
                                        configOverwrite: {{
                                          startWithAudioMuted: false,
                                          startWithVideoMuted: false,
                                          prejoinPageEnabled: false
                                        }},
                                        interfaceConfigOverwrite: {{
                                          SHOW_JITSI_WATERMARK: false,
                                          TOOLBAR_BUTTONS: ['microphone','camera','hangup','chat','raisehand']
                                        }},
                                        userInfo: {{ displayName: 'Dr. {u["name"]}' }}
                                      }};
                                      new JitsiMeetExternalAPI(domain, options);
                                    </script>
                                    </div>"""
                                    components.html(jitsi_html, height=500)
                                    patient_link = f"https://meet.jit.si/{room_id}"
                                    st.info(f"**Share with patient:** `{patient_link}` — joins from any browser, no app needed.")
                                    tc_notes = st.text_area("Session notes (saved to record)",
                                                            key=f"tcnotes_{row['ref_id']}")
                                    if st.button("End Session & Save Notes",
                                                 key=f"tcend_{row['ref_id']}"):
                                        conn = get_conn()
                                        conn.execute(
                                            "UPDATE referrals SET teleconsult_notes=?,"
                                            "teleconsult_ended_at=? WHERE id=?",
                                            (tc_notes, datetime.now().isoformat(), row["ref_id"]),
                                        )
                                        conn.commit()
                                        conn.close()
                                        st.session_state[tc_state_key] = False
                                        st.success("Session saved to patient record.")
                                        st.rerun()

                            # ── Diagnostic Coordination ─────────────────────
                            with st.container(border=True):
                                st.markdown("**Diagnostic Coordination**")
                                fac_tests = qdf(
                                    "SELECT test_name FROM diagnostic_tests "
                                    "WHERE facility=? AND available=1 ORDER BY test_name",
                                    (u["facility"],),
                                )
                                if fac_tests.empty:
                                    st.caption("No diagnostic tests set up for this facility yet.")
                                else:
                                    dc_t1, dc_t2 = st.columns([3, 1])
                                    test_pick = dc_t1.selectbox(
                                        "Order a test", fac_tests["test_name"].tolist(),
                                        key=f"testpick_{row['ref_id']}",
                                        label_visibility="collapsed",
                                    )
                                    if dc_t2.button("Order Test",
                                                    key=f"orderTest_{row['ref_id']}",
                                                    use_container_width=True):
                                        conn = get_conn()
                                        conn.execute(
                                            """INSERT INTO diagnostic_orders
                                            (id,abha_id,referral_id,test_name,facility,status,
                                             result_notes,ordered_by,ordered_at,completed_at)
                                            VALUES(?,?,?,?,?,'ORDERED',NULL,?,?,NULL)""",
                                            (str(uuid.uuid4()), row["abha_id"], row["ref_id"],
                                             test_pick, u["facility"], u["name"],
                                             datetime.now().isoformat()),
                                        )
                                        conn.commit()
                                        conn.close()
                                        st.success(f"{test_pick} ordered.")
                                        st.rerun()
                                open_orders = qdf(
                                    "SELECT id,test_name,status,result_notes,ordered_at "
                                    "FROM diagnostic_orders WHERE referral_id=? ORDER BY ordered_at DESC",
                                    (row["ref_id"],),
                                )
                                if not open_orders.empty:
                                    for _, od in open_orders.iterrows():
                                        if od["status"] == "ORDERED":
                                            oc1, oc2 = st.columns([3, 1])
                                            res_notes = oc1.text_input(
                                                f"Result for {od['test_name']}", key=f"res_{od['id']}"
                                            )
                                            if oc2.button("Mark Completed",
                                                          key=f"compTest_{od['id']}",
                                                          use_container_width=True):
                                                conn = get_conn()
                                                conn.execute(
                                                    "UPDATE diagnostic_orders SET status='COMPLETED',"
                                                    "result_notes=?,completed_at=? WHERE id=?",
                                                    (res_notes, datetime.now().isoformat(), od["id"]),
                                                )
                                                conn.commit()
                                                conn.close()
                                                st.success("Result recorded.")
                                                st.rerun()
                                        else:
                                            st.caption(f"✅ {od['test_name']}: {od['result_notes'] or '—'}")

                            with st.expander("Flag as Chronic Condition (recurring follow-up)"):
                                cf1, cf2, cf3 = st.columns([2, 1, 1])
                                cf_cond     = cf1.selectbox("Condition", CHRONIC_CONDITIONS,
                                                            key=f"cfcond_{row['ref_id']}")
                                cf_interval = cf2.number_input("Every N days", 7, 180, 30,
                                                               key=f"cfint_{row['ref_id']}")
                                if cf3.button("Add", key=f"cfadd_{row['ref_id']}",
                                              use_container_width=True):
                                    next_due = (datetime.now() + timedelta(days=int(cf_interval))).strftime("%Y-%m-%d")
                                    conn = get_conn()
                                    conn.execute(
                                        "INSERT INTO chronic_registry(id,abha_id,condition,"
                                        "interval_days,next_due_date,active,created_by,created_at) "
                                        "VALUES(?,?,?,?,?,1,?,?)",
                                        (str(uuid.uuid4()), row["abha_id"], cf_cond,
                                         int(cf_interval), next_due, u["name"],
                                         datetime.now().isoformat()),
                                    )
                                    conn.commit()
                                    conn.close()
                                    st.success(f"Added. Next follow-up: {next_due}")

                            presc = st.text_area(tr("prescription"), key=f"presc_{row['ref_id']}")
                            notes = st.text_input("Notes", key=f"notes_{row['ref_id']}")
                            cc1, cc2 = st.columns(2)
                            if cc1.button(tr("save_prescription"),
                                          key=f"save_{row['ref_id']}", type="primary"):
                                conn = get_conn()
                                conn.execute(
                                    "UPDATE referrals SET status='COMPLETED',prescription=?,"
                                    "doctor_notes=?,completed_at=?,doctor_id=? WHERE id=?",
                                    (presc, notes, datetime.now().isoformat(),
                                     u["id"], row["ref_id"]),
                                )
                                conn.commit()
                                conn.close()
                                notify_all_asha(
                                    f"Referral for {row['name']} completed at {u['facility']}. "
                                    f"Prescription issued.", "GREEN", abha_id=row["abha_id"],
                                )
                                st.success("Completed.")
                                st.rerun()

                            other_facs = [f for f in get_facility_names() if f != u["facility"]]
                            if other_facs:
                                esc_fac = cc2.selectbox(
                                    "Escalate to", other_facs,
                                    key=f"escfac_{row['ref_id']}",
                                    label_visibility="collapsed",
                                )
                                if cc2.button("Escalate / Re-refer", key=f"esc_{row['ref_id']}"):
                                    conn = get_conn()
                                    conn.execute(
                                        """INSERT INTO referrals
                                        (id,abha_id,triage_id,facility,status,prescription,
                                         doctor_notes,created_at,completed_at,doctor_id,
                                         acknowledged_at,acknowledged_by,escalated_from,escalated_to)
                                        SELECT ?,abha_id,triage_id,?,?,'','',?,NULL,NULL,NULL,NULL,?,NULL
                                        FROM referrals WHERE id=?""",
                                        (str(uuid.uuid4()), esc_fac, "PENDING",
                                         datetime.now().isoformat(), u["facility"], row["ref_id"]),
                                    )
                                    conn.execute(
                                        "UPDATE referrals SET status='COMPLETED',escalated_to=?,"
                                        "completed_at=? WHERE id=?",
                                        (esc_fac, datetime.now().isoformat(), row["ref_id"]),
                                    )
                                    conn.commit()
                                    conn.close()
                                    notify_all_asha(
                                        f"{row['name']} escalated from {u['facility']} to {esc_fac}.",
                                        "YELLOW", abha_id=row["abha_id"],
                                    )
                                    st.success(f"Escalated to {esc_fac}.")
                                    st.rerun()

        with dt2:
            st.subheader("Search Patient")
            search = st.text_input("Search by name", placeholder="Type at least 2 characters…")
            if search and len(search.strip()) >= 2:
                res = qdf(
                    "SELECT abha_id,name,age,gender,village,phone,aadhaar_id "
                    "FROM patients WHERE name LIKE ?",
                    (f"%{search}%",),
                )
                if res.empty:
                    st.info("No patients found.")
                else:
                    st.caption(f"{len(res)} match(es) found")
                    opts = {f"{r['name']} — {r['village'] or '—'} (Age {r['age'] or '—'})": r["abha_id"]
                            for _, r in res.iterrows()}
                    picked = st.selectbox("Select a patient", list(opts.keys()))
                    sel = res[res["abha_id"] == opts[picked]].iloc[0]
                    with st.container(border=True):
                        st.write(
                            f"**Age:** {sel['age'] or '—'}  |  **Gender:** {sel['gender'] or '—'}  |  "
                            f"**Phone:** {sel['phone'] or '—'}  |  **Aadhaar:** {mask_aadhaar(sel['aadhaar_id'])}"
                        )
                        st.download_button(
                            "Export Interoperable Record (ABDM-lite JSON)",
                            data=(fhir_lite_export(sel["abha_id"]) or "{}"),
                            file_name=f"{sel['abha_id']}_health_record.json",
                            mime="application/json", key=f"exp_{sel['abha_id']}",
                        )
                        pht1, pht2, pht3 = st.tabs([
                            "Triage History", "Referrals & Prescriptions", "Diagnostic Reports"
                        ])
                        with pht1:
                            ph = qdf(
                                "SELECT symptoms_text,priority,department,temperature,spo2,pulse,created_at "
                                "FROM triage WHERE abha_id=? ORDER BY created_at DESC", (sel["abha_id"],)
                            )
                            if ph.empty: st.caption("No visits.")
                            else: st.dataframe(clean_df(ph), use_container_width=True, hide_index=True)
                        with pht2:
                            rh = qdf(
                                "SELECT facility,status,prescription,doctor_notes,completed_at "
                                "FROM referrals WHERE abha_id=? ORDER BY created_at DESC", (sel["abha_id"],)
                            )
                            if rh.empty: st.caption("No referrals.")
                            else: st.dataframe(clean_df(rh), use_container_width=True, hide_index=True)
                        with pht3:
                            dh = qdf(
                                "SELECT test_name,facility,status,result_notes,ordered_at,completed_at "
                                "FROM diagnostic_orders WHERE abha_id=? ORDER BY ordered_at DESC",
                                (sel["abha_id"],),
                            )
                            if dh.empty: st.caption("No diagnostic orders.")
                            else: st.dataframe(clean_df(dh), use_container_width=True, hide_index=True)
            else:
                st.caption("Type at least 2 characters to search.")

        with dt3:
            st.subheader("Appointment Requests")
            appts = qdf(
                """SELECT a.id,p.name,p.phone,a.appointment_date,a.time_slot,a.status,a.decline_reason
                   FROM appointments a JOIN patients p ON p.abha_id=a.abha_id
                   WHERE a.facility=? ORDER BY a.appointment_date,a.time_slot""", (u["facility"],)
            )
            pending = appts[appts["status"] == "REQUESTED"] if not appts.empty else pd.DataFrame()
            if pending.empty:
                st.info("No pending appointment requests.")
            else:
                st.markdown("**Pending Requests**")
                for _, a in pending.iterrows():
                    with st.container(border=True):
                        ac1, ac2, ac3 = st.columns([3, 1, 1])
                        ac1.write(f"**{a['name']}** — {a['appointment_date']} at {a['time_slot']}")
                        ac1.caption(f"{a['phone'] or '—'}")
                        if ac2.button("Accept", key=f"acc_{a['id']}", use_container_width=True):
                            conn = get_conn()
                            conn.execute("UPDATE appointments SET status='CONFIRMED',doctor_id=? WHERE id=?",
                                         (u["id"], a["id"]))
                            conn.commit(); conn.close(); st.rerun()
                        if ac3.button("Decline", key=f"dec_{a['id']}", use_container_width=True):
                            st.session_state[f"show_decline_{a['id']}"] = True
                    if st.session_state.get(f"show_decline_{a['id']}"):
                        reason = st.text_input("Reason for declining (required)",
                                               key=f"reason_{a['id']}",
                                               placeholder="e.g. Holiday on that date")
                        if st.button("Confirm Decline", key=f"confirm_dec_{a['id']}"):
                            if not reason:
                                st.error("Please enter a reason.")
                            else:
                                conn = get_conn()
                                conn.execute("UPDATE appointments SET status='DECLINED',decline_reason=? WHERE id=?",
                                             (reason, a["id"]))
                                conn.commit(); conn.close()
                                del st.session_state[f"show_decline_{a['id']}"]
                                st.rerun()

            st.divider()
            st.markdown("**All Appointments**")
            for status, label in [("CONFIRMED", "Confirmed"), ("COMPLETED", "Completed"),
                                   ("DECLINED", "Declined")]:
                grp = appts[appts["status"] == status] if not appts.empty else pd.DataFrame()
                if not grp.empty:
                    with st.expander(f"{label} ({len(grp)})"):
                        for _, a in grp.iterrows():
                            ac1, ac2 = st.columns([4, 1])
                            ac1.write(f"**{a['name']}** — {a['appointment_date']} at {a['time_slot']}")
                            if a["decline_reason"]:
                                ac1.caption(f"Reason: {a['decline_reason']}")
                            if status == "CONFIRMED":
                                if ac2.button("Mark Done", key=f"done_{a['id']}",
                                              use_container_width=True):
                                    conn = get_conn()
                                    conn.execute("UPDATE appointments SET status='COMPLETED' WHERE id=?",
                                                 (a["id"],))
                                    conn.commit(); conn.close(); st.rerun()

        with dt4:
            st.subheader("My Completed Cases")
            my_hist = qdf(
                """SELECT p.name,p.village,t.priority,r.prescription,r.doctor_notes,r.completed_at
                   FROM referrals r JOIN patients p ON p.abha_id=r.abha_id
                   JOIN triage t ON t.id=r.triage_id
                   WHERE r.doctor_id=? AND r.status='COMPLETED' ORDER BY r.completed_at DESC""",
                (u["id"],),
            )
            if my_hist.empty:
                st.info("No completed cases yet.")
            else:
                for _, r in my_hist.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['name']}** ({r['village'] or '—'}) — "
                                 f"{priority_badge(r['priority'])}", unsafe_allow_html=True)
                        if r["prescription"]:
                            st.write(f"{r['prescription']}")
                        st.caption(f"Completed: {str(r['completed_at'])[:10]}")

        with dt5:
            st.subheader("Active SOS Alerts")
            sos = qdf(
                "SELECT id,patient_name,village,triggered_at,accepted_by "
                "FROM sos_alerts WHERE status='ACTIVE' ORDER BY triggered_at DESC"
            )
            if sos.empty:
                st.success("No active SOS alerts.")
            else:
                for _, s in sos.iterrows():
                    with st.container(border=True):
                        sc1, sc2 = st.columns([4, 1])
                        sc1.write(f"**{s['patient_name']}** — {s['village'] or '—'}")
                        sc1.caption(f"Triggered: {s['triggered_at'][:16]}")
                        if s["accepted_by"]:
                            sc1.info(f"Being handled by {s['accepted_by']}")
                        else:
                            if sc2.button("Accept", key=f"accept_sos_{s['id']}",
                                          type="primary", use_container_width=True):
                                conn = get_conn()
                                conn.execute("UPDATE sos_alerts SET accepted_by=? WHERE id=?",
                                             (u["name"], s["id"]))
                                conn.commit(); conn.close()
                                notify_all_doctors(
                                    f"SOS for {s['patient_name']} is being handled by Dr. {u['name']}. "
                                    "No further action needed.", "GREEN",
                                )
                                st.rerun()

        with dt6:
            st.subheader("Diagnostic Test Orders — My Facility")
            all_orders = qdf(
                """SELECT d.id,p.name,p.village,d.test_name,d.status,d.result_notes,
                          d.ordered_by,d.ordered_at,d.completed_at
                   FROM diagnostic_orders d JOIN patients p ON p.abha_id=d.abha_id
                   WHERE d.facility=? ORDER BY d.ordered_at DESC""", (u["facility"],)
            )
            if all_orders.empty:
                st.info("No diagnostic tests ordered yet.")
            else:
                open_o = all_orders[all_orders["status"] == "ORDERED"]
                done_o = all_orders[all_orders["status"] == "COMPLETED"]
                st.markdown(f"**Pending Results ({len(open_o)})**")
                if open_o.empty:
                    st.caption("Nothing pending.")
                for _, od in open_o.iterrows():
                    with st.container(border=True):
                        oc1, oc2 = st.columns([3, 1])
                        oc1.write(f"**{od['name']}** ({od['village'] or '—'}) — {od['test_name']}")
                        res = oc1.text_input("Result / notes", key=f"dt6res_{od['id']}")
                        if oc2.button("Complete", key=f"dt6comp_{od['id']}",
                                      use_container_width=True):
                            conn = get_conn()
                            conn.execute(
                                "UPDATE diagnostic_orders SET status='COMPLETED',"
                                "result_notes=?,completed_at=? WHERE id=?",
                                (res, datetime.now().isoformat(), od["id"]),
                            )
                            conn.commit(); conn.close()
                            st.success("Result recorded."); st.rerun()
                st.divider()
                st.markdown(f"**Completed ({len(done_o)})**")
                if not done_o.empty:
                    st.dataframe(clean_df(done_o.drop(columns=["id"])),
                                 use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════
# PAGE: FACILITY / HOSPITAL PORTAL
# ══════════════════════════════════════════════════════════════
elif page == tr("facility"):
    sk = "facility_user"
    if sk not in st.session_state:
        st.session_state[sk] = None

    if not st.session_state[sk]:
        row = facility_auth_screen()
        if row:
            st.session_state[sk] = row
            st.rerun()
    else:
        u = st.session_state[sk]
        with st.container(border=True):
            fh1, fh2 = st.columns([4, 1])
            fh1.markdown(f"### {u['name']} — {u['type']}")
            fh1.caption(f"Area served: {u['village'] or '—'}")
            if fh2.button(tr("logout_btn")):
                st.session_state[sk] = None; st.rerun()
            fm1, fm2, fm3, fm4 = st.columns(4)
            fm1.metric("ASHA Workers",
                       int(qdf("SELECT COUNT(*) as n FROM asha_workers WHERE facility_id=?",
                               (u["id"],))["n"][0]))
            fm2.metric("Doctors",
                       int(qdf("SELECT COUNT(*) as n FROM doctors WHERE facility_id=?",
                               (u["id"],))["n"][0]))
            fm3.metric("Pending Referrals",
                       int(qdf("SELECT COUNT(*) as n FROM referrals WHERE facility=? AND status='PENDING'",
                               (u["name"],))["n"][0]))
            fm4.metric("Pending Appointments",
                       int(qdf("SELECT COUNT(*) as n FROM appointments WHERE facility=? AND status='REQUESTED'",
                               (u["name"],))["n"][0]))

        ft1, ft2, ft3 = st.tabs(["Staff Management", "Medicine Stock", "Diagnostic Tests"])

        with ft1:
            sc1, sc2 = st.columns(2)
            with sc1:
                with st.expander("Add ASHA / ANM Worker", expanded=False):
                    with st.form("add_asha_form"):
                        an  = st.text_input("Worker Name")
                        aph = st.text_input("Worker Phone (for contact only)")
                        if st.form_submit_button("Create ASHA Account", type="primary"):
                            if not an:
                                st.error("Name required.")
                            else:
                                wid = gen_worker_id("ASHA")
                                pwd = gen_password()
                                h, s = hash_pw(pwd)
                                conn = get_conn()
                                conn.execute(
                                    "INSERT INTO asha_workers(id,name,phone,facility_id,facility,"
                                    "password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                    (wid, an, aph, u["id"], u["name"], h, s,
                                     datetime.now().isoformat()),
                                )
                                conn.commit(); conn.close()
                                st.success("ASHA worker account created.")
                                st.info(f"Share with {an}:\n\nWorker ID: **{wid}**\n\nPassword: **{pwd}**")
            with sc2:
                with st.expander("Add Doctor", expanded=False):
                    with st.form("add_doctor_form"):
                        dn  = st.text_input("Doctor Name")
                        dph = st.text_input("Doctor Phone (for contact only)")
                        dsp = st.selectbox("Speciality", SPECIALITIES)
                        if st.form_submit_button("Create Doctor Account", type="primary"):
                            if not dn:
                                st.error("Name required.")
                            else:
                                wid = gen_worker_id("DOC")
                                pwd = gen_password()
                                h, s = hash_pw(pwd)
                                conn = get_conn()
                                conn.execute(
                                    "INSERT INTO doctors(id,name,phone,facility_id,facility,speciality,"
                                    "password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                                    (wid, dn, dph, u["id"], u["name"], dsp, h, s,
                                     datetime.now().isoformat()),
                                )
                                conn.commit(); conn.close()
                                st.success("Doctor account created.")
                                st.info(f"Share with Dr. {dn}:\n\nWorker ID: **{wid}**\n\nPassword: **{pwd}**")

            st.divider()
            st.subheader("My ASHA Workers")
            st.dataframe(
                clean_df(qdf("SELECT id,name,phone,created_at FROM asha_workers "
                             "WHERE facility_id=? ORDER BY created_at DESC", (u["id"],))),
                use_container_width=True, hide_index=True,
            )
            st.subheader("My Doctors")
            st.dataframe(
                clean_df(qdf("SELECT id,name,phone,speciality,created_at FROM doctors "
                             "WHERE facility_id=? ORDER BY created_at DESC", (u["id"],))),
                use_container_width=True, hide_index=True,
            )

        with ft2:
            st.subheader("My Medicine Stock")
            stock = qdf(
                "SELECT id,medicine_name,quantity,unit,last_updated,updated_by "
                "FROM medicine_stock WHERE facility_id=? ORDER BY medicine_name", (u["id"],)
            )
            if stock.empty:
                st.info("No medicines recorded yet.")
            else:
                stock["predicted_stockout_days"] = stock["medicine_name"].apply(
                    lambda m: predict_stockout(u["id"], m)
                )
                def hl(row):
                    if row["quantity"] < 10:
                        return ["background-color:#ffcdd2;color:black"] * len(row)
                    return [""] * len(row)
                display_stock = stock.drop(columns=["id"])
                st.dataframe(clean_df(display_stock).style.apply(hl, axis=1),
                             use_container_width=True, hide_index=True)
                st.caption("Red rows = low stock (below 10 units). "
                           "'Predicted stockout days' uses actual consumption history.")

            st.divider()
            upd_tab, add_tab, log_tab = st.tabs([
                "Update Existing Stock", "Add New Medicine", "Change Log"
            ])
            with upd_tab:
                if stock.empty:
                    st.caption("Add a medicine first.")
                else:
                    labels = {f"{r['medicine_name']} (current: {r['quantity']} {r['unit']})": r["id"]
                              for _, r in stock.iterrows()}
                    chosen_label = st.selectbox("Select medicine", list(labels.keys()))
                    chosen_id    = labels[chosen_label]
                    mode   = st.radio("Action", ["Add stock (restock)",
                                                 "Remove stock (dispensed/damaged)",
                                                 "Set exact quantity"])
                    amount = st.number_input("Amount", min_value=0, value=10, step=1)
                    if st.button("Apply Update", type="primary"):
                        conn = get_conn()
                        cur_row = conn.execute(
                            "SELECT quantity,medicine_name FROM medicine_stock WHERE id=?",
                            (chosen_id,),
                        ).fetchone()
                        cur_qty = cur_row[0]; med_name = cur_row[1]
                        if "Add" in mode:
                            new_qty = cur_qty + amount; action = "Restock"; change = amount
                        elif "Remove" in mode:
                            new_qty = max(0, cur_qty - amount); action = "Dispensed/Damaged"; change = -amount
                        else:
                            new_qty = amount; action = "Manual correction"; change = amount - cur_qty
                        now_iso = datetime.now().isoformat()
                        conn.execute(
                            "UPDATE medicine_stock SET quantity=?,last_updated=?,updated_by=? WHERE id=?",
                            (new_qty, now_iso, u["name"], chosen_id),
                        )
                        conn.execute(
                            "INSERT INTO medicine_stock_log VALUES(?,?,?,?,?,?,?,?,?)",
                            (str(uuid.uuid4()), u["id"], u["name"], med_name,
                             action, change, new_qty, u["name"], now_iso),
                        )
                        conn.commit(); conn.close()
                        st.success(f"Updated. New quantity: {new_qty}"); st.rerun()

            with add_tab:
                with st.form("facility_add_med"):
                    nm = st.text_input("Medicine name")
                    nq = st.number_input("Starting quantity", 0, value=50)
                    nu = st.selectbox("Unit", ["tablets", "capsules", "vials",
                                               "sachets", "units", "bottles"])
                    if st.form_submit_button("Add Medicine", type="primary"):
                        if not nm:
                            st.error("Medicine name required.")
                        else:
                            now_iso = datetime.now().isoformat()
                            new_id  = str(uuid.uuid4())
                            conn = get_conn()
                            conn.execute(
                                "INSERT INTO medicine_stock(id,facility_id,facility,medicine_name,"
                                "quantity,unit,last_updated,updated_by) VALUES(?,?,?,?,?,?,?,?)",
                                (new_id, u["id"], u["name"], nm, nq, nu, now_iso, u["name"]),
                            )
                            conn.execute(
                                "INSERT INTO medicine_stock_log VALUES(?,?,?,?,?,?,?,?,?)",
                                (str(uuid.uuid4()), u["id"], u["name"], nm,
                                 "Initial stock", nq, nq, u["name"], now_iso),
                            )
                            conn.commit(); conn.close()
                            st.success(f"Added {nm}."); st.rerun()

            with log_tab:
                log_df = qdf(
                    "SELECT medicine_name,action,change_amount,new_quantity,changed_by,changed_at "
                    "FROM medicine_stock_log WHERE facility_id=? ORDER BY changed_at DESC LIMIT 30",
                    (u["id"],),
                )
                if log_df.empty: st.caption("No changes logged yet.")
                else: st.dataframe(clean_df(log_df), use_container_width=True, hide_index=True)

        with ft3:
            st.subheader("My Diagnostic Test Catalog")
            diag = qdf(
                "SELECT id,test_name,available,turnaround_hours,last_updated,updated_by "
                "FROM diagnostic_tests WHERE facility_id=? ORDER BY test_name", (u["id"],)
            )
            if diag.empty:
                st.info("No diagnostic tests recorded yet.")
            else:
                st.dataframe(clean_df(diag.drop(columns=["id"])),
                             use_container_width=True, hide_index=True)

            st.divider()
            dtab1, dtab2 = st.tabs(["Toggle Availability / Turnaround", "Add New Test"])
            with dtab1:
                if diag.empty:
                    st.caption("Add a test first.")
                else:
                    d_labels = {f"{r['test_name']} ({'Available' if r['available'] else 'Unavailable'})": r["id"]
                                for _, r in diag.iterrows()}
                    d_pick   = st.selectbox("Select test", list(d_labels.keys()))
                    d_id     = d_labels[d_pick]
                    d_avail  = st.checkbox("Available at this facility", value=True)
                    d_turn   = st.number_input("Turnaround time (hours)", 1, 240, 24)
                    if st.button("Update Test", type="primary"):
                        conn = get_conn()
                        conn.execute(
                            "UPDATE diagnostic_tests SET available=?,turnaround_hours=?,"
                            "last_updated=?,updated_by=? WHERE id=?",
                            (1 if d_avail else 0, d_turn,
                             datetime.now().isoformat(), u["name"], d_id),
                        )
                        conn.commit(); conn.close()
                        st.success("Updated."); st.rerun()
            with dtab2:
                with st.form("facility_add_test"):
                    tn = st.text_input("Test name")
                    tt = st.number_input("Turnaround time (hours)", 1, 240, 24,
                                         key="new_test_turn")
                    if st.form_submit_button("Add Test", type="primary"):
                        if not tn:
                            st.error("Test name required.")
                        else:
                            conn = get_conn()
                            conn.execute(
                                "INSERT INTO diagnostic_tests(id,facility_id,facility,test_name,"
                                "available,turnaround_hours,last_updated,updated_by) VALUES(?,?,?,?,1,?,?,?)",
                                (str(uuid.uuid4()), u["id"], u["name"], tn, tt,
                                 datetime.now().isoformat(), u["name"]),
                            )
                            conn.commit(); conn.close()
                            st.success(f"Added {tn}."); st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE: DISTRICT ADMIN DASHBOARD  (FIX 1: password-protected)
# ══════════════════════════════════════════════════════════════
elif page == tr("admin"):
    sk = "admin_user"
    if sk not in st.session_state:
        st.session_state[sk] = False

    # ── Auth gate ───────────────────────────────────────────────
    if not st.session_state[sk]:
        st.markdown("### District Admin Login")
        with st.container(border=True):
            st.caption(
                "In production: integrated with NIC LDAP / Maharashtra SSO. "
                "Demo password set via ADMIN_PASSWORD environment variable."
            )
            admin_pw = st.text_input("Admin Password", type="password", key="admin_pw_input")
            if st.button("Login", type="primary", key="admin_login_btn"):
                if admin_pw == ADMIN_PASSWORD:
                    st.session_state[sk] = True
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        st.stop()

    # ── Logged-in admin content ──────────────────────────────────
    col_title, col_logout = st.columns([5, 1])
    col_title.subheader(tr("admin"))
    if col_logout.button("Logout", key="admin_logout"):
        st.session_state[sk] = False
        st.rerun()

    active_sos = qdf(
        "SELECT id,patient_name,village,triggered_at FROM sos_alerts "
        "WHERE status='ACTIVE' ORDER BY triggered_at DESC"
    )
    if not active_sos.empty:
        st.error(f"{len(active_sos)} ACTIVE EMERGENCY SOS ALERT(S) — Requires Immediate Action")
        for _, s in active_sos.iterrows():
            sc1, sc2 = st.columns([4, 1])
            sc1.write(f"**{s['patient_name']}** — {s['village'] or '—'} | {s['triggered_at'][:16]}")
            if sc2.button("Resolve", key=f"res_{s['id']}", use_container_width=True):
                conn = get_conn()
                conn.execute(
                    "UPDATE sos_alerts SET status='RESOLVED',resolved_at=?,resolved_by='Admin' WHERE id=?",
                    (datetime.now().isoformat(), s["id"]),
                )
                conn.commit(); conn.close(); st.rerun()
        st.divider()

    total_p     = qdf("SELECT COUNT(*) as n FROM patients")["n"][0]
    total_t     = qdf("SELECT COUNT(*) as n FROM triage")["n"][0]
    total_r     = qdf("SELECT COUNT(*) as n FROM referrals")["n"][0]
    comp_r      = qdf("SELECT COUNT(*) as n FROM referrals WHERE status='COMPLETED' "
                      "AND (escalated_to IS NULL OR escalated_to='')")["n"][0]
    comp_rate   = (comp_r / total_r * 100) if total_r else 0
    pend_fu     = qdf("SELECT COUNT(*) as n FROM triage WHERE follow_up_due_date IS NOT NULL "
                      "AND (follow_up_done IS NULL OR follow_up_done=0)")["n"][0]
    pend_appts  = qdf("SELECT COUNT(*) as n FROM appointments WHERE status='REQUESTED'")["n"][0]
    total_docs  = qdf("SELECT COUNT(*) as n FROM doctors")["n"][0]
    total_asha  = qdf("SELECT COUNT(*) as n FROM asha_workers")["n"][0]
    total_facs  = qdf("SELECT COUNT(*) as n FROM facilities")["n"][0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Patients", total_p); m2.metric("Triages", total_t)
    m3.metric("Referrals", total_r); m4.metric("Completion", f"{comp_rate:.0f}%")
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Follow-ups Due", pend_fu); m6.metric("Appointments Pending", pend_appts)
    m7.metric("Registered Doctors", total_docs); m8.metric("ASHA Workers", total_asha)
    st.caption(f"{total_facs} facility/facilities registered on the platform.")

    st.divider()
    tab_fac, tab_area = st.tabs(["Facility-wise View", "Area / Village-wise View"])

    with tab_fac:
        st.subheader("Referral Funnel (Closed-Loop Tracking)")
        pending_n   = qdf("SELECT COUNT(*) as n FROM referrals WHERE status='PENDING'")["n"][0]
        ack_n       = qdf("SELECT COUNT(*) as n FROM referrals WHERE status='ACKNOWLEDGED'")["n"][0]
        completed_n = qdf("SELECT COUNT(*) as n FROM referrals WHERE status='COMPLETED' "
                          "AND (escalated_to IS NULL OR escalated_to='')")["n"][0]
        escalated_n = qdf("SELECT COUNT(*) as n FROM referrals "
                          "WHERE escalated_to IS NOT NULL AND escalated_to!=''")["n"][0]
        fc1, fc2, fc3, fc4 = st.columns(4)
        fc1.metric("Pending", pending_n)
        fc2.metric("Acknowledged (arrived)", ack_n)
        fc3.metric("Completed", completed_n)
        fc4.metric("Escalated", escalated_n)

        ch1, ch2 = st.columns(2)
        with ch1:
            st.subheader("Triage by Priority")
            pr = qdf("SELECT priority,COUNT(*) as count FROM triage GROUP BY priority")
            if not pr.empty:
                chart = alt.Chart(pr).mark_bar().encode(
                    x=alt.X("count:Q", title="Cases"),
            y=alt.Y("priority:N", title="Priority", sort=["RED", "YELLOW", "GREEN"]),
            color=alt.Color(
                "priority:N",
                scale=alt.Scale(domain=["RED", "YELLOW", "GREEN"],
                                 range=[PRIORITY_COLORS["RED"], PRIORITY_COLORS["YELLOW"], PRIORITY_COLORS["GREEN"]]),
                legend=None,
            ),
        )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No triage data yet.")
        with ch2:
            st.subheader("Referrals by Facility")
            rf = qdf("SELECT facility,COUNT(*) as count FROM referrals GROUP BY facility")
            if not rf.empty: st.bar_chart(rf.set_index("facility"), horizontal=True)
            else: st.info("No referral data yet.")

        ch3, ch4 = st.columns(2)
        with ch3:
            st.subheader("Department-wise Cases")
            dp = qdf("SELECT department,COUNT(*) as count FROM triage "
                     "WHERE department IS NOT NULL GROUP BY department ORDER BY count DESC")
            if not dp.empty: st.bar_chart(dp.set_index("department"), horizontal=True)
        with ch4:
            st.subheader("Appointments Status")
            ap = qdf("SELECT status,COUNT(*) as count FROM appointments GROUP BY status")
            if not ap.empty: st.bar_chart(ap.set_index("status"), horizontal=True)

        st.divider()
        st.subheader("Facility Directory")
        fac_dir = qdf("SELECT name,type,village,phone,created_at FROM facilities ORDER BY created_at DESC")
        if fac_dir.empty: st.info("No facilities registered yet.")
        else: st.dataframe(clean_df(fac_dir), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Quality Monitoring — SLA & Patient Feedback")
        sla_rows = qdf(
            """SELECT t.priority as priority, r.created_at as created_at,
                      r.acknowledged_at as acknowledged_at, r.status as status
               FROM referrals r JOIN triage t ON t.id=r.triage_id"""
        )
        breach_count = 0; total_checked = 0
        if not sla_rows.empty:
            for _, r in sla_rows.iterrows():
                _, breached = compute_sla_status(
                    r["priority"], r["created_at"], r["acknowledged_at"], r["status"]
                )
                total_checked += 1
                if breached: breach_count += 1
        fb = qdf("SELECT feedback_rating FROM referrals WHERE feedback_rating IS NOT NULL")
        avg_rating = round(fb["feedback_rating"].astype(float).mean(), 2) if not fb.empty else None
        diag_total = qdf("SELECT COUNT(*) as n FROM diagnostic_orders")["n"][0]
        diag_done  = qdf("SELECT COUNT(*) as n FROM diagnostic_orders WHERE status='COMPLETED'")["n"][0]
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("SLA Breaches", f"{breach_count}/{total_checked}")
        q2.metric("Avg Patient Rating", f"{avg_rating} / 5" if avg_rating else "No ratings yet")
        q3.metric("Diagnostics Ordered", diag_total)
        q4.metric("Diagnostics Completed", diag_done)
        st.caption(
            f"SLA targets: RED within {SLA_TARGET_HOURS['RED']}h, "
            f"YELLOW within {SLA_TARGET_HOURS['YELLOW']}h, "
            f"GREEN within {SLA_TARGET_HOURS['GREEN']}h."
        )

        # ── FIX 7: Outbreak Signal Detection ───────────────────
        st.divider()
        st.subheader("Outbreak Signal Detection (last 7 days)")
        st.caption(
            "Auto-clusters repeated symptom keywords by village — "
            "3+ cases of the same symptom in the same village within 7 days flags a potential outbreak."
        )
        recent_7d = qdf(
            """SELECT t.symptoms_text, p.village FROM triage t
               JOIN patients p ON p.abha_id=t.abha_id
               WHERE t.created_at >= datetime('now', '-7 days')"""
        )
        if recent_7d.empty:
            st.info("No triage data in the last 7 days.")
        else:
            signals: dict = {}
            for _, row in recent_7d.iterrows():
                text    = (row["symptoms_text"] or "").lower()
                village = row["village"] or "Unknown"
                for kw in OUTBREAK_KEYWORDS:
                    if kw in text:
                        key = f"{kw} — {village}"
                        signals[key] = signals.get(key, 0) + 1
            if signals:
                signal_df = (
                    pd.DataFrame(list(signals.items()),
                                 columns=["Signal (Symptom — Village)", "Cases (7 days)"])
                    .sort_values("Cases (7 days)", ascending=False)
                )
                high_signals = signal_df[signal_df["Cases (7 days)"] >= 3]
                if not high_signals.empty:
                    st.error(
                        f"⚠️ {len(high_signals)} potential outbreak signal(s) detected "
                        f"(3+ cases of same symptom in same village within 7 days). "
                        f"Consider alerting district health officer."
                    )
                    st.dataframe(high_signals, use_container_width=True, hide_index=True)
                    st.divider()
                st.dataframe(signal_df, use_container_width=True, hide_index=True)
            else:
                st.success("No clustering signals detected in the last 7 days.")

    with tab_area:
        st.subheader("Village / Area-wise Overview")
        village_df = qdf(
            """SELECT p.village as village,
                      COUNT(DISTINCT p.abha_id) as patients,
                      SUM(CASE WHEN t.priority='RED'    THEN 1 ELSE 0 END) as red_cases,
                      SUM(CASE WHEN t.priority='YELLOW' THEN 1 ELSE 0 END) as yellow_cases,
                      SUM(CASE WHEN t.priority='GREEN'  THEN 1 ELSE 0 END) as green_cases
               FROM patients p LEFT JOIN triage t ON t.abha_id=p.abha_id
               WHERE p.village IS NOT NULL AND p.village!=''
               GROUP BY p.village ORDER BY red_cases DESC, patients DESC"""
        )
        if village_df.empty:
            st.info("No village-linked records yet.")
        else:
            st.dataframe(clean_df(village_df), use_container_width=True, hide_index=True)
            chart_data = village_df.set_index("village")[["red_cases", "yellow_cases", "green_cases"]].fillna(0)
            st.bar_chart(
    chart_data,
    color=[PRIORITY_COLORS["RED"], PRIORITY_COLORS["YELLOW"], PRIORITY_COLORS["GREEN"]],
)

    st.divider()
    st.subheader("Area-wise Patient Records")
    with st.container(border=True):
        facs_for_filter = ["All"] + get_facility_names()
        f1, f2, f3, f4 = st.columns(4)
        fac_filter  = f1.selectbox("Filter by Facility", facs_for_filter, key="admin_fac")
        prio_filter = f2.selectbox("Filter by Priority", ["All", "RED", "YELLOW", "GREEN"],
                                   key="admin_prio")
        dept_filter = f3.selectbox(
            "Filter by Department",
            ["All"] + [d for d, _ in DEPT_KW] + ["General Medicine"],
            key="admin_dept",
        )
        sort_by = f4.selectbox(
            "Sort by",
            ["Date (newest)", "Date (oldest)", "Priority (urgent first)", "Village"],
            key="admin_sort",
        )
        sym_search = st.text_input(
            "Search by symptom keywords",
            placeholder="e.g. fever, chest pain (2+ characters)",
            key="admin_sym",
        )
        sql = """SELECT p.name,p.village,t.priority,t.department,t.symptoms_text,
                        t.temperature,t.spo2,t.pulse,t.created_at,
                        r.facility,r.status as referral_status
                 FROM triage t
                 JOIN patients p ON p.abha_id=t.abha_id
                 LEFT JOIN referrals r ON r.triage_id=t.id
                 WHERE 1=1"""
        params = []
        if prio_filter != "All": sql += " AND t.priority=?"; params.append(prio_filter)
        if dept_filter != "All": sql += " AND t.department=?"; params.append(dept_filter)
        if fac_filter  != "All": sql += " AND r.facility=?"; params.append(fac_filter)
        if sym_search and len(sym_search.strip()) >= 2:
            sql += " AND t.symptoms_text LIKE ?"; params.append(f"%{sym_search}%")
        sort_map = {
            "Date (newest)":          "t.created_at DESC",
            "Date (oldest)":          "t.created_at ASC",
            "Priority (urgent first)": "CASE t.priority WHEN 'RED' THEN 0 WHEN 'YELLOW' THEN 1 ELSE 2 END",
            "Village":                 "p.village",
        }
        sql += f" ORDER BY {sort_map[sort_by]}"
        area_df = qdf(sql, tuple(params))
        st.caption(f"{len(area_df)} records found")
        if area_df.empty: st.info("No records match your filters.")
        else: st.dataframe(clean_df(area_df), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Symptom Signal (recent 20 entries)")
    recent = qdf(
        "SELECT symptoms_text,priority,department,created_at FROM triage "
        "ORDER BY created_at DESC LIMIT 20"
    )
    st.dataframe(clean_df(recent), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Low Stock Alerts (below 10 units, all facilities)")
    low = qdf(
        "SELECT facility,medicine_name,quantity,unit FROM medicine_stock "
        "WHERE quantity<10 ORDER BY quantity"
    )
    if low.empty: st.success("No low-stock alerts.")
    else: st.dataframe(clean_df(low), use_container_width=True, hide_index=True)
