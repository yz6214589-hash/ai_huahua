from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from core.db import connect, execute, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("sentiment_store")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _store_root() -> Path:
    root = _project_root() / ".ai_quant"
    root.mkdir(parents=True, exist_ok=True)
    return root


SENTIMENT_ROOT = _store_root() / "sentiment"
RUNS_DIR = SENTIMENT_ROOT / "runs"
EVENTS_DIR = SENTIMENT_ROOT / "events"
SCHEDULE_FILE = SENTIMENT_ROOT / "schedule.json"
MACRO_FILE = SENTIMENT_ROOT / "macro.json"

_DEFAULT_SCHEDULE: dict[str, Any] = {
    "enabled": True,
    "cron": "10 15 * * 1-5",
    "timezone": "Asia/Shanghai",
    "frequency": "daily",
    "market_time": "14:00",
    "fixed_time": "15:10",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)


#
#  运行记录持久化
#

def write_run(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_dirs()
    run_id = str(payload.get("run_id") or "").strip() or uuid4().hex
    record = dict(payload)
    record["run_id"] = run_id
    if "created_at" not in record or not record["created_at"]:
        record["created_at"] = _now_iso()
    tmp = RUNS_DIR / f".{run_id}.json.tmp"
    out = RUNS_DIR / f"{run_id}.json"
    try:
        tmp.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(out)
        logger.info("运行记录写入成功", extra={
            "run_id": run_id,
            "status": record.get("status"),
            "file_path": str(out),
        })
    except Exception as e:
        logger.error("运行记录写入失败", extra={
            "run_id": run_id,
            "error": str(e),
            "error_type": type(e).__name__,
        })
    return record


def read_run(run_id: str) -> dict[str, Any] | None:
    rid = str(run_id or "").strip()
    if not rid:
        logger.warning("运行记录读取失败，run_id 为空")
        return None
    p = RUNS_DIR / f"{rid}.json"
    if p.exists() and p.is_file():
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                logger.info("运行记录读取成功", extra={
                    "run_id": rid,
                    "status": obj.get("status"),
                })
                return obj
            else:
                logger.warning("运行记录格式异常", extra={
                    "run_id": rid,
                    "expected": "dict",
                    "actual": type(obj).__name__,
                })
        except Exception as e:
            logger.error("运行记录JSON解析失败", extra={
                "run_id": rid,
                "error": str(e),
                "error_type": type(e).__name__,
            })
    else:
        logger.info("运行记录文件不存在", extra={"run_id": rid})
    return None


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    n = max(1, min(limit, 200))
    _ensure_dirs()
    items: list[tuple[float, dict[str, Any]]] = []
    for p in RUNS_DIR.glob("*.json"):
        if p.name.startswith("."):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("运行记录文件解析失败，已跳过", extra={
                "file": str(p),
                "error": str(e),
            })
            continue
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = 0.0
        if isinstance(data, dict):
            items.append((mtime, data))
    items.sort(key=lambda x: x[0], reverse=True)
    result = [x[1] for x in items[:n]]
    logger.info("运行记录列表查询完成", extra={
        "total": len(items),
        "returned": len(result),
        "limit": n,
    })
    return result


def delete_run(run_id: str) -> bool:
    rid = str(run_id or "").strip()
    if not rid:
        logger.warning("运行记录删除失败，run_id 为空")
        return False
    p = RUNS_DIR / f"{rid}.json"
    if p.exists():
        try:
            p.unlink(missing_ok=True)
            logger.info("运行记录删除成功", extra={"run_id": rid})
            return True
        except Exception as e:
            logger.error("运行记录文件删除失败", extra={
                "run_id": rid,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            return False
    logger.info("运行记录删除失败，文件不存在", extra={"run_id": rid})
    return False


#
#  事件持久化
#

def next_event_id() -> int:
    _ensure_dirs()
    max_id = 0
    for p in EVENTS_DIR.glob("*.json"):
        if p.name.startswith("."):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                eid = int(data.get("id") or 0)
                if eid > max_id:
                    max_id = eid
        except Exception as e:
            logger.warning("事件文件解析失败，跳过计算ID", extra={
                "file": str(p),
                "error": str(e),
            })
    next_id = max_id + 1
    logger.info("下一个事件ID计算完成", extra={
        "max_existing": max_id,
        "next_id": next_id,
    })
    return next_id


def write_event(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_dirs()
    record = dict(payload)
    if "id" not in record:
        record["id"] = next_event_id()
    event_id = str(record["id"])
    tmp = EVENTS_DIR / f".{event_id}.json.tmp"
    out = EVENTS_DIR / f"{event_id}.json"
    try:
        tmp.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(out)
        logger.info("事件写入成功", extra={
            "event_id": event_id,
            "run_id": record.get("run_id"),
            "stock_code": record.get("stock_code"),
            "file_path": str(out),
        })
    except Exception as e:
        logger.error("事件写入失败", extra={
            "event_id": event_id,
            "run_id": record.get("run_id"),
            "error": str(e),
            "error_type": type(e).__name__,
        })
    return record


def list_events(
    run_id: str | None = None,
    limit: int = 200,
    q: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    n = max(1, min(limit, 500))
    _ensure_dirs()
    out: list[dict[str, Any]] = []
    filter_info = {}
    if run_id:
        filter_info["run_id"] = run_id
    if q:
        filter_info["keyword"] = q
    if event_type:
        filter_info["event_type"] = event_type
    logger.info("事件列表查询开始", extra={
        "filters": filter_info,
        "limit": n,
    })
    for p in EVENTS_DIR.glob("*.json"):
        if p.name.startswith("."):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("事件文件解析失败，已跳过", extra={
                "file": str(p),
                "error": str(e),
            })
            continue
        if not isinstance(data, dict):
            continue
        if run_id:
            rid = str(run_id).strip()
            if str(data.get("run_id") or "") != rid:
                continue
        if q:
            kw = str(q).strip().lower()
            if kw:
                hay = " ".join([
                    str(data.get("stock_code") or "").lower(),
                    str(data.get("stock_name") or "").lower(),
                    str(data.get("source_title") or "").lower(),
                ])
                if kw not in hay:
                    continue
        if event_type and str(event_type).strip() and str(event_type) != "全部":
            if str(data.get("event_type") or "") != str(event_type).strip():
                continue
        out.append(data)
        if len(out) >= n:
            break
    logger.info("事件列表查询完成", extra={
        "returned": len(out),
        "filters": filter_info,
    })
    return out


def delete_events_by_run(run_id: str) -> int:
    rid = str(run_id or "").strip()
    if not rid:
        logger.warning("按运行记录删除事件失败，run_id 为空")
        return 0
    count = 0
    for p in EVENTS_DIR.glob("*.json"):
        if p.name.startswith("."):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("事件文件解析失败，跳过删除检查", extra={
                "file": str(p),
                "error": str(e),
            })
            continue
        if isinstance(data, dict) and str(data.get("run_id") or "") == rid:
            try:
                p.unlink(missing_ok=True)
                count += 1
            except Exception as e:
                logger.error("事件文件删除失败", extra={
                    "file": str(p),
                    "error": str(e),
                })
    logger.info("按运行记录删除事件完成", extra={
        "run_id": rid,
        "deleted_count": count,
    })
    return count


#
#  调度配置持久化
#

def get_schedule() -> dict[str, Any]:
    if SCHEDULE_FILE.exists():
        try:
            data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                logger.info("调度配置读取成功（从文件）", extra={
                    "file_path": str(SCHEDULE_FILE),
                    "schedule": data,
                })
                return data
            else:
                logger.warning("调度配置文件格式异常，使用默认配置", extra={
                    "expected": "dict",
                    "actual": type(data).__name__,
                })
        except Exception as e:
            logger.error("调度配置文件解析失败，使用默认配置", extra={
                "file_path": str(SCHEDULE_FILE),
                "error": str(e),
                "error_type": type(e).__name__,
            })
    cfg = dict(_DEFAULT_SCHEDULE)
    logger.info("调度配置使用默认值", extra={"schedule": cfg})
    save_schedule(cfg)
    return cfg


def save_schedule(cfg: dict[str, Any]) -> dict[str, Any]:
    SENTIMENT_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SENTIMENT_ROOT / ".schedule.json.tmp"
    try:
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(SCHEDULE_FILE)
        logger.info("调度配置写入成功", extra={
            "file_path": str(SCHEDULE_FILE),
            "schedule": cfg,
        })
    except Exception as e:
        logger.error("调度配置写入失败", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": str(SCHEDULE_FILE),
        })
    return dict(cfg)


#
#  宏观指标：从 trade_macro_indicator 表读取
#

def _fred_latest(series_id: str) -> tuple:
    """
    从 FRED 公开 CSV 获取最后一笔有效观测值。
    地址: https://fred.stlouisfed.org/graph/fredgraph.csv?id=<series_id>
    无需 API Key。

    Returns:
        (value, date_str) 或 (None, None)
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("FRED CSV 获取失败", extra={
            "series_id": series_id,
            "error": str(e),
        })
        return None, None

    last_val, last_date = None, None
    for line in resp.text.strip().splitlines():
        if line.startswith("DATE"):
            continue
        parts = line.split(",", 1)
        if len(parts) < 2:
            continue
        raw = parts[1].strip()
        if raw == "" or raw == ".":
            continue
        try:
            last_val = float(raw)
            last_date = parts[0].strip()
        except ValueError:
            continue
    return last_val, last_date


def _fred_history(series_id: str, days: int = 90) -> list[dict[str, Any]]:
    """
    从 FRED 公开 CSV 获取历史数据。
    返回最近 days 天内的有效数据点列表。
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("FRED 历史数据获取失败", extra={"series_id": series_id, "error": str(e)})
        return []

    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    data: list[dict[str, Any]] = []
    for line in resp.text.strip().splitlines():
        if line.startswith("DATE"):
            continue
        parts = line.split(",", 1)
        if len(parts) < 2:
            continue
        date_str = parts[0].strip()
        raw = parts[1].strip()
        if raw == "" or raw == "." or date_str < cutoff:
            continue
        try:
            data.append({"date": date_str, "value": float(raw)})
        except ValueError:
            continue
    return data


def _compute_fear_greed(vix_value: float | None) -> int | None:
    """
    基于 VIX 值计算恐惧贪婪指数（0-100）。
    仅作为 CNN 数据不可用时的降级方案。

    映射规则:
      VIX > 35: 极度恐慌, 指数 10-20
      VIX 25-35: 恐慌, 指数 20-35
      VIX 20-25: 焦虑, 指数 35-50
      VIX 15-20: 正常, 指数 50-65
      VIX < 15: 贪婪, 指数 65-80

    公式: fear_greed = max(0, min(100, 100 - (vix_value - 10) * 2.5))
    """
    if vix_value is None:
        return None
    return max(0, min(100, int(round(100 - (vix_value - 10) * 2.5))))


def _fetch_cnn_fear_greed() -> tuple[float | None, str | None, str]:
    """
    从 CNN 官方 API 获取 Fear & Greed Index。

    CNN Fear & Greed Index 基于7个维度加权合成:
      股价动量、股价强度、股价广度、看跌看涨期权、
      市场波动率、避险需求、垃圾债需求

    返回: (score, date_str, source)
      score: 0-100 的恐惧贪婪指数值
      date_str: 数据日期 (YYYY-MM-DD)
      source: 数据来源标识 ("CNN" 或 "")
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        fg = data.get("fear_and_greed", {})
        score = fg.get("score")
        if score is not None:
            # 从 timestamp 提取日期
            ts = fg.get("timestamp", "")
            date_str = ""
            if ts:
                try:
                    from datetime import timezone as _tz
                    dt_obj = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    date_str = dt_obj.strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(ts)[:10]
            return round(float(score), 1), date_str or _now_iso()[:10], "CNN"
    except Exception as e:
        logger.warning("CNN Fear & Greed Index 获取失败", extra={"error": str(e)})
    return None, None, ""


def _fetch_cnn_fear_greed_history(days: int = 90) -> list[dict[str, Any]]:
    """
    从 CNN 官方 API 获取 Fear & Greed Index 历史数据。

    返回最近 days 天内的数据点列表。
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        historical = data.get("fear_and_greed_historical", {})
        raw_data = historical.get("data", [])
        if not raw_data:
            return []

        from datetime import timedelta, timezone as _tz
        cutoff = (datetime.now(_tz.utc) - timedelta(days=days)).timestamp() * 1000

        result: list[dict[str, Any]] = []
        for point in raw_data:
            ts_ms = point.get("x", 0)
            if ts_ms < cutoff:
                continue
            val = point.get("y")
            if val is None:
                continue
            # 将毫秒时间戳转为日期字符串
            try:
                dt_obj = datetime.fromtimestamp(ts_ms / 1000, tz=_tz.utc)
                date_str = dt_obj.strftime("%Y-%m-%d")
            except Exception:
                continue
            result.append({"date": date_str, "value": round(float(val), 1)})

        return result
    except Exception as e:
        logger.warning("CNN Fear & Greed Index 历史数据获取失败", extra={"error": str(e)})
        return []


def _fear_greed_sentiment(score: int | None) -> tuple[str, str]:
    """
    根据恐惧贪婪指数分数返回 (整体情绪, 操作建议)。
    """
    if score is None:
        return "中性偏多", "维持仓位并跟踪增量信息"
    if score >= 80:
        return "极度贪婪", "市场可能过热，注意回调风险"
    if score >= 65:
        return "贪婪", "市场情绪偏乐观，可顺势但控制仓位"
    if score >= 45:
        return "中性偏多", "维持仓位并跟踪增量信息"
    if score >= 30:
        return "恐慌", "市场存在恐慌，可关注超跌反弹机会"
    return "极度恐慌", "市场极度恐慌，历史上往往是中长期买入良机"


def _fetch_ivix_from_tushare() -> tuple[float | None, str | None]:
    """从 Tushare 获取50ETF数据，计算历史波动率作为 iVIX 替代

    使用 fund_daily 接口获取上证50ETF(510050.SH)最近30个交易日的日线数据，
    计算对数收益率的年化波动率，作为 iVIX 的近似替代。
    该接口积分要求低（120积分即可），历史波动率与隐含波动率趋势高度相关。
    """
    try:
        from infra.tushare_client import get_pro_api
        pro = get_pro_api()
        if pro is None:
            return None, None

        import numpy as np
        from datetime import timedelta

        # 获取50ETF最近60个自然日的日线数据（约30个交易日）
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

        df = pro.fund_daily(ts_code='510050.SH', start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return None, None

        # 按日期排序
        df = df.sort_values('trade_date')

        # 计算对数收益率
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        df = df.dropna(subset=['log_ret'])

        if len(df) < 10:
            return None, None

        # 取最近20个交易日的波动率
        recent = df.tail(20)
        daily_vol = recent['log_ret'].std()
        # 年化波动率，转为百分比形式
        annual_vol = daily_vol * np.sqrt(252) * 100

        latest_date = str(df.iloc[-1]['trade_date'])
        date_str = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:8]}"

        return round(annual_vol, 2), date_str
    except Exception as e:
        logger.warning("Tushare iVIX 计算失败", extra={"error": str(e)})
        return None, None


def _fetch_ivix_history_from_tushare(days: int = 90) -> list[dict[str, Any]]:
    """从 Tushare 获取50ETF数据，计算滚动历史波动率作为 iVIX 历史替代

    使用 fund_daily 接口获取上证50ETF(510050.SH)日线数据，
    计算滚动20日年化波动率，作为 iVIX 历史数据的替代。
    """
    try:
        from infra.tushare_client import get_pro_api
        pro = get_pro_api()
        if pro is None:
            return []

        import numpy as np
        from datetime import timedelta

        # 需要多取一些天数用于计算滚动波动率
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days + 60)).strftime("%Y%m%d")

        df = pro.fund_daily(ts_code='510050.SH', start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return []

        df = df.sort_values('trade_date')
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))

        # 计算20日滚动年化波动率
        df['vol_20d'] = df['log_ret'].rolling(window=20).std() * np.sqrt(252) * 100
        df = df.dropna(subset=['vol_20d'])

        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        data: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            trade_date = str(row['trade_date'])
            date_str = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            if date_str < cutoff:
                continue
            data.append({"date": date_str, "value": round(float(row['vol_20d']), 2)})

        return data
    except Exception as e:
        logger.warning("Tushare iVIX 历史数据获取失败", extra={"error": str(e)})
        return []


def _fetch_ivix() -> tuple[float | None, str | None, str]:
    """获取中国波指（iVIX）- 多级降级策略

    第一级：akshare QVix 指数（基于 iVIX 算法复现，误差<0.5%）
    第二级：Tushare 50ETF 历史波动率（作为 iVIX 替代）
    第三级：返回 None

    Returns:
        (value, date, source) 三元组，source 标识实际数据来源
    """
    # 第一级：akshare QVix
    try:
        import akshare as ak
        df = ak.index_option_50etf_qvix()
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            for col in df.columns:
                if '波动' in str(col) or 'qvix' in str(col).lower() or 'ivix' in str(col).lower():
                    val = latest[col]
                    if val is not None and str(val) != 'nan':
                        date_str = str(latest.get(df.columns[0], ''))[:10]
                        logger.info("iVIX 数据来源: akshare QVix")
                        return float(val), date_str, "akshare"
    except Exception as e:
        logger.warning("iVIX 第一级（akshare QVix）获取失败", extra={"error": str(e)})

    # 第二级：Tushare 50ETF 历史波动率
    result = _fetch_ivix_from_tushare()
    if result[0] is not None:
        logger.info("iVIX 数据来源: Tushare 50ETF 历史波动率")
        return result[0], result[1], "tushare"

    # 第三级：返回 None
    logger.warning("iVIX 所有数据源均不可用，指标值设为 None")
    return None, None, ""


def _fetch_ivix_history(days: int = 90) -> list[dict[str, Any]]:
    """获取中国波指（iVIX）历史数据 - 多级降级策略

    第一级：akshare QVix 指数历史数据
    第二级：Tushare 50ETF 滚动历史波动率
    第三级：返回空列表
    """
    # 第一级：akshare QVix
    try:
        import akshare as ak
        df = ak.index_option_50etf_qvix()
        if df is not None and not df.empty:
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # 查找包含波动率的列
            value_col = None
            for col in df.columns:
                if '波动' in str(col) or 'qvix' in str(col).lower() or 'ivix' in str(col).lower():
                    value_col = col
                    break
            if value_col is not None:
                # 日期列默认为第一列
                date_col = df.columns[0]

                data: list[dict[str, Any]] = []
                for _, row in df.iterrows():
                    date_str = str(row.get(date_col, ''))[:10]
                    if date_str < cutoff:
                        continue
                    val = row.get(value_col)
                    if val is None or str(val) == 'nan':
                        continue
                    try:
                        data.append({"date": date_str, "value": float(val)})
                    except (ValueError, TypeError):
                        continue

                # 如果成功获取到数据，直接返回
                if data:
                    logger.info("iVIX 历史数据来源: akshare QVix")
                    return data
    except Exception as e:
        logger.warning("iVIX 历史数据第一级（akshare QVix）获取失败", extra={"error": str(e)})

    # 第二级：Tushare 50ETF 滚动历史波动率
    history = _fetch_ivix_history_from_tushare(days)
    if history:
        logger.info("iVIX 历史数据来源: Tushare 50ETF 历史波动率")
        return history

    # 第三级：返回空列表
    logger.warning("iVIX 历史数据所有数据源均不可用")
    return []


def get_macro_data() -> dict[str, Any]:
    """
    获取宏观指标数据，返回 9 个标准化指标:
      CPI, PMI, LPR (来自 trade_macro_indicator 宽表)
      FearGreed (基于 VIX 计算)
      VIX, iVIX, OVX, GVZ, US10Y (来自 FRED/akshare)
    """
    indicators: list[dict[str, Any]] = []
    today_str = _now_iso()[:10]

    # ============================================================
    # 第1步: 从 trade_macro_indicator 宽表读取中国指标 (CPI/PMI/LPR)
    # ============================================================
    db_latest_date = ""
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            # 取最近3行，对每个指标取最新的非 None 值
            rows = query_dict(
                conn,
                "SELECT indicator_date, cpi_yoy, ppi_yoy, pmi, m2_yoy, shrzgm, lpr_1y, lpr_5y "
                "FROM trade_macro_indicator ORDER BY indicator_date DESC LIMIT 3",
            )
            # 从最新行往前查找每个指标的非 None 值
            cpi_val, pmi_val, lpr_val = None, None, None
            cpi_date, pmi_date, lpr_date = "", "", ""
            for r in rows:
                if cpi_val is None and r.get("cpi_yoy") is not None:
                    try:
                        cpi_val = float(r["cpi_yoy"])
                        cpi_date = str(r.get("indicator_date", ""))[:10]
                    except (ValueError, TypeError):
                        pass
                if pmi_val is None and r.get("pmi") is not None:
                    try:
                        pmi_val = float(r["pmi"])
                        pmi_date = str(r.get("indicator_date", ""))[:10]
                    except (ValueError, TypeError):
                        pass
                if lpr_val is None and r.get("lpr_1y") is not None:
                    try:
                        lpr_val = float(r["lpr_1y"])
                        lpr_date = str(r.get("indicator_date", ""))[:10]
                    except (ValueError, TypeError):
                        pass
            db_latest_date = str(rows[0].get("indicator_date", ""))[:10] if rows else ""

            # CPI
            if cpi_val is not None:
                indicators.append({
                    "indicator": "CPI",
                    "value": cpi_val,
                    "date": cpi_date,
                    "name": "CPI（居民消费价格指数）",
                    "source": "akshare",
                })

            # PMI
            if pmi_val is not None:
                indicators.append({
                    "indicator": "PMI",
                    "value": pmi_val,
                    "date": pmi_date,
                    "name": "PMI（采购经理指数）",
                    "source": "akshare",
                })

            # LPR（1年期）
            if lpr_val is not None:
                indicators.append({
                    "indicator": "LPR",
                    "value": lpr_val,
                    "date": lpr_date,
                    "name": "LPR（贷款市场报价利率）",
                    "source": "akshare",
                })

            logger.info("宏观指标从数据库读取成功", extra={
                "indicator_count": len(indicators),
                "latest_date": db_latest_date,
            })
        finally:
            conn.close()
    except Exception as e:
        logger.warning("宏观指标数据库查询失败，将继续获取 FRED 指标", extra={
            "error": str(e),
            "error_type": type(e).__name__,
        })

    # ============================================================
    # 第2步: 从 FRED 获取波动率指标 (VIX/OVX/GVZ)
    # ============================================================
    vix_value = None
    vix_date = None

    # VIX
    val, dt = _fred_latest("VIXCLS")
    if val is not None:
        vix_value = val
        vix_date = dt
        indicators.append({
            "indicator": "VIX",
            "value": round(val, 2),
            "date": dt or today_str,
            "name": "VIX（CBOE波动率指数）",
            "source": "FRED",
        })
    else:
        indicators.append({
            "indicator": "VIX",
            "value": None,
            "date": today_str,
            "name": "VIX（CBOE波动率指数）",
            "source": "FRED",
        })
        logger.warning("VIX 数据获取失败，指标值设为 None")

    # iVIX（中国波动率指数）- 多级降级策略
    ivix_val, ivix_date, ivix_source = _fetch_ivix()
    indicators.append({
        "indicator": "iVIX",
        "value": round(ivix_val, 2) if ivix_val is not None else None,
        "date": ivix_date or today_str,
        "name": "iVIX（中国波动率指数）",
        "source": ivix_source if ivix_source else "unavailable",
    })

    # OVX
    val, dt = _fred_latest("OVXCLS")
    if val is not None:
        indicators.append({
            "indicator": "OVX",
            "value": round(val, 2),
            "date": dt or today_str,
            "name": "OVX（原油波动率指数）",
            "source": "FRED",
        })
    else:
        indicators.append({
            "indicator": "OVX",
            "value": None,
            "date": today_str,
            "name": "OVX（原油波动率指数）",
            "source": "FRED",
        })
        logger.warning("OVX 数据获取失败，指标值设为 None")

    # GVZ
    val, dt = _fred_latest("GVZCLS")
    if val is not None:
        indicators.append({
            "indicator": "GVZ",
            "value": round(val, 2),
            "date": dt or today_str,
            "name": "GVZ（黄金波动率指数）",
            "source": "FRED",
        })
    else:
        indicators.append({
            "indicator": "GVZ",
            "value": None,
            "date": today_str,
            "name": "GVZ（黄金波动率指数）",
            "source": "FRED",
        })
        logger.warning("GVZ 数据获取失败，指标值设为 None")

    # ============================================================
    # 第3步: 从 FRED 获取美国10年期国债收益率 (US10Y)
    # ============================================================
    val, dt = _fred_latest("DGS10")
    if val is not None:
        indicators.append({
            "indicator": "US10Y",
            "value": round(val, 3),
            "date": dt or today_str,
            "name": "美国10年期国债收益率",
            "source": "FRED",
        })
    else:
        indicators.append({
            "indicator": "US10Y",
            "value": None,
            "date": today_str,
            "name": "美国10年期国债收益率",
            "source": "FRED",
        })
        logger.warning("US10Y 数据获取失败，指标值设为 None")

    # ============================================================
    # 第4步: 获取恐惧贪婪指数 (FearGreed)
    # 优先使用 CNN 官方数据，降级使用 VIX 计算
    # ============================================================
    cnn_score, cnn_date, cnn_source = _fetch_cnn_fear_greed()
    if cnn_score is not None:
        # CNN 数据可用
        fear_greed_score = cnn_score
        fear_greed_date = cnn_date
        fear_greed_source = cnn_source
    else:
        # 降级: 基于 VIX 计算
        fear_greed_score = _compute_fear_greed(vix_value)
        fear_greed_date = vix_date or today_str
        fear_greed_source = "calculated"
        logger.info("FearGreed 降级使用 VIX 计算值", extra={"score": fear_greed_score})

    # FearGreed 插入到 indicators 列表中 LPR 之后、VIX 之前的位置
    lpr_idx = next((i for i, ind in enumerate(indicators) if ind["indicator"] == "LPR"), -1)
    fear_greed_item = {
        "indicator": "FearGreed",
        "value": fear_greed_score,
        "date": fear_greed_date,
        "name": "恐惧贪婪指数",
        "source": fear_greed_source,
    }
    if lpr_idx >= 0:
        indicators.insert(lpr_idx + 1, fear_greed_item)
    else:
        indicators.insert(0, fear_greed_item)

    # ============================================================
    # 第5步: 更新 composite 对象
    # ============================================================
    overall_sentiment, action_suggestion = _fear_greed_sentiment(fear_greed_score)
    composite = {
        "composite_fear_greed_index": fear_greed_score,
        "overall_sentiment": overall_sentiment,
        "action_suggestion": action_suggestion,
        "timestamp": _now_iso(),
    }

    logger.info("宏观指标汇总完成", extra={
        "indicator_count": len(indicators),
        "fear_greed_score": fear_greed_score,
        "overall_sentiment": overall_sentiment,
    })

    return {
        "indicators": indicators,
        "composite": composite,
    }


#
#  MySQL 双写：运行记录
#

def write_run_to_mysql(run: dict[str, Any]) -> None:
    """将运行记录同步写入 MySQL（非阻塞，失败仅记录日志）"""
    try:
        import json as _json
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            trigger_type = str(run.get("trigger") or "manual").strip()
            use_llm = 1 if run.get("use_llm") else 0
            days = int(run.get("days") or 3)
            total_events = int(run.get("total_events") or 0)
            status = str(run.get("status") or "running").strip()

            execute(conn, """
                INSERT INTO sentiment_run
                    (run_id, trigger_type, stock_codes_json, stock_names_json,
                     days, use_llm, status, total_events,
                     created_at, started_at, finished_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    total_events = VALUES(total_events),
                    finished_at = VALUES(finished_at),
                    error_message = VALUES(error_message)
            """, (
                str(run.get("run_id", "")),
                trigger_type,
                _json.dumps(run.get("stock_codes", []), ensure_ascii=False),
                _json.dumps(run.get("stock_names", []), ensure_ascii=False),
                days,
                use_llm,
                status,
                total_events,
                str(run.get("created_at") or "")[:19],
                str(run.get("started_at") or "")[:19],
                str(run.get("finished_at") or "")[:19] or None,
                str(run.get("error_message") or "")[:500] or None,
            ))
            logger.debug("运行记录 MySQL 写入成功", extra={"run_id": run.get("run_id")})
        finally:
            conn.close()
    except Exception as e:
        logger.warning("运行记录 MySQL 写入失败（不影响 JSON 存储）", extra={
            "run_id": run.get("run_id"),
            "error": str(e),
            "error_type": type(e).__name__,
        })


#
#  MySQL 双写：事件
#

def write_event_to_mysql(evt: dict[str, Any]) -> None:
    """将事件记录同步写入 MySQL（非阻塞，失败仅记录日志）"""
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            event_type_map = {
                "利好": "positive",
                "利空": "negative",
                "中性": "neutral",
                "政策": "policy",
            }
            event_type = event_type_map.get(str(evt.get("event_type") or ""), "neutral")
            source_title = str(evt.get("source_title") or "")[:255]
            signal_reason = str(evt.get("signal_reason") or "")[:255]
            impact = str(evt.get("impact") or "")[:255]
            # 将 0-1 的 confidence 转为 1-5 的整数分
            confidence_float = float(evt.get("confidence") or 0.5)
            confidence_int = max(1, min(5, int(round(confidence_float * 5))))

            execute(conn, """
                INSERT INTO sentiment_event
                    (run_id, stock_code, stock_name, source_type, source_title,
                     source_url, published_at, event_type, event_category,
                     signal_action, signal_reason, impact, confidence, urgency,
                     sentiment_score, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                str(evt.get("run_id", "")),
                str(evt.get("stock_code", "")),
                str(evt.get("stock_name", ""))[:100],
                str(evt.get("source_type", "news")),
                source_title,
                str(evt.get("source_url") or "")[:500] or None,
                str(evt.get("published_at") or "")[:19] or None,
                event_type,
                str(evt.get("event_category", "")),
                str(evt.get("signal", "观察")),
                signal_reason,
                impact,
                confidence_int,
                str(evt.get("urgency", "低")),
                confidence_int,
            ))
            logger.debug("事件 MySQL 写入成功", extra={
                "run_id": evt.get("run_id"),
                "stock_code": evt.get("stock_code"),
            })
        finally:
            conn.close()
    except Exception as e:
        logger.warning("事件 MySQL 写入失败（不影响 JSON 存储）", extra={
            "run_id": evt.get("run_id"),
            "stock_code": evt.get("stock_code"),
            "error": str(e),
            "error_type": type(e).__name__,
        })


#
#  MySQL 双写：调度配置
#

def save_schedule_to_mysql(cfg: dict[str, Any]) -> None:
    """将调度配置同步写入 MySQL（非阻塞，失败仅记录日志）"""
    try:
        enabled = 1 if cfg.get("enabled") else 0
        cron = str(cfg.get("cron") or "10 15 * * 1-5")
        timezone = str(cfg.get("timezone") or "Asia/Shanghai")
        frequency = str(cfg.get("frequency") or "daily")

        # 根据 frequency 映射 schedule_type
        schedule_type_map = {
            "1h": "market_open",
            "2h": "market_open",
            "4h": "market_open",
            "daily": "daily",
            "hourly": "market_open",
            "every_2_hours": "market_open",
            "every_4_hours": "market_open",
            "custom": "custom",
        }
        schedule_type = schedule_type_map.get(frequency, "custom")

        cfg_mysql = load_mysql_config()
        conn = connect(cfg_mysql)
        try:
            execute(conn, """
                UPDATE sentiment_schedule
                SET enabled = %s,
                    cron_expression = %s,
                    timezone = %s,
                    frequency = %s,
                    schedule_type = %s,
                    updated_at = NOW()
                WHERE id = 1
            """, (enabled, cron, timezone, frequency, schedule_type))
            logger.debug("调度配置 MySQL 更新成功")
        finally:
            conn.close()
    except Exception as e:
        logger.warning("调度配置 MySQL 写入失败（不影响 JSON 存储）", extra={
            "error": str(e),
            "error_type": type(e).__name__,
        })
