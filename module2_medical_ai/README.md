# Module 2: Medical document analysis (built phase by phase)

Phase 2.1/2.2 (this folder): read text from PDFs and scanned/photographed documents.

    .\.venv\Scripts\python.exe -m medai ..\demo_documents\rahul_prescription_photo.jpg     # print what was read
    .\.venv\Scripts\python.exe -m medai FILE --json                                      # full result
    .\.venv\Scripts\python.exe evaluate.py                                               # accuracy on the demo set
    .\.venv\Scripts\python.exe evaluate.py --stress                                      # accuracy on worse pictures

Digital PDFs are read exactly. Scans and photos are straightened, enlarged and read with OCR (RapidOCR;
Tesseract is used only if you pick it and have it installed). Every page reports how it was read,
its confidence and picture-quality problems, so later phases can flag uncertain values.

## Phase 2.3: structured results with safety checks

    .\.venv\Scripts\python.exe -m medai FILE --analyze          # lab values or prescription fields, with REVIEW marks
    .\.venv\Scripts\python.exe -m medai FILE --analyze --json   # full structured result
    .\.venv\Scripts\python.exe evaluate_parse.py                # accuracy + "silent errors" on the demo set
    .\.venv\Scripts\python.exe evaluate_parse.py --stress       # same on worse pictures

Checks that catch reading mistakes: second reading of every number from an enlarged crop; the report's own
flag (H/L) against its own range; physically plausible limits per test; unit checks; confidence limits;
duplicate tests; unknown names listed (never dropped); medicine names checked against a list (suggestion only,
never auto-corrected); missing prescription fields shown as "not detected" (never guessed).
Everything is returned as status "unconfirmed" / "draft": a person must confirm it.

## Phase 2.4: clinical rules and the doctor-visit level

    .\.venv\Scripts\python.exe -m medai FILE --analyze     # now ends with an ASSESSMENT (routine / soon / promptly / urgent)

Fixed rules (module2_medical_ai\medai\rules.py) decide abnormal / critical values and the urgency; no AI model is involved.
The full table of ranges and thresholds is in docs\CLINICAL_RULES.md (generated from the code) for a doctor to review.
If an uncertain value could change the urgency, the result is marked "needs review before advice".

## Phase 2.5: the plain-language report

    .\.venv\Scripts\python.exe -m medai FILE --report     # what a patient would read: summary, good news, concerns, self-care, when to see a doctor

The wording lives in medai\knowledge.py (reviewed by a doctor via docs\PATIENT_ADVICE_TEXTS.md). Tests forbid any dose or
"start/stop a medicine" wording. Every concern links back to the exact place on the document it was read from.
