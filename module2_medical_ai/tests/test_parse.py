import pytest

import evaluate_parse
from medai import ExtractionError, analyze_document, check_identity
from medai import lab_parser, rx_parser
from medai.parse import patient_on_document
import os

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "demo_documents")


def cell(text, x, y, conf=0.98, w=None, alt=None, alt_conf=None):
    w = w or max(40, len(text) * 14)
    c = {"text": text, "bbox": [x, y - 12, x + w, y + 12], "confidence": conf}
    if alt is not None:
        c["alt_text"], c["alt_confidence"] = alt, alt_conf
    return c


def lab_page(*rows):
    """rows: lists of (text, kwargs) laid out as table columns at y = 100, 140, ..."""
    xs = [20, 300, 420, 600, 800]
    lines = []
    for i, row in enumerate(rows):
        for j, item in enumerate(row):
            text, kw = (item, {}) if isinstance(item, str) else item
            lines.append(cell(text, xs[j], 100 + 40 * i, **kw))
    return [{"page": 1, "lines": lines}]


def parse(*rows):
    return lab_parser.parse_lab_rows(lab_page(*rows))


# ---------------------------------------------------------------- lab results
def test_clean_row_is_structured_and_not_flagged():
    (r,), unknown = parse(["Haemoglobin", "9.8", "g/dL", "12.0 - 15.5", "L"], ["WBC count", "7.2", "thousand/uL", "4.0 - 11.0", ""])[0][:1], None
    assert (r["test"], r["value"], r["unit"], r["unit_status"], r["printed_flag"]) == ("Haemoglobin", 9.8, "g/dL", "ok", "L")
    assert r["reference"]["low"] == 12.0 and r["reference"]["high"] == 15.5
    assert r["issues"] == [] and r["needs_review"] is False
    assert r["source"]["page"] == 1 and len(r["source"]["bbox"]) == 4


def test_misread_value_is_caught_by_the_flag_and_plausibility_checks():
    results, _ = parse(["Haemoglobin", "86", "g/dL", "12.0 - 15.5", "L"], ["WBC count", "7.2", "thousand/uL", "4.0 - 11.0", ""])
    r = results[0]
    assert r["needs_review"]
    text = " ".join(r["issues"])
    assert "plausible" in text and "disagrees" in text


def test_second_reading_that_disagrees_is_flagged_and_better_one_is_shown():
    results, _ = parse([("TSH", {}), ("86", {"conf": 0.94, "alt": "9.8", "alt_conf": 1.0}), "mIU/L", "0.4 - 4.0", "H"],
                       ["Free T4", "0.7", "ng/dL", "0.8 - 1.8", "L"])
    r = results[0]
    assert r["value"] == 9.8 and r["value_alternative"] == 86.0 and r["needs_review"]
    assert any("disagree" in i for i in r["issues"])


def test_second_reading_with_lower_confidence_keeps_first_but_flags():
    results, _ = parse([("Haemoglobin", {}), ("9.8", {"conf": 0.99, "alt": "98", "alt_conf": 0.7}), "g/dL", "12.0 - 15.5", "L"])
    r = results[0]
    assert r["value"] == 9.8 and r["value_alternative"] == 98.0 and r["needs_review"]


def test_garbage_unit_missing_unit_and_wrong_unit():
    results, _ = parse(["Haemoglobin", "9.1", "7p/6", "12.0 - 15.5", "L"], ["MCV", "72", "", "80 - 100", "L"], ["Platelet count", "310", "mg/dL", "150 - 400", ""])
    garbage, missing, wrong = results
    assert garbage["unit_status"] == "uncertain" and garbage["needs_review"]
    assert missing["unit_status"] == "missing" and missing["needs_review"]
    assert wrong["unit_status"] == "unexpected" and wrong["needs_review"]


def test_cells_glued_together_by_ocr_are_split():
    results, _ = parse([("Haemoglobin", {}), ("9.8 g/dL", {}), ("12.0-15.5 L", {})])
    r = results[0]
    assert r["value"] == 9.8 and r["unit"] == "g/dL" and r["printed_flag"] == "L" and r["reference"]["high"] == 15.5


def test_range_kinds_and_flags():
    results, _ = parse(["Total cholesterol", "232", "mg/dL", "less than 200", "H"], ["HDL cholesterol", "38", "mg/dL", "more than 40", "L"],
                       ["HbA1c", "8.9", "%", "<5.7", "H"], ["eGFR", "14", "mL/min/1.73m2", "morethan90", "L"], ["Serum sodium", "140", "mmol/L", "135 - 145", ""])
    assert [r["needs_review"] for r in results] == [False] * 5
    assert [r["reference"]["kind"] for r in results] == ["less", "more", "less", "more", "between"]


def test_critical_flag_is_read():
    results, _ = parse(["Serum potassium", "6.4", "mmol/L", "3.5 - 5.0", "CRITICAL H"], ["Serum sodium", "132", "mmol/L", "135 - 145", "L"])
    assert results[0]["printed_flag"] == "H" and results[0]["printed_critical"] is True and not results[0]["needs_review"]


def test_missing_flag_in_a_report_that_prints_flags_is_suspicious():
    results, _ = parse(["Haemoglobin", "9.8", "g/dL", "12.0 - 15.5", ""], ["Serum sodium", "132", "mmol/L", "135 - 145", "L"])
    assert results[0]["needs_review"] and "disagrees" in results[0]["issues"][0]


def test_report_without_any_flags_is_not_penalised():
    results, _ = parse(["Haemoglobin", "9.8", "g/dL", "12.0 - 15.5"], ["Serum sodium", "132", "mmol/L", "135 - 145"])
    assert not any(r["needs_review"] for r in results)


def test_unknown_test_is_listed_never_dropped():
    results, unknown = parse(["Haemoglobin", "13.1", "g/dL", "12.0 - 15.5", ""], ["Zorblax factor", "4.2", "U/L", "1.0 - 5.0", ""])
    assert len(results) == 1 and len(unknown) == 1 and unknown[0]["name_as_printed"] == "Zorblax factor" and unknown[0]["issues"]


def test_spacing_loss_and_small_name_typos_are_tolerated_but_noted():
    results, _ = parse(["Serumpotassium", "4.1", "mmol/L", "3.5 - 5.0", ""], ["Haemoglobln", "13.0", "g/dL", "12.0 - 15.5", ""])
    assert results[0]["test_key"] == "potassium" and not results[0]["needs_review"]
    assert results[1]["test_key"] == "hemoglobin" and results[1]["needs_review"]


def test_duplicate_test_with_different_values_is_flagged():
    results, _ = parse(["Haemoglobin", "13.0", "g/dL", "12.0 - 15.5", ""], ["Haemoglobin", "9.0", "g/dL", "12.0 - 15.5", ""])
    assert all(r["needs_review"] for r in results)


def test_low_confidence_cell_is_flagged():
    results, _ = parse([("Haemoglobin", {}), ("13.0", {"conf": 0.6}), "g/dL", "12.0 - 15.5", ""])
    assert results[0]["needs_review"] and "confidence" in results[0]["issues"][0]


# ---------------------------------------------------------------- prescriptions
def rx_page(rows, header=True, conf=0.98):
    xs = {"no": 20, "medicine": 100, "strength": 300, "dose": 420, "route": 540, "frequency": 640, "duration": 860}
    lines = []
    if header:
        for k, t in (("no", "No."), ("medicine", "MEDICINE"), ("strength", "STRENGTH"), ("dose", "DOSE"), ("route", "ROUTE"), ("frequency", "FREQUENCY"), ("duration", "DURATION")):
            lines.append(cell(t, xs[k], 60))
    for i, row in enumerate(rows):
        for k, v in zip(("medicine", "strength", "dose", "route", "frequency", "duration"), row):
            if v is None:
                continue
            kw = {}
            if isinstance(v, tuple):
                v, kw = v
            lines.append(cell(v, xs[k], 110 + 40 * i, **({"conf": conf} | kw)))
        lines.append(cell(str(i + 1), xs["no"], 110 + 40 * i, w=20))
    return {"page": 1, "lines": lines}


def test_prescription_table_gives_separate_fields_and_stays_draft():
    items = rx_parser.parse_table(rx_page([("Metformin", "500 mg", "1 tablet", "Oral", "Twice daily after food", "30 days")]), False)
    it = items[0]
    assert it["strength"]["value"] == {"value": 500.0, "unit": "mg", "text": "500 mg"}
    assert it["dose"]["value"]["text"] == "1 tablet" and it["route"]["value"]["text"] == "oral"
    assert it["frequency"]["value"]["times_per_day"] == 2 and "after food" in it["frequency"]["value"]["timing"]
    assert it["duration"]["value"]["days"] == 30
    assert it["status"] == "draft" and it["requires_doctor_confirmation"] is True and not it["needs_review"]


def test_missing_and_unreadable_fields_are_reported_not_guessed():
    items = rx_parser.parse_table(rx_page([("Metformin", None, "1 tablet", "Oral", "whenever", "30 days")]), False)
    it = items[0]
    assert it["strength"]["status"] == "missing" and it["strength"]["value"] is None
    assert it["frequency"]["status"] == "uncertain" and it["frequency"]["value"] is None
    assert it["needs_review"] and any("Strength" in i for i in it["issues"]) and any("Frequency" in i for i in it["issues"])


def test_unknown_medicine_gets_a_suggestion_but_is_never_corrected():
    it = rx_parser.parse_table(rx_page([("Metformn", "500 mg", "1 tablet", "Oral", "Twice daily", "30 days")]), False)[0]
    assert it["medicine"]["value"] == "Metformn" and it["medicine"]["suggestion"] == "metformin" and it["needs_review"]
    assert any("Did you mean Metformin" in i for i in it["issues"])


def test_strength_second_reading_disagreement_is_flagged():
    it = rx_parser.parse_table(rx_page([("Metformin", ("500 mg", {"alt": "600 mg", "alt_conf": 0.9}), "1 tablet", "Oral", "Twice daily", "30 days")]), False)[0]
    assert it["needs_review"] and any("disagree" in i for i in it["issues"])


def test_low_confidence_and_poor_picture_are_flagged():
    assert rx_parser.parse_table(rx_page([("Metformin", "500 mg", "1 tablet", "Oral", "Twice daily", "30 days")], conf=0.6), False)[0]["needs_review"]
    assert rx_parser.parse_table(rx_page([("Metformin", "500 mg", "1 tablet", "Oral", "Twice daily", "30 days")]), True)[0]["needs_review"]


def test_misspelt_timing_word_is_noticed():
    it = rx_parser.parse_table(rx_page([("Furosemide", "40 mg", "1 tablet", "Oral", "Once daily, moning", "14 days")]), False)[0]
    assert it["frequency"]["value"]["times_per_day"] == 1 and it["needs_review"]
    assert any("moning" in i for i in it["issues"])


def test_free_text_prescription_lines():
    page = {"page": 1, "lines": [cell("1. Tab. Metformin 500mg 1-0-1 x 30 days after food", 20, 100, w=700),
                                 cell("2. Tab Amlodipine 5 mg 1-0-0 for 2 weeks", 20, 140, w=700),
                                 cell("Review after one month", 20, 180, w=300)]}
    a, b = rx_parser.parse_free_text(page, False)
    assert a["medicine"]["value"].lower().endswith("metformin") and a["strength"]["value"]["value"] == 500.0
    assert a["frequency"]["value"]["times_per_day"] == 2 and a["duration"]["value"]["days"] == 30
    assert b["strength"]["value"]["text"] == "5 mg" and b["duration"]["value"]["days"] == 14


@pytest.mark.parametrize("text,times", [("1-1-1", 3), ("TDS", 3), ("BD", 2), ("Twice daily", 2), ("Once daily at night", 1), ("QID", 4), ("1-0-1", 2)])
def test_frequency_patterns(text, times):
    assert rx_parser.parse_frequency(text)["times_per_day"] == times


def test_frequency_as_needed_and_weekly():
    assert rx_parser.parse_frequency("SOS")["as_needed"] is True
    assert rx_parser.parse_frequency("once weekly")["schedule"] == "weekly"
    assert rx_parser.parse_frequency("blah") is None


def test_duration_units():
    assert rx_parser.parse_duration("2 weeks")["days"] == 14 and rx_parser.parse_duration("1 month")["days"] == 30
    assert rx_parser.parse_duration("continue")["ongoing"] is True and rx_parser.parse_duration("soon") is None


# ---------------------------------------------------------------- identity
def test_identity_check():
    assert check_identity("Ananya Krishnan", "Ananya Krishnan")["status"] == "match"
    assert check_identity("AnanyaKrishnan", "Ananya Krishnan")["status"] == "match"
    assert check_identity("Ananya Krishnen", "Ananya Krishnan")["status"] == "similar"
    mismatch = check_identity("Rahul Menon", "Ananya Krishnan")
    assert mismatch["status"] == "mismatch" and "NOT match" in mismatch["message"]
    assert check_identity(None, "Ananya Krishnan")["status"] == "not_found"
    assert "sex" in check_identity("Ananya Krishnan", "Ananya Krishnan", "female", "male")["message"]


# ---------------------------------------------------------------- whole documents
def read(name):
    return open(os.path.join(DOCS, name), "rb").read()


def test_whole_digital_report_end_to_end():
    r = analyze_document(read("meena_kidney_panel_critical.pdf"), patient={"name": "Meena Rajan", "sex": "female"})
    assert r["document_type"] == "lab_report" and r["status"] == "unconfirmed" and r["disclaimer"]
    assert r["identity"]["status"] == "match" and r["patient_on_document"]["age"] == 75
    assert r["patient_on_document"]["collected"] == "2026-10-24"
    k = next(x for x in r["lab_results"] if x["test_key"] == "potassium")
    assert k["value"] == 6.4 and k["printed_critical"] is True
    assert r["summary"]["items"] == 6 and r["summary"]["needs_review"] == 0


def test_wrong_patient_is_warned_about():
    r = analyze_document(read("rahul_diabetes_panel.pdf"), patient={"name": "Ananya Krishnan"})
    assert r["identity"]["status"] == "mismatch" and any("does NOT match" in w for w in r["warnings"])


def test_prescription_photo_end_to_end():
    r = analyze_document(read("rahul_prescription_photo.jpg"))
    assert r["document_type"] == "prescription" and r["summary"]["items"] == 3
    assert [i["medicine"]["value"] for i in r["prescription_items"]] == ["Metformin", "Amlodipine", "Atorvastatin"]
    assert all(i["status"] == "draft" for i in r["prescription_items"])


def test_unreadable_picture_is_reported_as_unknown_with_warnings():
    r = analyze_document(read("extras/blurry_low_quality_report.jpg"))
    assert r["document_type"] == "unknown" and r["summary"]["items"] == 0 and r["warnings"]


def test_bad_files_still_raise():
    with pytest.raises(ExtractionError):
        analyze_document(read("extras/fake_report.pdf"))


def test_patient_details_are_read_from_a_scan():
    from medai import extract_document
    info = patient_on_document(extract_document(read("ananya_cbc_iron_report_scan.jpg"))["pages"])
    assert info["age"] == 31 and info["sex"] == "female" and info["collected"] == "2026-10-24"
    assert "ananya" in info["name_as_printed"].lower()


# ---------------------------------------------------------------- measured safety on the demo set
def test_no_silent_errors_on_demo_documents(capsys):
    out = evaluate_parse.run(show=False)
    assert out["silent"] == 0 and out["missed"] == 0
    assert (out["fields"] - out["errors"]) / out["fields"] >= 0.99
