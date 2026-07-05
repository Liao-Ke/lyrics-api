#!/usr/bin/env python3
"""异步性能压测脚本——httpx 并发发压，输出延迟分布 + RPS。

用法：
  python scripts/load_test.py --endpoint /healthz --concurrency 50 --duration 10
  python scripts/load_test.py --endpoint /api/v1/songs --key <key> --concurrency 20 --duration 30 --markdown
"""

import argparse
import asyncio
import math
import sys
import time

import httpx


def _percentile(sorted_latencies: list[float], p: float) -> float:
    if not sorted_latencies:
        return 0.0
    k = (p / 100.0) * (len(sorted_latencies) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_latencies[int(k)]
    return sorted_latencies[f] * (c - k) + sorted_latencies[c] * (k - f)


async def _worker(
    url: str,
    headers: dict,
    results: list,
    stop_event: asyncio.Event,
):
    async with httpx.AsyncClient(timeout=10.0) as client:
        while not stop_event.is_set():
            start = time.monotonic()
            try:
                r = await client.get(url, headers=headers)
                status = r.status_code
            except Exception:
                status = 0
            latency = (time.monotonic() - start) * 1000
            results.append((status, latency))


async def main():
    parser = argparse.ArgumentParser(description="歌词API 性能压测")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--endpoint", default="/healthz", help="请求路径")
    parser.add_argument("--concurrency", type=int, default=10, help="并发连接数")
    parser.add_argument("--duration", type=int, default=15, help="测试时长（秒）")
    parser.add_argument("--key", default=None, help="API key")
    parser.add_argument("--markdown", action="store_true", help="输出 Markdown 表格行")
    args = parser.parse_args()

    headers = {}
    if args.key:
        headers["Authorization"] = f"Bearer {args.key}"

    full_url = args.url.rstrip("/") + "/" + args.endpoint.lstrip("/")
    stop_event = asyncio.Event()
    results: list[tuple[int, float]] = []

    workers = [_worker(full_url, headers, results, stop_event) for _ in range(args.concurrency)]

    print(f"压测 {full_url}  {args.concurrency} 并发  {args.duration}s…", file=sys.stderr)
    start = time.monotonic()

    tasks = [asyncio.create_task(w) for w in workers]
    await asyncio.sleep(args.duration)
    stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.monotonic() - start
    total = len(results)
    success = sum(1 for s, _ in results if s == 200)
    latencies = sorted(lat for _, lat in results if _ == 200)

    if total == 0:
        print("没有完成任何请求", file=sys.stderr)
        sys.exit(1)

    rps = total / elapsed
    success_rate = success / total * 100

    if args.markdown:
        p50 = _percentile(latencies, 50)
        p95 = _percentile(latencies, 95)
        p99 = _percentile(latencies, 99)
        p_max = latencies[-1] if latencies else 0
        print(f"| `{args.endpoint}` | {args.concurrency} | {rps:.0f} | {success_rate:.0f}% | {p50:.1f} | {p95:.1f} | {p99:.1f} | {p_max:.1f} |")
    else:
        print("\n结果:")
        print(f"  总请求: {total}")
        print(f"  成功: {success} ({success_rate:.1f}%)")
        print(f"  RPS: {rps:.0f}")
        if latencies:
            p50 = _percentile(latencies, 50)
            p95 = _percentile(latencies, 95)
            p99 = _percentile(latencies, 99)
            print(f"  延迟 (ms):  P50={p50:.1f}  P95={p95:.1f}  P99={p99:.1f}  Max={latencies[-1]:.1f}")


if __name__ == "__main__":
    asyncio.run(main())