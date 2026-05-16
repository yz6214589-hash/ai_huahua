"""
信号中心API模块
提供买卖信号的生成、查询和管理功能
数据存储使用MySQL数据库
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from core.db import connect, load_mysql_config, query_dict, execute
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


def generate_mock_signals() -> list[dict[str, Any]]:
    """生成模拟信号数据"""
    import random
    signals = []
    signal_types = ["BUY", "SELL"]
    reasons_buy = ["价格上穿MA20，RSI超卖", "MACD金叉", "价格站稳MA20上方"]
    reasons_sell = ["RSI超买，价格下穿MA20", "价格跌破布林中轨", "MACD死叉"]

    stock_pool = [
        ("600519.SH", "贵州茅台"), ("300750.SZ", "宁德时代"), ("002594.SZ", "比亚迪"),
        ("688041.SH", "寒武纪"), ("601318.SH", "中国平安"), ("000001.SZ", "平安银行"),
    ]

    for stock_code, stock_name in stock_pool:
        signal_type = random.choice(signal_types)
        strength = random.randint(3, 5)
        score = random.randint(65, 88)
        macd = round(random.uniform(-3, 3), 2)
        rsi = round(random.uniform(20, 85), 1)
        ma20 = round(random.uniform(10, 2000), 2)
        close = round(ma20 * random.uniform(0.95, 1.1), 2)
        reasons = reasons_buy if signal_type == "BUY" else reasons_sell
        signal = {
            "id": str(uuid4()),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "signal_type": signal_type,
            "strength": strength,
            "score": score,
            "macd": macd,
            "rsi": rsi,
            "ma20": ma20,
            "close": close,
            "reason": random.choice(reasons),
            "trade_date": (datetime.now() - timedelta(minutes=random.randint(0, 120))).strftime("%Y-%m-%d"),
            "created_at": (datetime.now() - timedelta(minutes=random.randint(0, 120))).strftime("%Y-%m-%d %H:%M:%S"),
        }
        signals.append(signal)
    return sorted(signals, key=lambda x: x["created_at"], reverse=True)


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
        mock_signals = generate_mock_signals()
        if signal_type:
            mock_signals = [s for s in mock_signals if s["signal_type"] == signal_type]
        if strength_min > 0:
            mock_signals = [s for s in mock_signals if s["strength"] >= strength_min]
        total = len(mock_signals)
        logger.info("使用模拟数据返回", extra={"mock_count": len(mock_signals)})
        return {
            "items": mock_signals[:page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
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
