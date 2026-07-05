# 性能文档

按日期追加基线报告，格式 `baseline-YYYY-MM-DD.md`。每次压测时注明测试环境（裸跑/容器）、并发数、时长。

## 对比方法

```
# 新基线对比旧基线
python scripts/load_test.py --endpoint /healthz --concurrency 100 --duration 10 --markdown
```

## 回归判断

- P99 延迟超过上一基线 2 倍 → 需排查
- 成功率 < 99% → 需排查（API 端点除外，401 不算失败）
- RPS 下降超过 30% → 需排查