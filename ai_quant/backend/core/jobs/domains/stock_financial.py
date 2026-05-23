from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, normalize_stock_code, safe_float, to_ymd


_INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, revenue, net_profit, eps, roe, roa, gross_margin, net_margin, debt_ratio, current_ratio, operating_cashflow, total_assets, total_equity, data_source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
revenue=COALESCE(VALUES(revenue), revenue),
net_profit=COALESCE(VALUES(net_profit), net_profit),
eps=COALESCE(VALUES(eps), eps),
roe=COALESCE(VALUES(roe), roe),
roa=COALESCE(VALUES(roa), roa),
gross_margin=COALESCE(VALUES(gross_margin), gross_margin),
net_margin=COALESCE(VALUES(net_margin), net_margin),
debt_ratio=COALESCE(VALUES(debt_ratio), debt_ratio),
current_ratio=COALESCE(VALUES(current_ratio), current_ratio),
operating_cashflow=COALESCE(VALUES(operating_cashflow), operating_cashflow),
total_assets=COALESCE(VALUES(total_assets), total_assets),
total_equity=COALESCE(VALUES(total_equity), total_equity),
data_source=VALUES(data_source)
"""


def _infer_exchange(code_num: str) -> str:
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


def _get_stock_list(test_mode: bool, test_stock: str, max_stocks: int) -> list[str]:
    if test_mode:
        s = normalize_stock_code(test_stock)
        return [s] if s else []
    import akshare as ak

    df = ak.stock_zh_a_spot_em()
    if df is None or len(df) == 0:
        return []
    out: list[str] = []
    for _, r in df.iterrows():
        code_num = str(r.get("代码") or "").strip()
        if not code_num:
            continue
        out.append(f"{code_num}.{_infer_exchange(code_num)}")
        if 0 < max_stocks <= len(out):
            break
    return out


def run_stock_financial(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    test_mode = (mode or "").lower() == "test"
    test_stock = str((params or {}).get("test_stock") or "600519.SH")
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 50))
    max_rows_per_stock = int((params or {}).get("max_rows_per_stock") or 12)
    max_workers = max(1, int((params or {}).get("max_workers") or 4))

    codes = _get_stock_list(test_mode, test_stock, max_stocks)
    total_count = len(codes)
    processed = 0
    rows_written = 0
    failed: list[str] = []

    def _process_one(code):
        code_num = code.split(".")[0]
        try:
            df = ak.stock_financial_analysis_indicator_em(symbol=code_num, indicator="按报告期")
        except Exception:
            return None, True
        if df is None or len(df) == 0:
            return [], False
        rows = []
        for _, r in df.head(max_rows_per_stock).iterrows():
            rd = r.get("REPORT_DATE") if "REPORT_DATE" in df.columns else (r.get("报告期") if "报告期" in df.columns else None)
            report_date = to_ymd(rd)
            if not report_date:
                continue
            payload = r.to_dict()
            for k, v in list(payload.items()):
                if isinstance(v, (pd.Timestamp,)):
                    payload[k] = v.isoformat()
            revenue = safe_float(payload.get("营业总收入") or payload.get("REVENUE"))
            net_profit = safe_float(payload.get("净利润") or payload.get("NET_PROFIT"))
            eps = safe_float(payload.get("每股收益") or payload.get("BASIC_EPS"))
            roe = safe_float(payload.get("净资产收益率") or payload.get("WEIGHT_AVG_ROE"))
            roa = safe_float(payload.get("总资产净利率") or payload.get("ROA"))
            gross_margin = safe_float(payload.get("销售毛利率") or payload.get("GROSS_PROFIT_RATIO"))
            net_margin = safe_float(payload.get("销售净利率") or payload.get("NET_PROFIT_RATIO"))
            debt_ratio = safe_float(payload.get("资产负债率") or payload.get("DEBT_ASSET_RATIO"))
            current_ratio = safe_float(payload.get("流动比率") or payload.get("CURRENT_RATIO"))
            operating_cashflow = safe_float(payload.get("经营活动产生的现金流量净额") or payload.get("OPERATE_CASH_FLOW"))
            total_assets = safe_float(payload.get("总资产") or payload.get("TOTAL_ASSETS"))
            total_equity = safe_float(payload.get("所有者权益合计") or payload.get("TOTAL_EQUITY"))
            rows.append((code, report_date, revenue, net_profit, eps, roe, roa, gross_margin, net_margin, debt_ratio, current_ratio, operating_cashflow, total_assets, total_equity, "akshare"))
        return rows, False

    conn = connect(cfg)
    try:
        batch: list[tuple[Any, ...]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(_process_one, code): code for code in codes}
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                processed += 1
                try:
                    result_rows, is_failed = future.result()
                except Exception:
                    failed.append(code)
                    continue
                if is_failed:
                    failed.append(code)
                    continue
                batch.extend(result_rows)
        rows_written = executemany(conn, _INSERT_SQL, batch)
        return JobStats(
            items_processed=processed,
            rows_written=rows_written,
            failed_items=failed,
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()

