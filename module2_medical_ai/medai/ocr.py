"""OCR engines. RapidOCR works with a plain pip install (no extra program to
install on Windows). Tesseract is used only if you choose it and it is installed."""
import os
import shutil
import threading
from dataclasses import dataclass

import numpy as np


@dataclass
class OcrLine:
    text: str
    bbox: list  # [x0, y0, x1, y1] in pixels of the image given to the engine
    confidence: float  # 0..1
    alt_text: str = None        # a second, independent reading of a number cell (only when it differs)
    alt_confidence: float = None

    def as_dict(self):
        d = {"text": self.text, "bbox": [round(v, 1) for v in self.bbox], "confidence": round(self.confidence, 3)}
        if self.alt_text is not None:
            d["alt_text"], d["alt_confidence"] = self.alt_text, round(self.alt_confidence or 0, 3)
        return d


_local = threading.local()


def _rapidocr():
    """One OCR engine per thread, so several documents can be read at the same time
    without sharing an engine between threads."""
    engine = getattr(_local, "rapid", None)
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        engine = _local.rapid = RapidOCR()
    return engine


def _tesseract_cmd():
    cmd = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    if not cmd and os.path.isfile(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
        cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return cmd


def available_engines():
    engines = []
    try:
        import rapidocr_onnxruntime  # noqa: F401
        engines.append("rapidocr")
    except ImportError:
        pass
    try:
        import pytesseract  # noqa: F401
        if _tesseract_cmd():
            engines.append("tesseract")
    except ImportError:
        pass
    return engines


def _run_rapidocr(gray):
    result, _ = _rapidocr()(gray)
    lines = []
    for box, text, conf in result or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        if text.strip():
            lines.append(OcrLine(text.strip(), [min(xs), min(ys), max(xs), max(ys)], float(conf)))
    return lines


def _run_tesseract(gray):
    try:
        import pytesseract  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pytesseract is required for the tesseract OCR engine") from exc
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    data = pytesseract.image_to_data(gray, config="--psm 6", output_type=pytesseract.Output.DICT)
    groups = {}
    for i, word in enumerate(data["text"]):
        if not word.strip() or float(data["conf"][i]) < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append(i)
    lines = []
    for idx in groups.values():
        # words far apart horizontally are separate table cells, nearby ones one phrase
        idx.sort(key=lambda i: data["left"][i])
        cell = [idx[0]]
        cells = []
        for i in idx[1:]:
            prev = cell[-1]
            gap = data["left"][i] - (data["left"][prev] + data["width"][prev])
            if gap > 2.2 * data["height"][prev]:
                cells.append(cell)
                cell = [i]
            else:
                cell.append(i)
        cells.append(cell)
        for c in cells:
            x0 = min(data["left"][i] for i in c)
            y0 = min(data["top"][i] for i in c)
            x1 = max(data["left"][i] + data["width"][i] for i in c)
            y1 = max(data["top"][i] + data["height"][i] for i in c)
            conf = float(np.mean([float(data["conf"][i]) for i in c])) / 100
            lines.append(OcrLine(" ".join(data["text"][i] for i in c), [x0, y0, x1, y1], conf))
    return lines


def run_ocr(gray, engine="auto"):
    """Returns (engine_name, [OcrLine]) sorted top to bottom, left to right."""
    available = available_engines()
    if engine == "auto":
        engine = "rapidocr" if "rapidocr" in available else ("tesseract" if "tesseract" in available else None)
    if engine not in available:
        raise RuntimeError("No OCR engine available. Run: pip install rapidocr-onnxruntime")
    lines = _run_rapidocr(gray) if engine == "rapidocr" else _run_tesseract(gray)
    lines.sort(key=lambda l: (round(l.bbox[1] / 12), l.bbox[0]))
    return engine, lines
