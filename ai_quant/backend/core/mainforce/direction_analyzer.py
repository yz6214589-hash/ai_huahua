# -*- coding: utf-8 -*-
"""
主力行为识别 - 买卖方向分析器

从K线数据中计算订单流不平衡(OFI)有向值，
并根据主力类型和OFI值判断买卖方向。
"""

from __future__ import annotations

import math
from typing import Any

from core.mainforce.models import TYPE_INSTITUTION, TYPE_HOT_MONEY, TYPE_RETAIL


class DirectionAnalyzer:
    """买卖方向分析器"""

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

    def compute_ofi_signed(self, data: list[dict]) -> dict[str, float]:
        """
        从K线数据计算 OFI 有向值

        通过K线方向推断买卖方向，计算：
        - ofi_signed: 全量数据的有向OFI值
        - ofi_signed_recent: 近期(最后1/3)数据的有向OFI值

        Returns:
            dict: {"ofi_signed": float, "ofi_signed_recent": float}
        """
        ofi_signed = 0.0
        ofi_signed_recent = 0.0

        if not data:
            return {"ofi_signed": 0.0, "ofi_signed_recent": 0.0}

        # 全量数据计算
        directions = self._infer_directions(data)
        volumes = [self._safe_float(d.get("volume")) for d in data]
        buy_vol = sum(v for v, d in zip(volumes, directions) if d == 1)
        sell_vol = sum(v for v, d in zip(volumes, directions) if d == -1)
        total_vol = buy_vol + sell_vol
        if total_vol > 0:
            ofi_signed = (buy_vol - sell_vol) / total_vol

        # 近期数据计算
        recent_n = max(20, len(data) // 3)
        recent_data = data[-recent_n:]
        recent_directions = self._infer_directions(recent_data)
        recent_volumes = [self._safe_float(d.get("volume")) for d in recent_data]
        recent_buy = sum(v for v, d in zip(recent_volumes, recent_directions) if d == 1)
        recent_sell = sum(v for v, d in zip(recent_volumes, recent_directions) if d == -1)
        recent_total = recent_buy + recent_sell
        if recent_total > 0:
            ofi_signed_recent = (recent_buy - recent_sell) / recent_total

        return {
            "ofi_signed": round(ofi_signed, 4),
            "ofi_signed_recent": round(ofi_signed_recent, 4),
        }

    def _infer_directions(self, data: list[dict]) -> list[int]:
        """
        从K线 OHLC 推断每根的方向 (+1=买主导, -1=卖主导)
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

    def determine_direction(
        self,
        primary_type: str,
        ofi_signed: float,
        ofi_signed_recent: float,
    ) -> dict[str, Any]:
        """
        根据主力类型和OFI有向值判断买卖方向

        规则：
        - 散户类型：始终返回 neutral
        - 非散户类型：
          - direction_score > 0.3 → strong_buy
          - direction_score > 0.1 → weak_buy
          - direction_score < -0.3 → strong_sell
          - direction_score < -0.1 → weak_sell
          - 其他 → neutral

        Args:
            primary_type: 主力类型 (institution/hot_money/retail)
            ofi_signed: 全量OFI有向值
            ofi_signed_recent: 近期OFI有向值

        Returns:
            dict: {"direction": str, "direction_score": float}
        """
        if primary_type == TYPE_RETAIL:
            return {
                "direction": "neutral",
                "direction_score": 0.0,
            }

        # 近期权重0.7，全量权重0.3
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
            "direction": direction,
            "direction_score": round(direction_score, 4),
        }
