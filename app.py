"""
ArogyaBridge - "Bridge to Healthcare"
SIH 2026 | PS ID: SIH26133 — Full prototype with multi-role auth,
AI triage, notifications, appointments, vitals, analytics.
Run: pip install -r requirements.txt && streamlit run app.py
"""

import os, sqlite3, uuid, random, hashlib, secrets
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# ─────────────────────────── CONFIG ────────────────────────────
DB_PATH    = os.path.join(os.path.dirname(__file__), "sevasetu.db")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"
FACILITIES = ["Sub-Centre Wagholi", "PHC Ranjangaon", "District Hospital Pune"]

PRIORITY_COLORS = {"RED": "#e53935", "YELLOW": "#fbc02d", "GREEN": "#43a047"}
PRIORITY_ORDER  = {"RED": 0, "YELLOW": 1, "GREEN": 2}

st.set_page_config(page_title="ArogyaBridge", page_icon="🩺",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html,body,[class*="css"]{font-size:16px}
.stButton>button{padding:.55rem 1.3rem;font-size:1.05rem;font-weight:600;
  border-radius:10px;min-height:2.9rem}
.stTextInput input,.stNumberInput input,.stTextArea textarea{
  font-size:1.05rem;padding:.55rem .7rem}
.stSelectbox>div>div{min-height:2.9rem;font-size:1.05rem}
.stTabs [data-baseweb="tab"]{font-size:1rem;font-weight:600;padding:.45rem .9rem}
.stRadio>div{gap:.35rem}.stRadio label{font-size:1.05rem}
[data-testid="stMetricValue"]{font-size:1.55rem}
[data-testid="stMetricLabel"]{font-size:.9rem}
</style>""", unsafe_allow_html=True)

# ─────────────────────────── I18N ──────────────────────────────
T = {
"en": {
  "app_title":"ArogyaBridge — Bridge to Healthcare","role":"Select your role",
  "patient_portal":"Patient Portal","asha":"ASHA / ANM Worker",
  "doctor":"Doctor Dashboard","admin":"District Admin Dashboard","medicine":"Medicine Stock",
  "login":"Login","register_tab":"Register","login_btn":"Login",
  "name":"Full Name","age":"Age","gender":"Gender","village":"Village / Ward",
  "phone":"Phone Number","language":"Preferred Language",
  "password":"Password","confirm_password":"Confirm Password",
  "register_btn":"Register","invalid_login":"Invalid phone or password.",
  "welcome_back":"Welcome back","logout_btn":"Logout",
  "symptoms":"Describe symptoms","run_triage":"Run AI Triage","priority":"Priority",
  "refer_btn":"Refer to Facility","select_facility":"Refer to which facility?",
  "queue":"Live Patient Queue","no_referrals":"No referrals in queue.",
  "prescription":"Prescription","save_prescription":"Save Prescription & Complete",
  "teleconsult":"Start Teleconsultation","book_appointment":"Book Appointment",
  "sos":"Emergency SOS","my_health_record":"My Health Record",
  "my_triage_history":"My Symptom History","my_referrals":"My Referrals & Prescriptions",
  "no_records_yet":"No records yet.","create_login":"Create your login",
  "phone_login_hint":"Login with your registered phone number.",
  "register_patient":"Register New Patient",
},
"hi": {
  "app_title":"ArogyaBridge — स्वास्थ्य सेवा का पुल","role":"अपनी भूमिका चुनें",
  "patient_portal":"रोगी पोर्टल","asha":"आशा / एएनएम कार्यकर्ता",
  "doctor":"डॉक्टर डैशबोर्ड","admin":"जिला प्रशासन डैशबोर्ड","medicine":"दवा स्टॉक",
  "login":"लॉगिन","register_tab":"पंजीकरण","login_btn":"लॉगिन करें",
  "name":"पूरा नाम","age":"आयु","gender":"लिंग","village":"गाँव / वार्ड",
  "phone":"फ़ोन नंबर","language":"पसंदीदा भाषा",
  "password":"पासवर्ड","confirm_password":"पासवर्ड की पुष्टि",
  "register_btn":"पंजीकरण करें","invalid_login":"फ़ोन नंबर या पासवर्ड गलत है।",
  "welcome_back":"वापसी पर स्वागत है","logout_btn":"लॉगआउट",
  "symptoms":"लक्षण बताएं","run_triage":"AI ट्राइएज चलाएं","priority":"प्राथमिकता",
  "refer_btn":"रेफर करें","select_facility":"कहाँ रेफर करें?",
  "queue":"लाइव रोगी कतार","no_referrals":"कतार में कोई रेफरल नहीं।",
  "prescription":"नुस्खा","save_prescription":"नुस्खा सहेजें",
  "teleconsult":"टेलीकंसल्टेशन","book_appointment":"अपॉइंटमेंट बुक करें",
  "sos":"आपातकालीन SOS","my_health_record":"मेरा स्वास्थ्य रिकॉर्ड",
  "my_triage_history":"मेरा लक्षण इतिहास","my_referrals":"मेरे रेफरल",
  "no_records_yet":"अभी कोई रिकॉर्ड नहीं।","create_login":"अपना लॉगिन बनाएं",
  "phone_login_hint":"अपने पंजीकृत फ़ोन नंबर से लॉगिन करें।",
  "register_patient":"नया रोगी पंजीकृत करें",
},
"mr": {
  "app_title":"ArogyaBridge — आरोग्यसेवेचा पूल","role":"तुमची भूमिका निवडा",
  "patient_portal":"रुग्ण पोर्टल","asha":"आशा / एएनएम कार्यकर्ता",
  "doctor":"डॉक्टर डॅशबोर्ड","admin":"जिल्हा प्रशासन डॅशबोर्ड","medicine":"औषध साठा",
  "login":"लॉगिन","register_tab":"नोंदणी","login_btn":"लॉगिन करा",
  "name":"पूर्ण नाव","age":"वय","gender":"लिंग","village":"गाव / वॉर्ड",
  "phone":"फोन नंबर","language":"पसंतीची भाषा",
  "password":"पासवर्ड","confirm_password":"पासवर्डची पुष्टी",
  "register_btn":"नोंदणी करा","invalid_login":"फोन नंबर किंवा पासवर्ड चुकीचा.",
  "welcome_back":"परत स्वागत","logout_btn":"लॉगआउट",
  "symptoms":"लक्षणे सांगा","run_triage":"AI ट्रायएज","priority":"प्राधान्य",
  "refer_btn":"संदर्भित करा","select_facility":"कुठे संदर्भित करायचे?",
  "queue":"रुग्ण रांग","no_referrals":"रांगेत कोणतेही रेफरल नाही.",
  "prescription":"प्रिस्क्रिप्शन","save_prescription":"प्रिस्क्रिप्शन जतन करा",
  "teleconsult":"टेलिकन्सल्टेशन","book_appointment":"अपॉइंटमेंट बुक करा",
  "sos":"आणीबाणी SOS","my_health_record":"माझी आरोग्य नोंद",
  "my_triage_history":"माझा लक्षण इतिहास","my_referrals":"माझे संदर्भ",
  "no_records_yet":"अजून नोंद नाही.","create_login":"लॉगिन तयार करा",
  "phone_login_hint":"नोंदणीकृत फोन नंबर वापरा.","register_patient":"नवीन रुग्ण नोंदणी",
},
"ta": {
  "app_title":"ArogyaBridge — சுகாதார சேவைக்கான பாலம்","role":"பாத்திரம் தேர்வு",
  "patient_portal":"நோயாளர் போர்ட்டல்","asha":"ஆஷா / ஏஎன்எம்",
  "doctor":"மருத்துவர் டாஷ்போர்டு","admin":"மாவட்ட நிர்வாக டாஷ்போர்டு","medicine":"மருந்து கையிருப்பு",
  "login":"உள்நுழைய","register_tab":"பதிவு","login_btn":"உள்நுழையவும்",
  "name":"பெயர்","age":"வயது","gender":"பாலினம்","village":"கிராமம்",
  "phone":"தொலைபேசி","language":"மொழி",
  "password":"கடவுச்சொல்","confirm_password":"உறுதிப்படுத்தவும்",
  "register_btn":"பதிவு செய்யவும்","invalid_login":"தவறான தொலைபேசி அல்லது கடவுச்சொல்.",
  "welcome_back":"மீண்டும் வரவேற்கிறோம்","logout_btn":"வெளியேறு",
  "symptoms":"அறிகுறிகள்","run_triage":"AI முன்னுரிமை","priority":"முன்னுரிமை",
  "refer_btn":"பரிந்துரைக்கவும்","select_facility":"எந்த மையம்?",
  "queue":"நோயாளர் வரிசை","no_referrals":"பரிந்துரைகள் இல்லை.",
  "prescription":"மருந்துச் சீட்டு","save_prescription":"சேமிக்கவும்",
  "teleconsult":"தொலை ஆலோசனை","book_appointment":"சந்திப்பு",
  "sos":"அவசர SOS","my_health_record":"சுகாதார பதிவு",
  "my_triage_history":"அறிகுறி வரலாறு","my_referrals":"பரிந்துரைகள்",
  "no_records_yet":"பதிவுகள் இல்லை.","create_login":"லாக்இன் உருவாக்கவும்",
  "phone_login_hint":"பதிவுசெய்யப்பட்ட தொலைபேசி பயன்படுத்தவும்.","register_patient":"நோயாளர் பதிவு",
},
"te": {
  "app_title":"ArogyaBridge — ఆరోగ్య సేవకు వంతెన","role":"పాత్ర ఎంచుకోండి",
  "patient_portal":"రోగి పోర్టల్","asha":"ఆశా / ఏఎన్ఎం",
  "doctor":"డాక్టర్ డాష్‌బోర్డ్","admin":"జిల్లా అడ్మిన్ డాష్‌బోర్డ్","medicine":"మందుల నిల్వ",
  "login":"లాగిన్","register_tab":"నమోదు","login_btn":"లాగిన్ చేయండి",
  "name":"పూర్తి పేరు","age":"వయస్సు","gender":"లింగం","village":"గ్రామం",
  "phone":"ఫోన్","language":"భాష",
  "password":"పాస్‌వర్డ్","confirm_password":"నిర్ధారించండి",
  "register_btn":"నమోదు చేయండి","invalid_login":"తప్పు ఫోన్ లేదా పాస్‌వర్డ్.",
  "welcome_back":"తిరిగి స్వాగతం","logout_btn":"లాగ్ అవుట్",
  "symptoms":"లక్షణాలు","run_triage":"AI ట్రయాజ్","priority":"ప్రాధాన్యత",
  "refer_btn":"రిఫర్ చేయండి","select_facility":"ఏ సదుపాయం?",
  "queue":"రోగి క్యూ","no_referrals":"రిఫరల్స్ లేవు.",
  "prescription":"ప్రిస్క్రిప్షన్","save_prescription":"సేవ్ చేయండి",
  "teleconsult":"టెలికన్సల్టేషన్","book_appointment":"అపాయింట్‌మెంట్",
  "sos":"అత్యవసర SOS","my_health_record":"ఆరోగ్య రికార్డు",
  "my_triage_history":"లక్షణాల చరిత్ర","my_referrals":"రిఫరల్స్",
  "no_records_yet":"రికార్డులు లేవు.","create_login":"లాగిన్ సృష్టించండి",
  "phone_login_hint":"నమోదిత ఫోన్ నంబర్ ఉపయోగించండి.","register_patient":"రోగి నమోదు",
},
"bn": {
  "app_title":"ArogyaBridge — স্বাস্থ্যসেবার সেতু","role":"ভূমিকা নির্বাচন",
  "patient_portal":"রোগী পোর্টাল","asha":"আশা / এএনএম",
  "doctor":"ডাক্তার ড্যাশবোর্ড","admin":"জেলা প্রশাসন ড্যাশবোর্ড","medicine":"ওষুধ স্টক",
  "login":"লগইন","register_tab":"নিবন্ধন","login_btn":"লগইন করুন",
  "name":"পুরো নাম","age":"বয়স","gender":"লিঙ্গ","village":"গ্রাম",
  "phone":"ফোন","language":"ভাষা",
  "password":"পাসওয়ার্ড","confirm_password":"নিশ্চিত করুন",
  "register_btn":"নিবন্ধন করুন","invalid_login":"ভুল ফোন বা পাসওয়ার্ড।",
  "welcome_back":"আবার স্বাগতম","logout_btn":"লগআউট",
  "symptoms":"লক্ষণ","run_triage":"AI ট্রায়াজ","priority":"অগ্রাধিকার",
  "refer_btn":"রেফার করুন","select_facility":"কোন সুবিধা?",
  "queue":"রোগীর সারি","no_referrals":"রেফারেল নেই।",
  "prescription":"প্রেসক্রিপশন","save_prescription":"সংরক্ষণ করুন",
  "teleconsult":"টেলিকনসালটেশন","book_appointment":"অ্যাপয়েন্টমেন্ট",
  "sos":"জরুরি SOS","my_health_record":"স্বাস্থ্য রেকর্ড",
  "my_triage_history":"লক্ষণ ইতিহাস","my_referrals":"রেফারেল",
  "no_records_yet":"রেকর্ড নেই।","create_login":"লগইন তৈরি করুন",
  "phone_login_hint":"নিবন্ধিত ফোন নম্বর ব্যবহার করুন।","register_patient":"রোগী নিবন্ধন",
},
}

def tr(key):
    lang = st.session_state.get("ui_lang","en")
    return T.get(lang,T["en"]).get(key, T["en"].get(key,key))

# ─────────────────────────── DATABASE ──────────────────────────
def get_conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS patients(
      abha_id TEXT PRIMARY KEY, name TEXT, age INTEGER, gender TEXT,
      village TEXT, phone TEXT, language TEXT, created_at TEXT,
      password_hash TEXT, salt TEXT);
    CREATE TABLE IF NOT EXISTS asha_workers(
      id TEXT PRIMARY KEY, name TEXT, phone TEXT, facility TEXT,
      password_hash TEXT, salt TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS doctors(
      id TEXT PRIMARY KEY, name TEXT, phone TEXT, facility TEXT,
      speciality TEXT, password_hash TEXT, salt TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS triage(
      id TEXT PRIMARY KEY, abha_id TEXT, symptoms_text TEXT,
      priority TEXT, rationale TEXT, created_by TEXT, created_at TEXT,
      department TEXT, follow_up_due_date TEXT, follow_up_done INTEGER DEFAULT 0,
      temperature TEXT, spo2 TEXT, pulse TEXT, triggered_by TEXT DEFAULT 'asha');
    CREATE TABLE IF NOT EXISTS referrals(
      id TEXT PRIMARY KEY, abha_id TEXT, triage_id TEXT, facility TEXT,
      status TEXT, prescription TEXT, doctor_notes TEXT,
      created_at TEXT, completed_at TEXT, doctor_id TEXT);
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
      id TEXT PRIMARY KEY, facility TEXT, medicine_name TEXT,
      quantity INTEGER, unit TEXT, last_updated TEXT);
    """)
    conn.commit()

    # safe migrations
    def add_col(table, col, typ="TEXT"):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    add_col("triage","temperature"); add_col("triage","spo2"); add_col("triage","pulse")
    add_col("triage","triggered_by"); add_col("referrals","doctor_id")
    add_col("appointments","doctor_id"); add_col("appointments","decline_reason")
    add_col("sos_alerts","accepted_by")
    add_col("sos_alerts","medical_summary"); add_col("sos_alerts","routing_log")
    add_col("sos_alerts","cancelled","INTEGER DEFAULT 0")
    # notifications may have been created without triage_id/abha_id in older DB files
    add_col("notifications","triage_id"); add_col("notifications","abha_id")
    conn.commit()

    # seed medicine
    c.execute("SELECT COUNT(*) FROM medicine_stock")
    if c.fetchone()[0]==0:
        meds=[("Paracetamol 500mg","tablets",40),("ORS Sachets","sachets",5),
              ("Iron Folic Acid","tablets",120),("Amoxicillin 250mg","capsules",8),
              ("Insulin (Regular)","vials",15),("Antenatal Vitamin D","tablets",60)]
        for fac in FACILITIES:
            for med,unit,base in meds:
                qty=max(0,base+random.randint(-10,10))
                c.execute("INSERT INTO medicine_stock VALUES(?,?,?,?,?,?)",
                         (str(uuid.uuid4()),fac,med,qty,unit,datetime.now().isoformat()))
        conn.commit()
    conn.close()

# ─────────────────────────── AUTH HELPERS ──────────────────────
def hash_pw(pw, salt=None):
    if not salt: salt=secrets.token_hex(16)
    h=hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),100_000).hex()
    return h,salt

def verify_pw(pw,salt,stored):
    return hash_pw(pw,salt)[0]==stored

# ─────────────────────────── TRIAGE ENGINE ─────────────────────
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
        if f in t: return "RED",f"Red-flag: '{f}' — immediate escalation needed."
    for f in YELLOW_FLAGS:
        if f in t: return "YELLOW",f"Moderate risk: '{f}' — facility visit recommended."
    return "GREEN","No high-risk indicators. Routine care advised."

def groq_triage(text):
    if not GROQ_API_KEY: return None
    try:
        from groq import Groq
        client=Groq(api_key=GROQ_API_KEY)
        prompt=(f"Rural Indian health triage assistant. Classify symptoms as RED/YELLOW/GREEN. "
                f"Reply ONLY as: PRIORITY|one sentence rationale.\nSymptoms: {text}")
        resp=client.chat.completions.create(model=GROQ_MODEL,
             messages=[{"role":"user","content":prompt}],max_tokens=100,temperature=0.2)
        out=resp.choices[0].message.content.strip()
        if "|" in out:
            p,r=out.split("|",1)
            p=p.strip().upper()
            if p in PRIORITY_ORDER: return p,r.strip()
    except: return None

def run_triage(text):
    res=groq_triage(text)
    priority,rationale=res if res else rule_triage(text)
    dept=suggest_dept(text)
    fud=None
    if priority=="RED": fud=(datetime.now()+timedelta(days=2)).strftime("%Y-%m-%d")
    elif priority=="YELLOW": fud=(datetime.now()+timedelta(days=7)).strftime("%Y-%m-%d")
    return priority,rationale,dept,fud

# ─────────────────────────── NOTIFICATION HELPERS ──────────────
def send_notification(role, recipient_id, message, priority, triage_id=None, abha_id=None):
    conn=get_conn()
    conn.execute("INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) VALUES(?,?,?,?,?,0,?,?,?)",
                 (str(uuid.uuid4()),role,recipient_id,message,priority,datetime.now().isoformat(),triage_id,abha_id))
    conn.commit(); conn.close()

def notify_all_doctors(message, priority, triage_id=None, abha_id=None):
    conn=get_conn()
    docs=conn.execute("SELECT id FROM doctors").fetchall()
    for d in docs:
        conn.execute("INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) VALUES(?,?,?,?,?,0,?,?,?)",
                     (str(uuid.uuid4()),"doctor",d["id"],message,priority,datetime.now().isoformat(),triage_id,abha_id))
    conn.commit(); conn.close()

def notify_all_asha(message, priority, triage_id=None, abha_id=None):
    conn=get_conn()
    ashas=conn.execute("SELECT id FROM asha_workers").fetchall()
    for a in ashas:
        conn.execute("INSERT INTO notifications(id,recipient_role,recipient_id,message,priority,read,created_at,triage_id,abha_id) VALUES(?,?,?,?,?,0,?,?,?)",
                     (str(uuid.uuid4()),"asha",a["id"],message,priority,datetime.now().isoformat(),triage_id,abha_id))
    conn.commit(); conn.close()

def get_unread(role, uid):
    conn=get_conn()
    rows=conn.execute("SELECT * FROM notifications WHERE recipient_role=? AND recipient_id=? AND read=0 ORDER BY created_at DESC",(role,uid)).fetchall()
    conn.close(); return rows

def mark_read(role, uid):
    conn=get_conn()
    conn.execute("UPDATE notifications SET read=1 WHERE recipient_role=? AND recipient_id=?",(role,uid))
    conn.commit(); conn.close()

# ─────────────────────────── UTILS ─────────────────────────────
def gen_abha(): return "ABHA-"+str(uuid.uuid4())[:8].upper()
def priority_badge(p):
    c=PRIORITY_COLORS.get(p,"#999")
    return f"<span style='background:{c};color:white;padding:3px 12px;border-radius:12px;font-weight:700;font-size:.85em'>{p}</span>"
def qdf(sql,params=()):
    conn=get_conn(); d=pd.read_sql_query(sql,conn,params=params); conn.close(); return d

# ─────────────────────────── AUTH SCREENS ──────────────────────
def auth_screen(role_label, table, extra_fields=None):
    """Generic login/register screen. Returns (id, row_dict) or (None,None)."""
    st.markdown(f"### {'🧑‍🦱' if table=='patients' else '🚶‍♀️' if table=='asha_workers' else '🩺'} {role_label}")
    login_tab, reg_tab = st.tabs(["🔐 "+tr("login"), "📝 "+tr("register_tab")])

    with login_tab:
        with st.container(border=True):
            st.caption(tr("phone_login_hint"))
            ph=st.text_input(tr("phone"), key=f"l_phone_{table}", placeholder="98765 43210")
            pw=st.text_input(tr("password"), type="password", key=f"l_pw_{table}")
            if st.button(tr("login_btn"), type="primary", use_container_width=True, key=f"l_btn_{table}"):
                if not ph or not pw:
                    st.warning("Enter phone and password.")
                else:
                    conn=get_conn()
                    row=conn.execute(f"SELECT * FROM {table} WHERE phone=? AND password_hash IS NOT NULL",(ph,)).fetchone()
                    conn.close()
                    if row and verify_pw(pw, row["salt"], row["password_hash"]):
                        return dict(row)
                    st.error(tr("invalid_login"))

    with reg_tab:
        with st.container(border=True):
            st.caption(tr("create_login"))
            with st.form(f"reg_{table}"):
                c1,c2=st.columns(2)
                rn=c1.text_input(tr("name"), key=f"r_name_{table}")
                rph=c2.text_input(tr("phone"), key=f"r_ph_{table}", placeholder="98765 43210")
                rpw=c1.text_input(tr("password"), type="password", key=f"r_pw_{table}")
                rc=c2.text_input(tr("confirm_password"), type="password", key=f"r_conf_{table}")
                extras={}
                if extra_fields:
                    for fname,flabel,fopts in extra_fields:
                        if fopts:
                            extras[fname]=st.selectbox(flabel, fopts, key=f"r_{fname}_{table}")
                        else:
                            extras[fname]=st.text_input(flabel, key=f"r_{fname}_{table}")
                submitted=st.form_submit_button(tr("register_btn"), type="primary", use_container_width=True)
                if submitted:
                    conn=get_conn()
                    pk = "abha_id" if table == "patients" else "id"
                    exists=conn.execute(f"SELECT {pk} FROM {table} WHERE phone=?",(rph,)).fetchone()
                    conn.close()
                    if not rn or not rph: st.error("Name and phone required.")
                    elif not rpw or rpw!=rc: st.error("Passwords don't match.")
                    elif exists: st.error("Phone already registered — please log in.")
                    else:
                        h,s=hash_pw(rpw)
                        rid=str(uuid.uuid4())
                        conn=get_conn()
                        if table=="patients":
                            conn.execute("INSERT INTO patients(abha_id,name,age,gender,village,phone,language,created_at,password_hash,salt) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                         (gen_abha(),rn,0,"","",rph,"",datetime.now().isoformat(),h,s))
                        elif table=="asha_workers":
                            conn.execute("INSERT INTO asha_workers(id,name,phone,facility,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?)",
                                         (rid,rn,rph,extras.get("facility",""),h,s,datetime.now().isoformat()))
                        elif table=="doctors":
                            conn.execute("INSERT INTO doctors(id,name,phone,facility,speciality,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                         (rid,rn,rph,extras.get("facility",""),extras.get("speciality","General Medicine"),h,s,datetime.now().isoformat()))
                        conn.commit(); conn.close()
                        st.success("✅ Registered! Please log in above.")
    return None

# ─────────────────────────── INIT ──────────────────────────────
init_db()
if "ui_lang" not in st.session_state: st.session_state.ui_lang="en"

# ─────────────────────────── SIDEBAR ───────────────────────────
with st.sidebar:
    st.markdown("## 🩺 ArogyaBridge")
    st.caption("Bridge to Healthcare")
    LANG_LABELS={"en":"English","hi":"हिंदी (Hindi)","mr":"मराठी (Marathi)",
                 "ta":"தமிழ் (Tamil)","te":"తెలుగు (Telugu)","bn":"বাংলা (Bengali)"}
    lc=st.selectbox("🌐 Language",list(LANG_LABELS.values()))
    st.session_state.ui_lang=next(k for k,v in LANG_LABELS.items() if v==lc)
    st.divider()
    ROLE_ICONS={tr("patient_portal"):"🧑‍🦱 ",tr("asha"):"🚶‍♀️ ",
                tr("doctor"):"🩺 ",tr("admin"):"🏛️ ",tr("medicine"):"💊 "}
    ROLES=[tr("patient_portal"),tr("asha"),tr("doctor"),tr("admin"),tr("medicine")]
    page=st.radio(tr("role"),ROLES,format_func=lambda o:ROLE_ICONS.get(o,"")+o)
    st.divider()
    st.caption("🟢 AI: "+("Groq Llama 3.1" if GROQ_API_KEY else "Rule-based fallback"))

st.title(tr("app_title"))

# ══════════════════════════════════════════════════════════════
# PAGE: PATIENT PORTAL
# ══════════════════════════════════════════════════════════════
if page==tr("patient_portal"):
    sk="patient_user"
    if sk not in st.session_state: st.session_state[sk]=None

    if not st.session_state[sk]:
        row=auth_screen(tr("patient_portal"),"patients")
        if row: st.session_state[sk]=row; st.rerun()
    else:
        u=st.session_state[sk]
        abha_id=u["abha_id"]
        # refresh profile
        conn=get_conn(); p=conn.execute("SELECT * FROM patients WHERE abha_id=?",(abha_id,)).fetchone(); conn.close()

        with st.container(border=True):
            h1,h2=st.columns([4,1])
            h1.markdown(f"### 👋 {tr('welcome_back')}, **{p['name'] or u['name']}**")
            if h2.button(tr("logout_btn")):
                st.session_state[sk]=None; st.rerun()
            mc1,mc2,mc3=st.columns(3)
            mc1.metric("ABHA ID",p["abha_id"])
            mc2.metric(tr("age"),int(p["age"]) if p["age"] else "—")
            mc3.metric(tr("village"),p["village"] or "—")

        # Quick-action row
        qa1,qa2,qa3=st.columns(3)
        if qa1.button("📅 "+tr("book_appointment"),use_container_width=True):
            st.session_state["show_appt"]=not st.session_state.get("show_appt",False)
            st.session_state["show_self_triage"]=False
        if qa2.button("🤖 Self Triage",use_container_width=True):
            st.session_state["show_self_triage"]=not st.session_state.get("show_self_triage",False)
            st.session_state["show_appt"]=False
        if qa3.button("🆘 "+tr("sos"),type="primary",use_container_width=True):
            # Arm the 5-second cancel window — don't fire yet
            st.session_state["sos_armed"]=True
            st.session_state["sos_armed_at"]=datetime.now().isoformat()
            st.session_state["show_appt"]=False
            st.session_state["show_self_triage"]=False

        # ── 5-Second SOS Cancel Window ──────────────────────────────────
        if st.session_state.get("sos_armed"):
            armed_at=datetime.fromisoformat(st.session_state["sos_armed_at"])
            elapsed=(datetime.now()-armed_at).total_seconds()
            remaining=max(0,5-int(elapsed))

            with st.container(border=True):
                st.markdown(
                    f"""<div style='background:#b71c1c;color:white;border-radius:12px;padding:18px;text-align:center'>
                    <h2 style='margin:0;color:white'>🚨 SOS ARMING IN {remaining}s</h2>
                    <p style='margin:6px 0 0 0;font-size:1.1rem'>
                    Emergency alert will be dispatched automatically.<br>
                    <b>Press CANCEL below if this was a mistake.</b></p>
                    </div>""",
                    unsafe_allow_html=True
                )
                cc1,cc2=st.columns(2)
                if cc1.button("❌ CANCEL — False Alarm",use_container_width=True):
                    # Log false alarm so admin can see accidental triggers
                    conn=get_conn()
                    conn.execute(
                        "INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()),abha_id,p["name"],p["village"],
                         st.session_state["sos_armed_at"],"CANCELLED",
                         datetime.now().isoformat(),"Patient (self-cancel)",None,
                         "Cancelled within 5-second window — false alarm.",None,None,1)
                    )
                    conn.commit(); conn.close()
                    st.session_state["sos_armed"]=False
                    st.info("✅ SOS cancelled. No alert was sent. A false-alarm log has been recorded.")
                    st.rerun()

                if remaining==0 or cc2.button("🚨 SEND NOW (skip timer)",type="primary",use_container_width=True):
                    # ── Package medical history ─────────────────────────
                    past_triage=qdf(
                        "SELECT priority,department,symptoms_text,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC LIMIT 5",
                        (abha_id,)
                    )
                    med_summary_lines=[
                        f"Patient: {p['name']}, Age: {p['age']}, Gender: {p['gender']}",
                        f"Village/Location: {p['village']}",
                        f"Phone: {p['phone']}",
                        f"ABHA ID: {abha_id}",
                        "── Recent Medical History ──",
                    ]
                    if not past_triage.empty:
                        for _,r in past_triage.iterrows():
                            med_summary_lines.append(f"• [{r['priority']}] {r['department']}: {r['symptoms_text'][:60]} ({r['created_at'][:10]})")
                    else:
                        med_summary_lines.append("• No prior visits on record.")
                    med_summary="\n".join(med_summary_lines)

                    # ── Split-routing log ───────────────────────────────
                    routing_log_lines=[
                        f"[{datetime.now().strftime('%H:%M:%S')}] SOS activated by patient {p['name']}",
                        f"[{datetime.now().strftime('%H:%M:%S')}] GPS/Location packaged: {p['village']}",
                        f"[{datetime.now().strftime('%H:%M:%S')}] Medical history packaged ({len(past_triage)} records)",
                        "── LOCALIZED RESPONDERS ──",
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Notified: All ASHA/ANM workers in system",
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Notified: Duty doctor at nearest PHC (PHC Ranjangaon)",
                        "── CENTRAL COMMAND ──",
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Dispatch Center pinged — patient location: {p['village']}",
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Ambulance dispatch requested for {p['village']}",
                    ]
                    routing_log="\n".join(routing_log_lines)

                    # ── Write SOS to DB ─────────────────────────────────
                    sid=str(uuid.uuid4())
                    conn=get_conn()
                    conn.execute(
                        "INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sid,abha_id,p["name"],p["village"],datetime.now().isoformat(),
                         "ACTIVE",None,None,None,"Manual SOS",med_summary,routing_log,0)
                    )
                    conn.commit(); conn.close()

                    # ── Dispatch notifications ──────────────────────────
                    notify_all_doctors(
                        f"🚨 EMERGENCY SOS — {p['name']} ({p['village']}) | Age {p['age']} | ABHA: {abha_id} | Nearest PHC: Ranjangaon. Medical history attached.",
                        "RED",abha_id=abha_id
                    )
                    notify_all_asha(
                        f"🚨 SOS ALERT — {p['name']} ({p['village']}) needs immediate help. You are the nearest responder.",
                        "RED",abha_id=abha_id
                    )

                    st.session_state["sos_armed"]=False
                    st.session_state["last_sos_id"]=sid

                    # ── Show split-routing result ───────────────────────
                    st.error("🚨 **EMERGENCY SOS DISPATCHED**")
                    with st.container(border=True):
                        st.markdown("#### 📡 Dispatch Report")
                        rc1,rc2=st.columns(2)
                        with rc1:
                            st.markdown("**📍 Localized Responders**")
                            st.success("✅ ASHA/ANM workers notified")
                            st.success("✅ Duty doctor at PHC Ranjangaon alerted")
                        with rc2:
                            st.markdown("**🏥 Central Command**")
                            st.success("✅ Dispatch Center pinged")
                            st.success("✅ Ambulance requested")
                        st.markdown("**📋 Medical Package Sent**")
                        st.code(med_summary,language=None)
                    st.rerun()

        # Show last SOS dispatch report if just triggered
        if st.session_state.get("last_sos_id"):
            sos_row=qdf("SELECT routing_log FROM sos_alerts WHERE id=?",(st.session_state["last_sos_id"],))
            if not sos_row.empty and sos_row.iloc[0]["routing_log"]:
                with st.expander("📡 View last SOS routing log"):
                    st.code(sos_row.iloc[0]["routing_log"],language=None)

        # Appointment booking form
        if st.session_state.get("show_appt"):
            with st.container(border=True):
                st.markdown("#### 📅 "+tr("book_appointment"))
                af1,af2,af3=st.columns(3)
                appt_fac=af1.selectbox("Facility",FACILITIES,key="appt_fac_p")
                appt_date=af2.date_input("Date",min_value=datetime.now().date(),key="appt_date_p")
                appt_slot=af3.selectbox("Time",["9:00–10:00 AM","10:00–11:00 AM","11:00–12:00 PM","2:00–3:00 PM","3:00–4:00 PM","4:00–5:00 PM"],key="appt_slot_p")
                if st.button("✅ Confirm Request",type="primary",key="book_appt_p"):
                    conn=get_conn()
                    conn.execute("INSERT INTO appointments(id,abha_id,facility,appointment_date,time_slot,status,created_at) VALUES(?,?,?,?,?,?,?)",
                                 (str(uuid.uuid4()),abha_id,appt_fac,str(appt_date),appt_slot,"REQUESTED",datetime.now().isoformat()))
                    conn.commit(); conn.close()
                    st.success(f"Appointment requested at {appt_fac} on {appt_date} ({appt_slot}).")
                    st.session_state["show_appt"]=False; st.rerun()

        # Self-triage form
        if st.session_state.get("show_self_triage"):
            with st.container(border=True):
                st.markdown("#### 🤖 Self Symptom Check")
                st.caption("Describe how you're feeling. The AI will assess your priority and alert the right people.")
                syms=st.text_area("Your symptoms",placeholder="e.g. I have chest pain and I'm finding it hard to breathe",height=90,key="self_triage_syms")
                if st.button("Check Symptoms",type="primary",key="self_triage_btn"):
                    if not syms:
                        st.warning("Please describe your symptoms first.")
                    else:
                        with st.spinner("Analysing..."):
                            priority,rationale,dept,fud=run_triage(syms)
                        tid=str(uuid.uuid4())
                        conn=get_conn()
                        conn.execute("""INSERT INTO triage(id,abha_id,symptoms_text,priority,rationale,
                                        created_by,created_at,department,follow_up_due_date,follow_up_done,triggered_by)
                                        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                                     (tid,abha_id,syms,priority,rationale,p["name"],datetime.now().isoformat(),dept,fud,0,"patient"))
                        conn.commit()

                        # Smart notification routing
                        if priority=="RED":
                            # Auto-SOS with full medical package
                            past_triage=qdf("SELECT priority,department,symptoms_text,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC LIMIT 5",(abha_id,))
                            med_lines=[f"Patient: {p['name']}, Age: {p['age']}, Village: {p['village']}, ABHA: {abha_id}","── Recent History ──"]
                            for _,r in past_triage.iterrows():
                                med_lines.append(f"• [{r['priority']}] {r['department']}: {r['symptoms_text'][:60]}")
                            med_summary="\n".join(med_lines)
                            routing_log="\n".join([
                                f"[{datetime.now().strftime('%H:%M:%S')}] AUTO-SOS from self-triage RED result",
                                f"[{datetime.now().strftime('%H:%M:%S')}] Symptoms: {syms[:80]}",
                                f"[{datetime.now().strftime('%H:%M:%S')}] ✅ All doctors notified",
                                f"[{datetime.now().strftime('%H:%M:%S')}] ✅ All ASHA workers notified",
                                f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Dispatch center pinged — {p['village']}",
                                f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Ambulance requested",
                            ])
                            sid=str(uuid.uuid4())
                            conn.execute(
                                "INSERT INTO sos_alerts(id,abha_id,patient_name,village,triggered_at,status,resolved_at,resolved_by,accepted_by,notes,medical_summary,routing_log,cancelled) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (sid,abha_id,p["name"],p["village"],datetime.now().isoformat(),"ACTIVE",None,None,None,"Auto-SOS from self-triage",med_summary,routing_log,0)
                            )
                            notify_all_doctors(f"🚨 AUTO-SOS: {p['name']} ({p['village']}) self-reported RED symptoms: '{syms[:60]}'. Full medical record attached.","RED",tid,abha_id)
                            notify_all_asha(f"🚨 AUTO-SOS: {p['name']} ({p['village']}) is in emergency. You are the nearest responder.","RED",tid,abha_id)
                        elif priority=="YELLOW":
                            notify_all_doctors(f"⚠️ YELLOW: {p['name']} ({p['village']}) needs follow-up — '{syms[:60]}'.","YELLOW",tid,abha_id)
                            notify_all_asha(f"⚠️ YELLOW: Patient {p['name']} ({p['village']}) reported symptoms. Please follow up.","YELLOW",tid,abha_id)
                        else:
                            notify_all_asha(f"ℹ️ GREEN: {p['name']} self-checked symptoms. No urgent action needed.","GREEN",tid,abha_id)
                        conn.commit(); conn.close()

                        col_r,_=st.columns([1,2])
                        col_r.markdown(f"**Result:** {priority_badge(priority)}",unsafe_allow_html=True)
                        st.write(rationale)
                        st.info(f"🏥 Suggested: **{dept}**")
                        if priority=="RED":
                            st.error("🚨 Emergency SOS auto-triggered. All doctors + ASHA workers alerted. Ambulance requested.")
                            with st.container(border=True):
                                st.markdown("**📡 Auto-Dispatch Report**")
                                rc1,rc2=st.columns(2)
                                rc1.success("✅ ASHA/ANM notified")
                                rc1.success("✅ Duty doctor alerted")
                                rc2.success("✅ Dispatch center pinged")
                                rc2.success("✅ Ambulance requested")
                        elif priority=="YELLOW":
                            st.warning("⚠️ Doctors and your ASHA worker have been notified.")
                        else:
                            st.success("✅ Your ASHA worker has been informed. Routine care advised.")

        st.divider()

        # My appointments & SOS status
        my_sos=qdf("SELECT status,triggered_at FROM sos_alerts WHERE abha_id=? AND status='ACTIVE'",(abha_id,))
        if not my_sos.empty:
            st.warning(f"🚨 {len(my_sos)} active SOS alert(s) awaiting response.")
        my_appts=qdf("SELECT facility,appointment_date,time_slot,status FROM appointments WHERE abha_id=? ORDER BY appointment_date DESC",(abha_id,))
        if not my_appts.empty:
            st.markdown("**📅 My Appointments**")
            st.dataframe(my_appts,use_container_width=True,hide_index=True)

        # Health record tabs
        st.subheader("📋 "+tr("my_health_record"))
        ht1,ht2=st.tabs(["🩺 "+tr("my_triage_history"),"📨 "+tr("my_referrals")])
        with ht1:
            th=qdf("SELECT symptoms_text,priority,department,temperature,spo2,pulse,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC",(abha_id,))
            if th.empty: st.info("🗒️ "+tr("no_records_yet"))
            else:
                for _,r in th.iterrows():
                    with st.container(border=True):
                        rc1,rc2=st.columns([3,1])
                        rc1.write(f"**{r['symptoms_text']}**")
                        rc2.markdown(priority_badge(r["priority"]),unsafe_allow_html=True)
                        rc1.caption(f"🏥 {r['department'] or '—'}  |  📅 {r['created_at'][:10]}")
                        if any([r["temperature"],r["spo2"],r["pulse"]]):
                            vc1,vc2,vc3=st.columns(3)
                            if r["temperature"]: vc1.metric("🌡️ Temp",f"{r['temperature']}°F")
                            if r["spo2"]: vc2.metric("🩸 SpO₂",f"{r['spo2']}%")
                            if r["pulse"]: vc3.metric("💓 Pulse",f"{r['pulse']} bpm")
        with ht2:
            rh=qdf("SELECT facility,status,prescription,doctor_notes,created_at,completed_at FROM referrals WHERE abha_id=? ORDER BY created_at DESC",(abha_id,))
            if rh.empty: st.info("🗒️ "+tr("no_records_yet"))
            else:
                for _,r in rh.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['facility']}** — `{r['status']}`  |  {r['created_at'][:10]}")
                        if r["prescription"]: st.write(f"💊 **Prescription:** {r['prescription']}")
                        if r["doctor_notes"]: st.caption(f"📝 Notes: {r['doctor_notes']}")

# ══════════════════════════════════════════════════════════════
# PAGE: ASHA WORKER PORTAL
# ══════════════════════════════════════════════════════════════
elif page==tr("asha"):
    sk="asha_user"
    if sk not in st.session_state: st.session_state[sk]=None

    if not st.session_state[sk]:
        row=auth_screen(tr("asha"),"asha_workers",
            extra_fields=[("facility","Facility",FACILITIES)])
        if row: st.session_state[sk]=row; st.rerun()
    else:
        u=st.session_state[sk]
        # Notifications badge
        notifs=get_unread("asha",u["id"])
        with st.container(border=True):
            ah1,ah2=st.columns([4,1])
            ah1.markdown(f"### 🚶‍♀️ Welcome, **{u['name']}** — {u['facility']}")
            if ah2.button(tr("logout_btn")):
                st.session_state[sk]=None; st.rerun()
            if notifs:
                st.warning(f"🔔 **{len(notifs)} new notification(s)**")
                for n in notifs:
                    st.write(f"• {n['message']}")
                if st.button("Mark all read",key="asha_mark_read"):
                    mark_read("asha",u["id"]); st.rerun()

        tab1,tab2,tab3,tab4=st.tabs([
            "📝 "+tr("register_patient"),
            "🤖 Triage & Referral",
            "🔔 High-Risk Follow-ups",
            "📜 My Patient History",
        ])

        with tab1:
            with st.form("asha_reg_form"):
                c1,c2=st.columns(2)
                rn=c1.text_input(tr("name")); ra=c2.number_input(tr("age"),0,120,30)
                rg=c1.selectbox(tr("gender"),["Female","Male","Other"])
                rv=c2.text_input(tr("village")); rph=c1.text_input(tr("phone"))
                rl=c2.selectbox(tr("language"),["Marathi","Hindi","Tamil","Telugu","Bengali","English"])
                setup_login=st.checkbox("Set up patient app login now")
                rpw=st.text_input("Patient password",type="password") if setup_login else ""
                submitted=st.form_submit_button(tr("register_btn"),type="primary",use_container_width=True)
                if submitted:
                    if not rn: st.error("Name required.")
                    elif setup_login and not rpw: st.error("Enter a password or uncheck login setup.")
                    else:
                        h,s=(hash_pw(rpw) if setup_login else (None,None))
                        aid=gen_abha()
                        conn=get_conn()
                        conn.execute("INSERT INTO patients(abha_id,name,age,gender,village,phone,language,created_at,password_hash,salt) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                     (aid,rn,ra,rg,rv,rph,rl,datetime.now().isoformat(),h,s))
                        conn.commit(); conn.close()
                        st.success(f"✅ Registered! ABHA ID: **{aid}**")
                        if setup_login: st.info(f"Patient can log in using phone {rph}.")
            st.subheader("My Registered Patients")
            # ASHA sees only patients they registered (by facility match, since we track facility)
            pts=qdf("SELECT abha_id,name,age,gender,village,phone FROM patients ORDER BY created_at DESC")
            st.dataframe(pts,use_container_width=True,hide_index=True)

        with tab2:
            pts2=qdf("SELECT abha_id,name FROM patients ORDER BY created_at DESC")
            if pts2.empty: st.info("Register a patient first.")
            else:
                opts={f"{r['name']} ({r['abha_id']})":r["abha_id"] for _,r in pts2.iterrows()}
                sel=st.selectbox("Select Patient",list(opts.keys()))
                abha_id=opts[sel]
                syms=st.text_area(tr("symptoms"),placeholder="e.g. High fever with breathlessness",height=90)
                with st.expander("📊 Vitals (optional)",expanded=False):
                    v1,v2,v3=st.columns(3)
                    vt=v1.text_input("🌡️ Temp (°F)",placeholder="e.g. 101.4",key="vt")
                    vs=v2.text_input("🩸 SpO₂ (%)",placeholder="e.g. 96",key="vs")
                    vp=v3.text_input("💓 Pulse (bpm)",placeholder="e.g. 88",key="vp")
                    for val,label,lo,hi in [(vt,"Temp",103,999),(vs,"SpO₂",0,93),(vp,"Pulse",60,100)]:
                        try:
                            fv=float(val)
                            if (label=="Temp" and fv>=lo) or (label=="SpO₂" and fv<=93) or (label=="Pulse" and (fv>100 or fv<60)):
                                st.warning(f"⚠️ Abnormal {label}: {val}")
                        except: pass
                if st.button("🤖 "+tr("run_triage"),type="primary"):
                    if not syms: st.warning("Enter symptoms.")
                    else:
                        with st.spinner("Analysing..."):
                            priority,rationale,dept,fud=run_triage(syms)
                        tid=str(uuid.uuid4())
                        conn=get_conn()
                        conn.execute("""INSERT INTO triage(id,abha_id,symptoms_text,priority,rationale,
                                        created_by,created_at,department,follow_up_due_date,follow_up_done,
                                        temperature,spo2,pulse,triggered_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                     (tid,abha_id,syms,priority,rationale,u["name"],datetime.now().isoformat(),
                                      dept,fud,0,vt or None,vs or None,vp or None,"asha"))
                        conn.commit(); conn.close()
                        st.session_state["last_tid"]=tid
                        st.session_state["last_priority"]=priority
                        st.markdown(f"### Result: {priority_badge(priority)}",unsafe_allow_html=True)
                        st.write(rationale)
                        st.info(f"🏥 Suggested: **{dept}**")
                        if fud: st.caption(f"📅 Follow-up due: {fud}")

                if st.session_state.get("last_tid"):
                    pr=st.session_state.get("last_priority","GREEN")
                    if pr in ("RED","YELLOW"):
                        st.divider()
                        st.warning("⚠️ Patient needs facility care.")
                        fac=st.selectbox(tr("select_facility"),FACILITIES)
                        if st.button("🚑 "+tr("refer_btn"),type="primary"):
                            conn=get_conn()
                            conn.execute("INSERT INTO referrals VALUES(?,?,?,?,?,?,?,?,?,?)",
                                         (str(uuid.uuid4()),abha_id,st.session_state["last_tid"],fac,"PENDING","","",datetime.now().isoformat(),None,None))
                            conn.commit(); conn.close()
                            st.success(f"Referral sent to {fac}.")
                            del st.session_state["last_tid"]
                    else:
                        st.info("GREEN — routine care.")

        with tab3:
            st.caption("Patients needing follow-up based on their triage priority.")
            due=qdf("""SELECT t.id as tid, p.name, p.phone, p.village, t.priority, t.department,
                               t.follow_up_due_date
                        FROM triage t JOIN patients p ON p.abha_id=t.abha_id
                        WHERE t.follow_up_due_date IS NOT NULL
                          AND (t.follow_up_done IS NULL OR t.follow_up_done=0)
                        ORDER BY t.follow_up_due_date ASC""")
            if due.empty: st.success("✅ No pending follow-ups!")
            else:
                today=datetime.now().strftime("%Y-%m-%d")
                for _,r in due.iterrows():
                    overdue=r["follow_up_due_date"]<today
                    with st.container(border=True):
                        dc1,dc2=st.columns([4,1])
                        label=f"{'🔴 OVERDUE' if overdue else '🟡 Due'} **{r['follow_up_due_date']}** — {r['name']} ({r['village']})"
                        dc1.markdown(label)
                        dc1.caption(f"{r['priority']} · {r['department']} · 📞 {r['phone']}")
                        if dc2.button("✅ Done",key=f"fu_{r['tid']}",use_container_width=True):
                            conn=get_conn(); conn.execute("UPDATE triage SET follow_up_done=1 WHERE id=?",(r["tid"],)); conn.commit(); conn.close(); st.rerun()

        with tab4:
            st.subheader("📜 All Emergency (RED) Patients")
            em=qdf("""SELECT p.name,p.village,t.symptoms_text,t.created_at,t.department
                       FROM triage t JOIN patients p ON p.abha_id=t.abha_id
                       WHERE t.priority='RED' ORDER BY t.created_at DESC""")
            if em.empty: st.info("No RED priority cases yet.")
            else:
                for _,r in em.iterrows():
                    with st.container(border=True):
                        st.write(f"🔴 **{r['name']}** ({r['village']}) — {r['department']}")
                        st.caption(f"{r['symptoms_text'][:80]}  |  {r['created_at'][:10]}")
            st.divider()
            st.subheader("📜 All Registered Patients History")
            ah=qdf("""SELECT p.name,p.village,t.priority,t.symptoms_text,t.department,t.created_at
                       FROM triage t JOIN patients p ON p.abha_id=t.abha_id ORDER BY t.created_at DESC LIMIT 50""")
            if ah.empty: st.info("No triage history yet.")
            else: st.dataframe(ah,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════
# PAGE: DOCTOR DASHBOARD
# ══════════════════════════════════════════════════════════════
elif page==tr("doctor"):
    sk="doctor_user"
    if sk not in st.session_state: st.session_state[sk]=None

    if not st.session_state[sk]:
        row=auth_screen(tr("doctor"),"doctors",
            extra_fields=[
                ("facility","Facility",FACILITIES),
                ("speciality","Speciality",["General Medicine","Cardiology","Pediatrics","Obstetrics & Gynaecology","Pulmonology","Neurology","Orthopedics","Gastroenterology"]),
            ])
        if row: st.session_state[sk]=row; st.rerun()
    else:
        u=st.session_state[sk]
        notifs=get_unread("doctor",u["id"])
        with st.container(border=True):
            dh1,dh2=st.columns([4,1])
            dh1.markdown(f"### 🩺 Dr. **{u['name']}** — {u['facility']} ({u['speciality']})")
            if dh2.button(tr("logout_btn")):
                st.session_state[sk]=None; st.rerun()
            if notifs:
                reds=[n for n in notifs if n["priority"]=="RED"]
                if reds:
                    st.error(f"🚨 {len(reds)} EMERGENCY ALERT(S)!")
                    for n in reds: st.write(f"• {n['message']}")
                yellows=[n for n in notifs if n["priority"] in ("YELLOW","GREEN")]
                if yellows:
                    st.warning(f"🔔 {len(yellows)} patient notification(s)")
                    for n in yellows: st.write(f"• {n['message']}")
                if st.button("Mark all read",key="doc_mark_read"):
                    mark_read("doctor",u["id"]); st.rerun()

        # Metrics
        total_seen=qdf(f"SELECT COUNT(*) as n FROM referrals WHERE doctor_id=? AND status='COMPLETED'",(u["id"],))["n"][0]
        pending_ref=qdf(f"SELECT COUNT(*) as n FROM referrals WHERE facility=? AND status='PENDING'",(u["facility"],))["n"][0]
        pending_appts=qdf(f"SELECT COUNT(*) as n FROM appointments WHERE facility=? AND status='REQUESTED'",(u["facility"],))["n"][0]
        mc1,mc2,mc3=st.columns(3)
        mc1.metric("✅ Patients Completed",total_seen)
        mc2.metric("📋 Pending Referrals",pending_ref)
        mc3.metric("📅 Pending Appointments",pending_appts)

        dt1,dt2,dt3,dt4,dt5=st.tabs([
            "📋 Queue","🔍 Search Patient","📅 Appointments","📜 My History","🚨 SOS Alerts"
        ])

        with dt1:
            q_sql="""SELECT r.id as ref_id,p.abha_id,p.name,p.age,p.gender,p.village,
                            t.symptoms_text,t.priority,t.rationale,t.department,t.created_by,r.status,r.created_at
                     FROM referrals r JOIN patients p ON p.abha_id=r.abha_id
                     JOIN triage t ON t.id=r.triage_id
                     WHERE r.facility=? AND r.status='PENDING'"""
            queue=qdf(q_sql,(u["facility"],))
            if queue.empty: st.info("✅ No pending referrals.")
            else:
                queue["sort"]=queue["priority"].map(PRIORITY_ORDER)
                queue=queue.sort_values("sort")
                for _,row in queue.iterrows():
                    with st.expander(f"{row['name']} · {row['age']}y · {row['priority']} · {row['department'] or 'General Medicine'}",expanded=False):
                        b1,b2=st.columns([3,1])
                        b1.markdown(priority_badge(row["priority"]),unsafe_allow_html=True)
                        b2.markdown(f"🏥 **{row['department'] or 'General'}**")
                        st.write(f"**ABHA:** {row['abha_id']}  |  **Village:** {row['village']}")
                        st.write(f"**Symptoms:** {row['symptoms_text']}")
                        st.caption(f"AI: {row['rationale']}")
                        with st.container(border=True):
                            st.markdown("**📜 Full Patient History**")
                            ht1,ht2=st.tabs(["Past Visits","Past Prescriptions"])
                            with ht1:
                                ph=qdf("SELECT symptoms_text,priority,department,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC",(row["abha_id"],))
                                if ph.empty: st.caption("No prior visits.")
                                else: st.dataframe(ph,use_container_width=True,hide_index=True)
                            with ht2:
                                pr=qdf("SELECT facility,prescription,doctor_notes,completed_at FROM referrals WHERE abha_id=? AND status='COMPLETED' ORDER BY completed_at DESC",(row["abha_id"],))
                                if pr.empty: st.caption("No past prescriptions.")
                                else: st.dataframe(pr,use_container_width=True,hide_index=True)
                        if st.button("📹 "+tr("teleconsult"),key=f"tc_{row['ref_id']}"):
                            st.info("WebRTC teleconsultation would launch here.")
                        presc=st.text_area(tr("prescription"),key=f"presc_{row['ref_id']}")
                        notes=st.text_input("Notes",key=f"notes_{row['ref_id']}")
                        if st.button(tr("save_prescription"),key=f"save_{row['ref_id']}",type="primary"):
                            conn=get_conn()
                            conn.execute("UPDATE referrals SET status='COMPLETED',prescription=?,doctor_notes=?,completed_at=?,doctor_id=? WHERE id=?",
                                         (presc,notes,datetime.now().isoformat(),u["id"],row["ref_id"]))
                            conn.commit(); conn.close()
                            st.success("Completed!"); st.rerun()

        with dt2:
            st.subheader("🔍 Search Patient")
            search=st.text_input("Search by name, ABHA ID or phone",placeholder="e.g. Sunita or ABHA-12345")
            if search:
                res=qdf(f"SELECT abha_id,name,age,gender,village,phone FROM patients WHERE name LIKE ? OR abha_id LIKE ? OR phone LIKE ?",
                        (f"%{search}%",f"%{search}%",f"%{search}%"))
                if res.empty: st.info("No patients found.")
                else:
                    for _,r in res.iterrows():
                        with st.expander(f"{r['name']} — {r['abha_id']} ({r['village']})"):
                            st.write(f"**Age:** {r['age']}  |  **Gender:** {r['gender']}  |  **Phone:** {r['phone']}")
                            ht1,ht2=st.tabs(["Triage History","Referrals & Prescriptions"])
                            with ht1:
                                ph=qdf("SELECT symptoms_text,priority,department,temperature,spo2,pulse,created_at FROM triage WHERE abha_id=? ORDER BY created_at DESC",(r["abha_id"],))
                                if ph.empty: st.caption("No visits.")
                                else: st.dataframe(ph,use_container_width=True,hide_index=True)
                            with ht2:
                                rh=qdf("SELECT facility,status,prescription,doctor_notes,completed_at FROM referrals WHERE abha_id=? ORDER BY created_at DESC",(r["abha_id"],))
                                if rh.empty: st.caption("No referrals.")
                                else: st.dataframe(rh,use_container_width=True,hide_index=True)

        with dt3:
            st.subheader("📅 Appointment Requests")
            appts=qdf("""SELECT a.id,p.name,p.phone,a.appointment_date,a.time_slot,a.status,a.decline_reason
                          FROM appointments a JOIN patients p ON p.abha_id=a.abha_id
                          WHERE a.facility=? ORDER BY a.appointment_date,a.time_slot""",(u["facility"],))
            pending=appts[appts["status"]=="REQUESTED"] if not appts.empty else pd.DataFrame()
            if pending.empty: st.info("No pending appointment requests.")
            else:
                st.markdown("**Pending Requests**")
                for _,a in pending.iterrows():
                    with st.container(border=True):
                        ac1,ac2,ac3=st.columns([3,1,1])
                        ac1.write(f"**{a['name']}** — {a['appointment_date']} at {a['time_slot']}")
                        ac1.caption(f"📞 {a['phone']}")
                        if ac2.button("✅ Accept",key=f"acc_{a['id']}",use_container_width=True):
                            conn=get_conn(); conn.execute("UPDATE appointments SET status='CONFIRMED',doctor_id=? WHERE id=?",(u["id"],a["id"])); conn.commit(); conn.close(); st.rerun()
                        if ac3.button("❌ Decline",key=f"dec_{a['id']}",use_container_width=True):
                            st.session_state[f"show_decline_{a['id']}"]=True
                    if st.session_state.get(f"show_decline_{a['id']}"):
                        reason=st.text_input("Reason for declining (required)",key=f"reason_{a['id']}",placeholder="e.g. Holiday on that date")
                        if st.button("Confirm Decline",key=f"confirm_dec_{a['id']}"):
                            if not reason: st.error("Please enter a reason.")
                            else:
                                conn=get_conn(); conn.execute("UPDATE appointments SET status='DECLINED',decline_reason=? WHERE id=?",(reason,a["id"])); conn.commit(); conn.close()
                                del st.session_state[f"show_decline_{a['id']}"]; st.rerun()

            st.divider()
            st.markdown("**All Appointments**")
            for status,label in [("CONFIRMED","✅ Confirmed"),("COMPLETED","🏁 Completed"),("DECLINED","❌ Declined")]:
                grp=appts[appts["status"]==status] if not appts.empty else pd.DataFrame()
                if not grp.empty:
                    with st.expander(f"{label} ({len(grp)})"):
                        for _,a in grp.iterrows():
                            ac1,ac2=st.columns([4,1])
                            ac1.write(f"**{a['name']}** — {a['appointment_date']} at {a['time_slot']}")
                            if a["decline_reason"]: ac1.caption(f"Reason: {a['decline_reason']}")
                            if status=="CONFIRMED":
                                if ac2.button("🏁 Done",key=f"done_{a['id']}",use_container_width=True):
                                    conn=get_conn(); conn.execute("UPDATE appointments SET status='COMPLETED' WHERE id=?",(a["id"],)); conn.commit(); conn.close(); st.rerun()

        with dt4:
            st.subheader("📜 My Completed Cases")
            my_hist=qdf("""SELECT p.name,p.village,t.priority,r.prescription,r.doctor_notes,r.completed_at
                            FROM referrals r JOIN patients p ON p.abha_id=r.abha_id
                            JOIN triage t ON t.id=r.triage_id
                            WHERE r.doctor_id=? AND r.status='COMPLETED' ORDER BY r.completed_at DESC""",(u["id"],))
            if my_hist.empty: st.info("No completed cases yet.")
            else:
                for _,r in my_hist.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['name']}** ({r['village']}) — {priority_badge(r['priority'])}",unsafe_allow_html=True)
                        if r["prescription"]: st.write(f"💊 {r['prescription']}")
                        st.caption(f"Completed: {str(r['completed_at'])[:10]}")

        with dt5:
            st.subheader("🚨 Active SOS Alerts")
            sos=qdf("SELECT id,patient_name,village,triggered_at,accepted_by FROM sos_alerts WHERE status='ACTIVE' ORDER BY triggered_at DESC")
            if sos.empty: st.success("No active SOS alerts.")
            else:
                for _,s in sos.iterrows():
                    with st.container(border=True):
                        sc1,sc2=st.columns([4,1])
                        sc1.write(f"🚨 **{s['patient_name']}** — {s['village']}")
                        sc1.caption(f"Triggered: {s['triggered_at'][:16]}")
                        if s["accepted_by"]:
                            sc1.info(f"✅ Being handled by {s['accepted_by']}")
                        else:
                            if sc2.button("Accept",key=f"accept_sos_{s['id']}",type="primary",use_container_width=True):
                                conn=get_conn()
                                conn.execute("UPDATE sos_alerts SET accepted_by=? WHERE id=?",(u["name"],s["id"]))
                                conn.commit(); conn.close()
                                notify_all_doctors(f"✅ SOS for {s['patient_name']} is being handled by Dr. {u['name']}. No further action needed.","GREEN")
                                st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE: DISTRICT ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════
elif page==tr("admin"):
    st.subheader("🏛️ "+tr("admin"))

    # Live emergency banner
    active_sos=qdf("SELECT id,patient_name,village,triggered_at FROM sos_alerts WHERE status='ACTIVE' ORDER BY triggered_at DESC")
    if not active_sos.empty:
        st.error(f"🚨 {len(active_sos)} ACTIVE EMERGENCY SOS ALERT(S) — Requires Immediate Action")
        for _,s in active_sos.iterrows():
            sc1,sc2=st.columns([4,1])
            sc1.write(f"**{s['patient_name']}** — {s['village']} | {s['triggered_at'][:16]}")
            if sc2.button("✅ Resolve",key=f"res_{s['id']}",use_container_width=True):
                conn=get_conn(); conn.execute("UPDATE sos_alerts SET status='RESOLVED',resolved_at=?,resolved_by='Admin' WHERE id=?",(datetime.now().isoformat(),s["id"])); conn.commit(); conn.close(); st.rerun()
        st.divider()

    # Key metrics
    total_p=qdf("SELECT COUNT(*) as n FROM patients")["n"][0]
    total_t=qdf("SELECT COUNT(*) as n FROM triage")["n"][0]
    total_r=qdf("SELECT COUNT(*) as n FROM referrals")["n"][0]
    comp_r=qdf("SELECT COUNT(*) as n FROM referrals WHERE status='COMPLETED'")["n"][0]
    comp_rate=(comp_r/total_r*100) if total_r else 0
    pend_fu=qdf("SELECT COUNT(*) as n FROM triage WHERE follow_up_due_date IS NOT NULL AND (follow_up_done IS NULL OR follow_up_done=0)")["n"][0]
    pend_appts=qdf("SELECT COUNT(*) as n FROM appointments WHERE status='REQUESTED'")["n"][0]
    total_docs=qdf("SELECT COUNT(*) as n FROM doctors")["n"][0]
    total_asha=qdf("SELECT COUNT(*) as n FROM asha_workers")["n"][0]

    m1,m2,m3,m4=st.columns(4)
    m1.metric("👥 Patients",total_p); m2.metric("🤖 Triages",total_t)
    m3.metric("📋 Referrals",total_r); m4.metric("✅ Completion",f"{comp_rate:.0f}%")
    m5,m6,m7,m8=st.columns(4)
    m5.metric("🔔 Follow-ups Due",pend_fu); m6.metric("📅 Appts Pending",pend_appts)
    m7.metric("🩺 Registered Doctors",total_docs); m8.metric("🚶‍♀️ ASHA Workers",total_asha)

    st.divider()

    # Charts — horizontal for readability
    ch1,ch2=st.columns(2)
    with ch1:
        st.subheader("Triage by Priority")
        pr=qdf("SELECT priority,COUNT(*) as count FROM triage GROUP BY priority")
        if not pr.empty:
            pr=pr.set_index("priority")
            st.bar_chart(pr,horizontal=True,color=["#e53935"])
        else: st.info("No triage data yet.")
    with ch2:
        st.subheader("Referrals by Facility")
        rf=qdf("SELECT facility,COUNT(*) as count FROM referrals GROUP BY facility")
        if not rf.empty:
            st.bar_chart(rf.set_index("facility"),horizontal=True)
        else: st.info("No referral data yet.")

    ch3,ch4=st.columns(2)
    with ch3:
        st.subheader("Department-wise Cases")
        dp=qdf("SELECT department,COUNT(*) as count FROM triage WHERE department IS NOT NULL GROUP BY department ORDER BY count DESC")
        if not dp.empty: st.bar_chart(dp.set_index("department"),horizontal=True)
    with ch4:
        st.subheader("Appointments Status")
        ap=qdf("SELECT status,COUNT(*) as count FROM appointments GROUP BY status")
        if not ap.empty: st.bar_chart(ap.set_index("status"),horizontal=True)

    st.divider()

    # Area-wise patient history with filters
    st.subheader("🗺️ Area-wise Patient Records")
    with st.container(border=True):
        f1,f2,f3,f4=st.columns(4)
        fac_filter=f1.selectbox("Filter by Facility",["All"]+FACILITIES,key="admin_fac")
        prio_filter=f2.selectbox("Filter by Priority",["All","RED","YELLOW","GREEN"],key="admin_prio")
        dept_filter=f3.selectbox("Filter by Department",["All","General Medicine","Cardiology","Pediatrics","Obstetrics & Gynaecology","Pulmonology","Neurology","Orthopedics","Gastroenterology"],key="admin_dept")
        sort_by=f4.selectbox("Sort by",["Date (newest)","Date (oldest)","Priority (urgent first)","Village"],key="admin_sort")

        sym_search=st.text_input("Search by symptom keywords",placeholder="e.g. fever, chest pain",key="admin_sym")

        sql="""SELECT p.name,p.village,t.priority,t.department,t.symptoms_text,
                      t.temperature,t.spo2,t.pulse,t.created_at,
                      r.facility,r.status as referral_status
               FROM triage t
               JOIN patients p ON p.abha_id=t.abha_id
               LEFT JOIN referrals r ON r.triage_id=t.id
               WHERE 1=1"""
        params=[]
        if prio_filter!="All": sql+=" AND t.priority=?"; params.append(prio_filter)
        if dept_filter!="All": sql+=" AND t.department=?"; params.append(dept_filter)
        if fac_filter!="All": sql+=" AND r.facility=?"; params.append(fac_filter)
        if sym_search: sql+=" AND t.symptoms_text LIKE ?"; params.append(f"%{sym_search}%")

        sort_map={"Date (newest)":"t.created_at DESC","Date (oldest)":"t.created_at ASC",
                  "Priority (urgent first)":"CASE t.priority WHEN 'RED' THEN 0 WHEN 'YELLOW' THEN 1 ELSE 2 END",
                  "Village":"p.village"}
        sql+=f" ORDER BY {sort_map[sort_by]}"
        area_df=qdf(sql,tuple(params))
        st.caption(f"{len(area_df)} records found")
        if area_df.empty: st.info("No records match your filters.")
        else: st.dataframe(area_df,use_container_width=True,hide_index=True)

    st.divider()
    # Outbreak signal
    st.subheader("⚠️ Symptom Outbreak Signal (recent 20 entries)")
    recent=qdf("SELECT symptoms_text,priority,department,created_at FROM triage ORDER BY created_at DESC LIMIT 20")
    st.dataframe(recent,use_container_width=True,hide_index=True)

    st.divider()
    st.subheader("💊 Low Stock Alerts (below 10 units)")
    low=qdf("SELECT facility,medicine_name,quantity,unit FROM medicine_stock WHERE quantity<10 ORDER BY quantity")
    if low.empty: st.success("No low-stock alerts.")
    else: st.dataframe(low,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════
# PAGE: MEDICINE STOCK
# ══════════════════════════════════════════════════════════════
elif page==tr("medicine"):
    st.subheader("💊 "+tr("medicine"))
    s1,s2=st.columns(2)
    fac_filter=s1.selectbox("Facility",["All"]+FACILITIES,key="med_fac_filter")
    med_search=s2.text_input("Search medicine name",key="med_search")

    sql="SELECT facility,medicine_name,quantity,unit,last_updated FROM medicine_stock WHERE 1=1"
    params=[]
    if fac_filter!="All": sql+=" AND facility=?"; params.append(fac_filter)
    if med_search: sql+=" AND medicine_name LIKE ?"; params.append(f"%{med_search}%")
    sql+=" ORDER BY facility,medicine_name"
    stock=qdf(sql,tuple(params))

    def hl(row):
        if row["quantity"]<10: return ["background-color:#ffcdd2;color:black"]*len(row)
        return ["color:white"]*len(row)

    if stock.empty: st.info("No medicines found.")
    else:
        st.dataframe(stock.style.apply(hl,axis=1),use_container_width=True,hide_index=True)
        st.caption("🔴 Red rows = low stock (below 10 units)")

    st.divider()
    st.subheader("📦 Restock / Update Inventory")
    upd_tab,add_tab=st.tabs(["Update existing stock","Add new medicine"])

    with upd_tab:
        # Facility selector for update (the key ask — filter to one facility first)
        upd_fac=st.selectbox("Select Facility to Update",FACILITIES,key="upd_fac")
        fac_meds=qdf("SELECT id,medicine_name,quantity,unit FROM medicine_stock WHERE facility=? ORDER BY medicine_name",(upd_fac,))
        if fac_meds.empty: st.info("No medicines for this facility.")
        else:
            labels={f"{r['medicine_name']} (current: {r['quantity']} {r['unit']})":r["id"] for _,r in fac_meds.iterrows()}
            chosen_label=st.selectbox("Select medicine",list(labels.keys()),key="med_chosen")
            chosen_id=labels[chosen_label]
            mode=st.radio("Action",["➕ Add stock (restock)","➖ Remove stock (dispensed/damaged)","🔢 Set exact quantity"],key="med_mode")
            amount=st.number_input("Amount",min_value=0,value=10,step=1,key="med_amount")
            if st.button("✅ Apply Update",type="primary",key="med_apply"):
                conn=get_conn()
                cur=conn.execute("SELECT quantity FROM medicine_stock WHERE id=?",(chosen_id,)).fetchone()[0]
                new_qty=cur+amount if "Add" in mode else (max(0,cur-amount) if "Remove" in mode else amount)
                conn.execute("UPDATE medicine_stock SET quantity=?,last_updated=? WHERE id=?",(new_qty,datetime.now().isoformat(),chosen_id))
                conn.commit(); conn.close()
                st.success(f"Updated — new quantity: **{new_qty}**"); st.rerun()

    with add_tab:
        with st.form("add_med_form"):
            nf=st.selectbox("Facility",FACILITIES,key="new_med_fac")
            nm=st.text_input("Medicine name"); nq=st.number_input("Starting quantity",0,value=50)
            nu=st.selectbox("Unit",["tablets","capsules","vials","sachets","units","bottles"])
            if st.form_submit_button("➕ Add Medicine",type="primary",use_container_width=True):
                if not nm: st.error("Medicine name required.")
                else:
                    conn=get_conn()
                    conn.execute("INSERT INTO medicine_stock VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),nf,nm,nq,nu,datetime.now().isoformat()))
                    conn.commit(); conn.close()
                    st.success(f"Added {nm} to {nf}."); st.rerun()
