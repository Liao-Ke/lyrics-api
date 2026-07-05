import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.logging import logger
from app.middleware import register_middleware


def test_middleware_passthrough():
    app = FastAPI()
    register_middleware(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_middleware_logs_properly():
    app = FastAPI()
    register_middleware(app)

    @app.get("/ping")
    def ping():
        return {"pong": True}

    sink = io.StringIO()
    logger.add(sink, format="{message}", serialize=False)
    try:
        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 200
        output = sink.getvalue()
        assert "request" in output
    finally:
        logger.remove()