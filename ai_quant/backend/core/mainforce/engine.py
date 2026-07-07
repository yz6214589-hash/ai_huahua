# -*- coding: utf-8 -*-
"""
主力行为识别核心引擎

支持日线和分钟级别的行情数据分析。
通过时间范围参数（今日/昨日/近五日）从 QMT 网关获取分钟级数据，
提取10大微观结构特征后通过规则引擎分类主力类型。

内部委托给以下子模块：
- models.py:           数据结构定义（常量）
- data_collector.py:   数据获取层
- feature_extractor.py: 微观结构特征提取
- classifier.py:       主力行为分类
- direction_analyzer.py: 买卖方向分析
"""

from __future__ import annotations

import json as _json_module
import math
from datetime import datetime, date
from typing import Any, Optional

from core.db import connect, load_mysql_config, query_dict, execute
from infra.storage.logging_service import get_logger

from core.mainforce.models import TIME_RANGE_PRESETS, TYPE_INSTITUTION, TYPE_HOT_MONEY, TYPE_RETAIL, TYPE_LABELS
from core.mainforce.data_collector import DataCollector
from core.mainforce.feature_extractor import FeatureExtractor
from core.mainforce.classifier import ForceClassifier
from core.mainforce.direction_analyzer import DirectionAnalyzer

logger = get_logger("mainforce_engine")


class MainForceEngine:
    """
    主力行为识别引擎

    支持日线和分钟级别的行情数据特征提取和主力类型分类。
    内部委托给子模块 DataCollector / FeatureExtractor / ForceClassifier / DirectionAnalyzer。
    """

    # 主力类型常量（保持向后兼容）
    TYPE_INSTITUTION = TYPE_INSTITUTION
    TYPE_HOT_MONEY = TYPE_HOT_MONEY
    TYPE_RETAIL = TYPE_RETAIL
    TYPE_LABELS = TYPE_LABELS

    def __init__(self) -> None:
        """初始化引擎及其子模块"""
        self._cfg = load_mysql_config()
        self.data_collector = DataCollector()
        self.feature_extractor = FeatureExtractor()
        self.direction_analyzer = DirectionAnalyzer()
        self.classifier = ForceClassifier(
            feature_extractor=self.feature_extractor,
            direction_analyzer=self.direction_analyzer,
        )

    def _get_conn(self):
        """获取数据库连接（保留用于持久化方法）"""
        return connect(self._cfg)

    # ================================================================
    # 数据获取 - 委托给 DataCollector
    # ================================================================

    def _is_trading_day(self, dt: date) -> bool:
        """判断给定日期是否为交易日（委托给 DataCollector）"""
        return self.data_collector._is_trading_day(dt)

    def _get_expected_bars_for_time(self, time_range: str) -> int:
        """获取期望数据条数（委托给 DataCollector）"""
        return self.data_collector._get_expected_bars_for_time(time_range)

    def _get_trading_dates(self, time_range: str) -> tuple[date, date]:
        """获取交易日期范围（委托给 DataCollector）"""
        return self.data_collector._get_trading_dates(time_range)

    def _fetch_stock_name(self, conn, stock_code: str) -> str:
        """从数据库获取股票名称（委托给 DataCollector）"""
        return self.data_collector._fetch_stock_name(conn, stock_code)

    def _fetch_minute_data_from_db(self, conn, stock_code: str, start_date: date, end_date: date) -> list[dict]:
        """从数据库获取分钟数据（委托给 DataCollector）"""
        return self.data_collector._fetch_minute_data_from_db(conn, stock_code, start_date, end_date)

    def _fetch_minute_data_from_qmt(self, stock_code: str, time_range: str, conn=None) -> list[dict]:
        """从QMT获取分钟数据（委托给 DataCollector）"""
        return self.data_collector._fetch_minute_data_from_qmt(stock_code, time_range, conn)

    def _fetch_mainforce_flow(self, conn, stock_code: str, days: int) -> list[dict]:
        """获取主力资金流数据（委托给 DataCollector）"""
        return self.data_collector._fetch_mainforce_flow(conn, stock_code, days)

    def _fetch_daily_data(self, conn, stock_code: str, days: int) -> list[dict]:
        """获取日线数据（委托给 DataCollector）"""
        return self.data_collector._fetch_daily_data(conn, stock_code, days)

    def _format_time_range_label(self, time_range: str) -> str:
        """格式化时间范围标签（委托给 DataCollector）"""
        return self.data_collector._format_time_range_label(time_range)

    # ================================================================
    # 特征提取 - 委托给 FeatureExtractor
    # ================================================================

    def _safe_float(self, val: Any, default: float = 0.0) -> float:
        """安全转换为浮点数（委托给 FeatureExtractor）"""
        return self.feature_extractor._safe_float(val, default)

    def _infer_directions(self, data: list[dict]) -> list[int]:
        """推断K线方向（委托给 FeatureExtractor）"""
        return self.feature_extractor._infer_directions(data)

    def _amounts(self, data: list[dict]) -> list[float]:
        """计算成交额（委托给 FeatureExtractor）"""
        return self.feature_extractor._amounts(data)

    def _compute_ofi_abs(self, data: list[dict]) -> float:
        """OFI 绝对值（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_ofi_abs(data)

    def _compute_large_ratio(self, data: list[dict]) -> float:
        """大单比例（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_large_ratio(data)

    def _compute_cancel_rate(self, data: list[dict]) -> float:
        """撤单率（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_cancel_rate(data)

    def _compute_interval_cv(self, data: list[dict]) -> float:
        """成交节奏规律性（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_interval_cv(data)

    def _compute_recovery_speed(self, data: list[dict], window: int) -> float:
        """价格冲击恢复速度（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_recovery_speed(data, window)

    def _compute_run_length(self, data: list[dict]) -> float:
        """方向持续性（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_run_length(data)

    def _compute_vol_cv(self, data: list[dict]) -> float:
        """成交量变异系数（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_vol_cv(data)

    def _compute_direction_symmetry(self, data: list[dict]) -> float:
        """方向对称性（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_direction_symmetry(data)

    def _compute_limit_ratio(self, data: list[dict]) -> float:
        """限价单比例（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_limit_ratio(data)

    def _compute_price_volatility(self, data: list[dict]) -> float:
        """价格波动率（委托给 FeatureExtractor）"""
        return self.feature_extractor._compute_price_volatility(data)

    def extract_features(self, stock_code: str, time_range: str = "today") -> dict[str, Any]:
        """
        提取10大微观结构特征

        Args:
            stock_code: 股票代码（如 "000001.SZ"）
            time_range: 时间范围（today/yesterday/last_5_days）

        Returns:
            dict: 包含所有特征值和原始数据的字典
        """
        logger.info("===== extract_features 开始 =====")
        logger.info(f"stock_code={stock_code}, time_range={time_range}")

        if time_range not in TIME_RANGE_PRESETS:
            time_range = "today"

        preset = TIME_RANGE_PRESETS[time_range]
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

            # 通过 QMT 网关获取分钟数据
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
                    range_label = self._format_time_range_label(time_range)
                    if actual_bars == 0:
                        error_msg = (
                            f"在时间范围 {range_label} 内，QMT 网关未返回任何分钟行情数据。"
                            f"可能原因：1) 当前非交易时段（盘前/盘中休市/收盘后）；"
                            f"2) QMT 网关未连接或数据尚未同步；"
                            f"3) 股票在该时间范围内停牌。"
                            f"建议稍后重试或选择其他时间范围。"
                        )
                    else:
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

            # 委托给 FeatureExtractor 计算特征
            result = self.feature_extractor.extract_features(
                stock_code, time_range, stock_name, market_data, expected_bars
            )

            # 添加数据缺失警告
            if not result.get("data_complete", True):
                result["warning"] = "数据缺失一部分，分析结果可能有误请谨慎对待"

            return result
        except Exception as e:
            logger.error("特征提取失败", extra={"stock_code": stock_code, "error": str(e)})
            raise
        finally:
            conn.close()

    # ================================================================
    # 行为分类 - 委托给 ForceClassifier
    # ================================================================

    def classify_behavior(self, features: dict[str, float], data: list[dict] | None = None) -> dict[str, Any]:
        """
        基于微观结构特征进行主力类型判断（委托给 ForceClassifier）
        """
        return self.classifier.classify_behavior(features, data)

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

        range_label = self._format_time_range_label(time_range)

        logger.info("开始分析股票主力行为", extra={
            "stock_code": stock_code,
            "time_range": time_range,
            "range_label": range_label,
        })

        extract_result = self.extract_features(stock_code, time_range)

        # 检查是否有错误
        if "error" in extract_result:
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
                    _json_module.dumps(indicators_json, ensure_ascii=False),
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
        conn = self._get_conn()
        try:
            task_id = f"mf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{stock_code.replace('.', '')}"

            params_json = _json_module.dumps({"time_range": time_range}, ensure_ascii=False)
            result_json = _json_module.dumps(analysis_result, ensure_ascii=False, default=str)

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
