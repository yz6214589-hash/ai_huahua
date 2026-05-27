"""
模拟盘账户API模块
支持模拟账户管理、交易、持仓查询等功能
数据存储使用MySQL数据库
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.db import connect, load_mysql_config, query_dict, execute
from infra.storage.logging_service import get_logger

logger = get_logger("sim_account")

router = APIRouter(prefix="/api/v1/sim-account", tags=["sim-account"])


def _get_conn():
    """获取数据库连接"""
    cfg = load_mysql_config()
    return connect(cfg)


def _ensure_sim_tables() -> None:
    try:
        conn = _get_conn()
        try:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS trade_sim_account (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    account_name VARCHAR(100) NOT NULL,
                    initial_capital DECIMAL(15,2) NOT NULL DEFAULT 1000000.00,
                    current_capital DECIMAL(15,2) NOT NULL DEFAULT 1000000.00,
                    market_value DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    total_asset DECIMAL(15,2) NOT NULL DEFAULT 1000000.00,
                    total_pnl DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    total_pnl_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
                    today_pnl DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    today_pnl_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
                    position_count INT NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    description VARCHAR(500) DEFAULT NULL,
                    UNIQUE KEY uk_account_name (account_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """, ())
            execute(conn, """
                CREATE TABLE IF NOT EXISTS trade_sim_position (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    account_id INT NOT NULL,
                    stock_code VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(100) NOT NULL,
                    volume INT NOT NULL DEFAULT 0,
                    available_volume INT NOT NULL DEFAULT 0,
                    cost DECIMAL(15,4) NOT NULL DEFAULT 0.00,
                    cur_price DECIMAL(15,4) NOT NULL DEFAULT 0.00,
                    market_value DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    pnl DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                    pnl_pct DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
                    buy_date DATE DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_account_stock (account_id, stock_code)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """, ())
            execute(conn, """
                CREATE TABLE IF NOT EXISTS trade_sim_trade (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    trade_no VARCHAR(50) NOT NULL,
                    account_id INT NOT NULL,
                    stock_code VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(100) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    price DECIMAL(15,4) NOT NULL,
                    volume INT NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    commission DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    trade_time DATETIME NOT NULL,
                    strategy VARCHAR(50) DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_trade_no (trade_no),
                    KEY idx_account_id (account_id),
                    KEY idx_trade_time (trade_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """, ())
        finally:
            conn.close()
    except Exception as e:
        import traceback
        logger.error("自动建表失败", extra={"error": str(e), "traceback": traceback.format_exc()})


_ensure_sim_tables()


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


def _generate_trade_no() -> str:
    """生成成交编号"""
    return f"SIM{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _calculate_commission(price: float, volume: int) -> float:
    """计算手续费"""
    commission = price * volume * 0.0003
    return max(5.0, min(commission, 100.0))


def _ensure_default_account(conn):
    """确保默认模拟账户存在"""
    accounts = query_dict(conn, "SELECT id FROM trade_sim_account LIMIT 1", ())
    if not accounts:
        execute(
            conn,
            """INSERT INTO trade_sim_account (account_name, initial_capital, current_capital, total_asset, status)
               VALUES (%s, %s, %s, %s, %s)""",
            ("默认模拟账户", 1000000.0, 1000000.0, 1000000.0, "active")
        )


@router.get("/list")
async def get_sim_account_list() -> dict[str, Any]:
    """获取模拟盘账户列表"""
    logger.info("开始获取模拟盘账户列表")
    conn = _get_conn()
    try:
        logger.debug("确保默认账户存在")
        _ensure_default_account(conn)
        
        logger.debug("查询账户列表")
        accounts = query_dict(
            conn,
            "SELECT * FROM trade_sim_account ORDER BY created_at DESC",
            ()
        )
        logger.info(f"查询到 {len(accounts)} 个账户", extra={"account_count": len(accounts)})
        
        for acc in accounts:
            for key in ("created_at", "updated_at"):
                if acc.get(key):
                    acc[key] = str(acc[key])
        return {"accounts": accounts, "total": len(accounts)}
    except Exception as e:
        logger.error("获取模拟盘账户列表失败", extra={"error": str(e)})
        return {"accounts": [], "total": 0}
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.get("/detail/{account_id}")
async def get_sim_account_detail(account_id: int) -> dict[str, Any]:
    """获取模拟盘账户详情"""
    logger.info("开始获取模拟盘账户详情", extra={"account_id": account_id})
    conn = _get_conn()
    try:
        logger.debug("查询账户详情")
        accounts = query_dict(conn, "SELECT * FROM trade_sim_account WHERE id = %s", (account_id,))
        if not accounts:
            logger.warning("账户不存在", extra={"account_id": account_id})
            raise HTTPException(status_code=404, detail="账户不存在")
        
        account = accounts[0]
        for key in ("created_at", "updated_at"):
            if account.get(key):
                account[key] = str(account[key])
        logger.info("查询成功", extra={"account_id": account_id})
        return account
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取模拟盘账户详情失败", extra={"error": str(e), "account_id": account_id})
        raise HTTPException(status_code=500, detail=f"获取账户详情失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.post("/create")
async def create_sim_account(request: SimAccountCreate) -> dict[str, Any]:
    """创建模拟盘账户"""
    logger.info("开始创建模拟盘账户", extra={
        "account_name": request.account_name,
        "initial_capital": request.initial_capital
    })
    conn = _get_conn()
    try:
        logger.debug("插入账户记录")
        execute(
            conn,
            """INSERT INTO trade_sim_account (account_name, initial_capital, current_capital, total_asset, status, description)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (request.account_name, request.initial_capital, request.initial_capital,
             request.initial_capital, "active", request.description)
        )
        result = query_dict(conn, "SELECT LAST_INSERT_ID() as id", ())
        account_id = result[0]["id"] if result else 0
        logger.info(f"模拟盘账户创建成功，account_id: {account_id}", extra={"account_id": account_id})
        return {"success": True, "message": "账户创建成功", "data": {"account_id": account_id}}
    except Exception as e:
        logger.error("创建模拟盘账户失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建账户失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.get("/positions/{account_id}")
async def get_sim_positions(account_id: int) -> dict[str, Any]:
    """获取模拟盘持仓列表"""
    conn = _get_conn()
    try:
        positions = query_dict(
            conn,
            "SELECT * FROM trade_sim_position WHERE account_id = %s AND volume > 0 ORDER BY updated_at DESC",
            (account_id,)
        )
        for pos in positions:
            for key in ("created_at", "updated_at", "buy_date"):
                if pos.get(key):
                    pos[key] = str(pos[key])
        return {"positions": positions, "total": len(positions)}
    except Exception as e:
        logger.error("获取模拟盘持仓失败", extra={"error": str(e)})
        return {"positions": [], "total": 0}
    finally:
        conn.close()


@router.get("/trades/{account_id}")
async def get_sim_trades(
    account_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
) -> dict[str, Any]:
    """获取模拟盘交易记录"""
    conn = _get_conn()
    try:
        count_result = query_dict(
            conn,
            "SELECT COUNT(*) as total FROM trade_sim_trade WHERE account_id = %s",
            (account_id,)
        )
        total = count_result[0]["total"] if count_result else 0
        offset = (page - 1) * page_size
        trades = query_dict(
            conn,
            """SELECT * FROM trade_sim_trade WHERE account_id = %s
               ORDER BY trade_time DESC LIMIT %s OFFSET %s""",
            (account_id, page_size, offset)
        )
        for trade in trades:
            for key in ("created_at", "trade_time"):
                if trade.get(key):
                    trade[key] = str(trade[key])
        return {
            "trades": trades,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取模拟盘交易记录失败", extra={"error": str(e)})
        return {"trades": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()


@router.post("/trade")
async def place_sim_trade(request: SimTradeRequest) -> dict[str, Any]:
    """模拟交易下单"""
    logger.info("开始模拟交易下单", extra={
        "account_id": request.account_id,
        "stock_code": request.stock_code,
        "side": request.side,
        "price": request.price,
        "volume": request.volume
    })
    conn = _get_conn()
    try:
        logger.debug("查询账户信息")
        accounts = query_dict(conn, "SELECT * FROM trade_sim_account WHERE id = %s", (request.account_id,))
        if not accounts:
            logger.warning("账户不存在", extra={"account_id": request.account_id})
            raise HTTPException(status_code=404, detail="账户不存在")

        commission = _calculate_commission(request.price, request.volume)
        amount = request.price * request.volume
        trade_no = _generate_trade_no()

        logger.debug("插入交易记录", extra={"trade_no": trade_no})
        execute(
            conn,
            """INSERT INTO trade_sim_trade (trade_no, account_id, stock_code, stock_name, side, price, volume, amount, commission, trade_time, strategy)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (trade_no, request.account_id, request.stock_code, request.stock_name,
             request.side, request.price, request.volume, amount, commission,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), request.strategy)
        )

        if request.side == "buy":
            logger.debug("处理买入操作")
            total_cost = amount + commission
            logger.debug("更新账户资金", extra={"total_cost": total_cost})
            execute(
                conn,
                "UPDATE trade_sim_account SET current_capital = current_capital - %s WHERE id = %s",
                (total_cost, request.account_id)
            )
            
            logger.debug("查询现有持仓")
            existing_pos = query_dict(
                conn,
                "SELECT id, volume, cost FROM trade_sim_position WHERE account_id = %s AND stock_code = %s",
                (request.account_id, request.stock_code)
            )
            if existing_pos:
                logger.debug("更新现有持仓")
                pos = existing_pos[0]
                new_volume = pos["volume"] + request.volume
                new_cost = (pos["cost"] * pos["volume"] + request.price * request.volume) / new_volume
                execute(
                    conn,
                    """UPDATE trade_sim_position SET volume = %s, cost = %s, cur_price = %s, market_value = %s,
                       updated_at = NOW() WHERE id = %s""",
                    (new_volume, new_cost, request.price, new_volume * request.price, pos["id"])
                )
            else:
                logger.debug("创建新持仓")
                execute(
                    conn,
                    """INSERT INTO trade_sim_position (account_id, stock_code, stock_name, volume, available_volume, cost, cur_price, market_value, pnl, pnl_pct, buy_date)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (request.account_id, request.stock_code, request.stock_name,
                     request.volume, request.volume, request.price, request.price,
                     amount, 0, 0, datetime.now().strftime('%Y-%m-%d'))
                )
        elif request.side == "sell":
            logger.debug("处理卖出操作")
            existing_pos = query_dict(
                conn,
                "SELECT id, volume FROM trade_sim_position WHERE account_id = %s AND stock_code = %s",
                (request.account_id, request.stock_code)
            )
            if not existing_pos or existing_pos[0]["volume"] < request.volume:
                logger.warning("可用持仓不足", extra={"current_volume": existing_pos[0]["volume"] if existing_pos else 0, "request_volume": request.volume})
                raise HTTPException(status_code=400, detail="可用持仓不足")
            
            logger.debug("更新账户资金", extra={"amount": amount - commission})
            execute(
                conn,
                "UPDATE trade_sim_account SET current_capital = current_capital + %s WHERE id = %s",
                (amount - commission, request.account_id)
            )
            new_volume = existing_pos[0]["volume"] - request.volume
            if new_volume > 0:
                logger.debug("减少持仓数量")
                execute(
                    conn,
                    "UPDATE trade_sim_position SET volume = %s, available_volume = %s, updated_at = NOW() WHERE id = %s",
                    (new_volume, new_volume, existing_pos[0]["id"])
                )
            else:
                logger.debug("删除持仓记录")
                execute(
                    conn,
                    "DELETE FROM trade_sim_position WHERE id = %s",
                    (existing_pos[0]["id"],)
                )

        logger.info(f"模拟交易成功，trade_no: {trade_no}", extra={"trade_no": trade_no})
        return {
            "success": True,
            "message": f"{'买入' if request.side == 'buy' else '卖出'}成功",
            "data": {"trade_no": trade_no, "amount": amount, "commission": commission}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("模拟交易下单失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"交易失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.get("/performance/{account_id}")
async def get_sim_performance(account_id: int) -> dict[str, Any]:
    """获取模拟盘收益曲线数据"""
    conn = _get_conn()
    try:
        accounts = query_dict(conn, "SELECT * FROM trade_sim_account WHERE id = %s", (account_id,))
        if not accounts:
            raise HTTPException(status_code=404, detail="账户不存在")
        account = accounts[0]
        return {
            "history": [],
            "summary": {
                "initial_capital": float(account.get("initial_capital", 0)),
                "current_capital": float(account.get("current_capital", 0)),
                "market_value": float(account.get("market_value", 0)),
                "total_asset": float(account.get("total_asset", 0)),
                "total_pnl": float(account.get("total_pnl", 0)),
                "total_pnl_pct": float(account.get("total_pnl_pct", 0)),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取模拟盘收益曲线失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取收益曲线失败: {str(e)}")
    finally:
        conn.close()
