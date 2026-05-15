from __future__ import annotations

from fastapi.testclient import TestClient

from app import app


def _unwrap(resp):
    body = resp.json()
    if isinstance(body, dict) and "success" in body and "data" in body:
        return body.get("data"), body
    return body, body


def test_jobs_run_alias_exists() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/jobs/run",
        json={
            "domain": "stock_daily",
            "mode": "test",
            "params": {"test_stock": "600519.SH"},
        },
    )
    assert resp.status_code == 200
    data, body = _unwrap(resp)
    assert body.get("success") is True
    assert isinstance(data.get("result"), dict)
    assert data["result"].get("runId")


def test_console_morning_error_is_sanitized(monkeypatch) -> None:
    import api.console_ceo as console_ceo

    def _raise_raw(_: dict) -> dict:
        raise RuntimeError("Table 'trade_stock_daily' doesn't exist")

    monkeypatch.setattr(console_ceo, "trigger_morning", _raise_raw)
    client = TestClient(app)
    resp = client.post("/api/v1/console/morning/trigger", json={})
    assert resp.status_code == 500
    _, body = _unwrap(resp)
    message = str(body.get("message") or "")
    assert "table" not in message.lower()
    assert "数据库" in message


def test_sentiment_routes_exist_and_run() -> None:
    client = TestClient(app)
    schedule = client.get("/api/v1/sentiment/schedule")
    assert schedule.status_code == 200
    sch, sch_body = _unwrap(schedule)
    assert sch_body.get("success") is True
    assert "enabled" in sch
    assert "cron" in sch
    assert "timezone" in sch

    run = client.post("/api/v1/sentiment/runs", json={"days": 3, "use_llm": False})
    assert run.status_code == 200
    run_data, run_body = _unwrap(run)
    assert run_body.get("success") is True
    assert isinstance(run_data.get("run"), dict)
    run_id = str(run_data["run"].get("run_id") or "")
    assert run_id

    runs = client.get("/api/v1/sentiment/runs?limit=5")
    assert runs.status_code == 200
    runs_data, runs_body = _unwrap(runs)
    assert runs_body.get("success") is True
    assert isinstance((runs_data or {}).get("runs"), list)

    events = client.get(f"/api/v1/sentiment/events?run_id={run_id}&limit=20")
    assert events.status_code == 200
    events_data, events_body = _unwrap(events)
    assert events_body.get("success") is True
    assert isinstance((events_data or {}).get("events"), list)

    macro = client.get("/api/v1/macro/latest")
    assert macro.status_code == 200
    macro_data, macro_body = _unwrap(macro)
    assert macro_body.get("success") is True
    assert isinstance(macro_data.get("indicators"), list)
    assert isinstance(macro_data.get("composite"), dict)
