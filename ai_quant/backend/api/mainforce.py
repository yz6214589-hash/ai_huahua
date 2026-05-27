"""
主力识别API接口
提供主力活动、任务、K线标注和告警规则的CRUD操作
数据存储使用MySQL数据库
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Optional, List
from datetime import datetime, date
import json
import uuid

from core.db import connect, load_mysql_config, query_dict, execute
from infra.storage.logging_service import get_logger

logger = get_logger("mainforce")

router = APIRouter(prefix="/api/v1/mainforce", tags=["主力识别"])


def _get_conn():
    """获取数据库连接"""
    cfg = load_mysql_config()
    return connect(cfg)


# ============ 数据模型 ============

class MainForceActivity(BaseModel):
    id: Optional[str] = None
    date: str
    stock_code: str
    stock_name: str
    activity_type: str
    volume: int
    amount: float
    price: float
    ratio: float
    mainforce_type: str = 'retail'
    description: Optional[str] = None
    indicators: Optional[str] = None
    is_anomaly: int = 0
    alert_status: str = 'none'


class MainForceRule(BaseModel):
    id: Optional[str] = None
    name: str
    rule_type: str
    description: Optional[str] = None
    enabled: int = 1
    threshold: float
    threshold_unit: Optional[str] = None
    condition: Optional[str] = None
    action: str = 'alert'
    priority: int = 0
    alert_template: Optional[str] = None


class KlineMarker(BaseModel):
    id: Optional[str] = None
    stock_code: str
    stock_name: str
    marker_date: str
    marker_price: float
    marker_type: str
    volume: Optional[int] = None
    amount: Optional[float] = None
    mainforce_type: str = 'retail'
    source: str = 'auto'
    activity_id: Optional[str] = None
    description: Optional[str] = None
    is_visible: int = 1


# ============ 主力活动API ============

@router.get("/activities", response_model=List[dict])
async def get_activities(
    stock_code: Optional[str] = None,
    activity_type: Optional[str] = None,
    mainforce_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    alert_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100)
):
    """获取主力活动列表"""
    logger.info("开始获取主力活动列表", extra={
        "filters": {"stock_code": stock_code, "activity_type": activity_type},
        "pagination": {"page": page, "page_size": page_size}
    })
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list = []

        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)
        if activity_type:
            conditions.append("activity_type = %s")
            params.append(activity_type)
        if mainforce_type:
            conditions.append("mainforce_type = %s")
            params.append(mainforce_type)
        if start_date:
            conditions.append("activity_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("activity_date <= %s")
            params.append(end_date)
        if alert_status:
            conditions.append("alert_status = %s")
            params.append(alert_status)

        where = " AND ".join(conditions)
        logger.debug("构建查询条件", extra={"where": where, "params_count": len(params)})

        count_sql = f"SELECT COUNT(*) as total FROM trade_mainforce_activity WHERE {where}"
        logger.debug("查询总数")
        count_result = query_dict(conn, count_sql, tuple(params))
        total = count_result[0]["total"] if count_result else 0
        logger.debug(f"总数: {total}")

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT * FROM trade_mainforce_activity WHERE {where}
            ORDER BY activity_date DESC, created_at DESC
            LIMIT %s OFFSET %s
        """
        logger.debug(f"查询数据，offset: {offset}, limit: {page_size}")
        rows = query_dict(conn, data_sql, tuple(params + [page_size, offset]))
        logger.info(f"查询完成，返回 {len(rows)} 条记录")

        for row in rows:
            if row.get("indicators") and isinstance(row["indicators"], str):
                try:
                    row["indicators"] = json.loads(row["indicators"])
                except Exception:
                    pass
            for key in ("created_at", "updated_at", "activity_date"):
                if row.get(key):
                    row[key] = str(row[key])
            row["date"] = row.get("activity_date", "")

        return rows
    except Exception as e:
        logger.error("获取主力活动列表失败", extra={"error": str(e)})
        return []
    finally:
        conn.close()
        logger.debug("数据库连接已关闭")


@router.post("/activities")
async def create_activity(activity: MainForceActivity):
    """创建主力活动记录"""
    conn = _get_conn()
    try:
        execute(
            conn,
            """INSERT INTO trade_mainforce_activity
               (activity_date, stock_code, stock_name, activity_type, volume, amount, price, ratio,
                mainforce_type, description, indicators, is_anomaly, alert_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (activity.date, activity.stock_code, activity.stock_name, activity.activity_type,
             activity.volume, activity.amount, activity.price, activity.ratio,
             activity.mainforce_type, activity.description,
             json.dumps(activity.indicators) if activity.indicators else None,
             activity.is_anomaly, activity.alert_status)
        )
        result = query_dict(conn, "SELECT LAST_INSERT_ID() as id", ())
        activity_id = result[0]["id"] if result else 0
        return {"id": activity_id, "message": "活动记录创建成功"}
    except Exception as e:
        logger.error("创建主力活动记录失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建活动记录失败: {str(e)}")
    finally:
        conn.close()


@router.get("/activities/{activity_id}")
async def get_activity(activity_id: str):
    """获取单个主力活动"""
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_mainforce_activity WHERE id = %s", (activity_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="活动记录不存在")
        row = rows[0]
        if row.get("indicators") and isinstance(row["indicators"], str):
            try:
                row["indicators"] = json.loads(row["indicators"])
            except Exception:
                pass
        for key in ("created_at", "updated_at", "activity_date"):
            if row.get(key):
                row[key] = str(row[key])
        row["date"] = row.get("activity_date", "")
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取主力活动失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取活动记录失败: {str(e)}")
    finally:
        conn.close()


# ============ 告警规则API ============

@router.get("/rules", response_model=List[dict])
async def get_rules(enabled: Optional[bool] = None):
    """获取告警规则列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list = []
        if enabled is not None:
            conditions.append("enabled = %s")
            params.append(1 if enabled else 0)
        where = " AND ".join(conditions)

        rows = query_dict(
            conn,
            f"SELECT * FROM trade_mainforce_alert_rule WHERE {where} ORDER BY priority DESC, created_at DESC",
            tuple(params)
        )
        for row in rows:
            if row.get("condition") and isinstance(row["condition"], str):
                try:
                    row["condition"] = json.loads(row["condition"])
                except Exception:
                    pass
            row["enabled"] = bool(row.get("enabled", 0))
            for key in ("created_at", "updated_at", "last_trigger_time"):
                if row.get(key):
                    row[key] = str(row[key])
        return rows
    except Exception as e:
        logger.error("获取告警规则列表失败", extra={"error": str(e)})
        return []
    finally:
        conn.close()


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, rule: MainForceRule):
    """更新告警规则"""
    conn = _get_conn()
    try:
        existing = query_dict(conn, "SELECT id FROM trade_mainforce_alert_rule WHERE id = %s", (rule_id,))
        if not existing:
            raise HTTPException(status_code=404, detail="规则不存在")

        execute(
            conn,
            """UPDATE trade_mainforce_alert_rule
               SET name = %s, rule_type = %s, description = %s, enabled = %s, threshold = %s,
                   threshold_unit = %s, `condition` = %s, action = %s, priority = %s,
                   alert_template = %s
               WHERE id = %s""",
            (rule.name, rule.rule_type, rule.description, rule.enabled, rule.threshold,
             rule.threshold_unit, json.dumps(rule.condition) if rule.condition else None,
             rule.action, rule.priority, rule.alert_template, rule_id)
        )
        return {"message": "规则更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新告警规则失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"更新规则失败: {str(e)}")
    finally:
        conn.close()


@router.post("/rules/{rule_id}/trigger")
async def trigger_rule(rule_id: str, stock_code: str, stock_name: str, value: float):
    """触发规则检查"""
    conn = _get_conn()
    try:
        rules = query_dict(
            conn,
            "SELECT * FROM trade_mainforce_alert_rule WHERE id = %s AND enabled = 1",
            (rule_id,)
        )
        if not rules:
            raise HTTPException(status_code=404, detail="规则不存在或未启用")

        rule = rules[0]
        threshold = float(rule.get("threshold", 0))
        triggered = value >= threshold

        if triggered:
            execute(
                conn,
                """UPDATE trade_mainforce_alert_rule
                   SET trigger_count = trigger_count + 1,
                       last_trigger_time = NOW(),
                       last_trigger_value = %s
                   WHERE id = %s""",
                (value, rule_id)
            )

        alert_template = rule.get("alert_template", "")
        message = None
        if triggered and alert_template:
            try:
                ratio = value / threshold * 100 if threshold > 0 else 0
                message = alert_template.format(
                    stock_code=stock_code, stock_name=stock_name,
                    amount=value, ratio=round(ratio, 2)
                )
            except Exception:
                message = alert_template

        return {
            "triggered": triggered,
            "rule_name": rule.get("name", ""),
            "threshold": threshold,
            "actual_value": value,
            "message": message
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("触发规则检查失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"触发规则检查失败: {str(e)}")
    finally:
        conn.close()


# ============ K线标注API ============

@router.get("/markers", response_model=List[dict])
async def get_markers(
    stock_code: Optional[str] = None,
    marker_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """获取K线标注列表"""
    conn = _get_conn()
    try:
        conditions = ["is_visible = 1"]
        params: list = []

        if stock_code:
            conditions.append("stock_code = %s")
            params.append(stock_code)
        if marker_type:
            conditions.append("marker_type = %s")
            params.append(marker_type)
        if start_date:
            conditions.append("marker_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("marker_date <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)
        rows = query_dict(
            conn,
            f"SELECT * FROM trade_kline_marker WHERE {where} ORDER BY marker_date DESC",
            tuple(params)
        )
        for row in rows:
            for key in ("created_at", "updated_at", "marker_date"):
                if row.get(key):
                    row[key] = str(row[key])
        return rows
    except Exception as e:
        logger.error("获取K线标注列表失败", extra={"error": str(e)})
        return []
    finally:
        conn.close()


@router.post("/markers")
async def create_marker(marker: KlineMarker):
    """创建K线标注"""
    conn = _get_conn()
    try:
        execute(
            conn,
            """INSERT INTO trade_kline_marker
               (stock_code, stock_name, marker_date, marker_price, marker_type,
                volume, amount, mainforce_type, source, activity_id, description, is_visible)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (marker.stock_code, marker.stock_name, marker.marker_date, marker.marker_price,
             marker.marker_type, marker.volume, marker.amount, marker.mainforce_type,
             marker.source, marker.activity_id, marker.description, marker.is_visible)
        )
        result = query_dict(conn, "SELECT LAST_INSERT_ID() as id", ())
        marker_id = result[0]["id"] if result else 0
        return {"id": marker_id, "message": "标注创建成功"}
    except Exception as e:
        logger.error("创建K线标注失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建标注失败: {str(e)}")
    finally:
        conn.close()


# ============ 统计API ============

@router.get("/statistics")
async def get_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """获取主力识别统计"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("stat_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("stat_date <= %s")
            params.append(end_date)

        where = " AND ".join(conditions)
        rows = query_dict(
            conn,
            f"SELECT * FROM trade_mainforce_statistic WHERE {where} ORDER BY stat_date DESC",
            tuple(params)
        )
        for row in rows:
            if row.get("top_stocks") and isinstance(row["top_stocks"], str):
                try:
                    row["top_stocks"] = json.loads(row["top_stocks"])
                except Exception:
                    row["top_stocks"] = []
            for key in ("created_at", "updated_at", "stat_date"):
                if row.get(key):
                    row[key] = str(row[key])
        return rows
    except Exception as e:
        logger.error("获取主力识别统计失败", extra={"error": str(e)})
        return []
    finally:
        conn.close()


@router.get("/summary")
async def get_summary():
    """获取总体统计摘要"""
    conn = _get_conn()
    try:
        today = datetime.now().strftime('%Y-%m-%d')

        today_stats = query_dict(
            conn,
            """SELECT
                COUNT(*) as total_count,
                SUM(CASE WHEN activity_type = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN activity_type = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                SUM(CASE WHEN activity_type = 'BUY' THEN amount ELSE 0 END) as total_buy_amount,
                SUM(CASE WHEN activity_type = 'SELL' THEN amount ELSE 0 END) as total_sell_amount,
                SUM(CASE WHEN mainforce_type = 'institution' THEN 1 ELSE 0 END) as institution_count,
                SUM(CASE WHEN mainforce_type = 'hot_money' THEN 1 ELSE 0 END) as hot_money_count
            FROM trade_mainforce_activity
            WHERE activity_date = %s""",
            (today,)
        )

        week_stats = query_dict(
            conn,
            """SELECT
                COUNT(*) as total_count,
                SUM(amount) as total_amount
            FROM trade_mainforce_activity
            WHERE activity_date >= DATE_SUB(%s, INTERVAL 7 DAY)""",
            (today,)
        )

        active_rules = query_dict(conn, "SELECT COUNT(*) as cnt FROM trade_mainforce_alert_rule WHERE enabled = 1", ())
        active_rules_count = active_rules[0]["cnt"] if active_rules else 0

        ts = today_stats[0] if today_stats else {}
        ws = week_stats[0] if week_stats else {}

        buy_amount = float(ts.get("total_buy_amount") or 0)
        sell_amount = float(ts.get("total_sell_amount") or 0)

        return {
            "today": {
                "total_count": int(ts.get("total_count") or 0),
                "buy_count": int(ts.get("buy_count") or 0),
                "sell_count": int(ts.get("sell_count") or 0),
                "total_buy_amount": buy_amount,
                "total_sell_amount": sell_amount,
                "net_flow": buy_amount - sell_amount,
                "institution_count": int(ts.get("institution_count") or 0),
                "hot_money_count": int(ts.get("hot_money_count") or 0)
            },
            "week": {
                "total_count": int(ws.get("total_count") or 0),
                "total_amount": float(ws.get("total_amount") or 0)
            },
            "active_rules": active_rules_count
        }
    except Exception as e:
        logger.error("获取总体统计摘要失败", extra={"error": str(e)})
        return {
            "today": {"total_count": 0, "buy_count": 0, "sell_count": 0,
                      "total_buy_amount": 0, "total_sell_amount": 0, "net_flow": 0,
                      "institution_count": 0, "hot_money_count": 0},
            "week": {"total_count": 0, "total_amount": 0},
            "active_rules": 0
        }
    finally:
        conn.close()


# ============ 异动监控 ============

@router.get("/abnormal")
async def get_abnormal_stocks(
    alert_type: Optional[str] = Query(None, description="异动类型: volume/amplitude/turnover/price"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
) -> dict[str, Any]:
    """
    获取异动监控数据。

    从 trade_mainforce_activity 表查询主力异动记录，
    关联 trade_stock_daily 获取最新行情指标。

    Args:
        alert_type: 异动类型筛选（volume-放量/amplitude-振幅/turnover-换手率/price-价格）
        limit: 返回条数上限

    Returns:
        dict: 包含 items（异动股票列表）和 total（总数）
    """
    logger.info("异动监控数据请求", extra={
        "alert_type": alert_type or "all",
        "limit": limit,
    })
    conn = _get_conn()
    try:
        # 查询最新的交易日期
        latest_date_rows = query_dict(
            conn,
            "SELECT MAX(activity_date) as max_date FROM trade_mainforce_activity",
            ()
        )
        latest_date = None
        if latest_date_rows and latest_date_rows[0].get("max_date"):
            max_dt = latest_date_rows[0]["max_date"]
            if hasattr(max_dt, "strftime"):
                latest_date = max_dt.strftime("%Y-%m-%d")
            else:
                latest_date = str(max_dt)

        if not latest_date:
            return {"items": [], "total": 0}

        # 构建查询 - 从主力活动表关联日线行情
        conditions = ["a.activity_date = %s"]
        params: list[Any] = [latest_date]

        if alert_type:
            conditions.append("a.alert_status = 'triggered'")
            # 根据异动类型添加额外条件
            if alert_type == "volume":
                # 放量异动：成交量大
                conditions.append("a.ratio >= 0.5")
            elif alert_type == "amplitude":
                # 振幅异动：筛选大单活动
                pass
            elif alert_type == "turnover":
                # 换手率异动：高成交额
                conditions.append("a.amount >= 10000000")
            elif alert_type == "price":
                # 价格异动：大单买卖
                conditions.append("a.activity_type IN ('BUY', 'SELL')")

        where = " AND ".join(conditions)

        sql = f"""
            SELECT
                a.stock_code,
                a.stock_name,
                a.activity_type,
                a.volume,
                a.amount,
                a.price,
                a.ratio,
                a.mainforce_type,
                a.is_anomaly,
                a.alert_status,
                a.description,
                a.indicators,
                m.sector_level1 as sector,
                d.change_pct,
                d.volume_ratio,
                d.turnover_rate,
                d.amplitude,
                d.change_pct_5d,
                d.change_pct_20d
            FROM trade_mainforce_activity a
            LEFT JOIN trade_stock_master m ON a.stock_code = m.stock_code
            LEFT JOIN trade_stock_daily d ON a.stock_code = d.stock_code AND d.trade_date = a.activity_date
            WHERE {where}
            ORDER BY a.amount DESC
            LIMIT %s
        """
        rows = query_dict(conn, sql, tuple(params + [limit]))

        items = []
        for row in rows:
            # 确定异动类型
            row_alert_type = alert_type or "volume"
            # 构建异动原因
            alert_reason = row.get("description") or ""
            if not alert_reason:
                activity_type = row.get("activity_type", "")
                mainforce_type = row.get("mainforce_type", "")
                ratio_val = float(row.get("ratio") or 0)
                if activity_type == "BUY":
                    alert_reason = f"{mainforce_type}大额买入，占比{round(ratio_val * 100, 1)}%"
                elif activity_type == "SELL":
                    alert_reason = f"{mainforce_type}大额卖出，占比{round(ratio_val * 100, 1)}%"
                else:
                    alert_reason = f"{mainforce_type}异动，占比{round(ratio_val * 100, 1)}%"

            def _safe_float(v):
                if v is None:
                    return None
                try:
                    f = float(v)
                    return f if float("inf") > f > float("-inf") else None
                except (ValueError, TypeError):
                    return None

            items.append({
                "code": row.get("stock_code", ""),
                "name": row.get("stock_name", ""),
                "change_pct": _safe_float(row.get("change_pct")),
                "volume_ratio": _safe_float(row.get("volume_ratio")),
                "turnover_rate": _safe_float(row.get("turnover_rate")),
                "amplitude": _safe_float(row.get("amplitude")),
                "change_5d": _safe_float(row.get("change_pct_5d")),
                "change_20d": _safe_float(row.get("change_pct_20d")),
                "alert_reason": alert_reason,
                "sector": row.get("sector") or "",
                "alert_type": row_alert_type,
            })

        logger.info("异动监控数据查询完成",
                    extra={"date": latest_date, "count": len(items)})

        return {
            "items": items,
            "total": len(items),
        }
    except Exception as e:
        logger.error("获取异动监控数据失败", extra={"error": str(e)})
        return {"items": [], "total": 0}
    finally:
        conn.close()
