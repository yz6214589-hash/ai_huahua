"""
机器学习选股信号模块
基于 LightGBM / XGBoost 的二分类模型，预测股票未来N日上涨概率。
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

# 特征列定义 - 用于训练和预测保持一致
FEATURE_COLS: list[str] = [
    "ret_1d", "ret_5d", "ret_10d", "ret_20d",
    "dist_ma5", "dist_ma10", "dist_ma20", "dist_ma60",
    "ma5_slope", "ma20_slope",
    "vol_5d", "vol_20d", "vol_ratio_5_20",
    "rsi_14",
    "macd_dif", "macd_dea", "macd_hist",
    "bb_position",
    "amount_ratio_5_20",
]


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均"""
    n = len(values)
    out = np.full(n, np.nan)
    if n == 0 or period <= 0:
        return out
    alpha = 2.0 / (float(period) + 1.0)
    out[0] = float(values[0])
    for i in range(1, n):
        out[i] = alpha * float(values[i]) + (1.0 - alpha) * float(out[i - 1])
    return out


def _sma(values: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均"""
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    out[period - 1:] = (cumsum[period:] - cumsum[:-period]) / float(period)
    return out


def _rolling_std(values: np.ndarray, period: int) -> np.ndarray:
    """滚动标准差"""
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    s = pd.Series(values)
    out[period - 1:] = s.rolling(period).std().values[period - 1:]
    return out


def _rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """相对强弱指标"""
    n = len(closes)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.zeros(n)
    avg_loss = np.zeros(n)
    avg_gain[period] = gains[1:period + 1].mean()
    avg_loss[period] = losses[1:period + 1].mean()
    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
    rs = np.divide(avg_gain, np.where(avg_loss == 0, 1e-10, avg_loss),
                   out=np.zeros(n), where=avg_loss != 0)
    valid = (avg_loss != 0) & (np.arange(n) >= period)
    out[valid] = 100.0 - 100.0 / (1.0 + rs[valid])
    return out


def _macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD 指标"""
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = _ema(np.nan_to_num(dif, nan=0.0), signal)
    hist = dif - dea
    return dif, dea, hist


def _compute_features_row(closes: np.ndarray, amounts: np.ndarray, idx: int) -> dict[str, float] | None:
    """
    在第 idx 个交易日根据截止该日（含）的历史K线计算特征。
    需要至少 60 个交易日的历史窗口。
    """
    if idx < 60 or idx >= len(closes):
        return None

    window_close = closes[max(0, idx - 60):idx + 1].astype(np.float64)
    window_amount = amounts[max(0, idx - 60):idx + 1].astype(np.float64) if amounts is not None else None
    cur = float(window_close[-1])
    if cur <= 0 or not math.isfinite(cur):
        return None

    # 收益率特征
    ret_1d = (cur / float(window_close[-2]) - 1.0) * 100.0 if len(window_close) >= 2 else 0.0
    ret_5d = (cur / float(window_close[-6]) - 1.0) * 100.0 if len(window_close) >= 6 else 0.0
    ret_10d = (cur / float(window_close[-11]) - 1.0) * 100.0 if len(window_close) >= 11 else 0.0
    ret_20d = (cur / float(window_close[-21]) - 1.0) * 100.0 if len(window_close) >= 21 else 0.0

    # 均线偏离度
    ma5 = float(np.mean(window_close[-5:])) if len(window_close) >= 5 else cur
    ma10 = float(np.mean(window_close[-10:])) if len(window_close) >= 10 else cur
    ma20 = float(np.mean(window_close[-20:])) if len(window_close) >= 20 else cur
    ma60 = float(np.mean(window_close[-60:])) if len(window_close) >= 60 else cur
    dist_ma5 = (cur / ma5 - 1.0) * 100.0
    dist_ma10 = (cur / ma10 - 1.0) * 100.0
    dist_ma20 = (cur / ma20 - 1.0) * 100.0
    dist_ma60 = (cur / ma60 - 1.0) * 100.0

    # 均线斜率
    ma5_arr = _sma(window_close, 5)
    ma20_arr = _sma(window_close, 20)
    ma5_slope = 0.0
    if len(window_close) >= 6 and not np.isnan(ma5_arr[-1]) and not np.isnan(ma5_arr[-6]) and ma5_arr[-6] > 0:
        ma5_slope = (float(ma5_arr[-1]) / float(ma5_arr[-6]) - 1.0) * 100.0
    ma20_slope = 0.0
    if len(window_close) >= 21 and not np.isnan(ma20_arr[-1]) and not np.isnan(ma20_arr[-21]) and ma20_arr[-21] > 0:
        ma20_slope = (float(ma20_arr[-1]) / float(ma20_arr[-21]) - 1.0) * 100.0

    # 波动率
    vol_5d = float(np.std(window_close[-5:]) / np.mean(window_close[-5:]) * 100.0) if len(window_close) >= 5 else 0.0
    vol_20d = float(np.std(window_close[-20:]) / np.mean(window_close[-20:]) * 100.0) if len(window_close) >= 20 else 0.0
    vol_ratio_5_20 = (vol_5d / vol_20d) if vol_20d > 0 else 1.0

    # RSI
    rsi_arr = _rsi(window_close, 14)
    rsi_14 = float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50.0

    # MACD
    dif, dea, hist = _macd(window_close)
    macd_dif = float(dif[-1]) if not np.isnan(dif[-1]) else 0.0
    macd_dea = float(dea[-1]) if not np.isnan(dea[-1]) else 0.0
    macd_hist = float(hist[-1]) if not np.isnan(hist[-1]) else 0.0

    # 布林带位置
    bb_mid = ma20
    bb_std_arr = _rolling_std(window_close, 20)
    bb_std = float(bb_std_arr[-1]) if not np.isnan(bb_std_arr[-1]) else 0.0
    if bb_std > 0 and bb_mid > 0:
        bb_position = (cur - bb_mid) / (2.0 * bb_std)
    else:
        bb_position = 0.0

    # 成交额比
    amount_ratio_5_20 = 1.0
    if window_amount is not None and len(window_amount) >= 20:
        am5 = float(np.mean(window_amount[-5:]))
        am20 = float(np.mean(window_amount[-20:]))
        if am20 > 0:
            amount_ratio_5_20 = am5 / am20

    return {
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_10d": ret_10d,
        "ret_20d": ret_20d,
        "dist_ma5": dist_ma5,
        "dist_ma10": dist_ma10,
        "dist_ma20": dist_ma20,
        "dist_ma60": dist_ma60,
        "ma5_slope": ma5_slope,
        "ma20_slope": ma20_slope,
        "vol_5d": vol_5d,
        "vol_20d": vol_20d,
        "vol_ratio_5_20": vol_ratio_5_20,
        "rsi_14": rsi_14,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "macd_hist": macd_hist,
        "bb_position": bb_position,
        "amount_ratio_5_20": amount_ratio_5_20,
    }


def build_training_samples(
    stock_data: dict[str, dict[str, np.ndarray]],
    forward_days: int = 5,
    threshold_pct: float = 2.0,
    sample_step: int = 3,
) -> tuple[pd.DataFrame, np.ndarray, list[tuple[str, int]]]:
    """
    从多只股票的历史K线构建训练样本。

    Args:
        stock_data: {stock_code: {"close": np.ndarray(日线收盘价),
                                    "amount": np.ndarray(日线成交额)}}
        forward_days: 预测未来N日的涨跌
        threshold_pct: 涨幅超过该阈值算正例
        sample_step: 每隔多少个交易日采样一次

    Returns:
        (特征DataFrame, 标签数组, 样本来源 [(stock_code, idx), ...])
    """
    rows: list[dict[str, float]] = []
    labels: list[int] = []
    sources: list[tuple[str, int]] = []

    for code, data in stock_data.items():
        closes = data["close"]
        amounts = data.get("amount")
        n = len(closes)
        if n < 60 + forward_days:
            continue

        amount_arr = amounts if amounts is not None else np.zeros(n, dtype=np.float64)
        if len(amount_arr) != n:
            amount_arr = np.zeros(n, dtype=np.float64)

        for idx in range(60, n - forward_days, sample_step):
            feat = _compute_features_row(closes, amount_arr, idx)
            if feat is None:
                continue
            cur_close = float(closes[idx])
            future_close = float(closes[idx + forward_days])
            if cur_close <= 0:
                continue
            ret_pct = (future_close / cur_close - 1.0) * 100.0
            label = 1 if ret_pct > threshold_pct else 0
            rows.append(feat)
            labels.append(label)
            sources.append((code, idx))

    if not rows:
        return pd.DataFrame(columns=FEATURE_COLS), np.array([], dtype=int), []

    features_df = pd.DataFrame(rows, columns=FEATURE_COLS)
    return features_df, np.array(labels, dtype=int), sources


def _build_model(model_type: str, scale_pos_weight: float = 1.0):
    """根据 model_type 实例化分类器"""
    if model_type == "lightgbm":
        import lightgbm as lgb
        return "lightgbm", lgb.LGBMClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.08,
            num_leaves=15,
            min_child_samples=10,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            verbose=-1,
        )
    if model_type == "xgboost":
        import xgboost as xgb
        return "xgboost", xgb.XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.08,
            min_child_weight=3,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
            verbosity=0,
            random_state=42,
        )
    raise ValueError(f"不支持的模型类型: {model_type}")


def train_and_predict(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_predict: pd.DataFrame,
    model_type: str = "lightgbm",
) -> tuple[Any, np.ndarray, str]:
    """
    训练单模型并返回预测概率。

    Args:
        X_train: 训练特征
        y_train: 训练标签
        X_predict: 待预测特征
        model_type: lightgbm / xgboost

    Returns:
        (训练好的模型, 预测为正例的概率数组, 实际使用的引擎名)
    """
    if len(X_train) == 0 or len(X_predict) == 0:
        return None, np.array([]), model_type

    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    scale_pos_weight = (neg / pos) if pos > 0 else 1.0

    engine_name, model = _build_model(model_type, scale_pos_weight)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_predict)[:, 1]
    return model, proba, engine_name


def probability_to_signal(prob: float, buy_threshold: float = 0.6, sell_threshold: float = 0.3) -> str:
    """根据上涨概率映射为交易信号"""
    if prob >= buy_threshold:
        return "BUY"
    if prob <= sell_threshold:
        return "SELL"
    return "HOLD"


def build_top_reasons(features: dict[str, float], model: Any, feature_cols: list[str], top_k: int = 3) -> list[str]:
    """
    基于特征值和模型重要性生成简要的预测理由。
    """
    if model is None or not features:
        return []

    try:
        importances = model.feature_importances_
    except Exception:
        return []

    if importances is None or len(importances) != len(feature_cols):
        return []

    pairs = list(zip(feature_cols, importances))
    pairs.sort(key=lambda x: x[1], reverse=True)
    top_features = [name for name, _ in pairs[:top_k] if _ > 0]

    reason_map = {
        "ret_1d": "短期动量",
        "ret_5d": "5日动量",
        "ret_10d": "10日动量",
        "ret_20d": "20日动量",
        "dist_ma5": "对MA5偏离",
        "dist_ma10": "对MA10偏离",
        "dist_ma20": "对MA20偏离",
        "dist_ma60": "对MA60偏离",
        "ma5_slope": "MA5趋势",
        "ma20_slope": "MA20趋势",
        "vol_5d": "短期波动",
        "vol_20d": "中期波动",
        "vol_ratio_5_20": "波动率结构",
        "rsi_14": "RSI强弱",
        "macd_dif": "MACD快线",
        "macd_dea": "MACD慢线",
        "macd_hist": "MACD柱体",
        "bb_position": "布林带位置",
        "amount_ratio_5_20": "成交额变化",
    }

    reasons = []
    for fname in top_features:
        label = reason_map.get(fname, fname)
        v = features.get(fname)
        if v is None:
            continue
        if "ret" in fname or "dist" in fname or "slope" in fname:
            if v > 0:
                reasons.append(f"{label}为正 ({v:.2f}%)")
            else:
                reasons.append(f"{label}为负 ({v:.2f}%)")
        elif "vol" in fname:
            reasons.append(f"{label}={v:.2f}")
        elif "rsi" in fname:
            if v >= 70:
                reasons.append(f"{label}超买 ({v:.1f})")
            elif v <= 30:
                reasons.append(f"{label}超卖 ({v:.1f})")
            else:
                reasons.append(f"{label}={v:.1f}")
        elif "macd" in fname:
            if v > 0:
                reasons.append(f"{label}为正")
            else:
                reasons.append(f"{label}为负")
        elif "bb_position" in fname:
            if v > 0.5:
                reasons.append(f"{label}偏上轨")
            elif v < -0.5:
                reasons.append(f"{label}偏下轨")
            else:
                reasons.append(f"{label}居中")
        else:
            reasons.append(f"{label}={v:.2f}")
    return reasons
