"""
指数日线数据管理模块

职责：
1. 多数据源获取：AKShare（主）、QMT Gateway（备1）、TuShare（备2）
2. 数据校验：格式校验、重复检查、异常值过滤
3. 存储写入：批量写入 trade_index_daily 表，INSERT ON DUPLICATE KEY 去重
4. 查询接口：供回测系统和基准加载器调用
5. 自动采集：查询时若数据不足，自动触发增量采集
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

import pandas as pd

from core.db import connect, executemany, load_mysql_config, query_dict
from core.jobs.common import safe_float
from infra.storage.logging_service import get_logger

logger = get_logger("index_data")

# 沪深交易所主要指数代码及名称映射
INDEX_META: dict[str, str] = {
    "000001.SH": "上证指数",
    "000016.SH": "上证50",
    "000300.SH": "沪深300",
    "000688.SH": "科创50",
    "000905.SH": "中证500",
    "000852.SH": "中证1000",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "399005.SZ": "中小100",
    "399673.SZ": "创业板50",
}

# AKShare 指数代码映射
_AKSHARE_INDEX_MAP: dict[str, str] = {
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

# 最大重试次数
_MAX_RETRIES = 3
# 重试间隔（秒）
_RETRY_DELAY_SEC = 2
# 批量写入最大条数
_BATCH_SIZE = 500
# 自动触发采集的天数阈值：当数据库中的数据距离当前时间超过此天数时触发
_AUTO_FETCH_THRESHOLD_DAYS = 7


@dataclass
class FetchResult:
    """数据获取结果"""
    success: bool
    rows_count: int
    data_source: str
    error_message: str | None = None
    fallback_chain: list[str] | None = None


def _is_index_code(code: str) -> bool:
    """判断是否为已知的指数代码"""
    if code in INDEX_META:
        return True
    code_num = code.split(".")[0]
    if code_num.startswith("000") and code.endswith(".SH"):
        return True
    if code_num.startswith("399") and code.endswith(".SZ"):
        return True
    return False


# ==================== 数据获取层 ====================


def _fetch_from_akshare(
    code: str,
    start: str,
    end: str,
) -> pd.DataFrame | None:
    """从 AKShare 获取指数日线数据（主数据源）

    Args:
        code: 指数代码（如 000300.SH）
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        包含 trade_date, close_price, open_price, high_price, low_price,
        volume, amount 列的 DataFrame，失败返回 None
    """
    try:
        import akshare as ak

        symbol = _AKSHARE_INDEX_MAP.get(code)
        if not symbol:
            logger.warning("指数代码不在 AKShare 映射表中", extra={"code": code})
            return None

        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty:
            logger.warning("AKShare 返回指数数据为空", extra={"code": code})
            return None

        col_map = {
            "date": "trade_date",
            "close": "close_price",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "volume": "volume",
            "amount": "amount",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "trade_date" not in df.columns or "close_price" not in df.columns:
            logger.warning("AKShare 返回数据缺少必要列", extra={"code": code, "columns": list(df.columns)})
            return None

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")

        if "open_price" in df.columns:
            df["open_price"] = pd.to_numeric(df["open_price"], errors="coerce")
        if "high_price" in df.columns:
            df["high_price"] = pd.to_numeric(df["high_price"], errors="coerce")
        if "low_price" in df.columns:
            df["low_price"] = pd.to_numeric(df["low_price"], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        df = df[(df["trade_date"] >= start_dt) & (df["trade_date"] <= end_dt)]
        df = df.dropna(subset=["close_price"])
        df = df.sort_values("trade_date").reset_index(drop=True)

        logger.info("AKShare 获取指数数据成功", extra={"code": code, "rows": len(df)})
        return df
    except ImportError:
        logger.error("AKShare 库未安装")
        return None
    except Exception as e:
        logger.error("AKShare 获取异常", extra={"code": code, "error": str(e)})
        return None


def _fetch_from_qmt(
    code: str,
    start: str,
    end: str,
) -> pd.DataFrame | None:
    """从 QMT Gateway 获取指数日线数据（备选数据源 1）

    Args:
        code: 指数代码
        start: 开始日期 (YYYYMMDD)
        end: 结束日期 (YYYYMMDD)

    Returns:
        包含 trade_date, close_price 等列的 DataFrame，失败返回 None
    """
    try:
        from infra.qmt_gateway_client import historical_kline

        start_fmt = start.replace("-", "")
        end_fmt = end.replace("-", "")

        raw = historical_kline(
            stock_code=code,
            period="1d",
            start_time=start_fmt,
            end_time=end_fmt,
            dividend_type="front",
            fill_data=True,
        )
        rows = raw.get("rows") or []
        if not rows:
            logger.warning("QMT 返回指数数据为空", extra={"code": code})
            return None

        df = pd.DataFrame(rows)
        col_map = {
            "date": "trade_date",
            "close": "close_price",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "volume": "volume",
            "amount": "amount",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "trade_date" not in df.columns or "close_price" not in df.columns:
            return None

        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
        df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")

        for col in ["open_price", "high_price", "low_price", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        df = df[(df["trade_date"] >= start_dt) & (df["trade_date"] <= end_dt)]
        df = df.dropna(subset=["close_price"])
        df = df.sort_values("trade_date").reset_index(drop=True)

        logger.info("QMT 获取指数数据成功", extra={"code": code, "rows": len(df)})
        return df
    except Exception as e:
        logger.warning("QMT 获取异常", extra={"code": code, "error": str(e)})
        return None


def _fetch_from_tushare(
    code: str,
    start: str,
    end: str,
) -> pd.DataFrame | None:
    """从 TuShare 获取指数日线数据（备选数据源 2）

    Args:
        code: 指数代码（如 000300.SH）
        start: 开始日期 (YYYYMMDD)
        end: 结束日期 (YYYYMMDD)

    Returns:
        包含 trade_date, close_price 等列的 DataFrame，失败返回 None
    """
    try:
        from infra.tushare_client import get_pro_api

        pro = get_pro_api()
        code_ts = code.replace(".SH", ".SH").replace(".SZ", ".SZ")
        df = pro.index_daily(ts_code=code_ts, start_date=start.replace("-", ""), end_date=end.replace("-", ""))
        if df is None or df.empty:
            logger.warning("TuShare 返回指数数据为空", extra={"code": code})
            return None

        col_map = {
            "trade_date": "trade_date",
            "close": "close_price",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "vol": "volume",
            "amount": "amount",
            "pre_close": "pre_close_price",
            "pct_chg": "change_pct",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "trade_date" not in df.columns or "close_price" not in df.columns:
            return None

        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
        df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")

        for col in ["open_price", "high_price", "low_price", "volume", "amount", "pre_close_price", "change_pct"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        df = df[(df["trade_date"] >= start_dt) & (df["trade_date"] <= end_dt)]
        df = df.dropna(subset=["close_price"])
        df = df.sort_values("trade_date").reset_index(drop=True)

        logger.info("TuShare 获取指数数据成功", extra={"code": code, "rows": len(df)})
        return df
    except Exception as e:
        logger.warning("TuShare 获取异常", extra={"code": code, "error": str(e)})
        return None


# 数据源链：按优先级排列
_FETCH_CHAIN: list[tuple[str, Callable]] = [
    ("akshare", _fetch_from_akshare),
    ("qmt", _fetch_from_qmt),
    ("tushare", _fetch_from_tushare),
]


def fetch_index_data(
    code: str,
    start: str,
    end: str,
) -> FetchResult:
    """按优先级链获取指数数据，带重试和回退机制

    Args:
        code: 指数代码
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        FetchResult: 获取结果，成功时 rows 包含原始数据
    """
    used_sources: list[str] = []

    for source_name, fetcher in _FETCH_CHAIN:
        for attempt in range(_MAX_RETRIES):
            try:
                df = fetcher(code, start, end)
                if df is not None and not df.empty:
                    used_sources.append(source_name)
                    return FetchResult(
                        success=True,
                        rows_count=len(df),
                        data_source=source_name,
                        fallback_chain=used_sources,
                    )
            except Exception as e:
                logger.warning(
                    "指数数据获取重试",
                    extra={
                        "source": source_name,
                        "attempt": attempt + 1,
                        "code": code,
                        "error": str(e),
                    },
                )
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY_SEC)

        used_sources.append(source_name)

    return FetchResult(
        success=False,
        rows_count=0,
        data_source="",
        error_message="所有数据源均获取失败",
        fallback_chain=used_sources,
    )


# ==================== 数据校验层 ====================


def validate_index_data(
    df: pd.DataFrame,
    code: str,
) -> pd.DataFrame:
    """校验和清洗指数数据

    Args:
        df: 待校验的 DataFrame
        code: 指数代码

    Returns:
        清洗后的 DataFrame
    """
    if df.empty:
        return df

    result = df.copy()

    # 移除异常价格（负值或零值收盘价）
    if "close_price" in result.columns:
        before = len(result)
        result = result[result["close_price"] > 0]
        if len(result) < before:
            logger.warning("移除异常收盘价数据", extra={"code": code, "removed": before - len(result)})

    # 移除重复日期（保留第一条）
    if "trade_date" in result.columns:
        before = len(result)
        result = result.drop_duplicates(subset=["trade_date"], keep="first")
        if len(result) < before:
            logger.warning("移除重复日期数据", extra={"code": code, "removed": before - len(result)})

    # 确保日期排序
    result = result.sort_values("trade_date").reset_index(drop=True)

    return result


# ==================== 数据存储层 ====================


def save_index_data(
    df: pd.DataFrame,
    code: str,
    data_source: str,
) -> int:
    """将指数数据写入 trade_index_daily 表

    使用 INSERT ... ON DUPLICATE KEY UPDATE 实现幂等写入，
    防止重复数据入库。

    Args:
        df: 待写入的 DataFrame（需包含 trade_date, close_price 列）
        code: 指数代码
        data_source: 数据来源名称

    Returns:
        int: 写入行数
    """
    if df.empty:
        return 0

    index_name = INDEX_META.get(code, "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows: list[tuple] = []
    for _, row in df.iterrows():
        trade_date = row.get("trade_date")
        if trade_date is not None and hasattr(trade_date, "strftime"):
            trade_date_str = trade_date.strftime("%Y-%m-%d")
        else:
            trade_date_str = str(trade_date)[:10] if trade_date else ""

        if not trade_date_str:
            continue

        rows.append((
            code,
            index_name,
            trade_date_str,
            safe_float(row.get("open_price")),
            safe_float(row.get("close_price")),
            safe_float(row.get("high_price")),
            safe_float(row.get("low_price")),
            safe_float(row.get("pre_close_price")),
            safe_float(row.get("change_pct")),
            safe_float(row.get("volume")),
            safe_float(row.get("amount")),
            data_source,
            now_str,
        ))

    if not rows:
        return 0

    sql = """
        INSERT INTO trade_index_daily
        (index_code, index_name, trade_date,
         open_price, close_price, high_price, low_price,
         pre_close_price, change_pct,
         volume, amount,
         data_source, collected_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            close_price = VALUES(close_price),
            open_price = VALUES(open_price),
            high_price = VALUES(high_price),
            low_price = VALUES(low_price),
            pre_close_price = VALUES(pre_close_price),
            change_pct = VALUES(change_pct),
            volume = VALUES(volume),
            amount = VALUES(amount),
            data_source = VALUES(data_source),
            collected_at = VALUES(collected_at)
    """

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            total = 0
            for i in range(0, len(rows), _BATCH_SIZE):
                batch = rows[i:i + _BATCH_SIZE]
                affected = executemany(conn, sql, batch)
                total += affected
            logger.info("指数数据写入成功", extra={"code": code, "rows": len(rows), "affected": total})
            return total
        finally:
            conn.close()
    except Exception as e:
        logger.error("指数数据写入失败", extra={"code": code, "error": str(e)})
        return 0


# ==================== 查询接口层 ====================


def query_index_data(
    code: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """从 trade_index_daily 表查询指数数据

    Args:
        code: 指数代码
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        包含 trade_date, close_price 等列的 DataFrame，查不到返回空 DataFrame
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                """
                SELECT trade_date, close_price, open_price, high_price, low_price,
                       volume, amount, change_pct, data_source
                FROM trade_index_daily
                WHERE index_code = %s AND trade_date >= %s AND trade_date <= %s
                ORDER BY trade_date ASC
                """,
                (code, start, end),
            )
            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.dropna(subset=["close_price"])
            return df
        finally:
            conn.close()
    except Exception as e:
        logger.error("查询指数数据异常", extra={"code": code, "error": str(e)})
        return pd.DataFrame()


def check_data_freshness(
    code: str,
    start: str,
    end: str,
) -> tuple[bool, str]:
    """检查指数数据的完整性和时效性

    Args:
        code: 指数代码
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        (是否完整, 描述信息)
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                """
                SELECT MIN(trade_date) AS min_date, MAX(trade_date) AS max_date,
                       COUNT(*) AS total_days
                FROM trade_index_daily
                WHERE index_code = %s AND trade_date >= %s AND trade_date <= %s
                """,
                (code, start, end),
            )
            if not rows or rows[0]["total_days"] == 0:
                return (False, "数据库中无该指数数据")

            row = rows[0]
            min_date = row["min_date"]
            max_date = row["max_date"]
            total_days = row["total_days"]

            start_dt = pd.to_datetime(start).date()
            end_dt = pd.to_datetime(end).date()

            # 检查范围覆盖
            if min_date > start_dt:
                return (False, f"数据起始日期 {min_date} 晚于需求起始日期 {start}")

            # 检查时效性
            days_gap = (end_dt - max_date).days
            if days_gap > _AUTO_FETCH_THRESHOLD_DAYS:
                return (False, f"数据最新日期 {max_date}，距今 {days_gap} 天，超过阈值 {_AUTO_FETCH_THRESHOLD_DAYS} 天")

            return (True, f"数据完整，共 {total_days} 条，范围 {min_date} ~ {max_date}")
        finally:
            conn.close()
    except Exception as e:
        return (False, f"检查数据状态异常: {str(e)}")


def _fetch_and_store(
    code: str,
    start: str,
    end: str,
) -> bool:
    """采集并存储指数数据（一步完成）

    按优先级链逐个尝试数据源，成功后立即校验并写入数据库。

    Args:
        code: 指数代码
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        bool: 是否成功采集并存储了数据
    """
    for source_name, fetcher in _FETCH_CHAIN:
        for attempt in range(_MAX_RETRIES):
            try:
                df = fetcher(code, start, end)
                if df is not None and not df.empty:
                    validated = validate_index_data(df, code)
                    saved = save_index_data(validated, code, source_name)
                    logger.info("指数数据采集并存储完成", extra={"code": code, "source": source_name, "saved": saved})
                    return True
            except Exception as e:
                logger.warning("指数数据采集重试", extra={"source": source_name, "attempt": attempt + 1, "code": code, "error": str(e)})
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY_SEC)
    return False


def ensure_index_data(
    code: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """确保指数数据可用：查表 -> 检查完整性 -> 自动采集 -> 返回数据

    这是回测系统调用的统一入口，实现：
    1. 先查 trade_index_daily 表
    2. 检查数据是否覆盖所需时间范围
    3. 若数据不足，自动触发多源采集
    4. 采集完成写入后，再次查询返回

    Args:
        code: 指数代码
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        包含 trade_date, close_price 列的 DataFrame
    """
    # 先查数据库
    df = query_index_data(code, start, end)

    # 检查数据完整性和时效性
    is_fresh, msg = check_data_freshness(code, start, end)

    if is_fresh and not df.empty:
        logger.info("指数数据命中缓存", extra={"code": code, "rows": len(df)})
        return df

    # 数据不足，触发自动采集
    logger.info("触发指数数据采集", extra={"code": code, "start": start, "end": end, "reason": msg})

    success = _fetch_and_store(code, start, end)

    if not success and not df.empty:
        # 采集失败但数据库有部分数据，返回已有数据
        logger.warning("增量采集失败，使用已有数据", extra={"code": code, "rows": len(df)})
        return df

    # 采集完成后重新查询
    return query_index_data(code, start, end)


# ==================== 公开便捷函数 ====================


def get_index_name(code: str) -> str:
    """获取指数中文名称"""
    return INDEX_META.get(code, "")


def list_all_index_codes() -> list[str]:
    """获取所有支持的指数代码列表"""
    return list(INDEX_META.keys())


def get_index_data_for_benchmark(
    code: str,
    start: str,
    end: str,
    initial_cash: float = 100000.0,
) -> list[dict[str, Any]]:
    """为回测基准计算提供指数净值序列（benchmark_loader 调用此函数）

    这是 benchmark_loader.py 的替代查询入口，
    提供与 calc_benchmark_nav 相同的返回格式。

    Args:
        code: 指数代码
        start: 开始日期
        end: 结束日期
        initial_cash: 初始资金

    Returns:
        基准净值列表 [{"date": "...", "nav": ...}]
    """
    df = ensure_index_data(code, start, end)
    if df.empty:
        return []

    first_close = float(df["close_price"].iloc[0])
    if first_close <= 0:
        return []

    nav_log: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        nav = initial_cash * (float(row["close_price"]) / first_close)
        date_str = row["trade_date"].strftime("%Y-%m-%d") if pd.notna(row["trade_date"]) else ""
        nav_log.append({"date": date_str, "nav": round(nav, 2)})

    return nav_log
