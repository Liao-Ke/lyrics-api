import sqlite3
import time

from fastapi import Depends

from app.auth import KeyContext, verify_api_key
from app.deps import get_db_conn
from app.errors import RateLimitedError
from app.metrics import rate_limited_total


def check_rate_limit(
    key: KeyContext = Depends(verify_api_key),
    conn: sqlite3.Connection = Depends(get_db_conn),
) -> None:
    if key.key_id == "anonymous":
        return

    rpm = key.rate_limit_rpm
    now = time.time()
    window_start = now - 60

    conn.execute("DELETE FROM rate_counters WHERE key_id = ? AND request_at < ?", (key.key_id, window_start))
    conn.execute("INSERT INTO rate_counters (key_id, request_at) VALUES (?, ?)", (key.key_id, now))

    count = conn.execute(
        "SELECT COUNT(*) FROM rate_counters WHERE key_id = ? AND request_at >= ?",
        (key.key_id, window_start),
    ).fetchone()[0]

    conn.commit()

    if count > rpm:
        rate_limited_total.inc()
        raise RateLimitedError(retry_after_seconds=int(now - window_start), limit=rpm)