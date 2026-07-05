# 阶段8：安全加固

**日期：** 2026-07-05

## 目标

为歌词API增加生产就绪安全层：安全响应头中间件、限流响应头修复 + 增强、审计日志、CORS 完善、key 吊销脚本。

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/security_headers.py` | 安全响应头中间件（X-Content-Type-Options/X-Frame-Options/Referrer-Policy/Cache-Control/CSP/HSTS） |
| `scripts/revoke_key.py` | API key 吊销脚本（UPDATE revoked_at + 审计日志） |
| `tests/unit/test_security_headers.py` | 安全头中间件单元测试（10 个用例） |
| `tests/integration/test_security_headers.py` | 安全头 + 限流头 + 审计日志集成测试（8 个用例） |
| `docs/features/phase-8.md` | 本阶段记录 |
| `docs/superpowers/specs/2026-07-05-security-hardening-design.md` | 设计文档 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/config.py` | 加 `HSTS_ENABLED: bool = False` |
| `app/errors.py` | `ApiError` 加 `headers` 关键字参数；`_as_json` 合并头；`RateLimitedError` 默认设 `Retry-After` 头；`handle_http_exception` 429 防御分支传空 headers |
| `app/middleware.py` | 重构 `register_middleware`：安全头中间件（最外层）、CORS 中间件（expose_headers + max_age）、request_logging 均移入；CORS 从 `main.py` 迁入 |
| `app/ratelimit.py` | `check_rate_limit` 接收 `Response` 参数；修复 `retry_after_seconds` 算法为 `max(1, int(oldest+60-now)+1)`；成功响应设 `X-RateLimit-Limit/Remaining/Reset` 三头；超限记审计日志 |
| `app/auth.py` | 4 类 auth failure 路径加 `logger.info("audit", event="auth_failure", ...)` |
| `app/main.py` | 移除 CORS 注册块（已迁入 `middleware.py`）；`METRICS_ENABLED` 改用 `get_settings()` 调用 |
| `scripts/seed_key.py` | 签发后加 `logger.info("audit", event="key_issued", ...)` |
| `tests/conftest.py` | 加 `audit_log` fixture（loguru JSON sink 捕获审计事件） |
| `tests/unit/test_errors.py` | 加 3 个用例：RateLimitedError Retry-After 头、空 headers、自定义 headers |
| `tests/unit/test_ratelimit.py` | 加 3 个用例：X-RateLimit-* 头、anonymous 不设头、429 Retry-After 头 |
| `tests/unit/test_auth.py` | 4 个用例加 audit_log 断言 |
| `tests/smoke/test_smoke.py` | 加安全头 + X-RateLimit-* 头断言 |
| `docs/arch/README.md` | 追加 ADR-021（安全加固） |
| `docs/api/README.md` | 通用约定补安全响应头/限流头/审计日志；错误码 `RATE_LIMITED` detail 语义修正 |
| `docs/deploy/README.md` | 环境变量表加 `HSTS_ENABLED`；快速部署加 revoke_key 步骤；可观测性加审计日志段 |
| `docs/db/README.md` | 审计日志说明（不走 sqlite 表）；api_keys 访问模式表写者加 revoke_key.py |
| `README.md` | 环境变量加 `HSTS_ENABLED`；项目结构补 security_headers.py/revoke_key.py；特性补安全段 |
| `RULES.md` | 技术栈约束补安全头/审计；禁止事项补审计表/CSP/HSTS/Retry-After/X-RateLimit-*；反模式补 retry_after 算法 |
| `AGENTS.md` | 项目状态补阶段8；数据流图补 security_headers + audit 分支；关键约束补审计/HSTS/retry_after/安全头；常用命令补 revoke_key |
| `.env.example` | 加 `HSTS_ENABLED=false`、`METRICS_ENABLED=true` |

## 核心实现

### 安全响应头中间件

`app/security_headers.py`：`set_security_headers(response, request)` 函数，在 `register_middleware` 中以最外层中间件注册。对所有响应设 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: strict-origin-when-cross-origin`；对 `/api/`、`/metrics`、`/healthz` 路径设 `Cache-Control: no-store`；对 `media_type="text/html"` 设 `Content-Security-Policy: default-src 'self'`；`HSTS_ENABLED=true` 时设 `Strict-Transport-Security: max-age=31536000`。

### 限流响应头修复

`retry_after_seconds` 算法从 `int(now - window_start)`（恒=60）修复为 `max(1, int(oldest + 60 - now) + 1)`，其中 `oldest = MIN(request_at)` 是窗口内最早请求时间戳。`X-RateLimit-Limit` = RPM 上限，`X-RateLimit-Remaining = max(0, rpm - count)`，`X-RateLimit-Reset = int(oldest + 60)`（epoch 秒）。

### 审计日志

loguru JSON stdout 4 类事件：`auth_failure`（含 reason/ip/path）、`rate_limited`（含 limit/retry_after）、`key_issued`（含 key_id/name）、`key_revoked`（含 key_id）。运行时事件在 `app/auth.py` 和 `app/ratelimit.py` 中现有 counter 调用点旁写入；脚本事件在 `scripts/seed_key.py` 和 `scripts/revoke_key.py` 中写入。

## 验证结果

| 项 | 结果 |
|---|---|
| ruff check | 通过 |
| pytest --cov --cov-fail-under=80 | 121 passed, 93.76% |
| 安全头 10 项单元测试 | 全部通过 |
| 安全头 + 限流头 + 审计日志集成测试 | 8 项全部通过 |
| 冒烟测试（安全头 + X-RateLimit-*） | 通过 |

## 已知限制

- HSTS 仅在 `HSTS_ENABLED=true` 且部署在反代 TLS 后方有意义，默认 false
- 审计日志走 loguru JSON stdout，不可直接 SQL 查询（需日志聚合系统）
- `retry_after` 用 `MIN(request_at)` 而非 `OFFSET count - rpm` 查询第 N 旧请求，count >> rpm 时略偏小（ponytail: 60 RPM 下 burst ≤ 3，差异 ≤ 3s）
- `revoke_key.py` 不提供 list/rotate 功能（仅吊销，需手动管理）
- CORS 保持 opt-in（`CORS_ORIGINS` 非空时启用），JS 客户端需 `expose_headers` 以读取限流头