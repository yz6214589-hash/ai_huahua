# -*- coding: utf-8 -*-
"""QMT Gateway HTTP 客户端模块

提供与本地 QMT Gateway 服务进行 HTTP 通信的功能。
支持多账户切换，通过 X-Account-Type 请求头区分不同 QMT 实例。
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

from infra.storage.logging_service import get_logger

logger = get_logger("qmt_gateway_client")


def _base_url() -> str:
    return str(os.getenv("AI_QUANT_QMT_GATEWAY_BASE", "") or "").rstrip("/")


def _token() -> str:
    return str(os.getenv("AI_QUANT_QMT_GATEWAY_TOKEN", "") or "").strip()


def _account_query(account_type: str | None) -> str:
    if account_type:
        return f"?account_type={urllib.parse.quote(account_type)}"
    return ""


def request_json(
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
    timeout: int = 30,
    account_type: str | None = None,
) -> Any:
    base = _base_url()
    tok = _token()
    logger.info(f"QMT请求: method={method}, path={path}, base_url={base}, token_set={bool(tok)}, data_keys={list(data.keys()) if data else None}")
    
    if not base:
        logger.error("AI_QUANT_QMT_GATEWAY_BASE 未配置")
        raise ConnectionError("AI_QUANT_QMT_GATEWAY_BASE 未配置")
    
    url = f"{base}{path}{_account_query(account_type)}"
    hdrs = {"Content-Type": "application/json"}
    if tok:
        hdrs["X-API-Token"] = tok
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.warning("QMT Gateway HTTP %s %s", e.code, url)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise ConnectionError(f"QMT Gateway {e.code}: {body[:200]}")
    except urllib.error.URLError as e:
        logger.error("QMT Gateway 不可达 %s: %s", url, e)
        raise ConnectionError(f"QMT Gateway 不可达: {e}")


def check_health() -> bool:
    try:
        result = request_json("GET", "/health", timeout=5)
        return result.get("ok") is True
    except Exception:
        return False


def get_accounts(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/accounts", timeout=10, account_type=account_type)


def connect(account_type: str | None = None) -> dict[str, Any]:
    return request_json("POST", "/api/trading/connect", data={}, timeout=15, account_type=account_type)


def disconnect(account_type: str | None = None) -> dict[str, Any]:
    return request_json("POST", "/api/trading/disconnect", data={}, timeout=10, account_type=account_type)


def get_state(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/state", timeout=10, account_type=account_type)


def get_asset(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/asset", timeout=10, account_type=account_type)


def get_positions(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/positions", timeout=10, account_type=account_type)


def get_orders(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/orders", timeout=10, account_type=account_type)


def get_trades(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/trades", timeout=10, account_type=account_type)


def get_events(account_type: str | None = None) -> dict[str, Any]:
    return request_json("GET", "/api/trading/events", timeout=10, account_type=account_type)


def buy(
    stock_code: str,
    volume: int,
    price: float = 0.0,
    strategy_name: str = "",
    remark: str = "",
    account_type: str | None = None,
) -> dict[str, Any]:
    return request_json(
        "POST", "/api/trading/buy",
        data={"stock_code": stock_code, "volume": volume, "price": price,
              "strategy_name": strategy_name, "remark": remark},
        timeout=15, account_type=account_type,
    )


def sell(
    stock_code: str,
    volume: int,
    price: float = 0.0,
    strategy_name: str = "",
    remark: str = "",
    account_type: str | None = None,
) -> dict[str, Any]:
    return request_json(
        "POST", "/api/trading/sell",
        data={"stock_code": stock_code, "volume": volume, "price": price,
              "strategy_name": strategy_name, "remark": remark},
        timeout=15, account_type=account_type,
    )


def cancel(order_id: int, account_type: str | None = None) -> dict[str, Any]:
    return request_json("POST", "/api/trading/cancel", data={"order_id": order_id},
                        timeout=10, account_type=account_type)


def cancel_all(account_type: str | None = None) -> dict[str, Any]:
    return request_json("POST", "/api/trading/cancel_all", data={},
                        timeout=10, account_type=account_type)


def historical_kline(
    stock_code: str,
    period: str = "1d",
    start_time: str = "",
    end_time: str = "",
    dividend_type: str = "front",
    fill_data: bool = True,
) -> dict[str, Any]:
    return request_json(
        "POST", "/api/historical/kline",
        data={
            "stock_code": stock_code, "period": period,
            "start_time": start_time, "end_time": end_time,
            "dividend_type": dividend_type, "fill_data": fill_data,
        },
        timeout=30,
    )


def historical_kline_batch(
    stock_codes: list[str],
    period: str = "1d",
    start_time: str = "",
    end_time: str = "",
    dividend_type: str = "front",
    fill_data: bool = True,
) -> dict[str, Any]:
    return request_json(
        "POST", "/api/historical/kline_batch",
        data={
            "stock_codes": stock_codes, "period": period,
            "start_time": start_time, "end_time": end_time,
            "dividend_type": dividend_type, "fill_data": fill_data,
        },
        timeout=180,
    )


def get_financial_data(stock_code: str, max_rows: int = 12) -> dict[str, Any]:
    return request_json(
        "POST", "/api/historical/financial_data",
        data={"stock_code": stock_code, "max_rows": max_rows},
        timeout=30,
    )


def get_stock_list() -> list[str]:
    result = request_json("GET", "/api/historical/stock_list", timeout=30)
    return result.get("codes") or []
