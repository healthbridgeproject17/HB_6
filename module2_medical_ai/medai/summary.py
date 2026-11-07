"""Builds the report a person reads: summary, good findings, concerns (what each
means, how it may affect you, general self-care), when to see a doctor.
Every statement about a value carries a pointer to where it was read. All wording
comes from knowledge.py, which a doctor reviews. No medicine advice, ever."""
import re

from .knowledge import MEDICINE_INFO, PATTERNS, T

NO_MEDICINE_CHANGES = ("Do not start, stop or change any medicine because of this report. Talk to your doctor first.")
SEVERITY_WORD = {"borderline": "slightly", "mild": "mildly", "moderate": "moderately", "marked": "markedly", "critical": "critically"}
GENERIC = {
    "meaning": "This value is outside the usual range. A doctor can explain what it means together with your other results and your health history.",
    "may_affect": [], "self_care": ["Keep a balanced diet, stay active and drink enough water until you have seen a doctor"],
    "see_doctor_sooner_if": ["You feel unwell, or your symptoms get worse"],
}


def unit_text(r):
    """A unit that could not be read is shown as such, never as garbled text."""
    return r["unit"] if r.get("unit_status") in ("ok", "unexpected") and r["unit"] else "[unit unclear]"


def _tidy(text):
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text or "")  # 'more than90' -> 'more than 90'
    return re.sub(r"\s*,\s*", ", ", text).strip()


def _value_text(r):
    return f"{r['value']:g} {unit_text(r)}".strip()


def _range_text(r):
    i = r["interpretation"]
    if r.get("reference") and i["range_used"] and i["range_used"]["source"] == "printed":
        return _tidy(r["reference"]["text"])
    ru = i["range_used"]
    if not ru:
        return ""
    lo, hi = ru["low"], ru["high"]
    return f"{lo:g} - {hi:g}" if lo is not None and hi is not None else (f"more than {lo:g}" if lo is not None else f"less than {hi:g}")


def _explain(r):
    i = r["interpretation"]
    entry = T.get(r["test_key"], {})
    side = entry.get(i["status"]) if entry else None
    if side:
        meaning, may, care, sooner = side
        data = {"meaning": meaning, "may_affect": may, "self_care": care, "see_doctor_sooner_if": sooner}
    else:
        data = dict(GENERIC)
    data["measures"] = entry.get("measures") if entry else None
    return data


def _concern(r):
    i = r["interpretation"]
    word = SEVERITY_WORD.get(i["severity"], "")
    headline = f"{r['test']} is {word + ' ' if word else ''}{i['status']}: {_value_text(r)} (usual range {_range_text(r)})"
    if i["severity"] == "critical":
        headline += ". This is at a dangerous level"
    return {"test": r["test"], "test_key": r["test_key"], "headline": headline, "value": _value_text(r), "status": i["status"], "severity": i["severity"],
            "level": i["level"], "range": _range_text(r), "needs_review": r["needs_review"], "evidence": r["source"], **_explain(r)}


def _lab_report(a):
    labs = a["lab_results"]
    t = a["triage"]
    normal = [r for r in labs if r["interpretation"]["status"] == "normal"]
    abnormal = sorted([r for r in labs if r["interpretation"]["status"] in ("low", "high") and r["interpretation"]["severity"] not in ("normal", "borderline")],
                      key=lambda r: (-(r["interpretation"]["level"] or 0), r["test"]))
    borderline = [r for r in labs if r["interpretation"]["status"] in ("low", "high") and r["interpretation"]["severity"] == "borderline"]
    unassessed = [r for r in labs if r["interpretation"]["status"] == "not_assessed"]

    groups = {}
    for r in normal:
        groups.setdefault(r["group"], []).append(r["test"])
    good_news = [f"{g}: {', '.join(names)} - in the usual range" for g, names in groups.items()]

    patterns = []
    for p in t["patterns"]:
        text, _ = PATTERNS.get(p["id"], (p["text"], []))
        patterns.append({"id": p["id"], "label": p["label"], "explanation": text, "tests": p["tests"], "level": p["level"]})

    questions = []
    for p in sorted(t["patterns"], key=lambda p: -p["level"]):
        questions += PATTERNS.get(p["id"], (None, []))[1]
    if abnormal and not questions:
        questions.append("Which of these results matter most, and what should I do about them?")
    if abnormal:
        questions.append("Do any of these tests need to be repeated, and when?")
    questions = list(dict.fromkeys(questions))[:6]

    concerns = [_concern(r) for r in abnormal]
    flags = list(dict.fromkeys(f for c in concerns[:4] for f in c["see_doctor_sooner_if"]))[:6]

    n = len(labs)
    counts = t["counts"]
    if n == 0:
        headline = "No lab values could be read from this document."
    elif not abnormal and not borderline:
        headline = f"All {n} results that were read are within the usual range."
    else:
        headline = (f"{n} results were read: {counts['normal']} normal and {len(abnormal) + len(borderline)} outside the usual range"
                    + (f", of which {counts['critical']} at a dangerous level" if counts["critical"] else "") + ".")
    notes = []
    if t["provisional"]:
        notes.append(t["review_note"])
    if unassessed:
        notes.append(f"{len(unassessed)} result(s) could not be assessed ({', '.join(r['test'] for r in unassessed)}). A doctor should look at them.")
    if a["unrecognized_rows"]:
        notes.append(f"{len(a['unrecognized_rows'])} row(s) were not recognised and are not part of this assessment: "
                     + ", ".join(u["name_as_printed"] for u in a["unrecognized_rows"]) + ".")
    if borderline:
        notes.append("Slightly outside the range (usually not a concern): " + ", ".join(f"{r['test']} {_value_text(r)}" for r in borderline) + ".")
    if a.get("identity") and a["identity"]["status"] != "match":
        notes.insert(0, a["identity"]["message"])

    visit = {"level": t["level"], "label": t["label"], "timeframe": t["timeframe"], "advice": t["advice"], "why": [x["text"] for x in t["reasons"][:6]],
             "see_a_doctor_sooner_if": flags, "needs_review_before_advice": t["needs_review_before_advice"]}
    return {"type": "lab_report", "headline": headline, "visit": visit, "good_news": good_news, "concerns": concerns, "patterns": patterns,
            "questions_for_doctor": questions, "notes": notes, "medicines": NO_MEDICINE_CHANGES}


ROUTE_PHRASE = {"oral": "by mouth", "intravenous": "into a vein (IV)", "intramuscular": "by injection into a muscle", "subcutaneous": "by injection under the skin",
                "topical": "on the skin", "sublingual": "under the tongue", "inhalation": "by inhaling", "nasal": "into the nose", "rectal": "rectally",
                "ophthalmic": "into the eye", "otic": "into the ear"}


def _sentence(item):
    def part(f, fmt="{}"):
        v = item[f]["value"]
        text = v["text"] if isinstance(v, dict) and "text" in v else (v if isinstance(v, str) else None)
        return fmt.format(text) if text else None

    strength, dose, route, freq, dur = (part("strength"), part("dose"), part("route"), part("frequency"), part("duration"))
    name = item["medicine"]["value"] or "(name not detected)"
    pieces = [name + (f" {strength}" if strength else " [strength not detected]")]
    take = f"take {dose}" if dose else "dose [not detected]"
    take += f" {ROUTE_PHRASE.get(route, route)}" if route else ""
    when = f", {_tidy(item['frequency']['printed']).lower()}" if item["frequency"]["status"] != "missing" else ", frequency [not detected]"
    for_ = f", for {dur}" if dur else ", duration [not detected]"
    return f"{pieces[0]}: {take}{when}{for_}."


def _prescription_report(a):
    items = []
    for it in a["prescription_items"]:
        key = (it["medicine"]["suggestion"] if not it["medicine"]["recognised"] else (it["medicine"]["value"] or "")).lower()
        purpose = MEDICINE_INFO.get(key if it["medicine"]["recognised"] else (it["medicine"]["value"] or "").lower())
        missing = [f for f in ("strength", "dose", "frequency", "duration") if it[f]["status"] != "ok"]
        items.append({"medicine": it["medicine"]["value"], "instructions": _sentence(it), "purpose": purpose or "Ask your doctor or pharmacist what this medicine is for.",
                      "missing_fields": missing, "needs_review": it["needs_review"], "issues": it["issues"], "evidence": it["source"]})
    n = len(items)
    need = sum(1 for i in items if i["needs_review"])
    headline = f"{n} medicine(s) were read from this prescription." + (f" {need} need checking against the original." if need else "")
    return {"type": "prescription", "headline": headline, "items": items,
            "confirm": "This is a DRAFT read from a document. It does not count as a prescription in the record until a doctor has checked and confirmed it.",
            "reminders": ["Take medicines exactly as your doctor prescribed", "Ask your pharmacist if anything is unclear", "Tell your doctor about any allergies or other medicines you take"],
            "notes": ([a["identity"]["message"]] if a.get("identity") and a["identity"]["status"] != "match" else []), "medicines": NO_MEDICINE_CHANGES}


def clinician_view(a):
    if a["document_type"] == "lab_report":
        return {"triage": {k: a["triage"][k] for k in ("level", "label", "timeframe", "provisional", "needs_review_before_advice", "possible_level")},
                "findings": [{"test": r["test"], "value": r["value"], "unit": r["unit"], "range": _range_text(r), "status": r["interpretation"]["status"],
                              "severity": r["interpretation"]["severity"], "printed_flag": r["printed_flag"], "needs_review": r["needs_review"], "issues": r["issues"]}
                             for r in a["lab_results"]],
                "patterns": [p["label"] for p in a["triage"]["patterns"]], "reasons": [x["text"] for x in a["triage"]["reasons"]]}
    if a["document_type"] == "prescription":
        return {"items": [{f: i[f]["printed"] for f in ("medicine", "strength", "dose", "route", "frequency", "duration")} | {"needs_review": i["needs_review"], "issues": i["issues"]}
                          for i in a["prescription_items"]]}
    return {}


def build_report(a):
    if a["document_type"] == "lab_report":
        patient = _lab_report(a)
    elif a["document_type"] == "prescription":
        patient = _prescription_report(a)
    else:
        patient = {"type": "unknown", "headline": "This document could not be read as a lab report or a prescription.",
                   "notes": a["warnings"], "medicines": NO_MEDICINE_CHANGES}
    patient["disclaimer"] = a["disclaimer"]
    return {"patient": patient, "clinician": clinician_view(a)}


def to_text(report):
    p = report["patient"]
    out = [p["headline"], ""]
    if p["type"] == "lab_report":
        v = p["visit"]
        out += [f"DOCTOR VISIT: {v['label'].upper()}" + (f" ({v['timeframe']})" if v["timeframe"] else ""), v["advice"], ""]
        if v["why"]:
            out += ["Why:"] + [f"  - {w}" for w in v["why"]] + [""]
        if p["good_news"]:
            out += ["Good news:"] + [f"  + {g}" for g in p["good_news"]] + [""]
        seen = set()  # related results (e.g. kidney tests) share advice: say it once
        for c in p["concerns"]:
            out += [c["headline"] + ("  [CHECK THIS VALUE]" if c["needs_review"] else ""), f"  What it is: {c.get('measures') or ''}", f"  What it means: {c['meaning']}"]
            shared = False
            for label, key in (("How it may affect you", "may_affect"), ("What you can do", "self_care"), ("See a doctor sooner if", "see_doctor_sooner_if")):
                fresh = [x for x in c[key] if x not in seen]
                shared = shared or (len(fresh) < len(c[key]))
                seen.update(fresh)
                if fresh:
                    out += [f"  {label}:"] + [f"    - {x}" for x in fresh]
            if shared:
                out.append("  (Other advice for this result is the same as for the related results above.)")
            out.append("")
        if p["patterns"]:
            out += ["Putting results together:"] + [f"  * {x['label']}: {x['explanation']}" for x in p["patterns"]] + [""]
        if p["questions_for_doctor"]:
            out += ["Questions to ask your doctor:"] + [f"  ? {q}" for q in p["questions_for_doctor"]] + [""]
        if v["see_a_doctor_sooner_if"]:
            out += ["Get medical help sooner if:"] + [f"  ! {x}" for x in v["see_a_doctor_sooner_if"]] + [""]
    elif p["type"] == "prescription":
        out += [p["confirm"], ""]
        for i in p["items"]:
            out += [i["instructions"] + ("  [CHECK THIS]" if i["needs_review"] else ""), f"  What it is generally for: {i['purpose']}"] + [f"  ! {x}" for x in i["issues"]]
        out += [""] + [f"  - {r}" for r in p["reminders"]] + [""]
    for n in p.get("notes", []):
        out.append(f"NOTE: {n}")
    out += ["", p["medicines"], p["disclaimer"]]
    return "\n".join(out)
