from fastapi.testclient import TestClient

VALID_KEY = "test-api-key-active"
HEADERS = {"Authorization": f"Bearer {VALID_KEY}"}


class TestSecurityHeaders:
    def test_healthz_has_security_headers(self, test_app):
        client = TestClient(test_app)
        resp = client.get("/healthz")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["Cache-Control"] == "no-store"

    def test_api_songs_has_security_headers(self, test_app):
        client = TestClient(test_app)
        resp = client.get("/api/v1/songs", headers=HEADERS)
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["Cache-Control"] == "no-store"

    def test_metrics_has_security_headers(self, test_app):
        client = TestClient(test_app)
        resp = client.get("/metrics")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["Cache-Control"] == "no-store"

    def test_api_has_rate_limit_headers_on_success(self, test_app):
        client = TestClient(test_app)
        resp = client.get("/api/v1/songs", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.headers.get("X-RateLimit-Limit") == "60"
        assert resp.headers.get("X-RateLimit-Remaining") is not None
        assert resp.headers.get("X-RateLimit-Reset") is not None

    def test_401_has_no_rate_limit_headers(self, test_app):
        client = TestClient(test_app)
        resp = client.get("/api/v1/songs")
        assert resp.status_code == 401
        assert resp.headers.get("X-RateLimit-Limit") is None

    def test_429_has_retry_after(self, test_app, auth_conn):
        import hashlib
        low_rpm_hash = hashlib.sha256(b"low-rpm-integration").hexdigest()
        auth_conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, name, created_at, rate_limit_rpm) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("low-int", low_rpm_hash, "low rpm", 1),
        )
        auth_conn.commit()

        client = TestClient(test_app)
        h = {"Authorization": "Bearer low-rpm-integration"}
        client.get("/api/v1/songs", headers=h)
        resp = client.get("/api/v1/songs", headers=h)
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") is not None
        assert int(resp.headers["Retry-After"]) >= 1


class TestAuditLog:
    def test_auth_failure_logged(self, test_app, audit_log):
        client = TestClient(test_app)
        client.get("/api/v1/songs")
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 1
        assert events[0]["record"]["extra"]["reason"] == "missing_header"

    def test_valid_auth_not_logged_as_failure(self, test_app, audit_log):
        client = TestClient(test_app)
        client.get("/api/v1/songs", headers=HEADERS)
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 0