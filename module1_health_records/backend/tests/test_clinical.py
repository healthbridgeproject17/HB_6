import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import AuditLog, MedicalRecord, Prescription, User


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        admin = User(name="Admin", email="admin@test.com", role="admin")
        admin.set_password("AdminPass1")
        db.session.add(admin)
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).get_json()["access_token"]


def register(client, email="pat@test.com"):
    r = client.post("/api/v1/auth/register", json={"name": "Pat Ient", "email": email, "password": "Patient123"})
    token = r.get_json()["access_token"]
    pid = client.get("/api/v1/patients/me", headers=auth(token)).get_json()["patient"]["id"]
    return token, pid


def make_doctor(client, email="doc@test.com", name="Dr Test"):
    admin = login(client, "admin@test.com", "AdminPass1")
    client.post("/api/v1/admin/doctors", headers=auth(admin), json={
        "name": name, "email": email, "password": "Doctor1234"})
    return login(client, email, "Doctor1234")


def admin_token(client):
    return login(client, "admin@test.com", "AdminPass1")


def add_record(client, doc, pid, **extra):
    body = {"record_type": "diagnosis", "title": "Seasonal allergy", "details": "Mild rhinitis"}
    body.update(extra)
    return client.post(f"/api/v1/patients/{pid}/records", headers=auth(doc), json=body)


# ---------- medical records ----------

def test_doctor_creates_record_patient_reads_it(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    r = add_record(client, doc, pid)
    assert r.status_code == 201 and r.get_json()["record"]["doctor"] == "Dr Test"
    rows = client.get(f"/api/v1/patients/{pid}/records", headers=auth(pt)).get_json()["records"]
    assert len(rows) == 1 and rows[0]["title"] == "Seasonal allergy"


def test_patient_and_admin_cannot_create_records(client):
    pt, pid = register(client)
    assert add_record(client, pt, pid).status_code == 403
    assert add_record(client, admin_token(client), pid).status_code == 403


def test_record_validation(client):
    _, pid = register(client)
    doc = make_doctor(client)
    assert add_record(client, doc, pid, title="x").status_code == 400
    assert add_record(client, doc, pid, record_type="surgery").status_code == 400
    assert add_record(client, doc, pid, details="x" * 5001).status_code == 400
    assert client.get("/api/v1/patients/9999/records", headers=auth(doc)).status_code == 404


def test_patient_cannot_read_other_patients_records(client):
    t1, pid1 = register(client, "a@test.com")
    t2, pid2 = register(client, "b@test.com")
    doc = make_doctor(client)
    add_record(client, doc, pid2)
    assert client.get(f"/api/v1/patients/{pid2}/records", headers=auth(t1)).status_code == 403
    assert client.post(f"/api/v1/patients/{pid2}/records", headers=auth(t1),
                       json={"title": "Hacked"}).status_code == 403


def test_doctor_amendment_keeps_history(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    rid = add_record(client, doc, pid).get_json()["record"]["id"]

    r = client.post(f"/api/v1/records/{rid}/amend", headers=auth(doc),
                    json={"details": "Moderate rhinitis", "reason": "Reassessed at follow-up"})
    assert r.status_code == 201
    new = r.get_json()["record"]
    assert new["amended_from_id"] == rid and new["title"] == "Seasonal allergy"
    assert new["amendment_reason"] == "Reassessed at follow-up"

    # original row is untouched in the database
    original = db.session.get(MedicalRecord, rid)
    assert original.details == "Mild rhinitis"

    current = client.get(f"/api/v1/patients/{pid}/records", headers=auth(pt)).get_json()["records"]
    assert [x["id"] for x in current] == [new["id"]]
    full = client.get(f"/api/v1/patients/{pid}/records?include_history=true", headers=auth(pt)).get_json()["records"]
    assert len(full) == 2

    hist = client.get(f"/api/v1/records/{rid}/history", headers=auth(pt)).get_json()["history"]
    assert [h["id"] for h in hist] == [rid, new["id"]]
    assert hist[0]["superseded"] is True and hist[1]["superseded"] is False


def test_cannot_amend_an_already_amended_record(client):
    _, pid = register(client)
    doc = make_doctor(client)
    rid = add_record(client, doc, pid).get_json()["record"]["id"]
    ok = client.post(f"/api/v1/records/{rid}/amend", headers=auth(doc), json={"title": "Updated title", "reason": "Correction"})
    assert ok.status_code == 201
    again = client.post(f"/api/v1/records/{rid}/amend", headers=auth(doc), json={"title": "Another", "reason": "Second try"})
    assert again.status_code == 409


def test_amendment_needs_reason_and_content(client):
    _, pid = register(client)
    doc = make_doctor(client)
    rid = add_record(client, doc, pid).get_json()["record"]["id"]
    assert client.post(f"/api/v1/records/{rid}/amend", headers=auth(doc), json={"title": "New title here"}).status_code == 400
    assert client.post(f"/api/v1/records/{rid}/amend", headers=auth(doc), json={"reason": "no content given"}).status_code == 400
    assert client.post("/api/v1/records/9999/amend", headers=auth(doc), json={"title": "x", "reason": "whatever"}).status_code == 404


def test_admin_amendment_is_traceable_and_patient_cannot_amend(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    rid = add_record(client, doc, pid).get_json()["record"]["id"]
    assert client.post(f"/api/v1/records/{rid}/amend", headers=auth(pt),
                       json={"title": "Edited by patient", "reason": "I disagree"}).status_code == 403

    r = client.post(f"/api/v1/records/{rid}/amend", headers=auth(admin_token(client)),
                    json={"title": "Seasonal allergy (typo fixed)", "reason": "Administrative typo correction"})
    assert r.status_code == 201
    assert db.session.get(MedicalRecord, rid).title == "Seasonal allergy"  # original untouched
    audit = AuditLog.query.filter_by(action="record_amended").first()
    assert "by=admin" in audit.detail and "typo" in audit.detail


def test_doctor_reads_are_audited(client):
    _, pid = register(client)
    doc = make_doctor(client)
    client.get(f"/api/v1/patients/{pid}/records", headers=auth(doc))
    assert "records_viewed" in {a.action for a in AuditLog.query.all()}


# ---------- prescriptions ----------

RX = {"medicine": "Example Medicine A", "strength": "500 mg", "dose": "1 tablet", "route": "oral",
      "frequency": "twice daily", "duration": "5 days", "start_date": "2026-10-28", "end_date": "2026-11-02"}


def add_rx(client, doc, pid, **extra):
    body = dict(RX)
    body.update(extra)
    return client.post(f"/api/v1/patients/{pid}/prescriptions", headers=auth(doc), json=body)


def test_doctor_creates_confirmed_prescription_with_separate_fields(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    r = add_rx(client, doc, pid)
    assert r.status_code == 201
    rx = r.get_json()["prescription"]
    assert rx["status"] == "confirmed" and rx["confirmed_at"]
    assert (rx["strength"], rx["dose"], rx["route"], rx["frequency"], rx["duration"]) == (
        "500 mg", "1 tablet", "oral", "twice daily", "5 days")
    listing = client.get(f"/api/v1/patients/{pid}/prescriptions", headers=auth(pt)).get_json()["prescriptions"]
    assert len(listing) == 1


def test_patient_and_admin_cannot_write_prescriptions(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    rid = add_rx(client, doc, pid).get_json()["prescription"]["id"]
    adm = admin_token(client)
    for token in (pt, adm):
        assert add_rx(client, token, pid).status_code == 403
        assert client.put(f"/api/v1/prescriptions/{rid}", headers=auth(token), json={"dose": "10 tablets"}).status_code == 403
        assert client.put(f"/api/v1/prescriptions/{rid}/confirm", headers=auth(token)).status_code == 403
    # admin can still read
    assert client.get(f"/api/v1/patients/{pid}/prescriptions", headers=auth(adm)).status_code == 200


def test_patient_cannot_read_other_patients_prescriptions(client):
    t1, _ = register(client, "a@test.com")
    _, pid2 = register(client, "b@test.com")
    doc = make_doctor(client)
    add_rx(client, doc, pid2)
    assert client.get(f"/api/v1/patients/{pid2}/prescriptions", headers=auth(t1)).status_code == 403


def test_prescription_validation(client):
    _, pid = register(client)
    doc = make_doctor(client)
    assert add_rx(client, doc, pid, medicine="").status_code == 400
    assert add_rx(client, doc, pid, start_date="28/10/2026").status_code == 400
    assert add_rx(client, doc, pid, start_date="2026-11-05", end_date="2026-11-01").status_code == 400
    assert add_rx(client, doc, pid, status="discontinued").status_code == 400
    assert add_rx(client, doc, pid, dose="x" * 61).status_code == 400


def test_draft_must_be_confirmed_by_a_doctor(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    rx = add_rx(client, doc, pid, status="draft").get_json()["prescription"]
    assert rx["status"] == "draft" and rx["confirmed_at"] is None
    assert client.put(f"/api/v1/prescriptions/{rx['id']}", headers=auth(doc), json={"status": "confirmed"}).status_code == 400
    assert client.put(f"/api/v1/prescriptions/{rx['id']}/confirm", headers=auth(pt)).status_code == 403

    ok = client.put(f"/api/v1/prescriptions/{rx['id']}/confirm", headers=auth(doc))
    assert ok.status_code == 200 and ok.get_json()["prescription"]["status"] == "confirmed"
    assert client.put(f"/api/v1/prescriptions/{rx['id']}/confirm", headers=auth(doc)).status_code == 409
    assert "prescription_confirmed" in {a.action for a in AuditLog.query.all()}


def test_update_and_discontinue_are_audited_with_old_and_new(client):
    _, pid = register(client)
    doc = make_doctor(client)
    rid = add_rx(client, doc, pid).get_json()["prescription"]["id"]
    r = client.put(f"/api/v1/prescriptions/{rid}", headers=auth(doc), json={"frequency": "once daily"})
    assert r.status_code == 200 and r.get_json()["prescription"]["frequency"] == "once daily"
    audit = AuditLog.query.filter_by(action="prescription_updated").first()
    assert "frequency: twice daily -> once daily" in audit.detail

    r = client.put(f"/api/v1/prescriptions/{rid}", headers=auth(doc), json={"status": "discontinued"})
    assert r.get_json()["prescription"]["status"] == "discontinued"
    assert client.put(f"/api/v1/prescriptions/{rid}", headers=auth(doc), json={"status": "banana"}).status_code == 400
    assert client.put("/api/v1/prescriptions/9999", headers=auth(doc), json={"dose": "1"}).status_code == 404
    only = client.get(f"/api/v1/patients/{pid}/prescriptions?status=confirmed", headers=auth(doc)).get_json()
    assert only["prescriptions"] == []


def test_update_cannot_break_date_order(client):
    _, pid = register(client)
    doc = make_doctor(client)
    rid = add_rx(client, doc, pid).get_json()["prescription"]["id"]
    r = client.put(f"/api/v1/prescriptions/{rid}", headers=auth(doc), json={"end_date": "2026-01-01"})
    assert r.status_code == 400


def test_unauthenticated_requests_blocked(client):
    for method, url in (("get", "/api/v1/patients/1/records"), ("post", "/api/v1/records/1/amend"),
                        ("get", "/api/v1/patients/1/prescriptions"), ("put", "/api/v1/prescriptions/1")):
        assert getattr(client, method)(url).status_code == 401
