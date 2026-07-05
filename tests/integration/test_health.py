from fastapi.testclient import TestClient


def test_health_ok(test_app):
    client = TestClient(test_app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "db": "ok"}


def test_health_no_auth_required(test_app):
    client = TestClient(test_app)
    resp = client.get("/healthz")
    assert resp.status_code == 200