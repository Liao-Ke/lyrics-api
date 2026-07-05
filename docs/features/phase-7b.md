# 阶段7b：性能压测与基线

**日期：** 2026-07-05

## 目标

为歌词API建立性能基线：压测脚本、FTS5 查询计划分析、基线报告文档。

## 修改范围

### 新增文件

| 文件 | 说明 |
|---|---|
| `scripts/load_test.py` | 异步 httpx 并发发压，支持 --markdown 输出表格行 |
| `scripts/perf_inspect.py` | SQLite EXPLAIN QUERY PLAN + 平均计时 |
| `docs/perf/README.md` | 性能文档目录索引 |
| `docs/perf/baseline-2026-07-05.md` | 基线报告（测试环境/压测矩阵/查询计划/瓶颈分析/升级路径） |
| `docs/superpowers/specs/2026-07-05-load-test-design.md` | 设计文档（方案对比/压测矩阵设计/boundary） |

### 修改文件

| 文件 | 变更 |
|---|---|
| `docs/arch/README.md` | 追加 ADR-020（压测用手写 httpx 脚本，不引入 locust/k6） |
| `docs/deploy/README.md` | 新增「性能基线」段，引用 docs/perf/ |
| `README.md` | 项目结构补 scripts/load_test.py / perf_inspect.py；文档链接补 docs/perf/ |
| `AGENTS.md` | 项目状态补阶段7b；常用命令补 load_test / perf_inspect |
| `RULES.md` | 禁止事项补「不引入 locust/k6」；反模式补「不要在 CI 跑 load_test」 |

## 核心实现

### 压测脚本设计

`scripts/load_test.py`：
- 异步并发（`asyncio` + `httpx`），每个 worker 独立循环，`asyncio.Event` 控制停止
- 参数：`--endpoint` / `--concurrency` / `--duration` / `--key` / `--markdown`
- 百分位计算：线性插值（`math.floor` + `math.ceil` 混合），不引入 numpy
- 输出：默认详细模式 + `--markdown` 表格行（便于追加到基线文档）

**不引入 locust/k6**（ADR-020）：locust 引入 gevent/flask 等传递依赖，单只读 API 用不到 web UI；k6 是外部二进制，非 pip 管理。httpx 已在 dev dep 中。

### FTS5 查询计划

`scripts/perf_inspect.py` 对 10 个代表性查询运行 `EXPLAIN QUERY PLAN` + 50 次计时平均。结果写入基线报告。关键发现：

- 所有查询均在 0.3ms 以内，SQLite 非瓶颈
- FTS5 trigram 比 LIKE 快约 2 倍（4+ 字符查询）
- 列表分页触发 `TEMP B-TREE FOR ORDER BY`（全表扫描 + 排序），1647 行下 0.27ms 可接受

## 验证结果

| 项 | 结果 |
|---|---|
| `/healthz` 100 并发 10s | 114 RPS, 100%, P50=68.8ms, P95=108.9ms |
| `/metrics` 50 并发 10s | 88 RPS, 100%, P50=54.2ms, P95=78.8ms |
| 查询计划 10 项 | 全部 ≤ 0.27ms |
| ruff check | 通过 |
| pytest --cov-fail-under=80 | 不破（脚本未测试，无代码改动） |

## 已知限制

- 压测脚本不使用 API key 鉴权，/api/v1 端点未覆盖（状态码 401 而非 200，统计无意义）。需先 seed 一个 key 后 `--key <key>` 压测
- 基线在裸跑下采集，容器部署可能有差异（容器网络栈 + 少量 image 开销）
- 仅单 worker 基准，多 worker 压测需手动启动 `uvicorn --workers 4`
- 缓存未预热，get_song/get_lyrics 等端点全部 MISS。长时间运行后基线需更新