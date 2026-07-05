from fastapi.testclient import TestClient

VALID_KEY = "test-api-key-active"
HEADERS = {"Authorization": f"Bearer {VALID_KEY}"}


def test_smoke(test_app):
    client = TestClient(test_app)

    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Cache-Control"] == "no-store"

    resp = client.get("/api/v1/songs", headers=HEADERS)
    assert resp.status_code == 200
    songs_data = resp.json()
    assert songs_data["total"] > 0
    assert resp.headers.get("X-RateLimit-Limit") == "60"
    first_id = songs_data["items"][0]["id"]

    resp = client.get(f"/api/v1/songs/{first_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == first_id
    assert resp.headers.get("X-RateLimit-Limit") == "60"

    resp = client.get(f"/api/v1/songs/{first_id}/lyrics", headers=HEADERS)
    assert resp.status_code == 200
    lyrics_data = resp.json()
    assert lyrics_data["song_id"] == first_id
    assert len(lyrics_data["lyrics"]) > 0
    assert resp.headers.get("X-RateLimit-Limit") == "60"

    resp = client.get(
        f"/api/v1/songs/{first_id}/lyrics?time=5.0&context=1", headers=HEADERS
    )
    assert resp.status_code == 200
    karaoke = resp.json()
    assert karaoke["time_sec"] == 5.0
    assert resp.headers.get("X-RateLimit-Limit") == "60"

    resp = client.get("/api/v1/search?q=测试", headers=HEADERS)
    assert resp.status_code == 200
    search_data = resp.json()
    assert search_data["total"] > 0
    assert resp.headers.get("X-RateLimit-Limit") == "60"