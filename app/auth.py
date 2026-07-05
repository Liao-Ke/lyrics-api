import hashlib
import sqlite3
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPBearer

from app.config import get_settings, Settings
from app.deps import get_db_conn
from app.errors import UnauthorizedError
from app.metrics import auth_failures_total

_bearer = HTTPBearer(auto_error=False)


@dataclass
class KeyContext:
    key_id: str
    rate_limit_rpm: int


ANONYMOUS = KeyContext(key_id="anonymous", rate_limit_rpm=0)


def verify_api_key(
    request: Request,
    creds=Depends(_bearer),
    conn: sqlite3.Connection = Depends(get_db_conn),
    settings: Settings = Depends(get_settings),
) -> KeyContext:
    if not settings.API_KEYS_ENABLED:
        request.state.key_id = ANONYMOUS.key_id
        return ANONYMOUS

    if creds is None:
        auth_failures_total.labels(reason="missing_header").inc()
        raise UnauthorizedError("missing_header")

    if creds.scheme.lower() != "bearer":
        auth_failures_total.labels(reason="malformed_header").inc()
        raise UnauthorizedError("malformed_header")

    key_hash = hashlib.sha256(creds.credentials.encode()).hexdigest()
    row = conn.execute(
        "SELECT key_id, rate_limit_rpm FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
        (key_hash,),
    ).fetchone()

    if row is None:
        auth_failures_total.labels(reason="invalid_key").inc()
        raise UnauthorizedError("invalid_key")

    ctx = KeyContext(key_id=row["key_id"], rate_limit_rpm=row["rate_limit_rpm"])
    request.state.key_id = ctx.key_id
    return ctx