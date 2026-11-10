import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User

COOKIE = {"X-Auth-Mode": "cookie"}


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


def cookie_login(client):
    return client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "AdminPass1"}, headers=COOKIE)


def cookies(response):
    return [h for h in response.headers.getlist("Set-Cookie")]


def csrf_value(client):
    cookie = client.get_cookie("csrf_access_token")
    return cookie.value if cookie else None


def test_cookie_login_hides_token_and_sets_httponly_cookie(client):
    r = cookie_login(client)
    assert r.status_code == 200
    assert "access_token" not in r.get_json()
    access = [c for c in cookies(r) if c.startswith("access_token_cookie=")]
    assert access and "HttpOnly" in access[0] and "SameSite=Lax" in access[0]
    csrf = [c for c in cookies(r) if c.startswith("csrf_access_token=")]
    assert csrf and "HttpOnly" not in csrf[0]   # the page must be able to read this one


def test_cookie_session_works_for_reading(client):
    cookie_login(client)
    assert client.get("/api/v1/auth/me").status_code == 200


def test_cookie_session_needs_csrf_header_for_changes(client):
    cookie_login(client)
    assert client.post("/api/v1/auth/logout").status_code in (400, 401)       # no CSRF header: refused
    assert client.get("/api/v1/auth/me").status_code == 200                    # and still logged in


def test_cookie_logout_with_csrf_ends_session_and_clears_cookie(client):
    cookie_login(client)
    r = client.post("/api/v1/auth/logout", headers={"X-CSRF-TOKEN": csrf_value(client)})
    assert r.status_code == 200
    assert any(c.startswith("access_token_cookie=;") for c in cookies(r))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bearer_header_still_works_without_csrf(client):
    token = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "AdminPass1"}).get_json()["access_token"]
    plain = client.application.test_client()
    h = {"Authorization": f"Bearer {token}"}
    assert plain.get("/api/v1/auth/me", headers=h).status_code == 200
    assert plain.post("/api/v1/auth/change-password", json={"current_password": "x", "new_password": "y"}, headers=h).status_code == 400  # reached the route: no CSRF needed


def test_clear_session_removes_cookies(client):
    cookie_login(client)
    r = client.post("/api/v1/auth/session/clear")
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_login_without_header_mode_still_returns_token(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "AdminPass1"})
    assert "access_token" in r.get_json()
