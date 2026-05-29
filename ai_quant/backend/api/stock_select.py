"""
股票筛选API模块
提供基于财务指标的股票筛选功能
"""

from __future__ import annotations

import os
from typing import Any

import pymysql
from fastapi import APIRouter, HTTPException
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
    net_margin_min: float | None = None
    net_margin_max: float | None = None
    debt_ratio_min: float | None = None
    debt_ratio_max: float | None = None
    report_date: str | None = None
    page: int = 1
    page_size: int = 50
    operating_margin_min: float | None = None
    operating_margin_max: float | None = None
    quick_ratio_min: float | None = None
    quick_ratio_max: float | None = None
    asset_turnover_min: float | None = None
    asset_turnover_max: float | None = None
    free_cash_flow_min: float | None = None
    free_cash_flow_max: float | None = None
    dividend_yield_min: float | None = None
    dividend_yield_max: float | None = None
    ebitda_min: float | None = None
    ebitda_max: float | None = None
    ev_ebitda_min: float | None = None
    ev_ebitda_max: float | None = None
    industries: list[str] | None = None


FILTER_FIELD_MAPPING: dict[str, str] = {
    "pe": "pe_ttm",
    "pb": "pb",
    "roe": "roe",
    "revenue_growth": "revenue_growth_yoy",
    "profit_growth": "profit_growth_yoy",
    "market_cap": "market_cap",
    "gross_margin": "gross_margin",
    "operating_margin": "operating_margin",
    "debt_ratio": "debt_ratio",
    "quick_ratio": "quick_ratio",
    "asset_turnover": "total_asset_turnover",
    "free_cash_flow": "free_cash_flow",
    "dividend_yield": "dividend_yield",
    "ebitda": "ebitda",
    "ev_ebitda": "ev_ebitda",
    "net_margin": "net_margin",
}

# 数据库中存储为比率的字段（0.10 表示 10%），前端传入百分比值（10 表示 10%），
# 查询时需要将前端值除以 100 转换为比率
RATIO_FIELDS: set[str] = {
    "roe", "gross_margin", "net_margin", "operating_margin",
    "revenue_growth", "profit_growth", "dividend_yield",
    "debt_ratio",
}


def _build_where_clause(params: dict[str, Any]) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    values: list[Any] = []

    for prefix, db_column in FILTER_FIELD_MAPPING.items():
        min_val = params.get(f"{prefix}_min")
        if min_val is not None:
            conditions.append(f"f.{db_column} >= %s")
            if prefix in RATIO_FIELDS:
                min_val = min_val / 100.0
            values.append(min_val)

        max_val = params.get(f"{prefix}_max")
        if max_val is not None:
            conditions.append(f"f.{db_column} <= %s")
            if prefix in RATIO_FIELDS:
                max_val = max_val / 100.0
            values.append(max_val)

    if params.get("report_date"):
        conditions.append("f.report_date = %s")
        values.append(params["report_date"])

    # 行业筛选 - sector_level1 在 trade_stock_master 表中
    industries = params.get("industries")
    if industries:
        placeholders = ",".join(["%s"] * len(industries))
        conditions.append(f"m.sector_level1 IN ({placeholders})")
        values.extend(industries)

    where = " AND ".join(conditions) if conditions else "1=1"
    return where, values


def _create_direct_connection(cfg):
    """创建独立的数据库连接（非连接池），使用较长的超时时间"""
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5,
        read_timeout=15,
        write_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )


# 子查询SQL常量：取每只股票最新的报告期数据
_LATEST_REPORT_SUBQUERY = """
    SELECT f2.*
    FROM trade_stock_financial f2
    INNER JOIN (
        SELECT stock_code, MAX(report_date) as latest_date
        FROM trade_stock_financial
        GROUP BY stock_code
    ) latest ON f2.stock_code = latest.stock_code AND f2.report_date = latest.latest_date
"""


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
        conn = _create_direct_connection(cfg)
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
            "net_margin_min": body.net_margin_min,
            "net_margin_max": body.net_margin_max,
            "debt_ratio_min": body.debt_ratio_min,
            "debt_ratio_max": body.debt_ratio_max,
            "operating_margin_min": body.operating_margin_min,
            "operating_margin_max": body.operating_margin_max,
            "quick_ratio_min": body.quick_ratio_min,
            "quick_ratio_max": body.quick_ratio_max,
            "asset_turnover_min": body.asset_turnover_min,
            "asset_turnover_max": body.asset_turnover_max,
            "free_cash_flow_min": body.free_cash_flow_min,
            "free_cash_flow_max": body.free_cash_flow_max,
            "dividend_yield_min": body.dividend_yield_min,
            "dividend_yield_max": body.dividend_yield_max,
            "ebitda_min": body.ebitda_min,
            "ebitda_max": body.ebitda_max,
            "ev_ebitda_min": body.ev_ebitda_min,
            "ev_ebitda_max": body.ev_ebitda_max,
            "report_date": body.report_date,
            "industries": body.industries,
        }

        where, values = _build_where_clause(params)

        page = max(body.page, 1)
        page_size = min(max(body.page_size, 1), 200)
        offset = (page - 1) * page_size

        # 统计总数（使用子查询确保每只股票只计算一次）
        count_sql = f"""
            SELECT COUNT(DISTINCT f.stock_code) as total
            FROM ({_LATEST_REPORT_SUBQUERY}) f
            LEFT JOIN trade_stock_master m ON f.stock_code = m.stock_code
            WHERE {where}
        """
        count_result = query_dict(conn, count_sql, tuple(values))
        total = count_result[0]["total"] if count_result else 0

        # 查询数据（使用子查询确保每只股票只取最新报告期数据）
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
                f.operating_margin,
                f.net_margin,
                f.revenue_growth_yoy,
                f.profit_growth_yoy,
                f.debt_ratio,
                f.quick_ratio,
                f.total_asset_turnover,
                f.revenue,
                f.net_profit,
                f.eps,
                f.free_cash_flow,
                f.dividend_yield,
                f.ebitda,
                f.ev_ebitda
            FROM ({_LATEST_REPORT_SUBQUERY}) f
            LEFT JOIN trade_stock_master m ON f.stock_code = m.stock_code
            WHERE {where}
            ORDER BY f.roe DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(values + [page_size, offset]))

        # 将比率字段转回百分比，方便前端展示
        ratio_db_columns = {FILTER_FIELD_MAPPING[k] for k in RATIO_FIELDS}
        for row in rows:
            for col in ratio_db_columns:
                if col in row and row[col] is not None:
                    row[col] = round(row[col] * 100, 4)

        logger.info("股票筛选完成", extra={
            "total": total,
            "returned": len(rows)
        })

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": rows,
            "filters_applied": {
                "pe": {"min": body.pe_min, "max": body.pe_max},
                "pb": {"min": body.pb_min, "max": body.pb_max},
                "roe": {"min": body.roe_min, "max": body.roe_max},
                "revenue_growth": {"min": body.revenue_growth_min, "max": body.revenue_growth_max},
                "profit_growth": {"min": body.profit_growth_min, "max": body.profit_growth_max},
                "market_cap": {"min": body.market_cap_min, "max": body.market_cap_max},
                "gross_margin": {"min": body.gross_margin_min, "max": body.gross_margin_max},
                "operating_margin": {"min": body.operating_margin_min, "max": body.operating_margin_max},
                "quick_ratio": {"min": body.quick_ratio_min, "max": body.quick_ratio_max},
                "asset_turnover": {"min": body.asset_turnover_min, "max": body.asset_turnover_max},
                "free_cash_flow": {"min": body.free_cash_flow_min, "max": body.free_cash_flow_max},
                "dividend_yield": {"min": body.dividend_yield_min, "max": body.dividend_yield_max},
                "ebitda": {"min": body.ebitda_min, "max": body.ebitda_max},
                "ev_ebitda": {"min": body.ev_ebitda_min, "max": body.ev_ebitda_max},
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
                "name": "operating_margin",
                "label": "营业利润率",
                "unit": "%",
                "description": "营业利润率越高盈利能力越强",
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
            },
            {
                "name": "quick_ratio",
                "label": "速动比率",
                "unit": "",
                "description": "速动比率越高短期偿债能力越强，通常1为合理",
                "range": {"min": 0, "max": 5},
                "type": "range"
            },
            {
                "name": "total_asset_turnover",
                "label": "总资产周转率",
                "unit": "次",
                "description": "总资产周转率越高资产运营效率越好",
                "range": {"min": 0, "max": 5},
                "type": "range"
            },
            {
                "name": "free_cash_flow",
                "label": "自由现金流",
                "unit": "亿",
                "description": "自由现金流越高公司现金创造能力越强",
                "range": {"min": -100, "max": 1000},
                "type": "range"
            },
            {
                "name": "dividend_yield",
                "label": "股息率",
                "unit": "%",
                "description": "股息率越高分红回报越高",
                "range": {"min": 0, "max": 20},
                "type": "range"
            },
            {
                "name": "ebitda",
                "label": "EBITDA",
                "unit": "亿",
                "description": "息税折旧摊销前利润，反映核心盈利能力",
                "range": {"min": 0, "max": 5000},
                "type": "range"
            },
            {
                "name": "ev_ebitda",
                "label": "EV/EBITDA",
                "unit": "",
                "description": "企业价值倍数，越低估值越便宜",
                "range": {"min": 0, "max": 50},
                "type": "range"
            }
        ],
        "tips": [
            "PE在0-30之间通常被认为是价值投资的合理区间",
            "ROE大于15%表示公司盈利能力较强",
            "营收和净利润增长率大于0表示公司处于成长阶段",
            "资产负债率低于50%通常被认为是财务健康的",
            "速动比率大于1表示短期偿债能力较强",
            "EV/EBITDA在10以下通常被认为是价值投资合理区间",
            "建议结合多个指标综合筛选，避免单一指标选股"
        ]
    }


# ---------------------------------------------------------------------------
# 因子评分 API
# ---------------------------------------------------------------------------

class FactorItem(BaseModel):
    """因子配置项"""
    key: str
    weight: float
    direction: str  # 'up' 表示越大越好, 'down' 表示越小越好


class FactorScoreRequest(BaseModel):
    """因子评分请求"""
    factors: list[FactorItem]
    stock_codes: list[str] | None = None


# 因子key到数据库字段的映射
FACTOR_FIELD_MAPPING: dict[str, str] = {
    "pe": "pe_ttm",
    "pb": "pb",
    "roe": "roe",
    "revenue_growth": "revenue_growth_yoy",
    "profit_growth": "profit_growth_yoy",
    "market_cap": "market_cap",
    "gross_margin": "gross_margin",
    "operating_margin": "operating_margin",
    "net_margin": "net_margin",
    "debt_ratio": "debt_ratio",
    "quick_ratio": "quick_ratio",
    "eps": "eps",
    "free_cash_flow": "free_cash_flow",
    "dividend_yield": "dividend_yield",
    "total_asset_turnover": "total_asset_turnover",
    "ev_ebitda": "ev_ebitda",
    "ebitda": "ebitda",
}


@router.post("/score")
def factor_score(body: FactorScoreRequest) -> dict[str, Any]:
    """
    因子评分接口。

    接收因子权重配置，从 trade_stock_master + trade_stock_financial 表
    查询实时数据，对股票进行综合评分并返回排名结果。

    Args:
        body: 包含因子配置和可选股票代码列表的请求体

    Returns:
        dict: 包含 items（评分结果列表）和 total（总数）
    """
    logger.info("因子评分请求", extra={
        "factor_count": len(body.factors),
        "stock_codes_provided": bool(body.stock_codes),
        "stock_codes_count": len(body.stock_codes) if body.stock_codes else 0,
    })

    if not body.factors:
        raise HTTPException(status_code=400, detail="至少需要提供一个因子")

    try:
        cfg = load_mysql_config()
        conn = _create_direct_connection(cfg)
    except Exception as e:
        logger.error("数据库连接失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="数据库连接失败")

    try:
        # 构建select字段列表
        select_fields = ["f.stock_code", "m.stock_name"]
        for factor in body.factors:
            db_field = FACTOR_FIELD_MAPPING.get(factor.key)
            if db_field:
                select_fields.append(f"f.{db_field}")

        # 构建where条件
        conditions: list[str] = []
        params: list[Any] = []

        if body.stock_codes:
            placeholders = ",".join(["%s"] * len(body.stock_codes))
            conditions.append(f"f.stock_code IN ({placeholders})")
            params.extend(body.stock_codes)

        # 查询最新报告期的财务数据
        # 使用子查询确保每只股票只取各自最新的报告期数据
        select_str = ", ".join(select_fields)
        sql = f"""
            SELECT {select_str}
            FROM ({_LATEST_REPORT_SUBQUERY}) f
            LEFT JOIN trade_stock_master m ON f.stock_code = m.stock_code
            WHERE 1=1
        """
        if conditions:
            sql += f" AND {' AND '.join(conditions)}"
        sql += " ORDER BY f.stock_code"
        rows = query_dict(conn, sql, tuple(params))

        if not rows:
            return {"items": [], "total": 0}

        # 计算评分
        # 先收集每个因子的值列表，用于标准化
        factor_values: dict[str, list[float]] = {}
        for factor in body.factors:
            db_field = FACTOR_FIELD_MAPPING.get(factor.key)
            if not db_field:
                continue
            vals = []
            for row in rows:
                v = row.get(db_field)
                if v is not None:
                    try:
                        vals.append(float(v))
                    except (ValueError, TypeError):
                        pass
            if vals:
                factor_values[factor.key] = vals

        if not factor_values:
            return {"items": [], "total": 0}

        # 计算每个因子的Min-Max标准化参数
        factor_stats: dict[str, dict] = {}
        for key, vals in factor_values.items():
            min_v = min(vals)
            max_v = max(vals)
            range_v = max_v - min_v if max_v > min_v else 1
            factor_stats[key] = {"min": min_v, "range": range_v}

        # 计算每只股票的得分
        scored_items: list[dict] = []
        for row in rows:
            stock_code = row.get("stock_code", "")
            stock_name = row.get("stock_name", "") or stock_code

            factor_scores: dict[str, float] = {}
            total_score = 0.0
            total_weight = 0.0

            for factor in body.factors:
                db_field = FACTOR_FIELD_MAPPING.get(factor.key)
                if not db_field or factor.key not in factor_stats:
                    continue

                raw_val = row.get(db_field)
                if raw_val is None:
                    continue

                try:
                    raw_val_f = float(raw_val)
                except (ValueError, TypeError):
                    continue

                stats = factor_stats[factor.key]
                # Min-Max归一化到[0, 1]
                normalized = (raw_val_f - stats["min"]) / stats["range"]
                # 根据方向调整
                if factor.direction == "down":
                    normalized = 1.0 - normalized
                # 限制在[0, 1]范围
                normalized = max(0.0, min(1.0, normalized))

                score = normalized * factor.weight
                factor_scores[factor.key] = round(normalized, 4)
                total_score += score
                total_weight += factor.weight

            if total_weight > 0:
                total_score = total_score / total_weight * 100  # 转为百分制
            else:
                continue

            scored_items.append({
                "code": stock_code,
                "name": stock_name,
                "factors": factor_scores,
                "total_score": round(total_score, 2),
                "rank": 0,  # 排序后填充
            })

        # 按总分降序排列
        scored_items.sort(key=lambda x: x["total_score"], reverse=True)

        # 填充排名
        for i, item in enumerate(scored_items):
            item["rank"] = i + 1

        logger.info("因子评分计算完成",
                    extra={"total": len(scored_items), "factors": len(body.factors)})

        return {
            "items": scored_items,
            "total": len(scored_items),
        }
    except Exception as e:
        logger.error("因子评分计算失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"因子评分计算失败: {str(e)}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 数据库迁移（创建索引）
# ---------------------------------------------------------------------------

def run_financial_indexes_migration():
    """
    执行财务数据表索引迁移。

    读取迁移SQL文件并逐条执行，为 trade_stock_financial 表添加索引，
    提升基本面选股查询性能。如果索引已存在则跳过（不报错）。
    """
    # 定位迁移SQL文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(current_dir, "..", "migrations", "011_add_financial_indexes.sql")

    if not os.path.exists(sql_file):
        logger.warning("迁移SQL文件不存在", extra={"path": sql_file})
        return

    try:
        cfg = load_mysql_config()
        conn = _create_direct_connection(cfg)
        try:
            with conn.cursor() as cur:
                with open(sql_file, "r", encoding="utf-8") as f:
                    sql_content = f.read()
                statements = [s.strip() for s in sql_content.split(";") if s.strip()]
                for stmt in statements:
                    try:
                        cur.execute(stmt)
                        logger.info("迁移SQL执行成功", extra={"sql": stmt[:80]})
                    except Exception as e:
                        logger.warning("迁移SQL执行警告（可能索引已存在）",
                                       extra={"sql": stmt[:80], "error": str(e)})
        finally:
            conn.close()
        logger.info("财务数据索引迁移完成")
    except Exception as e:
        logger.error("财务数据索引迁移失败", extra={"error": str(e)})


# ---------------------------------------------------------------------------
# 数据补充：批量更新 pe_ttm / pb / market_cap / 行业分类
# ---------------------------------------------------------------------------

@router.post("/enrich")
async def enrich_financial_data():
    """
    批量补充财务数据中缺失的 pe_ttm、pb、market_cap 以及行业分类。

    数据来源：akshare stock_zh_a_spot_em（行情数据）+ stock_board_industry_cons_em（行业成分股）。
    仅更新数据库中已有股票的缺失字段，不新增股票记录。
    """
    import akshare as ak

    updated_market = 0
    updated_industry = 0
    errors: list[str] = []

    # ---- 第一部分：补充 pe_ttm / pb / market_cap ----
    try:
        logger.info("开始补充行情数据（pe_ttm/pb/market_cap）...")
        cfg = load_mysql_config()
        conn = _create_direct_connection(cfg)
        try:
            with conn.cursor() as cur:
                # 获取最新报告期
                cur.execute("SELECT MAX(report_date) as max_date FROM trade_stock_financial")
                row = cur.fetchone()
                latest_date = row["max_date"] if row else None
                if not latest_date:
                    errors.append("trade_stock_financial 表无数据")
                else:
                    # 获取需要更新的股票代码（pe_ttm 或 market_cap 为空的）
                    cur.execute(
                        "SELECT DISTINCT stock_code FROM trade_stock_financial "
                        "WHERE report_date = %s AND (pe_ttm IS NULL OR market_cap IS NULL)",
                        (latest_date,)
                    )
                    codes_needing_update = [r["stock_code"] for r in cur.fetchall()]
                    logger.info(f"需要补充行情数据的股票: {len(codes_needing_update)} 只")

                    if codes_needing_update:
                        # 从 akshare 获取全市场行情快照
                        try:
                            df = ak.stock_zh_a_spot_em()
                            if df is not None and len(df) > 0:
                                # 构建代码→行情映射
                                market_map: dict[str, dict] = {}
                                for _, r in df.iterrows():
                                    code_num = str(r.get("代码") or "").strip()
                                    if not code_num:
                                        continue
                                    pe_val = safe_float(r.get("市盈率（动态）"))
                                    market_map[code_num] = {
                                        "pe": pe_val if pe_val and pe_val > 0 else None,
                                        "pb": safe_float(r.get("市净率")),
                                        "market_cap": safe_float(r.get("总市值")),
                                        "float_market_cap": safe_float(r.get("流通市值")),
                                    }

                                # 批量更新
                                for code in codes_needing_update:
                                    code_num = code.split(".")[0]
                                    md = market_map.get(code_num)
                                    if not md:
                                        continue
                                    pe_val = md["pe"]
                                    pb_val = md["pb"]
                                    mc_val = md["market_cap"]
                                    fmc_val = md["float_market_cap"]
                                    if pe_val is None and pb_val is None and mc_val is None:
                                        continue
                                    cur.execute(
                                        "UPDATE trade_stock_financial "
                                        "SET pe_ttm=COALESCE(pe_ttm, %s), "
                                        "    pb=COALESCE(pb, %s), "
                                        "    market_cap=COALESCE(market_cap, %s), "
                                        "    float_market_cap=COALESCE(float_market_cap, %s) "
                                        "WHERE stock_code=%s AND report_date=%s",
                                        (pe_val, pb_val, mc_val, fmc_val, code, latest_date)
                                    )
                                    updated_market += 1
                                conn.commit()
                                logger.info(f"行情数据补充完成: 更新 {updated_market} 只")
                        except Exception as e:
                            errors.append(f"akshare行情数据获取失败: {e}")
                            logger.error("akshare行情数据获取失败", extra={"error": str(e)})
        finally:
            conn.close()
    except Exception as e:
        errors.append(f"行情数据补充异常: {e}")
        logger.error("行情数据补充异常", extra={"error": str(e)})

    # ---- 第二部分：补充行业分类 ----
    try:
        logger.info("开始补充行业分类数据...")
        cfg = load_mysql_config()
        conn = _create_direct_connection(cfg)
        try:
            with conn.cursor() as cur:
                # 检查当前行业数据覆盖率
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM trade_stock_master "
                    "WHERE (asset_type='stock' OR asset_type IS NULL) "
                    "AND (sector_level1 IS NULL OR sector_level1='')"
                )
                missing_count = cur.fetchone()["cnt"]
                logger.info(f"缺少行业数据的股票: {missing_count} 只")

                if missing_count > 0:
                    # 使用 akshare 获取各行业成分股
                    industry_names = [
                        '农林牧渔', '基础化工', '钢铁', '有色金属', '电子', '家用电器',
                        '食品饮料', '纺织服饰', '轻工制造', '医药生物', '公用事业',
                        '交通运输', '房地产', '商贸零售', '社会服务', '银行',
                        '非银金融', '综合', '建筑材料', '建筑装饰', '电力设备',
                        '机械设备', '国防军工', '计算机', '传媒', '通信',
                        '煤炭', '石油石化', '环保', '美容护理', '汽车',
                    ]
                    for industry_name in industry_names:
                        try:
                            import time
                            time.sleep(0.5)
                            cons_df = ak.stock_board_industry_cons_em(symbol=industry_name)
                            if cons_df is None or len(cons_df) == 0:
                                continue
                            code_col = "代码" if "代码" in cons_df.columns else cons_df.columns[0]
                            for _, r in cons_df.iterrows():
                                code_num = str(r.get(code_col) or "").strip()
                                if not code_num:
                                    continue
                                exchange = "SH" if code_num.startswith("6") else "SZ"
                                stock_code = f"{code_num}.{exchange}"
                                cur.execute(
                                    "UPDATE trade_stock_master "
                                    "SET sector_level1=%s, updated_at=NOW() "
                                    "WHERE stock_code=%s "
                                    "AND (sector_level1 IS NULL OR sector_level1='')",
                                    (industry_name, stock_code)
                                )
                                if cur.rowcount > 0:
                                    updated_industry += 1
                            conn.commit()
                            logger.info(f"行业 [{industry_name}] 成分股更新完成")
                        except Exception as e:
                            logger.warning(f"行业 [{industry_name}] 获取失败",
                                           extra={"error": str(e)})
                            continue
                    logger.info(f"行业分类补充完成: 更新 {updated_industry} 只")
        finally:
            conn.close()
    except Exception as e:
        errors.append(f"行业分类补充异常: {e}")
        logger.error("行业分类补充异常", extra={"error": str(e)})

    return {
        "updated_market_data": updated_market,
        "updated_industry": updated_industry,
        "errors": errors[:10],
    }
