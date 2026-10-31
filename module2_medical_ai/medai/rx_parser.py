"""Reads prescriptions into separate fields: medicine, strength, dose, route,
frequency, duration. A field that cannot be read with confidence is reported as
missing or uncertain; it is never guessed. Everything stays a DRAFT until a
doctor confirms it."""
import bisect
import difflib
import re

from .catalog import MEDICINES, squash_name
from .layout import group_rows

HEADERS = {
    "medicine": ["medicine", "medicines", "drug", "medication", "name", "item"],
    "strength": ["strength", "power"],
    "dose": ["dose", "dosage", "qty", "quantity"],
    "route": ["route"],
    "frequency": ["frequency", "freq", "timing", "schedule"],
    "duration": ["duration"],
}
FIELDS = ["medicine", "strength", "dose", "route", "frequency", "duration"]
REQUIRED = ["medicine", "strength", "dose", "frequency", "duration"]
STOP_WORDS = ("advice", "signature", "note", "fictional", "review", "diet", "follow", "next")

RE_STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|µg|μg|ug|g|ml|iu|%|units?)(?![a-z])", re.I)
RE_DOSE = re.compile(r"(\d+(?:/\d+)?|\d*\.\d+|one|half)\s*(tablets?|tabs?|capsules?|caps?|ml|drops?|puffs?|units?|sachets?|teaspoons?|tsp)", re.I)
RE_DURATION = re.compile(r"(\d+)\s*(days?|d|weeks?|wks?|months?)(?![a-z])", re.I)
ROUTES = {"oral": "oral", "po": "oral", "iv": "intravenous", "im": "intramuscular", "sc": "subcutaneous", "topical": "topical",
          "sublingual": "sublingual", "inhalation": "inhalation", "nasal": "nasal", "rectal": "rectal", "eye": "ophthalmic", "ear": "otic"}
FREQ_RULES = [  # (pattern on a letters/digits/hyphen only string, times per day, as needed)
    (r"(?<!\d)1-1-1-1(?!\d)|qid|4times|fourtimes", 4, False), (r"(?<!\d)1-1-1(?!\d)|thricedaily|tds|tid|3times|threetimes|threetimesdaily", 3, False),
    (r"(?<!\d)1-0-1(?!\d)|twicedaily|twiceaday|bd|bid|2times|twotimes|1-0-0-1|1-1-0(?!\d)|0-1-1(?!\d)", 2, False),
    (r"(?<!\d)(?:1-0-0|0-1-0|0-0-1)(?!\d)|oncedaily|onceaday|od|qd|oncea|athsnight|hs|daily|atnight|bedtime|everynight", 1, False),
]
TIMING = {"afterfood": "after food", "beforefood": "before food", "withfood": "with food", "emptystomach": "empty stomach",
          "morning": "morning", "night": "at night", "bedtime": "at bedtime", "afterbreakfast": "after breakfast", "beforebreakfast": "before breakfast",
          "afterlunch": "after lunch", "afterdinner": "after dinner"}


def parse_strength(text):
    m = RE_STRENGTH.search(text or "")
    if not m:
        return None
    unit = m.group(2).lower().replace("µ", "mc").replace("μ", "mc")
    unit = "mcg" if unit == "ug" else unit
    return {"value": float(m.group(1)), "unit": unit, "text": f"{m.group(1)} {unit}"}


def parse_dose(text):
    m = RE_DOSE.search(text or "")
    if not m:
        return None
    unit = m.group(2).lower().rstrip("s") if m.group(2).lower() not in ("ml", "tsp") else m.group(2).lower()
    unit = {"tab": "tablet", "cap": "capsule"}.get(unit, unit)
    return {"text": f"{m.group(1)} {unit}"}


def parse_route(text):
    t = re.sub(r"[^a-z]", "", (text or "").lower())
    return {"text": ROUTES[t]} if t in ROUTES else None


def parse_frequency(text):
    t = re.sub(r"[^a-z0-9-]", "", (text or "").lower())
    if not t:
        return None
    as_needed = bool(re.search(r"sos|prn|asneeded|ifrequired|whenrequired", t))
    times = None
    if re.search(r"weekly|oncea?week", t):
        times = None
        label = "weekly"
    else:
        label = None
        for pattern, n, _ in FREQ_RULES:
            if re.search(pattern, t):
                times = n
                break
    timing = [v for k, v in TIMING.items() if k in t]
    corrected = []
    for token in re.findall(r"[a-z]{5,}", (text or "").lower()):  # a misspelt word such as 'moning': use it, but say so
        close = difflib.get_close_matches(token, ["morning", "evening", "afternoon", "bedtime"], n=1, cutoff=0.75)
        if close and token != close[0]:
            if close[0] not in " ".join(timing):
                timing.append(TIMING.get(close[0], close[0]))
            corrected.append((token, close[0]))
    if times is None and not as_needed and not label:
        return None
    return {"text": text.strip(), "times_per_day": times, "as_needed": as_needed, "schedule": label, "timing": timing, "corrected": corrected}


def parse_duration(text):
    t = (text or "").lower()
    if re.search(r"continue|ongoing|lifelong|long\s*term", t):
        return {"text": text.strip(), "days": None, "ongoing": True}
    m = RE_DURATION.search(text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    days = n * (7 if unit.startswith(("w",)) else 30 if unit.startswith("m") else 1)
    return {"text": f"{n} {unit.rstrip('s') if n == 1 else (unit if unit.endswith('s') else unit + 's')}", "days": days, "ongoing": False}


def check_medicine(printed):
    name = re.sub(r"^(tab|tablet|cap|capsule|syp|syrup|inj|injection)\.?\s*", "", printed.strip(), flags=re.I)
    name = re.split(r"\d", name)[0].strip() or name
    key = squash_name(name)
    known = {squash_name(m): m for m in MEDICINES}
    if key in known:
        return {"name": name, "recognised": True, "suggestion": None}
    close = difflib.get_close_matches(key, list(known), n=1, cutoff=0.8)
    return {"name": name, "recognised": False, "suggestion": known[close[0]] if close else None}


def _field(printed, parsed, confidence):
    if printed is None or not str(printed).strip():
        return {"value": None, "printed": None, "confidence": None, "status": "missing"}
    if parsed is None:
        return {"value": None, "printed": printed, "confidence": round(confidence, 3), "status": "uncertain"}
    return {"value": parsed, "printed": printed, "confidence": round(confidence, 3), "status": "ok"}


def _build_item(parts, source, quality_poor):
    """parts: field -> (printed text or None, confidence)."""
    item, issues, confs = {}, [], []
    parsers = {"strength": parse_strength, "dose": parse_dose, "route": parse_route, "frequency": parse_frequency, "duration": parse_duration}
    med_text, med_conf = parts.get("medicine", (None, 0))[:2]
    med_alt = parts["medicine"][2] if "medicine" in parts and len(parts["medicine"]) > 2 else None
    if med_alt:
        issues.append(f"Two readings of the medicine name disagree ('{med_text}' and '{med_alt}'). Check the original.")
    check = check_medicine(med_text) if med_text else {"name": None, "recognised": False, "suggestion": None}
    item["medicine"] = {"value": check["name"], "printed": med_text, "confidence": round(med_conf, 3) if med_text else None,
                        "status": "ok" if med_text else "missing", "recognised": check["recognised"], "suggestion": check["suggestion"]}
    if med_text:
        confs.append(med_conf)
        if not check["recognised"]:
            hint = f" Did you mean {check['suggestion'].title()}?" if check["suggestion"] else ""
            issues.append(f"Medicine name '{check['name']}' is not in the known-medicine list. Verify the spelling.{hint}")
    else:
        issues.append("Medicine name not detected.")
    for name, parser in parsers.items():
        text, conf = parts.get(name, (None, 0))[:2]
        alt = parts[name][2] if name in parts and len(parts[name]) > 2 else None
        if alt:
            issues.append(f"Two readings of the {name} disagree ('{text}' and '{alt}'). Check the original.")
        item[name] = _field(text, parser(text) if text else None, conf)
        if item[name]["status"] != "missing":
            confs.append(conf)
        if item[name]["status"] != "ok" and name in REQUIRED:
            issues.append(f"{name.capitalize()} not confidently detected" + (f" (read as '{text}')." if text else "."))
        elif item[name]["status"] == "ok" and name == "frequency" and item[name]["value"].get("corrected"):
            word, fixed = item[name]["value"]["corrected"][0]
            issues.append(f"Frequency contained '{word}', read as '{fixed}'. Check the spelling against the original.")
        elif item[name]["status"] == "ok" and conf < 0.85:
            issues.append(f"{name.capitalize()} was read with low confidence ({conf:.0%}).")
    if med_text and med_conf < 0.85:
        issues.append(f"Medicine name was read with low confidence ({med_conf:.0%}).")
    if quality_poor:
        issues.append("The picture quality is poor. Check every field against the original.")
    return {**item, "confidence": round(min(confs), 3) if confs else 0.0, "source": source, "issues": issues,
            "needs_review": bool(issues), "status": "draft", "requires_doctor_confirmation": True}


# ---------------------------------------------------------------- table prescriptions
def _find_columns(lines):
    cols = {}
    for l in lines:
        t = squash_name(l["text"])
        for field, names in HEADERS.items():
            if t in names and field not in cols:
                cols[field] = l
    return cols


def parse_table(page, quality_poor):
    cols = _find_columns(page["lines"])
    if "medicine" not in cols or len(cols) < 3:
        return None
    centers = sorted(((c["bbox"][0] + c["bbox"][2]) / 2, f) for f, c in cols.items())
    bounds = [(centers[i][0] + centers[i + 1][0]) / 2 for i in range(len(centers) - 1)]
    order = [f for _, f in centers]
    header_y = max((c["bbox"][1] + c["bbox"][3]) / 2 for c in cols.values())
    left_edge = cols["medicine"]["bbox"][0] - 8
    items = []
    for row in group_rows(page["lines"]):
        if row["y"] <= header_y + 4:
            continue
        if squash_name(row["cells"][0]["text"]).startswith(STOP_WORDS):
            break
        parts = {}
        for cell in row["cells"]:
            cx = (cell["bbox"][0] + cell["bbox"][2]) / 2
            if cx < left_edge:
                continue  # the "No." column
            field = order[bisect.bisect(bounds, cx)]
            prev = parts.get(field)
            alt = cell.get("alt_text") or (prev[2] if prev and len(prev) > 2 else None)
            parts[field] = ((prev[0] + " " + cell["text"]) if prev else cell["text"], min(prev[1], cell["confidence"]) if prev else cell["confidence"], alt)
        med = parts.get("medicine")
        if not med or len(re.sub(r"[^A-Za-z]", "", med[0])) < 3:
            continue
        bbox = [min(c["bbox"][0] for c in row["cells"]), min(c["bbox"][1] for c in row["cells"]),
                max(c["bbox"][2] for c in row["cells"]), max(c["bbox"][3] for c in row["cells"])]
        items.append(_build_item(parts, {"page": page["page"], "bbox": [round(v, 1) for v in bbox], "text": row["text"]}, quality_poor))
    return items


# ---------------------------------------------------------------- free-text prescriptions
RE_LINE = re.compile(r"^(?:\d+[.)]\s*)?(tab|tablet|cap|capsule|syp|syrup|inj|injection)\b\.?\s*(.+)$", re.I)


def parse_free_text(page, quality_poor):
    items = []
    for row in group_rows(page["lines"]):
        m = RE_LINE.match(row["text"].strip())
        if not m:
            continue
        rest = m.group(2)
        name = re.split(r"\d", rest)[0].strip(" -,.") or rest
        freq = re.search(r"(\d-\d-\d(?:-\d)?|\b(?:od|bd|bid|tds|tid|qid|hs|sos|prn)\b|(?:once|twice|thrice)\s*(?:a\s*)?daily)", rest, re.I)
        dur = re.search(r"(?:x|for)\s*(\d+\s*(?:days?|d|weeks?|months?))", rest, re.I)
        timing = re.search(r"(after food|before food|with food|empty stomach|at night|morning|bedtime)", rest, re.I)
        parts = {"medicine": (f"{m.group(1).title()} {name}", row["min_confidence"])}
        s = RE_STRENGTH.search(rest)
        if s:
            parts["strength"] = (s.group(0), row["min_confidence"])
        d = RE_DOSE.search(rest)
        if d:
            parts["dose"] = (d.group(0), row["min_confidence"])
        elif freq:
            lead = re.search(r"(\d)-\d-\d", freq.group(0))
            if lead and s:
                parts["dose"] = (f"{lead.group(1)} tablet" if m.group(1).lower().startswith("tab") else f"{lead.group(1)} unit", row["min_confidence"] * 0.9)
        if freq:
            parts["frequency"] = (freq.group(0) + (" " + timing.group(0) if timing else ""), row["min_confidence"])
        if dur:
            parts["duration"] = (dur.group(1), row["min_confidence"])
        for key in ("route",):
            r = re.search(r"\b(oral|iv|im|sc|topical|sublingual|po)\b", rest, re.I)
            if r:
                parts[key] = (r.group(1), row["min_confidence"])
        items.append(_build_item(parts, {"page": page["page"], "bbox": [round(v, 1) for v in (min(c["bbox"][0] for c in row["cells"]), min(c["bbox"][1] for c in row["cells"]),
                                                                                                max(c["bbox"][2] for c in row["cells"]), max(c["bbox"][3] for c in row["cells"]))],
                                         "text": row["text"]}, quality_poor))
    return items
