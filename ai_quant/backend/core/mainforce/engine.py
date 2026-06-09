# -*- coding: utf-8 -*-
"""
主力行为识别核心引擎

支持日线和分钟级别的行情数据分析。
通过时间范围参数（今日/昨日/近五日）从 QMT 网关获取分钟级数据，
提取10大微观结构特征后通过规则引擎分类主力类型。

10大微观结构特征（与参考代码 7-主力行为识别.py L198-287 保持一致）:
    1. ofi_abs             - 订单流不平衡 (OFI) 绝对值
    2. large_ratio         - 大单比例（成交额超均值3倍的比例）
    3. cancel_rate         - 撤单率（从K线形态近似）
    4. interval_cv         - 成交节奏规律性（变异系数）
    5. recovery_speed      - 价格冲击恢复速度
    6. run_length          - 方向持续性（连续同方向平均长度）
    7. vol_cv              - 成交量变异系数
    8. direction_symmetry  - 方向对称性（买卖笔数差异）
    9. limit_ratio         - 限价单比例（从K线形态近似）
   10. price_volatility    - 价格波动率
"""

from __future__ import annotations

import math
from datetime import datetime, date, timedelta, time
from typing import Any, Optional

from core.db import connect, load_mysql_config, query_dict, execute
from infra.qmt_gateway_client import historical_kline
from infra.storage.logging_service import get_logger

logger = get_logger("mainforce_engine")


# 时间范围预设值：定义每个时间范围对应的分钟数据周期和特征窗口
TIME_RANGE_PRESETS: dict[str, dict[str, Any]] = {
    "today": {
        "label": "今日",
        "period": "1m",
        "window": 60,           # 特征计算窗口（60个1分钟K线）
        "min_bars": 20,         # 最少需要的数据条数
        "expected_bars": 240,   # 期望数据条数（完整交易日）
    },
    "yesterday": {
        "label": "昨日",
        "period": "1m",
        "window": 60,
        "min_bars": 20,
        "expected_bars": 240,   # 完整交易日约240根1分钟K线
    },
    "last_5_days": {
        "label": "近五日",
        "period": "1m",
        "window": 60,
        "min_bars": 100,
        "expected_bars": 1200,  # 5天 × 240根
    },
}


class MainForceEngine:
    """
    主力行为识别引擎

    支持日线和分钟级别的行情数据特征提取和主力类型分类。
    """

    # 主力类型常量
    TYPE_INSTITUTION = "institution"   # 机构主力
    TYPE_HOT_MONEY = "hot_money"       # 游资
    TYPE_RETAIL = "retail"             # 散户

    # 主力类型中文名称映射
    TYPE_LABELS = {
        "institution": "机构主力",
        "hot_money": "游资",
        "retail": "散户",
    }

    def __init__(self) -> None:
        """初始化引擎"""
        self._cfg = load_mysql_config()

    def _get_conn(self):
        """获取数据库连接"""
        return connect(self._cfg)

    # ================================================================
    # 交易日判断工具
    # ================================================================

    def _is_trading_day(self, dt: date) -> bool:
        """
        判断给定日期是否为交易日

        规则（按可靠性从高到低）：
        1. 周末（周六、周日）一定不是交易日
        2. 周一至周五默认是交易日（法定节假日需通过交易日历表判断，项目内暂无该表）
        3. 数据库中有该日线数据，进一步确认是交易日
        4. 数据库中无该日线数据但日期是工作日，仍然判定为交易日（数据可能尚未同步）

        注意：法定节假日的精确判断需要交易日历表，本项目暂无该表。
        """
        # 1. 先检查周末：周一=0, 周日=6
        if dt.weekday() >= 5:  # Saturday=5, Sunday=6
            return False

        # 2. 工作日（周一至周五）默认是交易日
        # 注：精确的法定节假日判断需要外部交易日历数据，本项目暂无该数据源
        return True

    def _get_expected_bars_for_time(self, time_range: str) -> int:
        """
        获取当前时间范围下的期望数据条数

        对于"今日"，根据当前时间计算期望条数：
        - 9:30-11:30: 2小时 = 120分钟
        - 13:00-15:00: 2小时 = 120分钟
        - 总计：240分钟/天

        对于"昨日"和"近五日"，直接使用预设中定义的期望条数（按交易日计算）：
        - 昨日 = 1 个交易日 × 240 根 = 240
        - 近五日 = 5 个交易日 × 240 根 = 1200

        如果今日不是交易日，返回0
        """
        if time_range == "today":
            # 检查今日是否为交易日
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

            # 计算已过去的交易分钟数
            if now < lunch_start:
                minutes_passed = (now - market_open).seconds // 60
                return minutes_passed
            elif now < lunch_end:
                return 120  # 上午全部完成
            else:
                morning_minutes = 120
                afternoon_minutes = (now - lunch_end).seconds // 60
                return morning_minutes + afternoon_minutes
        else:
            # 对于"昨日"和"近五日"，直接使用预设中定义的期望条数
            # "近五日"指5个交易日（不是自然日），每天约240根1分钟K线
            return TIME_RANGE_PRESETS[time_range]["expected_bars"]

    def _get_trading_dates(self, time_range: str) -> tuple[date, date]:
        """
        获取指定时间范围的实际交易日期范围

        返回：(start_date, end_date)
        """
        today = date.today()

        if time_range == "today":
            return today, today
        elif time_range == "yesterday":
            yesterday = today - timedelta(days=1)
            # 如果昨天是周末，往前找最近的交易日
            while yesterday.weekday() >= 5:
                yesterday -= timedelta(days=1)
            return yesterday, yesterday
        else:  # last_5_days
            end_date = today
            # 如果今天不是交易日，找最近的交易日
            while end_date.weekday() >= 5:
                end_date -= timedelta(days=1)

            # 往前找5个交易日
            start_date = end_date
            trading_days_found = 1
            while trading_days_found < 5:
                start_date -= timedelta(days=1)
                if start_date.weekday() < 5:  # 不是周末
                    trading_days_found += 1

            return start_date, end_date

    # ================================================================
    # 数据获取层
    # ================================================================

    def _fetch_stock_name(self, conn, stock_code: str) -> str:
        """
        从 trade_stock_master 表获取股票名称
        """
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
            # 由于 intraday 表没有 open/high/low，我们用价格字段填充
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
        max_bars = preset["expected_bars"]  # 使用期望条数作为上限

        # 获取实际交易日范围
        start_date, end_date = self._get_trading_dates(time_range)

        start_time = start_date.strftime("%Y%m%d")
        end_time = (end_date + timedelta(days=1)).strftime("%Y%m%d")

        logger.info(f"===== _fetch_minute_data_from_qmt 开始 =====")
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

        # 记录原始数据条数用于调试
        original_count = len(rows)
        if original_count > max_bars:
            logger.warning(f"QMT 返回数据超过期望条数: {original_count} > {max_bars}", extra={
                "stock_code": stock_code,
                "time_range": time_range,
            })

        # 限制最大条数并按时间升序（取最新的）
        rows = rows[-max_bars:] if len(rows) > max_bars else rows

        # 统一字段名（分钟数据可能用 datetime 字段）
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
                "turnover_rate": 0.0,  # 分钟级别没有换手率字段
            })

        # 检查数据完整性
        expected_bars = self._get_expected_bars_for_time(time_range)
        actual_bars = len(normalized)
        if actual_bars < expected_bars * 0.9:
            logger.warning(f"QMT数据不完整: 实际 {actual_bars} 条，期望 {expected_bars} 条，尝试从数据库补充", extra={
                "stock_code": stock_code,
                "time_range": time_range,
            })
            conn = self._get_conn()
            try:
                db_data = self._fetch_minute_data_from_db(conn, stock_code, start_date, end_date)
                if len(db_data) > actual_bars:
                    logger.info(f"数据库数据更完整，使用数据库数据", extra={
                        "stock_code": stock_code,
                        "qmt_count": actual_bars,
                        "db_count": len(db_data),
                    })
                    return db_data
            finally:
                conn.close()

        logger.info(f"获取到 {len(normalized)} 条分钟数据", extra={
            "stock_code": stock_code,
            "time_range": time_range,
        })

        return normalized

    def _fetch_mainforce_flow(self, conn, stock_code: str, days: int) -> list[dict]:
        """
        从 trade_mainforce_flow 表获取主力资金流数据
        """
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
        """
        从 trade_stock_daily 表获取日线数据作为备选数据源
        """
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
        
        # 标准化字段名
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
    # 微观结构特征提取（与参考代码 7-主力行为识别.py L198-287 对齐）
    # ================================================================

    def _safe_float(self, val: Any, default: float = 0.0) -> float:
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

    def _infer_directions(self, data: list[dict]) -> list[int]:
        """
        从K线 OHLC 推断每根的方向 (+1=买主导, -1=卖主导)

        - close > open → +1（多头主导）
        - close < open → -1（空头主导）
        - close == open → 0
        """
        directions = []
        for d in data:
            open_p = self._safe_float(d.get("open_price"))
            close_p = self._safe_float(d.get("close_price"))
            if close_p > open_p:
                directions.append(1)
            elif close_p < open_p:
                directions.append(-1)
            else:
                directions.append(0)
        return directions

    def _amounts(self, data: list[dict]) -> list[float]:
        """计算每根K线的成交额（price * volume）"""
        result = []
        for d in data:
            price = self._safe_float(d.get("close_price"))
            vol = self._safe_float(d.get("volume"))
            result.append(price * vol)
        return result

    # ---- 1. 订单流不平衡 (OFI) ----
    def _compute_ofi_abs(self, data: list[dict]) -> float:
        """OFI 绝对值：|买成交量 - 卖成交量| / 总成交量"""
        if not data:
            return 0.0

        directions = self._infer_directions(data)
        volumes = [self._safe_float(d.get("volume")) for d in data]

        buy_vol = sum(v for v, d in zip(volumes, directions) if d == 1)
        sell_vol = sum(v for v, d in zip(volumes, directions) if d == -1)
        total_vol = buy_vol + sell_vol

        if total_vol <= 0:
            return 0.0

        ofi = (buy_vol - sell_vol) / total_vol
        return round(abs(ofi), 4)

    # ---- 2. 大单比例 ----
    def _compute_large_ratio(self, data: list[dict]) -> float:
        """大单比例：成交额超过均值3倍的K线数 / 总数"""
        n = len(data)
        if n < 5:
            return 0.0

        amounts = self._amounts(data)
        avg_amount = sum(amounts) / n
        if avg_amount <= 0:
            return 0.0

        threshold = avg_amount * 3
        large_count = sum(1 for a in amounts if a > threshold)
        return round(large_count / n, 4)

    # ---- 3. 撤单率 ----
    def _compute_cancel_rate(self, data: list[dict]) -> float:
        """撤单率：从K线形态近似（上影线比例）"""
        if not data:
            return 0.0

        rates = []
        for d in data:
            high = self._safe_float(d.get("high_price"))
            low = self._safe_float(d.get("low_price"))
            open_p = self._safe_float(d.get("open_price"))
            close_p = self._safe_float(d.get("close_price"))

            if high <= low:
                continue
            max_oc = max(open_p, close_p)
            upper_shadow_ratio = max(0.0, (high - max_oc) / (high - low))
            rates.append(upper_shadow_ratio)

        if not rates:
            return 0.0
        return round(sum(rates) / len(rates), 4)

    # ---- 4. 成交节奏规律性 ----
    def _compute_interval_cv(self, data: list[dict]) -> float:
        """成交节奏规律性：成交量的变异系数"""
        if len(data) < 5:
            return 1.0

        volumes = [self._safe_float(d.get("volume")) for d in data]
        mean_vol = sum(volumes) / len(volumes)
        if mean_vol <= 0:
            return 1.0

        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_vol = math.sqrt(variance)
        return round(std_vol / mean_vol, 4)

    # ---- 5. 价格冲击恢复速度 ----
    def _compute_recovery_speed(self, data: list[dict], window: int) -> float:
        """价格冲击恢复速度：大单后价格回归的比例"""
        n = len(data)
        if n < window + 1:
            return 0.5

        recent = data[-window:]
        closes = [self._safe_float(d.get("close_price")) for d in recent]
        amounts = self._amounts(recent)

        if not amounts or sum(amounts) <= 0:
            return 0.5

        avg_amount = sum(amounts) / len(amounts)
        large_threshold = avg_amount * 3

        recovery_speeds = []
        for i in range(len(recent) - 10):
            if amounts[i] <= large_threshold:
                continue
            pre_window = closes[max(0, i - 5):i]
            pre_price = sum(pre_window) / len(pre_window) if pre_window else closes[i]
            post_prices = closes[i + 1:i + 11]
            if len(post_prices) < 5:
                continue
            denominator = abs(closes[i] - pre_price) + 1e-8
            recovery = abs(post_prices[-1] - closes[i]) / denominator
            recovery_speeds.append(min(recovery, 1.0))

        if not recovery_speeds:
            return 0.5
        return round(sum(recovery_speeds) / len(recovery_speeds), 4)

    # ---- 6. 方向持续性 ----
    def _compute_run_length(self, data: list[dict]) -> float:
        """方向持续性：连续同方向K线的平均长度"""
        n = len(data)
        if n < 2:
            return 1.0

        directions = self._infer_directions(data)
        run_lengths = []
        current_run = 1
        for i in range(1, n):
            if directions[i] != 0 and directions[i] == directions[i - 1]:
                current_run += 1
            else:
                run_lengths.append(current_run)
                current_run = 1
        run_lengths.append(current_run)

        if not run_lengths:
            return 1.0
        return round(sum(run_lengths) / len(run_lengths), 4)

    # ---- 7. 成交量变异系数 ----
    def _compute_vol_cv(self, data: list[dict]) -> float:
        """成交量变异系数：volumes 的 std / mean"""
        if len(data) < 5:
            return 0.0

        volumes = [self._safe_float(d.get("volume")) for d in data]
        mean_vol = sum(volumes) / len(volumes)
        if mean_vol <= 0:
            return 0.0

        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_vol = math.sqrt(variance)
        return round(std_vol / mean_vol, 4)

    # ---- 8. 方向对称性 ----
    def _compute_direction_symmetry(self, data: list[dict]) -> float:
        """方向对称性：min(买笔,卖笔) / max(买笔,卖笔)"""
        directions = self._infer_directions(data)
        buy_count = sum(1 for d in directions if d == 1)
        sell_count = sum(1 for d in directions if d == -1)

        if buy_count == 0 and sell_count == 0:
            return 1.0
        return round(min(buy_count, sell_count) / (max(buy_count, sell_count) + 1e-8), 4)

    # ---- 9. 限价单比例 ----
    def _compute_limit_ratio(self, data: list[dict]) -> float:
        """限价单比例：实体/振幅比"""
        n = len(data)
        if n < 3:
            return 0.5

        ratios = []
        for d in data:
            high = self._safe_float(d.get("high_price"))
            low = self._safe_float(d.get("low_price"))
            open_p = self._safe_float(d.get("open_price"))
            close_p = self._safe_float(d.get("close_price"))

            span = high - low
            if span <= 0:
                continue
            body_ratio = abs(close_p - open_p) / span
            ratios.append(body_ratio)

        if not ratios:
            return 0.5
        return round(sum(ratios) / len(ratios), 4)

    # ---- 10. 价格波动率 ----
    def _compute_price_volatility(self, data: list[dict]) -> float:
        """价格波动率：归一化价格变化的标准差"""
        if len(data) < 3:
            return 0.0

        closes = [self._safe_float(d.get("close_price")) for d in data]
        if len(closes) < 2:
            return 0.0

        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        mean_price = sum(closes) / len(closes)
        if mean_price <= 0:
            return 0.0

        mean_diff = sum(diffs) / len(diffs)
        variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
        std_diff = math.sqrt(variance)
        return round(std_diff / mean_price, 6)

    def extract_features(self, stock_code: str, time_range: str = "today") -> dict[str, Any]:
        """
        提取10大微观结构特征

        Args:
            stock_code: 股票代码（如 "000001.SZ"）
            time_range: 时间范围（today/yesterday/last_5_days）

        Returns:
            dict: 包含所有特征值和原始数据的字典
        """
        logger.info(f"===== extract_features 开始 =====")
        logger.info(f"stock_code={stock_code}, time_range={time_range}")
        
        if time_range not in TIME_RANGE_PRESETS:
            time_range = "today"

        preset = TIME_RANGE_PRESETS[time_range]
        window = preset["window"]
        min_bars = preset["min_bars"]

        conn = self._get_conn()
        try:
            stock_name = self._fetch_stock_name(conn, stock_code)
            logger.info(f"stock_name={stock_name}")

            # 检查交易日（仅对今日有效）
            if time_range == "today":
                if not self._is_trading_day(date.today()):
                    today_label = f"{date.today().year}年{date.today().month}月{date.today().day}日"
                    return {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "error": f"{today_label} 不是交易日（周末或法定节假日），QMT 网关不会返回当日行情数据。请选择「昨日」或「近五日」时间范围进行分析。",
                        "features": {},
                        "daily_data": [],
                        "is_trading_day": False,
                    }

            # 通过 QMT 网关获取分钟数据（如果失败会从数据库获取）
            logger.info("准备调用 _fetch_minute_data_from_qmt...")
            market_data = self._fetch_minute_data_from_qmt(stock_code, time_range, conn)
            logger.info(f"_fetch_minute_data_from_qmt 返回 {len(market_data)} 条数据")

            # 检查数据完整性
            expected_bars = self._get_expected_bars_for_time(time_range)
            actual_bars = len(market_data)
            data_complete = actual_bars >= expected_bars * 0.9

            if actual_bars < min_bars:
                logger.warning(f"分钟数据不足({actual_bars}条)，尝试获取日线数据", extra={
                    "stock_code": stock_code,
                    "time_range": time_range,
                })

                daily_data = self._fetch_daily_data(conn, stock_code, 30)
                if len(daily_data) >= min_bars:
                    logger.info(f"使用日线数据进行分析，共{len(daily_data)}条", extra={
                        "stock_code": stock_code,
                    })
                    market_data = daily_data
                    actual_bars = len(market_data)
                    expected_bars = len(daily_data)
                    data_complete = True
                else:
                    # 构建用户友好的错误提示
                    range_label = self._format_time_range_label(time_range)
                    if actual_bars == 0:
                        # 完全无数据：明确提示 QMT 未返回数据
                        error_msg = (
                            f"在时间范围 {range_label} 内，QMT 网关未返回任何分钟行情数据。"
                            f"可能原因：1) 当前非交易时段（盘前/盘中休市/收盘后）；"
                            f"2) QMT 网关未连接或数据尚未同步；"
                            f"3) 股票在该时间范围内停牌。"
                            f"建议稍后重试或选择其他时间范围。"
                        )
                    else:
                        # 数据不足：说明已获取到的数据条数
                        error_msg = (
                            f"在时间范围 {range_label} 内，QMT 网关仅返回 {actual_bars} 条数据，"
                            f"少于分析所需的最低 {min_bars} 条，"
                            f"数据库中也未找到足够的日线数据进行补充。"
                            f"可能原因：1) 该股票刚上市或刚复牌数据较少；"
                            f"2) 交易日内部分时段停牌。"
                            f"建议选择其他时间范围或稍后重试。"
                        )

                    return {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "error": error_msg,
                        "features": {},
                        "daily_data": market_data,
                        "actual_bars": actual_bars,
                        "expected_bars": expected_bars,
                        "data_complete": False,
                    }

            # 计算特征
            features = {
                "ofi_abs": self._compute_ofi_abs(market_data),
                "large_ratio": self._compute_large_ratio(market_data),
                "cancel_rate": self._compute_cancel_rate(market_data),
                "interval_cv": self._compute_interval_cv(market_data),
                "recovery_speed": self._compute_recovery_speed(market_data, window),
                "run_length": self._compute_run_length(market_data),
                "vol_cv": self._compute_vol_cv(market_data),
                "direction_symmetry": self._compute_direction_symmetry(market_data),
                "limit_ratio": self._compute_limit_ratio(market_data),
                "price_volatility": self._compute_price_volatility(market_data),
            }

            result = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "features": features,
                "daily_data": market_data,
                "actual_bars": actual_bars,
                "expected_bars": expected_bars,
                "data_complete": data_complete,
            }

            # 添加数据缺失警告
            if not data_complete:
                result["warning"] = "数据缺失一部分，分析结果可能有误请谨慎对待"

            return result
        except Exception as e:
            logger.error("特征提取失败", extra={"stock_code": stock_code, "error": str(e)})
            raise
        finally:
            conn.close()

    # ================================================================
    # 行为分类层
    # ================================================================

    def classify_behavior(self, features: dict[str, float], data: list[dict] | None = None) -> dict[str, Any]:
        """
        基于微观结构特征进行主力类型判断

        参考代码 L566-582 关键指标：
        - 疑似 RL 做市：撤单率 > 25%、interval_cv < 0.5、direction_symmetry > 0.8、vol_cv < 0.3
        - 疑似 RL 拆单：run_length > 3.0、ofi_abs > 0.5、limit_ratio > 0.6
        - 散户：撤单率 < 10%、偶尔大单、interval_cv > 1.0

        同时根据 OFI 有向值推断主力买卖方向：
        - ofi_signed > 0.3 → 强买
        - ofi_signed > 0.1 → 弱买
        - |ofi_signed| <= 0.1 → 中性
        - ofi_signed < -0.1 → 弱卖
        - ofi_signed < -0.3 → 强卖
        """
        # 通过K线方向计算 OFI 有向值
        ofi_signed = 0.0
        ofi_signed_recent = 0.0
        if data:
            directions = self._infer_directions(data)
            volumes = [self._safe_float(d.get("volume")) for d in data]
            buy_vol = sum(v for v, d in zip(volumes, directions) if d == 1)
            sell_vol = sum(v for v, d in zip(volumes, directions) if d == -1)
            total_vol = buy_vol + sell_vol
            if total_vol > 0:
                ofi_signed = (buy_vol - sell_vol) / total_vol

            recent_n = max(20, len(data) // 3)
            recent_data = data[-recent_n:]
            recent_directions = self._infer_directions(recent_data)
            recent_volumes = [self._safe_float(d.get("volume")) for d in recent_data]
            recent_buy = sum(v for v, d in zip(recent_volumes, recent_directions) if d == 1)
            recent_sell = sum(v for v, d in zip(recent_volumes, recent_directions) if d == -1)
            recent_total = recent_buy + recent_sell
            if recent_total > 0:
                ofi_signed_recent = (recent_buy - recent_sell) / recent_total

        ofi_abs = features.get("ofi_abs", 0.0)
        large_ratio = features.get("large_ratio", 0.0)
        cancel_rate = features.get("cancel_rate", 0.0)
        interval_cv = features.get("interval_cv", 1.0)
        recovery_speed = features.get("recovery_speed", 0.5)
        run_length = features.get("run_length", 1.0)
        vol_cv = features.get("vol_cv", 0.0)
        direction_symmetry = features.get("direction_symmetry", 1.0)
        limit_ratio = features.get("limit_ratio", 0.5)
        price_volatility = features.get("price_volatility", 0.0)

        # ---- 机构主力（做市商）得分 ----
        institution_score = 0.0

        if cancel_rate > 0.25:
            institution_score += 0.25
        elif cancel_rate > 0.15:
            institution_score += 0.10

        if interval_cv < 0.3:
            institution_score += 0.20
        elif interval_cv < 0.5:
            institution_score += 0.10

        if direction_symmetry > 0.8:
            institution_score += 0.20
        elif direction_symmetry > 0.6:
            institution_score += 0.10

        if vol_cv < 0.3:
            institution_score += 0.15
        elif vol_cv < 0.5:
            institution_score += 0.08

        if price_volatility < 0.001:
            institution_score += 0.10
        elif price_volatility < 0.002:
            institution_score += 0.05

        if large_ratio < 0.05:
            institution_score += 0.10

        # ---- 游资（拆单执行）得分 ----
        hot_money_score = 0.0

        if run_length > 3.0:
            hot_money_score += 0.25
        elif run_length > 2.0:
            hot_money_score += 0.15

        if ofi_abs > 0.5:
            hot_money_score += 0.20
        elif ofi_abs > 0.3:
            hot_money_score += 0.10

        if limit_ratio > 0.6:
            hot_money_score += 0.20
        elif limit_ratio > 0.4:
            hot_money_score += 0.10

        if recovery_speed > 0.5:
            hot_money_score += 0.10

        if 0.2 < vol_cv < 0.6:
            hot_money_score += 0.10

        if large_ratio > 0.1:
            hot_money_score += 0.10

        if direction_symmetry < 0.5:
            hot_money_score += 0.05

        # ---- 散户得分 ----
        retail_score = 0.0

        if cancel_rate < 0.10:
            retail_score += 0.25
        elif cancel_rate < 0.15:
            retail_score += 0.15

        if interval_cv > 1.0:
            retail_score += 0.20
        elif interval_cv > 0.7:
            retail_score += 0.10

        if run_length < 1.5:
            retail_score += 0.15

        if 0.4 < direction_symmetry < 0.7:
            retail_score += 0.10

        if large_ratio > 0.05:
            retail_score += 0.10

        if 0.001 < price_volatility < 0.005:
            retail_score += 0.10

        if 0.2 < limit_ratio < 0.5:
            retail_score += 0.10

        # ---- 归一化得分 ----
        total_score = institution_score + hot_money_score + retail_score
        if total_score <= 0:
            total_score = 1.0

        institution_pct = round(institution_score / total_score, 4)
        hot_money_pct = round(hot_money_score / total_score, 4)
        retail_pct = round(retail_score / total_score, 4)

        total_pct = institution_pct + hot_money_pct + retail_pct
        if total_pct > 0:
            institution_pct = round(institution_pct / total_pct, 4)
            hot_money_pct = round(hot_money_pct / total_pct, 4)
            retail_pct = round(1.0 - institution_pct - hot_money_pct, 4)
        else:
            institution_pct = 0.3333
            hot_money_pct = 0.3333
            retail_pct = 0.3334

        scores = {
            self.TYPE_INSTITUTION: institution_pct,
            self.TYPE_HOT_MONEY: hot_money_pct,
            self.TYPE_RETAIL: retail_pct,
        }
        primary_type = max(scores, key=scores.get)
        confidence = scores[primary_type]

        # 判断主力买卖方向
        if primary_type == self.TYPE_RETAIL:
            direction = "neutral"
            direction_score = 0.0
        else:
            direction_score = ofi_signed_recent * 0.7 + ofi_signed * 0.3
            if direction_score > 0.3:
                direction = "strong_buy"
            elif direction_score > 0.1:
                direction = "weak_buy"
            elif direction_score < -0.3:
                direction = "strong_sell"
            elif direction_score < -0.1:
                direction = "weak_sell"
            else:
                direction = "neutral"

        return {
            "primary_type": primary_type,
            "confidence": confidence,
            "type_scores": {
                "institution": institution_pct,
                "hot_money": hot_money_pct,
                "retail": retail_pct,
            },
            "direction": direction,
            "direction_score": round(direction_score, 4),
            "ofi_signed": round(ofi_signed, 4),
            "ofi_signed_recent": round(ofi_signed_recent, 4),
        }

    # ================================================================
    # 指标分析层
    # ================================================================

    def _compute_indicators(self, data: list[dict], features: dict[str, float]) -> dict[str, str]:
        """计算市场趋势指标"""
        vol_cv = features.get("vol_cv", 0.0)
        if vol_cv > 0.7:
            volume_trend = "increasing"
        elif vol_cv < 0.3:
            volume_trend = "stable"
        else:
            volume_trend = "decreasing"

        recent = data[-20:] if len(data) >= 20 else data
        if len(recent) >= 2:
            first_close = self._safe_float(recent[0].get("close_price"))
            last_close = self._safe_float(recent[-1].get("close_price"))
            if first_close > 0:
                price_change = (last_close - first_close) / first_close * 100
                if price_change > 1.0:
                    price_trend = "up"
                elif price_change < -1.0:
                    price_trend = "down"
                else:
                    price_trend = "sideways"
            else:
                price_trend = "sideways"
        else:
            price_trend = "sideways"

        directions = self._infer_directions(data)
        volumes = [self._safe_float(d.get("volume")) for d in data]
        buy_vol = sum(v for v, d in zip(volumes, directions) if d == 1)
        sell_vol = sum(v for v, d in zip(volumes, directions) if d == -1)
        total_vol = buy_vol + sell_vol
        if total_vol > 0:
            ofi_signed = (buy_vol - sell_vol) / total_vol
        else:
            ofi_signed = 0.0
        if ofi_signed > 0.1:
            capital_flow = "inflow"
        elif ofi_signed < -0.1:
            capital_flow = "outflow"
        else:
            capital_flow = "neutral"

        ofi_abs = features.get("ofi_abs", 0.0)
        price_volatility = features.get("price_volatility", 0.0)
        large_ratio = features.get("large_ratio", 0.0)

        activity_score = 0
        if ofi_abs > 0.3:
            activity_score += 1
        if price_volatility > 0.003:
            activity_score += 1
        if large_ratio > 0.1:
            activity_score += 1

        if activity_score >= 2:
            activity_level = "high"
        elif activity_score >= 1:
            activity_level = "medium"
        else:
            activity_level = "low"

        return {
            "volume_trend": volume_trend,
            "price_trend": price_trend,
            "capital_flow": capital_flow,
            "activity_level": activity_level,
        }

    # ================================================================
    # 信号生成层
    # ================================================================

    def _generate_signals(
        self,
        data: list[dict],
        features: dict[str, float],
        classification: dict[str, Any],
        indicators: dict[str, str],
    ) -> list[dict]:
        """生成交易信号"""
        signals = []
        primary_type = classification.get("primary_type", self.TYPE_RETAIL)
        confidence = classification.get("confidence", 0.0)

        if not data:
            return signals

        latest = data[-1]
        latest_date = latest.get("trade_date", "")
        if hasattr(latest_date, "strftime"):
            latest_date = latest_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            latest_date = str(latest_date)

        ofi_abs = features.get("ofi_abs", 0.0)
        run_length = features.get("run_length", 1.0)
        large_ratio = features.get("large_ratio", 0.0)
        interval_cv = features.get("interval_cv", 1.0)
        cancel_rate = features.get("cancel_rate", 0.0)
        recovery_speed = features.get("recovery_speed", 0.5)
        direction_symmetry = features.get("direction_symmetry", 1.0)

        directions = self._infer_directions(data)
        volumes = [self._safe_float(d.get("volume")) for d in data]
        buy_vol = sum(v for v, d in zip(volumes, directions) if d == 1)
        sell_vol = sum(v for v, d in zip(volumes, directions) if d == -1)
        total_vol = buy_vol + sell_vol
        ofi_signed = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0.0

        # ---- 机构（做市商）信号 ----
        if primary_type == self.TYPE_INSTITUTION and ofi_signed > 0.1:
            strength = min(5, int(3 + confidence * 3))
            signals.append({
                "date": latest_date,
                "type": "BUY",
                "strength": strength,
                "description": f"做市商主导，撤单率{cancel_rate:.0%}，成交节奏规律（CV={interval_cv:.2f}）",
            })
        if primary_type == self.TYPE_INSTITUTION and ofi_signed < -0.1:
            strength = min(5, int(3 + confidence * 3))
            signals.append({
                "date": latest_date,
                "type": "SELL",
                "strength": strength,
                "description": f"做市商减仓，方向对称性{direction_symmetry:.2f}，价格回归快（恢复速度={recovery_speed:.2f}）",
            })

        # ---- 游资（拆单执行）信号 ----
        if primary_type == self.TYPE_HOT_MONEY and run_length > 2.0 and ofi_abs > 0.3:
            signal_type = "BUY" if ofi_signed > 0 else "SELL"
            strength = min(5, int(2 + run_length))
            signals.append({
                "date": latest_date,
                "type": signal_type,
                "strength": strength,
                "description": f"拆单执行特征明显，方向持续{run_length:.1f}根K线，OFI={ofi_abs:.2f}",
            })

        # ---- 大单信号 ----
        if large_ratio > 0.15 and ofi_abs > 0.4:
            signal_type = "BUY" if ofi_signed > 0 else "SELL"
            signals.append({
                "date": latest_date,
                "type": signal_type,
                "strength": 3,
                "description": f"大单占比{large_ratio:.1%}，存在主力{'买入' if signal_type == 'BUY' else '卖出'}动作",
            })

        # ---- 散户活跃信号 ----
        if primary_type == self.TYPE_RETAIL and interval_cv > 1.0 and cancel_rate < 0.1:
            signals.append({
                "date": latest_date,
                "type": "BUY",
                "strength": 2,
                "description": "散户交易为主（撤单率低、节奏不规律），市场无明显主力",
            })

        return signals

    # ================================================================
    # 摘要生成层
    # ================================================================

    def _generate_summary(
        self,
        stock_name: str,
        features: dict[str, float],
        classification: dict[str, Any],
        indicators: dict[str, str],
        signals: list[dict],
        time_range: str,
    ) -> str:
        """生成分析摘要文本"""
        primary_type = classification.get("primary_type", self.TYPE_RETAIL)
        type_label = self.TYPE_LABELS.get(primary_type, "未知")
        confidence = classification.get("confidence", 0.0)
        volume_trend = indicators.get("volume_trend", "stable")
        price_trend = indicators.get("price_trend", "sideways")
        capital_flow = indicators.get("capital_flow", "neutral")
        activity_level = indicators.get("activity_level", "low")

        ofi_abs = features.get("ofi_abs", 0.0)
        cancel_rate = features.get("cancel_rate", 0.0)
        interval_cv = features.get("interval_cv", 1.0)
        run_length = features.get("run_length", 1.0)
        direction_symmetry = features.get("direction_symmetry", 1.0)
        large_ratio = features.get("large_ratio", 0.0)

        range_label = TIME_RANGE_PRESETS.get(time_range, {}).get("label", time_range)

        trend_map = {
            "increasing": "成交量波动放大",
            "decreasing": "成交量波动收缩",
            "stable": "成交量稳定",
        }
        price_map = {
            "up": "价格上行",
            "down": "价格下行",
            "sideways": "价格横盘",
        }
        flow_map = {
            "inflow": "订单流偏买",
            "outflow": "订单流偏卖",
            "neutral": "订单流均衡",
        }
        activity_map = {
            "high": "活跃度高",
            "medium": "活跃度中等",
            "low": "活跃度较低",
        }

        parts = []
        parts.append(f"{range_label}{stock_name}以{type_label}为主导力量（置信度{confidence:.0%}）")
        parts.append(trend_map.get(volume_trend, ""))
        parts.append(price_map.get(price_trend, ""))
        parts.append(flow_map.get(capital_flow, ""))
        parts.append(activity_map.get(activity_level, ""))

        if primary_type == self.TYPE_INSTITUTION:
            parts.append(f"撤单率{cancel_rate:.0%}，成交节奏CV={interval_cv:.2f}，方向对称性{direction_symmetry:.2f}")
        elif primary_type == self.TYPE_HOT_MONEY:
            parts.append(f"方向持续{run_length:.1f}根K线，OFI绝对值{ofi_abs:.2f}，大单占比{large_ratio:.1%}")
        else:
            parts.append(f"撤单率低({cancel_rate:.0%})，节奏不规律(CV={interval_cv:.2f})，无明显主力痕迹")

        if ofi_abs > 0.5:
            parts.append(f"订单流不平衡显著（OFI={ofi_abs:.2f}）")
        elif ofi_abs < 0.1:
            parts.append("订单流基本均衡")

        if signals:
            signal_types = [s["type"] for s in signals]
            buy_count = signal_types.count("BUY")
            sell_count = signal_types.count("SELL")
            if buy_count > sell_count:
                parts.append("综合信号偏多")
            elif sell_count > buy_count:
                parts.append("综合信号偏空")
            else:
                parts.append("多空信号均衡")

        summary = "，".join(p for p in parts if p)
        return summary + "。"

    # ================================================================
    # 主分析方法
    # ================================================================

    def _format_time_range_label(self, time_range: str) -> str:
        """
        格式化时间范围标签为具体日期显示

        规则：
        - today: 显示今天的日期（如 "2026年6月8日"）
        - yesterday: 显示昨天的日期（如 "2026年6月7日"）
        - last_5_days: 显示开始到结束日期（如 "2026年6月3日 - 2026年6月7日"）
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

    def analyze_stock(self, stock_code: str, time_range: str = "today") -> dict[str, Any]:
        """
        分析单只股票的主力行为

        Args:
            stock_code: 股票代码（如 "000001.SZ"）
            time_range: 时间范围（today/yesterday/last_5_days）

        Returns:
            dict: 完整的分析结果
        """
        if time_range not in TIME_RANGE_PRESETS:
            time_range = "today"

        # 使用具体日期作为标签
        range_label = self._format_time_range_label(time_range)

        logger.info("开始分析股票主力行为", extra={
            "stock_code": stock_code,
            "time_range": time_range,
            "range_label": range_label,
        })

        extract_result = self.extract_features(stock_code, time_range)

        # 检查是否有错误
        if "error" in extract_result:
            # 计算期望数据条数（用于显示）
            try:
                expected_bars = self._get_expected_bars_for_time(time_range)
            except Exception:
                expected_bars = 0
            return {
                "stock_code": stock_code,
                "stock_name": extract_result.get("stock_name", stock_code),
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "time_range": time_range,
                "time_range_label": range_label,
                "error": extract_result["error"],
                "data_bars": 0,
                "features": {},
                "classification": {
                    "primary_type": self.TYPE_RETAIL,
                    "confidence": 0.0,
                    "type_scores": {
                        "institution": 0.0,
                        "hot_money": 0.0,
                        "retail": 1.0,
                    },
                    "direction": "neutral",
                    "direction_score": 0.0,
                    "ofi_signed": 0.0,
                    "ofi_signed_recent": 0.0,
                },
                "indicators": {
                    "volume_trend": "stable",
                    "price_trend": "sideways",
                    "capital_flow": "neutral",
                    "activity_level": "low",
                },
                "signals": [],
                "summary": f"分析失败: {extract_result['error']}",
                "actual_bars": 0,
                "expected_bars": expected_bars,
                "data_complete": extract_result.get("data_complete", False),
                "warning": extract_result.get("warning"),
                "is_trading_day": extract_result.get("is_trading_day", True),
            }

        features = extract_result["features"]
        market_data = extract_result["daily_data"]
        stock_name = extract_result["stock_name"]

        # 分类主力类型
        classification = self.classify_behavior(features, data=market_data)

        # 计算趋势指标
        indicators = self._compute_indicators(market_data, features)

        # 生成交易信号
        signals = self._generate_signals(market_data, features, classification, indicators)

        # 生成摘要
        summary = self._generate_summary(
            stock_name, features, classification, indicators, signals, time_range
        )

        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time_range": time_range,
            "time_range_label": range_label,
            "data_bars": len(market_data),
            "actual_bars": extract_result.get("actual_bars", len(market_data)),
            "expected_bars": extract_result.get("expected_bars", 0),
            "data_complete": extract_result.get("data_complete", True),
            "warning": extract_result.get("warning"),
            "features": features,
            "classification": classification,
            "indicators": indicators,
            "signals": signals,
            "summary": summary,
        }

        logger.info("股票主力行为分析完成", extra={
            "stock_code": stock_code,
            "time_range": time_range,
            "primary_type": classification.get("primary_type"),
            "confidence": classification.get("confidence"),
            "data_bars": len(market_data),
            "signals_count": len(signals),
        })

        return result

    # ================================================================
    # 分析结果持久化
    # ================================================================

    def save_analysis_result(self, analysis_result: dict[str, Any]) -> Optional[int]:
        """将分析结果保存到 trade_mainforce_activity 表"""
        conn = self._get_conn()
        try:
            stock_code = analysis_result.get("stock_code", "")
            stock_name = analysis_result.get("stock_name", "")
            features = analysis_result.get("features", {})
            classification = analysis_result.get("classification", {})
            signals = analysis_result.get("signals", [])
            analysis_date = analysis_result.get("analysis_date", datetime.now().strftime("%Y-%m-%d"))

            primary_type = classification.get("primary_type", self.TYPE_RETAIL)
            confidence = classification.get("confidence", 0.0)

            if signals:
                strongest = max(signals, key=lambda s: s.get("strength", 0))
                activity_type = strongest.get("type", "BUY")
                strength = strongest.get("strength", 3)
            else:
                activity_type = "BUY"
                strength = 1

            indicators_json = {
                "features": features,
                "classification": classification,
                "indicators": analysis_result.get("indicators", {}),
                "time_range": analysis_result.get("time_range"),
            }

            volume_ratio = features.get("ofi_abs", 0.0)
            price_impact = features.get("price_volatility", 0.0)

            execute(
                conn,
                """INSERT INTO trade_mainforce_activity
                   (activity_date, stock_code, stock_name, activity_type, volume, amount, price, ratio,
                    mainforce_type, description, indicators, is_anomaly, alert_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    analysis_date,
                    stock_code,
                    stock_name,
                    activity_type,
                    0,
                    0,
                    0,
                    round(confidence, 4),
                    primary_type,
                    analysis_result.get("summary", ""),
                    __import__("json").dumps(indicators_json, ensure_ascii=False),
                    1 if volume_ratio > 0.5 or price_impact > 0.005 else 0,
                    "none",
                )
            )

            result = query_dict(conn, "SELECT LAST_INSERT_ID() as id", ())
            activity_id = result[0]["id"] if result else None

            logger.info("分析结果已保存", extra={
                "stock_code": stock_code,
                "activity_id": activity_id,
            })

            return activity_id
        except Exception as e:
            logger.error("保存分析结果失败", extra={"error": str(e)})
            return None
        finally:
            conn.close()

    def save_task_record(self, stock_code: str, time_range: str, analysis_result: dict[str, Any], status: str = "done") -> Optional[str]:
        """将分析任务记录保存到 trade_mainforce_task 表"""
        import json
        import uuid

        conn = self._get_conn()
        try:
            task_id = f"mf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{stock_code.replace('.', '')}"

            params_json = json.dumps({"time_range": time_range}, ensure_ascii=False)
            result_json = json.dumps(analysis_result, ensure_ascii=False, default=str)

            execute(
                conn,
                """INSERT INTO trade_mainforce_task
                   (task_id, stock_code, company_name, mode, params, status, result, error_message)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    task_id,
                    stock_code,
                    analysis_result.get("stock_name", ""),
                    "minute",
                    params_json,
                    status,
                    result_json,
                    None,
                )
            )

            logger.info("任务记录已保存", extra={
                "task_id": task_id,
                "stock_code": stock_code,
                "status": status,
            })

            return task_id
        except Exception as e:
            logger.error("保存任务记录失败", extra={"error": str(e)})
            return None
        finally:
            conn.close()