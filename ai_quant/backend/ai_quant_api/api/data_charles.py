from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ai_quant_api.db import connect, load_mysql_config, query_dict
from ai_quant_api.services.charles.integration import get_job_store_dir

router = APIRouter(prefix="/api", tags=["data"])


def _contains_injection(v: str) -> bool:
    s = str(v or "")
    bad = (";", "--", "/*", "*/")
    return any(x in s for x in bad)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dataset_def(dataset: str) -> tuple[str, list[str], str]:
    mapping: dict[str, tuple[str, list[str], str]] = {
        "trade_stock_daily": ("trade_stock_daily", ["stock_code", "trade_date"], "trade_date"),
        "trade_stock_financial": ("trade_stock_financial", ["stock_code", "report_date", "data_source"], "report_date"),
        "trade_stock_news": ("trade_stock_news", ["stock_code", "news_type", "published_at"], "published_at"),
        "trade_macro_indicator": ("trade_macro_indicator", ["indicator_date"], "indicator_date"),
        "trade_rate_daily": ("trade_rate_daily", ["rate_date"], "rate_date"),
        "trade_report_consensus": ("trade_report_consensus", ["stock_code", "broker", "report_date"], "report_date"),
        "trade_calendar_event": ("trade_calendar_event", ["event_date", "country", "importance", "source"], "event_date"),
    }
    if dataset not in mapping:
        raise HTTPException(status_code=400, detail="unknown dataset")
    return mapping[dataset]


def _is_missing_table_error(exc: Exception) -> bool:
    code = None
    try:
        code = int((getattr(exc, "args", [None]) or [None])[0])
    except Exception:
        code = None
    return code in (1146, 1051)


def _connect_and_query():
    cfg = load_mysql_config()
    conn = connect(cfg)
    return conn, query_dict


@router.get("/data/summary")
def data_summary() -> dict[str, object]:
    return {
        "source": "charles",
        "status": "ready",
        "datasets": [
            "trade_stock_daily",
            "trade_stock_financial",
            "trade_stock_news",
            "trade_macro_indicator",
            "trade_rate_daily",
            "trade_report_consensus",
            "trade_calendar_event",
        ],
        "job_store_dir": get_job_store_dir(),
    }


@router.get("/data/{dataset}")
def data_get(request: Request, dataset: str, page: int = 1, pageSize: int = 50) -> dict[str, Any]:
    table, allowed, order_col = _dataset_def(dataset)
    page = max(page, 1)
    page_size = min(max(pageSize, 1), 200)

    filters: dict[str, Any] = {}
    for k, v in request.query_params.items():
        if k in ("page", "pageSize"):
            continue
        if isinstance(v, str) and _contains_injection(v):
            raise HTTPException(status_code=400, detail="非法输入")
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
            continue
        where.append(f"{k} = %s")
        params.append(v)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * page_size
    sql = f"SELECT * FROM {table}{where_sql} ORDER BY {order_col} DESC LIMIT %s OFFSET %s"
    count_sql = f"SELECT COUNT(*) AS c FROM {table}{where_sql}"

    try:
        conn, query_dict_func = _connect_and_query()
    except Exception:
        return {"page": page, "pageSize": page_size, "total": 0, "rows": []}
    try:
        try:
            total = query_dict_func(conn, count_sql, tuple(params))
            rows = query_dict_func(conn, sql, tuple(params + [page_size, offset]))
        except Exception as exc:
            if _is_missing_table_error(exc):
                return {"page": page, "pageSize": page_size, "total": 0, "rows": []}
            raise
        return {
            "page": page,
            "pageSize": page_size,
            "total": int(total[0]["c"]) if total else 0,
            "rows": rows,
        }
    finally:
        conn.close()


@router.post("/export")
def export_data(body: dict[str, Any]) -> Response:
    dataset = str(body.get("dataset") or "").strip()
    fmt = str(body.get("format") or "").lower().strip()
    filters = body.get("filters") if isinstance(body.get("filters"), dict) else {}
    limit = min(max(int(body.get("limit") or 5000), 1), 50000)

    table, allowed, order_col = _dataset_def(dataset)
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="format must be csv/json")

    where = []
    params: list[Any] = []
    for k, v in filters.items():
        if k not in allowed or v in (None, ""):
            continue
        if isinstance(v, str) and _contains_injection(v):
            raise HTTPException(status_code=400, detail="非法输入")
        if k == "stock_code" and isinstance(v, str) and "," in v:
            codes = [p.strip() for p in v.split(",") if p.strip()]
            if not codes:
                continue
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
            continue
        where.append(f"{k} = %s")
        params.append(v)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM {table}{where_sql} ORDER BY {order_col} DESC LIMIT %s"

    rows: list[dict[str, Any]] = []
    try:
        conn, query_dict_func = _connect_and_query()
    except Exception:
        conn = None
        query_dict_func = None
    if conn is not None and query_dict_func is not None:
        try:
            try:
                rows = query_dict_func(conn, sql, tuple(params + [limit]))
            except Exception as exc:
                if not _is_missing_table_error(exc):
                    raise
                rows = []
        finally:
            conn.close()

    if fmt == "json":
        content = json.dumps(
            {"dataset": dataset, "exportedAt": _now_iso(), "filters": filters, "rows": rows},
            ensure_ascii=False,
            default=str,
        )
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

    filename = f"{dataset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(iter_csv(), media_type="text/csv; charset=utf-8", headers=headers)
