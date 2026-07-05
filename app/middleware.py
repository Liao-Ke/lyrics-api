import time

from app.logging import logger


def register_middleware(app):
    @app.middleware("http")
    async def request_logging(request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = (time.monotonic() - start) * 1000
        key_id = getattr(request.state, "key_id", "anonymous")
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=f"{latency_ms:.1f}",
            key_id=key_id,
        )
        return response