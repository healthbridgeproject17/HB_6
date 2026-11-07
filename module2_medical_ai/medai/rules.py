"""Clinical rules for lab results: which values are abnormal or critical, and
how urgently a doctor should be seen. Fixed, readable rules decide this, never a
language model. Ranges and alert levels are commonly used ADULT values; they are
a working draft that a doctor must review before any real-world use."""
from .catalog import TESTS, normalize_unit

RULES_VERSION = "draft-2026-11"  # change whenever a range, threshold or rule changes
LEVELS = ["routine", "consult_soon", "consult_promptly", "urgent"]
LEVEL_INFO = {
    "routine": ("Routine", "at your next regular check-up", "No urgent action is needed based on the values read."),
    "consult_soon": ("Consult a doctor soon", "within 1-2 weeks", "Some values are outside the usual range. Book a visit and take this report."),
    "consult_promptly": ("Consult a doctor promptly", "within 24-48 hours", "Some values are markedly abnormal. See a doctor within a day or two."),
    "urgent": ("Urgent: seek medical care today", "today", "At least one value is at a dangerous level. Contact a doctor now or go to the nearest hospital emergency department. "
                                                         "If you feel unwell (chest pain, irregular heartbeat, severe weakness, confusion, breathlessness), call 112."),
}

# standard adult reference ranges: (low, high), either may be None; or {"M": (...), "F": (...)}
RANGES = {
    "hemoglobin": {"M": (13.5, 17.5), "F": (12.0, 15.5)}, "rbc": {"M": (4.5, 5.9), "F": (3.8, 5.2)}, "hematocrit": {"M": (41, 53), "F": (36, 46)},
    "mcv": (80, 100), "mch": (27, 33), "mchc": (32, 36), "wbc": (4.0, 11.0), "platelets": (150, 400), "esr": {"M": (0, 15), "F": (0, 20)},
    "glucose_fasting": (70, 99), "glucose_pp": (None, 140), "glucose_random": (None, 140), "hba1c": (None, 5.7),
    "cholesterol_total": (None, 200), "ldl": (None, 100), "hdl": {"M": (40, None), "F": (50, None)}, "triglycerides": (None, 150), "vldl": (2, 30),
    "creatinine": {"M": (0.7, 1.3), "F": (0.6, 1.1)}, "urea": (15, 40), "bun": (7, 20), "uric_acid": {"M": (3.5, 7.2), "F": (2.6, 6.0)}, "egfr": (90, None),
    "sodium": (135, 145), "potassium": (3.5, 5.0), "chloride": (98, 107), "calcium": (8.5, 10.5),
    "alt": (7, 56), "ast": (10, 40), "alp": (44, 147), "bilirubin_total": (0.1, 1.2), "bilirubin_direct": (0.0, 0.3), "albumin": (3.5, 5.0),
    "protein_total": (6.0, 8.3), "ggt": {"M": (8, 61), "F": (5, 36)},
    "tsh": (0.4, 4.0), "ft4": (0.8, 1.8), "ft3": (2.3, 4.2), "t3": (80, 200), "t4": (5, 12),
    "ferritin": {"M": (30, 400), "F": (13, 150)}, "iron": {"M": (65, 175), "F": (60, 170)}, "tibc": (250, 450),
    "vitamin_d": (30, 100), "vitamin_b12": (200, 900),
}

# absolute severity thresholds beyond the range (inclusive, so a value exactly on a line escalates)
BANDS = {
    "hemoglobin": {"low": dict(moderate=10.0, marked=8.0, critical=7.0), "high": dict(marked=18.5, critical=20.0)},
    "platelets": {"low": dict(moderate=100, marked=50, critical=20), "high": dict(marked=700, critical=1000)},
    "wbc": {"low": dict(moderate=3.0, marked=2.5, critical=2.0), "high": dict(moderate=15, marked=25, critical=30)},
    "glucose_fasting": {"low": dict(moderate=60, marked=54, critical=50), "high": dict(moderate=126, marked=250, critical=400)},
    "glucose_pp": {"low": dict(moderate=60, marked=54, critical=50), "high": dict(moderate=200, marked=300, critical=400)},
    "glucose_random": {"low": dict(moderate=60, marked=54, critical=50), "high": dict(moderate=200, marked=300, critical=400)},
    "hba1c": {"high": dict(moderate=8.0, marked=10.0)},
    "cholesterol_total": {"high": dict(moderate=240, marked=300)}, "ldl": {"high": dict(moderate=160, marked=190)},
    "triglycerides": {"high": dict(moderate=200, marked=500, critical=1000)},
    "creatinine": {"high": dict(moderate=1.5, marked=3.0, critical=6.0)}, "urea": {"high": dict(moderate=60, marked=120)},
    "egfr": {"low": dict(moderate=60, marked=30)},
    "sodium": {"low": dict(moderate=130, marked=125, critical=120), "high": dict(moderate=150, marked=155, critical=160)},
    "potassium": {"low": dict(moderate=3.3, marked=3.0, critical=2.8), "high": dict(moderate=5.5, critical=6.0)},
    "calcium": {"low": dict(moderate=8.0, marked=7.0, critical=6.5), "high": dict(moderate=11.5, marked=12.5, critical=13.0)},
    "alt": {"high": dict(moderate=168, marked=280, critical=1000)}, "ast": {"high": dict(moderate=120, marked=200, critical=1000)},
    "bilirubin_total": {"high": dict(moderate=3.0, marked=6.0, critical=15.0)},
    "tsh": {"high": dict(moderate=10, marked=25), "low": dict(moderate=0.1, marked=0.01)},
    "ft4": {"low": dict(moderate=0.5, marked=0.3), "high": dict(moderate=2.5, marked=4.0)},
    "uric_acid": {"high": dict(moderate=9.0, marked=12.0)}, "ferritin": {"low": dict(moderate=10, marked=5)},
    "vitamin_d": {"low": dict(moderate=20, marked=10)}, "vitamin_b12": {"low": dict(moderate=200, marked=150)},
}
SEVERITY_LEVEL = {"normal": 0, "borderline": 0, "mild": 1, "moderate": 1, "marked": 2, "critical": 3}
SEVERITY_ORDER = ["normal", "borderline", "mild", "moderate", "marked", "critical"]


def standard_range(key, sex):
    """(low, high, note). With unknown sex the wider of the two ranges is used."""
    r = RANGES.get(key)
    if r is None:
        return None, None, "no standard range"
    if isinstance(r, dict):
        if sex in ("male", "female"):
            lo, hi = r["M" if sex == "male" else "F"]
            return lo, hi, f"standard adult range for {sex}s"
        (a, b), (c, d) = r["M"], r["F"]
        lo = None if a is None or c is None else min(a, c)
        hi = None if b is None or d is None else max(b, d)
        return lo, hi, "sex not known: the wider adult range was used"
    return r[0], r[1], "standard adult range"


def _severity(key, direction, value, limit):
    """How far outside the range is the value? Returns (severity, reason or None)."""
    bands = BANDS.get(key, {}).get(direction)
    if bands:
        hit = "mild"
        for name in ("moderate", "marked", "critical"):
            t = bands.get(name)
            if t is None:
                continue
            if (direction == "high" and value >= t) or (direction == "low" and value <= t):
                hit = name
        if hit == "critical":
            t = bands["critical"]
            return hit, f"{'at or above' if direction == 'high' else 'at or below'} the alert level of {t:g}"
        return hit, None
    dev = abs(value - limit) / abs(limit) * 100 if limit else 100.0
    return ("borderline" if dev <= 5 else "mild" if dev < 20 else "moderate" if dev < 50 else "marked"), None


def interpret(result, sex=None, age=None):
    """Adds the meaning of one lab value: status, severity, level, range used."""
    key, value = result["test_key"], result["value"]
    out = {"status": "not_assessed", "severity": None, "level": None, "range_used": None, "standard_range": None, "alert_reason": None, "notes": []}
    printed = result.get("reference")
    slo, shi, snote = standard_range(key, sex)
    out["standard_range"] = {"low": slo, "high": shi, "note": snote}
    if result.get("unit_status") == "unexpected":
        out["notes"].append("The unit differs from the usual one, so this value was not assessed. Check the original.")
        return out
    if result.get("value_qualifier"):
        out["notes"].append(f"The report gives '{result['value_qualifier']}{value:g}', a limit and not an exact value, so it was not assessed.")
        return out
    if printed and printed["kind"] in ("between", "less", "more"):
        lo, hi, source = printed["low"], printed["high"], "printed"
        out["notes"].append("The report's own reference range was used.")
        for name, mine, std in (("low", lo, slo), ("high", hi, shi)):
            if mine is not None and std not in (None, 0) and abs(mine - std) / abs(std) > 0.30:
                out["notes"].append(f"The printed {name} limit ({mine:g}) differs a lot from the usual adult value ({std:g}). Check it was read correctly.")
    elif slo is not None or shi is not None:
        if age is not None and age < 18:
            out["notes"].append("Standard ranges here are for adults only, and this patient is under 18. Not assessed.")
            return out
        lo, hi, source = slo, shi, "standard"
        out["notes"].append(f"No printed range was read, so the {snote} was used.")
    else:
        out["notes"].append("No range is available for this test, so it was not assessed.")
        return out

    out["range_used"] = {"low": lo, "high": hi, "source": source}
    direction = "low" if lo is not None and value < lo else "high" if hi is not None and value > hi else None
    if direction is None:
        out.update(status="normal", severity="normal", level=0)
        # a value inside the printed range can still be at an alert level (e.g. printed range copied wrongly)
        for d in ("low", "high"):
            t = BANDS.get(key, {}).get(d, {}).get("critical")
            if t is not None and ((d == "high" and value >= t) or (d == "low" and value <= t)):
                out.update(status=d, severity="critical", level=3, alert_reason=f"at the alert level of {t:g} even though it is inside the range used")
        return out
    limit = lo if direction == "low" else hi
    severity, reason = _severity(key, direction, value, limit)
    dev = abs(value - limit) / abs(limit) * 100 if limit else None
    out.update(status=direction, severity=severity, level=SEVERITY_LEVEL[severity], alert_reason=reason,
               deviation_percent=round(dev, 1) if dev is not None else None)
    return out


# ------------------------------------------------------------------ combinations
def _val(items, key):
    r = items.get(key)
    return r["value"] if r and r["interpretation"]["status"] != "not_assessed" else None


def _stat(items, key):
    r = items.get(key)
    return r["interpretation"]["status"] if r else None


def find_patterns(items):
    """Combinations of results that mean more together than alone."""
    found = []

    def add(pid, label, level, keys, text):
        found.append({"id": pid, "label": label, "level": level, "tests": [items[k]["test"] for k in keys if k in items], "text": text})

    egfr, k = _val(items, "egfr"), _val(items, "potassium")
    kidney_marker = _stat(items, "creatinine") == "high" or (egfr is not None and egfr < 60)
    if kidney_marker and (_stat(items, "urea") == "high" or egfr is not None):
        lvl = 2 if (egfr is not None and egfr < 30) or (items.get("creatinine") and items["creatinine"]["interpretation"]["level"] >= 2) else 1
        add("kidney_impairment", "Possible reduced kidney function", lvl, ["creatinine", "urea", "egfr"],
            "Creatinine, urea and/or eGFR together suggest the kidneys are not filtering well.")
    if k is not None and k >= 5.5 and kidney_marker:
        add("hyperkalaemia_kidney", "High potassium together with reduced kidney function", 3, ["potassium", "creatinine", "egfr"],
            "When the kidneys are weak, potassium can build up and affect the heart rhythm.")
    low_counts = [x for x in ("hemoglobin", "wbc", "platelets") if _stat(items, x) == "low"]
    if len(low_counts) >= 2:
        add("low_counts", "More than one blood count is low", 2, low_counts, "Several blood cell types are low at the same time.")
    if _stat(items, "hemoglobin") == "low" and (_stat(items, "ferritin") == "low" or (_stat(items, "mcv") == "low" and _stat(items, "mch") == "low")):
        add("iron_deficiency", "Pattern of iron deficiency anaemia", 1, ["hemoglobin", "mcv", "mch", "ferritin", "iron"],
            "Low haemoglobin with small red cells and/or low iron stores is typical of iron deficiency.")
    a1c, fg = _val(items, "hba1c"), _val(items, "glucose_fasting")
    pp = max([v for v in (_val(items, "glucose_pp"), _val(items, "glucose_random")) if v is not None], default=None)
    if (a1c is not None and a1c >= 6.5) or (fg is not None and fg >= 126) or (pp is not None and pp >= 200):
        lvl = 2 if (a1c is not None and a1c >= 10) or (fg is not None and fg >= 300) or (pp is not None and pp >= 300) else 1
        add("diabetes_range", "Blood sugar in the diabetes range", lvl, ["hba1c", "glucose_fasting", "glucose_pp", "glucose_random"],
            "HbA1c of 6.5% or more, fasting glucose of 126 mg/dL or more, or glucose of 200 mg/dL or more is in the diabetes range.")
    elif (a1c is not None and 5.7 <= a1c < 6.5) or (fg is not None and 100 <= fg < 126):
        add("prediabetes", "Blood sugar in the pre-diabetes range", 1, ["hba1c", "glucose_fasting"], "Blood sugar is above normal but below the diabetes range.")
    tsh, ft4 = _stat(items, "tsh"), _stat(items, "ft4")
    if tsh == "high":
        add("hypothyroid", "Pattern of an underactive thyroid" if ft4 == "low" else "Raised TSH", 1, ["tsh", "ft4"],
            "A high TSH with a low free T4 suggests an underactive thyroid." if ft4 == "low" else "A raised TSH can be an early sign of an underactive thyroid.")
    if tsh == "low" and ft4 == "high":
        add("hyperthyroid", "Pattern of an overactive thyroid", 2, ["tsh", "ft4"], "A low TSH with a high free T4 suggests an overactive thyroid.")
    if _stat(items, "ldl") == "high" and _stat(items, "triglycerides") == "high":
        add("mixed_lipids", "Both LDL cholesterol and triglycerides are high", 1, ["ldl", "triglycerides", "cholesterol_total", "hdl"],
            "Raised blood fats increase the long-term risk of heart disease.")
    for enzyme, uln in (("alt", 56), ("ast", 40)):
        v = _val(items, enzyme)
        if v is not None and v > 3 * uln:
            add("liver_enzymes", "Liver enzymes are well above normal", 2, ["alt", "ast"], "Liver enzymes more than three times the upper limit can point to liver injury.")
            break
    return found


# ------------------------------------------------------------------ whole report
def assess(lab_results, patient=None, document=None):
    """Adds result['interpretation'] to every result and returns the report-level triage."""
    patient = patient or {}
    document = document or {}
    sex = patient.get("sex") or document.get("sex")
    age = patient.get("age") or document.get("age")
    items = {}
    for r in lab_results:
        r["interpretation"] = interpret(r, sex, age)
        if r["test_key"] not in items or r["interpretation"]["level"] is not None:
            items[r["test_key"]] = r

    def worst(rs):
        return max([r["interpretation"]["level"] or 0 for r in rs], default=0)

    patterns = find_patterns(items)
    base = max(worst(lab_results), max([p["level"] for p in patterns], default=0))

    # what could the level be if an uncertain value had been read differently?
    possible = base
    for r in lab_results:
        if r.get("value_alternative") is not None and r["needs_review"]:
            alt = dict(r, value=r["value_alternative"])
            possible = max(possible, interpret(alt, sex, age)["level"] or 0)
    uncertain = [r for r in lab_results if r["needs_review"]]
    unassessed = [r for r in lab_results if r["interpretation"]["status"] == "not_assessed"]

    reasons = []
    for r in sorted(lab_results, key=lambda r: -(r["interpretation"]["level"] or 0)):
        i = r["interpretation"]
        if i["status"] in ("low", "high") and i["severity"] not in ("normal", "borderline"):
            ru = i["range_used"]
            if ru and ru["source"] == "printed" and r.get("reference"):
                import re as _re
                rng = _re.sub(r"(?<=[A-Za-z])(?=\d)", " ", r["reference"]["text"])
            elif ru:
                rng = (f"{ru['low']:g}-{ru['high']:g}" if ru["low"] is not None and ru["high"] is not None
                       else f"more than {ru['low']:g}" if ru["low"] is not None else f"less than {ru['high']:g}")
            else:
                rng = ""
            unit = r["unit"] if r.get("unit_status") in ("ok", "unexpected") and r["unit"] else "[unit unclear]"
            text = f"{r['test']} {r['value']:g} {unit} is {i['status']} ({i['severity']}; range {rng})"
            if i["alert_reason"]:
                text += f", {i['alert_reason']}"
            reasons.append({"level": i["level"], "text": text, "test": r["test"]})
    for p in sorted(patterns, key=lambda p: -p["level"]):
        reasons.append({"level": p["level"], "text": p["label"] + ": " + p["text"], "test": None})

    label, timeframe, advice = LEVEL_INFO[LEVELS[base]]
    triage = {
        "level": LEVELS[base], "level_number": base, "label": label, "timeframe": timeframe, "advice": advice,
        "reasons": reasons, "patterns": patterns,
        "counts": {"results": len(lab_results), "normal": sum(1 for r in lab_results if r["interpretation"]["status"] == "normal"),
                   "abnormal": sum(1 for r in lab_results if r["interpretation"]["status"] in ("low", "high")),
                   "critical": sum(1 for r in lab_results if r["interpretation"]["severity"] == "critical"), "not_assessed": len(unassessed)},
        "possible_level": LEVELS[possible],
        "provisional": bool(uncertain),
        "needs_review_before_advice": bool(uncertain) and (possible > base or base >= 2 or len(unassessed) > 0 and base >= 1),
        "context": {"sex": sex, "age": age},
    }
    if uncertain:
        triage["review_note"] = (f"{len(uncertain)} value(s) were flagged for checking. Confirm them against the original before relying on this assessment."
                                 + (f" If an uncertain value was misread, the level could be '{LEVEL_INFO[LEVELS[possible]][0]}'." if possible > base else ""))
    if not lab_results:
        triage.update(level=None, label="Cannot assess", timeframe=None, advice="No lab values could be read.")
    return triage
