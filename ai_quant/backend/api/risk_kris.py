"""
风控看板API模块
提供风控状态查询、审批、审计日志、风险事件、告警管理、风控规则等功能
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from core.db import connect, execute, load_mysql_config, query_dict
from core.risk import approve, audit, status
from core.risk.service import RiskManager, _get_manager, _now_iso
from infra.storage.logging_service import get_logger

logger = get_logger("risk")

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


def _get_conn():
    cfg = load_mysql_config()
    return connect(cfg)


@router.get("/status")
def risk_status() -> dict[str, object]:
    logger.info("风控状态查询", extra={})
    return status()


@router.post("/approve")
def risk_approve(body: dict[str, Any]) -> dict[str, Any]:
    logger.info("风控审批请求", extra={
        "stock_code": body.get("stockCode"),
        "qty": body.get("qty"),
        "side": body.get("side")
    })
    try:
        result = approve(body)
        logger.info("风控审批成功", extra={
            "stock_code": body.get("stockCode"),
            "decision": result.get("decision")
        })
        try:
            conn = _get_conn()
            try:
                event_id = f"evt_{uuid.uuid4().hex[:12]}"
                event_data_json = json.dumps(result, ensure_ascii=False, default=str)
                execute(
                    conn,
                    """INSERT INTO trade_risk_event
                       (event_id, event_type, risk_level, stock_code, stock_name, account_id,
                        description, event_data, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        event_id,
                        "approve",
                        result.get("decision", "APPROVE"),
                        (body.get("order") or {}).get("stock_code", ""),
                        "",
                        "",
                        result.get("reason", ""),
                        event_data_json,
                        "processed",
                    )
                )
                logger.info("风控审批结果已同步至MySQL", extra={"event_id": event_id})
            finally:
                conn.close()
        except Exception as sync_err:
            logger.warning("风控审批结果同步MySQL失败", extra={"error": str(sync_err)})
        return result
    except Exception as exc:
        logger.error("风控审批失败", extra={
            "stock_code": body.get("stockCode"),
            "error": str(exc)
        })
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/audit")
def risk_audit(last_n: int = 200) -> dict[str, Any]:
    logger.info("风控审计查询", extra={
        "last_n": last_n
    })
    return audit(last_n)


# ============================================
# 风险事件管理
# ============================================

@router.get("/events")
def get_risk_events(
    event_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    stock_code: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取风险事件列表"""
    logger.info("开始获取风险事件列表", extra={
        "filters": {"event_type": event_type, "risk_level": risk_level, "status": status},
        "pagination": {"page": page, "page_size": page_size}
    })
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        if risk_level:
            conditions.append("risk_level = %s")
            params.append(risk_level)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)
        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)
        logger.debug("构建查询条件", extra={"params_count": len(params)})
        
        count_sql = f"SELECT COUNT(*) as total FROM trade_risk_event WHERE {where}"
        logger.debug("查询总数")
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0
        logger.debug(f"总数: {total}")

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_risk_event
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        logger.debug(f"查询数据，offset: {offset}, limit: {page_size}")
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))
        logger.info(f"查询完成，返回 {len(rows)} 条记录")

        for row in rows:
            if row.get("event_data") and isinstance(row["event_data"], str):
                try:
                    row["event_data"] = json.loads(row["event_data"])
                except Exception:
                    pass
            for dt_field in ["created_at", "updated_at", "handled_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取风险事件列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取风险事件失败: {str(e)}")
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.post("/events")
def create_risk_event(body: dict[str, Any]) -> dict[str, Any]:
    """创建风险事件"""
    conn = _get_conn()
    try:
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        event_data_json = json.dumps(body.get("event_data", {}), ensure_ascii=False) if body.get("event_data") else None

        execute(
            conn,
            """INSERT INTO trade_risk_event
               (event_id, event_type, risk_level, stock_code, stock_name, position_id, account_id,
                description, event_data, triggered_rule_id, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                event_id,
                body.get("event_type", ""),
                body.get("risk_level", "medium"),
                body.get("stock_code"),
                body.get("stock_name"),
                body.get("position_id"),
                body.get("account_id", ""),
                body.get("description"),
                event_data_json,
                body.get("triggered_rule_id"),
                body.get("status", "pending"),
            )
        )

        return {"success": True, "event_id": event_id, "message": "风险事件创建成功"}
    except Exception as e:
        logger.error("创建风险事件失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建风险事件失败: {str(e)}")
    finally:
        conn.close()

    try:
        mgr = _get_manager()
        audit_entry = {
            "timestamp": _now_iso(),
            "stock_code": body.get("stock_code", ""),
            "direction": "",
            "amount": 0.0,
            "price": 0.0,
            "quantity": 0,
            "decision": body.get("risk_level", "medium"),
            "reason": body.get("description", ""),
            "rule_name": "risk_event",
            "max_position_pct": 0.0,
            "event_id": event_id,
        }
        mgr.audit_log.append(audit_entry)
        from core.risk.service import _write_audit_entry
        _write_audit_entry(audit_entry)
    except Exception as e:
        logger.warning("风险事件同步审计日志失败", extra={"error": str(e)})


@router.put("/events/{event_id}/handle")
def handle_risk_event(event_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """处理风险事件"""
    conn = _get_conn()
    try:
        events = query_dict(conn, "SELECT * FROM trade_risk_event WHERE event_id = %s", (event_id,))
        if not events:
            raise HTTPException(status_code=404, detail="风险事件不存在")

        new_status = body.get("status", "processed")
        handler_id = body.get("handler_id", "current_user")
        handle_comment = body.get("handle_comment", "")

        execute(
            conn,
            """UPDATE trade_risk_event
               SET status = %s, handler_id = %s, handle_comment = %s, handled_at = %s
               WHERE event_id = %s""",
            (new_status, handler_id, handle_comment, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), event_id)
        )

        return {"success": True, "message": "风险事件处理成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("处理风险事件失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"处理风险事件失败: {str(e)}")
    finally:
        conn.close()


# ============================================
# 风控告警管理
# ============================================

@router.get("/alerts")
def get_risk_alerts(
    alert_type: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    stock_code: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    is_read: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取风控告警列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if alert_type:
            conditions.append("alert_type = %s")
            params.append(alert_type)
        if level:
            conditions.append("level = %s")
            params.append(level)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)
        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if is_read is not None:
            conditions.append("is_read = %s")
            params.append(is_read)
        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_risk_alert WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_risk_alert
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        for row in rows:
            for dt_field in ["created_at", "updated_at", "handled_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取风控告警列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取风控告警失败: {str(e)}")
    finally:
        conn.close()


@router.post("/alerts")
def create_risk_alert(body: dict[str, Any]) -> dict[str, Any]:
    """创建风控告警"""
    conn = _get_conn()
    try:
        alert_id = f"alt_{uuid.uuid4().hex[:12]}"

        execute(
            conn,
            """INSERT INTO trade_risk_alert
               (alert_id, alert_type, level, stock_code, stock_name, account_id,
                message, metric_value, threshold_value, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                alert_id,
                body.get("alert_type", ""),
                body.get("level", "yellow"),
                body.get("stock_code"),
                body.get("stock_name"),
                body.get("account_id", ""),
                body.get("message", ""),
                body.get("metric_value"),
                body.get("threshold_value"),
                body.get("status", "pending"),
            )
        )

        return {"success": True, "alert_id": alert_id, "message": "告警创建成功"}
    except Exception as e:
        logger.error("创建风控告警失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建风控告警失败: {str(e)}")
    finally:
        conn.close()

    try:
        mgr = _get_manager()
        audit_entry = {
            "timestamp": _now_iso(),
            "stock_code": body.get("stock_code", ""),
            "direction": "",
            "amount": 0.0,
            "price": 0.0,
            "quantity": 0,
            "decision": body.get("level", "yellow"),
            "reason": body.get("message", ""),
            "rule_name": "risk_alert",
            "max_position_pct": 0.0,
            "alert_id": alert_id,
        }
        mgr.audit_log.append(audit_entry)
        from core.risk.service import _write_audit_entry
        _write_audit_entry(audit_entry)
    except Exception as e:
        logger.warning("风控告警同步审计日志失败", extra={"error": str(e)})


@router.put("/alerts/{alert_id}/handle")
def handle_risk_alert(alert_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """处理风控告警"""
    conn = _get_conn()
    try:
        alerts = query_dict(conn, "SELECT * FROM trade_risk_alert WHERE alert_id = %s", (alert_id,))
        if not alerts:
            raise HTTPException(status_code=404, detail="告警不存在")

        new_status = body.get("status", "processed")
        handler_id = body.get("handler_id", "current_user")
        handle_result = body.get("handle_result", "")

        execute(
            conn,
            """UPDATE trade_risk_alert
               SET status = %s, handler_id = %s, handle_result = %s, handled_at = %s
               WHERE alert_id = %s""",
            (new_status, handler_id, handle_result, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), alert_id)
        )

        return {"success": True, "message": "告警处理成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("处理风控告警失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"处理风控告警失败: {str(e)}")
    finally:
        conn.close()


@router.put("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: str) -> dict[str, Any]:
    """标记告警已读"""
    conn = _get_conn()
    try:
        execute(conn, "UPDATE trade_risk_alert SET is_read = 1 WHERE alert_id = %s", (alert_id,))
        return {"success": True, "message": "标记已读成功"}
    except Exception as e:
        logger.error("标记告警已读失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"标记已读失败: {str(e)}")
    finally:
        conn.close()


# ============================================
# 风控规则管理
# ============================================

@router.get("/rules")
def get_risk_rules(
    rule_type: Optional[str] = Query(None),
    enabled: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取风控规则列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if rule_type:
            conditions.append("rule_type = %s")
            params.append(rule_type)
        if enabled is not None:
            conditions.append("enabled = %s")
            params.append(enabled)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_risk_rule WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_risk_rule
            WHERE {where}
            ORDER BY priority ASC, created_at DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        for row in rows:
            for dt_field in ["created_at", "updated_at", "last_trigger_time"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取风控规则列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取风控规则失败: {str(e)}")
    finally:
        conn.close()


@router.post("/rules")
def create_risk_rule(body: dict[str, Any]) -> dict[str, Any]:
    """创建风控规则"""
    conn = _get_conn()
    try:
        rule_code = body.get("rule_code", f"rule_{uuid.uuid4().hex[:8]}")

        execute(
            conn,
            """INSERT INTO trade_risk_rule
               (rule_code, rule_name, rule_type, decision, condition_expr, condition_desc,
                max_position_pct, max_single_loss_pct, max_daily_loss_pct, max_concentration_pct,
                min_cash_reserve_pct, circuit_breaker_pct, priority, enabled, account_id, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                rule_code,
                body.get("rule_name", ""),
                body.get("rule_type", "position"),
                body.get("decision", "WARN"),
                body.get("condition_expr", ""),
                body.get("condition_desc"),
                body.get("max_position_pct"),
                body.get("max_single_loss_pct"),
                body.get("max_daily_loss_pct"),
                body.get("max_concentration_pct"),
                body.get("min_cash_reserve_pct"),
                body.get("circuit_breaker_pct"),
                body.get("priority", 100),
                body.get("enabled", 1),
                body.get("account_id"),
                body.get("notes"),
            )
        )

        return {"success": True, "rule_code": rule_code, "message": "风控规则创建成功"}
    except Exception as e:
        logger.error("创建风控规则失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建风控规则失败: {str(e)}")
    finally:
        conn.close()


@router.put("/rules/{rule_id}")
def update_risk_rule(rule_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """更新风控规则"""
    conn = _get_conn()
    try:
        rules = query_dict(conn, "SELECT * FROM trade_risk_rule WHERE id = %s", (rule_id,))
        if not rules:
            raise HTTPException(status_code=404, detail="风控规则不存在")

        update_fields = []
        update_values: list[Any] = []

        for field in ["rule_name", "rule_type", "decision", "condition_expr", "condition_desc",
                       "max_position_pct", "max_single_loss_pct", "max_daily_loss_pct",
                       "max_concentration_pct", "min_cash_reserve_pct", "circuit_breaker_pct",
                       "priority", "enabled", "account_id", "notes"]:
            if field in body:
                update_fields.append(f"{field} = %s")
                update_values.append(body[field])

        if not update_fields:
            return {"success": True, "message": "无更新内容"}

        update_values.append(rule_id)
        sql = f"UPDATE trade_risk_rule SET {', '.join(update_fields)} WHERE id = %s"
        execute(conn, sql, tuple(update_values))

        return {"success": True, "message": "风控规则更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新风控规则失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"更新风控规则失败: {str(e)}")
    finally:
        conn.close()


@router.put("/rules/{rule_id}/toggle")
def toggle_risk_rule(rule_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """切换风控规则启用/禁用状态"""
    conn = _get_conn()
    try:
        enabled = body.get("enabled", 1)
        execute(conn, "UPDATE trade_risk_rule SET enabled = %s WHERE id = %s", (enabled, rule_id))
        return {"success": True, "message": f"规则已{'启用' if enabled else '禁用'}"}
    except Exception as e:
        logger.error("切换风控规则状态失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"切换规则状态失败: {str(e)}")
    finally:
        conn.close()


# ============================================
# 风控看板概览
# ============================================

@router.get("/dashboard")
def get_risk_dashboard() -> dict[str, Any]:
    """获取风控看板概览数据"""
    conn = _get_conn()
    try:
        event_stats = query_dict(conn, """
            SELECT
                COUNT(*) as total_events,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_events,
                SUM(CASE WHEN risk_level = 'critical' THEN 1 ELSE 0 END) as critical_events,
                SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) as high_events
            FROM trade_risk_event
        """)

        alert_stats = query_dict(conn, """
            SELECT
                COUNT(*) as total_alerts,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_alerts,
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread_alerts,
                SUM(CASE WHEN level = 'red' THEN 1 ELSE 0 END) as red_alerts,
                SUM(CASE WHEN level = 'orange' THEN 1 ELSE 0 END) as orange_alerts
            FROM trade_risk_alert
        """)

        rule_stats = query_dict(conn, """
            SELECT
                COUNT(*) as total_rules,
                SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled_rules,
                SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) as disabled_rules
            FROM trade_risk_rule
        """)

        recent_events = query_dict(conn, """
            SELECT event_id, event_type, risk_level, stock_code, stock_name, status, created_at
            FROM trade_risk_event
            ORDER BY created_at DESC
            LIMIT 10
        """)

        for row in recent_events:
            if row.get("created_at") and hasattr(row["created_at"], "isoformat"):
                row["created_at"] = row["created_at"].isoformat()

        return {
            "event_stats": event_stats[0] if event_stats else {},
            "alert_stats": alert_stats[0] if alert_stats else {},
            "rule_stats": rule_stats[0] if rule_stats else {},
            "recent_events": recent_events,
        }
    except Exception as e:
        logger.error("获取风控看板数据失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取风控看板数据失败: {str(e)}")
    finally:
        conn.close()


# ============================================
# 持仓风险评估
# ============================================

@router.get("/position-risks")
def get_position_risks(
    account_id: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取持仓风险评估列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if risk_level:
            conditions.append("risk_level = %s")
            params.append(risk_level)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_position_risk WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_position_risk
            WHERE {where}
            ORDER BY risk_value DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        for row in rows:
            for dt_field in ["created_at", "updated_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取持仓风险评估失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取持仓风险评估失败: {str(e)}")
    finally:
        conn.close()


# ============================================
# 账户风险指标
# ============================================

@router.get("/account-metrics")
def get_account_risk_metrics(
    account_id: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取账户风险指标列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if risk_level:
            conditions.append("risk_level = %s")
            params.append(risk_level)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_account_risk_metric WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_account_risk_metric
            WHERE {where}
            ORDER BY risk_score DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        for row in rows:
            for dt_field in ["created_at", "updated_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取账户风险指标失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取账户风险指标失败: {str(e)}")
    finally:
        conn.close()


# ============================================
# 风控操作日志
# ============================================

@router.get("/operation-logs")
def get_operation_logs(
    operation_type: Optional[str] = Query(None),
    operator_id: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """获取风控操作日志"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list[Any] = []

        if operation_type:
            conditions.append("operation_type = %s")
            params.append(operation_type)
        if operator_id:
            conditions.append("operator_id = %s")
            params.append(operator_id)
        if target_type:
            conditions.append("target_type = %s")
            params.append(target_type)
        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) as total FROM trade_risk_operation_log WHERE {where}"
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_risk_operation_log
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))

        for row in rows:
            if row.get("operation_data") and isinstance(row["operation_data"], str):
                try:
                    row["operation_data"] = json.loads(row["operation_data"])
                except Exception:
                    pass
            for dt_field in ["created_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error("获取风控操作日志失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取风控操作日志失败: {str(e)}")
    finally:
        conn.close()
