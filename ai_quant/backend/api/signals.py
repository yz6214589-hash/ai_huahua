"""
信号中心API模块
提供买卖信号的生成、查询和管理功能
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel, Field

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


SIGNALS_STORE: list[dict[str, Any]] = []
RULES_STORE: list[dict[str, Any]] = []


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
    global SIGNALS_STORE
    if not SIGNALS_STORE:
        SIGNALS_STORE.extend(generate_mock_signals())

    signals = SIGNALS_STORE.copy()
    if signal_type:
        signals = [s for s in signals if s["signal_type"] == signal_type]
    if strength_min > 0:
        signals = [s for s in signals if s["strength"] >= strength_min]
    if keyword:
        kw = keyword.lower()
        signals = [s for s in signals if kw in s["stock_code"].lower() or kw in s["stock_name"].lower()]

    total = len(signals)
    start_idx = (page - 1) * page_size
    signals = signals[start_idx:start_idx + page_size]

    return {
        "items": signals,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/rules", response_model=list)
async def get_rules() -> list[dict[str, Any]]:
    """获取信号规则列表"""
    return RULES_STORE


@router.post("/rules", response_model=dict)
async def create_rule(rule: SignalRuleRequest) -> dict[str, Any]:
    """创建信号规则"""
    rule_dict = rule.model_dump()
    if not rule_dict.get("id"):
        rule_dict["id"] = str(uuid4())
    RULES_STORE.append(rule_dict)
    return rule_dict


@router.put("/rules/{rule_id}", response_model=dict)
async def update_rule(rule_id: str, rule: SignalRuleRequest) -> dict[str, Any]:
    """更新信号规则"""
    for i, r in enumerate(RULES_STORE):
        if r["id"] == rule_id:
            rule_dict = rule.model_dump()
            rule_dict["id"] = rule_id
            RULES_STORE[i] = rule_dict
            return rule_dict
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="规则不存在")


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str) -> dict[str, str]:
    """删除信号规则"""
    global RULES_STORE
    initial_len = len(RULES_STORE)
    RULES_STORE = [r for r in RULES_STORE if r["id"] != rule_id]
    if len(RULES_STORE) == initial_len:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"deleted": rule_id}


@router.post("/generate")
async def generate_signals(
    request: SignalGenerateRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """生成信号"""
    global SIGNALS_STORE
    SIGNALS_STORE = generate_mock_signals()
    return {
        "message": "信号生成完成",
        "count": len(SIGNALS_STORE),
        "signals": SIGNALS_STORE[:20],
    }


@router.post("/refresh")
async def refresh_signals() -> dict[str, Any]:
    """刷新信号数据"""
    global SIGNALS_STORE
    SIGNALS_STORE = generate_mock_signals()
    return {"message": "信号已刷新", "count": len(SIGNALS_STORE)}


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
    return [
        {"stat_date": datetime.now().strftime("%Y-%m-%d"), "buy_count": 5, "sell_count": 3, "avg_strength": 4.2}
    ]


@router.delete("/{signal_id}")
async def delete_signal_by_id(signal_id: str) -> dict[str, str]:
    """删除信号"""
    return {"deleted": signal_id}
