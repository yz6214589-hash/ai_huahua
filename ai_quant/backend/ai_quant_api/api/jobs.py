from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from ai_quant_api.services.charles.integration import list_job_runs, write_job_run

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_KNOWN_JOB_DOMAINS = {
    "stock_daily",
    "stock_financial",
    "stock_news",
    "macro_indicator",
    "rate_daily",
    "calendar",
    "report_consensus",
    "catalyst",
}

_SCHEDULES: dict[str, dict[str, Any]] = {
    "stock_daily": {"enabled": True, "cron": "0 18 * * 1-5", "timezone": "Asia/Shanghai", "mode": "test"},
    "stock_financial": {"enabled": True, "cron": "30 19 * * 6", "timezone": "Asia/Shanghai", "mode": "test"},
    "stock_news": {"enabled": True, "cron": "*/10 * * * *", "timezone": "Asia/Shanghai", "mode": "test"},
    "macro_indicator": {"enabled": True, "cron": "0 9 1 * *", "timezone": "Asia/Shanghai", "mode": "full"},
    "rate_daily": {"enabled": True, "cron": "0 8 * * 1-5", "timezone": "Asia/Shanghai", "mode": "full"},
    "calendar": {"enabled": True, "cron": "0 7 * * *", "timezone": "Asia/Shanghai", "mode": "full"},
    "report_consensus": {"enabled": True, "cron": "0 20 * * 1-5", "timezone": "Asia/Shanghai", "mode": "test"},
    "catalyst": {"enabled": True, "cron": "0 21 * * 0", "timezone": "Asia/Shanghai", "mode": "full"},
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _validate_cron(expr: str) -> None:
    parts = [x for x in (expr or "").strip().split() if x]
    if len(parts) not in (5, 6):
        raise ValueError("cron 必须是 5 或 6 段")


@router.get("/runs")
def list_runs(limit: int = 10, domain: str | None = None) -> dict[str, object]:
    runs = list_job_runs(domain=domain, limit=limit)
    timeout_s = 900
    try:
        timeout_s = max(30, int(str(__import__("os").getenv("AI_QUANT_JOB_RUN_TIMEOUT_SECONDS", "900")).strip() or "900"))
    except Exception:
        timeout_s = 900

    now = datetime.now()
    out: list[dict[str, Any]] = []
    for r in runs:
        it = dict(r or {})
        status = str(it.get("status") or "")
        started = str(it.get("startedAt") or "").strip()
        finished = str(it.get("finishedAt") or "").strip()
        if status == "running" and started and not finished:
            try:
                started_dt = datetime.fromisoformat(started[:19])
            except Exception:
                started_dt = None
            if started_dt is not None:
                age = (now - started_dt).total_seconds()
                if age > timeout_s:
                    it["status"] = "failed"
                    if not str(it.get("message") or "").strip():
                        it["message"] = "任务长时间未更新，已标记为失败"
                    if not str(it.get("userMessage") or "").strip():
                        it["userMessage"] = "任务长时间未更新，已标记为失败"
                    it["finishedAt"] = _now_iso()
        out.append(it)
    return {"runs": out}


@router.post("/runs")
def write_run(body: dict[str, Any]) -> dict[str, Any]:
    domain = str(body.get("domain") or "").strip()
    if domain not in _KNOWN_JOB_DOMAINS:
        raise HTTPException(status_code=400, detail="unknown domain")
    try:
        run = write_job_run(domain=domain, payload=body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run": run}


@router.get("/schedules")
def list_schedules() -> dict[str, object]:
    items: list[dict[str, Any]] = []
    for domain in sorted(_SCHEDULES.keys()):
        conf = _SCHEDULES[domain]
        latest = list_job_runs(domain=domain, limit=1)
        last = latest[0] if latest else None
        items.append(
            {
                "domain": domain,
                "enabled": bool(conf.get("enabled", True)),
                "cron": str(conf.get("cron") or ""),
                "timezone": str(conf.get("timezone") or "Asia/Shanghai"),
                "mode": conf.get("mode"),
                "nextRunAt": None,
                "lastRunAt": last.get("startedAt") if last else None,
                "lastStatus": last.get("status") if last else None,
                "updatedAt": str(conf.get("updatedAt") or ""),
            }
        )
    return {"schedules": items}


@router.put("/schedules/{domain}")
def update_schedule(domain: str, body: dict[str, object]) -> dict[str, object]:
    if domain not in _KNOWN_JOB_DOMAINS:
        raise HTTPException(status_code=400, detail="unknown domain")
    cron = str(body.get("cron") or "").strip()
    timezone = str(body.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai"
    enabled = bool(body.get("enabled", True))
    mode = body.get("mode")
    try:
        _validate_cron(cron)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _SCHEDULES[domain] = {
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
        "mode": mode,
        "updatedAt": _now_iso(),
    }
    return {"ok": True}
