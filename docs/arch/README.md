# 架构描述：歌词API

## 模块职责

```
app/
├── main.py          # FastAPI 入口，路由注册，startup 初始化
├── config.py        # pydantic-settings 配置加载 + 安全 WARNING
├── deps.py          # 依赖注入链编排（repo / key / rate_limit）
├── errors.py        # 自定义异常 + @app.exception_handler 统一 JSON 错误
├── logging.py       # loguru 配置 + request_id contextvar
├── middleware.py     # 请求日志中间件 + record_request 调用 + request_id 注入
├── metrics.py       # Prometheus Counter/Histogram 定义 + record_request()
├── auth.py          # API key 鉴权 dependency（verify_api_key）+ auth_failures counter
├── ratelimit.py     # 滑动窗口限流 dependency（check_rate_limit）+ rate_limited counter
├── models.py        # Pydantic 请求/响应模型
├── routers/         # 端点路由
│   ├── songs.py     # /api/v1/songs /api/v1/songs/{id}
│   ├── search.py    # /api/v1/search
│   ├── lyrics.py    # /api/v1/songs/{id}/lyrics?time=
│   ├── random.py    # /api/v1/random?format=json|js
│   └── health.py    # /healthz
├── repositories/    # 数据访问层
│   ├── base.py      # SongRepository ABC 抽象基类（含 get_random_line）
│   ├── sqlite_repo.py  # SqliteSongRepository 实现（FTS5 锁内部）
│   └── caching.py   # 缓存装饰器（dict + TTL 1h）
└── static/          # 落地页 index.html
```

## 数据流

```
HTTP 请求 → 中间件（日志 pre）
→ FastAPI 路由匹配
├─ /healthz 或 / → 直通（无鉴权/限流）
├─ /api/v1/* (除 /random?format=js) → Depends(verify_api_key) [鉴权]
│                                    → Depends(check_rate_limit) [限流]
│                                    → 路由端点
│                                    → Depends(get_repository) [缓存装饰器 → SqliteSongRepository → sqlite3]
│                                    → Pydantic 序列化响应
└─ /api/v1/random?format=js → Depends(verify_api_key_flexible) [鉴权：Bearer 头优先，回退 ?key=]
                            → _enforce_rate_limit [限流]
                            → get_random_line [不缓存]
                            → JS IIFE 文本响应
→ 中间件（日志 post）
```

## 设计决策记录 (ADR)

### ADR-001: 定位为半开放作品集，非公网服务

**决策**：公网部署但带 API key 鉴权 + 限流 + robots 禁爬，不暴露全量目录。

**理由**：1647 首歌词受版权保护，未经授权公网提供全文 = 侵权风险。半开放模式（需 token 访问、非公开传播）将法律风险降至可接受。

**替代方案**：纯私有局域网（放弃公网可访问性）、全开放无鉴权（法律风险不可接受）。

---

### ADR-002: 多 API Key 鉴权，非 OAuth/JWT

**决策**：sqlite 存储 API key，支持签发/吊销/per-key 限流。请求通过 `Authorization: Bearer <key>` 传递。

**理由**：无用户系统，OAuth 过度设计。多 key 比单 token 提供细粒度管理（不同使用者不同 key）。

**替代方案**：单一静态 token（管理粗放）、OAuth/JWT（无用户系统，过度设计）。

---

### ADR-003: 滑动窗口限流，非固定窗口

**决策**：每请求在 `rate_counters` 表存一条时间戳，查询时 `COUNT WHERE request_at >= now - 60s`。默认 60 RPM/key。

**理由**：固定窗口有边界突刺（59s 和 61s 各 60 次，实际 1s 内 120 次）。滑动窗口每个请求独立判断，无边界突刺。

**替代方案**：固定窗口（代码更少但有漏洞）、令牌桶（作品集 demo 过度设计）。

---

### ADR-004: 限流作为 FastAPI dependency，非中间件

**决策**：`Depends(check_rate_limit)` 在 `verify_api_key` 之后、业务逻辑之前执行。

**理由**：/healthz 不该被限流（容器探针高频调用），中间件方式会误杀。dependency 方式每端点可选不同策略，职责分离更干净。

**替代方案**：中间件（/healthz 误伤，不可控）。

---

### ADR-005: sqlite3 全量导入，非 JSON 文件存储

**决策**：1647 首 JSON 导入 sqlite 单文件，songs + lyrics 表 + FTS5 trigram 虚拟表。

**理由**：单文件部署友好（容器化）；SQL 查询能力 >> 文件扫描；FTS5 全文搜索是 JSON 文件做不到的。

**替代方案**：纯 JSON 文件 + 内存索引（查询能力弱，无 FTS 搜索）、双轨混合存储（复杂度高，YAGNI）。

---

### ADR-006: 手写 Repository ABC 抽象，非 ORM

**决策**：`SongRepository` ABC 定义只读接口（get_song / list_songs / search / get_lyrics / get_lyric_at_time），`SqliteSongRepository` 实现。sqlite3 标准库，零 ORM 依赖。

**理由**：1647 首静态只读数据，ORM 的 session/relationship 是过度设计。ABC 抽象满足"换库只换实现"的诉求，sqlite3 标准库零依赖。

**替代方案**：SQLModel/SQLAlchemy（OR 依赖 + session 管理，过度设计）、直接写 SQL 无抽象（换库改全局）。

---

### ADR-007: FTS5 trigram 分词，中文搜索

**决策**：sqlite FTS5 虚拟表，`tokenize='trigram'`，`content=lyrics` 同步模式。title/artist 元数据搜索走 SQL 层 JOIN + LIKE。

**理由**：trigram 是 sqlite 3.34+ 内置分词器，零外部依赖，对中文按三字滑窗，效果好于 unicode61。FTS5 只索引歌词正文（体积大、需分词），元数据 1647 首用 LIKE 够用。

**替代方案**：jieba 分词（需 Python 层预分词，复杂度高）、LIKE 全模糊（无分词，搜索体验差）。

---

### ADR-008: 缓存装饰器，内存 dict + TTL 1h

**决策**：`repositories/caching.py` 用装饰器包 `SongRepository`，存储用自维护 dict + 时间戳过期。缓存 get_song / get_lyrics / get_lyric_at_time / search。不缓存 list_songs（分页命中率低）。

**理由**：装饰器模式对 Repository 无侵入，将来换 Redis 只需换装饰器实现。TTL 1h 平衡内存和新鲜度。

**替代方案**：lru_cache（参数有不可 hash 的）、Redis（新依赖，YAGNI）。

---

### ADR-009: 双模式部署，裸跑 + Podman 容器

**决策**：`python -m app.main` 裸跑，`podman compose up` 容器化。统一入口，容器只是套一层 Podman。sqlite 数据文件挂载 volume。

**理由**：本地开发用裸跑（快速迭代），作品集展示用容器（含金量高）。pydantic-settings + .env 统一配置注入。

**替代方案**：serverless（sqlite 不能持久化，需上 Redis/D1）、仅容器（本地开发慢）。

---

### ADR-010: 三层测试 + 80% 覆盖率

**决策**：pytest + pytest-asyncio + httpx + pytest-cov。单元（限流算法/鉴权/配置）、集成（端点 happy path + 错误路径）、冒烟（全链路）。侧重点：单元重算法正确性，集成重端点契约，冒烟重关键路径。

**理由**：三层覆盖不同风险面，80% 是工业常识门槛，作品集加分项。

**替代方案**：只做接口测试（覆盖率低）、不写测试（作品集减分）。

---

### ADR-011: 请求日志中间件，只记响应后一条

**决策**：middleware.py 在 post 阶段记一条日志（method / path / status / latency / key_id）。pre 阶段只记 start_time。key_id 从 `request.state.key_id` 取（鉴权 dependency 设置），401 时写 "anonymous"。

**理由**：减少日志量（不做"请求进入+响应"两条），key_id 脱敏。loguru 写 JSON 格式，容器友好。

**替代方案**：请求 + 响应两条日志（日志量大）、无 key_id 日志（可观测性弱）。

---

### ADR-012: 统一 JSON 错误格式

**决策**：`{"error": {"code": "NOT_FOUND", "message": "...", "detail": {...}}}`，错误码 UNAUTHORIZED / RATE_LIMITED / NOT_FOUND / VALIDATION_ERROR / INTERNAL_ERROR，HTTP 401/429/404/422/500 映射。

**理由**：统一格式是 REST API 基本功，客户端只需解析一种错误结构。

**替代方案**：默认 HTTPException（格式不统一）。

---

### ADR-013: 时间轴定位语义——最后 `time_sec <= t` 的行

**决策**：`get_lyric_at_time(t)` 将"当前行"定义为歌词中**最后一个 `time_sec <= t` 的行**。早于首行时取首 N 行，晚于末行时取末 N 行，边界处不补齐（返回行数可能少于 `2*context+1`）。

**理由**：卡拉OK 的真实播放语义是"正在唱的行"——即当前时间已经到达但尚未结束的那一行。`time_sec <= t` 正好表达"这一行已经开始播放"。边界处不补齐保持了行为可预测：如果在第一行之前，看到的是开头若干行；如果在最后一行之后，看到的是末尾若干行。

**替代方案**：
- `ABS(time_sec - t)` 取最近行（模拟意义不明——时间点落在两行中间时，最近行不是"正在唱的行"，也不是"将要唱的行"）。
- 对称补齐（边界处也保证返回 `2*context+1` 行，算法更复杂，且模拟不到真实的"首行之前无上行"体验）。

---

### ADR-014: auth/ratelimit 独立共享 sqlite 连接，不复用 Repository 连接

**决策**：`app/auth.py` 和 `app/ratelimit.py` 不通过 `SongRepository` 访问 `api_keys`/`rate_counters` 表，而是通过 `deps.py` 提供的共享 sqlite3 连接（singleton `get_db_conn`）直接读写。

**理由**：
- `SongRepository` 接口只暴露歌曲查询方法（get_song/list_songs/search/get_lyrics/get_lyric_at_time），若在其上加 raw 连接访问则泄漏抽象
- auth/ratelimit 是 API 网关关注点，与歌曲数据访问职责分离
- 除非将来把 auth 拆成独立服务，否则一个共享连接足够（只读+高频短查询，无写入竞争）

**替代方案**：
- 通过 `SongRepository` 暴露 raw connection（泄漏抽象，违反接口隔离）
- 每请求创建新连接（sqlite 连接开销虽小，1647 RPS 时仍有浪费）

---

### ADR-015: 响应包装对象而非裸数组

**决策**：所有返回多元素的端点使用包装对象：`LyricsResponse(song_id, lyrics, time_sec?, context?)`、`SearchResponse(query, scope, total, items)`、`SongsPage(items, total, page, size)`。单对象端点 `GET /songs/{id}` 返回 `Song`（裸对象）。

**理由**：
- 包装对象可扩展——未来加 metadata/分页字段无需破坏性变更
- 客户端解构一致（`data.items` vs `data`）
- OpenAPI schema 更清晰（`items: [...]` 有显式字段名而非数组作为根元素）
- `SongsPage` 已开创打包先例，同一接口风格保持内外一致

**替代方案**：
- 裸数组（简单但不可扩展，与已有 `SongsPage` 风格不一致）
- 全部返回裸对象（无元数据，且 `GET /songs` 已用 `SongsPage` 破坏了对称性）

---

### ADR-016: 构建时生成 db 烤入镜像

**决策**：Dockerfile 多阶段构建，builder 阶段跑 `import_songs.py` 生成 `data/lyrics.db`，final 阶段只拷贝 db 文件。镜像自包含，启动即用。

**理由**：
- 1647 首静态数据，更新频率极低，重新 build 成本可接受
- 开箱即用，用户无需手动导入数据（符合 ADR-005 单文件部署友好）
- `data/songs/*.json` 已在 git 中，构建时无需额外下载

**替代方案**：
- 挂载宿主机 volume（用户需手动导入，开箱体验差）
- 入口脚本启动时初始化（首次启动慢几秒，且需把 json 烤进镜像）

---

### ADR-017: 落地页挂载 StaticFiles 不鉴权

**决策**：`app.mount("/", StaticFiles(directory="app/static", html=True))` 放在所有路由注册后，`/` 返回落地页 HTML，不鉴权不限流。

**理由**：
- 落地页是公开介绍层，API 才需鉴权（符合 ADR-001 半开放定位）
- FastAPI 按注册顺序匹配，路由优先于 StaticFiles，不影响 `/healthz` `/api/v1/*` `/docs`
- 零依赖，FastAPI 内置支持

**替代方案**：
- 集成到 FastAPI 路由（需额外路由函数，不如 StaticFiles 简洁）
- 落地页也鉴权（违背"公开介绍"目的）

---

### ADR-018: CI 用 docker 不用 podman，无 CD

**决策**：GitHub Actions CI 工作流，三 job（lint → test ∥ build-smoke），lint 门禁。CI 用 `docker build` 而非 `podman`，不推容器 registry，无 CD（部署仍手动 `podman compose up`）。

**理由**：
- GHA ubuntu-latest runner 预装 docker，零配置；podman 需 `--storage-driver=vfs` 否则在 CI 下可能失败。Dockerfile 是标准多阶段 `python:3.12-slim`，两个引擎行为无差异
- 无 CD 是因为用户选择「仅 CI」——部署仍是手动 podman compose，保持部署方式正交
- 不推 GHCR：当前无需要，将来要推时加一个 job 即可
- 不矩阵多 Python 版本：项目锁定 3.12

**替代方案**：
- 用 podman build in CI（GHA podman 有 storage-driver 问题，需额外配置 vfs；收益为零——Dockerfile 相同）
- 推 GHCR + 自动部署（用户选择不做，YAGNI）
- 单 job 串行（无 lint 门禁，无并行，无单检查徽章）

---

### ADR-019: Metrics 用 prometheus_client，标签不放 key_id

**决策**：引入 `prometheus-client>=0.20` 作为唯一可观测性依赖。`/metrics` 端点以 FastAPI route 方式提供（`generate_latest()` + `CONTENT_TYPE_LATEST`），不鉴权不限流，受 `METRICS_ENABLED` 开关控制（默认 true）。标签策略：`path` 用路由模板（`/songs/{song_id}` 而非 `/songs/1`），不放 `key_id` 作 label。

**理由**：
- prometheus_client 零传递依赖（纯 Python ~50KB），de-facto 标准，作品集信号强
- 手写 exposition 格式有边界陷阱（`+Inf` 桶、`_total` 后缀、label 转义、exposition 顺序），flimsier
- 用 `request.scope["route"].path` 避免路径参数 ID 爆基数；不放 key_id 避免泄漏使用者身份（ADR-001 半开放定位）
- 不鉴权符合 Prometheus 抓取惯例，标签无 key_id 则无隐私风险
- `METRICS_ENABLED` 开关给部署方控制权，默认开

**替代方案**：
- 手写 /metrics（无依赖但 exposition 格式有边界陷阱，flimsier）
- `/metrics` 加鉴权（Prometheus 抓取需带 key，运维麻烦，违反惯例）
- 引入 OpenTelemetry（单服务过重，YAGNI）

**ponytail:** `make_asgi_app()` 的 ASGI lifespan 与 FastAPI mount 不兼容（prometheus_client 0.25），改用 `generate_latest()` + 内联 route。若未来 prometheus_client 修复 lifespan 兼容（发 PR 或新版），可改回 mount 方式。

---

### ADR-020: 压测用手写 httpx 异步脚本，不引入 locust/k6

**决策**：新增 `scripts/load_test.py`，基于 httpx + asyncio 手写 ~80 行异步发压脚本。不引入 locust、k6 或其他压测框架。

**理由**：
- locust 引入 gevent/flask 等传递依赖，与项目 asyncio 栈不兼容（需额外配置 gevent 模式），且单只读 API 用不到 web UI
- k6 是外部二进制，非 pip 管理，需额外安装步骤
- httpx 已在 `requirements-dev.txt` 中，`asyncio` 是 stdlib，零新增依赖
- 1647 首静态只读数据的压测场景简单，手写脚本完全覆盖（RPS/百分位/成功率）

**替代方案**：
- locust（传递依赖，asyncio 不兼容，YAGNI）
- k6（外部二进制，非 pip 管理）

**ponytail:** 压测脚本未使用 API key 鉴权，/api/v1 端点均为 401 未覆盖。压测前需先 seed 一个 key 并用 `--key <key>` 参数。

---

### ADR-021: 安全加固——响应头中间件 + 限流响应头 + 审计日志走 loguru

**决策**：

1. **安全响应头中间件**（`app/security_headers.py`）：手写中间件，不引 `secure` 库。对所有响应设 `X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy: strict-origin-when-cross-origin`；对 `/api/v1/*`、`/metrics`、`/healthz` 设 `Cache-Control: no-store`；对 `media_type="text/html"` 的落地页设 `Content-Security-Policy: default-src 'self'`；`Strict-Transport-Security` 受 `HSTS_ENABLED` 环境变量控制（默认 false）。
2. **限流响应头**：`ApiError` 基类加 `headers` 字段，`_as_json` 合并进 `JSONResponse`。`RateLimitedError` 设 `Retry-After` 头。`check_rate_limit` 接收 `Response` 参数，成功响应设 `X-RateLimit-Limit/Remaining/Reset` 三头。`retry_after_seconds` 算法修复为 `max(1, int(oldest + 60 - now) + 1)`（最早请求过期时间）。
3. **审计日志**：4 类事件（`auth_failure` / `rate_limited` / `key_issued` / `key_revoked`）走 loguru JSON stdout。不上 sqlite 表（零 schema 变更）。字段含 `key_id`、`ip`、`reason`、`path`、`request_id`，脚本事件省略 `ip`/`path`。
4. **CORS 完善**：`CORS_ORIGINS` 非空时，加 `expose_headers=["Retry-After","X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset"]` 和 `max_age=600`。移到 `register_middleware` 统一管理。
5. **Key 吊销脚本**：新增 `scripts/revoke_key.py`，手动吊销 key 并记审计日志。

**理由**：

- 安全响应头是生产就绪的基本要求，手写 ~20 行中间件够用，`secure` 库 YAGNI
- `Retry-After` 头是 HTTP 429 标准要求，`X-RateLimit-*` 三头是客户端友好实践
- 审计日志走 loguru 复用已有日志基础设施，sqlite 表增加复杂度且无查询需求（ADR-001 半开放作品集定位）
- 日志聚合系统（如 Loki、ELK）可采集 JSON stdout，不影响可查询性
- CORS `expose_headers` 让 JS 客户端能读到限流头

**替代方案**：

- 引入 `secure` 库管理安全头（新依赖，项目静态头用不到库的 CSP nonce/HSTS preload 等高级功能）
- 审计日志上 sqlite `audit_events` 表（动 schema.sql，增加 Repository 复杂度，违背「不引入 ORM」原则）
- 成功响应不设 `X-RateLimit-*` 头（客户端体验差，DevTools 看不到限流余量）

**ponytail:** `retry_after` 用 `MIN(request_at)` 而非 `OFFSET count - rpm` 查询第 N 旧请求。若 count >> rpm（突发大量请求），实际 retry_after 略大于计算值。60 RPM 下典型 burst ≤ 3，差异在 1-3s 内可接受。若需精确值，改为 `OFFSET count - rpm` 查询。

---

### ADR-022: 随机歌词 JS 模式采用 query 参数传 API key

**决策**：`/api/v1/random?format=js` 端点支持通过 `?key=<api_key>` query 参数传递 API key 作为鉴权方式，优先于 Bearer header 存在时使用 header。

**理由**：
- 浏览器 `<script src="...">` 标签无法发送自定义 HTTP 头（`Authorization: Bearer`），无法使用标准 Bearer 鉴权
- 若要求 JS 模式也走 Bearer，则只能通过 `fetch()` 获取 JS 字符串再手动注入，失去"直接可嵌入 `<script>` 标签"的便利性
- 应用层日志使用 `request.url.path`（不含 query string），`key` 参数不被记录；metrics label 也不含 key_id
- 反代层（nginx 等）的 access log 默认记录完整 URL，需部署方在 `log_format` 中对 `$args` 脱敏

**替代方案**：
- JS 端点公开免鉴权（简单但破坏安全模型，ADR-001 半开放定位）
- JS 端点也走 Bearer（只能用 fetch，无法 `<script src>` 嵌入）
- 单独一套 IP 限流无需鉴权的公开 JS 端点（复杂度增加，YAGNI）

**ponytail:** `?key=` 暴露在 URL 中，可能被浏览器历史、Referer 头、反代日志记录。应用层已做脱敏，反代层需部署方自行处理。若此风险不可接受，部署方可通过 `API_KEYS_ENABLED=true` 强制 Bearer 鉴权，放弃 JS 模式的 `<script src>` 嵌入能力。