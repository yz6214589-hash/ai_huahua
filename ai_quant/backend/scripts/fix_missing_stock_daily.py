"""
数据补全脚本：扫描数据库中存在于 trade_stock_master 但缺失 trade_stock_daily 行情数据的股票/指数，
并通过 AkShare 采集缺失的日线行情数据写入数据库。

使用方法:
    cd ai_quant
    source venv/bin/activate
    python -m backend.scripts.fix_missing_stock_daily [--dry-run] [--max-stocks N] [--days N]

参数:
    --dry-run      仅扫描不写入数据库
    --max-stocks   最大处理股票数量（默认 50）
    --days         采集最近N天的数据（默认 365）
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Any

sys.path.insert(0, ".")

from core.db import MySQLConfig, connect, executemany, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("fix_missing_daily")

_INSERT_SQL = """
INSERT INTO trade_stock_daily
(stock_code, trade_date, close_price, volume, rsi14, ma20, stock_name)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
close_price=VALUES(close_price),
volume=VALUES(volume),
rsi14=VALUES(rsi14),
ma20=VALUES(ma20),
stock_name=COALESCE(VALUES(stock_name), stock_name)
"""

# 沪深交易所主要指数代码（.SH/.SZ 后缀），这些需要走指数接口
_INDEX_CODES = {
    "000001.SH", "000016.SH", "000300.SH", "000688.SH",
    "000905.SH", "000852.SH",
    "399001.SZ", "399006.SZ", "399005.SZ", "399673.SZ",
}

# AkShare 指数代码映射（AkShare 使用不同的 symbol 命名）
_AKSHARE_INDEX_MAP = {
    "000001.SH": "sh000001",
    "000016.SH": "sh000016",
    "000300.SH": "sh000300",
    "000688.SH": "sh000688",
    "000905.SH": "sh000905",
    "000852.SH": "sh000852",
    "399001.SZ": "sz399001",
    "399006.SZ": "sz399006",
    "399005.SZ": "sz399005",
    "399673.SZ": "sz399673",
}


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def _is_index(code: str) -> bool:
    """判断是否为指数代码"""
    return code in _INDEX_CODES or code.split(".")[0].startswith("000") and code.endswith(".SH") or \
           code.split(".")[0].startswith("399") and code.endswith(".SZ")


def scan_missing_stocks(cfg: MySQLConfig) -> list[dict[str, Any]]:
    """扫描存在于 master 但缺失 daily 数据的股票/指数"""
    conn = connect(cfg)
    try:
        rows = query_dict(conn, """
            SELECT m.stock_code, m.stock_name
            FROM trade_stock_master m
            LEFT JOIN (
                SELECT DISTINCT stock_code FROM trade_stock_daily
            ) d ON m.stock_code = d.stock_code
            WHERE d.stock_code IS NULL
            ORDER BY m.stock_code
        """)
        return rows
    finally:
        conn.close()


def _fetch_index_daily(code: str, start_date: str, end_date: str) -> list[tuple] | None:
    """通过 AkShare 指数接口获取指数日线行情数据"""
    try:
        import akshare as ak

        symbol = _AKSHARE_INDEX_MAP.get(code)
        if not symbol:
            _log(f"  指数 {code} 不在 AkShare 映射表中，跳过")
            return None

        _log(f"  使用指数接口 stock_zh_index_daily 获取 {code} (symbol={symbol})")
        df = ak.stock_zh_index_daily(symbol=symbol)

        if df is None or len(df) == 0:
            _log(f"  指数接口返回 {code} 数据为空")
            return None

        col_map = {"date": "date", "close": "close", "volume": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        if "date" not in df.columns or "close" not in df.columns:
            _log(f"  指数接口返回 {code} 数据缺少 date/close 列，可用列: {list(df.columns)}")
            return None

        # 日期过滤
        df["date"] = df["date"].astype(str)
        df = df[df["date"] >= start_date]
        df = df[df["date"] <= end_date]

        if "volume" in df.columns:
            df["volume"] = df["volume"].astype(float)
        else:
            df["volume"] = 0.0

        rows = []
        for _, r in df.iterrows():
            rows.append((
                code,
                r["date"],
                float(r["close"]),
                float(r.get("volume", 0)),
                None,
                None,
                None,
            ))
        return rows if rows else None
    except Exception as e:
        _log(f"  指数接口获取 {code} 失败: {type(e).__name__}: {e}")
        return None


def _fetch_stock_daily(code: str, start_date: str, end_date: str) -> list[tuple] | None:
    """通过 AkShare 获取个股日线行情数据"""
    try:
        import akshare as ak

        code_num = code.split(".")[0]
        df = ak.stock_zh_a_hist(
            symbol=code_num,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if df is None or len(df) == 0:
            return None

        col_map = {"日期": "date", "收盘": "close", "成交量": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "date" not in df.columns or "close" not in df.columns:
            return None

        df["date"] = df["date"].astype(str)
        if "volume" in df.columns:
            df["volume"] = df["volume"].astype(float)
        else:
            df["volume"] = 0.0

        rows = []
        for _, r in df.iterrows():
            rows.append((
                code,
                r["date"],
                float(r["close"]),
                float(r.get("volume", 0)),
                None,
                None,
                None,
            ))
        return rows if rows else None
    except Exception as e:
        _log(f"  个股接口获取 {code} 失败: {type(e).__name__}: {e}")
        return None


def fetch_daily(code: str, start_date: str, end_date: str) -> list[tuple] | None:
    """根据代码类型自动选择指数或个股接口获取日线数据"""
    if _is_index(code):
        result = _fetch_index_daily(code, start_date, end_date)
        if result:
            return result
        _log(f"  指数接口失败，尝试个股接口作为备选...")
        return _fetch_stock_daily(code, start_date, end_date)
    return _fetch_stock_daily(code, start_date, end_date)


def main():
    parser = argparse.ArgumentParser(description="补全缺失行情数据的股票/指数日线数据")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描，不写入数据库")
    parser.add_argument("--max-stocks", type=int, default=50, help="最大处理股票数量")
    parser.add_argument("--days", type=int, default=365, help="采集最近N天的数据")
    args = parser.parse_args()

    _log("=" * 60)
    _log("开始执行数据补全脚本")
    _log(f"参数: dry_run={args.dry_run}, max_stocks={args.max_stocks}, days={args.days}")
    _log("=" * 60)

    cfg = load_mysql_config()

    # 第1步：扫描缺失行情数据的股票
    _log("第1步：扫描缺失行情数据的股票/指数...")
    missing = scan_missing_stocks(cfg)
    _log(f"扫描完成：共发现 {len(missing)} 只缺失行情数据的股票/指数")

    if not missing:
        _log("所有股票行情数据完整，无需补全。")
        return

    for i, stock in enumerate(missing[:15]):
        tag = "[指数]" if _is_index(stock["stock_code"]) else "[个股]"
        _log(f"  {tag} {stock['stock_code']} - {stock.get('stock_name', '未知')}")
    if len(missing) > 15:
        _log(f"  ... 还有 {len(missing) - 15} 只股票/指数")

    if args.dry_run:
        _log("[dry-run 模式] 不执行数据写入，扫描结束。")
        return

    # 第2步：逐只采集行情数据
    to_process = missing[:args.max_stocks]
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    _log(f"第2步：开始采集 {len(to_process)} 只股票/指数的行情数据 (日期: {start_date}~{end_date})...")

    success_count = 0
    fail_count = 0
    total_rows = 0

    for i, stock in enumerate(to_process, 1):
        code = stock["stock_code"]
        name = stock.get("stock_name", "")
        tag = "[指数]" if _is_index(code) else "[个股]"
        _log(f"[{i}/{len(to_process)}] {tag} 处理 {code} ({name})...")

        rows = fetch_daily(code, start_date, end_date)
        if rows is None or len(rows) == 0:
            _log(f"  {code} 获取数据失败或为空，跳过")
            fail_count += 1
            continue

        # 写入数据库
        try:
            conn = connect(cfg)
            try:
                updated_rows = []
                for r in rows:
                    row_list = list(r)
                    if row_list[6] is None and name:
                        row_list[6] = name
                    updated_rows.append(tuple(row_list))

                executemany(conn, _INSERT_SQL, updated_rows)
                total_rows += len(updated_rows)
                success_count += 1
                _log(f"  {code} 写入 {len(updated_rows)} 条日线数据")
            finally:
                conn.close()
        except Exception as e:
            _log(f"  {code} 写入数据库失败: {type(e).__name__}: {e}")
            fail_count += 1

    _log("=" * 60)
    _log("数据补全脚本执行完毕")
    _log(f"结果: 成功 {success_count} 只, 失败 {fail_count} 只, 共写入 {total_rows} 条记录")
    _log(f"剩余未处理: {max(0, len(missing) - args.max_stocks)} 只（使用 --max-stocks 增加）")
    _log("=" * 60)


if __name__ == "__main__":
    main()
