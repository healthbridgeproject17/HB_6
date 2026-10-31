"""Writes docs/CLINICAL_RULES.md from the rules in module2_medical_ai/medai/rules.py,
so the document a doctor reviews is always exactly what the code does."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "module2_medical_ai"))
from medai import rules  # noqa: E402
from medai.catalog import TESTS  # noqa: E402


def rng(r):
    if isinstance(r, dict):
        return " / ".join(f"{s}: {rng(v)}" for s, v in (("men", r["M"]), ("women", r["F"])))
    lo, hi = r
    return f"{lo:g} - {hi:g}" if lo is not None and hi is not None else (f"above {lo:g}" if lo is not None else f"below {hi:g}")


def bands(b):
    out = []
    for d in ("low", "high"):
        if d in b:
            parts = [f"{n} {'<=' if d == 'low' else '>='} {v:g}" for n, v in b[d].items() if v is not None]
            out.append(f"{d}: " + ", ".join(parts))
    return "; ".join(out)


lines = ["# Clinical rules used by HealthBridge Module 2 (DRAFT FOR DOCTOR REVIEW)", "",
         "These tables are generated from the code. Ranges are commonly used ADULT values. They have NOT been clinically validated. "
         "A doctor must review and approve every line before the system is used with real patients.", "",
         "## How the level is decided", "",
         "| Level | Meaning | When |", "|---|---|---|"]
for i, name in enumerate(rules.LEVELS):
    label, timeframe, _ = rules.LEVEL_INFO[name]
    when = ["All values normal or only borderline (within 5% of a limit)", "Mild or moderate abnormality, or a pattern such as diabetes-range sugar",
            "Marked abnormality, or a worrying combination (several low blood counts, very high liver enzymes)", "Any value at an alert (critical) level, or high potassium with reduced kidney function"][i]
    lines.append(f"| {label} | {timeframe} | {when} |")
lines += ["", "Severity words: borderline, mild, moderate, marked, critical. Thresholds are inclusive (a value exactly on a line escalates).",
          "The report's own printed range is used when it can be read; the standard range below is the fallback (and a cross-check).", "",
          "## Ranges and severity thresholds per test", "", "| Test | Group | Usual unit | Standard adult range | Severity thresholds |", "|---|---|---|---|---|"]
for key, t in TESTS.items():
    lines.append(f"| {t['label']} | {t['group']} | {t['unit']} | {rng(rules.RANGES[key]) if key in rules.RANGES else '-'} | {bands(rules.BANDS[key]) if key in rules.BANDS else 'generic: within 5% borderline, under 20% mild, under 50% moderate, more marked'} |")
lines += ["", "## Combinations that raise the level", "",
          "- Possible reduced kidney function (creatinine high or eGFR below 60, with urea high or eGFR available): consult soon; promptly if eGFR below 30 or creatinine marked.",
          "- High potassium (5.5 or more) together with reduced kidney function: urgent.",
          "- Two or more of haemoglobin, WBC, platelets low: consult promptly.",
          "- Iron deficiency pattern (low haemoglobin with low ferritin, or low MCV and MCH): consult soon.",
          "- Diabetes range (HbA1c 6.5 or more, fasting glucose 126 or more, glucose 200 or more): consult soon; promptly if HbA1c 10 or more or glucose 300 or more.",
          "- Pre-diabetes range (HbA1c 5.7-6.4 or fasting 100-125): consult soon.",
          "- Raised TSH (with low free T4 = underactive thyroid pattern): consult soon. Low TSH with high free T4: promptly.",
          "- LDL and triglycerides both high: consult soon.",
          "- ALT above 3 x 56 or AST above 3 x 40: consult promptly.", "",
          "## Known limits", "",
          "- Adult ranges only (patients under 18 are not assessed unless the report prints its own range). No pregnancy, ethnicity or age-band adjustments.",
          "- Values in unusual units are not assessed (they are flagged for checking).",
          "- This is decision support. It never diagnoses and never advises changing medicines."]
os.makedirs(os.path.join(os.path.dirname(__file__), "..", "docs"), exist_ok=True)
open(os.path.join(os.path.dirname(__file__), "..", "docs", "CLINICAL_RULES.md"), "w").write("\n".join(lines) + "\n")
print("written")
