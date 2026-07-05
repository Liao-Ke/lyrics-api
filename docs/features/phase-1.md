# 阶段1：配置 + 日志 + 数据导入

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `app/config.py` | pydantic-settings 配置加载 |
| `app/logging.py` | loguru JSON 日志配置 |
| `scripts/import_songs.py` | 将 `data/songs/*.json` 导入 SQLite |
| `tests/unit/test_config.py` | config 加载、env 覆盖、is_insecure 单元测试 |
| `docs/db/README.md` | 数据库设计文档 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `scripts/clean_lrc.py` | 移除 3 个未使用的 import（ruff lint 修复） |

### 新增数据

| 文件 | 说明 |
|---|---|
| `data/lyrics.db` | SQLite 数据库（.gitignore 排除，不提交） |

## 技术决策

- **配置**：pydantic-settings v2 + `SettingsConfigDict(env_file='.env')`，无前缀
- **日志**：loguru `serialize=True` 输出 JSON 到 stdout，容器友好（ADR-011）
- **导入脚本**：离线运行，os.environ.get 覆盖路径，不引入 `app.config` 依赖（与 clean_lrc.py 风格一致）
- **幂等**：`DROP TABLE IF EXISTS` 后重建，每次运行产生干净数据库
- **group_key 重复**：同名同艺术家不同 LRC 文件（9 对），导入时加 `|2`/`|3` 后缀去重
- **FTS 维护**：全部数据 INSERT 后 `INSERT INTO lyrics_fts(lyrics_fts) VALUES('rebuild')` 一次重建

## 验证结果

| 项 | 结果 |
|---|---|
| songs 行数 | 1647 |
| lyrics 行数 | 71294 |
| FTS 行数 | 71294（与 lyrics 一致） |
| FTS 搜索 `暗里着迷` | 4 行命中 |
| FTS 搜索 `在一起` | 176 行命中 |
| 导入耗时 | 0.92s |
| ruff check | 通过 |
| pytest (--cov --cov-fail-under=80) | 5 passed, 100% 覆盖率 |

## 已知限制

- `tokenize='trigram'` 仅对 3+ 字查询有效（2 字如"爱你"无匹配），属于 FTS5 trigram 分词器行为
- group_key 去重仅处理 `|2`/`|3` 后缀，不保证绝对唯一（极端情况下 3+ 重复可能需要 `|3`/`|4`）