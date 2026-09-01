# SevaSetu — SIH26133 Prototype (Streamlit)

Bridge to Healthcare — a rural/underserved public healthcare access platform.
This is the **hackathon demo prototype**: one Streamlit app simulating all three
user roles (ASHA worker, Doctor, District Admin) plus the AI triage engine and
medicine stock checker.

## Getting the code (for teammates)

If you're new to Git/GitHub, follow these exactly — one time setup only.

### 1. Install prerequisites (skip if already installed)
- **Git** — https://git-scm.com/downloads (just click through the installer with defaults)
- **Python 3.10+** — https://www.python.org/downloads/ (on Windows, tick **"Add Python to PATH"** during install)

Check both worked by opening a terminal (Command Prompt / PowerShell / Terminal) and running:
```bash
git --version
python --version
```
Both should print a version number, not an error.

### 2. Clone the repo
Pick a folder on your computer where you want the project, open a terminal there, and run:
```bash
git clone https://github.com/MAYANK-108/sevasetu.git
cd sevasetu
```
This downloads the whole project into a new `sevasetu` folder and moves you into it.

### 3. Create a virtual environment (keeps dependencies isolated)
```bash
python -m venv venv
```
Activate it:
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **Windows (Command Prompt):** `venv\Scripts\activate.bat`
- **Mac/Linux:** `source venv/bin/activate`

You'll know it worked because your terminal prompt now starts with `(venv)`.

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the app
```bash
streamlit run app.py
```
It should auto-open in your browser at `http://localhost:8501`. If not, copy that URL from the terminal into your browser manually.

### Getting future updates
Whenever someone pushes new changes to GitHub, get them with:
```bash
git pull
```
(Run this from inside the `sevasetu` folder, with your virtual environment activated.)

### If something goes wrong
- **`git` or `python` not recognized** → it's not installed or not added to PATH; reinstall and check the box for adding to PATH.
- **`pip install` fails** → make sure your virtual environment is activated (prompt shows `(venv)`), then try again.
- **Port already in use** → close other Streamlit tabs/terminals, or run `streamlit run app.py --server.port 8502`.

## Quick start (if you already have the repo cloned)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

### Optional: real AI triage (Groq + Llama 3.1)
By default the app uses a bilingual (Hindi/English) rule-based triage engine so
it works fully offline with zero setup — good for a flaky demo-hall wifi.
To use the real Groq-hosted Llama 3.1 model instead:

```bash
export GROQ_API_KEY=your_key_here     # Windows: set GROQ_API_KEY=your_key_here
streamlit run app.py
```

The sidebar shows which mode is active.

## Demo script (matches the PS end-to-end flow)

1. **ASHA/ANM Worker** tab → Register New Patient → note the generated ABHA-linked ID.
2. Switch to **Run AI Triage & Referral** tab → select the patient → type symptoms
   (try `"chest pain and breathlessness"` for RED, `"fever and vomiting"` for YELLOW,
   or Hindi text like `"सीने में दर्द"`).
3. If priority is RED/YELLOW, pick a facility and click **Refer to Facility**.
4. Switch role to **Doctor / Facility Dashboard**, pick the same facility →
   the patient appears in the live queue, sorted by priority. Expand the card,
   click **Start Teleconsultation**, write a prescription, and **Save & Complete Referral**.
5. Switch role to **District Admin Dashboard** → see live metrics update: patient
   count, triage breakdown, referral completion rate, and low medicine-stock alerts.
6. Switch role to **Medicine Stock Checker** → search/filter inventory across facilities.

## What's implemented (MVP scope)
- Patient registration with auto-generated ABHA-linked ID
- Bilingual (Hindi/English) AI triage: RED/YELLOW/GREEN, with optional live
  Groq + Llama 3.1 classification and an offline rule-based fallback
- One-tap referral with full record attached (symptoms + rationale + ASHA name)
- Doctor queue sorted by priority, teleconsult placeholder, prescription capture
- Referral completion tracking end-to-end
- District admin analytics: triage breakdown, referrals by facility, completion
  rate, recent-symptom outbreak signal, low-stock alerts
- Medicine stock checker with search + low-stock highlighting
- Data persists locally in `sevasetu.db` (SQLite) so the demo survives page reloads

## What's stubbed for the demo (call out in Q&A if judges ask)
- Teleconsultation is a placeholder button — production version wires up
  WebRTC/Daily.co as per the architecture doc
- ABHA integration is simulated with a locally generated ID (real ABDM/FHIR
  sandbox integration is the next build step)
- SMS/WhatsApp follow-up reminders and Flutter mobile apps are separate
  workstreams not included in this Streamlit prototype
- Multilingual UI currently covers English + Hindi; Marathi strings can be
  added to the `T` dict in `app.py` the same way

## Files
- `app.py` — the full prototype (single file, ~4 pages/roles)
- `requirements.txt` — dependencies
- `sevasetu.db` — auto-created SQLite database on first run (safe to delete to reset demo data)
