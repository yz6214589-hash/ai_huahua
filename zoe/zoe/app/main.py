from __future__ import annotations

import os
import sys
from datetime import date, datetime
from importlib import import_module
from importlib import metadata
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
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
from zoe.app.performance.broker import load_broker_csv_bytes_list
from zoe.app.performance.charts import compute_chart_series
from zoe.app.performance.io import read_nav_csv_bytes
from zoe.app.performance.portfolio import analyze_by_stock, analyze_costs, build_portfolio_nav_from_trades
from zoe.app.performance.quantstats_engine import calc_quantstats_metrics
from zoe.app.performance.report import generate_report_html
from zoe.app.performance.svd import diagnose_market_regime
from zoe.app.mainforce.engine import run_mainforce_job
from zoe.app.mainforce.params import validate_mainforce_params
from zoe.app.mainforce.store import MainForceTask, create_task, delete_task, get_task, load_tasks, save_tasks, upsert_task


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


@app.get("/performance", response_class=HTMLResponse)
def page_performance(request: Request):
    return templates.TemplateResponse("performance.html", {"request": request})


@app.get("/mainforce", response_class=HTMLResponse)
def page_mainforce(request: Request):
    return templates.TemplateResponse("mainforce.html", {"request": request})


@app.get("/health")
def health():
    def dep(pkg: str, mod: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {"package": pkg}
        try:
            out["version"] = metadata.version(pkg)
        except Exception as e:
            out["version_error"] = str(e)
        if mod:
            try:
                import_module(mod)
                out["import_ok"] = True
            except Exception as e:
                out["import_ok"] = False
                out["import_error"] = str(e)
        return out

    db_ok = False
    try:
        row = fetch_one(settings, "SELECT 1 AS ok", tuple())
        db_ok = bool(row and row.get("ok") == 1)
    except Exception:
        db_ok = False
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split(" ")[0],
        "talib": has_talib(),
        "talib_backend": talib_backend(),
        "talib_error": talib_error(),
        "db": db_ok,
        "deps": {
            "websockets": dep("websockets", "websockets"),
            "quantstats": dep("quantstats", "quantstats"),
            "yfinance": dep("yfinance", "yfinance"),
        },
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
    return {"metrics": res.metrics, "trades": res.trades, "nav_log": getattr(res, "nav_log", [])}


class CommonPerfBacktestReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    commission: float = 0.001
    benchmark_code: str | None = None


def _load_close_series(stock_code: str, start_d: date, end_d: date) -> pd.Series:
    df = load_daily_ohlcv(settings, stock_code, start=start_d, end=end_d)
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data")
    s = df.set_index("trade_date")["close"].astype(float)
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    return s


def _close_to_returns(close: pd.Series) -> pd.Series:
    c = close.copy()
    c.index = pd.to_datetime(c.index)
    c = c.sort_index().astype(float)
    r = c.pct_change().fillna(0.0)
    return r


def _maybe_load_benchmark_returns(benchmark_code: str | None, start_d: date, end_d: date) -> pd.Series | None:
    code = (benchmark_code or "").strip()
    if not code:
        return None
    close = _load_close_series(code, start_d, end_d)
    return _close_to_returns(close)


@app.post("/api/v1/performance/quantstats/common/backtest")
def api_perf_common_backtest(payload: CommonPerfBacktestReq = Body(...)):
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

    nav_log = getattr(res, "nav_log", []) or []
    if not nav_log:
        raise HTTPException(status_code=500, detail="nav_log_empty")
    nav_df = pd.DataFrame(nav_log)
    nav_df["date"] = pd.to_datetime(nav_df["date"])
    nav_df["nav"] = pd.to_numeric(nav_df["nav"], errors="coerce")
    nav_df = nav_df.dropna(subset=["date", "nav"]).sort_values("date")
    nav = (nav_df.set_index("date")["nav"].astype(float) / float(payload.initial_cash)).astype(float)
    returns = nav.pct_change().fillna(0.0)

    benchmark = _maybe_load_benchmark_returns(payload.benchmark_code, start_d, end_d)
    metrics = calc_quantstats_metrics(returns, benchmark=benchmark)
    chart_series = compute_chart_series(returns)
    rep = generate_report_html(returns=returns, benchmark=benchmark, output_dir=os.path.abspath(settings.reports_path))
    report_url = f"/reports/{rep['report_filename']}"

    return {"metrics": metrics, "chart_series": chart_series, "report_url": report_url}


@app.post("/api/v1/performance/quantstats/common/navcsv")
def api_perf_common_navcsv(file: UploadFile = File(...), benchmark_code: str | None = Form(default=None)):
    content = file.file.read()
    nav_raw = read_nav_csv_bytes(content)
    nav_raw.index = pd.to_datetime(nav_raw.index)
    nav_raw = nav_raw.sort_index().astype(float)
    nav = (nav_raw / float(nav_raw.iloc[0])).astype(float)
    returns = nav.pct_change().fillna(0.0)

    start_d = nav.index.min().date()
    end_d = nav.index.max().date()
    benchmark = _maybe_load_benchmark_returns(benchmark_code, start_d, end_d)
    metrics = calc_quantstats_metrics(returns, benchmark=benchmark)
    chart_series = compute_chart_series(returns)
    rep = generate_report_html(returns=returns, benchmark=benchmark, output_dir=os.path.abspath(settings.reports_path))
    report_url = f"/reports/{rep['report_filename']}"

    return {"metrics": metrics, "chart_series": chart_series, "report_url": report_url}


@app.post("/api/v1/performance/quantstats/plus/brokercsv")
def api_perf_plus_brokercsv(
    files: list[UploadFile] = File(...),
    initial_cash: float = Form(...),
    svd_window: int = Form(default=120),
    svd_step: int = Form(default=20),
    benchmark_code: str | None = Form(default=None),
):
    contents = [f.file.read() for f in files]
    trades = load_broker_csv_bytes_list(contents)
    if trades.empty:
        raise HTTPException(status_code=400, detail="empty_trades")

    start_d = pd.to_datetime(trades["成交日期"]).min().date()
    end_d = pd.to_datetime(trades["成交日期"]).max().date()

    close_map: dict[str, pd.Series] = {}
    for code in trades["标准代码"].dropna().unique().tolist():
        close = _load_close_series(str(code), start_d, end_d)
        close_map[str(code)] = close

    nav = build_portfolio_nav_from_trades(trades, close_map=close_map, initial_cash=float(initial_cash))
    returns = nav.pct_change().fillna(0.0)

    benchmark = _maybe_load_benchmark_returns(benchmark_code, start_d, end_d)
    metrics = calc_quantstats_metrics(returns, benchmark=benchmark)
    chart_series = compute_chart_series(returns)
    costs = analyze_costs(trades)
    per_stock = analyze_by_stock(trades)

    svd = None
    try:
        ret_map = {code: _close_to_returns(s).replace([pd.NA], 0.0) for code, s in close_map.items()}
        ret_df = pd.DataFrame(ret_map).dropna(how="any")
        svd = diagnose_market_regime(ret_df, window=int(svd_window), step=int(svd_step))
    except Exception as e:
        svd = {"skipped": True, "reason": str(e)}

    rep = generate_report_html(returns=returns, benchmark=benchmark, output_dir=os.path.abspath(settings.reports_path))
    report_url = f"/reports/{rep['report_filename']}"
    return {
        "metrics": metrics,
        "chart_series": chart_series,
        "report_url": report_url,
        "costs": costs,
        "per_stock": per_stock,
        "svd": svd,
    }


class PlusComboItem(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str | None = None
    instance_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


class PlusComboReq(BaseModel):
    items: list[PlusComboItem]
    initial_cash: float = 1000000.0
    commission: float = 0.001
    svd_window: int = 120
    svd_step: int = 20
    benchmark_code: str | None = None


@app.post("/api/v1/performance/quantstats/plus/combo")
def api_perf_plus_combo(payload: PlusComboReq = Body(...)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="empty_items")

    reg = get_strategy_registry()
    instances = {x.instance_id: x for x in load_instances(settings.instances_path)}

    nav_series_list: list[pd.Series] = []
    weights: list[float] = []
    codes: list[str] = []

    for item in payload.items:
        start_d = _parse_date(item.start)
        end_d = _parse_date(item.end)
        if start_d > end_d:
            raise HTTPException(status_code=400, detail="start_after_end")

        strategy_id = (item.strategy_id or "").strip()
        params = item.params or {}
        if item.instance_id:
            inst = instances.get(str(item.instance_id))
            if not inst:
                raise HTTPException(status_code=400, detail="unknown_instance")
            strategy_id = inst.strategy_id
            params = dict(inst.params or {})

        meta = reg.get(strategy_id)
        if not meta:
            raise HTTPException(status_code=400, detail="unknown_strategy")

        df = load_daily_ohlcv(settings, item.stock_code, start=start_d, end=end_d)
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
            p = params or {}
            backend = str(p.get("chan_backend") or "chanpy").strip()
            if backend not in ("chanpy", "self"):
                raise HTTPException(status_code=400, detail="invalid_chan_backend")
            try:
                cres = add_chan_fields(df, backend=backend, symbol=item.stock_code)
                df = cres.df
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"chan_engine_failed: {e}")

        from zoe.app.backtest import run_backtest

        res = run_backtest(
            df=df,
            strategy_cls=meta.bt_strategy_factory(),
            strategy_params=params,
            initial_cash=float(payload.initial_cash),
            commission=float(payload.commission),
            requires_weekly=bool(getattr(meta, "requires_weekly", False)),
        )
        if isinstance(res.metrics, dict) and res.metrics.get("error") == "backtrader_missing":
            raise HTTPException(status_code=500, detail=res.metrics)
        nav_log = getattr(res, "nav_log", []) or []
        if not nav_log:
            raise HTTPException(status_code=500, detail="nav_log_empty")
        nav_df = pd.DataFrame(nav_log)
        nav_df["date"] = pd.to_datetime(nav_df["date"])
        nav_df["nav"] = pd.to_numeric(nav_df["nav"], errors="coerce")
        nav_df = nav_df.dropna(subset=["date", "nav"]).sort_values("date")
        nav = (nav_df.set_index("date")["nav"].astype(float) / float(payload.initial_cash)).astype(float)

        nav_series_list.append(nav)
        weights.append(float(item.weight))
        codes.append(str(item.stock_code))

    if not nav_series_list:
        raise HTTPException(status_code=400, detail="empty_nav")

    wsum = float(sum(weights)) if sum(weights) else 1.0
    w_norm = [float(w) / wsum for w in weights]
    nav_df = pd.concat(nav_series_list, axis=1, join="inner")
    if nav_df.empty:
        raise HTTPException(status_code=400, detail="no_common_dates")
    nav_df.columns = codes
    port_nav = (nav_df * w_norm).sum(axis=1)
    port_returns = port_nav.pct_change().fillna(0.0)

    start_d = port_nav.index.min().date()
    end_d = port_nav.index.max().date()
    benchmark = _maybe_load_benchmark_returns(payload.benchmark_code, start_d, end_d)
    metrics = calc_quantstats_metrics(port_returns, benchmark=benchmark)
    chart_series = compute_chart_series(port_returns)

    svd = None
    try:
        close_map = {c: _load_close_series(c, start_d, end_d) for c in codes}
        ret_df = pd.DataFrame({c: _close_to_returns(s) for c, s in close_map.items()}).dropna(how="any")
        svd = diagnose_market_regime(ret_df, window=int(payload.svd_window), step=int(payload.svd_step))
    except Exception as e:
        svd = {"skipped": True, "reason": str(e)}

    rep = generate_report_html(returns=port_returns, benchmark=benchmark, output_dir=os.path.abspath(settings.reports_path))
    report_url = f"/reports/{rep['report_filename']}"

    per_stock = [{"stock_code": c, "weight": w_norm[i]} for i, c in enumerate(codes)]
    return {"metrics": metrics, "chart_series": chart_series, "report_url": report_url, "per_stock": per_stock, "svd": svd}


class MainForceTaskCreateReq(BaseModel):
    stock_code: str
    company_name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


def _validate_mainforce_params(params: dict[str, Any]) -> dict[str, int]:
    p = params or {}
    allowed = {"n_samples_per_class", "seed", "n_ticks", "window"}
    unknown = [k for k in p.keys() if k not in allowed]
    if unknown:
        raise HTTPException(status_code=400, detail={"error": "invalid_params", "fields": {"params": f"unknown_keys: {unknown}"}})

    def as_int(key: str, default: int) -> int:
        v = p.get(key, default)
        if v is None:
            return int(default)
        try:
            return int(v)
        except Exception:
            raise HTTPException(status_code=400, detail={"error": "invalid_params", "fields": {key: "not_int"}})

    n_samples_per_class = as_int("n_samples_per_class", 200)
    seed = as_int("seed", 42)
    n_ticks = as_int("n_ticks", 300)
    window = as_int("window", 50)

    errors: dict[str, str] = {}
    if n_samples_per_class < 1 or n_samples_per_class > 500:
        errors["n_samples_per_class"] = "range: 1..500"
    if n_ticks < 30 or n_ticks > 1000:
        errors["n_ticks"] = "range: 30..1000"
    if window < 5 or window > 300:
        errors["window"] = "range: 5..300"
    if window >= n_ticks:
        errors["window"] = "must_be_lt_n_ticks"
    if errors:
        raise HTTPException(status_code=400, detail={"error": "invalid_params", "fields": errors})

    return {
        "n_samples_per_class": int(n_samples_per_class),
        "seed": int(seed),
        "n_ticks": int(n_ticks),
        "window": int(window),
    }


def _task_to_dict(t: MainForceTask) -> dict[str, Any]:
    return {
        "task_id": t.task_id,
        "stock_code": t.stock_code,
        "company_name": t.company_name,
        "mode": t.mode,
        "params": t.params,
        "status": t.status,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "result": t.result,
        "artifacts": t.artifacts,
    }


@app.get("/api/v1/mainforce/tasks")
def api_mainforce_list_tasks():
    tasks = load_tasks(settings.mainforce_tasks_path)
    out = []
    for t in tasks:
        out.append(
            {
                "task_id": t.task_id,
                "stock_code": t.stock_code,
                "company_name": t.company_name,
                "status": t.status,
                "updated_at": t.updated_at,
                "result_summary": {
                    "label": (t.result or {}).get("label"),
                    "test_acc": (t.result or {}).get("test_acc"),
                },
            }
        )
    return {"tasks": out}


@app.post("/api/v1/mainforce/tasks")
def api_mainforce_create_task(payload: MainForceTaskCreateReq = Body(...)):
    stock_code = (payload.stock_code or "").strip()
    if not stock_code:
        raise HTTPException(status_code=400, detail="empty_stock_code")

    params = validate_mainforce_params(payload.params or {})
    task = create_task(stock_code=stock_code, company_name=payload.company_name, params=params, tasks_path=settings.mainforce_tasks_path)
    tasks = load_tasks(settings.mainforce_tasks_path)
    tasks.append(task)
    save_tasks(settings.mainforce_tasks_path, tasks)
    return {"task_id": task.task_id}


@app.get("/api/v1/mainforce/tasks/{task_id}")
def api_mainforce_get_task(task_id: str):
    t = get_task(settings.mainforce_tasks_path, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="not_found")
    return {"task": _task_to_dict(t)}


@app.delete("/api/v1/mainforce/tasks/{task_id}")
def api_mainforce_delete_task(task_id: str):
    ok = delete_task(settings.mainforce_tasks_path, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not_found")
    return {"deleted": task_id}


def _write_mainforce_report(task_id: str, result: dict[str, Any], artifacts: dict[str, Any]) -> str | None:
    reports_dir = os.path.abspath(settings.reports_path)
    os.makedirs(reports_dir, exist_ok=True)

    filename = f"mainforce_{task_id}.html"
    path = os.path.join(reports_dir, filename)

    label = str(result.get("label") or "")
    train_acc = result.get("train_acc")
    test_acc = result.get("test_acc")
    proba = result.get("pred_proba") if isinstance(result.get("pred_proba"), dict) else {}

    def _img(url: str | None) -> str:
        if not url:
            return ""
        return f'<img src="{url}" style="max-width:100%;border:1px solid #e5e7eb;border-radius:10px;" />'

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>主力识别报告 - {task_id}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; padding: 16px; }}
    .card {{ border:1px solid #e5e7eb; border-radius: 10px; padding: 12px; margin-bottom: 12px; }}
    .muted {{ color: #6b7280; }}
    table {{ width:100%; border-collapse: collapse; }}
    th, td {{ border-bottom:1px solid #e5e7eb; padding:8px; font-size:12px; text-align:left; }}
    .grid {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .grid > div {{ flex: 1; min-width: 320px; }}
  </style>
</head>
<body>
  <div class="card">
    <div style="font-weight:700;">主力识别报告</div>
    <div class="muted">task_id={task_id}</div>
  </div>
  <div class="card">
    <div style="font-weight:700;margin-bottom:6px;">结论</div>
    <table>
      <tbody>
        <tr><th style="width:220px;">label</th><td class="muted">{label}</td></tr>
        <tr><th>train_acc</th><td class="muted">{train_acc}</td></tr>
        <tr><th>test_acc</th><td class="muted">{test_acc}</td></tr>
        <tr><th>pred_proba</th><td class="muted">{proba}</td></tr>
      </tbody>
    </table>
  </div>
  <div class="card">
    <div style="font-weight:700;margin-bottom:6px;">图表</div>
    <div class="grid">
      <div>{_img(artifacts.get("radar_png"))}</div>
      <div>{_img(artifacts.get("feature_importance_png"))}</div>
      <div>{_img(artifacts.get("patterns_png"))}</div>
      <div>{_img(artifacts.get("confusion_png"))}</div>
    </div>
  </div>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"/reports/{filename}"


@app.post("/api/v1/mainforce/tasks/{task_id}/run")
def api_mainforce_run_task(task_id: str):
    t = get_task(settings.mainforce_tasks_path, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="not_found")

    p = validate_mainforce_params(t.params or {})
    now = datetime.now().isoformat(timespec="seconds")
    running = MainForceTask(
        task_id=t.task_id,
        stock_code=t.stock_code,
        company_name=t.company_name,
        mode=t.mode,
        params=p,
        status="running",
        created_at=t.created_at,
        updated_at=now,
        result=t.result,
        artifacts=t.artifacts,
    )
    upsert_task(settings.mainforce_tasks_path, running)

    out_dir = os.path.join(os.path.abspath(settings.mainforce_artifacts_path), t.task_id)
    try:
        res = run_mainforce_job(
            output_dir=out_dir,
            n_samples_per_class=int(p.get("n_samples_per_class")),
            seed=int(p.get("seed")),
            n_ticks=int(p.get("n_ticks")),
            window=int(p.get("window")),
            stock_code=t.stock_code,
        )
        artifacts_url = {
            "radar_png": f"/mainforce-assets/{t.task_id}/radar.png",
            "patterns_png": f"/mainforce-assets/{t.task_id}/patterns.png",
            "confusion_png": f"/mainforce-assets/{t.task_id}/confusion.png",
            "feature_importance_png": f"/mainforce-assets/{t.task_id}/feature_importance.png",
        }
        result = {
            "label": res.get("pred_label"),
            "pred_proba": res.get("pred_proba"),
            "train_acc": res.get("train_acc"),
            "test_acc": res.get("test_acc"),
            "feature_importance_top": (res.get("feature_importance") or [])[:6],
        }
        report_url = _write_mainforce_report(t.task_id, result=result, artifacts=artifacts_url)
        if report_url:
            artifacts_url["report_url"] = report_url

        done = MainForceTask(
            task_id=t.task_id,
            stock_code=t.stock_code,
            company_name=t.company_name,
            mode=t.mode,
            params=t.params,
            status="done",
            created_at=t.created_at,
            updated_at=datetime.now().isoformat(timespec="seconds"),
            result=result,
            artifacts=artifacts_url,
        )
        upsert_task(settings.mainforce_tasks_path, done)
        return {"status": "done", "result": result}
    except Exception as e:
        failed = MainForceTask(
            task_id=t.task_id,
            stock_code=t.stock_code,
            company_name=t.company_name,
            mode=t.mode,
            params=t.params,
            status="failed",
            created_at=t.created_at,
            updated_at=datetime.now().isoformat(timespec="seconds"),
            result={"error": str(e)},
            artifacts=t.artifacts,
        )
        upsert_task(settings.mainforce_tasks_path, failed)
        raise HTTPException(status_code=500, detail=str(e))


def _mount_static() -> None:
    static_dir = os.path.join(BASE_DIR, "web", "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    reports_dir = os.path.abspath(getattr(settings, "reports_path", "./zoe/data/reports"))
    os.makedirs(reports_dir, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")
    mainforce_dir = os.path.abspath(getattr(settings, "mainforce_artifacts_path", "./zoe/data/mainforce"))
    os.makedirs(mainforce_dir, exist_ok=True)
    app.mount("/mainforce-assets", StaticFiles(directory=mainforce_dir), name="mainforce_assets")


_mount_static()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)

