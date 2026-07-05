import sqlite3

from app.config import get_settings
from app.repositories.base import SongRepository
from app.repositories.caching import CachingSongRepository
from app.repositories.sqlite_repo import SqliteSongRepository


def get_db_path() -> str:
    return get_settings().DATABASE_PATH


_db_conn: sqlite3.Connection | None = None


def get_db_conn() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
    return _db_conn


_repo: SongRepository | None = None


def get_repository() -> SongRepository:
    global _repo
    if _repo is None:
        inner = SqliteSongRepository(get_db_path())
        _repo = CachingSongRepository(inner)
    return _repo