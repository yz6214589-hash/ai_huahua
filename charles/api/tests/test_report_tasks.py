import os
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"
    os.environ["CHARLES_REPORT_DISABLE_BG"] = "1"
    os.environ["CHARLES_JOB_STORE_DIR"] = str(tmp_path / "job_runs")

    import importlib

    mod = importlib.import_module("charles_api.app")

    store: dict[str, Any] = {
        "master": {"600000.SH": "浦发银行"},
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

        if "from trade_report_task" in s and "order by created_at desc" in s:
            limit = int(p[-1]) if p else 50
            rows = list(store["report_tasks"].values())
            rows.sort(key=lambda r: r.get("created_at") or datetime(1970, 1, 1), reverse=True)
            return rows[:limit]

        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        p = params or ()
        s = " ".join(sql.split()).lower()

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

        if s.startswith("delete from trade_report_task"):
            task_id = p[0]
            store["report_tasks"].pop(task_id, None)
            return 1

        if s.startswith("update trade_report_task set status"):
            status = p[0]
            task_id = p[-1]
            obj = store["report_tasks"].get(task_id)
            if not obj:
                return 0
            obj["status"] = status
            if "started_at=now()" in s:
                obj["started_at"] = datetime.utcnow()
            if "finished_at=now()" in s:
                obj["finished_at"] = datetime.utcnow()
            if "report_markdown=%s" in s:
                obj["report_markdown"] = p[1]
            if "error_message=%s" in s:
                obj["error_message"] = p[1]
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


def test_report_task_create_list_and_view(client_reports: TestClient):
    res = client_reports.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600000.SH"]},
    )
    assert res.status_code == 200
    task = res.json()["task"]
    assert task["model"] == "qwen-max"
    assert task["status"] == "waiting"
    assert task["stock_codes"] == ["600000.SH"]

    lst = client_reports.get("/api/reports/tasks?limit=50")
    assert lst.status_code == 200
    tasks = lst.json()["tasks"]
    assert any(t["task_id"] == task["task_id"] for t in tasks)

    view = client_reports.get(f"/api/reports/tasks/{task['task_id']}/view")
    assert view.status_code == 200
    assert "text/html" in view.headers.get("content-type", "")


def test_report_task_delete(client_reports: TestClient):
    res = client_reports.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600000.SH"]},
    )
    assert res.status_code == 200
    task_id = res.json()["task"]["task_id"]

    d = client_reports.delete(f"/api/reports/tasks/{task_id}")
    assert d.status_code == 200
    assert d.json()["ok"] is True

    missing = client_reports.get(f"/api/reports/tasks/{task_id}")
    assert missing.status_code == 404
