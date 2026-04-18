from __future__ import annotations

import csv
import io
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import load_settings
from .db import MySQLConfig, connect, execute, executemany, query_dict
from .job_store import init_running, list_runs, read_run, write_run
from .models import ExportRequest, JobDomain, JobRunRequest, JobRunResult
from .jobs.calendar import run_calendar
from .jobs.catalyst import run_catalyst
from .jobs.macro_indicator import run_macro_indicator
from .jobs.rate_daily import run_rate_daily
from .jobs.report_consensus import run_report_consensus
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

    def _parse_cron(expr: str) -> tuple[str, str, str, str, str]:
        parts = [p for p in (expr or "").strip().split() if p]
        if len(parts) != 5:
            raise ValueError("cron must be 5 parts: min hour day month dow")
        return parts[0], parts[1], parts[2], parts[3], parts[4]

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
                minute, hour, day, month, dow = _parse_cron(str(r.get("cron") or ""))
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
            trigger = CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow, timezone=tz)
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
            daily = query_dict(conn, "SELECT MAX(trade_date) AS d, COUNT(*) AS c FROM trade_stock_daily")
            fin = query_dict(conn, "SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_stock_financial")
            news = query_dict(conn, "SELECT MAX(published_at) AS d, COUNT(*) AS c FROM trade_stock_news")
            macro = query_dict(conn, "SELECT MAX(indicator_date) AS d, COUNT(*) AS c FROM trade_macro_indicator")
            rate = query_dict(conn, "SELECT MAX(rate_date) AS d, COUNT(*) AS c FROM trade_rate_daily")
            report = query_dict(conn, "SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_report_consensus")
            cal = query_dict(conn, "SELECT MAX(event_date) AS d, COUNT(*) AS c FROM trade_calendar_event")

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
        conn = connect(mysql_cfg)
        try:
            master_cnt = query_dict(conn, "SELECT COUNT(*) AS c FROM trade_stock_master")
            has_master = bool(master_cnt and int(master_cnt[0].get("c") or 0) > 0)

            if codes:
                arr = [_normalize_stock_code(p) for p in codes.split(",") if str(p).strip()]
                if not arr:
                    return {"items": []}
                ph = ",".join(["%s"] * len(arr))
                rows = query_dict(
                    conn,
                    f"SELECT stock_code AS code, stock_name AS name FROM trade_stock_master WHERE stock_code IN ({ph})",
                    tuple(arr),
                )
                m = {str(r.get("code")): r.get("name") for r in (rows or []) if r.get("code")}
                return {"items": [{"code": c, "name": m.get(c)} for c in arr]}

            if q:
                like = f"%{q}%"
                if has_master:
                    rows = query_dict(
                        conn,
                        "SELECT stock_code AS code, stock_name AS name FROM trade_stock_master WHERE stock_code LIKE %s OR stock_name LIKE %s ORDER BY stock_code LIMIT %s",
                        (like, like, limit),
                    )
                else:
                    rows = query_dict(
                        conn,
                        "SELECT DISTINCT stock_code AS code, stock_name AS name FROM trade_stock_daily WHERE stock_code LIKE %s OR stock_name LIKE %s ORDER BY stock_code LIMIT %s",
                        (like, like, limit),
                    )
            else:
                if has_master:
                    rows = query_dict(
                        conn,
                        "SELECT stock_code AS code, stock_name AS name FROM trade_stock_master ORDER BY stock_code LIMIT %s",
                        (limit,),
                    )
                else:
                    rows = query_dict(
                        conn,
                        "SELECT DISTINCT stock_code AS code, stock_name AS name FROM trade_stock_daily ORDER BY stock_code LIMIT %s",
                        (limit,),
                    )
            return {"items": [{"code": str(r.get('code')), "name": r.get("name")} for r in (rows or []) if r.get("code")]}
        finally:
            conn.close()

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

        return {"stock_code": code, "stock_name": snap.get("stock_name"), "reportDate": report_date_str, "items": items}

    @app.get("/api/stock/{stock_code}/technical/latest")
    def stock_technical_latest(stock_code: str) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
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
        finally:
            conn.close()
        return {"stock_code": code, "row": (rows[0] if rows else None)}

    @app.get("/api/stock/{stock_code}/technical/series")
    def stock_technical_series(stock_code: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        code = _normalize_stock_code(stock_code)
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

