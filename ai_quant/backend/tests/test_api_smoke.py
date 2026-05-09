from fastapi.testclient import TestClient

from ai_quant_api.app import app, create_app
import json


def test_root_and_health_alias_ok() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("docs") == "/docs"

    resp2 = client.get("/health")
    assert resp2.status_code == 200
    assert resp2.json().get("ok") is True


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


def test_data_rejects_injection_inputs() -> None:
    client = TestClient(app)
    resp = client.get("/api/data/trade_stock_daily?page=1&pageSize=5&stock_code=1;DROP TABLE x")
    assert resp.status_code == 400
    assert "非法输入" in str(resp.json().get("detail") or "")

    resp2 = client.post(
        "/api/export",
        json={"dataset": "trade_stock_daily", "format": "json", "filters": {"stock_code": "1;DROP TABLE x"}, "limit": 5},
    )
    assert resp2.status_code == 400
    assert "非法输入" in str(resp2.json().get("detail") or "")


def test_no_store_headers_exist() -> None:
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert str(resp.headers.get("Cache-Control") or "") == "no-store"


def test_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("AI_QUANT_RATE_LIMIT_MAX", "1")
    api = create_app()
    client = TestClient(api)
    ok = client.get("/api/health")
    assert ok.status_code == 200
    limited = client.get("/api/health")
    assert limited.status_code == 429


def test_agent_route_to_morning_graph(monkeypatch) -> None:
    from ai_quant_api.ai.graphs import morning_brief_graph

    monkeypatch.setattr(
        morning_brief_graph,
        "run_morning_workflow",
        lambda _: {
            "industry_rank": [],
            "stock_pool": [],
            "factor_rank": [],
            "picked_stocks": [],
            "report_md": "# 晨会分析简报 -- 测试",
            "report_html": "<html><body>test</body></html>",
            "messages": [],
            "generated_at": "2026-05-06T00:00:00",
        },
    )
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


def test_jobs_runs_write_and_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_CHARLES_JOB_STORE_DIR", str(tmp_path))
    client = TestClient(app)
    resp = client.post(
        "/api/jobs/runs",
        json={
            "domain": "stock_daily",
            "status": "success",
            "dataSourceFinal": "qmt",
            "fallbackChain": ["qmt"],
            "rowsWritten": 12,
            "itemsProcessed": 3,
            "failedItems": [],
            "message": "ok",
        },
    )
    assert resp.status_code == 200
    run = (resp.json() or {}).get("run") or {}
    run_id = run.get("runId")
    assert run_id
    assert run.get("userMessage") == "ok"

    files = list(tmp_path.glob("*.json"))
    assert files

    get_resp = client.get("/api/jobs/runs?limit=5")
    assert get_resp.status_code == 200
    runs = get_resp.json().get("runs") or []
    assert any(x.get("runId") == run_id for x in runs)


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


def test_watchlist_write_routes_exist_without_db(monkeypatch) -> None:
    from ai_quant_api.services.charles import integration as charles_integration

    monkeypatch.setattr(charles_integration, "_get_conn_and_query", lambda: (None, None))
    client = TestClient(app)

    add = client.post("/api/watchlist", json={"stock_code": "000001.SZ"})
    assert add.status_code == 200
    assert add.json().get("ok") is False

    pin = client.put("/api/watchlist/000001.SZ/pin", json={"pinned": True})
    assert pin.status_code == 200
    assert pin.json().get("ok") is False

    reo = client.put("/api/watchlist/reorder", json={"codes": ["000001.SZ"]})
    assert reo.status_code == 200
    assert reo.json().get("ok") is False

    dele = client.delete("/api/watchlist/000001.SZ")
    assert dele.status_code == 200
    assert dele.json().get("ok") is False


def test_reports_create_requires_stock_codes() -> None:
    client = TestClient(app)
    resp = client.post("/api/reports/tasks", json={"model": "qwen-max", "stock_codes": []})
    assert resp.status_code == 400
    assert "请选择至少一只股票" in str(resp.json().get("detail") or "")


def test_reports_running_task_timeout_mark_failed(monkeypatch) -> None:
    from datetime import datetime, timedelta

    from ai_quant_api.runtime import report_store

    monkeypatch.setenv("AI_QUANT_REPORT_TIMEOUT_SECONDS", "10")
    rec = report_store.create_task(model="qwen-max", stock_codes=["600519.SH"], stock_names=["贵州茅台"])
    report_store.update_task(rec.task_id, status="running", started_at=(datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds"))

    client = TestClient(app)
    resp = client.get("/api/reports/tasks?limit=200")
    assert resp.status_code == 200
    tasks = resp.json().get("tasks") or []
    t = next((x for x in tasks if x.get("task_id") == rec.task_id), None)
    assert t is not None
    assert t.get("status") == "failed"
    assert "超时" in str(t.get("error_message") or "")


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


def test_console_status_and_morning_trigger_exist(monkeypatch) -> None:
    from ai_quant_api.services.ceo import integration as ceo_integration

    monkeypatch.setattr(
        ceo_integration,
        "run_morning_workflow",
        lambda _: {
            "industry_rank": [],
            "stock_pool": [],
            "factor_rank": [],
            "picked_stocks": [],
            "report_md": "# 晨会分析简报 -- 测试",
            "report_html": "<html><body>test</body></html>",
            "messages": [],
            "generated_at": "2026-05-06T00:00:00",
        },
    )
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
    assert "mysql" in body
    mysql = body["mysql"] or {}
    assert isinstance(mysql.get("ok"), bool)
    assert "tables" in mysql
