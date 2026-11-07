# Document analysis workflow (Modules 1 + 2 together)

1. **Upload**: a patient (own record), doctor or admin uploads a PDF or photo in the Documents tab. The original is stored encrypted.
2. **Analyse**: the Analyse button starts a background job. The server decrypts the file in memory, reads it (digital PDF text, or straightening + OCR for scans and photos),
   structures lab values / prescription fields, runs the checks (second reading of numbers, flag-vs-range, plausibility, units, identity), applies the clinical rules
   and builds the report. Page pictures are stored encrypted for the review screen.
3. **Review**: the review screen shows the document beside the values. Flagged values are highlighted. The person corrects or accepts each one;
   every correction re-runs the rules, so the urgency and report always follow the corrected values.
4. **Confirm**: nothing is saved as a result until every flagged item is corrected or knowingly accepted (and a wrong-patient warning is acknowledged).
   - Lab values become saved lab results (marked confirmed by patient or doctor).
   - Prescriptions confirmed by a **patient** become DRAFTS (never in the medication tracker); confirmed by a **doctor** they become active prescriptions.
   - A patient's draft can still be confirmed later by a doctor with the Confirm button.
5. **Audit**: requests, views by staff, reviews and confirmations are written to the append-only audit log. The urgency the machine first computed is kept next to the confirmed one.

| Role | Analyse | See result | Correct / confirm |
|---|---|---|---|
| Patient | own documents | own | yes (prescriptions only as drafts) |
| Doctor | any patient | yes, plus clinician summary | yes (prescriptions become active) |
| Admin | any patient | yes | no (read only) |

Limits: one analysis runs at a time inside the web server (a queue worker is the next step for deployment); 20 analyses per user per hour; documents with confirmed results cannot be deleted.
