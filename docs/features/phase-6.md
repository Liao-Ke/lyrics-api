# 阶段6：CI 流水线

**日期：** 2026-07-05

## 目标

为歌词API项目添加 GitHub Actions CI 流水线，闭环「push → lint → test → build 验证」链路。

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `.github/workflows/ci.yml` | CI 工作流：lint → test + build-smoke 三 job，lint 门禁 |
| `requirements-dev.txt` | 声明 dev 依赖（ruff/pytest/httpx/pytest-cov/pytest-asyncio），继承 runtime deps |
| `docs/superpowers/specs/2026-07-05-cicd-pipeline-design.md` | 设计文档（方案对比/选定/细节） |

### 修改文件

| 文件 | 变更 |
|---|---|
| `docs/arch/README.md` | 追加 ADR-018（CI 策略：lint 门禁 + 并行 + 无 CD + docker-not-podman） |
| `AGENTS.md` | 项目状态补「阶段6（CI 流水线）」；ADR 计数 17→18 |
| `RULES.md` | 禁止事项增 4 条 CI 规则；反模式增 1 条 GHA podman 记录 |
| `README.md` | 加 CI 徽章（`<owner>/<repo>` 占位） |
| `docs/deploy/README.md` | 「更新数据」段尾加 CI 交叉引用 1 行 |

## 核心实现

### CI 工作流结构

```
lint (ruff check)
  ├── test (pytest --cov --cov-fail-under=80)
  └── build-smoke (docker build → run → curl healthz → curl / → cleanup)
```

- **触发**：push main + PR to main + tag v* + workflow_dispatch
- **Runner**：ubuntu-latest（docker 预装）
- **Python**：3.12，`actions/setup-python@v5` + 内置 `cache: pip`

### Dev 依赖修复

项目原有 `requirements.txt` 只含 runtime deps（fastapi/uvicorn/loguru/pydantic-settings），dev 工具（pytest/ruff/httpx 等）仅在本地 miniconda env。`requirements-dev.txt` 通过 `-r requirements.txt` 继承 + 追加 dev 依赖，CI 才能复现测试环境。

### 镜像烟测

`build-smoke` job 在 `docker build` 后启动容器，curl 轮询 `/healthz` 等待就绪（最长 30s），验证健康检查和落地页均正常响应。始终 `always()` 清理容器。

## 验证方式

| 项 | 结果 |
|---|---|
| `ruff check .` | 通过 |
| `yq e '.on.push.branches[0]' .github/workflows/ci.yml` | main 正确 |
| YAML 无语法错误 | 通过 |
| 实跑（推 GitHub 后） | — |

## 已知限制

- CI 徽章 URL 中的 `<owner>/<repo>` 暂为占位，`gh repo create` 后需手动回填
- 无 CD 自动部署（按用户选择，部署仍手动 `podman compose up -d`）
- 镜像烟测仅覆盖 `/healthz` 和 `/`（公开端点），API 端点需 API key 未覆盖
- `build-smoke` 用 `docker` 而非 `podman`（GHA ubuntu-latest 预装 docker，podman 有 storage-driver quirks）；Dockerfile 标准，二者构建无差异