# 接口文档 — 歌词API

## 通用约定

- **Base URL**: `/api/v1`（`/healthz` 除外）
- **鉴权**: `Authorization: Bearer <api_key>`，所有 `/api/v1/*` 端点必须
- **限流**: 60 RPM / key（在 `api_keys` 表 `rate_limit_rpm` 配置），`/healthz` 不限流
- **错误格式**: 统一 `{"error": {"code": "...", "message": "...", "detail": {...}}}`（详见底部错误章节）

## 接口清单

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/healthz` | 否 | 健康检查 |
| GET | `/api/v1/songs` | 是 | 歌曲列表，分页 + 过滤 |
| GET | `/api/v1/songs/{id}` | 是 | 单首歌曲元数据 |
| GET | `/api/v1/songs/{id}/lyrics` | 是 | 歌词全文或卡拉OK 时间轴 |
| GET | `/api/v1/search` | 是 | 统一搜索 |

---

## GET /healthz

**说明：** 健康检查。Kubernetes/Podman 探针使用。`/healthz` 不经过鉴权/限流，但会检查数据库连接。

**请求：** 无参数

**成功响应:** `200 OK`

```json
{
  "status": "ok",
  "db": "ok"
}
```

**错误响应:** 数据库不可用时 `db` 字段为 `"error"`，状态码仍为 200（探针需自行判断）。

---

## GET /api/v1/songs

**说明：** 歌曲列表，支持按标题/艺术家/作词作曲人模糊过滤。默认按标题排序，分页返回。

**请求：**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| title | query | str | 否 | 标题模糊匹配（LIKE %title%） |
| artist | query | str | 否 | 艺术家模糊匹配 |
| writer | query | str | 否 | 作词/作曲/编曲人模糊匹配（OR 查询） |
| page | query | int | 否 | 页码，从 1 开始，默认 1 |
| size | query | int | 否 | 每页条数，1-100，默认 20 |

**成功响应:** `200 OK`

```json
{
  "items": [
    {
      "id": 1,
      "title": "暗里着迷",
      "title_raw": "暗里着迷",
      "version": null,
      "artist": "刘德华",
      "lyricist": "向雪怀",
      "composer": "陈耀川",
      "arranger": "杜自持",
      "has_translation": false
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20
}
```

**错误响应:**

| 状态码 | 错误码 | 触发条件 |
|--------|--------|----------|
| 401 | `UNAUTHORIZED` | API key 缺失/无效/吊销 |
| 422 | `VALIDATION_ERROR` | page < 1、size < 1 或 > 100 |

---

## GET /api/v1/songs/{id}

**说明：** 获取单首歌曲的元数据（标题、艺术家、作词人、作曲人、编曲人、是否有翻译）。

**请求：**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| id | path | int | 是 | 歌曲 ID |

**成功响应:** `200 OK`

```json
{
  "id": 1,
  "title": "暗里着迷",
  "title_raw": "暗里着迷",
  "version": null,
  "artist": "刘德华",
  "lyricist": "向雪怀",
  "composer": "陈耀川",
  "arranger": "杜自持",
  "has_translation": false
}
```

**错误响应:**

| 状态码 | 错误码 | 触发条件 |
|--------|--------|----------|
| 401 | `UNAUTHORIZED` | API key 缺失/无效/吊销 |
| 404 | `NOT_FOUND` | 歌曲 ID 不存在 |

---

## GET /api/v1/songs/{id}/lyrics

**说明：** 获取歌词。支持两种模式：不传 `?time=` 时返回完整歌词（按时间戳排序）；传 `?time=` 时进入卡拉OK 模式，返回当前播放时间点前后各若干行。

**请求：**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| id | path | int | 是 | 歌曲 ID |
| time | query | float | 否 | 当前播放时间（秒）。有值 → 卡拉OK 模式，无值 → 全文模式 |
| context | query | int | 否 | 卡拉OK 模式上下文行数（前后各 N 行），0-10，默认 1 |

**成功响应（全文模式）:** `200 OK`

```json
{
  "song_id": 1,
  "lyrics": [
    {"time_sec": 0.0, "time_str": "00:00.000", "text": "第一行", "translation": null, "seq": 0},
    {"time_sec": 5.0, "time_str": "00:05.000", "text": "暗里着迷", "translation": "secretly", "seq": 1}
  ]
}
```

**成功响应（卡拉OK 模式）:** `200 OK`

```json
{
  "song_id": 1,
  "time_sec": 7.5,
  "context": 1,
  "lyrics": [
    {"time_sec": 0.0, "time_str": "00:00.000", "text": "第一行", "translation": null, "seq": 0},
    {"time_sec": 5.0, "time_str": "00:05.000", "text": "暗里着迷", "translation": "secretly", "seq": 1},
    {"time_sec": 10.0, "time_str": "00:10.000", "text": "第三行", "translation": null, "seq": 2}
  ]
}
```

**卡拉OK 语义（ADR-013）：** 当前行定义为最后一个 `time_sec <= t` 的行。早于首行时返回首 N 行，晚于末行时返回末 N 行。边界处返回的行数可能少于 `2*context+1`。

**错误响应:**

| 状态码 | 错误码 | 触发条件 |
|--------|--------|----------|
| 401 | `UNAUTHORIZED` | API key 缺失/无效/吊销 |
| 404 | `NOT_FOUND` | 歌曲 ID 不存在 |

---

## GET /api/v1/search

**说明：** 统一搜索。支持 4 个维度：标题 / 艺术家 / 作词人 / 歌词正文。歌词正文使用 FTS5 trigram 分词（3+ 字符），其余维度使用 SQL LIKE。scope 参数控制搜索范围，不传时搜索全部维度。

**请求：**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| q | query | str | 是 | 搜索关键词，最短 1 字符 |
| scope | query | str | 否 | 逗号分隔的范围：`title,artist,writer,lyrics`。默认全部 |

**成功响应:** `200 OK`

```json
{
  "query": "暗里着迷",
  "scope": ["title", "artist", "writer", "lyrics"],
  "total": 2,
  "items": [
    {"id": 1, "title": "测试A", "artist": "艺术家1", ...},
    {"id": 3, "title": "测试C", "artist": "艺术家2", ...}
  ]
}
```

**错误响应:**

| 状态码 | 错误码 | 触发条件 |
|--------|--------|----------|
| 401 | `UNAUTHORIZED` | API key 缺失/无效/吊销 |
| 422 | `VALIDATION_ERROR` | `q` 为空字符串 |

**注意：** FTS5 trigram 仅对 3+ 字符生效。1-2 字符的歌词搜索自动降级为 `text LIKE`。

---

## 错误响应

所有 API 端点共享统一错误响应格式。

### 响应格式

```json
{
  "error": {
    "code": "<ERROR_CODE>",
    "message": "<人类可读描述>",
    "detail": {}
  }
}
```

### 错误码表

| code | HTTP | 触发条件 | detail |
|------|------|----------|--------|
| `UNAUTHORIZED` | 401 | API key 缺失、无效、已吊销，或 `Authorization` 头格式错误 | `reason`: `missing_header` / `malformed_header` / `invalid_key` / `revoked_key` |
| `RATE_LIMITED` | 429 | 请求频率超过当前 key 的 RPM 上限 | `retry_after_seconds`: 窗口剩余秒数（int）; `limit`: RPM 上限 |
| `NOT_FOUND` | 404 | 请求的资源（歌曲/歌词）不存在 | `resource_type`: `song` / `lyrics`; `resource_id`: 请求的 ID（str） |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败（类型错误、越界等） | `errors`: `[{field, message}]` |
| `INTERNAL_ERROR` | 500 | 服务器内部未预期异常 | 仅开发环境含 `debug` 信息，生产环境省略 |

### 实现说明

- 由 `app/errors.py` 的 `register_exception_handlers(app)` 在应用启动时注入
- 自定异常 `ApiError`、FastAPI 的 `RequestValidationError`、`HTTPException` 统一进入此格式
- 非 FastAPI 的 500 异常（未捕获异常）由 `INTERNAL_ERROR` 兜底，生产环境不暴露栈信息