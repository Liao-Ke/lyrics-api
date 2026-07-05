from app.config import get_settings


def set_security_headers(response, request):
    settings = get_settings()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith(("/api/", "/metrics", "/healthz")):
        response.headers["Cache-Control"] = "no-store"
    if response.media_type == "text/html":
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    if settings.HSTS_ENABLED:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"