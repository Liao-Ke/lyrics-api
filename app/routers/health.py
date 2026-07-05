import sqlite3

from fastapi import APIRouter, Depends

from app.deps import get_db_conn

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health(conn: sqlite3.Connection = Depends(get_db_conn)):
    try:
        conn.execute("SELECT 1").fetchone()
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status}