# 阶段7a：可观测性增强

**日期：** 2026-07-05

## 目标

为歌词API添加可观测性基础设施：Prometheus metrics 端点、trace_id 注入、健康检查深度增强、缓存/鉴权/限流计数器埋点。

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/metrics.py` | Counter/Histogram/Gauge 定义 + `record_request()` 辅助函数 + `get_uptime_seconds()` |
| `docs/superpowers/specs/2026-07-05-observability-design.md` | 设计文档（方案对比/标签设计/边界） |

### 修改文件

| 文件 | 变更 |
|---|---|
| `requirements.txt` | + `prometheus-client>=0.20` |
| `app/config.py` | + `METRICS_ENABLED: bool = True` |
| `app/logging.py` | + contextvar `request_id_var` + loguru `patcher` 自动注入 |
| `app/middleware.py` | 生成 uuid request_id → contextvar + request.state；调用 `record_request()` |
| `app/main.py` | 条件挂载 `GET /metrics`（METRICS_ENABLED 开关）；模块级调用 `setup_logging()` |
| `app/routers/health.py` | + `songs_total` / `cache_entries` / `uptime_seconds` 字段 |
| `app/repositories/base.py` | `SongRepository.cache_size` property（默认 0） |
| `app/repositories/caching.py` | `_get` 内埋点 `cache_ops_total{method,result}`；`cache_size` 返回 `len(self._cache)` |
| `app/auth.py` | 各失败路径 `auth_failures_total{reason}` |
| `app/ratelimit.py` | 抛 `RateLimitedError` 前 `rate_limited_total.inc()` |
| `tests/integration/test_health.py` | 更新 healthz 断言；新增 `/metrics` 端点测试 |
| `tests/unit/test_caching.py` | 新增 `test_cache_size_detects_population` / `test_cache_hit_miss_counters` |
| `docs/arch/README.md` | 模块图补 metrics.py；数据流补 record_request；追加 ADR-019（prometheus_client 策略） |
| `docs/api/README.md` | 接口清单补 `GET /metrics`；健康检查章节更新字段 |
| `docs/deploy/README.md` | 环境变量表补 METRICS_ENABLED；新增「可观测性」段 |
| `README.md` | 环境变量表/API端点表/技术栈/项目结构更新 |
| `AGENTS.md` | 项目状态补阶段7a；关键约束补 metrics label 规则；技术栈锁定补 prometheus_client |
| `RULES.md` | 禁止事项补 metrics label 规则；反模式补「不要手写 exposition format」 |

## 核心实现

### Metrics 标签设计（ADR-019）

| Metric | 类型 | 标签 | 基数 |
|---|---|---|---|
| `http_requests_total` | Counter | `method, path, status` | 2×10×6≈120 |
| `http_request_duration_seconds` | Histogram | `method, path` | 2×10=20 |
| `cache_ops_total` | Counter | `method, result` | 4×2=8 |
| `auth_failures_total` | Counter | `reason` | 4 |
| `rate_limited_total` | Counter | 无 | 1 |

**关键规则**：`path` 标签用 `request.scope["route"].path`（路由模板 `/songs/{song_id}`），不用 `request.url.path`（避免 ID 爆基数）。不放 `key_id` 作 label（泄漏使用者身份）。

### /metrics 暴露策略

- 不鉴权（Prometheus 抓取惯例），受 `METRICS_ENABLED` 开关控制（默认 true）
- 端点用法 `GET /metrics`，返回 Prometheus text exposition 格式
- 标签不含 key_id，无隐私泄漏风险

### Trace ID

`app/logging.py` 导出一个 `request_id_var`（`contextvars.ContextVar`），`middleware.py` 在 pre-middleware 阶段注入 uuid hex（12 字符）。通过 loguru `patcher` 自动附加到每条日志记录的 `extra.request_id` 字段。

loguru `configure(patcher=...)` 是全局回调，但 `ContextVar` 基于 asyncio Task 隔离，并发请求互不干扰。

### 健康检查增强

```diff
- {"status": "ok", "db": "ok"}
+ {"status": "ok", "db": "ok", "songs_total": 1647, "cache_entries": 12, "uptime_seconds": 3600}
```

- `songs_total`：`SELECT COUNT(*) FROM songs`（证明数据已加载）
- `cache_entries`：`repo.cache_size`（缓存温状态）
- `uptime_seconds`：模块导入时 `time.monotonic()` 差值

### 依赖引入

`prometheus-client>=0.20`（纯 Python ~50KB，零传递依赖，PyPI 名 `prometheus-client`，import 名 `prometheus_client`）。使用 `generate_latest()` + `CONTENT_TYPE_LATEST` 以 FastAPI route 方式提供服务，不挂载 `make_asgi_app()`（避免 ASGI lifespan 事件兼容问题）。

## 验证结果

| 项 | 结果 |
|---|---|
| `ruff check .` | 通过 |
| `pytest --cov --cov-fail-under=80` | 96 passed, 97.57% |
| `curl /metrics` | 200 + text/plain + 5 个 metric 系列 |
| `curl /healthz` | 200 + 5 字段 |
| auth failures counter | 401 时 `auth_failures_total` 递增 |
| rate limit counter | 429 时 `rate_limited_total` 递增 |
| cache hit/miss counter | `cache_ops_total{result="hit|miss"}` 递增 |
| request_id in logs | 每条日志含 `request_id` 字段 |

## 已知限制

- `make_asgi_app()`（prometheus_client 0.25）返回的 ASGI3 应用与 FastAPI `app.mount` 的 lifespan 协议不兼容，改用 `generate_latest()` + 内联 route。若未来 prometheus_client 修复 lifespan 兼容性，可改回 mount 方式
- `/metrics` 端点请求走标准 middleware（有日志/metrics 自增强），不"零成本"。低流量场景无影响；高流量时可用配置 `METRICS_ENABLED=false` 关闭
- request_id 通过 loguru patcher 全局附加，但 ContextVar 为 asyncio Task 级别隔离，正确。若未来引入多线程 middleware（非 asyncio），需改用 `threading.local` + `contextvars.copy_context`
- `songs_total` 在每请求都 `SELECT COUNT(*)`，1647 行秒级计数，SQLite WAL 模式无锁争用，性能可接受。若未来到百万级需加缓存