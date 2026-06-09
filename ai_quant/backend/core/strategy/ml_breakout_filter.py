"""
ML突破过滤器
复刻自 参考代码/海龟ML增强.py
提供 特征工程 + 模型训练 + 预测生成 三段式流程
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "atr_ratio", "adx", "vol_ratio", "rsi",
    "breakout_strength", "momentum_5d",
    "consolidation_days", "atr_change",
]


def _try_import_talib():
    try:
        import talib
        return talib
    except Exception:
        return None


def _calc_indicators_fallback(df: pd.DataFrame, atr_period: int = 20) -> dict[str, np.ndarray]:
    """当 TA-Lib 不可用时的回退实现（与 TA-Lib 计算方式保持一致）"""
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)
    volume = df["volume"].values.astype(np.float64)

    n = len(close)
    atr = np.full(n, np.nan)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    for i in range(atr_period - 1, n):
        atr[i] = tr[i - atr_period + 1:i + 1].mean()

    adx = np.full(n, np.nan)
    period = 14
    if n > period * 2:
        up_move = np.diff(high, prepend=high[0])
        down_move = -np.diff(low, prepend=low[0])
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        atr14 = np.zeros(n)
        atr14[:period] = tr[:period].mean()
        for i in range(period, n):
            atr14[i] = (atr14[i - 1] * (period - 1) + tr[i]) / period
        plus_di = 100 * plus_dm / np.where(atr14 == 0, 1, atr14)
        minus_di = 100 * minus_dm / np.where(atr14 == 0, 1, atr14)
        dx = 100 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di))
        adx[:period * 2] = np.nan
        for i in range(period * 2, n):
            adx[i] = dx[i - period + 1:i + 1].mean()

    rsi = np.full(n, np.nan)
    if n > 15:
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.zeros(n); avg_loss = np.zeros(n)
        avg_gain[14] = gain[:15].mean(); avg_loss[14] = loss[:15].mean()
        for i in range(15, n):
            avg_gain[i] = (avg_gain[i - 1] * 13 + gain[i]) / 14
            avg_loss[i] = (avg_loss[i - 1] * 13 + loss[i]) / 14
        rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
        rsi = 100 - 100 / (1 + rs)
        rsi[:15] = np.nan

    vol_ma = pd.Series(volume).rolling(20).mean().values

    return {"atr": atr, "adx": adx, "rsi": rsi, "vol_ma": vol_ma}


def compute_features(df: pd.DataFrame, entry_period: int = 20, atr_period: int = 20) -> tuple[pd.DataFrame, np.ndarray, list[int]]:
    """
    在每个突破点提取市场特征
    返回: (features_df按日期索引, labels数组, breakout_indices原始索引列表)
    """
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)
    volume = df["volume"].values.astype(np.float64)

    talib = _try_import_talib()
    if talib is not None:
        atr = talib.ATR(high, low, close, timeperiod=atr_period)
        adx = talib.ADX(high, low, close, timeperiod=14)
        rsi = talib.RSI(close, timeperiod=14)
        vol_ma = talib.SMA(volume, timeperiod=20)
    else:
        ind = _calc_indicators_fallback(df, atr_period)
        atr = ind["atr"]; adx = ind["adx"]; rsi = ind["rsi"]; vol_ma = ind["vol_ma"]

    donchian_high = pd.Series(high).rolling(entry_period).max().shift(1).values

    min_idx = max(entry_period, atr_period, 14) + 20

    features_list: list[dict] = []
    labels_list: list[float] = []
    breakout_indices: list[int] = []

    for i in range(min_idx, len(df)):
        if close[i] <= donchian_high[i]:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        if np.isnan(adx[i]) or np.isnan(rsi[i]):
            continue
        if np.isnan(vol_ma[i]) or vol_ma[i] <= 0:
            continue

        momentum_5d = close[i] / close[i - 5] - 1 if i >= 5 else 0.0

        consolidation_days = 0
        for j in range(i - 1, max(i - 60, min_idx), -1):
            if close[j] > donchian_high[j]:
                break
            consolidation_days += 1

        atr_change = (atr[i] / atr[i - 5] - 1) if (i >= 5 and not np.isnan(atr[i - 5]) and atr[i - 5] > 0) else 0.0

        features_list.append({
            "atr_ratio": atr[i] / close[i],
            "adx": adx[i],
            "vol_ratio": volume[i] / vol_ma[i],
            "rsi": rsi[i],
            "breakout_strength": (close[i] - donchian_high[i]) / atr[i],
            "momentum_5d": momentum_5d,
            "consolidation_days": consolidation_days,
            "atr_change": atr_change,
        })

        if i + 5 < len(df):
            future_max = float(np.max(close[i + 1:i + 6]))
            labels_list.append(1 if (future_max / close[i] - 1) > 0.02 else 0)
        else:
            labels_list.append(np.nan)
        breakout_indices.append(i)

    if not features_list:
        return pd.DataFrame(columns=FEATURE_COLS), np.array([]), []

    features_df = pd.DataFrame(features_list, index=[df.index[i] for i in breakout_indices])
    labels = np.array(labels_list, dtype=float)
    valid = ~np.isnan(labels)
    return features_df[valid], labels[valid].astype(int), [bi for bi, v in zip(breakout_indices, valid) if v]


def collect_multi_stock_features(
    stock_dfs: list[tuple[str, pd.DataFrame]],
    entry_period: int = 20,
    atr_period: int = 20,
) -> tuple[pd.DataFrame, np.ndarray, dict[str, list[int]]]:
    """从多只股票收集突破事件特征
    stock_dfs: [(stock_code, df), ...]
    返回: (combined_features, combined_labels, {code: breakout_indices_in_its_df})
    """
    all_features: list[pd.DataFrame] = []
    all_labels: list[np.ndarray] = []
    stock_breakout_indices: dict[str, list[int]] = {}

    for code, df in stock_dfs:
        try:
            feat, lab, idx = compute_features(df, entry_period, atr_period)
            if len(feat) > 0:
                all_features.append(feat)
                all_labels.append(lab)
                stock_breakout_indices[code] = idx
        except Exception as e:
            logger.warning("compute_features for %s failed: %s", code, e)

    if not all_features:
        return pd.DataFrame(columns=FEATURE_COLS), np.array([]), {}

    combined = pd.concat(all_features).sort_index()
    combined_labels = np.concatenate(all_labels)
    return combined, combined_labels, stock_breakout_indices


def _try_select_engine(prefer: str = "auto") -> tuple[str, Any]:
    """按指定或默认顺序选择 ML 引擎
    prefer: auto/lightgbm/xgboost/sklearn
    """
    def _try_lgb():
        try:
            import lightgbm as lgb
            return "lightgbm", lgb
        except Exception:
            return None
    def _try_xgb():
        try:
            import xgboost as xgb
            return "xgboost", xgb
        except Exception:
            return None
    def _try_sklearn():
        from sklearn.ensemble import GradientBoostingClassifier
        return "sklearn", GradientBoostingClassifier

    prefer = (prefer or "auto").lower()
    if prefer == "lightgbm":
        r = _try_lgb()
        if r: return r
        raise ImportError("lightgbm 未安装")
    if prefer == "xgboost":
        r = _try_xgb()
        if r: return r
        raise ImportError("xgboost 未安装")
    if prefer == "sklearn":
        return _try_sklearn()

    # auto: 按 lightgbm -> xgboost -> sklearn 顺序选择
    r = _try_lgb()
    if r: return r
    r = _try_xgb()
    if r: return r
    return _try_sklearn()


def train_model(features_df: pd.DataFrame, labels: np.ndarray, split_date: str, engine: str = "auto") -> tuple[Any | None, dict[str, Any], str]:
    """训练模型
    split_date: 训练/测试分割日期 (此日期前训练, 此日期后测试)
    engine: 引擎选择 auto/lightgbm/xgboost/sklearn
    """
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    try:
        engine_name, lib = _try_select_engine(engine)
    except ImportError as e:
        logger.warning("指定引擎不可用: %s，将回退到 auto", e)
        engine_name, lib = _try_select_engine("auto")
    engine = engine_name
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    split_ts = pd.Timestamp(split_date)
    train_mask = features_df.index < split_ts
    test_mask = features_df.index >= split_ts

    if not train_mask.any() or not test_mask.any():
        logger.warning("训练集或测试集为空: train=%d, test=%d", int(train_mask.sum()), int(test_mask.sum()))
        return None, {}, engine

    X_train = features_df[train_mask]
    y_train = labels[train_mask]
    X_test = features_df[test_mask]
    y_test = labels[test_mask]

    if len(X_train) < 5 or len(X_test) < 3:
        logger.warning("样本不足: 训练%d, 测试%d (需训练>=5 测试>=3)", len(X_train), len(X_test))
        return None, {}, engine

    if engine == "lightgbm":
        model = lib.LGBMClassifier(
            n_estimators=80, max_depth=3, learning_rate=0.1,
            min_child_samples=3, reg_alpha=0.1, reg_lambda=1.0,
            is_unbalance=True, verbose=-1, random_state=42,
        )
    elif engine == "xgboost":
        pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
        model = lib.XGBClassifier(
            n_estimators=80, max_depth=3, learning_rate=0.1,
            min_child_weight=3, reg_alpha=0.1, reg_lambda=1.0,
            scale_pos_weight=pos_weight, eval_metric="logloss",
            verbosity=0, random_state=42,
        )
    else:
        model = lib(
            n_estimators=80, max_depth=3, learning_rate=0.1,
            min_samples_leaf=3, random_state=42,
        )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "engine": engine,
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "train_positive_rate": float(y_train.mean()),
        "test_positive_rate": float(y_test.mean()),
    }

    logger.info(
        "ML训练完成: 引擎=%s 训练=%d(正例率%.0f%%) 测试=%d(正例率%.0f%%) 准确率=%.1f%% 精确率=%.1f%% 召回率=%.1f%%",
        engine, metrics["train_size"], metrics["train_positive_rate"] * 100,
        metrics["test_size"], metrics["test_positive_rate"] * 100,
        metrics["accuracy"] * 100, metrics["precision"] * 100, metrics["recall"] * 100,
    )

    return model, metrics, engine


def generate_predictions(model: Any, features_df: pd.DataFrame) -> dict[str, float]:
    """为所有突破事件生成预测概率"""
    if features_df.empty:
        return {}
    probas = model.predict_proba(features_df)[:, 1]
    predictions: dict[str, float] = {}
    for date, prob in zip(features_df.index, probas):
        d = date.date().isoformat() if hasattr(date, "date") else str(date)
        predictions[d] = float(prob)
    return predictions


def auto_train_predictions(
    target_code: str,
    target_df: pd.DataFrame,
    train_stocks: list[tuple[str, pd.DataFrame]],
    split_date: str,
    entry_period: int = 20,
    atr_period: int = 20,
) -> tuple[dict[str, float], dict[str, Any]]:
    """端到端: 收集多股票特征 → 训练模型 → 为目标股票生成预测
    返回: (predictions, metrics)
    """
    combined_features, combined_labels, _ = collect_multi_stock_features(
        train_stocks, entry_period, atr_period,
    )

    if len(combined_features) < 10:
        logger.warning("总样本不足(%d), 无法训练", len(combined_features))
        return {}, {"error": "insufficient_samples", "total": int(len(combined_features))}

    model, metrics, engine = train_model(combined_features, combined_labels, split_date)
    if model is None:
        return {}, {**metrics, "error": "training_failed"}

    target_features, _, _ = compute_features(target_df, entry_period, atr_period)
    predictions = generate_predictions(model, target_features)
    high_prob = sum(1 for p in predictions.values() if p >= 0.5)
    metrics["target_breakouts"] = int(len(predictions))
    metrics["target_high_prob"] = int(high_prob)
    logger.info(
        "目标股票 %s 突破事件=%d ML通过(>=0.5)=%d",
        target_code, len(predictions), high_prob,
    )
    return predictions, metrics
