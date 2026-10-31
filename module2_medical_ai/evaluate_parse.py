"""Measures the STRUCTURED results against the known answers, and counts
'silent errors': a wrong field that was NOT flagged for review. That number is
the one that matters for safety.
Run:  python evaluate_parse.py [--stress]"""
import argparse
import json
import os
import re

from evaluate import degrade
from medai import analyze_document
from medai.catalog import match_test, normalize_unit, squash_name
from medai.lab_parser import parse_flag, parse_range

DOCS = os.path.join(os.path.dirname(__file__), "..", "demo_documents")


def lab_compare(truth, result):
    fields = errors = silent = missed = 0
    got = {r["test_key"]: r for r in result["lab_results"]}
    for exp in truth["rows"]:
        key, _ = match_test(exp["test"])
        r = got.get(key)
        if r is None:
            missed += 1
            continue
        want_flag = parse_flag(exp["flag"])["flag"] if exp["flag"] else None
        want_rng = parse_range(exp["reference"])
        checks = [
            float(exp["value"]) == r["value"],
            normalize_unit(exp["unit"]) == normalize_unit(r["unit"] or "") or exp["unit"] == r["unit"],
            want_flag == r["printed_flag"],
            bool(r["reference"]) and bool(want_rng) and (want_rng["low"], want_rng["high"]) == (r["reference"]["low"], r["reference"]["high"]),
        ]
        fields += len(checks)
        bad = checks.count(False)
        errors += bad
        if bad and not r["needs_review"]:
            silent += bad
    return fields, errors, silent, missed


def rx_compare(truth, result):
    fields = errors = silent = missed = 0
    items = result["prescription_items"]
    for exp in truth["rows"]:
        item = next((i for i in items if squash_name(i["medicine"]["value"] or "") == squash_name(exp["medicine"])), None)
        if item is None:
            missed += 1
            continue
        bad = 0
        for f in ("strength", "dose", "route", "frequency", "duration"):
            fields += 1
            if squash_name(item[f]["printed"] or "") != squash_name(exp[f]):
                bad += 1
        errors += bad
        if bad and not item["needs_review"]:
            silent += bad
    return fields, errors, silent, missed


def run(variant=None, show=True):
    truth = json.load(open(os.path.join(DOCS, "ground_truth.json")))
    tot = [0, 0, 0, 0]
    flagged = items = 0
    for name, t in truth.items():
        if variant and not name.endswith(".jpg"):
            continue
        data = open(os.path.join(DOCS, name), "rb").read()
        if variant:
            data = degrade(data, variant)
        res = analyze_document(data)
        f, e, s, m = (lab_compare if t["type"] == "lab_report" else rx_compare)(t, res)
        for i, v in enumerate((f, e, s, m)):
            tot[i] += v
        flagged += res["summary"]["needs_review"]
        items += res["summary"]["items"]
        if show and not variant:
            print(f"{name:46} type={res['document_type']:12} fields {f - e}/{f} ok  silent errors {s}  missed rows {m}  flagged {res['summary']['needs_review']}/{res['summary']['items']}")
    f, e, s, m = tot
    label = variant or "demo documents"
    print(f"{label:22} fields correct {f - e}/{f} ({(f - e) / max(f, 1):.1%}) | SILENT ERRORS {s} | rows missed {m} | flagged for review {flagged}/{items}")
    return {"fields": f, "errors": e, "silent": s, "missed": m, "flagged": flagged, "items": items}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stress", action="store_true")
    a = ap.parse_args()
    if a.stress:
        for v in ("half-resolution", "tilted 4 degrees", "heavy JPEG (q25)", "shadow + blur"):
            run(v)
    else:
        run()
