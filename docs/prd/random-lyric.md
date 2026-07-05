# PRD: 随机歌词

## 一句话目标

从歌词库中随机返回一句歌词，支持 JSON 和可嵌入 JS 两种模式，提供按歌手/作词人/版本/翻译/字符数范围的筛选能力。

## 用户与场景

1. **歌词挂件/博客侧栏**：通过 `<script src="...?format=js&target=#lyric-box">` 嵌入页面，展示随机金句
2. **命令行摸鱼**：`curl .../random?format=json` 随手看一句歌词
3. **音乐播放器"今日推荐"**：筛选特定歌手的随机歌词作为推荐

## 功能描述

### 核心流程

1. 调用方 GET `/api/v1/random`，携带格式参数 `format=json|js` 和筛选参数
2. 服务端在库中匹配满足筛选条件 + 字符数范围的歌词行，`ORDER BY RANDOM() LIMIT 1`
3. `format=json` 返回 `RandomLyricLine` 结构（含歌词文本 + 歌曲元数据）
4. `format=js` 返回 `application/javascript` 自执行脚本，将歌词渲染到指定容器（`?target=` 选择器 → `window.LYRIC_TARGET` → 新建 `div`）
5. JS 模式通过 `?key=` 参数鉴权（Bearer 头在 `<script>` 标签下不可用）

### 输入

| 参数 | 位置 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|------|
| format | query | str | 否 | `json` | 响应格式：`json` 或 `js` |
| key | query | str | 否 | — | API key（JS 模式替代 Bearer 头） |
| target | query | str | 否 | — | CSS 选择器，JS 模式渲染目标容器 |
| min_chars | query | int | 否 | 1 | 歌词文本最小字符数，1-5000 |
| max_chars | query | int | 否 | 200 | 歌词文本最大字符数，1-5000 |
| artist | query | str | 否 | — | 歌手模糊匹配（LIKE） |
| writer | query | str | 否 | — | 作词/作曲/编曲人模糊匹配（OR LIKE） |
| version | query | str | 否 | — | 版本模糊匹配（LIKE，如 `Live`） |
| has_translation | query | bool | 否 | — | 仅筛选有/无翻译的歌曲 |

### 输出

#### JSON 模式

| 字段 | 类型 | 说明 |
|------|------|------|
| text | str | 歌词文本 |
| translation | str\|null | 翻译 |
| seq | int | 行序号 |
| time_sec | float\|null | 时间戳（秒） |
| time_str | str\|null | 原始时间串 |
| song | Song | 歌曲元数据 |

#### JS 模式

`Content-Type: application/javascript`，`Cache-Control: no-store`。自执行 IIFE：
- 渲染选择器优先级：`?target=` 选择器 → `window.LYRIC_TARGET` → 新建 `div`
- 歌词文本和元数据做 JS 字符串 + HTML 双重转义
- 通过 `window.onRandomLyric(data)` 回调通知调用方

## 边界与约束

- **性能**：`ORDER BY RANDOM()` 全表扫描，当前库万级行可接受。升级路径：`COUNT` + `OFFSET abs(random())%n`
- **安全**：JS 模式 `?key=` 参数在 URL 中传递，应用层日志（`request.url.path` 不含 query）不泄露，反代层需脱敏
- **技术**：不引入新依赖；结果不缓存；`target` 来自不可信 query 参数，嵌入 JS 前必须转义

## 验收标准

### 正常路径
- [ ] `format=json` 返回 200 + `RandomLyricLine` JSON
- [ ] `format=js` 返回 200 + `Content-Type: application/javascript` + 自执行 JS
- [ ] `?target=#box` 使 JS 渲染到该选择器元素
- [ ] 无 `target` 且无 `window.LYRIC_TARGET` 时 JS 新建 `div`
- [ ] `?artist=刘德华` 仅返回该歌手歌词
- [ ] `?min_chars=10&max_chars=50` 仅返回字符数在范围内的歌词
- [ ] `?key=xxx` 通过鉴权
- [ ] `?format=js&key=xxx` 成功返回 JS

### 边界条件
- [ ] 无匹配行 → 404 `NOT_FOUND`
- [ ] `format=invalid` → 422 `VALIDATION_ERROR`
- [ ] 无 key 且 API_KEYS_ENABLED=true → 401 `UNAUTHORIZED`
- [ ] `target=invalid-selector` → JS 回退新建 div
- [ ] 歌词文本含 `'`、`\`、`</`、换行 → JS 输出正确转义
- [ ] `window.onRandomLyric` 被调用并收到正确数据

### 异常处理
- [ ] 空库 → 404
- [ ] 限流超限 → 429

## 不做的范围

- 不扩展 language/genre/era 元数据筛选（schema 无这些字段）
- 不做连续片段模式（仅单行随机）
- 不做行数约束（仅字符数约束）
- 不缓存随机结果
- 不引入新依赖
- 不加 `JS_QUERY_KEY_ENABLED` 开关（按需再加）