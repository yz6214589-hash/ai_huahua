from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from ai_quant_api.runtime.job_store import list_runs
from ai_quant_api.services.charles.integration import get_summary, list_job_runs
from ai_quant_api.services.ethan.integration import get_status as get_execution_status
from ai_quant_api.services.kris.integration import status as get_risk_status


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _ensure_ceo_import_path() -> None:
    root = _project_root()
    paths = [str(root), str(root / "ceo")]
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)


def get_status() -> dict[str, Any]:
    return {
        "source": "ceo",
        "status": "ready",
        "features": ["morning", "live", "backtest"],
        "project_path": str(_project_root() / "ceo"),
    }


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
    }


def trigger_morning(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_ceo_import_path()
    top_n_industries = int(payload.get("top_n_industries", 3) or 3)
    top_n_stocks = int(payload.get("top_n_stocks", 5) or 5)
    sample_stocks = int(payload.get("sample_stocks", 15) or 15)
    lookback_days = int(payload.get("lookback_days", 90) or 90)
    os.environ.setdefault("PYTHONUTF8", "1")

    try:
        from ceo.morning_brief.graph import build_graph  # type: ignore

        graph = build_graph()
        result = graph.invoke(
            {
                "trigger_time": None,
                "industry_level": 2,
                "top_n_industries": top_n_industries,
                "top_n_stocks": top_n_stocks,
                "lookback_days": lookback_days,
                "sample_stocks": sample_stocks,
                "messages": [],
            }
        )
        return {
            "ok": True,
            "workflow": "ceo.morning_brief",
            "result": {
                "report_html": result.get("report_html"),
                "messages": result.get("messages", []),
                "picked_stocks": result.get("picked_stocks", []),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "workflow": "ceo.morning_brief",
            "error": f"{type(exc).__name__}: {exc}",
        }
