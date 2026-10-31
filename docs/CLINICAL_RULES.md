# Clinical rules used by HealthBridge Module 2 (DRAFT FOR DOCTOR REVIEW)

These tables are generated from the code. Ranges are commonly used ADULT values. They have NOT been clinically validated. A doctor must review and approve every line before the system is used with real patients.

## How the level is decided

| Level | Meaning | When |
|---|---|---|
| Routine | at your next regular check-up | All values normal or only borderline (within 5% of a limit) |
| Consult a doctor soon | within 1-2 weeks | Mild or moderate abnormality, or a pattern such as diabetes-range sugar |
| Consult a doctor promptly | within 24-48 hours | Marked abnormality, or a worrying combination (several low blood counts, very high liver enzymes) |
| Urgent: seek medical care today | today | Any value at an alert (critical) level, or high potassium with reduced kidney function |

Severity words: borderline, mild, moderate, marked, critical. Thresholds are inclusive (a value exactly on a line escalates).
The report's own printed range is used when it can be read; the standard range below is the fallback (and a cross-check).

## Ranges and severity thresholds per test

| Test | Group | Usual unit | Standard adult range | Severity thresholds |
|---|---|---|---|---|
| Haemoglobin | CBC | g/dL | men: 13.5 - 17.5 / women: 12 - 15.5 | low: moderate <= 10, marked <= 8, critical <= 7; high: marked >= 18.5, critical >= 20 |
| RBC count | CBC | million/µL | men: 4.5 - 5.9 / women: 3.8 - 5.2 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Haematocrit (PCV) | CBC | % | men: 41 - 53 / women: 36 - 46 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| MCV | CBC | fL | 80 - 100 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| MCH | CBC | pg | 27 - 33 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| MCHC | CBC | g/dL | 32 - 36 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| WBC count | CBC | thousand/µL | 4 - 11 | low: moderate <= 3, marked <= 2.5, critical <= 2; high: moderate >= 15, marked >= 25, critical >= 30 |
| Platelet count | CBC | thousand/µL | 150 - 400 | low: moderate <= 100, marked <= 50, critical <= 20; high: marked >= 700, critical >= 1000 |
| ESR | CBC | mm/hr | men: 0 - 15 / women: 0 - 20 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Fasting glucose | Glucose | mg/dL | 70 - 99 | low: moderate <= 60, marked <= 54, critical <= 50; high: moderate >= 126, marked >= 250, critical >= 400 |
| Post-prandial glucose | Glucose | mg/dL | below 140 | low: moderate <= 60, marked <= 54, critical <= 50; high: moderate >= 200, marked >= 300, critical >= 400 |
| Random glucose | Glucose | mg/dL | below 140 | low: moderate <= 60, marked <= 54, critical <= 50; high: moderate >= 200, marked >= 300, critical >= 400 |
| HbA1c | Glucose | % | below 5.7 | high: moderate >= 8, marked >= 10 |
| Total cholesterol | Lipids | mg/dL | below 200 | high: moderate >= 240, marked >= 300 |
| LDL cholesterol | Lipids | mg/dL | below 100 | high: moderate >= 160, marked >= 190 |
| HDL cholesterol | Lipids | mg/dL | men: above 40 / women: above 50 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Triglycerides | Lipids | mg/dL | below 150 | high: moderate >= 200, marked >= 500, critical >= 1000 |
| VLDL cholesterol | Lipids | mg/dL | 2 - 30 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Serum creatinine | Kidney | mg/dL | men: 0.7 - 1.3 / women: 0.6 - 1.1 | high: moderate >= 1.5, marked >= 3, critical >= 6 |
| Blood urea | Kidney | mg/dL | 15 - 40 | high: moderate >= 60, marked >= 120 |
| Blood urea nitrogen | Kidney | mg/dL | 7 - 20 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Uric acid | Kidney | mg/dL | men: 3.5 - 7.2 / women: 2.6 - 6 | high: moderate >= 9, marked >= 12 |
| eGFR | Kidney | mL/min/1.73 m² | above 90 | low: moderate <= 60, marked <= 30 |
| Serum sodium | Electrolytes | mmol/L | 135 - 145 | low: moderate <= 130, marked <= 125, critical <= 120; high: moderate >= 150, marked >= 155, critical >= 160 |
| Serum potassium | Electrolytes | mmol/L | 3.5 - 5 | low: moderate <= 3.3, marked <= 3, critical <= 2.8; high: moderate >= 5.5, critical >= 6 |
| Serum chloride | Electrolytes | mmol/L | 98 - 107 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Serum calcium | Electrolytes | mg/dL | 8.5 - 10.5 | low: moderate <= 8, marked <= 7, critical <= 6.5; high: moderate >= 11.5, marked >= 12.5, critical >= 13 |
| SGPT (ALT) | Liver | U/L | 7 - 56 | high: moderate >= 168, marked >= 280, critical >= 1000 |
| SGOT (AST) | Liver | U/L | 10 - 40 | high: moderate >= 120, marked >= 200, critical >= 1000 |
| Alkaline phosphatase | Liver | U/L | 44 - 147 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Total bilirubin | Liver | mg/dL | 0.1 - 1.2 | high: moderate >= 3, marked >= 6, critical >= 15 |
| Direct bilirubin | Liver | mg/dL | 0 - 0.3 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Albumin | Liver | g/dL | 3.5 - 5 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Total protein | Liver | g/dL | 6 - 8.3 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| GGT | Liver | U/L | men: 8 - 61 / women: 5 - 36 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| TSH | Thyroid | mIU/L | 0.4 - 4 | low: moderate <= 0.1, marked <= 0.01; high: moderate >= 10, marked >= 25 |
| Free T4 | Thyroid | ng/dL | 0.8 - 1.8 | low: moderate <= 0.5, marked <= 0.3; high: moderate >= 2.5, marked >= 4 |
| Free T3 | Thyroid | pg/mL | 2.3 - 4.2 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Total T3 | Thyroid | ng/dL | 80 - 200 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Total T4 | Thyroid | µg/dL | 5 - 12 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Serum ferritin | Iron | ng/mL | men: 30 - 400 / women: 13 - 150 | low: moderate <= 10, marked <= 5 |
| Serum iron | Iron | µg/dL | men: 65 - 175 / women: 60 - 170 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| TIBC | Iron | µg/dL | 250 - 450 | generic: within 5% borderline, under 20% mild, under 50% moderate, more marked |
| Vitamin D (25-OH) | Vitamins | ng/mL | 30 - 100 | low: moderate <= 20, marked <= 10 |
| Vitamin B12 | Vitamins | pg/mL | 200 - 900 | low: moderate <= 200, marked <= 150 |

## Combinations that raise the level

- Possible reduced kidney function (creatinine high or eGFR below 60, with urea high or eGFR available): consult soon; promptly if eGFR below 30 or creatinine marked.
- High potassium (5.5 or more) together with reduced kidney function: urgent.
- Two or more of haemoglobin, WBC, platelets low: consult promptly.
- Iron deficiency pattern (low haemoglobin with low ferritin, or low MCV and MCH): consult soon.
- Diabetes range (HbA1c 6.5 or more, fasting glucose 126 or more, glucose 200 or more): consult soon; promptly if HbA1c 10 or more or glucose 300 or more.
- Pre-diabetes range (HbA1c 5.7-6.4 or fasting 100-125): consult soon.
- Raised TSH (with low free T4 = underactive thyroid pattern): consult soon. Low TSH with high free T4: promptly.
- LDL and triglycerides both high: consult soon.
- ALT above 3 x 56 or AST above 3 x 40: consult promptly.

## Known limits

- Adult ranges only (patients under 18 are not assessed unless the report prints its own range). No pregnancy, ethnicity or age-band adjustments.
- Values in unusual units are not assessed (they are flagged for checking).
- This is decision support. It never diagnoses and never advises changing medicines.
