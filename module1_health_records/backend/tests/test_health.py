from app import create_app
from app.config import TestConfig


def test_health_endpoint():
    app = create_app(TestConfig)
    client = app.test_client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_health_db_endpoint():
    app = create_app(TestConfig)
    client = app.test_client()
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.get_json()["database"] == "connected"


def test_health_db_failure_does_not_leak_details(monkeypatch):
    from app.extensions import db

    app = create_app(TestConfig)
    client = app.test_client()

    def boom(*args, **kwargs):
        raise RuntimeError("password authentication failed for user secret@ep-example.neon.tech")

    monkeypatch.setattr(db.session, "execute", boom)
    response = client.get("/api/v1/health/db")
    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "database": "unreachable"}
    assert "neon.tech" not in response.get_data(as_text=True)
