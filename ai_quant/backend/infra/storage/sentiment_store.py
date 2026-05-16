from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.db import connect, load_mysql_config, query_dict
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

def get_macro_data() -> dict[str, Any]:
    indicators: list[dict[str, Any]] = []
    composite = {
        "composite_fear_greed_index": 52,
        "overall_sentiment": "中性偏多",
        "action_suggestion": "维持仓位并跟踪增量信息",
        "timestamp": _now_iso(),
    }
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT indicator_date, indicator_name, indicator_value, source "
                "FROM trade_macro_indicator "
                "WHERE indicator_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY) "
                "ORDER BY indicator_date DESC, indicator_name",
            )
            seen: set[str] = set()
            for r in rows or []:
                if not isinstance(r, dict):
                    continue
                name = str(r.get("indicator_name") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                val = r.get("indicator_value")
                try:
                    val = float(val) if val is not None else None
                except Exception:
                    val = None
                indicators.append({
                    "indicator": name,
                    "value": val,
                    "date": str(r.get("indicator_date") or "")[:10],
                    "name": name,
                    "source": str(r.get("source") or "").strip() or None,
                })
            logger.info("宏观指标从数据库读取成功", extra={
                "indicator_count": len(indicators),
            })
        finally:
            conn.close()
    except Exception as e:
        logger.warning("宏观指标数据库查询失败，使用默认数据", extra={
            "error": str(e),
            "error_type": type(e).__name__,
        })

    if not indicators:
        logger.info("宏观指标无数据，使用硬编码默认值")
        indicators = [
            {"indicator": "CN_CPI_YOY", "value": 0.3, "date": _now_iso()[:10], "name": "中国 CPI 同比", "source": None},
            {"indicator": "US10Y", "value": 0.043, "date": _now_iso()[:10], "name": "美国10Y国债", "source": None},
        ]

    return {
        "indicators": indicators,
        "composite": composite,
    }
