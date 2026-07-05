from fastapi.testclient import TestClient

VALID_KEY = "test-api-key-active"
HEADERS = {"Authorization": f"Bearer {VALID_KEY}"}


def test_list_songs(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["size"] == 20


def test_list_songs_filter_title(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs?title=测试A", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "测试A"


def test_list_songs_filter_artist(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs?artist=艺术家1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_songs_filter_writer(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs?writer=作词人1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_songs_pagination(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs?page=1&size=2", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3


def test_get_song(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "测试A"
    assert data["artist"] == "艺术家1"
    assert data["lyricist"] == "作词人1"


def test_get_song_not_found(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/999", headers=HEADERS)
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["detail"]["resource_id"] == "999"


def test_unauthorized_no_header(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["detail"]["reason"] == "missing_header"


def test_unauthorized_invalid_key(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs", headers={"Authorization": "Bearer invalid-key"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["detail"]["reason"] == "invalid_key"


def test_unauthorized_malformed_scheme(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/songs", headers={"Authorization": "Basic dGVzdDp0ZXN0"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_invalid_page_parameter(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs?page=0", headers=HEADERS)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_size_parameter(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs?size=0", headers=HEADERS)
    assert resp.status_code == 422


def test_revoked_key(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/songs", headers={"Authorization": "Bearer test-api-key-revoked"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["detail"]["reason"] == "invalid_key"