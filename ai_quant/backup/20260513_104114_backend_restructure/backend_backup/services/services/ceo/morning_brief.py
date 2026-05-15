from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any

from db import connect, load_mysql_config, query_dict


@dataclass(frozen=True)
class MorningParams:
    industry_level: int
    top_n_industries: int
    top_n_stocks: int
    lookback_days: int
    sample_stocks: int


PHASE_DESC: dict[str, str] = {
    "accel_up": "主升加速",
    "decel_up": "高位钝化",
    "accel_down": "主跌",
    "decel_down": "左侧抄底",
    "neutral": "中性",
}


PHASE_BONUS: dict[str, float] = {
    "accel_up": 3.0,
    "decel_down": 2.0,
    "decel_up": 0.5,
    "accel_down": -2.0,
    "neutral": 0.0,
}


def _now_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def normalize_params(payload: dict[str, Any]) -> MorningParams:
    industry_level = _safe_int(payload.get("industry_level", 2), 2)
    if industry_level not in (1, 2):
        industry_level = 2
    return MorningParams(
        industry_level=industry_level,
        top_n_industries=max(1, min(_safe_int(payload.get("top_n_industries", 5), 5), 30)),
        top_n_stocks=max(1, min(_safe_int(payload.get("top_n_stocks", 5), 5), 50)),
        lookback_days=max(70, min(_safe_int(payload.get("lookback_days", 90), 90), 365)),
        sample_stocks=max(5, min(_safe_int(payload.get("sample_stocks", 20), 20), 200)),
    )


def _sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += float(v)
        if i >= period:
            s -= float(values[i - period])
        if i >= period - 1:
            out[i] = s / float(period)
    return out


def _ema(values: list[float], span: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if not values or span <= 0:
        return out
    alpha = 2.0 / (float(span) + 1.0)
    ema = float(values[0])
    out[0] = ema
    for i in range(1, len(values)):
        ema = alpha * float(values[i]) + (1.0 - alpha) * ema
        out[i] = ema
    return out


def _zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mu = sum(values) / float(len(values))
    var = sum((x - mu) * (x - mu) for x in values) / float(len(values))
    sd = math.sqrt(max(0.0, var))
    if sd == 0.0:
        return [0.0 for _ in values]
    return [(x - mu) / sd for x in values]


def detect_phase(derivs: dict[str, float]) -> dict[str, Any]:
    roc_20 = float(derivs.get("ROC_20", 0.0))
    ma20_slope = float(derivs.get("MA20_SLOPE", 0.0))
    macd_hist = float(derivs.get("MACD_HIST", 0.0))
    hist_delta = float(derivs.get("HIST_DELTA", 0.0))
    ma20_accel = float(derivs.get("MA20_ACCEL", 0.0))

    velocity_up = roc_20 > 0.5 and ma20_slope > 0.1
    velocity_dn = roc_20 < -0.5 and ma20_slope < -0.1
    accel_up = macd_hist > 0 and hist_delta > 0 and ma20_accel > 0
    accel_dn = macd_hist < 0 and hist_delta < 0 and ma20_accel < 0

    if velocity_up and accel_up:
        phase = "accel_up"
    elif velocity_up and accel_dn:
        phase = "decel_up"
    elif velocity_dn and accel_dn:
        phase = "accel_down"
    elif velocity_dn and accel_up:
        phase = "decel_down"
    else:
        phase = "neutral"

    return {
        "phase": phase,
        "phase_desc": PHASE_DESC.get(phase, "中性"),
        "vote_velocity": "up" if velocity_up else ("down" if velocity_dn else "flat"),
        "vote_accel": "up" if accel_up else ("down" if accel_dn else "flat"),
    }


def list_sectors(level: int) -> list[dict[str, Any]]:
    field = "sector_1" if int(level) == 1 else "sector_2"
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(
            conn,
            f"""
            SELECT {field} AS sector_name, COUNT(*) AS member_count
            FROM trade_stock_status
            WHERE {field} IS NOT NULL
            GROUP BY {field}
            ORDER BY {field}
            """,
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            name = str(r.get("sector_name") or "").strip()
            if not name:
                continue
            out.append({"sector_name": name, "member_count": int(r.get("member_count") or 0)})
        return out
    finally:
        conn.close()


def get_sector_member_codes(sector_name: str, level: int) -> list[str]:
    field = "sector_1" if int(level) == 1 else "sector_2"
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(
            conn,
            f"SELECT stock_code FROM trade_stock_status WHERE {field} = %s ORDER BY stock_code",
            (sector_name,),
        )
        return [str(r.get("stock_code") or "").strip() for r in rows if str(r.get("stock_code") or "").strip()]
    finally:
        conn.close()


def load_sector_kline(sector_name: str, level: int, end_date: str | None) -> list[dict[str, Any]]:
    conditions = ["sector_name = %s", "sector_level = %s"]
    params: list[Any] = [sector_name, int(level)]
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)
    sql = f"""
        SELECT trade_date, close_idx, total_amount
        FROM trade_sector_daily
        WHERE {' AND '.join(conditions)}
        ORDER BY trade_date ASC
    """
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        return query_dict(conn, sql, tuple(params))
    finally:
        conn.close()


def _calc_strength_indicators(close: list[float], amount: list[float]) -> dict[str, float]:
    if len(close) < 65 or len(amount) < 65:
        return {}
    mom_21 = float(close[-1] / close[-22] - 1.0) if close[-22] != 0 else 0.0
    avg_amt_5 = sum(amount[-5:]) / 5.0
    avg_amt_60 = sum(amount[-60:]) / 60.0
    vol_ratio = float(avg_amt_5 / avg_amt_60) if avg_amt_60 > 0 else 0.0
    return {"MOM_21": mom_21, "VOL_RATIO": vol_ratio}


def _calc_derivatives(close: list[float]) -> dict[str, float]:
    if len(close) < 60:
        return {}
    roc_20 = float(close[-1] / close[-21] - 1.0) * 100.0 if close[-21] != 0 else 0.0
    ma20 = _sma(close, 20)
    if len(close) < 26 or ma20[-1] is None or ma20[-6] is None or float(ma20[-6] or 0.0) == 0.0:
        return {"ROC_20": roc_20}
    ma20_slope = float((float(ma20[-1]) - float(ma20[-6])) / float(ma20[-6])) * 100.0
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    dif: list[float] = []
    for i in range(len(close)):
        if ema12[i] is None or ema26[i] is None:
            dif.append(0.0)
        else:
            dif.append(float(ema12[i]) - float(ema26[i]))
    dea = _ema(dif, 9)
    macd_hist = float((dif[-1] - float(dea[-1] or 0.0)) * 2.0)
    hist_prev = float((dif[-2] - float(dea[-2] or 0.0)) * 2.0) if len(dif) >= 2 else macd_hist
    hist_delta = macd_hist - hist_prev

    ma20_accel = 0.0
    if len(ma20) >= 11 and ma20[-11] is not None and float(ma20[-11] or 0.0) != 0.0:
        slope_now = (float(ma20[-1]) - float(ma20[-6])) / float(ma20[-6]) * 100.0
        slope_prev = (float(ma20[-6]) - float(ma20[-11])) / float(ma20[-11]) * 100.0
        ma20_accel = float(slope_now - slope_prev)

    return {
        "ROC_20": roc_20,
        "MA20_SLOPE": ma20_slope,
        "MACD_HIST": macd_hist,
        "HIST_DELTA": hist_delta,
        "MA20_ACCEL": ma20_accel,
    }


def rank_industries_with_phase(params: MorningParams, end_date: str | None) -> list[dict[str, Any]]:
    sectors = list_sectors(params.industry_level)
    if not sectors:
        return []

    rows: list[dict[str, Any]] = []
    mom_list: list[float] = []
    rs_list: list[float] = []
    vol_list: list[float] = []

    per_sector_ret60: dict[str, float] = {}
    sector_closes: dict[str, list[float]] = {}
    sector_amounts: dict[str, list[float]] = {}
    sector_meta: dict[str, dict[str, Any]] = {str(x["sector_name"]): x for x in sectors}

    for s in sectors:
        name = str(s.get("sector_name") or "")
        kline = load_sector_kline(name, params.industry_level, end_date)
        close: list[float] = []
        amount: list[float] = []
        for r in kline[-max(params.lookback_days, 70) :]:
            try:
                close.append(float(r.get("close_idx")))
                amount.append(float(r.get("total_amount") or 0.0))
            except Exception:
                continue
        if len(close) < 70:
            continue
        sector_closes[name] = close
        sector_amounts[name] = amount
        if len(close) >= 61 and close[-61] != 0:
            per_sector_ret60[name] = float(close[-1] / close[-61] - 1.0)

    if not per_sector_ret60:
        return []

    benchmark_ret60 = sum(per_sector_ret60.values()) / float(len(per_sector_ret60))

    for name, close in sector_closes.items():
        amount = sector_amounts.get(name, [])
        strength = _calc_strength_indicators(close, amount)
        if not strength:
            continue
        derivs = _calc_derivatives(close)
        phase = detect_phase(derivs)
        rs_60 = float(per_sector_ret60.get(name, 0.0) - benchmark_ret60)

        mom_list.append(float(strength["MOM_21"]))
        rs_list.append(rs_60)
        vol_list.append(float(strength["VOL_RATIO"]))

        rows.append(
            {
                "industry": name,
                "members": int(sector_meta.get(name, {}).get("member_count", 0)),
                "MOM_21": float(strength["MOM_21"]) * 100.0,
                "RS_60": float(rs_60) * 100.0,
                "VOL_R": float(strength["VOL_RATIO"]),
                "ROC_20": float(derivs.get("ROC_20", 0.0)),
                "phase": str(phase.get("phase")),
                "phase_desc": str(phase.get("phase_desc")),
            }
        )

    if not rows:
        return []

    mom_z = _zscore(mom_list)
    rs_z = _zscore(rs_list)
    vol_z = _zscore(vol_list)

    for i, r in enumerate(rows):
        score = float(mom_z[i]) + float(rs_z[i]) + 0.5 * float(vol_z[i])
        phase_bonus = float(PHASE_BONUS.get(str(r.get("phase")), 0.0))
        composite = float(score + phase_bonus)
        r["raw_score"] = float(score)
        r["score"] = float(composite)

    rows.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    out = []
    for idx, r in enumerate(rows[: params.top_n_industries], start=1):
        out.append(
            {
                "industry": r["industry"],
                "rank": idx,
                "score": round(float(r["score"]), 3),
                "raw_score": round(float(r["raw_score"]), 3),
                "MOM_21": round(float(r["MOM_21"]), 2),
                "RS_60": round(float(r["RS_60"]), 2),
                "VOL_R": round(float(r["VOL_R"]), 2),
                "phase": r["phase"],
                "phase_desc": r["phase_desc"],
                "ROC_20": round(float(r["ROC_20"]), 2),
                "members": int(r["members"]),
            }
        )
    return out


def _batch_load_stock_daily(codes: list[str], end_date: str | None, min_days: int) -> dict[str, list[dict[str, Any]]]:
    if not codes:
        return {}
    ph = ",".join(["%s"] * len(codes))
    conditions = [f"stock_code IN ({ph})"]
    params: list[Any] = list(codes)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)
    sql = f"""
        SELECT stock_code, trade_date, close_price, volume, rsi14, ma20
        FROM trade_stock_daily
        WHERE {' AND '.join(conditions)}
        ORDER BY stock_code ASC, trade_date ASC
    """
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(conn, sql, tuple(params))
    finally:
        conn.close()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        code = str(r.get("stock_code") or "").strip()
        if not code:
            continue
        grouped.setdefault(code, []).append(r)
    return {k: v for k, v in grouped.items() if len(v) >= min_days}


def pick_stocks_from_industries(industry_rank: list[dict[str, Any]], params: MorningParams, end_date: str | None) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    if not industry_rank:
        return [], [], []

    industry_to_codes: dict[str, list[str]] = {}
    pool: list[str] = []
    for r in industry_rank:
        ind = str(r.get("industry") or "")
        codes = get_sector_member_codes(ind, params.industry_level)[: params.sample_stocks]
        industry_to_codes[ind] = codes
        pool.extend(codes)

    pool = sorted(set([x for x in pool if x]))
    if not pool:
        return [], [], []

    grouped = _batch_load_stock_daily(pool, end_date, min_days=max(params.lookback_days, 70))
    if len(grouped) < 5:
        return pool, [], []

    items: list[dict[str, Any]] = []
    for code, rows in grouped.items():
        closes: list[float] = []
        vols: list[float] = []
        last_rsi: float | None = None
        last_ma20: float | None = None
        for x in rows[-params.lookback_days :]:
            try:
                closes.append(float(x.get("close_price")))
            except Exception:
                continue
            try:
                vols.append(float(x.get("volume") or 0.0))
            except Exception:
                vols.append(0.0)
            try:
                if x.get("rsi14") is not None:
                    last_rsi = float(x.get("rsi14"))
            except Exception:
                pass
            try:
                if x.get("ma20") is not None:
                    last_ma20 = float(x.get("ma20"))
            except Exception:
                pass
        if len(closes) < 70:
            continue

        mom_1m = float(closes[-1] / closes[-22] - 1.0) if closes[-22] != 0 else 0.0
        mom_3m = float(closes[-1] / closes[-61] - 1.0) if closes[-61] != 0 else 0.0
        avg_vol_20 = sum(vols[-20:]) / 20.0
        avg_vol_60 = sum(vols[-60:]) / 60.0
        vol_20 = float(avg_vol_20 / avg_vol_60) if avg_vol_60 > 0 else 0.0

        ma20_val = last_ma20
        if ma20_val is None:
            ma20_series = _sma(closes, 20)
            ma20_val = ma20_series[-1]
        bias_20 = float((closes[-1] - float(ma20_val or closes[-1])) / float(ma20_val or closes[-1])) if float(ma20_val or 0.0) != 0.0 else 0.0
        rsi_14 = float(last_rsi or 50.0)

        industry = next((k for k, v in industry_to_codes.items() if code in v), "未分类")
        items.append(
            {
                "code": code,
                "industry": industry,
                "MOM_1M": mom_1m,
                "MOM_3M": mom_3m,
                "VOL_20": vol_20,
                "RSI_14": rsi_14 / 100.0,
                "BIAS_20": bias_20,
            }
        )

    if len(items) < 5:
        return pool, [], []

    keys = ["MOM_1M", "MOM_3M", "VOL_20", "RSI_14", "BIAS_20"]
    zmap: dict[str, list[float]] = {}
    for k in keys:
        zmap[k] = _zscore([float(x[k]) for x in items])
    for i, it in enumerate(items):
        alpha = sum(float(zmap[k][i]) for k in keys) / float(len(keys))
        it["alpha"] = float(alpha)

    items.sort(key=lambda x: float(x.get("alpha") or 0.0), reverse=True)

    factor_rank: list[dict[str, Any]] = []
    for it in items[: params.top_n_stocks * 3]:
        factor_rank.append(
            {
                "code": it["code"],
                "industry": it["industry"],
                "alpha": round(float(it["alpha"]), 3),
                "raw_factors": {
                    "MOM_1M": round(float(it["MOM_1M"]), 4),
                    "MOM_3M": round(float(it["MOM_3M"]), 4),
                    "VOL_20": round(float(it["VOL_20"]), 3),
                    "RSI_14": round(float(it["RSI_14"]) * 100.0, 2),
                    "BIAS_20": round(float(it["BIAS_20"]), 4),
                },
            }
        )

    picked = factor_rank[: params.top_n_stocks]
    return pool, factor_rank, picked


def build_report(industry_level: int, industry_rank: list[dict[str, Any]], picked_stocks: list[dict[str, Any]]) -> dict[str, str]:
    today_str = datetime.now().strftime("%Y-%m-%d %A")
    md_lines: list[str] = [
        f"# 晨会分析简报 -- {today_str}",
        "",
        f"## Top {len(industry_rank)} 强势板块 (申万{'一' if int(industry_level) == 1 else '二'}级)",
        "",
        "| Rank | 板块 | 综合分 | 拐点信号 | 21日动量 | 60日相对强度 | 20日ROC |",
        "|------|------|--------|----------|----------|--------------|---------|",
    ]

    for r in industry_rank:
        md_lines.append(
            f"| {r['rank']} | **{r['industry']}** | {float(r['score']):+.2f} | "
            f"{r.get('phase_desc', '中性')} | "
            f"{float(r['MOM_21']):+.2f}% | {float(r['RS_60']):+.2f}% | {float(r.get('ROC_20', 0.0)):+.2f}% |"
        )

    md_lines += ["", f"## Top {len(picked_stocks)} 选中标的", ""]
    md_lines.append("| 代码 | 行业 | 综合alpha | 3M动量 |")
    md_lines.append("|------|------|-----------|--------|")
    for p in picked_stocks:
        raw = p.get("raw_factors") or {}
        mom_3m = raw.get("MOM_3M", 0.0)
        try:
            mom_3m_f = float(mom_3m)
        except Exception:
            mom_3m_f = 0.0
        md_lines.append(
            f"| `{p['code']}` | {p.get('industry', '')} | {float(p.get('alpha') or 0.0):+.3f} | {mom_3m_f:+.2%} |"
        )

    md_lines += ["", "## 盘中应对建议", ""]
    if picked_stocks:
        for p in picked_stocks:
            md_lines.append(
                f"- `{p['code']}` ({p.get('industry', '')}): alpha={float(p.get('alpha') or 0.0):+.3f}, 关注开盘 30 分钟方向"
            )
    else:
        md_lines.append("- 无候选标的, 今日观望")

    md_lines += [
        "",
        "---",
        "",
        "> 本简报由 AI 量化团队自动生成, 仅供参考, 不构成投资建议",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    report_md = "\n".join(md_lines)
    report_html = md_to_html(report_md)
    return {"report_md": report_md, "report_html": report_html}


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>",
        "<title>晨会分析简报</title>",
        "<style>",
        "body{font-family:-apple-system,'Microsoft YaHei',sans-serif;max-width:900px;margin:30px auto;padding:0 24px;color:#2c3e50;line-height:1.7}",
        "h1{border-bottom:3px solid #3498db;padding-bottom:10px}",
        "h2{color:#3498db;margin-top:30px}",
        "table{border-collapse:collapse;width:100%;margin:14px 0}",
        "th{background:#34495e;color:#fff;padding:8px 12px;text-align:left}",
        "td{padding:8px 12px;border:1px solid #dee2e6}",
        "tr:nth-child(even){background:#f8f9fa}",
        "code{background:#e8ecef;padding:2px 6px;border-radius:4px;font-family:'Consolas',monospace}",
        "blockquote{border-left:3px solid #95a5a6;color:#555;padding-left:12px;background:#f1f3f5;padding-top:8px;padding-bottom:8px}",
        "</style></head><body>",
    ]

    in_table = False
    table_rows: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.match(r"^-+$", c) for c in cells):
                continue
            if not in_table:
                in_table = True
                table_rows = ["<table><thead><tr>"]
                for c in cells:
                    table_rows.append(f"<th>{escape(c)}</th>")
                table_rows.append("</tr></thead><tbody>")
            else:
                table_rows.append("<tr>")
                for c in cells:
                    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(c))
                    rendered = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", rendered)
                    table_rows.append(f"<td>{rendered}</td>")
                table_rows.append("</tr>")
            continue
        if in_table:
            table_rows.append("</tbody></table>")
            out.extend(table_rows)
            in_table = False
            table_rows = []

        if s.startswith("# "):
            out.append(f"<h1>{escape(s[2:])}</h1>")
        elif s.startswith("## "):
            out.append(f"<h2>{escape(s[3:])}</h2>")
        elif s.startswith("- "):
            li_html = re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(s[2:]))
            out.append(f"<li>{li_html}</li>")
        elif s.startswith("> "):
            out.append(f"<blockquote>{escape(s[2:])}</blockquote>")
        elif s == "---":
            out.append("<hr>")
        elif s == "":
            continue
        else:
            p_html = re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(s))
            out.append(f"<p>{p_html}</p>")

    if in_table:
        table_rows.append("</tbody></table>")
        out.extend(table_rows)

    out.append("</body></html>")
    return "\n".join(out)


def run_morning_workflow(state: dict[str, Any]) -> dict[str, Any]:
    params = normalize_params(state)
    end_date = state.get("end_date")
    if end_date is not None:
        end_date = str(end_date)

    preset_industry_rank = state.get("industry_rank")
    preset_picked = state.get("picked_stocks")
    if isinstance(preset_industry_rank, list) and isinstance(preset_picked, list):
        industry_rank = preset_industry_rank
        picked_stocks = preset_picked
        stock_pool = list(state.get("stock_pool") or [])
        factor_rank = list(state.get("factor_rank") or [])
    else:
        industry_rank = rank_industries_with_phase(params, end_date)
        stock_pool, factor_rank, picked_stocks = pick_stocks_from_industries(industry_rank, params, end_date)

    report = build_report(params.industry_level, industry_rank, picked_stocks)
    return {
        "industry_rank": industry_rank,
        "stock_pool": stock_pool,
        "factor_rank": factor_rank,
        "picked_stocks": picked_stocks,
        **report,
        "messages": [
            {"role": "industry", "time": _now_time(), "content": f"Top {len(industry_rank)} 板块: " + ", ".join([x.get('industry', '') for x in industry_rank])},
            {"role": "stock_picker", "time": _now_time(), "content": f"选中 {len(picked_stocks)} 只: " + ", ".join([x.get('code', '') for x in picked_stocks])},
            {"role": "report", "time": _now_time(), "content": f"晨报生成 {len(str(report.get('report_md') or ''))} 字节"},
        ],
        "generated_at": _now_iso(),
    }
