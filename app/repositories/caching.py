import time

from app.models import LyricLine, Song, SongsPage
from app.repositories.base import SongRepository


class CachingSongRepository(SongRepository):
    def __init__(self, inner: SongRepository, ttl_sec: int = 3600):
        self._inner = inner
        self._ttl = ttl_sec
        self._cache: dict[str, tuple[float, object]] = {}

    def _get(self, key: str) -> object | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, val = entry
        if time.monotonic() - ts > self._ttl:
            del self._cache[key]
            return None
        return val

    def _set(self, key: str, val: object) -> None:
        self._cache[key] = (time.monotonic(), val)

    def get_song(self, song_id: int) -> Song | None:
        key = f"get_song:{song_id}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.get_song(song_id)
        self._set(key, result)
        return result

    def list_songs(
        self,
        *,
        title: str | None = None,
        artist: str | None = None,
        writer: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> SongsPage:
        return self._inner.list_songs(title=title, artist=artist, writer=writer, page=page, size=size)

    def search(self, query: str, scope: list[str] | None = None) -> list[Song]:
        key = f"search:{query}:{scope}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.search(query, scope)
        self._set(key, result)
        return result

    def get_lyrics(self, song_id: int) -> list[LyricLine]:
        key = f"get_lyrics:{song_id}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.get_lyrics(song_id)
        self._set(key, result)
        return result

    def get_lyric_at_time(self, song_id: int, time_sec: float, context: int = 1) -> list[LyricLine]:
        key = f"get_lyric_at_time:{song_id}:{time_sec}:{context}"
        cached = self._get(key)
        if cached is not None:
            return cached
        result = self._inner.get_lyric_at_time(song_id, time_sec, context)
        self._set(key, result)
        return result