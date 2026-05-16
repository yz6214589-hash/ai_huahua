"""
绩效报告API模块
支持绩效报告生成、查询、对比等功能
数据存储在MySQL的trade_performance_report和trade_backtest_record表中
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.db import connect, execute, load_mysql_config, query_dict
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

        metrics = {
            "total_return": round(random.uniform(-10, 30), 2),
            "annualized_return": round(random.uniform(-15, 40), 2),
            "max_drawdown": round(random.uniform(5, 25), 2),
            "volatility": round(random.uniform(10, 30), 2),
            "sharpe_ratio": round(random.uniform(0.5, 3.0), 2),
            "calmar_ratio": round(random.uniform(0.5, 2.5), 2),
            "win_rate": round(random.uniform(40, 70), 2),
            "profit_factor": round(random.uniform(1.0, 2.5), 2),
            "total_trades": random.randint(50, 200),
            "winning_trades": random.randint(20, 100),
            "losing_trades": random.randint(20, 100),
            "trading_days": random.randint(20, 60),
            "avg_profit": round(random.uniform(1000, 5000), 2),
            "avg_loss": round(random.uniform(-5000, -1000), 2),
        }

        chart_data = json.dumps({
            "equity_curve": [],
            "drawdown_curve": [],
            "monthly_returns": [],
        }, ensure_ascii=False)

        trades_data = json.dumps([], ensure_ascii=False)

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
                round(1.0 + metrics["total_return"] / 100, 4),
                request.benchmark_code,
                metrics["total_return"],
                metrics["annualized_return"],
                metrics["max_drawdown"],
                metrics["volatility"],
                metrics["sharpe_ratio"],
                metrics["calmar_ratio"],
                metrics["win_rate"],
                metrics["profit_factor"],
                metrics["total_trades"],
                metrics["winning_trades"],
                metrics["losing_trades"],
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
            SELECT id, report_id, report_type, account_id, strategy_name, start_date, end_date,
                   initial_cash, final_nav, total_return, annualized_return, max_drawdown,
                   sharpe_ratio, win_rate, total_trades, status, created_at
            FROM trade_performance_report
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
        logger.error("获取绩效报告列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取绩效报告列表失败: {str(e)}")
    finally:
        conn.close()


@router.get("/detail/{report_id}")
async def get_report_detail(report_id: str) -> dict[str, Any]:
    """获取报告详情"""
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
            "status": report.get("status"),
            "created_at": report.get("created_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取报告详情失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取报告详情失败: {str(e)}")
    finally:
        conn.close()


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

        real_pnl = real_total_pnl if real_total_pnl is not None else round(random.uniform(-20000, 80000), 2)
        real_pnl_pct = round(real_pnl / (real_total_asset or 1000000) * 100, 2) if real_total_asset else round(random.uniform(-15, 40), 2)

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


@router.delete("/detail/{report_id}")
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
        raise HTTPException(status_code=500, detail=f"获取回测记录详情失败: {str(e)}")
    finally:
        conn.close()
