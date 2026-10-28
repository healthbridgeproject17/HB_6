import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, AuditLog


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


def register(client, email="pat@test.com", **extra):
    payload = {"name": "Pat Ient", "email": email, "password": "Patient123"}
    payload.update(extra)
    return client.post("/api/v1/auth/register", json=payload)


def login(client, email, password, **extra):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password, **extra})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def admin_token(client):
    return login(client, "admin@test.com", "AdminPass1").get_json()["access_token"]


def test_register_creates_patient_with_health_id(client):
    r = register(client, dob="1999-05-20", sex="female")
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["role"] == "patient"
    assert body["user"]["health_id"].startswith("HB-") and len(body["user"]["health_id"]) == 14
    assert "access_token" in body


def test_register_ignores_role_in_body(client):
    r = register(client, role="admin")
    assert r.get_json()["user"]["role"] == "patient"


def test_register_validation(client):
    assert register(client, email="not-an-email").status_code == 400
    assert register(client, password="short").status_code == 400
    assert register(client, password="allletters").status_code == 400
    assert register(client, dob="2999-01-01").status_code == 400
    assert register(client, sex="robot").status_code == 400


def test_duplicate_email_rejected(client):
    assert register(client).status_code == 201
    assert register(client, email="PAT@test.com").status_code == 409


def test_login_success_and_failure(client):
    register(client)
    assert login(client, "pat@test.com", "Patient123").status_code == 200
    assert login(client, "pat@test.com", "wrong").status_code == 401
    assert login(client, "nobody@test.com", "Patient123").status_code == 401


def test_portal_mismatch_is_refused(client):
    register(client)
    assert login(client, "pat@test.com", "Patient123", portal="patient").status_code == 200
    assert login(client, "pat@test.com", "Patient123", portal="doctor").status_code == 401
    assert login(client, "pat@test.com", "Patient123", portal="admin").status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    token = register(client).get_json()["access_token"]
    r = client.get("/api/v1/auth/me", headers=auth(token))
    assert r.status_code == 200 and r.get_json()["user"]["email"] == "pat@test.com"


def test_patient_cannot_use_admin_routes(client):
    token = register(client).get_json()["access_token"]
    assert client.get("/api/v1/admin/users", headers=auth(token)).status_code == 403
    r = client.post("/api/v1/admin/doctors", headers=auth(token), json={
        "name": "Dr X", "email": "x@test.com", "password": "Doctor1234"})
    assert r.status_code == 403


def test_admin_routes_need_login(client):
    assert client.get("/api/v1/admin/users").status_code == 401


def test_admin_creates_doctor_who_can_log_in_but_not_create_doctors(client):
    t = admin_token(client)
    r = client.post("/api/v1/admin/doctors", headers=auth(t), json={
        "name": "Dr Who", "email": "doc@test.com", "password": "Doctor1234",
        "specialty": "Cardiology"})
    assert r.status_code == 201
    dl = login(client, "doc@test.com", "Doctor1234", portal="doctor")
    assert dl.status_code == 200 and dl.get_json()["user"]["role"] == "doctor"
    dt = dl.get_json()["access_token"]
    again = client.post("/api/v1/admin/doctors", headers=auth(dt), json={
        "name": "Dr Two", "email": "d2@test.com", "password": "Doctor1234"})
    assert again.status_code == 403


def test_disabled_user_token_stops_working(client):
    reg = register(client).get_json()
    token, uid = reg["access_token"], reg["user"]["id"]
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200
    r = client.patch(f"/api/v1/admin/users/{uid}/active", headers=auth(admin_token(client)),
                     json={"is_active": False})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401
    assert login(client, "pat@test.com", "Patient123").status_code == 403


def test_admin_cannot_disable_self(client):
    t = admin_token(client)
    admin_id = client.get("/api/v1/auth/me", headers=auth(t)).get_json()["user"]["id"]
    r = client.patch(f"/api/v1/admin/users/{admin_id}/active", headers=auth(t),
                     json={"is_active": False})
    assert r.status_code == 400


def test_important_actions_are_audited(client):
    register(client)
    login(client, "pat@test.com", "wrong")
    admin_token(client)
    actions = {a.action for a in AuditLog.query.all()}
    assert {"register", "login_failed", "login"} <= actions
