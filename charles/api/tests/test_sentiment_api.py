import os
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_sentiment(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"
    os.environ["CHARLES_JOB_STORE_DIR"] = str(tmp_path / "job_runs")
    os.environ["CHARLES_SENTIMENT_DISABLE_BG"] = "1"
    os.environ["CHARLES_SENTIMENT_TEST_MODE"] = "1"

    import importlib

    mod = importlib.import_module("charles_api.app")

    store: dict[str, Any] = {
        "watchlist": [{"stock_code": "600000.SH", "stock_name": "浦发银行"}],
        "job_schedule": {},
        "sentiment_runs": {},
        "sentiment_events": {},
    }

    class DummyConn:
        def commit(self) -> None:
            return None

        def close(self) -> None:
            return None

    def connect(_cfg: Any) -> DummyConn:
        return DummyConn()

    def query_dict(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        p = params or ()
        s = " ".join(sql.split()).lower()

        if s == "select domain from trade_job_schedule":
            return [{"domain": k} for k in store["job_schedule"].keys()]

        if "select domain, enabled, cron, timezone, mode, params_json from trade_job_schedule" in s:
            out = []
            for domain, row in store["job_schedule"].items():
                out.append(
                    {
                        "domain": domain,
                        "enabled": row["enabled"],
                        "cron": row["cron"],
                        "timezone": row.get("timezone") or "Asia/Shanghai",
                        "mode": row.get("mode") or "full",
                        "params_json": row.get("params_json") or "{}",
                    }
                )
            return out

        if "select domain, enabled, cron, timezone, mode, params_json, updated_at from trade_job_schedule" in s:
            out = []
            for domain, row in store["job_schedule"].items():
                out.append(
                    {
                        "domain": domain,
                        "enabled": row["enabled"],
                        "cron": row["cron"],
                        "timezone": row.get("timezone") or "Asia/Shanghai",
                        "mode": row.get("mode") or "full",
                        "params_json": row.get("params_json") or "{}",
                        "updated_at": datetime.utcnow(),
                    }
                )
            return out

        if "from trade_watchlist" in s and "select" in s:
            return store["watchlist"]

        if "from trade_sentiment_run where run_id=%s" in s:
            run_id = p[0]
            r = store["sentiment_runs"].get(run_id)
            return [r] if r else []

        if "from trade_sentiment_run" in s and "order by created_at desc" in s:
            limit = int(p[-1]) if p else 50
            rows = list(store["sentiment_runs"].values())
            rows.sort(key=lambda x: x["created_at"], reverse=True)
            return rows[:limit]

        if "from trade_sentiment_event" in s and "where run_id=%s" in s:
            run_id = p[0]
            return store["sentiment_events"].get(run_id) or []

        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        p = params or ()
        s = " ".join(sql.split()).lower()

        if s.startswith("insert into trade_job_schedule") or s.startswith("insert into trade_job_schedule (domain"):
            domain = str(p[0])
            store["job_schedule"][domain] = {
                "enabled": int(p[1]),
                "cron": str(p[2]),
                "timezone": str(p[3]),
                "mode": str(p[4]),
                "params_json": str(p[5]),
            }
            return 1

        if s.startswith("update trade_job_schedule"):
            enabled, cron, timezone, mode, params_json, domain = p
            store["job_schedule"][str(domain)] = {
                "enabled": int(enabled),
                "cron": str(cron),
                "timezone": str(timezone),
                "mode": str(mode),
                "params_json": str(params_json),
            }
            return 1

        if s.startswith("insert into trade_sentiment_run"):
            (
                run_id,
                trigger,
                stock_codes_json,
                stock_names_json,
                days,
                use_llm,
                status,
            ) = p
            store["sentiment_runs"][run_id] = {
                "run_id": run_id,
                "trigger_type": trigger,
                "stock_codes_json": stock_codes_json,
                "stock_names_json": stock_names_json,
                "days": days,
                "use_llm": use_llm,
                "status": status,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "finished_at": None,
                "error_message": None,
            }
            return 1

        if s.startswith("update trade_sentiment_run set"):
            if "where run_id=%s" not in s:
                return 0
            run_id = p[-1]
            obj = store["sentiment_runs"].get(run_id)
            if not obj:
                return 0
            if "status=%s" in s:
                obj["status"] = p[0]
            if "started_at=now()" in s:
                obj["started_at"] = datetime.utcnow()
            if "finished_at=now()" in s:
                obj["finished_at"] = datetime.utcnow()
            if "error_message=%s" in s:
                obj["error_message"] = p[1] if len(p) > 2 else p[0]
            return 1

        return 0

    def executemany(_conn: DummyConn, sql: str, rows: list[tuple[Any, ...]]) -> int:
        for r in rows:
            execute(_conn, sql, r)
        return len(rows)

    monkeypatch.setattr(mod, "connect", connect)
    monkeypatch.setattr(mod, "query_dict", query_dict)
    monkeypatch.setattr(mod, "execute", execute)
    monkeypatch.setattr(mod, "executemany", executemany)

    app = mod.create_app()
    return TestClient(app)


def test_sentiment_schedule_get_put(client_sentiment: TestClient):
    g = client_sentiment.get("/api/sentiment/schedule")
    assert g.status_code == 200
    assert g.json()["cron"] == "10 15 * * 1-5"

    p = client_sentiment.put("/api/sentiment/schedule", json={"enabled": False})
    assert p.status_code == 200
    assert p.json()["ok"] is True

    g2 = client_sentiment.get("/api/sentiment/schedule")
    assert g2.status_code == 200
    assert g2.json()["enabled"] is False


def test_sentiment_run_create_list(client_sentiment: TestClient):
    res = client_sentiment.post("/api/sentiment/runs", json={"days": 3, "use_llm": False, "stock_codes": ["600000.SH"]})
    assert res.status_code == 200
    run = res.json()["run"]
    assert run["status"] == "waiting"

    lst = client_sentiment.get("/api/sentiment/runs?limit=10")
    assert lst.status_code == 200
    assert any(x["run_id"] == run["run_id"] for x in lst.json()["runs"])

    detail = client_sentiment.get(f"/api/sentiment/runs/{run['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["run"]["run_id"] == run["run_id"]

    stock = client_sentiment.get(f"/api/sentiment/stocks/600000.SH?run_id={run['run_id']}")
    assert stock.status_code == 200
    assert "news" in stock.json()
    assert "events" in stock.json()


def test_sentiment_events_empty(client_sentiment: TestClient):
    res = client_sentiment.get("/api/sentiment/events?limit=50")
    assert res.status_code == 200
    assert res.json()["events"] == []


def test_macro_latest_shape(client_sentiment: TestClient):
    res = client_sentiment.get("/api/macro/latest")
    assert res.status_code == 200
    obj = res.json()
    assert "composite" in obj
    assert "indicators" in obj
