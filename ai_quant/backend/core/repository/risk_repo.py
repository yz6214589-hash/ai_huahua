"""
风控 Repository - 封装风控事件、告警、规则、看板数据访问操作
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from core.repository.base import BaseRepository


class RiskRepository(BaseRepository):
    """风控数据访问层，封装trade_risk_event、trade_risk_alert、trade_risk_rule等表操作"""

    # ========================================
    # 风险事件 (trade_risk_event)
    # ========================================

    def list_events(
        self,
        event_type: str | None = None,
        risk_level: str | None = None,
        status: str | None = None,
        stock_code: str | None = None,
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """分页查询风险事件列表"""
        conditions = ["1=1"]
        params: list = []

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

        count_result = self._query(
            f"SELECT COUNT(*) as total FROM trade_risk_event WHERE {where}",
            tuple(params),
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = self._query(
            f"SELECT * FROM trade_risk_event WHERE {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        for row in rows:
            if row.get("event_data") and isinstance(row["event_data"], str):
                try:
                    row["event_data"] = json.loads(row["event_data"])
                except Exception:
                    pass
            for dt_field in ["created_at", "updated_at", "handled_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return rows, total

    def create_event(self, body: dict) -> dict:
        """创建风险事件"""
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        event_data_json = (
            json.dumps(body.get("event_data", {}), ensure_ascii=False)
            if body.get("event_data")
            else None
        )

        self._execute(
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
            ),
        )

        return {"success": True, "event_id": event_id}

    def handle_event(self, event_id: str, body: dict) -> dict | None:
        """处理风险事件，不存在时返回None"""
        existing = self._query_one(
            "SELECT id FROM trade_risk_event WHERE event_id = %s", (event_id,)
        )
        if not existing:
            return None

        new_status = body.get("status", "processed")
        handler_id = body.get("handler_id", "current_user")
        handle_comment = body.get("handle_comment", "")

        self._execute(
            """UPDATE trade_risk_event
               SET status = %s, handler_id = %s, handle_comment = %s, handled_at = %s
               WHERE event_id = %s""",
            (
                new_status,
                handler_id,
                handle_comment,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                event_id,
            ),
        )
        return {"success": True}

    def write_approval_event(self, result: dict, body: dict) -> None:
        """写入审批事件记录"""
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        event_data_json = json.dumps(result, ensure_ascii=False, default=str)
        self._execute(
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
            ),
        )

    # ========================================
    # 风控告警 (trade_risk_alert)
    # ========================================

    def list_alerts(
        self,
        alert_type: str | None = None,
        level: str | None = None,
        status: str | None = None,
        stock_code: str | None = None,
        account_id: str | None = None,
        is_read: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """分页查询告警列表"""
        conditions = ["1=1"]
        params: list = []

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

        count_result = self._query(
            f"SELECT COUNT(*) as total FROM trade_risk_alert WHERE {where}",
            tuple(params),
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = self._query(
            f"SELECT * FROM trade_risk_alert WHERE {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        for row in rows:
            for dt_field in ["created_at", "updated_at", "handled_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return rows, total

    def create_alert(self, body: dict) -> dict:
        """创建告警"""
        alert_id = f"alt_{uuid.uuid4().hex[:12]}"
        self._execute(
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
            ),
        )
        return {"success": True, "alert_id": alert_id}

    def handle_alert(self, alert_id: str, body: dict) -> dict | None:
        """处理告警，不存在时返回None"""
        existing = self._query_one(
            "SELECT id FROM trade_risk_alert WHERE alert_id = %s", (alert_id,)
        )
        if not existing:
            return None

        new_status = body.get("status", "processed")
        handler_id = body.get("handler_id", "current_user")
        handle_result = body.get("handle_result", "")

        self._execute(
            """UPDATE trade_risk_alert
               SET status = %s, handler_id = %s, handle_result = %s, handled_at = %s
               WHERE alert_id = %s""",
            (
                new_status,
                handler_id,
                handle_result,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                alert_id,
            ),
        )
        return {"success": True}

    def mark_alert_read(self, alert_id: str) -> bool:
        """标记告警已读，返回是否成功"""
        affected = self._execute(
            "UPDATE trade_risk_alert SET is_read = 1 WHERE alert_id = %s",
            (alert_id,),
        )
        return affected > 0

    # ========================================
    # 风控规则 (trade_risk_rule)
    # ========================================

    def list_rules(
        self,
        rule_type: str | None = None,
        enabled: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """分页查询风控规则列表"""
        conditions = ["1=1"]
        params: list = []

        if rule_type:
            conditions.append("rule_type = %s")
            params.append(rule_type)
        if enabled is not None:
            conditions.append("enabled = %s")
            params.append(enabled)

        where = " AND ".join(conditions)

        count_result = self._query(
            f"SELECT COUNT(*) as total FROM trade_risk_rule WHERE {where}",
            tuple(params),
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = self._query(
            f"SELECT * FROM trade_risk_rule WHERE {where} "
            f"ORDER BY priority ASC, created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        for row in rows:
            for dt_field in ["created_at", "updated_at", "last_trigger_time"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return rows, total

    def create_rule(self, body: dict) -> dict:
        """创建风控规则"""
        rule_code = body.get("rule_code", f"rule_{uuid.uuid4().hex[:8]}")
        self._execute(
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
            ),
        )
        return {"success": True, "rule_code": rule_code}

    def update_rule(self, rule_id: int, body: dict) -> dict | None:
        """更新风控规则，不存在时返回None"""
        existing = self._query_one(
            "SELECT id FROM trade_risk_rule WHERE id = %s", (rule_id,)
        )
        if not existing:
            return None

        update_fields = []
        update_values: list = []

        for field in [
            "rule_name", "rule_type", "decision", "condition_expr", "condition_desc",
            "max_position_pct", "max_single_loss_pct", "max_daily_loss_pct",
            "max_concentration_pct", "min_cash_reserve_pct", "circuit_breaker_pct",
            "priority", "enabled", "account_id", "notes",
        ]:
            if field in body:
                update_fields.append(f"{field} = %s")
                update_values.append(body[field])

        if not update_fields:
            return {"success": True}

        update_values.append(rule_id)
        sql = f"UPDATE trade_risk_rule SET {', '.join(update_fields)} WHERE id = %s"
        self._execute(sql, tuple(update_values))
        return {"success": True}

    def toggle_rule(self, rule_id: int, enabled: int) -> bool:
        """切换规则启用/禁用状态"""
        affected = self._execute(
            "UPDATE trade_risk_rule SET enabled = %s WHERE id = %s",
            (enabled, rule_id),
        )
        return affected > 0

    def get_rule(self, rule_id: int) -> dict | None:
        """获取单个规则"""
        return self._query_one(
            "SELECT * FROM trade_risk_rule WHERE id = %s", (rule_id,)
        )

    # ========================================
    # 风控看板
    # ========================================

    def get_dashboard(self) -> dict:
        """获取风控看板概览数据"""
        event_stats = self._query(
            """SELECT
                COUNT(*) as total_events,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_events,
                SUM(CASE WHEN risk_level = 'critical' THEN 1 ELSE 0 END) as critical_events,
                SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) as high_events
            FROM trade_risk_event"""
        )

        alert_stats = self._query(
            """SELECT
                COUNT(*) as total_alerts,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_alerts,
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread_alerts,
                SUM(CASE WHEN level = 'red' THEN 1 ELSE 0 END) as red_alerts,
                SUM(CASE WHEN level = 'orange' THEN 1 ELSE 0 END) as orange_alerts
            FROM trade_risk_alert"""
        )

        rule_stats = self._query(
            """SELECT
                COUNT(*) as total_rules,
                SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled_rules,
                SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) as disabled_rules
            FROM trade_risk_rule"""
        )

        recent_events = self._query(
            """SELECT event_id, event_type, risk_level, stock_code, stock_name, status, created_at
            FROM trade_risk_event ORDER BY created_at DESC LIMIT 10"""
        )

        for row in recent_events:
            if row.get("created_at") and hasattr(row["created_at"], "isoformat"):
                row["created_at"] = row["created_at"].isoformat()

        return {
            "event_stats": event_stats[0] if event_stats else {},
            "alert_stats": alert_stats[0] if alert_stats else {},
            "rule_stats": rule_stats[0] if rule_stats else {},
            "recent_events": recent_events,
        }

    # ========================================
    # 持仓风险 (trade_position_risk)
    # ========================================

    def list_position_risks(
        self,
        account_id: str | None = None,
        risk_level: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """分页查询持仓风险评估"""
        conditions = ["1=1"]
        params: list = []

        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if risk_level:
            conditions.append("risk_level = %s")
            params.append(risk_level)

        where = " AND ".join(conditions)

        count_result = self._query(
            f"SELECT COUNT(*) as total FROM trade_position_risk WHERE {where}",
            tuple(params),
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = self._query(
            f"SELECT * FROM trade_position_risk WHERE {where} "
            f"ORDER BY risk_value DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        for row in rows:
            for dt_field in ["created_at", "updated_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return rows, total

    # ========================================
    # 账户风险指标 (trade_account_risk_metric)
    # ========================================

    def list_account_metrics(
        self,
        account_id: str | None = None,
        risk_level: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """分页查询账户风险指标"""
        conditions = ["1=1"]
        params: list = []

        if account_id:
            conditions.append("account_id = %s")
            params.append(account_id)
        if risk_level:
            conditions.append("risk_level = %s")
            params.append(risk_level)

        where = " AND ".join(conditions)

        count_result = self._query(
            f"SELECT COUNT(*) as total FROM trade_account_risk_metric WHERE {where}",
            tuple(params),
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = self._query(
            f"SELECT * FROM trade_account_risk_metric WHERE {where} "
            f"ORDER BY risk_score DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        for row in rows:
            for dt_field in ["created_at", "updated_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return rows, total

    # ========================================
    # 操作日志 (trade_risk_operation_log)
    # ========================================

    def list_operation_logs(
        self,
        operation_type: str | None = None,
        operator_id: str | None = None,
        target_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """分页查询操作日志"""
        conditions = ["1=1"]
        params: list = []

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

        count_result = self._query(
            f"SELECT COUNT(*) as total FROM trade_risk_operation_log WHERE {where}",
            tuple(params),
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = self._query(
            f"SELECT * FROM trade_risk_operation_log WHERE {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        for row in rows:
            if row.get("operation_data") and isinstance(row["operation_data"], str):
                try:
                    row["operation_data"] = json.loads(row["operation_data"])
                except Exception:
                    pass
            for dt_field in ["created_at"]:
                if row.get(dt_field) and hasattr(row[dt_field], "isoformat"):
                    row[dt_field] = row[dt_field].isoformat()

        return rows, total
