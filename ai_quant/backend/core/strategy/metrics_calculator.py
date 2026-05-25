# -*- coding: utf-8 -*-
"""
回测指标计算模块
提供丰富的回测分析指标，包括波动率、Sortino/Calmar比率、Alpha/Beta、
信息比率、盈亏比、连续盈亏、月度收益、回撤序列等
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


# 交易日数（用于年化）
_TRADING_DAYS_PER_YEAR = 252


def calc_volatility(returns: pd.Series) -> float:
    """
    计算年化波动率

    Args:
        returns: 日收益率序列

    Returns:
        年化波动率
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    return float(returns.std(ddof=1) * math.sqrt(_TRADING_DAYS_PER_YEAR))


def calc_downside_volatility(returns: pd.Series, risk_free: float = 0.03) -> float:
    """
    计算下行波动率
    仅考虑低于无风险利率的日收益率

    Args:
        returns: 日收益率序列
        risk_free: 年化无风险利率，默认0.03

    Returns:
        年化下行波动率
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    daily_rf = risk_free / _TRADING_DAYS_PER_YEAR
    downside = returns[returns < daily_rf] - daily_rf
    if downside.empty:
        return 0.0
    return float(downside.std(ddof=1) * math.sqrt(_TRADING_DAYS_PER_YEAR))


def calc_sortino(returns: pd.Series, risk_free: float = 0.03) -> float:
    """
    计算Sortino比率
    使用下行波动率代替总波动率来衡量风险

    Args:
        returns: 日收益率序列
        risk_free: 年化无风险利率，默认0.03

    Returns:
        Sortino比率
    """
    if returns.empty:
        return 0.0
    annual_return = float(returns.mean() * _TRADING_DAYS_PER_YEAR)
    downside_vol = calc_downside_volatility(returns, risk_free)
    if downside_vol == 0:
        return 0.0
    return (annual_return - risk_free) / downside_vol


def calc_calmar(annual_return: float, max_drawdown: float) -> float:
    """
    计算Calmar比率
    年化收益与最大回撤之比

    Args:
        annual_return: 年化收益率
        max_drawdown: 最大回撤（正数）

    Returns:
        Calmar比率
    """
    if max_drawdown == 0:
        return 0.0
    return annual_return / max_drawdown


def calc_alpha_beta(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free: float = 0.03,
) -> tuple[float, float]:
    """
    通过CAPM回归计算Alpha和Beta

    Args:
        strategy_returns: 策略日收益率序列
        benchmark_returns: 基准日收益率序列
        risk_free: 年化无风险利率，默认0.03

    Returns:
        (alpha, beta) 元组
    """
    if strategy_returns.empty or benchmark_returns.empty:
        return (0.0, 1.0)
    # 对齐索引
    common_idx = strategy_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < 2:
        return (0.0, 1.0)
    sr = strategy_returns.loc[common_idx].values
    br = benchmark_returns.loc[common_idx].values
    daily_rf = risk_free / _TRADING_DAYS_PER_YEAR
    # 超额收益
    excess_s = sr - daily_rf
    excess_b = br - daily_rf
    # 线性回归: excess_s = alpha + beta * excess_b
    try:
        beta_val = float(np.cov(excess_s, excess_b)[0, 1] / np.var(excess_b, ddof=1))
        alpha_val = float(np.mean(excess_s) - beta_val * np.mean(excess_b))
        # 年化alpha
        alpha_val = alpha_val * _TRADING_DAYS_PER_YEAR
    except Exception:
        return (0.0, 1.0)
    return (alpha_val, beta_val)


def calc_tracking_error(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    计算跟踪误差
    策略收益与基准收益之差的年化标准差

    Args:
        strategy_returns: 策略日收益率序列
        benchmark_returns: 基准日收益率序列

    Returns:
        年化跟踪误差
    """
    if strategy_returns.empty or benchmark_returns.empty:
        return 0.0
    common_idx = strategy_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < 2:
        return 0.0
    diff = strategy_returns.loc[common_idx] - benchmark_returns.loc[common_idx]
    return float(diff.std(ddof=1) * math.sqrt(_TRADING_DAYS_PER_YEAR))


def calc_information_ratio(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    计算信息比率
    超额收益与跟踪误差之比

    Args:
        strategy_returns: 策略日收益率序列
        benchmark_returns: 基准日收益率序列

    Returns:
        信息比率
    """
    if strategy_returns.empty or benchmark_returns.empty:
        return 0.0
    common_idx = strategy_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < 2:
        return 0.0
    diff = strategy_returns.loc[common_idx] - benchmark_returns.loc[common_idx]
    annual_excess = float(diff.mean() * _TRADING_DAYS_PER_YEAR)
    tracking_err = calc_tracking_error(strategy_returns, benchmark_returns)
    if tracking_err == 0:
        return 0.0
    return annual_excess / tracking_err


def calc_profit_factor(won_pnl: float, lost_pnl: float) -> float:
    """
    计算盈亏比（Profit Factor）
    总盈利 / 总亏损的绝对值

    Args:
        won_pnl: 盈利金额总和
        lost_pnl: 亏损金额总和（负数）

    Returns:
        盈亏比
    """
    abs_lost = abs(lost_pnl)
    if abs_lost == 0:
        return float("inf") if won_pnl > 0 else 0.0
    return won_pnl / abs_lost


def calc_max_consecutive(pnl_list: list[float]) -> tuple[int, int]:
    """
    计算最大连续盈利/亏损次数

    Args:
        pnl_list: 每笔交易盈亏列表

    Returns:
        (最大连续盈利次数, 最大连续亏损次数)
    """
    if not pnl_list:
        return (0, 0)
    max_win = 0
    max_loss = 0
    cur_win = 0
    cur_loss = 0
    for pnl in pnl_list:
        if pnl > 0:
            cur_win += 1
            cur_loss = 0
            max_win = max(max_win, cur_win)
        elif pnl < 0:
            cur_loss += 1
            cur_win = 0
            max_loss = max(max_loss, cur_loss)
        else:
            cur_win = 0
            cur_loss = 0
    return (max_win, max_loss)


def calc_monthly_returns(nav_log: list[dict]) -> list[dict]:
    """
    计算月度收益率

    Args:
        nav_log: 净值日志 [{"date": "2023-01-03", "nav": 100000}, ...]

    Returns:
        月度收益率列表 [{"month": "2023-01", "return": 0.05}, ...]
    """
    if not nav_log or len(nav_log) < 2:
        return []
    # 按日期排序
    sorted_log = sorted(nav_log, key=lambda x: x.get("date", ""))
    df = pd.DataFrame(sorted_log)
    if "date" not in df.columns or "nav" not in df.columns:
        return []
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    # 每月最后一个交易日的净值
    monthly_last = df.groupby("month")["nav"].last()
    # 每月第一个交易日的净值（上月末净值作为基准）
    months = monthly_last.index.tolist()
    result = []
    for i, month in enumerate(months):
        end_nav = float(monthly_last.iloc[i])
        if i == 0:
            # 第一个月用该月第一个交易日的净值作为起始
            first_nav = float(df[df["month"] == month]["nav"].iloc[0])
        else:
            prev_month = months[i - 1]
            first_nav = float(monthly_last.iloc[i - 1])
        if first_nav > 0:
            ret = (end_nav / first_nav) - 1.0
        else:
            ret = 0.0
        result.append({"month": month, "return": round(float(ret), 6)})
    return result


def calc_drawdown_log(nav_log: list[dict]) -> list[dict]:
    """
    计算回撤序列

    Args:
        nav_log: 净值日志 [{"date": "2023-01-03", "nav": 100000}, ...]

    Returns:
        回撤序列 [{"date": "2023-01-03", "nav": 100000, "peak": 100000, "drawdown": 0.0}, ...]
    """
    if not nav_log:
        return []
    result = []
    peak = 0.0
    for row in nav_log:
        nav = float(row.get("nav", 0))
        date = row.get("date", "")
        peak = max(peak, nav)
        dd = (nav - peak) / peak if peak > 0 else 0.0
        result.append({
            "date": date,
            "nav": nav,
            "peak": round(peak, 2),
            "drawdown": round(float(dd), 6),
        })
    return result


def enhance_metrics(
    base_metrics: dict,
    nav_log: list[dict],
    benchmark_nav_log: list[dict] | None = None,
) -> dict:
    """
    综合增强指标计算
    在基础指标上增加波动率、Sortino、Calmar、Alpha/Beta、信息比率、
    盈亏比、连续盈亏、月度收益、回撤序列等

    Args:
        base_metrics: 基础指标字典（来自 backtest_engine）
        nav_log: 策略净值日志
        benchmark_nav_log: 基准净值日志（可选）

    Returns:
        增强后的指标字典
    """
    enhanced = dict(base_metrics)

    # 从净值日志计算日收益率
    if nav_log and len(nav_log) >= 2:
        sorted_log = sorted(nav_log, key=lambda x: x.get("date", ""))
        navs = [float(r.get("nav", 0)) for r in sorted_log]
        returns = pd.Series(navs).pct_change().dropna()
        if len(returns) >= 2:
            # 重置索引以便后续对齐
            returns = returns.reset_index(drop=True)
            enhanced["volatility"] = round(calc_volatility(returns), 6)
            enhanced["sortino"] = round(calc_sortino(returns), 6)
            annual_return = base_metrics.get("annual_return", 0.0)
            max_dd = base_metrics.get("max_drawdown", 0.0)
            if max_dd == 0:
                enhanced["calmar"] = 0.0
            else:
                enhanced["calmar"] = round(calc_calmar(annual_return, max_dd), 6)

            # 基准相关指标
            if benchmark_nav_log and len(benchmark_nav_log) >= 2:
                sorted_bench = sorted(benchmark_nav_log, key=lambda x: x.get("date", ""))
                bench_navs = [float(r.get("nav", 0)) for r in sorted_bench]
                bench_returns = pd.Series(bench_navs).pct_change().dropna().reset_index(drop=True)
                # 对齐长度
                min_len = min(len(returns), len(bench_returns))
                if min_len >= 2:
                    sr = returns.iloc[:min_len]
                    br = bench_returns.iloc[:min_len]
                    sr.index = br.index  # 统一索引以便对齐
                    alpha, beta = calc_alpha_beta(sr, br)
                    enhanced["alpha"] = round(alpha, 6)
                    enhanced["beta"] = round(beta, 6)
                    enhanced["tracking_error"] = round(calc_tracking_error(sr, br), 6)
                    enhanced["information_ratio"] = round(calc_information_ratio(sr, br), 6)

    # 盈亏比和连续盈亏
    trades_pnl = base_metrics.get("_trades_pnl", [])
    if trades_pnl:
        won_pnl = sum(p for p in trades_pnl if p > 0)
        lost_pnl = sum(p for p in trades_pnl if p < 0)
        enhanced["profit_factor"] = round(calc_profit_factor(won_pnl, lost_pnl), 6)
        max_win, max_loss = calc_max_consecutive(trades_pnl)
        enhanced["max_consecutive_wins"] = max_win
        enhanced["max_consecutive_losses"] = max_loss
    else:
        # 从基础指标中的 won/lost 和 trades 推算
        won = base_metrics.get("won", 0)
        lost = base_metrics.get("lost", 0)
        if won + lost > 0:
            enhanced["profit_factor"] = None  # 缺少具体金额，无法计算
        enhanced["max_consecutive_wins"] = None
        enhanced["max_consecutive_losses"] = None

    # 月度收益
    enhanced["monthly_returns"] = calc_monthly_returns(nav_log)

    # 回撤序列
    enhanced["drawdown_log"] = calc_drawdown_log(nav_log)

    return enhanced
