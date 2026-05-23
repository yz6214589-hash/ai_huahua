from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from core.db import connect, load_mysql_config, query_dict
from core.data import get_summary, list_job_runs
from core.execution import get_status as get_execution_status
from core.risk import status as get_risk_status
from infra.storage.job_store import list_runs

_OVERVIEW_CACHE_KEY = "console_overview"
_OVERVIEW_CACHE_TTL = 30
_overview_cache: dict[str, Any] = {"data": None, "ts": 0.0}


def get_status() -> dict[str, Any]:
    return {
        "source": "console",
        "status": "ready",
        "features": ["morning"],
        "mode": "embedded",
    }


def _mysql_diagnostics() -> dict[str, Any]:
    cfg = load_mysql_config()
    try:
        conn = connect(cfg)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "tables": {},
        }

    tables = [
        "trade_stock_master",
        "trade_watchlist",
        "trade_stock_daily",
        "trade_stock_financial",
        "trade_stock_news",
        "trade_macro_indicator",
        "trade_rate_daily",
        "trade_report_consensus",
        "trade_calendar_event",
    ]
    try:
        version_rows = query_dict(conn, "SELECT VERSION() AS version")
        version = (version_rows or [{}])[0].get("version")

        ph = ",".join(["%s"] * len(tables))
        sql = (
            "SELECT table_name, table_rows "
            "FROM information_schema.tables "
            f"WHERE table_schema=%s AND table_name IN ({ph})"
        )
        rows = query_dict(conn, sql, tuple([cfg.database] + tables))
        found = {str(r.get("table_name") or ""): r.get("table_rows") for r in rows if r.get("table_name")}

        table_diag: dict[str, Any] = {}
        for name in tables:
            if name in found:
                v = found.get(name)
                try:
                    row_count = int(v) if v is not None else None
                except Exception:
                    row_count = None
                table_diag[name] = {"exists": True, "rows": row_count}
            else:
                table_diag[name] = {"exists": False, "rows": None}

        return {
            "ok": True,
            "server": {"version": version},
            "tables": table_diag,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "tables": {},
        }
    finally:
        conn.close()


def get_overview() -> dict[str, Any]:
    now = time.time()
    cached = _overview_cache.get("data")
    if cached is not None and (now - _overview_cache["ts"]) < _OVERVIEW_CACHE_TTL:
        return cached

    results: dict[str, Any] = {}

    def _fetch_summary():
        results["data_latest"] = get_summary()

    def _fetch_jobs():
        results["recent_jobs"] = list_job_runs(domain=None, limit=8)

    def _fetch_execution():
        results["execution_status"] = get_execution_status()

    def _fetch_risk():
        results["risk_status"] = get_risk_status()

    def _fetch_runs():
        results["_agent_runs"] = list_runs()

    def _fetch_mysql():
        results["mysql"] = _mysql_diagnostics()

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_fetch_summary): "summary",
            executor.submit(_fetch_jobs): "jobs",
            executor.submit(_fetch_execution): "execution",
            executor.submit(_fetch_risk): "risk",
            executor.submit(_fetch_runs): "runs",
            executor.submit(_fetch_mysql): "mysql",
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass

    agent_runs = results.get("_agent_runs", [])
    morning_run = next((x for x in agent_runs if x.get("route") == "graph:morning_brief"), None)
    results["morning"] = {
        "last_run": morning_run,
        "run_count": len([x for x in agent_runs if x.get("route") == "graph:morning_brief"]),
    }
    results.pop("_agent_runs", None)

    _overview_cache["data"] = results
    _overview_cache["ts"] = time.time()

    return results


def trigger_morning(payload: dict[str, Any]) -> dict[str, Any]:
    diag = _mysql_diagnostics()
    if not bool(diag.get("ok")):
        return {
            "ok": False,
            "workflow": "ai_quant.morning_brief",
            "result": None,
            "message": "数据库未配置或连接失败，请先完成数据配置与采集后再生成晨会简报",
        }
    tables = diag.get("tables") if isinstance(diag.get("tables"), dict) else {}
    core = ["trade_stock_master", "trade_stock_daily"]
    for name in core:
        it = tables.get(name) if isinstance(tables, dict) else None
        exists = bool((it or {}).get("exists")) if isinstance(it, dict) else False
        rows = (it or {}).get("rows") if isinstance(it, dict) else None
        if not exists or not isinstance(rows, int) or rows <= 0:
            return {
                "ok": False,
                "workflow": "ai_quant.morning_brief",
                "result": None,
                "message": "数据库为空或核心数据表缺失，请先采集行情数据后再生成晨会简报",
            }
    from importlib import import_module

    morning_brief = import_module("modules.console.morning_brief")
    result = morning_brief.run_morning_workflow(payload)
    return {
        "ok": True,
        "workflow": "ai_quant.morning_brief",
        "result": {
            "report_html": result.get("report_html"),
            "report_md": result.get("report_md"),
            "messages": result.get("messages", []),
            "picked_stocks": result.get("picked_stocks", []),
            "industry_rank": result.get("industry_rank", []),
        },
    }
