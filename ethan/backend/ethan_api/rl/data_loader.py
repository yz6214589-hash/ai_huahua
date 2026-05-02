from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .db import execute_query


def load_stock_data(stock_code: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    conditions = ["stock_code = %s"]
    params: list[Any] = [stock_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    sql = f"""
        SELECT trade_date, open_price, high_price, low_price, close_price, volume
        FROM trade_stock_daily
        WHERE {' AND '.join(conditions)}
        ORDER BY trade_date ASC
    """
    rows = execute_query(sql, params)
    if not rows:
        raise ValueError(f"no data for {stock_code}")

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df.set_index("trade_date", inplace=True)
    df.columns = ["open", "high", "low", "close", "volume"]
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def generate_intraday_data(daily_row: Any, num_steps: int = 48, seed: int | None = None) -> dict[str, Any]:
    if seed is not None:
        np.random.seed(seed)

    o, h, l, c = float(daily_row["open"]), float(daily_row["high"]), float(daily_row["low"]), float(daily_row["close"])
    total_vol = float(daily_row["volume"])

    drift = (c / o) ** (1.0 / float(num_steps)) - 1.0
    vol = (h - l) / o / np.sqrt(float(num_steps)) * 0.5

    prices = [o]
    for _ in range(num_steps):
        shock = np.random.normal(0, 1)
        new_price = prices[-1] * (1.0 + drift + vol * shock)
        new_price = float(np.clip(new_price, l * 0.999, h * 1.001))
        prices.append(new_price)
    prices[-1] = c
    prices_arr = np.array(prices, dtype=float)

    x = np.linspace(0, 1, num_steps)
    vol_weights = 1.5 * (x - 0.5) ** 2 + 0.3
    vol_weights = vol_weights / float(vol_weights.sum())
    volumes = total_vol * vol_weights

    vwap = float(np.sum(prices_arr[1:] * volumes) / np.sum(volumes))

    return {"prices": prices_arr, "volumes": volumes, "vwap": vwap}

