import io
import json
import os

import cv2
import numpy as np
import pymupdf
import pytest
from PIL import Image

import evaluate
from medai import ExtractionError, extract_document, imaging
from medai.layout import group_rows, squash

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "demo_documents")
read = lambda name: open(os.path.join(DOCS, name), "rb").read()  # noqa: E731
TRUTH = json.load(open(os.path.join(DOCS, "ground_truth.json")))


# ---------- bad input is refused clearly ----------

@pytest.mark.parametrize("data,msg", [
    (b"", "empty"),
    (b"just some text", "Unsupported"),
    (b"%PDF-1.4 this is not really a pdf", "damaged"),
    (b"\xff\xd8\xff garbage that is not a jpeg", "damaged"),
])
def test_unreadable_files_raise_clear_errors(data, msg):
    with pytest.raises(ExtractionError) as exc:
        extract_document(data)
    assert msg.lower() in str(exc.value).lower()


def test_extras_fake_files_are_rejected():
    for name in ("extras/fake_report.pdf", "extras/notes.txt"):
        with pytest.raises(ExtractionError):
            extract_document(read(name))


def test_password_protected_pdf_is_refused():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Secret patient report " * 5)
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    with pytest.raises(ExtractionError) as exc:
        extract_document(data)
    assert "password" in str(exc.value).lower()


def test_file_size_limit():
    with pytest.raises(ExtractionError):
        extract_document(b"%PDF-" + b"0" * (16 * 1024 * 1024))


def test_long_pdf_is_capped_with_a_warning():
    doc = pymupdf.open()
    for i in range(25):
        doc.new_page().insert_text((72, 72), f"Page {i + 1} of a long laboratory report with enough text to count as digital.")
    result = extract_document(doc.tobytes())
    assert result["page_count"] == 25 and len(result["pages"]) == 20
    assert any("first 20" in w for w in result["warnings"])


# ---------- digital PDFs: exact text, no OCR ----------

def test_digital_pdf_is_read_exactly_without_ocr():
    result = extract_document(read("meena_kidney_panel_critical.pdf"))
    page = result["pages"][0]
    assert result["kind"] == "pdf" and page["method"] == "pdf_text" and result["ocr_engine"] is None
    assert page["mean_confidence"] == 1.0 and "6.4" in page["text"] and "CRITICAL H" in page["text"]
    assert all(len(l["bbox"]) == 4 for l in page["lines"])


def test_table_rows_are_rebuilt_from_positions():
    page = extract_document(read("ananya_cbc_iron_report.pdf"))["pages"][0]
    rows = [r["text"] for r in group_rows(page["lines"])]
    assert any(squash("Haemoglobin 9.8 g/dL 12.0 - 15.5 L") == squash(r) for r in rows)


def test_image_only_pdf_falls_back_to_ocr():
    doc = pymupdf.open()
    img = read("meena_kidney_panel_critical_scan.jpg")
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=img)
    result = extract_document(doc.tobytes())
    assert result["pages"][0]["method"] == "ocr"
    assert "6.4" in result["text"]


# ---------- images ----------

def test_scanned_report_values_are_read():
    result = extract_document(read("ananya_cbc_iron_report_scan.jpg"))
    page = result["pages"][0]
    assert page["method"] == "ocr" and result["ocr_engine"] == "rapidocr"
    rows = [squash(r["text"]) for r in group_rows(page["lines"])]
    assert any("haemoglobin" in r and "9.8" in r for r in rows)
    assert any("ferritin" in r and "8" in r for r in rows)


def test_phone_photo_page_is_found_and_prescription_read():
    result = extract_document(read("rahul_prescription_photo.jpg"))
    page = result["pages"][0]
    assert any("straightened" in n for n in page["preprocessing"])
    text = squash(result["text"])
    for med in ("metformin", "amlodipine", "atorvastatin"):
        assert med in text


def test_blurry_low_quality_picture_is_flagged():
    result = extract_document(read("extras/blurry_low_quality_report.jpg"))
    page = result["pages"][0]
    assert page["quality"]["label"] in ("poor", "fair") and page["quality"]["issues"]
    assert result["warnings"]


# ---------- image helpers ----------

def _text_page():
    page = pymupdf.open(os.path.join(DOCS, "rahul_diabetes_panel.pdf"))[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False)
    return cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3), cv2.COLOR_RGB2GRAY)


def test_skew_is_measured_in_the_right_direction():
    straight = _text_page()
    assert abs(imaging.estimate_skew(straight)) <= 0.5
    tilted = imaging.rotate(straight, 3.0)           # text now tilted 3 degrees
    est = imaging.estimate_skew(tilted)
    assert abs(est + 3.0) <= 0.75                    # estimate says "rotate back by about -3"
    fixed = imaging.rotate(tilted, est)
    assert abs(imaging.estimate_skew(fixed)) <= 0.75


def test_blank_page_has_no_skew():
    assert imaging.estimate_skew(np.full((900, 700), 255, np.uint8)) == 0.0


def test_exif_rotation_is_honoured():
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    exif = Image.Exif()
    exif[274] = 6  # "rotate 90 degrees clockwise to view"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert imaging.load_image(buf.getvalue()).shape[:2] == (200, 100)


# ---------- measured accuracy on the whole demo set ----------

def test_demo_documents_are_read_accurately():
    ok = total = 0
    for name, truth in TRUTH.items():
        a, b, missed, _ = evaluate.score(os.path.join(DOCS, name), truth, "auto")
        ok, total = ok + a, total + b
    assert ok / total >= 0.97, f"only {ok}/{total} rows correct"
