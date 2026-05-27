"""
个股分时图 API 模块
提供个股的1分钟级别分时数据查询，支持多数据源自动降级
数据源优先级：QMT Gateway > TuShare > AkShare
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from core.db import connect, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("intraday")
router = APIRouter(prefix="/api/v1", tags=["intraday"])


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _get_conn_qd() -> tuple[Any, Any]:
    try:
        cfg = load_mysql_config()
        return connect(cfg), query_dict
    except Exception:
        return None, None


def _norm(code: str) -> str:
    c = str(code or "").strip().upper()
    if "." not in c:
        if c.startswith("6"):
            c += ".SH"
        elif c.startswith(("0", "3")):
            c += ".SZ"
    return c


def _to_float(v: Any) -> float | None:
    """安全转换为 float"""
    if v is None:
        return None
    try:
        f = float(v)
        return f if float("inf") > f > float("-inf") else None
    except (ValueError, TypeError):
        return None


def _to_int(v: Any) -> int | None:
    """安全转换为 int"""
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 建表逻辑（模块加载时自动执行）
# ---------------------------------------------------------------------------

_DDL_SQL = """CREATE TABLE IF NOT EXISTS trade_stock_intraday (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码，如600519.SH',
    trade_date DATE NOT NULL COMMENT '交易日期',
    trade_time VARCHAR(10) NOT NULL COMMENT '交易时间 HH:MM 格式',
    price DECIMAL(18,6) DEFAULT NULL COMMENT '当前分钟价格',
    avg_price DECIMAL(18,6) DEFAULT NULL COMMENT '当前均价（从开盘到当前分钟的成交均价）',
    volume BIGINT DEFAULT NULL COMMENT '当前分钟成交量（股）',
    amount DECIMAL(18,4) DEFAULT NULL COMMENT '当前分钟成交额',
    pre_close DECIMAL(18,6) DEFAULT NULL COMMENT '前一日收盘价',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_date_time (stock_code, trade_date, trade_time),
    INDEX idx_stock_date (stock_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个股分时数据'"""


def _ensure_table():
    """确保分时数据表存在，在模块加载时自动执行"""
    conn = None
    try:
        conn, _ = _get_conn_qd()
        if conn:
            with conn.cursor() as cur:
                cur.execute(_DDL_SQL)
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


_ensure_table()


# ---------------------------------------------------------------------------
# 交易日判断
# ---------------------------------------------------------------------------

def _is_trading_day(d: date) -> bool:
    """判断是否为交易日。简单策略：周一至周五即为交易日"""
    return d.weekday() < 5  # 0=周一, 4=周五


def _prev_trade_day(d: date) -> date:
    """获取前一个交易日"""
    prev = d - timedelta(days=1)
    while not _is_trading_day(prev):
        prev = prev - timedelta(days=1)
    return prev


def _get_trade_date() -> date:
    """获取应展示的交易日期。
    如果今天是交易日且当前时间在 9:15 之后，返回今天；
    否则返回上一个交易日。"""
    today = date.today()
    now = datetime.now()

    # 如果不是交易日，返回上一个交易日
    if not _is_trading_day(today):
        return _prev_trade_day(today)

    # 如果是交易日但时间在 9:15（集合竞价开始）之前，返回上一个交易日
    trade_start = datetime(today.year, today.month, today.day, 9, 15)
    if now < trade_start:
        return _prev_trade_day(today)

    return today


# ---------------------------------------------------------------------------
# 数据获取函数（优先级从高到低）
# ---------------------------------------------------------------------------

def _fetch_intraday_from_qmt(stock_code: str, trade_date: str) -> list[dict] | None:
    """通过 QMT Gateway 获取分时数据（优先级1）。
    返回格式统一的 list[dict]，失败返回 None。
    """
    try:
        from infra.qmt_gateway_client import (
            QMTConnectionError,
            QMTGatewayError,
            historical_kline,
        )

        # QMT 要求日期格式为 YYYYMMDD
        qmt_date = trade_date.replace("-", "")
        result = historical_kline(
            stock_code=stock_code,
            period="1m",
            start_time=qmt_date,
            end_time=qmt_date,
            dividend_type="none",
            fill_data=False,
        )
        rows = result.get("rows") or []
        if not rows:
            logger.info("QMT 分时数据为空", extra={"stock_code": stock_code, "trade_date": trade_date})
            return None

        # 解析 QMT 返回的行数据
        # 每行格式：{"date": "2025-05-23 09:30:00", "open": ..., "close": ..., "volume": ..., "amount": ...}
        data: list[dict] = []
        for row in rows:
            dt_str = str(row.get("date", ""))
            # 提取 HH:MM 部分
            time_part = ""
            if " " in dt_str:
                time_part = dt_str.split(" ")[1][:5]
            elif "T" in dt_str:
                time_part = dt_str.split("T")[1][:5]
            if not time_part:
                continue

            data.append({
                "trade_time": time_part,
                "price": _to_float(row.get("close")),
                "volume": _to_int(row.get("volume")),
                "amount": _to_float(row.get("amount")),
            })

        if not data:
            return None

        logger.info("从 QMT 获取分时数据成功",
                    extra={"stock_code": stock_code, "trade_date": trade_date, "count": len(data)})
        return data
    except (QMTConnectionError, QMTGatewayError) as e:
        logger.warning("QMT 分时数据获取失败", extra={"stock_code": stock_code, "error": str(e)})
        return None
    except Exception as e:
        logger.warning("QMT 分时数据获取异常", extra={"stock_code": stock_code, "error": str(e)})
        return None


def _fetch_intraday_from_tushare(stock_code: str, trade_date: str) -> list[dict] | None:
    """通过 TuShare 获取分时数据（优先级2）。
    返回格式统一的 list[dict]，失败返回 None。
    注意：TuShare 的 stk_mins 接口需要较高积分，免费版通常不可用。
    """
    try:
        from infra.tushare_client import get_pro_api

        pro = get_pro_api()
        # TuShare 日期格式：YYYYMMDD
        ts_date = trade_date.replace("-", "")
        df = pro.stk_mins(ts_code=stock_code, freq="1min", start_date=ts_date, end_date=ts_date)
        if df is None or len(df) == 0:
            logger.info("TuShare 分时数据为空", extra={"stock_code": stock_code, "trade_date": trade_date})
            return None

        data: list[dict] = []
        for _, row in df.iterrows():
            trade_time = str(row.get("trade_time", ""))
            # TuShare 返回的时间可能是 "09:30:00" 格式
            if len(trade_time) >= 5:
                trade_time = trade_time[:5]

            data.append({
                "trade_time": trade_time,
                "price": _to_float(row.get("close")),
                "volume": (_to_int(row.get("vol")) or 0) * 100,  # TuShare 返回手数，乘以100转为股数
                "amount": _to_float(row.get("amount")),
            })

        if not data:
            return None

        logger.info("从 TuShare 获取分时数据成功",
                    extra={"stock_code": stock_code, "trade_date": trade_date, "count": len(data)})
        return data
    except Exception as e:
        logger.warning("TuShare 分时数据获取失败", extra={"stock_code": stock_code, "error": str(e)})
        return None


def _akshare_code(stock_code: str) -> str:
    """将 600519.SH 格式转换为 AkShare 股票代码格式"""
    code_num = stock_code.split(".")[0]
    suffix = stock_code.split(".")[-1].upper() if "." in stock_code else ""
    # stock_zh_a_minute 使用 sh/sz 前缀
    if suffix == "SH":
        return f"sh{code_num}"
    elif suffix == "SZ":
        return f"sz{code_num}"
    return code_num


def _fetch_intraday_from_akshare(stock_code: str, trade_date: str) -> list[dict] | None:
    """通过 AkShare 获取分时数据（优先级3，免费数据源）。
    优先使用 stock_zh_a_hist_min_em，失败回退到 stock_zh_a_minute。
    返回格式统一的 list[dict]，失败返回 None。
    """
    try:
        import akshare as ak

        # 提取纯数字代码（去除 .SH/.SZ 后缀）
        code_num = stock_code.split(".")[0]
        data: list[dict] | None = None

        # 方法1：尝试 stock_zh_a_hist_min_em（东方财富历史分钟K线）
        try:
            start_dt = f"{trade_date} 09:30:00"
            end_dt = f"{trade_date} 15:00:00"
            df = ak.stock_zh_a_hist_min_em(
                symbol=code_num,
                period="1",
                start_date=start_dt,
                end_date=end_dt,
                adjust="",
            )
            if df is not None and len(df) > 0:
                raw_data: list[dict] = []
                for _, row in df.iterrows():
                    time_str = str(row.get("时间", ""))
                    if len(time_str) > 5:
                        if " " in time_str:
                            time_str = time_str.split(" ")[1][:5]
                        else:
                            time_str = time_str[-8:][:5] if len(time_str) >= 8 else time_str[:5]
                    if not time_str or len(time_str) > 5:
                        continue
                    raw_data.append({
                        "trade_time": time_str,
                        "price": _to_float(row.get("收盘")),
                        "volume": (_to_int(row.get("成交量")) or 0) * 100,
                        "amount": _to_float(row.get("成交额")),
                    })
                if raw_data:
                    data = raw_data
                    logger.info("从 AkShare(stock_zh_a_hist_min_em) 获取分时数据成功",
                                extra={"stock_code": stock_code, "trade_date": trade_date, "count": len(data)})
        except Exception as e1:
            logger.info("AkShare stock_zh_a_hist_min_em 失败",
                        extra={"stock_code": stock_code, "error": str(e1)})

        # 方法2：回退到 stock_zh_a_minute（Sina 分钟数据，更稳定）
        if not data:
            try:
                aks_code = _akshare_code(stock_code)
                df = ak.stock_zh_a_minute(symbol=aks_code, period="1")
                if df is not None and len(df) > 0:
                    target_date = trade_date
                    raw_data = []
                    for _, row in df.iterrows():
                        day_str = str(row.get("day", ""))
                        # day 格式如 "2026-05-22 09:31:00"
                        row_date = day_str[:10] if len(day_str) >= 10 else ""
                        if row_date != target_date:
                            continue
                        time_str = day_str[11:16] if len(day_str) >= 16 else ""
                        if not time_str:
                            continue
                        raw_data.append({
                            "trade_time": time_str,
                            "price": _to_float(row.get("close")),
                            "volume": _to_int(row.get("volume")),
                            "amount": _to_float(row.get("amount")),
                        })
                    if raw_data:
                        data = raw_data
                        logger.info("从 AkShare(stock_zh_a_minute) 获取分时数据成功",
                                    extra={"stock_code": stock_code, "trade_date": trade_date, "count": len(data)})
            except Exception as e2:
                logger.info("AkShare stock_zh_a_minute 失败",
                            extra={"stock_code": stock_code, "error": str(e2)})

        if not data:
            return None

        # 按时间排序
        data.sort(key=lambda x: x["trade_time"])

        return data
    except Exception as e:
        logger.warning("AkShare 分时数据获取失败", extra={"stock_code": stock_code, "error": str(e)})
        return None


# ---------------------------------------------------------------------------
# avg_price 计算 & pre_close 获取
# ---------------------------------------------------------------------------

def _compute_avg_price(data: list[dict]) -> None:
    """在原始数据上就地计算 avg_price 字段。
    avg_price = 累计成交额 / 累计成交量，如果无成交量数据则用当前价格近似。
    """
    cum_amount: float = 0.0
    cum_volume: int = 0

    for row in data:
        vol = row.get("volume") or 0
        amt = row.get("amount") or 0.0
        price = row.get("price")

        cum_volume += int(vol)
        cum_amount += float(amt)

        if cum_volume > 0 and cum_amount > 0:
            row["avg_price"] = round(cum_amount / cum_volume, 6)
        else:
            row["avg_price"] = price


def _get_pre_close(conn, qd, stock_code: str, trade_date: str, data: list[dict]) -> float | None:
    """获取前一日收盘价。
    优先从传入的 data 中提取，其次从数据库 trade_stock_daily 表查询。
    """
    # 尝试从数据中获取（如果数据源提供了 pre_close）
    if data:
        first = data[0]
        if "pre_close" in first and first["pre_close"] is not None:
            return _to_float(first["pre_close"])

    # 从数据库获取前一日数据
    if conn and qd:
        try:
            target_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
            prev_dt = target_dt - timedelta(days=1)
            # 向前查询最多7天（跳过周末和节假日可能的空白）
            for _ in range(7):
                prev_str = prev_dt.strftime("%Y-%m-%d")
                rows = qd(conn,
                    "SELECT close_price FROM trade_stock_daily WHERE stock_code=%s AND trade_date=%s",
                    (stock_code, prev_str))
                if rows and rows[0].get("close_price") is not None:
                    return _to_float(rows[0]["close_price"])
                prev_dt = prev_dt - timedelta(days=1)
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# 数据保存
# ---------------------------------------------------------------------------

_SAVE_SQL = """INSERT INTO trade_stock_intraday
    (stock_code, trade_date, trade_time, price, avg_price, volume, amount, pre_close)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    price=VALUES(price), avg_price=VALUES(avg_price),
    volume=VALUES(volume), amount=VALUES(amount), pre_close=VALUES(pre_close)"""


def _save_intraday_data(conn, stock_code: str, trade_date: str, rows: list[dict]) -> None:
    """将分时数据保存到 MySQL。使用 INSERT ... ON DUPLICATE KEY UPDATE 实现覆盖更新。"""
    if not rows:
        return

    try:
        params_list: list[tuple] = []
        for r in rows:
            params_list.append((
                stock_code,
                trade_date,
                r.get("trade_time", ""),
                r.get("price"),
                r.get("avg_price"),
                r.get("volume"),
                r.get("amount"),
                r.get("pre_close"),
            ))
        with conn.cursor() as cur:
            cur.executemany(_SAVE_SQL, params_list)
        logger.info("分时数据保存成功",
                    extra={"stock_code": stock_code, "trade_date": trade_date, "count": len(rows)})
    except Exception as e:
        logger.error("分时数据保存失败", extra={"stock_code": stock_code, "error": str(e)})


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.get("/stock/{code}/intraday")
def stock_intraday(
    code: str,
    date_param: str = Query(default="", alias="date"),
) -> dict[str, Any]:
    """获取个股分时数据。

    流程：
    1. 标准化股票代码
    2. 确定目标日期（指定或自动判断）
    3. 先查数据库缓存
    4. 若无缓存，按优先级从 QMT / TuShare / AkShare 获取
    5. 补充 avg_price 和 pre_close
    6. 保存数据到数据库并返回
    """
    c = _norm(code)
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        # 确定目标交易日期
        if date_param:
            # 用户指定了日期
            try:
                target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                target_date_str = target_date.strftime("%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        else:
            target_date = _get_trade_date()
            target_date_str = target_date.strftime("%Y-%m-%d")

        is_trading_today = _is_trading_day(date.today()) and target_date == date.today()

        # 先查询数据库是否已有缓存数据
        cached_rows = qd(conn,
            """SELECT stock_code, trade_date, trade_time, price, avg_price, volume, amount, pre_close
               FROM trade_stock_intraday
               WHERE stock_code=%s AND trade_date=%s
               ORDER BY trade_time""",
            (c, target_date_str))

        if cached_rows and len(cached_rows) > 0:
            minute_data = []
            pre_close = None
            for r in cached_rows:
                if pre_close is None:
                    pre_close = _to_float(r.get("pre_close"))
                minute_data.append({
                    "time": r.get("trade_time"),
                    "price": _to_float(r.get("price")),
                    "avg_price": _to_float(r.get("avg_price")),
                    "volume": _to_int(r.get("volume")),
                })

            return {
                "stock_code": c,
                "trade_date": target_date_str,
                "pre_close": pre_close,
                "is_trading_today": is_trading_today,
                "data_source": "cache",
                "minute_data": minute_data,
            }

        # 数据库无缓存，按优先级尝试获取数据
        data: list[dict] | None = None
        data_source: str = ""

        # 优先级1: QMT Gateway
        data = _fetch_intraday_from_qmt(c, target_date_str)
        if data:
            data_source = "qmt"

        # 优先级2: TuShare
        if not data:
            data = _fetch_intraday_from_tushare(c, target_date_str)
            if data:
                data_source = "tushare"

        # 优先级3: AkShare
        if not data:
            data = _fetch_intraday_from_akshare(c, target_date_str)
            if data:
                data_source = "akshare"

        if not data:
            # 所有数据源均不可用
            return {
                "stock_code": c,
                "trade_date": target_date_str,
                "pre_close": None,
                "is_trading_today": is_trading_today,
                "data_source": "none",
                "minute_data": [],
            }

        # 计算 avg_price
        _compute_avg_price(data)

        # 获取 pre_close
        pre_close = _get_pre_close(conn, qd, c, target_date_str, data)

        # 将 pre_close 写入每条数据记录
        for r in data:
            r["pre_close"] = pre_close

        # 保存到数据库
        _save_intraday_data(conn, c, target_date_str, data)

        # 构建响应
        minute_data = [
            {
                "time": r["trade_time"],
                "price": r.get("price"),
                "avg_price": r.get("avg_price"),
                "volume": r.get("volume"),
            }
            for r in data
        ]

        return {
            "stock_code": c,
            "trade_date": target_date_str,
            "pre_close": pre_close,
            "is_trading_today": is_trading_today,
            "data_source": data_source,
            "minute_data": minute_data,
        }

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 板块轮动数据
# ---------------------------------------------------------------------------

@router.get("/intraday/sectors")
def get_sector_rotation(
    date_param: str = Query(default="", alias="date"),
    sort: str = Query(default="inflow", alias="sort"),
) -> dict[str, Any]:
    """
    获取板块轮动数据。

    从 trade_sector_daily 表查询指定日期的板块数据，
    支持按主力净流入或涨跌幅排序。

    Args:
        date_param: 交易日期（YYYY-MM-DD），不传则查询最新交易日
        sort: 排序方式 inflow（按成交额排序）/ change（按涨跌幅排序）

    Returns:
        dict: 包含 items（板块列表）和 total（总数）
    """
    logger.info("板块轮动数据请求", extra={
        "date": date_param or "auto",
        "sort": sort,
    })
    conn, qd = _get_conn_qd()
    if conn is None or qd is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        # 确定目标日期
        if date_param:
            try:
                target_date = date_param
                datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
        else:
            # 查询 trade_sector_daily 中最新的交易日期
            latest_rows = qd(conn, "SELECT MAX(trade_date) as max_date FROM trade_sector_daily", ())
            if not latest_rows or not latest_rows[0].get("max_date"):
                return {"items": [], "total": 0}
            max_dt = latest_rows[0]["max_date"]
            if hasattr(max_dt, "strftime"):
                target_date = max_dt.strftime("%Y-%m-%d")
            else:
                target_date = str(max_dt)

        # 确定排序字段
        sort_column = "amount" if sort == "inflow" else "change_pct"
        sort_order = "DESC"

        # 查询板块数据
        sql = f"""
            SELECT
                sector_code,
                sector_name,
                sector_level,
                trade_date,
                change_pct,
                amount,
                composite_score,
                rank_position,
                phase,
                strength_score
            FROM trade_sector_daily
            WHERE trade_date = %s AND sector_level = 1
            ORDER BY {sort_column} {sort_order}
        """
        rows = qd(conn, sql, (target_date,))

        # 对于每个板块，尝试获取3日涨跌幅（通过查询前3个交易日的数据）
        items = []
        for row in rows:
            sector_code = row.get("sector_code", "")
            sector_name = row.get("sector_name", "")

            # 查询前3日涨跌幅
            change_3d_sql = """
                SELECT change_pct FROM trade_sector_daily
                WHERE sector_code = %s AND sector_level = 1 AND trade_date < %s
                ORDER BY trade_date DESC LIMIT 1 OFFSET 2
            """
            change_3d_rows = qd(conn, change_3d_sql, (sector_code, target_date))
            change_3d_val = None
            if change_3d_rows and change_3d_rows[0].get("change_pct") is not None:
                current_pct = _to_float(row.get("change_pct")) or 0
                prev_3d_pct = _to_float(change_3d_rows[0]["change_pct"]) or 0
                # 3日涨跌幅 = (1 + 今日%) * (1 + 昨日%) * (1 + 前日%) - 1 的近似
                # 改用累计涨跌幅差值
                change_3d_val = round(current_pct - prev_3d_pct, 4)

            # 查询板块内top股票
            top_stocks_sql = """
                SELECT m.stock_code, m.stock_name, d.change_pct
                FROM trade_stock_daily d
                JOIN trade_stock_master m ON d.stock_code = m.stock_code
                WHERE m.sector_level1 = %s AND d.trade_date = %s
                ORDER BY d.change_pct DESC
                LIMIT 5
            """
            top_rows = qd(conn, top_stocks_sql, (sector_name, target_date))
            top_stocks = []
            for ts in top_rows:
                top_stocks.append({
                    "code": ts.get("stock_code", ""),
                    "name": ts.get("stock_name", ""),
                    "change_pct": _to_float(ts.get("change_pct")),
                })

            amount_val = _to_float(row.get("amount"))
            # 将 amount（元）转为亿元
            net_inflow_val = round(amount_val / 100000000, 2) if amount_val else 0

            items.append({
                "name": sector_name,
                "change_pct": _to_float(row.get("change_pct")),
                "change_3d": change_3d_val,
                "net_inflow": net_inflow_val,
                "turnover": net_inflow_val,
                "top_stocks": top_stocks,
                "hot_rank": _to_int(row.get("rank_position")),
            })

        logger.info("板块轮动数据查询完成",
                    extra={"date": target_date, "count": len(items)})

        return {
            "items": items,
            "total": len(items),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("板块轮动数据查询失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"板块轮动数据查询失败: {str(e)}")
    finally:
        conn.close()
