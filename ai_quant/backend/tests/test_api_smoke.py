from fastapi.testclient import TestClient

from app import app, create_app
import json


def _unwrap(resp):
    body = resp.json()
    if isinstance(body, dict) and "success" in body and "data" in body:
        return body.get("data"), body
    return body, body


def test_root_and_health_alias_ok() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert data.get("ok") is True
    assert data.get("docs") == "/docs"

    resp2 = client.get("/health")
    assert resp2.status_code == 200
    data2, body2 = _unwrap(resp2)
    assert body2.get("success") is True
    assert data2.get("ok") is True


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert data["ok"] is True


def test_domain_routes_exist() -> None:
    client = TestClient(app)
    routes = [
        "/api/v1/data/summary",
        "/api/v1/analysis/status",
        "/api/v1/execution/status",
        "/api/v1/risk/status",
        "/api/v1/console/status",
        "/api/v1/agent/status",
    ]
    for path in routes:
        resp = client.get(path)
        assert resp.status_code == 200


def test_data_query_and_export_exist() -> None:
    client = TestClient(app)
    data_resp = client.get("/api/v1/data/trade_stock_daily?page=1&pageSize=5")
    assert data_resp.status_code == 200
    data, body = _unwrap(data_resp)
    assert body.get("success") is True
    assert "page" in data
    assert "rows" in data
    assert "total" in data

    export_resp = client.post(
        "/api/v1/export",
        json={"dataset": "trade_stock_daily", "format": "json", "filters": {}, "limit": 5},
    )
    assert export_resp.status_code == 200
    export_data, export_body = _unwrap(export_resp)
    assert export_body.get("success") is True
    assert "dataset" in export_data
    assert "rows" in export_data


def test_data_rejects_injection_inputs() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/data/trade_stock_daily?page=1&pageSize=5&stock_code=1;DROP TABLE x")
    assert resp.status_code == 400
    _, body = _unwrap(resp)
    assert "非法输入" in str(body.get("message") or "")

    resp2 = client.post(
        "/api/v1/export",
        json={"dataset": "trade_stock_daily", "format": "json", "filters": {"stock_code": "1;DROP TABLE x"}, "limit": 5},
    )
    assert resp2.status_code == 400
    _, body2 = _unwrap(resp2)
    assert "非法输入" in str(body2.get("message") or "")


def test_no_store_headers_exist() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert str(resp.headers.get("Cache-Control") or "") == "no-store"


def test_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("AI_QUANT_RATE_LIMIT_MAX", "1")
    api = create_app()
    client = TestClient(api)
    ok = client.get("/api/v1/health")
    assert ok.status_code == 200
    limited = client.get("/api/v1/health")
    assert limited.status_code == 429


def test_agent_route_to_morning_graph(monkeypatch) -> None:
    from agents import deepagent_agent
    from ai import deepagent_engine

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test")

    monkeypatch.setattr(
        deepagent_agent,
        "run_deepagent",
        lambda *_args, **_kwargs: deepagent_engine.DeepAgentResult(text="ok", steps=[]),
    )
    client = TestClient(app)
    resp = client.post("/api/v1/agent/run", json={"input": "请生成晨会简报"})
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert data["route"]["target"] == "deepagent"


def test_agent_runs_list() -> None:
    from agents import deepagent_agent
    from ai import deepagent_engine
    from unittest.mock import patch

    client = TestClient(app)
    with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test"}):
        with patch.object(deepagent_agent, "run_deepagent", return_value=deepagent_engine.DeepAgentResult(text="ok", steps=[])):
            client.post("/api/v1/agent/run", json={"input": "测试记录"})
    resp = client.get("/api/v1/agent/runs")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert isinstance(data.get("runs"), list)


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
    monkeypatch.setenv("AI_QUANT_JOB_STORE_DIR", str(tmp_path))
    client = TestClient(app)
    resp = client.get("/api/v1/jobs/runs?limit=5")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    runs = data.get("runs") or []
    assert runs, "应返回 Charles 存储中的运行记录"
    assert runs[0]["runId"] == "charles-real-001"


def test_jobs_runs_write_and_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_JOB_STORE_DIR", str(tmp_path))
    client = TestClient(app)
    resp = client.post(
        "/api/v1/jobs/runs",
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
    data, body = _unwrap(resp)
    run = (data or {}).get("run") or {}
    run_id = run.get("runId")
    assert run_id
    assert run.get("userMessage") == "ok"

    files = list(tmp_path.glob("*.json"))
    assert files

    get_resp = client.get("/api/v1/jobs/runs?limit=5")
    assert get_resp.status_code == 200
    data2, _ = _unwrap(get_resp)
    runs = data2.get("runs") or []
    assert any(x.get("runId") == run_id for x in runs)


def test_jobs_schedules_get_and_put_exist() -> None:
    client = TestClient(app)
    get_resp = client.get("/api/v1/jobs/schedules")
    assert get_resp.status_code == 200
    data, body = _unwrap(get_resp)
    assert body.get("success") is True
    assert isinstance(data.get("schedules"), list)
    assert any(str(x.get("domain")) == "stock_daily" for x in data.get("schedules", []))

    put_resp = client.put(
        "/api/v1/jobs/schedules/stock_daily",
        json={
            "enabled": True,
            "cron": "0 18 * * 1-5",
            "timezone": "Asia/Shanghai",
        },
    )
    assert put_resp.status_code == 200
    put_data, put_body = _unwrap(put_resp)
    assert put_body.get("success") is True
    assert put_data.get("ok") is True


def test_watchlist_get_exists() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/watchlist")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert "items" in data


def test_watchlist_write_routes_exist_without_db(monkeypatch) -> None:
    from core.data import service as data_service

    monkeypatch.setattr(data_service, "_get_conn_and_query", lambda: (None, None))
    client = TestClient(app)

    add = client.post("/api/v1/watchlist", json={"stock_code": "000001.SZ"})
    assert add.status_code == 200
    add_data, add_body = _unwrap(add)
    assert add_body.get("success") is True
    assert add_data.get("ok") is False

    pin = client.put("/api/v1/watchlist/000001.SZ/pin", json={"pinned": True})
    assert pin.status_code == 200
    pin_data, pin_body = _unwrap(pin)
    assert pin_body.get("success") is True
    assert pin_data.get("ok") is False

    reo = client.put("/api/v1/watchlist/reorder", json={"codes": ["000001.SZ"]})
    assert reo.status_code == 200
    reo_data, reo_body = _unwrap(reo)
    assert reo_body.get("success") is True
    assert reo_data.get("ok") is False

    dele = client.delete("/api/v1/watchlist/000001.SZ")
    assert dele.status_code == 200
    dele_data, dele_body = _unwrap(dele)
    assert dele_body.get("success") is True
    assert dele_data.get("ok") is False


def test_reports_create_requires_stock_codes() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/reports/tasks", json={"model": "qwen-max", "stock_codes": []})
    assert resp.status_code == 400
    _, body = _unwrap(resp)
    assert "请选择至少一只股票" in str(body.get("message") or "")


def test_reports_running_task_timeout_mark_failed(monkeypatch) -> None:
    from datetime import datetime, timedelta

    from runtime import report_store

    monkeypatch.setenv("AI_QUANT_REPORT_TIMEOUT_SECONDS", "10")
    rec = report_store.create_task(model="qwen-max", stock_codes=["600519.SH"], stock_names=["贵州茅台"])
    report_store.update_task(rec.task_id, status="running", started_at=(datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds"))

    client = TestClient(app)
    resp = client.get("/api/v1/reports/tasks?limit=200")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    tasks = data.get("tasks") or []
    t = next((x for x in tasks if x.get("task_id") == rec.task_id), None)
    assert t is not None
    assert t.get("status") == "failed"
    assert "超时" in str(t.get("error_message") or "")


def test_analysis_sample_and_signals_exist() -> None:
    client = TestClient(app)
    sample = client.get("/api/v1/analysis/stocks/sample?limit=5")
    assert sample.status_code == 200
    data, body = _unwrap(sample)
    assert body.get("success") is True
    assert isinstance(data.get("codes"), list)

    signals = client.get("/api/v1/analysis/signals?stock_code=600519.SH&start=2024-01-01&end=2024-02-01")
    assert signals.status_code == 200
    data2, body2 = _unwrap(signals)
    assert body2.get("success") is True
    assert "stock_code" in data2
    assert "signals" in data2


def test_execution_tasks_create_and_list() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/api/v1/execution/tasks",
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
    data, body = _unwrap(create_resp)
    task_id = (data.get("task") or {}).get("id")
    assert task_id

    list_resp = client.get("/api/v1/execution/tasks")
    assert list_resp.status_code == 200
    data2, _ = _unwrap(list_resp)
    items = data2.get("items") or []
    assert any(x.get("id") == task_id for x in items)


def test_risk_approve_and_audit_exist() -> None:
    client = TestClient(app)
    approve_resp = client.post(
        "/api/v1/risk/approve",
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
    approve_data, approve_body = _unwrap(approve_resp)
    assert approve_body.get("success") is True
    assert "decision" in approve_data
    assert "checks" in approve_data

    audit_resp = client.get("/api/v1/risk/audit")
    assert audit_resp.status_code == 200
    audit_data, audit_body = _unwrap(audit_resp)
    assert audit_body.get("success") is True
    assert isinstance(audit_data.get("items"), list)


def test_console_status_and_morning_trigger_exist(monkeypatch) -> None:
    from core.console import morning_brief

    monkeypatch.setattr(
        morning_brief,
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
    status_resp = client.get("/api/v1/console/status")
    assert status_resp.status_code == 200
    status_data, status_body = _unwrap(status_resp)
    assert status_body.get("success") is True
    assert "source" in status_data
    assert "features" in status_data

    trigger_resp = client.post("/api/v1/console/morning/trigger", json={"top_n_industries": 3, "top_n_stocks": 3})
    assert trigger_resp.status_code == 200
    trigger_data, trigger_body = _unwrap(trigger_resp)
    assert trigger_body.get("success") is True
    assert "ok" in trigger_data
    assert "workflow" in trigger_data


def test_agent_tools_list_exists() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/agent/tools")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert isinstance(data.get("items"), list)
    names = {str(item.get("name")) for item in data.get("items", [])}
    assert "data.query_summary" in names
    assert "execution.create_task" in names
    assert "risk.approve_order" in names


def test_console_overview_exists() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/console/overview")
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert "data_latest" in data
    assert "recent_jobs" in data
    assert "execution_status" in data
    assert "risk_status" in data
    assert "morning" in data
    assert "mysql" in data
    mysql = data["mysql"] or {}
    assert isinstance(mysql.get("ok"), bool)
    assert "tables" in mysql
