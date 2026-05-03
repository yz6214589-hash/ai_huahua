import json
import time
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:7865"


def _request_json(method: str, path: str, body=None, timeout_s: int = 5):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            ct = resp.headers.get("content-type", "")
            elapsed_ms = int((time.time() - started) * 1000)
            if "application/json" in ct:
                return {
                    "ok": True,
                    "status": resp.status,
                    "elapsed_ms": elapsed_ms,
                    "json": json.loads(raw.decode("utf-8")),
                }
            return {
                "ok": True,
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "text": raw.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        elapsed_ms = int((time.time() - started) * 1000)
        text = raw.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text else None
        except Exception:
            parsed = None
        return {
            "ok": False,
            "status": e.code,
            "elapsed_ms": elapsed_ms,
            "error": text,
            "json": parsed,
        }


def run():
    cases = []

    def add_case(case_id: str, title: str, method: str, path: str, body, expect):
        cases.append(
            {
                "id": case_id,
                "title": title,
                "method": method,
                "path": path,
                "body": body,
                "expect": expect,
            }
        )

    add_case(
        "API-01",
        "系统健康检查返回数组",
        "GET",
        "/api/system/health",
        None,
        {"status": 200, "json_type": "list"},
    )
    add_case(
        "API-02",
        "Live 路由探活",
        "GET",
        "/api/live/ping",
        None,
        {"status": 200, "json_has_keys": ["ok", "module"]},
    )
    add_case(
        "API-03",
        "读取 live_state（不存在也应返回默认结构）",
        "GET",
        "/api/live/state",
        None,
        {"status": 200, "json_has_keys": ["trading_status", "positions", "control"]},
    )
    add_case(
        "API-04",
        "读取模拟盘运行状态",
        "GET",
        "/api/live/sim/status",
        None,
        {"status": 200, "json_type": "dict"},
    )
    add_case(
        "API-05",
        "策略注册表可拉取",
        "GET",
        "/api/live/strategies/registry",
        None,
        {"status": 200, "json_has_keys": ["groups", "flat"]},
    )
    add_case(
        "API-06",
        "回测 ping（可反映 mysql 可用性）",
        "GET",
        "/api/backtest/ping",
        None,
        {"status": 200, "json_has_keys": ["ok", "module", "mysql_available"]},
    )
    add_case(
        "API-07",
        "回测策略列表可拉取",
        "GET",
        "/api/backtest/strategies",
        None,
        {"status": 200, "json_has_keys": ["ok", "groups", "list"]},
    )
    add_case(
        "API-08",
        "Live 设置状态：非法 status 应返回 ok=false",
        "POST",
        "/api/live/status",
        {"status": "BAD"},
        {"status": 200, "json_match": {"ok": False}},
    )
    add_case(
        "API-09",
        "Live 控制字段：缺 field 应返回 ok=false",
        "POST",
        "/api/live/control",
        {"value": True},
        {"status": 200, "json_match": {"ok": False}},
    )
    add_case(
        "API-10",
        "回测 run：空参数应返回 ok=false",
        "POST",
        "/api/backtest/run",
        {},
        {"status": 200, "json_match": {"ok": False}},
    )

    results = []
    bugs = []

    for c in cases:
        r = _request_json(c["method"], c["path"], body=c["body"])

        passed = True
        expect = c["expect"]
        if r.get("status") != expect.get("status"):
            passed = False

        payload = r.get("json")
        if passed and expect.get("json_type"):
            t = expect["json_type"]
            if t == "list" and not isinstance(payload, list):
                passed = False
            if t == "dict" and not isinstance(payload, dict):
                passed = False

        if passed and expect.get("json_has_keys"):
            if not isinstance(payload, dict):
                passed = False
            else:
                for k in expect["json_has_keys"]:
                    if k not in payload:
                        passed = False
                        break

        if passed and expect.get("json_match"):
            if not isinstance(payload, dict):
                passed = False
            else:
                for k, v in expect["json_match"].items():
                    if payload.get(k) != v:
                        passed = False
                        break

        results.append(
            {
                "id": c["id"],
                "title": c["title"],
                "method": c["method"],
                "path": c["path"],
                "body": c["body"],
                "status": r.get("status"),
                "elapsed_ms": r.get("elapsed_ms"),
                "passed": passed,
                "resp_json_preview": payload if isinstance(payload, (dict, list)) else None,
                "resp_error": r.get("error"),
            }
        )

        if not passed:
            bugs.append(
                {
                    "id": f"BUG-{c['id']}",
                    "source_case": c["id"],
                    "title": f"{c['title']} 未满足预期",
                    "evidence": {"status": r.get("status"), "body": payload, "error": r.get("error")},
                }
            )

    print(json.dumps({"base": BASE, "results": results, "bugs": bugs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()

