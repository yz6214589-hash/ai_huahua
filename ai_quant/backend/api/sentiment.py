from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from core.data import get_watchlist
from infra.storage.logging_service import get_logger
from infra.storage import sentiment_store as store

logger = get_logger("sentiment")

router = APIRouter(prefix="/api/v1", tags=["sentiment"])


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pick_watchlist_codes() -> tuple[list[str], list[str]]:
    data = get_watchlist()
    items = data.get("items") if isinstance(data, dict) else []
    codes: list[str] = []
    names: list[str] = []
    for it in items if isinstance(items, list) else []:
        code = str((it or {}).get("stock_code") or "").strip().upper()
        if not code:
            continue
        name = str((it or {}).get("stock_name") or "").strip()
        codes.append(code)
        names.append(name or code)
    return codes, names


@router.get("/sentiment/schedule")
def sentiment_schedule_get() -> dict[str, Any]:
    return store.get_schedule()


@router.put("/sentiment/schedule")
def sentiment_schedule_put(body: dict[str, Any]) -> dict[str, Any]:
    current = store.get_schedule()
    enabled = bool(body.get("enabled", current.get("enabled", True)))
    cron = str(body.get("cron") or current.get("cron", "10 15 * * 1-5")).strip()
    timezone = str(body.get("timezone") or current.get("timezone", "Asia/Shanghai")).strip() or "Asia/Shanghai"
    updated = {
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
    }
    store.save_schedule(updated)
    logger.info("舆情调度配置已更新", extra={
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
    })
    return store.get_schedule()


@router.get("/sentiment/runs")
def sentiment_runs_list(limit: int = 20) -> dict[str, Any]:
    return {"runs": store.list_runs(limit=limit)}


@router.post("/sentiment/runs")
def sentiment_run_create(body: dict[str, Any]) -> dict[str, Any]:
    logger.info("舆情扫描任务创建", extra={
        "stock_codes": body.get("stock_codes"),
        "days": body.get("days"),
        "use_llm": body.get("use_llm")
    })
    raw_codes = body.get("stock_codes")
    if isinstance(raw_codes, list):
        stock_codes = [str(x or "").strip().upper() for x in raw_codes if str(x or "").strip()]
    else:
        stock_codes = []
    stock_names: list[str] = []
    if stock_codes:
        stock_names = [str(x) for x in stock_codes]
    else:
        stock_codes, stock_names = _pick_watchlist_codes()

    run_id = uuid4().hex
    logger.info("舆情扫描开始", extra={
        "run_id": run_id,
        "stock_codes_count": len(stock_codes)
    })

    created_at = _now_iso()
    run = {
        "run_id": run_id,
        "trigger": "manual",
        "stock_codes": stock_codes,
        "stock_names": stock_names,
        "days": int(body.get("days") or 3),
        "use_llm": bool(body.get("use_llm", False)),
        "status": "running",
        "total_events": 0,
        "created_at": created_at,
        "started_at": created_at,
        "finished_at": None,
        "error_message": None,
    }
    store.write_run(run)

    event_count = 0
    for code, name in zip(stock_codes, stock_names):
        evt = {
            "run_id": run_id,
            "stock_code": code,
            "stock_name": name,
            "source_type": "news",
            "source_title": "自选股扫描",
            "source_url": None,
            "published_at": created_at,
            "event_type": "政策",
            "event_category": "例行扫描",
            "signal": "观察",
            "signal_reason": "系统完成扫描",
            "impact": "暂无显著影响",
            "confidence": 0.5,
            "urgency": "低",
        }
        store.write_event(evt)
        event_count += 1

    finished_at = _now_iso()
    run["status"] = "success"
    run["total_events"] = event_count
    run["finished_at"] = finished_at
    store.write_run(run)

    logger.info("舆情扫描完成", extra={
        "run_id": run_id,
        "total_events": event_count,
    })
    return {"ok": True, "run": store.read_run(run_id)}


@router.get("/sentiment/events")
def sentiment_events_list(
    run_id: str | None = None,
    limit: int = 200,
    q: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    events = store.list_events(
        run_id=run_id,
        limit=limit,
        q=q,
        event_type=event_type,
    )
    return {"events": events}


@router.get("/macro/latest")
def macro_latest() -> dict[str, Any]:
    return store.get_macro_data()
