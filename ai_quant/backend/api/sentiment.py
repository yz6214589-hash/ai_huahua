"""
舆情监控 API 路由

提供舆情监控相关接口，包括：
- 定时任务调度配置
- 舆情分析任务触发
- 舆情事件、新闻查询
- 宏观舆情数据查询
- 自定义股票监控列表管理
- 通知设置
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from core.data import get_watchlist
from core.db import MySQLConfig, connect, execute, executemany, query_dict
from core.jobs.common import safe_float, to_ymd

logger = logging.getLogger("sentiment_api")

router = APIRouter()

# 时区
_tz = timezone(timedelta(hours=8))

# LLM API 密钥
DASHSCOPE_API_KEY = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()

# ---------- 工具函数 ----------

def load_mysql_config() -> MySQLConfig:
    """
    从环境变量加载 MySQL 连接配置。

    环境变量优先级：
    1. WUCAI_SQL_* 系列的四个变量
    2. 回退到 AI_QUANT_SQL_* 系列
    3. 默认值 localhost:3306/quant_trade

    Returns:
        MySQLConfig: 数据库连接配置对象
    """
    from core.db import load_mysql_config as _load
    return _load()


def _now_iso() -> str:
    """返回北京时间 ISO 格式时间字符串"""
    return datetime.now(_tz).isoformat(timespec="seconds")


def _now_ymd() -> str:
    """返回北京时间 YYYYMMDD 格式日期字符串"""
    return datetime.now(_tz).strftime("%Y%m%d")


def _generate_run_id() -> str:
    """生成一个16位十六进制运行ID"""
    return os.urandom(8).hex()


class SentimentStore:
    """
    舆情监控本地存储管理器

    将调度配置持久化到本地 JSON 文件。
    兼容之前的文件存储格式，并支持同步到 MySQL。
    """

    def __init__(self) -> None:
        """
        初始化存储目录，从环境变量或默认路径获取。
        优先使用 AI_QUANT_CHARLES_JOB_STORE_DIR 环境变量指定的目录。
        """
        base = str(os.getenv("AI_QUANT_CHARLES_JOB_STORE_DIR", "")).strip()
        if not base:
            base = os.path.join(os.path.dirname(__file__), "..", ".ai_quant")
        self._dir = os.path.join(base, "sentiment")
        try:
            os.makedirs(self._dir, exist_ok=True)
        except PermissionError:
            self._dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "..", ".ai_quant", "sentiment"
            )
            os.makedirs(self._dir, exist_ok=True)

    def _path(self, name: str) -> str:
        return os.path.join(self._dir, name)

    def get_schedule(self) -> dict[str, Any]:
        """
        获取调度配置。

        Returns:
            dict: 包含 enabled/cron/timezone/frequency/market_time/fixed_time 的字典
        """
        default = {
            "enabled": True,
            "cron": "0 10 15 * * ?",
            "timezone": "Asia/Shanghai",
            "frequency": "daily",
            "market_time": "14:00",
            "fixed_time": "15:10",
        }
        p = self._path("schedule.json")
        if not os.path.exists(p):
            return default
        try:
            with open(p, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                return {**default, **stored}
        except Exception:
            pass
        return default

    def save_schedule(self, data: dict[str, Any]) -> None:
        """
        保存调度配置到本地文件。

        Args:
            data: 调度配置字典
        """
        p = self._path("schedule.json")
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("保存调度配置失败", extra={"error": str(e)})

    def save_schedule_to_mysql(self, data: dict[str, Any]) -> None:
        """
        同步调度配置到 MySQL。

        更新 sentiment_schedule 表中 id=1 的配置记录。
        此操作非阻塞，失败不影响主流程。

        Args:
            data: 调度配置字典
        """
        try:
            cfg = load_mysql_config()
            conn = connect(cfg)
            try:
                execute(
                    conn,
                    """INSERT INTO sentiment_schedule (id, name, enabled, schedule_type, cron_expression, timezone, frequency, use_watchlist)
                       VALUES (1, %s, %s, 'market_open', %s, %s, %s, 1)
                       ON DUPLICATE KEY UPDATE enabled=VALUES(enabled), cron_expression=VALUES(cron_expression), frequency=VALUES(frequency)""",
                    (
                        "舆情监控",
                        1 if data.get("enabled") else 0,
                        data.get("cron", "0 10 15 * * ?"),
                        data.get("timezone", "Asia/Shanghai"),
                        data.get("frequency", "daily"),
                    ),
                )
            finally:
                conn.close()
        except Exception as e:
            logger.warning("保存调度配置到MySQL失败", extra={"error": str(e)})

    def get_notify_config(self) -> dict[str, Any]:
        """
        获取通知配置。

        Returns:
            dict: 包含 enabled/threshold 的字典
        """
        default = {"enabled": True, "threshold": 0.3}
        p = self._path("notify.json")
        if not os.path.exists(p):
            return default
        try:
            with open(p, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                return {**default, **stored}
        except Exception:
            pass
        return default

    def save_notify_config(self, data: dict[str, Any]) -> None:
        """
        保存通知配置到本地文件。

        Args:
            data: 通知配置字典
        """
        p = self._path("notify.json")
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning("保存通知配置失败", extra={"error": str(e)})


store = SentimentStore()


# ---------- 路由 ----------

@router.get("/sentiment/schedule")
def sentiment_schedule_get() -> dict[str, Any]:
    """获取舆情监控定时调度配置"""
    return store.get_schedule()


@router.put("/sentiment/schedule")
def sentiment_schedule_put(body: dict[str, Any]) -> dict[str, Any]:
    """
    更新舆情监控定时调度配置。

    支持更新 enabled/cron/timezone/frequency/market_time/fixed_time 字段。
    同时同步到 MySQL（非阻塞）。
    """
    current = store.get_schedule()
    enabled = bool(body.get("enabled", current.get("enabled", True)))
    cron = str(body.get("cron") or current.get("cron", "0 10 15 * * ?")).strip()
    timezone = str(body.get("timezone") or current.get("timezone", "Asia/Shanghai")).strip() or "Asia/Shanghai"
    frequency = str(body.get("frequency") or current.get("frequency", "daily")).strip() or "daily"
    market_time = str(body.get("market_time") or current.get("market_time", "14:00")).strip() or "14:00"
    fixed_time = str(body.get("fixed_time") or current.get("fixed_time", "15:10")).strip() or "15:10"
    updated = {
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
        "frequency": frequency,
        "market_time": market_time,
        "fixed_time": fixed_time,
    }
    store.save_schedule(updated)
    store.save_schedule_to_mysql(updated)
    logger.info("舆情调度配置已更新", extra={
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
        "frequency": frequency,
        "market_time": market_time,
        "fixed_time": fixed_time,
    })
    return store.get_schedule()


@router.post("/sentiment/runs")
def sentiment_run(body: dict[str, Any]) -> dict[str, Any]:
    """
    触发舆情分析任务

    三种触发模式：
    1. 无参数（或空 body）：使用自选股列表+默认配置
    2. 指定 stock_codes：手动分析指定股票
    3. 其他配置参数（days, use_llm 等）可选

    Args:
        body: 请求体，可包含 stock_codes/days/use_llm 等

    Returns:
        {"run_id": str, "status": str, "message": str}

    Raises:
        HTTPException: 参数校验失败时抛出 400
    """
    raw_codes = body.get("stock_codes")
    if raw_codes is not None:
        if not isinstance(raw_codes, list) or len(raw_codes) == 0:
            raise HTTPException(status_code=400, detail="stock_codes 必须是非空列表")
        stock_codes = [str(c).strip().upper() for c in raw_codes if str(c).strip()]
        if not stock_codes:
            raise HTTPException(status_code=400, detail="股票代码列表为空")
    else:
        # 从舆情股票列表读取
        try:
            cfg = load_mysql_config()
            conn = connect(cfg)
            try:
                rows = query_dict(conn, "SELECT stock_code, stock_name FROM sentiment_stock_list")
                stock_codes = [str(r["stock_code"]).strip().upper() for r in (rows or []) if r.get("stock_code")]
                stock_names = [str(r.get("stock_name") or "") for r in (rows or [])]
            finally:
                conn.close()
        except Exception:
            stock_codes = []

    days = max(1, min(30, int(body.get("days", 3) or 3)))
    use_llm = bool(body.get("use_llm", False))
    use_watchlist = bool(body.get("use_watchlist", True))

    if not stock_codes:
        raise HTTPException(status_code=400, detail="股票列表为空，请先添加股票")

    run_id = _generate_run_id()
    now_iso = _now_iso()

    # 记录运行记录到 MySQL
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            execute(
                conn,
                """INSERT INTO sentiment_run
                   (run_id, trigger_type, stock_codes_json, stock_names_json, days, use_llm, status, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    run_id,
                    "manual",
                    json.dumps(stock_codes, ensure_ascii=False),
                    json.dumps(stock_names if stock_names else [], ensure_ascii=False),
                    days,
                    1 if use_llm else 0,
                    "waiting",
                    now_iso,
                ),
            )
        finally:
            conn.close()
    except Exception as e:
        logger.warning("写入运行记录失败", extra={"error": str(e)})

    # 异步启动采集子进程（后台任务），传递必要参数
    script = os.path.join(os.path.dirname(__file__), "..", "core", "jobs", "domains", "sentiment_monitor.py")
    if not os.path.exists(script):
        raise HTTPException(status_code=500, detail=f"采集脚本不存在: {script}")

    args = [
        "python3",
        script,
        "--run_id", run_id,
        "--stock_codes", ",".join(stock_codes),
        "--days", str(days),
        "--mysql_host", str(os.getenv("WUCAI_SQL_HOST", "127.0.0.1")),
        "--mysql_port", str(os.getenv("WUCAI_SQL_PORT", "3306")),
        "--mysql_user", str(os.getenv("WUCAI_SQL_USERNAME", "root")),
        "--mysql_password", str(os.getenv("WUCAI_SQL_PASSWORD", "")),
        "--mysql_db", str(os.getenv("WUCAI_SQL_DB", "quant_trade")),
    ]
    if use_llm:
        args.append("--use_llm")

    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        logger.info("舆情分析任务已启动", extra={"run_id": run_id, "stock_count": len(stock_codes)})
    except Exception as e:
        logger.error("启动舆情分析任务失败", extra={"run_id": run_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"启动任务失败: {e}")

    return {
        "run_id": run_id,
        "status": "pending",
        "message": f"舆情分析任务已启动，涉及 {len(stock_codes)} 只股票",
    }


@router.get("/sentiment/runs")
def sentiment_runs(limit: int = 20) -> dict[str, Any]:
    """
    获取舆情分析运行记录列表。

    Args:
        limit: 返回记录数量上限，默认 20

    Returns:
        {"runs": list[dict]}，包含 run_id/status/total_events/stock_count 等字段
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                """SELECT run_id, trigger_type, stock_codes_json, days, use_llm, status,
                          total_events, total_news, positive_count, negative_count, neutral_count,
                          created_at, started_at, finished_at, error_message
                   FROM sentiment_run ORDER BY created_at DESC LIMIT %s""",
                (int(limit),),
            )
            items = []
            for r in rows or []:
                codes = []
                try:
                    codes = json.loads(str(r.get("stock_codes_json") or "[]"))
                except Exception:
                    pass
                items.append({
                    "run_id": r.get("run_id"),
                    "trigger_type": r.get("trigger_type"),
                    "stock_count": len(codes),
                    "days": r.get("days"),
                    "use_llm": bool(int(r.get("use_llm") or 0) == 1),
                    "status": r.get("status"),
                    "total_events": int(r.get("total_events") or 0),
                    "total_news": int(r.get("total_news") or 0),
                    "positive_count": int(r.get("positive_count") or 0),
                    "negative_count": int(r.get("negative_count") or 0),
                    "neutral_count": int(r.get("neutral_count") or 0),
                    "created_at": str(r.get("created_at") or ""),
                    "started_at": str(r.get("started_at") or ""),
                    "finished_at": str(r.get("finished_at") or ""),
                    "error_message": r.get("error_message"),
                })
            return {"runs": items}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询运行记录失败", extra={"error": str(e)})
        return {"runs": []}


@router.get("/sentiment/events")
def sentiment_events(
    run_id: str | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """
    查询舆情事件列表。

    支持按运行ID、事件类型和数量限制进行过滤。

    Args:
        run_id: 运行ID，不传时查询所有
        event_type: 事件类型过滤，"利好"/"利空"/"政策"
        limit: 返回事件数量上限，默认 200

    Returns:
        {"events": list[dict]}，包含事件详细信息
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            sql = "SELECT * FROM sentiment_event WHERE 1=1"
            params: list[Any] = []
            if run_id:
                sql += " AND run_id = %s"
                params.append(run_id)
            if event_type:
                sql += " AND event_type = %s"
                params.append(event_type)
            sql += " ORDER BY published_at DESC, id DESC LIMIT %s"
            params.append(int(limit))
            rows = query_dict(conn, sql, tuple(params))
            return {"events": rows if rows else []}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询舆情事件失败", extra={"error": str(e)})
        return {"events": []}


@router.get("/sentiment/news")
def sentiment_news(
    run_id: str | None = None,
    stock_code: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """
    查询舆情新闻列表。

    支持按运行ID、股票代码过滤。

    Args:
        run_id: 运行ID，不传时查询所有
        stock_code: 股票代码过滤
        limit: 返回新闻数量上限，默认 200

    Returns:
        {"news": list[dict]}，包含新闻详细信息
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            sql = "SELECT * FROM sentiment_news WHERE 1=1"
            params: list[Any] = []
            if run_id:
                sql += " AND run_id = %s"
                params.append(run_id)
            if stock_code:
                sql += " AND stock_code = %s"
                params.append(stock_code)
            sql += " ORDER BY published_at DESC, id DESC LIMIT %s"
            params.append(int(limit))
            rows = query_dict(conn, sql, tuple(params))
            return {"news": rows if rows else []}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询舆情新闻失败", extra={"error": str(e)})
        return {"news": []}


@router.get("/sentiment/macro")
def sentiment_macro() -> list[dict[str, Any]]:
    """获取宏观舆情数据（占位接口，返回空列表）"""
    return []


@router.get("/sentiment/stock-list")
def get_sentiment_stock_list() -> dict[str, Any]:
    """
    查询舆情监控系统的独立股票列表

    从 sentiment_stock_list 表中读取所有股票，按添加时间倒序排列。

    Returns:
        {"items": list[dict]}，每项包含 stock_code/stock_name/added_at/notes
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT stock_code, stock_name, added_at, notes FROM sentiment_stock_list ORDER BY added_at DESC",
            )
            return {"items": rows if rows else []}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询舆情股票列表失败", extra={"error": str(e)})
        return {"items": []}


@router.delete("/sentiment/stock-list/{stock_code}")
def delete_sentiment_stock(stock_code: str) -> dict[str, Any]:
    """
    从舆情监控股票列表中删除指定股票

    根据股票代码删除 sentiment_stock_list 表中的对应记录。

    Args:
        stock_code: 股票代码，如 "600519.SH"

    Returns:
        {"ok": bool, "message": str}
    """
    code = str(stock_code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            affected = execute(conn, "DELETE FROM sentiment_stock_list WHERE stock_code = %s", (code,))
            if affected > 0:
                logger.info("已从舆情股票列表删除: %s", code)
                return {"ok": True, "message": f"已删除 {code}"}
            else:
                return {"ok": False, "message": f"未找到 {code}"}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("删除舆情股票失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.post("/sentiment/stock-list/sync")
def sync_from_watchlist() -> dict[str, Any]:
    """
    从通用自选库同步股票到舆情监控股票列表。

    同步规则：
    - 仅添加自选库中尚不存在的股票
    - 已存在的股票跳过
    - stock_code 带 @ 前缀表示受保护的记录，以 @ 后的实际代码判断是否已存在

    Returns:
        {"items": list, "added_count": int, "skipped_count": int, "total": int}
    """
    added_count = 0
    skipped_count = 0
    try:
        watchlist_data = get_watchlist()
        watchlist_items = watchlist_data.get("items") if isinstance(watchlist_data, dict) else []
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            existing_rows = query_dict(conn, "SELECT stock_code, stock_name FROM sentiment_stock_list")
            existing_codes = set()
            for r in existing_rows or []:
                code = str(r.get("stock_code", "")).strip()
                if code.startswith("@"):
                    existing_codes.add(code[1:].strip())
                else:
                    existing_codes.add(code)
            for it in watchlist_items if isinstance(watchlist_items, list) else []:
                code = str((it or {}).get("stock_code") or "").strip().upper()
                if not code:
                    skipped_count += 1
                    continue
                name = str((it or {}).get("stock_name") or "").strip()
                if code in existing_codes:
                    skipped_count += 1
                    continue
                try:
                    execute(conn, "INSERT INTO sentiment_stock_list (stock_code, stock_name) VALUES (%s, %s)", (code, name or code))
                    added_count += 1
                except Exception as e:
                    logger.warning("插入舆情股票失败: %s", str(e))
                    skipped_count += 1
            updated_rows = query_dict(conn, "SELECT stock_code, stock_name, added_at, notes FROM sentiment_stock_list ORDER BY added_at DESC")
            return {"items": updated_rows if updated_rows else [], "added_count": added_count, "skipped_count": skipped_count, "total": len(updated_rows or [])}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("从自选库同步舆情股票列表失败", extra={"error": str(e)})
        return {"items": [], "added_count": 0, "skipped_count": 0, "total": 0, "error": str(e)}


@router.get("/sentiment/notify")
def sentiment_notify_get() -> dict[str, Any]:
    """获取舆情通知配置"""
    return store.get_notify_config()


@router.put("/sentiment/notify")
def sentiment_notify_put(body: dict[str, Any]) -> dict[str, Any]:
    """
    更新舆情通知配置

    Args:
        body: 包含 enabled/threshold 等字段

    Returns:
        dict: 更新后的通知配置
    """
    current = store.get_notify_config()
    enabled = bool(body.get("enabled", current.get("enabled", True)))
    threshold = float(body.get("threshold", current.get("threshold", 0.3)))
    updated = {"enabled": enabled, "threshold": threshold}
    store.save_notify_config(updated)
    return store.get_notify_config()


@router.get("/sentiment/history")
def sentiment_history(days: int = 7) -> list[dict[str, Any]]:
    """
    获取历史舆情数据概览。

    以日为维度聚合过去 N 天的舆情事件数量。

    Args:
        days: 回溯天数，默认 7

    Returns:
        list[dict]，每项包含日期和事件数量
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            since = (datetime.now(_tz) - timedelta(days=max(1, days))).isoformat()
            rows = query_dict(
                conn,
                """SELECT DATE(published_at) AS day, COUNT(*) AS cnt
                   FROM sentiment_event
                   WHERE published_at >= %s
                   GROUP BY DATE(published_at)
                   ORDER BY day ASC""",
                (since,),
            )
            return [{"date": str(r["day"]), "count": int(r["cnt"])} for r in (rows or [])]
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询历史舆情数据失败", extra={"error": str(e)})
        return []
