from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..db import execute, query_dict
from .models import ReportModel, ReportTask, ReportTaskStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_task(r: dict[str, Any]) -> ReportTask:
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
    return ReportTask(
        task_id=str(r.get("task_id") or ""),
        model=ReportModel(str(r.get("model") or "")),
        stock_codes=stock_codes if isinstance(stock_codes, list) else [],
        stock_names=stock_names if isinstance(stock_names, list) else [],
        status=ReportTaskStatus(str(r.get("status") or "")),
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else _now_iso(),
        started_at=started_at.isoformat() if hasattr(started_at, "isoformat") else None,
        finished_at=finished_at.isoformat() if hasattr(finished_at, "isoformat") else None,
        error_message=r.get("error_message"),
    )


def get_task(conn, *, task_id: str) -> ReportTask:
    rows = query_dict(conn, "SELECT * FROM trade_report_task WHERE task_id=%s", (task_id,))
    if not rows:
        raise RuntimeError("task not found")
    return _row_to_task(rows[0])


def mark_running(conn, *, task_id: str) -> None:
    execute(conn, "UPDATE trade_report_task SET status=%s, started_at=NOW() WHERE task_id=%s", (ReportTaskStatus.running.value, task_id))


def mark_failed(conn, *, task_id: str, error_message: str) -> None:
    execute(
        conn,
        "UPDATE trade_report_task SET status=%s, finished_at=NOW(), error_message=%s WHERE task_id=%s",
        (ReportTaskStatus.failed.value, error_message, task_id),
    )


def mark_success(conn, *, task_id: str, report_markdown: str) -> None:
    execute(
        conn,
        "UPDATE trade_report_task SET status=%s, finished_at=NOW(), report_markdown=%s WHERE task_id=%s",
        (ReportTaskStatus.success.value, report_markdown, task_id),
    )

