"""
信号中心API模块
提供买卖信号的生成、查询和管理功能
数据存储使用MySQL数据库
"""
from __future__ import annotations

import os
import pickle
import threading
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import APIRouter, Body, Query, HTTPException
from pydantic import BaseModel, Field

from core.db import connect, load_mysql_config, query_dict, execute
from core.analysis.ml_signals import (
    FEATURE_COLS,
    build_training_samples,
    train_and_predict,
    probability_to_signal,
    build_top_reasons,
    _compute_features_row,
)
from infra.storage.logging_service import get_logger

logger = get_logger("signals")

# ---------------------------------------------------------------------------
# ML训练缓存：存储训练好的模型及相关数据，避免每次预测都重新训练
# ---------------------------------------------------------------------------
_model_cache: dict[str, dict] = {}
_training_tasks: dict[str, dict] = {}
_training_lock = threading.Lock()

# 模型持久化目录
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "ml_models")


def _get_model_dir() -> str:
    """确保模型目录存在并返回路径"""
    d = os.path.abspath(MODEL_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _save_model_to_disk(model_type: str, cache_data: dict) -> str:
    """将训练好的模型和元数据保存到磁盘文件，文件名包含训练日期时间。

    Returns:
        model_id: 模型唯一标识（如 lightgbm_20260615_231212）
    """
    d = _get_model_dir()
    trained_at = cache_data.get("trained_at", datetime.now().isoformat())
    # 从 ISO 时间提取 YYYYMMDD_HHMMSS
    try:
        dt = datetime.fromisoformat(trained_at)
        date_tag = dt.strftime("%Y%m%d_%H%M%S")
    except Exception:
        date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_id = f"{model_type}_{date_tag}"
    model_path = os.path.join(d, f"{model_id}_model.pkl")
    meta_path = os.path.join(d, f"{model_id}_metadata.pkl")

    model_obj = cache_data.get("model")
    with open(model_path, "wb") as f:
        pickle.dump(model_obj, f)
    meta = {k: v for k, v in cache_data.items() if k != "model"}
    meta["model_id"] = model_id
    meta["model_type"] = model_type
    with open(meta_path, "wb") as f:
        pickle.dump(meta, f)
    logger.info("模型已持久化到磁盘", extra={
        "model_id": model_id,
        "model_path": model_path,
    })
    return model_id


def _load_model_by_id(model_id: str) -> dict | None:
    """按 model_id 从磁盘加载指定模型"""
    d = _get_model_dir()
    model_path = os.path.join(d, f"{model_id}_model.pkl")
    meta_path = os.path.join(d, f"{model_id}_metadata.pkl")

    if not os.path.exists(model_path) or not os.path.exists(meta_path):
        return None

    try:
        with open(model_path, "rb") as f:
            model_obj = pickle.load(f)
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        cache = dict(meta)
        cache["model"] = model_obj
        logger.info("从磁盘加载模型成功", extra={"model_id": model_id})
        return cache
    except Exception as e:
        logger.warning("从磁盘加载模型失败", extra={
            "model_id": model_id,
            "error": str(e),
        })
        return None


def _list_saved_models() -> list[dict]:
    """扫描磁盘，列出所有已训练的模型（仅元数据，不加载模型对象）"""
    d = _get_model_dir()
    if not os.path.isdir(d):
        return []
    models: list[dict] = []
    for fname in os.listdir(d):
        if not fname.endswith("_metadata.pkl"):
            continue
        meta_path = os.path.join(d, fname)
        try:
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            models.append({
                "model_id": meta.get("model_id", fname.replace("_metadata.pkl", "")),
                "model_type": meta.get("model_type", "unknown"),
                "engine": meta.get("engine", "unknown"),
                "trained_at": meta.get("trained_at", ""),
                "train_samples": meta.get("train_samples", 0),
                "stock_count": meta.get("stock_count", 0),
            })
        except Exception:
            continue
    # 按训练时间倒序排列（最新的在前）
    models.sort(key=lambda m: m.get("trained_at", ""), reverse=True)
    return models


def _load_all_models() -> None:
    """启动时扫描磁盘模型列表（仅记录元数据，不加载模型对象到内存）"""
    models = _list_saved_models()
    logger.info("磁盘模型扫描完成", extra={"count": len(models)})


# 启动时加载已有模型
_load_all_models()

router = APIRouter(prefix="/api/v1/signals", tags=["信号中心"])


class SignalResponse(BaseModel):
    """信号响应"""
    id: str
    stock_code: str
    stock_name: str
    signal_type: str
    strength: int
    score: float
    macd: Optional[float]
    rsi: Optional[float]
    ma20: Optional[float]
    close: float
    reason: str
    trade_date: str
    created_at: str


class SignalRuleRequest(BaseModel):
    """信号规则请求"""
    id: str = ""
    name: str
    description: Optional[str] = ""
    conditions: list = Field(default_factory=list)
    logic: str = "AND"
    enabled: bool = True


class RuleBasedSignalRequest(BaseModel):
    """机器学习选股信号生成请求"""
    model: str = Field(default="lightgbm", description="模型名称: lightgbm / xgboost")
    forward_days: int = Field(default=5, ge=2, le=20, description="预测未来N日涨跌")
    threshold_pct: float = Field(default=2.0, ge=0.5, le=10.0, description="正例涨幅阈值(%)")
    train_window: int = Field(default=250, ge=60, le=500, description="训练数据回溯天数")
    sample_step: int = Field(default=3, ge=1, le=10, description="训练样本采样步长")
    buy_threshold: float = Field(default=0.6, ge=0.5, le=0.95, description="BUY 信号概率阈值")
    sell_threshold: float = Field(default=0.3, ge=0.05, le=0.5, description="SELL 信号概率阈值")


def _get_conn():
    cfg = load_mysql_config()
    return connect(cfg)


# ============ 原始信号API ============

@router.get("/", response_model=list[SignalResponse])
async def list_signals(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    signal_type: Optional[str] = Query(None, description="信号类型"),
    stock_code: Optional[str] = Query(None, description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
):
    """
    获取信号列表，支持分页和筛选
    """
    conn = _get_conn()
    try:
        where_parts = ["1=1"]
        params: list[Any] = []
        if signal_type:
            where_parts.append("signal_type = %s")
            params.append(signal_type)
        if stock_code:
            where_parts.append("stock_code = %s")
            params.append(stock_code)
        if start_date:
            where_parts.append("trade_date >= %s")
            params.append(start_date)
        if end_date:
            where_parts.append("trade_date <= %s")
            params.append(end_date)

        where_clause = " AND ".join(where_parts)
        offset = (page - 1) * page_size

        rows = query_dict(
            conn,
            f"SELECT * FROM trade_signals WHERE {where_clause} ORDER BY trade_date DESC, score DESC LIMIT %s OFFSET %s",
            (*params, page_size, offset),
        )
        return [
            SignalResponse(
                id=str(r["id"]),
                stock_code=r["stock_code"],
                stock_name=r.get("stock_name", ""),
                signal_type=r["signal_type"],
                strength=r.get("strength", 0),
                score=float(r.get("score", 0)),
                macd=float(r["macd"]) if r.get("macd") is not None else None,
                rsi=float(r["rsi"]) if r.get("rsi") is not None else None,
                ma20=float(r["ma20"]) if r.get("ma20") is not None else None,
                close=float(r.get("close", 0)),
                reason=r.get("reason", ""),
                trade_date=str(r["trade_date"]),
                created_at=str(r.get("created_at", "")),
            )
            for r in rows
        ]
    except Exception as e:
        logger.error("获取信号列表失败", extra={"error": str(e)})
        return []
    finally:
        conn.close()


@router.post("/rule-based")
async def rule_based_signals(request: RuleBasedSignalRequest = Body(...)) -> dict[str, Any]:
    """
    基于机器学习模型（LightGBM / XGBoost）的选股信号生成。

    股票池：trade_stock_master 中所有 status=active 且非 ST 的股票，无数量限制。
    训练数据：每只股票最近 train_window 个交易日的K线，按 sample_step 采样，
              标签为未来 forward_days 日涨幅是否超过 threshold_pct。
    预测：对每只股票最新一个交易日计算特征，输入训练好的模型得到上涨概率，
          根据阈值映射为 BUY / HOLD / SELL 信号。

    Args:
        request: 包含模型类型及训练/预测参数的请求体

    Returns:
        dict: 包含 items（信号列表）和 total（总数）
    """
    model_type = (request.model or "lightgbm").lower()
    if model_type not in ("lightgbm", "xgboost"):
        model_type = "lightgbm"

    logger.info("ML选股信号请求", extra={
        "model": model_type,
        "forward_days": request.forward_days,
        "threshold_pct": request.threshold_pct,
        "train_window": request.train_window,
    })

    conn = _get_conn()
    try:
        # 查询最新的交易日期
        latest_date_rows = query_dict(
            conn,
            "SELECT MAX(trade_date) as max_date FROM trade_stock_daily",
            ()
        )
        if not latest_date_rows or not latest_date_rows[0].get("max_date"):
            return {"items": [], "total": 0}

        max_dt = latest_date_rows[0]["max_date"]
        if hasattr(max_dt, "strftime"):
            latest_date = max_dt.strftime("%Y-%m-%d")
        else:
            latest_date = str(max_dt)

        # 获取所有活跃且非 ST 的股票池 - 无数量限制
        pool_sql = """
            SELECT stock_code, stock_name
            FROM trade_stock_master
            WHERE status = 'active' AND (is_st IS NULL OR is_st = 0)
              AND (asset_type IS NULL OR asset_type = 'stock')
        """
        pool_rows = query_dict(conn, pool_sql, ())
        if not pool_rows:
            return {"items": [], "total": 0}

        logger.info("获取股票池完成", extra={"count": len(pool_rows), "date": latest_date})

        # 拉取每只股票的训练窗口K线
        stock_data: dict[str, dict[str, np.ndarray]] = {}
        latest_features: dict[str, dict[str, float]] = {}
        latest_indicators: dict[str, dict[str, Any]] = {}

        for pool_item in pool_rows:
            stock_code = pool_item["stock_code"]
            stock_name = pool_item.get("stock_name") or stock_code

            try:
                kline_rows = query_dict(
                    conn,
                    """SELECT trade_date, close_price, amount
                       FROM trade_stock_daily
                       WHERE stock_code = %s AND trade_date <= %s
                         AND close_price IS NOT NULL AND close_price > 0
                       ORDER BY trade_date ASC
                       LIMIT %s""",
                    (stock_code, latest_date, request.train_window + 20),
                )
                if len(kline_rows) < 70 + request.forward_days:
                    continue

                closes = np.array([float(r["close_price"]) for r in kline_rows], dtype=np.float64)
                amounts = np.array(
                    [float(r.get("amount") or 0.0) for r in kline_rows],
                    dtype=np.float64,
                )
                stock_data[stock_code] = {
                    "close": closes,
                    "amount": amounts,
                }

                # 最新一日特征用于预测
                last_idx = len(closes) - 1
                feat = _compute_features_row(closes, amounts, last_idx)
                if feat is None:
                    continue
                latest_features[stock_code] = feat
                latest_indicators[stock_code] = {
                    "name": stock_name,
                    "close": float(closes[-1]),
                    "rsi": feat.get("rsi_14"),
                    "macd": feat.get("macd_hist"),
                    "ma20": float(np.mean(closes[-20:])),
                }
            except Exception as e:
                logger.warning("拉取K线异常",
                               extra={"stock_code": stock_code, "error": str(e)})
                continue

        if not stock_data or not latest_features:
            return {"items": [], "total": 0}

        logger.info("K线拉取完成", extra={
            "stocks_with_data": len(stock_data),
            "stocks_to_predict": len(latest_features),
        })

        # 构造训练样本
        X_train_df, y_train, _sources = build_training_samples(
            stock_data,
            forward_days=request.forward_days,
            threshold_pct=request.threshold_pct,
            sample_step=request.sample_step,
        )
        if len(X_train_df) < 50:
            logger.warning("训练样本不足", extra={"samples": len(X_train_df)})
            return {"items": [], "total": 0}

        # 构造预测样本（按 stock_code 顺序）
        predict_codes = list(latest_features.keys())
        X_predict_df = pd.DataFrame(
            [latest_features[code] for code in predict_codes],
            columns=FEATURE_COLS,
        )

        # 训练和预测
        probas: np.ndarray = np.array([])
        used_engines: list[str] = []
        trained_models: list[Any] = []

        try:
            model, probas, engine_name = train_and_predict(
                X_train_df, y_train, X_predict_df, model_type=model_type,
            )
            if model is not None:
                trained_models = [model]
                used_engines = [engine_name]
        except Exception as e:
            logger.error("模型训练/预测失败", extra={"error": str(e), "model": model_type})
            return {"items": [], "total": 0}

        if len(probas) == 0:
            return {"items": [], "total": 0}

        # 组装返回结果
        items: list[dict[str, Any]] = []
        primary_model = trained_models[0] if trained_models else None

        for code, prob in zip(predict_codes, probas):
            prob_f = float(prob)
            signal = probability_to_signal(
                prob_f,
                buy_threshold=request.buy_threshold,
                sell_threshold=request.sell_threshold,
            )
            indicator = latest_indicators.get(code, {})
            feat_dict = latest_features.get(code, {})

            reasons = build_top_reasons(feat_dict, primary_model, FEATURE_COLS, top_k=3)
            if not reasons:
                if signal == "BUY":
                    reasons = [f"模型预测上涨概率 {prob_f:.1%}，超过买入阈值"]
                elif signal == "SELL":
                    reasons = [f"模型预测上涨概率 {prob_f:.1%}，低于卖出阈值"]
                else:
                    reasons = [f"模型预测上涨概率 {prob_f:.1%}，处于观望区间"]

            items.append({
                "code": code,
                "name": indicator.get("name", code),
                "signal": signal,
                "confidence": round(prob_f, 4),
                "reasons": reasons,
                "indicators": {
                    "rsi": indicator.get("rsi"),
                    "macd": indicator.get("macd"),
                    "ma20": indicator.get("ma20"),
                    "close": indicator.get("close"),
                },
            })

        # 排序：BUY 优先，再按上涨概率降序
        def _sort_key(item: dict) -> tuple:
            order = {"BUY": 0, "HOLD": 1, "SELL": 2}
            return (order.get(item["signal"], 3), -item.get("confidence", 0.0))

        items.sort(key=_sort_key)

        logger.info("ML选股信号生成完成", extra={
            "model": model_type,
            "engines": used_engines,
            "total": len(items),
            "buys": sum(1 for i in items if i["signal"] == "BUY"),
            "sells": sum(1 for i in items if i["signal"] == "SELL"),
            "train_samples": len(X_train_df),
            "positive_rate": float(y_train.mean()) if len(y_train) else 0.0,
        })

        return {
            "items": items,
            "total": len(items),
        }
    except Exception as e:
        logger.error("ML选股信号生成失败", extra={"error": str(e)})
        return {"items": [], "total": 0}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 分阶段训练 + 预测 API
# ---------------------------------------------------------------------------

class MlTrainRequest(BaseModel):
    """机器学习训练请求参数"""
    model: str = Field(default="lightgbm", description="模型名称: lightgbm / xgboost")
    forward_days: int = Field(default=5, ge=2, le=20, description="预测未来N日涨跌")
    threshold_pct: float = Field(default=2.0, ge=0.5, le=10.0, description="正例涨幅阈值(%)")
    train_window: int = Field(default=250, ge=60, le=500, description="训练数据回溯天数")
    sample_step: int = Field(default=3, ge=1, le=10, description="训练样本采样步长")


class MlPredictRequest(BaseModel):
    """机器学习预测请求参数"""
    model_id: str = Field(..., description="已训练模型的ID（如 lightgbm_20260615_231212）")
    buy_threshold: float = Field(default=0.6, ge=0.5, le=0.95, description="BUY 信号概率阈值")
    sell_threshold: float = Field(default=0.3, ge=0.05, le=0.5, description="SELL 信号概率阈值")
    stock_scope: str = Field(default="all", description="股票范围: all(全部) / sh(上海) / sz(深圳) / cyb(创业板) / kcb(科创板)")
    custom_codes: list[str] = Field(default=[], description="自定义股票代码列表（stock_scope=custom 时使用）")


def _run_training(task_id: str, request: MlTrainRequest) -> None:
    """在后台线程中执行训练，逐步更新进度"""
    model_type = (request.model or "lightgbm").lower()
    if model_type not in ("lightgbm", "xgboost"):
        model_type = "lightgbm"

    def _update(stage: str, progress: int, message: str) -> None:
        with _training_lock:
            _training_tasks[task_id] = {
                "stage": stage,
                "progress": progress,
                "message": message,
            }

    try:
        _update("pool", 5, "获取股票池中...")
        conn = _get_conn()
        try:
            # 查询最新交易日期
            latest_date_rows = query_dict(
                conn,
                "SELECT MAX(trade_date) as max_date FROM trade_stock_daily",
                ()
            )
            if not latest_date_rows or not latest_date_rows[0].get("max_date"):
                _update("error", 0, "无交易数据")
                return

            max_dt = latest_date_rows[0]["max_date"]
            latest_date = max_dt.strftime("%Y-%m-%d") if hasattr(max_dt, "strftime") else str(max_dt)

            # 获取股票池
            pool_rows = query_dict(
                conn,
                """SELECT stock_code, stock_name
                   FROM trade_stock_master
                   WHERE status = 'active' AND (is_st IS NULL OR is_st = 0)
                     AND (asset_type IS NULL OR asset_type = 'stock')
                   LIMIT 500""",
                ()
            )
            if not pool_rows:
                _update("error", 0, "股票池为空")
                return

            total_stocks = len(pool_rows)

            # 拉取每只股票的K线 + 特征提取
            stock_data: dict[str, dict[str, np.ndarray]] = {}
            latest_features: dict[str, dict[str, float]] = {}
            latest_indicators: dict[str, dict[str, Any]] = {}
            skipped = 0

            for i, pool_item in enumerate(pool_rows):
                stock_code = pool_item["stock_code"]
                stock_name = pool_item.get("stock_name") or stock_code

                pct = 5 + int((i + 1) / total_stocks * 50)  # 5% ~ 55%
                _update("features", pct, f"特征提取中... ({i + 1}/{total_stocks})")

                try:
                    kline_rows = query_dict(
                        conn,
                        """SELECT trade_date, close_price, amount
                           FROM trade_stock_daily
                           WHERE stock_code = %s AND trade_date <= %s
                             AND close_price IS NOT NULL AND close_price > 0
                           ORDER BY trade_date ASC
                           LIMIT %s""",
                        (stock_code, latest_date, request.train_window + 20),
                    )
                    if len(kline_rows) < 70 + request.forward_days:
                        skipped += 1
                        continue

                    closes = np.array([float(r["close_price"]) for r in kline_rows], dtype=np.float64)
                    amounts = np.array(
                        [float(r.get("amount") or 0.0) for r in kline_rows],
                        dtype=np.float64,
                    )
                    stock_data[stock_code] = {"close": closes, "amount": amounts}

                    last_idx = len(closes) - 1
                    feat = _compute_features_row(closes, amounts, last_idx)
                    if feat is None:
                        skipped += 1
                        continue
                    latest_features[stock_code] = feat
                    latest_indicators[stock_code] = {
                        "name": stock_name,
                        "close": float(closes[-1]),
                        "rsi": feat.get("rsi_14"),
                        "macd": feat.get("macd_hist"),
                        "ma20": float(np.mean(closes[-20:])),
                    }
                except Exception:
                    skipped += 1
                    continue

            if not stock_data:
                _update("error", 0, "无可用的训练数据")
                return

            _update("samples", 60, "构建训练样本中...")

            # 构造训练样本
            X_train_df, y_train, _sources = build_training_samples(
                stock_data,
                forward_days=request.forward_days,
                threshold_pct=request.threshold_pct,
                sample_step=request.sample_step,
            )
            if len(X_train_df) < 50:
                _update("error", 0, f"训练样本不足 ({len(X_train_df)} < 50)")
                return

            _update("training", 75, f"模型训练中... (样本数: {len(X_train_df)})")

            # 构造预测样本
            predict_codes = list(latest_features.keys())
            X_predict_df = pd.DataFrame(
                [latest_features[code] for code in predict_codes],
                columns=FEATURE_COLS,
            )

            # 训练模型
            model, probas, engine_name = train_and_predict(
                X_train_df, y_train, X_predict_df, model_type=model_type,
            )
            if model is None:
                _update("error", 0, "模型训练失败")
                return

            # 缓存训练结果到内存
            model_id = _save_model_to_disk(model_type, {
                "model": model,
                "engine": engine_name,
                "predict_codes": predict_codes,
                "latest_indicators": latest_indicators,
                "latest_features": latest_features,
                "train_samples": len(X_train_df),
                "stock_count": len(stock_data),
                "trained_at": datetime.now().isoformat(),
                "forward_days": request.forward_days,
                "threshold_pct": request.threshold_pct,
            })

            with _training_lock:
                _model_cache[model_id] = _load_model_by_id(model_id)

            _update("done", 100, f"训练完成! 模型: {model_id}, 数据: {len(stock_data)}只, 样本: {len(X_train_df)}条")

        finally:
            conn.close()
    except Exception as e:
        logger.error("后台训练异常", extra={"task_id": task_id, "error": str(e)})
        _update("error", 0, f"训练异常: {str(e)[:80]}")


@router.post("/train")
def start_training(request: MlTrainRequest = Body(...)) -> dict[str, Any]:
    """
    启动ML模型训练（后台异步执行）。
    训练过程包含：特征提取 → 训练样本构建 → 模型训练。
    通过 /train-status/{task_id} 轮询进度。
    """
    task_id = str(uuid4())
    model_type = (request.model or "lightgbm").lower()

    with _training_lock:
        _training_tasks[task_id] = {
            "stage": "queued",
            "progress": 0,
            "message": "排队中...",
        }

    thread = threading.Thread(target=_run_training, args=(task_id, request), daemon=True)
    thread.start()

    logger.info("ML训练任务已启动", extra={
        "task_id": task_id,
        "model": model_type,
        "forward_days": request.forward_days,
    })

    return {
        "task_id": task_id,
        "status": "started",
        "message": "训练任务已启动，请通过 /train-status/{task_id} 查询进度",
    }


@router.get("/train-status/{task_id}")
def get_training_status(task_id: str) -> dict[str, Any]:
    """
    查询ML训练任务的当前进度。
    """
    with _training_lock:
        status = _training_tasks.get(task_id)
    if status is None:
        return {"stage": "unknown", "progress": 0, "message": "未知任务ID"}
    if status["stage"] == "done":
        # 完成后保留一段时间，不自动清理
        pass
    return dict(status)


@router.get("/models")
def list_models() -> dict[str, Any]:
    """列出所有已训练的模型，按框架分组"""
    models = _list_saved_models()
    # 按 model_type 分组
    grouped: dict[str, list] = {}
    for m in models:
        mt = m.get("model_type", "unknown")
        grouped.setdefault(mt, []).append(m)
    return {"models": models, "grouped": grouped}


@router.delete("/models/{model_id}")
def delete_model(model_id: str) -> dict[str, Any]:
    """删除指定的已训练模型"""
    d = _get_model_dir()
    model_path = os.path.join(d, f"{model_id}_model.pkl")
    meta_path = os.path.join(d, f"{model_id}_metadata.pkl")
    deleted = False
    if os.path.exists(model_path):
        os.remove(model_path)
        deleted = True
    if os.path.exists(meta_path):
        os.remove(meta_path)
        deleted = True
    # 从内存缓存中移除
    with _training_lock:
        _model_cache.pop(model_id, None)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在")
    logger.info("模型已删除", extra={"model_id": model_id})
    return {"status": "deleted", "model_id": model_id}


# 股票范围过滤逻辑
_SCOPE_FILTERS = {
    "all": lambda code: True,
    "sh": lambda code: code.endswith(".SH") and code.startswith("60"),
    "sz": lambda code: code.endswith(".SZ") and (code.startswith("00") or code.startswith("30")),
    "cyb": lambda code: code.endswith(".SZ") and code.startswith("30"),
    "kcb": lambda code: code.endswith(".SH") and code.startswith("68"),
    "sz_main": lambda code: code.endswith(".SZ") and code.startswith("00"),
}


@router.post("/ml-predict")
def ml_predict(request: MlPredictRequest = Body(...)) -> dict[str, Any]:
    """使用指定的已训练模型生成预测信号。"""
    model_id = request.model_id

    # 从内存或磁盘加载模型
    with _training_lock:
        cache = _model_cache.get(model_id)
    if not cache:
        cache = _load_model_by_id(model_id)
        if cache:
            with _training_lock:
                _model_cache[model_id] = cache
    if not cache:
        raise HTTPException(status_code=400, detail=f"模型 {model_id} 不存在，请检查模型ID")

    model = cache["model"]
    all_codes = cache["predict_codes"]
    latest_features = cache["latest_features"]
    latest_indicators = cache["latest_indicators"]

    # 按股票范围过滤
    scope = request.stock_scope or "all"
    if scope == "custom" and request.custom_codes:
        code_set = set(request.custom_codes)
        predict_codes = [c for c in all_codes if c in code_set]
    elif scope in _SCOPE_FILTERS:
        filter_fn = _SCOPE_FILTERS[scope]
        predict_codes = [c for c in all_codes if filter_fn(c)]
    else:
        predict_codes = list(all_codes)

    if not predict_codes:
        return {"items": [], "total": 0, "model_info": {
            "model_id": model_id,
            "engine": cache.get("engine", "unknown"),
            "trained_at": cache.get("trained_at", ""),
        }}

    logger.info("ML预测请求", extra={
        "model_id": model_id,
        "scope": scope,
        "stocks": len(predict_codes),
    })

    # 构造预测样本
    X_predict_df = pd.DataFrame(
        [latest_features[code] for code in predict_codes],
        columns=FEATURE_COLS,
    )

    # 预测概率
    try:
        probas = model.predict_proba(X_predict_df)
        if probas.ndim == 2 and probas.shape[1] >= 2:
            probas = probas[:, 1]
    except Exception:
        probas = model.predict(X_predict_df)

    items: list[dict[str, Any]] = []
    for code, prob in zip(predict_codes, probas):
        prob_f = float(prob)
        signal = probability_to_signal(
            prob_f,
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
        )
        indicator = latest_indicators.get(code, {})
        feat_dict = latest_features.get(code, {})

        reasons = build_top_reasons(feat_dict, model, FEATURE_COLS, top_k=3)
        if not reasons:
            if signal == "BUY":
                reasons = [f"模型预测上涨概率 {prob_f:.1%}，超过买入阈值"]
            elif signal == "SELL":
                reasons = [f"模型预测上涨概率 {prob_f:.1%}，低于卖出阈值"]
            else:
                reasons = [f"模型预测上涨概率 {prob_f:.1%}，处于观望区间"]

        items.append({
            "code": code,
            "name": indicator.get("name", code),
            "signal": signal,
            "confidence": round(prob_f, 4),
            "reasons": reasons,
            "indicators": {
                "rsi": indicator.get("rsi"),
                "macd": indicator.get("macd"),
                "ma20": indicator.get("ma20"),
                "close": indicator.get("close"),
            },
        })

    def _sort_key(item: dict) -> tuple:
        order = {"BUY": 0, "HOLD": 1, "SELL": 2}
        return (order.get(item["signal"], 3), -item.get("confidence", 0.0))

    items.sort(key=_sort_key)

    logger.info("ML预测完成", extra={
        "model_id": model_id,
        "total": len(items),
        "buys": sum(1 for i in items if i["signal"] == "BUY"),
    })

    return {
        "items": items,
        "total": len(items),
        "model_info": {
            "model_id": model_id,
            "engine": cache.get("engine", "unknown"),
            "trained_at": cache.get("trained_at", ""),
            "train_samples": cache.get("train_samples", 0),
            "stock_count": cache.get("stock_count", 0),
        },
    }
