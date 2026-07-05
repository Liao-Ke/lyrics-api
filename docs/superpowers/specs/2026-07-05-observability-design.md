# 可观测性设计

**日期：** 2026-07-05

## 目标

添加 Prometheus 可观测性基础设施，支撑后续性能压测的可量化对比。

## 方案对比

### /metrics 实现

| 方案 | 依赖 | 代码量 | exposition 正确性 | 兼容性 |
|---|---|---|---|---|
| A `prometheus_client` + `generate_latest()` | +1 纯 Python | 3 行 | 标准 | 好（FastAPI route） |
| B `prometheus_client` + `make_asgi_app()` | +1 纯 Python | 2 行 | 标准 | 差（ASGI lifespan 不兼容 FastAPI mount） |
| C 手写 dict + 文本输出 | 0 | ~80 行 | flimsier（+Inf/转义/_total/排序） | N/A |

**选定：A**。二行与三行差异可忽略，但 mount 方案有实际兼容问题（FastAPI 在挂载 ASGI app 时发送 lifespan 事件，`make_asgi_app` 不处理 lifespan → 响应不可达）。`generate_latest()` + 内联 route 完全兼容。

### Trace ID

| 方案 | 实现 | 并发安全 | loguru 集成 |
|---|---|---|---|
| `contextvars.ContextVar` + patcher | 10 行 | ✓（asyncio Task 级） | ✓（`configure(patcher=...)`） |
| `threading.local` | ~5 行 | ✓（thread 级） | 需额外配置 |
| 只传 request.state | ~5 行 | ✓ | 每 log 调用手动传 |

**选定：contextvars + patcher**。`ContextVar` 是 asyncio-native 并发原语，patcher 将 `request_id` 自动注入每条日志，下游代码无需手动传参。

### 标签基数控制

| 做法 | 风险 |
|---|---|
| `path` 用 `request.url.path` | 爆基数（`/songs/1`, `/songs/2`, …） |
| `path` 用 `request.scope["route"].path` | 基数可控（`/songs/{song_id}`） |
| label 含 `key_id` | 基数按使用者数量膨胀 + 泄漏身份 |
| label 不含 `key_id` | 无用户身份信息暴露 |

**选定**：route.path_format + 不放 key_id。

## 边界与已排除

| 不做 | 理由 |
|---|---|
| OpenTelemetry | 单服务，分布追踪无意义 |
| Grafana dashboard JSON | YAGNI，用户自行配置或看 Prometheus 原生查询 |
| Alerting rules | 无 SLO/Pager，作品集不需要 |
| Log aggregation 接入 | loguru JSON 到 stdout 已容器友好，部署方自行接入 Loki/ES |
| /metrics 鉴权 | Prometheus 抓取惯例是不鉴权 + 白名单网络 |

## 变更影响

`prometheus-client>=0.20` 被引入 runtime 依赖（`requirements.txt`）。dev 依赖不变。