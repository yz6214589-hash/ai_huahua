"""
个股详情 API 模块
提供个股的行情快照、基本面数据、技术指标、新闻研报等数据查询
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from db import connect, load_mysql_config, query_dict
from runtime.logging_service import get_logger

logger = get_logger("stock_detail")

router = APIRouter(prefix="/api", tags=["stock_detail"])


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


def _calc_tech_row(row: dict[str, Any]) -> dict[str, Any]:
    close = _safe_float(row.get("close_price"))
    open_ = _safe_float(row.get("open_price"))
    high = _safe_float(row.get("high_price"))
    low = _safe_float(row.get("low_price"))
    vol = _safe_float(row.get("volume"))
    amount = _safe_float(row.get("amount"))
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
        "ma_custom": _safe_float(row.get("ma20")),
        "macd_dif_custom": _safe_float(row.get("macd_dif")),
        "macd_dea_custom": _safe_float(row.get("macd_dea")),
        "macd_hist_custom": _safe_float(row.get("macd_hist")),
        "rsi_custom": _safe_float(row.get("rsi14")),
        "atr_custom": None,
    }


def _calc_tech_latest(rows: list[dict[str, Any]], ma_period: int, macd_short: int, macd_long: int, macd_signal: int, rsi_period: int) -> dict[str, Any] | None:
    if not rows:
        return None
    closes = [float(r["close_price"]) for r in rows if r.get("close_price") is not None]
    n = len(closes)
    latest: dict[str, Any] = {}
    latest["ma5"] = _safe_float(rows[-1].get("ma5")) if rows else None
    latest["ma10"] = _safe_float(rows[-1].get("ma10")) if rows else None
    latest["ma20"] = _safe_float(rows[-1].get("ma20")) if rows else None
    latest["ma60"] = _safe_float(rows[-1].get("ma60")) if rows else None
    latest["vol_ma5"] = _safe_float(rows[-1].get("vol_ma5")) if rows else None
    latest["vol_ma20"] = _safe_float(rows[-1].get("vol_ma20")) if rows else None
    latest["rsi14"] = _safe_float(rows[-1].get("rsi14")) if rows else None
    latest["macd_dif"] = _safe_float(rows[-1].get("macd_dif")) if rows else None
    latest["macd_dea"] = _safe_float(rows[-1].get("macd_dea")) if rows else None
    latest["macd_hist"] = _safe_float(rows[-1].get("macd_hist")) if rows else None
    latest["boll_upper"] = _safe_float(rows[-1].get("boll_upper")) if rows else None
    latest["boll_mid"] = _safe_float(rows[-1].get("boll_mid")) if rows else None
    latest["boll_lower"] = _safe_float(rows[-1].get("boll_lower")) if rows else None
    latest["kdj_k"] = _safe_float(rows[-1].get("kdj_k")) if rows else None
    latest["kdj_d"] = _safe_float(rows[-1].get("kdj_d")) if rows else None
    latest["kdj_j"] = _safe_float(rows[-1].get("kdj_j")) if rows else None
    latest["atr14"] = None
    latest["ma_custom"] = _safe_float(rows[-1].get(f"ma{ma_period}")) if rows and rows[-1].get(f"ma{ma_period}") is not None else None
    latest["macd_dif_custom"] = latest["macd_dif"]
    latest["macd_dea_custom"] = latest["macd_dea"]
    latest["macd_hist_custom"] = latest["macd_hist"]
    latest["rsi_custom"] = latest["rsi14"]
    latest["atr_custom"] = None
    return latest


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
                pv = _safe_float(prev.get(key)) if prev else None
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
        rows.reverse()
        latest = _calc_tech_latest(rows, maPeriod, macdShort, macdLong, macdSignal, rsiPeriod)
        return {"stock_code": c, "row": latest or {}}
    finally:
        conn.close()


@router.get("/stock/{code}/technical/series")
def stock_technical_series(
    code: str,
    start: str = Query(default=""),
    end: str = Query(default=""),
) -> dict[str, Any]:
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        today = date.today()
        d_start = datetime.strptime(start, "%Y-%m-%d").date() if start else today - timedelta(days=180)
        d_end = datetime.strptime(end, "%Y-%m-%d").date() if end else today
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
        return {"stock_code": c, "rows": [_calc_tech_row(r) for r in rows]}
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
                """SELECT published_at, news_type, title, source, source_url
                   FROM trade_stock_news
                   WHERE stock_code=%s
                   ORDER BY published_at DESC
                   LIMIT %s OFFSET %s""",
                (c, pageSize, offset))
            items = [{"title": r.get("title", "—"),
                      "source": r.get("source", "") or r.get("news_type", ""),
                      "publishedAt": _fmt_dt(r.get("published_at")),
                      "url": r.get("source_url")}
                     for r in rows]
        return {"tab": tab, "page": page, "pageSize": pageSize, "total": total, "items": items}
    finally:
        conn.close()