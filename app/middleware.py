import time
import uuid

from app.logging import logger, request_id_var
from app.metrics import record_request


def register_middleware(app):
    @app.middleware("http")
    async def request_logging(request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request_id_var.set(request_id)
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        latency_ms = (time.monotonic() - start) * 1000
        key_id = getattr(request.state, "key_id", "anonymous")

        route = request.scope.get("route")
        path_template = getattr(route, "path", request.url.path) if route else request.url.path

        record_request(request.method, path_template, response.status_code, latency_ms)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            path_template=path_template,
            status=response.status_code,
            latency_ms=f"{latency_ms:.1f}",
            key_id=key_id,
        )
        return response