"""
任务调度管理API模块
提供定时任务的查询、创建和调度配置管理功能
支持查看任务执行历史、创建新任务、配置定时调度策略等
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.backend..infra.storage.database import connect, execute, executemany, load_mysql_config, query_dict

from src.backend..data import list_job_runs, write_job_run
from .jobs import run_domain
from src.backend..infra.storage.logging_service import get_logger

logger = get_logger("jobs")

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

# 支持的任务领域类型
_KNOWN_JOB_DOMAINS = {
    "stock_daily",      # 股票每日数据
    "stock_financial",  # 股票财务数据
    "stock_news",       # 股票新闻
    "macro_indicator",  # 宏观指标
    "rate_daily",       # 利率日度数据
    "calendar",         # 日历数据
    "report_consensus", # 研报共识
    "catalyst",         # 催化剂事件
    "sentiment_monitor", # 舆情监控扫描
}

_DEFAULT_SCHEDULES: dict[str, dict[str, Any]] = {
    "stock_daily": {"enabled": True, "cron": "0 18 * * 1-5", "timezone": "Asia/Shanghai", "mode": "full"},
    "stock_financial": {"enabled": True, "cron": "30 19 * * 6", "timezone": "Asia/Shanghai", "mode": "test"},
    "stock_news": {"enabled": True, "cron": "*/10 * * * *", "timezone": "Asia/Shanghai", "mode": "test"},
    "macro_indicator": {"enabled": True, "cron": "0 9 1 * *", "timezone": "Asia/Shanghai", "mode": "full"},
    "rate_daily": {"enabled": True, "cron": "0 8 * * 1-5", "timezone": "Asia/Shanghai", "mode": "full"},
    "calendar": {"enabled": True, "cron": "0 7 * * *", "timezone": "Asia/Shanghai", "mode": "full"},
    "report_consensus": {"enabled": True, "cron": "0 20 * * 1-5", "timezone": "Asia/Shanghai", "mode": "test"},
    "catalyst": {"enabled": True, "cron": "0 21 * * 0", "timezone": "Asia/Shanghai", "mode": "full"},
    "sentiment_monitor": {"enabled": True, "cron": "10 15 * * 1-5", "timezone": "Asia/Shanghai", "mode": "full"},
}

_DOMAIN_META: dict[str, dict[str, Any]] = {
    "stock_daily": {"title": "行情日线", "desc": "收盘价/成交量 + RSI14/MA20（QMT > AkShare > Tushare）", "defaultMode": "full"},
    "stock_financial": {"title": "财务季度", "desc": "财务指标原始数据（payload_json，AkShare）", "defaultMode": "test"},
    "stock_news": {"title": "新闻事件", "desc": "AkShare 新闻（title/content）", "defaultMode": "test"},
    "macro_indicator": {"title": "宏观指标", "desc": "CPI/PPI/PMI/M2/社融/LPR（AkShare）", "defaultMode": "full"},
    "rate_daily": {"title": "利率日频", "desc": "中美 10Y 国债收益率（AkShare）", "defaultMode": "full"},
    "calendar": {"title": "财经日历", "desc": "百度财经日历（AkShare）", "defaultMode": "full"},
    "report_consensus": {"title": "研报一致预期", "desc": "券商评级/目标价（AkShare）", "defaultMode": "test"},
    "catalyst": {"title": "关键催化剂", "desc": "Qwen 联网搜索（需要 DASHSCOPE_API_KEY）", "defaultMode": "full"},
    "sentiment_monitor": {"title": "舆情监控", "desc": "扫描自选股（当前为轻量实现）", "defaultMode": "full"},
}

_SCHEDULER = None
_SCHEDULER_ERROR: str | None = None
_LOCKS: dict[str, threading.Lock] = {d: threading.Lock() for d in _KNOWN_JOB_DOMAINS}


def _now_iso() -> str:
    """
    获取当前时间的ISO格式字符串
    
    Returns:
        str: 当前时间，精确到秒的ISO格式
    """
    return datetime.now().isoformat(timespec="seconds")


def _validate_cron(expr: str) -> None:
    """
    验证Cron表达式格式
    
    支持5段或6段Cron表达式（5段为标准格式，6段包含秒）
    
    Args:
        expr: Cron表达式字符串
        
    Raises:
        ValueError: 表达式格式不正确时抛出
    """
    parts = [x for x in (expr or "").strip().split() if x]
    if len(parts) not in (5, 6):
        logger.error("Cron 表达式验证失败", extra={
            "cron": expr,
            "error": "invalid format",
            "expected": "5 or 6 parts"
        })
        raise ValueError("cron 必须是 5 或 6 段")
    logger.debug("Cron 表达式验证成功", extra={
        "cron": expr,
        "parts": len(parts)
    })


def _parse_cron(expr: str) -> tuple[str, str, str, str, str, str | None]:
    parts = [p for p in (expr or "").strip().split() if p]
    if len(parts) not in (5, 6):
        raise ValueError("cron 必须是 5 或 6 段")
    if len(parts) == 5:
        return parts[0], parts[1], parts[2], parts[3], parts[4], None
    return parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]


def _schedule_job_id(domain: str) -> str:
    return f"job:{domain}"


def _ensure_job_schedule_table() -> None:
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS trade_job_schedule (
              domain varchar(32) NOT NULL,
              enabled tinyint(1) NOT NULL DEFAULT 1,
              cron varchar(64) NOT NULL,
              timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
              mode varchar(10) DEFAULT NULL,
              params_json text,
              updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (domain)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        )
    finally:
        conn.close()


def _ensure_default_schedules() -> None:
    _ensure_job_schedule_table()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(conn, "SELECT domain FROM trade_job_schedule")
        existing = {str(r.get("domain")) for r in rows if r.get("domain")}
        inserts: list[tuple[Any, ...]] = []
        for d, conf in _DEFAULT_SCHEDULES.items():
            if d in existing:
                continue
            inserts.append(
                (
                    d,
                    1 if bool(conf.get("enabled", True)) else 0,
                    str(conf.get("cron") or "").strip(),
                    str(conf.get("timezone") or "Asia/Shanghai"),
                    conf.get("mode"),
                    json.dumps({}, ensure_ascii=False),
                )
            )
        if inserts:
            executemany(
                conn,
                "INSERT INTO trade_job_schedule (domain, enabled, cron, timezone, mode, params_json) VALUES (%s,%s,%s,%s,%s,%s)",
                inserts,
            )
    finally:
        conn.close()


def _scheduler_available() -> bool:
    return _SCHEDULER is not None


def _reschedule_all() -> None:
    if _SCHEDULER is None:
        return
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(conn, "SELECT domain, enabled, cron, timezone, mode, params_json FROM trade_job_schedule")
    finally:
        conn.close()

    for job in _SCHEDULER.get_jobs():
        _SCHEDULER.remove_job(job.id)

    try:
        from apscheduler.triggers.cron import CronTrigger
    except Exception:
        return

    for r in rows:
        if int(r.get("enabled") or 0) != 1:
            continue
        domain = str(r.get("domain") or "").strip()
        if not domain or domain not in _KNOWN_JOB_DOMAINS:
            continue
        cron = str(r.get("cron") or "").strip()
        try:
            minute, hour, day, month, dow, year = _parse_cron(cron)
        except Exception:
            continue
        tz = str(r.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai"
        mode = str(r.get("mode") or "").strip() or None
        params: dict[str, Any] | None = None
        try:
            raw = r.get("params_json") or ""
            obj = json.loads(raw) if raw else {}
            params = obj if isinstance(obj, dict) else None
        except Exception:
            params = None
        kw: dict[str, Any] = {"minute": minute, "hour": hour, "day": day, "month": month, "day_of_week": dow, "timezone": tz}
        if year is not None:
            kw["year"] = year
        trigger = CronTrigger(**kw)
        _SCHEDULER.add_job(
            _enqueue_domain,
            trigger=trigger,
            id=_schedule_job_id(domain),
            args=[domain, mode, params],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("任务注册", extra={
            "domain": domain,
            "cron": cron,
            "timezone": tz,
            "mode": mode
        })


def _enqueue_domain(domain: str, mode: str | None, params: dict[str, Any] | None) -> None:
    lk = _LOCKS.get(domain)
    if lk is None:
        logger.warning("任务并发限制", extra={
            "domain": domain,
            "reason": "lock not found"
        })
        return
    if not lk.acquire(blocking=False):
        logger.warning("任务并发限制", extra={
            "domain": domain,
            "reason": "previous running"
        })
        return
    try:
        run = write_job_run(
            domain=domain,
            payload={
                "runId": "",
                "domain": domain,
                "status": "running",
                "startedAt": _now_iso(),
                "mode": mode,
                "params": params or {},
            },
        )
        run_id = str(run.get("runId") or "").strip()
        started_at = str(run.get("startedAt") or "").strip()
        logger.info("任务入队", extra={
            "run_id": run_id,
            "domain": domain,
            "mode": mode
        })
        _run_job_impl(run_id=run_id, started_at=started_at, domain=domain, mode=mode, params=params or {})
    finally:
        lk.release()


def init_jobs_scheduler() -> None:
    global _SCHEDULER, _SCHEDULER_ERROR
    if _SCHEDULER is not None or _SCHEDULER_ERROR is not None:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _SCHEDULER = BackgroundScheduler()
        logger.info("APScheduler 初始化成功", extra={
            "scheduler_type": "BackgroundScheduler"
        })
    except Exception as e:
        _SCHEDULER = None
        _SCHEDULER_ERROR = f"{type(e).__name__}: {e}"
        logger.error("APScheduler 初始化失败", extra={
            "error": _SCHEDULER_ERROR
        })


def start_jobs_scheduler() -> None:
    init_jobs_scheduler()
    if _SCHEDULER is None:
        logger.warning("任务调度器未初始化，跳过启动", extra={
            "error": _SCHEDULER_ERROR
        })
        return
    if not _SCHEDULER.running:
        _ensure_default_schedules()
        _reschedule_all()
        _SCHEDULER.start()
        jobs_count = len(_KNOWN_JOB_DOMAINS)
        logger.info("任务调度器启动成功", extra={
            "jobs_count": jobs_count,
            "domains": list(_KNOWN_JOB_DOMAINS)
        })


def stop_jobs_scheduler() -> None:
    if _SCHEDULER is None:
        return
    if _SCHEDULER.running:
        jobs_count = len(_KNOWN_JOB_DOMAINS)
        _SCHEDULER.shutdown(wait=False)
        logger.info("任务调度器关闭成功", extra={
            "jobs_count": jobs_count
        })


def _run_job_impl(*, run_id: str, started_at: str, domain: str, mode: str | None, params: dict[str, Any]) -> None:
    logger.info("任务执行开始", extra={
        "run_id": run_id,
        "domain": domain,
        "mode": mode,
        "started_at": started_at
    })
    try:
        stats = run_domain(domain, mode, params)
        status = "success" if not stats.failed_items else "partial"
        write_job_run(
            domain=domain,
            payload={
                "runId": run_id,
                "domain": domain,
                "startedAt": started_at,
                "finishedAt": _now_iso(),
                "status": status,
                "dataSourceFinal": stats.data_source_final,
                "fallbackChain": list(stats.fallback_chain),
                "rowsWritten": int(stats.rows_written or 0),
                "itemsProcessed": int(stats.items_processed or 0),
                "failedItems": list(stats.failed_items or []),
                "message": stats.message,
                "params": params,
            },
        )
        logger.info("任务执行成功", extra={
            "run_id": run_id,
            "domain": domain,
            "status": status,
            "rows_written": int(stats.rows_written or 0),
            "items_processed": int(stats.items_processed or 0),
            "failed_items": len(stats.failed_items or [])
        })
    except Exception as e:
        logger.error("任务执行失败", extra={
            "run_id": run_id,
            "domain": domain,
            "error": str(e),
            "error_type": type(e).__name__
        })
        write_job_run(
            domain=domain,
            payload={
                "runId": run_id,
                "domain": domain,
                "startedAt": started_at,
                "finishedAt": _now_iso(),
                "status": "failed",
                "dataSourceFinal": "unknown",
                "fallbackChain": [],
                "rowsWritten": 0,
                "itemsProcessed": 0,
                "failedItems": [],
                "message": f"{type(e).__name__}: {e}",
                "params": params,
            },
        )


@router.get("/runs")
def list_runs(limit: int = 10, domain: str | None = None) -> dict[str, object]:
    """
    查询任务执行历史
    
    获取最近的任务执行记录，支持按任务域过滤和超时检测
    
    Args:
        limit: 返回记录数量上限，默认为10
        domain: 可选的任务域过滤器
        
    Returns:
        dict: 包含任务执行记录列表
    """
    runs = list_job_runs(domain=domain, limit=limit)
    
    # 从环境变量读取任务超时时间，默认900秒（15分钟）
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
        
        # 检测长时间运行但未完成的任务，自动标记为失败
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


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    from src.backend..data import read_job_run

    rid = str(run_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="run_id required")
    obj = read_job_run(rid)
    if not obj:
        raise HTTPException(status_code=404, detail="run not found")
    return obj


@router.post("/runs")
def write_run(body: dict[str, Any]) -> dict[str, Any]:
    """
    创建新的任务执行记录
    
    在Charles服务中创建任务运行记录，用于跟踪任务执行状态
    
    Args:
        body: 任务配置信息，包含domain等字段
        
    Returns:
        dict: 包含创建的任务记录
    """
    domain = str(body.get("domain") or "").strip()
    if domain not in _KNOWN_JOB_DOMAINS:
        raise HTTPException(status_code=400, detail="unknown domain")
    try:
        run = write_job_run(domain=domain, payload=body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run": run}


@router.post("/run")
def run_job_once(body: dict[str, Any], bg: BackgroundTasks) -> dict[str, Any]:
    """
    兼容旧版单次运行接口

    前端历史版本使用 /api/jobs/run，这里保持兼容并复用 runs 写入逻辑。
    """
    domain = str(body.get("domain") or "").strip()
    if domain not in _KNOWN_JOB_DOMAINS:
        raise HTTPException(status_code=400, detail="unknown domain")
    mode = str(body.get("mode") or "").strip() or "test"
    params = body.get("params") if isinstance(body.get("params"), dict) else {}

    run = write_job_run(
        domain=domain,
        payload={
            "domain": domain,
            "status": "running",
            "startedAt": _now_iso(),
            "mode": mode,
            "params": params,
        },
    )
    run_id = str(run.get("runId") or "").strip()
    started_at = str(run.get("startedAt") or "").strip()
    bg.add_task(_run_job_impl, run_id=run_id, started_at=started_at, domain=domain, mode=mode, params=params)
    return {"ok": True, "result": run}


@router.get("/domains")
def list_domains() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for d in sorted(_KNOWN_JOB_DOMAINS):
        meta = _DOMAIN_META.get(d) or {}
        items.append(
            {
                "domain": d,
                "title": meta.get("title") or d,
                "desc": meta.get("desc") or "",
                "defaultMode": meta.get("defaultMode") or None,
            }
        )
    return {"domains": items}


@router.get("/schedules")
def list_schedules() -> dict[str, object]:
    """
    查询所有定时调度配置
    
    返回所有已注册任务的调度策略，包括最近执行时间和状态
    
    Returns:
        dict: 包含调度配置列表
    """
    _ensure_default_schedules()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(conn, "SELECT domain, enabled, cron, timezone, mode, updated_at FROM trade_job_schedule ORDER BY domain")
    finally:
        conn.close()

    items: list[dict[str, Any]] = []
    for r in rows:
        domain = str(r.get("domain") or "")
        if not domain:
            continue
        latest = list_job_runs(domain=domain, limit=1)
        last = latest[0] if latest else None
        next_run = None
        if _SCHEDULER is not None:
            try:
                j = _SCHEDULER.get_job(_schedule_job_id(domain))
                if j and j.next_run_time:
                    next_run = j.next_run_time.isoformat()
            except Exception:
                next_run = None
        updated_at = r.get("updated_at")
        items.append(
            {
                "domain": domain,
                "enabled": bool(int(r.get("enabled") or 0) == 1),
                "cron": str(r.get("cron") or ""),
                "timezone": str(r.get("timezone") or "Asia/Shanghai"),
                "mode": r.get("mode"),
                "nextRunAt": next_run,
                "lastRunAt": last.get("startedAt") if last else None,
                "lastStatus": last.get("status") if last else None,
                "updatedAt": (updated_at.isoformat() if hasattr(updated_at, "isoformat") else None),
            }
        )
    return {"schedules": items}


@router.put("/schedules/{domain}")
def update_schedule(domain: str, body: dict[str, object]) -> dict[str, object]:
    """
    更新任务的定时调度配置
    
    修改指定任务域的调度规则，包括Cron表达式、时区和启用状态
    
    Args:
        domain: 任务域名称
        body: 新的调度配置，包含cron、timezone、enabled等字段
        
    Returns:
        dict: 操作结果
    """
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
    _ensure_job_schedule_table()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        execute(
            conn,
            """
            INSERT INTO trade_job_schedule (domain, enabled, cron, timezone, mode, params_json)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              enabled=VALUES(enabled),
              cron=VALUES(cron),
              timezone=VALUES(timezone),
              mode=VALUES(mode)
            """,
            (domain, 1 if enabled else 0, cron, timezone, mode, json.dumps({}, ensure_ascii=False)),
        )
    finally:
        conn.close()
    if _SCHEDULER is not None:
        _reschedule_all()
    return {"ok": True}
