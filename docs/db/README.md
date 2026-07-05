# 数据库设计

单文件 SQLite (`lyrics.db`)，FTS5 trigram 全文索引。静态只读数据，由 `scripts/import_songs.py` 从 `data/songs/*.json` 导入。

## 表结构

### songs

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| title | TEXT | 清洗后标题（去括号版本信息） |
| title_raw | TEXT | 原始标题 |
| version | TEXT | 版本（如 Live, Demo），可 null |
| artist | TEXT | 艺术家 |
| group_key | TEXT UNIQUE | 去重键 `normalize(title)\|normalize(artist)`，同名同艺术家歌曲加 `\|N` 后缀 |
| lyricist | TEXT | 作词人 |
| composer | TEXT | 作曲人 |
| arranger | TEXT | 编曲人 |
| has_translation | INTEGER | 是否有翻译（0/1） |
| source_file | TEXT | 原始 LRC 文件名 |
| json_file | TEXT | 对应 JSON 文件名 |

### lyrics

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| song_id | INTEGER FK | 关联 `songs.id`，ON DELETE CASCADE |
| time_sec | REAL | 时间戳（秒） |
| time_str | TEXT | 原始时间串（如 `00:32.030`） |
| text | TEXT | 歌词正文 |
| translation | TEXT | 翻译（英译中/中译英等），可 null |
| seq | INTEGER | 行序号，同首歌内唯一 |

UNIQUE(song_id, seq)

### api_keys

| 列 | 类型 | 说明 |
|---|---|---|
| key_id | TEXT PK | API key 标识 |
| key_hash | TEXT | key 哈希（sha256） |
| name | TEXT | 使用者说明 |
| created_at | TEXT | 创建时间 ISO-8601 |
| revoked_at | TEXT | 吊销时间，null 表示活跃 |
| rate_limit_rpm | INTEGER | 该 key 的 RPM 上限，默认 60 |

### rate_counters

滑动窗口限流记录。

| 列 | 类型 | 说明 |
|---|---|---|
| key_id | TEXT PK/FK | 关联 `api_keys.key_id`，ON DELETE CASCADE |
| request_at | REAL | 请求时间戳（秒） |

PRIMARY KEY (key_id, request_at) — 单调插入，无需额外去重。

索引：`idx_rate_counters_key_time(key_id, request_at)` — 窗口计数查询。

### lyrics_fts（FTS5 虚拟表）

```sql
CREATE VIRTUAL TABLE lyrics_fts USING fts5(
  text,
  content=lyrics,
  content_rowid=id,
  tokenize='trigram'
);
```

- **外部内容表**：`content=lyrics`，FTS5 查询时从 `lyrics` 表读取未索引列
- **trigram 分词**：3 字符滑动窗口，对中文按三字切分，无需外部分词器
- **只索引 `text` 列**：仅歌词正文分词搜索，元数据搜索走 SQL LIKE
- **维护**：一次性导入后 `INSERT INTO lyrics_fts(lyrics_fts) VALUES('rebuild')` 重建索引