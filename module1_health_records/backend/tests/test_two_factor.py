import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User
from app.utils import second_factor as sf
from app.utils import totp


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


def login(client, **extra):
    return client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "AdminPass1", **extra})


def bearer(client):
    return {"Authorization": "Bearer " + login(client).get_json()["access_token"]}


def turn_on(client):
    """Switch two-factor on for the admin. Returns (secret, backup_codes)."""
    h = bearer(client)
    setup = client.post("/api/v1/auth/2fa/setup", headers=h).get_json()
    secret = setup["secret"].replace(" ", "")
    code = totp.code_at(secret)
    r = client.post("/api/v1/auth/2fa/enable", json={"code": code}, headers=h)
    assert r.status_code == 200
    return secret, r.get_json()["backup_codes"]


def user():
    return User.query.filter_by(email="admin@test.com").first()


def test_setup_gives_secret_and_secret_is_stored_encrypted(client):
    r = client.post("/api/v1/auth/2fa/setup", headers=bearer(client))
    body = r.get_json()
    assert r.status_code == 200 and body["otpauth_uri"].startswith("otpauth://")
    raw = body["secret"].replace(" ", "")
    assert raw not in user().totp_secret_enc
    assert sf.read_secret(user()) == raw
    assert user().totp_enabled is False


def test_enable_needs_a_correct_code(client):
    h = bearer(client)
    client.post("/api/v1/auth/2fa/setup", headers=h)
    assert client.post("/api/v1/auth/2fa/enable", json={"code": "000000"}, headers=h).status_code == 400
    assert user().totp_enabled is False


def test_login_now_needs_a_second_step(client):
    secret, _ = turn_on(client)
    r = login(client)
    body = r.get_json()
    assert r.status_code == 200 and body["mfa_required"] is True
    assert "access_token" not in body and "user" not in body


def test_second_step_with_correct_code_logs_in(client):
    secret, _ = turn_on(client)
    ticket = login(client).get_json()["ticket"]
    # the code used while enabling cannot be reused, so use the next time step
    import time
    code = totp.code_at(secret, when=time.time() + 30)
    r = client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": code})
    assert r.status_code == 200 and "access_token" in r.get_json()


def test_wrong_code_and_bad_ticket_are_refused(client):
    turn_on(client)
    ticket = login(client).get_json()["ticket"]
    assert client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": "123456"}).status_code == 401
    assert client.post("/api/v1/auth/login/2fa", json={"ticket": "garbage", "code": "123456"}).status_code == 401


def test_a_normal_login_token_is_not_a_ticket_and_ticket_is_not_a_login_token(client):
    turn_on(client)
    ticket = login(client).get_json()["ticket"]
    # refused either way (401 or 422 "not a valid token"); the ticket must never open the API
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ticket}"}).status_code in (401, 422)


def test_backup_code_works_once(client):
    secret, codes = turn_on(client)
    ticket = login(client).get_json()["ticket"]
    assert client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": codes[0]}).status_code == 200
    ticket = login(client).get_json()["ticket"]
    assert client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": codes[0]}).status_code == 401


def test_repeated_wrong_codes_lock_the_account(client):
    turn_on(client)
    for _ in range(5):
        ticket = login(client).get_json()["ticket"]
        client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": "111111"})
    assert login(client).status_code == 429


def test_wrong_portal_is_refused_before_the_code_step(client):
    turn_on(client)
    assert login(client, portal="doctor").status_code == 401


def test_cookie_mode_second_step_sets_cookie(client):
    secret, codes = turn_on(client)
    ticket = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "AdminPass1"},
                         headers={"X-Auth-Mode": "cookie"}).get_json()["ticket"]
    r = client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": codes[0]}, headers={"X-Auth-Mode": "cookie"})
    assert r.status_code == 200 and "access_token" not in r.get_json()
    assert any(c.startswith("access_token_cookie=") for c in r.headers.getlist("Set-Cookie"))


def test_disable_needs_password_and_code(client):
    secret, codes = turn_on(client)
    h = bearer_after_2fa(client, codes[0])
    assert client.post("/api/v1/auth/2fa/disable", json={"password": "wrong", "code": codes[1]}, headers=h).status_code == 400
    assert client.post("/api/v1/auth/2fa/disable", json={"password": "AdminPass1", "code": codes[1]}, headers=h).status_code == 200
    assert user().totp_enabled is False and user().totp_secret_enc is None
    assert "access_token" in login(client).get_json()


def bearer_after_2fa(client, backup_code):
    ticket = login(client).get_json()["ticket"]
    token = client.post("/api/v1/auth/login/2fa", json={"ticket": ticket, "code": backup_code}).get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_me_reports_two_factor_state(client):
    h = bearer(client)
    assert client.get("/api/v1/auth/me", headers=h).get_json()["user"]["two_factor_enabled"] is False


def test_cli_reset_turns_it_off(client):
    turn_on(client)
    result = client.application.test_cli_runner().invoke(args=["reset-2fa", "--email", "admin@test.com"])
    assert result.exit_code == 0 and "turned off" in result.output
    assert "access_token" in login(client).get_json()
