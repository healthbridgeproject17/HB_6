"""Turns lab-report text into structured results, each with a confidence, a
link back to its source line, and checks that catch reading mistakes."""
import re

from .catalog import TESTS, match_test, normalize_unit, squash_name
from .layout import group_rows

NUM = r"\d+(?:[.,]\d+)?"
RE_VALUE = re.compile(rf"^([<>]?)\s*({NUM})$")
RE_VALUE_UNIT = re.compile(rf"^([<>]?\s*{NUM})\s*([A-Za-zµμ%/][A-Za-zµμ%/0-9.^² ]*)$")
RE_FLAG = re.compile(r"^(critical|crit)?\s*(h|l|hh|ll|high|low)\*?$", re.I)
RE_TRAILING_FLAG = re.compile(r"^(.*\d)\s+((?:critical\s*)?(?:h|l|high|low))$", re.I)


def _to_float(text):
    return float(text.replace(",", "."))


def parse_range(text):
    """'12.0 - 15.5' / 'less than 200' / '<5.7' / 'more than 40' -> dict or None."""
    t = re.sub(r"\s+", "", (text or "").lower())
    m = re.match(rf"^({NUM})[-–—to]+({NUM})$", t)
    if m:
        return {"kind": "between", "low": _to_float(m.group(1)), "high": _to_float(m.group(2)), "text": text.strip()}
    m = re.match(rf"^(?:lessthan|<|upto|below|upper|max)[:]?({NUM})$", t)
    if m:
        return {"kind": "less", "low": None, "high": _to_float(m.group(1)), "text": text.strip()}
    m = re.match(rf"^(?:morethan|greaterthan|>|above|min)[:]?({NUM})$", t)
    if m:
        return {"kind": "more", "low": _to_float(m.group(1)), "high": None, "text": text.strip()}
    return None


def computed_flag(value, rng):
    if not rng:
        return None
    if rng["kind"] == "between":
        return "L" if value < rng["low"] else "H" if value > rng["high"] else None
    if rng["kind"] == "less":
        return "H" if value >= rng["high"] else None
    return "L" if value <= rng["low"] else None


def parse_flag(text):
    m = RE_FLAG.match(text.strip())
    if not m:
        return None
    letter = "H" if m.group(2).lower().startswith("h") else "L"
    return {"flag": letter, "critical": bool(m.group(1))}


def _split_cells(cells):
    """Split cells where the OCR glued things together ('9.8 g/dL', '12.0-15.5 L')."""
    out = []
    for c in cells:
        text = c["text"].strip()
        m = RE_TRAILING_FLAG.match(text)
        if m and parse_range(m.group(1)):
            out.append({**c, "text": m.group(1).strip()})
            out.append({**c, "text": m.group(2).strip()})
            continue
        m = RE_VALUE_UNIT.match(text)
        if m and not parse_range(text):
            out.append({**c, "text": m.group(1).strip()})
            out.append({**c, "text": m.group(2).strip()})
            continue
        out.append(c)
    return out


def _union(cells):
    return [min(c["bbox"][0] for c in cells), min(c["bbox"][1] for c in cells), max(c["bbox"][2] for c in cells), max(c["bbox"][3] for c in cells)]


def parse_lab_rows(pages):
    results, unrecognized = [], []
    for page in pages:
        for row in group_rows(page["lines"]):
            cells = _split_cells(row["cells"])
            if len(cells) < 2:
                continue
            name_cell = cells[0]
            if RE_VALUE.match(name_cell["text"]) or len(squash_name(name_cell["text"])) < 2:
                continue
            value_cell = unit_cell = range_cell = flag_cell = None
            for c in cells[1:]:
                t = c["text"].strip()
                if value_cell is None and RE_VALUE.match(t):
                    value_cell = c
                elif range_cell is None and parse_range(t):
                    range_cell = c
                elif flag_cell is None and parse_flag(t):
                    flag_cell = c
                elif unit_cell is None and len(t) <= 22 and not parse_range(t) and not RE_VALUE.match(t):
                    unit_cell = c
            if value_cell is None or (unit_cell is None and range_cell is None):
                continue  # not a result row (header, note, patient line...)

            key, how = match_test(name_cell["text"])
            used = [name_cell, value_cell] + [c for c in (unit_cell, range_cell, flag_cell) if c]
            raw = RE_VALUE.match(value_cell["text"])
            value = _to_float(raw.group(2))
            qualifier = raw.group(1) or None
            confidence = min(c["confidence"] for c in used)
            disagreements, value_alt, range_alt = [], None, None
            alt = value_cell.get("alt_text")
            alt_match = RE_VALUE.match(alt.strip()) if alt else None
            if alt and not alt_match:
                disagreements.append(f"A second reading of the value gave '{alt}', which is not a number. Check the original.")
            elif alt_match and _to_float(alt_match.group(2)) != value:
                value_alt = _to_float(alt_match.group(2))
                disagreements.append(f"Two readings of the value disagree ({value:g} and {value_alt:g}). Check the original.")
                if value_cell.get("alt_confidence", 0) > value_cell["confidence"]:
                    disagreements.append(f"The more confident re-read ({value_alt:g}) is shown instead of {value:g}.")
                    value, value_alt = value_alt, value
                    confidence = min(confidence, value_cell["alt_confidence"])
            source = {"page": page["page"], "bbox": [round(v, 1) for v in _union(used)], "text": row["text"]}

            if key is None:
                unrecognized.append({"name_as_printed": name_cell["text"], "value": value, "unit_as_printed": unit_cell["text"] if unit_cell else None,
                                     "confidence": round(confidence, 3), "source": source,
                                     "issues": ["Test name not recognised. Review this row manually."]})
                continue

            test = TESTS[key]
            issues = []
            if how == "approximate":
                issues.append(f"Test name '{name_cell['text']}' matched approximately to {test['label']}. Check the name.")

            unit, unit_status = None, "missing"
            if unit_cell:
                unit = normalize_unit(unit_cell["text"])
                if unit is None:
                    unit_status = "uncertain"
                    issues.append(f"Unit '{unit_cell['text']}' not recognised (expected {test['unit']}). Check the original.")
                elif normalize_unit(test["unit"]) != unit and test["unit"] != unit:
                    unit_status = "unexpected"
                    issues.append(f"Unit {unit} differs from the usual {test['unit']}. The value may need converting.")
                else:
                    unit_status = "ok"
            else:
                issues.append(f"Unit not detected (usual unit: {test['unit']}).")

            lo, hi = test["plausible"]
            if not lo <= value <= hi:
                issues.append(f"Value {value:g} is outside what is physically plausible for {test['label']} ({lo:g}-{hi:g}). It was probably misread.")

            rng = parse_range(range_cell["text"]) if range_cell else None
            if rng is None:
                issues.append("Reference range not detected.")
            if range_cell and range_cell.get("alt_text"):
                alt_rng = parse_range(range_cell["alt_text"])
                if alt_rng is None or (alt_rng["low"], alt_rng["high"]) != (rng["low"], rng["high"]) if rng else True:
                    range_alt = range_cell["alt_text"]
                    issues.append(f"Two readings of the reference range disagree ('{range_cell['text']}' and '{range_cell['alt_text']}'). Check the original.")
            issues.extend(disagreements)
            printed = parse_flag(flag_cell["text"]) if flag_cell else None

            if confidence < 0.85:
                issues.append(f"Low reading confidence ({confidence:.0%}). Check against the original.")

            results.append({
                "test_key": key, "test": test["label"], "group": test["group"], "name_as_printed": name_cell["text"],
                "value": value, "value_qualifier": qualifier, "unit": unit or (unit_cell["text"] if unit_cell else None), "unit_status": unit_status,
                "reference": rng, "printed_flag": printed["flag"] if printed else None, "printed_critical": bool(printed and printed["critical"]),
                "confidence": round(confidence, 3), "source": source, "issues": issues,
                "value_alternative": value_alt, "reference_alternative": range_alt,
            })

    # does this report print flags at all? then a missing/different flag is meaningful
    flags_used = any(r["printed_flag"] for r in results)
    for r in results:
        if r["reference"] and not qualifier_present(r):
            expected = computed_flag(r["value"], r["reference"])
            if flags_used and expected != r["printed_flag"]:
                r["issues"].append(
                    f"The report's flag ({r['printed_flag'] or 'none'}) disagrees with the value against its own range "
                    f"({expected or 'normal'}). The value or the range was probably misread.")
        r["needs_review"] = bool(r["issues"])
    seen = {}
    for r in results:
        seen.setdefault(r["test_key"], []).append(r)
    for rows in seen.values():
        if len(rows) > 1 and len({x["value"] for x in rows}) > 1:
            for r in rows:
                r["issues"].append("The same test appears more than once with different values.")
                r["needs_review"] = True
    return results, unrecognized


def qualifier_present(r):
    return bool(r.get("value_qualifier"))
