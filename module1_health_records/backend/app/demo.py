"""Loads FICTIONAL demo data: doctors, patients, records, prescriptions,
medication history and documents (from demo_documents/). Nothing here is real."""
import io
import json
import os
import random
from datetime import date, datetime, timedelta, timezone

from flask import current_app
from PIL import Image, ImageDraw

from .extensions import db
from .models import (AuditLog, Doctor, Document, MedicalRecord, MedicationLog,
                     Patient, Prescription, User)
from .utils.documents import delete_document_file, save_document
from .utils.health_id import generate_health_id
from .utils.photos import delete_photo, save_photo

DOMAIN = "demo.healthbridge.test"  # reserved .test domain: can never be a real address
NOW = lambda: datetime.now(timezone.utc)  # noqa: E731
ago = lambda days, hour=9: (NOW() - timedelta(days=days)).replace(hour=hour, minute=random.randint(0, 40), second=0, microsecond=0)  # noqa: E731

DOCTORS = [
    ("meera.iyer", "Dr. Meera Iyer", "General Medicine", "DEMO-REG-18822"),
    ("arjun.nair", "Dr. Arjun Nair", "Internal Medicine", "DEMO-REG-20417"),
]

PATIENTS = [
    dict(key="ananya.krishnan", name="Ananya Krishnan", dob=date(1995, 3, 14), sex="female", phone="+91 90000 10001",
         emergency="Lakshmi Krishnan (mother) +91 90000 10011", allergies="No known drug allergies", color=(236, 130, 160)),
    dict(key="rahul.menon", name="Rahul Menon", dob=date(1978, 7, 2), sex="male", phone="+91 90000 10002",
         emergency="Divya Menon (wife) +91 90000 10012", allergies="Penicillin (rash)", color=(86, 140, 220)),
    dict(key="fatima.sheikh", name="Fatima Sheikh", dob=date(1966, 11, 23), sex="female", phone="+91 90000 10003",
         emergency="Imran Sheikh (son) +91 90000 10013", allergies="None recorded", color=(120, 190, 150)),
    dict(key="karthik.subramanian", name="Karthik Subramanian", dob=date(1990, 1, 9), sex="male", phone="+91 90000 10004",
         emergency="Priya S. (sister) +91 90000 10014", allergies="Dust (mild)", color=(240, 180, 90)),
    dict(key="meena.rajan", name="Meena Rajan", dob=date(1951, 5, 30), sex="female", phone="+91 90000 10005",
         emergency="Suresh Rajan (son) +91 90000 10015", allergies="Sulfa drugs", color=(170, 130, 210)),
    dict(key="arun.das", name="Arun Das", dob=date(2001, 9, 18), sex="male", phone=None, emergency=None, allergies=None, color=(150, 160, 170)),
]
WITH_PHOTO = {"ananya.krishnan", "rahul.menon", "meena.rajan"}

# records: (patient, doctor, type, title, details, days_ago)
RECORDS = [
    ("ananya.krishnan", "meera.iyer", "visit", "Tiredness and breathlessness on exertion", "Pallor noted. No bleeding history. CBC and iron studies advised.", 6),
    ("ananya.krishnan", "meera.iyer", "diagnosis", "Iron-deficiency anaemia", "Low haemoglobin with low ferritin and microcytic indices. Start oral iron, recheck CBC in 8 weeks.", 2),
    ("rahul.menon", "arjun.nair", "diagnosis", "Type 2 diabetes mellitus", "HbA1c 8.9%. Started metformin. Diet and exercise counselling given.", 21),
    ("rahul.menon", "arjun.nair", "diagnosis", "Essential hypertension", "BP 148/92 on two readings. Started amlodipine 5 mg.", 21),
    ("rahul.menon", "arjun.nair", "note", "Follow-up", "Home sugars improving. Continue current medicines. Review in 4 weeks.", 4),
    ("fatima.sheikh", "meera.iyer", "diagnosis", "Primary hypothyroidism", "TSH 9.8 with low free T4. Start levothyroxine 50 mcg.", 9),
    ("fatima.sheikh", "meera.iyer", "diagnosis", "Dyslipidaemia", "LDL 172, triglycerides 240. Start atorvastatin and diet changes.", 9),
    ("karthik.subramanian", "meera.iyer", "visit", "Routine annual health check-up", "No complaints. Examination normal. All screening tests within range.", 12),
    ("meena.rajan", "arjun.nair", "diagnosis", "Chronic kidney disease, advanced", "Creatinine 3.4, eGFR 14. Potassium critically high at 6.4. Urgent nephrology referral.", 1),
    ("meena.rajan", "arjun.nair", "note", "Urgent advice", "Avoid potassium-rich foods. Repeat kidney panel in 3 days. Go to emergency if palpitations or weakness.", 1),
]
# one amended record to show the amendment trail: (patient, index in RECORDS to amend, new details, reason)
AMENDMENT = ("rahul.menon", "Type 2 diabetes mellitus", "HbA1c 8.9%. Started metformin 500 mg twice daily. Diet and exercise counselling given. Annual eye and foot check advised.",
             "Added screening advice after reviewing guidelines")

# prescriptions: (patient, doctor, medicine, strength, dose, route, frequency, duration, status, start_days_ago, length_days, logs)
RX = [
    ("ananya.krishnan", "meera.iyer", "Ferrous sulfate", "200 mg", "1 tablet", "oral", "once daily", "60 days", "confirmed", 2, 60, "mixed"),
    ("rahul.menon", "arjun.nair", "Metformin", "500 mg", "1 tablet", "oral", "twice daily after food", "30 days", "confirmed", 21, 30, "good"),
    ("rahul.menon", "arjun.nair", "Amlodipine", "5 mg", "1 tablet", "oral", "once daily, morning", "30 days", "confirmed", 21, 30, "good"),
    ("rahul.menon", "arjun.nair", "Atorvastatin", "20 mg", "1 tablet", "oral", "once daily at night", "30 days", "confirmed", 4, 30, "mixed"),
    ("rahul.menon", "arjun.nair", "Glimepiride", "1 mg", "1 tablet", "oral", "once daily before breakfast", "14 days", "discontinued", 21, 14, None),
    ("fatima.sheikh", "meera.iyer", "Levothyroxine", "50 mcg", "1 tablet", "oral", "once daily, empty stomach", "60 days", "confirmed", 9, 60, "good"),
    ("fatima.sheikh", "meera.iyer", "Atorvastatin", "20 mg", "1 tablet", "oral", "once daily at night", "60 days", "confirmed", 9, 60, "poor"),
    ("meena.rajan", "arjun.nair", "Sodium bicarbonate", "500 mg", "1 tablet", "oral", "twice daily", "14 days", "draft", 0, 14, None),
    ("meena.rajan", "arjun.nair", "Furosemide", "40 mg", "1 tablet", "oral", "once daily, morning", "14 days", "draft", 0, 14, None),
]
PATTERN = {"good": 0.92, "mixed": 0.7, "poor": 0.4}


def _avatar(color, initial):
    img = Image.new("RGB", (400, 400), (235, 242, 245))
    d = ImageDraw.Draw(img)
    d.ellipse((120, 70, 280, 230), fill=color)           # head
    d.ellipse((50, 250, 350, 560), fill=color)           # shoulders
    d.text((190, 135), initial, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _clear_clinical(folder, patients):
    for p in patients:
        for doc in Document.query.filter_by(patient_id=p.id).all():
            delete_document_file(folder, doc.stored_path)
        MedicationLog.query.filter_by(patient_id=p.id).delete()
        Prescription.query.filter_by(patient_id=p.id).update({"source_document_id": None})
        Prescription.query.filter_by(patient_id=p.id).delete()
        for rec in MedicalRecord.query.filter_by(patient_id=p.id).order_by(MedicalRecord.id.desc()).all():
            db.session.delete(rec)
            db.session.flush()
        Document.query.filter_by(patient_id=p.id).delete()
        delete_photo(folder, p.photo_path)
        p.photo_path = None
    db.session.flush()


def seed_demo(password, demo_dir, reset=False):
    """Create (or with reset=True recreate) the demo data. Returns a summary dict."""
    if current_app.config["ENV_NAME"] == "production":
        raise RuntimeError("Demo data cannot be loaded in production.")
    random.seed(7)
    folder = current_app.config["UPLOAD_FOLDER"]
    email = lambda key: f"{key}@{DOMAIN}"  # noqa: E731
    existing = User.query.filter(User.email.like(f"%@{DOMAIN}")).count()
    if existing and not reset:
        return {"skipped": True, "existing": existing}

    users = {}
    for key, name, specialty, reg in DOCTORS:
        u = User.query.filter_by(email=email(key)).first() or User(name=name, email=email(key), role="doctor")
        u.name, u.is_active, u.must_change_password = name, True, False
        u.set_password(password)
        if u.id is None:
            db.session.add(u)
            db.session.flush()
            db.session.add(Doctor(user_id=u.id, specialty=specialty, license_no=reg))
        users[key] = u
    patients = {}
    for spec in PATIENTS:
        u = User.query.filter_by(email=email(spec["key"])).first() or User(name=spec["name"], email=email(spec["key"]), role="patient")
        u.name, u.is_active, u.must_change_password = spec["name"], True, False
        u.set_password(password)
        if u.id is None:
            db.session.add(u)
            db.session.flush()
            db.session.add(Patient(user_id=u.id, health_id=generate_health_id()))
            db.session.flush()
        p = Patient.query.filter_by(user_id=u.id).first()
        p.dob, p.sex, p.phone, p.emergency_contact, p.allergies = spec["dob"], spec["sex"], spec["phone"], spec["emergency"], spec["allergies"]
        users[spec["key"]], patients[spec["key"]] = u, p
    db.session.flush()
    if reset:
        _clear_clinical(folder, list(patients.values()))

    for spec in PATIENTS:
        if spec["key"] in WITH_PHOTO:
            p = patients[spec["key"]]
            p.photo_path = save_photo(folder, p.id, _avatar(spec["color"], spec["name"][0]))

    doctor = lambda key: db.session.query(Doctor).filter_by(user_id=users[key].id).first()  # noqa: E731
    made = {}
    for pat, doc, rtype, title, details, days in RECORDS:
        rec = MedicalRecord(patient_id=patients[pat].id, doctor_id=doctor(doc).id, record_type=rtype, title=title, details=details,
                            created_by_user_id=users[doc].id, created_at=ago(days))
        db.session.add(rec)
        db.session.flush()
        made[(pat, title)] = rec
    pat, title, new_details, reason = AMENDMENT
    original = made[(pat, title)]
    db.session.add(MedicalRecord(patient_id=original.patient_id, doctor_id=original.doctor_id, record_type=original.record_type,
                                 title=original.title, details=new_details, amended_from_id=original.id,
                                 created_by_user_id=original.created_by_user_id, amendment_reason=reason, created_at=ago(3)))

    manifest = json.load(open(os.path.join(demo_dir, "manifest.json")))
    docs = {}
    for item in manifest:
        path = os.path.join(demo_dir, item["file"])
        data = open(path, "rb").read()
        ext = item["file"].rsplit(".", 1)[-1]
        mime = {"pdf": "application/pdf", "jpg": "image/jpeg"}[ext]
        by = item["by"]
        uploader = users[by.split(":")[1]] if by.startswith("doctor:") else users[item["patient"]]
        d = Document(patient_id=patients[item["patient"]].id, uploaded_by=uploader.id, doc_type=item["doc_type"], original_name=item["file"],
                     stored_path=save_document(folder, patients[item["patient"]].id, data, ext), mime_type=mime, size_bytes=len(data),
                     uploaded_at=ago(2))
        db.session.add(d)
        db.session.flush()
        docs[item["file"]] = d

    rx_rows = []
    for pat, doc, med, strength, dose, route, freq, dur, status, start_ago, length, logs in RX:
        start = date.today() - timedelta(days=start_ago)
        rx = Prescription(patient_id=patients[pat].id, doctor_id=doctor(doc).id, medicine=med, strength=strength, dose=dose, route=route,
                          frequency=freq, duration=dur, start_date=start, end_date=start + timedelta(days=length), status=status,
                          created_at=ago(start_ago))
        if status == "confirmed":
            rx.confirmed_by_doctor_id, rx.confirmed_at = rx.doctor_id, ago(start_ago)
        if status == "draft":  # as if read from the photographed prescription, waiting for a doctor to verify
            rx.source_document_id = docs.get("meena_prescription_photo.jpg").id if docs.get("meena_prescription_photo.jpg") else None
        db.session.add(rx)
        db.session.flush()
        rx_rows.append((rx, pat, logs, start_ago))

    log_count = 0
    for rx, pat, pattern, start_ago in rx_rows:
        if not pattern:
            continue
        per_day = 2 if "twice" in (rx.frequency or "") else 1
        for day in range(min(start_ago, 6), -1, -1):
            for slot in range(per_day):
                if day == 0 and slot == 1:
                    continue  # today's evening dose not yet due
                taken = random.random() < PATTERN[pattern]
                db.session.add(MedicationLog(prescription_id=rx.id, patient_id=rx.patient_id, status="taken" if taken else "skipped",
                                             logged_at=ago(day, 8 if slot == 0 else 20), note=None if taken else random.choice(["Forgot", "Felt nauseous", "Ran out of tablets"])))
                log_count += 1

    db.session.add(AuditLog(user_id=None, action="demo_seeded", detail=f"patients={len(patients)} documents={len(docs)}"))
    db.session.commit()
    return {"skipped": False, "doctors": len(DOCTORS), "patients": len(patients), "records": len(RECORDS) + 1,
            "prescriptions": len(RX), "medication_logs": log_count, "documents": len(docs)}
