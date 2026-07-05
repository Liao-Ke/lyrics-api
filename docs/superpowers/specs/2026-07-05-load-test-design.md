# 性能压测设计

**日期：** 2026-07-05

## 目标

为歌词API建立可复现的性能基线，支撑后续优化决策。

## 方案对比

### 压测框架

| 方案 | 依赖 | 安装 | 适用性 |
|---|---|---|---|
| A 手写 httpx + asyncio | ~80 行，httpx 已 dev dep | pip 已有 | 单只读 API，够用 |
| B locust | gevent/flask/msgpack 等传递依赖 | pip install locust | 场景复杂时需 web UI |
| C k6 | 外部二进制 | brew install / apt | 需 JS 写脚本 |

**选定：A**。locust 引入 gevent 依赖，与 asyncio 不兼容（需额外配置 gevent 模式），且单只读 API 的 web UI 无意义。k6 是外部二进制，非 pip 管理。httpx 已在 dev dep 中，asyncio 是 stdlib。

### 百分位计算

| 方案 | 精度 | 依赖 |
|---|---|---|
| 线性插值（sorted + floor/ceil） | 连续 | 无 |
| numpy.percentile | 连续 | numpy（~20MB） |
| 直方图近似 | 近似 | 无 |

**选定：线性插值**。不引入 numpy（20MB 瓦罐），实时计算 10k 条延迟排序足够快。

### 查询计划分析

直接连接 SQLite 运行 `EXPLAIN QUERY PLAN` + 50 次平均计时。无第三方依赖。

## 边界与已排除

| 不做 | 理由 |
|---|---|
| 在 CI 中跑 load_test | 耗时长（30-60s）且结果受 runner 性能影响，不适合门禁 |
| 测试多版本 Python | 项目锁定 3.12 |
| locust web UI | 单只读 API 不需要 |
| k6 | 外部二进制，非 pip 管理 |

## 测试矩阵设计

| 场景 | 端点 | 并发 | 检验目标 |
|---|---|---|---|
| 健康检查 | /healthz | 100 | uvicorn 调度上限 |
| 指标 | /metrics | 50 | generate_latest() 序列化开销 |
| 鉴权失败 | /api/v1/songs | 20 | auth/hash/DB 查询开销 |
| 搜索 | /api/v1/search?q= | 20 | FTS5 分词 + 查询延迟 |

## 报告格式

基线报告记录在 `docs/perf/baseline-YYYY-MM-DD.md`，每份包含：测试环境、压测矩阵表（P50/P95/P99/Max/RPS）、查询计划、瓶颈分析、升级路径。对比回归时查最新一份。