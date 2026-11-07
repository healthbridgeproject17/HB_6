import io
import os
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("cv2")
pytest.importorskip("pymupdf")
pytest.importorskip("rapidocr_onnxruntime")

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import AnalysisJob, AuditLog, Document, LabResult, MedicationLog, Patient, Prescription, User  # noqa: E402

DEMO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "demo_documents"))


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        admin = User(name="Admin", email="admin@test.com", role="admin")
        admin.set_password("AdminPass1")
        db.session.add(admin)
        db.session.commit()
        c = app.test_client()
        c.app_ref = app
        yield c
        db.session.remove()
        db.drop_all()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).get_json()["access_token"]


def patient(client, name="Meena Rajan", email="meena@test.com", sex="female"):
    r = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "Patient123", "sex": sex, "dob": "1951-05-30"})
    token = r.get_json()["access_token"]
    pid = client.get("/api/v1/patients/me", headers=auth(token)).get_json()["patient"]["id"]
    return token, pid


def doctor(client):
    client.post("/api/v1/admin/doctors", headers=auth(login(client, "admin@test.com", "AdminPass1")),
                json={"name": "Dr Test", "email": "doc@test.com", "password": "Doctor1234"})
    User.query.filter_by(role="doctor").update({"must_change_password": False})
    db.session.commit()
    return login(client, "doc@test.com", "Doctor1234")


def upload(client, token, pid, name, doc_type="lab_report"):
    data = open(os.path.join(DEMO, name), "rb").read()
    r = client.post(f"/api/v1/patients/{pid}/documents", headers=auth(token), data={"file": (io.BytesIO(data), name), "doc_type": doc_type},
                    content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["document"]["id"]


def analyze(client, token, doc_id):
    return client.post(f"/api/v1/documents/{doc_id}/analyze", headers=auth(token))


def detail(client, token, job_id):
    return client.get(f"/api/v1/analysis/{job_id}", headers=auth(token)).get_json()["analysis_job"]


def review(client, token, job_id, edits=None, confirm=False, **extra):
    return client.put(f"/api/v1/analysis/{job_id}/review", headers=auth(token), json={"edits": edits or {}, "confirm": confirm, **extra})


def index_of(job, key):
    return str(next(i for i, r in enumerate(job["analysis"]["lab_results"]) if r["test_key"] == key))


# ---------------------------------------------------------------- running an analysis
def test_patient_analyses_their_own_report_and_sees_the_patient_view(client):
    t, pid = patient(client)
    r = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf"))
    assert r.status_code == 201 and r.get_json()["job"]["status"] == "done" and r.get_json()["job"]["level"] == "urgent"
    job = detail(client, t, r.get_json()["job"]["id"])
    a = job["analysis"]
    assert a["document_type"] == "lab_report" and len(a["lab_results"]) == 6 and a["triage"]["level"] == "urgent"
    assert "patient" in a["report"] and "clinician" not in a["report"]
    assert "extraction" not in a and a["pages"][0]["page"] == 1 and job["review_status"] == "pending"
    assert a["identity"]["status"] == "match" and job["versions"]["rules"]
    img = client.get(f"/api/v1/analysis/{job['id']}/pages/1/image", headers=auth(t))
    assert img.status_code == 200 and img.mimetype == "image/jpeg" and img.data[:2] == b"\xff\xd8"
    assert client.get(f"/api/v1/analysis/{job['id']}/pages/9/image", headers=auth(t)).status_code == 404


def test_page_pictures_are_encrypted_on_disk(client):
    t, pid = patient(client)
    jid = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf")).get_json()["job"]["id"]
    path = os.path.join(client.app_ref.config["UPLOAD_FOLDER"], "analysis", f"job_{jid}", "page_1.jpg")
    assert open(path, "rb").read(5) == b"gAAAA"


def test_doctor_gets_the_clinician_view_and_views_are_audited(client):
    t, pid = patient(client)
    jid = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf")).get_json()["job"]["id"]
    d = doctor(client)
    job = detail(client, d, jid)
    assert job["analysis"]["report"]["clinician"]["triage"]["level"] == "urgent"
    assert "analysis_viewed" in {a.action for a in AuditLog.query.all()}
    adm = login(client, "admin@test.com", "AdminPass1")
    assert client.get(f"/api/v1/analysis/{jid}", headers=auth(adm)).status_code == 200


def test_permissions(client):
    t1, p1 = patient(client)
    t2, _ = patient(client, "Other Person", "other@test.com")
    doc_id = upload(client, t1, p1, "meena_kidney_panel_critical.pdf")
    assert analyze(client, t2, doc_id).status_code == 403
    jid = analyze(client, t1, doc_id).get_json()["job"]["id"]
    assert client.get(f"/api/v1/analysis/{jid}", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/analysis/{jid}/pages/1/image", headers=auth(t2)).status_code == 403
    assert client.get("/api/v1/analysis/999", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/documents/{doc_id}/analyses", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/analysis/{jid}").status_code == 401
    assert analyze(client, t1, 99999).status_code == 403
    assert review(client, t2, jid).status_code == 403


def test_a_second_run_while_one_is_active_is_refused_and_stale_jobs_expire(client):
    t, pid = patient(client)
    doc_id = upload(client, t, pid, "meena_kidney_panel_critical.pdf")
    uid = User.query.filter_by(email="meena@test.com").first().id
    db.session.add(AnalysisJob(document_id=doc_id, patient_id=pid, requested_by=uid, status="running", created_at=datetime.now(timezone.utc)))
    db.session.commit()
    assert analyze(client, t, doc_id).status_code == 409
    AnalysisJob.query.update({"created_at": datetime.now(timezone.utc) - timedelta(minutes=40)})
    db.session.commit()
    listing = client.get(f"/api/v1/documents/{doc_id}/analyses", headers=auth(t)).get_json()["analyses"]
    assert listing[0]["status"] == "failed" and "interrupted" in listing[0]["error"]
    assert analyze(client, t, doc_id).status_code == 201


def test_rate_limit(client):
    t, pid = patient(client)
    client.app_ref.config["ANALYSIS_MAX_PER_HOUR"] = 1
    doc_id = upload(client, t, pid, "meena_kidney_panel_critical.pdf")
    assert analyze(client, t, doc_id).status_code == 201
    assert analyze(client, t, doc_id).status_code == 429


def test_engine_errors_become_safe_messages(client, monkeypatch):
    import medai
    t, pid = patient(client)
    doc_id = upload(client, t, pid, "meena_kidney_panel_critical.pdf")
    monkeypatch.setattr(medai, "analyze_document", lambda *a, **k: (_ for _ in ()).throw(medai.ExtractionError("The PDF is damaged or cannot be opened.")))
    job = analyze(client, t, doc_id).get_json()["job"]
    assert job["status"] == "failed" and "damaged" in job["error"]
    monkeypatch.setattr(medai, "analyze_document", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internal path /srv/x")))
    job = analyze(client, t, doc_id).get_json()["job"]
    assert job["status"] == "failed" and "secret" not in job["error"] and "failed" in job["error"]


def test_engine_missing_gives_a_clear_503(client, monkeypatch):
    from app import analysis_bridge
    t, pid = patient(client)
    doc_id = upload(client, t, pid, "meena_kidney_panel_critical.pdf")
    monkeypatch.setattr(analysis_bridge, "available", lambda: False)
    r = analyze(client, t, doc_id)
    assert r.status_code == 503 and "not installed" in r.get_json()["error"]


# ---------------------------------------------------------------- review and confirm
def test_correcting_a_value_updates_urgency_and_confirming_saves_lab_results(client):
    t, pid = patient(client)
    jid = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf")).get_json()["job"]["id"]
    job = detail(client, t, jid)
    k = index_of(job, "potassium")
    r = review(client, t, jid, {"lab_results": {k: {"value": 4.1, "flag": ""}}})
    assert r.status_code == 200
    a = r.get_json()["analysis_job"]["analysis"]
    assert a["triage"]["level"] == "consult_promptly" and a["review_log"][0]["field"] == "value"
    assert r.get_json()["analysis_job"]["original_level"] == "urgent"            # the audit trail keeps what the machine first said

    done = review(client, t, jid, confirm=True)
    assert done.status_code == 200 and done.get_json()["analysis_job"]["review_status"] == "confirmed"
    rows = LabResult.query.filter_by(patient_id=pid).all()
    assert len(rows) == 6 and {x.confirmed_by_role for x in rows} == {"patient"}
    potassium = next(x for x in rows if x.test_key == "potassium")
    assert potassium.value == 4.1 and potassium.status == "normal" and str(potassium.collected_on) == "2026-10-24"
    listed = client.get(f"/api/v1/patients/{pid}/lab-results?test_key=potassium", headers=auth(t)).get_json()["lab_results"]
    assert len(listed) == 1 and listed[0]["confirmed_by_role"] == "patient"
    again = review(client, t, jid, {"lab_results": {k: {"value": 6.0}}})
    assert again.status_code == 409
    assert {"analysis_reviewed", "analysis_confirmed"} <= {a.action for a in AuditLog.query.all()}


def test_confirm_is_blocked_while_values_are_flagged(client):
    t, pid = patient(client)
    jid = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical_scan.jpg")).get_json()["job"]["id"]
    job = detail(client, t, jid)
    assert job["analysis"]["triage"]["provisional"] and job["analysis"]["summary"]["needs_review"] == 1
    blocked = review(client, t, jid, confirm=True)
    assert blocked.status_code == 400 and "still need checking" in blocked.get_json()["error"]
    assert LabResult.query.count() == 0
    h = index_of(job, "hemoglobin")
    ok = review(client, t, jid, {"lab_results": {h: {"unit": "g/dL", "accepted": True}}}, confirm=True)
    assert ok.status_code == 200 and LabResult.query.count() == 6


def test_wrong_patient_needs_an_explicit_acknowledgement(client):
    t, pid = patient(client, "Ananya Krishnan", "ananya@test.com")
    jid = analyze(client, t, upload(client, t, pid, "rahul_diabetes_panel.pdf")).get_json()["job"]["id"]
    assert detail(client, t, jid)["analysis"]["identity"]["status"] == "mismatch"
    blocked = review(client, t, jid, confirm=True)
    assert blocked.status_code == 400 and "does NOT match" in blocked.get_json()["error"]
    assert review(client, t, jid, confirm=True, acknowledge_identity=True).status_code == 200


def test_invalid_corrections_are_rejected_without_changing_anything(client):
    t, pid = patient(client)
    jid = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf")).get_json()["job"]["id"]
    before = detail(client, t, jid)["analysis"]["triage"]["level"]
    for edits in ({"lab_results": {"0": {"value": "abc"}}}, {"lab_results": {"77": {"value": 1}}}, {"lab_results": "nonsense"}, {"add_lab_results": [{"test": "Zorblax", "value": 1}]}):
        assert review(client, t, jid, edits).status_code == 400
    assert detail(client, t, jid)["analysis"]["triage"]["level"] == before and not detail(client, t, jid)["analysis"].get("review_log")


def test_admin_can_read_but_never_review_or_confirm(client):
    t, pid = patient(client)
    jid = analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf")).get_json()["job"]["id"]
    adm = login(client, "admin@test.com", "AdminPass1")
    assert review(client, adm, jid, confirm=True).status_code == 403


def test_patient_confirmed_prescriptions_are_drafts_and_never_enter_the_tracker(client):
    t, pid = patient(client, "Rahul Menon", "rahul@test.com", "male")
    jid = analyze(client, t, upload(client, t, pid, "rahul_prescription.pdf", "prescription")).get_json()["job"]["id"]
    assert review(client, t, jid, confirm=True).status_code == 200
    rows = Prescription.query.filter_by(patient_id=pid).all()
    assert len(rows) == 3 and {r.status for r in rows} == {"draft"} and all(r.doctor_id is None and r.confirmed_at is None for r in rows)
    assert all(r.source_document_id for r in rows)
    metformin = next(r for r in rows if r.medicine == "Metformin")
    assert (metformin.strength, metformin.dose, metformin.route, metformin.frequency, metformin.duration) == ("500 mg", "1 tablet", "oral", "Twice daily after food", "30 days")
    med = client.get(f"/api/v1/patients/{pid}/medication", headers=auth(t)).get_json()["medication"]
    assert med == []                                                              # drafts are not trackable


def test_doctor_confirmed_prescriptions_become_real_and_a_doctor_can_confirm_the_patients_drafts(client):
    t, pid = patient(client, "Rahul Menon", "rahul@test.com", "male")
    d = doctor(client)
    jid = analyze(client, d, upload(client, d, pid, "rahul_prescription.pdf", "prescription")).get_json()["job"]["id"]
    assert review(client, d, jid, confirm=True).status_code == 200
    rows = Prescription.query.filter_by(patient_id=pid).all()
    assert {r.status for r in rows} == {"confirmed"} and all(r.doctor_id and r.confirmed_by_doctor_id and r.confirmed_at for r in rows)
    med = client.get(f"/api/v1/patients/{pid}/medication", headers=auth(t)).get_json()["medication"]
    assert len(med) == 3 and all(m["last_taken_at"] is None for m in med)

    # a patient-confirmed draft can still be confirmed through the existing doctor route
    t2, pid2 = patient(client, "Rahul Menon", "rahul2@test.com", "male")
    j2 = analyze(client, t2, upload(client, t2, pid2, "rahul_prescription.pdf", "prescription")).get_json()["job"]["id"]
    review(client, t2, j2, confirm=True)
    draft = Prescription.query.filter_by(patient_id=pid2).first()
    assert client.put(f"/api/v1/prescriptions/{draft.id}/confirm", headers=auth(d)).status_code == 200


def test_prescription_corrections_flow_through_to_the_saved_prescription(client):
    t, pid = patient(client, "Rahul Menon", "rahul@test.com", "male")
    jid = analyze(client, t, upload(client, t, pid, "rahul_prescription.pdf", "prescription")).get_json()["job"]["id"]
    review(client, t, jid, {"prescription_items": {"0": {"strength": "850 mg"}, "2": {"remove": True}}}, confirm=True)
    rows = {r.medicine: r for r in Prescription.query.filter_by(patient_id=pid).all()}
    assert set(rows) == {"Metformin", "Amlodipine"} and rows["Metformin"].strength == "850 mg"


def test_unreadable_document_cannot_be_confirmed(client):
    t, pid = patient(client)
    jid = analyze(client, t, _blank_upload(client, t, pid)).get_json()["job"]["id"]
    job = detail(client, t, jid)
    assert job["analysis"]["document_type"] == "unknown"
    assert "nothing to confirm" in review(client, t, jid, confirm=True).get_json()["error"].lower()


def _blank_upload(client, t, pid):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (900, 1200), (250, 250, 250)).save(buf, "PNG")
    r = client.post(f"/api/v1/patients/{pid}/documents", headers=auth(t), data={"file": (io.BytesIO(buf.getvalue()), "blank.png"), "doc_type": "other"},
                    content_type="multipart/form-data")
    return r.get_json()["document"]["id"]


# ---------------------------------------------------------------- housekeeping
def test_documents_with_confirmed_results_cannot_be_deleted_but_unconfirmed_analyses_are_cleaned_up(client):
    t, pid = patient(client)
    d1 = upload(client, t, pid, "meena_kidney_panel_critical.pdf")
    j1 = analyze(client, t, d1).get_json()["job"]["id"]
    folder = os.path.join(client.app_ref.config["UPLOAD_FOLDER"], "analysis", f"job_{j1}")
    assert os.path.isdir(folder)
    assert client.delete(f"/api/v1/documents/{d1}", headers=auth(t)).status_code == 200      # not confirmed yet: removed with its analysis
    assert not os.path.isdir(folder) and AnalysisJob.query.count() == 0

    d2 = upload(client, t, pid, "meena_kidney_panel_critical.pdf")
    j2 = analyze(client, t, d2).get_json()["job"]["id"]
    review(client, t, j2, confirm=True)
    blocked = client.delete(f"/api/v1/documents/{d2}", headers=auth(t))
    assert blocked.status_code == 409 and "cannot be deleted" in blocked.get_json()["error"]
    assert db.session.get(Document, d2) is not None


def test_lists_and_visibility_of_patient_analyses(client):
    t, pid = patient(client)
    t2, _ = patient(client, "Other", "o@test.com")
    analyze(client, t, upload(client, t, pid, "meena_kidney_panel_critical.pdf"))
    listing = client.get(f"/api/v1/patients/{pid}/analyses", headers=auth(t)).get_json()["analyses"]
    assert len(listing) == 1 and listing[0]["document_name"] == "meena_kidney_panel_critical.pdf" and listing[0]["level"] == "urgent"
    assert client.get(f"/api/v1/patients/{pid}/analyses", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/patients/{pid}/lab-results", headers=auth(t2)).status_code == 403


def test_saved_prescriptions_use_tidy_text(client):
    from app.routes.analysis import rx_text
    item = {"strength": {"status": "ok", "value": {"text": "500 mg"}, "printed": "500mg"}, "dose": {"status": "ok", "value": {"text": "1 tablet"}, "printed": "1tablet"},
            "route": {"status": "ok", "value": {"text": "oral"}, "printed": "Oral"}, "duration": {"status": "ok", "value": {"text": "14 days"}, "printed": "14days"},
            "frequency": {"status": "ok", "value": {}, "printed": "once daily.morning"}}
    assert [rx_text(item, f) for f in ("strength", "dose", "route", "duration", "frequency")] == ["500 mg", "1 tablet", "oral", "14 days", "Once daily, morning"]
    assert rx_text({"frequency": {"status": "missing"}}, "frequency") is None
