# 架构描述：歌词API

## 模块职责

```
app/
├── main.py          # FastAPI 入口，路由注册，startup 初始化
├── config.py        # pydantic-settings 配置加载 + 安全 WARNING
├── deps.py          # 依赖注入链编排（repo / key / rate_limit）
├── errors.py        # 自定义异常 + @app.exception_handler 统一 JSON 错误
├── logging.py       # loguru 配置
├── middleware.py     # 请求日志中间件（method / path / status / latency / key_id）
├── auth.py          # API key 鉴权 dependency（verify_api_key）
├── ratelimit.py     # 滑动窗口限流 dependency（check_rate_limit）
├── models.py        # Pydantic 请求/响应模型
├── routers/         # 端点路由
│   ├── songs.py     # /api/v1/songs /api/v1/songs/{id}
│   ├── search.py    # /api/v1/search
│   ├── lyrics.py    # /api/v1/songs/{id}/lyrics?time=
│   └── health.py    # /healthz
├── repositories/    # 数据访问层
│   ├── base.py      # SongRepository ABC 抽象基类
│   ├── sqlite_repo.py  # SqliteSongRepository 实现（FTS5 锁内部）
│   └── caching.py   # 缓存装饰器（dict + TTL 1h）
└── static/          # 落地页 index.html
```

## 数据流

```
HTTP 请求 → 中间件（日志 pre）
→ FastAPI 路由匹配
→ Depends(verify_api_key) [鉴权]
→ Depends(check_rate_limit) [限流，/healthz 除外]
→ 路由端点
→ Depends(get_repository) [缓存装饰器 → SqliteSongRepository → sqlite3]
→ Pydantic 序列化响应
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