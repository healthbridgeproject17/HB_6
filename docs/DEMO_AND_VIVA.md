# HealthBridge: demo script and viva answers

All data is FICTIONAL. Demo password for every demo account: `Demo@12345`. Demo emails end in `@demo.healthbridge.test`.

## Before the demo (10 minutes, do it the evening before)
```powershell
cd D:\HB_6\module1_health_records\backend
.\.venv\Scripts\flask.exe --app run db upgrade
.\.venv\Scripts\flask.exe --app run seed-demo --reset      # fresh demo patients, records, documents
.\.venv\Scripts\flask.exe --app run seed-security          # 3 simulated machines
.\.venv\Scripts\flask.exe --app run run                    # terminal 1: backend
cd ..\frontend ; npm run dev -- --host                     # terminal 2: website, open http://localhost:5173
```
- Log in once as each of the 3 roles to check it works. Keep the files from `demo_documents\` open in a folder.
- Closing the laptop lid or switching Wi-Fi can break the database connection; reload the page if the site says it cannot reach the server.
- Change the admin password if it was ever typed in a chat (`reset-admin-password` after editing `.env`).

## The 12-minute route
**1. Patient (2 min).** Log in as `rahul.menon`. Show the profile and Health ID, the medication tracker (last taken comes only from the log), and the amended record: the original is kept, the correction is a new linked version with a reason.

**2. Document analysis (5 min).** Log in as Dr. Meera Iyer (`meera.iyer`), open Meena Rajan, Documents.
- Try uploading `extras\fake_report.pdf` and `extras\notes.txt`: both refused because the content, not the name, is checked.
- Press **Analyse** on `meena_kidney_panel_critical_scan`. The review screen shows the document beside the values; flagged values are highlighted.
- Point at potassium 6.4: the report says Urgent, and why. Correct one value and show the urgency recalculate.
- Confirm. Show that a prescription confirmed by a patient is only a draft, and that Dr. Iyer's confirmation makes it active.
- Say: "The system never changes a medicine or dose. Anything read by the AI stays unconfirmed until a person confirms it."
- Optional: analyse `extras\blurry_low_quality_report.jpg` to show the quality warnings.

**3. Admin and audit (1 min).** Log in as admin. Show that an admin can manage accounts but has no button to write clinical data. Open the Audit log and filter by action.

**4. Security monitor (4 min).** Follow `docs\MODULE3_MONITOR.md`: "Show normal activity" on one computer, "Show a ransomware attack" on another, read "What stood out" and "How the risk level was reached", Acknowledge, Isolate (simulated), Close, then show the audit entries and read the model card caveats aloud.

## Viva answers

### Project and process
- **What did you build?** Three modules: digital health records, AI analysis of medical documents with human review, and a simulated ransomware-behaviour monitor.
- **What is yours and what is a library?** The rules, workflow, review screen, security design and simulator are written for this project. Flask, React, PyMuPDF, OpenCV, RapidOCR and scikit-learn are libraries. AI tools were used while building, and every result was tested.

### Module 1
- **How do you stop patients seeing each other's data?** The backend checks the role and the owner on every request, reading the role from the database, not the token. Other patients' ids return 403.
- **Why can doctors see all patients?** That was the specification. It is a stated limit: a care-team or "break-glass" model would be stricter, and every doctor access is audited.
- **Can records be edited?** Corrections are new linked versions with a required reason; originals are never overwritten.
- **How are files protected?** Encrypted on disk (Fernet/AES), served only through permission-checked routes, verified by content, renamed randomly. If the key is lost the files cannot be opened.
- **How can the audit log not be tampered with?** On PostgreSQL a trigger blocks any UPDATE or DELETE on it.
- **How are passwords and sessions handled?** bcrypt hashes, 2-hour tokens, lock after 5 wrong passwords for 15 minutes, and logout or password change ends every session.

### Module 2
- **Why RapidOCR?** It installs with a plain `pip install` on Windows and read the demo scans better than Tesseract in my comparison.
- **How accurate is it?** On clean synthetic demo documents: digital PDFs 40 of 40 rows, scans and phone photos 29 of 29. On harder pictures it drops (half resolution 72%, shadow and blur 83%, heavy compression 93%, 4-degree tilt 97%). The demo files are clean and I tuned on them, so real hospital photos will do worse.
- **What is an example of OCR being wrong?** An orange bold "9.8" was read as "86" with 99% confidence because a contrast step erased the decimal point. I removed the step and added a test. This is why every number is read twice, checked against its range, and shown for human review.
- **Why a rules engine and not AI advice?** Fixed, reviewable rules (`docs\CLINICAL_RULES.md`) decide the visit level, so the result is explainable and cannot invent advice. A doctor must still review those rules before real use.
- **Does it give medicine advice?** No. It never suggests or changes a medicine or a dose.

### Module 3
- **Is this real ransomware detection?** No. It demonstrates a method on synthetic telemetry. The model card says so, and the website shows the same caveat.
- **What was the shortcut and how did you find it?** Early simulated attacks contained a constant value, so every result was 100%. Feature importance showed that one feature dominated. I fixed the simulator and added a regression test.
- **How good is it on attacks it has not seen?** Seen families are caught well. A never-seen slow family that sleeps between bursts is caught in only about 78% of runs and late (median 85 seconds). False alarms are about 0.08 per machine-hour, measured over only about 25 hours, so that number is uncertain.
- **Why 2 of 3 windows?** One noisy window should not raise an alarm. The cost is a few seconds of delay.
- **How is the risk level decided?** Three points that add up: model confidence, how many different kinds of suspicious behaviour are visible, and how long it has lasted. The incident screen shows the three parts.
- **Why is isolation simulated?** Wrongly cutting off a clinical machine is itself harmful, so a person decides. The system records and recommends; it never touches a real machine or network.
- **What would real deployment need?** Real telemetry from the machines (file-system and network events), training on real benign and attack data, split by machine, far more benign hours, and HTTPS with a proper agent.

## Honest limits to say out loud
- Synthetic data in Module 3; clean synthetic documents in Module 2.
- Clinical rules and patient advice texts are drafts until a doctor reviews them.
- No email verification, password reset by email or two-factor login.
- The login token is kept in the browser's sessionStorage; a cookie-based session would resist script injection better.
- One analysis runs at a time inside the web server; a queue worker is the next step for deployment.
- Deployment (HTTPS, private storage, backups) is not done.
