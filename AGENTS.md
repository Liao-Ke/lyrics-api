# AGENTS.md — 歌词API

全局开发环境、工程原则、任务分级、Git 提交规范见 `~/.config/opencode/AGENTS.md`，本文件只记录本仓库特有的高信号信息。

## 项目状态

阶段 0（骨架 + 文档）、阶段1（配置+日志+导入）、阶段2（Repository）、阶段3（HTTP 交叉基础设施）、阶段4（API 端点层）、阶段5（容器化部署与落地页）、阶段6（CI 流水线）、阶段7a（可观测性增强）、阶段7b（性能压测与基线）、阶段8（安全加固）均已完成并提交。执行计划与决策记录在 `docs/arch/README.md`（21 条 ADR）。

## 数据流

```
lrc/*.lrc  →  scripts/clean_lrc.py  →  data/songs/*.json  →  scripts/import_songs.py  →  data/lyrics.db
└─ 容器构建：Dockerfile builder 阶段 ──→ data/lyrics.db（烤入镜像）

HTTP 请求 → security_headers（post: 设安全响应头）
         → CORS（条件挂载，CORS_ORIGINS 非空时）
         → request_logging（pre: set request_id；post: record_request + log）
         → FastAPI 路由匹配
         ├─ /healthz / /metrics / → 直通（无鉴权/限流）
         └─ /api/v1/* → Depends(verify_api_key) → Depends(check_rate_limit)
                      │ 超限 → 429 + Retry-After 头 + audit 日志
                      │ 成功 → X-RateLimit-* 三头
                      → 路由端点 → Depends(get_repository) → 缓存装饰器 → sqlite3
         → auth_failure / rate_limited / key_issued / key_revoked → audit 日志（loguru JSON stdout）
```

- `clean_lrc.py` 用相对路径 `../lrc` 和 `../data`，**必须从 `scripts/` 目录运行**：`python scripts/clean_lrc.py`（workdir=scripts/ 也可以）
- `data/lyrics.db` 是运行时生成物，不提交（已在 `.gitignore`），容器构建时自动生成

## 关键约束

- **schema.sql 手动管理，不上 alembic**。Repository ABC 抽象已支持将来换库时再加迁移工具
- **FTS5 trigram 是 SQLite 专属**，搜索实现锁在 `SqliteSongRepository` 内部，接口只暴露 `search(query, scope)`
- **限流是滑动窗口**（`rate_counters` 存每请求时间戳），不是固定窗口。作为 FastAPI dependency 而非中间件，`/healthz` 不走限流
- **审计日志走 loguru JSON stdout**，不上 sqlite 表（ADR-021）。4 类事件：`auth_failure` / `rate_limited` / `key_issued` / `key_revoked`
- **`retry_after_seconds` = 最早请求过期时间**（`oldest + 60 - now`），非窗口长度。`Handle_http_exception` 429 防御分支不设 Retry-After 头
- **HSTS 受环境变量 `HSTS_ENABLED` 开关**（默认 false），需反代 TLS 场景才开
- **安全响应头手写中间件**，不引 `secure` 库
- **配置安全**：`API_KEYS_ENABLED=false` 且 `HOST` 非 localhost 时，启动必须打 WARNING 日志
- **metrics label 不放 key_id**：基数爆炸 + 泄漏使用者身份，违反 ADR-001 半开放定位
- **path 标签用路由模板**：`request.scope["route"].path`（如 `/songs/{song_id}`），不用 `request.url.path`
- **/metrics 受 METRICS_ENABLED 开关**：默认开启，部署方可关闭

## 常用命令

```bash
# 清洗 LRC（从 scripts/ 运行）
python scripts/clean_lrc.py

# 导入 JSON → SQLite
python scripts/import_songs.py

# 生成 API key
python scripts/seed_key.py

# 测试（覆盖率门槛 80%）
pytest --cov --cov-fail-under=80

# Lint
ruff check .

# 性能压测（需先启动服务）
python scripts/load_test.py --endpoint /healthz --concurrency 100 --duration 10

# 吊销 API key
python scripts/revoke_key.py <key_id>

# FTS5 查询计划分析
python scripts/perf_inspect.py

# 裸跑
python -m app.main

# 容器
podman compose up -d
```

## 技术栈锁定

FastAPI + pydantic-settings + loguru + sqlite3 标准库 + prometheus_client（仅 metrics）。测试用 pytest + pytest-asyncio + httpx + pytest-cov。压测用手写 httpx 脚本（不引入 locust/k6）。不引入 ORM（SQLModel/SQLAlchemy），不引入 Redis（缓存用内存 dict + TTL）。