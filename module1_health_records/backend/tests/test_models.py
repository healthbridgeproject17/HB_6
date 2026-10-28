import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, Patient, Doctor, Prescription, MedicationLog
from app.utils.health_id import generate_health_id


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def make_user(email, role="patient"):
    u = User(name="Test " + role, email=email, role=role)
    u.set_password("StrongPass1")
    db.session.add(u)
    db.session.commit()
    return u


def test_password_is_hashed_and_checked(app):
    u = make_user("a@test.com")
    assert u.password_hash != "StrongPass1"
    assert u.check_password("StrongPass1")
    assert not u.check_password("wrong")


def test_invalid_role_rejected(app):
    u = User(name="Bad", email="bad@test.com", role="hacker")
    u.set_password("StrongPass1")
    db.session.add(u)
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_health_id_format_and_uniqueness(app):
    ids = []
    for i in range(3):
        u = make_user(f"p{i}@test.com")
        p = Patient(user_id=u.id, health_id=generate_health_id())
        db.session.add(p)
        db.session.commit()
        ids.append(p.health_id)
    assert all(h.startswith("HB-") and len(h) == 14 for h in ids)
    assert len(set(ids)) == 3
    assert ids[0].endswith("000001")


def test_duplicate_health_id_rejected(app):
    u1, u2 = make_user("x1@test.com"), make_user("x2@test.com")
    db.session.add(Patient(user_id=u1.id, health_id="HB-2026-000001"))
    db.session.commit()
    db.session.add(Patient(user_id=u2.id, health_id="HB-2026-000001"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_prescription_defaults_to_draft_and_log_status_checked(app):
    u = make_user("pp@test.com")
    p = Patient(user_id=u.id, health_id=generate_health_id())
    db.session.add(p)
    db.session.commit()
    rx = Prescription(patient_id=p.id, medicine="Example Medicine A")
    db.session.add(rx)
    db.session.commit()
    assert rx.status == "draft"
    db.session.add(MedicationLog(prescription_id=rx.id, patient_id=p.id, status="maybe"))
    with pytest.raises(IntegrityError):
        db.session.commit()
