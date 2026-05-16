"""
股票筛选API模块
提供基于财务指标的股票筛选功能
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.db import connect, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("stock_select")

router = APIRouter(prefix="/api/v1/stock-select", tags=["stock-select"])


class StockSelectRequest(BaseModel):
    pe_min: float | None = None
    pe_max: float | None = None
    pb_min: float | None = None
    pb_max: float | None = None
    roe_min: float | None = None
    roe_max: float | None = None
    revenue_growth_min: float | None = None
    revenue_growth_max: float | None = None
    profit_growth_min: float | None = None
    profit_growth_max: float | None = None
    market_cap_min: float | None = None
    market_cap_max: float | None = None
    gross_margin_min: float | None = None
    gross_margin_max: float | None = None
    debt_ratio_max: float | None = None
    report_date: str | None = None
    page: int = 1
    page_size: int = 50


def _build_where_clause(params: dict[str, Any]) -> tuple[str, list[Any]]:
    """
    根据筛选参数构建WHERE子句

    Args:
        params: 筛选参数字典

    Returns:
        tuple: (WHERE子句字符串, 参数列表)
    """
    conditions = []
    values = []

    if params.get("pe_min") is not None:
        conditions.append("pe_ttm >= %s")
        values.append(params["pe_min"])

    if params.get("pe_max") is not None:
        conditions.append("pe_ttm <= %s")
        values.append(params["pe_max"])

    if params.get("pb_min") is not None:
        conditions.append("pb >= %s")
        values.append(params["pb_min"])

    if params.get("pb_max") is not None:
        conditions.append("pb <= %s")
        values.append(params["pb_max"])

    if params.get("roe_min") is not None:
        conditions.append("roe >= %s")
        values.append(params["roe_min"])

    if params.get("roe_max") is not None:
        conditions.append("roe <= %s")
        values.append(params["roe_max"])

    if params.get("revenue_growth_min") is not None:
        conditions.append("revenue_growth_yoy >= %s")
        values.append(params["revenue_growth_min"])

    if params.get("revenue_growth_max") is not None:
        conditions.append("revenue_growth_yoy <= %s")
        values.append(params["revenue_growth_max"])

    if params.get("profit_growth_min") is not None:
        conditions.append("profit_growth_yoy >= %s")
        values.append(params["profit_growth_min"])

    if params.get("profit_growth_max") is not None:
        conditions.append("profit_growth_yoy <= %s")
        values.append(params["profit_growth_max"])

    if params.get("market_cap_min") is not None:
        conditions.append("market_cap >= %s")
        values.append(params["market_cap_min"])

    if params.get("market_cap_max") is not None:
        conditions.append("market_cap <= %s")
        values.append(params["market_cap_max"])

    if params.get("gross_margin_min") is not None:
        conditions.append("gross_margin >= %s")
        values.append(params["gross_margin_min"])

    if params.get("gross_margin_max") is not None:
        conditions.append("gross_margin <= %s")
        values.append(params["gross_margin_max"])

    if params.get("debt_ratio_max") is not None:
        conditions.append("debt_ratio <= %s")
        values.append(params["debt_ratio_max"])

    if params.get("report_date"):
        conditions.append("report_date = %s")
        values.append(params["report_date"])

    where = " AND ".join(conditions) if conditions else "1=1"
    return where, values


@router.post("/query")
def stock_select(body: StockSelectRequest) -> dict[str, Any]:
    """
    基于财务指标筛选股票

    支持的筛选指标：
    - 估值指标：pe_ttm, pb, market_cap
    - 盈利指标：roe, gross_margin
    - 成长指标：revenue_growth_yoy, profit_growth_yoy
    - 财务健康：debt_ratio

    Args:
        body: 筛选参数

    Returns:
        dict: 包含分页信息和筛选结果的字典
    """
    logger.info("股票筛选请求", extra={
        "filters": {
            "pe": f"{body.pe_min}-{body.pe_max}",
            "pb": f"{body.pb_min}-{body.pb_max}",
            "roe": f"{body.roe_min}-{body.roe_max}",
            "revenue_growth": f"{body.revenue_growth_min}-{body.revenue_growth_max}",
            "profit_growth": f"{body.profit_growth_min}-{body.profit_growth_max}",
        }
    })

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception as e:
        logger.error("数据库连接失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="数据库连接失败")

    try:
        params = {
            "pe_min": body.pe_min,
            "pe_max": body.pe_max,
            "pb_min": body.pb_min,
            "pb_max": body.pb_max,
            "roe_min": body.roe_min,
            "roe_max": body.roe_max,
            "revenue_growth_min": body.revenue_growth_min,
            "revenue_growth_max": body.revenue_growth_max,
            "profit_growth_min": body.profit_growth_min,
            "profit_growth_max": body.profit_growth_max,
            "market_cap_min": body.market_cap_min,
            "market_cap_max": body.market_cap_max,
            "gross_margin_min": body.gross_margin_min,
            "gross_margin_max": body.gross_margin_max,
            "debt_ratio_max": body.debt_ratio_max,
            "report_date": body.report_date,
        }

        where, values = _build_where_clause(params)

        page = max(body.page, 1)
        page_size = min(max(body.page_size, 1), 200)
        offset = (page - 1) * page_size

        count_sql = f"""
            SELECT COUNT(DISTINCT stock_code) as total
            FROM trade_stock_financial
            WHERE {where}
        """
        count_result = query_dict(conn, count_sql, tuple(values))
        total = count_result[0]["total"] if count_result else 0

        data_sql = f"""
            SELECT
                f.stock_code,
                m.stock_name,
                m.sector_level1,
                m.sector_level2,
                f.report_date,
                f.pe_ttm,
                f.pb,
                f.market_cap,
                f.roe,
                f.gross_margin,
                f.net_margin,
                f.revenue_growth_yoy,
                f.profit_growth_yoy,
                f.debt_ratio,
                f.revenue,
                f.net_profit,
                f.eps
            FROM trade_stock_financial f
            LEFT JOIN trade_stock_master m ON f.stock_code = m.stock_code
            WHERE {where}
            ORDER BY f.report_date DESC, f.roe DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(values + [page_size, offset]))

        logger.info("股票筛选完成", extra={
            "total": total,
            "returned": len(rows)
        })

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "rows": rows,
            "filters_applied": {
                "pe": {"min": body.pe_min, "max": body.pe_max},
                "pb": {"min": body.pb_min, "max": body.pb_max},
                "roe": {"min": body.roe_min, "max": body.roe_max},
                "revenue_growth": {"min": body.revenue_growth_min, "max": body.revenue_growth_max},
                "profit_growth": {"min": body.profit_growth_min, "max": body.profit_growth_max},
                "market_cap": {"min": body.market_cap_min, "max": body.market_cap_max},
                "gross_margin": {"min": body.gross_margin_min, "max": body.gross_margin_max},
                "debt_ratio": {"max": body.debt_ratio_max},
            }
        }
    except Exception as e:
        logger.error("股票筛选失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"筛选失败: {str(e)}")
    finally:
        conn.close()


@router.get("/criteria")
def get_filter_criteria() -> dict[str, Any]:
    """
    获取可选的筛选指标列表及其说明

    Returns:
        dict: 筛选指标列表
    """
    return {
        "criteria": [
            {
                "name": "pe_ttm",
                "label": "市盈率TTM",
                "unit": "",
                "description": "市盈率越低，估值越便宜",
                "range": {"min": 0, "max": 100},
                "type": "range"
            },
            {
                "name": "pb",
                "label": "市净率",
                "unit": "",
                "description": "市净率越低，估值越便宜",
                "range": {"min": 0, "max": 10},
                "type": "range"
            },
            {
                "name": "roe",
                "label": "净资产收益率",
                "unit": "%",
                "description": "ROE越高盈利能力越强",
                "range": {"min": 0, "max": 50},
                "type": "range"
            },
            {
                "name": "revenue_growth_yoy",
                "label": "营收同比增长率",
                "unit": "%",
                "description": "营收增长率越高成长性越好",
                "range": {"min": -50, "max": 100},
                "type": "range"
            },
            {
                "name": "profit_growth_yoy",
                "label": "净利润同比增长率",
                "unit": "%",
                "description": "净利润增长率越高成长性越好",
                "range": {"min": -50, "max": 100},
                "type": "range"
            },
            {
                "name": "market_cap",
                "label": "总市值",
                "unit": "亿",
                "description": "公司总市值规模",
                "range": {"min": 0, "max": 10000},
                "type": "range"
            },
            {
                "name": "gross_margin",
                "label": "毛利率",
                "unit": "%",
                "description": "毛利率越高竞争力越强",
                "range": {"min": 0, "max": 100},
                "type": "range"
            },
            {
                "name": "debt_ratio",
                "label": "资产负债率",
                "unit": "%",
                "description": "资产负债率越低财务越健康",
                "range": {"min": 0, "max": 100},
                "type": "range"
            }
        ],
        "tips": [
            "PE在0-30之间通常被认为是价值投资的合理区间",
            "ROE大于15%表示公司盈利能力较强",
            "营收和净利润增长率大于0表示公司处于成长阶段",
            "资产负债率低于50%通常被认为是财务健康的",
            "建议结合多个指标综合筛选，避免单一指标选股"
        ]
    }
