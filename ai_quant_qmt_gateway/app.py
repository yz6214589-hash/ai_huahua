"""
QMT Gateway FastAPI 应用模块

提供基于 FastAPI 的 RESTful API 接口，用于与 MiniQMT 交易终端进行交互。
支持多账户配置，通过 X-Account-Type 请求头切换不同的 QMT 实例。
所有接口均通过 X-API-Token 请求头进行身份验证。
"""

from __future__ import annotations

import json
import logging
import os
import time
import sys
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from miniqmt_trader import MiniQMTTrader

logger = logging.getLogger("qmt_gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


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


class KLineBatchRequest(BaseModel):
    stock_codes: list[str]
    period: str = "1d"
    start_time: str = ""
    end_time: str = ""
    dividend_type: str = "front"
    fill_data: bool = True


class FinancialDataRequest(BaseModel):
    stock_code: str
    start_time: str = "20150101"
    end_time: str = "20261231"
    max_rows: int = 12


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    try:
        return int(raw) if raw else int(default)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "")).strip()
    try:
        return float(raw) if raw else float(default)
    except Exception:
        return float(default)


def _check_token(x_api_token: str | None) -> None:
    required = str(os.getenv("QMT_API_TOKEN", "")).strip()
    if not required:
        return
    if str(x_api_token or "").strip() != required:
        raise HTTPException(status_code=401, detail="invalid token")


_ACCOUNT_CONFIGS: dict[str, dict] = {}
_TRADERS: dict[str, MiniQMTTrader] = {}
_LOADED = False


def _load_account_configs() -> dict[str, dict]:
    raw = os.getenv("QMT_ACCOUNTS", "").strip()
    if raw:
        try:
            configs = json.loads(raw)
            if isinstance(configs, dict):
                return configs
        except json.JSONDecodeError as e:
            logger.error("QMT_ACCOUNTS 配置解析失败: %s", e)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qmt_accounts.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                configs = json.load(f)
                if isinstance(configs, dict):
                    return configs
        except Exception as e:
            logger.error("qmt_accounts.json 配置加载失败: %s", e)

    qmt_path = os.getenv("QMT_PATH", "").strip()
    account_id = os.getenv("ACCOUNT_ID", "").strip()
    if qmt_path and account_id:
        return {account_id: {"qmt_path": qmt_path, "account_id": account_id}}

    return {}


def _ensure_configs() -> None:
    global _ACCOUNT_CONFIGS, _LOADED
    if _LOADED:
        return
    _LOADED = True
    _ACCOUNT_CONFIGS = _load_account_configs()
    if not _ACCOUNT_CONFIGS:
        logger.warning("未配置任何 QMT 账户 (设置 QMT_ACCOUNTS 或 QMT_PATH/ACCOUNT_ID)")
    else:
        keys = list(_ACCOUNT_CONFIGS.keys())
        logger.info("已加载 %d 个 QMT 账户: %s", len(keys), keys)


def _get_default_account_type() -> str:
    _ensure_configs()
    if not _ACCOUNT_CONFIGS:
        raise HTTPException(status_code=503, detail="未配置 QMT 账户")
    return next(iter(_ACCOUNT_CONFIGS.keys()))


def _resolve_account_type(x_account_type: str | None) -> str:
    if x_account_type:
        return x_account_type
    return _get_default_account_type()


def _get_or_create_trader(account_type: str) -> MiniQMTTrader:
    _ensure_configs()
    config = _ACCOUNT_CONFIGS.get(account_type)
    if not config:
        raise HTTPException(status_code=400, detail=f"未知的账户类型: {account_type}，可用: {list(_ACCOUNT_CONFIGS.keys())}")

    if account_type in _TRADERS:
        return _TRADERS[account_type]

    max_positions = _env_int("QMT_MAX_POSITIONS", 10)
    max_order_amount = _env_float("QMT_MAX_ORDER_AMOUNT", 500000.0)
    trader = MiniQMTTrader(
        qmt_path=config["qmt_path"],
        account_id=config["account_id"],
        max_positions=max_positions,
        max_order_amount=max_order_amount,
    )
    _TRADERS[account_type] = trader
    return trader


def _ensure_connected(trader: MiniQMTTrader) -> None:
    if trader.connected:
        return
    try:
        trader.connect()
        logger.info("自动重连成功: account=%s", trader.account_id)
    except Exception as e:
        logger.warning("自动重连失败: account=%s error=%s", trader.account_id, e)
        raise HTTPException(status_code=503, detail=f"QMT 未连接且自动重连失败: {e}")


def create_app() -> FastAPI:
    api = FastAPI(title="AI Quant QMT Gateway", version="0.3.0")

    @api.on_event("startup")
    def startup() -> None:
        _ensure_configs()

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/api/trading/accounts")
    def trading_accounts(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        _ensure_configs()
        result = {}
        for key, config in _ACCOUNT_CONFIGS.items():
            trader = _TRADERS.get(key)
            result[key] = {
                "qmt_path": config["qmt_path"],
                "account_id": config["account_id"],
                "connected": trader.connected if trader else False,
            }
        return {"accounts": result, "default": _get_default_account_type()}

    @api.post("/api/trading/connect")
    def trading_connect(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        try:
            trader = _get_or_create_trader(account_type)
            ok = trader.connect()
            logger.info("连接请求: account_type=%s connected=%s account=%s", account_type, trader.connected, trader.account_id)
            return {
                "ok": bool(ok),
                "connected": trader.connected,
                "account_id": trader.account_id,
                "account_type": account_type,
                "session_id": trader.session_id,
            }
        except Exception as exc:
            logger.error("连接失败: account_type=%s error=%s", account_type, exc)
            # 连接失败时清除缓存，下次连接时重新创建 trader 实例
            _TRADERS.pop(account_type, None)
            raise HTTPException(status_code=400, detail=str(exc))

    @api.post("/api/trading/disconnect")
    def trading_disconnect(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        trader.disconnect()
        logger.info("断开连接: account_type=%s", account_type)
        return {"ok": True, "connected": trader.connected, "account_type": account_type}

    @api.get("/api/trading/state")
    def trading_state(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        events = trader.events
        last = events[-1] if events else None
        return {
            "connected": trader.connected,
            "account_id": trader.account_id,
            "account_type": account_type,
            "session_id": trader.session_id,
            "events_count": len(events),
            "last_event": last,
        }

    @api.get("/api/trading/asset")
    def trading_asset(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        _ensure_connected(trader)
        return {"asset": trader.query_asset(), "account_type": account_type}

    @api.get("/api/trading/positions")
    def trading_positions(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        _ensure_connected(trader)
        return {"positions": trader.query_positions(), "account_type": account_type}

    @api.get("/api/trading/orders")
    def trading_orders(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        _ensure_connected(trader)
        return {"orders": trader.query_orders(), "account_type": account_type}

    @api.get("/api/trading/trades")
    def trading_trades(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        _ensure_connected(trader)
        return {"trades": trader.query_trades(), "account_type": account_type}

    @api.get("/api/trading/events")
    def trading_events(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        return {"events": trader.events[-200:], "account_type": account_type}

    @api.post("/api/trading/buy")
    def trading_buy(
        body: BuySellRequest,
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        _ensure_connected(trader)
        order_id = trader.buy(
            stock_code=body.stock_code,
            volume=int(body.volume),
            price=float(body.price or 0.0),
            strategy_name=str(body.strategy_name or ""),
            remark=str(body.remark or ""),
        )
        if order_id is None:
            raise HTTPException(status_code=400, detail="order rejected by risk check")
        logger.info("买入委托: account=%s %s %d股 order_id=%s", account_type, body.stock_code, body.volume, order_id)
        return {"order_id": int(order_id), "account_type": account_type}

    @api.post("/api/trading/sell")
    def trading_sell(
        body: BuySellRequest,
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        _ensure_connected(trader)
        order_id = trader.sell(
            stock_code=body.stock_code,
            volume=int(body.volume),
            price=float(body.price or 0.0),
            strategy_name=str(body.strategy_name or ""),
            remark=str(body.remark or ""),
        )
        if order_id is None:
            raise HTTPException(status_code=400, detail="order rejected by risk check")
        logger.info("卖出委托: account=%s %s %d股 order_id=%s", account_type, body.stock_code, body.volume, order_id)
        return {"order_id": int(order_id), "account_type": account_type}

    @api.post("/api/trading/cancel")
    def trading_cancel(
        body: CancelRequest,
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        if not trader.connected:
            raise HTTPException(status_code=400, detail="QMT 未连接，无法撤单")
        order_id = trader.cancel(int(body.order_id))
        if order_id is None:
            raise HTTPException(status_code=400, detail="cancel rejected")
        logger.info("撤单: account=%s order_id=%s", account_type, order_id)
        return {"order_id": int(order_id), "account_type": account_type}

    @api.post("/api/trading/cancel_all")
    def trading_cancel_all(
        x_api_token: str | None = Header(default=None),
        x_account_type: str | None = Header(default=None),
        account_type: str | None = Query(default=None),
    ) -> dict[str, Any]:
        _check_token(x_api_token)
        account_type = _resolve_account_type(account_type or x_account_type)
        trader = _get_or_create_trader(account_type)
        if not trader.connected:
            raise HTTPException(status_code=400, detail="QMT 未连接，无法撤单")
        canceled = trader.cancel_all()
        logger.info("全部撤单: account=%s count=%d", account_type, len(canceled))
        return {"canceled_count": len(canceled), "canceled_ids": canceled, "account_type": account_type}

    @api.post("/api/historical/kline")
    def historical_kline(body: KLineRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_or_create_trader(_get_default_account_type())
        stock_code = str(body.stock_code or "").strip()
        period = str(body.period or "1d").strip()
        start_time = str(body.start_time or "").strip()
        end_time = str(body.end_time or "").strip()
        dividend_type = str(body.dividend_type or "front").strip()
        fill_data = bool(body.fill_data)

        try:
            trader.download_history_data(
                stock_code=stock_code,
                period=period,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as e:
            logger.warning("下载历史数据失败: %s %s", stock_code, e)

        time.sleep(1)

        try:
            raw = trader.get_market_data_ex(
                stock_list=[stock_code],
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=-1,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
        except Exception as e:
            logger.error("获取K线数据失败: %s %s", stock_code, e)
            return {"rows": [], "columns": [], "error": str(e)}

        if not raw or stock_code not in raw:
            return {"rows": [], "columns": []}

        df = raw[stock_code]
        if df is None or df.empty:
            return {"rows": [], "columns": []}

        import pandas as pd

        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass

        out_rows = []
        for idx, row in df.iterrows():
            date_str = ""
            if hasattr(idx, "strftime"):
                date_str = idx.strftime("%Y%m%d")
            else:
                date_str = str(idx)

            out_rows.append({
                "date": date_str,
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
                "volume": int(row.get("volume", 0) or 0),
                "amount": float(row.get("amount", 0) or 0),
            })

        return {"rows": out_rows, "columns": ["date", "open", "high", "low", "close", "volume", "amount"]}

    @api.post("/api/historical/kline_batch")
    def historical_kline_batch(body: KLineBatchRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_or_create_trader(_get_default_account_type())
        stock_codes = [str(c).strip() for c in (body.stock_codes or []) if str(c).strip()]
        period = str(body.period or "1d").strip()
        start_time = str(body.start_time or "").strip()
        end_time = str(body.end_time or "").strip()
        dividend_type = str(body.dividend_type or "front").strip()
        fill_data = bool(body.fill_data)

        if not stock_codes:
            return {"results": {}}

        _log = logger.info
        _log(f"[kline_batch] 批量获取 {len(stock_codes)} 只股票K线数据...")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        download_count = 0
        with ThreadPoolExecutor(max_workers=8) as exc:
            futs = {exc.submit(trader.download_history_data, code, period, start_time, end_time): code for code in stock_codes}
            for f in as_completed(futs):
                if f.result():
                    download_count += 1

        _log(f"[kline_batch] 下载完成: {download_count}/{len(stock_codes)} 只")

        time.sleep(1.5)

        try:
            raw = trader.get_market_data_ex(
                stock_list=stock_codes,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=-1,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
        except Exception as e:
            _log(f"[kline_batch] get_market_data_ex 失败: {e}")
            return {"results": {}, "error": str(e)}

        if not raw:
            return {"results": {}}

        import pandas as pd

        results = {}
        for code in stock_codes:
            df = raw.get(code)
            if df is None or df.empty:
                results[code] = {"rows": []}
                continue

            if not isinstance(df.index, pd.DatetimeIndex):
                try:
                    df.index = pd.to_datetime(df.index)
                except Exception:
                    pass

            out_rows = []
            for idx, row in df.iterrows():
                date_str = idx.strftime("%Y%m%d") if hasattr(idx, "strftime") else str(idx)
                out_rows.append({
                    "date": date_str,
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": int(row.get("volume", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                })
            results[code] = {"rows": out_rows}

        _log(f"[kline_batch] 批量查询完成: {len(stock_codes)} 只股票, {sum(len(r['rows']) for r in results.values())} 行")
        return {"results": results}

    @api.get("/api/historical/stock_list")
    def historical_stock_list(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_or_create_trader(_get_default_account_type())
        try:
            codes = trader.get_stock_list()
            logger.info("获取股票列表成功: %d 只", len(codes))
            return {"codes": codes, "count": len(codes)}
        except Exception as e:
            logger.error("获取股票列表失败: %s", e)
            return {"codes": [], "count": 0, "error": str(e)}

    @api.post("/api/historical/financial_data")
    def historical_financial_data(body: FinancialDataRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_or_create_trader(_get_default_account_type())
        stock_code = str(body.stock_code or "").strip()
        start_time = str(body.start_time or "20150101").strip()
        end_time = str(body.end_time or "20261231").strip()
        max_rows = max(1, int(body.max_rows or 12))

        tables = ['Balance', 'Income', 'CashFlow', 'PershareIndex', 'Capital']

        try:
            trader.download_financial_data(
                stock_list=[stock_code],
                table_list=tables,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as e:
            logger.warning("下载财务数据失败: %s %s", stock_code, e)

        import time as _time
        _time.sleep(1)

        try:
            raw = trader.get_financial_data(
                stock_list=[stock_code],
                table_list=tables,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as e:
            logger.error("获取财务数据失败: %s %s", stock_code, e)
            return {"rows": [], "error": str(e)}

        if not raw or stock_code not in raw:
            return {"rows": []}

        stock_data = raw[stock_code]

        def _normalize_timetag(ts_val):
            if ts_val is None:
                return None
            s = str(ts_val).strip()
            if len(s) == 8 and s.isdigit():
                return s
            try:
                v = float(s)
                if v == 0:
                    return None
                if v > 1e12:
                    v = v / 1000
                from datetime import datetime as _dt
                return _dt.fromtimestamp(v).strftime('%Y%m%d')
            except (OSError, ValueError, TypeError):
                return None

        def _build_map(data_list):
            pm = {}
            if isinstance(data_list, list):
                for rec in data_list:
                    if isinstance(rec, dict):
                        pd_val = _normalize_timetag(rec.get('m_timetag'))
                        if pd_val:
                            pm[pd_val] = rec
            elif hasattr(data_list, 'iterrows'):
                for _, row in data_list.iterrows():
                    pd_val = _normalize_timetag(row.get('m_timetag'))
                    if pd_val:
                        pm[pd_val] = row.to_dict()
            return pm

        pershare_map = _build_map(stock_data.get('PershareIndex', []))
        balance_map = _build_map(stock_data.get('Balance', []))
        income_map = _build_map(stock_data.get('Income', []))
        cashflow_map = _build_map(stock_data.get('CashFlow', []))
        capital_map = _build_map(stock_data.get('Capital', []))

        all_periods = sorted(set(
            list(pershare_map.keys()) + list(balance_map.keys()) +
            list(income_map.keys()) + list(cashflow_map.keys())
        ))

        rows = []

        def _pi(rec, field_names, default=0):
            for name in field_names:
                val = rec.get(name)
                if val is not None:
                    try:
                        v = float(val)
                        if v != 0:
                            return v
                    except (ValueError, TypeError):
                        pass
            return default

        for period in all_periods[-max_rows:]:
            pi = pershare_map.get(period, {})
            bi = balance_map.get(period, {})
            ii = income_map.get(period, {})
            ci = cashflow_map.get(period, {})
            cap = capital_map.get(period, {})

            n_oe = _pi(ii, ['revenue_inc', 'operating_revenue', 'total_operating_income'])
            net_profit = _pi(ii, ['net_profit_incl_min_int_inc', 'net_profit_excl_min_int_inc', 'net_profit'])

            rows.append({
                "报告期": period,
                "基本每股收益": _pi(pi, ['s_fa_eps_basic', 'eps']),
                "每股净资产": _pi(pi, ['s_fa_bps', 'bps']),
                "每股经营现金流": _pi(pi, ['s_fa_ocfps', 'ocfps']),
                "营业收入": float(n_oe),
                "净利润": float(net_profit),
                "总资产": _pi(bi, ['tot_assets', 'total_assets']),
                "净资产": _pi(bi, ['total_equity', 'total_owner_equity', 'tot_shrhldr_eqy_incl_min_int']),
                "ROE": _pi(pi, ['du_return_on_equity', 'roe', 'net_roe']),
                "毛利率": _pi(pi, ['sales_gross_profit', 'gross_profit_margin']),
                "净利率": float(ii.get('net_profit_margin', 0) or 0) if ii.get('net_profit_margin') else (net_profit / n_oe if n_oe else 0),
                "总股本": _pi(cap, ['total_capital', 'totalShares', 'totalCapital', 'total_shares', 'totalshares']),
                "流通股本": _pi(cap, ['circulating_capital', 'outstanding_shares', 'free_shares']),
            })

        return {"rows": rows}

    return api


app = create_app()
