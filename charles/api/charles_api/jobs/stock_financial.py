from __future__ import annotations

from datetime import date, datetime
import time
import os
from typing import Any

import pandas as pd

from ..db import MySQLConfig, connect, executemany, query_dict
from ..models import DataSource
from .common import JobStats


INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, revenue, net_profit, eps, roe, roa, gross_margin, net_margin, debt_ratio, current_ratio,
 operating_cashflow, total_assets, total_equity, data_source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
revenue=VALUES(revenue), net_profit=VALUES(net_profit), eps=VALUES(eps), roe=VALUES(roe), roa=VALUES(roa),
gross_margin=VALUES(gross_margin), net_margin=VALUES(net_margin), debt_ratio=VALUES(debt_ratio), current_ratio=VALUES(current_ratio),
operating_cashflow=VALUES(operating_cashflow), total_assets=VALUES(total_assets), total_equity=VALUES(total_equity),
data_source=VALUES(data_source)
"""


def _normalize_timetag(ts_val: Any) -> str | None:
    if ts_val is None:
        return None
    s = str(ts_val).strip()
    if len(s) == 8 and s.isdigit():
        return s
    try:
        v = float(s)
        if v == 0:
            return None
        if v > 1e12:
            v = v / 1000
        return datetime.fromtimestamp(v).strftime("%Y%m%d")
    except Exception:
        return None


def _build_period_map(data_list: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if isinstance(data_list, pd.DataFrame):
        for _, row in data_list.iterrows():
            p = _normalize_timetag(row.get("m_timetag"))
            if p:
                out[p] = row.to_dict()
    elif isinstance(data_list, list):
        for rec in data_list:
            if isinstance(rec, dict):
                p = _normalize_timetag(rec.get("m_timetag"))
                if p:
                    out[p] = rec
    return out


def _get_field(record: dict[str, Any], names: list[str]) -> Any:
    for n in names:
        v = record.get(n)
        if v is not None:
            return v
    return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        v = float(val)
    except Exception:
        return None
    return v if v == v else None


def _safe_div(a: Any, b: Any, pct: bool = False) -> float | None:
    if a is None or b is None:
        return None
    try:
        a_f = float(a)
        b_f = float(b)
    except Exception:
        return None
    if b_f == 0:
        return None
    r = a_f / b_f
    if pct:
        r *= 100
    r = round(r, 4)
    if r > 999999.9999:
        return 999999.9999
    if r < -999999.9999:
        return -999999.9999
    return r


def _extract_periods(data: dict[str, Any], stock_code: str) -> list[dict[str, Any]]:
    stock_data = data.get(stock_code, {})
    if not stock_data:
        return []

    ps_map = _build_period_map(stock_data.get("PershareIndex", []))
    bal_map = _build_period_map(stock_data.get("Balance", []))
    inc_map = _build_period_map(stock_data.get("Income", []))
    cf_map = _build_period_map(stock_data.get("CashFlow", []))

    periods = sorted(set(ps_map.keys()) | set(bal_map.keys()) | set(inc_map.keys()) | set(cf_map.keys()))
    out: list[dict[str, Any]] = []
    for p in periods:
        ps = ps_map.get(p, {})
        bal = bal_map.get(p, {})
        inc = inc_map.get(p, {})
        cf = cf_map.get(p, {})

        eps = _get_field(ps, ["s_fa_eps_basic"])
        revenue = _get_field(inc, ["revenue", "operating_revenue"])
        net_profit = _get_field(inc, ["net_profit_incl_min_int_inc", "net_profit_excl_min_int_inc"])
        operating_cost = _get_field(inc, ["cost_of_goods_sold", "total_operating_cost"])

        roe = _get_field(ps, ["du_return_on_equity", "equity_roe", "net_roe"])
        gross_margin = _get_field(ps, ["sales_gross_profit"])
        if gross_margin is None and revenue and operating_cost:
            try:
                r = float(revenue)
                c = float(operating_cost)
                if r > 0:
                    gross_margin = round((r - c) / r * 100, 4)
            except Exception:
                gross_margin = None

        total_assets = _get_field(bal, ["tot_assets"])
        total_liab = _get_field(bal, ["tot_liab"])
        total_equity = _get_field(bal, ["total_equity", "tot_shrhldr_eqy_incl_min_int"])
        current_assets = _get_field(bal, ["total_current_assets"])
        current_liab = _get_field(bal, ["total_current_liability"])

        roa = _safe_div(net_profit, total_assets, pct=True)
        if roe is None and net_profit and total_equity:
            roe = _safe_div(net_profit, total_equity, pct=True)

        net_margin = _safe_div(net_profit, revenue, pct=True)
        debt_ratio = _safe_div(total_liab, total_assets, pct=True)
        current_ratio = _safe_div(current_assets, current_liab, pct=False)
        operating_cashflow = _get_field(cf, ["net_cash_flows_oper_act"])

        out.append(
            {
                "report_date": p,
                "revenue": _safe_float(revenue),
                "net_profit": _safe_float(net_profit),
                "eps": _safe_float(eps),
                "roe": _safe_float(roe),
                "roa": _safe_float(roa),
                "gross_margin": _safe_float(gross_margin),
                "net_margin": _safe_float(net_margin),
                "debt_ratio": _safe_float(debt_ratio),
                "current_ratio": _safe_float(current_ratio),
                "operating_cashflow": _safe_float(operating_cashflow),
                "total_assets": _safe_float(total_assets),
                "total_equity": _safe_float(total_equity),
            }
        )
    return out


def run_stock_financial(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    test_mode = (mode or "").lower() == "test"
    test_stock = (params or {}).get("test_stock") or "600519.SH"
    batch_size = int((params or {}).get("batch_size") or 50)

    def _infer_exchange(code_num: str) -> str:
        if code_num.startswith("6"):
            return "SH"
        return "SZ"

    def _get_stock_list_fallback(max_n: int) -> list[str]:
        if test_mode:
            return [test_stock]
        token = os.getenv("TUSHARE_TOKEN")
        if token and str(token).strip():
            import tushare as ts

            ts.set_token(str(token).strip())
            pro = ts.pro_api()
            df = pro.stock_basic(exchange="", list_status="L", fields="ts_code")
            if df is not None and len(df) > 0:
                codes = [str(x) for x in df["ts_code"].tolist() if "." in str(x)]
                return codes[:max_n]
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return []
        codes = []
        for c in df["代码"].astype(str).tolist():
            codes.append(f"{c}.{_infer_exchange(c)}")
        return codes[:max_n]

    def _fetch_financial_tushare(ts_code: str) -> list[tuple[Any, ...]]:
        import tushare as ts

        token = os.getenv("TUSHARE_TOKEN")
        if not token or not str(token).strip():
            raise RuntimeError("missing TUSHARE_TOKEN")
        ts.set_token(str(token).strip())
        pro = ts.pro_api()

        income = pro.income(ts_code=ts_code, fields="end_date,revenue,n_income_attr_p")
        bal = pro.balancesheet(
            ts_code=ts_code,
            fields="end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int,total_cur_assets,total_cur_liab",
        )
        cf = pro.cashflow(ts_code=ts_code, fields="end_date,n_cashflow_act")
        ind = pro.fina_indicator(ts_code=ts_code, fields="end_date,eps,roe,roa,grossprofit_margin,netprofit_margin,debt_to_assets,current_ratio")

        def _prep(df: Any) -> pd.DataFrame:
            if df is None or len(df) == 0:
                return pd.DataFrame(columns=["end_date"]).astype({"end_date": str})
            return df.copy()

        income = _prep(income)
        bal = _prep(bal)
        cf = _prep(cf)
        ind = _prep(ind)

        merged = income.merge(bal, on="end_date", how="outer").merge(cf, on="end_date", how="outer").merge(ind, on="end_date", how="outer")
        if merged is None or len(merged) == 0:
            return []
        merged = merged.dropna(subset=["end_date"]).drop_duplicates(subset=["end_date"]).sort_values("end_date")

        rows: list[tuple[Any, ...]] = []
        for _, r in merged.iterrows():
            end_date = str(r.get("end_date", "")).strip()
            if len(end_date) != 8:
                continue
            report_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            rows.append(
                (
                    ts_code,
                    report_date,
                    None if pd.isna(r.get("revenue")) else float(r.get("revenue")),
                    None if pd.isna(r.get("n_income_attr_p")) else float(r.get("n_income_attr_p")),
                    None if pd.isna(r.get("eps")) else float(r.get("eps")),
                    None if pd.isna(r.get("roe")) else float(r.get("roe")),
                    None if pd.isna(r.get("roa")) else float(r.get("roa")),
                    None if pd.isna(r.get("grossprofit_margin")) else float(r.get("grossprofit_margin")),
                    None if pd.isna(r.get("netprofit_margin")) else float(r.get("netprofit_margin")),
                    None if pd.isna(r.get("debt_to_assets")) else float(r.get("debt_to_assets")),
                    None if pd.isna(r.get("current_ratio")) else float(r.get("current_ratio")),
                    None if pd.isna(r.get("n_cashflow_act")) else float(r.get("n_cashflow_act")),
                    None if pd.isna(r.get("total_assets")) else float(r.get("total_assets")),
                    None if pd.isna(r.get("total_hldr_eqy_exc_min_int")) else float(r.get("total_hldr_eqy_exc_min_int")),
                    "tushare",
                )
            )
        return rows

    def _fetch_financial_akshare(stock_code: str) -> list[tuple[Any, ...]]:
        import akshare as ak

        code_num = stock_code.split(".")[0]
        ex = stock_code.split(".")[-1].lower()
        sina_code = f"{ex}{code_num}"
        df_income = ak.stock_financial_report_sina(stock=sina_code, symbol="利润表")
        df_balance = ak.stock_financial_report_sina(stock=sina_code, symbol="资产负债表")
        df_cashflow = ak.stock_financial_report_sina(stock=sina_code, symbol="现金流量表")
        if df_income is None or df_balance is None or len(df_income) == 0 or len(df_balance) == 0:
            return []

        def _norm(df: pd.DataFrame) -> pd.DataFrame:
            d = df.copy()
            first = d.columns[0]
            d["_date"] = d[first].astype(str).str.replace("-", "").str[:8]
            return d

        inc = _norm(df_income)
        bal = _norm(df_balance)
        cf = _norm(df_cashflow) if df_cashflow is not None else pd.DataFrame(columns=["_date"])

        inc_map = {str(r["_date"]): r for _, r in inc.iterrows() if str(r.get("_date", "")).isdigit() and len(str(r.get("_date"))) == 8}
        bal_map = {str(r["_date"]): r for _, r in bal.iterrows() if str(r.get("_date", "")).isdigit() and len(str(r.get("_date"))) == 8}
        cf_map = {str(r["_date"]): r for _, r in cf.iterrows() if str(r.get("_date", "")).isdigit() and len(str(r.get("_date"))) == 8}
        periods = sorted(set(inc_map.keys()) & set(bal_map.keys()))

        def _get(row: Any, candidates: list[str]) -> float | None:
            if row is None:
                return None
            for c in candidates:
                if c in row.index:
                    v = row.get(c)
                    try:
                        x = float(str(v).replace(",", ""))
                        return x if x == x else None
                    except Exception:
                        continue
            return None

        rows: list[tuple[Any, ...]] = []
        for p in periods:
            inc_r = inc_map.get(p)
            bal_r = bal_map.get(p)
            cf_r = cf_map.get(p)

            revenue = _get(inc_r, ["营业收入", "一、营业收入", "一、营业总收入"])
            operating_cost = _get(inc_r, ["营业成本", "二、营业总成本", "营业总成本"])
            net_profit = _get(inc_r, ["净利润", "五、净利润", "四、净利润", "归属于母公司股东的净利润"])
            eps = _get(inc_r, ["基本每股收益", "（一）基本每股收益"])
            total_assets = _get(bal_r, ["资产总计", "资产合计"])
            total_liab = _get(bal_r, ["负债合计", "负债总计"])
            total_equity = _get(bal_r, ["所有者权益合计", "所有者权益（或股东权益）合计", "股东权益合计", "归属于母公司股东权益合计"])
            current_assets = _get(bal_r, ["流动资产合计"])
            current_liab = _get(bal_r, ["流动负债合计"])
            operating_cashflow = _get(cf_r, ["经营活动产生的现金流量净额"])

            gross_margin = None
            if revenue and operating_cost and revenue > 0:
                gross_margin = round((revenue - operating_cost) / revenue * 100, 4)
            roe = _safe_div(net_profit, total_equity, pct=True)
            roa = _safe_div(net_profit, total_assets, pct=True)
            net_margin = _safe_div(net_profit, revenue, pct=True)
            debt_ratio = _safe_div(total_liab, total_assets, pct=True)
            current_ratio = _safe_div(current_assets, current_liab, pct=False)

            report_date = f"{p[:4]}-{p[4:6]}-{p[6:8]}"
            rows.append(
                (
                    stock_code,
                    report_date,
                    revenue,
                    net_profit,
                    eps,
                    roe,
                    roa,
                    gross_margin,
                    net_margin,
                    debt_ratio,
                    current_ratio,
                    operating_cashflow,
                    total_assets,
                    total_equity,
                    "akshare",
                )
            )
        return rows

    fallback_chain: list[DataSource] = []
    primary: DataSource = DataSource.qmt
    try:
        from xtquant import xtdata

        xtdata.connect()
        if test_mode:
            all_codes = [test_stock]
        else:
            all_codes = [c for c in xtdata.get_stock_list_in_sector("沪深A股") if "." in str(c)]
        fallback_chain.append(DataSource.qmt)
        primary = DataSource.qmt
    except Exception:
        token = os.getenv("TUSHARE_TOKEN")
        primary = DataSource.tushare if token and str(token).strip() else DataSource.akshare
        fallback_chain.append(primary)
        max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 50))
        all_codes = _get_stock_list_fallback(max_stocks)

    conn = connect(cfg)
    try:
        existing_rows = query_dict(conn, "SELECT DISTINCT stock_code FROM trade_stock_financial")
        existing = {str(r["stock_code"]) for r in existing_rows}
        pending = [c for c in all_codes if c not in existing]
        if test_mode:
            pending = [test_stock]

        total_rows = 0
        processed = 0
        failed: list[str] = []

        if primary == DataSource.qmt:
            table_list = ["Balance", "Income", "CashFlow", "PershareIndex", "Capital"]
            data_start = (params or {}).get("data_start") or "20150101"
            data_end = (params or {}).get("data_end") or date.today().strftime("%Y%m%d")
            from xtquant import xtdata

            for i in range(0, len(pending), batch_size):
                batch = pending[i : i + batch_size]
                processed += len(batch)
                try:
                    done = {"ok": False}

                    def on_done(_data):
                        done["ok"] = True

                    xtdata.download_financial_data2(
                        stock_list=batch,
                        table_list=table_list,
                        start_time=data_start,
                        end_time=data_end,
                        callback=on_done,
                    )
                    deadline = time.time() + 120
                    while not done["ok"] and time.time() < deadline:
                        time.sleep(0.5)
                    time.sleep(1)

                    data = xtdata.get_financial_data(
                        stock_list=batch,
                        table_list=table_list,
                        start_time=data_start,
                        end_time=data_end,
                        report_type="report_time",
                    )
                    rows: list[tuple[Any, ...]] = []
                    for code in batch:
                        recs = _extract_periods(data or {}, code)
                        for rec in recs:
                            p = rec["report_date"]
                            report_date = f"{p[:4]}-{p[4:6]}-{p[6:8]}"
                            rows.append(
                                (
                                    code,
                                    report_date,
                                    rec["revenue"],
                                    rec["net_profit"],
                                    rec["eps"],
                                    rec["roe"],
                                    rec["roa"],
                                    rec["gross_margin"],
                                    rec["net_margin"],
                                    rec["debt_ratio"],
                                    rec["current_ratio"],
                                    rec["operating_cashflow"],
                                    rec["total_assets"],
                                    rec["total_equity"],
                                    "qmt",
                                )
                            )
                    total_rows += executemany(conn, INSERT_SQL, rows)
                    conn.commit()
                except Exception:
                    failed.extend(batch)

            return JobStats(
                items_processed=processed,
                rows_written=total_rows,
                failed_items=failed,
                data_source_final=DataSource.qmt,
                fallback_chain=fallback_chain,
                message=None if not failed else f"失败 {len(failed)} 只股票",
            )

        for code in pending:
            processed += 1
            ok = False
            for src in [primary, DataSource.tushare, DataSource.akshare]:
                if src == DataSource.qmt:
                    continue
                try:
                    if src == DataSource.tushare:
                        rows = _fetch_financial_tushare(code)
                    else:
                        rows = _fetch_financial_akshare(code)
                    if not rows:
                        continue
                    if src not in fallback_chain:
                        fallback_chain.append(src)
                    total_rows += executemany(conn, INSERT_SQL, rows)
                    conn.commit()
                    ok = True
                    break
                except Exception:
                    continue
            if not ok:
                failed.append(code)

        return JobStats(
            items_processed=processed,
            rows_written=total_rows,
            failed_items=failed,
            data_source_final=primary,
            fallback_chain=fallback_chain,
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()

