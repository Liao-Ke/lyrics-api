from fastapi.testclient import TestClient

VALID_KEY = "test-api-key-active"
HEADERS = {"Authorization": f"Bearer {VALID_KEY}"}


def test_get_lyrics_full(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/1/lyrics", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["song_id"] == 1
    assert len(data["lyrics"]) == 3
    assert data["lyrics"][0]["text"] == "第一行"
    assert data["lyrics"][1]["text"] == "暗里着迷"
    assert data["lyrics"][1]["translation"] == "secretly"
    assert "time_sec" not in data or data["time_sec"] is None


def test_get_lyrics_karaoke(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/1/lyrics?time=7.5&context=1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["song_id"] == 1
    assert data["time_sec"] == 7.5
    assert data["context"] == 1
    assert len(data["lyrics"]) == 3
    assert data["lyrics"][0]["seq"] == 0
    assert data["lyrics"][1]["seq"] == 1
    assert data["lyrics"][2]["seq"] == 2


def test_get_lyrics_karaoke_before_start(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/1/lyrics?time=-1", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["song_id"] == 1
    assert len(data["lyrics"]) == 3


def test_get_lyrics_karaoke_after_end(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/1/lyrics?time=999", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["song_id"] == 1
    assert data["lyrics"][-1]["seq"] == 2


def test_get_lyrics_song_not_found(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/999/lyrics", headers=HEADERS)
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_lyrics_unauthorized(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/songs/1/lyrics")
    assert resp.status_code == 401