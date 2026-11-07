"""Applies a person's corrections to an analysis, then re-runs the rules so the
urgency and the report always follow the CORRECTED values. Nothing here trusts
the original reading more than the human's correction, and nothing is saved as
confirmed unless every flagged item was corrected or knowingly accepted."""
import copy
import math

from . import lab_parser, rules, rx_parser, summary
from .catalog import TESTS, match_test, normalize_unit


class ReviewError(ValueError):
    """The edit is not valid (shown to the user as is)."""


def _number(value, label):
    try:
        x = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ReviewError(f"{label}: '{value}' is not a number.")
    if not math.isfinite(x) or abs(x) > 1e7:
        raise ReviewError(f"{label}: '{value}' is not a sensible number.")
    return x


def _recheck_lab(r, flags_used):
    """Fresh checks for a value a person has typed in (no OCR confidence involved)."""
    issues, test = [], TESTS[r["test_key"]]
    unit = normalize_unit(r["unit"] or "")
    if not r["unit"]:
        r["unit_status"] = "missing"
        issues.append(f"Unit not given (usual unit: {test['unit']}).")
    elif unit is None:
        r["unit_status"] = "uncertain"
        issues.append(f"Unit '{r['unit']}' not recognised (expected {test['unit']}).")
    elif normalize_unit(test["unit"]) != unit and test["unit"] != unit:
        r["unit_status"] = "unexpected"
        issues.append(f"Unit {unit} differs from the usual {test['unit']}. The value may need converting.")
    else:
        r["unit_status"], r["unit"] = "ok", unit
    lo, hi = test["plausible"]
    if not lo <= r["value"] <= hi:
        issues.append(f"Value {r['value']:g} is outside what is physically plausible for {test['label']} ({lo:g}-{hi:g}).")
    if r["reference"] is None:
        issues.append("Reference range not given.")
    elif flags_used and not r.get("value_qualifier"):
        expected = lab_parser.computed_flag(r["value"], r["reference"])
        if expected != r["printed_flag"]:
            issues.append(f"The flag ({r['printed_flag'] or 'none'}) disagrees with the value against the range ({expected or 'normal'}).")
    return issues


def _apply_lab_edit(r, edit, log, index):
    if "value" in edit and edit["value"] not in (None, ""):
        new = _number(edit["value"], f"{r['test']} value")
        if new != r["value"]:
            log.append({"kind": "lab", "index": index, "test": r["test"], "field": "value", "old": r["value"], "new": new})
            r["value"] = new
        r["value_alternative"] = None
    if "unit" in edit and (edit["unit"] or "") != (r["unit"] or ""):
        log.append({"kind": "lab", "index": index, "test": r["test"], "field": "unit", "old": r["unit"], "new": edit["unit"]})
        r["unit"] = str(edit["unit"]).strip()[:20] or None
    if "reference" in edit and edit["reference"] not in (None, ""):
        rng = lab_parser.parse_range(str(edit["reference"]))
        if rng is None:
            raise ReviewError(f"{r['test']} reference range: '{edit['reference']}' is not understood. Use a form like 12.0 - 15.5, less than 200 or more than 40.")
        old = r["reference"]["text"] if r["reference"] else None
        if rng["text"] != old:
            log.append({"kind": "lab", "index": index, "test": r["test"], "field": "reference", "old": old, "new": rng["text"]})
        r["reference"], r["reference_alternative"] = rng, None
    if "flag" in edit and edit["flag"] is not None:
        flag = str(edit["flag"]).strip().upper()
        if flag not in ("", "H", "L"):
            raise ReviewError(f"{r['test']} flag must be H, L or empty.")
        if (flag or None) != r["printed_flag"]:
            log.append({"kind": "lab", "index": index, "test": r["test"], "field": "flag", "old": r["printed_flag"], "new": flag or None})
        r["printed_flag"] = flag or None
        r["printed_critical"] = r["printed_critical"] and bool(flag)


def apply_review(analysis, edits, context=None):
    """edits = {"lab_results": {"0": {"value": 9.8, "unit": "g/dL", "reference": "12-15.5", "flag": "L", "accepted": true, "remove": false}},
                "add_lab_results": [{"test": "Haemoglobin", "value": 9.8, "unit": "g/dL", "reference": "12-15.5"}],
                "prescription_items": {"0": {"strength": "500 mg", ..., "accepted": true, "remove": false}},
                "add_prescription_items": [{"medicine": ..., "strength": ..., ...}]}
    Returns a NEW analysis (the original is left untouched) with "review_log"."""
    a = copy.deepcopy(analysis)
    log = []
    context = context or {}
    labs, items = a["lab_results"], a["prescription_items"]
    remove_labs, remove_rx = set(), set()

    for key, edit in (edits.get("lab_results") or {}).items():
        i = int(key)
        if not 0 <= i < len(labs):
            raise ReviewError(f"There is no result number {i}.")
        r = labs[i]
        if edit.get("remove"):
            remove_labs.add(i)
            log.append({"kind": "lab", "index": i, "test": r["test"], "field": "row", "old": r["value"], "new": "removed"})
            continue
        before = (r["value"], r["unit"], r["reference"] and r["reference"]["text"], r["printed_flag"])
        _apply_lab_edit(r, edit, log, i)
        r["user_reviewed"] = True
        r["_accepted"] = bool(edit.get("accepted"))
        r["_changed"] = before != (r["value"], r["unit"], r["reference"] and r["reference"]["text"], r["printed_flag"])

    for n, add in enumerate(edits.get("add_lab_results") or []):
        key, _ = match_test(str(add.get("test") or ""))
        if key is None:
            raise ReviewError(f"Added result {n + 1}: the test '{add.get('test')}' is not one we know. Pick a name from the list.")
        value = _number(add.get("value"), f"{TESTS[key]['label']} value")
        rng = lab_parser.parse_range(str(add["reference"])) if add.get("reference") else None
        if add.get("reference") and rng is None:
            raise ReviewError(f"{TESTS[key]['label']} reference range '{add['reference']}' is not understood.")
        labs.append({"test_key": key, "test": TESTS[key]["label"], "group": TESTS[key]["group"], "name_as_printed": str(add.get("test")), "value": value,
                     "value_qualifier": None, "unit": (str(add.get("unit") or "").strip() or None), "unit_status": "ok", "reference": rng,
                     "printed_flag": None, "printed_critical": False, "confidence": 1.0, "source": None, "issues": [], "value_alternative": None,
                     "reference_alternative": None, "needs_review": False, "user_reviewed": True, "manual": True, "_accepted": True, "_changed": True})
        log.append({"kind": "lab", "index": len(labs) - 1, "test": TESTS[key]["label"], "field": "row", "old": None, "new": "added by hand"})

    for key, edit in (edits.get("prescription_items") or {}).items():
        i = int(key)
        if not 0 <= i < len(items):
            raise ReviewError(f"There is no medicine number {i}.")
        it = items[i]
        if edit.get("remove"):
            remove_rx.add(i)
            log.append({"kind": "prescription", "index": i, "test": it["medicine"]["printed"], "field": "row", "old": "item", "new": "removed"})
            continue
        parts = {f: (it[f]["printed"], it[f]["confidence"] or 0.9) for f in rx_parser.FIELDS if it[f]["printed"]}
        for f in rx_parser.FIELDS:
            if f in edit:
                text = str(edit[f] or "").strip()[:200]
                if text != (it[f]["printed"] or ""):
                    log.append({"kind": "prescription", "index": i, "test": it["medicine"]["printed"], "field": f, "old": it[f]["printed"], "new": text or None})
                if text:
                    parts[f] = (text, 1.0)
                else:
                    parts.pop(f, None)
        rebuilt = rx_parser._build_item(parts, it["source"], False)
        rebuilt["user_reviewed"], rebuilt["_accepted"] = True, bool(edit.get("accepted"))
        items[i] = rebuilt

    for n, add in enumerate(edits.get("add_prescription_items") or []):
        if not str(add.get("medicine") or "").strip():
            raise ReviewError(f"Added medicine {n + 1} needs a name.")
        parts = {f: (str(add[f]).strip()[:200], 1.0) for f in rx_parser.FIELDS if str(add.get(f) or "").strip()}
        item = rx_parser._build_item(parts, None, False)
        item["user_reviewed"], item["manual"], item["_accepted"] = True, True, True
        items.append(item)
        log.append({"kind": "prescription", "index": len(items) - 1, "test": add.get("medicine"), "field": "row", "old": None, "new": "added by hand"})

    a["lab_results"] = [r for i, r in enumerate(labs) if i not in remove_labs]
    a["prescription_items"] = [r for i, r in enumerate(items) if i not in remove_rx]

    flags_used = any(r["printed_flag"] for r in a["lab_results"])
    for r in a["lab_results"]:
        if not r.get("user_reviewed"):
            continue
        accepted, changed = r.pop("_accepted", False), r.pop("_changed", False)
        if changed:
            r["confidence"] = 1.0
            r["issues"] = _recheck_lab(r, flags_used)
        elif accepted and r["issues"]:
            r["acknowledged_issues"] = r["issues"]
            r["issues"] = []
        r["needs_review"] = bool(r["issues"]) and not accepted
        if accepted and r["issues"]:
            r["acknowledged_issues"] = r["issues"]
            r["issues"], r["needs_review"] = [], False
    for it in a["prescription_items"]:
        if it.get("user_reviewed"):
            accepted = it.pop("_accepted", False)
            if accepted and it["issues"]:
                it["acknowledged_issues"] = it["issues"]
                it["issues"] = []
            it["needs_review"] = bool(it["issues"])
        it["status"], it["requires_doctor_confirmation"] = "draft", True

    if a["document_type"] == "lab_report" or a["lab_results"]:
        a["document_type"] = "lab_report" if a["lab_results"] else a["document_type"]
        a["triage"] = rules.assess(a["lab_results"], {"sex": context.get("sex"), "age": context.get("age")},
                                   {"sex": a["patient_on_document"]["sex"], "age": a["patient_on_document"]["age"]}) if a["lab_results"] else None
    items_all = a["lab_results"] + a["prescription_items"]
    a["summary"] = {"items": len(items_all), "needs_review": sum(1 for i in items_all if i["needs_review"]), "unrecognized_rows": len(a["unrecognized_rows"])}
    a["warnings"] = [w for w in a["warnings"] if "flagged for checking" not in w]
    if a.get("triage") and a["triage"]["needs_review_before_advice"]:
        a["warnings"].append(a["triage"]["review_note"])
    a["review_log"] = (analysis.get("review_log") or []) + log
    a["report"] = summary.build_report(a)
    return a
