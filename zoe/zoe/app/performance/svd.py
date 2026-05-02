from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def diagnose_market_regime(returns_df: pd.DataFrame, window: int = 120, step: int = 20) -> dict[str, Any]:
    if returns_df is None or returns_df.empty:
        raise ValueError("returns_df is required")

    df = returns_df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="any")
    if df.shape[1] < 3:
        raise ValueError("need_at_least_3_assets")

    t = int(df.shape[0])
    if t < window + step:
        raise ValueError("insufficient_days")

    out_rows: list[dict[str, Any]] = []
    for start in range(0, t - window, step):
        end = start + window
        w = df.iloc[start:end]
        r = w.to_numpy().T
        r = r - r.mean(axis=1, keepdims=True)
        _, sigma, _ = np.linalg.svd(r, full_matrices=False)
        total = float(np.sum(sigma**2))
        if total <= 0:
            continue
        top1 = float((sigma[0] ** 2) / total)
        top3 = float(np.sum(sigma[: min(3, len(sigma))] ** 2) / total)
        mid = w.index[window // 2]
        out_rows.append({"date": pd.to_datetime(mid), "top1_var": top1, "top3_var": top3})

    if not out_rows:
        raise ValueError("svd_failed")

    roll_df = pd.DataFrame(out_rows).set_index("date").sort_index()
    recent = roll_df["top1_var"].iloc[-min(3, len(roll_df)) :].mean()

    if float(recent) > 0.50:
        state = "齐涨齐跌"
        advice = (
            "当前市场齐涨齐跌特征明显，beta 因子主导。\n"
            "建议：指数增强更有效，个股选择的 alpha 空间有限。\n"
            "可考虑：增大仓位跟随大盘趋势，减少个股博弈。"
        )
    elif float(recent) > 0.35:
        state = "板块分化"
        advice = (
            "当前市场处于板块分化阶段，行业轮动特征显著。\n"
            "建议：行业配置是关键，选对板块比选对个股更重要。\n"
            "可考虑：关注行业动量因子，超配强势板块。"
        )
    else:
        state = "个股行情"
        advice = (
            "当前市场个股分化明显，alpha 机会更丰富。\n"
            "建议：选股策略更有效，多因子模型价值更高。\n"
            "可考虑：精选个股，降低对大盘方向的依赖。"
        )

    return {
        "rolling": {
            "dates": [d.date().isoformat() for d in roll_df.index.to_pydatetime()],
            "top1_var": [float(x) for x in roll_df["top1_var"].to_numpy()],
            "top3_var": [float(x) for x in roll_df["top3_var"].to_numpy()],
        },
        "current_state": state,
        "current_f1_ratio": float(recent),
        "advice": advice,
        "stock_count": int(df.shape[1]),
        "data_days": int(df.shape[0]),
    }

