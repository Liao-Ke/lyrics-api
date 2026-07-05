# 阶段3：HTTP 交叉基础设施层

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/errors.py` | 5 个 ApiError 子类 + `register_exception_handlers(app)` 统一 JSON 错误处理 |
| `app/repositories/caching.py` | `CachingSongRepository` 装饰器，dict + TTL 1h 缓存（ADR-008） |
| `app/auth.py` | `verify_api_key` dependency，sha256 比对 api_keys 表（ADR-002） |
| `app/ratelimit.py` | `check_rate_limit` dependency，滑动窗口 INSERT→DELETE→COUNT（ADR-003/004） |
| `app/middleware.py` | `register_middleware`，post 阶段记录 method/path/status/latency/key_id（ADR-011） |
| `app/deps.py` | `get_db_path` / `get_db_conn`(singleton) / `get_repository`(CachingSongRepository 包装) |
| `scripts/seed_key.py` | 生成 API key 并写入 api_keys 表 |
| `tests/unit/test_errors.py` | 9 个测试：5 错误码 × shape + HTTPException 兜底 + RequestValidationError 包装 |
| `tests/unit/test_caching.py` | 9 个测试：命中/未命中/TTL 过期/list_songs 旁路/search/lyrics 缓存 |
| `tests/unit/test_auth.py` | 5 个测试：缺 header/无效/已吊销/有效/关闭鉴权 |
| `tests/unit/test_ratelimit.py` | 4 个测试：限内/超限 429/匿名绕过/per-key 隔离 |
| `tests/unit/test_middleware.py` | 2 个测试：透传不损坏/日志输出 |
| `docs/api/README.md` | 错误响应契约文档 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `tests/conftest.py` | 新增 `auth_db` / `auth_conn` fixture（api_keys 表预填） |
| `app/repositories/__init__.py` | 导出 `CachingSongRepository` |
| `docs/arch/README.md` | 新增 ADR-014（auth/ratelimit 独立共享连接） |
| `docs/db/README.md` | 新增 api_keys/rate_counters 访问模式小节 |

## 技术决策

### 连接策略（ADR-014）
- auth/ratelimit 通过 `deps.get_db_conn`（singleton sqlite3 连接）直接访问 `api_keys`/`rate_counters` 表，不经过 `SongRepository` 接口
- Repository 保持纯歌曲数据接口，不泄漏 raw connection

### auth 设计
- `verify_api_key` 返回 `KeyContext(key_id, rate_limit_rpm)` dataclass
- `API_KEYS_ENABLED=false` 时返回匿名上下文（`key_id="anonymous"`, `rate_limit_rpm=0`），不限流
- 请求在 `request.state.key_id` 写入 key_id 供中间件日志使用

### ratelimit 设计
- 滑动窗口：DELETE 过期 → INSERT 当前 → COUNT 窗口内 → 超限 429
- 匿名 key（非 API_KEYS_ENABLED 模式）直接跳过限流
- 每请求在 `rate_counters` 插入一条记录，超限时也插入（60s 后自动清出窗口）

### 错误处理
- ApiError 基类 + 5 个子类（NotFoundError / UnauthorizedError / RateLimitedError / ValidationError / InternalError）
- `register_exception_handlers` 在 aplicación startup 时注入，统一处理 ApiError、RequestValidationError、HTTPException
- 错误响应格式：`{"error": {"code", "message", "detail"}}`

### 缓存
- `CachingSongRepository` 包装 `SongRepository`，使用 `time.monotonic()` 做 TTL 判断
- 缓存：get_song / get_lyrics / get_lyric_at_time / search（参数相关key）
- 旁路：list_songs（分页命中率低）
- 测试通过 id 互等判断缓存命中（不依赖 deep equality）

### 测试策略
- 所有新模块通过 TestClient + dependency_overrides 测试
- auth/ratelimit 测试使用独立 `auth_db` fixture（临时 sqlite 文件，含预填 api_keys）
- 环境变量隔离：`RATE_LIMIT_RPM` 在测试中以 per-key 值而非 settings 为准

## 验证结果

| 项 | 结果 |
|---|---|
| ruff check | 通过 |
| pytest --cov --cov-fail-under=80 | 63 passed, 97.51% 覆盖率 |
| 错误响应格式 | 5 错误码 × 正确 JSON shape + HTTPException/RequestValidationError 兜底 |
| 缓存命中 | get_song / get_lyrics / search 缓存命中返回同一对象 |
| 缓存 TTL | TTL=0 时第二次访问重新计算 |
| 缓存在旁路 | list_songs 两次调用返回不同对象 |
| auth 活跃 key | key_id="active", rpm=60 |
| auth 无效/吊销 | 401 + reason: invalid_key |
| auth 关闭鉴权 | 200 + key_id="anonymous" |
| ratelimit 超限 | RPM=1 时第 2 次请求 429 + RATE_LIMITED 码 |
| ratelimit per-key | 不同 key 互不影响 |
| ratelimit 匿名 bypass | 10 次连续请求全部 200 |

## 已知限制

- `deps.py` 的 `get_db_conn` 和 `get_repository` 是全局 singleton（模块级变量），在单测中被 `dependency_overrides` 替换，但单元测试未覆盖其默认实现。集成/冒烟测试（阶段4+）会覆盖。
- `rate_counters` 表中 rejected 请求也会插入一行（超限也计为 1 次）。这是滑动窗口的标准行为——超限请求 60s 后自动移出窗口，不做额外清理。
- auth 中间件依赖 `Authorization: Bearer` 格式，不支持其他 scheme。HTTPBearer 的 auto_error=False 行为需要手动 401（FastAPI 默认 auto_error=True 会直接返回 HTML，不符合 ADR-012 统一 JSON 格式）。
- `seed_key.py` 仅生成新 key，不提供吊销/列表功能。产品使用时需手动 `sqlite3 lyrics.db "UPDATE api_keys SET revoked_at=datetime('now') WHERE key_id=?"`。