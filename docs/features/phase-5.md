# 阶段5：容器化部署与落地页

**日期：** 2026-07-05 &emsp; **关联 PRD：** [docs/prd/README.md](../prd/README.md)

## 目标

完成容器化部署方案和公开落地页，实现 PRD 验收标准中的"裸跑和容器两种方式均可启动"。

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `Dockerfile` | 多阶段构建：builder 跑 import 生成 db，final 只含 db+app+依赖 |
| `docker-compose.yml` | Podman compose 编排，端口/环境/healthcheck |
| `.dockerignore` | 排除 lrc/ tests/ .git/ 等 |
| `app/static/index.html` | 落地页（kami landing-page 模板），展示端点/示例/FAQ |
| `docs/deploy/README.md` | 部署方案文档 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/main.py` | 挂载 `StaticFiles(directory="app/static", html=True)` 在 `/`，公开落地页 |
| `README.md` | 容器部署补 key 生成步骤 + 新增环境变量表 + 项目结构更新 |
| `AGENTS.md` | 项目状态补阶段5，常用命令去"待实现" |
| `docs/arch/README.md` | 模块图补 static/，新增 ADR-016/017 |

## 核心实现

### 多阶段 Dockerfile

```
builder (python:3.12-slim)
  pip install -r requirements.txt
  COPY data/songs/ schema.sql scripts/import_songs.py
  RUN python scripts/import_songs.py   → 生成 data/lyrics.db

final (python:3.12-slim)
  COPY --from=builder /usr/local        → Python 依赖
  COPY app/                             → 应用代码
  COPY scripts/seed_key.py              → 保留 key 生成脚本
  COPY --from=builder data/lyrics.db    → 歌词数据库
  CMD uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- builder 阶段只烤 `data/songs/*.json`（1647 个文件，已在 git），不烤 `lrc/`（原始 LRC 在容器中不需要）
- final 镜像不含 `tests/`、`docs/`、`lrc/`，约 150MB
- 更新数据 = 重新 build

### StaticFiles 挂载

`app/mount("/", StaticFiles(directory="app/static", html=True), name="static")` 放在所有路由注册后，FastAPI 先匹配 `/healthz` `/api/v1/*` `/docs`，`/` 兜底落地页。落地页不鉴权。

### 落地页

kami landing-page 模板，包含：项目简介、5 个端点说明、curl 示例、架构要点、FAQ。

## 验证方式

| 项 | 结果 |
|---|---|
| `podman compose build` | 成功，1647 首歌 0.49s 导入 |
| `podman compose up -d` | 容器启动 |
| `curl :8000/healthz` | 200 + `{"status":"ok","db":"ok"}` |
| `curl :8000/` | 200（落地页 HTML） |
| `curl :8000/docs` | 200（Swagger UI） |
| 401 无 key / 无效 key | 401 + `UNAUTHORIZED` + 正确 reason |
| `ruff check .` | 通过 |
| `pytest --cov --cov-fail-under=80` | 93 passed, 93.79% 覆盖率 |

## 已知限制

- `main.py` 的 `app.mount` 行在集成测试 `test_app` fixture 中通过 `create_app()` 自动生效，但 `/` 路由未被测试覆盖（落地页是静态内容，测试不关心 HTML 内容）
- `seed_key.py` 在容器中需 `podman exec` 运行，未自动化（YAGNI，交互式够用）
- 镜像中 `scripts/` 目录包含 `clean_lrc.py`（未使用）和 `import_songs.py`（运行时不需要但保留）