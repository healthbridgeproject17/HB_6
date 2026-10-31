"""Names, units and sanity limits for the lab tests and medicines we recognise.
'plausible' is NOT a reference range: it is a very wide limit used only to catch
reading mistakes (e.g. haemoglobin 86 g/dL cannot be right)."""
import re

# key: (label, group, canonical unit, plausible (min, max), aliases)
_TESTS = {
    "hemoglobin": ("Haemoglobin", "CBC", "g/dL", (2, 25), ["haemoglobin", "hemoglobin", "hb", "hgb"]),
    "rbc": ("RBC count", "CBC", "million/µL", (1, 9), ["rbccount", "rbc", "redbloodcellcount", "redbloodcells"]),
    "hematocrit": ("Haematocrit (PCV)", "CBC", "%", (10, 70), ["haematocrit", "hematocrit", "pcv", "hct"]),
    "mcv": ("MCV", "CBC", "fL", (50, 140), ["mcv"]),
    "mch": ("MCH", "CBC", "pg", (10, 50), ["mch"]),
    "mchc": ("MCHC", "CBC", "g/dL", (20, 45), ["mchc"]),
    "wbc": ("WBC count", "CBC", "thousand/µL", (0.5, 100), ["wbccount", "wbc", "totalleucocytecount", "tlc", "whitebloodcellcount"]),
    "platelets": ("Platelet count", "CBC", "thousand/µL", (5, 1500), ["plateletcount", "platelets", "plt"]),
    "esr": ("ESR", "CBC", "mm/hr", (0, 150), ["esr"]),
    "glucose_fasting": ("Fasting glucose", "Glucose", "mg/dL", (20, 700), ["fastingplasmaglucose", "fastingbloodglucose", "fastingglucose", "fastingbloodsugar", "fbs", "fpg"]),
    "glucose_pp": ("Post-prandial glucose", "Glucose", "mg/dL", (20, 800), ["postprandialglucose", "postprandialbloodsugar", "ppbs", "ppg", "glucosepostprandial"]),
    "glucose_random": ("Random glucose", "Glucose", "mg/dL", (20, 800), ["randomglucose", "randombloodsugar", "rbs"]),
    "hba1c": ("HbA1c", "Glucose", "%", (3, 20), ["hba1c", "glycatedhemoglobin", "glycosylatedhemoglobin", "glycatedhaemoglobin"]),
    "cholesterol_total": ("Total cholesterol", "Lipids", "mg/dL", (50, 600), ["totalcholesterol", "cholesteroltotal", "cholesterol"]),
    "ldl": ("LDL cholesterol", "Lipids", "mg/dL", (10, 500), ["ldlcholesterol", "ldl", "ldlc"]),
    "hdl": ("HDL cholesterol", "Lipids", "mg/dL", (5, 150), ["hdlcholesterol", "hdl", "hdlc"]),
    "triglycerides": ("Triglycerides", "Lipids", "mg/dL", (20, 2000), ["triglycerides", "triglyceride", "tg"]),
    "vldl": ("VLDL cholesterol", "Lipids", "mg/dL", (1, 200), ["vldlcholesterol", "vldl"]),
    "creatinine": ("Serum creatinine", "Kidney", "mg/dL", (0.1, 20), ["serumcreatinine", "creatinine"]),
    "urea": ("Blood urea", "Kidney", "mg/dL", (3, 400), ["bloodurea", "urea", "serumurea"]),
    "bun": ("Blood urea nitrogen", "Kidney", "mg/dL", (1, 200), ["bloodureanitrogen", "bun"]),
    "uric_acid": ("Uric acid", "Kidney", "mg/dL", (0.5, 20), ["uricacid", "serumuricacid"]),
    "egfr": ("eGFR", "Kidney", "mL/min/1.73 m²", (1, 200), ["egfr", "estimatedgfr"]),
    "sodium": ("Serum sodium", "Electrolytes", "mmol/L", (90, 190), ["serumsodium", "sodium", "na"]),
    "potassium": ("Serum potassium", "Electrolytes", "mmol/L", (1.5, 10), ["serumpotassium", "potassium", "k"]),
    "chloride": ("Serum chloride", "Electrolytes", "mmol/L", (60, 140), ["serumchloride", "chloride"]),
    "calcium": ("Serum calcium", "Electrolytes", "mg/dL", (3, 18), ["serumcalcium", "calcium"]),
    "alt": ("SGPT (ALT)", "Liver", "U/L", (1, 3000), ["sgptalt", "sgpt", "alt", "alanineaminotransferase"]),
    "ast": ("SGOT (AST)", "Liver", "U/L", (1, 3000), ["sgotast", "sgot", "ast", "aspartateaminotransferase"]),
    "alp": ("Alkaline phosphatase", "Liver", "U/L", (10, 2500), ["alkalinephosphatase", "alp"]),
    "bilirubin_total": ("Total bilirubin", "Liver", "mg/dL", (0.05, 40), ["totalbilirubin", "bilirubintotal", "serumbilirubin", "bilirubin"]),
    "bilirubin_direct": ("Direct bilirubin", "Liver", "mg/dL", (0.01, 30), ["directbilirubin", "bilirubindirect", "conjugatedbilirubin"]),
    "albumin": ("Albumin", "Liver", "g/dL", (0.5, 7), ["albumin", "serumalbumin"]),
    "protein_total": ("Total protein", "Liver", "g/dL", (2, 12), ["totalprotein", "proteintotal", "serumprotein"]),
    "ggt": ("GGT", "Liver", "U/L", (1, 2000), ["ggt", "gammagt", "gammaglutamyltransferase"]),
    "tsh": ("TSH", "Thyroid", "mIU/L", (0.005, 150), ["tsh", "thyroidstimulatinghormone"]),
    "ft4": ("Free T4", "Thyroid", "ng/dL", (0.1, 8), ["freet4", "ft4", "freethyroxine"]),
    "ft3": ("Free T3", "Thyroid", "pg/mL", (0.5, 20), ["freet3", "ft3", "freetriiodothyronine"]),
    "t3": ("Total T3", "Thyroid", "ng/dL", (10, 600), ["totalt3", "t3"]),
    "t4": ("Total T4", "Thyroid", "µg/dL", (0.5, 30), ["totalt4", "t4"]),
    "ferritin": ("Serum ferritin", "Iron", "ng/mL", (0.5, 3000), ["serumferritin", "ferritin"]),
    "iron": ("Serum iron", "Iron", "µg/dL", (2, 600), ["serumiron", "iron"]),
    "tibc": ("TIBC", "Iron", "µg/dL", (50, 800), ["tibc", "totalironbindingcapacity"]),
    "vitamin_d": ("Vitamin D (25-OH)", "Vitamins", "ng/mL", (1, 200), ["vitamind", "25ohvitamind", "25hydroxyvitamind", "vitamind25oh"]),
    "vitamin_b12": ("Vitamin B12", "Vitamins", "pg/mL", (50, 3000), ["vitaminb12", "b12", "cobalamin"]),
}

TESTS = {k: dict(label=v[0], group=v[1], unit=v[2], plausible=v[3], aliases=v[4]) for k, v in _TESTS.items()}


def squash(text: str) -> str:
    """Lower case, keep letters/digits only (a few symbols kept for units)."""
    return re.sub(r"[^a-z0-9.%/]", "", (text or "").lower().replace("µ", "u").replace("μ", "u")).replace(".", "")


def squash_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


_ALIAS = sorted(((a, k) for k, t in TESTS.items() for a in t["aliases"]), key=lambda x: -len(x[0]))


def match_test(name: str):
    """Returns (key, how) with how = 'exact' | 'contains' | 'approximate', or (None, None)."""
    import difflib
    q = squash_name(name)
    if len(q) < 2:
        return None, None
    for alias, key in _ALIAS:
        if q == alias:
            return key, "exact"
    for alias, key in _ALIAS:
        if len(alias) >= 4 and alias in q:
            return key, "contains"
    best = difflib.get_close_matches(q, [a for a, _ in _ALIAS if len(a) >= 5], n=1, cutoff=0.86)
    if best:
        return dict(_ALIAS)[best[0]], "approximate"
    return None, None


# ---------- units ----------
_UNITS = {
    "g/dl": "g/dL", "gm/dl": "g/dL", "gms/dl": "g/dL", "g%": "g/dL", "mg/dl": "mg/dL", "%": "%", "fl": "fL", "pg": "pg",
    "u/l": "U/L", "iu/l": "U/L", "mmol/l": "mmol/L", "meq/l": "mEq/L", "ng/ml": "ng/mL", "ng/dl": "ng/dL",
    "ug/dl": "µg/dL", "mcg/dl": "µg/dL", "ug/ml": "µg/mL", "miu/l": "mIU/L", "uiu/ml": "µIU/mL", "miu/ml": "mIU/mL",
    "pg/ml": "pg/mL", "mm/hr": "mm/hr", "mm/h": "mm/hr", "mg/l": "mg/L", "million/ul": "million/µL", "millions/ul": "million/µL",
    "mill/ul": "million/µL", "10^6/ul": "million/µL", "thousand/ul": "thousand/µL", "thousands/ul": "thousand/µL",
    "10^3/ul": "thousand/µL", "ml/min/1.73m2": "mL/min/1.73 m²", "ml/min/1.73m": "mL/min/1.73 m²", "ml/min": "mL/min",
    "umol/l": "µmol/L", "seconds": "sec", "sec": "sec",
}


def normalize_unit(text: str):
    t = (text or "").lower().replace("µ", "u").replace("μ", "u").replace(" ", "").replace("²", "2")
    t = re.sub(r"[^a-z0-9%/.^]", "", t)
    return _UNITS.get(t)


# ---------- medicines ----------
MEDICINES = [
    "paracetamol", "acetaminophen", "ibuprofen", "diclofenac", "aspirin", "naproxen", "tramadol", "amoxicillin", "amoxicillin clavulanate",
    "azithromycin", "ciprofloxacin", "levofloxacin", "doxycycline", "cefixime", "cefuroxime", "metronidazole", "cotrimoxazole", "nitrofurantoin",
    "pantoprazole", "omeprazole", "esomeprazole", "rabeprazole", "ranitidine", "domperidone", "ondansetron", "metoclopramide",
    "metformin", "glimepiride", "gliclazide", "sitagliptin", "vildagliptin", "pioglitazone", "insulin glargine", "insulin",
    "amlodipine", "telmisartan", "losartan", "olmesartan", "enalapril", "ramipril", "atenolol", "metoprolol", "bisoprolol", "carvedilol",
    "hydrochlorothiazide", "chlorthalidone", "furosemide", "spironolactone", "torsemide", "clopidogrel", "warfarin", "rivaroxaban",
    "atorvastatin", "rosuvastatin", "simvastatin", "fenofibrate", "ezetimibe", "levothyroxine", "thyroxine", "carbimazole",
    "ferrous sulfate", "ferrous fumarate", "folic acid", "cyanocobalamin", "vitamin d3", "cholecalciferol", "calcium carbonate",
    "sodium bicarbonate", "potassium chloride", "salbutamol", "montelukast", "cetirizine", "levocetirizine", "loratadine", "prednisolone",
    "dexamethasone", "methylprednisolone", "amitriptyline", "escitalopram", "sertraline", "alprazolam", "clonazepam", "gabapentin",
    "pregabalin", "levetiracetam", "sodium valproate", "carbamazepine", "allopurinol", "febuxostat", "colchicine", "albendazole",
    "ivermectin", "fluconazole", "acyclovir", "oseltamivir", "lactulose", "bisacodyl", "oral rehydration salts", "zinc sulfate",
]
