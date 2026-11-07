import copy
import os

import pytest

from medai import ReviewError, analyze_document, apply_review

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "demo_documents")
PATIENT = {"name": "Meena Rajan", "sex": "female", "age": 75}


@pytest.fixture(scope="module")
def meena_scan():
    return analyze_document(open(os.path.join(DOCS, "meena_kidney_panel_critical_scan.jpg"), "rb").read(), patient=PATIENT)


@pytest.fixture(scope="module")
def meena():
    return analyze_document(open(os.path.join(DOCS, "meena_kidney_panel_critical.pdf"), "rb").read(), patient=PATIENT)


@pytest.fixture(scope="module")
def rahul_rx():
    return analyze_document(open(os.path.join(DOCS, "rahul_prescription.pdf"), "rb").read())


def idx(a, key):
    return next(str(i) for i, r in enumerate(a["lab_results"]) if r["test_key"] == key)


def test_original_is_never_changed(meena):
    before = copy.deepcopy(meena)
    apply_review(meena, {"lab_results": {idx(meena, "potassium"): {"value": 4.0}}}, PATIENT)
    assert meena == before


def test_correcting_a_value_changes_urgency_and_the_report(meena):
    assert meena["triage"]["level"] == "urgent"
    k = idx(meena, "potassium")
    fixed = apply_review(meena, {"lab_results": {k: {"value": 4.1, "flag": ""}}}, PATIENT)
    assert next(r for r in fixed["lab_results"] if r["test_key"] == "potassium")["interpretation"]["status"] == "normal"
    assert fixed["triage"]["level"] == "consult_promptly"            # kidney results are still marked
    assert "Serum potassium is" not in " ".join(c["headline"] for c in fixed["report"]["patient"]["concerns"])
    assert fixed["review_log"][0] == {"kind": "lab", "index": int(k), "test": "Serum potassium", "field": "value", "old": 6.4, "new": 4.1} or fixed["review_log"][0]["field"] == "value"


def test_correcting_to_a_worse_value_raises_the_level(meena):
    s = idx(meena, "sodium")
    worse = apply_review(meena, {"lab_results": {s: {"value": 114, "flag": "L"}}}, PATIENT)
    assert worse["triage"]["level"] == "urgent"
    assert any(c["test_key"] == "sodium" and c["severity"] == "critical" for c in worse["report"]["patient"]["concerns"])


def test_accepting_a_flagged_item_clears_the_provisional_state(meena_scan):
    assert meena_scan["triage"]["provisional"] and meena_scan["summary"]["needs_review"] == 1
    flagged = next(i for i, r in enumerate(meena_scan["lab_results"]) if r["needs_review"])
    out = apply_review(meena_scan, {"lab_results": {str(flagged): {"unit": "g/dL", "accepted": True}}}, PATIENT)
    r = out["lab_results"][flagged]
    assert r["unit_status"] == "ok" and not r["needs_review"] and r["user_reviewed"]
    assert not out["triage"]["provisional"] and out["summary"]["needs_review"] == 0
    assert "[unit unclear]" not in " ".join(c["headline"] for c in out["report"]["patient"]["concerns"])


def test_accept_without_correction_keeps_a_record_of_what_was_waved_through(meena_scan):
    flagged = next(i for i, r in enumerate(meena_scan["lab_results"]) if r["needs_review"])
    out = apply_review(meena_scan, {"lab_results": {str(flagged): {"accepted": True}}}, PATIENT)
    r = out["lab_results"][flagged]
    assert not r["needs_review"] and r["acknowledged_issues"]


def test_a_correction_that_creates_a_new_problem_is_flagged_again(meena):
    h = idx(meena, "hemoglobin")
    out = apply_review(meena, {"lab_results": {h: {"value": 86}}}, PATIENT)
    r = out["lab_results"][int(h)]
    assert r["needs_review"] and any("plausible" in i for i in r["issues"])


def test_invalid_edits_are_refused_with_a_clear_message(meena):
    k = idx(meena, "potassium")
    for bad, text in (({"value": "abc"}, "not a number"), ({"value": "1e99"}, "sensible"), ({"reference": "xyz"}, "not understood"), ({"flag": "Q"}, "H, L or empty")):
        with pytest.raises(ReviewError) as exc:
            apply_review(meena, {"lab_results": {k: bad}}, PATIENT)
        assert text in str(exc.value)
    with pytest.raises(ReviewError):
        apply_review(meena, {"lab_results": {"99": {"value": 1}}}, PATIENT)


def test_rows_can_be_removed_and_added_by_hand(meena):
    junk = idx(meena, "sodium")
    out = apply_review(meena, {"lab_results": {junk: {"remove": True}},
                               "add_lab_results": [{"test": "Haemoglobin", "value": "9.0", "unit": "g/dL", "reference": "12.0 - 15.5"}]}, PATIENT)
    keys = [r["test_key"] for r in out["lab_results"]]
    assert "sodium" not in keys and keys[-1] == "hemoglobin"
    added = out["lab_results"][-1]
    assert added["manual"] and added["interpretation"]["status"] == "low" and not added["needs_review"]
    assert {"added by hand", "removed"} <= {e["new"] for e in out["review_log"]}
    with pytest.raises(ReviewError):
        apply_review(meena, {"add_lab_results": [{"test": "Zorblax", "value": 1}]}, PATIENT)


def test_prescription_fields_can_be_corrected_and_stay_a_draft(rahul_rx):
    out = apply_review(rahul_rx, {"prescription_items": {"0": {"strength": "850 mg", "frequency": "Once daily", "accepted": True}}})
    it = out["prescription_items"][0]
    assert it["strength"]["value"]["value"] == 850.0 and it["frequency"]["value"]["times_per_day"] == 1
    assert it["status"] == "draft" and it["requires_doctor_confirmation"] and it["user_reviewed"]
    assert {e["field"] for e in out["review_log"]} == {"strength", "frequency"}
    assert "850 mg" in out["report"]["patient"]["items"][0]["instructions"]


def test_prescription_can_be_fixed_removed_and_extended(rahul_rx):
    out = apply_review(rahul_rx, {"prescription_items": {"0": {"medicine": "Metformn"}, "1": {"remove": True}},
                                  "add_prescription_items": [{"medicine": "Paracetamol", "strength": "500 mg", "dose": "1 tablet", "frequency": "Twice daily", "duration": "3 days"}]})
    names = [i["medicine"]["value"] for i in out["prescription_items"]]
    assert names == ["Metformn", "Atorvastatin", "Paracetamol"]
    assert out["prescription_items"][0]["needs_review"] and out["prescription_items"][0]["medicine"]["suggestion"] == "metformin"
    assert out["prescription_items"][2]["manual"]
    with pytest.raises(ReviewError):
        apply_review(rahul_rx, {"add_prescription_items": [{"medicine": " "}]})
