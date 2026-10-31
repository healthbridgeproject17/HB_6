"""Rebuild table rows from text pieces using their positions."""
import re
import statistics


def group_rows(lines):
    """lines: dicts with text/bbox/confidence. Pieces whose vertical centres are
    close belong to one table row. Returns rows sorted top to bottom, each row's
    cells sorted left to right."""
    items = [l for l in lines if l.get("text", "").strip()]
    if not items:
        return []
    heights = [l["bbox"][3] - l["bbox"][1] for l in items]
    tol = 0.55 * statistics.median(heights)
    items.sort(key=lambda l: (l["bbox"][1] + l["bbox"][3]) / 2)
    rows, current, current_y = [], [], None
    for l in items:
        cy = (l["bbox"][1] + l["bbox"][3]) / 2
        if current and abs(cy - current_y) > tol:
            rows.append(current)
            current = []
        current.append(l)
        current_y = statistics.mean((x["bbox"][1] + x["bbox"][3]) / 2 for x in current)
    rows.append(current)
    out = []
    for r in rows:
        r.sort(key=lambda l: l["bbox"][0])
        out.append({"cells": r, "text": " ".join(c["text"] for c in r), "y": round(statistics.mean((c["bbox"][1] + c["bbox"][3]) / 2 for c in r), 1),
                    "min_confidence": min(c["confidence"] for c in r)})
    return out


def squash(text):
    """Lower-case with spaces/punctuation removed: lets 'Serum potassium' match
    'Serumpotassium' (some OCR engines drop spaces)."""
    return re.sub(r"[^a-z0-9.%/]", "", text.lower())
