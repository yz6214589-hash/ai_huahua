"""
个股详情 API 模块
提供个股的行情快照、基本面数据、技术指标、新闻研报等数据查询
技术指标（MA/MACD/RSI/BOLL/KDJ/ATR/量均线）全部采用服务端实时计算
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from core.db import connect, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("stock_detail")

router = APIRouter(prefix="/api/v1", tags=["stock_detail"])


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _get_conn_qd() -> tuple[Any, Any]:
    try:
        cfg = load_mysql_config()
        return connect(cfg), query_dict
    except Exception:
        return None, None


def _norm(code: str) -> str:
    c = str(code or "").strip().upper()
    if "." not in c:
        if c.startswith("6"):
            c += ".SH"
        elif c.startswith(("0", "3")):
            c += ".SZ"
    return c


def _fmt_date(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, str):
        return str(v)[:10]
    return str(v)


def _fmt_dt(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%dT%H:%M:%S")
    return str(v)


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
        return f if float("inf") > f > float("-inf") else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 技术指标计算函数（服务端实时计算）
# ---------------------------------------------------------------------------

def _calc_sma(values: list[float | None], period: int) -> list[float | None]:
    """简单移动平均线。前 period-1 个值为 None"""
    n = len(values)
    result: list[float | None] = [None] * n
    if n < period:
        return result
    for i in range(period - 1, n):
        window = values[i - period + 1:i + 1]
        if all(v is not None for v in window):
            result[i] = round(sum(window) / period, 4)  # type: ignore[arg-type]
    return result


def _calc_ema(values: list[float | None], period: int) -> list[float | None]:
    """指数移动平均线。前 period-1 个值为 None，之后用 EMA = alpha*price + (1-alpha)*prev_ema"""
    n = len(values)
    result: list[float | None] = [None] * n
    if n < period:
        return result
    # 找到第一个有效 SMA 作为 EMA 起始值
    first_idx: int | None = None
    first_sma: float | None = None
    for i in range(period - 1, n):
        window = values[i - period + 1:i + 1]
        if all(v is not None for v in window):
            first_sma = sum(window) / period  # type: ignore[arg-type]
            result[i] = round(first_sma, 4)
            first_idx = i
            break
    if first_idx is None:
        return result
    alpha = 2.0 / (period + 1.0)
    prev_ema = first_sma
    for i in range(first_idx + 1, n):
        v = values[i]
        if v is not None:
            prev_ema = alpha * v + (1.0 - alpha) * prev_ema
            result[i] = round(prev_ema, 4)
    return result


def _calc_rsi(closes: list[float | None], period: int = 14) -> list[float | None]:
    """RSI 计算 - 使用 Wilder 平滑方法。
    前 period 个值为 None，之后用 avg_gain/avg_loss 的 Wilder 平滑计算"""
    n = len(closes)
    result: list[float | None] = [None] * n
    if n < period + 1:
        return result

    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        c = closes[i]
        p = closes[i - 1]
        if c is not None and p is not None:
            d = c - p
            if d > 0:
                gains[i] = d
                losses[i] = 0.0
            elif d < 0:
                gains[i] = 0.0
                losses[i] = -d
            else:
                gains[i] = 0.0
                losses[i] = 0.0
        else:
            gains[i] = 0.0
            losses[i] = 0.0

    # 初始平均增益/亏损：第一个 period 天涨跌的简单平均
    avg_gain = sum(gains[1:period + 1]) / period
    avg_loss = sum(losses[1:period + 1]) / period

    for i in range(period, n):
        if i > period:
            # Wilder 平滑：avg = (avg * (period-1) + current) / period
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rs = float("inf")
        else:
            rs = avg_gain / avg_loss
        if rs == float("inf"):
            result[i] = 100.0
        else:
            result[i] = round(100.0 - 100.0 / (1.0 + rs), 4)
    return result


def _calc_macd(closes: list[float | None], short: int = 12, long: int = 26, signal: int = 9) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """计算 MACD 指标。
    返回 (dif_list, dea_list, hist_list) 三个列表
    dif = EMA(short) - EMA(long)
    dea = EMA(dif, signal)
    hist = 2 * (dif - dea)"""
    n = len(closes)
    ema_short = _calc_ema(closes, short)
    ema_long = _calc_ema(closes, long)

    dif: list[float | None] = [None] * n
    for i in range(n):
        if ema_short[i] is not None and ema_long[i] is not None:
            dif[i] = round(ema_short[i] - ema_long[i], 4)  # type: ignore[operator]

    dea = _calc_ema(dif, signal)

    hist: list[float | None] = [None] * n
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            hist[i] = round(2.0 * (dif[i] - dea[i]), 4)  # type: ignore[operator]

    return dif, dea, hist


def _calc_boll(closes: list[float | None], period: int = 20, std_mult: float = 2.0) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """计算布林带指标。
    返回 (upper_list, mid_list, lower_list)
    mid = SMA(close, period)
    upper = mid + std_mult * rolling_std
    lower = mid - std_mult * rolling_std"""
    n = len(closes)
    upper: list[float | None] = [None] * n
    mid: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n

    if n < period:
        return upper, mid, lower

    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        if all(v is not None for v in window):
            m = sum(window) / period  # type: ignore[arg-type]
            variance = sum((x - m) ** 2 for x in window) / period  # type: ignore[operator]
            std = math.sqrt(variance)
            mid[i] = round(m, 4)
            upper[i] = round(m + std_mult * std, 4)
            lower[i] = round(m - std_mult * std, 4)

    return upper, mid, lower


def _calc_kdj(highs: list[float | None], lows: list[float | None], closes: list[float | None],
              n: int = 9, m1: int = 3, m2: int = 3) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """计算 KDJ 指标。
    返回 (k_list, d_list, j_list)
    RSV = (close - low_n) / (high_n - low_n) * 100
    K = SMA(RSV, m1)
    D = SMA(K, m2)
    J = 3*K - 2*D"""
    length = len(closes)

    # 计算 RSV（要求窗口内所有 high/low 都非 None，否则无法正确反映价格范围）
    rsv: list[float | None] = [None] * length
    for i in range(n - 1, length):
        window_highs = highs[i - n + 1:i + 1]
        window_lows = lows[i - n + 1:i + 1]
        # 窗口内所有 high/low 必须非 None，close 也必须非 None
        if (all(h is not None for h in window_highs) and
            all(l is not None for l in window_lows) and
            closes[i] is not None):
            hh = max(window_highs)  # type: ignore[arg-type]
            ll = min(window_lows)  # type: ignore[arg-type]
            if hh != ll:
                rsv[i] = (closes[i] - ll) / (hh - ll) * 100.0  # type: ignore[operator]
            else:
                rsv[i] = 50.0  # 最高最低价相等时取中间值

    # K = SMA(RSV, m1)
    k_temp = _calc_sma(rsv, m1)
    # D = SMA(K, m2)
    d_temp = _calc_sma(k_temp, m2)

    k_list: list[float | None] = [None] * length
    d_list: list[float | None] = [None] * length
    j_list: list[float | None] = [None] * length

    for i in range(length):
        if k_temp[i] is not None:
            k_list[i] = round(k_temp[i], 4)
        if d_temp[i] is not None:
            d_list[i] = round(d_temp[i], 4)
        if k_list[i] is not None and d_list[i] is not None:
            j_list[i] = round(3.0 * k_list[i] - 2.0 * d_list[i], 4)  # type: ignore[operator]

    return k_list, d_list, j_list


def _compute_all_indicators(
    rows: list[dict[str, Any]],
    ma_period: int = 20,
    rsi_period: int = 14,
    macd_short: int = 12,
    macd_long: int = 26,
    macd_signal: int = 9,
    boll_period: int = 20,
    kdj_n: int = 9,
    kdj_m1: int = 3,
    kdj_m2: int = 3,
    atr_period: int = 14,
) -> list[dict[str, Any]]:
    """批量计算所有技术指标。
    传入原始 OHLCV 数据行列表，返回每一行对应的技术指标字典列表。
    长度与输入 rows 一致，索引一一对应。"""
    n = len(rows)
    if n == 0:
        return []

    # 提取 OHLCV 列表
    closes: list[float | None] = [_safe_float(r.get("close_price")) for r in rows]
    highs: list[float | None] = [_safe_float(r.get("high_price")) for r in rows]
    lows: list[float | None] = [_safe_float(r.get("low_price")) for r in rows]
    volumes: list[float | None] = [_safe_float(r.get("volume")) for r in rows]

    # ---- 均线 ----
    ma5 = _calc_sma(closes, 5)
    ma10 = _calc_sma(closes, 10)
    ma20 = _calc_sma(closes, 20)
    ma60 = _calc_sma(closes, 60)
    ma_custom = _calc_sma(closes, ma_period)

    # 成交量均线
    vol_ma5 = _calc_sma(volumes, 5)
    vol_ma20 = _calc_sma(volumes, 20)

    # ---- RSI ----
    rsi14 = _calc_rsi(closes, 14)
    rsi_custom = _calc_rsi(closes, rsi_period)

    # ---- MACD（标准参数 + 自定义参数）----
    dif_std, dea_std, hist_std = _calc_macd(closes, 12, 26, 9)
    dif_custom, dea_custom, hist_custom = _calc_macd(closes, macd_short, macd_long, macd_signal)

    # ---- 布林带 ----
    boll_upper, boll_mid, boll_lower = _calc_boll(closes, boll_period)

    # ---- KDJ ----
    kdj_k, kdj_d, kdj_j = _calc_kdj(highs, lows, closes, kdj_n, kdj_m1, kdj_m2)

    # ---- ATR ----
    atr: list[float | None] = [None] * n
    for i in range(atr_period - 1, n):
        tr_values: list[float] = []
        for j in range(i - atr_period + 1, i + 1):
            h = highs[j]
            lo = lows[j]
            c = closes[j]
            # 如果当前行 high/low 有一个为 None，尝试用 close 差值作为近似 TR
            if h is None or lo is None:
                if j > 0 and c is not None:
                    pc = closes[j - 1]
                    if pc is not None:
                        tr_values.append(abs(c - pc))
                continue
            if j > 0:
                pc = closes[j - 1]
                if pc is None:
                    tr = h - lo
                else:
                    tr = max(h - lo, abs(h - pc), abs(lo - pc))
            else:
                tr = h - lo
            tr_values.append(tr)
        if len(tr_values) >= atr_period:
            atr[i] = round(sum(tr_values) / len(tr_values), 4)

    # ---- 组装每行结果 ----
    result: list[dict[str, Any]] = []
    for i in range(n):
        computed: dict[str, Any] = {
            "ma5": ma5[i],
            "ma10": ma10[i],
            "ma20": ma20[i],
            "ma60": ma60[i],
            "vol_ma5": vol_ma5[i],
            "vol_ma20": vol_ma20[i],
            "rsi14": rsi14[i],
            "macd_dif": dif_std[i],
            "macd_dea": dea_std[i],
            "macd_hist": hist_std[i],
            "boll_upper": boll_upper[i],
            "boll_mid": boll_mid[i],
            "boll_lower": boll_lower[i],
            "kdj_k": kdj_k[i],
            "kdj_d": kdj_d[i],
            "kdj_j": kdj_j[i],
            "atr14": None,
            "atr_custom": atr[i],
            "ma_custom": ma_custom[i],
            "macd_dif_custom": dif_custom[i],
            "macd_dea_custom": dea_custom[i],
            "macd_hist_custom": hist_custom[i],
            "rsi_custom": rsi_custom[i],
        }
        result.append(computed)
    return result


# ---------------------------------------------------------------------------
# 单行 ATR 计算（兼容旧逻辑，仅在 computed=None 时使用）
# ---------------------------------------------------------------------------

def _calc_atr(current_row: dict[str, Any], prev_rows: list[dict[str, Any]], period: int) -> float | None:
    if not prev_rows:
        return None
    all_rows = list(prev_rows) + [current_row]
    if len(all_rows) < 2:
        return None
    n = len(all_rows)
    start = max(0, n - period - 1)
    tr_values = []
    for i in range(start + 1, n):
        high = _safe_float(all_rows[i].get("high_price"))
        low = _safe_float(all_rows[i].get("low_price"))
        prev_close = _safe_float(all_rows[i - 1].get("close_price"))
        if high is None or low is None or prev_close is None:
            continue
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    if not tr_values:
        return None
    return round(sum(tr_values) / len(tr_values), 4)


# ---------------------------------------------------------------------------
# 技术指标行构建
# ---------------------------------------------------------------------------

def _calc_tech_row(
    row: dict[str, Any],
    computed: dict[str, Any] | None = None,
    atr_period: int = 14,
    prev_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构建单行技术指标数据。
    如果 computed 不为 None，从中读取所有预计算的指标值；
    如果 computed 为 None（兼容旧逻辑），从 DB row 读取并单独计算 ATR。"""
    close = _safe_float(row.get("close_price"))
    open_ = _safe_float(row.get("open_price"))
    high = _safe_float(row.get("high_price"))
    low = _safe_float(row.get("low_price"))
    vol = _safe_float(row.get("volume"))
    amount = _safe_float(row.get("amount"))

    if computed is not None:
        # 从预计算字典读取所有指标
        return {
            "trade_date": _fmt_date(row.get("trade_date")),
            "open_price": open_,
            "high_price": high,
            "low_price": low,
            "close_price": close,
            "volume": vol,
            "amount": amount,
            "ma5": computed.get("ma5"),
            "ma10": computed.get("ma10"),
            "ma20": computed.get("ma20"),
            "ma60": computed.get("ma60"),
            "vol_ma5": computed.get("vol_ma5"),
            "vol_ma20": computed.get("vol_ma20"),
            "rsi14": computed.get("rsi14"),
            "macd_dif": computed.get("macd_dif"),
            "macd_dea": computed.get("macd_dea"),
            "macd_hist": computed.get("macd_hist"),
            "boll_upper": computed.get("boll_upper"),
            "boll_mid": computed.get("boll_mid"),
            "boll_lower": computed.get("boll_lower"),
            "kdj_k": computed.get("kdj_k"),
            "kdj_d": computed.get("kdj_d"),
            "kdj_j": computed.get("kdj_j"),
            "atr14": None,
            "atr_custom": computed.get("atr_custom"),
            "ma_custom": computed.get("ma_custom"),
            "macd_dif_custom": computed.get("macd_dif_custom"),
            "macd_dea_custom": computed.get("macd_dea_custom"),
            "macd_hist_custom": computed.get("macd_hist_custom"),
            "rsi_custom": computed.get("rsi_custom"),
        }
    else:
        # 兼容旧逻辑：从 DB row 读取（这些字段在 DB 中可能为 NULL）
        atr_val = _calc_atr(row, prev_rows, atr_period) if prev_rows else None
        return {
            "trade_date": _fmt_date(row.get("trade_date")),
            "open_price": open_,
            "high_price": high,
            "low_price": low,
            "close_price": close,
            "volume": vol,
            "amount": amount,
            "ma5": _safe_float(row.get("ma5")),
            "ma10": _safe_float(row.get("ma10")),
            "ma20": _safe_float(row.get("ma20")),
            "ma60": _safe_float(row.get("ma60")),
            "vol_ma5": _safe_float(row.get("vol_ma5")),
            "vol_ma20": _safe_float(row.get("vol_ma20")),
            "rsi14": _safe_float(row.get("rsi14")),
            "macd_dif": _safe_float(row.get("macd_dif")),
            "macd_dea": _safe_float(row.get("macd_dea")),
            "macd_hist": _safe_float(row.get("macd_hist")),
            "boll_upper": _safe_float(row.get("boll_upper")),
            "boll_mid": _safe_float(row.get("boll_mid")),
            "boll_lower": _safe_float(row.get("boll_lower")),
            "kdj_k": _safe_float(row.get("kdj_k")),
            "kdj_d": _safe_float(row.get("kdj_d")),
            "kdj_j": _safe_float(row.get("kdj_j")),
            "atr14": None,
            "atr_custom": atr_val,
            "ma_custom": _safe_float(row.get("ma20")),
            "macd_dif_custom": _safe_float(row.get("macd_dif")),
            "macd_dea_custom": _safe_float(row.get("macd_dea")),
            "macd_hist_custom": _safe_float(row.get("macd_hist")),
            "rsi_custom": _safe_float(row.get("rsi14")),
        }


def _calc_tech_latest(
    computed: dict[str, Any],
    ma_period: int = 20,
) -> dict[str, Any] | None:
    """构建最新技术指标数据。
    从预计算的 computed 字典中读取所有指标值。"""
    if computed is None:
        return None
    return {
        "ma5": computed.get("ma5"),
        "ma10": computed.get("ma10"),
        "ma20": computed.get("ma20"),
        "ma60": computed.get("ma60"),
        "vol_ma5": computed.get("vol_ma5"),
        "vol_ma20": computed.get("vol_ma20"),
        "rsi14": computed.get("rsi14"),
        "macd_dif": computed.get("macd_dif"),
        "macd_dea": computed.get("macd_dea"),
        "macd_hist": computed.get("macd_hist"),
        "boll_upper": computed.get("boll_upper"),
        "boll_mid": computed.get("boll_mid"),
        "boll_lower": computed.get("boll_lower"),
        "kdj_k": computed.get("kdj_k"),
        "kdj_d": computed.get("kdj_d"),
        "kdj_j": computed.get("kdj_j"),
        "atr14": None,
        "atr_custom": computed.get("atr_custom"),
        "ma_custom": computed.get("ma_custom"),
        "macd_dif_custom": computed.get("macd_dif_custom"),
        "macd_dea_custom": computed.get("macd_dea_custom"),
        "macd_hist_custom": computed.get("macd_hist_custom"),
        "rsi_custom": computed.get("rsi_custom"),
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.get("/stock/{code}/snapshot")
def stock_snapshot(code: str) -> dict[str, Any]:
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        rows = qd(conn,
            """SELECT stock_code, stock_name, trade_date, close_price, volume, turnover_rate
               FROM trade_stock_daily WHERE stock_code=%s
               ORDER BY trade_date DESC LIMIT 2""",
            (c,))
        if not rows:
            raise HTTPException(status_code=404, detail="stock not found")
        latest = rows[0]
        prev_row = rows[1] if len(rows) > 1 else None
        close = _safe_float(latest.get("close_price"))
        prev = _safe_float(prev_row.get("close_price")) if prev_row else None
        change = round(float(close - prev), 4) if close is not None and prev is not None else None
        pct = round(float((close - prev) / prev * 100), 4) if close is not None and prev is not None and prev != 0 else None
        return {
            "stock_code": c,
            "stock_name": latest.get("stock_name"),
            "price": close,
            "change": change,
            "pctChange": pct,
            "asOf": _fmt_dt(latest.get("trade_date")),
            "source": "daily",
        }
    finally:
        conn.close()


@router.get("/stock/{code}/fundamentals")
def stock_fundamentals(code: str) -> dict[str, Any]:
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        fin_rows = qd(conn,
            """SELECT report_date, revenue, net_profit, eps, roe, roa, gross_margin,
                      net_margin, debt_ratio, current_ratio, operating_cashflow, total_assets, total_equity
               FROM trade_stock_financial
               WHERE stock_code=%s ORDER BY report_date DESC LIMIT 2""",
            (c,))
        items: list[dict[str, Any]] = []
        if fin_rows:
            latest = fin_rows[0]
            prev = fin_rows[1] if len(fin_rows) > 1 else None
            report_date = _fmt_date(latest.get("report_date"))

            def _fin(key: str, label: str, unit: str, tooltip: str = "") -> None:
                v = _safe_float(latest.get(key))
                if v is not None and unit == "亿":
                    v = round(v / 100000000, 4)
                pv = _safe_float(prev.get(key)) if prev else None
                if pv is not None and unit == "亿":
                    pv = round(pv / 100000000, 4)
                delta = round(float(v - pv), 4) if v is not None and pv is not None else None
                dir_ = "up" if delta is not None and delta > 0 else "down" if delta is not None and delta < 0 else None
                items.append({"key": key, "label": label, "unit": unit, "tooltip": tooltip,
                              "value": v, "delta": delta, "dir": dir_})

            _fin("revenue", "营业总收入", "亿", "当年营业总收入")
            _fin("net_profit", "净利润", "亿", "归母净利润")
            _fin("eps", "EPS", "元", "每股收益")
            _fin("roe", "ROE", "%", "净资产收益率")
            _fin("roa", "ROA", "%", "资产收益率")
            _fin("gross_margin", "毛利率", "%", "主营业务利润率")
            _fin("net_margin", "净利率", "%", "净利润率")
            _fin("debt_ratio", "资产负债率", "%", "总负债/总资产")
            _fin("total_assets", "总资产", "亿", "企业总资产规模")
            _fin("total_equity", "净资产", "亿", "归属母公司股东权益")
            _fin("current_ratio", "流动比率", "", "流动资产/流动负债")
            _fin("operating_cashflow", "经营现金流", "亿", "经营活动产生的现金流量净额")

            return {
                "stock_code": c,
                "stock_name": None,
                "reportDate": report_date,
                "items": items,
            }
        return {"stock_code": c, "stock_name": None, "reportDate": None, "items": []}
    finally:
        conn.close()


@router.get("/stock/{code}/technical/latest")
def stock_technical_latest(
    code: str,
    maPeriod: int = Query(default=20),
    macdShort: int = Query(default=12),
    macdLong: int = Query(default=26),
    macdSignal: int = Query(default=9),
    rsiPeriod: int = Query(default=14),
    atrPeriod: int = Query(default=14),
) -> dict[str, Any]:
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        # 获取足够多的历史数据用于指标计算（取 300 条保证稳定性）
        rows = qd(conn,
            """SELECT trade_date, open_price, high_price, low_price, close_price, volume, amount,
                      ma5, ma10, ma20, ma60, vol_ma5, vol_ma20,
                      rsi14, macd_dif, macd_dea, macd_hist,
                      boll_upper, boll_mid, boll_lower,
                      kdj_k, kdj_d, kdj_j
               FROM trade_stock_daily
               WHERE stock_code=%s
               ORDER BY trade_date DESC LIMIT 300""",
            (c,))
        if not rows:
            raise HTTPException(status_code=404, detail="no technical data")
        # 按日期升序排列（指标计算需要时间序列从旧到新）
        rows.reverse()

        # 批量计算所有技术指标
        computed_list = _compute_all_indicators(
            rows,
            ma_period=maPeriod,
            rsi_period=rsiPeriod,
            macd_short=macdShort,
            macd_long=macdLong,
            macd_signal=macdSignal,
            atr_period=atrPeriod,
        )
        latest_computed = computed_list[-1] if computed_list else None
        latest = _calc_tech_latest(latest_computed, maPeriod)
        return {"stock_code": c, "row": latest or {}}
    finally:
        conn.close()


@router.get("/stock/{code}/technical/series")
def stock_technical_series(
    code: str,
    start: str = Query(default=""),
    end: str = Query(default=""),
    atrPeriod: int = Query(default=14),
) -> dict[str, Any]:
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        today = date.today()
        d_start = datetime.strptime(start, "%Y-%m-%d").date() if start else today - timedelta(days=180)
        d_end = datetime.strptime(end, "%Y-%m-%d").date() if end else today

        # 获取目标时间范围内的主数据
        rows = qd(conn,
            """SELECT trade_date, open_price, high_price, low_price, close_price, volume, amount,
                      ma5, ma10, ma20, ma60, vol_ma5, vol_ma20,
                      rsi14, macd_dif, macd_dea, macd_hist,
                      boll_upper, boll_mid, boll_lower,
                      kdj_k, kdj_d, kdj_j
               FROM trade_stock_daily
               WHERE stock_code=%s AND trade_date BETWEEN %s AND %s
               ORDER BY trade_date ASC""",
            (c, d_start, d_end))

        # 获取前序数据用于指标计算（需要足够多的前序数据才能正确计算长周期指标）
        atr_extra_start = d_start - timedelta(days=atrPeriod * 2)
        prev_rows = qd(conn,
            """SELECT trade_date, open_price, high_price, low_price, close_price, volume
               FROM trade_stock_daily
               WHERE stock_code=%s AND trade_date BETWEEN %s AND %s
               ORDER BY trade_date ASC""",
            (c, atr_extra_start, d_start))

        # 合并前序数据与主数据，批量计算所有技术指标
        full_rows = list(prev_rows) + list(rows)
        computed_list = _compute_all_indicators(
            full_rows,
            atr_period=atrPeriod,
        )
        prev_len = len(prev_rows)

        result_rows = []
        for i, r in enumerate(rows):
            computed = computed_list[prev_len + i]
            result_rows.append(_calc_tech_row(r, computed=computed))
        return {"stock_code": c, "rows": result_rows}
    finally:
        conn.close()


@router.get("/stock/{code}/feed")
def stock_feed(
    code: str,
    tab: str = Query(default="news"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=5, ge=1),
) -> dict[str, Any]:
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        if tab == "reports":
            count_row = qd(conn,
                "SELECT COUNT(*) AS total FROM trade_report_consensus WHERE stock_code=%s", (c,))
            total = int(count_row[0].get("total", 0)) if count_row else 0
            offset = (page - 1) * pageSize
            rows = qd(conn,
                """SELECT report_date, broker, rating, target_price
                   FROM trade_report_consensus
                   WHERE stock_code=%s
                   ORDER BY report_date DESC
                   LIMIT %s OFFSET %s""",
                (c, pageSize, offset))
            items = [{"title": f"{r.get('broker', '')} {r.get('report_date', '')} | 评级:{r.get('rating', '—')} 目标价:{r.get('target_price', '—')}",
                      "source": r.get("broker", ""),
                      "publishedAt": _fmt_date(r.get("report_date")),
                      "url": None}
                     for r in rows]
        else:
            count_row = qd(conn,
                "SELECT COUNT(*) AS total FROM trade_stock_news WHERE stock_code=%s", (c,))
            total = int(count_row[0].get("total", 0)) if count_row else 0
            offset = (page - 1) * pageSize
            rows = qd(conn,
                """SELECT published_at, news_type, title, source, source_url, content
                   FROM trade_stock_news
                   WHERE stock_code=%s
                   ORDER BY published_at DESC
                   LIMIT %s OFFSET %s""",
                (c, pageSize, offset))
            items = [{"title": r.get("title", "—"),
                      "source": r.get("source", "") or r.get("news_type", ""),
                      "publishedAt": _fmt_dt(r.get("published_at")),
                      "url": r.get("source_url"),
                      "content": r.get("content")}
                     for r in rows]
        return {"tab": tab, "page": page, "pageSize": pageSize, "total": total, "items": items}
    finally:
        conn.close()
