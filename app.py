"""
SevaSetu - "Bridge to Healthcare"
SIH 2026 | PS ID: SIH26133
Streamlit Prototype (MVP) for live demo

Demo flow:
ASHA registers patient -> runs AI triage -> flags HIGH RISK -> refers to facility
  -> Doctor sees referral in queue -> teleconsults -> writes prescription -> completes referral
  -> Admin Dashboard shows live analytics across the system

Run:
    pip install -r requirements.txt
    streamlit run app.py

Optional (for real LLM-based triage instead of the built-in rule engine):
    export GROQ_API_KEY=your_key_here
"""

import os
import sqlite3
import uuid
import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "sevasetu.db")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"

st.set_page_config(
    page_title="SevaSetu | SIH26133",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIORITY_COLORS = {"RED": "#e53935", "YELLOW": "#fbc02d", "GREEN": "#43a047"}
PRIORITY_ORDER = {"RED": 0, "YELLOW": 1, "GREEN": 2}

FACILITIES = [
    "Sub-Centre Wagholi",
    "PHC Ranjangaon",
    "District Hospital Pune",
]

# ---------------------------------------------------------------------------
# I18N (minimal, extensible)
# ---------------------------------------------------------------------------
T = {
    "en": {
        "app_title": "SevaSetu — Bridge to Healthcare",
        "role": "Select your role",
        "asha": "ASHA / ANM Worker",
        "doctor": "Doctor / Facility Dashboard",
        "admin": "District Admin Dashboard",
        "medicine": "Medicine Stock Checker",
        "register_patient": "Register New Patient",
        "name": "Full Name",
        "age": "Age",
        "gender": "Gender",
        "village": "Village / Ward",
        "phone": "Phone Number",
        "language": "Preferred Language",
        "register_btn": "Register Patient (Generate ABHA-linked ID)",
        "symptoms": "Describe symptoms",
        "run_triage": "Run AI Triage",
        "priority": "Priority",
        "refer_btn": "Refer to Facility",
        "select_facility": "Refer to which facility?",
        "queue": "Live Patient Queue",
        "no_referrals": "No referrals in queue yet.",
        "prescription": "Prescription",
        "save_prescription": "Save Prescription & Complete Referral",
        "teleconsult": "Start Teleconsultation (WebRTC)",
    },
    "hi": {
        "app_title": "सेवासेतु — स्वास्थ्य सेवा का पुल",
        "role": "अपनी भूमिका चुनें",
        "asha": "आशा / एएनएम कार्यकर्ता",
        "doctor": "डॉक्टर / सुविधा डैशबोर्ड",
        "admin": "जिला प्रशासन डैशबोर्ड",
        "medicine": "दवा स्टॉक जांच",
        "register_patient": "नया रोगी पंजीकृत करें",
        "name": "पूरा नाम",
        "age": "आयु",
        "gender": "लिंग",
        "village": "गाँव / वार्ड",
        "phone": "फ़ोन नंबर",
        "language": "पसंदीदा भाषा",
        "register_btn": "रोगी पंजीकृत करें (ABHA ID बनाएं)",
        "symptoms": "लक्षण बताएं",
        "run_triage": "AI ट्राइएज चलाएं",
        "priority": "प्राथमिकता",
        "refer_btn": "सुविधा के लिए रेफर करें",
        "select_facility": "किस सुविधा के लिए रेफर करें?",
        "queue": "लाइव रोगी कतार",
        "no_referrals": "कतार में अभी कोई रेफरल नहीं है।",
        "prescription": "नुस्खा",
        "save_prescription": "नुस्खा सहेजें और रेफरल पूरा करें",
        "teleconsult": "टेलीकंसल्टेशन शुरू करें (WebRTC)",
    },
    "mr": {
        "app_title": "सेवासेतू — आरोग्यसेवेचा पूल",
        "role": "तुमची भूमिका निवडा",
        "asha": "आशा / एएनएम कार्यकर्ता",
        "doctor": "डॉक्टर / सुविधा डॅशबोर्ड",
        "admin": "जिल्हा प्रशासन डॅशबोर्ड",
        "medicine": "औषध साठा तपासणी",
        "register_patient": "नवीन रुग्ण नोंदणी",
        "name": "पूर्ण नाव",
        "age": "वय",
        "gender": "लिंग",
        "village": "गाव / वॉर्ड",
        "phone": "फोन नंबर",
        "language": "पसंतीची भाषा",
        "register_btn": "रुग्ण नोंदणी करा (ABHA ID तयार करा)",
        "symptoms": "लक्षणे सांगा",
        "run_triage": "AI ट्रायएज चालवा",
        "priority": "प्राधान्य",
        "refer_btn": "सुविधेकडे संदर्भित करा",
        "select_facility": "कोणत्या सुविधेकडे संदर्भित करायचे?",
        "queue": "थेट रुग्ण रांग",
        "no_referrals": "रांगेत अद्याप कोणतेही संदर्भ नाहीत.",
        "prescription": "प्रिस्क्रिप्शन",
        "save_prescription": "प्रिस्क्रिप्शन जतन करा आणि संदर्भ पूर्ण करा",
        "teleconsult": "टेलिकन्सल्टेशन सुरू करा (WebRTC)",
    },
    "ta": {
        "app_title": "சேவாசேது — சுகாதார சேவைக்கான பாலம்",
        "role": "உங்கள் பாத்திரத்தைத் தேர்ந்தெடுக்கவும்",
        "asha": "ஆஷா / ஏஎன்எம் பணியாளர்",
        "doctor": "மருத்துவர் / மையம் டாஷ்போர்டு",
        "admin": "மாவட்ட நிர்வாக டாஷ்போர்டு",
        "medicine": "மருந்து கையிருப்பு சரிபார்ப்பு",
        "register_patient": "புதிய நோயாளியைப் பதிவு செய்யவும்",
        "name": "முழுப் பெயர்",
        "age": "வயது",
        "gender": "பாலினம்",
        "village": "கிராமம் / வார்டு",
        "phone": "தொலைபேசி எண்",
        "language": "விருப்பமான மொழி",
        "register_btn": "நோயாளியைப் பதிவு செய்யவும் (ABHA ID உருவாக்கவும்)",
        "symptoms": "அறிகுறிகளை விவரிக்கவும்",
        "run_triage": "AI முன்னுரிமை வகைப்பாட்டை இயக்கவும்",
        "priority": "முன்னுரிமை",
        "refer_btn": "மையத்திற்கு பரிந்துரைக்கவும்",
        "select_facility": "எந்த மையத்திற்கு பரிந்துரைக்க வேண்டும்?",
        "queue": "நேரடி நோயாளர் வரிசை",
        "no_referrals": "வரிசையில் இதுவரை பரிந்துரைகள் இல்லை.",
        "prescription": "மருந்துச் சீட்டு",
        "save_prescription": "மருந்துச் சீட்டைச் சேமித்து பரிந்துரையை முடிக்கவும்",
        "teleconsult": "தொலைத் தொடர்பு ஆலோசனையைத் தொடங்கவும் (WebRTC)",
    },
    "te": {
        "app_title": "సేవాసేతు — ఆరోగ్య సేవకు వంతెన",
        "role": "మీ పాత్రను ఎంచుకోండి",
        "asha": "ఆశా / ఏఎన్ఎం కార్యకర్త",
        "doctor": "డాక్టర్ / సదుపాయ డాష్‌బోర్డ్",
        "admin": "జిల్లా అడ్మిన్ డాష్‌బోర్డ్",
        "medicine": "మందుల నిల్వ తనిఖీ",
        "register_patient": "కొత్త రోగిని నమోదు చేయండి",
        "name": "పూర్తి పేరు",
        "age": "వయస్సు",
        "gender": "లింగం",
        "village": "గ్రామం / వార్డు",
        "phone": "ఫోన్ నంబర్",
        "language": "ఇష్టమైన భాష",
        "register_btn": "రోగిని నమోదు చేయండి (ABHA ID సృష్టించండి)",
        "symptoms": "లక్షణాలను వివరించండి",
        "run_triage": "AI ట్రయాజ్ నడపండి",
        "priority": "ప్రాధాన్యత",
        "refer_btn": "సదుపాయానికి రిఫర్ చేయండి",
        "select_facility": "ఏ సదుపాయానికి రిఫర్ చేయాలి?",
        "queue": "ప్రత్యక్ష రోగుల క్యూ",
        "no_referrals": "క్యూలో ఇంకా రిఫరల్స్ లేవు.",
        "prescription": "ప్రిస్క్రిప్షన్",
        "save_prescription": "ప్రిస్క్రిప్షన్ సేవ్ చేసి రిఫరల్ పూర్తి చేయండి",
        "teleconsult": "టెలికన్సల్టేషన్ ప్రారంభించండి (WebRTC)",
    },
    "bn": {
        "app_title": "সেবাসেতু — স্বাস্থ্যসেবার সেতু",
        "role": "আপনার ভূমিকা নির্বাচন করুন",
        "asha": "আশা / এএনএম কর্মী",
        "doctor": "ডাক্তার / সুবিধা ড্যাশবোর্ড",
        "admin": "জেলা প্রশাসন ড্যাশবোর্ড",
        "medicine": "ওষুধ স্টক পরীক্ষা",
        "register_patient": "নতুন রোগী নিবন্ধন করুন",
        "name": "পুরো নাম",
        "age": "বয়স",
        "gender": "লিঙ্গ",
        "village": "গ্রাম / ওয়ার্ড",
        "phone": "ফোন নম্বর",
        "language": "পছন্দের ভাষা",
        "register_btn": "রোগী নিবন্ধন করুন (ABHA ID তৈরি করুন)",
        "symptoms": "লক্ষণ বর্ণনা করুন",
        "run_triage": "AI ট্রায়াজ চালান",
        "priority": "অগ্রাধিকার",
        "refer_btn": "সুবিধার জন্য রেফার করুন",
        "select_facility": "কোন সুবিধায় রেফার করবেন?",
        "queue": "লাইভ রোগীর সারি",
        "no_referrals": "সারিতে এখনও কোনো রেফারেল নেই।",
        "prescription": "প্রেসক্রিপশন",
        "save_prescription": "প্রেসক্রিপশন সংরক্ষণ করুন এবং রেফারেল সম্পূর্ণ করুন",
        "teleconsult": "টেলিকনসালটেশন শুরু করুন (WebRTC)",
    },
}


def tr(key: str) -> str:
    lang = st.session_state.get("ui_lang", "en")
    return T.get(lang, T["en"]).get(key, key)


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS patients (
            abha_id TEXT PRIMARY KEY,
            name TEXT, age INTEGER, gender TEXT,
            village TEXT, phone TEXT, language TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS triage (
            id TEXT PRIMARY KEY,
            abha_id TEXT,
            symptoms_text TEXT,
            priority TEXT,
            rationale TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id TEXT PRIMARY KEY,
            abha_id TEXT,
            triage_id TEXT,
            facility TEXT,
            status TEXT,
            prescription TEXT,
            doctor_notes TEXT,
            created_at TEXT,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS medicine_stock (
            id TEXT PRIMARY KEY,
            facility TEXT,
            medicine_name TEXT,
            quantity INTEGER,
            unit TEXT,
            last_updated TEXT
        );
        """
    )
    conn.commit()

    # seed medicine stock once
    c.execute("SELECT COUNT(*) FROM medicine_stock")
    if c.fetchone()[0] == 0:
        seed_meds = [
            ("Paracetamol 500mg", "tablets", 40),
            ("ORS Sachets", "sachets", 5),
            ("Iron Folic Acid", "tablets", 120),
            ("Amoxicillin 250mg", "capsules", 8),
            ("Insulin (Regular)", "vials", 15),
            ("ASHA Kit - BP Monitor", "units", 3),
            ("Antenatal Vitamin D", "tablets", 60),
        ]
        for facility in FACILITIES:
            for med, unit, base_qty in seed_meds:
                qty = max(0, base_qty + random.randint(-10, 10))
                c.execute(
                    "INSERT INTO medicine_stock VALUES (?,?,?,?,?,?)",
                    (str(uuid.uuid4()), facility, med, qty, unit, datetime.now().isoformat()),
                )
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# AI TRIAGE ENGINE
# rule-based fallback (bilingual keyword matching) + optional Groq/Llama 3.1
# ---------------------------------------------------------------------------
RED_FLAGS = [
    "chest pain", "severe bleeding", "unconscious", "seizure", "not breathing",
    "difficulty breathing", "breathlessness", "convulsion", "high fever infant",
    "severe abdominal pain", "stroke", "paralysis", "blue lips",
    "सीने में दर्द", "बेहोश", "दौरा", "सांस लेने में तकलीफ", "तेज़ बुखार शिशु",
    "अत्यधिक रक्तस्राव", "लकवा",
]
YELLOW_FLAGS = [
    "fever", "vomiting", "diarrhea", "dehydration", "moderate pain",
    "pregnancy bleeding", "high blood pressure", "persistent cough",
    "बुखार", "उल्टी", "दस्त", "गर्भावस्था रक्तस्राव", "उच्च रक्तचाप", "लगातार खांसी",
]


def rule_based_triage(symptoms_text: str):
    text = symptoms_text.lower()
    for flag in RED_FLAGS:
        if flag in text:
            return "RED", f"Red-flag keyword detected: '{flag}'. Requires immediate escalation."
    for flag in YELLOW_FLAGS:
        if flag in text:
            return "YELLOW", f"Moderate-risk keyword detected: '{flag}'. Needs facility follow-up."
    return "GREEN", "No high-risk keywords detected. Routine care advised."


def groq_triage(symptoms_text: str):
    """Optional: real LLM triage via Groq + Llama 3.1. Falls back silently on any error."""
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        prompt = (
            "You are a clinical triage assistant for a rural Indian health worker (ASHA). "
            "Classify the patient's symptoms into exactly one of RED, YELLOW, GREEN "
            "(RED = emergency, refer immediately; YELLOW = needs PHC visit soon; "
            "GREEN = routine/self-care). Symptoms may be in Hindi or English. "
            "Reply strictly as: PRIORITY|one-sentence rationale.\n\n"
            f"Symptoms: {symptoms_text}"
        )
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.2,
        )
        out = resp.choices[0].message.content.strip()
        if "|" in out:
            priority, rationale = out.split("|", 1)
            priority = priority.strip().upper()
            if priority in PRIORITY_ORDER:
                return priority, rationale.strip()
    except Exception:
        return None
    return None


def run_triage(symptoms_text: str):
    result = groq_triage(symptoms_text)
    if result:
        return result
    return rule_based_triage(symptoms_text)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def gen_abha_id():
    return "ABHA-" + str(uuid.uuid4())[:8].upper()


def priority_badge(priority: str) -> str:
    color = PRIORITY_COLORS.get(priority, "#999")
    return f"<span style='background:{color};color:white;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.8em'>{priority}</span>"


def df(query, params=()):
    conn = get_conn()
    d = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return d


# ---------------------------------------------------------------------------
# UI: SIDEBAR
# ---------------------------------------------------------------------------
init_db()

if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"

with st.sidebar:
    st.markdown("## 🩺 SevaSetu")
    st.caption("SIH26133 · Govt. of Maharashtra")
    LANG_LABELS = {
        "en": "English",
        "hi": "हिंदी (Hindi)",
        "mr": "मराठी (Marathi)",
        "ta": "தமிழ் (Tamil)",
        "te": "తెలుగు (Telugu)",
        "bn": "বাংলা (Bengali)",
    }
    lang_choice = st.selectbox("Language / भाषा", list(LANG_LABELS.values()))
    st.session_state.ui_lang = next(code for code, label in LANG_LABELS.items() if label == lang_choice)

    page = st.radio(
        tr("role"),
        [tr("asha"), tr("doctor"), tr("admin"), tr("medicine")],
    )
    st.divider()
    st.caption(
        "🟢 AI mode: " + ("Groq Llama 3.1 (live)" if GROQ_API_KEY else "Rule-based fallback (no API key set)")
    )

st.title(tr("app_title"))

# ---------------------------------------------------------------------------
# PAGE: ASHA / ANM WORKER
# ---------------------------------------------------------------------------
if page == tr("asha"):
    tab1, tab2 = st.tabs(["📝 " + tr("register_patient"), "🤖 " + tr("run_triage") + " & Referral"])

    with tab1:
        with st.form("register_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input(tr("name"))
            age = c2.number_input(tr("age"), min_value=0, max_value=120, value=30)
            gender = c1.selectbox(tr("gender"), ["Female", "Male", "Other"])
            village = c2.text_input(tr("village"))
            phone = c1.text_input(tr("phone"))
            patient_lang = c2.selectbox(tr("language"), ["Marathi", "Hindi", "Tamil", "Telugu", "Bengali", "English"])
            submitted = st.form_submit_button(tr("register_btn"), type="primary")
            if submitted:
                if not name:
                    st.error("Name is required.")
                else:
                    abha_id = gen_abha_id()
                    conn = get_conn()
                    conn.execute(
                        "INSERT INTO patients VALUES (?,?,?,?,?,?,?,?)",
                        (abha_id, name, age, gender, village, phone, patient_lang, datetime.now().isoformat()),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Patient registered! ABHA-linked ID: **{abha_id}**")
                    st.balloons()

        st.divider()
        st.subheader("Registered Patients")
        patients_df = df("SELECT abha_id, name, age, gender, village, language FROM patients ORDER BY created_at DESC")
        st.dataframe(patients_df, use_container_width=True, hide_index=True)

    with tab2:
        patients_df = df("SELECT abha_id, name FROM patients ORDER BY created_at DESC")
        if patients_df.empty:
            st.info("Register a patient first in the previous tab.")
        else:
            options = {f"{r['name']} ({r['abha_id']})": r["abha_id"] for _, r in patients_df.iterrows()}
            selected = st.selectbox("Select Patient", list(options.keys()))
            abha_id = options[selected]

            symptoms = st.text_area(
                tr("symptoms"),
                placeholder="e.g. High fever for 3 days with breathlessness / बुखार और सांस लेने में तकलीफ",
                height=100,
            )
            worker_name = st.text_input("Your name (ASHA/ANM)", value="ASHA Worker")

            if st.button("🤖 " + tr("run_triage"), type="primary"):
                if not symptoms:
                    st.warning("Please enter symptoms.")
                else:
                    with st.spinner("Running AI triage..."):
                        priority, rationale = run_triage(symptoms)
                    triage_id = str(uuid.uuid4())
                    conn = get_conn()
                    conn.execute(
                        "INSERT INTO triage VALUES (?,?,?,?,?,?,?)",
                        (triage_id, abha_id, symptoms, priority, rationale, worker_name, datetime.now().isoformat()),
                    )
                    conn.commit()
                    conn.close()
                    st.session_state["last_triage_id"] = triage_id
                    st.session_state["last_triage_priority"] = priority
                    st.markdown(f"### {tr('priority')}: {priority_badge(priority)}", unsafe_allow_html=True)
                    st.write(rationale)

            last_triage_id = st.session_state.get("last_triage_id")
            if last_triage_id:
                st.divider()
                priority = st.session_state.get("last_triage_priority", "GREEN")
                if priority in ("RED", "YELLOW"):
                    st.warning("⚠️ This patient needs facility follow-up.")
                    facility = st.selectbox(tr("select_facility"), FACILITIES)
                    if st.button("🚑 " + tr("refer_btn"), type="primary"):
                        ref_id = str(uuid.uuid4())
                        conn = get_conn()
                        conn.execute(
                            "INSERT INTO referrals VALUES (?,?,?,?,?,?,?,?,?)",
                            (ref_id, abha_id, last_triage_id, facility, "PENDING", "", "", datetime.now().isoformat(), None),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Referral sent to {facility}. Full record attached.")
                        del st.session_state["last_triage_id"]
                else:
                    st.info("GREEN priority — routine care, no referral needed.")

# ---------------------------------------------------------------------------
# PAGE: DOCTOR / FACILITY DASHBOARD
# ---------------------------------------------------------------------------
elif page == tr("doctor"):
    facility = st.selectbox("Facility", FACILITIES)

    q = """
    SELECT r.id as ref_id, p.abha_id, p.name, p.age, p.gender, p.village,
           t.symptoms_text, t.priority, t.rationale, t.created_by, r.status, r.created_at
    FROM referrals r
    JOIN patients p ON p.abha_id = r.abha_id
    JOIN triage t ON t.id = r.triage_id
    WHERE r.facility = ? AND r.status != 'COMPLETED'
    """
    queue = df(q, (facility,))

    st.subheader(f"📋 {tr('queue')} — {facility}")
    if queue.empty:
        st.info(tr("no_referrals"))
    else:
        queue["sort"] = queue["priority"].map(PRIORITY_ORDER)
        queue = queue.sort_values("sort")
        for _, row in queue.iterrows():
            with st.expander(f"{row['name']} · {row['age']}y {row['gender']} · {row['priority']}", expanded=False):
                st.markdown(priority_badge(row["priority"]), unsafe_allow_html=True)
                st.write(f"**ABHA ID:** {row['abha_id']}  |  **Village:** {row['village']}")
                st.write(f"**Symptoms (from ASHA {row['created_by']}):** {row['symptoms_text']}")
                st.caption(f"AI rationale: {row['rationale']}")

                colA, colB = st.columns(2)
                with colA:
                    if st.button("📹 " + tr("teleconsult"), key=f"tc_{row['ref_id']}"):
                        st.info("🔴 Live WebRTC teleconsultation would launch here (Daily.co room).")
                with colB:
                    st.write(f"Status: `{row['status']}`")

                prescription = st.text_area(tr("prescription"), key=f"presc_{row['ref_id']}")
                notes = st.text_input("Doctor notes", key=f"notes_{row['ref_id']}")
                if st.button(tr("save_prescription"), key=f"save_{row['ref_id']}", type="primary"):
                    conn = get_conn()
                    conn.execute(
                        "UPDATE referrals SET status='COMPLETED', prescription=?, doctor_notes=?, completed_at=? WHERE id=?",
                        (prescription, notes, datetime.now().isoformat(), row["ref_id"]),
                    )
                    conn.commit()
                    conn.close()
                    st.success("Referral completed & prescription saved. Patient record updated.")
                    st.rerun()

    st.divider()
    st.subheader("Completed Referrals (History)")
    hist = df(
        """SELECT p.name, t.priority, r.prescription, r.completed_at
           FROM referrals r JOIN patients p ON p.abha_id=r.abha_id
           JOIN triage t ON t.id=r.triage_id
           WHERE r.facility=? AND r.status='COMPLETED' ORDER BY r.completed_at DESC""",
        (facility,),
    )
    st.dataframe(hist, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# PAGE: DISTRICT ADMIN DASHBOARD
# ---------------------------------------------------------------------------
elif page == tr("admin"):
    total_patients = df("SELECT COUNT(*) as n FROM patients")["n"][0]
    total_triage = df("SELECT COUNT(*) as n FROM triage")["n"][0]
    total_referrals = df("SELECT COUNT(*) as n FROM referrals")["n"][0]
    completed = df("SELECT COUNT(*) as n FROM referrals WHERE status='COMPLETED'")["n"][0]
    completion_rate = (completed / total_referrals * 100) if total_referrals else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered Patients", total_patients)
    c2.metric("Triage Runs", total_triage)
    c3.metric("Referrals", total_referrals)
    c4.metric("Referral Completion Rate", f"{completion_rate:.0f}%")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Triage Priority Breakdown")
        pr = df("SELECT priority, COUNT(*) as n FROM triage GROUP BY priority")
        if not pr.empty:
            st.bar_chart(pr.set_index("priority"))
        else:
            st.info("No triage data yet.")

    with col2:
        st.subheader("Referrals by Facility")
        rf = df("SELECT facility, COUNT(*) as n FROM referrals GROUP BY facility")
        if not rf.empty:
            st.bar_chart(rf.set_index("facility"))
        else:
            st.info("No referral data yet.")

    st.divider()
    st.subheader("🚨 Disease / Symptom Outbreak Signal (last entries)")
    recent = df("SELECT symptoms_text, priority, created_at FROM triage ORDER BY created_at DESC LIMIT 15")
    st.dataframe(recent, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("💊 Low Medicine Stock Alerts (below 10 units)")
    low_stock = df("SELECT facility, medicine_name, quantity, unit FROM medicine_stock WHERE quantity < 10 ORDER BY quantity ASC")
    if low_stock.empty:
        st.success("No low-stock alerts.")
    else:
        st.dataframe(low_stock, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# PAGE: MEDICINE STOCK CHECKER
# ---------------------------------------------------------------------------
elif page == tr("medicine"):
    st.subheader("💊 " + tr("medicine"))
    facility = st.selectbox("Facility", ["All"] + FACILITIES)
    search = st.text_input("Search medicine name")

    query = "SELECT facility, medicine_name, quantity, unit, last_updated FROM medicine_stock WHERE 1=1"
    params = []
    if facility != "All":
        query += " AND facility = ?"
        params.append(facility)
    if search:
        query += " AND medicine_name LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY facility, medicine_name"

    stock_df = df(query, tuple(params))

    def highlight_low(row):
        if row["quantity"] < 10:
            return ["background-color:#ffcdd2;color:black" for _ in row]
        return ["color:white" for _ in row]

    if stock_df.empty:
        st.info("No matching medicine records.")
    else:
        st.dataframe(stock_df.style.apply(highlight_low, axis=1), use_container_width=True, hide_index=True)
        st.caption("🔴 Highlighted rows = low stock (below 10 units) — flagged for supply chain restock.")

    st.divider()
    st.subheader("📦 Restock / Update Inventory")
    update_tab, add_tab = st.tabs(["Update existing stock", "Add new medicine"])

    with update_tab:
        all_meds = df("SELECT id, facility, medicine_name, quantity, unit FROM medicine_stock ORDER BY facility, medicine_name")
        if all_meds.empty:
            st.info("No medicines in inventory yet — add one in the next tab.")
        else:
            labels = {
                f"{r['medicine_name']} — {r['facility']} (current: {r['quantity']} {r['unit']})": r["id"]
                for _, r in all_meds.iterrows()
            }
            chosen_label = st.selectbox("Select medicine", list(labels.keys()))
            chosen_id = labels[chosen_label]

            mode = st.radio("Action", ["Add stock (restock delivery)", "Remove stock (dispensed/damaged)", "Set exact quantity"], horizontal=False)
            amount = st.number_input("Amount", min_value=0, value=10, step=1)

            if st.button("✅ Apply Update", type="primary"):
                conn = get_conn()
                cur_qty = conn.execute("SELECT quantity FROM medicine_stock WHERE id=?", (chosen_id,)).fetchone()[0]
                if mode.startswith("Add"):
                    new_qty = cur_qty + amount
                elif mode.startswith("Remove"):
                    new_qty = max(0, cur_qty - amount)
                else:
                    new_qty = amount
                conn.execute(
                    "UPDATE medicine_stock SET quantity=?, last_updated=? WHERE id=?",
                    (new_qty, datetime.now().isoformat(), chosen_id),
                )
                conn.commit()
                conn.close()
                st.success(f"Updated — new quantity: {new_qty}")
                st.rerun()

    with add_tab:
        with st.form("add_medicine_form"):
            new_facility = st.selectbox("Facility", FACILITIES, key="new_med_facility")
            new_name = st.text_input("Medicine name")
            new_qty = st.number_input("Starting quantity", min_value=0, value=50, step=1)
            new_unit = st.selectbox("Unit", ["tablets", "capsules", "vials", "sachets", "units", "bottles"])
            add_submitted = st.form_submit_button("➕ Add Medicine", type="primary")
            if add_submitted:
                if not new_name:
                    st.error("Medicine name is required.")
                else:
                    conn = get_conn()
                    conn.execute(
                        "INSERT INTO medicine_stock VALUES (?,?,?,?,?,?)",
                        (str(uuid.uuid4()), new_facility, new_name, new_qty, new_unit, datetime.now().isoformat()),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Added {new_name} ({new_qty} {new_unit}) to {new_facility}.")
                    st.rerun()