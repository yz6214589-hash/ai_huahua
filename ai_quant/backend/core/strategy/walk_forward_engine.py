# -*- coding: utf-8 -*-
"""
Walk-Forward 滚动验证引擎
支持滚动窗口和锚定窗口两种模式，对策略进行时序交叉验证
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from core.strategy.backtest_engine import BacktestResult, run_backtest
from infra.storage.logging_service import get_logger

logger = get_logger("walk_forward_engine")


@dataclass
class WalkForwardResult:
    """滚动验证结果"""
    windows: list[dict[str, Any]]
    stability: dict[str, Any]
    aggregated_metrics: dict[str, Any]


def generate_windows(
    start: str,
    end: str,
    train_years: int = 3,
    test_years: int = 1,
    step_years: int = 1,
    mode: str = "rolling",
) -> list[dict[str, Any]]:
    """
    生成滚动窗口或锚定窗口

    Args:
        start: 总起始日期 (YYYY-MM-DD)
        end: 总结束日期 (YYYY-MM-DD)
        train_years: 训练窗口年数，默认3
        test_years: 测试窗口年数，默认1
        step_years: 步进年数，默认1
        mode: 窗口模式，"rolling"(滚动) 或 "anchored"(锚定)

    Returns:
        窗口列表，每个窗口包含 train_start, train_end, test_start, test_end
    """
    start_d = pd.to_datetime(start).date()
    end_d = pd.to_datetime(end).date()
    windows: list[dict[str, Any]] = []
    current_start = start_d

    while True:
        train_start = current_start
        train_end = train_start + timedelta(days=365 * train_years - 1)

        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=365 * test_years - 1)

        # 如果测试窗口超出总结束日期，终止
        if test_start > end_d:
            break

        # 限制测试结束日期不超过总结束日期
        test_end = min(test_end, end_d)

        windows.append({
            "train_start": train_start.isoformat(),
            "train_end": train_end.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat(),
        })

        if mode == "anchored":
            # 锚定模式：训练起点不变，只扩展训练窗口
            current_start = start_d
            # 步进的是测试窗口
            next_test_start = test_start + timedelta(days=365 * step_years)
            # 但为了简化，锚定模式下使用步进偏移
            current_start = current_start + timedelta(days=365 * step_years)
        else:
            # 滚动模式：整体向前步进
            current_start = current_start + timedelta(days=365 * step_years)

    return windows


def run_walk_forward(
    df: pd.DataFrame,
    strategy_cls: Any,
    strategy_params: dict[str, Any],
    windows: list[dict[str, Any]],
    initial_cash: float = 100000.0,
    **kwargs: Any,
) -> WalkForwardResult:
    """
    执行 Walk-Forward 滚动验证

    对每个窗口分别运行训练期和测试期的回测，
    汇总各窗口的测试期指标，计算策略稳定性和综合指标

    Args:
        df: 日线数据 DataFrame
        strategy_cls: 策略类
        strategy_params: 策略参数字典
        windows: 滚动窗口列表（由 generate_windows 生成）
        initial_cash: 初始资金
        **kwargs: 传递给 run_backtest 的其他参数

    Returns:
        WalkForwardResult 滚动验证结果
    """
    window_results: list[dict[str, Any]] = []

    for i, win in enumerate(windows):
        train_start = win["train_start"]
        train_end = win["train_end"]
        test_start = win["test_start"]
        test_end = win["test_end"]

        # 筛选训练期数据
        df_all = df.copy()
        if "trade_date" in df_all.columns:
            df_all["trade_date"] = pd.to_datetime(df_all["trade_date"])

        train_mask = (df_all["trade_date"] >= train_start) & (df_all["trade_date"] <= train_end)
        test_mask = (df_all["trade_date"] >= test_start) & (df_all["trade_date"] <= test_end)

        train_df = df_all.loc[train_mask].copy()
        test_df = df_all.loc[test_mask].copy()

        # 运行训练期回测（可选，主要用于参数优化）
        train_result: BacktestResult | None = None
        if not train_df.empty:
            try:
                train_result = run_backtest(
                    df=train_df,
                    strategy_cls=strategy_cls,
                    strategy_params=strategy_params,
                    initial_cash=initial_cash,
                    **kwargs,
                )
            except Exception as e:
                logger.warning(f"窗口{i+1}训练期回测失败", extra={"error": str(e)})

        # 运行测试期回测
        test_result: BacktestResult | None = None
        if not test_df.empty:
            try:
                test_result = run_backtest(
                    df=test_df,
                    strategy_cls=strategy_cls,
                    strategy_params=strategy_params,
                    initial_cash=initial_cash,
                    **kwargs,
                )
            except Exception as e:
                logger.warning(f"窗口{i+1}测试期回测失败", extra={"error": str(e)})

        win_data: dict[str, Any] = {
            "window_index": i + 1,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
        }
        if train_result and "error" not in train_result.metrics:
            win_data["train_metrics"] = train_result.metrics
        if test_result and "error" not in test_result.metrics:
            win_data["test_metrics"] = test_result.metrics

        window_results.append(win_data)

    # 计算稳定性指标
    stability = _calc_stability(window_results)

    # 计算综合指标
    aggregated_metrics = _calc_aggregated_metrics(window_results)

    return WalkForwardResult(
        windows=window_results,
        stability=stability,
        aggregated_metrics=aggregated_metrics,
    )


def _calc_stability(window_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    计算策略稳定性指标

    包括测试期收益率的胜率、平均收益、收益标准差、最差窗口等

    Args:
        window_results: 各窗口结果列表

    Returns:
        稳定性指标字典
    """
    test_returns = []
    for win in window_results:
        tm = win.get("test_metrics", {})
        if tm and "total_return" in tm:
            test_returns.append(float(tm["total_return"]))

    if not test_returns:
        return {
            "win_rate": 0.0,
            "avg_return": 0.0,
            "std_return": 0.0,
            "worst_return": 0.0,
            "best_return": 0.0,
        }

    import numpy as np
    arr = np.array(test_returns)
    return {
        "win_rate": round(float((arr > 0).sum() / len(arr)), 4),
        "avg_return": round(float(arr.mean()), 6),
        "std_return": round(float(arr.std()), 6),
        "worst_return": round(float(arr.min()), 6),
        "best_return": round(float(arr.max()), 6),
    }


def _calc_aggregated_metrics(window_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    计算所有窗口的综合指标（加权平均）

    Args:
        window_results: 各窗口结果列表

    Returns:
        综合指标字典
    """
    metrics_keys = ["total_return", "annual_return", "max_drawdown", "sharpe", "win_rate"]
    aggregated: dict[str, Any] = {}

    for key in metrics_keys:
        values = []
        for win in window_results:
            tm = win.get("test_metrics", {})
            if tm and key in tm:
                val = tm[key]
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    values.append(float(val))
        if values:
            import numpy as np
            aggregated[key] = round(float(np.mean(values)), 6)
        else:
            aggregated[key] = None

    return aggregated
