from __future__ import annotations

import json
from typing import Any

from src.backend..infra.storage.database import MySQLConfig, connect, executemany
from .common import JobStats, normalize_stock_code, to_ymd


_INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, data_source, payload_json)
VALUES (%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
data_source=VALUES(data_source),
payload_json=VALUES(payload_json)
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

    codes = _get_stock_list(test_mode, test_stock, max_stocks)
    processed = 0
    rows_written = 0
    failed: list[str] = []

    conn = connect(cfg)
    try:
        batch: list[tuple[Any, ...]] = []
        for code in codes:
            processed += 1
            code_num = code.split(".")[0]
            try:
                df = ak.stock_financial_analysis_indicator_em(symbol=code_num, indicator="按报告期")
            except Exception:
                failed.append(code)
                continue
            if df is None or len(df) == 0:
                continue
            df2 = df.head(max_rows_per_stock)
            for _, r in df2.iterrows():
                rd = r.get("REPORT_DATE") if "REPORT_DATE" in df2.columns else (r.get("报告期") if "报告期" in df2.columns else None)
                report_date = to_ymd(rd)
                if not report_date:
                    continue
                payload = r.to_dict()
                for k, v in list(payload.items()):
                    if isinstance(v, (pd.Timestamp,)):
                        payload[k] = v.isoformat()
                batch.append((code, report_date, "akshare", json.dumps(payload, ensure_ascii=False, default=str)))
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

