from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import (
    ApiError,
    InternalError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    ValidationError,
    register_exception_handlers,
)


def test_unauthorized_shape():
    err = UnauthorizedError("missing_header")
    assert err.code == "UNAUTHORIZED"
    assert err.http_status == 401
    assert err.detail == {"reason": "missing_header"}


def test_not_found_shape():
    err = NotFoundError("song", "42")
    assert err.code == "NOT_FOUND"
    assert err.http_status == 404
    assert err.detail == {"resource_type": "song", "resource_id": "42"}


def test_rate_limited_shape():
    err = RateLimitedError(45, 60)
    assert err.code == "RATE_LIMITED"
    assert err.http_status == 429
    assert err.detail == {"retry_after_seconds": 45, "limit": 60}


def test_validation_error_shape():
    err = ValidationError([{"field": "size", "message": "too big"}])
    assert err.code == "VALIDATION_ERROR"
    assert err.http_status == 422
    assert err.detail == {"errors": [{"field": "size", "message": "too big"}]}


def test_internal_error_shape():
    err = InternalError()
    assert err.code == "INTERNAL_ERROR"
    assert err.http_status == 500
    assert err.detail == {}


def test_api_error_custom():
    err = ApiError("CUSTOM", 418, "I'm a teapot", {"foo": "bar"})
    assert err.code == "CUSTOM"
    assert err.http_status == 418
    assert err.detail == {"foo": "bar"}


def test_register_handlers_produces_correct_response():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-not-found")
    def raise_not_found():
        raise NotFoundError("song", "999")

    client = TestClient(app)
    resp = client.get("/raise-not-found")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["detail"]["resource_id"] == "999"


def test_http_exception_404_wrapped():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-404")
    def http_404():
        raise HTTPException(status_code=404, detail="Not here")

    client = TestClient(app)
    resp = client.get("/http-404")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_http_exception_500_wrapped():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-500")
    def http_500():
        raise HTTPException(status_code=500, detail="broken")

    client = TestClient(app)
    resp = client.get("/http-500")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"


def test_request_validation_wrapped():
    app = FastAPI()
    register_exception_handlers(app)

    class Body(BaseModel):
        size: int

    @app.post("/validate")
    def validate(body: Body):
        return {"ok": True}

    client = TestClient(app)
    resp = client.post("/validate", json={"size": "not-a-number"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert len(body["error"]["detail"]["errors"]) > 0