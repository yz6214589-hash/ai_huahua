from __future__ import annotations

import csv
import io
import json
import os
import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .config import load_settings
from .db import MySQLConfig, connect, execute, executemany, query_dict
from .job_store import init_running, list_runs, read_run, write_run
from .models import ExportRequest, JobDomain, JobRunRequest, JobRunResult
from .jobs.calendar import run_calendar
from .jobs.catalyst import run_catalyst
from .jobs.macro_indicator import run_macro_indicator
from .jobs.rate_daily import run_rate_daily
from .jobs.report_consensus import run_report_consensus
from .jobs.sentiment_monitor import run_sentiment_monitor
from .jobs.stock_daily import run_stock_daily
from .jobs.stock_financial import run_stock_financial
from .jobs.stock_news import run_stock_news


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app() -> FastAPI:
    settings = load_settings()

    app = FastAPI(title="Charles API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    mysql_cfg = MySQLConfig(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_db,
    )

    job_store_dir = settings.job_store_dir

    def _ensure_stock_master_table() -> None:
        conn = connect(mysql_cfg)
        try:
            execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS trade_stock_master (
                  stock_code varchar(20) NOT NULL,
                  stock_name varchar(100) DEFAULT NULL,
                  source varchar(20) DEFAULT 'akshare',
                  updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (stock_code),
                  KEY idx_stock_master_name (stock_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            conn.commit()
        finally:
            conn.close()

    _ensure_stock_master_table()

    def _ensure_watchlist_table() -> None:
        conn = connect(mysql_cfg)
        try:
            execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS trade_watchlist (
                  id int(11) NOT NULL AUTO_INCREMENT,
                  stock_code varchar(20) NOT NULL,
                  pinned tinyint(1) NOT NULL DEFAULT 0,
                  sort_order int(11) NOT NULL DEFAULT 0,
                  created_at datetime DEFAULT CURRENT_TIMESTAMP,
                  updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY idx_watchlist_code (stock_code),
                  KEY idx_watchlist_sort (pinned, sort_order, updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            conn.commit()
        finally:
            conn.close()

    def _ensure_report_task_table() -> None:
        conn = connect(mysql_cfg)
        try:
            execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS trade_report_task (
                  task_id varchar(32) NOT NULL,
                  model varchar(32) NOT NULL,
                  stock_codes_json text NOT NULL,
                  stock_names_json text,
                  status varchar(16) NOT NULL,
                  created_at datetime DEFAULT CURRENT_TIMESTAMP,
                  started_at datetime DEFAULT NULL,
                  finished_at datetime DEFAULT NULL,
                  error_message text,
                  report_markdown longtext,
                  PRIMARY KEY (task_id),
                  KEY idx_report_task_created (created_at),
                  KEY idx_report_task_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            conn.commit()
        finally:
            conn.close()

    def _ensure_sentiment_tables() -> None:
        conn = connect(mysql_cfg)
        try:
            execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS trade_sentiment_run (
                  run_id varchar(32) NOT NULL,
                  trigger_type varchar(16) NOT NULL,
                  stock_codes_json text NOT NULL,
                  stock_names_json text,
                  days int NOT NULL DEFAULT 3,
                  use_llm tinyint(1) NOT NULL DEFAULT 0,
                  status varchar(16) NOT NULL,
                  total_events int NOT NULL DEFAULT 0,
                  created_at datetime DEFAULT CURRENT_TIMESTAMP,
                  started_at datetime DEFAULT NULL,
                  finished_at datetime DEFAULT NULL,
                  error_message text,
                  PRIMARY KEY (run_id),
                  KEY idx_sent_run_created (created_at),
                  KEY idx_sent_run_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS trade_sentiment_event (
                  id int(11) NOT NULL AUTO_INCREMENT,
                  run_id varchar(32) NOT NULL,
                  stock_code varchar(20) NOT NULL,
                  stock_name varchar(100) DEFAULT NULL,
                  source_type varchar(16) NOT NULL,
                  source_title varchar(255) DEFAULT NULL,
                  source_url text,
                  published_at datetime DEFAULT NULL,
                  event_type varchar(16) NOT NULL,
                  event_category varchar(64) NOT NULL,
                  signal_action varchar(32) NOT NULL,
                  signal_reason varchar(255) DEFAULT NULL,
                  impact varchar(255) DEFAULT NULL,
                  confidence tinyint(1) NOT NULL DEFAULT 3,
                  urgency varchar(8) NOT NULL DEFAULT '中',
                  created_at datetime DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  KEY idx_sent_evt_run (run_id),
                  KEY idx_sent_evt_stock (stock_code),
                  KEY idx_sent_evt_type (event_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS trade_sentiment_news (
                  id int(11) NOT NULL AUTO_INCREMENT,
                  run_id varchar(32) NOT NULL,
                  stock_code varchar(20) NOT NULL,
                  stock_name varchar(100) DEFAULT NULL,
                  source_type varchar(16) NOT NULL,
                  title varchar(255) DEFAULT NULL,
                  url text,
                  published_at datetime DEFAULT NULL,
                  content longtext,
                  sentiment varchar(16) DEFAULT NULL,
                  strength tinyint(1) DEFAULT NULL,
                  summary text,
                  market_impact text,
                  created_at datetime DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  KEY idx_sent_news_run (run_id),
                  KEY idx_sent_news_stock (stock_code),
                  KEY idx_sent_news_pub (published_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            )
            conn.commit()
        finally:
            conn.close()

    def _ensure_job_schedule_table() -> None:
        conn = connect(mysql_cfg)
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
            conn.commit()
        finally:
            conn.close()

    def _ensure_default_schedules() -> None:
        defaults: dict[str, tuple[str, str, str, dict[str, Any] | None]] = {
            "stock_daily": ("0 18 * * 1-5", "Asia/Shanghai", "full", None),
            "stock_financial": ("30 19 * * 6", "Asia/Shanghai", "full", None),
            "stock_news": ("*/10 * * * *", "Asia/Shanghai", "full", None),
            "macro_indicator": ("0 9 1 * *", "Asia/Shanghai", "full", None),
            "rate_daily": ("0 8 * * 1-5", "Asia/Shanghai", "full", None),
            "calendar": ("0 7 * * *", "Asia/Shanghai", "full", None),
            "report_consensus": ("0 20 * * 1-5", "Asia/Shanghai", "full", None),
            "catalyst": ("0 21 * * 0", "Asia/Shanghai", "full", None),
            "sentiment_monitor": ("10 15 * * 1-5", "Asia/Shanghai", "full", {"days": 3, "use_llm": False}),
        }
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT domain FROM trade_job_schedule")
            existing = {str(r.get("domain")) for r in rows if r.get("domain")}
            inserts: list[tuple[Any, ...]] = []
            for d, (cron, tz, mode, params) in defaults.items():
                if d in existing:
                    continue
                inserts.append((d, 1, cron, tz, mode, json.dumps(params or {}, ensure_ascii=False)))
            if inserts:
                executemany(
                    conn,
                    "INSERT INTO trade_job_schedule (domain, enabled, cron, timezone, mode, params_json) VALUES (%s,%s,%s,%s,%s,%s)",
                    inserts,
                )
                conn.commit()
        finally:
            conn.close()

    _ensure_job_schedule_table()
    _ensure_default_schedules()
    _ensure_watchlist_table()
    _ensure_report_task_table()
    _ensure_sentiment_tables()

    scheduler_error: str | None = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()
    except Exception as e:
        scheduler = None
        scheduler_error = f"{type(e).__name__}: {e}"

    locks: dict[str, threading.Lock] = {d.value: threading.Lock() for d in JobDomain}
    app.state.scheduler = scheduler
    app.state.scheduler_error = scheduler_error

    def _schedule_job_id(domain: str) -> str:
        return f"job:{domain}"

    def _parse_cron(expr: str) -> tuple[str, str, str, str, str, str | None]:
        parts = [p for p in (expr or "").strip().split() if p]
        if len(parts) not in (5, 6):
            raise ValueError("cron must be 5 or 6 parts: min hour day month dow [year]")
        if len(parts) == 5:
            return parts[0], parts[1], parts[2], parts[3], parts[4], None
        return parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]

    def _enqueue_domain(domain: JobDomain, mode: str | None, params: dict[str, Any] | None) -> None:
        key = domain.value
        lk = locks[key]
        if not lk.acquire(blocking=False):
            return
        try:
            run = init_running(domain)
            write_run(job_store_dir, run)
            _run_job(run, JobRunRequest(domain=domain, mode=mode, params=params))
        finally:
            lk.release()

    def _reschedule_all() -> None:
        if scheduler is None:
            return
        for job in scheduler.get_jobs():
            scheduler.remove_job(job.id)
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT domain, enabled, cron, timezone, mode, params_json FROM trade_job_schedule")
        finally:
            conn.close()
        for r in rows:
            if int(r.get("enabled") or 0) != 1:
                continue
            domain = str(r.get("domain") or "")
            if not domain:
                continue
            try:
                minute, hour, day, month, dow, year = _parse_cron(str(r.get("cron") or ""))
            except Exception:
                continue
            tz = str(r.get("timezone") or "Asia/Shanghai")
            mode = r.get("mode")
            params: dict[str, Any] | None = None
            try:
                raw = r.get("params_json") or ""
                obj = json.loads(raw) if raw else {}
                params = obj if isinstance(obj, dict) else None
            except Exception:
                params = None
            try:
                dom = JobDomain(domain)
            except Exception:
                continue
            kw: dict[str, Any] = {"minute": minute, "hour": hour, "day": day, "month": month, "day_of_week": dow, "timezone": tz}
            if year is not None:
                kw["year"] = year
            trigger = CronTrigger(**kw)
            scheduler.add_job(
                _enqueue_domain,
                trigger=trigger,
                id=_schedule_job_id(domain),
                args=[dom, str(mode) if mode else None, params],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

    @app.on_event("startup")
    def _start_scheduler() -> None:
        if scheduler is None:
            return
        if not scheduler.running:
            _reschedule_all()
            scheduler.start()

    @app.on_event("shutdown")
    def _stop_scheduler() -> None:
        if scheduler is None:
            return
        if scheduler.running:
            scheduler.shutdown(wait=False)

    def _run_job(run: JobRunResult, req: JobRunRequest) -> None:
        try:
            if req.domain == JobDomain.stock_daily:
                stats = run_stock_daily(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.stock_financial:
                stats = run_stock_financial(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.stock_news:
                stats = run_stock_news(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.macro_indicator:
                stats = run_macro_indicator(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.rate_daily:
                stats = run_rate_daily(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.calendar:
                stats = run_calendar(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.catalyst:
                stats = run_catalyst(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.report_consensus:
                stats = run_report_consensus(mysql_cfg, req.mode, req.params)
            elif req.domain == JobDomain.sentiment_monitor:
                stats = run_sentiment_monitor(mysql_cfg, req.mode, req.params)
            else:
                raise RuntimeError("unknown domain")

            finished = run.model_copy(
                update={
                    "finishedAt": _now_iso(),
                    "status": "success" if not stats.failed_items else "partial",
                    "dataSourceFinal": stats.data_source_final,
                    "fallbackChain": stats.fallback_chain,
                    "rowsWritten": stats.rows_written,
                    "itemsProcessed": stats.items_processed,
                    "failedItems": stats.failed_items,
                    "message": stats.message,
                }
            )
            write_run(job_store_dir, finished)
        except Exception as e:
            failed = run.model_copy(update={"finishedAt": _now_iso(), "status": "failed", "message": f"{type(e).__name__}: {e}"})
            write_run(job_store_dir, failed)

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "name": "Charles API",
            "ok": True,
            "health": "/api/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        try:
            conn = connect(mysql_cfg)
        except Exception as e:
            return {"ok": True, "db": False, "detail": f"{type(e).__name__}: {e}"}
        try:
            rows = query_dict(conn, "SELECT 1 AS ok")
            return {"ok": True, "db": bool(rows and rows[0].get("ok") == 1)}
        finally:
            conn.close()

    @app.get("/api/summary")
    def summary() -> dict[str, Any]:
        try:
            conn = connect(mysql_cfg)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"db unavailable: {type(e).__name__}: {e}")
        try:
            def safe(sql: str) -> list[dict[str, Any]]:
                try:
                    return query_dict(conn, sql)
                except Exception as e:
                    code = None
                    try:
                        code = int((getattr(e, "args", [None]) or [None])[0])
                    except Exception:
                        code = None
                    if code in (1146, 1051):
                        return [{"d": None, "c": 0}]
                    raise

            daily = safe("SELECT MAX(trade_date) AS d, COUNT(*) AS c FROM trade_stock_daily")
            fin = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_stock_financial")
            news = safe("SELECT MAX(published_at) AS d, COUNT(*) AS c FROM trade_stock_news")
            macro = safe("SELECT MAX(indicator_date) AS d, COUNT(*) AS c FROM trade_macro_indicator")
            rate = safe("SELECT MAX(rate_date) AS d, COUNT(*) AS c FROM trade_rate_daily")
            report = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_report_consensus")
            cal = safe("SELECT MAX(event_date) AS d, COUNT(*) AS c FROM trade_calendar_event")

            def pack(x):
                row = (x or [{}])[0]
                return {"latest": row.get("d"), "count": int(row.get("c") or 0)}

            return {
                "trade_stock_daily": pack(daily),
                "trade_stock_financial": pack(fin),
                "trade_stock_news": pack(news),
                "trade_macro_indicator": pack(macro),
                "trade_rate_daily": pack(rate),
                "trade_report_consensus": pack(report),
                "trade_calendar_event": pack(cal),
            }
        finally:
            conn.close()

    @app.post("/api/jobs/run")
    def jobs_run(req: JobRunRequest, bg: BackgroundTasks) -> dict[str, Any]:
        run = init_running(req.domain)
        write_run(job_store_dir, run)
        bg.add_task(_run_job, run, req)
        return {"result": run.model_dump()}

    @app.get("/api/jobs/runs")
    def jobs_runs(domain: str | None = None, limit: int = 50) -> dict[str, Any]:
        d = JobDomain(domain) if domain else None
        return {"runs": list_runs(job_store_dir, d, min(max(limit, 1), 200))}

    @app.get("/api/jobs/runs/{run_id}")
    def jobs_run_get(run_id: str) -> dict[str, Any]:
        obj = read_run(job_store_dir, run_id)
        if not obj:
            raise HTTPException(status_code=404, detail="run not found")
        return obj

    @app.get("/api/jobs/schedules")
    def jobs_schedules() -> dict[str, Any]:
        if scheduler is None:
            raise HTTPException(status_code=503, detail=f"scheduler unavailable: {scheduler_error}")
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT domain, enabled, cron, timezone, mode, params_json, updated_at FROM trade_job_schedule ORDER BY domain")
        finally:
            conn.close()
        out: list[dict[str, Any]] = []
        for r in rows:
            domain = str(r.get("domain") or "")
            next_run = None
            try:
                j = scheduler.get_job(_schedule_job_id(domain))
                if j and j.next_run_time:
                    next_run = j.next_run_time.isoformat()
            except Exception:
                next_run = None
            last = list_runs(job_store_dir, JobDomain(domain), 1) if domain else []
            last_run = last[0] if last else None
            out.append(
                {
                    "domain": domain,
                    "enabled": bool(int(r.get("enabled") or 0) == 1),
                    "cron": r.get("cron"),
                    "timezone": r.get("timezone"),
                    "mode": r.get("mode"),
                    "nextRunAt": next_run,
                    "lastRunAt": last_run.get("startedAt") if last_run else None,
                    "lastStatus": last_run.get("status") if last_run else None,
                    "updatedAt": (r.get("updated_at").isoformat() if r.get("updated_at") else None),
                }
            )
        return {"schedules": out}

    @app.put("/api/jobs/schedules/{domain}")
    def jobs_schedule_update(domain: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            d = JobDomain(domain)
        except Exception:
            raise HTTPException(status_code=400, detail="unknown domain")
        enabled = 1 if bool(body.get("enabled", True)) else 0
        cron = str(body.get("cron") or "").strip()
        timezone = str(body.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai"
        mode = body.get("mode")
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        try:
            _parse_cron(cron)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        conn = connect(mysql_cfg)
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
                  mode=VALUES(mode),
                  params_json=VALUES(params_json)
                """,
                (d.value, enabled, cron, timezone, mode, json.dumps(params, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
        _reschedule_all()
        return {"ok": True}

    def _report_task_row_to_obj(r: dict[str, Any]) -> dict[str, Any]:
        try:
            stock_codes = json.loads(str(r.get("stock_codes_json") or "[]"))
        except Exception:
            stock_codes = []
        try:
            stock_names = json.loads(str(r.get("stock_names_json") or "[]")) if r.get("stock_names_json") else []
        except Exception:
            stock_names = []
        created_at = r.get("created_at")
        started_at = r.get("started_at")
        finished_at = r.get("finished_at")
        return {
            "task_id": str(r.get("task_id") or ""),
            "model": str(r.get("model") or ""),
            "stock_codes": stock_codes if isinstance(stock_codes, list) else [],
            "stock_names": stock_names if isinstance(stock_names, list) else [],
            "status": str(r.get("status") or ""),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else None,
            "started_at": started_at.isoformat() if hasattr(started_at, "isoformat") else None,
            "finished_at": finished_at.isoformat() if hasattr(finished_at, "isoformat") else None,
            "error_message": r.get("error_message"),
        }

    def _report_disable_bg() -> bool:
        return str(os.getenv("CHARLES_REPORT_DISABLE_BG") or "").strip() == "1"

    @app.post("/api/reports/tasks")
    def report_task_create(body: dict[str, Any], bg: BackgroundTasks) -> dict[str, Any]:
        model = str(body.get("model") or "").strip()
        if model not in ("qwen-max", "deepseek"):
            raise HTTPException(status_code=400, detail="model must be qwen-max/deepseek")
        raw_codes = body.get("stock_codes")
        if not isinstance(raw_codes, list) or not raw_codes:
            raise HTTPException(status_code=400, detail="stock_codes required")
        stock_codes = [_normalize_stock_code(str(c)) for c in raw_codes if str(c).strip()]
        stock_codes = [c for c in stock_codes if c]
        if not stock_codes:
            raise HTTPException(status_code=400, detail="stock_codes required")
        stock_names = [(_get_stock_name(c) or "") for c in stock_codes]

        task_id = uuid4().hex
        conn = connect(mysql_cfg)
        try:
            execute(
                conn,
                """
                INSERT INTO trade_report_task
                  (task_id, model, stock_codes_json, stock_names_json, status, created_at)
                VALUES
                  (%s,%s,%s,%s,%s,NOW())
                """,
                (
                    task_id,
                    model,
                    json.dumps(stock_codes, ensure_ascii=False),
                    json.dumps(stock_names, ensure_ascii=False),
                    "waiting",
                ),
            )
            conn.commit()
            rows = query_dict(conn, "SELECT * FROM trade_report_task WHERE task_id=%s", (task_id,))
            if not rows:
                raise HTTPException(status_code=500, detail="create failed")
            task = _report_task_row_to_obj(rows[0])
        finally:
            conn.close()

        if not _report_disable_bg():
            try:
                from .reports.generator import run_report_task

                bg.add_task(run_report_task, mysql_cfg, task_id, str(os.getcwd()))
            except Exception as e:
                conn2 = connect(mysql_cfg)
                try:
                    execute(
                        conn2,
                        "UPDATE trade_report_task SET status=%s, finished_at=NOW(), error_message=%s WHERE task_id=%s",
                        ("failed", f"{type(e).__name__}: {e}", task_id),
                    )
                    conn2.commit()
                finally:
                    conn2.close()

        return {"task": task}

    @app.get("/api/reports/tasks")
    def report_task_list(
        q: str | None = None,
        created_start: str | None = None,
        created_end: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        limit = min(max(int(limit or 100), 1), 200)
        q = (q or "").strip()
        created_start = (created_start or "").strip()
        created_end = (created_end or "").strip()
        where: list[str] = []
        params: list[Any] = []
        if q:
            like = f"%{q}%"
            where.append("(stock_codes_json LIKE %s OR stock_names_json LIKE %s)")
            params.extend([like, like])
        if created_start:
            where.append("created_at >= %s")
            params.append(created_start)
        if created_end:
            where.append("created_at <= %s")
            params.append(f"{created_end} 23:59:59")
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, f"SELECT * FROM trade_report_task{where_sql} ORDER BY created_at DESC LIMIT %s", tuple(params + [limit]))
            return {"tasks": [_report_task_row_to_obj(r) for r in (rows or [])]}
        finally:
            conn.close()

    @app.get("/api/reports/tasks/{task_id}")
    def report_task_get(task_id: str) -> dict[str, Any]:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT * FROM trade_report_task WHERE task_id=%s", (task_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="task not found")
            return {"task": _report_task_row_to_obj(rows[0])}
        finally:
            conn.close()

    @app.delete("/api/reports/tasks/{task_id}")
    def report_task_delete(task_id: str) -> dict[str, Any]:
        conn = connect(mysql_cfg)
        try:
            execute(conn, "DELETE FROM trade_report_task WHERE task_id=%s", (task_id,))
            conn.commit()
            return {"ok": True}
        finally:
            conn.close()

    @app.get("/api/reports/tasks/{task_id}/view")
    def report_task_view(task_id: str) -> Response:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT report_markdown, status, error_message FROM trade_report_task WHERE task_id=%s", (task_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="task not found")
            r = rows[0]
        finally:
            conn.close()

        md_text = str(r.get("report_markdown") or "")
        if not md_text:
            st = str(r.get("status") or "")
            err = str(r.get("error_message") or "")
            md_text = f"# 研报尚未生成\n\n状态：{st}\n\n{err}"

        try:
            import markdown as _md

            body = _md.markdown(md_text, extensions=["tables", "fenced_code"])
        except Exception:
            body = "<pre>" + md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre>"

        html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Report {task_id}</title>
    <style>
      body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;padding:24px;max-width:980px;margin:0 auto;}}
      pre,code{{background:#f4f4f5;}}
      pre{{padding:12px;overflow:auto;}}
      table{{border-collapse:collapse;width:100%;}}
      th,td{{border:1px solid #e4e4e7;padding:6px 8px;}}
    </style>
  </head>
  <body>{body}</body>
</html>"""
        return HTMLResponse(content=html)

    def _sentiment_disable_bg() -> bool:
        return str(os.getenv("CHARLES_SENTIMENT_DISABLE_BG") or "").strip() == "1"

    def _sentiment_run_row_to_obj(r: dict[str, Any]) -> dict[str, Any]:
        try:
            stock_codes = json.loads(str(r.get("stock_codes_json") or "[]"))
        except Exception:
            stock_codes = []
        try:
            stock_names = json.loads(str(r.get("stock_names_json") or "[]")) if r.get("stock_names_json") else []
        except Exception:
            stock_names = []
        created_at = r.get("created_at")
        started_at = r.get("started_at")
        finished_at = r.get("finished_at")
        return {
            "run_id": str(r.get("run_id") or ""),
            "trigger": str(r.get("trigger_type") or ""),
            "stock_codes": stock_codes if isinstance(stock_codes, list) else [],
            "stock_names": stock_names if isinstance(stock_names, list) else [],
            "days": int(r.get("days") or 3),
            "use_llm": bool(int(r.get("use_llm") or 0) == 1),
            "status": str(r.get("status") or ""),
            "total_events": int(r.get("total_events") or 0),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else None,
            "started_at": started_at.isoformat() if hasattr(started_at, "isoformat") else None,
            "finished_at": finished_at.isoformat() if hasattr(finished_at, "isoformat") else None,
            "error_message": r.get("error_message"),
        }

    def _sentiment_event_row_to_obj(r: dict[str, Any]) -> dict[str, Any]:
        published = r.get("published_at")
        return {
            "id": int(r.get("id") or 0),
            "run_id": str(r.get("run_id") or ""),
            "stock_code": str(r.get("stock_code") or ""),
            "stock_name": str(r.get("stock_name") or ""),
            "source_type": str(r.get("source_type") or ""),
            "source_title": str(r.get("source_title") or ""),
            "source_url": r.get("source_url"),
            "published_at": published.isoformat() if hasattr(published, "isoformat") else None,
            "event_type": str(r.get("event_type") or ""),
            "event_category": str(r.get("event_category") or ""),
            "signal": str(r.get("signal_action") or ""),
            "signal_reason": r.get("signal_reason"),
            "impact": r.get("impact"),
            "confidence": int(r.get("confidence") or 0),
            "urgency": str(r.get("urgency") or ""),
        }

    def _sentiment_default_cron() -> str:
        return "10 15 * * 1-5"

    def _sentiment_get_schedule() -> dict[str, Any]:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT domain, enabled, cron, timezone, mode, params_json FROM trade_job_schedule WHERE domain=%s",
                ("sentiment_monitor",),
            )
            row = None
            if rows:
                row = next((x for x in rows if str(x.get("domain") or "") == "sentiment_monitor"), None)
            if not row:
                return {"domain": "sentiment_monitor", "enabled": True, "cron": _sentiment_default_cron(), "timezone": "Asia/Shanghai"}
            r = row
            return {
                "domain": "sentiment_monitor",
                "enabled": int(r.get("enabled") or 0) == 1,
                "cron": str(r.get("cron") or _sentiment_default_cron()),
                "timezone": str(r.get("timezone") or "Asia/Shanghai"),
            }
        finally:
            conn.close()

    @app.get("/api/sentiment/schedule")
    def sentiment_schedule_get() -> dict[str, Any]:
        return _sentiment_get_schedule()

    @app.put("/api/sentiment/schedule")
    def sentiment_schedule_put(body: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(body.get("enabled") is True)
        cron = str(body.get("cron") or _sentiment_default_cron()).strip() or _sentiment_default_cron()
        timezone = str(body.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai"
        try:
            _parse_cron(cron)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        conn = connect(mysql_cfg)
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
                  mode=VALUES(mode),
                  params_json=VALUES(params_json)
                """,
                ("sentiment_monitor", 1 if enabled else 0, cron, timezone, "full", json.dumps({"days": 3, "use_llm": False}, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
        _reschedule_all()
        return {"ok": True}

    @app.post("/api/sentiment/runs")
    def sentiment_run_create(body: dict[str, Any], bg: BackgroundTasks) -> dict[str, Any]:
        days = int(body.get("days") or 3)
        days = max(1, min(days, 30))
        use_llm = bool(body.get("use_llm") is True)
        raw_codes = body.get("stock_codes")
        stock_codes: list[str] = []
        stock_names: list[str] = []
        trigger = "manual_watchlist"

        if isinstance(raw_codes, list) and raw_codes:
            trigger = "manual_selected"
            stock_codes = [_normalize_stock_code(str(c)) for c in raw_codes if str(c).strip()]
            stock_codes = [c for c in stock_codes if c]
            stock_names = [(_get_stock_name(c) or "") for c in stock_codes]
        else:
            conn = connect(mysql_cfg)
            try:
                rows = query_dict(conn, "SELECT stock_code FROM trade_watchlist ORDER BY pinned DESC, sort_order ASC, updated_at DESC", ())
                stock_codes = [str(r.get("stock_code") or "") for r in rows if r.get("stock_code")]
                stock_names = [(_get_stock_name(c) or "") for c in stock_codes]
            finally:
                conn.close()

        if not stock_codes:
            raise HTTPException(status_code=400, detail="no stocks")

        run_id = uuid4().hex
        conn2 = connect(mysql_cfg)
        try:
            execute(
                conn2,
                """
                INSERT INTO trade_sentiment_run
                  (run_id, trigger_type, stock_codes_json, stock_names_json, days, use_llm, status, created_at)
                VALUES
                  (%s,%s,%s,%s,%s,%s,%s,NOW())
                """,
                (
                    run_id,
                    trigger,
                    json.dumps(stock_codes, ensure_ascii=False),
                    json.dumps(stock_names, ensure_ascii=False),
                    days,
                    1 if use_llm else 0,
                    "waiting",
                ),
            )
            conn2.commit()
            rows2 = query_dict(conn2, "SELECT * FROM trade_sentiment_run WHERE run_id=%s", (run_id,))
            run = _sentiment_run_row_to_obj((rows2 or [])[0]) if rows2 else {"run_id": run_id, "status": "waiting"}
        finally:
            conn2.close()

        if not _sentiment_disable_bg():
            try:
                from .sentiment.runner import run_sentiment_run

                bg.add_task(run_sentiment_run, mysql_cfg, run_id)
            except Exception as e:
                conn3 = connect(mysql_cfg)
                try:
                    execute(
                        conn3,
                        "UPDATE trade_sentiment_run SET status=%s, finished_at=NOW(), error_message=%s WHERE run_id=%s",
                        ("failed", f"{type(e).__name__}: {e}", run_id),
                    )
                    conn3.commit()
                finally:
                    conn3.close()

        return {"run": run}

    @app.get("/api/sentiment/runs")
    def sentiment_run_list(limit: int = 50) -> dict[str, Any]:
        limit = min(max(int(limit or 50), 1), 200)
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT * FROM trade_sentiment_run ORDER BY created_at DESC LIMIT %s", (limit,))
            return {"runs": [_sentiment_run_row_to_obj(r) for r in (rows or [])]}
        finally:
            conn.close()

    @app.get("/api/sentiment/runs/{run_id}")
    def sentiment_run_get(run_id: str) -> dict[str, Any]:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT * FROM trade_sentiment_run WHERE run_id=%s", (run_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="run not found")
            run = _sentiment_run_row_to_obj(rows[0])
            events = query_dict(conn, "SELECT * FROM trade_sentiment_event WHERE run_id=%s ORDER BY published_at DESC, id DESC LIMIT 500", (run_id,))
            return {"run": run, "events": [_sentiment_event_row_to_obj(r) for r in (events or [])]}
        finally:
            conn.close()

    @app.get("/api/sentiment/stocks/{code}")
    def sentiment_stock_get(code: str, run_id: str) -> dict[str, Any]:
        stock_code = _normalize_stock_code(code)
        conn = connect(mysql_cfg)
        try:
            news_rows = query_dict(
                conn,
                "SELECT * FROM trade_sentiment_news WHERE run_id=%s AND stock_code=%s ORDER BY published_at DESC, id DESC LIMIT 200",
                (run_id, stock_code),
            )
            evt_rows = query_dict(
                conn,
                "SELECT * FROM trade_sentiment_event WHERE run_id=%s AND stock_code=%s ORDER BY published_at DESC, id DESC LIMIT 200",
                (run_id, stock_code),
            )
            news = []
            for r in news_rows or []:
                published = r.get("published_at")
                news.append(
                    {
                        "id": int(r.get("id") or 0),
                        "source_type": str(r.get("source_type") or ""),
                        "title": str(r.get("title") or ""),
                        "url": r.get("url"),
                        "published_at": published.isoformat() if hasattr(published, "isoformat") else None,
                        "content": r.get("content"),
                        "sentiment": r.get("sentiment"),
                        "strength": r.get("strength"),
                        "summary": r.get("summary"),
                        "market_impact": r.get("market_impact"),
                    }
                )
            return {"news": news, "events": [_sentiment_event_row_to_obj(r) for r in (evt_rows or [])]}
        finally:
            conn.close()

    @app.get("/api/sentiment/events")
    def sentiment_event_list(
        run_id: str | None = None,
        q: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        limit = min(max(int(limit or 200), 1), 500)
        conn = connect(mysql_cfg)
        try:
            rid = (run_id or "").strip()
            if not rid:
                rows2 = query_dict(conn, "SELECT run_id FROM trade_sentiment_run ORDER BY created_at DESC LIMIT 1")
                rid = str((rows2 or [{}])[0].get("run_id") or "") if rows2 else ""
            if not rid:
                return {"events": []}
            where: list[str] = ["run_id=%s"]
            params: list[Any] = [rid]
            qq = (q or "").strip()
            if qq:
                like = f"%{qq}%"
                where.append("(stock_code LIKE %s OR stock_name LIKE %s OR source_title LIKE %s)")
                params.extend([like, like, like])
            et = (event_type or "").strip()
            if et:
                where.append("event_type=%s")
                params.append(et)
            where_sql = " AND ".join(where)
            rows = query_dict(conn, f"SELECT * FROM trade_sentiment_event WHERE {where_sql} ORDER BY published_at DESC, id DESC LIMIT %s", tuple(params + [limit]))
            return {"events": [_sentiment_event_row_to_obj(r) for r in (rows or [])]}
        finally:
            conn.close()

    @app.get("/api/macro/latest")
    def macro_latest() -> dict[str, Any]:
        from .sentiment.macro import get_macro_latest

        return get_macro_latest()

    def _assistant_test_mode() -> bool:
        return str(os.getenv("CHARLES_ASSISTANT_TEST_MODE") or "").strip() == "1"

    def _assistant_stream_chunks(text: str, size: int = 120) -> list[str]:
        if not text:
            return []
        return [text[i : i + size] for i in range(0, len(text), size)]

    def _assistant_create_report_task(*, model: str, stock_codes: list[str]) -> dict[str, Any]:
        if model not in ("qwen-max", "deepseek"):
            raise RuntimeError("model must be qwen-max/deepseek")
        codes = [_normalize_stock_code(str(c)) for c in stock_codes if str(c).strip()]
        codes = [c for c in codes if c]
        if not codes:
            raise RuntimeError("stock_codes required")
        names = [(_get_stock_name(c) or "") for c in codes]
        task_id = uuid4().hex
        conn = connect(mysql_cfg)
        try:
            execute(
                conn,
                """
                INSERT INTO trade_report_task
                  (task_id, model, stock_codes_json, stock_names_json, status, created_at)
                VALUES
                  (%s,%s,%s,%s,%s,NOW())
                """,
                (task_id, model, json.dumps(codes, ensure_ascii=False), json.dumps(names, ensure_ascii=False), "waiting"),
            )
            conn.commit()
        finally:
            conn.close()

        if not _report_disable_bg():
            from .reports.generator import run_report_task

            def _bg() -> None:
                run_report_task(mysql_cfg, task_id, str(os.getcwd()))

            threading.Thread(target=_bg, daemon=True).start()

        return {"task_id": task_id, "model": model, "stock_codes": codes, "stock_names": names, "view_url": f"/api/reports/tasks/{task_id}/view"}

    @app.post("/api/assistant/chat_stream")
    async def assistant_chat_stream(body: dict[str, Any]) -> StreamingResponse:
        from langchain_core.tools import StructuredTool

        from .assistant.agent import build_assistant_agent
        from .assistant.sse import sse_iter

        message = str(body.get("message") or "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="message required")
        session_id = str(body.get("session_id") or uuid4().hex)
        context = body.get("context") if isinstance(body.get("context"), dict) else {}
        mode = str((context or {}).get("mode") or "normal")
        stock_codes = (context or {}).get("stock_codes") or []
        if not isinstance(stock_codes, list):
            stock_codes = []

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(item: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, item)

        def _create_report_task_tool(model: str = "qwen-max", stock_codes: list[str] | None = None) -> str:
            """创建“智能研报任务”，返回 task_id 与查看链接。

            Args:
                model: qwen-max 或 deepseek
                stock_codes: 股票代码列表（如 ["002594.SZ","600519.SH"]）
            """
            codes = stock_codes or []
            r = _assistant_create_report_task(model=model, stock_codes=[str(c) for c in codes])
            emit({"type": "report_task", "task": r})
            return json.dumps(r, ensure_ascii=False)

        create_report_task_tool = StructuredTool.from_function(_create_report_task_tool, name="create_report_task")

        async def _runner() -> None:
            try:
                emit({"type": "start", "session_id": session_id})
                if _assistant_test_mode():
                    emit({"type": "token", "content": "这是测试模式输出。"})
                    emit({"type": "done"})
                    return

                agent = build_assistant_agent(emit=emit, create_report_task_tool=create_report_task_tool)
                user_prompt = json.dumps(
                    {
                        "message": message,
                        "context": {
                            "mode": mode,
                            "stock_codes": stock_codes,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                res = await asyncio.to_thread(agent.invoke, {"messages": [{"role": "user", "content": user_prompt}]})
                msg = (res.get("messages") or [])[-1] if isinstance(res, dict) else None
                answer = str(getattr(msg, "content", "") or "")
                emit({"type": "answer_start"})
                for chunk in _assistant_stream_chunks(answer):
                    emit({"type": "token", "content": chunk})
                    await asyncio.sleep(0)
                emit({"type": "done"})
            except Exception as e:
                emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
                emit({"type": "done"})

        asyncio.create_task(_runner())
        return StreamingResponse(sse_iter(queue), media_type="text/event-stream")

    def _dataset_def(dataset: str) -> tuple[str, list[str], str]:
        mapping: dict[str, tuple[str, list[str], str]] = {
            "trade_stock_daily": ("trade_stock_daily", ["stock_code", "trade_date"], "trade_date"),
            "trade_stock_financial": ("trade_stock_financial", ["stock_code", "report_date"], "report_date"),
            "trade_stock_news": ("trade_stock_news", ["stock_code", "news_type", "published_at"], "published_at"),
            "trade_macro_indicator": ("trade_macro_indicator", ["indicator_date"], "indicator_date"),
            "trade_rate_daily": ("trade_rate_daily", ["rate_date"], "rate_date"),
            "trade_report_consensus": ("trade_report_consensus", ["stock_code", "broker", "report_date"], "report_date"),
            "trade_calendar_event": ("trade_calendar_event", ["event_date", "country", "importance", "source"], "event_date"),
        }
        if dataset not in mapping:
            raise HTTPException(status_code=400, detail="unknown dataset")
        return mapping[dataset]

    def _normalize_stock_code(v: str) -> str:
        s = (v or "").strip().upper()
        if not s:
            return s
        if "." in s:
            return s
        if len(s) == 6 and s.isdigit():
            ex = "SH" if s.startswith("6") else "SZ"
            return f"{s}.{ex}"
        return s

    def _sync_stock_master(scope: str, limit: int) -> dict[str, Any]:
        scope = (scope or "daily").strip().lower()
        limit = int(limit or 0)
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            raise RuntimeError("akshare returned empty")

        name_map: dict[str, str] = {}
        for _, r in df.iterrows():
            code_num = str(r.get("代码") or "").strip()
            name = str(r.get("名称") or "").strip()
            if not code_num or not name:
                continue
            ex = "SH" if code_num.startswith("6") else "SZ"
            name_map[f"{code_num}.{ex}"] = name

        if scope == "all":
            codes = sorted(name_map.keys())
        else:
            conn = connect(mysql_cfg)
            try:
                rows = query_dict(conn, "SELECT DISTINCT stock_code AS code FROM trade_stock_daily ORDER BY stock_code")
                codes = [str(r["code"]) for r in rows if r.get("code")]
            finally:
                conn.close()

        codes = [_normalize_stock_code(c) for c in codes if c]
        if limit > 0:
            codes = codes[:limit]

        upserts: list[tuple[Any, ...]] = []
        missing: list[str] = []
        for c in codes:
            n = name_map.get(c)
            if not n:
                missing.append(c)
                continue
            upserts.append((c, n, "akshare"))

        if upserts:
            conn2 = connect(mysql_cfg)
            try:
                sql = """
                INSERT INTO trade_stock_master (stock_code, stock_name, source)
                VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  stock_name=VALUES(stock_name),
                  source=VALUES(source)
                """
                chunk = 1000
                for i in range(0, len(upserts), chunk):
                    executemany(conn2, sql, upserts[i : i + chunk])
                conn2.commit()
            finally:
                conn2.close()

        return {"scope": scope, "codesTotal": len(codes), "upserted": len(upserts), "missing": missing[:200]}

    stock_sync_lock = threading.Lock()
    stock_sync_state: dict[str, Any] = {
        "running": False,
        "startedAt": None,
        "finishedAt": None,
        "lastResult": None,
        "lastError": None,
    }

    def _start_stock_sync(scope: str, limit: int) -> bool:
        with stock_sync_lock:
            if stock_sync_state["running"]:
                return False
            stock_sync_state["running"] = True
            stock_sync_state["startedAt"] = _now_iso()
            stock_sync_state["finishedAt"] = None
            stock_sync_state["lastResult"] = None
            stock_sync_state["lastError"] = None

        def _run():
            try:
                res = _sync_stock_master(scope, limit)
                with stock_sync_lock:
                    stock_sync_state["lastResult"] = res
            except Exception as e:
                with stock_sync_lock:
                    stock_sync_state["lastError"] = f"{type(e).__name__}: {e}"
            finally:
                with stock_sync_lock:
                    stock_sync_state["running"] = False
                    stock_sync_state["finishedAt"] = _now_iso()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return True

    @app.get("/api/stocks")
    def stocks(q: str | None = None, codes: str | None = None, limit: int = 30) -> dict[str, Any]:
        q = (q or "").strip()
        codes = (codes or "").strip()
        limit = min(max(int(limit or 30), 1), 200)

        stock_master_lock = getattr(stocks, "_stock_master_lock", None)
        if stock_master_lock is None:
            stock_master_lock = threading.Lock()
            setattr(stocks, "_stock_master_lock", stock_master_lock)
        stock_master_cache = getattr(stocks, "_stock_master_cache", None)
        if stock_master_cache is None:
            stock_master_cache = {"ts": 0.0, "refreshing": False, "lastError": None, "map": {}, "items": []}
            setattr(stocks, "_stock_master_cache", stock_master_cache)

        def _safe_missing_table(e: Exception) -> bool:
            code = None
            try:
                code = int((getattr(e, "args", [None]) or [None])[0])
            except Exception:
                code = None
            return code in (1146, 1051)

        def _refresh_stock_master_cache() -> None:
            try:
                conn0 = connect(mysql_cfg)
                try:
                    rows0 = query_dict(conn0, "SELECT stock_code AS code, stock_name AS name FROM trade_stock_master")
                finally:
                    conn0.close()

                m0: dict[str, Any] = {}
                items0: list[tuple[str, str]] = []
                for r in rows0 or []:
                    code = str(r.get("code") or "").strip()
                    if not code:
                        continue
                    name = r.get("name")
                    name_s = str(name).strip() if name not in (None, "") else None
                    m0[code] = name_s
                    if name_s:
                        items0.append((code, name_s))
                items0.sort(key=lambda x: x[0])
                with stock_master_lock:
                    stock_master_cache["ts"] = time.time()
                    stock_master_cache["map"] = m0
                    stock_master_cache["items"] = items0
                    stock_master_cache["lastError"] = None
            except Exception as e:
                with stock_master_lock:
                    if not _safe_missing_table(e):
                        stock_master_cache["lastError"] = f"{type(e).__name__}: {e}"
            finally:
                with stock_master_lock:
                    stock_master_cache["refreshing"] = False

        def _trigger_master_refresh(force: bool = False) -> None:
            now0 = time.time()
            with stock_master_lock:
                if stock_master_cache.get("refreshing"):
                    return
                ts0 = float(stock_master_cache.get("ts") or 0.0)
                if not force and ts0 > 0 and (now0 - ts0) < 600:
                    return
                stock_master_cache["refreshing"] = True
            threading.Thread(target=_refresh_stock_master_cache, daemon=True).start()

        def _get_master_snapshot() -> tuple[float, dict[str, Any], list[tuple[str, str]], Any, bool]:
            now0 = time.time()
            with stock_master_lock:
                ts0 = float(stock_master_cache.get("ts") or 0.0)
                m0 = dict(stock_master_cache.get("map") or {})
                items0 = list(stock_master_cache.get("items") or [])
                err0 = stock_master_cache.get("lastError")
                refreshing0 = bool(stock_master_cache.get("refreshing"))
            if ts0 == 0.0 and not refreshing0:
                _trigger_master_refresh(force=True)
            elif ts0 > 0 and (now0 - ts0) >= 600 and not refreshing0:
                _trigger_master_refresh(force=False)
            return ts0, m0, items0, err0, refreshing0

        ts_master, master_map, master_items, master_err, master_refreshing = _get_master_snapshot()
        has_master = bool(master_map)
        if not has_master and not master_refreshing and ts_master == 0.0 and (codes or any(ord(ch) > 127 for ch in q)):
            _refresh_stock_master_cache()
            ts_master, master_map, master_items, master_err, master_refreshing = _get_master_snapshot()
            has_master = bool(master_map)

        if codes:
            arr = [_normalize_stock_code(p) for p in codes.split(",") if str(p).strip()]
            if not arr:
                return {"items": []}
            m = {c: master_map.get(c) for c in arr if c}
            missing = [c for c in arr if not m.get(c)]
            if missing:
                conn = connect(mysql_cfg)
                try:
                    ph2 = ",".join(["%s"] * len(missing))
                    rows2 = query_dict(
                        conn,
                        f"""
                        SELECT d.stock_code AS code, d.stock_name AS name
                        FROM trade_stock_daily d
                        JOIN (
                          SELECT stock_code, MAX(trade_date) AS max_trade_date
                          FROM trade_stock_daily
                          WHERE stock_code IN ({ph2})
                          GROUP BY stock_code
                        ) t
                          ON d.stock_code=t.stock_code AND d.trade_date=t.max_trade_date
                        """,
                        tuple(missing),
                    )
                    for r in rows2 or []:
                        code = str(r.get("code") or "")
                        name = r.get("name")
                        if code and code in missing and not m.get(code) and name not in (None, ""):
                            m[code] = str(name)
                except Exception as e:
                    if not _safe_missing_table(e):
                        raise
                finally:
                    conn.close()
            return {"items": [{"code": c, "name": m.get(c)} for c in arr], "cache_ts": ts_master, "cache_refreshing": master_refreshing}

        if q:
            qn = _normalize_stock_code(q)
            if qn and all(ord(ch) < 128 for ch in q) and ((len(q) == 6 and q.isdigit()) or qn == q.upper()):
                if has_master and qn in master_map:
                    return {"items": [{"code": qn, "name": master_map.get(qn)}], "cache_ts": ts_master, "cache_refreshing": master_refreshing}

                conn = connect(mysql_cfg)
                try:
                    rows2 = query_dict(
                        conn,
                        """
                        SELECT stock_code AS code, stock_name AS name
                        FROM trade_stock_daily
                        WHERE stock_code=%s
                        ORDER BY trade_date DESC
                        LIMIT 1
                        """,
                        (qn,),
                    )
                    if rows2:
                        return {"items": [{"code": str(rows2[0].get("code")), "name": rows2[0].get("name")}]}
                except Exception as e:
                    if not _safe_missing_table(e):
                        raise
                finally:
                    conn.close()
                return {"items": []}

            if has_master:
                out: list[dict[str, Any]] = []
                q_upper = q.upper()
                for code, name in master_items:
                    if q_upper in code or (name and q in name):
                        out.append({"code": code, "name": name})
                        if len(out) >= limit:
                            break
                return {"items": out, "cache_ts": ts_master, "cache_refreshing": master_refreshing, "cache_size": len(master_items), "cache_error": master_err}

            if any(ord(ch) > 127 for ch in q):
                return {"items": []}

            prefix = qn or q.upper()
            conn = connect(mysql_cfg)
            try:
                rows = query_dict(
                    conn,
                    "SELECT DISTINCT stock_code AS code, stock_name AS name FROM trade_stock_daily WHERE stock_code LIKE %s ORDER BY stock_code LIMIT %s",
                    (f"{prefix}%", limit),
                )
            except Exception as e:
                if _safe_missing_table(e):
                    rows = []
                else:
                    raise
            finally:
                conn.close()
            return {"items": [{"code": str(r.get('code')), "name": r.get('name')} for r in (rows or []) if r.get('code')]}

        if has_master:
            out = [{"code": code, "name": name} for code, name in master_items[:limit]]
            return {"items": out, "cache_ts": ts_master, "cache_refreshing": master_refreshing}

        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT DISTINCT stock_code AS code, stock_name AS name FROM trade_stock_daily ORDER BY stock_code LIMIT %s", (limit,))
        except Exception as e:
            if _safe_missing_table(e):
                rows = []
            else:
                raise
        finally:
            conn.close()
        return {"items": [{"code": str(r.get('code')), "name": r.get('name')} for r in (rows or []) if r.get('code')]}

    @app.get("/api/stocks/sync/status")
    def stocks_sync_status() -> dict[str, Any]:
        with stock_sync_lock:
            return dict(stock_sync_state)

    @app.post("/api/stocks/sync")
    def stocks_sync(scope: str = "daily", limit: int = 0) -> dict[str, Any]:
        started = _start_stock_sync(scope, int(limit or 0))
        return {"started": started, "scope": scope, "limit": int(limit or 0)}

    spot_lock = threading.Lock()
    spot_cache: dict[str, Any] = {"ts": 0.0, "m": {}, "refreshing": False, "lastError": None}

    def _refresh_spot_cache() -> None:
        try:
            import akshare as ak

            df = ak.stock_zh_a_spot_em()
            m: dict[str, Any] = {}
            for _, r in df.iterrows():
                code_num = str(r.get("代码") or "").strip()
                name = str(r.get("名称") or "").strip()
                if not code_num:
                    continue
                ex = "SH" if code_num.startswith("6") else "SZ"
                c = f"{code_num}.{ex}"
                price = r.get("最新价")
                pct = r.get("涨跌幅")
                chg = r.get("涨跌额")
                m[c] = {
                    "stock_code": c,
                    "stock_name": name or None,
                    "price": float(price) if price not in (None, "") else None,
                    "change": float(chg) if chg not in (None, "") else None,
                    "pctChange": float(pct) if pct not in (None, "") else None,
                    "asOf": _now_iso(),
                    "source": "akshare",
                }
            with spot_lock:
                spot_cache["ts"] = time.time()
                spot_cache["m"] = m
                spot_cache["lastError"] = None
        except Exception as e:
            with spot_lock:
                spot_cache["lastError"] = f"{type(e).__name__}: {e}"
        finally:
            with spot_lock:
                spot_cache["refreshing"] = False

    def _trigger_spot_refresh() -> None:
        with spot_lock:
            if spot_cache.get("refreshing"):
                return
            spot_cache["refreshing"] = True
        t = threading.Thread(target=_refresh_spot_cache, daemon=True)
        t.start()

    def _get_spot_snapshot(code: str) -> dict[str, Any] | None:
        now = time.time()
        with spot_lock:
            ts = float(spot_cache.get("ts") or 0.0)
            m = spot_cache.get("m") or {}
            val = m.get(code)
            fresh = (now - ts) < 60
        if fresh and val is not None:
            return val
        _trigger_spot_refresh()
        return val

    _trigger_spot_refresh()

    def _fallback_snapshot_from_db(code: str) -> dict[str, Any]:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT stock_name, trade_date, close_price FROM trade_stock_daily WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 2",
                (code,),
            )
        finally:
            conn.close()
        if not rows:
            return {"stock_code": code, "stock_name": None, "price": None, "change": None, "pctChange": None, "asOf": _now_iso(), "source": "db"}
        last = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        price = float(last.get("close_price") or 0.0) if last.get("close_price") is not None else None
        prev_price = float(prev.get("close_price") or 0.0) if prev and prev.get("close_price") is not None else None
        change = (price - prev_price) if (price is not None and prev_price is not None) else None
        pct = (change / prev_price * 100.0) if (change is not None and prev_price) else None
        return {
            "stock_code": code,
            "stock_name": last.get("stock_name"),
            "price": price,
            "change": change,
            "pctChange": pct,
            "asOf": _now_iso(),
            "source": "db",
        }

    def _get_stock_name(code: str) -> str | None:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, "SELECT stock_name FROM trade_stock_master WHERE stock_code=%s LIMIT 1", (code,))
            if rows and rows[0].get("stock_name"):
                return str(rows[0]["stock_name"])
            rows2 = query_dict(conn, "SELECT stock_name FROM trade_stock_daily WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 1", (code,))
            if rows2 and rows2[0].get("stock_name"):
                return str(rows2[0]["stock_name"])
            return None
        finally:
            conn.close()

    @app.get("/api/stock/{stock_code}/snapshot")
    def stock_snapshot(stock_code: str) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        if not code:
            raise HTTPException(status_code=400, detail="stock_code required")
        s = _get_spot_snapshot(code)
        if s is None:
            s = _fallback_snapshot_from_db(code)
        if not s.get("stock_name"):
            s["stock_name"] = _get_stock_name(code)
        return s

    @app.get("/api/stock/{stock_code}/fundamentals")
    def stock_fundamentals(stock_code: str) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        if not code:
            raise HTTPException(status_code=400, detail="stock_code required")
        snap = _get_spot_snapshot(code) or _fallback_snapshot_from_db(code)

        conn = connect(mysql_cfg)
        try:
            fin_rows = query_dict(
                conn,
                """
                SELECT report_date, revenue, net_profit, eps, roe, operating_cashflow, total_assets, total_equity
                FROM trade_stock_financial
                WHERE stock_code=%s
                ORDER BY report_date DESC
                LIMIT 2
                """,
                (code,),
            )
        finally:
            conn.close()

        cur = fin_rows[0] if fin_rows else {}
        prev = fin_rows[1] if len(fin_rows) > 1 else {}
        report_date = cur.get("report_date")
        report_date_str = report_date.isoformat() if report_date else None

        bps = None
        eps_em = None
        roe_em = None
        try:
            import akshare as ak

            df = ak.stock_financial_analysis_indicator_em(symbol=code, indicator="按报告期")
            if df is not None and len(df) > 0:
                r0 = df.iloc[0]
                bps = float(r0.get("BPS")) if r0.get("BPS") not in (None, "") else None
                eps_em = float(r0.get("EPSJB")) if r0.get("EPSJB") not in (None, "") else None
                roe_em = float(r0.get("ROEJQ")) if r0.get("ROEJQ") not in (None, "") else None
                if report_date_str is None:
                    rd = r0.get("REPORT_DATE")
                    try:
                        report_date_str = rd.date().isoformat() if hasattr(rd, "date") else str(rd)[:10]
                    except Exception:
                        report_date_str = None
        except Exception:
            pass

        def num(v: Any, digits: int) -> float | None:
            if v in (None, ""):
                return None
            try:
                return round(float(v), digits)
            except Exception:
                return None

        def delta(cur_v: Any, prev_v: Any, digits: int) -> dict[str, Any]:
            a = num(cur_v, digits)
            b = num(prev_v, digits)
            if a is None or b is None:
                return {"value": a, "delta": None, "dir": None}
            d = round(a - b, digits)
            if d > 0:
                di = "up"
            elif d < 0:
                di = "down"
            else:
                di = "flat"
            return {"value": a, "delta": d, "dir": di}

        price = snap.get("price")
        pe = None
        pb = None
        eps_for_pe = eps_em if eps_em is not None else cur.get("eps")
        if price not in (None, ""):
            try:
                p = float(price)
                if eps_for_pe not in (None, "") and float(eps_for_pe) != 0:
                    pe = round(p / float(eps_for_pe), 2)
                if bps not in (None, "") and float(bps) != 0:
                    pb = round(p / float(bps), 2)
            except Exception:
                pe = None
                pb = None

        items = [
            {"key": "roe", "label": "ROE", "unit": "%", "tooltip": "净资产收益率(%)", **delta(roe_em if roe_em is not None else cur.get("roe"), prev.get("roe"), 2)},
            {"key": "pe", "label": "PE", "unit": "倍", "tooltip": "市盈率(倍)", "value": pe, "delta": None, "dir": None},
            {"key": "pb", "label": "PB", "unit": "倍", "tooltip": "市净率(倍)", "value": pb, "delta": None, "dir": None},
            {"key": "revenue", "label": "营业收入", "unit": "元", "tooltip": "营业收入(元)", **delta(cur.get("revenue"), prev.get("revenue"), 2)},
            {"key": "net_profit", "label": "净利润", "unit": "元", "tooltip": "净利润(元)", **delta(cur.get("net_profit"), prev.get("net_profit"), 2)},
            {"key": "eps", "label": "EPS", "unit": "元", "tooltip": "每股收益(元)", **delta(eps_em if eps_em is not None else cur.get("eps"), prev.get("eps"), 2)},
            {"key": "operating_cashflow", "label": "经营现金流", "unit": "元", "tooltip": "经营现金流(元)", **delta(cur.get("operating_cashflow"), prev.get("operating_cashflow"), 2)},
            {"key": "total_assets", "label": "总资产", "unit": "元", "tooltip": "总资产(元)", **delta(cur.get("total_assets"), prev.get("total_assets"), 2)},
            {"key": "total_equity", "label": "净资产", "unit": "元", "tooltip": "净资产(元)", **delta(cur.get("total_equity"), prev.get("total_equity"), 2)},
        ]

        name = snap.get("stock_name") or _get_stock_name(code)
        return {"stock_code": code, "stock_name": name, "reportDate": report_date_str, "items": items}

    @app.get("/api/stock/{stock_code}/technical/latest")
    def stock_technical_latest(
        stock_code: str,
        maPeriod: int = 20,
        macdShort: int = 12,
        macdLong: int = 26,
        macdSignal: int = 9,
        rsiPeriod: int = 14,
        atrPeriod: int = 14,
    ) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        ma_period = min(max(int(maPeriod or 20), 2), 200)
        macd_short = min(max(int(macdShort or 12), 2), 200)
        macd_long = min(max(int(macdLong or 26), 2), 300)
        macd_signal = min(max(int(macdSignal or 9), 2), 200)
        rsi_period = min(max(int(rsiPeriod or 14), 2), 200)
        atr_period = min(max(int(atrPeriod or 14), 2), 200)
        if macd_short >= macd_long:
            raise HTTPException(status_code=400, detail="macdShort must be < macdLong")

        lookback = max(ma_period, macd_long + macd_signal, rsi_period + 1, atr_period + 1) + 10
        lookback = min(max(int(lookback), 60), 400)

        conn = connect(mysql_cfg)
        try:
            rows = query_dict(
                conn,
                """
                SELECT trade_date, ma5, ma10, ma20, ma60, vol_ma5, vol_ma20, rsi14,
                       macd_dif, macd_dea, macd_hist, boll_upper, boll_mid, boll_lower,
                       kdj_k, kdj_d, kdj_j
                FROM trade_stock_daily
                WHERE stock_code=%s
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                (code,),
            )

            atr_rows = query_dict(
                conn,
                """
                SELECT trade_date, high_price, low_price, close_price
                FROM trade_stock_daily
                WHERE stock_code=%s
                ORDER BY trade_date DESC
                LIMIT %s
                """,
                (code, lookback),
            )
        finally:
            conn.close()

        def _ema_opt(values: list[float | None], span: int) -> list[float | None]:
            if not values:
                return []
            alpha = 2.0 / (span + 1.0)
            out: list[float | None] = []
            for v in values:
                if v is None:
                    out.append(out[-1] if out else None)
                    continue
                if not out or out[-1] is None:
                    out.append(v)
                    continue
                out.append(out[-1] + alpha * (v - out[-1]))
            return out

        def _macd_opt(
            close: list[float | None], short: int, long: int, signal: int
        ) -> tuple[list[float | None], list[float | None], list[float | None]]:
            ema_s = _ema_opt(close, short)
            ema_l = _ema_opt(close, long)
            dif: list[float | None] = []
            for a, b in zip(ema_s, ema_l):
                dif.append((a - b) if (a is not None and b is not None) else None)
            dea = _ema_opt(dif, signal)
            hist: list[float | None] = []
            for d, e in zip(dif, dea):
                hist.append(((d - e) * 2.0) if (d is not None and e is not None) else None)
            return dif, dea, hist

        def _rsi_opt(close: list[float | None], period: int) -> list[float | None]:
            n = len(close)
            out: list[float | None] = [None] * n
            if n < period + 1:
                return out
            filled: list[float] = []
            last = 0.0
            for v in close:
                if v is None:
                    filled.append(last)
                else:
                    last = float(v)
                    filled.append(last)
            gains = [0.0] * n
            losses = [0.0] * n
            for i in range(1, n):
                d = filled[i] - filled[i - 1]
                gains[i] = d if d > 0 else 0.0
                losses[i] = -d if d < 0 else 0.0
            avg_gain = sum(gains[1 : period + 1]) / period
            avg_loss = sum(losses[1 : period + 1]) / period
            for i in range(period, n):
                if i > period:
                    avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                    avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                if avg_loss == 0:
                    out[i] = 100.0
                else:
                    rs = avg_gain / avg_loss
                    out[i] = 100.0 - 100.0 / (1.0 + rs)
            return out

        ma_custom = None
        macd_dif_custom = None
        macd_dea_custom = None
        macd_hist_custom = None
        rsi_custom = None
        atr_custom = None

        if atr_rows and len(atr_rows) >= 2:
            r = list(reversed(atr_rows))
            close_vals: list[float | None] = [float(x["close_price"]) if x.get("close_price") is not None else None for x in r]

            if any(v is not None for v in close_vals):
                tail = [v for v in close_vals if v is not None][-ma_period:]
                ma_custom = (sum(tail) / len(tail)) if tail else None

                dif, dea, hist = _macd_opt(close_vals, macd_short, macd_long, macd_signal)
                macd_dif_custom = dif[-1] if dif else None
                macd_dea_custom = dea[-1] if dea else None
                macd_hist_custom = hist[-1] if hist else None

                rsi_seq = _rsi_opt(close_vals, rsi_period)
                rsi_custom = rsi_seq[-1] if rsi_seq else None

            prev_close: float | None = None
            trs: list[float] = []
            for x in r:
                hi = x.get("high_price")
                lo = x.get("low_price")
                cl = x.get("close_price")
                if hi is None or lo is None or cl is None:
                    continue
                hi_f = float(hi)
                lo_f = float(lo)
                cl_f = float(cl)
                if prev_close is None:
                    tr = hi_f - lo_f
                else:
                    tr = max(hi_f - lo_f, abs(hi_f - prev_close), abs(lo_f - prev_close))
                trs.append(tr)
                prev_close = cl_f
            if len(trs) >= atr_period:
                atr_custom = sum(trs[-atr_period:]) / float(atr_period)

        row = (rows[0] if rows else None)
        if row is not None:
            row["ma_custom"] = ma_custom
            row["macd_dif_custom"] = macd_dif_custom
            row["macd_dea_custom"] = macd_dea_custom
            row["macd_hist_custom"] = macd_hist_custom
            row["rsi_custom"] = rsi_custom
            row["atr_custom"] = atr_custom
        return {"stock_code": code, "row": row}

    @app.get("/api/stock/{stock_code}/technical/series")
    def stock_technical_series(
        stock_code: str,
        start: str | None = None,
        end: str | None = None,
        maPeriod: int = 20,
        macdShort: int = 12,
        macdLong: int = 26,
        macdSignal: int = 9,
        rsiPeriod: int = 14,
        atrPeriod: int = 14,
    ) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        ma_period = min(max(int(maPeriod or 20), 2), 200)
        macd_short = min(max(int(macdShort or 12), 2), 200)
        macd_long = min(max(int(macdLong or 26), 2), 300)
        macd_signal = min(max(int(macdSignal or 9), 2), 200)
        rsi_period = min(max(int(rsiPeriod or 14), 2), 200)
        atr_period = min(max(int(atrPeriod or 14), 2), 200)
        if macd_short >= macd_long:
            raise HTTPException(status_code=400, detail="macdShort must be < macdLong")

        start_s = (start or "").strip()
        end_s = (end or "").strip()
        where = ["stock_code=%s"]
        params: list[Any] = [code]
        if start_s:
            where.append("trade_date >= %s")
            params.append(start_s)
        if end_s:
            where.append("trade_date <= %s")
            params.append(end_s)
        where_sql = " AND ".join(where)
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(
                conn,
                f"""
                SELECT trade_date, open_price, high_price, low_price, close_price, volume, amount,
                       ma5, ma10, ma20, ma60, vol_ma5, vol_ma20, rsi14,
                       macd_dif, macd_dea, macd_hist, boll_upper, boll_mid, boll_lower,
                       kdj_k, kdj_d, kdj_j
                FROM trade_stock_daily
                WHERE {where_sql}
                ORDER BY trade_date ASC
                """,
                tuple(params),
            )
        finally:
            conn.close()

        def _ema_opt(values: list[float | None], span: int) -> list[float | None]:
            if not values:
                return []
            alpha = 2.0 / (span + 1.0)
            out: list[float | None] = []
            for v in values:
                if v is None:
                    out.append(out[-1] if out else None)
                    continue
                if not out or out[-1] is None:
                    out.append(v)
                    continue
                out.append(out[-1] + alpha * (v - out[-1]))
            return out

        def _macd_opt(
            close: list[float | None], short: int, long: int, signal: int
        ) -> tuple[list[float | None], list[float | None], list[float | None]]:
            ema_s = _ema_opt(close, short)
            ema_l = _ema_opt(close, long)
            dif: list[float | None] = []
            for a, b in zip(ema_s, ema_l):
                dif.append((a - b) if (a is not None and b is not None) else None)
            dea = _ema_opt(dif, signal)
            hist: list[float | None] = []
            for d, e in zip(dif, dea):
                hist.append(((d - e) * 2.0) if (d is not None and e is not None) else None)
            return dif, dea, hist

        def _rsi_opt(close: list[float | None], period: int) -> list[float | None]:
            n = len(close)
            out: list[float | None] = [None] * n
            if n < period + 1:
                return out
            filled: list[float] = []
            last = 0.0
            for v in close:
                if v is None:
                    filled.append(last)
                else:
                    last = float(v)
                    filled.append(last)
            gains = [0.0] * n
            losses = [0.0] * n
            for i in range(1, n):
                d = filled[i] - filled[i - 1]
                gains[i] = d if d > 0 else 0.0
                losses[i] = -d if d < 0 else 0.0
            avg_gain = sum(gains[1 : period + 1]) / period
            avg_loss = sum(losses[1 : period + 1]) / period
            for i in range(period, n):
                if i > period:
                    avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                    avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                if avg_loss == 0:
                    out[i] = 100.0
                else:
                    rs = avg_gain / avg_loss
                    out[i] = 100.0 - 100.0 / (1.0 + rs)
            return out

        if rows and len(rows) >= 2:
            close_vals: list[float | None] = [float(r["close_price"]) if r.get("close_price") is not None else None for r in rows]
            dif, dea, hist = _macd_opt(close_vals, macd_short, macd_long, macd_signal)
            rsi_seq = _rsi_opt(close_vals, rsi_period)

            ma_seq: list[float | None] = []
            s = 0.0
            window: list[float] = []
            for r in rows:
                c = r.get("close_price")
                if c is None:
                    ma_seq.append(None)
                    continue
                cf = float(c)
                window.append(cf)
                s += cf
                if len(window) > ma_period:
                    s -= window.pop(0)
                ma_seq.append(s / len(window))

            prev_close = None
            trs: list[float] = []
            for i, r in enumerate(rows):
                hi = r.get("high_price")
                lo = r.get("low_price")
                cl = r.get("close_price")
                if hi is None or lo is None or cl is None:
                    tr = 0.0
                    trs.append(tr)
                    prev_close = cl
                    r["atr14"] = None
                    continue
                hi_f = float(hi)
                lo_f = float(lo)
                cl_f = float(cl)
                if prev_close is None or prev_close is None:
                    tr = hi_f - lo_f
                else:
                    pc = float(prev_close)
                    tr = max(hi_f - lo_f, abs(hi_f - pc), abs(lo_f - pc))
                trs.append(tr)
                prev_close = cl_f
                if i >= (atr_period - 1):
                    r["atr_custom"] = sum(trs[i - (atr_period - 1) : i + 1]) / float(atr_period)
                else:
                    r["atr_custom"] = None

                r["ma_custom"] = ma_seq[i] if i < len(ma_seq) else None
                r["rsi_custom"] = rsi_seq[i] if i < len(rsi_seq) else None
                r["macd_dif_custom"] = dif[i] if i < len(dif) else None
                r["macd_dea_custom"] = dea[i] if i < len(dea) else None
                r["macd_hist_custom"] = hist[i] if i < len(hist) else None
        return {"stock_code": code, "rows": rows}

    @app.get("/api/stock/{stock_code}/feed")
    def stock_feed(stock_code: str, tab: str = "news", page: int = 1, pageSize: int = 5) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        page = max(int(page or 1), 1)
        page_size = min(max(int(pageSize or 5), 1), 20)
        offset = (page - 1) * page_size
        conn = connect(mysql_cfg)
        try:
            if tab == "reports":
                total = query_dict(conn, "SELECT COUNT(*) AS c FROM trade_report_consensus WHERE stock_code=%s", (code,))
                rows = query_dict(
                    conn,
                    """
                    SELECT broker, report_date, rating, target_price, source_file
                    FROM trade_report_consensus
                    WHERE stock_code=%s
                    ORDER BY report_date DESC
                    LIMIT %s OFFSET %s
                    """,
                    (code, page_size, offset),
                )
                out = []
                for r in rows:
                    title = " ".join([str(r.get("broker") or ""), str(r.get("rating") or "")]).strip() or "研报"
                    if r.get("target_price") not in (None, ""):
                        title = f"{title} 目标价{r.get('target_price')}"
                    url = r.get("source_file")
                    url_str = str(url) if url else None
                    out.append(
                        {
                            "title": title,
                            "source": r.get("broker"),
                            "publishedAt": (r.get("report_date").isoformat() if r.get("report_date") else None),
                            "url": url_str if (url_str and url_str.startswith("http")) else None,
                        }
                    )
                return {"tab": tab, "page": page, "pageSize": page_size, "total": int(total[0]["c"]) if total else 0, "items": out}

            total = query_dict(conn, "SELECT COUNT(*) AS c FROM trade_stock_news WHERE stock_code=%s", (code,))
            rows = query_dict(
                conn,
                """
                SELECT title, source, source_url, published_at
                FROM trade_stock_news
                WHERE stock_code=%s
                ORDER BY published_at DESC
                LIMIT %s OFFSET %s
                """,
                (code, page_size, offset),
            )
            out2 = []
            for r in rows:
                out2.append(
                    {
                        "title": r.get("title"),
                        "source": r.get("source"),
                        "publishedAt": (r.get("published_at").isoformat() if r.get("published_at") else None),
                        "url": r.get("source_url"),
                    }
                )
            return {"tab": "news", "page": page, "pageSize": page_size, "total": int(total[0]["c"]) if total else 0, "items": out2}
        finally:
            conn.close()

    @app.get("/api/watchlist")
    def watchlist_get() -> dict[str, Any]:
        conn = connect(mysql_cfg)
        try:
            rows = query_dict(
                conn,
                """
                SELECT w.stock_code, w.pinned, w.sort_order, m.stock_name
                FROM trade_watchlist w
                LEFT JOIN trade_stock_master m ON m.stock_code=w.stock_code
                ORDER BY w.pinned DESC, w.sort_order ASC, w.updated_at DESC
                """,
            )
            items = [
                {"stock_code": r.get("stock_code"), "stock_name": r.get("stock_name"), "pinned": bool(int(r.get("pinned") or 0) == 1), "sortOrder": int(r.get("sort_order") or 0)}
                for r in rows
            ]
            return {"items": items, "max": 50}
        finally:
            conn.close()

    @app.post("/api/watchlist")
    def watchlist_add(body: dict[str, Any]) -> dict[str, Any]:
        code = _normalize_stock_code(str(body.get("stock_code") or ""))
        if not code:
            raise HTTPException(status_code=400, detail="stock_code required")
        conn = connect(mysql_cfg)
        try:
            cnt = query_dict(conn, "SELECT COUNT(*) AS c FROM trade_watchlist")
            if cnt and int(cnt[0].get("c") or 0) >= 50:
                raise HTTPException(status_code=400, detail="自选股数量已达上限(50)，请先删除后再添加")
            exists = query_dict(conn, "SELECT 1 AS ok FROM trade_watchlist WHERE stock_code=%s LIMIT 1", (code,))
            if exists:
                return {"ok": True, "stock_code": code}
            mx = query_dict(conn, "SELECT COALESCE(MAX(sort_order),0) AS m FROM trade_watchlist")
            next_order = int(mx[0].get("m") or 0) + 1 if mx else 1
            execute(conn, "INSERT INTO trade_watchlist (stock_code, pinned, sort_order) VALUES (%s,0,%s)", (code, next_order))
            conn.commit()
            return {"ok": True, "stock_code": code}
        finally:
            conn.close()

    @app.delete("/api/watchlist/{stock_code}")
    def watchlist_delete(stock_code: str) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        conn = connect(mysql_cfg)
        try:
            execute(conn, "DELETE FROM trade_watchlist WHERE stock_code=%s", (code,))
            conn.commit()
            return {"ok": True}
        finally:
            conn.close()

    @app.put("/api/watchlist/{stock_code}/pin")
    def watchlist_pin(stock_code: str, body: dict[str, Any]) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
        pinned = 1 if bool(body.get("pinned", True)) else 0
        conn = connect(mysql_cfg)
        try:
            execute(conn, "UPDATE trade_watchlist SET pinned=%s WHERE stock_code=%s", (pinned, code))
            conn.commit()
            return {"ok": True}
        finally:
            conn.close()

    @app.put("/api/watchlist/reorder")
    def watchlist_reorder(body: dict[str, Any]) -> dict[str, Any]:
        codes = body.get("codes")
        if not isinstance(codes, list):
            raise HTTPException(status_code=400, detail="codes required")
        ordered = [_normalize_stock_code(str(c)) for c in codes if str(c).strip()]
        conn = connect(mysql_cfg)
        try:
            rows = [(i + 1, c) for i, c in enumerate(ordered)]
            executemany(conn, "UPDATE trade_watchlist SET sort_order=%s WHERE stock_code=%s", rows)
            conn.commit()
            return {"ok": True}
        finally:
            conn.close()

    @app.get("/api/data/{dataset}")
    def data_get(request: Request, dataset: str, page: int = 1, pageSize: int = 50) -> dict[str, Any]:
        table, allowed, order_col = _dataset_def(dataset)
        page = max(page, 1)
        page_size = min(max(pageSize, 1), 200)

        filters: dict[str, Any] = {}
        for k, v in request.query_params.items():
            if k in ("page", "pageSize"):
                continue
            if k == "filters" and v:
                try:
                    obj = json.loads(v)
                    if isinstance(obj, dict):
                        for kk, vv in obj.items():
                            filters[str(kk)] = vv
                except Exception:
                    pass
                continue
            filters[k] = v

        where = []
        params: list[Any] = []

        for k, v in list(filters.items()):
            if k not in allowed or v in (None, ""):
                continue
            if k == "stock_code" and isinstance(v, str) and "," in v:
                codes = [p.strip() for p in v.split(",") if p.strip()]
                if not codes:
                    continue
                ph = ",".join(["%s"] * len(codes))
                where.append(f"{k} IN ({ph})")
                params.extend(codes)
                continue
            if k in ("trade_date", "report_date", "published_at", "indicator_date", "rate_date", "event_date") and isinstance(v, str) and "," in v:
                start, end = [p.strip() for p in v.split(",", 1)]
                if start:
                    where.append(f"{k} >= %s")
                    params.append(start)
                if end:
                    where.append(f"{k} <= %s")
                    params.append(end)
            else:
                where.append(f"{k} = %s")
                params.append(v)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        offset = (page - 1) * page_size
        sql = f"SELECT * FROM {table}{where_sql} ORDER BY {order_col} DESC LIMIT %s OFFSET %s"
        count_sql = f"SELECT COUNT(*) AS c FROM {table}{where_sql}"

        conn = connect(mysql_cfg)
        try:
            total = query_dict(conn, count_sql, tuple(params))
            rows = query_dict(conn, sql, tuple(params + [page_size, offset]))
            return {"page": page, "pageSize": page_size, "total": int(total[0]["c"]) if total else 0, "rows": rows}
        finally:
            conn.close()

    @app.post("/api/export")
    def export(req: ExportRequest) -> Response:
        table, allowed, order_col = _dataset_def(req.dataset)
        fmt = (req.format or "").lower()
        if fmt not in ("csv", "json"):
            raise HTTPException(status_code=400, detail="format must be csv/json")
        limit = int(req.limit or 5000)
        limit = min(max(limit, 1), 50000)

        where = []
        params: list[Any] = []
        for k, v in (req.filters or {}).items():
            if k not in allowed or v in (None, ""):
                continue
            if k == "stock_code" and isinstance(v, str) and "," in v:
                codes = [p.strip() for p in v.split(",") if p.strip()]
                if not codes:
                    continue
                ph = ",".join(["%s"] * len(codes))
                where.append(f"{k} IN ({ph})")
                params.extend(codes)
                continue
            if k in ("trade_date", "report_date", "published_at", "indicator_date", "rate_date", "event_date") and isinstance(v, str) and "," in v:
                start, end = [p.strip() for p in v.split(",", 1)]
                if start:
                    where.append(f"{k} >= %s")
                    params.append(start)
                if end:
                    where.append(f"{k} <= %s")
                    params.append(end)
            else:
                where.append(f"{k} = %s")
                params.append(v)

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"SELECT * FROM {table}{where_sql} ORDER BY {order_col} DESC LIMIT %s"

        conn = connect(mysql_cfg)
        try:
            rows = query_dict(conn, sql, tuple(params + [limit]))
        finally:
            conn.close()

        if fmt == "json":
            content = json.dumps({"dataset": req.dataset, "exportedAt": _now_iso(), "filters": req.filters, "rows": rows}, ensure_ascii=False)
            return Response(content=content, media_type="application/json")

        def iter_csv():
            buf = io.StringIO()
            writer = None
            for r in rows:
                if writer is None:
                    writer = csv.DictWriter(buf, fieldnames=list(r.keys()))
                    writer.writeheader()
                writer.writerow(r)
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)

        filename = f"{req.dataset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(iter_csv(), media_type="text/csv; charset=utf-8", headers=headers)

    return app


if os.getenv("CHARLES_SKIP_APP_IMPORT") == "1":
    app = None
else:
    app = create_app()

