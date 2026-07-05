import sqlite3
import time

from fastapi import Depends, Response

from app.auth import KeyContext, verify_api_key
from app.deps import get_db_conn
from app.errors import RateLimitedError
from app.logging import logger
from app.metrics import rate_limited_total


def check_rate_limit(
    response: Response,
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

    oldest = conn.execute(
        "SELECT MIN(request_at) FROM rate_counters WHERE key_id = ? AND request_at >= ?",
        (key.key_id, window_start),
    ).fetchone()[0]
    remaining = max(0, rpm - count)
    reset = int(oldest + 60) if oldest is not None else int(now + 60)

    response.headers["X-RateLimit-Limit"] = str(rpm)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)

    conn.commit()

    if count > rpm:
        # ponytail: retry_after = oldest+60-now assumes count drops enough when the
        # oldest request expires. If count >> rpm, multiple requests must expire before
        # the next request is allowed. For 60 RPM with typical burst ≤ 3, this is adequate.
        retry_after = max(1, int(oldest + 60 - now) + 1) if oldest is not None else 60
        rate_limited_total.inc()
        logger.info("audit", event="rate_limited", key_id=key.key_id, limit=rpm, retry_after_seconds=retry_after)
        raise RateLimitedError(retry_after_seconds=retry_after, limit=rpm)