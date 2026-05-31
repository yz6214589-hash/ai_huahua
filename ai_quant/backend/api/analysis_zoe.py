# -*- coding: utf-8 -*-
"""
分析API路由模块
提供策略管理、回测执行、Walk-Forward验证、参数搜索、回测历史等API
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, datetime as dt, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.db import connect, load_mysql_config, query_dict
from core.analysis import get_sample_codes, get_signals, get_status as get_analysis_status
from core.strategy.strategy_registry import get_strategy_registry
from core.strategy.multi_agent_backtest import MultiAgentBacktestEngine
from infra.storage.logging_service import get_logger
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
logger = get_logger("analysis")


@router.get("/status")
def status() -> dict[str, Any]:
    return get_analysis_status()


@router.get("/stocks/sample")
def sample_stocks(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return get_sample_codes(limit)


@router.get("/signals")
def signals(stock_code: str = Query(...), start: str = Query(...), end: str = Query(...)) -> dict[str, Any]:
    return get_signals(stock_code=stock_code, start=start, end=end)


# ============== 策略元数据注册表 ==============

_REGISTRY = get_strategy_registry()

STRATEGIES: list[dict[str, Any]] = []
for _sid, _meta in _REGISTRY.items():
    STRATEGIES.append({
        "strategy_id": _meta.strategy_id,
        "name": _meta.name,
        "description": _meta.description,
        "pros": [],
        "cons": [],
        "params_schema": _meta.params_schema,
        "default_params": _meta.default_params,
        "requires_weekly": _meta.requires_weekly,
        "requires_chan": _meta.requires_chan,
        "requires_predictions": _meta.requires_predictions,
        "group": _meta.group,
    })


# ============== 实例存储路径 ==============

def _instances_path() -> Path:
    base = Path(__file__).parent.parent.parent.parent
    p = base / ".ai_quant" / "strategy_instances.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_instances() -> list[dict[str, Any]]:
    p = _instances_path()
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _save_instances(instances: list[dict[str, Any]]) -> None:
    p = _instances_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(instances, f, ensure_ascii=False, indent=2)


# ============== 数据加载 ==============

def _load_daily(stock_code: str, start: str, end: str) -> pd.DataFrame:
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return pd.DataFrame()
    try:
        rows = query_dict(
            conn,
            """
            SELECT trade_date, open_price, high_price, low_price, close_price, volume, amount, stock_name
            FROM trade_stock_daily
            WHERE stock_code = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """,
            (stock_code, start, end),
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ["open_price", "high_price", "low_price", "close_price", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        rename_map = {
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
        df = df.rename(columns=rename_map)
        return df
    finally:
        conn.close()


# ============== 请求模型 ==============

class InstanceCreateReq(BaseModel):
    strategy_id: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class BacktestReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    # 新增：佣金与滑点参数
    commission_buy: float = Field(default=0.0003, description="买入佣金率")
    commission_sell: float = Field(default=0.0013, description="卖出佣金率（含印花税）")
    slippage_pct: float = Field(default=0.0, description="滑点百分比")
    slippage_fixed: float = Field(default=0.0, description="固定滑点")
    min_commission: float = Field(default=5.0, description="最低手续费")
    # 新增：仓位比例
    position_pct: float = Field(default=0.95, ge=0.01, le=1.0, description="仓位比例")
    # 新增：印花税和过户费
    stamp_duty: float = Field(default=0.001, ge=0.0, le=0.01, description="印花税费率，卖出时收取，默认千分之一")
    transfer_fee_buy: float = Field(default=0.00001, ge=0.0, le=0.001, description="买入过户费率，默认十万分之一")
    transfer_fee_sell: float = Field(default=0.00001, ge=0.0, le=0.001, description="卖出过户费率，默认十万分之一")
    # 新增：基准代码
    benchmark_code: str | None = Field(default=None, description="基准指数代码，如 000300.SH")
    # 新增：区间模式
    interval_mode: str | None = Field(default=None, description="区间模式：train_val_test")
    train_ratio: float = Field(default=0.6, description="训练集比例")
    val_ratio: float = Field(default=0.2, description="验证集比例")
    test_ratio: float = Field(default=0.2, description="测试集比例")
    custom_intervals: list[dict[str, str]] | None = Field(default=None, description="自定义区间列表")


class BatchBacktestReq(BaseModel):
    selection_type: str = Field(default="list", description="选择类型：list（直接列表）或 group（分组）")
    stock_codes: list[str] = Field(default_factory=list, description="股票代码列表")
    group_id: int | None = Field(default=None, description="分组ID（selection_type为group时必填）")
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    max_workers: int = Field(default=4, ge=1, le=16, description="最大并发数")
    # 新增：佣金与滑点参数（与单股回测保持一致）
    commission_buy: float = Field(default=0.0003, description="买入佣金率")
    commission_sell: float = Field(default=0.0013, description="卖出佣金率（含印花税）")
    slippage_pct: float = Field(default=0.0, description="滑点百分比")
    slippage_fixed: float = Field(default=0.0, description="固定滑点")
    min_commission: float = Field(default=5.0, description="最低手续费")
    # 新增：仓位比例
    position_pct: float = Field(default=0.95, ge=0.01, le=1.0, description="仓位比例")
    # 新增：印花税和过户费
    stamp_duty: float = Field(default=0.001, ge=0.0, le=0.01, description="印花税费率，卖出时收取，默认千分之一")
    transfer_fee_buy: float = Field(default=0.00001, ge=0.0, le=0.001, description="买入过户费率，默认十万分之一")
    transfer_fee_sell: float = Field(default=0.00001, ge=0.0, le=0.001, description="卖出过户费率，默认十万分之一")


class WalkForwardReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    train_years: int = Field(default=3, description="训练窗口年数")
    test_years: int = Field(default=1, description="测试窗口年数")
    step_years: int = Field(default=1, description="步进年数")
    mode: str = Field(default="rolling", description="窗口模式：rolling 或 anchored")
    # 佣金与滑点
    commission_buy: float = Field(default=0.0003, description="买入佣金率")
    commission_sell: float = Field(default=0.0013, description="卖出佣金率（含印花税）")
    slippage_pct: float = Field(default=0.0, description="滑点百分比")
    slippage_fixed: float = Field(default=0.0, description="固定滑点")
    min_commission: float = Field(default=5.0, description="最低手续费")
    # 印花税和过户费
    stamp_duty: float = Field(default=0.001, ge=0.0, le=0.01, description="印花税费率，卖出时收取，默认千分之一")
    transfer_fee_buy: float = Field(default=0.00001, ge=0.0, le=0.001, description="买入过户费率，默认十万分之一")
    transfer_fee_sell: float = Field(default=0.00001, ge=0.0, le=0.001, description="卖出过户费率，默认十万分之一")


class ParamSearchReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    param_grid: dict[str, Any] = Field(default_factory=dict, description="参数网格，如 {\"fast\": [5,10,15], \"slow\": [20,30]}")
    initial_cash: float = 100000.0
    # 佣金与滑点
    commission_buy: float = Field(default=0.0003, description="买入佣金率")
    commission_sell: float = Field(default=0.0013, description="卖出佣金率（含印花税）")
    slippage_pct: float = Field(default=0.0, description="滑点百分比")
    slippage_fixed: float = Field(default=0.0, description="固定滑点")
    min_commission: float = Field(default=5.0, description="最低手续费")
    # 印花税和过户费
    stamp_duty: float = Field(default=0.001, ge=0.0, le=0.01, description="印花税费率，卖出时收取，默认千分之一")
    transfer_fee_buy: float = Field(default=0.00001, ge=0.0, le=0.001, description="买入过户费率，默认十万分之一")
    transfer_fee_sell: float = Field(default=0.00001, ge=0.0, le=0.001, description="卖出过户费率，默认十万分之一")


class CompareReq(BaseModel):
    backtest_ids: list[str] = Field(default_factory=list, description="要对比的回测ID列表")


# ============== API 路由 ==============

@router.get("/strategies")
def list_strategies() -> dict[str, Any]:
    return {"strategies": STRATEGIES}


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str) -> dict[str, Any]:
    meta = _REGISTRY.get(strategy_id)
    if not meta:
        raise HTTPException(status_code=404, detail="strategy_not_found")
    for s in STRATEGIES:
        if s["strategy_id"] == strategy_id:
            return {"strategy": s}
    raise HTTPException(status_code=404, detail="strategy_not_found")


@router.get("/strategy-instances")
def list_instances(strategy_id: str | None = Query(default=None)) -> dict[str, Any]:
    instances = _load_instances()
    if strategy_id:
        instances = [x for x in instances if x.get("strategy_id") == strategy_id]
    return {"instances": instances}


@router.post("/strategy-instances")
def create_instance(req: InstanceCreateReq = Body(...)) -> dict[str, Any]:
    if req.strategy_id not in _REGISTRY:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="empty_name")

    meta = _REGISTRY[req.strategy_id]
    defaults = dict(meta.default_params)
    params = {**defaults, **req.params}

    instances = _load_instances()
    next_id = str(uuid.uuid4())[:8]
    instances.append({
        "instance_id": next_id,
        "strategy_id": req.strategy_id,
        "name": name,
        "params": params,
    })
    _save_instances(instances)
    return {"instance_id": next_id}


@router.delete("/strategy-instances/{instance_id}")
def delete_instance(instance_id: str) -> dict[str, Any]:
    instances = _load_instances()
    before = len(instances)
    instances = [x for x in instances if x.get("instance_id") != instance_id]
    _save_instances(instances)
    return {"deleted": instance_id, "removed": before - len(instances)}


def _format_backtest_result(bt_result: Any, req: BacktestReq, benchmark_nav_log: list[dict] | None = None, chan_vis: dict | None = None) -> dict[str, Any]:
    """
    格式化回测结果为API响应格式

    Args:
        bt_result: BacktestResult 回测结果对象
        req: BacktestReq 请求对象
        benchmark_nav_log: 基准净值日志（可选）
        chan_vis: 缠论可视化数据（可选）

    Returns:
        格式化后的响应字典
    """
    m = bt_result.metrics
    trades = []
    for t in bt_result.trades:
        action = t.get("action", "sell")
        if action == "buy":
            trades.append({
                "date": t.get("trade_date", ""),
                "action": "buy",
                "price": t.get("price", 0),
                "qty": int(t.get("size", 0)),
                "cost": t.get("cost", 0),
                "proceeds": 0,
                "note": "买入",
                "fee_detail": t.get("fee_detail", ""),
            })
        elif action == "pending_sell":
            pnl = t.get("pnl", 0)
            trades.append({
                "date": t.get("trade_date", ""),
                "action": "pending_sell",
                "price": t.get("price", 0),
                "qty": int(t.get("size", 0)),
                "cost": 0,
                "proceeds": t.get("proceeds", 0),
                "note": f"待卖（浮盈 {pnl:.2f}）",
                "fee_detail": t.get("fee_detail", ""),
            })
        else:
            pnlcomm = t.get("pnlcomm", 0)
            trades.append({
                "date": t.get("trade_date", ""),
                "action": "sell",
                "price": t.get("price", 0),
                "qty": int(t.get("size", 0)),
                "cost": 0,
                "proceeds": t.get("proceeds", 0),
                "note": f"盈亏: {pnlcomm:.2f}",
                "fee_detail": t.get("fee_detail", ""),
            })

    # 基础指标（百分比指标统一返回小数形式，如0.25表示25%，前端负责乘以100显示）
    metrics = {
        "initial_nav": round(m.get("start_value", 100000), 2),
        "final_nav": round(m.get("end_value", 100000), 2),
        "total_return": round(m.get("total_return", 0), 6),
        "annual_return": round(m.get("annual_return", 0), 6),
        "sharpe": round(m.get("sharpe", 0), 4) if m.get("sharpe") is not None else None,
        "max_drawdown": round(m.get("max_drawdown", 0), 6),
        "num_trades": m.get("total_trades", 0),
        "won": m.get("won", 0),
        "lost": m.get("lost", 0),
        "win_rate": round(m.get("win_rate", 0), 6),
    }

    # 增强指标
    enhanced_keys = [
        "volatility", "sortino", "calmar",
        "alpha", "beta", "tracking_error", "information_ratio",
        "profit_factor", "avg_profit_loss",
        "max_consecutive_wins", "max_consecutive_losses",
    ]
    for key in enhanced_keys:
        if key in m:
            val = m[key]
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                metrics[key] = val

    result = {
        "metrics": metrics,
        "trades": trades,
        "nav_log": bt_result.nav_log,
        "strategy_id": req.strategy_id,
        "stock_code": req.stock_code,
        "start_date": req.start,
        "end_date": req.end,
        "drawdown_log": bt_result.drawdown_log if bt_result.drawdown_log else [],
        "monthly_returns": bt_result.monthly_returns if bt_result.monthly_returns else [],
        "benchmark_nav_log": benchmark_nav_log or bt_result.benchmark_nav_log or [],
        "kline": bt_result.kline if bt_result.kline else [],
        "indicator_data": bt_result.indicator_data if bt_result.indicator_data else {},
        "chan_vis": chan_vis,
    }

    return result


def _run_single_backtest(
    df: pd.DataFrame,
    meta: Any,
    params: dict[str, Any],
    req: BacktestReq,
    chan_vis: dict | None = None,
) -> dict[str, Any]:
    from core.strategy.backtest_engine import run_backtest as bt_run

    _t0 = time.time()
    logger.info(
        "单次回测开始",
        extra={
            "stock_code": req.stock_code,
            "strategy_id": req.strategy_id,
            "data_rows": len(df),
            "params": params,
            "initial_cash": req.initial_cash,
        }
    )

    try:
        bt_result = bt_run(
            df=df,
            strategy_cls=meta.bt_strategy_factory(),
            strategy_params=params,
            initial_cash=req.initial_cash,
            requires_weekly=meta.requires_weekly,
            commission_buy=req.commission_buy,
            commission_sell=req.commission_sell,
            slippage_pct=req.slippage_pct,
            slippage_fixed=req.slippage_fixed,
            min_commission=req.min_commission,
            position_pct=req.position_pct,
            stamp_duty=req.stamp_duty,
            transfer_fee_buy=req.transfer_fee_buy,
            transfer_fee_sell=req.transfer_fee_sell,
        )
        _t1 = time.time()
        logger.info(
            "回测引擎执行完成",
            extra={
                "stock_code": req.stock_code,
                "strategy_id": req.strategy_id,
                "engine_duration_ms": round((_t1 - _t0) * 1000),
                "has_error": "error" in bt_result.metrics,
                "metrics_keys": list(bt_result.metrics.keys()),
            }
        )
    except Exception as e:
        logger.error(
            "回测引擎执行异常",
            extra={
                "stock_code": req.stock_code,
                "strategy_id": req.strategy_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round((time.time() - _t0) * 1000),
            }
        )
        raise HTTPException(
            status_code=500,
            detail=f"回测引擎执行异常：{type(e).__name__}: {str(e)}"
        )

    # 增强错误处理：记录详细日志并返回更有意义的错误信息
    if "error" in bt_result.metrics:
        error_info = bt_result.metrics["error"]
        error_detail = bt_result.metrics.get("detail", "")

        # 记录详细错误日志
        logger.error(
            "回测执行失败",
            extra={
                "stock_code": req.stock_code,
                "strategy_id": req.strategy_id,
                "error": error_info,
                "detail": error_detail,
                "start": req.start,
                "end": req.end,
            }
        )

        # 根据错误类型返回不同的HTTP状态码和详细信息
        if error_info == "backtrader_missing":
            raise HTTPException(
                status_code=500,
                detail=f"回测引擎初始化失败：Backtrader库未正确安装或导入失败。详情：{error_detail}"
            )
        elif error_info == "empty_data":
            raise HTTPException(
                status_code=404,
                detail="回测数据为空，请检查股票代码和日期范围是否正确"
            )
        else:
            # 其他未知错误
            raise HTTPException(
                status_code=500,
                detail=f"回测执行失败：{error_info}。详情：{error_detail}" if error_detail else f"回测执行失败：{error_info}"
            )

    # 加载基准数据
    benchmark_nav_log = []
    if req.benchmark_code:
        from core.strategy.benchmark_loader import calc_benchmark_nav
        benchmark_nav_log = calc_benchmark_nav(
            code=req.benchmark_code,
            start=req.start,
            end=req.end,
            initial_cash=req.initial_cash,
        )
        if not benchmark_nav_log:
            logger.warning(
                "基准数据加载失败",
                extra={"benchmark_code": req.benchmark_code, "start": req.start, "end": req.end},
            )

    # 使用 enhance_metrics 增强指标
    from core.strategy.metrics_calculator import enhance_metrics
    enhanced_metrics = enhance_metrics(
        base_metrics=bt_result.metrics,
        nav_log=bt_result.nav_log,
        benchmark_nav_log=benchmark_nav_log if benchmark_nav_log is not None else None,
    )

    # 创建新的 BacktestResult 实例（因为原实例是 frozen dataclass，不可修改）
    from core.strategy.backtest_engine import BacktestResult
    from dataclasses import replace
    bt_result = replace(bt_result, metrics=enhanced_metrics)

    return _format_backtest_result(bt_result, req, benchmark_nav_log=benchmark_nav_log, chan_vis=chan_vis)


@router.post("/backtest/run")
def run_backtest(req: BacktestReq = Body(...)) -> dict[str, Any]:
    _t0 = time.time()
    logger.info(
        "回测请求开始",
        extra={
            "stock_code": req.stock_code,
            "strategy_id": req.strategy_id,
            "start": req.start,
            "end": req.end,
            "interval_mode": req.interval_mode,
            "params": req.params,
            "benchmark_code": req.benchmark_code,
        }
    )

    try:
        start_d = pd.to_datetime(req.start).date()
        end_d = pd.to_datetime(req.end).date()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_date")

    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    meta = _REGISTRY.get(req.strategy_id)
    if not meta:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    df = _load_daily(req.stock_code, str(start_d), str(end_d))
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data_for_stock")

    params = dict(meta.default_params)
    params.update(req.params)

    # 缠论数据
    _chan_vis_data = None
    if meta.requires_chan:
        from core.strategy.chan_engine import add_chan_fields
        chan_backend = params.pop("chan_backend", "self")
        chan_result = add_chan_fields(df, backend=chan_backend, symbol=req.stock_code)
        df = chan_result.df
        if df["chan_signal"].isna().all():
            raise HTTPException(status_code=400, detail="chan_data_unavailable_当前缠论数据不可用")
        # 保存缠论可视化数据，后续传给前端
        _chan_vis_data = chan_result.chan_vis

    # 区间模式支持
    if req.interval_mode == "train_val_test":
        _load_cost = time.time()
        logger.info(
            "数据加载完成，开始区间模式回测",
            extra={"stock_code": req.stock_code, "data_rows": len(df), "load_cost_ms": round((_load_cost - _t0) * 1000)}
        )
        result = _run_interval_backtest(df, meta, params, req, chan_vis=_chan_vis_data)
        _t1 = time.time()
        logger.info(
            "回测请求结束（区间模式）",
            extra={
                "stock_code": req.stock_code,
                "strategy_id": req.strategy_id,
                "duration_ms": round((_t1 - _t0) * 1000),
                "interval_count": len(result.get("interval_results", [])),
            }
        )
        return result

    # 普通回测（增加异常包装）
    try:
        _bt_start = time.time()
        result = _run_single_backtest(df, meta, params, req, chan_vis=_chan_vis_data)
        _bt_end = time.time()
        _trades_count = len(result.get("trades", []))
        _metrics = result.get("metrics", {})
        logger.info(
            "回测执行完成",
            extra={
                "stock_code": req.stock_code,
                "strategy_id": req.strategy_id,
                "duration_ms": round((_bt_end - _t0) * 1000),
                "backtest_duration_ms": round((_bt_end - _bt_start) * 1000),
                "trades_count": _trades_count,
                "total_return": _metrics.get("total_return"),
                "sharpe": _metrics.get("sharpe"),
                "max_drawdown": _metrics.get("max_drawdown"),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "回测执行发生未预期异常",
            extra={
                "stock_code": req.stock_code,
                "strategy_id": req.strategy_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round((time.time() - _t0) * 1000),
            }
        )
        raise HTTPException(
            status_code=500,
            detail=f"回测执行失败：系统内部错误（{type(e).__name__}）。请联系管理员查看详细日志"
        )

    # 保存回测记录到数据库
    _save_start = time.time()
    _save_backtest_to_db(result, req)
    logger.info(
        "回测记录保存完成",
        extra={
            "stock_code": req.stock_code,
            "save_duration_ms": round((time.time() - _save_start) * 1000),
            "total_duration_ms": round((time.time() - _t0) * 1000),
        }
    )

    return result


def _run_interval_backtest(
    df: pd.DataFrame,
    meta: Any,
    params: dict[str, Any],
    req: BacktestReq,
    chan_vis: dict | None = None,
) -> dict[str, Any]:
    _t0 = time.time()
    df_all = df.copy()
    if "trade_date" in df_all.columns:
        df_all["trade_date"] = pd.to_datetime(df_all["trade_date"])

    intervals: list[dict[str, str]] = []

    if req.custom_intervals:
        intervals = req.custom_intervals
        logger.info(
            "区间模式-自定义区间",
            extra={"interval_count": len(intervals), "intervals": intervals}
        )
    else:
        total_days = len(df_all)
        train_end = int(total_days * req.train_ratio)
        val_end = train_end + int(total_days * req.val_ratio)

        df_train = df_all.iloc[:train_end]
        df_val = df_all.iloc[train_end:val_end]
        df_test = df_all.iloc[val_end:]

        if not df_train.empty:
            intervals.append({
                "name": "train",
                "start": str(df_train["trade_date"].iloc[0].date()),
                "end": str(df_train["trade_date"].iloc[-1].date()),
            })
        if not df_val.empty:
            intervals.append({
                "name": "val",
                "start": str(df_val["trade_date"].iloc[0].date()),
                "end": str(df_val["trade_date"].iloc[-1].date()),
            })
        if not df_test.empty:
            intervals.append({
                "name": "test",
                "start": str(df_test["trade_date"].iloc[0].date()),
                "end": str(df_test["trade_date"].iloc[-1].date()),
            })

        logger.info(
            "区间模式-按比例划分",
            extra={
                "total_days": total_days,
                "train_ratio": req.train_ratio,
                "val_ratio": req.val_ratio,
                "test_ratio": req.test_ratio,
                "train_days": len(df_train),
                "val_days": len(df_val),
                "test_days": len(df_test),
                "intervals": intervals,
            }
        )

    interval_results = []
    for interval in intervals:
        i_start = interval.get("start", "")
        i_end = interval.get("end", "")
        i_name = interval.get("name", "unknown")

        _it0 = time.time()
        i_df = df_all[(df_all["trade_date"] >= i_start) & (df_all["trade_date"] <= i_end)].copy()
        if i_df.empty:
            interval_results.append({"name": i_name, "start": i_start, "end": i_end, "error": "no_data"})
            logger.warning(
                "区间模式-子区间无数据",
                extra={"interval_name": i_name, "start": i_start, "end": i_end}
            )
            continue

        if meta.requires_chan and "chan_signal" not in i_df.columns:
            from core.strategy.chan_engine import add_chan_fields
            chan_backend = params.get("chan_backend", "self")
            chan_result = add_chan_fields(i_df, backend=chan_backend, symbol=req.stock_code)
            i_df = chan_result.df

        sub_req = BacktestReq(
            stock_code=req.stock_code,
            start=i_start,
            end=i_end,
            strategy_id=req.strategy_id,
            params=req.params,
            initial_cash=req.initial_cash,
            commission_buy=req.commission_buy,
            commission_sell=req.commission_sell,
            slippage_pct=req.slippage_pct,
            slippage_fixed=req.slippage_fixed,
            min_commission=req.min_commission,
            benchmark_code=req.benchmark_code,
            position_pct=req.position_pct,
            stamp_duty=req.stamp_duty,
            transfer_fee_buy=req.transfer_fee_buy,
            transfer_fee_sell=req.transfer_fee_sell,
        )

        try:
            sub_result = _run_single_backtest(i_df, meta, params, sub_req, chan_vis=chan_vis)
            _it1 = time.time()
            _sub_metrics = sub_result.get("metrics", {})
            interval_results.append({
                "name": i_name,
                "start": i_start,
                "end": i_end,
                "result": sub_result,
            })
            logger.info(
                "区间模式-子区间回测完成",
                extra={
                    "interval_name": i_name,
                    "start": i_start,
                    "end": i_end,
                    "duration_ms": round((_it1 - _it0) * 1000),
                    "data_rows": len(i_df),
                    "total_return": _sub_metrics.get("total_return"),
                    "sharpe": _sub_metrics.get("sharpe"),
                    "trades_count": len(sub_result.get("trades", [])),
                }
            )
        except HTTPException as e:
            interval_results.append({
                "name": i_name,
                "start": i_start,
                "end": i_end,
                "error": e.detail,
            })
            logger.error(
                "区间模式-子区间回测异常",
                extra={"interval_name": i_name, "start": i_start, "end": i_end, "error": e.detail}
            )

    return {
        "interval_mode": "train_val_test",
        "interval_results": interval_results,
        "strategy_id": req.strategy_id,
        "stock_code": req.stock_code,
        "start_date": req.start,
        "end_date": req.end,
        "metrics": None,
        "trades": [],
        "nav_log": [],
        "benchmark_nav_log": [],
        "drawdown_log": [],
        "monthly_returns": [],
    }


def _save_backtest_to_db(result: dict[str, Any], req: BacktestReq) -> None:
    """
    将回测结果保存到数据库

    Args:
        result: 格式化后的回测结果
        req: 回测请求
    """
    try:
        from core.strategy.backtest_storage import save_backtest, ensure_backtest_tables
        ensure_backtest_tables()
        record = {
            "strategy_id": req.strategy_id,
            "stock_code": req.stock_code,
            "start_date": req.start,
            "end_date": req.end,
            "initial_cash": req.initial_cash,
            "commission_buy": req.commission_buy,
            "commission_sell": req.commission_sell,
            "slippage_pct": req.slippage_pct,
            "slippage_fixed": req.slippage_fixed,
            "min_commission": req.min_commission,
            "stamp_duty": req.stamp_duty,
            "transfer_fee_buy": req.transfer_fee_buy,
            "transfer_fee_sell": req.transfer_fee_sell,
            "benchmark_code": req.benchmark_code,
            "params": req.params,
            "metrics": result.get("metrics", {}),
            "trades": result.get("trades", []),
            "nav_log": result.get("nav_log", []),
            "benchmark_nav_log": result.get("benchmark_nav_log", []),
            "drawdown_log": result.get("drawdown_log", []),
            "monthly_returns": result.get("monthly_returns", []),
            "chan_vis": result.get("chan_vis"),
            "kline": result.get("kline", []),
        }
        backtest_id = save_backtest(record)
        result["backtest_id"] = backtest_id
    except Exception as e:
        logger.error("保存回测记录失败", extra={"error": str(e)})
        result["backtest_id"] = None
        result["save_warning"] = "回测结果保存失败，数据未持久化"


def _save_batch_backtest_to_db(
    task_result: dict[str, Any],
    req: BatchBacktestReq,
    stock_code: str
) -> None:
    """
    将批量回测中的单个任务结果保存到数据库

    Args:
        task_result: 单个任务的回测结果
        req: 批量回测请求
        stock_code: 股票代码
    """
    try:
        from core.strategy.backtest_storage import save_backtest, ensure_backtest_tables
        ensure_backtest_tables()
        record = {
            "strategy_id": req.strategy_id,
            "stock_code": stock_code,
            "start_date": req.start,
            "end_date": req.end,
            "initial_cash": req.initial_cash,
            "commission_buy": req.commission_buy,
            "commission_sell": req.commission_sell,
            "slippage_pct": req.slippage_pct,
            "slippage_fixed": req.slippage_fixed,
            "min_commission": req.min_commission,
            "stamp_duty": req.stamp_duty,
            "transfer_fee_buy": req.transfer_fee_buy,
            "transfer_fee_sell": req.transfer_fee_sell,
            "benchmark_code": None,  # 批量回测暂不支持基准
            "params": req.params,
            "metrics": task_result.get("metrics", {}),
            "trades": task_result.get("trades", []),
            "nav_log": task_result.get("nav_log", []),
            "benchmark_nav_log": [],
            "drawdown_log": [],
            "monthly_returns": [],
            # 缠论可视化数据和K线数据
            "chan_vis": task_result.get("chan_vis"),
            "kline": task_result.get("kline", []),
            # 标记为批量回测的一部分
            "batch_mode": True,
        }
        backtest_id = save_backtest(record)
        task_result["backtest_id"] = backtest_id
    except Exception as e:
        logger.error(
            "保存批量回测任务记录失败",
            extra={"stock_code": stock_code, "error": str(e)}
        )
        raise  # 重新抛出异常，让调用方处理


@router.get("/backtest/history")
def backtest_history(
    stock_code: str | None = Query(default=None),
    strategy_id: str | None = Query(default=None),
) -> dict[str, Any]:
    history_path = Path(__file__).parent.parent.parent.parent / ".ai_quant" / "backtest_history.json"
    if not history_path.exists():
        return {"items": []}
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            items = json.load(f) or []
    except Exception:
        items = []
    if stock_code:
        items = [x for x in items if x.get("stock_code") == stock_code]
    if strategy_id:
        items = [x for x in items if x.get("strategy_id") == strategy_id]
    return {"items": items}


@router.post("/backtest/batch")
def run_batch_backtest(req: BatchBacktestReq = Body(...)) -> dict[str, Any]:
    """批量回测API：支持选择多个股票或分组进行批量策略回测"""
    try:
        start_d = pd.to_datetime(req.start).date()
        end_d = pd.to_datetime(req.end).date()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_date")

    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    meta = _REGISTRY.get(req.strategy_id)
    if not meta:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    # 确定要回测的股票代码列表
    stock_codes = []
    if req.selection_type == "group":
        if not req.group_id:
            raise HTTPException(status_code=400, detail="group_id_required")
        # 从数据库获取分组的股票
        try:
            cfg = load_mysql_config()
            conn = connect(cfg)
            rows = query_dict(
                conn,
                "SELECT stock_code FROM trade_stock_group_item WHERE group_id = %s",
                (req.group_id,),
            )
            stock_codes = [str(r.get("stock_code", "")).strip() for r in rows]
            conn.close()
        except Exception as e:
            logger.error("获取分组股票失败", extra={"group_id": req.group_id, "error": str(e)})
            raise HTTPException(status_code=500, detail="failed_to_load_group")
    else:
        # 使用提供的股票代码列表
        stock_codes = [c.strip() for c in req.stock_codes if c.strip()]

    if not stock_codes:
        raise HTTPException(status_code=400, detail="no_stocks_selected")

    logger.info(
        "开始批量回测",
        extra={
            "strategy_id": req.strategy_id,
            "stock_count": len(stock_codes),
            "start": req.start,
            "end": req.end,
        },
    )

    # 创建并执行批量回测
    def loader_func(code: str, s: str, e: str) -> pd.DataFrame:
        return _load_daily(code, s, e)

    engine = MultiAgentBacktestEngine(loader_func, max_workers=req.max_workers)
    params = dict(meta.default_params)
    params.update(req.params)

    batch = engine.create_batch(
        stock_codes=stock_codes,
        strategy_id=req.strategy_id,
        strategy_cls=meta.bt_strategy_factory(),
        strategy_params=params,
        initial_cash=req.initial_cash,
        start_date=req.start,
        end_date=req.end,
        # 传递交易成本配置
        commission_buy=req.commission_buy,
        commission_sell=req.commission_sell,
        slippage_pct=req.slippage_pct,
        slippage_fixed=req.slippage_fixed,
        min_commission=req.min_commission,
        # 传递仓位比例
        position_pct=req.position_pct,
        # 传递印花税和过户费
        stamp_duty=req.stamp_duty,
        transfer_fee_buy=req.transfer_fee_buy,
        transfer_fee_sell=req.transfer_fee_sell,
    )

    batch = engine.execute_batch(batch)

    # 构建结果
    results_list = []
    for task in batch.results:
        task_result = {
            "task_id": task.task_id,
            "stock_code": task.stock_code,
            "status": task.status.value,
            "error": task.error,
        }
        if task.result:
            task_result["metrics"] = task.result.metrics
            task_result["nav_log"] = task.result.nav_log
            task_result["trades"] = task.result.trades

            # 对成功的任务保存回测记录到数据库
            try:
                _save_batch_backtest_to_db(task_result, req, task.stock_code)
            except Exception as e:
                logger.error(
                    "保存批量回测记录失败",
                    extra={"task_id": task.task_id, "stock_code": task.stock_code, "error": str(e)}
                )

        results_list.append(task_result)

    response = {
        "batch_id": batch.batch_id,
        "total_tasks": batch.total_tasks,
        "completed_tasks": batch.completed_tasks,
        "failed_tasks": batch.failed_tasks,
        "results": results_list,
        "aggregated": batch.aggregated_metrics,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
    }

    logger.info(
        "批量回测完成",
        extra={
            "batch_id": batch.batch_id,
            "total": batch.total_tasks,
            "completed": batch.completed_tasks,
            "failed": batch.failed_tasks,
        },
    )

    return response


# ============== Walk-Forward 滚动验证路由 ==============

@router.post("/backtest/walk-forward")
def run_walk_forward(req: WalkForwardReq = Body(...)) -> dict[str, Any]:
    """
    Walk-Forward 滚动验证API
    对策略进行时序交叉验证，评估策略在不同时间窗口的稳定性
    """
    try:
        start_d = pd.to_datetime(req.start).date()
        end_d = pd.to_datetime(req.end).date()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_date")

    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    meta = _REGISTRY.get(req.strategy_id)
    if not meta:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    df = _load_daily(req.stock_code, str(start_d), str(end_d))
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data_for_stock")

    params = dict(meta.default_params)
    params.update(req.params)

    # 缠论数据
    if meta.requires_chan:
        from core.strategy.chan_engine import add_chan_fields
        chan_backend = params.pop("chan_backend", "self")
        chan_result = add_chan_fields(df, backend=chan_backend, symbol=req.stock_code)
        df = chan_result.df
        if df["chan_signal"].isna().all():
            raise HTTPException(status_code=400, detail="chan_data_unavailable_当前缠论数据不可用")

    from core.strategy.walk_forward_engine import generate_windows, run_walk_forward as wf_run

    windows = generate_windows(
        start=req.start,
        end=req.end,
        train_years=req.train_years,
        test_years=req.test_years,
        step_years=req.step_years,
        mode=req.mode,
    )

    if not windows:
        raise HTTPException(status_code=400, detail="no_valid_windows")

    bt_kwargs = {
        "commission_buy": req.commission_buy,
        "commission_sell": req.commission_sell,
        "slippage_pct": req.slippage_pct,
        "slippage_fixed": req.slippage_fixed,
        "min_commission": req.min_commission,
        "stamp_duty": req.stamp_duty,
        "transfer_fee_buy": req.transfer_fee_buy,
        "transfer_fee_sell": req.transfer_fee_sell,
    }

    wf_result = wf_run(
        df=df,
        strategy_cls=meta.bt_strategy_factory(),
        strategy_params=params,
        windows=windows,
        initial_cash=req.initial_cash,
        **bt_kwargs,
    )

    return {
        "strategy_id": req.strategy_id,
        "stock_code": req.stock_code,
        "start_date": req.start,
        "end_date": req.end,
        "mode": req.mode,
        "train_years": req.train_years,
        "test_years": req.test_years,
        "step_years": req.step_years,
        "windows": wf_result.windows,
        "stability": wf_result.stability,
        "aggregated_metrics": wf_result.aggregated_metrics,
    }


# ============== 回测记录管理路由 ==============

@router.get("/backtest/records")
def list_backtest_records(
    strategy_id: str | None = Query(default=None),
    stock_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """分页查询回测记录"""
    from core.strategy.backtest_storage import list_backtests, ensure_backtest_tables
    ensure_backtest_tables()
    return list_backtests(
        strategy_id=strategy_id,
        stock_code=stock_code,
        page=page,
        page_size=page_size,
    )


@router.get("/backtest/records/{backtest_id}")
def get_backtest_record(backtest_id: str) -> dict[str, Any]:
    """获取单条回测记录详情"""
    from core.strategy.backtest_storage import get_backtest, ensure_backtest_tables
    ensure_backtest_tables()
    record = get_backtest(backtest_id)
    if not record:
        raise HTTPException(status_code=404, detail="backtest_not_found")
    return record


@router.delete("/backtest/records/{backtest_id}")
def delete_backtest_record(backtest_id: str) -> dict[str, Any]:
    """删除回测记录"""
    from core.strategy.backtest_storage import delete_backtest, ensure_backtest_tables
    ensure_backtest_tables()
    success = delete_backtest(backtest_id)
    if not success:
        raise HTTPException(status_code=404, detail="backtest_not_found")
    return {"deleted": backtest_id}


@router.post("/backtest/compare")
def compare_backtests(req: CompareReq = Body(...)) -> dict[str, Any]:
    """对比多条回测记录"""
    from core.strategy.backtest_storage import compare_backtests, ensure_backtest_tables
    ensure_backtest_tables()
    if not req.backtest_ids:
        raise HTTPException(status_code=400, detail="empty_backtest_ids")
    results = compare_backtests(req.backtest_ids)
    return {"comparisons": results}


# ============== 参数搜索路由 ==============

@router.post("/backtest/param-search")
def run_param_search(req: ParamSearchReq = Body(...)) -> dict[str, Any]:
    _t0 = time.time()
    logger.info(
        "参数搜索请求开始",
        extra={
            "stock_code": req.stock_code,
            "strategy_id": req.strategy_id,
            "start": req.start,
            "end": req.end,
            "param_grid": req.param_grid,
        }
    )

    try:
        start_d = pd.to_datetime(req.start).date()
        end_d = pd.to_datetime(req.end).date()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_date")

    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    meta = _REGISTRY.get(req.strategy_id)
    if not meta:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    df = _load_daily(req.stock_code, str(start_d), str(end_d))
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data_for_stock")

    if meta.requires_chan:
        from core.strategy.chan_engine import add_chan_fields
        chan_backend = params.pop("chan_backend", "self")
        chan_result = add_chan_fields(df, backend=chan_backend, symbol=req.stock_code)
        df = chan_result.df
        if df["chan_signal"].isna().all():
            raise HTTPException(status_code=400, detail="chan_data_unavailable_当前缠论数据不可用")

    from core.strategy.param_optimizer import run_param_search as ps_run

    bt_kwargs = {
        "commission_buy": req.commission_buy,
        "commission_sell": req.commission_sell,
        "slippage_pct": req.slippage_pct,
        "slippage_fixed": req.slippage_fixed,
        "min_commission": req.min_commission,
    }

    param_count = 1
    for v in req.param_grid.values():
        param_count *= len(v) if isinstance(v, list) else 1

    logger.info(
        "参数搜索开始执行",
        extra={
            "stock_code": req.stock_code,
            "param_count": param_count,
            "data_rows": len(df),
        }
    )

    _ps_start = time.time()
    result = ps_run(
        df=df,
        strategy_cls=meta.bt_strategy_factory(),
        param_grid=req.param_grid,
        initial_cash=req.initial_cash,
        **bt_kwargs,
    )
    _ps_end = time.time()

    best_return_val = result.best_by_return.get("total_return") if result.best_by_return else None
    best_sharpe_val = result.best_by_sharpe.get("sharpe") if result.best_by_sharpe else None

    logger.info(
        "参数搜索请求结束",
        extra={
            "stock_code": req.stock_code,
            "strategy_id": req.strategy_id,
            "total_combinations": result.total_combinations,
            "successful_count": len(result.results),
            "duration_ms": round((_ps_end - _t0) * 1000),
            "search_duration_ms": round((_ps_end - _ps_start) * 1000),
            "best_return": best_return_val,
            "best_sharpe": best_sharpe_val,
        }
    )

    return {
        "strategy_id": req.strategy_id,
        "stock_code": req.stock_code,
        "start_date": req.start,
        "end_date": req.end,
        "total_combinations": result.total_combinations,
        "results": result.results,
        "best_by_return": result.best_by_return,
        "best_by_sharpe": result.best_by_sharpe,
    }


# ============== 行情预览辅助函数 ==============

def _calc_adx(df: pd.DataFrame, period: int = 14):
    """计算ADX指标（纯pandas实现）"""
    close = df['close']
    high = df['high'].copy()
    low = df['low'].copy()
    # 当 high/low 为 NaN 时（如指数数据），使用 close 作为回退值
    if high.isna().any():
        high = high.fillna(close)
    if low.isna().any():
        low = low.fillna(close)
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # +DM / -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    # 平滑处理
    atr = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    return adx, plus_di, minus_di


def _calc_boll_width(df: pd.DataFrame, period: int = 20, devfactor: float = 2.0):
    """计算布林带宽度"""
    mid = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    upper = mid + devfactor * std
    lower = mid - devfactor * std
    width = (upper - lower) / mid
    return width, upper, lower, mid


# ============== 行情预览请求模型 ==============

class MarketPreviewReq(BaseModel):
    stock_code: str = Field(..., description="股票代码，如 000001")
    start_date: str = Field(..., description="开始日期，如 2024-01-01")
    end_date: str = Field(..., description="结束日期，如 2025-01-01")
    detector_type: str = Field(default="adx", description="行情判别方式: adx/ma/boll")
    adx_period: int = Field(default=14, description="ADX周期")
    adx_trend_threshold: float = Field(default=25.0, description="ADX趋势阈值")
    adx_range_threshold: float = Field(default=20.0, description="ADX震荡阈值")
    det_ma_fast: int = Field(default=10, description="快均线周期")
    det_ma_slow: int = Field(default=30, description="慢均线周期")
    det_boll_period: int = Field(default=20, description="布林带周期")
    det_boll_devfactor: float = Field(default=2.0, description="布林带标准差倍数")


# ============== 行情预览路由 ==============

@router.post("/market-preview")
def market_preview(req: MarketPreviewReq = Body(...)) -> dict[str, Any]:
    """行情预览：根据指定方式判别每日行情类型（趋势/震荡/中性）"""
    code = req.stock_code.strip().upper()
    if "." not in code:
        if code.startswith("6"):
            code += ".SH"
        elif code.startswith(("0", "3")):
            code += ".SZ"
    # 计算预热开始日期：从请求起始日期往前推90天，用于 ADX 等指标的预热计算
    warmup_start = req.start_date
    try:
        start_dt = dt.strptime(req.start_date, "%Y-%m-%d")
        warmup_start = (start_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    except ValueError:
        pass

    # 加载包含预热数据的完整数据
    df = _load_daily(code, warmup_start, req.end_date)
    if df.empty:
        return {
            "dates": [],
            "closes": [],
            "indicator_values": [],
            "indicator_name": "",
            "market_types": [],
            "stock_name": "",
        }

    # 获取股票名称
    stock_name = ""
    if "stock_name" in df.columns and not df["stock_name"].dropna().empty:
        stock_name = str(df["stock_name"].dropna().iloc[-1])

    indicator_values = []
    indicator_name = ""
    market_types = []

    if req.detector_type == "adx":
        indicator_name = "ADX"
        adx, plus_di, minus_di = _calc_adx(df, period=req.adx_period)
        indicator_values = [round(v, 2) if pd.notna(v) else None for v in adx]
        for v in adx:
            if pd.isna(v):
                market_types.append("neutral")
            elif v >= req.adx_trend_threshold:
                market_types.append("trend")
            elif v <= req.adx_range_threshold:
                market_types.append("range")
            else:
                market_types.append("neutral")

    elif req.detector_type == "ma":
        indicator_name = "MA_diff"
        ma_fast = df["close"].rolling(req.det_ma_fast).mean()
        ma_slow = df["close"].rolling(req.det_ma_slow).mean()
        diff = ma_fast - ma_slow
        indicator_values = [round(v, 4) if pd.notna(v) else None for v in diff]
        for v in diff:
            if pd.isna(v):
                market_types.append("neutral")
            elif v > 0:
                market_types.append("trend")
            else:
                market_types.append("range")

    elif req.detector_type == "boll":
        indicator_name = "BOLL_width"
        width, upper, lower, mid = _calc_boll_width(df, period=req.det_boll_period, devfactor=req.det_boll_devfactor)
        indicator_values = [round(v, 4) if pd.notna(v) else None for v in width]
        close = df["close"]
        for i in range(len(df)):
            w = width.iloc[i]
            c = close.iloc[i]
            u = upper.iloc[i]
            l = lower.iloc[i]
            if pd.isna(w) or pd.isna(u) or pd.isna(l):
                market_types.append("neutral")
            elif c > u or c < l:
                market_types.append("trend")
            else:
                market_types.append("range")

    else:
        raise HTTPException(status_code=400, detail=f"unsupported_detector_type: {req.detector_type}")

    # 裁剪到请求的日期范围（去除预热数据）
    mask = df["trade_date"] >= pd.Timestamp(req.start_date)
    df = df[mask].reset_index(drop=True)
    indicator_values = [indicator_values[i] for i in range(len(indicator_values)) if mask.iloc[i]]
    market_types = [market_types[i] for i in range(len(market_types)) if mask.iloc[i]]

    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in df["trade_date"]]
    closes = df["close"].round(2).tolist()

    return {
        "dates": dates,
        "closes": closes,
        "indicator_values": indicator_values,
        "indicator_name": indicator_name,
        "market_types": market_types,
        "stock_name": stock_name,
    }


# ============== 股票指数列表路由 ==============

@router.get("/indices")
def list_indices() -> dict[str, Any]:
    """获取所有可用的股票指数列表"""
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    try:
        rows = query_dict(
            conn,
            "SELECT stock_code, stock_name FROM trade_stock_master WHERE asset_type = %s ORDER BY stock_code ASC",
            ("index",),
        )
        indices = [{"stock_code": r["stock_code"], "stock_name": r["stock_name"]} for r in rows]
        return {"indices": indices}
    finally:
        conn.close()
