# 🩺 ArogyaBridge — Bridge to Healthcare

> **Smart India Hackathon 2026 | PS ID: SIH26133**  
> *Accessibility and quality of public healthcare services, particularly in rural and underserved areas*  
> **Organization:** Government of Maharashtra — Maharashtra State Innovation Society  
> **Category:** Software · Theme: MedTech / BioTech / HealthTech

---

## What is ArogyaBridge?

ArogyaBridge is an integrated rural healthcare access platform that digitises the full patient journey — from ASHA worker field registration through AI triage, facility referral, doctor consultation, diagnostic coordination, and district-level quality monitoring — in a single, multilingual, low-bandwidth-aware application.

It is built as a working prototype for SIH 2026, demonstrating the viability of a production system that can be deployed across Maharashtra's Sub-Centres, PHCs, and Rural/District Hospitals.

---

## Screenshots

> Run the app locally and log in to each role to explore. All five dashboards are accessible from the sidebar.

---

## Key Features

### Patient Portal
- Self-registration with Aadhaar-linked ABHA ID generation
- Self-symptom triage in 6 languages (English, Hindi, Marathi, Tamil, Telugu, Bengali)
- Appointment booking at any registered facility
- Full personal health record — triage history, referrals, prescriptions, diagnostics, MCH, chronic care plans
- ABDM-lite interoperable health record export (FHIR R4 bundle structure, JSON)
- **Emergency SOS** with 5-second cancel window, geographic routing, and medical history package
- **Guest SOS** — no login required, for bystander emergencies

### ASHA / ANM Worker Portal
- Patient registration with Aadhaar hashing (SHA-256, never stored in plaintext)
- AI triage with vitals entry (Temp, SpO₂, Pulse) and abnormal-value warnings
- Referral creation routed by `facility_id` (not just name) — no duplicate-facility confusion
- High-risk follow-up worklist (overdue flagging)
- Chronic care registry with recurring follow-up intervals
- Maternal & Child Health: Pregnancy/ANC tracker + auto-generated Government of India immunization schedule

### Doctor Dashboard
- Priority-sorted referral queue (RED → YELLOW → GREEN) with SLA breach indicators
- Full patient history visible on every referral card
- **Live Jitsi Meet teleconsultation** — no backend, no account, patient joins via link
- Diagnostic test ordering and result recording
- Prescription + chronic condition flagging
- Appointment management (accept / decline with reason)
- Facility escalation / re-referral to higher facility

### Facility / Hospital Portal
- Self-registration — creates facility account and seeds default medicine stock + diagnostic catalog
- Staff management — issues ASHA and Doctor login credentials
- Medicine stock with **consumption-velocity-based stockout prediction** (not a static threshold)
- Diagnostic test catalog (availability + turnaround time)
- Full stock change log with audit trail

### District Admin Dashboard
- Password-protected (env var `ADMIN_PASSWORD`)
- Live SOS alert monitoring with one-click resolve
- System-wide metrics: patients, triages, referral completion rate, follow-ups, SLA breaches
- **Referral funnel** (Pending → Acknowledged → Completed → Escalated)
- **Outbreak signal detection** — 7-day keyword clustering by village (3+ cases = alert)
- Area/village-wise case heat map
- SLA breach review workflow — admin can acknowledge and close breaches
- Low-stock alerts across all facilities
- Patient record search with filters (priority, department, facility, symptom keyword)

### Cross-cutting
- **6-language UI** — full string localisation for all roles
- **SMS fallback** via Fast2SMS for RED/YELLOW triage results (works when app is offline for the patient)
- **Browser TTS** (Web Speech API) for low-literacy users — reads triage results aloud in the patient's language
- **Geographic SOS routing** — notifies staff from the patient's village first, falls back to all staff
- **Aadhaar hashing** — SHA-256 with per-app salt; raw Aadhaar never persists in the database
- **SLA monitoring** — RED within 2h, YELLOW within 24h, GREEN within 72h
- **Patient feedback** loop — star rating after completed referrals feeds quality dashboard

---

## Tech Stack (Prototype)

| Layer | Technology |
|---|---|
| Frontend / App | Python 3.11 + Streamlit |
| AI Triage | Groq API — Llama 3.1 8B Instant (with rule-based fallback) |
| Video Consult | Jitsi Meet (embedded, free, no backend) |
| SMS Fallback | Fast2SMS REST API |
| Database | SQLite (prototype) |
| Charts | Altair + Streamlit native bar charts |
| Auth | PBKDF2-HMAC-SHA256 (passwords) + SHA-256 (Aadhaar) |
| Health Records | ABDM-lite FHIR R4 JSON export |
| TTS | Browser Web Speech API |
| Auto-refresh | `streamlit-autorefresh` (SOS countdown) |

---

## Production Tech Stack (Roadmap)

| Layer | Technology | Reason |
|---|---|---|
| Mobile App | Flutter (Android + iOS) | Offline-first, low-bandwidth, works on ₹5,000 phones |
| PWA / Web | Next.js 14 | Progressive Web App with service worker for offline ASHA use |
| Backend API | FastAPI (Python) | Async, type-safe, same ML ecosystem |
| Database | PostgreSQL 16 + PostGIS | Concurrent writes, geographic queries, ACID |
| Cache / Queue | Redis + Celery | Async SMS dispatch, notification fanout |
| AI Triage | Fine-tuned Llama 3.1 (on NIC cloud) or Groq API | Regional language accuracy, data sovereignty |
| Video Consult | Jitsi Meet self-hosted or 100ms.live | Government data residency requirement |
| SMS Gateway | BSNL Bulk SMS / MSG91 | Government-approved, India-wide reach |
| Auth | ABDM ABHA API + UIDAI OTP e-KYC | Real Aadhaar verification, ABHA ID generation |
| Health Records | ABDM HIU/HIP registered FHIR R4 | Full interoperability with national health stack |
| Deployment | NIC Cloud / AWS Mumbai (ap-south-1) | Data residency within India |
| CI/CD | GitHub Actions + Docker | Reproducible builds |
| Monitoring | Prometheus + Grafana | SLA breach alerting, system health |

---

## Project Structure

```
arogyabridge/
├── app.py                  # Main Streamlit application (single-file prototype)
├── sevasetu.db             # SQLite database (auto-created on first run, gitignored)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── README.md               # This file
```

---

## Setup & Installation

### Prerequisites
- Python 3.10 or higher
- pip

### 1. Clone the repository

```bash
git clone https://github.com/your-username/arogyabridge.git
cd arogyabridge
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required for AI triage (get free key at console.groq.com)
GROQ_API_KEY=your_groq_api_key_here

# Required for SMS fallback (get free key at fast2sms.com)
FAST2SMS_KEY=your_fast2sms_key_here

# Admin dashboard password (change this before any public demo)
ADMIN_PASSWORD=your_secure_password_here

# Aadhaar hashing salt — change this in production, store in KMS
AADHAAR_SALT=your_random_salt_string_here
```

> **Note:** The app runs fully without `GROQ_API_KEY` and `FAST2SMS_KEY` — it falls back to rule-based triage and skips SMS silently. The admin dashboard uses the default password `admin@sih2026` if `ADMIN_PASSWORD` is not set.

### 4. Run the application

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## First-Time Demo Walkthrough

Follow this sequence to see the full patient journey end-to-end:

1. **Register a Facility** → Sidebar: *Facility / Hospital* → Register tab  
   Use name `PHC Ranjangaon`, type `PHC`, village `Ranjangaon`, set a password.

2. **Create Staff** → Log in as facility → Staff Management  
   Add one ASHA worker and one Doctor. Note the generated Worker IDs and passwords.

3. **Register a Patient** → Sidebar: *ASHA / ANM Worker* → Log in with ASHA credentials  
   Tab 1: Register a patient with a 12-digit test Aadhaar (e.g. `123456789012`).

4. **Run Triage** → ASHA portal → Tab 2: Triage & Referral  
   Select the patient, enter symptoms like `chest pain and difficulty breathing`, click *Run AI Triage*.  
   Priority should return **RED**. Refer to `PHC Ranjangaon`.

5. **Handle Referral** → Sidebar: *Doctor Dashboard* → Log in with Doctor credentials  
   Tab 1: Queue — acknowledge arrival, start teleconsultation, order a diagnostic test, write prescription.

6. **View Admin Dashboard** → Sidebar: *District Admin Dashboard* → Enter admin password  
   See the referral funnel, outbreak signals panel, SLA monitoring, and low-stock alerts.

7. **Patient Self-Triage** → Sidebar: *Patient Portal* → Log in with Aadhaar + password  
   Use Self Triage with Hindi/Marathi symptoms. Check that TTS (🔊 Listen) works.

8. **Guest SOS** → Patient Portal before login → Expand the red Emergency SOS panel  
   Fill optional name/symptoms, trigger SOS, confirm. All doctors and ASHA workers receive alerts.

---

## Requirements (`requirements.txt`)

```
streamlit>=1.35.0
streamlit-autorefresh>=0.0.1
pandas>=2.0.0
altair>=5.0.0
groq>=0.9.0
requests>=2.31.0
```

---

## Security Notes (Prototype vs Production)

| Concern | Prototype Approach | Production Plan |
|---|---|---|
| Aadhaar storage | SHA-256 hash with env-var salt | KMS-managed key, UIDAI OTP e-KYC |
| Passwords | PBKDF2-HMAC-SHA256, 100k iterations | Same, with session expiry + rate limiting |
| Admin auth | Env-var password | NIC LDAP / Maharashtra SSO |
| Database | SQLite file | PostgreSQL with row-level encryption for PII |
| Transport | HTTP (local) | TLS 1.3 enforced |
| ABHA IDs | UUID-based demo IDs | Real ABHA API from ABDM registry |
| Session | Streamlit session state | JWT tokens with expiry |

---

## Compliance References

- **ABDM** — Ayushman Bharat Digital Mission health data standards
- **FHIR R4** — HL7 FHIR R4 bundle structure (ABDM HIU/HIP ready)
- **PM-JAY** — Pradhan Mantri Jan Arogya Yojana eligibility flag per patient
- **UIP** — Government of India Universal Immunization Programme schedule
- **DOTS** — Directly Observed Treatment, Short-course (TB protocol)
- **IT Act 2000 + DPDP Act 2023** — Data minimization, purpose limitation, Aadhaar hashing

---

## Team

| Name | Role |
|---|---|
| *Your Name* | Team Lead / Full Stack |
| *Member 2* | AI / ML |
| *Member 3* | UI/UX |
| *Member 4* | Backend / Database |
| *Member 5* | Research / Documentation |
| *Member 6* | Testing / Deployment |

> **Institution:** *Your College Name*, *City*

---

## License

This project is built for Smart India Hackathon 2026 and is not licensed for commercial use. All rights reserved by the team and the participating institution.

---

## Acknowledgements

- **Ministry of Education's Innovation Cell (MIC)** and **AICTE** for the SIH platform
- **Maharashtra State Innovation Society** and the **Department of Skills, Employment, Entrepreneurship and Innovation** for PS 26133
- **ABDM / NHA** for publicly available FHIR and ABHA API documentation
- **Groq** for free-tier LLM inference
- **Jitsi Meet** for open-source video conferencing infrastructure
