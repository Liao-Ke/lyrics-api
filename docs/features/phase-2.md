# 阶段2：数据访问层（Repository）

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/models.py` | Pydantic 响应模型：Song / LyricLine / SongWithLyrics / SongsPage |
| `app/repositories/base.py` | SongRepository ABC：5 个只读接口方法 |
| `app/repositories/sqlite_repo.py` | SqliteSongRepository：sqlite3 实现，FTS5 trigram 锁内部 |
| `tests/conftest.py` | tmp_repo fixture：3 首样本数据临时 db |
| `tests/unit/test_sqlite_repo.py` | 26 个单元测试，覆盖所有方法 × happy path + 边界 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/repositories/__init__.py` | 导出 SongRepository + SqliteSongRepository |

## 技术决策

### 接口设计
- **`search(query, scope)`** — `scope: list[str] | None`，`None`=全部 4 个维度。内部 UNION 子查询，FTS5 只跑 `lyrics` scope，其余走 SQL LIKE。短查询（<3 字符）FTS5 trigram 无法匹配，自动降级为 `lyrics.text LIKE`。
- **`get_lyric_at_time(time_sec)`** — "当前行"定义为最后一个 `time_sec <= t` 的行（卡拉OK 语义）。早于首行→返回首 N 行，晚于末行→返回末 N 行。边界处返回的行数可能少于 `2*context+1`。
- **`list_songs` 过滤** — title/artist/writer 参数自动包 `%` 做 LIKE 模糊匹配。writer 同时查 lyricist/composer/arranger。
- **分页** — `page`/`size`，默认 size=20，max=100。page 和 size 均 clamp 到合法范围。
- **行映射** — 显式 `_row_to_song` / `_row_to_lyric` 静态方法，不依赖 pydantic 泛化 dict 转换（避免 extra 字段传入）。

### 连接管理
- `check_same_thread=False` — FastAPI 同步端点在线程池中调用，sqlite3 默认不允许跨线程使用同一连接。
- `row_factory = sqlite3.Row` — 列名访问。
- 单连接复用（Singleton connection per repo instance）— 1647 首只读，无并发写入，单连接池化无必要。

### 测试策略
- **Fixture db** — 用 3 首硬编码样本创建临时 `.db` 文件，运行完整 SQL schema，INSERT 后重建 FTS5 索引。不依赖真实 `data/lyrics.db`，跑得快、可重现、无副产物。
- **不写集成/冒烟** — Repository 是纯逻辑层，单元测试已覆盖 100%。

## 验证结果

| 项 | 结果 |
|---|---|
| ruff check | 通过 |
| pytest (--cov --cov-fail-under=80) | 33 passed, 100% 覆盖率 |
| test_get_song(1).title | "测试A" |
| test_list_songs_filter_artist("艺术家1") | total=2（song 1, 2） |
| test_search_all("暗里着迷") | 2 hits（FTS：song 1, 3） |
| test_search_short("第三", scope=["lyrics"]) | 1 hit（LIKE 兜底：song 1） |
| test_get_lyric_at_time(1, 7.5) | [seq 0, 1, 2]（3 rows） |
| test_get_lyric_at_time(1, -1) | [seq 0, 1, 2]（早于首行回退） |

## 已知限制

- FTS5 trigram 仅对 3+ 字符生效。短查询（1-2 字符）降级为 `text LIKE`，不参与 FTS5 排名。
- `SongWithLyrics` 模型已定义但 `SqliteSongRepository` 未暴露 `get_song_with_lyrics` 方法——留给路由层组合 `get_song` + `get_lyrics`。
- `get_lyric_at_time` 边界处返回行数可能少于 `2*context+1`（首行或末行时），未做对称补齐。