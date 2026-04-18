# -*- coding: utf-8 -*-
"""
建库建表 + 下载 50 只股票日线数据到 MySQL(trade_stock_daily)

用法:
1) 先配置同目录 .env 的数据库账号密码
2) 执行:
   python 0-bootstrap_mysql_and_daily_data.py
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
import pymysql
import akshare as ak
from dotenv import dotenv_values


HERE = Path(__file__).parent
ENV_PATH = HERE / ".env"
ENV = dotenv_values(ENV_PATH)

HOST = ENV.get("WUCAI_SQL_HOST", "localhost")
USER = ENV.get("WUCAI_SQL_USERNAME", "root")
PASSWORD = ENV.get("WUCAI_SQL_PASSWORD", "")
PORT = int(ENV.get("WUCAI_SQL_PORT", "3306"))
DB_NAME = ENV.get("WUCAI_SQL_DB", "wucai_trade")

START_DATE = "20230101"
END_DATE = "20251231"

STOCK_POOL = [
    "600519.SH", "000858.SZ", "601318.SH", "600036.SH", "000333.SZ",
    "600900.SH", "601166.SH", "000001.SZ", "600276.SH", "601888.SH",
    "002594.SZ", "300750.SZ", "601398.SH", "601939.SH", "600030.SH",
    "000651.SZ", "002415.SZ", "600309.SH", "600887.SH", "601012.SH",
    "000568.SZ", "002304.SZ", "600050.SH", "601668.SH", "600000.SH",
    "000002.SZ", "601857.SH", "600585.SH", "002352.SZ", "600104.SH",
    "601601.SH", "600690.SH", "601288.SH", "600028.SH", "601138.SH",
    "002714.SZ", "300059.SZ", "002475.SZ", "600031.SH", "300760.SZ",
    "601899.SH", "600809.SH", "000725.SZ", "002230.SZ", "601919.SH",
    "300015.SZ", "002142.SZ", "600438.SH", "601225.SH", "002027.SZ",
]


DAILY_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS trade_stock_daily (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    open_price DECIMAL(10,2) COMMENT '开盘价',
    high_price DECIMAL(10,2) COMMENT '最高价',
    low_price DECIMAL(10,2) COMMENT '最低价',
    close_price DECIMAL(10,2) COMMENT '收盘价(前复权)',
    volume BIGINT COMMENT '成交量(股)',
    amount DECIMAL(20,2) COMMENT '成交额(元)',
    turnover_rate DECIMAL(10,4) COMMENT '换手率',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_stock_daily_code_date (stock_code, trade_date),
    KEY idx_stock_daily_code (stock_code),
    KEY idx_stock_daily_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日K线数据';
"""


def to_ak_symbol(code: str) -> str:
    ts_code, market = code.split(".")
    if market.upper() == "SH":
        return f"sh{ts_code}"
    return f"sz{ts_code}"


def get_conn(with_db: bool) -> pymysql.connections.Connection:
    kwargs = {
        "host": HOST,
        "user": USER,
        "password": PASSWORD,
        "port": PORT,
        "charset": "utf8mb4",
        "autocommit": True,
    }
    if with_db:
        kwargs["database"] = DB_NAME
    return pymysql.connect(**kwargs)


def init_db() -> None:
    conn = get_conn(with_db=False)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")
    cur.close()
    conn.close()

    conn = get_conn(with_db=True)
    cur = conn.cursor()
    cur.execute(DAILY_TABLE_DDL)
    cur.close()
    conn.close()


def fetch_daily_df(stock_code: str) -> pd.DataFrame:
    symbol = to_ak_symbol(stock_code)
    raw = None

    # 1) 优先腾讯源，当前网络环境下稳定性更高
    try:
        raw = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=START_DATE,
            end_date=END_DATE,
            adjust="qfq",
        )
    except Exception:
        raw = None

    # 2) 回退到东方财富源
    if raw is None or raw.empty:
        try:
            raw = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=START_DATE,
                end_date=END_DATE,
                adjust="qfq",
            )
        except Exception:
            raw = None

    if raw is None or raw.empty:
        return pd.DataFrame()

    # 兼容不同版本列名
    # 常见列: 日期 开盘 收盘 最高 最低 成交量 成交额 振幅 涨跌幅 涨跌额 换手率
    col_map = {
        "日期": "trade_date",
        "date": "trade_date",
        "开盘": "open_price",
        "open": "open_price",
        "最高": "high_price",
        "high": "high_price",
        "最低": "low_price",
        "low": "low_price",
        "收盘": "close_price",
        "close": "close_price",
        "成交量": "volume",
        "vol": "volume",
        "volume": "volume",
        "成交额": "amount",
        "amount": "amount",
        "换手率": "turnover_rate",
        "turnover": "turnover_rate",
    }
    df = raw.rename(columns=col_map)
    # 部分源会同时存在中英文字段，重命名后可能出现重复列名
    df = df.loc[:, ~df.columns.duplicated()].copy()
    keep_cols = list(dict.fromkeys([c for c in col_map.values() if c in df.columns]))
    df = df[keep_cols].copy()

    if "trade_date" not in df.columns:
        return pd.DataFrame()

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    for c in ("open_price", "high_price", "low_price", "close_price", "amount", "turnover_rate"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")

    df["stock_code"] = stock_code
    if "amount" not in df.columns:
        df["amount"] = None
    if "turnover_rate" not in df.columns:
        df["turnover_rate"] = None
    if "volume" not in df.columns:
        df["volume"] = 0

    df = df[
        [
            "stock_code", "trade_date", "open_price", "high_price", "low_price",
            "close_price", "volume", "amount", "turnover_rate",
        ]
    ].dropna(subset=["trade_date", "open_price", "high_price", "low_price", "close_price"])
    return df


def upsert_daily_rows(rows: List[Tuple]) -> None:
    if not rows:
        return
    sql = """
    INSERT INTO trade_stock_daily
    (stock_code, trade_date, open_price, high_price, low_price, close_price, volume, amount, turnover_rate)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
      open_price=VALUES(open_price),
      high_price=VALUES(high_price),
      low_price=VALUES(low_price),
      close_price=VALUES(close_price),
      volume=VALUES(volume),
      amount=VALUES(amount),
      turnover_rate=VALUES(turnover_rate)
    """
    conn = get_conn(with_db=True)
    cur = conn.cursor()
    cur.executemany(sql, rows)
    conn.commit()
    cur.close()
    conn.close()


def main() -> int:
    print("=" * 80)
    print("初始化 MySQL 数据库并导入 50 只股票日线")
    print("=" * 80)
    print(f"DB: {USER}@{HOST}:{PORT}/{DB_NAME}")

    try:
        init_db()
    except Exception as e:
        print(f"[失败] 建库建表失败: {e}")
        print("请检查 .env 中 WUCAI_SQL_USERNAME/WUCAI_SQL_PASSWORD 是否正确。")
        return 2

    ok, fail = 0, 0
    total_rows = 0
    for code in STOCK_POOL:
        try:
            df = fetch_daily_df(code)
            if df.empty:
                print(f"[跳过] {code} 无有效数据")
                fail += 1
                continue

            rows = [
                (
                    r["stock_code"], r["trade_date"], float(r["open_price"]), float(r["high_price"]),
                    float(r["low_price"]), float(r["close_price"]), int(r["volume"]),
                    (None if pd.isna(r["amount"]) else float(r["amount"])),
                    (None if pd.isna(r["turnover_rate"]) else float(r["turnover_rate"])),
                )
                for _, r in df.iterrows()
            ]
            upsert_daily_rows(rows)
            ok += 1
            total_rows += len(rows)
            print(f"[完成] {code} -> {len(rows)} 行")
        except Exception as e:
            fail += 1
            print(f"[失败] {code}: {e}")

    print("-" * 80)
    print(f"完成: 成功 {ok} 只, 失败 {fail} 只, 写入/更新总行数 {total_rows}")

    # 验证入库覆盖
    try:
        conn = get_conn(with_db=True)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS n_rows, COUNT(DISTINCT stock_code) AS n_codes,
                   MIN(trade_date), MAX(trade_date)
            FROM trade_stock_daily
            WHERE stock_code IN ({})
            """.format(",".join(["%s"] * len(STOCK_POOL))),
            STOCK_POOL,
        )
        n_rows, n_codes, min_dt, max_dt = cur.fetchone()
        print(f"校验: n_rows={n_rows}, n_codes={n_codes}, range={min_dt}~{max_dt}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[警告] 校验查询失败: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
