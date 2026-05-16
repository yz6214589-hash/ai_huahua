"""
QMT 交易代理路由

将前端请求代理到腾讯云 QMT Gateway，提供统一的交易 API 接口。
包括：连接管理、账户查询、买卖下单、撤单、历史行情等。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from infra import qmt_gateway_client
from infra.qmt_gateway_client import QMTConnectionError, QMTAuthError, QMTBusinessError, QMTGatewayError
from infra.storage.logging_service import get_logger

logger = get_logger("trading_qmt")

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


class BuySellRequest(BaseModel):
    stock_code: str
    volume: int = Field(ge=1)
    price: float = Field(default=0.0, ge=0.0)
    strategy_name: str = ""
    remark: str = ""


class CancelRequest(BaseModel):
    order_id: int


class KLineRequest(BaseModel):
    stock_code: str
    period: str = "1d"
    start_time: str = ""
    end_time: str = ""
    dividend_type: str = "front"
    fill_data: bool = True


def _handle_error(exc: Exception) -> HTTPException:
    """将客户端错误转换为 HTTP 异常"""
    if isinstance(exc, QMTAuthError):
        logger.error("QMT 认证失败", extra={"detail": exc.detail})
        return HTTPException(status_code=502, detail=str(exc))
    elif isinstance(exc, QMTConnectionError):
        logger.error("QMT 连接失败", extra={"detail": exc.detail})
        return HTTPException(status_code=502, detail=str(exc))
    elif isinstance(exc, QMTBusinessError):
        logger.warning("QMT 业务错误", extra={"status_code": exc.status_code, "detail": exc.detail})
        return HTTPException(status_code=exc.status_code or 400, detail=str(exc))
    elif isinstance(exc, QMTGatewayError):
        logger.error("QMT 网关错误", extra={"status_code": exc.status_code, "detail": exc.detail})
        return HTTPException(status_code=502, detail=str(exc))
    else:
        msg = f"{type(exc).__name__}: {exc}"
        logger.error("QMT 未知错误", extra={"error": msg})
        return HTTPException(status_code=502, detail=msg)


@router.get("/health")
def trading_health() -> dict[str, Any]:
    """检查 QMT Gateway 健康状态"""
    ok = qmt_gateway_client.check_health()
    return {"gateway_healthy": ok}


@router.get("/state")
def trading_state() -> dict[str, Any]:
    """获取交易终端当前状态"""
    try:
        return qmt_gateway_client.get_state()
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/connect")
def trading_connect() -> dict[str, Any]:
    """连接到 QMT 交易终端"""
    try:
        result = qmt_gateway_client.connect()
        logger.info("QMT 连接成功", extra={"account_id": result.get("account_id")})
        return result
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/disconnect")
def trading_disconnect() -> dict[str, Any]:
    """断开 QMT 交易终端连接"""
    try:
        return qmt_gateway_client.disconnect()
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/asset")
def trading_asset() -> dict[str, Any]:
    """查询账户资产"""
    try:
        return qmt_gateway_client.get_asset()
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/positions")
def trading_positions() -> dict[str, Any]:
    """查询持仓"""
    try:
        return qmt_gateway_client.get_positions()
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/orders")
def trading_orders() -> dict[str, Any]:
    """查询当日委托"""
    try:
        return qmt_gateway_client.get_orders()
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/trades")
def trading_trades() -> dict[str, Any]:
    """查询当日成交"""
    try:
        return qmt_gateway_client.get_trades()
    except Exception as exc:
        raise _handle_error(exc)


@router.get("/events")
def trading_events() -> dict[str, Any]:
    """获取交易事件日志"""
    try:
        return qmt_gateway_client.get_events()
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/buy")
def trading_buy(body: BuySellRequest) -> dict[str, Any]:
    """买入股票"""
    try:
        result = qmt_gateway_client.buy(
            stock_code=body.stock_code,
            volume=body.volume,
            price=body.price,
            strategy_name=body.strategy_name,
            remark=body.remark,
        )
        logger.info("买入委托", extra={
            "stock_code": body.stock_code,
            "volume": body.volume,
            "order_id": result.get("order_id"),
        })
        return result
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/sell")
def trading_sell(body: BuySellRequest) -> dict[str, Any]:
    """卖出股票"""
    try:
        result = qmt_gateway_client.sell(
            stock_code=body.stock_code,
            volume=body.volume,
            price=body.price,
            strategy_name=body.strategy_name,
            remark=body.remark,
        )
        logger.info("卖出委托", extra={
            "stock_code": body.stock_code,
            "volume": body.volume,
            "order_id": result.get("order_id"),
        })
        return result
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/cancel")
def trading_cancel(body: CancelRequest) -> dict[str, Any]:
    """撤销指定委托"""
    try:
        result = qmt_gateway_client.cancel(order_id=body.order_id)
        logger.info("撤单", extra={"order_id": body.order_id})
        return result
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/cancel_all")
def trading_cancel_all() -> dict[str, Any]:
    """撤销所有可撤委托"""
    try:
        result = qmt_gateway_client.cancel_all()
        logger.info("全部撤单", extra={"canceled_count": result.get("canceled_count", 0)})
        return result
    except Exception as exc:
        raise _handle_error(exc)


@router.post("/kline")
def trading_kline(body: KLineRequest) -> dict[str, Any]:
    """获取股票历史 K 线数据"""
    try:
        result = qmt_gateway_client.historical_kline(
            stock_code=body.stock_code,
            period=body.period,
            start_time=body.start_time,
            end_time=body.end_time,
            dividend_type=body.dividend_type,
            fill_data=body.fill_data,
        )
        logger.info("K线查询", extra={
            "stock_code": body.stock_code,
            "period": body.period,
            "rows_count": len(result.get("rows", [])),
        })
        return result
    except Exception as exc:
        raise _handle_error(exc)
