import io
import os

import pytest
from PIL import Image

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import AuditLog, User


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


def register(client, email, name="Pat Ient"):
    r = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "Patient123"})
    body = r.get_json()
    return body["access_token"], body["user"]["id"]


def patient_id(client, token):
    return client.get("/api/v1/patients/me", headers=auth(token)).get_json()["patient"]["id"]


def login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).get_json()["access_token"]


def make_doctor(client):
    t = login(client, "admin@test.com", "AdminPass1")
    client.post("/api/v1/admin/doctors", headers=auth(t), json={
        "name": "Dr Test", "email": "doc@test.com", "password": "Doctor1234"})
    return login(client, "doc@test.com", "Doctor1234")


def png_bytes(size=(64, 64), color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def upload(client, token, pid, data, filename="me.png"):
    return client.post(f"/api/v1/patients/{pid}/photo", headers=auth(token),
                       data={"photo": (io.BytesIO(data), filename)}, content_type="multipart/form-data")


def test_patient_sees_and_edits_own_profile(client):
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    r = client.put(f"/api/v1/patients/{pid}", headers=auth(t), json={
        "phone": "+91 98765 43210", "sex": "female", "dob": "2001-02-03",
        "allergies": "Dust", "emergency_contact": "Parent 99999 88888"})
    assert r.status_code == 200
    p = r.get_json()["patient"]
    assert p["phone"] == "+91 98765 43210" and p["dob"] == "2001-02-03"
    assert client.get(f"/api/v1/patients/{pid}", headers=auth(t)).status_code == 200


def test_profile_validation(client):
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    for bad in ({"phone": "abc"}, {"dob": "2999-01-01"}, {"sex": "x"}, {"name": "A"}):
        assert client.put(f"/api/v1/patients/{pid}", headers=auth(t), json=bad).status_code == 400


def test_patient_cannot_see_or_edit_another_patient(client):
    t1, _ = register(client, "a@test.com")
    t2, _ = register(client, "b@test.com")
    pid2 = patient_id(client, t2)
    assert client.get(f"/api/v1/patients/{pid2}", headers=auth(t1)).status_code == 403
    assert client.put(f"/api/v1/patients/{pid2}", headers=auth(t1), json={"phone": "1234567"}).status_code == 403
    assert client.get(f"/api/v1/patients/{pid2}/photo", headers=auth(t1)).status_code == 403
    assert client.get("/api/v1/patients/999", headers=auth(t1)).status_code == 403


def test_patient_cannot_list_patients(client):
    t, _ = register(client, "a@test.com")
    assert client.get("/api/v1/patients", headers=auth(t)).status_code == 403


def test_doctor_can_search_and_view_but_not_edit(client):
    t, _ = register(client, "a@test.com", name="Ravi Kumar")
    register(client, "b@test.com", name="Meena S")
    pid = patient_id(client, t)
    d = make_doctor(client)

    listing = client.get("/api/v1/patients", headers=auth(d)).get_json()
    assert listing["total"] == 2
    found = client.get("/api/v1/patients?q=ravi", headers=auth(d)).get_json()
    assert found["total"] == 1 and found["patients"][0]["name"] == "Ravi Kumar"
    hid = found["patients"][0]["health_id"]
    assert client.get(f"/api/v1/patients?q={hid}", headers=auth(d)).get_json()["total"] == 1

    assert client.get(f"/api/v1/patients/{pid}", headers=auth(d)).status_code == 200
    assert client.put(f"/api/v1/patients/{pid}", headers=auth(d), json={"phone": "1234567"}).status_code == 403
    assert client.get("/api/v1/patients/999", headers=auth(d)).status_code == 404

    actions = [a.action for a in AuditLog.query.all()]
    assert "patient_viewed" in actions and "patient_search" in actions


def test_admin_can_edit_any_patient(client):
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    admin = login(client, "admin@test.com", "AdminPass1")
    r = client.put(f"/api/v1/patients/{pid}", headers=auth(admin), json={"phone": "9876543210"})
    assert r.status_code == 200


def test_photo_upload_view_replace_delete(client):
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    assert client.get(f"/api/v1/patients/{pid}/photo", headers=auth(t)).status_code == 404  # fallback avatar

    r = upload(client, t, pid, png_bytes((800, 600)))
    assert r.status_code == 201 and r.get_json()["patient"]["has_photo"] is True
    img = client.get(f"/api/v1/patients/{pid}/photo", headers=auth(t))
    assert img.status_code == 200 and img.mimetype == "image/jpeg"
    assert max(Image.open(io.BytesIO(img.data)).size) <= 512

    folder = client.app_ref.config["UPLOAD_FOLDER"]
    first = set(os.listdir(os.path.join(folder, "photos")))
    assert len(first) == 1
    assert upload(client, t, pid, png_bytes(color=(0, 0, 200))).status_code == 201
    second = set(os.listdir(os.path.join(folder, "photos")))
    assert len(second) == 1 and second != first  # old file was removed

    assert client.delete(f"/api/v1/patients/{pid}/photo", headers=auth(t)).status_code == 200
    assert os.listdir(os.path.join(folder, "photos")) == []
    assert client.get(f"/api/v1/patients/{pid}/photo", headers=auth(t)).status_code == 404


def test_photo_validation(client):
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    assert upload(client, t, pid, b"not an image at all", "evil.png").status_code == 400  # fake image
    assert upload(client, t, pid, png_bytes(), "photo.exe").status_code == 400            # bad extension
    assert upload(client, t, pid, b"", "empty.png").status_code == 400
    big = Image.frombytes("RGB", (1200, 1200), os.urandom(1200 * 1200 * 3))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    assert len(buf.getvalue()) > 2 * 1024 * 1024
    assert upload(client, t, pid, buf.getvalue()).status_code == 400                      # too big
    r = client.post(f"/api/v1/patients/{pid}/photo", headers=auth(t), data={}, content_type="multipart/form-data")
    assert r.status_code == 400                                                           # no file


def test_doctor_and_other_patient_cannot_upload_photo(client):
    t1, _ = register(client, "a@test.com")
    t2, _ = register(client, "b@test.com")
    pid1 = patient_id(client, t1)
    d = make_doctor(client)
    assert upload(client, d, pid1, png_bytes()).status_code == 403
    assert upload(client, t2, pid1, png_bytes()).status_code == 403


def test_doctor_can_view_patient_photo(client):
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    upload(client, t, pid, png_bytes())
    d = make_doctor(client)
    assert client.get(f"/api/v1/patients/{pid}/photo", headers=auth(d)).status_code == 200


def test_reset_admin_password_command(client, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "NewAdminPass9")
    runner = client.app_ref.test_cli_runner()
    result = runner.invoke(args=["reset-admin-password"])
    assert "Admin password updated" in result.output
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "NewAdminPass9"})
    assert r.status_code == 200


def test_replace_photo_survives_locked_old_file(client, monkeypatch):
    """On Windows a file can be briefly locked; replacing the photo must still work."""
    t, _ = register(client, "a@test.com")
    pid = patient_id(client, t)
    assert upload(client, t, pid, png_bytes()).status_code == 201

    def locked(_path):
        raise PermissionError("file is in use")

    monkeypatch.setattr(os, "remove", locked)
    assert upload(client, t, pid, png_bytes(color=(0, 0, 200))).status_code == 201
    assert client.get(f"/api/v1/patients/{pid}/photo", headers=auth(t)).status_code == 200
