"""
模拟盘账户API模块
支持模拟账户管理、交易、持仓查询等功能
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/sim-account", tags=["sim-account"])


class SimAccountCreate(BaseModel):
    """创建模拟盘账户请求"""
    account_name: str = Field(..., min_length=1, max_length=100)
    initial_capital: float = Field(1000000.0, gt=0)
    description: Optional[str] = None


class SimTradeRequest(BaseModel):
    """模拟交易请求"""
    account_id: int = Field(..., gt=0)
    stock_code: str = Field(...)
    stock_name: str = Field(...)
    side: str = Field(...)
    price: float = Field(..., gt=0)
    volume: int = Field(..., gt=0)
    strategy: Optional[str] = None


ACCOUNTS_STORE: list[dict[str, Any]] = []
POSITIONS_STORE: list[dict[str, Any]] = []
TRADES_STORE: list[dict[str, Any]] = []


def _generate_trade_no() -> str:
    """生成成交编号"""
    return f"SIM{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _calculate_commission(price: float, volume: int) -> float:
    """计算手续费"""
    commission = price * volume * 0.0003
    return max(5.0, min(commission, 100.0))


@router.get("/list")
async def get_sim_account_list() -> dict[str, Any]:
    """获取模拟盘账户列表"""
    if not ACCOUNTS_STORE:
        ACCOUNTS_STORE.append({
            "id": 1,
            "account_name": "默认模拟账户",
            "initial_capital": 1000000.0,
            "current_capital": 1000000.0,
            "market_value": 0.0,
            "total_asset": 1000000.0,
            "total_pnl": 0.0,
            "position_count": 0,
            "status": "active",
            "created_at": datetime.now().isoformat(),
        })
    return {"accounts": ACCOUNTS_STORE, "total": len(ACCOUNTS_STORE)}


@router.get("/detail/{account_id}")
async def get_sim_account_detail(account_id: int) -> dict[str, Any]:
    """获取模拟盘账户详情"""
    account = next((a for a in ACCOUNTS_STORE if a["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    return account


@router.post("/create")
async def create_sim_account(request: SimAccountCreate) -> dict[str, Any]:
    """创建模拟盘账户"""
    account_id = len(ACCOUNTS_STORE) + 1
    account = {
        "id": account_id,
        "account_name": request.account_name,
        "initial_capital": request.initial_capital,
        "current_capital": request.initial_capital,
        "market_value": 0.0,
        "total_asset": request.initial_capital,
        "total_pnl": 0.0,
        "position_count": 0,
        "status": "active",
        "description": request.description,
        "created_at": datetime.now().isoformat(),
    }
    ACCOUNTS_STORE.append(account)
    return {"success": True, "message": "账户创建成功", "data": {"account_id": account_id}}


@router.get("/positions/{account_id}")
async def get_sim_positions(account_id: int) -> dict[str, Any]:
    """获取模拟盘持仓列表"""
    positions = [p for p in POSITIONS_STORE if p["account_id"] == account_id and p["volume"] > 0]
    return {"positions": positions, "total": len(positions)}


@router.get("/trades/{account_id}")
async def get_sim_trades(
    account_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
) -> dict[str, Any]:
    """获取模拟盘交易记录"""
    trades = [t for t in TRADES_STORE if t["account_id"] == account_id]
    total = len(trades)
    start_idx = (page - 1) * page_size
    return {
        "trades": trades[start_idx:start_idx + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/trade")
async def place_sim_trade(request: SimTradeRequest) -> dict[str, Any]:
    """模拟交易下单"""
    account = next((a for a in ACCOUNTS_STORE if a["id"] == request.account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    commission = _calculate_commission(request.price, request.volume)
    amount = request.price * request.volume
    trade_no = _generate_trade_no()

    trade = {
        "id": len(TRADES_STORE) + 1,
        "trade_no": trade_no,
        "account_id": request.account_id,
        "stock_code": request.stock_code,
        "stock_name": request.stock_name,
        "side": request.side,
        "price": request.price,
        "volume": request.volume,
        "amount": amount,
        "commission": commission,
        "trade_time": datetime.now().isoformat(),
        "strategy": request.strategy,
    }
    TRADES_STORE.append(trade)

    if request.side == "buy":
        total_cost = amount + commission
        account["current_capital"] -= total_cost
        position = next(
            (p for p in POSITIONS_STORE if p["account_id"] == request.account_id and p["stock_code"] == request.stock_code),
            None
        )
        if position:
            new_volume = position["volume"] + request.volume
            position["volume"] = new_volume
            position["cost"] = (position["cost"] * (new_volume - request.volume) + request.price * request.volume) / new_volume
        else:
            POSITIONS_STORE.append({
                "id": len(POSITIONS_STORE) + 1,
                "account_id": request.account_id,
                "stock_code": request.stock_code,
                "stock_name": request.stock_name,
                "volume": request.volume,
                "cost": request.price,
                "cur_price": request.price,
                "market_value": amount,
            })
    elif request.side == "sell":
        position = next(
            (p for p in POSITIONS_STORE if p["account_id"] == request.account_id and p["stock_code"] == request.stock_code),
            None
        )
        if not position or position["volume"] < request.volume:
            raise HTTPException(status_code=400, detail="可用持仓不足")
        position["volume"] -= request.volume
        account["current_capital"] += amount - commission

    return {
        "success": True,
        "message": f"{'买入' if request.side == 'buy' else '卖出'}成功",
        "data": {"trade_no": trade_no, "amount": amount, "commission": commission}
    }


@router.get("/performance/{account_id}")
async def get_sim_performance(account_id: int) -> dict[str, Any]:
    """获取模拟盘收益曲线数据"""
    account = next((a for a in ACCOUNTS_STORE if a["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    return {
        "history": [],
        "summary": {
            "initial_capital": account["initial_capital"],
            "current_capital": account["current_capital"],
            "market_value": account["market_value"],
            "total_asset": account["total_asset"],
            "total_pnl": account["total_pnl"],
            "total_pnl_pct": (account["total_pnl"] / account["initial_capital"] * 100) if account["initial_capital"] > 0 else 0,
        }
    }
