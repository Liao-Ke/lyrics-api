from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import KeyContext, verify_api_key
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
    def test_missing_header(self, auth_conn):
        client = _make_app(auth_conn)
        resp = client.get("/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "missing_header"

    def test_invalid_key(self, auth_conn):
        client = _make_app(auth_conn)
        resp = client.get("/me", headers={"Authorization": "Bearer invalid-key"})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "invalid_key"

    def test_revoked_key(self, auth_conn):
        client = _make_app(auth_conn)
        resp = client.get("/me", headers={"Authorization": "Bearer test-api-key-revoked"})
        assert resp.status_code == 401
        assert resp.json()["error"]["detail"]["reason"] == "invalid_key"

    def test_valid_key(self, auth_conn):
        client = _make_app(auth_conn)
        resp = client.get("/me", headers={"Authorization": "Bearer test-api-key-active"})
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "active"
        assert resp.json()["rpm"] == 60

    def test_api_keys_disabled(self, auth_conn):
        settings = Settings(DATABASE_PATH="", API_KEYS_ENABLED=False)
        client = _make_app(auth_conn, settings=settings)
        resp = client.get("/me")
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "anonymous"
        assert resp.json()["rpm"] == 0