# RULES

## 技术栈约束

- **框架**：FastAPI + pydantic-settings + loguru + sqlite3 标准库。不引入 ORM（SQLModel/SQLAlchemy）、不引入 Redis（缓存用内存 dict + TTL 1h）
- **测试**：pytest + pytest-asyncio + httpx + pytest-cov，三层测试（unit/integration/smoke），覆盖率门槛 ≥ 80%
- **代码检查**：`ruff check .`，零 warning 通过
- **部署**：Podman 容器（非 Docker），支持裸跑 `python -m app.main`
- **Python 运行时**：`/home/Lsk/miniconda3/bin/python`
- **包管理**：pip，依赖写 `requirements.txt`，不引入 `pyproject.toml` 以外的构建工具
- **安全响应头手写中间件**，不引 `secure` 库
- **审计日志走 loguru JSON stdout**，不上 sqlite 表

## 代码规范

- **schema.sql 手动管理**，不上 alembic 或其他迁移工具。schema.sql 是真相源
- **Repository ABC 抽象**：`SongRepository` 定义只读接口，`SqliteSongRepository` 实现。FTS5 trigram 搜索实现锁在 `SqliteSongRepository` 内部，接口只暴露 `search(query, scope)`。随机查询用 `get_random_line` 方法（`ORDER BY RANDOM()` + `length()` 过滤），不缓存结果
- **三层测试**：单元测试重算法正确性，集成测试重端点契约，冒烟测试重关键路径
- **配置安全**：`API_KEYS_ENABLED=false` 且 `HOST` 非 localhost 时，启动必须打 WARNING 日志
- **限流是滑动窗口**（`rate_counters` 存每请求时间戳），作为 FastAPI dependency 而非中间件，`/healthz` 不走限流
- **统一错误格式**：`{"error": {"code": "...", "message": "...", "detail": {...}}}`，错误码大写蛇形
- **响应包装**：多元素端点用 `XxxResponse` / `XxxPage` 包装对象，单对象端点返回裸模型
- **Auth 只支持 `Authorization: Bearer`**，HTTPBearer 的 auto_error 必须设为 False + 手动 401（避免 FastAPI 默认返回 HTML）。`/api/v1/random?format=js` 是受控例外：额外支持 `?key=` query 参数鉴权（浏览器 `<script>` 标签无法发 Bearer 头），通过 `verify_api_key_flexible` 依赖实现

## 禁止事项

- **不要引入 ORM**。1647 首静态只读数据，ORM 的 session/relationship 是过度设计
- **不要引入 Redis 或其他外部缓存**。内存 dict + TTL 1h 够用，将来换 Redis 只需换 `caching.py` 装饰器实现
- **不要缓存随机结果**。随机查询每次应返回不同结果，`CachingSongRepository` 直接透传 `get_random_line`
- **不要用固定窗口限流**。固定窗口有边界突刺（59s 和 61s 各 60 次，实际 1s 内 120 次），滑动窗口无此问题
- **不要把限流做成中间件**。`/healthz` 不该被限流（容器探针高频调用），dependency 方式每端点可选不同策略
- **不要返回裸数组**。包装对象可扩展，客户端解构一致，OpenAPI schema 更清晰
- **不要通过 Repository 暴露 raw sqlite connection**。auth/ratelimit 读写 `api_keys`/`rate_counters` 表走 `deps.py` 提供的独立共享连接，不污染 Repository 抽象
- **不要把 `/healthz` 和落地页（`/`）加鉴权/限流**。`/healthz` 是容器探针，落地页是公开介绍，API 才需鉴权
- **不要在 1-2 字查询上依赖 FTS5 trigram**。trigram 对 3 字以下无匹配，短查询降级为 `text LIKE`
- **CI 用 docker 不用 podman**。GHA ubuntu-latest 预装 docker 零配置；podman 需 `--storage-driver=vfs` 避免非交互环境下存储驱动失败。Dockerfile 标准，二者构建无差异
- **lint 必须 gate test/build**。job 间设 `needs: lint`，lint 失败则 test/build 不执行。不并行跑 ruff 和 pytest（lint ~15s，失败后浪费 test 分钟）
- **不矩阵多 Python 版本**。项目锁定 python:3.12-slim，矩阵增加 CI 耗时和构建复杂度，无实际收益
- **不引入 codecov 上传**。`pytest --cov --cov-fail-under=80` 本地门槛足够。codecov 增加第三方依赖和 CI 步骤，非开源社区项目不需要 coverage 看板
- **metrics label 不放 key_id**。基数爆炸 + 泄漏使用者身份，违反 ADR-001 半开放定位
- **path 指标用路由模板，不用 url.path**。`request.scope["route"].path` 返回 `/songs/{song_id}`，`request.url.path` 返回 `/songs/1`，后者的 ID 导致基数爆炸
- **不引入 locust / k6 做压测**。手写 httpx 异步脚本够用，locust 引入 gevent/flask 等传递依赖，单只读 API 用不到 web UI
- **不要把审计日志写进 sqlite 表**。审计走 loguru JSON stdout（ADR-021），日志聚合系统采集
- **不要在 JSON 响应上设 CSP**。CSP 仅对 `media_type="text/html"` 的落地页有效
- **不要让 HSTS 默认开启**。HSTS 需反代 TLS 场景，默认 false，通过 `HSTS_ENABLED` 环境变量控制
- **429 必须设 `Retry-After` 头**，`retry_after_seconds` = 最早请求过期时间（`oldest + 60 - now`），非窗口长度
- **成功 `/api/v1/*` 响应必须设 `X-RateLimit-Limit/Remaining/Reset`** 三头
- **不要把 query key 鉴权扩展到非 JS 端点**。`?key=` query 鉴权仅限 `/api/v1/random?format=js`，其他端点必须走 Bearer 头
- **不要在 JS 输出中嵌入未转义的 `target` 或歌词文本**。`target` 来自不可信 query 参数，歌词文本来自数据库，嵌入 JS 字符串前必须做 `\`/`'`/`</`/换行转义

## 反模式记录

### 不要让 HTTPBearer auto_error=True

- **为什么**：FastAPI 默认 `auto_error=True` 时，无 `Authorization` 头会直接返回 HTML 响应，不符合 ADR-012 统一 JSON 错误格式
- **正确做法**：`HTTPBearer(auto_error=False)`，在 dependency 中手动检查 `credentials is None`，抛 `ApiUnauthorized`

### 不要依赖 seed_key.py 提供吊销/列表功能

- **为什么**：`seed_key.py` 仅生成新 key，不提供吊销或列表功能
- **正确做法**：产品使用时通过 `sqlite3 lyrics.db "UPDATE api_keys SET revoked_at=datetime('now') WHERE key_id=?"` 手动吊销，或另写管理脚本

### 不要假设 deps.py 的 singleton 默认实现可测

- **为什么**：`deps.py` 的 `get_db_conn` 和 `get_repository` 是全局模块级 singleton，单元测试中通过 `dependency_overrides` 替换，其默认实现未被测试覆盖
- **正确做法**：集成测试和冒烟测试中覆盖默认实现路径

### 不要假设 group_key 去重绝对唯一

- **为什么**：group_key 去重仅处理 `|2`/`|3` 后缀，极端情况下 3+ 重复可能出现 `|3`/`|4`
- **正确做法**：接受当前去重粒度，遇到极端情况时增加后缀处理

### 不要在 FTS5 trigram 上跑 1-2 字查询

- **为什么**：`tokenize='trigram'` 仅对 3+ 字查询有效，2 字如"爱你"无匹配
- **正确做法**：短查询降级为 `text LIKE`，不参与 FTS5 排名

### 不要手写 Prometheus exposition format

- **为什么**：Prometheus 文本格式有多个边界情况：`+Inf` 桶在 histogram 中必须正确输出、`_total` 后缀对于 Counter 类型、label 值的转义规则（`\` `\n` `"`）、exposition 顺序（HELP 行必须在 TYPE 行之前）、样本行格式。手写 ~80 行代码容易遗漏这些边界
- **正确做法**：使用 `prometheus_client` 库的 `generate_latest()` 或 `make_asgi_app()`，它们是标准实现

### 不要在 CI 里跑 load_test（除非有强理由）

- **为什么**：load_test 执行耗时（30s-60s）且结果受 runner 性能影响，不适合作为 CI 门禁。CI 只验证 build 正确性
- **正确做法**：load_test 在本地或预发布环境按需运行，基线结果写入 `docs/perf/`

### 不要用 `int(now - window_start)` 算 retry_after

- **为什么**：`now - window_start = now - (now - 60) = 60`，恒等于窗口长度，不反映实际最早请求过期时间
- **正确做法**：`retry_after = max(1, int(oldest + 60 - now) + 1)`，其中 `oldest = MIN(request_at)` 在窗口内

### 不要依赖 ORDER BY RANDOM() 在百万级表上

- **为什么**：`ORDER BY RANDOM() LIMIT 1` 在 SQLite 中会全表扫描，对当前万级行歌词表可接受，但扩展到百万级时性能不可接受
- **正确做法**：当前万级可接受（ponytail: 加注释标注 ceiling）。升级路径：先 `COUNT` 符合条件的行数 N，再 `OFFSET abs(random()) % N` 取一行

### 不要把 JS 模式 query key 鉴权扩展到其他端点

- **为什么**：`?key=` 在 URL 中暴露，应用层日志已脱敏，但反代层可能记录。仅在 `<script>` 标签无法发送 Bearer 头的场景下使用
- **正确做法**：仅 `/api/v1/random?format=js` 使用 `verify_api_key_flexible`，其他端点保持 Bearer-only

### 不要用 podman 跑 CI 构建（除非有强理由）

- **为什么**：GHA ubuntu-latest runner 预装 podman，但非交互环境下 `podman build` 默认存储驱动（overlay）可能因权限限制失败，需 `--storage-driver=vfs` 才能稳定运行。而 docker 预装且零配置。Dockerfile 为标准多阶段 `FROM python:3.12-slim`，docker 和 podman 行为无差异
- **正确做法**：CI 中统一用 `docker build`；部署时本地仍用 `podman compose up`（ADR-009 双模式部署）

## 命名约定

- **端点版本化**：所有 API 端点以 `/api/v1/` 开头
- **错误码**：大写蛇形——`UNAUTHORIZED` / `RATE_LIMITED` / `NOT_FOUND` / `VALIDATION_ERROR` / `INTERNAL_ERROR`
- **Repository 方法**：`get_song`、`list_songs`、`search`、`get_lyrics`、`get_lyric_at_time`、`get_random_line`
- **响应模型**：多元素端点用 `XxxResponse`（如 `LyricsResponse`、`SearchResponse`）或 `XxxPage`（如 `SongsPage`），单对象端点返回裸模型（如 `Song`、`RandomLyricLine`）
- **日志 key_id**：鉴权通过时写实际 key_id，401 未鉴权时写 `"anonymous"`
- **测试文件**：`tests/unit/`、`tests/integration/`、`tests/smoke/` 三层目录，文件名 `test_<模块>.py`

## 文档约定

- **ADR 持续追加**：`docs/arch/README.md` 中的设计决策按序号追加，不删除已有条目，可标注「已过时」
- **功能记录**：`docs/features/phase-*.md` 按阶段记录，每次实现完成后更新
- **RULES 持续追加**：踩坑后追加反模式，不删除历史规则，可标注「已过时」。规则与 AGENTS.md 互不重复——AGENTS.md 记项目特有上下文，RULES.md 记编码规则
- **schema.sql 是真相源**：`docs/db/` 中的数据库设计文档为补充说明，不替代 schema.sql