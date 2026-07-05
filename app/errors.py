from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, http_status: int, message: str, detail: dict | None = None):
        self.code = code
        self.http_status = http_status
        self.message = message
        self.detail = detail or {}


class NotFoundError(ApiError):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            code="NOT_FOUND",
            http_status=404,
            message=f"{resource_type} not found",
            detail={"resource_type": resource_type, "resource_id": str(resource_id)},
        )


class UnauthorizedError(ApiError):
    def __init__(self, reason: str = "invalid_key"):
        reasons = {
            "missing_header": "Missing API key",
            "malformed_header": "Malformed Authorization header",
            "invalid_key": "Invalid API key",
            "revoked_key": "API key has been revoked",
        }
        super().__init__(
            code="UNAUTHORIZED",
            http_status=401,
            message=reasons.get(reason, "Unauthorized"),
            detail={"reason": reason},
        )


class RateLimitedError(ApiError):
    def __init__(self, retry_after_seconds: int, limit: int):
        super().__init__(
            code="RATE_LIMITED",
            http_status=429,
            message="Rate limit exceeded",
            detail={"retry_after_seconds": retry_after_seconds, "limit": limit},
        )


class ValidationError(ApiError):
    def __init__(self, errors: list[dict]):
        super().__init__(
            code="VALIDATION_ERROR",
            http_status=422,
            message="Request validation failed",
            detail={"errors": errors},
        )


class InternalError(ApiError):
    def __init__(self, debug: str | None = None):
        detail = {"debug": debug} if debug else {}
        super().__init__(
            code="INTERNAL_ERROR",
            http_status=500,
            message="Internal server error",
            detail=detail,
        )


def _as_json(error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.http_status,
        content={"error": {"code": error.code, "message": error.message, "detail": error.detail}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _as_json(exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return _as_json(ValidationError(errors))

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 404:
            e = NotFoundError("resource", str(exc.detail) if exc.detail else "unknown")
        elif exc.status_code in (401, 403):
            e = UnauthorizedError("invalid_key")
        elif exc.status_code == 429:
            e = RateLimitedError(0, 0)
        elif exc.status_code == 422:
            detail = exc.detail if isinstance(exc.detail, list) else [{"loc": [], "msg": str(exc.detail)}]
            errors = [{"field": ".".join(str(p) for p in d["loc"]), "message": d["msg"]} for d in detail]
            e = ValidationError(errors)
        else:
            e = ApiError(code="INTERNAL_ERROR", http_status=exc.status_code, message=str(exc.detail or "Unknown error"))
        return _as_json(e)