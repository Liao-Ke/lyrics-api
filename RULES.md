# RULES

## 技术栈约束

- **框架**：FastAPI + pydantic-settings + loguru + sqlite3 标准库。不引入 ORM（SQLModel/SQLAlchemy）、不引入 Redis（缓存用内存 dict + TTL 1h）
- **测试**：pytest + pytest-asyncio + httpx + pytest-cov，三层测试（unit/integration/smoke），覆盖率门槛 ≥ 80%
- **代码检查**：`ruff check .`，零 warning 通过
- **部署**：Podman 容器（非 Docker），支持裸跑 `python -m app.main`
- **Python 运行时**：`/home/Lsk/miniconda3/bin/python`
- **包管理**：pip，依赖写 `requirements.txt`，不引入 `pyproject.toml` 以外的构建工具

## 代码规范

- **schema.sql 手动管理**，不上 alembic 或其他迁移工具。schema.sql 是真相源
- **Repository ABC 抽象**：`SongRepository` 定义只读接口，`SqliteSongRepository` 实现。FTS5 trigram 搜索实现锁在 `SqliteSongRepository` 内部，接口只暴露 `search(query, scope)`
- **三层测试**：单元测试重算法正确性，集成测试重端点契约，冒烟测试重关键路径
- **配置安全**：`API_KEYS_ENABLED=false` 且 `HOST` 非 localhost 时，启动必须打 WARNING 日志
- **限流是滑动窗口**（`rate_counters` 存每请求时间戳），作为 FastAPI dependency 而非中间件，`/healthz` 不走限流
- **统一错误格式**：`{"error": {"code": "...", "message": "...", "detail": {...}}}`，错误码大写蛇形
- **响应包装**：多元素端点用 `XxxResponse` / `XxxPage` 包装对象，单对象端点返回裸模型
- **Auth 只支持 `Authorization: Bearer`**，HTTPBearer 的 auto_error 必须设为 False + 手动 401（避免 FastAPI 默认返回 HTML）

## 禁止事项

- **不要引入 ORM**。1647 首静态只读数据，ORM 的 session/relationship 是过度设计
- **不要引入 Redis 或其他外部缓存**。内存 dict + TTL 1h 够用，将来换 Redis 只需换 `caching.py` 装饰器实现
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

### 不要用 podman 跑 CI 构建（除非有强理由）

- **为什么**：GHA ubuntu-latest runner 预装 podman，但非交互环境下 `podman build` 默认存储驱动（overlay）可能因权限限制失败，需 `--storage-driver=vfs` 才能稳定运行。而 docker 预装且零配置。Dockerfile 为标准多阶段 `FROM python:3.12-slim`，docker 和 podman 行为无差异
- **正确做法**：CI 中统一用 `docker build`；部署时本地仍用 `podman compose up`（ADR-009 双模式部署）

## 命名约定

- **端点版本化**：所有 API 端点以 `/api/v1/` 开头
- **错误码**：大写蛇形——`UNAUTHORIZED` / `RATE_LIMITED` / `NOT_FOUND` / `VALIDATION_ERROR` / `INTERNAL_ERROR`
- **Repository 方法**：`get_song`、`list_songs`、`search`、`get_lyrics`、`get_lyric_at_time`
- **响应模型**：多元素端点用 `XxxResponse`（如 `LyricsResponse`、`SearchResponse`）或 `XxxPage`（如 `SongsPage`），单对象端点返回裸模型（如 `Song`）
- **日志 key_id**：鉴权通过时写实际 key_id，401 未鉴权时写 `"anonymous"`
- **测试文件**：`tests/unit/`、`tests/integration/`、`tests/smoke/` 三层目录，文件名 `test_<模块>.py`

## 文档约定

- **ADR 持续追加**：`docs/arch/README.md` 中的设计决策按序号追加，不删除已有条目，可标注「已过时」
- **功能记录**：`docs/features/phase-*.md` 按阶段记录，每次实现完成后更新
- **RULES 持续追加**：踩坑后追加反模式，不删除历史规则，可标注「已过时」。规则与 AGENTS.md 互不重复——AGENTS.md 记项目特有上下文，RULES.md 记编码规则
- **schema.sql 是真相源**：`docs/db/` 中的数据库设计文档为补充说明，不替代 schema.sql