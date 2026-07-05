from abc import ABC, abstractmethod

from app.models import LyricLine, Song, SongsPage


class SongRepository(ABC):

    @abstractmethod
    def get_song(self, song_id: int) -> Song | None: ...

    @abstractmethod
    def list_songs(
        self,
        *,
        title: str | None = None,
        artist: str | None = None,
        writer: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> SongsPage: ...

    @abstractmethod
    def search(self, query: str, scope: list[str] | None = None) -> list[Song]: ...

    @abstractmethod
    def get_lyrics(self, song_id: int) -> list[LyricLine]: ...

    @abstractmethod
    def get_lyric_at_time(
        self, song_id: int, time_sec: float, context: int = 1
    ) -> list[LyricLine]: ...