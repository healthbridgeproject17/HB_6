import argparse
import json
import sys

from .extract import ExtractionError, extract_document
from .parse import analyze_document


def show_report(args):
    from .summary import to_text
    try:
        r = analyze_document(open(args.file, "rb").read(), engine=args.engine)
    except ExtractionError as exc:
        print("Cannot read file:", exc)
        sys.exit(1)
    print(to_text(r["report"]))


def show_analysis(args):
    try:
        r = analyze_document(open(args.file, "rb").read(), engine=args.engine)
    except ExtractionError as exc:
        print("Cannot read file:", exc)
        sys.exit(1)
    if args.json:
        print(json.dumps({k: v for k, v in r.items() if k != "extraction"}, indent=2))
        return
    s = r["summary"]
    print(f"{args.file}: {r['document_type']} - {s['items']} item(s), {s['needs_review']} need review, {s['unrecognized_rows']} unrecognised row(s)")
    p = r["patient_on_document"]
    print(f"Patient on document: {p['name_as_printed']}  age {p['age']}  sex {p['sex']}")
    for x in r["lab_results"]:
        flag = x["printed_flag"] or "-"
        mark = "  REVIEW" if x["needs_review"] else ""
        i = x.get("interpretation") or {}
        meaning = f"{(i.get('status') or '?').upper():12} {(i.get('severity') or ''):9}"
        print(f"  {x['test']:24} {x['value']:>7g} {x['unit'] or '?':14} range {x['reference']['text'] if x['reference'] else '?':14} {meaning} conf {x['confidence']:.0%}{mark}")
        for issue in x["issues"]:
            print("      !", issue)
    for x in r["prescription_items"]:
        f = lambda n: (x[n]["printed"] or "NOT DETECTED")  # noqa: E731
        print(f"  {f('medicine')} | strength {f('strength')} | dose {f('dose')} | route {f('route')} | frequency {f('frequency')} | duration {f('duration')}" + ("  REVIEW" if x["needs_review"] else ""))
        for issue in x["issues"]:
            print("      !", issue)
    t = r.get("triage")
    if t:
        print(f"\n  ASSESSMENT: {t['label'].upper()}" + (f" ({t['timeframe']})" if t["timeframe"] else "") + ("  [PROVISIONAL: values need checking]" if t["provisional"] else ""))
        for reason in t["reasons"]:
            print("   -", reason["text"])
        print("   ", t["advice"])
    for u in r["unrecognized_rows"]:
        print("  UNRECOGNISED ROW:", u["name_as_printed"], u["value"])
    for w in r["warnings"]:
        print("WARNING:", w)
    print(r["disclaimer"])


def main():
    ap = argparse.ArgumentParser(prog="medai", description="Read text from a medical PDF or image.")
    ap.add_argument("file")
    ap.add_argument("--engine", default="auto", choices=["auto", "rapidocr", "tesseract"])
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--report", action="store_true", help="print the plain-language report a patient would read")
    ap.add_argument("--analyze", action="store_true", help="structure the result (lab values / prescription fields) and run the checks")
    args = ap.parse_args()
    if args.report:
        return show_report(args)
    if args.analyze:
        return show_analysis(args)
    try:
        result = extract_document(open(args.file, "rb").read(), engine=args.engine)
    except ExtractionError as exc:
        print("Cannot read file:", exc)
        sys.exit(1)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"{args.file}: {result['kind']}, {result['page_count']} page(s), {result['elapsed_seconds']}s, mean confidence {result['mean_confidence']:.0%}")
    for p in result["pages"]:
        print(f"--- page {p['page']}: {p['method']}{' (' + p['engine'] + ')' if p['engine'] else ''}, quality {p['quality']['label']}")
        for line in p["lines"]:
            mark = "" if line["confidence"] >= 0.9 else f"   <-- confidence {line['confidence']:.0%}"
            print("  ", line["text"], mark)
    for w in result["warnings"]:
        print("WARNING:", w)


main()
