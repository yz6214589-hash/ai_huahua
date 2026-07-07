# -*- coding: utf-8 -*-
"""
主力行为识别 - 微观结构特征提取

提取10大微观结构特征（与参考代码 7-主力行为识别.py L198-287 保持一致）:
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
from datetime import datetime, date
from typing import Any

from infra.storage.logging_service import get_logger
from core.mainforce.models import TIME_RANGE_PRESETS

logger = get_logger("mainforce_engine")


class FeatureExtractor:
    """微观结构特征提取器"""

    # ================================================================
    # 工具方法
    # ================================================================

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

    # ================================================================
    # 10大微观结构特征
    # ================================================================

    def _compute_ofi_abs(self, data: list[dict]) -> float:
        """1. OFI 绝对值：|买成交量 - 卖成交量| / 总成交量"""
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

    def _compute_large_ratio(self, data: list[dict]) -> float:
        """2. 大单比例：成交额超过均值3倍的K线数 / 总数"""
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

    def _compute_cancel_rate(self, data: list[dict]) -> float:
        """3. 撤单率：从K线形态近似（上影线比例）"""
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

    def _compute_interval_cv(self, data: list[dict]) -> float:
        """4. 成交节奏规律性：成交量的变异系数"""
        if len(data) < 5:
            return 1.0

        volumes = [self._safe_float(d.get("volume")) for d in data]
        mean_vol = sum(volumes) / len(volumes)
        if mean_vol <= 0:
            return 1.0

        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_vol = math.sqrt(variance)
        return round(std_vol / mean_vol, 4)

    def _compute_recovery_speed(self, data: list[dict], window: int) -> float:
        """5. 价格冲击恢复速度：大单后价格回归的比例"""
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

    def _compute_run_length(self, data: list[dict]) -> float:
        """6. 方向持续性：连续同方向K线的平均长度"""
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

    def _compute_vol_cv(self, data: list[dict]) -> float:
        """7. 成交量变异系数：volumes 的 std / mean"""
        if len(data) < 5:
            return 0.0

        volumes = [self._safe_float(d.get("volume")) for d in data]
        mean_vol = sum(volumes) / len(volumes)
        if mean_vol <= 0:
            return 0.0

        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_vol = math.sqrt(variance)
        return round(std_vol / mean_vol, 4)

    def _compute_direction_symmetry(self, data: list[dict]) -> float:
        """8. 方向对称性：min(买笔,卖笔) / max(买笔,卖笔)"""
        directions = self._infer_directions(data)
        buy_count = sum(1 for d in directions if d == 1)
        sell_count = sum(1 for d in directions if d == -1)

        if buy_count == 0 and sell_count == 0:
            return 1.0
        return round(min(buy_count, sell_count) / (max(buy_count, sell_count) + 1e-8), 4)

    def _compute_limit_ratio(self, data: list[dict]) -> float:
        """9. 限价单比例：实体/振幅比"""
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

    def _compute_price_volatility(self, data: list[dict]) -> float:
        """10. 价格波动率：归一化价格变化的标准差"""
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

    # ================================================================
    # 综合特征提取
    # ================================================================

    def extract_features(
        self,
        stock_code: str,
        time_range: str,
        stock_name: str,
        market_data: list[dict],
        expected_bars: int,
    ) -> dict[str, Any]:
        """
        从行情数据中提取10大微观结构特征

        Args:
            stock_code: 股票代码
            time_range: 时间范围
            stock_name: 股票名称
            market_data: 行情数据（分钟或日线）
            expected_bars: 期望数据条数

        Returns:
            dict: 包含所有特征值和元数据的字典
        """
        if time_range not in TIME_RANGE_PRESETS:
            time_range = "today"

        preset = TIME_RANGE_PRESETS[time_range]
        window = preset["window"]
        min_bars = preset["min_bars"]

        actual_bars = len(market_data)
        data_complete = actual_bars >= expected_bars * 0.9

        if actual_bars < min_bars:
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "features": {},
                "daily_data": market_data,
                "actual_bars": actual_bars,
                "expected_bars": expected_bars,
                "data_complete": False,
                "error": f"数据不足：实际 {actual_bars} 条 < 最低要求 {min_bars} 条",
            }

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

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "features": features,
            "daily_data": market_data,
            "actual_bars": actual_bars,
            "expected_bars": expected_bars,
            "data_complete": data_complete,
        }
