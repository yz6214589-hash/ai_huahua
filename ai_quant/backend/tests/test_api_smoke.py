from fastapi.testclient import TestClient

from ai_quant_api.app import app
import json


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_domain_routes_exist() -> None:
    client = TestClient(app)
    routes = [
        "/api/data/summary",
        "/api/analysis/status",
        "/api/execution/status",
        "/api/risk/status",
        "/api/console/status",
        "/api/agent/status",
    ]
    for path in routes:
        resp = client.get(path)
        assert resp.status_code == 200


def test_data_query_and_export_exist() -> None:
    client = TestClient(app)
    data_resp = client.get("/api/data/trade_stock_daily?page=1&pageSize=5")
    assert data_resp.status_code == 200
    body = data_resp.json()
    assert "page" in body
    assert "rows" in body
    assert "total" in body

    export_resp = client.post(
        "/api/export",
        json={"dataset": "trade_stock_daily", "format": "json", "filters": {}, "limit": 5},
    )
    assert export_resp.status_code == 200
    export_body = export_resp.json()
    assert "dataset" in export_body
    assert "rows" in export_body


def test_agent_route_to_morning_graph() -> None:
    client = TestClient(app)
    resp = client.post("/api/agent/run", json={"input": "请生成晨会简报"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"]["target"] == "graph:morning_brief"


def test_agent_runs_list() -> None:
    client = TestClient(app)
    client.post("/api/agent/run", json={"input": "测试记录"})
    resp = client.get("/api/agent/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json().get("runs"), list)


def test_jobs_runs_read_from_charles_store(tmp_path, monkeypatch) -> None:
    run_file = tmp_path / "sample-run.json"
    run_file.write_text(
        json.dumps(
            {
                "runId": "charles-real-001",
                "domain": "stock_daily",
                "startedAt": "2026-05-03T10:00:00",
                "finishedAt": "2026-05-03T10:00:05",
                "status": "success",
                "dataSourceFinal": "qmt",
                "fallbackChain": ["qmt"],
                "rowsWritten": 10,
                "itemsProcessed": 1,
                "failedItems": [],
                "message": "ok",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_QUANT_CHARLES_JOB_STORE_DIR", str(tmp_path))
    client = TestClient(app)
    resp = client.get("/api/jobs/runs?limit=5")
    assert resp.status_code == 200
    runs = resp.json().get("runs") or []
    assert runs, "应返回 Charles 存储中的运行记录"
    assert runs[0]["runId"] == "charles-real-001"


def test_jobs_schedules_get_and_put_exist() -> None:
    client = TestClient(app)
    get_resp = client.get("/api/jobs/schedules")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert isinstance(body.get("schedules"), list)
    assert any(str(x.get("domain")) == "stock_daily" for x in body.get("schedules", []))

    put_resp = client.put(
        "/api/jobs/schedules/stock_daily",
        json={
            "enabled": True,
            "cron": "0 18 * * 1-5",
            "timezone": "Asia/Shanghai",
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json().get("ok") is True


def test_watchlist_get_exists() -> None:
    client = TestClient(app)
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


def test_analysis_sample_and_signals_exist() -> None:
    client = TestClient(app)
    sample = client.get("/api/analysis/stocks/sample?limit=5")
    assert sample.status_code == 200
    assert isinstance(sample.json().get("codes"), list)

    signals = client.get("/api/analysis/signals?stock_code=600519.SH&start=2024-01-01&end=2024-02-01")
    assert signals.status_code == 200
    body = signals.json()
    assert "stock_code" in body
    assert "signals" in body


def test_execution_tasks_create_and_list() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/execution/tasks",
        json={
            "symbol": "600519.SH",
            "side": "buy",
            "total_qty": 1000,
            "num_steps": 4,
            "strategy": "twap",
            "adv": 2000000,
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json().get("task", {}).get("id")
    assert task_id

    list_resp = client.get("/api/execution/tasks")
    assert list_resp.status_code == 200
    items = list_resp.json().get("items") or []
    assert any(x.get("id") == task_id for x in items)


def test_risk_approve_and_audit_exist() -> None:
    client = TestClient(app)
    approve_resp = client.post(
        "/api/risk/approve",
        json={
            "order": {
                "stock_code": "600519.SH",
                "direction": "buy",
                "amount": 10000,
                "price": 100,
                "quantity": 100,
            },
            "portfolio": {
                "total_asset": 1_000_000,
                "prices": {"600519.SH": 100},
                "atr": {"600519.SH": 2},
            },
            "context": {"news_text": ""},
        },
    )
    assert approve_resp.status_code == 200
    approve_body = approve_resp.json()
    assert "decision" in approve_body
    assert "checks" in approve_body

    audit_resp = client.get("/api/risk/audit")
    assert audit_resp.status_code == 200
    assert isinstance(audit_resp.json().get("items"), list)


def test_console_status_and_morning_trigger_exist() -> None:
    client = TestClient(app)
    status_resp = client.get("/api/console/status")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert "source" in status_body
    assert "features" in status_body

    trigger_resp = client.post("/api/console/morning/trigger", json={"top_n_industries": 3, "top_n_stocks": 3})
    assert trigger_resp.status_code == 200
    trigger_body = trigger_resp.json()
    assert "ok" in trigger_body
    assert "workflow" in trigger_body


def test_agent_tools_list_exists() -> None:
    client = TestClient(app)
    resp = client.get("/api/agent/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("items"), list)
    names = {str(item.get("name")) for item in body.get("items", [])}
    assert "data.query_summary" in names
    assert "execution.create_task" in names
    assert "risk.approve_order" in names


def test_console_overview_exists() -> None:
    client = TestClient(app)
    resp = client.get("/api/console/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "data_latest" in body
    assert "recent_jobs" in body
    assert "execution_status" in body
    assert "risk_status" in body
    assert "morning" in body
