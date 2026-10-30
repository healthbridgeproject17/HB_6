import io
import os

import pytest
from PIL import Image

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import AuditLog, Document, User


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


def png(size=(100, 80)):
    buf = io.BytesIO()
    Image.new("RGB", size, (240, 240, 240)).save(buf, format="PNG")
    return buf.getvalue()


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def upload(client, token, pid, data, filename="report.pdf", doc_type="lab_report"):
    return client.post(f"/api/v1/patients/{pid}/documents", headers=auth(token),
                       data={"file": (io.BytesIO(data), filename), "doc_type": doc_type},
                       content_type="multipart/form-data")


def test_patient_uploads_pdf_and_image_and_lists_them(client):
    t, pid = register(client)
    r1 = upload(client, t, pid, PDF, "cbc report.pdf", "lab_report")
    r2 = upload(client, t, pid, png(), "prescription.png", "prescription")
    assert r1.status_code == 201 and r2.status_code == 201
    d = r1.get_json()["document"]
    assert d["mime_type"] == "application/pdf" and d["doc_type"] == "lab_report" and d["can_delete"] is True
    docs = client.get(f"/api/v1/patients/{pid}/documents", headers=auth(t)).get_json()["documents"]
    assert len(docs) == 2
    only = client.get(f"/api/v1/patients/{pid}/documents?doc_type=prescription", headers=auth(t)).get_json()["documents"]
    assert len(only) == 1 and only[0]["original_name"] == "prescription.png"


def test_camera_photo_with_no_name_or_wrong_extension_is_stored_correctly(client):
    t, pid = register(client)
    # phones/browsers often send camera shots as "image.jpg" or "blob" holding PNG data
    r = upload(client, t, pid, png(), "image.jpg", "prescription")
    assert r.status_code == 201
    doc = r.get_json()["document"]
    assert doc["mime_type"] == "image/png" and doc["original_name"].endswith(".png")


def test_file_download_returns_exact_bytes_with_safe_headers(client):
    t, pid = register(client)
    data = png((50, 50))
    doc_id = upload(client, t, pid, data, "a.png", "other").get_json()["document"]["id"]
    r = client.get(f"/api/v1/documents/{doc_id}/file", headers=auth(t))
    assert r.status_code == 200 and r.data == data and r.mimetype == "image/png"
    assert r.headers["X-Content-Type-Options"] == "nosniff" and "no-store" in r.headers["Cache-Control"]
    assert client.get(f"/api/v1/documents/{doc_id}/file").status_code == 401


def test_upload_validation(client):
    t, pid = register(client)
    assert upload(client, t, pid, b"hello", "notes.txt").status_code == 400                # wrong type
    assert upload(client, t, pid, b"MZ\x90 fake exe", "virus.pdf").status_code == 400      # fake PDF
    assert upload(client, t, pid, b"not really an image", "x.png").status_code == 400      # fake image
    assert upload(client, t, pid, b"", "empty.pdf").status_code == 400
    assert upload(client, t, pid, PDF, "ok.pdf", doc_type="selfie").status_code == 400     # bad doc_type
    big = PDF + b"0" * (10 * 1024 * 1024)
    assert upload(client, t, pid, big, "big.pdf").status_code == 400                       # too large
    no_file = client.post(f"/api/v1/patients/{pid}/documents", headers=auth(t),
                          data={"doc_type": "other"}, content_type="multipart/form-data")
    assert no_file.status_code == 400
    assert Document.query.count() == 0


def test_visibility_rules(client):
    t1, pid1 = register(client, "a@test.com")
    t2, pid2 = register(client, "b@test.com")
    doc = make_doctor(client)
    doc_id = upload(client, t1, pid1, PDF).get_json()["document"]["id"]

    assert client.get(f"/api/v1/patients/{pid1}/documents", headers=auth(t2)).status_code == 403
    assert client.get(f"/api/v1/documents/{doc_id}/file", headers=auth(t2)).status_code == 403
    assert upload(client, t2, pid1, PDF).status_code == 403
    assert client.get("/api/v1/documents/9999/file", headers=auth(t2)).status_code == 403

    assert client.get(f"/api/v1/documents/{doc_id}/file", headers=auth(doc)).status_code == 200
    assert client.get("/api/v1/documents/9999/file", headers=auth(doc)).status_code == 404
    assert len(client.get(f"/api/v1/patients/{pid1}/documents", headers=auth(doc)).get_json()["documents"]) == 1
    assert upload(client, doc, pid1, PDF, "from_doctor.pdf", "prescription").status_code == 201
    actions = {a.action for a in AuditLog.query.all()}
    assert {"document_uploaded", "document_viewed", "documents_listed"} <= actions


def test_delete_rules_and_file_removed(client):
    t, pid = register(client)
    doc = make_doctor(client)
    admin = login(client, "admin@test.com", "AdminPass1")
    mine = upload(client, t, pid, PDF, "mine.pdf").get_json()["document"]["id"]
    theirs = upload(client, doc, pid, PDF, "doctor.pdf").get_json()["document"]["id"]

    folder = client.app_ref.config["UPLOAD_FOLDER"]
    stored = Document.query.get(mine).stored_path
    assert os.path.isfile(os.path.join(folder, stored))

    assert client.delete(f"/api/v1/documents/{mine}", headers=auth(doc)).status_code == 403   # doctor can't delete patient's
    assert client.delete(f"/api/v1/documents/{theirs}", headers=auth(t)).status_code == 403   # patient can't delete doctor's
    assert client.delete(f"/api/v1/documents/{mine}", headers=auth(t)).status_code == 200
    assert not os.path.isfile(os.path.join(folder, stored))
    assert client.get(f"/api/v1/documents/{mine}/file", headers=auth(t)).status_code == 403
    assert client.delete(f"/api/v1/documents/{theirs}", headers=auth(admin)).status_code == 200
    assert "document_deleted" in {a.action for a in AuditLog.query.all()}


def test_create_admin_command(client):
    runner = client.app_ref.test_cli_runner()
    ok = runner.invoke(args=["create-admin", "--name", "Second Admin", "--email", "Second@Test.com"],
                       input="SecondPass9\nSecondPass9\n")
    assert "Admin created: second@test.com" in ok.output
    assert login(client, "second@test.com", "SecondPass9")
    weak = runner.invoke(args=["create-admin", "--name", "X Admin", "--email", "x@test.com"], input="abc\nabc\n")
    assert weak.exit_code != 0
    dup = runner.invoke(args=["create-admin", "--name", "Dup Admin", "--email", "second@test.com"],
                        input="SecondPass9\nSecondPass9\n")
    assert dup.exit_code != 0
