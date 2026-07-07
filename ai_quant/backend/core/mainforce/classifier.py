# -*- coding: utf-8 -*-
"""
主力行为识别 - 行为分类器

基于10大微观结构特征进行主力类型判断。
参考代码 L566-582 关键指标：
- 疑似 机构做市：撤单率 > 25%、interval_cv < 0.5、direction_symmetry > 0.8、vol_cv < 0.3
- 疑似 游资拆单：run_length > 3.0、ofi_abs > 0.5、limit_ratio > 0.6
- 散户：撤单率 < 10%、偶尔大单、interval_cv > 1.0
"""

from __future__ import annotations

import math
from typing import Any

from core.mainforce.models import TYPE_INSTITUTION, TYPE_HOT_MONEY, TYPE_RETAIL
from core.mainforce.feature_extractor import FeatureExtractor
from core.mainforce.direction_analyzer import DirectionAnalyzer


class ForceClassifier:
    """主力行为分类器"""

    TYPE_INSTITUTION = TYPE_INSTITUTION
    TYPE_HOT_MONEY = TYPE_HOT_MONEY
    TYPE_RETAIL = TYPE_RETAIL

    def __init__(
        self,
        feature_extractor: FeatureExtractor | None = None,
        direction_analyzer: DirectionAnalyzer | None = None,
    ) -> None:
        """初始化分类器"""
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.direction_analyzer = direction_analyzer or DirectionAnalyzer()

    def classify_behavior(
        self,
        features: dict[str, float],
        data: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        基于微观结构特征进行主力类型判断

        同时根据 OFI 有向值推断主力买卖方向：
        - ofi_signed > 0.3 → 强买
        - ofi_signed > 0.1 → 弱买
        - |ofi_signed| <= 0.1 → 中性
        - ofi_signed < -0.1 → 弱卖
        - ofi_signed < -0.3 → 强卖
        """
        # 计算 OFI 有向值
        ofi_result = {"ofi_signed": 0.0, "ofi_signed_recent": 0.0}
        if data:
            ofi_result = self.direction_analyzer.compute_ofi_signed(data)

        ofi_signed = ofi_result["ofi_signed"]
        ofi_signed_recent = ofi_result["ofi_signed_recent"]

        # 提取特征值
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
        direction_result = self.direction_analyzer.determine_direction(
            primary_type, ofi_signed, ofi_signed_recent
        )

        return {
            "primary_type": primary_type,
            "confidence": confidence,
            "type_scores": {
                "institution": institution_pct,
                "hot_money": hot_money_pct,
                "retail": retail_pct,
            },
            "direction": direction_result["direction"],
            "direction_score": direction_result["direction_score"],
            "ofi_signed": round(ofi_signed, 4),
            "ofi_signed_recent": round(ofi_signed_recent, 4),
        }
