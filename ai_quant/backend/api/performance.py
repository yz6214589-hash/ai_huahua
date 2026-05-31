"""
绩效报告API模块
支持绩效报告生成、查询、对比等功能
集成 QuantStats 库，提供更丰富的绩效指标和中文 HTML 报告
数据存储在MySQL的trade_performance_report和trade_backtest_record表中
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.db import connect, execute, load_mysql_config, query_dict
from core.strategy.metrics_calculator import calc_quantstats_metrics
from core.strategy.report_engine import (
    generate_chinese_report,
    nav_to_returns,
    diagnose_market_regime,
    analyze_trading_costs,
    analyze_stock_pnl,
)
from infra.storage.logging_service import get_logger

logger = get_logger("performance")

router = APIRouter(prefix="/api/v1/performance", tags=["绩效报告"])


def _get_conn():
    cfg = load_mysql_config()
    return connect(cfg)


class ReportGenerateRequest(BaseModel):
    """报告生成请求"""
    account_id: Optional[int] = None
    report_type: str = Field(default="common")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy_name: Optional[str] = None
    strategy_params: Optional[str] = None
    backtest_id: Optional[str] = None
    initial_cash: Optional[float] = None
    benchmark_code: Optional[str] = None
    # 真实回测数据字段（Optional，用于替代随机假数据）
    metrics: Optional[dict] = None
    trades: Optional[list[dict]] = None
    nav_log: Optional[list[dict]] = None
    drawdown_log: Optional[list[dict]] = None
    monthly_returns: Optional[list[dict]] = None


@router.get("/types")
async def get_report_types() -> list[dict[str, str]]:
    """获取报告类型列表"""
    return [
        {"value": "common", "label": "普通版", "description": "基础绩效指标报告"},
        {"value": "plus", "label": "PLUS版", "description": "详细绩效指标报告，包含更多分析"},
    ]


@router.post("/generate")
async def generate_report(request: ReportGenerateRequest) -> dict[str, Any]:
    """生成绩效报告"""
    conn = _get_conn()
    try:
        report_id = f"rpt_{uuid4().hex[:8]}"
        start = request.start_date or (datetime.now().replace(day=1).strftime("%Y-%m-%d"))
        end = request.end_date or datetime.now().strftime("%Y-%m-%d")
        initial_cash = request.initial_cash or 1000000.0

        # 初始化指标字典（默认值 0，当有真实数据时覆盖）
        metrics: dict[str, Any] = {}
        if request.metrics:
            m = request.metrics
            # 前端字段 → 数据库列名 映射
            # 注意：前端 EnhancedMetrics 中的总收益率是 decimal（如 0.05 表示 5%），直接存储
            if "total_return" in m and m["total_return"] is not None:
                metrics["total_return"] = float(m["total_return"])
            if "annual_return" in m and m["annual_return"] is not None:
                metrics["annualized_return"] = float(m["annual_return"])
            if "max_drawdown" in m and m["max_drawdown"] is not None:
                metrics["max_drawdown"] = float(m["max_drawdown"])
            # volatility 在前端是小数（如 0.0991），乘以 100 转为百分比存储
            if "volatility" in m and m["volatility"] is not None:
                metrics["volatility"] = round(float(m["volatility"]) * 100, 2)
            if "sharpe" in m and m["sharpe"] is not None:
                metrics["sharpe_ratio"] = float(m["sharpe"])
            if "calmar" in m and m["calmar"] is not None:
                metrics["calmar_ratio"] = float(m["calmar"])
            if "win_rate" in m and m["win_rate"] is not None:
                metrics["win_rate"] = float(m["win_rate"])
            if "profit_factor" in m and m["profit_factor"] is not None:
                metrics["profit_factor"] = float(m["profit_factor"])
            # 兼容：前端 EnhancedMetrics 使用 num_trades，映射到 total_trades
            if "total_trades" in m and m["total_trades"] is not None:
                metrics["total_trades"] = int(m["total_trades"])
            elif "num_trades" in m and m["num_trades"] is not None:
                metrics["total_trades"] = int(m["num_trades"])
            if "avg_profit_loss" in m and m["avg_profit_loss"] is not None:
                metrics["avg_profit"] = round(float(m["avg_profit_loss"]), 2)
                metrics["avg_loss"] = 0
            # 可选：如果 metrics 中也包含了 winning_trades / losing_trades / trading_days，则覆盖
            if "winning_trades" in m and m["winning_trades"] is not None:
                metrics["winning_trades"] = int(m["winning_trades"])
            if "losing_trades" in m and m["losing_trades"] is not None:
                metrics["losing_trades"] = int(m["losing_trades"])
            if "trading_days" in m and m["trading_days"] is not None:
                metrics["trading_days"] = int(m["trading_days"])

        # 构建 chart_data 字典：优先使用请求中的真实数据，否则为空列表
        chart_data_dict = {
            "equity_curve": request.nav_log if request.nav_log else [],
            "drawdown_curve": request.drawdown_log if request.drawdown_log else [],
            "monthly_returns": request.monthly_returns if request.monthly_returns else [],
        }
        # 将 sortino / alpha / beta / information_ratio 存入 chart_data（不单独占数据库列）
        if request.metrics:
            for extra_field in ["sortino", "alpha", "beta", "information_ratio"]:
                val = request.metrics.get(extra_field)
                if val is not None:
                    chart_data_dict[extra_field] = float(val)

        # ---- QuantStats 增强指标 ----
        # 如果有 nav_log 数据，调用 calc_quantstats_metrics 计算更多指标并存入 chart_data
        if request.nav_log and len(request.nav_log) >= 2:
            try:
                benchmark_nav_log = request.metrics.get("_benchmark_nav_log") if request.metrics else None
                qs_metrics = calc_quantstats_metrics(request.nav_log, benchmark_nav_log)
                # 将 quantstats 指标存入 chart_data（使用 "qs_" 前缀避免与已有字段冲突）
                for key, value in qs_metrics.items():
                    if value is not None:
                        try:
                            chart_data_dict[f"qs_{key}"] = float(value)
                        except (ValueError, TypeError):
                            pass
            except Exception:
                # quantstats 计算失败不影响报告生成
                pass
        chart_data = json.dumps(chart_data_dict, ensure_ascii=False)

        # 构建 trades_data：优先使用请求中的真实交易记录
        trades_data = json.dumps(request.trades if request.trades else [], ensure_ascii=False)

        execute(
            conn,
            """INSERT INTO trade_performance_report
               (report_id, report_type, account_id, strategy_name, strategy_params, backtest_id,
                start_date, end_date, initial_cash, final_nav, benchmark_code,
                total_return, annualized_return, max_drawdown, volatility,
                sharpe_ratio, calmar_ratio, win_rate, profit_factor,
                total_trades, winning_trades, losing_trades,
                chart_data, trades_data, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                report_id,
                request.report_type,
                request.account_id,
                request.strategy_name,
                request.strategy_params,
                request.backtest_id,
                start,
                end,
                initial_cash,
                round(1.0 + metrics.get("total_return", 0), 4),
                request.benchmark_code,
                metrics.get("total_return", 0),
                metrics.get("annualized_return", 0),
                metrics.get("max_drawdown", 0),
                metrics.get("volatility", 0),
                metrics.get("sharpe_ratio", 0),
                metrics.get("calmar_ratio", 0),
                metrics.get("win_rate", 0),
                metrics.get("profit_factor", 0),
                metrics.get("total_trades", 0),
                metrics.get("winning_trades", 0),
                metrics.get("losing_trades", 0),
                chart_data,
                trades_data,
                "completed",
            )
        )

        return {
            "success": True,
            "message": "报告生成成功",
            "data": {
                "id": report_id,
                "type": request.report_type,
                "account_id": request.account_id,
                "start_date": start,
                "end_date": end,
                "metrics": metrics,
                "generated_at": datetime.now().isoformat(),
            }
        }
    except Exception as e:
        logger.error("生成绩效报告失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"生成绩效报告失败: {str(e)}")
    finally:
        conn.close()


@router.get("/list")
async def get_report_list(
    report_type: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """获取绩效报告列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if report_type:
            conditions.append("report_type = %s")
            params.append(report_type)
        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if start_date:
            conditions.append("start_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("end_date <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_performance_report WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT id, report_id, report_type, account_id, strategy_name, backtest_id, start_date, end_date,
                   initial_cash, final_nav, total_return, annualized_return, max_drawdown,
                   sharpe_ratio, win_rate, total_trades, status, created_at
            FROM trade_performance_report
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        from decimal import Decimal
        for row in rows:
            for dt_field in ["start_date", "end_date", "created_at", "updated_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()
            # Decimal 类型在 JSON 序列化中会变成字符串，统一转 float
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取绩效报告列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取绩效报告列表失败: {str(e)}")
    finally:
        conn.close()


@router.get("/detail/{report_id}")
async def get_report_detail(report_id: str) -> dict[str, Any]:
    """获取报告详情（普通版）"""
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_performance_report WHERE report_id = %s", (report_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="报告不存在")

        report = rows[0]

        for dt_field in ["start_date", "end_date", "created_at", "updated_at"]:
            if report.get(dt_field) and hasattr(report[dt_field], "isoformat"):
                report[dt_field] = report[dt_field].isoformat()

        if report.get("chart_data") and isinstance(report["chart_data"], str):
            try:
                report["chart_data"] = json.loads(report["chart_data"])
            except Exception:
                report["chart_data"] = {}
        if report.get("trades_data") and isinstance(report["trades_data"], str):
            try:
                report["trades_data"] = json.loads(report["trades_data"])
            except Exception:
                report["trades_data"] = []

        metrics = {
            "total_return": float(report.get("total_return") or 0),
            "annualized_return": float(report.get("annualized_return") or 0),
            "max_drawdown": float(report.get("max_drawdown") or 0),
            "volatility": float(report.get("volatility") or 0),
            "sharpe_ratio": float(report.get("sharpe_ratio") or 0),
            "calmar_ratio": float(report.get("calmar_ratio") or 0),
            "win_rate": float(report.get("win_rate") or 0),
            "profit_factor": float(report.get("profit_factor") or 0),
            "total_trades": int(report.get("total_trades") or 0),
            "winning_trades": int(report.get("winning_trades") or 0),
            "losing_trades": int(report.get("losing_trades") or 0),
        }

        chart_data = report.get("chart_data") or {}

        # 从 chart_data 中提取 QuantStats 增强指标
        qs_fields = [
            "sortino", "alpha", "beta", "information_ratio", "tracking_error",
            "omega", "var_95", "cvar_95", "gain_to_pain", "skew", "kurtosis",
            "best_day", "worst_day", "consecutive_wins", "consecutive_losses",
            "cagr", "avg_win", "avg_loss", "downside_risk", "up_capture",
            "down_capture", "payoff_ratio", "profit_factor", "win_rate",
            "calmar", "volatility", "r_squared", "tail_ratio",
            "common_sense_ratio", "expected_return", "expected_shortfall",
            "ulcer_index", "ulcer_performance_index", "risk_return_ratio",
        ]
        qs_metrics = {}
        for field in qs_fields:
            val = chart_data.get(field)
            if val is None:
                val = chart_data.get(f"qs_{field}")
            if val is not None:
                qs_metrics[field] = float(val)

        # 字段名映射：前端期望 avg_profit，QuantStats 返回 avg_win
        if "avg_win" in qs_metrics and "avg_profit" not in qs_metrics:
            qs_metrics["avg_profit"] = qs_metrics["avg_win"]

        # 补充前端需要但后端未单独计算的字段
        nav_log = chart_data.get("equity_curve", [])
        if nav_log and len(nav_log) >= 2:
            qs_metrics.setdefault("trading_days", len(nav_log))
        if "max_drawdown" in metrics:
            qs_metrics.setdefault("max_drawdown_duration", None)
        if "total_return" in metrics and "max_drawdown" in metrics:
            md = abs(float(metrics["max_drawdown"]))
            if md > 0:
                qs_metrics.setdefault("recovery_factor", float(metrics["total_return"]) / md)

        # 从 chart_data 中提取 QuantStats 增强指标（qs_ 前缀版本）
        qs_enhanced_metrics = {}
        for key, val in chart_data.items():
            if key.startswith("qs_") and val is not None:
                try:
                    qs_enhanced_metrics[key] = float(val)
                except (ValueError, TypeError):
                    pass

        # 从 chart_data 中提取基准净值曲线
        benchmark_curve = chart_data.get("benchmark_curve") or chart_data.get("benchmark_nav_log") or []

        # 从 chart_data 中提取成本分析数据（如果有）
        cost_analysis = chart_data.get("cost_analysis") or None

        # 从 chart_data 中提取 SVD 诊断数据（如果有）
        svd_diagnosis = chart_data.get("svd_diagnosis") or None

        return {
            "id": report_id,
            "report_type": report.get("report_type"),
            "account_id": report.get("account_id"),
            "strategy_name": report.get("strategy_name"),
            "start_date": report.get("start_date"),
            "end_date": report.get("end_date"),
            "initial_cash": float(report.get("initial_cash") or 0),
            "final_nav": float(report.get("final_nav") or 1),
            "metrics": metrics,
            "equity_curve": chart_data.get("equity_curve", []),
            "drawdown_curve": chart_data.get("drawdown_curve", []),
            "monthly_returns": chart_data.get("monthly_returns", []),
            "trades": report.get("trades_data", []),
            "benchmark_curve": benchmark_curve,
            "qs_metrics": qs_enhanced_metrics,
            "cost_analysis": cost_analysis,
            "svd_diagnosis": svd_diagnosis,
            "status": report.get("status"),
            "created_at": report.get("created_at"),
            "quantstats_metrics": qs_enhanced_metrics,
            **qs_metrics,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取报告详情失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取报告详情失败: {str(e)}")
    finally:
        conn.close()


@router.get("/detail-plus/{report_id}")
async def get_report_detail_plus(report_id: str) -> dict[str, Any]:
    """
    获取报告详情（Plus 版）

    在普通版基础上额外返回：
    - svd_diagnosis: SVD 市场状态诊断结果（如果报告有 stock_codes 数据则计算）
    - cost_analysis: 交易成本分析（从 trades 数据计算佣金/印花税/过户费）
    - stock_pnl: 个股盈亏分析（从 trades 数据按股票分组统计）
    """
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_performance_report WHERE report_id = %s", (report_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="报告不存在")

        report = rows[0]

        for dt_field in ["start_date", "end_date", "created_at", "updated_at"]:
            if report.get(dt_field) and hasattr(report[dt_field], "isoformat"):
                report[dt_field] = report[dt_field].isoformat()

        if report.get("chart_data") and isinstance(report["chart_data"], str):
            try:
                report["chart_data"] = json.loads(report["chart_data"])
            except Exception:
                report["chart_data"] = {}
        if report.get("trades_data") and isinstance(report["trades_data"], str):
            try:
                report["trades_data"] = json.loads(report["trades_data"])
            except Exception:
                report["trades_data"] = []

        metrics = {
            "total_return": float(report.get("total_return") or 0),
            "annualized_return": float(report.get("annualized_return") or 0),
            "max_drawdown": float(report.get("max_drawdown") or 0),
            "volatility": float(report.get("volatility") or 0),
            "sharpe_ratio": float(report.get("sharpe_ratio") or 0),
            "calmar_ratio": float(report.get("calmar_ratio") or 0),
            "win_rate": float(report.get("win_rate") or 0),
            "profit_factor": float(report.get("profit_factor") or 0),
            "total_trades": int(report.get("total_trades") or 0),
            "winning_trades": int(report.get("winning_trades") or 0),
            "losing_trades": int(report.get("losing_trades") or 0),
        }

        chart_data = report.get("chart_data") or {}
        trades_data = report.get("trades_data") or []

        # 从 chart_data 中提取 QuantStats 增强指标
        qs_fields = [
            "sortino", "alpha", "beta", "information_ratio", "tracking_error",
            "omega", "var_95", "cvar_95", "gain_to_pain", "skew", "kurtosis",
            "best_day", "worst_day", "consecutive_wins", "consecutive_losses",
            "cagr", "avg_win", "avg_loss", "downside_risk", "up_capture",
            "down_capture", "payoff_ratio", "profit_factor", "win_rate",
            "calmar", "volatility", "r_squared", "tail_ratio",
            "common_sense_ratio", "expected_return", "expected_shortfall",
            "ulcer_index", "ulcer_performance_index", "risk_return_ratio",
        ]
        qs_metrics = {}
        for field in qs_fields:
            val = chart_data.get(field)
            if val is None:
                val = chart_data.get(f"qs_{field}")
            if val is not None:
                qs_metrics[field] = float(val)

        # 字段名映射：前端期望 avg_profit，QuantStats 返回 avg_win
        if "avg_win" in qs_metrics and "avg_profit" not in qs_metrics:
            qs_metrics["avg_profit"] = qs_metrics["avg_win"]

        # 补充前端需要但后端未单独计算的字段
        nav_log = chart_data.get("equity_curve", [])
        if nav_log and len(nav_log) >= 2:
            qs_metrics.setdefault("trading_days", len(nav_log))
        if "max_drawdown" in metrics:
            qs_metrics.setdefault("max_drawdown_duration", None)
        if "total_return" in metrics and "max_drawdown" in metrics:
            md = abs(float(metrics["max_drawdown"]))
            if md > 0:
                qs_metrics.setdefault("recovery_factor", float(metrics["total_return"]) / md)

        # 从 chart_data 中提取 QuantStats 增强指标（qs_ 前缀版本）
        qs_enhanced_metrics = {}
        for key, val in chart_data.items():
            if key.startswith("qs_") and val is not None:
                try:
                    qs_enhanced_metrics[key] = float(val)
                except (ValueError, TypeError):
                    pass

        # 从 chart_data 中提取基准净值曲线
        benchmark_curve = chart_data.get("benchmark_curve") or chart_data.get("benchmark_nav_log") or []

        # ---- Plus 版独有功能 ----

        # 1. SVD 市场状态诊断：从 chart_data 或 strategy_params 中获取 stock_codes
        svd_diagnosis = chart_data.get("svd_diagnosis") or None
        stock_codes_raw = chart_data.get("stock_codes") or None
        if not stock_codes_raw:
            # 尝试从 strategy_params 中获取
            strategy_params_str = report.get("strategy_params") or ""
            if strategy_params_str:
                try:
                    sp = json.loads(strategy_params_str) if isinstance(strategy_params_str, str) else strategy_params_str
                    stock_codes_raw = sp.get("stock_codes") if isinstance(sp, dict) else None
                except Exception:
                    pass

        # 如果有 stock_codes 但没有缓存的 svd_diagnosis，则实时计算
        if stock_codes_raw and not svd_diagnosis:
            try:
                stock_codes_list = stock_codes_raw if isinstance(stock_codes_raw, list) else []
                start_date = report.get("start_date", "")
                end_date = report.get("end_date", "")
                if stock_codes_list and start_date and end_date:
                    svd_diagnosis = diagnose_market_regime(
                        stock_codes=stock_codes_list,
                        start_date=start_date,
                        end_date=end_date,
                    )
            except Exception as e:
                logger.warning("Plus版 SVD 诊断计算失败", extra={"error": str(e)})
                svd_diagnosis = {"error": str(e)}

        # 2. 交易成本分析：从 trades 数据计算
        cost_analysis = chart_data.get("cost_analysis") or None
        if not cost_analysis and trades_data:
            try:
                cost_analysis = analyze_trading_costs(trades_data)
            except Exception as e:
                logger.warning("Plus版交易成本分析失败", extra={"error": str(e)})
                cost_analysis = {"error": str(e)}

        # 3. 个股盈亏分析：从 trades 数据按股票分组统计
        stock_pnl = []
        if trades_data:
            try:
                stock_pnl = analyze_stock_pnl(trades_data)
            except Exception as e:
                logger.warning("Plus版个股盈亏分析失败", extra={"error": str(e)})

        return {
            "id": report_id,
            "report_type": report.get("report_type"),
            "account_id": report.get("account_id"),
            "strategy_name": report.get("strategy_name"),
            "start_date": report.get("start_date"),
            "end_date": report.get("end_date"),
            "initial_cash": float(report.get("initial_cash") or 0),
            "final_nav": float(report.get("final_nav") or 1),
            "benchmark_code": report.get("benchmark_code"),
            "metrics": metrics,
            "equity_curve": chart_data.get("equity_curve", []),
            "drawdown_curve": chart_data.get("drawdown_curve", []),
            "monthly_returns": chart_data.get("monthly_returns", []),
            "trades": trades_data,
            "benchmark_curve": benchmark_curve,
            "qs_metrics": qs_enhanced_metrics,
            "cost_analysis": cost_analysis,
            "svd_diagnosis": svd_diagnosis,
            "stock_pnl": stock_pnl,
            "status": report.get("status"),
            "created_at": report.get("created_at"),
            "quantstats_metrics": qs_enhanced_metrics,
            **qs_metrics,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取Plus版报告详情失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取Plus版报告详情失败: {str(e)}")
    finally:
        conn.close()


class SVDDiagnosisRequest(BaseModel):
    """SVD 市场状态诊断请求"""
    stock_codes: list[str]
    start_date: str
    end_date: str
    window: int = Field(default=60, ge=20, le=252)
    step: int = Field(default=10, ge=1, le=60)


@router.post("/svd-diagnosis")
async def svd_diagnosis(request: SVDDiagnosisRequest) -> dict[str, Any]:
    """
    SVD 市场状态诊断接口

    接收股票代码列表和日期范围，执行 SVD 市场状态诊断。
    返回当前市场状态（齐涨齐跌/板块分化/个股行情）、
    第一主成分方差占比、投资建议和滚动诊断数据。
    """
    if not request.stock_codes:
        raise HTTPException(status_code=400, detail="stock_codes 不能为空")

    if len(request.stock_codes) < 3:
        raise HTTPException(status_code=400, detail="SVD 诊断至少需要 3 只股票的数据")

    try:
        result = diagnose_market_regime(
            stock_codes=request.stock_codes,
            start_date=request.start_date,
            end_date=request.end_date,
            window=request.window,
            step=request.step,
        )
        return result
    except Exception as e:
        logger.error("SVD 市场状态诊断失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"SVD 市场状态诊断失败: {str(e)}")


@router.get("/comparison")
async def compare_performance(
    sim_account_id: int = Query(...),
    real_total_asset: Optional[float] = Query(None),
    real_total_pnl: Optional[float] = Query(None),
) -> dict[str, Any]:
    """对比实盘和模拟盘收益"""
    conn = _get_conn()
    try:
        sim_accounts = query_dict(conn, "SELECT * FROM trade_sim_account WHERE id = %s", (sim_account_id,))
        if not sim_accounts:
            raise HTTPException(status_code=404, detail="模拟账户不存在")

        sim_account = sim_accounts[0]
        sim_pnl = float(sim_account.get("total_pnl") or 0)
        sim_pnl_pct = float(sim_account.get("total_pnl_pct") or 0)

        real_pnl = real_total_pnl if real_total_pnl is not None else 0
        real_pnl_pct = round(real_pnl / (real_total_asset or 1000000) * 100, 2) if real_total_asset else 0

        return {
            "sim": {
                "total_pnl": sim_pnl,
                "total_pnl_pct": sim_pnl_pct,
                "total_asset": float(sim_account.get("total_asset") or 0),
                "market_value": float(sim_account.get("market_value") or 0),
            },
            "real": {
                "total_pnl": real_pnl,
                "total_pnl_pct": real_pnl_pct,
            },
            "comparison": {
                "diff_amount": round(sim_pnl - real_pnl, 2),
                "diff_pct": round(sim_pnl_pct - real_pnl_pct, 2),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("对比收益失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"对比收益失败: {str(e)}")
    finally:
        conn.close()


@router.delete("/{report_id}")
async def delete_report(report_id: str) -> dict[str, Any]:
    """删除绩效报告"""
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_performance_report WHERE report_id = %s", (report_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="报告不存在")

        execute(conn, "DELETE FROM trade_performance_report WHERE report_id = %s", (report_id,))
        return {"success": True, "message": "报告删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除绩效报告失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"删除绩效报告失败: {str(e)}")
    finally:
        conn.close()


@router.get("/quantstats-html/{report_id}")
async def get_quantstats_html(report_id: str) -> dict[str, Any]:
    """
    根据 report_id 从数据库获取 nav_log 数据，用 quantstats 生成中文 HTML 报告，
    保存到 backend/static/reports/ 目录，返回 HTML 文件路径
    """
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_performance_report WHERE report_id = %s", (report_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="报告不存在")

        report = rows[0]

        # 解析 chart_data 获取 nav_log
        chart_data = {}
        if report.get("chart_data") and isinstance(report["chart_data"], str):
            try:
                chart_data = json.loads(report["chart_data"])
            except Exception:
                chart_data = {}

        equity_curve = chart_data.get("equity_curve", [])
        if not equity_curve:
            raise HTTPException(status_code=400, detail="该报告无净值曲线数据，无法生成 QuantStats 报告")

        # 从净值曲线构建日收益率序列
        sorted_log = sorted(equity_curve, key=lambda x: x.get("date", ""))
        navs = [float(r.get("nav", 0)) for r in sorted_log]
        dates = [r.get("date", "") for r in sorted_log]

        if len(navs) < 2:
            raise HTTPException(status_code=400, detail="净值数据不足，至少需要2个数据点")

        # 构建收益率序列
        nav_series = pd.Series(navs, index=pd.to_datetime(dates))
        returns = nav_series.pct_change().dropna()

        # 构建基准收益率序列（如果 chart_data 中有 qs_ 前缀的基准指标，说明有基准数据）
        benchmark = None
        # 尝试从 chart_data 中获取基准净值数据
        benchmark_curve = chart_data.get("benchmark_curve", [])
        if benchmark_curve and len(benchmark_curve) >= 2:
            sorted_bench = sorted(benchmark_curve, key=lambda x: x.get("date", ""))
            bench_navs = [float(r.get("nav", 0)) for r in sorted_bench]
            bench_dates = [r.get("date", "") for r in sorted_bench]
            bench_series = pd.Series(bench_navs, index=pd.to_datetime(bench_dates))
            benchmark = bench_series.pct_change().dropna()

        # 生成中文 HTML 报告
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reports_dir = os.path.join(project_root, "static", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        html_filename = f"quantstats_{report_id}.html"
        html_path = os.path.join(reports_dir, html_filename)

        strategy_name = report.get("strategy_name") or "策略"
        generate_chinese_report(
            returns,
            benchmark=benchmark,
            title=f"{strategy_name} - 绩效分析报告",
            output_path=html_path,
        )

        # 返回可访问的 URL 路径
        url = f"/static/reports/{html_filename}"
        return {"html_path": html_path, "url": url, "report_id": report_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("生成 QuantStats 中文 HTML 报告失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"生成 QuantStats 报告失败: {str(e)}")
    finally:
        conn.close()


class QuantStatsReportRequest(BaseModel):
    """QuantStats 报告生成请求"""
    nav_log: list[dict]
    benchmark_nav_log: Optional[list[dict]] = None
    title: str = Field(default="策略绩效报告")


@router.post("/generate-quantstats-report")
async def generate_quantstats_report(request: QuantStatsReportRequest) -> dict[str, Any]:
    """
    接收 nav_log 和 benchmark_nav_log，调用 quantstats 生成完整中文 HTML 报告，
    返回报告路径
    """
    try:
        if not request.nav_log or len(request.nav_log) < 2:
            raise HTTPException(status_code=400, detail="nav_log 数据不足，至少需要2个数据点")

        # 从净值日志构建日收益率序列
        sorted_log = sorted(request.nav_log, key=lambda x: x.get("date", ""))
        navs = [float(r.get("nav", 0)) for r in sorted_log]
        dates = [r.get("date", "") for r in sorted_log]
        nav_series = pd.Series(navs, index=pd.to_datetime(dates))
        returns = nav_series.pct_change().dropna()

        # 构建基准收益率序列
        benchmark = None
        if request.benchmark_nav_log and len(request.benchmark_nav_log) >= 2:
            sorted_bench = sorted(request.benchmark_nav_log, key=lambda x: x.get("date", ""))
            bench_navs = [float(r.get("nav", 0)) for r in sorted_bench]
            bench_dates = [r.get("date", "") for r in sorted_bench]
            bench_series = pd.Series(bench_navs, index=pd.to_datetime(bench_dates))
            benchmark = bench_series.pct_change().dropna()

        # 生成中文 HTML 报告
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reports_dir = os.path.join(project_root, "static", "reports")
        os.makedirs(reports_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_filename = f"quantstats_{ts}.html"
        html_path = os.path.join(reports_dir, html_filename)

        generate_chinese_report(
            returns,
            benchmark=benchmark,
            title=request.title,
            output_path=html_path,
        )

        url = f"/static/reports/{html_filename}"
        return {
            "success": True,
            "message": "QuantStats 中文报告生成成功",
            "html_path": html_path,
            "url": url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("生成 QuantStats 报告失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"生成 QuantStats 报告失败: {str(e)}")


# ============================================
# 回测记录管理
# ============================================

@router.get("/backtests")
async def get_backtest_list(
    strategy_name: Optional[str] = Query(None),
    stock_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """获取回测记录列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if strategy_name:
            conditions.append("strategy_name LIKE %s")
            params.append(f"%{strategy_name}%")
        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_backtest_record WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT id, backtest_id, strategy_name, strategy_type, stock_code,
                   start_date, end_date, initial_cash, final_capital,
                   total_return, annualized_return, max_drawdown, sharpe_ratio,
                   total_trades, winning_trades, losing_trades, status, created_at
            FROM trade_backtest_record
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        for row in rows:
            for dt_field in ["start_date", "end_date", "created_at", "updated_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取回测记录列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取回测记录列表失败: {str(e)}")
    finally:
        conn.close()


@router.get("/backtests/{backtest_id}")
async def get_backtest_detail(backtest_id: str) -> dict[str, Any]:
    """获取回测记录详情"""
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_backtest_record WHERE backtest_id = %s", (backtest_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="回测记录不存在")

        record = rows[0]

        for dt_field in ["start_date", "end_date", "created_at", "updated_at"]:
            if record.get(dt_field) and hasattr(record[dt_field], "isoformat"):
                record[dt_field] = record[dt_field].isoformat()

        if record.get("nav_data") and isinstance(record["nav_data"], str):
            try:
                record["nav_data"] = json.loads(record["nav_data"])
            except Exception:
                record["nav_data"] = []
        if record.get("trades_data") and isinstance(record["trades_data"], str):
            try:
                record["trades_data"] = json.loads(record["trades_data"])
            except Exception:
                record["trades_data"] = []
        if record.get("strategy_params") and isinstance(record["strategy_params"], str):
            try:
                record["strategy_params"] = json.loads(record["strategy_params"])
            except Exception:
                pass

        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取回测记录详情失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取回测记录详情失败：{str(e)}")
    finally:
        conn.close()


# ============================================
# 重新生成报告 API
# ============================================

class RegenerateReportRequest(BaseModel):
    """重新生成报告请求体"""
    report_type: str | None = Field(default=None, description="报告类型，'plus' 表示增强版")


@router.post("/regenerate/{report_id}")
async def regenerate_report(report_id: str, body: RegenerateReportRequest = None) -> dict[str, Any]:
    """
    重新生成绩效报告
    
    功能：
    1. 从数据库读取现有报告数据
    2. 解析 chart_data 和 trades_data
    3. 重新计算 QuantStats 指标（如果有 nav_log）
    4. 如果 body 中 report_type 为"plus"，还重新计算 SVD 诊断和交易成本分析
    5. 更新数据库中的记录
    6. 返回成功信息
    """
    conn = _get_conn()
    try:
        # 读取现有报告
        rows = query_dict(conn, "SELECT * FROM trade_performance_report WHERE report_id = %s", (report_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="报告不存在")
        
        report = rows[0]
        
        # 解析 chart_data
        chart_data_raw = {}
        if report.get("chart_data") and isinstance(report["chart_data"], str):
            try:
                chart_data_raw = json.loads(report["chart_data"])
            except Exception:
                chart_data_raw = {}
        
        # 从 chart_data 中获取 equity_curve 作为 nav_log
        nav_log = chart_data_raw.get("equity_curve", [])
        
        # 重新计算 QuantStats 指标
        chart_data_dict = dict(chart_data_raw)  # 复制原有数据
        
        if nav_log and len(nav_log) >= 2:
            try:
                # 提取基准净值曲线（如果存在）
                benchmark_nav_log = chart_data_raw.get("benchmark_curve") or chart_data_raw.get("benchmark_nav_log") or None
                
                qs_metrics = calc_quantstats_metrics(nav_log, benchmark_nav_log)
                
                # 将 quantstats 指标存入 chart_data（使用"qs_"前缀避免冲突）
                for key, value in qs_metrics.items():
                    if value is not None:
                        try:
                            chart_data_dict[f"qs_{key}"] = float(value)
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                logger.warning("重新计算 QuantStats 指标失败", extra={"error": str(e)})
        
        # 如果是 Plus 版，重新计算 SVD 诊断和交易成本分析
        report_type = report.get("report_type", "common")
        if body and body.report_type == "plus":
            report_type = "plus"
            
            # SVD 市场状态诊断
            stock_codes_raw = chart_data_raw.get("stock_codes") or None
            if not stock_codes_raw:
                strategy_params_str = report.get("strategy_params") or ""
                if strategy_params_str:
                    try:
                        sp = json.loads(strategy_params_str) if isinstance(strategy_params_str, str) else strategy_params_str
                        stock_codes_raw = sp.get("stock_codes") if isinstance(sp, dict) else None
                    except Exception:
                        pass
            
            if stock_codes_raw:
                try:
                    stock_codes_list = stock_codes_raw if isinstance(stock_codes_raw, list) else []
                    start_date = report.get("start_date", "")
                    end_date = report.get("end_date", "")
                    if stock_codes_list and start_date and end_date:
                        svd_result = diagnose_market_regime(
                            stock_codes=stock_codes_list,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        chart_data_dict["svd_diagnosis"] = svd_result
                except Exception as e:
                    logger.warning("重新计算 SVD 诊断失败", extra={"error": str(e)})
            
            # 交易成本分析
            trades_data_raw = report.get("trades_data") or []
            if isinstance(trades_data_raw, str):
                try:
                    trades_data_raw = json.loads(trades_data_raw)
                except Exception:
                    trades_data_raw = []
            
            if trades_data_raw:
                try:
                    cost_result = analyze_trading_costs(trades_data_raw)
                    chart_data_dict["cost_analysis"] = cost_result
                except Exception as e:
                    logger.warning("重新计算交易成本分析失败", extra={"error": str(e)})
        
        # 更新数据库中的记录
        chart_data_json = json.dumps(chart_data_dict, ensure_ascii=False)
        
        execute(
            conn,
            """UPDATE trade_performance_report
               SET chart_data = %s, report_type = %s, updated_at = NOW()
               WHERE report_id = %s""",
            (chart_data_json, report_type, report_id)
        )
        
        return {
            "status": "ok",
            "report_id": report_id,
            "message": "报告重新生成成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("重新生成报告失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"重新生成报告失败：{str(e)}")
    finally:
        conn.close()


# ============================================
# AI 分析 API
# ============================================


@router.post("/ai-analysis/{report_id}")
async def ai_analysis_report(report_id: str) -> dict[str, Any]:
    """
    AI 分析报告生成
    
    功能：
    1. 从数据库读取报告数据
    2. 收集策略名称、指标、交易记录等关键信息
    3. 调用 LLM 生成分析报告（如果 LLM 不可用则使用模板）
    4. 返回分析结果
    """
    conn = _get_conn()
    try:
        # 读取现有报告
        rows = query_dict(conn, "SELECT * FROM trade_performance_report WHERE report_id = %s", (report_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="报告不存在")
        
        report = rows[0]
        
        # 提取关键信息
        strategy_name = report.get("strategy_name") or "未知策略"
        start_date = report.get("start_date") or ""
        end_date = report.get("end_date") or ""
        initial_cash = float(report.get("initial_cash") or 0)
        
        # 核心绩效指标
        total_return = float(report.get("total_return") or 0)
        annual_return = float(report.get("annualized_return") or 0)
        max_drawdown = float(report.get("max_drawdown") or 0)
        volatility = float(report.get("volatility") or 0)
        sharpe_ratio = float(report.get("sharpe_ratio") or 0)
        calmar_ratio = float(report.get("calmar_ratio") or 0)
        win_rate = float(report.get("win_rate") or 0)
        profit_factor = float(report.get("profit_factor") or 0)
        total_trades = int(report.get("total_trades") or 0)
        
        # 解析 chart_data 获取增强指标
        chart_data_raw = {}
        if report.get("chart_data") and isinstance(report["chart_data"], str):
            try:
                chart_data_raw = json.loads(report["chart_data"])
            except Exception:
                chart_data_raw = {}
        
        # 解析 trades_data
        trades_data_raw = report.get("trades_data") or []
        if isinstance(trades_data_raw, str):
            try:
                trades_data_raw = json.loads(trades_data_raw)
            except Exception:
                trades_data_raw = []
        
        # 计算交易统计
        avg_profit_loss = 0.0
        if trades_data_raw and len(trades_data_raw) > 0:
            total_pnl = sum(float(t.get("pnl", 0)) for t in trades_data_raw)
            avg_profit_loss = total_pnl / len(trades_data_raw) if trades_data_raw else 0
        
        # 尝试调用 LLM 生成分析
        try:
            # 构建分析 prompt
            prompt = f"""请对以下量化策略绩效进行分析：

## 基本信息
- 策略名称：{strategy_name}
- 回测区间：{start_date} ~ {end_date}
- 初始资金：{initial_cash:,.2f}

## 核心绩效指标
- 总收益率：{total_return:.2f}%
- 年化收益率：{annual_return:.2f}%
- 最大回撤：{max_drawdown:.2f}%
- 波动率：{volatility:.2f}%
- 夏普比率：{sharpe_ratio:.2f}
- 卡尔玛比率：{calmar_ratio:.2f}
- 胜率：{win_rate:.1f}%
- 盈亏比：{profit_factor:.2f}

## 交易统计
- 总交易次数：{total_trades}
- 平均盈亏：{avg_profit_loss:.2f}

## 市场环境
"""
            # 如果是 Plus 版，添加 SVD 诊断信息
            svd_diagnosis = chart_data_raw.get("svd_diagnosis")
            if svd_diagnosis:
                prompt += f"- SVD 市场诊断：{json.dumps(svd_diagnosis, ensure_ascii=False)}\n"
            else:
                prompt += "- 无市场环境数据\n"
            
            prompt += "\n请根据以上数据生成一份专业的策略绩效分析报告，包括收益分析、风险评估、交易分析和综合评价。"
            
            # 由于 run_report_agent 是为个股研报设计的，我们使用模板方式作为 fallback
            # 这里直接调用简单的 LLM 方式
            from langchain_community.chat_models.tongyi import ChatTongyi
            import os
            
            llm = ChatTongyi(model=os.getenv("CHARLES_MODEL", "qwen-plus"))
            messages = [
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长分析策略绩效数据并提供专业建议。"},
                {"role": "user", "content": prompt}
            ]
            
            try:
                res = llm.invoke(messages)
                analysis_text = str(getattr(res, "content", "") or "")
                
                if analysis_text and len(analysis_text) > 50:
                    return {
                        "status": "ok",
                        "report_id": report_id,
                        "analysis": analysis_text,
                        "mode": "llm"
                    }
            except Exception as llm_error:
                logger.warning("LLM 调用失败，使用模板生成分析", extra={"error": str(llm_error)})
        
        except ImportError:
            logger.warning("LLM 模块不可用，使用模板生成分析")
        except Exception as e:
            logger.warning("AI 分析失败，使用模板生成", extra={"error": str(e)})
        
        # Fallback: 使用模板生成分析
        analysis = f"""## 策略绩效分析报告

### 基本信息
- 策略名称：{strategy_name}
- 回测区间：{start_date} ~ {end_date}
- 初始资金：{initial_cash:,.2f}

### 收益分析
- 总收益率：{total_return:.2f}%
- 年化收益率：{annual_return:.2f}%
- 最大回撤：{max_drawdown:.2f}%

### 风险评估
- 夏普比率：{sharpe_ratio:.2f}
- 波动率：{volatility:.2f}%
- 卡尔玛比率：{calmar_ratio:.2f}

### 交易分析
- 总交易次数：{total_trades}
- 胜率：{win_rate:.1f}%
- 盈亏比：{profit_factor:.2f}
- 平均盈亏：{avg_profit_loss:.2f}

### 综合评价
"""
        # 根据指标生成评价
        if sharpe_ratio > 1.5:
            evaluation = "策略风险调整后收益优秀，夏普比率高于 1.5，显示出较强的风险控制能力。"
        elif sharpe_ratio > 1.0:
            evaluation = "策略风险调整后收益良好，夏普比率超过 1.0，表现稳健。"
        elif sharpe_ratio > 0.5:
            evaluation = "策略风险调整后收益一般，建议进一步优化风险控制。"
        else:
            evaluation = "策略风险调整后收益偏低，需要重新评估策略逻辑和风险控制。"
        
        if max_drawdown < 10:
            evaluation += " 最大回撤控制在 10% 以内，风险水平较低。"
        elif max_drawdown < 20:
            evaluation += " 最大回撤在 10%-20% 之间，风险水平适中。"
        else:
            evaluation += " 最大回撤超过 20%，风险水平较高，建议加强风控。"
        
        if win_rate > 60:
            evaluation += " 胜率较高，策略具有较好的交易质量。"
        elif win_rate > 50:
            evaluation += " 胜率适中，策略表现正常。"
        else:
            evaluation += " 胜率偏低，建议优化入场和出场信号。"
        
        analysis += evaluation
        
        return {
            "status": "ok",
            "report_id": report_id,
            "analysis": analysis,
            "mode": "template"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI 分析失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"AI 分析失败：{str(e)}")
    finally:
        conn.close()
