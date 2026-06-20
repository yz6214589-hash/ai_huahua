"""
工作流团队API模块
提供团队工作流运行历史查询、运行详情查看、晨报状态查询等功能
数据存储使用MySQL数据库
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.db import connect, load_mysql_config, query_dict, execute
from infra.storage.logging_service import get_logger

logger = get_logger("workflow_team")

router = APIRouter(prefix="/api/v1/workflow", tags=["workflow"])


# ---------------------------------------------------------------------------
# 建表逻辑（模块加载时自动执行）
# ---------------------------------------------------------------------------

_DDL_TEAM_RUN_SQL = """CREATE TABLE IF NOT EXISTS trade_workflow_team_run (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL COMMENT '运行ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
    capital DECIMAL(15,2) NOT NULL DEFAULT 0.00 COMMENT '资金',
    status VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT '状态: running/completed/failed',
    verdict VARCHAR(255) DEFAULT NULL COMMENT '判决结果',
    verdict_reason TEXT DEFAULT NULL COMMENT '判决理由',
    detail_json JSON DEFAULT NULL COMMENT '运行详情JSON',
    started_at DATETIME DEFAULT NULL COMMENT '开始时间',
    finished_at DATETIME DEFAULT NULL COMMENT '结束时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_run_id (run_id),
    KEY idx_team_run_status (status),
    KEY idx_team_run_stock (stock_code),
    KEY idx_team_run_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='团队工作流运行记录表'"""


def _ensure_table():
    """确保团队工作流运行记录表存在，在模块加载时自动执行"""
    conn = None
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        if conn:
            with conn.cursor() as cur:
                cur.execute(_DDL_TEAM_RUN_SQL)
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


_ensure_table()


def _get_conn():
    """获取数据库连接"""
    cfg = load_mysql_config()
    return connect(cfg)


def _safe_float(v):
    """安全转换为float"""
    if v is None:
        return None
    try:
        f = float(v)
        return f if float("inf") > f > float("-inf") else None
    except (ValueError, TypeError):
        return None


def _safe_int(v):
    """安全转换为int"""
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 团队工作流运行历史
# ---------------------------------------------------------------------------

@router.get("/team/runs")
def get_team_runs(
    limit: int = Query(20, ge=1, le=100, description="返回条数上限"),
    status: Optional[str] = Query(None, description="按状态筛选"),
) -> dict[str, Any]:
    """
    获取团队工作流运行历史列表。

    从 trade_workflow_team_run 表查询团队工作流的运行历史记录。

    Args:
        limit: 返回条数上限
        status: 按状态筛选（running/completed/failed）

    Returns:
        dict: 包含 items（运行历史列表）和 total（总数）
    """
    logger.info("团队工作流运行历史请求", extra={
        "limit": limit,
        "status": status or "all",
    })

    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if status:
            conditions.append("status = %s")
            params.append(status)

        where = " AND ".join(conditions)

        # 查询总数
        count_sql = f"SELECT COUNT(*) as total FROM trade_workflow_team_run WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        # 查询数据
        sql = f"""
            SELECT run_id, stock_code, stock_name, capital, status,
                   verdict, verdict_reason, started_at, finished_at, created_at
            FROM trade_workflow_team_run
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)
        rows = query_dict(conn, sql, tuple(params))

        items = []
        for row in rows:
            started_at = row.get("started_at")
            if started_at and hasattr(started_at, "strftime"):
                started_at = started_at.strftime("%Y-%m-%d %H:%M:%S")

            items.append({
                "id": row.get("run_id", ""),
                "stock_code": row.get("stock_code", ""),
                "started_at": str(started_at) if started_at else "",
                "status": row.get("status", "unknown"),
                "verdict": row.get("verdict") or "",
                "verdict_reason": row.get("verdict_reason") or "",
            })

        logger.info("团队工作流运行历史查询完成", extra={"total": total, "returned": len(items)})

        return {
            "items": items,
            "total": total,
        }
    except Exception as e:
        logger.error("获取团队工作流运行历史失败", extra={"error": str(e)})
        return {"items": [], "total": 0}
    finally:
        conn.close()


@router.get("/team/detail/{run_id}")
def get_team_run_detail(run_id: str) -> dict[str, Any]:
    """
    获取团队工作流运行详情。

    从 trade_workflow_team_run 表查询指定运行的详细信息，
    包括各节点的消息和最终判决。

    Args:
        run_id: 运行ID

    Returns:
        dict: 包含 detail（运行详情）
    """
    logger.info("团队工作流运行详情请求", extra={"run_id": run_id})

    conn = _get_conn()
    try:
        rows = query_dict(
            conn,
            "SELECT * FROM trade_workflow_team_run WHERE run_id = %s",
            (run_id,)
        )

        if not rows:
            raise HTTPException(status_code=404, detail="运行记录不存在")

        row = rows[0]

        # 解析detail_json
        detail_data = {}
        detail_json_raw = row.get("detail_json")
        if detail_json_raw and isinstance(detail_json_raw, str):
            try:
                detail_data = json.loads(detail_json_raw)
            except Exception:
                detail_data = {}
        elif detail_json_raw and isinstance(detail_json_raw, dict):
            detail_data = detail_json_raw

        started_at = row.get("started_at")
        if started_at and hasattr(started_at, "strftime"):
            started_at = started_at.strftime("%Y-%m-%d %H:%M:%S")

        finished_at = row.get("finished_at")
        if finished_at and hasattr(finished_at, "strftime"):
            finished_at = finished_at.strftime("%Y-%m-%d %H:%M:%S")

        detail = {
            "run_id": row.get("run_id", ""),
            "stock_code": row.get("stock_code", ""),
            "capital": _safe_float(row.get("capital")) or 0,
            "nodes": detail_data.get("nodes", []),
            "messages": detail_data.get("messages", []),
            "final_verdict": row.get("verdict") or "",
            "final_reason": row.get("verdict_reason") or "",
            "status": row.get("status", ""),
            "started_at": str(started_at) if started_at else "",
            "finished_at": str(finished_at) if finished_at else "",
        }

        logger.info("团队工作流运行详情查询完成", extra={"run_id": run_id})

        return {
            "detail": detail,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取团队工作流运行详情失败", extra={"error": str(e), "run_id": run_id})
        raise HTTPException(status_code=500, detail=f"获取运行详情失败: {str(e)}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 晨报执行状态
# ---------------------------------------------------------------------------

@router.get("/morning/status/{task_id}")
def get_morning_status(task_id: str) -> dict[str, Any]:
    """
    获取晨报执行状态。

    从 trade_morning_brief 表查询指定晨报任务的执行进度和结果。

    Args:
        task_id: 晨报任务ID（对应 brief_id）

    Returns:
        dict: 包含 stage（阶段）、progress（进度）和 result（结果）
    """
    logger.info("晨报执行状态查询", extra={"task_id": task_id})

    conn = _get_conn()
    try:
        rows = query_dict(
            conn,
            "SELECT * FROM trade_morning_brief WHERE brief_id = %s",
            (task_id,)
        )

        if not rows:
            return {
                "stage": "unknown",
                "progress": 0,
                "result": None,
            }

        row = rows[0]
        status_val = row.get("status", "running")

        # 状态映射
        stage_map = {
            "running": "generating",
            "success": "done",
            "failed": "error",
        }
        stage = stage_map.get(str(status_val), "unknown")

        # 进度映射
        progress_map = {
            "running": 50,
            "success": 100,
            "failed": 100,
        }
        progress = progress_map.get(str(status_val), 0)

        # 如果已完成，构建结果
        result = None
        if status_val == "success":
            report_md = row.get("report_md") or ""
            report_html = row.get("report_html") or ""

            # 查询该简报关联的行业排名
            industry_rows = query_dict(
                conn,
                """SELECT sector_code, sector_name, rank_position, composite_score,
                          phase, strength, recommendation, win_rate_20d
                   FROM trade_morning_industry
                   WHERE brief_id = %s
                   ORDER BY rank_position ASC""",
                (task_id,)
            )

            industries = []
            for ind in industry_rows:
                industries.append({
                    "sector_code": ind.get("sector_code", ""),
                    "sector_name": ind.get("sector_name", ""),
                    "rank": _safe_int(ind.get("rank_position")),
                    "score": _safe_float(ind.get("composite_score")),
                    "phase": ind.get("phase", ""),
                    "strength": ind.get("strength", ""),
                    "recommendation": ind.get("recommendation", ""),
                    "win_rate_20d": _safe_float(ind.get("win_rate_20d")),
                })

            result = {
                "brief_id": task_id,
                "brief_date": str(row.get("brief_date")) if row.get("brief_date") else "",
                "status": "success",
                "report_md": report_md,
                "report_html": report_html,
                "industries": industries,
            }

        finished_at = row.get("finished_at")
        error_message = row.get("error_message")

        return {
            "stage": stage,
            "progress": progress,
            "result": result,
            "finished_at": str(finished_at) if finished_at and hasattr(finished_at, "strftime") else None,
            "error_message": str(error_message) if error_message else None,
        }
    except Exception as e:
        logger.error("查询晨报执行状态失败", extra={"error": str(e), "task_id": task_id})
        return {
            "stage": "unknown",
            "progress": 0,
            "result": None,
        }
    finally:
        conn.close()