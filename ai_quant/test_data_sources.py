#!/usr/bin/env python3
import os, sys, traceback

print("=== 1. QMT (xtquant) ===")
try:
    from xtquant import xtdata
    print("xtquant imported OK")
    res = xtdata.get_market_data(
        stock_list=["600519.SH"],
        period="1d",
        start_time="20250101",
        end_time="",
        count=-1,
        dividend_type="front",
        fill_data=True,
    )
    print("QMT result keys:", list(res.keys()) if res else "empty")
except Exception as e:
    print("QMT error:", type(e).__name__, str(e)[:300])

print()
print("=== 2. AkShare ===")
try:
    import akshare as ak
    df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20250101", end_date="", adjust="qfq")
    print("AkShare rows:", len(df) if df is not None else 0)
    if df is not None and len(df) > 0:
        print(df.head(2).to_string())
except Exception as e:
    print("AkShare error:", type(e).__name__, str(e)[:300])

print()
print("=== 3. Tushare ===")
token = os.getenv("TUSHARE_TOKEN", "")
print("TUSHARE_TOKEN set:", bool(token))
if token:
    try:
        import tushare as ts
        ts.set_token(token)
        pro = ts.pro_api()
        df = pro.daily(ts_code="600519.SH", start_date="20250101", end_date="")
        print("Tushare rows:", len(df) if df is not None else 0)
    except Exception as e:
        print("Tushare error:", type(e).__name__, str(e)[:300])
else:
    print("TUSHARE_TOKEN not set, skipped")
