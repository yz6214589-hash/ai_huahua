# -*- coding: utf-8 -*-
"""
主力行为识别 - 数据获取层

负责从 QMT 网关和数据库获取分钟级/日线级行情数据，
支持交易日判断、数据完整性检查等功能。
"""

from __future__ import annotations

import math
from datetime import datetime, date, timedelta, time
from typing import Any, Optional

from core.db import connect, load_mysql_config, query_dict
from infra.qmt_gateway_client import historical_kline
from infra.storage.logging_service import get_logger
from core.mainforce.models import TIME_RANGE_PRESETS

logger = get_logger("mainforce_engine")


class DataCollector:
    """数据获取器，负责从 QMT 网关和数据库获取行情数据"""

    def __init__(self) -> None:
        """初始化数据获取器"""
        self._cfg = load_mysql_config()

    def _get_conn(self):
        """获取数据库连接"""
        return connect(self._cfg)

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        """安全地将值转换为浮点数"""
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    # ================================================================
    # 交易日判断工具
    # ================================================================

    @staticmethod
    def _is_trading_day(dt: date) -> bool:
        """
        判断给定日期是否为交易日

        规则（按可靠性从高到低）：
        1. 周末（周六、周日）一定不是交易日
        2. 周一至周五默认是交易日（法定节假日需通过交易日历表判断，项目内暂无该表）

        注意：法定节假日的精确判断需要交易日历表，本项目暂无该表。
        """
        # 先检查周末：周一=0, 周日=6
        if dt.weekday() >= 5:  # Saturday=5, Sunday=6
            return False

        # 工作日（周一至周五）默认是交易日
        return True

    def _get_expected_bars_for_time(self, time_range: str) -> int:
        """
        获取当前时间范围下的期望数据条数

        对于"今日"，根据当前时间计算期望条数：
        - 9:30-11:30: 2小时 = 120分钟
        - 13:00-15:00: 2小时 = 120分钟
        - 总计：240分钟/天

        对于"昨日"和"近五日"，直接使用预设中定义的期望条数。
        """
        if time_range == "today":
            today = date.today()
            if not self._is_trading_day(today):
                return 0

            now = datetime.now()
            market_open = datetime.combine(today, time(9, 30))
            market_close = datetime.combine(today, time(15, 0))
            lunch_start = datetime.combine(today, time(11, 30))
            lunch_end = datetime.combine(today, time(13, 0))

            if now < market_open:
                return 0
            if now >= market_close:
                return 240

            if now < lunch_start:
                minutes_passed = (now - market_open).seconds // 60
                return minutes_passed
            elif now < lunch_end:
                return 120
            else:
                morning_minutes = 120
                afternoon_minutes = (now - lunch_end).seconds // 60
                return morning_minutes + afternoon_minutes
        else:
            return TIME_RANGE_PRESETS[time_range]["expected_bars"]

    @staticmethod
    def _get_trading_dates(time_range: str) -> tuple[date, date]:
        """
        获取指定时间范围的实际交易日期范围

        返回：(start_date, end_date)
        """
        today = date.today()

        if time_range == "today":
            return today, today
        elif time_range == "yesterday":
            yesterday = today - timedelta(days=1)
            while yesterday.weekday() >= 5:
                yesterday -= timedelta(days=1)
            return yesterday, yesterday
        else:  # last_5_days
            end_date = today
            while end_date.weekday() >= 5:
                end_date -= timedelta(days=1)

            start_date = end_date
            trading_days_found = 1
            while trading_days_found < 5:
                start_date -= timedelta(days=1)
                if start_date.weekday() < 5:
                    trading_days_found += 1

            return start_date, end_date

    # ================================================================
    # 数据获取方法
    # ================================================================

    def _fetch_stock_name(self, conn, stock_code: str) -> str:
        """从 trade_stock_master 表获取股票名称"""
        rows = query_dict(
            conn,
            "SELECT stock_name FROM trade_stock_master WHERE stock_code = %s LIMIT 1",
            (stock_code,)
        )
        if rows and rows[0].get("stock_name"):
            return str(rows[0]["stock_name"])
        return stock_code

    def _fetch_minute_data_from_db(self, conn, stock_code: str, start_date: date, end_date: date) -> list[dict]:
        """
        从数据库 trade_stock_intraday 表获取分钟级行情数据

        Args:
            conn: 数据库连接
            stock_code: 股票代码（如 "000001.SZ"）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            list[dict]: 分钟K线数据列表，按时间升序排列
        """
        sql = """
            SELECT 
                trade_date, 
                trade_time,
                price as close_price,
                avg_price,
                volume,
                amount,
                pre_close
            FROM trade_stock_intraday 
            WHERE stock_code = %s 
                AND trade_date >= %s 
                AND trade_date <= %s
            ORDER BY trade_date, trade_time
        """
        rows = query_dict(
            conn,
            sql,
            (stock_code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        )

        normalized: list[dict] = []
        for r in rows:
            price = float(r.get("close_price") or 0.0)
            normalized.append({
                "trade_date": r.get("trade_date", ""),
                "trade_time": r.get("trade_time", ""),
                "open_price": price,
                "high_price": price,
                "low_price": price,
                "close_price": price,
                "volume": int(r.get("volume") or 0),
                "amount": float(r.get("amount") or 0.0),
                "turnover_rate": 0.0,
            })

        logger.info(f"从数据库获取到 {len(normalized)} 条分钟数据", extra={
            "stock_code": stock_code,
            "start_date": str(start_date),
            "end_date": str(end_date),
        })

        return normalized

    def _fetch_minute_data_from_qmt(self, stock_code: str, time_range: str, conn=None) -> list[dict]:
        """
        通过 QMT 网关获取分钟级行情数据（如果失败则从数据库获取）

        Args:
            stock_code: 股票代码（如 "000001.SZ"）
            time_range: 时间范围（today/yesterday/last_5_days）
            conn: 可选的数据库连接，如果提供则复用

        Returns:
            list[dict]: 分钟K线数据列表，按时间升序排列
        """
        preset = TIME_RANGE_PRESETS[time_range]
        period = preset["period"]
        max_bars = preset["expected_bars"]

        start_date, end_date = self._get_trading_dates(time_range)

        start_time = start_date.strftime("%Y%m%d")
        end_time = (end_date + timedelta(days=1)).strftime("%Y%m%d")

        logger.info("===== _fetch_minute_data_from_qmt 开始 =====")
        logger.info(f"stock_code={stock_code}, time_range={time_range}")
        logger.info(f"start_date={start_date}, end_date={end_date}")
        logger.info(f"start_time={start_time}, end_time={end_time}")
        logger.info(f"period={period}, max_bars={max_bars}")

        # 先尝试从 QMT 网关获取数据
        try:
            logger.info("开始调用 historical_kline...")
            result = historical_kline(
                stock_code=stock_code,
                period=period,
                start_time=start_time,
                end_time=end_time,
                dividend_type="front",
                fill_data=False,
            )
        except Exception as e:
            logger.warning("QMT 网关获取分钟数据失败，尝试从数据库获取", extra={
                "stock_code": stock_code,
                "time_range": time_range,
                "error": str(e),
            })
            if conn:
                return self._fetch_minute_data_from_db(conn, stock_code, start_date, end_date)
            else:
                _conn = self._get_conn()
                try:
                    return self._fetch_minute_data_from_db(_conn, stock_code, start_date, end_date)
                finally:
                    _conn.close()

        rows = result.get("rows", []) if isinstance(result, dict) else []

        # 如果 QMT 返回空数据，尝试从数据库获取
        if not rows:
            logger.warning("QMT 网关返回空数据，尝试从数据库获取", extra={
                "stock_code": stock_code,
                "time_range": time_range,
            })
            if conn:
                return self._fetch_minute_data_from_db(conn, stock_code, start_date, end_date)
            else:
                _conn = self._get_conn()
                try:
                    return self._fetch_minute_data_from_db(_conn, stock_code, start_date, end_date)
                finally:
                    _conn.close()

        original_count = len(rows)
        if original_count > max_bars:
            logger.warning(f"QMT 返回数据超过期望条数: {original_count} > {max_bars}", extra={
                "stock_code": stock_code,
                "time_range": time_range,
            })

        rows = rows[-max_bars:] if len(rows) > max_bars else rows

        normalized: list[dict] = []
        for r in rows:
            normalized.append({
                "trade_date": r.get("date") or r.get("datetime", ""),
                "open_price": r.get("open", 0.0),
                "high_price": r.get("high", 0.0),
                "low_price": r.get("low", 0.0),
                "close_price": r.get("close", 0.0),
                "volume": r.get("volume", 0),
                "amount": r.get("amount", 0.0),
                "turnover_rate": 0.0,
            })

        # 检查数据完整性
        expected_bars = self._get_expected_bars_for_time(time_range)
        actual_bars = len(normalized)
        if actual_bars < expected_bars * 0.9:
            logger.warning(f"QMT数据不完整: 实际 {actual_bars} 条，期望 {expected_bars} 条，尝试从数据库补充", extra={
                "stock_code": stock_code,
                "time_range": time_range,
            })
            _conn = self._get_conn()
            try:
                db_data = self._fetch_minute_data_from_db(_conn, stock_code, start_date, end_date)
                if len(db_data) > actual_bars:
                    logger.info("数据库数据更完整，使用数据库数据", extra={
                        "stock_code": stock_code,
                        "qmt_count": actual_bars,
                        "db_count": len(db_data),
                    })
                    return db_data
            finally:
                _conn.close()

        logger.info(f"获取到 {len(normalized)} 条分钟数据", extra={
            "stock_code": stock_code,
            "time_range": time_range,
        })

        return normalized

    def _fetch_mainforce_flow(self, conn, stock_code: str, days: int) -> list[dict]:
        """从 trade_mainforce_flow 表获取主力资金流数据"""
        sql = """
            SELECT
                trade_date,
                main_inflow,
                main_outflow,
                main_netflow,
                main_inflow_ratio,
                total_volume
            FROM trade_mainforce_flow
            WHERE stock_code = %s
            ORDER BY trade_date DESC
            LIMIT %s
        """
        rows = query_dict(conn, sql, (stock_code, days))
        rows.reverse()
        return rows

    def _fetch_daily_data(self, conn, stock_code: str, days: int) -> list[dict]:
        """从 trade_stock_daily 表获取日线数据作为备选数据源"""
        sql = """
            SELECT
                trade_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                amount,
                turnover_rate
            FROM trade_stock_daily
            WHERE stock_code = %s
            ORDER BY trade_date DESC
            LIMIT %s
        """
        rows = query_dict(conn, sql, (stock_code, days))

        # 反转顺序，按时间升序排列
        rows.reverse()

        normalized: list[dict] = []
        for r in rows:
            normalized.append({
                "trade_date": r.get("trade_date", ""),
                "open_price": self._safe_float(r.get("open_price")),
                "high_price": self._safe_float(r.get("high_price")),
                "low_price": self._safe_float(r.get("low_price")),
                "close_price": self._safe_float(r.get("close_price")),
                "volume": int(r.get("volume") or 0),
                "amount": self._safe_float(r.get("amount")),
                "turnover_rate": self._safe_float(r.get("turnover_rate")),
            })

        logger.info(f"从数据库获取到 {len(normalized)} 条日线数据", extra={
            "stock_code": stock_code,
            "days": days,
        })

        return normalized

    # ================================================================
    # 辅助方法
    # ================================================================

    def _format_time_range_label(self, time_range: str) -> str:
        """
        格式化时间范围标签为具体日期显示
        """
        start_date, end_date = self._get_trading_dates(time_range)

        def _fmt(d: date) -> str:
            return f"{d.year}年{d.month}月{d.day}日"

        if time_range == "today":
            return _fmt(start_date)
        elif time_range == "yesterday":
            return _fmt(start_date)
        else:  # last_5_days
            return f"{_fmt(start_date)} - {_fmt(end_date)}"

    def fetch_data(self, stock_code: str, time_range: str = "today") -> dict[str, Any]:
        """
        一站式数据获取：获取股票名称和分钟级行情数据

        Returns:
            dict: 包含 stock_name, market_data, conn 的字典
        """
        conn = self._get_conn()
        stock_name = self._fetch_stock_name(conn, stock_code)
        market_data = self._fetch_minute_data_from_qmt(stock_code, time_range, conn)
        return {
            "stock_name": stock_name,
            "market_data": market_data,
            "conn": conn,
        }
