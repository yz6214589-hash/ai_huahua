import os
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_assistant(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"
    os.environ["CHARLES_JOB_STORE_DIR"] = str(tmp_path / "job_runs")
    os.environ["CHARLES_REPORT_DISABLE_BG"] = "1"
    os.environ["CHARLES_SENTIMENT_DISABLE_BG"] = "1"
    os.environ["CHARLES_ASSISTANT_TEST_MODE"] = "1"

    import importlib

    mod = importlib.import_module("charles_api.app")

    store: dict[str, Any] = {
        "master": {"600000.SH": "浦发银行"},
        "watchlist": [{"stock_code": "600000.SH", "stock_name": "浦发银行", "pinned": 1, "sort_order": 0}],
        "job_schedule": {},
        "report_tasks": {},
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

        if "from trade_watchlist" in s and "select" in s:
            return store["watchlist"]

        if "from trade_stock_master where stock_code=%s" in s:
            code = p[0]
            name = store["master"].get(code)
            return [{"stock_name": name}] if name else []

        if "from trade_stock_daily where stock_code=%s" in s and "order by trade_date desc" in s:
            code = p[0]
            name = store["master"].get(code)
            return [{"stock_name": name}] if name else []

        if "from trade_report_task where task_id=%s" in s:
            task_id = p[0]
            obj = store["report_tasks"].get(task_id)
            return [obj] if obj else []

        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        p = params or ()
        s = " ".join(sql.split()).lower()

        if s.startswith("insert into trade_job_schedule"):
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

        if s.startswith("insert into trade_report_task"):
            task_id, model, stock_codes_json, stock_names_json, status = p
            store["report_tasks"][task_id] = {
                "task_id": task_id,
                "model": model,
                "stock_codes_json": stock_codes_json,
                "stock_names_json": stock_names_json,
                "status": status,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "finished_at": None,
                "error_message": None,
                "report_markdown": None,
            }
            return 1

        return 0

    def executemany(_conn: DummyConn, sql: str, rows: list[tuple[Any, ...]]) -> int:
        return 0

    monkeypatch.setattr(mod, "connect", connect)
    monkeypatch.setattr(mod, "query_dict", query_dict)
    monkeypatch.setattr(mod, "execute", execute)
    monkeypatch.setattr(mod, "executemany", executemany)

    app = mod.create_app()
    return TestClient(app)


def test_assistant_chat_stream_test_mode(client_assistant: TestClient):
    with client_assistant.stream("POST", "/api/assistant/chat_stream", json={"message": "hi"}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        body = "".join([x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x) for x in r.iter_raw()])
        assert "type" in body
        assert "token" in body

