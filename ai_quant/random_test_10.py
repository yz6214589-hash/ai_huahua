#!/usr/bin/env python3
"""
随机抽取 10 只股票，用 tushare 采集近 3 年财务数据
"""

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

import random
import pymysql
from datetime import datetime, timedelta

from core.db import connect, executemany, load_mysql_config
from infra.tushare_client import get_pro_api

# 复用 collect_financial_3y.py 中的实现
from collect_financial_3y import (
    _INSERT_SQL,
    _log,
    _process_one_stock,
)


def random_pick_stocks(cfg, n=10, seed=None) -> list[str]:
    """从 trade_stock_master 随机抽取 n 只股票"""
    if seed is None:
        seed = int(datetime.now().timestamp()) % 10000
    _log(f"使用随机种子: {seed}")
    random.seed(seed)

    conn = connect(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT stock_code FROM trade_stock_master
                WHERE stock_code NOT LIKE 'SWL%%'
                  AND stock_code NOT LIKE '000%%.SH'
                  AND stock_code IS NOT NULL
                ORDER BY stock_code
            """)
            all_codes = [r['stock_code'] for r in cur.fetchall()]
    finally:
        conn.close()

    _log(f"总股票数: {len(all_codes)}")
    picked = random.sample(all_codes, n)
    _log(f"随机抽取的 {n} 只股票: {picked}")
    return picked


def main():
    _log("=" * 80)
    _log("随机抽取 10 只股票，用 tushare 采集近 3 年财务数据")
    _log("=" * 80)

    cfg = load_mysql_config()
    pro = get_pro_api()

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=3 * 365 + 30)).strftime("%Y%m%d")
    _log(f"采集时间范围: {start_date} 至 {end_date}")

    # 随机抽取
    codes = random_pick_stocks(cfg, n=10)
    codes_str = ", ".join(codes)
    _log(f"待采集: {codes_str}")

    # 采集数据
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )

    all_rows = []
    try:
        for code in codes:
            _log(f"  正在采集 {code} ...")
            rows = _process_one_stock(pro, code, start_date, end_date)
            if rows:
                _log(f"    {code}: 获取 {len(rows)} 条")
                all_rows.extend(rows)
            else:
                _log(f"    {code}: 无数据")

        if all_rows:
            _log(f"开始写入 {len(all_rows)} 条数据...")
            written = executemany(conn, _INSERT_SQL, all_rows)
            conn.commit()
            _log(f"写入完成: {written} 行")
        else:
            _log("没有数据可写入")

    finally:
        conn.close()

    _log("=" * 80)
    _log(f"采集完成: 共写入 {len(all_rows)} 条, 覆盖 {len(codes)} 只股票")
    _log("=" * 80)
    _log(f"股票列表: {codes_str}")


if __name__ == "__main__":
    main()
