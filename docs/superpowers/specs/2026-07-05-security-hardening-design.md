# 安全加固设计文档

**日期：** 2026-07-05

## 背景

歌词API已完成 0-7 阶段（骨架→部署→CI→可观测→压测基线），PRD 验收标准全部满足。phase-7b 留下三个工程缺口：压测未覆盖 `/api/v1`（401 未鉴权）、仅单 worker 基线、缓存冷启动无指标。选择「安全加固」作为阶段 8 方向。

## 方案对比

### 方案 A（推荐）：中间件统一加头 + 现有 dependency 链扩展 + ApiError 支持 headers

- **安全响应头**：新增 `app/security_headers.py` 中间件，对所有响应统一设安全头；HSTS 受 `HSTS_ENABLED` 开关（默认 false）
- **Retry-After + 三头**：`ApiError` 加 `headers` 字段，`_as_json` 合并；`RateLimitedError` 设 `Retry-After` 头；`ratelimit.py` 修复算法 + 成功响应设 X-RateLimit-* 三头
- **审计**：在 auth.py/ratelimit.py 现有 counter 旁加 `logger.info("audit", ...)`；seed_key.py 加签发日志；新增 revoke_key.py
- **CORS 完善**：`expose_headers` + `max_age`，保持 `allow_credentials=False`、默认 opt-in

**优点**：改动面聚焦、每层职责清晰、符合现有架构与不引入无必要依赖原则

### 方案 B：不新增中间件，安全头走 dependency / exception handler（排除）

安全头需覆盖所有响应（含 StaticFiles/healthz），走 dependency 只能覆盖 API 端点。不可行。

### 方案 C：引入 `secure` 库（排除）

安全头需求为静态值，手写 ~20 行够用，新依赖是 YAGNI。

## 设计

### 架构与组件

| 组件 | 位置 | 职责 |
|---|---|---|
| `app/security_headers.py`（新增） | 中间件 | 对所有响应设安全头；HSTS 受开关；CSP 仅 HTML |
| `app/errors.py`（扩展） | `ApiError` 加 `headers` 字段 + `_as_json` 合并头；`RateLimitedError` 设 `Retry-After` 头 | 让 429 响应带标准头 |
| `app/ratelimit.py`（扩展） | `check_rate_limit` 接收 `Response` 参数；修复 `retry_after_seconds` 算法；成功响应设 X-RateLimit-* 三头 | 限流响应头 + 算法修复 |
| `app/auth.py` + `app/ratelimit.py`（扩展） | 在 counter 调用点旁加 `logger.info("audit", ...)` | 运行时审计日志 |
| `app/main.py`（扩展） | `create_app` 注册安全头中间件；CORS 块迁入 `middleware.py` | 装配 |
| `app/config.py`（扩展） | 加 `HSTS_ENABLED: bool = False` | HSTS 开关 |
| `scripts/seed_key.py`（扩展） | 签发后审计日志 | key 生命周期审计 |
| `scripts/revoke_key.py`（新增） | `UPDATE ... revoked_at = datetime('now')` + 审计日志 | key 吊销 + 审计 |

**不动**：schema.sql、Repository 抽象、缓存、metrics

### 数据流

```
HTTP 请求
  → security_headers 中间件（post：设安全头）
  → CORS 中间件（仅 CORS_ORIGINS 非空时挂；expose_headers 暴露限流头）
  → request_logging 中间件（pre：set request_id；post：记请求日志 + record_request）
  → FastAPI 路由匹配
     ├─ /healthz / / /metrics → 直通，安全头中间件仍给它们加头
     └─ /api/v1/* → verify_api_key
        │  失败 → auth_failures counter + audit 日志 + UnauthorizedError
        │ 成功 → check_rate_limit(response: Response)
        │  ├─ 算 retry_after（窗口内最早请求 + 60 - now）
        │  ├─ 成功 → response.headers 设 X-RateLimit-Limit/Remaining/Reset
        │  └  超限 → rate_limited counter + audit 日志 + RateLimitedError(retry_after, limit) → _as_json 设 Retry-After
        → 路由端点 → Repository → sqlite3
  → 安全头中间件 post：统一补头（所有响应，含 StaticFiles 落地页 / 错误响应）
```

**中间件顺序**（FastAPI `add_middleware` + `@app.middleware` 均追加到 `user_middleware`，`reversed()` 构建栈）：security_headers（最外层）→ CORS → request_logging（最内层）。

### 算法与错误处理

**ApiError 扩展**：
```python
class ApiError(Exception):
    def __init__(self, code, http_status, message, detail=None, *, headers=None):
        self.headers = headers or {}

def _as_json(error):
    return JSONResponse(..., headers=error.headers)
```

**RateLimitedError**：`headers={"Retry-After": str(retry_after_seconds)}`，`handle_http_exception` 429 防御分支传 `headers={}`。

**retry_after_seconds 修复**：`max(1, int(oldest + 60 - now) + 1)`，`oldest = MIN(request_at)` 在窗口内。

**X-RateLimit-Reset**：`int(oldest + 60)`（epoch 秒），`oldest` 为 None 时用 `int(now + 60)`。

**审计日志字段**：
- `event`: `auth_failure` / `rate_limited` / `key_issued` / `key_revoked`
- `key_id`、`ip`（运行时）、`path`（运行时）、`reason`（auth_failure）
- `limit` + `retry_after_seconds`（rate_limited）
- 脚本事件省略 `ip`/`path`/`request_id`

### 测试策略

**新增 fixture**：`audit_log`（loguru JSON sink 捕获，返回 dict 列表）。

**单元**：
- `test_errors.py`：ApiError headers、RateLimitedError Retry-After 头
- `test_ratelimit.py`：X-RateLimit-* 头、retry_after 算法、anonymous 路径
- `test_security_headers.py`（新）：10 个用例覆盖所有安全头场景

**集成**：
- `test_security_headers.py`（新）：安全头、X-RateLimit-*、429 Retry-After、审计日志
- `test_auth.py`：4 类 auth failure 审计日志断言

**冒烟**：`test_smoke.py`：全链路安全头 + X-RateLimit-* 断言

## 验证

| 项 | 结果 |
|---|---|
| ruff check | 通过 |
| pytest --cov --cov-fail-under=80 | 121 passed, 93.76% |
| 安全头单元测试 | 10 项全部通过 |
| 集成测试 | 8 项全部通过 |
| 冒烟测试 | 通过 |