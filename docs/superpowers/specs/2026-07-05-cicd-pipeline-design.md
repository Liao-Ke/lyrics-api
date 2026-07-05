# CI 流水线设计

**日期：** 2026-07-05

## 目标

为歌词API项目添加 GitHub Actions CI 流水线，在 push/main、PR、tag 时自动执行 lint、test、镜像构建验证。无 CD（部署仍手动）。

## 方案对比

| 方案 | 结构 | 墙钟时间 | YAML 复杂度 | 特点 |
|---|---|---|---|---|
| A 单 job 串行 | 1 job: checkout→ruff→pytest→build→smoke | ~40s | 最简单 | 无并行，无单检查徽章 |
| B 三 job + lint 门禁 | `lint` → (`test` ∥ `build-smoke`) | ~30s | 适中 | lint 失败终止下游，test/build 并行，GitHub UI 独立状态 |
| C 双 job | `lint-test` ∥ `build-smoke` | ~35s | 折中 | ruff 失败 test 已浪费 |

**选定：B**。作品集需体现标准工业实践——lint 门禁 + 并行 + 单检查可观测。

## 设计

### 触发矩阵

| 事件 | lint | test | build-smoke |
|---|---|---|---|
| push main | ✓ | ✓ (gate) | ✓ (gate) |
| PR to main | ✓ | ✓ (gate) | ✓ (gate) |
| tag v* | ✓ | ✓ (gate) | ✓ (gate) |
| workflow_dispatch | ✓ | ✓ (gate) | ✓ (gate) |

### Job 定义

**lint** (ubuntu-latest, ~15s):
- actions/checkout@v6 → setup-python@v5 (3.12, cache:pip) → `pip install -r requirements-dev.txt` → `ruff check .`

**test** (needs: lint, ~30s):
- setup → `pytest --cov --cov-fail-under=80`

**build-smoke** (needs: lint, ~40s):
- checkout → `docker build -t lyrics-api-ci .`
- `docker run -d -p 8000:8000 --name ci lyrics-api-ci`
- curl 轮询等待 healthz (30s 超时)
- 断言 `/healthz` → `{"status":"ok","db":"ok"}`；断言 `/` → 200
- 始终清理容器

### Pre-CI 修复

`requirements.txt` 缺少 dev 依赖，新增 `requirements-dev.txt` 声明：

```
-r requirements.txt
ruff>=0.11
pytest>=8.4
pytest-asyncio>=1.4
httpx>=0.28
pytest-cov>=5
```

## 边界与已排除

| 不做 | 理由 |
|---|---|
| 推 GHCR 镜像 | 无 CD，YAGNI |
| codecov 上传 | pytest-cov 80% 门槛够 |
| 矩阵多 Python 版本 | 项目锁定 3.12 |
| Podman CI | GHA runner podman 有 storage-driver quirks；Dockerfile 标准，docker/podman 无差异 |
| 自动部署 | 用户选择「仅 CI，无 CD」 |
| Release workflow | tag 复用同一套 job，中建不单独写 release job |

## 前置条件

- `gh repo create <name> --source=. --push` 推到 GitHub
- 回填 README 徽章中的 `<owner>/<repo>`

## 文档变更

范围见 `docs/features/phase-6.md` 修改范围表。