from fastapi.testclient import TestClient


def test_health_ok(test_app):
    client = TestClient(test_app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert isinstance(body["songs_total"], int)
    assert isinstance(body["cache_entries"], int)
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0


def test_health_no_auth_required(test_app):
    client = TestClient(test_app)
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_metrics_endpoint(test_app):
    client = TestClient(test_app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain; version=")
    assert b"http_requests_total" in resp.content
    assert b"http_request_duration_seconds" in resp.content
    assert b"cache_ops_total" in resp.content
    assert b"auth_failures_total" in resp.content
    assert b"rate_limited_total" in resp.content