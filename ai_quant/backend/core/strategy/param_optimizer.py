# -*- coding: utf-8 -*-
"""
参数优化模块
支持对策略参数进行网格搜索（笛卡尔积），找到最优参数组合
限制最大组合数为1000以避免计算量过大
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.strategy.backtest_engine import run_backtest
from infra.storage.logging_service import get_logger

logger = get_logger("param_optimizer")

# 最大允许的参数组合数
_MAX_COMBINATIONS = 1000


@dataclass
class ParamSearchResult:
    """参数搜索结果"""
    total_combinations: int
    results: list[dict[str, Any]]
    best_by_return: dict[str, Any] | None
    best_by_sharpe: dict[str, Any] | None


def generate_param_combinations(param_grid: dict) -> list[dict]:
    """
    生成参数组合的笛卡尔积

    Args:
        param_grid: 参数网格，如 {"fast": [5, 10, 15], "slow": [20, 30]}

    Returns:
        参数组合列表，上限1000
    """
    if not param_grid:
        return [{}]

    keys = list(param_grid.keys())
    values = [param_grid[k] if isinstance(param_grid[k], list) else [param_grid[k]] for k in keys]

    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))
        if len(combinations) >= _MAX_COMBINATIONS:
            logger.warning(f"参数组合已达上限{_MAX_COMBINATIONS}，截断")
            break

    return combinations


def run_param_search(
    df: pd.DataFrame,
    strategy_cls: Any,
    param_grid: dict,
    initial_cash: float = 100000.0,
    **kwargs: Any,
) -> ParamSearchResult:
    """
    执行参数网格搜索

    对每组参数运行回测，收集结果并找出收益率最高和Sharpe比率最高的参数组合

    Args:
        df: 日线数据 DataFrame
        strategy_cls: 策略类
        param_grid: 参数网格，如 {"fast": [5, 10, 15], "slow": [20, 30]}
        initial_cash: 初始资金
        **kwargs: 传递给 run_backtest 的其他参数

    Returns:
        ParamSearchResult 参数搜索结果
    """
    combinations = generate_param_combinations(param_grid)
    total = len(combinations)
    results: list[dict[str, Any]] = []

    for i, params in enumerate(combinations):
        try:
            bt_result = run_backtest(
                df=df,
                strategy_cls=strategy_cls,
                strategy_params=params,
                initial_cash=initial_cash,
                **kwargs,
            )
            if "error" not in bt_result.metrics:
                result_item = {
                    "params": params,
                    "metrics": {
                        "total_return": bt_result.metrics.get("total_return", 0),
                        "annual_return": bt_result.metrics.get("annual_return", 0),
                        "sharpe": bt_result.metrics.get("sharpe", None),
                        "max_drawdown": bt_result.metrics.get("max_drawdown", 0),
                        "total_trades": bt_result.metrics.get("total_trades", 0),
                        "win_rate": bt_result.metrics.get("win_rate", 0),
                    },
                }
                results.append(result_item)
            else:
                results.append({"params": params, "error": bt_result.metrics.get("error", "unknown")})
        except Exception as e:
            results.append({"params": params, "error": str(e)})

        if (i + 1) % 50 == 0:
            logger.info(f"参数搜索进度: {i+1}/{total}")

    # 找出最佳参数（按收益率）
    valid_results = [r for r in results if "metrics" in r]
    best_by_return = None
    best_by_sharpe = None

    if valid_results:
        # 按总收益率排序
        sorted_by_return = sorted(valid_results, key=lambda x: x["metrics"].get("total_return", float("-inf")), reverse=True)
        best_by_return = sorted_by_return[0]

        # 按Sharpe排序（过滤掉 None/NaN）
        sharpe_valid = [r for r in valid_results if r["metrics"].get("sharpe") is not None and pd.notna(r["metrics"].get("sharpe"))]
        if sharpe_valid:
            sorted_by_sharpe = sorted(sharpe_valid, key=lambda x: x["metrics"].get("sharpe", float("-inf")), reverse=True)
            best_by_sharpe = sorted_by_sharpe[0]

    return ParamSearchResult(
        total_combinations=total,
        results=results,
        best_by_return=best_by_return,
        best_by_sharpe=best_by_sharpe,
    )
