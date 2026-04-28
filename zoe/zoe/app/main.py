from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from zoe.app.config import load_settings
from zoe.app.db import fetch_one
from zoe.app.chan_engine import add_chan_fields
from zoe.app.indicators import add_technical_indicators, has_talib, talib_backend, talib_error
from zoe.app.instances import StrategyInstance, load_instances, save_instances
from zoe.app.market_data import list_stock_codes, load_daily_ohlcv
from zoe.app.presets import Preset, load_presets, save_presets
from zoe.app.screener import FinancialFilters, score_factors, screen_financial
from zoe.app.signals import generate_signals
from zoe.app.strategy_registry import get_strategy_registry


settings = load_settings()
app = FastAPI(title="Zoe", version="0.1.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "web", "templates"))


@app.get("/", response_class=HTMLResponse)
def page_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/signals", response_class=HTMLResponse)
def page_signals(request: Request):
    return templates.TemplateResponse("signals.html", {"request": request})


@app.get("/screener", response_class=HTMLResponse)
def page_screener(request: Request):
    return templates.TemplateResponse("screener.html", {"request": request})


@app.get("/strategies", response_class=HTMLResponse)
def page_strategies(request: Request):
    return templates.TemplateResponse("strategies.html", {"request": request})


@app.get("/backtest", response_class=HTMLResponse)
def page_backtest(request: Request):
    return templates.TemplateResponse("backtest.html", {"request": request})


@app.get("/health")
def health():
    db_ok = False
    try:
        row = fetch_one(settings, "SELECT 1 AS ok", tuple())
        db_ok = bool(row and row.get("ok") == 1)
    except Exception:
        db_ok = False
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "talib": has_talib(),
        "talib_backend": talib_backend(),
        "talib_error": talib_error(),
        "db": db_ok,
    }


@app.get("/api/v1/stocks/sample")
def api_stocks_sample(limit: int = Query(default=50, ge=1, le=500)):
    codes = list_stock_codes(settings, limit=int(limit))
    return {"codes": codes}


def _parse_date(s: str) -> date:
    try:
        return pd.to_datetime(s).date()
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid_date: {s}")


@app.get("/api/v1/technical/series")
def api_technical_series(
    stock_code: str = Query(..., description="股票代码，如 600519.SH"),
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
):
    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    df = load_daily_ohlcv(settings, stock_code, start=start_d, end=end_d)
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data")
    df = add_technical_indicators(df)

    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        rows.append(
            {
                "trade_date": pd.to_datetime(r["trade_date"]).date().isoformat(),
                "open": None if pd.isna(r.get("open")) else float(r.get("open")),
                "high": None if pd.isna(r.get("high")) else float(r.get("high")),
                "low": None if pd.isna(r.get("low")) else float(r.get("low")),
                "close": None if pd.isna(r.get("close")) else float(r.get("close")),
                "volume": None if pd.isna(r.get("volume")) else float(r.get("volume")),
                "amount": None if pd.isna(r.get("amount")) else float(r.get("amount")),
                "ma5": None if pd.isna(r.get("ma5")) else float(r.get("ma5")),
                "ma10": None if pd.isna(r.get("ma10")) else float(r.get("ma10")),
                "ma20": None if pd.isna(r.get("ma20")) else float(r.get("ma20")),
                "ma60": None if pd.isna(r.get("ma60")) else float(r.get("ma60")),
                "rsi14": None if pd.isna(r.get("rsi14")) else float(r.get("rsi14")),
                "macd_dif": None if pd.isna(r.get("macd_dif")) else float(r.get("macd_dif")),
                "macd_dea": None if pd.isna(r.get("macd_dea")) else float(r.get("macd_dea")),
                "macd_hist": None if pd.isna(r.get("macd_hist")) else float(r.get("macd_hist")),
                "boll_upper": None if pd.isna(r.get("boll_upper")) else float(r.get("boll_upper")),
                "boll_mid": None if pd.isna(r.get("boll_mid")) else float(r.get("boll_mid")),
                "boll_lower": None if pd.isna(r.get("boll_lower")) else float(r.get("boll_lower")),
            }
        )

    return {"stock_code": stock_code, "rows": rows}


@app.get("/api/v1/signals")
def api_signals(
    stock_code: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
):
    start_d = _parse_date(start)
    end_d = _parse_date(end)
    df = load_daily_ohlcv(settings, stock_code, start=start_d, end=end_d)
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data")
    df = add_technical_indicators(df)
    sigs = generate_signals(df)
    return {
        "stock_code": stock_code,
        "signals": [
            {
                "trade_date": s.trade_date,
                "signal": s.signal,
                "score": s.score,
                "reasons": s.reasons,
                "snapshot": s.snapshot,
            }
            for s in sigs
        ],
    }


class ScreenerFinancialReq(BaseModel):
    filters: dict[str, float | None] = Field(default_factory=dict)
    stock_codes: list[str] | None = None
    limit: int = 200


@app.post("/api/v1/screener/financial")
def api_screener_financial(payload: ScreenerFinancialReq = Body(...)):
    f = payload.filters or {}
    filters = FinancialFilters(
        roe_min=f.get("roe_min"),
        net_margin_min=f.get("net_margin_min"),
        gross_margin_min=f.get("gross_margin_min"),
        debt_ratio_max=f.get("debt_ratio_max"),
        cashflow_to_revenue_min=f.get("cashflow_to_revenue_min"),
    )
    rows = screen_financial(settings, filters=filters, stock_codes=payload.stock_codes, limit=int(payload.limit))
    return {"rows": rows}


class ScreenerFactorsReq(BaseModel):
    stock_codes: list[str] | None = None
    as_of: str | None = None
    lookback_days: int = 180
    top_n: int = 30
    limit: int = 300


@app.post("/api/v1/screener/factors")
def api_screener_factors(payload: ScreenerFactorsReq = Body(...)):
    as_of = _parse_date(payload.as_of) if payload.as_of else None
    res = score_factors(
        settings,
        stock_codes=payload.stock_codes,
        as_of=as_of,
        lookback_days=int(payload.lookback_days),
        top_n=int(payload.top_n),
        limit=int(payload.limit),
    )
    return res


@app.get("/api/v1/strategies")
def api_strategies():
    reg = get_strategy_registry()
    strategies = []
    for _, meta in reg.items():
        strategies.append(
            {
                "strategy_id": meta.strategy_id,
                "name": meta.name,
                "description": meta.description,
                "params_schema": meta.params_schema,
                "default_params": meta.default_params,
                "requires_weekly": bool(getattr(meta, "requires_weekly", False)),
                "requires_chan": bool(getattr(meta, "requires_chan", False)),
                "requires_predictions": bool(getattr(meta, "requires_predictions", False)),
            }
        )
    return {"strategies": strategies}


@app.get("/api/v1/strategies/presets")
def api_list_presets(strategy_id: str | None = Query(default=None)):
    presets = load_presets(settings.presets_path)
    if strategy_id:
        presets = [p for p in presets if p.strategy_id == strategy_id]
    return {
        "presets": [
            {"preset_id": p.preset_id, "strategy_id": p.strategy_id, "name": p.name, "params": p.params} for p in presets
        ]
    }


class PresetCreateReq(BaseModel):
    preset_id: str | None = None
    strategy_id: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/strategies/presets")
def api_save_preset(payload: PresetCreateReq = Body(...)):
    reg = get_strategy_registry()
    if payload.strategy_id not in reg:
        raise HTTPException(status_code=400, detail="unknown_strategy")
    preset_id = (payload.preset_id or "").strip() or str(uuid4())

    presets = load_presets(settings.presets_path)
    presets = [p for p in presets if p.preset_id != preset_id]
    presets.append(
        Preset(
            preset_id=preset_id,
            strategy_id=payload.strategy_id,
            name=payload.name.strip(),
            params=payload.params or {},
        )
    )
    save_presets(settings.presets_path, presets)
    return {"preset_id": preset_id}


@app.delete("/api/v1/strategies/presets/{preset_id}")
def api_delete_preset(preset_id: str):
    presets = load_presets(settings.presets_path)
    new_presets = [p for p in presets if p.preset_id != preset_id]
    save_presets(settings.presets_path, new_presets)
    return {"deleted": preset_id}


@app.get("/api/v1/strategy-instances")
def api_list_strategy_instances(strategy_id: str | None = Query(default=None)):
    instances = load_instances(settings.instances_path)
    if strategy_id:
        instances = [x for x in instances if x.strategy_id == strategy_id]
    return {
        "instances": [
            {"instance_id": x.instance_id, "strategy_id": x.strategy_id, "name": x.name, "params": x.params} for x in instances
        ]
    }


class StrategyInstanceCreateReq(BaseModel):
    instance_id: str | None = None
    strategy_id: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


def _coerce_params(strategy: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    schema = strategy.get("params_schema") or {}
    defaults = strategy.get("default_params") or {}
    merged = dict(defaults)
    merged.update(params or {})

    out: dict[str, Any] = {}
    for k, meta in schema.items():
        if k not in merged:
            continue
        v = merged.get(k)
        t = str((meta or {}).get("type") or "").lower()
        if t in ("int", "integer"):
            try:
                out[k] = int(v)
            except Exception:
                raise HTTPException(status_code=400, detail=f"invalid_param:{k}")
        elif t in ("float", "number"):
            try:
                out[k] = float(v)
            except Exception:
                raise HTTPException(status_code=400, detail=f"invalid_param:{k}")
        elif t in ("bool", "boolean"):
            if isinstance(v, bool):
                out[k] = v
            elif isinstance(v, str) and v.lower() in ("true", "false"):
                out[k] = v.lower() == "true"
            else:
                raise HTTPException(status_code=400, detail=f"invalid_param:{k}")
        elif t == "enum":
            values = (meta or {}).get("values") or []
            if v not in values:
                raise HTTPException(status_code=400, detail=f"invalid_param:{k}")
            out[k] = v
        elif t == "object":
            if not isinstance(v, dict):
                raise HTTPException(status_code=400, detail=f"invalid_param:{k}")
            out[k] = v
        else:
            out[k] = v

    for k in list(out.keys()):
        if k not in schema:
            out.pop(k, None)
    return out


@app.post("/api/v1/strategy-instances")
def api_create_strategy_instance(payload: StrategyInstanceCreateReq = Body(...)):
    reg = get_strategy_registry()
    meta = reg.get(payload.strategy_id)
    if not meta:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="empty_name")

    strategy = {
        "params_schema": meta.params_schema,
        "default_params": meta.default_params,
    }
    resolved_params = _coerce_params(strategy, payload.params or {})

    instances = load_instances(settings.instances_path)
    next_id = 1
    for x in instances:
        if x.instance_id.isdigit():
            next_id = max(next_id, int(x.instance_id) + 1)
    instance_id = str(next_id)
    instances.append(StrategyInstance(instance_id=instance_id, strategy_id=payload.strategy_id, name=name, params=resolved_params))
    save_instances(settings.instances_path, instances)
    return {"instance_id": instance_id}


@app.delete("/api/v1/strategy-instances/{instance_id}")
def api_delete_strategy_instance(instance_id: str):
    instances = load_instances(settings.instances_path)
    new_instances = [x for x in instances if x.instance_id != instance_id]
    save_instances(settings.instances_path, new_instances)
    return {"deleted": instance_id}


class BacktestReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    commission: float = 0.001


@app.post("/api/v1/backtest/run")
def api_backtest(payload: BacktestReq = Body(...)):
    start_d = _parse_date(payload.start)
    end_d = _parse_date(payload.end)
    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    reg = get_strategy_registry()
    meta = reg.get(payload.strategy_id)
    if not meta:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    df = load_daily_ohlcv(settings, payload.stock_code, start=start_d, end=end_d)
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data")

    try:
        import backtrader  # type: ignore
    except ModuleNotFoundError:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "backtrader_missing",
                "message": "回测功能需要 backtrader 依赖。",
                "hint": "在 zoe 目录执行：pip install -r requirements-backtest.txt",
            },
        )

    if bool(getattr(meta, "requires_chan", False)):
        p = payload.params or {}
        backend = str(p.get("chan_backend") or "chanpy").strip()
        if backend not in ("chanpy", "self"):
            raise HTTPException(status_code=400, detail="invalid_chan_backend")
        try:
            cres = add_chan_fields(df, backend=backend, symbol=payload.stock_code)
            df = cres.df
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"chan_engine_failed: {e}")

    try:
        from zoe.app.backtest import run_backtest
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"backtrader_unavailable: {e}")

    try:
        strategy_cls = meta.bt_strategy_factory()
    except ModuleNotFoundError as e:
        if getattr(e, "name", None) == "backtrader":
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "backtrader_missing",
                    "message": "回测功能需要 backtrader 依赖。",
                    "hint": "在 zoe 目录执行：pip install -r requirements-backtest.txt",
                },
            )
        raise HTTPException(status_code=500, detail=f"strategy_factory_failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"strategy_factory_failed: {e}")

    res = run_backtest(
        df=df,
        strategy_cls=strategy_cls,
        strategy_params=payload.params,
        initial_cash=float(payload.initial_cash),
        commission=float(payload.commission),
        requires_weekly=bool(getattr(meta, "requires_weekly", False)),
    )
    if isinstance(res.metrics, dict) and res.metrics.get("error") == "backtrader_missing":
        raise HTTPException(status_code=500, detail=res.metrics)
    return {"metrics": res.metrics, "trades": res.trades}


def _mount_static() -> None:
    static_dir = os.path.join(BASE_DIR, "web", "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")


_mount_static()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)

