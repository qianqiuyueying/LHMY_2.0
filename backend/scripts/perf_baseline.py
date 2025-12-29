from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class Result:
    name: str
    status_codes: list[int]
    latencies_ms: list[float]

    def summary(self) -> dict:
        lat = self.latencies_ms
        lat_sorted = sorted(lat)
        p50 = lat_sorted[int(0.50 * (len(lat_sorted) - 1))] if lat_sorted else None
        p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if lat_sorted else None
        return {
            "name": self.name,
            "count": len(lat),
            "statusCodes": {str(c): self.status_codes.count(c) for c in sorted(set(self.status_codes))},
            "avgMs": round(statistics.fmean(lat), 2) if lat else None,
            "p50Ms": round(p50, 2) if p50 is not None else None,
            "p95Ms": round(p95, 2) if p95 is not None else None,
            "maxMs": round(max(lat), 2) if lat else None,
        }


def _request_timed(client: httpx.Client, method: str, url: str, **kwargs) -> tuple[int, float]:
    t0 = time.perf_counter()
    resp = client.request(method, url, **kwargs)
    ms = (time.perf_counter() - t0) * 1000
    return resp.status_code, ms


def main() -> int:
    base_url = os.getenv("PERF_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    n = int(os.getenv("PERF_N", "30"))
    timeout_s = float(os.getenv("PERF_TIMEOUT_SECONDS", "10"))

    print(f"PERF_BASE_URL={base_url} PERF_N={n}")

    results: list[Result] = []
    with httpx.Client(timeout=timeout_s) as client:
        # 1) OpenAPI
        r = Result(name="GET /api/v1/openapi.json", status_codes=[], latencies_ms=[])
        for _ in range(n):
            code, ms = _request_timed(client, "GET", f"{base_url}/api/v1/openapi.json")
            r.status_codes.append(code)
            r.latencies_ms.append(ms)
        results.append(r)

        # 2) Metrics
        r = Result(name="GET /metrics", status_codes=[], latencies_ms=[])
        for _ in range(n):
            code, ms = _request_timed(client, "GET", f"{base_url}/metrics")
            r.status_codes.append(code)
            r.latencies_ms.append(ms)
        results.append(r)

    report = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseUrl": base_url,
        "n": n,
        "results": [x.summary() for x in results],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

