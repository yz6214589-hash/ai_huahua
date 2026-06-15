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

from core.db import connect, load_mysql_config, query_dict
from core.data import get_job_store_dir, get_watchlist
from infra.storage.logging_service import get_logger

logger = get_logger("data")

router = APIRouter(prefix="/api/v1", tags=["data"])


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
def data_get(request: Request, dataset: str, page: int = 1, pageSize: int = 50, page_size: int = 50) -> dict[str, Any]:
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
    # 优先使用 page_size 参数，如果没有则使用 pageSize
    effective_page_size = page_size if page_size != 50 or request.query_params.get("page_size") else pageSize
    page_size = min(max(effective_page_size, 1), 200)

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
            # 数据条数：使用 INFORMATION_SCHEMA.TABLES 读 MySQL 维护的统计，避免全表 COUNT
            try:
                from core.db import load_mysql_config
                _cfg = load_mysql_config()
                _stat_rows = query_dict_func(
                    conn,
                    "SELECT TABLE_ROWS AS c FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                    (_cfg.database, table),
                )
                total_count = int(_stat_rows[0]["c"]) if _stat_rows else 0
            except Exception:
                # 回退方案：使用原始 COUNT(*) 查询
                total = query_dict_func(conn, count_sql, tuple(params))
                total_count = int(total[0]["c"]) if total else 0
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


@router.get("/macro/latest")
def macro_latest() -> dict[str, Any]:
    """
    获取宏观指标最新数据
    返回CPI、PPI、PMI、M2、社融、LPR、国债收益率等宏观指标的最新值
    每个指标分别查询最新非空值（因发布日期间隔不同）
    """
    from core.db import load_mysql_config
    import pymysql
    
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=int(cfg.port or 3306),
        user=cfg.user, password=cfg.password,
        database=cfg.database
    )
    
    try:
        cur = conn.cursor(pymysql.cursors.DictCursor)
        indicators = []
        
        # 定义需要查询的指标列表：(indicator_key, 表名, 字段名, 日期字段, 显示名称, 数据源)
        macro_indicators = [
            ('CPI', 'trade_macro_indicator', 'cpi_yoy', 'indicator_date', 'CPI（居民消费价格指数）', 'AkShare'),
            ('PPI', 'trade_macro_indicator', 'ppi_yoy', 'indicator_date', 'PPI（生产价格指数）', 'AkShare'),
            ('PMI', 'trade_macro_indicator', 'pmi', 'indicator_date', 'PMI（采购经理指数）', 'AkShare'),
            ('M2', 'trade_macro_indicator', 'm2_yoy', 'indicator_date', 'M2（广义货币供应量同比）', 'AkShare'),
            ('社融', 'trade_macro_indicator', 'shrzgm', 'indicator_date', '社融（社会融资规模）', 'AkShare'),
            ('LPR', 'trade_macro_indicator', 'lpr_1y', 'indicator_date', 'LPR（1年期贷款市场报价利率）', 'AkShare'),
            ('LPR5Y', 'trade_macro_indicator', 'lpr_5y', 'indicator_date', 'LPR（5年期贷款市场报价利率）', 'AkShare'),
        ]
        
        for key, table, col, date_col, name, source in macro_indicators:
            cur.execute(f"""
                SELECT {date_col} AS dt, {col} AS val
                FROM {table}
                WHERE {col} IS NOT NULL
                ORDER BY {date_col} DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row and row['val'] is not None:
                indicators.append({
                    'indicator': key,
                    'name': name,
                    'value': float(row['val']),
                    'date': str(row['dt']),
                    'source': source
                })
        
        # 查询国债收益率和市场情绪指标（从 trade_rate_daily 表）
        bond_indicators = [
            ('CN10Y', 'trade_rate_daily', 'cn_bond_10y', 'rate_date', 'CN10Y（中国10年期国债收益率）', 'Wind'),
            ('US10Y', 'trade_rate_daily', 'us_bond_10y', 'rate_date', 'US10Y（美国10年期国债收益率）', 'AkShare'),
            ('FearGreed', 'trade_rate_daily', 'fear_greed', 'rate_date', 'FearGreed（恐惧贪婪指数）', 'Alternative.me'),
            ('VIX', 'trade_rate_daily', 'vix', 'rate_date', 'VIX（标普500波动率指数）', '多级降级-Yahoo/FRED/AkShare(ETF代理)'),
            ('OVX', 'trade_rate_daily', 'ovx', 'rate_date', 'OVX（原油波动率指数）', '多级降级-Yahoo/FRED/AkShare(原油期货代理)'),
            ('GVZ', 'trade_rate_daily', 'gvz', 'rate_date', 'GVZ（黄金波动率指数）', '多级降级-Yahoo/FRED/AkShare(黄金期货代理)'),
            ('iVIX', 'trade_rate_daily', 'ivix', 'rate_date', 'iVIX（中国波动率指数）', 'AkShare/Tushare'),
        ]
        for key, table, col, date_col, name, source in bond_indicators:
            cur.execute(f"""
                SELECT {date_col} AS dt, {col} AS val
                FROM {table}
                WHERE {col} IS NOT NULL
                ORDER BY {date_col} DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row and row['val'] is not None:
                indicators.append({
                    'indicator': key,
                    'name': name,
                    'value': float(row['val']),
                    'date': str(row['dt']),
                    'source': source
                })
        
        # 查询 QVIX（中国期权波动率指数）
        cur.execute("""
            SELECT trade_date AS dt, qvix_50etf AS val
            FROM trade_qvix_daily
            WHERE qvix_50etf IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row and row['val'] is not None:
            indicators.append({
                'indicator': 'QVIX',
                'name': 'QVIX（中国期权波动率指数）',
                'value': float(row['val']),
                'date': str(row['dt']),
                'source': 'AkShare'
            })
        
        cur.close()
        
        # 计算综合情绪
        overall_sentiment = '中性'
        action_suggestion = '观望'
        pmi_value = next((i['value'] for i in indicators if i['indicator'] == 'PMI'), None)
        if pmi_value and pmi_value >= 50:
            overall_sentiment = '偏乐观'
            action_suggestion = '可适度关注'
        elif pmi_value and pmi_value < 50:
            overall_sentiment = '偏悲观'
            action_suggestion = '谨慎观望'
        
        return {
            'indicators': indicators,
            'composite': {
                'overall_sentiment': overall_sentiment,
                'action_suggestion': action_suggestion,
                'timestamp': datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.warning("获取宏观数据失败", extra={"error": str(e)})
        return {
            'indicators': [],
            'composite': {
                'overall_sentiment': '未知',
                'action_suggestion': '数据获取失败',
                'timestamp': datetime.now().isoformat()
            }
        }
    finally:
        conn.close()


@router.get("/macro/history/{indicator}")
def macro_history(indicator: str, days: int = 90) -> dict[str, Any]:
    """
    获取宏观指标历史数据
    Args:
        indicator: 指标名称（CPI/PPI/PMI/LPR/CN10Y/US10Y）
        days: 回溯天数，默认90天
    """
    from core.db import load_mysql_config
    import pymysql
    
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=int(cfg.port or 3306),
        user=cfg.user, password=cfg.password,
        database=cfg.database
    )
    
    try:
        days = max(1, min(days, 365))
        table_map = {
            'CPI': ('trade_macro_indicator', 'cpi_yoy', 'indicator_date'),
            'PPI': ('trade_macro_indicator', 'ppi_yoy', 'indicator_date'),
            'PMI': ('trade_macro_indicator', 'pmi', 'indicator_date'),
            'M2': ('trade_macro_indicator', 'm2_yoy', 'indicator_date'),
            '社融': ('trade_macro_indicator', 'shrzgm', 'indicator_date'),
            'LPR': ('trade_macro_indicator', 'lpr_1y', 'indicator_date'),
            'LPR5Y': ('trade_macro_indicator', 'lpr_5y', 'indicator_date'),
            'CN10Y': ('trade_rate_daily', 'cn_bond_10y', 'rate_date'),
            'US10Y': ('trade_rate_daily', 'us_bond_10y', 'rate_date'),
            'FearGreed': ('trade_rate_daily', 'fear_greed', 'rate_date'),
            'VIX': ('trade_rate_daily', 'vix', 'rate_date'),
            'OVX': ('trade_rate_daily', 'ovx', 'rate_date'),
            'GVZ': ('trade_rate_daily', 'gvz', 'rate_date'),
            'iVIX': ('trade_rate_daily', 'ivix', 'rate_date'),
            'QVIX': ('trade_qvix_daily', 'qvix_50etf', 'trade_date'),
        }
        
        table_info = table_map.get(indicator)
        if not table_info:
            return {'indicator': indicator, 'name': indicator, 'data': []}
        
        table, col, date_col = table_info
        
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute(f"""
            SELECT {date_col} AS date, {col} AS value
            FROM {table}
            WHERE {col} IS NOT NULL
            ORDER BY {date_col} DESC
            LIMIT %s
        """, (days,))
        rows = cur.fetchall() or []
        cur.close()
        
        data = [{
            'date': str(r['date']),
            'value': float(r['value']) if r['value'] else None
        } for r in rows]
        
        # 按日期升序排列
        data.reverse()
        
        indicator_labels = {
            'CPI': 'CPI（居民消费价格指数）',
            'PPI': 'PPI（生产价格指数）',
            'PMI': 'PMI（采购经理指数）',
            'M2': 'M2（广义货币供应量同比）',
            '社融': '社融（社会融资规模）',
            'LPR': 'LPR（1年期贷款市场报价利率）',
            'LPR5Y': 'LPR（5年期贷款市场报价利率）',
            'CN10Y': 'CN10Y（中国10年期国债收益率）',
            'US10Y': 'US10Y（美国10年期国债收益率）',
            'FearGreed': 'FearGreed（恐惧贪婪指数）',
            'VIX': 'VIX（标普500波动率指数）',
            'OVX': 'OVX（原油波动率指数）',
            'GVZ': 'GVZ（黄金波动率指数）',
            'iVIX': 'iVIX（中国波动率指数）',
            'QVIX': 'QVIX（中国期权波动率指数）',
        }
        
        return {
            'indicator': indicator,
            'name': indicator_labels.get(indicator, indicator),
            'data': data
        }
    except Exception as e:
        logger.warning("获取宏观历史数据失败", extra={"error": str(e), "indicator": indicator})
        return {'indicator': indicator, 'name': indicator, 'data': []}
    finally:
        conn.close()


@router.get("/financial-hot")
def financial_hot() -> dict[str, Any]:
    """
    财经热点接口
    返回今日市场财经热点事件（财经日历+宏观事件）和近期自选股重要新闻
    """
    from core.db import load_mysql_config
    import pymysql
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=int(cfg.port or 3306),
        user=cfg.user, password=cfg.password,
        database=cfg.database
    )
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # 1. 查询市场财经热点事件（财经日历：宏观经济数据发布、利率决议等）
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute(
            """
            SELECT event_date, event_time, country, category, title,
                   importance, previous_value, forecast_value, actual_value,
                   source, source_url
            FROM trade_calendar_event
            WHERE event_date >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
              AND event_date <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
            ORDER BY event_date ASC, FIELD(importance, 3, 2, 1), event_time ASC
            LIMIT 50
            """
        )
        events_raw = cur.fetchall() or []
        cur.close()

        # 2. 查询近期自选股重要新闻
        watchlist_data = get_watchlist()
        watchlist_items = watchlist_data.get("items", [])
        watchlist_codes = [item["stock_code"] for item in watchlist_items if item.get("stock_code")]

        news_raw = []
        if watchlist_codes:
            # 构建IN子句的占位符
            placeholders = ",".join(["%s"] * len(watchlist_codes))
            cur2 = conn.cursor(pymysql.cursors.DictCursor)
            cur2.execute(
                f"""
                SELECT n.stock_code, m.stock_name, n.title, n.source, n.published_at, n.source_url
                FROM trade_stock_news n
                LEFT JOIN trade_stock_master m ON n.stock_code = m.stock_code
                WHERE n.published_at >= DATE_SUB(NOW(), INTERVAL 3 DAY)
                AND n.stock_code IN ({placeholders})
                ORDER BY n.published_at DESC
                LIMIT 50
                """,
                tuple(watchlist_codes)
            )
            news_raw = cur2.fetchall() or []
            cur2.close()

        # 重要性数字转中文
        def _imp_label(v):
            try:
                n = int(v)
            except Exception:
                return "中"
            return "高" if n >= 3 else "低" if n <= 1 else "中"

        # 国家代码转中文
        def _country_label(v):
            m = {"CN": "中国", "US": "美国", "EU": "欧洲", "JP": "日本"}
            return m.get(v, v or "—")

        # events 按标题去重
        seen_titles = set()
        events_dedup = []
        for r in events_raw:
            t = (r.get("title") or "").strip()
            if t and t not in seen_titles:
                seen_titles.add(t)
                events_dedup.append(r)

        # news 按标题去重
        seen_news_titles = set()
        news_dedup = []
        for r in news_raw:
            t = (r.get("title") or "").strip()
            if t and t not in seen_news_titles:
                seen_news_titles.add(t)
                news_dedup.append(r)

        return {
            "updated_at": now_str,
            "events": [{"event_date": str(r["event_date"]) if r.get("event_date") else "—",
                        "event_time": r.get("event_time") or "",
                        "country": _country_label(r.get("country")),
                        "category": r.get("category") or "other",
                        "title": r["title"] or "—",
                        "importance": _imp_label(r.get("importance")),
                        "previous_value": r.get("previous_value") or "",
                        "forecast_value": r.get("forecast_value") or "",
                        "actual_value": r.get("actual_value") or "",
                        "source": r.get("source") or "—",
                        "url": r.get("source_url") or ""} for r in events_dedup],
            "news": [{"stock_code": r["stock_code"] or "—",
                      "stock_name": r.get("stock_name") or "—",
                      "title": r["title"] or "—",
                      "source": r.get("source") or "—",
                      "published_at": str(r["published_at"]) if r.get("published_at") else "—",
                      "url": r.get("source_url") or ""} for r in news_dedup],
        }
    finally:
        conn.close()
