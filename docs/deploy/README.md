# 部署方案

## 运行环境

| 组件 | 版本 | 说明 |
|------|------|------|
| Podman | 5+ | 或 Docker CE 24+ |
| Python | 3.12 | 仅裸跑时需要，容器版无需 |
| 基础镜像 | python:3.12-slim | 自动拉取，约 150MB |

## 快速部署（容器）

```bash
# 1. 配置环境变量（可选，有默认值即可跳过）
cp .env.example .env

# 2. 构建并启动
podman compose up -d

# 3. 生成 API key
podman exec -it lyrics-api python scripts/seed_key.py

# 4. 验证
curl http://localhost:8000/healthz
curl -H "Authorization: Bearer <key>" http://localhost:8000/api/v1/songs
```

## 快速部署（裸跑）

```bash
pip install -r requirements.txt
python scripts/import_songs.py    # 首次导入歌词数据
python scripts/seed_key.py        # 生成 API key
python -m app.main
```

## 环境变量

| 变量 | 说明 | 默认值 | 敏感 |
|------|------|--------|------|
| `DATABASE_PATH` | SQLite 数据库路径 | `data/lyrics.db` | 否 |
| `API_KEYS_ENABLED` | 是否启用 API key 鉴权 | `true` | 否 |
| `RATE_LIMIT_RPM` | 每 key 每分钟请求上限 | `60` | 否 |
| `LOG_LEVEL` | 日志级别 | `INFO` | 否 |
| `CORS_ORIGINS` | CORS 允许源，逗号分隔 | 空（不挂 CORS） | 否 |
| `HOST` | 监听地址 | `127.0.0.1` | 否 |
| `PORT` | 监听端口 | `8000` | 否 |
| `METRICS_ENABLED` | 是否暴露 `/metrics` 端点 | `true` | 否 |

> **注意：** 容器部署时 `HOST` 必须设为 `0.0.0.0`（docker-compose.yml 已强制覆盖）。裸跑保留 `127.0.0.1` 即仅本地访问。

## 健康检查

容器已内置 healthcheck（`GET /healthz`），每 30s 检测一次，10s 启动等待。

手动检测：
```bash
curl http://localhost:8000/healthz
# {"status":"ok","db":"ok"}
```

## 更新数据

歌词数据烤入镜像，更新需重新构建：

```bash
podman compose build --no-cache
podman compose up -d
```

> push main 时 CI 自动验证 lint + test + 镜像构建 + 烟测，部署仍手动 `podman compose up -d`。CI 用 docker 构建（GHA 环境），Dockerfile 兼容 docker/podman。

## 可观测性

服务启动后 `GET /metrics` 返回 Prometheus 格式指标（默认启用，`METRICS_ENABLED=false` 关闭）。抓取方式：

```bash
# 使用 Prometheus 容器抓取
podman run -d --name prometheus -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml:Z \
  prom/prometheus
```

最小 `prometheus.yml` 配置：

```yaml
scrape_configs:
  - job_name: lyrics-api
    static_configs:
      - targets: ['host.containers.internal:8000']
```

日志：loguru JSON 格式输出到 stdout，每条日志含 `request_id` 字段用于关联同一请求的相关事件。

## 回滚步骤

```bash
# 保留旧镜像 tag，回滚到上一版本
podman tag api-api:latest api-api:rollback
podman compose build
podman compose up -d
# 若新版本有问题：
podman tag api-api:rollback api-api:latest
podman compose up -d
```

## 性能基线

基线报告记录在 `docs/perf/baseline-YYYY-MM-DD.md`。每次压测前确认服务运行中：

```bash
# 裸跑基线
python scripts/load_test.py --endpoint /healthz --concurrency 100 --duration 10 --markdown

# FTS5 查询计划分析
python scripts/perf_inspect.py
```

容器部署下的基线对比：

```bash
podman compose up -d
python scripts/load_test.py --url http://localhost:8000 --endpoint /healthz --concurrency 100 --duration 10 --markdown
```

回归判断：P99 延迟超过上一基线 2 倍或成功率 < 99% 时需排查。

## 裸跑 vs 容器对照

| 维度 | 裸跑 | 容器 |
|------|------|------|
| 启动速度 | 即时 | ~2s |
| 依赖隔离 | 需系统 Python 环境 | 完全隔离 |
| 首次准备 | 需手动导入数据 | 开箱即用 |
| 镜像体积 | 不适用 | ~150MB |
| 适合场景 | 开发调试 | 部署展示 |