import re
from datetime import timedelta, timezone

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import AuditLog, PasswordResetToken, User

URL = "/api/v1/auth/password-reset"


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(name="Pat Ient", email="pat@test.com", role="patient")
        user.set_password("OldPassword1")
        db.session.add(user)
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def outbox(client):
    return client.application.extensions.get("outbox", [])


def ask(client, email="pat@test.com"):
    return client.post(f"{URL}/request", json={"email": email})


def token_from_mail(client):
    return re.search(r"token=([\w-]+)", outbox(client)[-1]["body"]).group(1)


def login(client, password):
    return client.post("/api/v1/auth/login", json={"email": "pat@test.com", "password": password})


def test_request_sends_link_and_answer_is_the_same_for_unknown_email(client):
    known, unknown = ask(client), ask(client, "nobody@test.com")
    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()
    assert len(outbox(client)) == 1 and outbox(client)[0]["to"] == "pat@test.com"


def test_link_resets_password_and_works_only_once(client):
    ask(client)
    token = token_from_mail(client)
    r = client.post(f"{URL}/confirm", json={"token": token, "new_password": "NewPassword9"})
    assert r.status_code == 200
    assert login(client, "NewPassword9").status_code == 200
    assert login(client, "OldPassword1").status_code == 401
    again = client.post(f"{URL}/confirm", json={"token": token, "new_password": "AnotherPass7"})
    assert again.status_code == 400


def test_token_is_stored_only_as_a_hash(client):
    ask(client)
    token = token_from_mail(client)
    assert PasswordResetToken.query.one().token_hash != token


def test_newest_link_replaces_older_ones(client):
    ask(client)
    first = token_from_mail(client)
    ask(client)
    second = token_from_mail(client)
    assert client.post(f"{URL}/confirm", json={"token": first, "new_password": "NewPassword9"}).status_code == 400
    assert client.post(f"{URL}/confirm", json={"token": second, "new_password": "NewPassword9"}).status_code == 200


def test_expired_and_bad_tokens_are_refused(client):
    ask(client)
    token = token_from_mail(client)
    record = PasswordResetToken.query.one()
    record.expires_at = record.expires_at.replace(tzinfo=timezone.utc) - timedelta(hours=1)
    db.session.commit()
    assert client.post(f"{URL}/confirm", json={"token": token, "new_password": "NewPassword9"}).status_code == 400
    assert client.post(f"{URL}/confirm", json={"token": "nonsense", "new_password": "NewPassword9"}).status_code == 400
    assert client.post(f"{URL}/confirm", json={"new_password": "NewPassword9"}).status_code == 400


def test_weak_new_password_is_refused_and_link_stays_usable(client):
    ask(client)
    token = token_from_mail(client)
    assert client.post(f"{URL}/confirm", json={"token": token, "new_password": "short"}).status_code == 400
    assert client.post(f"{URL}/confirm", json={"token": token, "new_password": "NewPassword9"}).status_code == 200


def test_reset_signs_out_existing_sessions(client):
    old = login(client, "OldPassword1").get_json()["access_token"]
    ask(client)
    client.post(f"{URL}/confirm", json={"token": token_from_mail(client), "new_password": "NewPassword9"})
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_disabled_account_gets_no_link(client):
    User.query.filter_by(email="pat@test.com").one().is_active = False
    db.session.commit()
    assert ask(client).status_code == 200
    assert outbox(client) == []


def test_requests_are_rate_limited_per_email(client):
    codes = [ask(client).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_reset_keeps_two_factor_on(client):
    user = User.query.filter_by(email="pat@test.com").one()
    user.totp_enabled = True
    db.session.commit()
    ask(client)
    client.post(f"{URL}/confirm", json={"token": token_from_mail(client), "new_password": "NewPassword9"})
    assert login(client, "NewPassword9").get_json().get("mfa_required") is True


def test_events_are_audited_without_secrets(client):
    ask(client)
    client.post(f"{URL}/confirm", json={"token": token_from_mail(client), "new_password": "NewPassword9"})
    actions = [a.action for a in AuditLog.query.all()]
    assert "password_reset_requested" in actions and "password_reset_done" in actions
    assert not any("NewPassword9" in (a.detail or "") for a in AuditLog.query.all())
