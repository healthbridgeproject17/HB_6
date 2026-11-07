"""Turns an uploaded PDF or image into text with positions and confidence.

Digital PDFs are read directly (exact text, no OCR). Scanned pages and photos
are cleaned up and read with OCR. Every page reports HOW it was read and how
sure we are, so later steps can flag anything uncertain instead of guessing."""
import re
import time

import cv2
import pymupdf  # PyMuPDF
import numpy as np

from .imaging import load_image, prepare_for_ocr
from .ocr import run_ocr

MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 20
MIN_TEXT_CHARS = 25     # fewer characters than this on a PDF page = treat as scanned
OCR_DPI = 200


RE_NUMERIC_CELL = re.compile(r"^[<>]?\s*\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|μg|g|ml|iu|%|units?)?$", re.I)  # single numbers and strengths; ranges are guarded by the flag check instead


def _norm_number(text):
    return re.sub(r"\s+", "", text.lower()).replace(",", ".").replace("–", "-").replace("—", "-")


def verify_numeric_cells(gray, lines, engine_used):
    """Numbers are where a misread hurts most (9.8 read as 86). Every number
    cell is read a second time from a tight, enlarged crop; if the two readings
    differ, the second one is attached so the parser can flag it."""
    for line in lines:
        if not RE_NUMERIC_CELL.match(line.text.strip()):
            continue
        x0, y0, x1, y1 = (int(v) for v in line.bbox)
        pad = max(8, int(0.4 * (y1 - y0)))
        crop = gray[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
        if crop.size == 0:
            continue
        big = cv2.copyMakeBorder(cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC), 40, 40, 40, 40, cv2.BORDER_REPLICATE)
        try:
            _, again = run_ocr(big, engine_used)
        except Exception:
            continue
        if not again:
            continue
        text = " ".join(l.text for l in again).strip()
        if _norm_number(text) != _norm_number(line.text):
            line.alt_text, line.alt_confidence = text, min(l.confidence for l in again)


class ExtractionError(ValueError):
    """The file cannot be read (wrong type, damaged, protected, too big)."""


def detect_kind(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return "image"
    raise ExtractionError("Unsupported file. Use a PDF, JPG, PNG or WEBP.")


def _pdf_lines(page):
    """Text lines of a digital PDF page with their positions (PDF points)."""
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                lines.append({"text": text, "bbox": [round(v, 1) for v in line["bbox"]], "confidence": 1.0})
    lines.sort(key=lambda l: (round(l["bbox"][1] / 4), l["bbox"][0]))
    return lines


def _ocr_page(gray_or_bgr_source, engine):
    gray, notes, quality = prepare_for_ocr(gray_or_bgr_source)
    used, lines = run_ocr(gray, engine)
    verify_numeric_cells(gray, lines, used)
    return used, lines, gray, notes, quality


def _finish_ocr_page(number, lines, gray, notes, quality, engine_used):
    confs = [l.confidence for l in lines]
    mean = float(np.mean(confs)) if confs else 0.0
    warnings = []
    if not lines:
        warnings.append("No text could be read on this page.")
    if quality["issues"]:
        warnings.append("Picture quality: " + ", ".join(quality["issues"]) + ". Read values carefully.")
    if 0 < len(lines) < 6:
        warnings.append(f"Only {len(lines)} line(s) of text could be read. The picture may be too blurry, or this may not be a document.")
    if lines and mean < 0.80:
        warnings.append(f"Low reading confidence ({mean:.0%}). Check every value against the original.")
    label = "poor" if (len(lines) < 6 or mean < 0.70 or len(quality["issues"]) >= 2) else ("fair" if (mean < 0.88 or quality["issues"]) else "good")
    return {
        "page": number, "method": "ocr", "engine": engine_used, "width": gray.shape[1], "height": gray.shape[0],
        "text": "\n".join(l.text for l in lines), "lines": [l.as_dict() for l in lines],
        "mean_confidence": round(mean, 3), "quality": {**quality, "label": label}, "preprocessing": notes,
    }, warnings


def extract_document(data: bytes, engine: str = "auto", keep_images: bool = False) -> dict:
    started = time.time()
    if not data:
        raise ExtractionError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ExtractionError("The file is larger than 15 MB.")
    kind = detect_kind(data)
    pages, warnings = [], []
    engine_used = None

    if kind == "pdf":
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            raise ExtractionError("The PDF is damaged or cannot be opened.")
        if doc.needs_pass or doc.is_encrypted:
            raise ExtractionError("The PDF is password-protected. Remove the password and upload it again.")
        if doc.page_count == 0:
            raise ExtractionError("The PDF has no pages.")
        total = doc.page_count
        if total > MAX_PAGES:
            warnings.append(f"The PDF has {total} pages. Only the first {MAX_PAGES} were read.")
        for i in range(min(total, MAX_PAGES)):
            page = doc[i]
            text = page.get_text().strip()
            if len(text) >= MIN_TEXT_CHARS:
                lines = _pdf_lines(page)
                entry = {"page": i + 1, "method": "pdf_text", "engine": None, "width": round(page.rect.width, 1),
                         "height": round(page.rect.height, 1), "text": "\n".join(l["text"] for l in lines), "lines": lines,
                         "mean_confidence": 1.0, "quality": {"label": "good", "issues": []}, "preprocessing": []}
                if keep_images:
                    shot = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False)
                    entry["_image"] = np.frombuffer(shot.samples, np.uint8).reshape(shot.height, shot.width, 3)[:, :, ::-1].copy()
                pages.append(entry)
                continue
            pix = page.get_pixmap(matrix=pymupdf.Matrix(OCR_DPI / 72, OCR_DPI / 72), alpha=False)
            img = cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3), cv2.COLOR_RGB2BGR)
            engine_used, lines, gray, notes, quality = _ocr_page(img, engine)
            result, page_warnings = _finish_ocr_page(i + 1, lines, gray, notes, quality, engine_used)
            if keep_images:
                result["_image"] = gray
            pages.append(result)
            warnings += [f"Page {i + 1}: {w}" for w in page_warnings]
        page_count = total
    else:
        try:
            img = load_image(data)
        except Exception:
            raise ExtractionError("The image is damaged or cannot be opened.")
        engine_used, lines, gray, notes, quality = _ocr_page(img, engine)
        result, page_warnings = _finish_ocr_page(1, lines, gray, notes, quality, engine_used)
        if keep_images:
            result["_image"] = gray
        pages.append(result)
        warnings += page_warnings
        page_count = 1

    return {
        "kind": kind, "page_count": page_count, "pages": pages,
        "text": "\n\n".join(p["text"] for p in pages),
        "mean_confidence": round(float(np.mean([p["mean_confidence"] for p in pages])), 3),
        "warnings": warnings, "ocr_engine": engine_used, "elapsed_seconds": round(time.time() - started, 2),
    }
