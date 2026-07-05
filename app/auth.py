import hashlib
import sqlite3
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPBearer

from app.config import get_settings, Settings
from app.deps import get_db_conn
from app.errors import UnauthorizedError
from app.logging import logger
from app.metrics import auth_failures_total

_bearer = HTTPBearer(auto_error=False)


@dataclass
class KeyContext:
    key_id: str
    rate_limit_rpm: int


ANONYMOUS = KeyContext(key_id="anonymous", rate_limit_rpm=0)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _authenticate(
    key_raw: str, conn: sqlite3.Connection, settings: Settings,
) -> KeyContext:
    key_hash = hashlib.sha256(key_raw.encode()).hexdigest()
    row = conn.execute(
        "SELECT key_id, rate_limit_rpm FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
        (key_hash,),
    ).fetchone()
    if row is None:
        raise UnauthorizedError("invalid_key")
    return KeyContext(key_id=row["key_id"], rate_limit_rpm=row["rate_limit_rpm"])


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
        logger.info("audit", event="auth_failure", key_id="unknown", reason="missing_header", ip=_client_ip(request), path=request.url.path)
        raise UnauthorizedError("missing_header")

    if creds.scheme.lower() != "bearer":
        auth_failures_total.labels(reason="malformed_header").inc()
        logger.info("audit", event="auth_failure", key_id="unknown", reason="malformed_header", ip=_client_ip(request), path=request.url.path)
        raise UnauthorizedError("malformed_header")

    try:
        ctx = _authenticate(creds.credentials, conn, settings)
    except UnauthorizedError:
        auth_failures_total.labels(reason="invalid_key").inc()
        logger.info("audit", event="auth_failure", key_id="unknown", reason="invalid_key", ip=_client_ip(request), path=request.url.path)
        raise

    request.state.key_id = ctx.key_id
    return ctx


def verify_api_key_flexible(
    request: Request,
    creds=Depends(_bearer),
    conn: sqlite3.Connection = Depends(get_db_conn),
    settings: Settings = Depends(get_settings),
) -> KeyContext:
    if not settings.API_KEYS_ENABLED:
        request.state.key_id = ANONYMOUS.key_id
        return ANONYMOUS

    if creds is not None and creds.scheme.lower() == "bearer":
        try:
            ctx = _authenticate(creds.credentials, conn, settings)
        except UnauthorizedError:
            auth_failures_total.labels(reason="invalid_key").inc()
            logger.info("audit", event="auth_failure", key_id="unknown", reason="invalid_key", ip=_client_ip(request), path=request.url.path)
            raise
        request.state.key_id = ctx.key_id
        return ctx

    query_key = request.query_params.get("key")
    if query_key:
        try:
            ctx = _authenticate(query_key, conn, settings)
            request.state.key_id = ctx.key_id
            return ctx
        except UnauthorizedError:
            auth_failures_total.labels(reason="invalid_query_key").inc()
            logger.info("audit", event="auth_failure", key_id="unknown", reason="invalid_query_key", ip=_client_ip(request), path=request.url.path)
            raise UnauthorizedError("invalid_key")

    auth_failures_total.labels(reason="missing_header").inc()
    logger.info("audit", event="auth_failure", key_id="unknown", reason="missing_header", ip=_client_ip(request), path=request.url.path)
    raise UnauthorizedError("missing_header")