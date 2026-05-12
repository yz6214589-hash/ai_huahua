from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from ai_quant_api.services.charles.integration import get_watchlist
from ai_quant_api.runtime.logging_service import get_logger

logger = get_logger("sentiment")

router = APIRouter(prefix="/api", tags=["sentiment"])

_SENTIMENT_SCHEDULE: dict[str, Any] = {
    "enabled": True,
    "cron": "10 15 * * 1-5",
    "timezone": "Asia/Shanghai",
}
_SENTIMENT_RUNS: list[dict[str, Any]] = []
_SENTIMENT_EVENTS: list[dict[str, Any]] = []


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
    return dict(_SENTIMENT_SCHEDULE)


@router.put("/sentiment/schedule")
def sentiment_schedule_put(body: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(body.get("enabled", _SENTIMENT_SCHEDULE["enabled"]))
    _SENTIMENT_SCHEDULE["enabled"] = enabled
    return dict(_SENTIMENT_SCHEDULE)


@router.get("/sentiment/runs")
def sentiment_runs_list(limit: int = 20) -> dict[str, Any]:
    n = max(1, min(limit, 200))
    return {"runs": _SENTIMENT_RUNS[:n]}


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

    logger.info("舆情扫描开始", extra={
        "run_id": run_id,
        "stock_codes_count": len(stock_codes)
    })

    run_id = uuid4().hex
    created_at = _now_iso()
    run = {
        "run_id": run_id,
        "trigger": "manual",
        "stock_codes": stock_codes,
        "stock_names": stock_names,
        "days": int(body.get("days") or 3),
        "use_llm": bool(body.get("use_llm", False)),
        "status": "success",
        "total_events": 0,
        "created_at": created_at,
        "started_at": created_at,
        "finished_at": created_at,
        "error_message": None,
    }
    _SENTIMENT_RUNS.insert(0, run)

    next_id = len(_SENTIMENT_EVENTS) + 1
    for code, name in zip(stock_codes, stock_names):
        _SENTIMENT_EVENTS.append(
            {
                "id": next_id,
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
        )
        next_id += 1
    run["total_events"] = len(stock_codes)
    return {"ok": True, "run": run}


@router.get("/sentiment/events")
def sentiment_events_list(run_id: str | None = None, limit: int = 200, q: str | None = None, event_type: str | None = None) -> dict[str, Any]:
    n = max(1, min(limit, 500))
    out = list(_SENTIMENT_EVENTS)
    if run_id:
        rid = str(run_id).strip()
        out = [x for x in out if str(x.get("run_id") or "") == rid]
    if q:
        kw = str(q).strip().lower()
        if kw:
            out = [
                x
                for x in out
                if kw in str(x.get("stock_code") or "").lower()
                or kw in str(x.get("stock_name") or "").lower()
                or kw in str(x.get("source_title") or "").lower()
            ]
    if event_type and str(event_type).strip() and str(event_type) != "全部":
        et = str(event_type).strip()
        out = [x for x in out if str(x.get("event_type") or "") == et]
    return {"events": out[:n]}


@router.get("/macro/latest")
def macro_latest() -> dict[str, Any]:
    return {
        "indicators": [
            {"indicator": "CN_CPI_YOY", "value": 0.3, "date": _now_iso()[:10], "name": "中国 CPI 同比"},
            {"indicator": "US10Y", "value": 0.043, "date": _now_iso()[:10], "name": "美国10Y国债"},
        ],
        "composite": {
            "composite_fear_greed_index": 52,
            "overall_sentiment": "中性偏多",
            "action_suggestion": "维持仓位并跟踪增量信息",
            "timestamp": _now_iso(),
        },
    }
