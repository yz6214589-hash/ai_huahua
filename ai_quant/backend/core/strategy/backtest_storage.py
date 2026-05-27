# -*- coding: utf-8 -*-
"""
回测存储模块
将回测记录和净值日志持久化到 MySQL 数据库
支持保存、查询、删除和对比回测结果
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from core.db import connect, execute, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("backtest_storage")


# 建表 SQL
_CREATE_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_records (
    backtest_id VARCHAR(64) PRIMARY KEY,
    strategy_id VARCHAR(128) NOT NULL,
    stock_code VARCHAR(32) NOT NULL,
    start_date VARCHAR(32) NOT NULL,
    end_date VARCHAR(32) NOT NULL,
    initial_cash DOUBLE NOT NULL DEFAULT 100000.0,
    commission_buy DOUBLE NOT NULL DEFAULT 0.0003,
    commission_sell DOUBLE NOT NULL DEFAULT 0.0013,
    slippage_pct DOUBLE NOT NULL DEFAULT 0.0,
    slippage_fixed DOUBLE NOT NULL DEFAULT 0.0,
    min_commission DOUBLE NOT NULL DEFAULT 5.0,
    benchmark_code VARCHAR(32) DEFAULT NULL,
    params_json TEXT,
    metrics_json MEDIUMTEXT,
    trades_json MEDIUMTEXT,
    benchmark_nav_json MEDIUMTEXT,
    drawdown_log_json MEDIUMTEXT,
    monthly_returns_json MEDIUMTEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_stock_code (stock_code),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

_CREATE_NAV_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_nav_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    backtest_id VARCHAR(64) NOT NULL,
    log_date VARCHAR(32) NOT NULL,
    nav DOUBLE NOT NULL,
    INDEX idx_backtest_id (backtest_id),
    FOREIGN KEY (backtest_id) REFERENCES backtest_records(backtest_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def ensure_backtest_tables() -> None:
    """
    自动创建回测相关的数据库表
    如果表已存在则不会重复创建
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception as e:
        logger.error("建表失败: 数据库连接异常", extra={"error": str(e)})
        return
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_RECORDS_TABLE)
            cur.execute(_CREATE_NAV_LOG_TABLE)
    except Exception as e:
        logger.error("建表失败", extra={"error": str(e)})
    finally:
        conn.close()


def save_backtest(record: dict) -> str:
    """
    保存回测记录到数据库

    Args:
        record: 回测记录字典，包含以下字段：
            - strategy_id: 策略ID
            - stock_code: 股票代码
            - start_date / end_date: 起止日期
            - initial_cash: 初始资金
            - params: 策略参数
            - metrics: 指标字典
            - trades: 交易列表
            - nav_log: 净值日志
            - benchmark_nav_log: 基准净值日志
            - drawdown_log: 回撤序列
            - monthly_returns: 月度收益
            - commission_buy, commission_sell, slippage_pct, slippage_fixed, min_commission
            - benchmark_code: 基准代码

    Returns:
        回测ID
    """
    backtest_id = record.get("backtest_id") or str(uuid.uuid4())[:12]

    # 确保 JSON 序列化
    def _json_dump(obj: Any) -> str:
        if obj is None:
            return "[]"
        return json.dumps(obj, ensure_ascii=False, default=str)

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception as e:
        logger.error("保存回测失败: 数据库连接异常", extra={"error": str(e)})
        return backtest_id
    try:
        # 插入主记录
        execute(
            conn,
            """
            INSERT INTO backtest_records
                (backtest_id, strategy_id, stock_code, start_date, end_date,
                 initial_cash, commission_buy, commission_sell, slippage_pct,
                 slippage_fixed, min_commission, benchmark_code,
                 params_json, metrics_json, trades_json, benchmark_nav_json,
                 drawdown_log_json, monthly_returns_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                backtest_id,
                record.get("strategy_id", ""),
                record.get("stock_code", ""),
                record.get("start_date", ""),
                record.get("end_date", ""),
                float(record.get("initial_cash", 100000)),
                float(record.get("commission_buy", 0.0003)),
                float(record.get("commission_sell", 0.0013)),
                float(record.get("slippage_pct", 0.0)),
                float(record.get("slippage_fixed", 0.0)),
                float(record.get("min_commission", 5.0)),
                record.get("benchmark_code"),
                _json_dump(record.get("params", {})),
                _json_dump(record.get("metrics", {})),
                _json_dump(record.get("trades", [])),
                _json_dump(record.get("benchmark_nav_log", [])),
                _json_dump(record.get("drawdown_log", [])),
                _json_dump(record.get("monthly_returns", [])),
            ),
        )

        # 插入净值日志
        nav_log = record.get("nav_log", [])
        if nav_log:
            nav_rows = [
                (backtest_id, str(r.get("date", "")), float(r.get("nav", 0)))
                for r in nav_log
            ]
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO backtest_nav_log (backtest_id, log_date, nav) VALUES (%s, %s, %s)",
                    nav_rows,
                )
        # 提交事务，确保数据持久化
        conn.commit()
    except Exception as e:
        logger.error("保存回测失败", extra={"backtest_id": backtest_id, "error": str(e)})
    finally:
        conn.close()

    return backtest_id


def get_backtest(backtest_id: str) -> dict | None:
    """
    获取单条回测记录

    Args:
        backtest_id: 回测ID

    Returns:
        回测记录字典，如果不存在返回 None
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return None
    try:
        rows = query_dict(
            conn,
            "SELECT * FROM backtest_records WHERE backtest_id = %s",
            (backtest_id,),
        )
        if not rows:
            return None
        rec = rows[0]
        # 解析 JSON 字段
        for key in ["params_json", "metrics_json", "trades_json", "benchmark_nav_json", "drawdown_log_json", "monthly_returns_json"]:
            raw = rec.get(key)
            if raw and isinstance(raw, str):
                try:
                    rec[key.replace("_json", "")] = json.loads(raw)
                except Exception:
                    rec[key.replace("_json", "")] = []
            else:
                rec[key.replace("_json", "")] = []

        # 加载净值日志
        nav_rows = query_dict(
            conn,
            "SELECT log_date, nav FROM backtest_nav_log WHERE backtest_id = %s ORDER BY log_date",
            (backtest_id,),
        )
        rec["nav_log"] = [{"date": r["log_date"], "nav": float(r["nav"])} for r in nav_rows]

        return rec
    except Exception as e:
        logger.error("获取回测失败", extra={"backtest_id": backtest_id, "error": str(e)})
        return None
    finally:
        conn.close()


def list_backtests(
    strategy_id: str | None = None,
    stock_code: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    分页查询回测记录

    Args:
        strategy_id: 策略ID筛选（可选）
        stock_code: 股票代码筛选（可选）
        page: 页码，从1开始
        page_size: 每页数量

    Returns:
        {"items": [...], "total": N, "page": page, "page_size": page_size}
    """
    conditions = []
    params_list: list[Any] = []
    if strategy_id:
        conditions.append("strategy_id = %s")
        params_list.append(strategy_id)
    if stock_code:
        conditions.append("stock_code = %s")
        params_list.append(stock_code)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    try:
        # 总数
        count_rows = query_dict(conn, f"SELECT COUNT(*) as cnt FROM backtest_records{where_clause}", tuple(params_list))
        total = int(count_rows[0]["cnt"]) if count_rows else 0

        # 分页数据
        offset = (page - 1) * page_size
        rows = query_dict(
            conn,
            f"SELECT backtest_id, strategy_id, stock_code, start_date, end_date, initial_cash, benchmark_code, created_at FROM backtest_records{where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params_list + [page_size, offset]),
        )

        items = []
        for r in rows:
            item = dict(r)
            # 日期格式化
            if isinstance(item.get("created_at"), datetime):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return {"items": items, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error("查询回测列表失败", extra={"error": str(e)})
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()


def delete_backtest(backtest_id: str) -> bool:
    """
    删除回测记录（同时删除关联的净值日志）

    Args:
        backtest_id: 回测ID

    Returns:
        是否删除成功
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return False
    try:
        # nav_log 通过外键 ON DELETE CASCADE 自动删除
        affected = execute(conn, "DELETE FROM backtest_records WHERE backtest_id = %s", (backtest_id,))
        conn.commit()
        return affected > 0
    except Exception as e:
        logger.error("删除回测失败", extra={"backtest_id": backtest_id, "error": str(e)})
        return False
    finally:
        conn.close()


def compare_backtests(backtest_ids: list[str]) -> list[dict]:
    """
    对比多条回测记录

    Args:
        backtest_ids: 回测ID列表

    Returns:
        对比结果列表，每项包含回测ID、基本信息和指标
    """
    if not backtest_ids:
        return []
    results = []
    for bid in backtest_ids:
        rec = get_backtest(bid)
        if rec is None:
            results.append({"backtest_id": bid, "error": "not_found"})
            continue
        # 只保留对比所需的关键字段
        metrics = rec.get("metrics", {})
        results.append({
            "backtest_id": bid,
            "strategy_id": rec.get("strategy_id", ""),
            "stock_code": rec.get("stock_code", ""),
            "start_date": rec.get("start_date", ""),
            "end_date": rec.get("end_date", ""),
            "initial_cash": rec.get("initial_cash", 0),
            "benchmark_code": rec.get("benchmark_code"),
            "metrics": metrics,
        })
    return results
