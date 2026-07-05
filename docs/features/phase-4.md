# 阶段4：API 端点层

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/routers/health.py` | `GET /healthz` — 健康检查，不鉴权不限流，返回 `{"status":"ok","db":"ok"}` |
| `app/routers/songs.py` | `GET /api/v1/songs`（分页+过滤）+ `GET /api/v1/songs/{id}`（单首，404 if 缺） |
| `app/routers/lyrics.py` | `GET /api/v1/songs/{id}/lyrics`（全文/卡拉OK 双模式，`?time=` 切换） |
| `app/routers/search.py` | `GET /api/v1/search?q=&scope=` — FTS 统一搜索，scope 逗号分隔 |
| `app/main.py` | FastAPI 应用装配：middleware / exception_handler / CORS / routers / startup WARNING |
| `tests/integration/test_health.py` | 2 个测试：健康检查可用、不鉴权 |
| `tests/integration/test_songs.py` | 12 个测试：列表/过滤/分页/详情/404/401/422/吊销 |
| `tests/integration/test_lyrics.py` | 6 个测试：全文/卡拉OK/边界/404/401 |
| `tests/integration/test_search.py` | 8 个测试：默认/指定scope/无结果/空query/401 |
| `tests/smoke/test_smoke.py` | 1 个全链路冒烟：健康→列表→详情→歌词→卡拉OK→搜索 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/models.py` | 新增 `LyricsResponse`（含可选 karaoke 字段）和 `SearchResponse` |
| `app/routers/__init__.py` | 导出 4 个 router |
| `tests/conftest.py` | 新增 `test_app` fixture：create_app + dependency_overrides(repo + auth_db) |

## 技术决策

### 响应包装对象（ADR-015）

所有多元素返回端点使用包装对象，而非裸 JSON 数组：

| 端点 | 响应模型 |
|---|---|
| `GET /api/v1/songs` | `SongsPage`（items/total/page/size） |
| `GET /api/v1/songs/{id}` | `Song`（单对象，无需包装） |
| `GET /api/v1/songs/{id}/lyrics` | `LyricsResponse`（song_id + lyrics + 可选 time_sec/context） |
| `GET /api/v1/search` | `SearchResponse`（query + scope + total + items） |

### 歌词端点双模式合并

`GET /api/v1/songs/{id}/lyrics?time=<sec>&context=<n>` 同时覆盖两种场景：
- `?time=` 缺失 → 返回完整歌词（`LyricsResponse`，不含 time_sec/context）
- `?time=` 存在 → 卡拉OK 模式，返回当前行 ± 前后各行（`LyricsResponse` 含 time_sec/context）

合并为单一端点而非两个独立路由，减少路由表噪声，URL 语义自然。

### 搜索不分页

`search()` 返回 `list[Song]`，`SearchResponse.items` 直接承载。1647 首规模下搜索命中通常较少，分页徒增复杂度。后续若需要可加。

### 鉴权/限流挂载

- `/healthz`：不挂任何 dependency（ADR-004）
- `/api/v1/*`：APIRouter 级 `dependencies=[Depends(check_rate_limit)]`，内部已含 `verify_api_key`
- 这意味着无需在每个端点单独加 `Depends`，新建路由自动继承

### CORS 条件挂载

`CORS_ORIGINS` 环境变量为空时（默认）不挂 `CORSMiddleware`，为零配置场景减少意外暴露。非空时按逗号分割配置。

## 验证结果

| 项 | 结果 |
|---|---|
| ruff check | 通过 |
| pytest --cov --cov-fail-under=80 | 93 passed, 97.55% 覆盖率 |
| /healthz | 200 + `{"status":"ok","db":"ok"}` |
| GET /api/v1/songs | 200 + `SongsPage(total=3)` |
| GET /api/v1/songs?title= | 过滤正确 |
| GET /api/v1/songs/999 | 404 + `NOT_FOUND` |
| GET /api/v1/songs/1/lyrics?time=7.5 | 200 + 3 行歌词（seq 0,1,2） |
| GET /api/v1/songs/1/lyrics?time=-1 | 200 + 首 3 行（边界） |
| GET /api/v1/search?q=暗里着迷&scope=lyrics | 200 + 2 条结果 |
| 401 无 header / 无效 key / 吊销 key | 401 + `UNAUTHORIZED` + 正确 reason |
| 422 page=0 / size=0 | 422 + `VALIDATION_ERROR` |

## 已知限制

- `deps.py` 的 `get_db_conn` 和 `get_repository` 是全局 singleton，在集成测试中被 `dependency_overrides` 替换，其默认实现（创建真实连接）未被测试覆盖（同阶段3）
- `main.py` 的 `if __name__ == "__main__"` 块（uvicorn.run）在 pytest 中不可测，为正常主入口行为
- CORS 条件分支和 is_insecure WARNING 在默认配置下不被测试覆盖，需设置特定环境变量才触发（由 `test_config.py` 在 config 层验证）
- `static/` 落地页和容器化部署留在阶段5