"""Writes docs/PATIENT_ADVICE_TEXTS.md from module2_medical_ai/medai/knowledge.py,
so a doctor can review every sentence a patient may be shown."""
import os
import sys

root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(root, "module2_medical_ai"))
from medai import knowledge  # noqa: E402
from medai.catalog import TESTS  # noqa: E402

L = ["# Patient-facing advice texts (DRAFT FOR DOCTOR REVIEW)", "",
     "Everything below is generated from the code. Rules followed: describe, never diagnose; general lifestyle self-care only; "
     "no medicine names, doses, or instructions to start, stop or change a medicine. Please mark any sentence you would change.", ""]
for key, t in TESTS.items():
    e = knowledge.T[key]
    L += [f"## {t['label']}  ({t['group']})", "", f"**What it measures:** {e['measures']}", ""]
    for side in ("low", "high"):
        if e[side]:
            meaning, may, care, sooner = e[side]
            L += [f"### If {side}", f"- **Meaning:** {meaning}", "- **May affect you:** " + "; ".join(may), "- **General self-care:** " + "; ".join(care),
                  "- **See a doctor sooner if:** " + "; ".join(sooner), ""]
L += ["## Combinations", ""]
for pid, (text, qs) in knowledge.PATTERNS.items():
    L += [f"- **{pid}:** {text}  Questions: " + " / ".join(qs)]
L += ["", "## What each medicine is generally for (shown on prescription summaries)", ""] + [f"- {k}: {v}" for k, v in knowledge.MEDICINE_INFO.items()]
open(os.path.join(root, "docs", "PATIENT_ADVICE_TEXTS.md"), "w").write("\n".join(L) + "\n")
print("written", len(L), "lines")
