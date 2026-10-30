# HealthBridge demo data (all FICTIONAL)

Load it:  `flask --app run seed-demo`   (add `--reset` to wipe and recreate the demo patients' data)
Password for every demo account: **Demo@12345**   (change with `--password` or `DEMO_PASSWORD`)
Demo emails end in `@demo.healthbridge.test` (a reserved domain that can never be a real address).

## Doctors
| Email | Name | Specialty |
|---|---|---|
| meera.iyer@demo.healthbridge.test | Dr. Meera Iyer | General Medicine |
| arjun.nair@demo.healthbridge.test | Dr. Arjun Nair | Internal Medicine |

## Patients and what each one demonstrates
| Email (before @) | Patient | Story | Documents | Medication tracker |
|---|---|---|---|---|
| ananya.krishnan | Ananya Krishnan, F, 31 | Iron-deficiency anaemia (low Hb, low ferritin) | CBC + iron report: PDF and scanner image | Iron tablet, mixed adherence |
| rahul.menon | Rahul Menon, M, 48 | Diabetes + hypertension + high lipids; **amended record** with history; one **discontinued** prescription | Diabetes/lipid panel PDF; prescription PDF; prescription **phone photo** | Metformin, Amlodipine (good), Atorvastatin (mixed) |
| fatima.sheikh | Fatima Sheikh, F, 60 | Hypothyroid + high cholesterol | Lipid/thyroid report scan; prescription scan | Levothyroxine (good), Atorvastatin (poor) |
| karthik.subramanian | Karthik Subramanian, M, 36 | Healthy check-up, all normal | Health check-up PDF | none |
| meena.rajan | Meena Rajan, F, 75 | **Urgent case**: advanced kidney disease, potassium 6.4 (critical); **draft prescriptions** waiting for a doctor to confirm | Kidney panel PDF + scan; prescription phone photo | none yet (drafts) |
| arun.das | Arun Das, M, 25 | Brand-new patient: empty states | none | none |

Profile photos (generated avatars) for Ananya, Rahul, Meena; the others show the initials avatar.

## Files in `demo_documents/`
Digital PDFs, scanner-style images (skew, noise, grey tint) and phone-photo-style images (perspective, shadow, colour cast).
The loader attaches 12 of them to the patients above; `manifest.json` lists which.

`demo_documents/extras/` (NOT loaded; use them to test the upload checks and, later, OCR uncertainty):
- `fake_report.pdf`: plain text renamed to .pdf, must be rejected
- `notes.txt`: wrong file type, must be rejected
- `blurry_low_quality_report.jpg`: poor scan, should later be flagged as low confidence

Regenerate documents: `python tools/make_demo_documents.py` (needs reportlab, pymupdf, pillow, numpy).

## Values used in the lab reports (for Module 2 testing)
Ananya Hb 9.8 g/dL (low), ferritin 8 (low). Rahul HbA1c 8.9 %, fasting glucose 168, LDL 152 (high).
Fatima TSH 9.8, free T4 0.7, LDL 172. Karthik everything normal.
Meena creatinine 3.4, eGFR 14, **potassium 6.4 (critical)**, sodium 132, Hb 9.1.

Handwritten prescriptions are not included (they cannot be generated honestly); add real handwritten samples later to test OCR limits.
