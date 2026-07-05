# 阶段9：随机歌词

**日期：** 2026-07-05  &emsp; **关联 PRD：** [random-lyric](../prd/random-lyric.md)

## 目标

提供 `/api/v1/random` 端点，返回一句随机歌词。支持 JSON 和可嵌入 JS 两种响应模式，允许按歌手/作词人/版本/翻译/字符数范围筛选。

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/routers/random.py` | 随机歌词路由（`GET /random`，format=json|js，支持筛选与字符数约束） |
| `docs/prd/random-lyric.md` | PRD |
| `docs/features/phase-9.md` | 本阶段记录 |
| `tests/integration/test_random.py` | 随机歌词集成测试（19 个用例） |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/models.py` | 新增 `RandomLyricLine` 模型（text/translation/seq/time_sec/time_str/song） |
| `app/repositories/base.py` | `SongRepository` 新增 `get_random_line` 抽象方法 |
| `app/repositories/sqlite_repo.py` | 实现 `get_random_line`（`JOIN lyrics+songs + WHERE 过滤 + ORDER BY RANDOM() LIMIT 1`） |
| `app/repositories/caching.py` | 透传 `get_random_line`（不缓存） |
| `app/auth.py` | 抽取 `_authenticate` 核心函数；新增 `verify_api_key_flexible`（Bearer 头优先，回退 `?key=` query 参数） |
| `app/ratelimit.py` | 抽取 `_enforce_rate_limit` 核心函数（行为不变，供 random 端点和原 `check_rate_limit` 共用） |
| `app/routers/__init__.py` | 导出 `random` 模块 |
| `app/main.py` | 注册 `random.router` 到 `/api/v1` |
| `tests/unit/test_sqlite_repo.py` | 加 10 个 `get_random_line` 单元测试 |
| `tests/unit/test_auth.py` | 加 `TestAuthFlexible` 类（6 个 `verify_api_key_flexible` 用例） |
| `docs/api/README.md` | 通用约定补 JS 模式 query key 鉴权说明；接口清单加 random；新增完整 endpoint 章节；错误码表补 `missing_query_key`/`invalid_query_key` |
| `docs/arch/README.md` | 模块清单补 random.py；数据流图补 `/api/v1/random` 分支；追加 ADR-022（JS 模式 query key 鉴权的安全取舍） |
| `docs/db/README.md` | 访问模式表补 `lyrics`+`songs` 随机查询行；FTS5 说明补随机不走 FTS |
| `docs/deploy/README.md` | 可观测性段补 JS 模式 query key 反代脱敏说明 |
| `README.md` | API 端点表加 random；项目结构端点数 +1 |
| `RULES.md` | 代码规范补不缓存随机/query key 例外；禁止事项补不缓存/不扩展 query key/JS 转义；反模式补 ORDER BY RANDOM ceiling / query key 仅 JS；命名约定补 `get_random_line`、`RandomLyricLine` |
| `AGENTS.md` | 项目状态补阶段9；数据流图补 random 分支；关键约束补不缓存/JS key/target 转义/RANDOM ceiling |

## 核心实现

### Repository 层

`get_random_line` 方法通过 `JOIN lyrics + songs` 单条 SQL 实现：
```sql
SELECT l.*, s.* FROM lyrics l JOIN songs s ON l.song_id = s.id
WHERE <artist/writer/version/has_translation 过滤>
  AND length(l.text) BETWEEN ? AND ?
  AND l.text IS NOT NULL AND l.text != ''
ORDER BY RANDOM() LIMIT 1
```
- writer 复用 `lyricist/composer/arranger` 三个字段的 OR LIKE
- `has_translation=True` 时额外过滤 `l.translation IS NOT NULL`
- 不缓存，`CachingSongRepository` 直接透传

### 鉴权提取

`_authenticate(key_raw, conn, settings)` 从 `verify_api_key` 中抽取为独立函数，供两个 dependency 使用：
- `verify_api_key`（现有，仅 Bearer）— 行为不变
- `verify_api_key_flexible`（新增，Bearer → `?key=` 回退）— JS 模式专用

### 限流提取

`_enforce_rate_limit(response, key, conn)` 从 `check_rate_limit` 中抽取为独立函数：
- `check_rate_limit`（现有 FastAPI dependency）调用 `_enforce_rate_limit` — 行为不变
- random 端点直接调用 `_enforce_rate_limit`（因依赖链不同，不经过 `check_rate_limit`）

### Router

`GET /random` 端点参数：format/json|js、key、target、min_chars/max_chars、artist/writer/version/has_translation。JS 输出通过 `_escape_js` 做双重转义（JS 字符串 + HTML），`target` 选择器优先级：`?target=` → `window.LYRIC_TARGET` → 新建 `div`。

## 验证方式

- [x] ruff check — 通过
- [x] pytest --cov --cov-fail-under=80 — 153 passed, 94.60%
- [x] 集成测试覆盖：json/js/筛选/字符数/404/401/422/query key/限流头/Cache-Control/转义注入

## 已知限制

- `ORDER BY RANDOM()` 全表扫描，当前万级行可接受。若数据增长到百万级，需改为 `COUNT` + `OFFSET abs(random())%n`
- JS 模式 `?key=` query 参数在 URL 中传递，应用层日志已脱敏，但反代层 access log 可能记录完整 URL，部署方需自行脱敏
- 不支持 language/genre/era 筛选（schema 无这些字段，标记为 future scope）
- 不支持连续歌词片段模式（仅单行随机）
- `has_translation=True` 同时过滤 `l.translation IS NOT NULL`，即仅返回实际有翻译文本的行（而非仅来自有翻译歌曲的行）