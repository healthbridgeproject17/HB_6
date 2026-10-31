import os

import pytest

from medai import analyze_document, rules
from medai.catalog import TESTS
from medai.lab_parser import parse_range

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "demo_documents")


def R(key, value, rng=None, unit=None, **extra):
    r = {"test_key": key, "test": TESTS[key]["label"], "value": value, "unit": unit or TESTS[key]["unit"], "unit_status": "ok",
         "reference": parse_range(rng) if rng else None, "needs_review": False, "value_alternative": None, "value_qualifier": None,
         "printed_flag": None, "issues": []}
    r.update(extra)
    return r


def level(*results, sex="female", age=40):
    return rules.assess(list(results), {"sex": sex, "age": age})["level"]


def interp(r, sex="female", age=40):
    return rules.interpret(r, sex, age)


# ---------------------------------------------------------------- single values
def test_normal_value():
    i = interp(R("potassium", 4.2, "3.5 - 5.0"))
    assert (i["status"], i["severity"], i["level"]) == ("normal", "normal", 0)


@pytest.mark.parametrize("key,value,rng,expected", [
    ("potassium", 6.4, "3.5 - 5.0", "critical"), ("potassium", 6.0, "3.5 - 5.0", "critical"),  # exactly on the alert line escalates
    ("potassium", 5.6, "3.5 - 5.0", "moderate"), ("potassium", 5.2, "3.5 - 5.0", "mild"),
    ("hemoglobin", 6.5, "12.0 - 15.5", "critical"), ("hemoglobin", 7.0, "12.0 - 15.5", "critical"), ("hemoglobin", 7.9, "12.0 - 15.5", "marked"),
    ("hemoglobin", 9.8, "12.0 - 15.5", "moderate"), ("hemoglobin", 11.5, "12.0 - 15.5", "mild"),
    ("sodium", 118, "135 - 145", "critical"), ("platelets", 15, "150 - 400", "critical"), ("glucose_fasting", 420, "70 - 99", "critical"),
    ("glucose_fasting", 45, "70 - 99", "critical"), ("calcium", 13.2, "8.5 - 10.5", "critical"), ("triglycerides", 1200, "less than 150", "critical"),
    ("tsh", 9.8, "0.4 - 4.0", "mild"), ("tsh", 12, "0.4 - 4.0", "moderate"), ("tsh", 30, "0.4 - 4.0", "marked"),
    ("hdl", 38, "more than 40", "borderline"), ("ldl", 152, "less than 100", "mild"), ("ldl", 195, "less than 100", "marked"),
])
def test_severity_bands(key, value, rng, expected):
    assert interp(R(key, value, rng))["severity"] == expected


def test_critical_values_map_to_urgent_and_others_to_lower_levels():
    assert level(R("potassium", 6.4, "3.5 - 5.0")) == "urgent"
    assert level(R("hemoglobin", 7.9, "12.0 - 15.5")) == "consult_promptly"
    assert level(R("hemoglobin", 9.8, "12.0 - 15.5")) == "consult_soon"
    assert level(R("hdl", 38, "more than 40")) == "routine"
    assert level(R("sodium", 140, "135 - 145")) == "routine"


def test_critical_alert_still_fires_when_a_printed_range_is_too_wide():
    i = interp(R("potassium", 6.4, "3.5 - 7.0"))
    assert i["status"] == "high" and i["severity"] == "critical" and "alert level" in i["alert_reason"]


def test_sex_specific_standard_ranges_when_no_printed_range():
    assert interp(R("hemoglobin", 13.0), sex="female")["status"] == "normal"
    assert interp(R("hemoglobin", 13.0), sex="male")["status"] == "low"
    unknown = interp(R("hemoglobin", 13.0), sex=None)
    assert unknown["status"] == "normal" and "sex not known" in unknown["standard_range"]["note"]


def test_printed_range_beats_standard_range_and_odd_ones_are_noted():
    assert interp(R("hemoglobin", 13.2, "13.0 - 17.0"), sex="male")["range_used"]["source"] == "printed"
    odd = interp(R("potassium", 4.2, "1.0 - 9.0"))
    assert any("differs a lot" in n for n in odd["notes"])


def test_not_assessed_cases():
    assert interp(R("hemoglobin", 9.0, "12.0 - 15.5", unit_status="unexpected"))["status"] == "not_assessed"
    assert interp(R("hba1c", 5.0, "less than 5.7", value_qualifier="<"))["status"] == "not_assessed"
    assert interp(R("hemoglobin", 9.0), age=10)["status"] == "not_assessed"           # adult ranges only, none printed
    assert interp(R("hemoglobin", 9.0, "11.0 - 14.0"), age=10)["status"] == "low"      # printed child range is fine


# ---------------------------------------------------------------- combinations
def pattern_ids(*results, **kw):
    return {p["id"] for p in rules.assess(list(results), {"sex": kw.get("sex", "female"), "age": 40})["patterns"]}


def test_high_potassium_with_kidney_problem_is_urgent_even_if_potassium_alone_is_not():
    rs = [R("potassium", 5.6, "3.5 - 5.0"), R("creatinine", 2.1, "0.6 - 1.1"), R("urea", 70, "15 - 40")]
    t = rules.assess(rs, {"sex": "female", "age": 70})
    assert t["level"] == "urgent" and "hyperkalaemia_kidney" in {p["id"] for p in t["patterns"]}


def test_kidney_pattern_levels():
    assert pattern_ids(R("creatinine", 1.8, "0.6 - 1.1"), R("urea", 60, "15 - 40")) >= {"kidney_impairment"}
    assert level(R("egfr", 25, "more than 90"), R("creatinine", 2.4, "0.6 - 1.1"), R("urea", 70, "15 - 40")) == "consult_promptly"


def test_diabetes_pre_diabetes_and_poor_control():
    assert "diabetes_range" in pattern_ids(R("hba1c", 7.2, "less than 5.7"))
    assert level(R("hba1c", 10.5, "less than 5.7")) == "consult_promptly"
    assert "prediabetes" in pattern_ids(R("hba1c", 6.0, "less than 5.7"))
    assert level(R("hba1c", 5.2, "less than 5.7"), R("glucose_fasting", 85, "70 - 99")) == "routine"


def test_thyroid_patterns():
    assert "hypothyroid" in pattern_ids(R("tsh", 9.8, "0.4 - 4.0"), R("ft4", 0.7, "0.8 - 1.8"))
    assert level(R("tsh", 0.02, "0.4 - 4.0"), R("ft4", 3.0, "0.8 - 1.8")) == "consult_promptly"


def test_blood_count_iron_and_liver_patterns():
    assert "low_counts" in pattern_ids(R("hemoglobin", 10.5, "12.0 - 15.5"), R("platelets", 90, "150 - 400"))
    assert "iron_deficiency" in pattern_ids(R("hemoglobin", 10.5, "12.0 - 15.5"), R("ferritin", 6, "13 - 150"))
    assert "iron_deficiency" not in pattern_ids(R("hemoglobin", 13.0, "12.0 - 15.5"), R("ferritin", 6, "13 - 150"))
    assert level(R("alt", 200, "7 - 56"), R("ast", 150, "10 - 40")) == "consult_promptly"


# ---------------------------------------------------------------- report level behaviour
def test_report_counts_reasons_and_advice():
    t = rules.assess([R("hemoglobin", 9.8, "12.0 - 15.5"), R("sodium", 140, "135 - 145")], {"sex": "female", "age": 30})
    assert t["counts"] == {"results": 2, "normal": 1, "abnormal": 1, "critical": 0, "not_assessed": 0}
    assert t["reasons"][0]["test"] == "Haemoglobin" and t["timeframe"] == "within 1-2 weeks" and not t["provisional"]


def test_urgent_advice_mentions_emergency_steps():
    t = rules.assess([R("potassium", 6.4, "3.5 - 5.0")], {})
    assert "emergency" in t["advice"] and "112" in t["advice"]


def test_uncertain_value_that_could_raise_the_level_blocks_advice():
    uncertain = R("hemoglobin", 12.5, "12.0 - 15.5", value_alternative=6.2, needs_review=True)
    t = rules.assess([uncertain, R("sodium", 140, "135 - 145")], {"sex": "female", "age": 30})
    assert t["level"] == "routine" and t["possible_level"] == "urgent"
    assert t["provisional"] and t["needs_review_before_advice"] and "Urgent" in t["review_note"]


def test_uncertain_value_with_same_outcome_is_provisional_but_not_blocking():
    r = R("sodium", 140, "135 - 145", value_alternative=141, needs_review=True)
    t = rules.assess([r], {})
    assert t["provisional"] and not t["needs_review_before_advice"]


def test_no_results():
    t = rules.assess([], {})
    assert t["level"] is None and t["label"] == "Cannot assess"


# ---------------------------------------------------------------- demo documents (expected levels set by clinical reasoning, not by the code)
@pytest.mark.parametrize("name,expected,patient", [
    ("karthik_health_checkup.pdf", "routine", {"name": "Karthik Subramanian", "sex": "male"}),
    ("ananya_cbc_iron_report.pdf", "consult_soon", {"name": "Ananya Krishnan", "sex": "female"}),
    ("rahul_diabetes_panel.pdf", "consult_soon", {"name": "Rahul Menon", "sex": "male"}),
    ("fatima_lipid_thyroid_report.pdf", "consult_soon", {"name": "Fatima Sheikh", "sex": "female"}),
    ("meena_kidney_panel_critical.pdf", "urgent", {"name": "Meena Rajan", "sex": "female"}),
])
def test_demo_reports_get_the_expected_level(name, expected, patient):
    r = analyze_document(open(os.path.join(DOCS, name), "rb").read(), patient=patient)
    assert r["triage"]["level"] == expected and not r["triage"]["provisional"]


def test_scanned_critical_report_is_still_urgent_and_marks_uncertain_unit():
    r = analyze_document(open(os.path.join(DOCS, "meena_kidney_panel_critical_scan.jpg"), "rb").read(), patient={"name": "Meena Rajan", "sex": "female"})
    assert r["triage"]["level"] == "urgent" and r["triage"]["provisional"]
    assert r["summary"]["needs_review"] == 1


def test_prescriptions_have_no_triage():
    r = analyze_document(open(os.path.join(DOCS, "rahul_prescription.pdf"), "rb").read())
    assert r["triage"] is None
