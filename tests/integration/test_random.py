from fastapi.testclient import TestClient

VALID_KEY = "test-api-key-active"
HEADERS = {"Authorization": f"Bearer {VALID_KEY}"}


def test_random_json_default(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "seq" in data
    assert "song" in data
    assert data["song"]["id"] in (1, 2, 3)


def test_random_js_format(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?format=js&key=" + VALID_KEY)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/javascript"
    body = resp.text
    assert "(function()" in body
    assert "lyric-random" in body
    assert "onRandomLyric" in body


def test_random_js_with_target(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?format=js&target=%23my-box&key=" + VALID_KEY)
    assert resp.status_code == 200
    body = resp.text
    assert "document.querySelector(sel)" in body
    assert "#my-box" in body


def test_random_js_callback_data(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?format=js&key=" + VALID_KEY)
    assert resp.status_code == 200
    body = resp.text
    assert "onRandomLyric(d)" in body
    assert "d.text" in body
    assert "d.title" in body
    assert "d.artist" in body


def test_random_filter_artist(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?artist=艺术家1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["song"]["artist"] == "艺术家1"


def test_random_filter_has_translation(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?has_translation=true", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["song"]["has_translation"] is True
    assert data["translation"] is not None


def test_random_filter_char_range_no_match(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?min_chars=100&max_chars=200", headers=HEADERS)
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_random_filter_char_range_narrow(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?min_chars=3&max_chars=3", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["text"]) == 3


def test_random_invalid_format(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?format=html", headers=HEADERS)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_random_unauthorized(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random")
    assert resp.status_code == 401


def test_random_query_key_auth(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?key=" + VALID_KEY)
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data


def test_random_query_key_invalid(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?key=bad-key")
    assert resp.status_code == 401


def test_random_cache_control(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store"


def test_random_x_ratelimit_headers(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random", headers=HEADERS)
    assert resp.status_code == 200
    assert "x-ratelimit-limit" in resp.headers
    assert "x-ratelimit-remaining" in resp.headers
    assert "x-ratelimit-reset" in resp.headers


def test_random_js_escape_special_chars(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?format=js&key=" + VALID_KEY)
    assert resp.status_code == 200
    body = resp.text
    assert "lyric-text" in body
    assert "lyric-meta" in body


def test_random_js_target_escape(test_app):
    client = TestClient(test_app)
    malicious = "');alert(1);//"
    resp = client.get(f"/api/v1/random?format=js&target={malicious}&key=" + VALID_KEY)
    assert resp.status_code == 200
    body = resp.text
    assert "alert(1)" in body
    # the ' should be escaped to \' so alert(1) stays inside the string
    assert "\\');alert(1)" in body


def test_random_no_match_404(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/random?artist=该歌手不存在", headers=HEADERS)
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"