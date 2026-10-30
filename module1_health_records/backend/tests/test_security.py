import io
import os

import pytest
from PIL import Image

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Document, User


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


def login(client, email, password, **extra):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password, **extra})


def admin_token(client):
    return login(client, "admin@test.com", "AdminPass1").get_json()["access_token"]


def register(client, email="pat@test.com", password="Patient123"):
    return client.post("/api/v1/auth/register", json={"name": "Pat Ient", "email": email, "password": password})


def new_doctor(client):
    client.post("/api/v1/admin/doctors", headers=auth(admin_token(client)), json={
        "name": "Dr Temp", "email": "temp@test.com", "password": "TempPass123"})
    return login(client, "temp@test.com", "TempPass123", portal="doctor")


# ---------- temporary password / sessions ----------

def test_new_doctor_must_change_temporary_password(client):
    r = new_doctor(client)
    assert r.status_code == 200 and r.get_json()["user"]["must_change_password"] is True
    token = r.get_json()["access_token"]

    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200
    blocked = client.get("/api/v1/patients", headers=auth(token))
    assert blocked.status_code == 403 and blocked.get_json()["code"] == "password_change_required"

    bad = client.post("/api/v1/auth/change-password", headers=auth(token),
                      json={"current_password": "wrong", "new_password": "BrandNew123"})
    assert bad.status_code == 400
    weak = client.post("/api/v1/auth/change-password", headers=auth(token),
                       json={"current_password": "TempPass123", "new_password": "short"})
    assert weak.status_code == 400
    same = client.post("/api/v1/auth/change-password", headers=auth(token),
                       json={"current_password": "TempPass123", "new_password": "TempPass123"})
    assert same.status_code == 400

    ok = client.post("/api/v1/auth/change-password", headers=auth(token),
                     json={"current_password": "TempPass123", "new_password": "BrandNew123"})
    assert ok.status_code == 200 and ok.get_json()["user"]["must_change_password"] is False
    fresh = ok.get_json()["access_token"]

    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401    # old token dead
    assert client.get("/api/v1/patients", headers=auth(fresh)).status_code == 200   # new one works
    assert login(client, "temp@test.com", "TempPass123").status_code == 401
    assert login(client, "temp@test.com", "BrandNew123").status_code == 200


def test_logout_ends_the_session(client):
    token = register(client).get_json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth(token)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401


def test_disabling_an_account_ends_its_sessions(client):
    reg = register(client).get_json()
    client.patch(f"/api/v1/admin/users/{reg['user']['id']}/active", headers=auth(admin_token(client)),
                 json={"is_active": False})
    client.patch(f"/api/v1/admin/users/{reg['user']['id']}/active", headers=auth(admin_token(client)),
                 json={"is_active": True})
    assert client.get("/api/v1/auth/me", headers=auth(reg["access_token"])).status_code == 401  # even after re-enable


# ---------- brute force / abuse limits ----------

def test_login_locks_after_repeated_failures(client):
    register(client)
    for _ in range(5):
        assert login(client, "pat@test.com", "wrong-password").status_code == 401
    assert login(client, "pat@test.com", "Patient123").status_code == 429      # locked even with the right password
    register(client, "other@test.com")
    assert login(client, "other@test.com", "Patient123").status_code == 200    # others unaffected


def test_registration_is_throttled_per_ip(client):
    client.app_ref.config["REGISTER_MAX_PER_IP_HOUR"] = 3
    codes = [register(client, f"u{i}@test.com").status_code for i in range(5)]
    assert codes == [201, 201, 201, 429, 429]


def test_password_longer_than_72_bytes_is_refused(client):
    assert register(client, password="Ab1" + "x" * 80).status_code == 400


# ---------- headers and errors ----------

def test_security_headers_and_no_caching(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers["Cache-Control"] == "no-store"


def test_errors_are_json_without_internals(client):
    assert client.get("/api/v1/does-not-exist").get_json() == {"error": "Not found."}
    app = create_app(TestConfig)
    app.testing = False
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.add_url_rule("/boom", "boom", lambda: 1 / 0)
    r = app.test_client().get("/boom")
    assert r.status_code == 500 and r.get_json() == {"error": "Something went wrong on the server."}
    assert b"Traceback" not in r.data and b"ZeroDivision" not in r.data


# ---------- files encrypted at rest ----------

def png():
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_uploaded_documents_are_encrypted_on_disk(client):
    token = register(client).get_json()["access_token"]
    pid = client.get("/api/v1/patients/me", headers=auth(token)).get_json()["patient"]["id"]
    data = png()
    r = client.post(f"/api/v1/patients/{pid}/documents", headers=auth(token),
                    data={"file": (io.BytesIO(data), "scan.png"), "doc_type": "other"},
                    content_type="multipart/form-data")
    doc = db.session.get(Document, r.get_json()["document"]["id"])
    on_disk = open(os.path.join(client.app_ref.config["UPLOAD_FOLDER"], doc.stored_path), "rb").read()
    assert on_disk != data and on_disk.startswith(b"gAAAA") and b"PNG" not in on_disk[:40]
    served = client.get(f"/api/v1/documents/{doc.id}/file", headers=auth(token))
    assert served.data == data


def test_profile_photos_are_encrypted_on_disk(client):
    token = register(client).get_json()["access_token"]
    pid = client.get("/api/v1/patients/me", headers=auth(token)).get_json()["patient"]["id"]
    client.post(f"/api/v1/patients/{pid}/photo", headers=auth(token),
                data={"photo": (io.BytesIO(png()), "me.png")}, content_type="multipart/form-data")
    folder = os.path.join(client.app_ref.config["UPLOAD_FOLDER"], "photos")
    raw = open(os.path.join(folder, os.listdir(folder)[0]), "rb").read()
    assert raw.startswith(b"gAAAA")
    img = client.get(f"/api/v1/patients/{pid}/photo", headers=auth(token))
    assert Image.open(io.BytesIO(img.data)).format == "JPEG"


def test_legacy_plaintext_files_still_open(client):
    token = register(client).get_json()["access_token"]
    pid = client.get("/api/v1/patients/me", headers=auth(token)).get_json()["patient"]["id"]
    folder = client.app_ref.config["UPLOAD_FOLDER"]
    os.makedirs(os.path.join(folder, "documents"), exist_ok=True)
    rel = os.path.join("documents", "old.png")
    open(os.path.join(folder, rel), "wb").write(png())
    uid = User.query.filter_by(email="pat@test.com").first().id
    doc = Document(patient_id=pid, uploaded_by=uid, doc_type="other", original_name="old.png",
                   stored_path=rel, mime_type="image/png", size_bytes=10)
    db.session.add(doc)
    db.session.commit()
    assert client.get(f"/api/v1/documents/{doc.id}/file", headers=auth(token)).data == png()


# ---------- production safety ----------

def test_production_refuses_weak_settings(client):
    class Weak(TestConfig):
        ENV_NAME = "production"
    with pytest.raises(RuntimeError) as exc:
        create_app(Weak)
    assert "SECRET_KEY" in str(exc.value) and "DOCUMENT_ENCRYPTION_KEY" in str(exc.value)

    class Strong(TestConfig):
        ENV_NAME = "production"
        SECRET_KEY = "s" * 40
        JWT_SECRET_KEY = "j" * 40
        DOCUMENT_ENCRYPTION_KEY = "k" * 44
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://u:p@localhost/db"
        CORS_ORIGINS = ["https://healthbridge.example"]
    create_app(Strong)
