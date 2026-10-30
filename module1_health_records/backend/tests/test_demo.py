import os

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Document, MedicalRecord, MedicationLog, Patient, Prescription, User

DEMO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "demo_documents"))


@pytest.fixture()
def app_ctx():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        os.environ["DEMO_DOCUMENTS_DIR"] = DEMO_DIR
        yield app
        db.session.remove()
        db.drop_all()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_seed_demo_loads_everything_and_is_usable(app_ctx):
    runner = app_ctx.test_cli_runner()
    out = runner.invoke(args=["seed-demo"]).output
    assert "Demo data loaded" in out and "documents=" in out
    assert User.query.filter_by(role="patient").count() == 6 and User.query.filter_by(role="doctor").count() == 2
    assert Document.query.count() == 12 and Prescription.query.count() == 9
    assert MedicationLog.query.count() > 20
    amended = MedicalRecord.query.filter(MedicalRecord.amended_from_id.isnot(None)).all()
    assert len(amended) == 1 and amended[0].amendment_reason
    assert Prescription.query.filter_by(status="draft").count() == 2 and Prescription.query.filter_by(status="discontinued").count() == 1

    c = app_ctx.test_client()
    tok = c.post("/api/v1/auth/login", json={"email": "meera.iyer@demo.healthbridge.test", "password": "Demo@12345", "portal": "doctor"}).get_json()["access_token"]
    patients = c.get("/api/v1/patients", headers=auth(tok)).get_json()
    assert patients["total"] == 6
    meena = next(p for p in patients["patients"] if p["name"] == "Meena Rajan")
    docs = c.get(f"/api/v1/patients/{meena['id']}/documents", headers=auth(tok)).get_json()["documents"]
    assert len(docs) == 3
    f = c.get(f"/api/v1/documents/{docs[0]['id']}/file", headers=auth(tok))
    assert f.status_code == 200 and (f.data.startswith(b"%PDF") or f.data[:2] == b"\xff\xd8")  # decrypts to a real PDF/JPEG
    # the patient can log in and sees their own data
    ptok = c.post("/api/v1/auth/login", json={"email": "rahul.menon@demo.healthbridge.test", "password": "Demo@12345"}).get_json()["access_token"]
    med = c.get(f"/api/v1/patients/{Patient.query.filter_by(user_id=User.query.filter_by(email='rahul.menon@demo.healthbridge.test').first().id).first().id}/medication",
                headers=auth(ptok)).get_json()["medication"]
    assert len(med) == 3 and all(m["last_taken_at"] for m in med)


def test_seed_demo_is_repeatable_and_resettable(app_ctx):
    runner = app_ctx.test_cli_runner()
    runner.invoke(args=["seed-demo"])
    assert "already exists" in runner.invoke(args=["seed-demo"]).output
    assert "Demo data loaded" in runner.invoke(args=["seed-demo", "--reset"]).output
    assert Document.query.count() == 12 and Prescription.query.count() == 9 and User.query.count() == 8
    assert Patient.query.count() == 6


def test_seed_demo_refuses_production(app_ctx):
    app_ctx.config["ENV_NAME"] = "production"
    result = app_ctx.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "production" in result.output
