import os
import re

import pytest

from medai import analyze_document, knowledge, rules
from medai.catalog import TESTS
from medai.summary import NO_MEDICINE_CHANGES, to_text

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "demo_documents")


def analyze(name, patient=None):
    return analyze_document(open(os.path.join(DOCS, name), "rb").read(), patient=patient)


# ---------------------------------------------------------------- the knowledge table
def all_strings():
    out = []
    for key, e in knowledge.T.items():
        out.append(e["measures"])
        for side in ("low", "high"):
            if e[side]:
                meaning, may, care, sooner = e[side]
                out += [meaning] + may + care + sooner
    for text, questions in knowledge.PATTERNS.values():
        out += [text] + questions
    out += list(knowledge.MEDICINE_INFO.values())
    return out


def test_every_test_has_an_explanation_and_every_alert_direction_is_covered():
    assert set(TESTS) <= set(knowledge.T)
    for key, bands in rules.BANDS.items():
        for direction in bands:
            assert knowledge.T[key][direction], f"{key} {direction} has threshold rules but no explanation"


def test_every_pattern_the_rules_can_find_has_a_text():
    ids = {"iron_deficiency", "kidney_impairment", "hyperkalaemia_kidney", "low_counts", "diabetes_range", "prediabetes",
           "hypothyroid", "hyperthyroid", "mixed_lipids", "liver_enzymes"}
    assert ids <= set(knowledge.PATTERNS)


# a dose such as "500 mg" is forbidden, but lab units such as "mg/dL" are fine
FORBIDDEN = [
    r"\b\d+(\.\d+)?\s*(mg|mcg|ml|iu|units)(?![/\w])",
    r"\bstop (taking|your)",
    r"\bstart (taking|using)\b",
    r"\bstart (a|an|any) (new )?(medicine|tablet|drug|supplement|antibiotic)",
    r"\b(increase|reduce|double|halve) (the|your) dose",
    r"\bdosage\b",
    r"\bno need (to see|for a doctor)",
]


def test_no_medicine_or_dose_advice_anywhere_in_the_texts():
    for text in all_strings():
        for pattern in FORBIDDEN:
            assert not re.search(pattern, text, re.I), f"forbidden wording in: {text}"


def test_wording_is_tentative_not_diagnostic():
    for key, e in knowledge.T.items():
        for side in ("low", "high"):
            if e[side]:
                assert not re.search(r"\byou have\b|\byou are suffering|\bdiagnos(is|ed with)\b", e[side][0], re.I), e[side][0]


def test_texts_stay_short_enough_to_read():
    assert max(len(t) for t in all_strings()) < 330


def test_emergency_texts_name_the_action():
    for text in all_strings():
        if "Call 112" in text:
            assert "emergency department" in text


# ---------------------------------------------------------------- whole reports
def test_urgent_report_tells_the_person_what_to_do():
    a = analyze("meena_kidney_panel_critical.pdf", {"name": "Meena Rajan", "sex": "female"})
    p = a["report"]["patient"]
    assert p["visit"]["level"] == "urgent" and "today" in p["visit"]["timeframe"]
    k = next(c for c in p["concerns"] if c["test_key"] == "potassium")
    assert k["severity"] == "critical" and "dangerous" in k["headline"]
    assert any("112" in x for x in k["see_doctor_sooner_if"]) and k["evidence"]["page"] == 1 and len(k["evidence"]["bbox"]) == 4
    assert p["concerns"][0]["test_key"] == "potassium"                       # most serious first
    assert any(x["id"] == "hyperkalaemia_kidney" for x in p["patterns"])
    assert p["medicines"] == NO_MEDICINE_CHANGES and p["disclaimer"]


def test_iron_deficiency_report_has_advice_and_questions():
    p = analyze("ananya_cbc_iron_report.pdf")["report"]["patient"]
    assert p["visit"]["level"] == "consult_soon" and p["visit"]["timeframe"] == "within 1-2 weeks"
    hb = next(c for c in p["concerns"] if c["test_key"] == "hemoglobin")
    assert any("iron-rich" in x for x in hb["self_care"]) and "anaemia" in hb["meaning"]
    assert any(x["id"] == "iron_deficiency" for x in p["patterns"])
    assert any("low iron" in q for q in p["questions_for_doctor"]) and len(p["questions_for_doctor"]) <= 6
    assert any("WBC" in g or "Platelet" in g for g in p["good_news"])


def test_normal_report_is_reassuring():
    p = analyze("karthik_health_checkup.pdf")["report"]["patient"]
    assert p["concerns"] == [] and p["visit"]["level"] == "routine" and "within the usual range" in p["headline"]
    assert p["good_news"] and "regular check-up" in p["visit"]["timeframe"]


def test_uncertain_scan_report_says_so():
    a = analyze("meena_kidney_panel_critical_scan.jpg", {"name": "Meena Rajan", "sex": "female"})
    p = a["report"]["patient"]
    assert any("flagged for checking" in n for n in p["notes"])
    assert p["visit"]["level"] == "urgent"


def test_wrong_patient_note_comes_first():
    p = analyze("rahul_diabetes_panel.pdf", {"name": "Ananya Krishnan"})["report"]["patient"]
    assert "does NOT match" in p["notes"][0]


def test_clinician_view_is_compact_and_complete():
    c = analyze("rahul_diabetes_panel.pdf")["report"]["clinician"]
    assert c["triage"]["level"] == "consult_soon" and len(c["findings"]) == 8
    hba1c = next(f for f in c["findings"] if f["test"] == "HbA1c")
    assert hba1c["value"] == 8.9 and hba1c["status"] == "high" and hba1c["range"] == "less than 5.7"
    assert "Blood sugar in the diabetes range" in c["patterns"]


def test_prescription_report_reads_like_instructions_and_stays_a_draft():
    p = analyze("rahul_prescription.pdf")["report"]["patient"]
    assert p["type"] == "prescription" and "DRAFT" in p["confirm"]
    first = p["items"][0]
    assert first["instructions"] == "Metformin 500 mg: take 1 tablet by mouth, twice daily after food, for 30 days."
    assert "blood sugar" in first["purpose"] and not first["missing_fields"]
    assert p["medicines"] == NO_MEDICINE_CHANGES


def test_prescription_report_marks_unreadable_fields():
    from medai import rx_parser
    from tests.test_parse import rx_page
    page = rx_page([("Metformin", None, "1 tablet", "Oral", "whenever", "30 days")])
    item = rx_parser.parse_table(page, False)[0]
    from medai.summary import _sentence
    s = _sentence(item)
    assert "[strength not detected]" in s and "frequency [not detected]" not in s.replace("whenever", "")  # unreadable frequency is shown as printed
    assert "30 days" in s


def test_unreadable_document_report():
    p = analyze("extras/blurry_low_quality_report.jpg")["report"]["patient"]
    assert p["type"] == "unknown" and "could not be read" in p["headline"] and p["notes"]


@pytest.mark.parametrize("name", ["ananya_cbc_iron_report.pdf", "fatima_lipid_thyroid_report.pdf", "karthik_health_checkup.pdf", "rahul_prescription.pdf"])
def test_text_version_renders_with_the_safety_lines(name):
    text = to_text(analyze(name)["report"])
    assert NO_MEDICINE_CHANGES in text and "not a diagnosis" in text.lower()


def test_shared_advice_is_not_repeated_in_the_text_version():
    text = to_text(analyze("meena_kidney_panel_critical.pdf")["report"])
    assert text.count("Cut down on salt") == 1


def test_unreadable_unit_is_never_shown_as_garbage():
    text = to_text(analyze("meena_kidney_panel_critical_scan.jpg", {"name": "Meena Rajan", "sex": "female"})["report"])
    assert "[unit unclear]" in text and "p/6" not in text
    assert "more than 90" in text and "more than90" not in text


def test_related_results_say_when_advice_is_shared():
    text = to_text(analyze("meena_kidney_panel_critical.pdf")["report"])
    assert "same as for the related results above" in text
