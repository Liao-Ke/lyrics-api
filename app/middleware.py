import time
import uuid

from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging import logger, request_id_var
from app.metrics import record_request
from app.security_headers import set_security_headers


def register_middleware(app):
    settings = get_settings()

    # security_headers: outermost — applies to all responses
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        set_security_headers(response, request)
        return response

    # CORS
    if settings.CORS_ORIGINS:
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET"],
            allow_headers=["Authorization"],
            expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
            max_age=600,
        )

    # request_logging: innermost
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