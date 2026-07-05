import sqlite3

from app.models import LyricLine, Song, SongsPage
from app.repositories.base import SongRepository

_VALID_SCOPES = frozenset({"title", "artist", "writer", "lyrics"})


class SqliteSongRepository(SongRepository):

    def __init__(self, db_path: str = "data/lyrics.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def get_song(self, song_id: int) -> Song | None:
        row = self._conn.execute(
            "SELECT * FROM songs WHERE id = ?", (song_id,)
        ).fetchone()
        return self._row_to_song(row) if row else None

    def list_songs(
        self,
        *,
        title: str | None = None,
        artist: str | None = None,
        writer: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> SongsPage:
        page = max(1, page)
        size = max(1, min(size, 100))

        clauses: list[str] = []
        params: list[str] = []

        if title:
            clauses.append("s.title LIKE ?")
            params.append(f"%{title}%")
        if artist:
            clauses.append("s.artist LIKE ?")
            params.append(f"%{artist}%")
        if writer:
            clauses.append("(s.lyricist LIKE ? OR s.composer LIKE ? OR s.arranger LIKE ?)")
            params.extend([f"%{writer}%"] * 3)

        where = " AND ".join(clauses) if clauses else "1=1"

        total = self._conn.execute(
            f"SELECT COUNT(*) FROM songs s WHERE {where}", params
        ).fetchone()[0]

        offset = (page - 1) * size
        rows = self._conn.execute(
            f"SELECT s.* FROM songs s WHERE {where} ORDER BY s.title LIMIT ? OFFSET ?",
            [*params, size, offset],
        ).fetchall()

        return SongsPage(
            items=[self._row_to_song(r) for r in rows],
            total=total,
            page=page,
            size=size,
        )

    def search(self, query: str, scope: list[str] | None = None) -> list[Song]:
        q = query.strip()
        if not q:
            return []

        active = _VALID_SCOPES if scope is None else (set(scope) & _VALID_SCOPES)
        if not active:
            return []

        like_param = f"%{q}%"
        subqueries: list[str] = []
        params: list[str] = []

        if "lyrics" in active:
            if len(q) >= 3:
                safe = q.replace('"', '""')
                subqueries.append(
                    "SELECT DISTINCT song_id AS id FROM lyrics "
                    "JOIN lyrics_fts ON lyrics_fts.rowid = lyrics.id "
                    "WHERE lyrics_fts MATCH ?"
                )
                params.append(f'"{safe}"')
            else:
                subqueries.append(
                    "SELECT DISTINCT song_id AS id FROM lyrics WHERE text LIKE ?"
                )
                params.append(like_param)

        for sc in ("title", "artist", "writer"):
            if sc in active:
                if sc == "title":
                    subqueries.append("SELECT id FROM songs WHERE title LIKE ?")
                    params.append(like_param)
                elif sc == "artist":
                    subqueries.append("SELECT id FROM songs WHERE artist LIKE ?")
                    params.append(like_param)
                elif sc == "writer":
                    subqueries.append(
                        "SELECT id FROM songs WHERE lyricist LIKE ? OR composer LIKE ? OR arranger LIKE ?"
                    )
                    params.extend([like_param] * 3)

        rows = self._conn.execute(
            " UNION ".join(subqueries), params
        ).fetchall()
        if not rows:
            return []

        ids = [r[0] for r in rows]
        placeholders = ",".join("?" * len(ids))
        songs = self._conn.execute(
            f"SELECT * FROM songs WHERE id IN ({placeholders}) ORDER BY title", ids
        ).fetchall()
        return [self._row_to_song(r) for r in songs]

    def get_lyrics(self, song_id: int) -> list[LyricLine]:
        rows = self._conn.execute(
            "SELECT * FROM lyrics WHERE song_id = ? ORDER BY seq", (song_id,)
        ).fetchall()
        return [self._row_to_lyric(r) for r in rows]

    def get_lyric_at_time(
        self, song_id: int, time_sec: float, context: int = 1
    ) -> list[LyricLine]:
        row = self._conn.execute(
            "SELECT seq FROM lyrics WHERE song_id = ? AND time_sec <= ? ORDER BY time_sec DESC LIMIT 1",
            (song_id, time_sec),
        ).fetchone()

        if row is None:
            rows = self._conn.execute(
                "SELECT * FROM lyrics WHERE song_id = ? ORDER BY seq LIMIT ?",
                (song_id, context * 2 + 1),
            ).fetchall()
            return [self._row_to_lyric(r) for r in rows] if rows else []

        center = row["seq"]
        rows = self._conn.execute(
            "SELECT * FROM lyrics WHERE song_id = ? AND seq BETWEEN ? AND ? ORDER BY seq",
            (song_id, max(0, center - context), center + context),
        ).fetchall()
        return [self._row_to_lyric(r) for r in rows]

    @staticmethod
    def _row_to_song(row: sqlite3.Row) -> Song:
        return Song(
            id=row["id"],
            title=row["title"],
            title_raw=row["title_raw"],
            version=row["version"],
            artist=row["artist"],
            lyricist=row["lyricist"],
            composer=row["composer"],
            arranger=row["arranger"],
            has_translation=bool(row["has_translation"]),
        )

    @staticmethod
    def _row_to_lyric(row: sqlite3.Row) -> LyricLine:
        return LyricLine(
            time_sec=row["time_sec"],
            time_str=row["time_str"],
            text=row["text"],
            translation=row["translation"],
            seq=row["seq"],
        )