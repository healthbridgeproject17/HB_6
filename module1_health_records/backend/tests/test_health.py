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
