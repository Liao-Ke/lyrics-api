import sqlite3

from fastapi import APIRouter, Depends

from app.deps import get_db_conn, get_repository
from app.metrics import get_uptime_seconds
from app.repositories.base import SongRepository

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health(
    conn: sqlite3.Connection = Depends(get_db_conn),
    repo: SongRepository = Depends(get_repository),
):
    try:
        conn.execute("SELECT 1").fetchone()
        db_status = "ok"
    except Exception:
        db_status = "error"

    try:
        songs_total = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
    except Exception:
        songs_total = -1

    cache_entries = repo.cache_size
    uptime_seconds = int(get_uptime_seconds())

    return {
        "status": "ok",
        "db": db_status,
        "songs_total": songs_total,
        "cache_entries": cache_entries,
        "uptime_seconds": uptime_seconds,
    }