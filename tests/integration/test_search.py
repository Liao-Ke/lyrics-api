from fastapi.testclient import TestClient

VALID_KEY = "test-api-key-active"
HEADERS = {"Authorization": f"Bearer {VALID_KEY}"}


def test_search_title(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/search?q=测试", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "测试"
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["scope"] == ["title", "artist", "writer", "lyrics"]


def test_search_lyrics_scope(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/search?q=暗里着迷&scope=lyrics", headers=HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_search_title_scope(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/search?q=暗里着迷&scope=title", headers=HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_search_writer_scope(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/search?q=作词人1&scope=writer", headers=HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_search_multi_scope(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/search?q=暗里着迷&scope=title,lyrics", headers=HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_search_no_result(test_app):
    client = TestClient(test_app)
    resp = client.get(
        "/api/v1/search?q=不存在的歌词", headers=HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_search_empty_query(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/search?q=", headers=HEADERS)
    assert resp.status_code == 422


def test_search_unauthorized(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/search?q=测试")
    assert resp.status_code == 401