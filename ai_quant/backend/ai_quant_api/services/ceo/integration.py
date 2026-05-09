from __future__ import annotations

from typing import Any

from ai_quant_api.db import connect, load_mysql_config, query_dict
from ai_quant_api.runtime.job_store import list_runs
from ai_quant_api.services.charles.integration import get_summary, list_job_runs
from ai_quant_api.services.ethan.integration import get_status as get_execution_status
from ai_quant_api.services.kris.integration import status as get_risk_status
from ai_quant_api.services.ceo.morning_brief import run_morning_workflow


def get_status() -> dict[str, Any]:
    return {
        "source": "ceo",
        "status": "ready",
        "features": ["morning"],
        "mode": "embedded",
    }


def _mysql_diagnostics() -> dict[str, Any]:
    cfg = load_mysql_config()
    base = {
        "config": {
            "host": cfg.host,
            "port": cfg.port,
            "user": cfg.user,
            "database": cfg.database,
        }
    }
    try:
        conn = connect(cfg)
    except Exception as exc:
        return {
            **base,
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
            **base,
            "ok": True,
            "server": {"version": version},
            "tables": table_diag,
        }
    except Exception as exc:
        return {
            **base,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "tables": {},
        }
    finally:
        conn.close()


def get_overview() -> dict[str, Any]:
    summary = get_summary()
    recent_jobs = list_job_runs(domain=None, limit=8)
    agent_runs = list_runs()
    morning_run = next((x for x in agent_runs if x.get("route") == "graph:morning_brief"), None)
    return {
        "data_latest": summary,
        "recent_jobs": recent_jobs,
        "execution_status": get_execution_status(),
        "risk_status": get_risk_status(),
        "morning": {
            "last_run": morning_run,
            "run_count": len([x for x in agent_runs if x.get("route") == "graph:morning_brief"]),
        },
        "mysql": _mysql_diagnostics(),
    }


def trigger_morning(payload: dict[str, Any]) -> dict[str, Any]:
    diag = _mysql_diagnostics()
    if not bool(diag.get("ok")):
        raise RuntimeError("数据库未配置或连接失败，请先完成数据配置与采集后再生成晨会简报")
    tables = diag.get("tables") if isinstance(diag.get("tables"), dict) else {}
    core = ["trade_stock_master", "trade_stock_daily"]
    for name in core:
        it = tables.get(name) if isinstance(tables, dict) else None
        exists = bool((it or {}).get("exists")) if isinstance(it, dict) else False
        rows = (it or {}).get("rows") if isinstance(it, dict) else None
        if not exists or not isinstance(rows, int) or rows <= 0:
            raise RuntimeError("数据库为空或核心数据表缺失，请先采集行情数据后再生成晨会简报")
    result = run_morning_workflow(payload)
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
