import time

from prometheus_client import Counter, Histogram

_APP_START = time.monotonic()

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request latency (seconds)",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

cache_ops_total = Counter(
    "cache_ops_total", "Cache hit/miss by method",
    ["method", "result"],
)

auth_failures_total = Counter(
    "auth_failures_total", "Authentication failures by reason",
    ["reason"],
)

rate_limited_total = Counter(
    "rate_limited_total", "Rate-limited requests",
)


def record_request(method: str, path: str, status: int, latency_ms: float) -> None:
    http_requests_total.labels(method=method, path=path, status=str(status)).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(latency_ms / 1000.0)


def get_uptime_seconds() -> float:
    return time.monotonic() - _APP_START