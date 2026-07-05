from pydantic import BaseModel


class Song(BaseModel):
    id: int
    title: str
    title_raw: str
    version: str | None = None
    artist: str
    lyricist: str | None = None
    composer: str | None = None
    arranger: str | None = None
    has_translation: bool = False


class LyricLine(BaseModel):
    time_sec: float | None = None
    time_str: str | None = None
    text: str | None = None
    translation: str | None = None
    seq: int


class SongWithLyrics(Song):
    lyrics: list[LyricLine] = []


class SongsPage(BaseModel):
    items: list[Song]
    total: int
    page: int
    size: int