import hashlib

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_db_conn
from app.errors import register_exception_handlers
from app.ratelimit import check_rate_limit


def _make_app(auth_conn, settings: Settings | None = None):
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_conn] = lambda: auth_conn
    app.dependency_overrides[get_settings] = lambda: settings or Settings(DATABASE_PATH="", API_KEYS_ENABLED=True)

    @app.get("/test")
    def test(check=Depends(check_rate_limit)):
        return {"ok": True}

    return TestClient(app)


class TestRateLimit:
    def test_under_limit_passes(self, auth_conn):
        client = _make_app(auth_conn)
        resp = client.get("/test", headers={"Authorization": "Bearer test-api-key-active"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_under_limit_has_rate_limit_headers(self, auth_conn):
        client = _make_app(auth_conn)
        resp = client.get("/test", headers={"Authorization": "Bearer test-api-key-active"})
        assert resp.status_code == 200
        assert resp.headers.get("X-RateLimit-Limit") == "60"
        assert resp.headers.get("X-RateLimit-Remaining") is not None
        assert resp.headers.get("X-RateLimit-Reset") is not None

    def test_exceeds_limit(self, auth_conn):
        low_rpm_hash = hashlib.sha256(b"low-rpm-key").hexdigest()
        auth_conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, name, created_at, rate_limit_rpm) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("low", low_rpm_hash, "low rpm", 1),
        )
        auth_conn.commit()

        client = _make_app(auth_conn)
        resp1 = client.get("/test", headers={"Authorization": "Bearer low-rpm-key"})
        assert resp1.status_code == 200
        resp2 = client.get("/test", headers={"Authorization": "Bearer low-rpm-key"})
        assert resp2.status_code == 429
        body = resp2.json()["error"]
        assert body["code"] == "RATE_LIMITED"

    def test_exceeds_limit_has_retry_after(self, auth_conn):
        low_rpm_hash = hashlib.sha256(b"low-rpm-key-2").hexdigest()
        auth_conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, name, created_at, rate_limit_rpm) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("low2", low_rpm_hash, "low rpm", 1),
        )
        auth_conn.commit()

        client = _make_app(auth_conn)
        client.get("/test", headers={"Authorization": "Bearer low-rpm-key-2"})
        resp = client.get("/test", headers={"Authorization": "Bearer low-rpm-key-2"})
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") is not None
        retry_after = int(resp.headers["Retry-After"])
        assert 1 <= retry_after <= 61

    def test_anonymous_bypasses(self, auth_conn):
        settings = Settings(DATABASE_PATH="", API_KEYS_ENABLED=False)
        client = _make_app(auth_conn, settings=settings)
        for _ in range(10):
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_anonymous_has_no_rate_limit_headers(self, auth_conn):
        settings = Settings(DATABASE_PATH="", API_KEYS_ENABLED=False)
        client = _make_app(auth_conn, settings=settings)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.headers.get("X-RateLimit-Limit") is None

    def test_per_key_isolation(self, auth_conn):
        low_rpm_hash = hashlib.sha256(b"key-a").hexdigest()
        auth_conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, name, created_at, rate_limit_rpm) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("key_a", low_rpm_hash, "key a", 1),
        )
        high_rpm_hash = hashlib.sha256(b"key-b").hexdigest()
        auth_conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, name, created_at, rate_limit_rpm) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("key_b", high_rpm_hash, "key b", 60),
        )
        auth_conn.commit()

        client = _make_app(auth_conn)
        # Exhaust key_a
        resp1 = client.get("/test", headers={"Authorization": "Bearer key-a"})
        assert resp1.status_code == 200
        resp2 = client.get("/test", headers={"Authorization": "Bearer key-a"})
        assert resp2.status_code == 429
        # key_b still works (isolated)
        resp3 = client.get("/test", headers={"Authorization": "Bearer key-b"})
        assert resp3.status_code == 200