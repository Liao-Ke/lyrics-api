from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import KeyContext, verify_api_key, verify_api_key_flexible
from app.config import Settings, get_settings
from app.deps import get_db_conn
from app.errors import register_exception_handlers


def _make_app(auth_conn, settings: Settings | None = None):
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_conn] = lambda: auth_conn
    app.dependency_overrides[get_settings] = lambda: settings or Settings(DATABASE_PATH="", API_KEYS_ENABLED=True)

    @app.get("/me")
    def me(ctx: KeyContext = Depends(verify_api_key)):
        return {"key_id": ctx.key_id, "rpm": ctx.rate_limit_rpm}

    return TestClient(app)


class TestAuth:
    def test_missing_header(self, auth_conn, audit_log):
        client = _make_app(auth_conn)
        resp = client.get("/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "missing_header"
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 1
        assert events[0]["record"]["extra"]["reason"] == "missing_header"

    def test_invalid_key(self, auth_conn, audit_log):
        client = _make_app(auth_conn)
        resp = client.get("/me", headers={"Authorization": "Bearer invalid-key"})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "invalid_key"
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 1
        assert events[0]["record"]["extra"]["reason"] == "invalid_key"

    def test_revoked_key(self, auth_conn, audit_log):
        client = _make_app(auth_conn)
        resp = client.get("/me", headers={"Authorization": "Bearer test-api-key-revoked"})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "invalid_key"
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 1
        assert events[0]["record"]["extra"]["reason"] == "invalid_key"

    def test_valid_key(self, auth_conn, audit_log):
        client = _make_app(auth_conn)
        resp = client.get("/me", headers={"Authorization": "Bearer test-api-key-active"})
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "active"
        assert resp.json()["rpm"] == 60
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 0

    def test_api_keys_disabled(self, auth_conn):
        settings = Settings(DATABASE_PATH="", API_KEYS_ENABLED=False)
        client = _make_app(auth_conn, settings=settings)
        resp = client.get("/me")
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "anonymous"
        assert resp.json()["rpm"] == 0


def _make_flexible_app(auth_conn, settings: Settings | None = None):
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_db_conn] = lambda: auth_conn
    app.dependency_overrides[get_settings] = lambda: settings or Settings(DATABASE_PATH="", API_KEYS_ENABLED=True)

    @app.get("/random")
    def rd(ctx: KeyContext = Depends(verify_api_key_flexible)):
        return {"key_id": ctx.key_id, "rpm": ctx.rate_limit_rpm}

    return TestClient(app)


class TestAuthFlexible:
    def test_bearer_header(self, auth_conn, audit_log):
        client = _make_flexible_app(auth_conn)
        resp = client.get("/random", headers={"Authorization": "Bearer test-api-key-active"})
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "active"

    def test_query_key(self, auth_conn, audit_log):
        client = _make_flexible_app(auth_conn)
        resp = client.get("/random?key=test-api-key-active")
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "active"

    def test_query_key_invalid(self, auth_conn, audit_log):
        client = _make_flexible_app(auth_conn)
        resp = client.get("/random?key=bad-key")
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "invalid_key"
        events = [r for r in audit_log if r["record"]["extra"].get("event") == "auth_failure"]
        assert len(events) == 1
        assert events[0]["record"]["extra"]["reason"] == "invalid_query_key"

    def test_bearer_precedence(self, auth_conn, audit_log):
        client = _make_flexible_app(auth_conn)
        resp = client.get(
            "/random?key=test-api-key-active",
            headers={"Authorization": "Bearer test-api-key-active"},
        )
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "active"

    def test_no_auth(self, auth_conn, audit_log):
        client = _make_flexible_app(auth_conn)
        resp = client.get("/random")
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "missing_header"

    def test_api_keys_disabled(self, auth_conn):
        settings = Settings(DATABASE_PATH="", API_KEYS_ENABLED=False)
        client = _make_flexible_app(auth_conn, settings=settings)
        resp = client.get("/random")
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "anonymous"