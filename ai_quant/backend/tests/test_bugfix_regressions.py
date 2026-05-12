from __future__ import annotations

from fastapi.testclient import TestClient

from ai_quant_api.app import app


def test_jobs_run_alias_exists() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/jobs/run",
        json={
            "domain": "stock_daily",
            "mode": "test",
            "params": {"test_stock": "600519.SH"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("result"), dict)
    assert body["result"].get("runId")


def test_console_morning_error_is_sanitized(monkeypatch) -> None:
    import ai_quant_api.api.console_ceo as console_ceo

    def _raise_raw(_: dict) -> dict:
        raise RuntimeError("Table 'trade_stock_daily' doesn't exist")

    monkeypatch.setattr(console_ceo, "trigger_morning", _raise_raw)
    client = TestClient(app)
    resp = client.post("/api/console/morning/trigger", json={})
    assert resp.status_code == 500
    detail = str((resp.json() or {}).get("detail") or "")
    assert "table" not in detail.lower()
    assert "数据库" in detail


def test_sentiment_routes_exist_and_run() -> None:
    client = TestClient(app)
    schedule = client.get("/api/sentiment/schedule")
    assert schedule.status_code == 200
    sch = schedule.json()
    assert "enabled" in sch
    assert "cron" in sch
    assert "timezone" in sch

    run = client.post("/api/sentiment/runs", json={"days": 3, "use_llm": False})
    assert run.status_code == 200
    run_body = run.json()
    assert isinstance(run_body.get("run"), dict)
    run_id = str(run_body["run"].get("run_id") or "")
    assert run_id

    runs = client.get("/api/sentiment/runs?limit=5")
    assert runs.status_code == 200
    assert isinstance((runs.json() or {}).get("runs"), list)

    events = client.get(f"/api/sentiment/events?run_id={run_id}&limit=20")
    assert events.status_code == 200
    assert isinstance((events.json() or {}).get("events"), list)

    macro = client.get("/api/macro/latest")
    assert macro.status_code == 200
    body = macro.json()
    assert isinstance(body.get("indicators"), list)
    assert isinstance(body.get("composite"), dict)
