"""
信号中心API模块
提供买卖信号的生成、查询和管理功能
数据存储使用MySQL数据库
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
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


class SignalGenerateRequest(BaseModel):
    """信号生成请求"""
    stock_codes: list[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    use_rules: bool = Field(default=True)


def _get_conn():
    """获取数据库连接"""
    cfg = load_mysql_config()
    return connect(cfg)


@router.get("", response_model=dict)
async def get_signals(
    signal_type: Optional[str] = Query(None),
    strength_min: int = Query(0, ge=0, le=5),
    keyword: Optional[str] = Query(None),
    stock_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取信号列表"""
    logger.info("开始获取信号列表", extra={
        "filters": {
            "signal_type": signal_type,
            "strength_min": strength_min,
            "keyword": keyword,
            "stock_code": stock_code,
            "start_date": start_date,
            "end_date": end_date
        },
        "pagination": {"page": page, "page_size": page_size}
    })

    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if signal_type:
            conditions.append("signal_type = %s")
            params.append(signal_type)
        if strength_min > 0:
            conditions.append("strength >= %s")
            params.append(strength_min)
        if keyword:
            conditions.append("(stock_code LIKE %s OR stock_name LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)
        if start_date:
            conditions.append("trade_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)

        logger.debug("构建查询条件", extra={
            "where_clause": where,
            "params_count": len(params)
        })

        count_sql = f"SELECT COUNT(*) as total FROM trade_signal_record WHERE {where}"
        logger.debug("执行总数查询", extra={"sql": count_sql[:200]})
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        logger.debug("查询总数完成", extra={"total": total})

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT signal_id as id, stock_code, stock_name, signal_type, strength, score,
                   macd, rsi, ma20, close_price as close, reason, trade_date, created_at
            FROM trade_signal_record
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        logger.debug("执行信号数据查询", extra={
            "offset": offset,
            "limit": page_size
        })
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        logger.info("信号数据查询完成", extra={
            "returned_count": len(rows),
            "total": total
        })

        for row in rows:
            if row.get("created_at"):
                row["created_at"] = str(row["created_at"])
            if row.get("trade_date"):
                row["trade_date"] = str(row["trade_date"])

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取信号列表失败", extra={"error": str(e)})
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.get("/rules", response_model=list)
async def get_rules() -> list[dict[str, Any]]:
    """获取信号规则列表"""
    logger.info("开始获取信号规则列表")
    conn = _get_conn()
    try:
        logger.debug("查询信号规则表")
        rules = query_dict(conn, "SELECT * FROM trade_signal_rule ORDER BY priority DESC, created_at DESC", ())
        logger.debug(f"查询到 {len(rules)} 条规则")
        
        for rule in rules:
            rule_id = rule["id"]
            logger.debug(f"查询规则 {rule_id} 的条件", extra={"rule_id": rule_id})
            conditions = query_dict(
                conn,
                "SELECT * FROM trade_signal_rule_condition WHERE rule_id = %s ORDER BY sort_order",
                (rule_id,)
            )
            rule["conditions"] = conditions
            rule["logic"] = rule.get("logic_type", "AND")
            if rule.get("created_at"):
                rule["created_at"] = str(rule["created_at"])
            if rule.get("updated_at"):
                rule["updated_at"] = str(rule["updated_at"])
            logger.debug(f"规则 {rule_id} 有 {len(conditions)} 个条件", extra={
                "rule_id": rule_id,
                "conditions_count": len(conditions)
            })
        
        logger.info(f"获取信号规则成功，共 {len(rules)} 条")
        return rules
    except Exception as e:
        logger.error("获取信号规则失败", extra={"error": str(e)})
        return []
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.post("/rules", response_model=dict)
async def create_rule(rule: SignalRuleRequest) -> dict[str, Any]:
    """创建信号规则"""
    logger.info("开始创建信号规则", extra={
        "rule_name": rule.name,
        "conditions_count": len(rule.conditions),
        "enabled": rule.enabled
    })
    conn = _get_conn()
    try:
        rule_id = rule.id or str(uuid4())
        logger.debug(f"插入规则表，rule_id: {rule_id}")
        execute(
            conn,
            """INSERT INTO trade_signal_rule (id, name, description, logic_type, enabled)
               VALUES (%s, %s, %s, %s, %s)""",
            (rule_id, rule.name, rule.description, rule.logic, 1 if rule.enabled else 0)
        )
        logger.debug("规则插入成功，开始插入条件")
        
        for idx, cond in enumerate(rule.conditions):
            cond_id = str(uuid4())
            logger.debug(f"插入条件 {idx + 1}/{len(rule.conditions)}", extra={
                "indicator": cond.get("indicator"),
                "operator": cond.get("operator")
            })
            execute(
                conn,
                """INSERT INTO trade_signal_rule_condition (id, rule_id, indicator, operator, threshold_value, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (cond_id, rule_id, cond.get("indicator", ""), cond.get("operator", "gt"),
                 cond.get("threshold_value", 0), idx)
            )
        
        logger.info(f"信号规则创建成功，rule_id: {rule_id}", extra={"rule_id": rule_id})
        return {"id": rule_id, "name": rule.name, "description": rule.description,
                "logic": rule.logic, "enabled": rule.enabled, "conditions": rule.conditions}
    except Exception as e:
        logger.error("创建信号规则失败", extra={"error": str(e), "rule_name": rule.name})
        raise HTTPException(status_code=500, detail=f"创建规则失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.put("/rules/{rule_id}", response_model=dict)
async def update_rule(rule_id: str, rule: SignalRuleRequest) -> dict[str, Any]:
    """更新信号规则"""
    logger.info("开始更新信号规则", extra={"rule_id": rule_id, "rule_name": rule.name})
    conn = _get_conn()
    try:
        logger.debug("检查规则是否存在")
        existing = query_dict(conn, "SELECT id FROM trade_signal_rule WHERE id = %s", (rule_id,))
        if not existing:
            logger.warning("规则不存在", extra={"rule_id": rule_id})
            raise HTTPException(status_code=404, detail="规则不存在")

        logger.debug("更新规则基本信息")
        execute(
            conn,
            """UPDATE trade_signal_rule SET name = %s, description = %s, logic_type = %s, enabled = %s
               WHERE id = %s""",
            (rule.name, rule.description, rule.logic, 1 if rule.enabled else 0, rule_id)
        )
        
        logger.debug("删除原有条件")
        execute(conn, "DELETE FROM trade_signal_rule_condition WHERE rule_id = %s", (rule_id,))
        
        logger.debug(f"插入新的条件，共 {len(rule.conditions)} 个")
        for idx, cond in enumerate(rule.conditions):
            cond_id = str(uuid4())
            logger.debug(f"插入条件 {idx + 1}/{len(rule.conditions)}", extra={
                "indicator": cond.get("indicator"),
                "operator": cond.get("operator")
            })
            execute(
                conn,
                """INSERT INTO trade_signal_rule_condition (id, rule_id, indicator, operator, threshold_value, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (cond_id, rule_id, cond.get("indicator", ""), cond.get("operator", "gt"),
                 cond.get("threshold_value", 0), idx)
            )
        
        logger.info(f"信号规则更新成功，rule_id: {rule_id}", extra={"rule_id": rule_id})
        return {"id": rule_id, "name": rule.name, "description": rule.description,
                "logic": rule.logic, "enabled": rule.enabled, "conditions": rule.conditions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新信号规则失败", extra={"error": str(e), "rule_id": rule_id})
        raise HTTPException(status_code=500, detail=f"更新规则失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str) -> dict[str, str]:
    """删除信号规则"""
    logger.info("开始删除信号规则", extra={"rule_id": rule_id})
    conn = _get_conn()
    try:
        logger.debug("检查规则是否存在")
        existing = query_dict(conn, "SELECT id FROM trade_signal_rule WHERE id = %s", (rule_id,))
        if not existing:
            logger.warning("规则不存在", extra={"rule_id": rule_id})
            raise HTTPException(status_code=404, detail="规则不存在")
        
        logger.debug("删除规则条件")
        execute(conn, "DELETE FROM trade_signal_rule_condition WHERE rule_id = %s", (rule_id,))
        
        logger.debug("删除规则")
        execute(conn, "DELETE FROM trade_signal_rule WHERE id = %s", (rule_id,))
        
        logger.info(f"信号规则删除成功，rule_id: {rule_id}", extra={"rule_id": rule_id})
        return {"deleted": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除信号规则失败", extra={"error": str(e), "rule_id": rule_id})
        raise HTTPException(status_code=500, detail=f"删除规则失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.post("/generate")
async def generate_signals(
    request: SignalGenerateRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """生成信号"""
    logger.info("开始生成信号", extra={
        "stock_codes_count": len(request.stock_codes),
        "use_rules": request.use_rules
    })
    mock_signals = generate_mock_signals()
    logger.debug(f"生成了 {len(mock_signals)} 条模拟信号")
    
    conn = _get_conn()
    try:
        saved_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, sig in enumerate(mock_signals):
            try:
                logger.debug(f"处理信号 {idx + 1}/{len(mock_signals)}", extra={
                    "signal_id": sig["id"],
                    "stock_code": sig["stock_code"]
                })
                existing = query_dict(
                    conn,
                    "SELECT signal_id FROM trade_signal_record WHERE signal_id = %s",
                    (sig["id"],)
                )
                if existing:
                    logger.debug("信号已存在，跳过", extra={"signal_id": sig["id"]})
                    skipped_count += 1
                    continue
                
                execute(
                    conn,
                    """INSERT INTO trade_signal_record
                       (signal_id, stock_code, stock_name, signal_type, strength, score,
                        close_price, reason, macd, rsi, ma20, trade_date, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (sig["id"], sig["stock_code"], sig["stock_name"], sig["signal_type"],
                     sig["strength"], sig["score"], sig["close"], sig["reason"],
                     sig.get("macd"), sig.get("rsi"), sig.get("ma20"),
                     sig["trade_date"], "pending")
                )
                logger.debug(f"信号插入成功，signal_id: {sig['id']}", extra={"signal_id": sig["id"]})
                saved_count += 1
            except Exception as e:
                error_count += 1
                logger.warning(f"处理信号失败，signal_id: {sig['id']}", extra={
                    "signal_id": sig.get("id"),
                    "error": str(e)
                })
                continue
        
        logger.info("信号生成完成", extra={
            "total": len(mock_signals),
            "saved": saved_count,
            "skipped": skipped_count,
            "error": error_count
        })
        return {
            "message": "信号生成完成",
            "count": len(mock_signals),
            "saved": saved_count,
            "signals": mock_signals[:20],
        }
    except Exception as e:
        logger.error("生成信号失败", extra={"error": str(e)})
        return {
            "message": "信号生成完成(未持久化)",
            "count": len(mock_signals),
            "signals": mock_signals[:20],
        }
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.post("/refresh")
async def refresh_signals() -> dict[str, Any]:
    """刷新信号数据"""
    mock_signals = generate_mock_signals()
    conn = _get_conn()
    try:
        saved_count = 0
        for sig in mock_signals:
            try:
                existing = query_dict(
                    conn,
                    "SELECT signal_id FROM trade_signal_record WHERE signal_id = %s",
                    (sig["id"],)
                )
                if existing:
                    continue
                execute(
                    conn,
                    """INSERT INTO trade_signal_record
                       (signal_id, stock_code, stock_name, signal_type, strength, score,
                        close_price, reason, macd, rsi, ma20, trade_date, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (sig["id"], sig["stock_code"], sig["stock_name"], sig["signal_type"],
                     sig["strength"], sig["score"], sig["close"], sig["reason"],
                     sig.get("macd"), sig.get("rsi"), sig.get("ma20"),
                     sig["trade_date"], "pending")
                )
                saved_count += 1
            except Exception:
                continue
        return {"message": "信号已刷新", "count": len(mock_signals), "saved": saved_count}
    except Exception as e:
        logger.error("刷新信号失败", extra={"error": str(e)})
        return {"message": "信号已刷新(未持久化)", "count": len(mock_signals)}
    finally:
        conn.close()


@router.get("/stocks")
async def get_stock_pool() -> list[dict[str, str]]:
    """获取股票池"""
    return [
        {"code": "600519.SH", "name": "贵州茅台"},
        {"code": "300750.SZ", "name": "宁德时代"},
        {"code": "002594.SZ", "name": "比亚迪"},
        {"code": "688041.SH", "name": "寒武纪"},
        {"code": "601318.SH", "name": "中国平安"},
        {"code": "000001.SZ", "name": "平安银行"},
    ]


@router.get("/statistics")
async def get_statistics(
    stat_type: str = Query("DAILY"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> list[dict]:
    """获取信号统计"""
    conn = _get_conn()
    try:
        conditions = ["stat_type = %s"]
        params: list[Any] = [stat_type]
        if start_date:
            conditions.append("stat_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("stat_date <= %s")
            params.append(end_date)
        where = " AND ".join(conditions)

        rows = query_dict(
            conn,
            f"SELECT * FROM trade_signal_statistic WHERE {where} ORDER BY stat_date DESC",
            tuple(params)
        )
        for row in rows:
            if row.get("stat_date"):
                row["stat_date"] = str(row["stat_date"])
            if row.get("created_at"):
                row["created_at"] = str(row["created_at"])
        return rows
    except Exception as e:
        logger.error("获取信号统计失败", extra={"error": str(e)})
        return [
            {"stat_date": datetime.now().strftime("%Y-%m-%d"), "buy_count": 5, "sell_count": 3, "avg_strength": 4.2}
        ]
    finally:
        conn.close()


@router.delete("/{signal_id}")
async def delete_signal_by_id(signal_id: str) -> dict[str, str]:
    """删除信号"""
    conn = _get_conn()
    try:
        execute(conn, "DELETE FROM trade_signal_record WHERE signal_id = %s", (signal_id,))
        return {"deleted": signal_id}
    except Exception as e:
        logger.error("删除信号失败", extra={"error": str(e)})
        return {"deleted": signal_id}
    finally:
        conn.close()


# ============ 机器学习模型信号生成 ============

class RuleBasedSignalRequest(BaseModel):
    """机器学习选股信号生成请求"""
    model: str = Field(default="lightgbm", description="模型名称: lightgbm / xgboost")
    forward_days: int = Field(default=5, ge=2, le=20, description="预测未来N日涨跌")
    threshold_pct: float = Field(default=2.0, ge=0.5, le=10.0, description="正例涨幅阈值(%)")
    train_window: int = Field(default=250, ge=60, le=500, description="训练数据回溯天数")
    sample_step: int = Field(default=3, ge=1, le=10, description="训练样本采样步长")
    buy_threshold: float = Field(default=0.6, ge=0.5, le=0.95, description="BUY 信号概率阈值")
    sell_threshold: float = Field(default=0.3, ge=0.05, le=0.5, description="SELL 信号概率阈值")


@router.post("/rule-based")
async def rule_based_signals(request: RuleBasedSignalRequest) -> dict[str, Any]:
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
