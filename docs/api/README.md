# 接口文档 — 歌词API

## 通用约定

- **Base URL**: `/api/v1`（`/healthz` 和 `/metrics` 除外）
- **鉴权**: `Authorization: Bearer <api_key>`，所有 `/api/v1/*` 端点必须。`/api/v1/random?format=js` 额外支持 `?key=<api_key>` query 参数鉴权（浏览器 `<script>` 标签无法发送 Bearer 头，此为受控例外）
- **限流**: 60 RPM / key（在 `api_keys` 表 `rate_limit_rpm` 配置），`/healthz` 和 `/metrics` 不限流
- **错误格式**: 统一 `{"error": {"code": "...", "message": "...", "detail": {...}}}`（详见底部错误章节）
- **可观测性**: `/metrics` 端点不鉴权不限流，`METRICS_ENABLED=false` 时不挂载
- **安全响应头**: 所有响应携带 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: strict-origin-when-cross-origin`；`/api/v1/*`、`/metrics`、`/healthz` 携带 `Cache-Control: no-store`；落地页 HTML 携带 `Content-Security-Policy: default-src 'self'`；`Strict-Transport-Security` 仅在 `HSTS_ENABLED=true` 时设置
- **限流响应头**: 429 响应携带 `Retry-After` 头（秒）；成功 `/api/v1/*` 响应携带 `X-RateLimit-Limit`（RPM 上限）、`X-RateLimit-Remaining`（剩余次数）、`X-RateLimit-Reset`（窗口重置 epoch 秒）三头
- **审计日志**: 鉴权失败、限流触发、key 签发/吊销均记审计事件，通过 loguru JSON stdout 输出（`event=auth_failure` / `rate_limited` / `key_issued` / `key_revoked`），由日志聚合系统采集

## 接口清单

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/healthz` | 否 | 健康检查 |
| GET | `/metrics` | 否 | Prometheus 指标（`METRICS_ENABLED=true` 时挂载） |
| GET | `/api/v1/songs` | 是 | 歌曲列表，分页 + 过滤 |
| GET | `/api/v1/songs/{id}` | 是 | 单首歌曲元数据 |
| GET | `/api/v1/songs/{id}/lyrics` | 是 | 歌词全文或卡拉OK 时间轴 |
| GET | `/api/v1/search` | 是 | 统一搜索 |
| GET | `/api/v1/random` | 是 | 随机一句歌词，?format=js 返回可嵌入 JavaScript，支持筛选与字符数范围 |

---

## GET /healthz

**说明：** 健康检查。Kubernetes/Podman 探针使用。`/healthz` 不经过鉴权/限流，但会检查数据库连接。

**请求：** 无参数

**成功响应:** `200 OK`

```json
{
  "status": "ok",
  "db": "ok",
  "songs_total": 1647,
  "cache_entries": 12,
  "uptime_seconds": 3600
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 服务状态，`"ok"` 或 `"error"` |
| `db` | string | 数据库连接状态，`"ok"` 或 `"error"` |
| `songs_total` | int | 数据库中的歌曲总数，`-1` 表示查询失败 |
| `cache_entries` | int | 当前缓存条目数 |
| `uptime_seconds` | int | 服务启动以来经过的秒数 |

**错误响应:** 数据库不可用时 `db` 字段为 `"error"`，状态码仍为 200（探针需自行判断）。

---

## GET /metrics

**说明：** Prometheus 指标端点。返回 Prometheus text exposition 格式，供 Prometheus 服务器抓取。不经过鉴权/限流，受 `METRICS_ENABLED` 环境变量控制（默认 true）。

**请求：** 无参数

**成功响应:** `200 OK`

```
Content-Type: text/plain; version=1.0.0; charset=utf-8
```

暴露的 metric 系列：

| Metric 名 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `http_requests_total` | Counter | `method, path, status` | HTTP 请求总数，按方法/路径模板/状态码分组 |
| `http_request_duration_seconds` | Histogram | `method, path` | 请求延迟分布（秒） |
| `cache_ops_total` | Counter | `method, result` | 缓存操作数，按方法/结果（hit/miss）分组 |
| `auth_failures_total` | Counter | `reason` | 鉴权失败次数，按原因（missing_header/malformed_header/invalid_key）分组 |
| `rate_limited_total` | Counter | 无 | 被限流拒绝的请求总数 |

`path` 标签使用路由模板（如 `/api/v1/songs/{song_id}`），而非实际 URL 路径，避免路径参数导致基数爆炸。所有标签不含 `key_id`，不暴露使用者身份。

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

## GET /api/v1/random

**说明：** 返回一句随机歌词。支持两种模式：`format=json` 返回 `RandomLyricLine` 结构（含歌词文本 + 歌曲元数据）；`format=js` 返回 `Content-Type: application/javascript` 的自执行脚本，可嵌入页面 `<script src="...">` 直接使用。JS 模式通过 `?key=` 参数鉴权（浏览器 `<script>` 无法发送 `Authorization` 头）。

**请求：**

| 参数 | 位置 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|------|
| format | query | str | 否 | `json` | 响应格式：`json` 或 `js` |
| key | query | str | 否 | — | API key（JS 模式替代 Bearer 头） |
| target | query | str | 否 | — | CSS 选择器，JS 模式渲染目标容器。优先级：`?target=` 选择器 → `window.LYRIC_TARGET` → 新建 `div` |
| min_chars | query | int | 否 | 1 | 歌词文本最小字符数，1-5000 |
| max_chars | query | int | 否 | 200 | 歌词文本最大字符数，1-5000 |
| artist | query | str | 否 | — | 歌手模糊匹配（LIKE） |
| writer | query | str | 否 | — | 作词/作曲/编曲人模糊匹配（OR LIKE） |
| version | query | str | 否 | — | 版本模糊匹配（LIKE，如 `Live`） |
| has_translation | query | bool | 否 | — | 筛选有/无翻译的歌词行 |

**成功响应（JSON 模式）:** `200 OK`

```json
{
  "text": "暗里着迷",
  "translation": "secretly",
  "seq": 1,
  "time_sec": 5.0,
  "time_str": "00:05.000",
  "song": {
    "id": 1,
    "title": "测试A",
    "title_raw": "测试A",
    "version": null,
    "artist": "艺术家1",
    "lyricist": "作词人1",
    "composer": "作曲人1",
    "arranger": "编曲人1",
    "has_translation": false
  }
}
```

**成功响应（JS 模式）:** `200 OK`

```
Content-Type: application/javascript
Cache-Control: no-store
```

自执行 IIFE 将歌词注入页面。目标容器选择优先级：`?target=` 参数 → `window.LYRIC_TARGET` 全局变量 → 新建 `div`。歌词文本与 `target` 选择器均做 JS 字符串 + HTML 双重转义防止 XSS。

```javascript
(function(){var d={text:'暗里着迷',title:'测试A',artist:'艺术家1',translation:null};var sel='';var el=sel?document.querySelector(sel):null;if(!el){el=document.createElement('div');document.body.appendChild(el);}el.className='lyric-random';el.innerHTML='<p class="lyric-text">「'+d.text+'」</p>'+(d.translation?'<p class="lyric-tr">'+d.translation+'</p>':'')+'<p class="lyric-meta">— '+d.title+' / '+d.artist+'</p>';if(window.onRandomLyric)window.onRandomLyric(d);})()
```

JS 模式可选回调：定义 `window.onRandomLyric` 函数，注入后收到 `{text, title, artist, translation}` 数据对象。

**错误响应:**

| 状态码 | 错误码 | 触发条件 |
|--------|--------|----------|
| 401 | `UNAUTHORIZED` | API key 缺失/无效/吊销（Bearer 或 query key 均可能） |
| 404 | `NOT_FOUND` | 无匹配筛选条件的歌词行 |
| 422 | `VALIDATION_ERROR` | `format` 不是 `json` 或 `js` |

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
| `UNAUTHORIZED` | 401 | API key 缺失、无效、已吊销，或 `Authorization` 头格式错误 | `reason`: `missing_header` / `malformed_header` / `invalid_key` / `revoked_key` / `missing_query_key` / `invalid_query_key` |
| `RATE_LIMITED` | 429 | 请求频率超过当前 key 的 RPM 上限 | `retry_after_seconds`: 最早请求过期剩余秒数（int）; `limit`: RPM 上限 |
| `NOT_FOUND` | 404 | 请求的资源（歌曲/歌词）不存在 | `resource_type`: `song` / `lyric`; `resource_id`: 请求的 ID（str） |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败（类型错误、越界等） | `errors`: `[{field, message}]` |
| `INTERNAL_ERROR` | 500 | 服务器内部未预期异常 | 仅开发环境含 `debug` 信息，生产环境省略 |

### 实现说明

- 由 `app/errors.py` 的 `register_exception_handlers(app)` 在应用启动时注入
- 自定异常 `ApiError`、FastAPI 的 `RequestValidationError`、`HTTPException` 统一进入此格式
- 非 FastAPI 的 500 异常（未捕获异常）由 `INTERNAL_ERROR` 兜底，生产环境不暴露栈信息