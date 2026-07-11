# 歌词API

[![CI](https://github.com/Liao-Ke/lyrics-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Liao-Ke/lyrics-api/actions/workflows/ci.yml)
[![API Docs](https://img.shields.io/badge/API%20Docs-Apifox-blue)](https://y22r5peszm.apifox.cn/)

> 歌词数据来自公开网络收集，仅供个人学习研究，不用于商业传播。版权归原作者及版权方所有。

基于 1647 首华语流行乐 LRC 歌词的半开放查询 API，支持元数据搜索、歌词全文检索、卡拉OK 时间轴定位。

数据来源：`lrc/` 目录下 1647 个 `.lrc` 文件，经 `clean_lrc.py` 清洗为结构化 JSON 后导入 sqlite。

## 快速开始

### 容器部署（推荐）

```bash
# 构建并启动
podman compose up -d

# 生成 API key
podman exec -it lyrics-api python scripts/seed_key.py

# 访问 Swagger 文档
open http://localhost:8000/docs
```

### 裸跑

```bash
# 安装依赖
pip install -r requirements.txt

# 导入歌词数据（首次运行）
python scripts/import_songs.py

# 生成 API key
python scripts/seed_key.py

# 启动服务
python -m app.main

# 访问 Swagger 文档
open http://localhost:8000/docs
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|---|
| GET | `/healthz` | 健康检查 |
| GET | `/metrics` | Prometheus 指标（`METRICS_ENABLED` 开关） |
| GET | `/api/v1/songs` | 歌曲列表，分页 + 过滤（?title= & ?artist= & ?writer=） |
| GET | `/api/v1/songs/{id}` | 单首元数据 |
| GET | `/api/v1/songs/{id}/lyrics` | 歌词全文，?time= 进入卡拉OK 模式。429 带 `Retry-After` 头，成功响应带 `X-RateLimit-Limit/Remaining/Reset` 三头 |
| GET | `/api/v1/search?q=` | 统一搜索（标题 / 艺术家 / 作词人 / 歌词正文） |
| GET | `/api/v1/random` | 随机一句歌词，?format=js 返回可嵌入 JavaScript，?key= 鉴权，?target= 自定义选择器 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_PATH` | SQLite 数据库路径 | `data/lyrics.db` |
| `API_KEYS_ENABLED` | 是否启用鉴权 | `true` |
| `RATE_LIMIT_RPM` | 每 key 每分钟请求上限 | `60` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `CORS_ORIGINS` | CORS 允许源，逗号分隔 | 空（不挂 CORS） |
| `HOST` | 监听地址 | `127.0.0.1` |
| `PORT` | 监听端口 | `8000` |
| `METRICS_ENABLED` | 是否暴露 `/metrics` 端点 | `true` |
| `HSTS_ENABLED` | 是否启用 HSTS 响应头（需反代 TLS） | `false` |

## 项目结构

```
├── app/          # FastAPI 应用
    │   ├── main.py           # 入口
    │   ├── metrics.py        # Prometheus 指标定义
    │   ├── routers/          # 6 个端点
    │   ├── repositories/     # 数据访问层
    │   ├── static/           # 落地页
    │   └── auth / ratelimit / middleware / errors / models / config / deps / logging
├── scripts/      # 工具脚本（含 load_test.py 性能压测、revoke_key.py 吊销 key）
├── data/         # 歌词数据（JSON + SQLite）
├── docs/         # 文档
├── Dockerfile    # 多阶段构建
├── docker-compose.yml
└── schema.sql
```

## 技术栈

- **框架**：FastAPI + Pydantic
- **数据库**：SQLite3（FTS5 trigram 全文索引）
- **配置**：pydantic-settings + .env
- **日志**：loguru（JSON 序列化，reqeust_id 关联）
- **可观测性**：prometheus_client（/metrics 端点）
- **安全**：安全响应头中间件（X-Content-Type-Options/X-Frame-Options/Referrer-Policy/CSP/HSTS）、限流 429 Retry-After 头 + X-RateLimit-* 三头、审计日志（loguru JSON stdout）
- **部署**：Podman 容器 / 裸跑

## 开发

```bash
# 运行测试
pytest --cov --cov-fail-under=80

# 性能压测（需先启动服务）
python scripts/load_test.py --endpoint /healthz --concurrency 100 --duration 10

# 代码检查
ruff check .
```

## 文档

- [产品需求](docs/prd/)
- [架构设计](docs/arch/)
- [接口文档](docs/api/)（Swagger UI 同步）
- [在线 API 文档](https://y22r5peszm.apifox.cn/)（Apifox）
- [数据库设计](docs/db/)
- [部署方案](docs/deploy/)
- [性能基线](docs/perf/)