# 接口文档 — 错误响应

所有 API 端点共享统一错误响应格式。

## 响应格式

```json
{
  "error": {
    "code": "<ERROR_CODE>",
    "message": "<人类可读描述>",
    "detail": {}
  }
}
```

## 错误码表

| code | HTTP | 触发条件 | detail |
|------|------|----------|--------|
| `UNAUTHORIZED` | 401 | API key 缺失、无效、已吊销，或 `Authorization` 头格式错误 | `reason`: `missing_header` / `malformed_header` / `invalid_key` / `revoked_key` |
| `RATE_LIMITED` | 429 | 请求频率超过当前 key 的 RPM 上限 | `retry_after_seconds`: 窗口剩余秒数（int）; `limit`: RPM 上限 |
| `NOT_FOUND` | 404 | 请求的资源（歌曲/歌词）不存在 | `resource_type`: `song` / `lyrics`; `resource_id`: 请求的 ID（str） |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败（类型错误、越界等） | `errors`: `[{field, message}]` |
| `INTERNAL_ERROR` | 500 | 服务器内部未预期异常 | 仅开发环境含 `debug` 信息，生产环境省略 |

## 示例

### 401 — API key 无效

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid API key",
    "detail": { "reason": "invalid_key" }
  }
}
```

### 429 — 超限

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded",
    "detail": { "retry_after_seconds": 45, "limit": 60 }
  }
}
```

### 404 — 歌曲不存在

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Song not found",
    "detail": { "resource_type": "song", "resource_id": "9999" }
  }
}
```

### 422 — 参数越界

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "detail": {
      "errors": [
        { "field": "size", "message": "ensure this value is less than or equal to 100" },
        { "field": "page", "message": "ensure this value is greater than or equal to 1" }
      ]
    }
  }
}
```

## 实现说明

- 由 `app/errors.py` 的 `register_exception_handlers(app)` 在应用启动时注入
- 自定异常 `ApiError`、FastAPI 的 `RequestValidationError`、`HTTPException` 统一进入此格式
- 非 FastAPI 的 500 异常（未捕获异常）由 `INTERNAL_ERROR` 兜底，生产环境不暴露栈信息