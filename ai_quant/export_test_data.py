#!/usr/bin/env python3
"""导出 10 只测试股票的财务数据，用于联网对比"""

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

import pymysql
import json
from core.db import load_mysql_config

CODES = ['600268.SH', '300956.SZ', '002173.SZ', '002685.SZ', '002182.SZ',
         '688266.SH', '000751.SZ', '603111.SH', '601318.SH', '002660.SZ']

cfg = load_mysql_config()
conn = pymysql.connect(
    host=cfg.host, port=cfg.port, user=cfg.user,
    password=cfg.password, database=cfg.database,
    charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
)

result = {}
with conn.cursor() as cur:
    for code in CODES:
        cur.execute("""
            SELECT stock_code, report_date, revenue, net_profit, eps, roe, roa,
                   gross_margin, net_margin, debt_ratio, current_ratio,
                   pe_ttm, pb, market_cap, data_source
            FROM trade_stock_financial
            WHERE stock_code = %s
            ORDER BY report_date DESC
            LIMIT 2
        """, (code,))
        result[code] = cur.fetchall()

# 打印对比数据
for code, rows in result.items():
    print("=" * 80)
    print(f"{code}")
    print("=" * 80)
    if not rows:
        print("  无数据")
        continue
    for r in rows:
        print(f"\n  报告期: {r['report_date']}")
        print(f"    营收: {r['revenue']}")
        print(f"    净利润: {r['net_profit']}")
        print(f"    EPS: {r['eps']}")
        print(f"    ROE: {r['roe']}%")
        print(f"    ROA: {r['roa']}%")
        print(f"    毛利率: {r['gross_margin']}%")
        print(f"    净利率: {r['net_margin']}%")
        print(f"    资产负债率: {r['debt_ratio']}%")
        print(f"    流动比率: {r['current_ratio']}")
        print(f"    PE TTM: {r['pe_ttm']}")
        print(f"    PB: {r['pb']}")
        print(f"    总市值: {r['market_cap']}")
        print(f"    数据来源: {r['data_source']}")

# 同时保存为 JSON 文件
with open('/Users/apple/Desktop/ai_huahua/ai_quant/test_data_10_stocks.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)

print("\n\n数据已保存到 test_data_10_stocks.json")
conn.close()
