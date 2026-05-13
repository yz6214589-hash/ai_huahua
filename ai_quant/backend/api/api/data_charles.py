"""
数据查询和导出API模块
提供市场数据的查询、分页、过滤和导出功能
支持查询股票行情、财务数据、新闻、宏观指标等多种数据集
支持CSV和JSON格式的数据导出
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from db import connect, load_mysql_config, query_dict
from services.charles.integration import get_job_store_dir
from runtime.logging_service import get_logger

logger = get_logger("data")

router = APIRouter(prefix="/api", tags=["data"])


def _contains_injection(v: str) -> bool:
    """
    检测字符串中是否包含SQL注入特征
    
    检查常见的SQL注入字符组合，防止恶意输入
    
    Args:
        v: 待检测的字符串
        
    Returns:
        bool: 包含注入特征返回True，否则返回False
    """
    s = str(v or "")
    bad = (";", "--", "/*", "*/")
    return any(x in s for x in bad)


def _project_root() -> Path:
    """
    获取项目根目录路径
    
    Returns:
        Path: 项目根目录
    """
    return Path(__file__).resolve().parents[4]


def _now_iso() -> str:
    """
    获取当前时间ISO格式字符串
    
    Returns:
        str: 当前时间，精确到秒
    """
    return datetime.now().isoformat(timespec="seconds")


def _dataset_def(dataset: str) -> tuple[str, list[str], str]:
    """
    获取数据集定义信息
    
    定义支持查询的数据集及其字段配置
    
    Args:
        dataset: 数据集名称
        
    Returns:
        tuple: (表名, 允许的过滤字段列表, 默认排序字段)
        
    Raises:
        HTTPException: 数据集名称不合法时抛出
    """
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
    """
    判断异常是否为表不存在错误
    
    MySQL错误码1146表示表不存在，1051表示删除不存在的表
    
    Args:
        exc: 异常对象
        
    Returns:
        bool: 表不存在错误返回True
    """
    code = None
    try:
        code = int((getattr(exc, "args", [None]) or [None])[0])
    except Exception:
        code = None
    return code in (1146, 1051)


def _connect_and_query():
    """
    建立数据库连接并返回查询函数
    
    Returns:
        tuple: (数据库连接, 查询函数)
    """
    cfg = load_mysql_config()
    conn = connect(cfg)
    return conn, query_dict


@router.get("/data/summary")
def data_summary() -> dict[str, object]:
    """
    获取数据源汇总信息
    
    返回当前支持查询的数据集列表和状态信息
    
    Returns:
        dict: 数据源信息
    """
    return {
        "source": "charles",
        "status": "ready",
        "datasets": [
            "trade_stock_daily",          # 股票日线行情
            "trade_stock_financial",        # 股票财务数据
            "trade_stock_news",            # 股票新闻
            "trade_macro_indicator",        # 宏观指标
            "trade_rate_daily",            # 利率日度数据
            "trade_report_consensus",       # 研报共识
            "trade_calendar_event",         # 日历事件
        ],
        "job_store_dir": get_job_store_dir(),
    }


@router.get("/data/{dataset}")
def data_get(request: Request, dataset: str, page: int = 1, pageSize: int = 50) -> dict[str, Any]:
    """
    分页查询数据集

    支持按多种字段过滤，包括股票代码（支持批量）、日期范围等
    自动防御SQL注入攻击

    Args:
        request: HTTP请求对象
        dataset: 数据集名称
        page: 页码，从1开始
        pageSize: 每页记录数，最大200

    Returns:
        dict: 包含分页信息和数据行的字典
    """
    logger.info("数据查询请求", extra={
        "dataset": dataset,
        "page": page,
        "pageSize": pageSize
    })
    table, allowed, order_col = _dataset_def(dataset)
    page = max(page, 1)
    page_size = min(max(pageSize, 1), 200)

    # 解析查询参数，过滤分页参数
    filters: dict[str, Any] = {}
    for k, v in request.query_params.items():
        if k in ("page", "pageSize"):
            continue
        if isinstance(v, str) and _contains_injection(v):
            raise HTTPException(status_code=400, detail="非法输入")
        filters[k] = v

    # 构建WHERE条件
    where = []
    params: list[Any] = []
    for k, v in list(filters.items()):
        if k not in allowed or v in (None, ""):
            continue
        # 处理股票代码批量查询（逗号分隔）
        if k == "stock_code" and isinstance(v, str) and "," in v:
            codes = [p.strip() for p in v.split(",") if p.strip()]
            if not codes:
                continue
            ph = ",".join(["%s"] * len(codes))
            where.append(f"{k} IN ({ph})")
            params.extend(codes)
            continue
        # 处理日期范围查询（逗号分隔起止日期）
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
            # 表不存在时返回空结果而非报错
            if _is_missing_table_error(exc):
                logger.warning("数据查询表不存在", extra={
                    "dataset": dataset,
                    "error": str(exc)
                })
                return {"page": page, "pageSize": page_size, "total": 0, "rows": []}
            raise
        total_count = int(total[0]["c"]) if total else 0
        rows_count = len(rows)
        logger.info("数据查询完成", extra={
            "dataset": dataset,
            "total": total_count,
            "rows_count": rows_count,
            "page": page
        })
        return {
            "page": page,
            "pageSize": page_size,
            "total": total_count,
            "rows": rows,
        }
    finally:
        conn.close()


@router.post("/export")
def export_data(body: dict[str, Any]) -> Response:
    """
    导出数据集为CSV或JSON格式

    支持大数据量导出（最大50000条），使用流式响应避免内存溢出

    Args:
        body: 导出请求参数，包含dataset、format、filters、limit等

    Returns:
        Response: CSV或JSON格式的数据响应
    """
    dataset = str(body.get("dataset") or "").strip()
    fmt = str(body.get("format") or "").lower().strip()
    filters = body.get("filters") if isinstance(body.get("filters"), dict) else {}
    limit = min(max(int(body.get("limit") or 5000), 1), 50000)

    logger.info("数据导出请求", extra={
        "dataset": dataset,
        "format": fmt,
        "limit": limit
    })

    table, allowed, order_col = _dataset_def(dataset)
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="format must be csv/json")

    # 构建WHERE条件
    where = []
    params: list[Any] = []
    for k, v in filters.items():
        if k not in allowed or v in (None, ""):
            continue
        if isinstance(v, str) and _contains_injection(v):
            raise HTTPException(status_code=400, detail="非法输入")
        # 处理股票代码批量查询
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
        # 处理日期范围查询
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

    # JSON格式导出
    if fmt == "json":
        content = json.dumps(
            {"dataset": dataset, "exportedAt": _now_iso(), "filters": filters, "rows": rows},
            ensure_ascii=False,
            default=str,
        )
        return Response(content=content, media_type="application/json")

    # CSV格式流式导出
    def iter_csv():
        """流式生成CSV内容"""
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


@router.get("/financial-hot")
def financial_hot() -> dict[str, Any]:
    """
    财经热点接口
    返回今日日历事件（财经日历）和最近重要新闻
    """
    from db import load_mysql_config
    import pymysql
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=int(cfg.port or 3306),
        user=cfg.user, password=cfg.password,
        database=cfg.database
    )
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute(
            """
            SELECT event_date, country, importance, source, event_name
            FROM trade_calendar_event
            WHERE event_date = %s
            ORDER BY FIELD(importance, '高', '中', '低'), source
            LIMIT 50
            """,
            (today,)
        )
        events = cur.fetchall() or []
        cur.close()

        cur2 = conn.cursor(pymysql.cursors.DictCursor)
        cur2.execute(
            """
            SELECT stock_code, stock_name, title, source, published_at, url
            FROM trade_stock_news
            WHERE published_at >= DATE_SUB(NOW(), INTERVAL 3 DAY)
            ORDER BY published_at DESC
            LIMIT 20
            """
        )
        news = cur2.fetchall() or []
        cur2.close()

        return {
            "date": today,
            "events": [{"event_date": str(r["event_date"]), "country": r["country"] or "—",
                        "importance": r["importance"] or "—", "source": r["source"] or "—",
                        "event_name": r.get("event_name") or "—"} for r in events],
            "news": [{"stock_code": r["stock_code"], "stock_name": r.get("stock_name") or "—",
                      "title": r["title"] or "—", "source": r.get("source") or "—",
                      "published_at": str(r["published_at"]) if r.get("published_at") else "—",
                      "url": r.get("url") or ""} for r in news],
        }
    finally:
        conn.close()
