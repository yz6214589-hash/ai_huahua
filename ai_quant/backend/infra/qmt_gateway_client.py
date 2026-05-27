"""
QMT Gateway HTTP 客户端

封装与腾讯云 QMT Gateway 的 HTTP 通信，提供：
- 请求/响应的 JSON 序列化
- Token 认证
- 自动重试机制
- 超时控制
- 错误分类（连接错误、认证错误、业务错误）
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("qmt_gateway_client")

_DOTENV_LOADED = False


class QMTGatewayError(Exception):
    """QMT Gateway 通信错误基类"""

    def __init__(self, message: str, status_code: int | None = None, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class QMTConnectionError(QMTGatewayError):
    """网络连接错误（Gateway 不可达）"""
    pass


class QMTAuthError(QMTGatewayError):
    """认证错误（Token 无效）"""
    pass


class QMTBusinessError(QMTGatewayError):
    """业务逻辑错误（风控拒绝、订单失败等）"""
    pass


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _base() -> str:
    _load_dotenv_once()
    v = str(os.getenv("AI_QUANT_QMT_GATEWAY_BASE", "")).strip()
    if not v:
        raise RuntimeError("missing env: AI_QUANT_QMT_GATEWAY_BASE")
    return v.rstrip("/")


def _env_timeout(name: str, default: float) -> float:
    _load_dotenv_once()
    raw = str(os.getenv(name, "")).strip()
    try:
        v = float(raw) if raw else float(default)
        return v if v > 0 else float(default)
    except Exception:
        return float(default)


def _token_header() -> dict[str, str]:
    _load_dotenv_once()
    token = str(os.getenv("AI_QUANT_QMT_GATEWAY_TOKEN", "")).strip()
    if not token:
        return {}
    return {"X-API-Token": token}


def _extract_detail(raw_detail: str) -> str:
    """从 Gateway 响应中提取可读的错误信息"""
    try:
        parsed = json.loads(raw_detail)
        if isinstance(parsed, dict):
            return parsed.get("detail", raw_detail)
    except (json.JSONDecodeError, TypeError):
        pass
    return raw_detail


def _classify_error(e: urllib.error.HTTPError) -> QMTGatewayError:
    """根据 HTTP 状态码分类错误"""
    status_code = e.code
    try:
        raw = e.read()
        detail = raw.decode("utf-8", errors="ignore")
    except Exception:
        detail = str(e)

    readable = _extract_detail(detail)

    if status_code == 401:
        return QMTAuthError(f"认证失败: {readable}", status_code=status_code, detail=detail)
    elif status_code == 503:
        return QMTConnectionError(f"QMT 未连接: {readable}", status_code=status_code, detail=detail)
    elif 400 <= status_code < 500:
        return QMTBusinessError(f"业务错误: {readable}", status_code=status_code, detail=detail)
    else:
        return QMTGatewayError(f"服务端错误: {readable}", status_code=status_code, detail=detail)


def request_json(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    向 QMT Gateway 发送 HTTP 请求并解析 JSON 响应

    Args:
        method: HTTP 方法 (GET/POST/PUT/DELETE)
        path: API 路径，如 "/api/trading/state"
        body: 请求体（可选）
        timeout_seconds: 超时时间（秒）
        max_retries: 最大重试次数（仅对网络错误重试）

    Returns:
        解析后的 JSON 响应字典

    Raises:
        QMTAuthError: 认证失败
        QMTConnectionError: 网络连接失败
        QMTBusinessError: 业务逻辑错误
        QMTGatewayError: 其他错误
    """
    url = f"{_base()}{path}"
    headers = {"Content-Type": "application/json", **_token_header()}

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    timeout = float(timeout_seconds) if timeout_seconds is not None else _env_timeout("AI_QUANT_QMT_GATEWAY_TIMEOUT", 5.0)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise _classify_error(e)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_error = e
            if attempt < max_retries:
                wait = 2.0 if attempt == 0 else 5.0
                logger.warning("QMT Gateway 请求失败，%.1f秒后重试 (%d/%d): %s", wait, attempt + 1, max_retries, e)
                time.sleep(wait)
            continue
        except Exception as e:
            raise QMTGatewayError(f"未知错误: {type(e).__name__}: {e}")

    raise QMTConnectionError(f"QMT Gateway 连接失败（已重试{max_retries}次）: {last_error}")


def check_health() -> bool:
    """检查 Gateway 健康状态"""
    try:
        result = request_json("GET", "/health", timeout_seconds=3.0, max_retries=0)
        return result.get("status") == "ok"
    except Exception:
        return False


def get_stock_list() -> list[str]:
    """
    通过 QMT Gateway 获取全市场A股股票列表

    Returns:
        list[str]: 股票代码列表（如 ["000001.SZ", "000002.SZ", ...]）
    """
    try:
        result = request_json("GET", "/api/historical/stock_list", timeout_seconds=30.0)
        return result.get("codes") or []
    except Exception as e:
        logger.error("获取股票列表失败: %s", e)
        return []


def connect() -> dict[str, Any]:
    """连接到 QMT 交易终端"""
    return request_json("POST", "/api/trading/connect", timeout_seconds=30.0)


def disconnect() -> dict[str, Any]:
    """断开 QMT 交易终端连接"""
    return request_json("POST", "/api/trading/disconnect", timeout_seconds=30.0, max_retries=1)


def get_state() -> dict[str, Any]:
    """获取交易终端当前状态"""
    return request_json("GET", "/api/trading/state", timeout_seconds=10.0)


def get_asset() -> dict[str, Any]:
    """查询账户资产"""
    return request_json("GET", "/api/trading/asset", timeout_seconds=30.0)


def get_positions() -> dict[str, Any]:
    """查询持仓"""
    return request_json("GET", "/api/trading/positions", timeout_seconds=30.0)


def get_orders() -> dict[str, Any]:
    """查询当日委托"""
    return request_json("GET", "/api/trading/orders", timeout_seconds=30.0)


def get_trades() -> dict[str, Any]:
    """查询当日成交"""
    return request_json("GET", "/api/trading/trades", timeout_seconds=30.0)


def get_events() -> dict[str, Any]:
    """获取交易事件日志"""
    return request_json("GET", "/api/trading/events")


def buy(stock_code: str, volume: int, price: float = 0.0, strategy_name: str = "", remark: str = "") -> dict[str, Any]:
    """买入股票"""
    return request_json(
        "POST",
        "/api/trading/buy",
        body={
            "stock_code": stock_code,
            "volume": volume,
            "price": price,
            "strategy_name": strategy_name,
            "remark": remark,
        },
        timeout_seconds=30.0,
    )


def sell(stock_code: str, volume: int, price: float = 0.0, strategy_name: str = "", remark: str = "") -> dict[str, Any]:
    """卖出股票"""
    return request_json(
        "POST",
        "/api/trading/sell",
        body={
            "stock_code": stock_code,
            "volume": volume,
            "price": price,
            "strategy_name": strategy_name,
            "remark": remark,
        },
        timeout_seconds=30.0,
    )


def cancel(order_id: int) -> dict[str, Any]:
    """撤销指定委托"""
    return request_json("POST", "/api/trading/cancel", body={"order_id": order_id}, timeout_seconds=30.0)


def cancel_all() -> dict[str, Any]:
    """撤销所有可撤委托"""
    return request_json("POST", "/api/trading/cancel_all", timeout_seconds=30.0)


def historical_kline(
    stock_code: str,
    period: str = "1d",
    start_time: str = "",
    end_time: str = "",
    dividend_type: str = "front",
    fill_data: bool = True,
) -> dict[str, Any]:
    """
    获取股票历史 K 线数据

    Args:
        stock_code: 股票代码，如 "600519.SH"
        period: K 线周期，默认 "1d"
        start_time: 开始日期，YYYYMMDD 格式
        end_time: 结束日期，YYYYMMDD 格式，默认为空表示至今
        dividend_type: 复权类型，"front"(前复权) / "back"(后复权) / "none"(不复权)
        fill_data: 是否填充空值

    Returns:
        {"rows": [...], "columns": [...]}，其中 rows 每行包含 date/open/high/low/close/volume/amount
    """
    return request_json(
        "POST",
        "/api/historical/kline",
        body={
            "stock_code": stock_code,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "dividend_type": dividend_type,
            "fill_data": fill_data,
        },
        timeout_seconds=_env_timeout("AI_QUANT_QMT_GATEWAY_KLINE_TIMEOUT", 60.0),
    )


def get_financial_data(
    stock_code: str,
    start_time: str = "20150101",
    end_time: str = "20261231",
    max_rows: int = 12,
) -> dict[str, Any]:
    """
    获取股票的历史财务数据（通过 QMT Gateway 远程调用）

    从 Balance（资产负债表）、Income（利润表）、CashFlow（现金流量表）、
    PershareIndex（每股指标）、Capital（股本）等报表中提取财务指标，
    包括 EPS、ROE、毛利率、营收、净利润、资产负债率、流动比率等。

    Args:
        stock_code: 股票代码，如 "600519.SH"
        start_time: 开始日期，YYYYMMDD 格式，默认 "20150101"
        end_time: 结束日期，YYYYMMDD 格式，默认 "20261231"
        max_rows: 最大返回行数，默认 12

    Returns:
        {"rows": [...]}，rows 每行包含 end_date/eps/roe/roa/gross_margin/net_margin/等字段
    """
    return request_json(
        "POST",
        "/api/historical/financial_data",
        body={
            "stock_code": stock_code,
            "start_time": start_time,
            "end_time": end_time,
            "max_rows": max_rows,
        },
        timeout_seconds=_env_timeout("AI_QUANT_QMT_GATEWAY_KLINE_TIMEOUT", 180.0),
    )
