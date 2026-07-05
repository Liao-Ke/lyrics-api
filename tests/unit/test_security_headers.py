from app.security_headers import set_security_headers


class MockResponse:
    def __init__(self, media_type="application/json"):
        self.headers = {}
        self.media_type = media_type


class MockRequest:
    def __init__(self, path="/", media_type="application/json"):
        class URL:
            def __init__(self, path):
                self.path = path
        self.url = URL(path)


def test_sets_x_content_type_options():
    resp = MockResponse()
    req = MockRequest("/healthz")
    set_security_headers(resp, req)
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_sets_x_frame_options():
    resp = MockResponse()
    req = MockRequest("/healthz")
    set_security_headers(resp, req)
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_sets_referrer_policy():
    resp = MockResponse()
    req = MockRequest("/healthz")
    set_security_headers(resp, req)
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_cache_control_no_store_on_api():
    resp = MockResponse()
    req = MockRequest("/api/v1/songs")
    set_security_headers(resp, req)
    assert resp.headers["Cache-Control"] == "no-store"


def test_cache_control_no_store_on_metrics():
    resp = MockResponse()
    req = MockRequest("/metrics")
    set_security_headers(resp, req)
    assert resp.headers["Cache-Control"] == "no-store"


def test_cache_control_no_store_on_healthz():
    resp = MockResponse()
    req = MockRequest("/healthz")
    set_security_headers(resp, req)
    assert resp.headers["Cache-Control"] == "no-store"


def test_no_cache_control_on_landing():
    resp = MockResponse()
    req = MockRequest("/")
    set_security_headers(resp, req)
    assert "Cache-Control" not in resp.headers


def test_csp_on_html():
    resp = MockResponse(media_type="text/html")
    req = MockRequest("/")
    set_security_headers(resp, req)
    assert resp.headers["Content-Security-Policy"] == "default-src 'self'"


def test_no_csp_on_json():
    resp = MockResponse(media_type="application/json")
    req = MockRequest("/api/v1/songs")
    set_security_headers(resp, req)
    assert "Content-Security-Policy" not in resp.headers


def test_hsts_not_set_by_default(monkeypatch):
    monkeypatch.setenv("HSTS_ENABLED", "false")
    from app.config import get_settings
    get_settings.cache_clear()
    resp = MockResponse()
    req = MockRequest("/")
    set_security_headers(resp, req)
    assert "Strict-Transport-Security" not in resp.headers
    get_settings.cache_clear()


def test_hsts_set_when_enabled(monkeypatch):
    monkeypatch.setenv("HSTS_ENABLED", "true")
    from app.config import get_settings
    get_settings.cache_clear()
    resp = MockResponse()
    req = MockRequest("/")
    set_security_headers(resp, req)
    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000"
    get_settings.cache_clear()