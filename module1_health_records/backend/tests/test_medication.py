from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import AuditLog, MedicationLog, User


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


def make_doctor(client):
    admin = login(client, "admin@test.com", "AdminPass1")
    client.post("/api/v1/admin/doctors", headers=auth(admin), json={
        "name": "Dr Test", "email": "doc@test.com", "password": "Doctor1234"})
    User.query.filter_by(role="doctor").update({"must_change_password": False})
    db.session.commit()
    return login(client, "doc@test.com", "Doctor1234")


def admin_token(client):
    return login(client, "admin@test.com", "AdminPass1")


def add_rx(client, doc, pid, **extra):
    body = {"medicine": "Example Medicine A", "strength": "500 mg", "dose": "1 tablet", "frequency": "twice daily"}
    body.update(extra)
    return client.post(f"/api/v1/patients/{pid}/prescriptions", headers=auth(doc), json=body).get_json()["prescription"]["id"]


def log_dose(client, token, rx_id, **body):
    body.setdefault("status", "taken")
    return client.post(f"/api/v1/prescriptions/{rx_id}/log", headers=auth(token), json=body)


def test_last_taken_comes_from_the_log_not_the_prescription(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    rx = add_rx(client, doc, pid)

    med = client.get(f"/api/v1/patients/{pid}/medication", headers=auth(pt)).get_json()["medication"][0]
    assert med["last_taken_at"] is None and med["last_taken_display"] == "Not recorded"
    assert med["last_entry"] is None and med["active"] is True

    assert log_dose(client, pt, rx, status="taken").status_code == 201
    assert log_dose(client, pt, rx, status="skipped", note="Felt nauseous").status_code == 201
    med = client.get(f"/api/v1/patients/{pid}/medication", headers=auth(pt)).get_json()["medication"][0]
    assert med["last_taken_at"] is not None
    assert med["last_entry"]["status"] == "skipped"       # latest action
    assert (med["taken_count"], med["skipped_count"]) == (1, 1)


def test_skipped_only_does_not_count_as_taken(client):
    pt, pid = register(client)
    rx = add_rx(client, make_doctor(client), pid)
    log_dose(client, pt, rx, status="skipped")
    med = client.get(f"/api/v1/patients/{pid}/medication", headers=auth(pt)).get_json()["medication"][0]
    assert med["last_taken_at"] is None and med["last_taken_display"] == "Not recorded"


def test_log_validation(client):
    pt, pid = register(client)
    rx = add_rx(client, make_doctor(client), pid)
    assert log_dose(client, pt, rx, status="maybe").status_code == 400
    assert log_dose(client, pt, rx, note="x" * 256).status_code == 400
    future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    assert log_dose(client, pt, rx, logged_at=future).status_code == 400
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert log_dose(client, pt, rx, logged_at=old).status_code == 400
    assert log_dose(client, pt, rx, logged_at="yesterday-ish").status_code == 400
    ok = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    assert log_dose(client, pt, rx, logged_at=ok).status_code == 201


def test_only_the_owning_patient_can_log(client):
    t1, pid1 = register(client, "a@test.com")
    t2, _ = register(client, "b@test.com")
    doc = make_doctor(client)
    rx = add_rx(client, doc, pid1)
    assert log_dose(client, t2, rx).status_code == 403            # another patient
    assert log_dose(client, doc, rx).status_code == 403           # doctor
    assert log_dose(client, admin_token(client), rx).status_code == 403  # admin
    assert client.post("/api/v1/prescriptions/9999/log", headers=auth(t2), json={"status": "taken"}).status_code == 403
    assert client.post(f"/api/v1/prescriptions/{rx}/log", json={"status": "taken"}).status_code == 401
    assert MedicationLog.query.count() == 0


def test_cannot_log_draft_or_discontinued(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    draft = add_rx(client, doc, pid, status="draft")
    assert log_dose(client, pt, draft).status_code == 409
    done = add_rx(client, doc, pid)
    client.put(f"/api/v1/prescriptions/{done}", headers=auth(doc), json={"status": "discontinued"})
    assert log_dose(client, pt, done).status_code == 409
    # drafts and discontinued never appear in the schedule
    assert client.get(f"/api/v1/patients/{pid}/medication", headers=auth(pt)).get_json()["medication"] == []


def test_schedule_active_flag_follows_dates(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    add_rx(client, doc, pid, start_date="2020-01-01", end_date="2020-01-05")
    med = client.get(f"/api/v1/patients/{pid}/medication", headers=auth(pt)).get_json()["medication"][0]
    assert med["active"] is False


def test_visibility_rules_and_audit(client):
    t1, pid1 = register(client, "a@test.com")
    t2, pid2 = register(client, "b@test.com")
    doc = make_doctor(client)
    rx = add_rx(client, doc, pid1)
    log_dose(client, t1, rx)

    assert client.get(f"/api/v1/patients/{pid1}/medication", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/prescriptions/{rx}/logs", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/patients/{pid1}/medication", headers=auth(doc)).status_code == 200
    logs = client.get(f"/api/v1/prescriptions/{rx}/logs", headers=auth(doc)).get_json()["logs"]
    assert len(logs) == 1 and logs[0]["status"] == "taken"
    assert client.get(f"/api/v1/patients/{pid1}/medication", headers=auth(admin_token(client))).status_code == 200
    assert client.get("/api/v1/prescriptions/9999/logs", headers=auth(doc)).status_code == 404

    actions = {a.action for a in AuditLog.query.all()}
    assert {"medication_logged", "medication_viewed", "medication_logs_viewed"} <= actions


# ---------- admin audit viewer ----------

def test_audit_viewer_is_admin_only(client):
    pt, _ = register(client)
    doc = make_doctor(client)
    for token in (pt, doc):
        assert client.get("/api/v1/admin/audit-logs", headers=auth(token)).status_code == 403
        assert client.get("/api/v1/admin/audit-logs/actions", headers=auth(token)).status_code == 403
    assert client.get("/api/v1/admin/audit-logs").status_code == 401


def test_audit_viewer_filters_and_names(client):
    pt, pid = register(client)
    doc = make_doctor(client)
    rx = add_rx(client, doc, pid)
    log_dose(client, pt, rx)
    client.get(f"/api/v1/patients/{pid}", headers=auth(doc))
    adm = admin_token(client)

    everything = client.get("/api/v1/admin/audit-logs", headers=auth(adm)).get_json()
    assert everything["total"] >= 5
    ts = [e["created_at"] for e in everything["logs"]]
    assert ts == sorted(ts, reverse=True)

    only = client.get("/api/v1/admin/audit-logs?action=patient_viewed", headers=auth(adm)).get_json()
    assert only["total"] == 1
    entry = only["logs"][0]
    assert entry["user_name"] == "Dr Test" and entry["user_role"] == "doctor" and entry["target_id"] == pid

    by_target = client.get(f"/api/v1/admin/audit-logs?target_type=patient&target_id={pid}", headers=auth(adm)).get_json()
    assert by_target["total"] >= 1 and all(e["target_type"] == "patient" for e in by_target["logs"])

    today = datetime.now(timezone.utc).date().isoformat()
    assert client.get(f"/api/v1/admin/audit-logs?since={today}", headers=auth(adm)).get_json()["total"] >= 5
    assert client.get("/api/v1/admin/audit-logs?since=2999-01-01", headers=auth(adm)).get_json()["total"] == 0
    assert client.get(f"/api/v1/admin/audit-logs?until={today}", headers=auth(adm)).get_json()["total"] >= 5
    assert client.get("/api/v1/admin/audit-logs?since=notadate", headers=auth(adm)).status_code == 400

    page = client.get("/api/v1/admin/audit-logs?per_page=2&page=1", headers=auth(adm)).get_json()
    assert len(page["logs"]) == 2 and page["per_page"] == 2

    actions = client.get("/api/v1/admin/audit-logs/actions", headers=auth(adm)).get_json()["actions"]
    assert "medication_logged" in actions and "doctor_created" in actions
