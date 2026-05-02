import json
import os
import time
from dataclasses import dataclass

import httpx


API_BASE = os.getenv("CHARLES_API_BASE", "http://127.0.0.1:8000")


@dataclass
class Case:
    id: str
    name: str
    method: str
    path: str
    json_body: dict | None = None
    expect_status: tuple[int, ...] = (200,)


def run_case(client: httpx.Client, c: Case) -> dict:
    url = f"{API_BASE}{c.path}"
    t0 = time.time()
    try:
        r = client.request(c.method, url, json=c.json_body)
        dt = int((time.time() - t0) * 1000)
        ok = r.status_code in c.expect_status
        preview = r.text[:800]
        return {"id": c.id, "name": c.name, "ok": ok, "status": r.status_code, "ms": dt, "url": url, "preview": preview}
    except Exception as e:
        dt = int((time.time() - t0) * 1000)
        return {"id": c.id, "name": c.name, "ok": False, "status": None, "ms": dt, "url": url, "preview": f"{type(e).__name__}: {e}"}


def main() -> int:
    cases = [
        Case("API-01", "summary", "GET", "/api/summary"),
        Case("API-02", "jobs runs", "GET", "/api/jobs/runs?limit=10"),
        Case("API-03", "jobs schedules", "GET", "/api/jobs/schedules", expect_status=(200, 503)),
        Case("API-04", "watchlist", "GET", "/api/watchlist"),
        Case("API-05", "stock search", "GET", "/api/stocks?q=%E6%B5%A6%E5%8F%91&limit=5", expect_status=(200, 404)),
        Case("API-06", "stock snapshot", "GET", "/api/stock/600000.SH/snapshot", expect_status=(200, 404)),
        Case("API-07", "report tasks list", "GET", "/api/reports/tasks?limit=5"),
        Case("API-08", "report task create validate", "POST", "/api/reports/tasks", json_body={"model": "qwen-max", "stock_codes": []}, expect_status=(400,)),
        Case("API-09", "sentiment schedule", "GET", "/api/sentiment/schedule"),
        Case("API-10", "macro latest", "GET", "/api/macro/latest", expect_status=(200, 500, 502, 503, 504)),
        Case(
            "API-11",
            "assistant chat stream (non-stream check)",
            "POST",
            "/api/assistant/chat_stream",
            json_body={"message": "hi", "context": {"mode": "normal"}},
            expect_status=(200, 400, 401, 403, 500),
        ),
    ]

    out = {"base": API_BASE, "results": []}
    with httpx.Client(timeout=10.0) as client:
        for c in cases:
            out["results"].append(run_case(client, c))

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

