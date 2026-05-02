from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import pandas as pd


def analyze_costs(trades_df: pd.DataFrame) -> dict[str, Any]:
    if trades_df is None or trades_df.empty:
        return {"commission": 0.0, "stamp_tax": 0.0, "transfer_fee": 0.0, "total": 0.0}

    commission = float(trades_df["佣金"].sum()) if "佣金" in trades_df.columns else 0.0
    stamp_tax = float(trades_df["印花税"].sum()) if "印花税" in trades_df.columns else 0.0
    transfer_fee = float(trades_df["过户费"].sum()) if "过户费" in trades_df.columns else 0.0
    total = commission + stamp_tax + transfer_fee
    return {"commission": commission, "stamp_tax": stamp_tax, "transfer_fee": transfer_fee, "total": total}


def analyze_by_stock(trades_df: pd.DataFrame) -> list[dict[str, Any]]:
    if trades_df is None or trades_df.empty:
        return []

    rows: list[dict[str, Any]] = []
    for code in sorted(trades_df["标准代码"].dropna().unique().tolist()):
        x = trades_df[trades_df["标准代码"] == code].copy()
        name = str(x["证券名称"].iloc[0]) if "证券名称" in x.columns and len(x) else ""

        buys = x[x.get("买卖方向") == "买入"] if "买卖方向" in x.columns else x.iloc[0:0]
        sells = x[x.get("买卖方向") == "卖出"] if "买卖方向" in x.columns else x.iloc[0:0]

        buy_amount = float(buys["成交金额"].sum()) if "成交金额" in buys.columns else 0.0
        sell_amount = float(sells["成交金额"].sum()) if "成交金额" in sells.columns else 0.0
        buy_volume = float(buys["成交数量"].sum()) if "成交数量" in buys.columns else 0.0
        sell_volume = float(sells["成交数量"].sum()) if "成交数量" in sells.columns else 0.0

        commission = float(x["佣金"].sum()) if "佣金" in x.columns else 0.0
        stamp_tax = float(x["印花税"].sum()) if "印花税" in x.columns else 0.0
        transfer_fee = float(x["过户费"].sum()) if "过户费" in x.columns else 0.0
        total_cost = commission + stamp_tax + transfer_fee

        remaining = float(buy_volume - sell_volume)
        realized_pnl = None if remaining > 0 else float(sell_amount - buy_amount - total_cost)

        rows.append(
            {
                "stock_code": code,
                "name": name,
                "buy_amount": buy_amount,
                "sell_amount": sell_amount,
                "total_cost": total_cost,
                "remaining": remaining,
                "realized_pnl": realized_pnl,
            }
        )

    rows.sort(key=lambda r: float(r.get("buy_amount") or 0.0), reverse=True)
    return rows


def build_portfolio_nav_from_trades(
    trades_df: pd.DataFrame,
    close_map: dict[str, pd.Series],
    initial_cash: float,
) -> pd.Series:
    if trades_df is None or trades_df.empty:
        raise ValueError("empty_trades")
    if not close_map:
        raise ValueError("empty_close_map")

    df = trades_df.copy()
    if "成交日期" not in df.columns:
        raise ValueError("missing_trade_date")
    df["成交日期"] = pd.to_datetime(df["成交日期"], errors="coerce")
    df = df.dropna(subset=["成交日期"])
    if df.empty:
        raise ValueError("invalid_trade_date")

    for c in ["成交金额", "成交数量", "佣金", "印花税", "过户费", "结算费"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    trades_by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for _, row in df.iterrows():
        d = pd.to_datetime(row["成交日期"]).date()
        trades_by_day[d].append(row.to_dict())

    all_dates: set[pd.Timestamp] = set()
    for s in close_map.values():
        all_dates.update(pd.to_datetime(s.index).to_list())
    for d in trades_by_day.keys():
        all_dates.add(pd.Timestamp(d))
    dates = sorted(all_dates)
    if not dates:
        raise ValueError("no_dates")

    cash = float(initial_cash)
    holdings: dict[str, float] = defaultdict(float)
    nav_rows: list[dict[str, Any]] = []

    for ts in dates:
        d = pd.to_datetime(ts).date()
        for t in trades_by_day.get(d, []):
            code = str(t.get("标准代码") or "").strip()
            if not code:
                continue
            side = str(t.get("买卖方向") or "").strip()
            qty = float(t.get("成交数量") or 0.0)
            amt = float(t.get("成交金额") or 0.0)
            cost = float(t.get("佣金") or 0.0) + float(t.get("印花税") or 0.0) + float(t.get("过户费") or 0.0) + float(
                t.get("结算费") or 0.0
            )
            if side == "买入":
                cash -= amt + cost
                holdings[code] += qty
            elif side == "卖出":
                cash += amt - cost
                holdings[code] -= qty

        total_value = cash
        for code, pos in holdings.items():
            if abs(float(pos)) <= 0:
                continue
            s = close_map.get(code)
            if s is None:
                raise ValueError(f"missing_close:{code}")
            if ts not in pd.to_datetime(s.index):
                raise ValueError(f"missing_close:{code}:{d.isoformat()}")
            px = float(pd.to_numeric(s.loc[ts], errors="coerce"))
            total_value += float(pos) * px

        nav_rows.append({"date": d.isoformat(), "nav": float(total_value) / float(initial_cash)})

    out = pd.DataFrame(nav_rows)
    out["date"] = pd.to_datetime(out["date"])
    out = out.set_index("date").sort_index()
    return out["nav"].astype(float)

