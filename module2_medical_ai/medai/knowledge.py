"""Plain-language explanations for each lab test, written for patients.
Rules for every line: describe, never diagnose ('can be', 'may'); self-care is
general lifestyle only; NEVER start, stop or change a medicine or give a dose.
A doctor must review this file (docs/PATIENT_ADVICE_TEXTS.md is generated from it)."""

CALL = "Call 112 or go to the nearest hospital emergency department"

# key: (what it measures, {"low": (meaning, [may affect], [self-care], [see a doctor sooner if]), "high": (...)})
T = {}


def add(key, measures, low=None, high=None):
    T[key] = {"measures": measures, "low": low, "high": high}


add("hemoglobin", "the protein in red blood cells that carries oxygen around the body",
    ("Low haemoglobin is called anaemia: the blood carries less oxygen than usual.",
     ["Tiredness and weakness", "Breathlessness on stairs or when walking", "Pale skin, dizziness or headaches", "A fast heartbeat"],
     ["Eat iron-rich foods such as leafy greens, pulses, eggs and meat, together with vitamin C foods (lemon, orange, tomato)",
      "Avoid tea and coffee with meals, because they reduce iron absorption", "Rest when you feel tired and avoid sudden heavy effort"],
     ["Chest pain, fainting or severe breathlessness", "Black stools, vomiting blood, or any heavy bleeding"]),
    ("High haemoglobin can happen with dehydration, smoking, living at high altitude, or conditions that make the body make too many red cells.",
     ["Headache, dizziness or a flushed face"], ["Drink enough water", "If you smoke, ask for help to stop"],
     ["Chest pain, a severe headache, or weakness on one side of the body"]))
add("rbc", "the number of red blood cells", ("Fewer red cells than usual, usually together with a low haemoglobin (anaemia).", ["Tiredness and breathlessness"],
    ["Eat a balanced diet with iron-rich foods, pulses and leafy greens"], ["Chest pain, fainting or severe breathlessness"]),
    ("More red cells than usual, which can follow dehydration, smoking or low oxygen levels.", ["Headache or a flushed face"], ["Drink enough water"], ["Chest pain or severe headache"]))
add("hematocrit", "the share of the blood that is made up of red cells", ("A low share of red cells goes with anaemia.", ["Tiredness and breathlessness"],
    ["Eat iron-rich foods and rest when tired"], ["Chest pain, fainting or severe breathlessness"]),
    ("A high share of red cells often means dehydration, and sometimes too many red cells.", ["Headache or dizziness"], ["Drink enough water"], ["Chest pain or severe headache"]))
add("mcv", "the average size of your red blood cells", ("Smaller red cells are common in iron deficiency and in some inherited blood traits.", ["Often only tiredness, together with anaemia"],
    ["Eat iron-rich foods"], ["Severe tiredness or breathlessness"]),
    ("Larger red cells can go with low vitamin B12 or folate, alcohol use, or liver or thyroid problems.", ["Tiredness, tingling in hands or feet"],
     ["Eat a balanced diet with eggs, dairy, pulses and green vegetables", "Limit alcohol"], ["Numbness that spreads or trouble walking"]))
add("mch", "the average amount of haemoglobin in each red cell", ("Low values go with iron deficiency.", ["Tiredness"], ["Eat iron-rich foods"], ["Severe tiredness or breathlessness"]),
    ("High values go with larger red cells, for example with low vitamin B12 or folate.", ["Tiredness"], ["Eat a balanced diet"], ["Numbness that spreads"]))
add("mchc", "how concentrated the haemoglobin is inside red cells", ("Low values go with iron deficiency.", ["Tiredness"], ["Eat iron-rich foods"], ["Severe tiredness or breathlessness"]), None)
add("wbc", "the white blood cells that fight infection",
    ("Fewer white cells than usual. Causes include viral infections, some medicines, and conditions of the bone marrow.", ["More frequent infections or fevers"],
     ["Wash your hands often", "Avoid close contact with people who are ill"], ["A fever of 38 C (100.4 F) or higher", "A sore throat or cough that is getting worse"]),
    ("Often the body's response to infection or inflammation. Stress, smoking and some medicines also raise it.", ["Fever, tiredness or pain at the site of an infection"],
     ["Rest and drink fluids", "If you smoke, ask for help to stop"], ["A fever that does not settle", "Unexplained weight loss, night sweats or bleeding"]))
add("platelets", "the cell fragments that help blood to clot",
    ("Platelets help blood to clot. A low count can mean easier bruising or bleeding.", ["Easy bruising", "Nosebleeds or bleeding gums", "Tiny red spots on the skin"],
     ["Avoid rough sports and activities where you could be injured", "Ask your doctor before using any pain-relief tablets"],
     ["Bleeding that does not stop", "Black stools, blood in the urine, or a severe headache"]),
    ("Platelets can rise with infection, inflammation or iron deficiency.", ["Usually no symptoms"], ["Drink fluids and stay active"],
     ["A sudden severe headache, chest pain, or a painful swollen leg"]))
add("esr", "a general sign of inflammation in the body", None, ("A raised ESR points to inflammation somewhere in the body. It does not say where, and many ordinary things raise it.",
    ["Often no symptoms by itself"], ["Rest when unwell and drink fluids"], ["Fever that lasts, joint swelling, or unexplained weight loss"]))
_sugar_high = ("Sugar is above the usual range. A fasting value of 100-125 mg/dL is the pre-diabetes range; 126 mg/dL or more on repeated tests suggests diabetes.",
               ["Feeling very thirsty and passing urine often", "Tiredness", "Blurred vision", "Cuts that heal slowly"],
               ["Cut down on sugary drinks, sweets and refined foods", "Choose whole grains, pulses and vegetables, and keep portions of rice and bread moderate",
                "Walk or do other moderate activity for about 30 minutes on most days", "Do not skip meals or start a crash diet"],
               ["Very strong thirst with frequent urination, vomiting, drowsiness or confusion", "Fruity-smelling breath or fast, deep breathing"])
_sugar_low = ("Low blood sugar can cause shakiness and sweating and can become dangerous if it falls further.", ["Shakiness, sweating and hunger", "Confusion or fainting"],
              ["If you feel these symptoms, have something sugary straight away and then a proper meal", "Do not go long hours without food"],
              ["Fainting, a seizure, or not being able to swallow: " + CALL])
add("glucose_fasting", "the sugar in your blood after not eating overnight", _sugar_low, _sugar_high)
add("glucose_pp", "the sugar in your blood two hours after a meal", _sugar_low, _sugar_high)
add("glucose_random", "the sugar in your blood at a random time of day", _sugar_low, _sugar_high)
add("hba1c", "your average blood sugar over the last 2-3 months", None,
    ("HbA1c of 5.7-6.4% is the pre-diabetes range and 6.5% or more is in the diabetes range. The higher it is, the higher the long-term risk to eyes, kidneys, nerves and heart.",
     _sugar_high[1], _sugar_high[2], _sugar_high[3]))
_fats = ["Choose fruit, vegetables, whole grains, pulses, nuts and fish", "Cut down on fried food, ghee or butter, bakery items and processed meat",
         "Do about 30 minutes of activity on most days", "If you smoke, ask for help to stop, and limit alcohol"]
_fat_help = ["Chest pain or pressure, or sudden weakness on one side of the body: " + CALL]
add("cholesterol_total", "the total amount of cholesterol (a blood fat)", None,
    ("High cholesterol usually causes no symptoms but, over years, raises the risk of heart disease and stroke.", ["No symptoms now; a long-term risk to the heart and blood vessels"], _fats, _fat_help))
add("ldl", "the 'bad' cholesterol that can build up in blood vessels", None,
    ("High LDL cholesterol raises the long-term risk of blocked blood vessels, heart attack and stroke.", ["No symptoms now; a long-term risk to the heart and blood vessels"], _fats, _fat_help))
add("hdl", "the 'good' cholesterol that helps clear fat from the blood",
    ("A low HDL cholesterol reduces your natural protection against heart disease.", ["No symptoms; a long-term risk to the heart"],
     ["Be active most days: regular exercise raises HDL", "Choose nuts, olive or groundnut oil, and fish", "If you smoke, stopping helps"], _fat_help), None)
add("triglycerides", "the fat carried in your blood that comes from food and sugar", None,
    ("High triglycerides are often linked to sugary and fatty food, alcohol, extra weight and diabetes. Very high levels can inflame the pancreas.",
     ["Usually no symptoms; a long-term risk to the heart"], ["Cut down on sweets, sugary drinks, refined flour and fried food", "Limit alcohol", "Do about 30 minutes of activity on most days"],
     ["Severe pain in the upper belly, especially with vomiting"]))
add("vldl", "a type of cholesterol made by the liver that carries triglycerides", None,
    ("A high VLDL usually goes along with high triglycerides.", ["Usually no symptoms"], _fats, _fat_help))
_kidney_self = ["Drink fluids normally unless a doctor has told you to limit them", "Ask your doctor before using pain-relief tablets such as ibuprofen or diclofenac, which can harm the kidneys",
                "Cut down on salt", "Keep blood pressure and blood sugar well controlled"]
_kidney_help = ["Very little urine, severe swelling, breathlessness, confusion or chest pain"]
add("creatinine", "a waste product that healthy kidneys remove from the blood", None,
    ("A high creatinine suggests the kidneys are not filtering as well as they should. Dehydration and some medicines can also raise it.",
     ["Tiredness", "Swelling of the feet or face", "Passing less urine, or foamy urine", "Nausea or loss of appetite"], _kidney_self, _kidney_help))
add("urea", "a waste product made when the body breaks down protein", None,
    ("A high urea can mean the kidneys are not clearing waste well, or that you are dehydrated.", ["Tiredness", "Nausea or loss of appetite", "Itching"], _kidney_self, _kidney_help))
add("bun", "the nitrogen in your blood that comes from urea, a waste product", None,
    ("A high BUN can mean the kidneys are not clearing waste well, or that you are dehydrated.", ["Tiredness", "Nausea"], _kidney_self, _kidney_help))
add("egfr", "an estimate of how well the kidneys filter the blood (higher is better)",
    ("A low eGFR means the kidneys are filtering less than normal. Below 60 for three months or more is called chronic kidney disease; below 15 is severe.",
     ["Tiredness", "Swelling of the feet or face", "Passing less urine", "Nausea, itching or loss of appetite"], _kidney_self, _kidney_help), None)
add("uric_acid", "a waste product that can form crystals in joints when it is too high", None,
    ("A high uric acid can cause gout (a sudden, painful, swollen joint, often the big toe) and kidney stones.", ["A sudden painful, swollen joint", "Pain in the side or back from kidney stones"],
     ["Drink plenty of water", "Limit red meat, organ meats, shellfish, alcohol (especially beer) and sugary drinks"], ["A hot, swollen, very painful joint with fever"]))
add("sodium", "the salt level in your blood, which controls water balance",
    ("Low sodium can follow drinking too much water, vomiting or diarrhoea, some medicines, and some illnesses.", ["Headache, nausea and tiredness", "Muscle cramps", "Confusion when it is very low"],
     ["Do not drink excessive amounts of water", "Do not change your salt intake sharply without advice"], ["Confusion, fits or fainting: " + CALL]),
    ("High sodium usually means the body is short of water.", ["Strong thirst", "Dry mouth and tiredness", "Confusion when it is very high"], ["Drink water regularly through the day"],
     ["Confusion, drowsiness or very little urine"]))
add("potassium", "a mineral that keeps the heart and muscles working",
    ("Low potassium can come from vomiting, diarrhoea, or some water tablets.", ["Muscle weakness and cramps", "Tiredness", "An irregular heartbeat when it is very low"],
     ["Eat potassium-rich foods such as bananas, potatoes, pulses and coconut water, unless your doctor has told you to limit potassium"], ["Palpitations, severe weakness or fainting: " + CALL]),
    ("Too much potassium can disturb the heart rhythm, especially when the kidneys are weak.", ["Weakness or tingling", "Palpitations or an irregular heartbeat"],
     ["Do not wait to see if it settles: contact a doctor now", "Until a doctor advises you, avoid very potassium-rich foods (banana, coconut water, potato, tomato, orange) and salt substitutes, which contain potassium"],
     ["Palpitations, chest pain, severe weakness or fainting: " + CALL]))
add("chloride", "a salt that works with sodium to balance body fluids", ("Low chloride often goes with vomiting or low sodium.", ["Weakness"], ["Drink fluids and rest"], ["Persistent vomiting or confusion"]),
    ("High chloride often goes with dehydration.", ["Thirst"], ["Drink water regularly"], ["Confusion or very little urine"]))
add("calcium", "the mineral that keeps bones, muscles and nerves working",
    ("Low calcium can come from low vitamin D or kidney or parathyroid problems.", ["Tingling around the mouth or in the fingers", "Muscle cramps"],
     ["Eat calcium-rich foods such as milk, curd, ragi and green leafy vegetables", "Get safe morning sunlight"], ["Muscle spasms, fits or fainting: " + CALL]),
    ("High calcium can come from an overactive parathyroid gland, or other conditions.", ["Thirst and passing a lot of urine", "Constipation", "Tiredness or confusion"],
     ["Drink plenty of water"], ["Confusion, severe weakness or vomiting"]))
_liver_self = ["Avoid alcohol", "Ask your doctor before using any medicine or herbal remedy, because many can strain the liver", "Choose a balanced diet and aim for a healthy weight"]
_liver_help = ["Yellow skin or eyes, dark urine, or severe belly pain", "Repeated vomiting or confusion"]
add("alt", "an enzyme (SGPT) released by liver cells when they are irritated", None,
    ("A high ALT means liver cells are irritated or injured. Common causes are fatty liver, alcohol, viral hepatitis and some medicines.", ["Often no symptoms", "Tiredness or nausea in more serious cases"], _liver_self, _liver_help))
add("ast", "an enzyme (SGOT) found in the liver and muscles", None,
    ("A high AST can come from the liver or from muscles. Common liver causes are fatty liver, alcohol, viral hepatitis and some medicines.", ["Often no symptoms", "Tiredness or nausea in more serious cases"], _liver_self, _liver_help))
add("alp", "an enzyme found in the liver and bones", None, ("A high ALP can come from the liver, the bile ducts or the bones.", ["Often no symptoms"], _liver_self, _liver_help))
add("ggt", "a liver enzyme that is sensitive to alcohol and some medicines", None, ("A high GGT often goes with alcohol use, fatty liver or some medicines.", ["Often no symptoms"], _liver_self, _liver_help))
add("bilirubin_total", "a yellow substance made when old red cells break down", None,
    ("A high bilirubin can make the skin and eyes look yellow. Causes range from harmless to liver or bile duct problems.", ["Yellow skin or eyes", "Dark urine", "Itching"], _liver_self, _liver_help))
add("bilirubin_direct", "the part of bilirubin that has been processed by the liver", None,
    ("A high direct bilirubin can point to a liver or bile duct problem.", ["Yellow skin or eyes", "Dark urine", "Pale stools"], _liver_self, _liver_help))
add("albumin", "the main protein made by the liver", ("A low albumin can follow liver disease, kidney disease, poor nutrition or long illness.", ["Swelling of the feet", "Tiredness"],
    ["Eat enough protein: eggs, pulses, dairy, fish"], ["Rapid swelling or breathlessness"]), None)
add("protein_total", "all the proteins in the blood", ("Low total protein can follow poor nutrition, liver or kidney disease.", ["Swelling of the feet", "Tiredness"], ["Eat enough protein"], ["Rapid swelling or breathlessness"]),
    ("High total protein can follow dehydration or long-term inflammation.", ["Often no symptoms"], ["Drink enough water"], ["Unexplained weight loss or bone pain"]))
add("tsh", "the signal your brain sends to your thyroid gland",
    ("A low TSH usually means the thyroid is overactive. It can also happen when thyroid medicine is more than the body needs, which is something to discuss with your doctor.",
     ["A racing heart and sweating", "Weight loss, anxiety or trembling hands"], ["Avoid too much caffeine", "Keep regular sleep"], ["Chest pain, fainting or a very fast heartbeat"]),
    ("A high TSH usually means the thyroid is underactive (hypothyroidism).", ["Tiredness and feeling cold", "Weight gain, constipation and dry skin", "Low mood or a slow heartbeat"],
     ["Keep regular sleep and activity", "Eat a balanced diet", "Do not start iodine or thyroid supplements on your own"], ["Extreme tiredness with confusion, or a very slow heartbeat"]))
add("ft4", "the active thyroid hormone in your blood",
    ("A low free T4, especially with a high TSH, goes with an underactive thyroid.", ["Tiredness and feeling cold", "Weight gain and constipation"], ["Keep regular sleep and activity"], ["Extreme tiredness with confusion"]),
    ("A high free T4 goes with an overactive thyroid.", ["A racing heart, sweating, weight loss", "Anxiety or trembling hands"], ["Avoid too much caffeine"], ["Chest pain, fainting or a very fast heartbeat"]))
add("ft3", "the most active thyroid hormone", ("A low free T3 can go with an underactive thyroid or a long illness.", ["Tiredness"], ["Keep regular sleep"], ["Extreme tiredness"]),
    ("A high free T3 can go with an overactive thyroid.", ["A racing heart, sweating"], ["Avoid too much caffeine"], ["Chest pain or fainting"]))
add("t3", "total triiodothyronine, a thyroid hormone", ("A low value can go with an underactive thyroid.", ["Tiredness"], ["Keep regular sleep"], ["Extreme tiredness"]),
    ("A high value can go with an overactive thyroid.", ["A racing heart"], ["Avoid too much caffeine"], ["Chest pain or fainting"]))
add("t4", "total thyroxine, a thyroid hormone", ("A low value can go with an underactive thyroid.", ["Tiredness"], ["Keep regular sleep"], ["Extreme tiredness"]),
    ("A high value can go with an overactive thyroid.", ["A racing heart"], ["Avoid too much caffeine"], ["Chest pain or fainting"]))
add("ferritin", "the iron stored in your body",
    ("Low ferritin means the body's iron stores are low. Common reasons are too little iron in the diet, heavy periods, or slow blood loss.", ["Tiredness", "Hair loss", "Feeling cold or short of breath"],
     ["Eat iron-rich foods such as leafy greens, pulses, eggs and meat with vitamin C foods", "Avoid tea and coffee with meals"], ["Black stools or heavy bleeding", "Chest pain or fainting"]),
    ("High ferritin can follow inflammation, liver disease, or too much iron in the body.", ["Often no symptoms"], ["Avoid alcohol"], ["Yellow skin or eyes, or severe tiredness"]))
add("iron", "the iron circulating in your blood", ("Low serum iron goes with iron deficiency.", ["Tiredness"], ["Eat iron-rich foods with vitamin C foods"], ["Chest pain or fainting"]),
    ("High serum iron can follow recent iron tablets or other causes.", ["Often no symptoms"], ["Do not take iron on your own without advice"], ["Severe belly pain or vomiting"]))
add("tibc", "the blood's capacity to carry iron", ("A low capacity can go with inflammation or poor nutrition.", ["Tiredness"], ["Eat a balanced diet"], ["Severe tiredness"]),
    ("A high capacity goes with iron deficiency.", ["Tiredness"], ["Eat iron-rich foods"], ["Chest pain or fainting"]))
add("vitamin_d", "your vitamin D level, which helps the body use calcium for bones",
    ("Low vitamin D is common. It can weaken bones and muscles over time.", ["Bone or muscle aches", "Tiredness"],
     ["Get some morning sunlight on your arms and legs, a few times a week", "Eat eggs, fish and fortified milk", "Ask your doctor whether you need a supplement and for how long"], ["A bone that hurts after a small fall", "Severe muscle weakness"]), None)
add("vitamin_b12", "vitamin B12, which the body needs for nerves and red blood cells",
    ("Low vitamin B12 can cause anaemia and affect the nerves.", ["Tiredness", "Tingling or numbness in the hands and feet", "Memory or mood changes", "A sore tongue"],
     ["Eat eggs, dairy, fish or meat; people who eat no animal foods should ask their doctor about fortified foods or supplements"], ["Numbness that is spreading, or trouble walking"]), None)

# patterns: label explanation + questions to ask the doctor
PATTERNS = {
    "iron_deficiency": ("Low haemoglobin with small red cells and/or low iron stores is the typical picture of iron deficiency anaemia.",
                        ["What is causing my low iron (food, periods or bleeding)?", "Do I need treatment, and when should the blood test be repeated?"]),
    "kidney_impairment": ("Creatinine, urea and/or eGFR together suggest the kidneys are not filtering as well as they should.",
                          ["How well are my kidneys working and what is the cause?", "Do I need a urine test, an ultrasound, or a kidney specialist?"]),
    "hyperkalaemia_kidney": ("When the kidneys are weak, potassium can build up and disturb the heart rhythm. This combination needs same-day medical attention.",
                             ["Do I need a heart tracing (ECG) and a repeat potassium test today?"]),
    "low_counts": ("Several types of blood cell are low together. A doctor will want to find the reason.", ["Why are several of my blood counts low, and do I need more tests?"]),
    "diabetes_range": ("The blood sugar results are in the diabetes range.", ["Do I have diabetes, and do the tests need repeating?", "What should I change in my food and activity, and when should I be checked again?"]),
    "prediabetes": ("Blood sugar is above normal but below the diabetes range. Lifestyle changes can often bring it back down.", ["What can I do to lower my sugar, and when should I be tested again?"]),
    "hypothyroid": ("A raised TSH, especially with a low free T4, points to an underactive thyroid.", ["Do I need treatment for my thyroid, and when should the test be repeated?"]),
    "hyperthyroid": ("A low TSH with a high free T4 points to an overactive thyroid.", ["What is causing my overactive thyroid, and do I need more tests?"]),
    "mixed_lipids": ("Both LDL cholesterol and triglycerides are high, which raises the long-term risk to the heart.", ["What is my heart risk, and do I need treatment besides diet and exercise?"]),
    "liver_enzymes": ("The liver enzymes are well above normal, which can point to liver irritation or injury.", ["What is irritating my liver, and do I need a scan or more tests?"]),
}

MEDICINE_INFO = {
    "metformin": "a medicine used to control blood sugar in type 2 diabetes", "glimepiride": "a medicine that helps the body release insulin to lower blood sugar",
    "insulin": "a hormone medicine that lowers blood sugar", "amlodipine": "a medicine used to lower blood pressure", "telmisartan": "a medicine used to lower blood pressure",
    "losartan": "a medicine used to lower blood pressure", "atorvastatin": "a medicine (a statin) that lowers cholesterol", "rosuvastatin": "a medicine (a statin) that lowers cholesterol",
    "levothyroxine": "a medicine that replaces thyroid hormone", "ferrous sulfate": "an iron supplement for low iron", "furosemide": "a 'water tablet' that helps the body remove extra fluid",
    "sodium bicarbonate": "a medicine used to reduce acid build-up in the blood, for example in some kidney conditions", "paracetamol": "a medicine for pain and fever",
    "ibuprofen": "a pain and inflammation medicine that can affect the stomach and kidneys", "amoxicillin": "an antibiotic for bacterial infections", "azithromycin": "an antibiotic for bacterial infections",
    "pantoprazole": "a medicine that reduces stomach acid", "omeprazole": "a medicine that reduces stomach acid", "aspirin": "a medicine that thins the blood and relieves pain",
    "clopidogrel": "a medicine that helps prevent blood clots", "cetirizine": "a medicine for allergy symptoms", "folic acid": "a vitamin supplement", "vitamin d3": "a vitamin D supplement",
    "cholecalciferol": "a vitamin D supplement", "cyanocobalamin": "a vitamin B12 supplement", "calcium carbonate": "a calcium supplement or antacid", "spironolactone": "a water tablet that also helps the heart and blood pressure",
    "hydrochlorothiazide": "a water tablet used to lower blood pressure", "salbutamol": "a reliever medicine that opens the airways",
}
