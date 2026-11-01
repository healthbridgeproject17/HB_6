"""One call: file bytes -> reading + structured, checked results."""
import difflib
import re

from . import lab_parser, rules, rx_parser, summary
from .catalog import squash_name
from .extract import extract_document

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DISCLAIMER = ("Automatic reading of a document. It can contain mistakes. Everything here is unconfirmed until a doctor or the "
              "patient checks it against the original. This is not a diagnosis.")


def _date(text):
    m = re.search(r"(\d{1,2})[-/ .]?([A-Za-z0]{3})[-/ .]?(\d{4})", text)
    if not m:
        return None
    month = difflib.get_close_matches(m.group(2).lower().replace("0", "o"), MONTHS, n=1, cutoff=0.6)
    return f"{m.group(3)}-{MONTHS.index(month[0]) + 1:02d}-{int(m.group(1)):02d}" if month else None


def patient_on_document(pages):
    info = {"name_as_printed": None, "age": None, "sex": None, "collected": None, "reported": None, "date": None}
    for page in pages:
        for line in page["lines"]:
            t = line["text"].strip()
            if info["name_as_printed"] is None:
                m = re.match(r"(?i)^(?:patient(?:\s*name)?|name)\s*[:\-]\s*(.+)$", t)
                if m and len(m.group(1)) >= 3:
                    info["name_as_printed"] = m.group(1).strip()
            m = re.search(r"(?i)age\s*/?\s*sex\s*[:\-]?\s*(\d{1,3})\s*y\w*\s*/?\s*(male|female|m|f)\b", t)
            if m and info["age"] is None:
                info["age"] = int(m.group(1))
                info["sex"] = "female" if m.group(2).lower().startswith("f") else "male"
            low = squash_name(t)
            if low.startswith("collected") and not info["collected"]:
                info["collected"] = _date(t)
            elif low.startswith("reported") and not info["reported"]:
                info["reported"] = _date(t)
            elif low.startswith("date") and not info["date"]:
                info["date"] = _date(t)
    return info


def check_identity(printed_name, record_name, record_sex=None, printed_sex=None):
    """Does the document belong to the patient it is being attached to?"""
    if not printed_name:
        return {"status": "not_found", "message": "No patient name could be read on the document. Confirm it belongs to this patient."}
    a, b = squash_name(printed_name), squash_name(record_name)
    sex_note = ""
    if record_sex and printed_sex and record_sex != printed_sex:
        sex_note = f" The sex on the document ({printed_sex}) also differs from the record ({record_sex})."
    if a == b or a in b or b in a:
        status = "match"
    elif difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
        status = "similar"
    else:
        status = "mismatch"
    messages = {"match": "Name matches the patient record.", "similar": f"The name on the document ('{printed_name}') is similar to the record ('{record_name}'). Check it.",
                "mismatch": f"The name on the document ('{printed_name}') does NOT match the patient record ('{record_name}'). Make sure this document belongs to this patient."}
    return {"status": status, "message": messages[status] + sex_note if status != "match" or sex_note else messages[status]}


def analyze_document(data: bytes, engine: str = "auto", patient: dict = None) -> dict:
    """patient (optional): {"name": ..., "sex": ...} from the record, for the identity check."""
    ex = extract_document(data, engine=engine)
    poor = any(p["quality"]["label"] == "poor" for p in ex["pages"])
    labs, unrecognized, rx_items, doc_type = [], [], [], "unknown"
    for page in ex["pages"]:
        table = rx_parser.parse_table(page, poor)
        if table is not None:
            rx_items += table
    if rx_items:
        doc_type = "prescription"
    else:
        labs, unrecognized = lab_parser.parse_lab_rows(ex["pages"])
        if len(labs) >= 2:
            doc_type = "lab_report"
        else:
            for page in ex["pages"]:
                rx_items += rx_parser.parse_free_text(page, poor)
            doc_type = "prescription" if rx_items else ("lab_report" if labs else "unknown")
    if poor:
        for r in labs:
            r["issues"].append("The picture quality is poor. Check every value against the original.")
            r["needs_review"] = True

    warnings = list(ex["warnings"])
    if doc_type == "unknown":
        warnings.append("No lab results or prescription items could be recognised. Check the picture or enter the details manually.")
    on_doc = patient_on_document(ex["pages"])
    identity = check_identity(on_doc["name_as_printed"], patient["name"], patient.get("sex"), on_doc["sex"]) if patient else None
    if identity and identity["status"] != "match":
        warnings.append(identity["message"])
    triage = None
    if doc_type == "lab_report":
        triage = rules.assess(labs, patient={"sex": (patient or {}).get("sex"), "age": (patient or {}).get("age")}, document={"sex": on_doc["sex"], "age": on_doc["age"]})
        if triage["needs_review_before_advice"]:
            warnings.append(triage["review_note"])
    items = labs + rx_items
    result = {
        "document_type": doc_type, "patient_on_document": on_doc, "identity": identity,
        "lab_results": labs, "unrecognized_rows": unrecognized, "prescription_items": rx_items, "triage": triage,
        "summary": {"items": len(items), "needs_review": sum(1 for i in items if i["needs_review"]), "unrecognized_rows": len(unrecognized)},
        "warnings": warnings, "status": "unconfirmed", "disclaimer": DISCLAIMER,
        "extraction": {k: ex[k] for k in ("kind", "page_count", "mean_confidence", "ocr_engine", "elapsed_seconds", "pages")},
    }
    result["report"] = summary.build_report(result)
    return result
