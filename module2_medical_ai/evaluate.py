"""Measures how well the pipeline reads the demo documents.
Run:  python evaluate.py [--engine rapidocr|tesseract|auto]
A lab row counts as correct when the row contains the right test name AND the
right result value; a prescription row when it has the medicine AND strength."""
import argparse
import json
import os
import re
import time

from medai import extract_document
from medai.layout import group_rows, squash

DOCS = os.path.join(os.path.dirname(__file__), "..", "demo_documents")


def number_tokens(text):
    return set(re.findall(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])", text))


def degrade(data, kind):
    """Make a harder version of a scan: smaller, tilted, compressed or shadowed."""
    import io

    import numpy as np
    from PIL import Image, ImageFilter
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if kind == "half-resolution":
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    elif kind == "tilted 4 degrees":
        img = img.rotate(4, resample=Image.BICUBIC, expand=True, fillcolor=(235, 235, 235))
    elif kind == "heavy JPEG (q25)":
        pass
    elif kind == "shadow + blur":
        a = np.asarray(img, dtype=np.float32)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        a *= (1 - 0.45 * (xx / w))[..., None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=25 if kind == "heavy JPEG (q25)" else 80)
    return out.getvalue()


def score(path, truth, engine, degrade_kind=None):
    data = open(path, "rb").read()
    if degrade_kind:
        data = degrade(data, degrade_kind)
    result = extract_document(data, engine=engine)
    lines = [l for p in result["pages"] for l in p["lines"]]
    rows = group_rows(lines)
    ok, missed = 0, []
    for exp in truth["rows"]:
        if truth["type"] == "lab_report":
            key, want = squash(exp["test"]), exp["value"]
            hit = any(key in squash(r["text"]) and want in number_tokens(r["text"]) for r in rows)
            label = f"{exp['test']} = {exp['value']}"
        else:
            key, want = squash(exp["medicine"]), squash(exp["strength"])
            hit = any(key in squash(r["text"]) and want in squash(r["text"]) for r in rows)
            label = f"{exp['medicine']} {exp['strength']}"
        ok += hit
        if not hit:
            missed.append(label)
    return ok, len(truth["rows"]), missed, result


def stress(engine):
    truth = json.load(open(os.path.join(DOCS, "ground_truth.json")))
    scans = {k: v for k, v in truth.items() if k.endswith(".jpg")}
    print("Harder versions of the scans and photos (tests how it copes with worse pictures):")
    for kind in ("half-resolution", "tilted 4 degrees", "heavy JPEG (q25)", "shadow + blur"):
        ok = n = 0
        for name, t in scans.items():
            a, b, _, _ = score(os.path.join(DOCS, name), t, engine, kind)
            ok, n = ok + a, n + b
        print(f"  {kind:20} {ok}/{n} rows correct = {ok / n:.0%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="auto")
    ap.add_argument("--stress", action="store_true", help="also test degraded pictures")
    args = ap.parse_args()
    if args.stress:
        stress(args.engine)
        return
    truth = json.load(open(os.path.join(DOCS, "ground_truth.json")))
    total_ok = total = 0
    print(f"{'document':46} {'kind':8} {'rows ok':8} {'conf':>6} {'time':>6}  quality")
    for name, t in truth.items():
        ok, n, missed, res = score(os.path.join(DOCS, name), t, args.engine)
        total_ok, total = total_ok + ok, total + n
        q = res["pages"][0]["quality"]["label"]
        print(f"{name:46} {res['kind']:8} {ok}/{n:<6} {res['mean_confidence']:>6.0%} {res['elapsed_seconds']:>5.1f}s  {q}" + (f"   missed: {missed}" if missed else ""))
    print(f"\nOVERALL ({args.engine}): {total_ok}/{total} rows read correctly = {total_ok / total:.0%}")


if __name__ == "__main__":
    main()
