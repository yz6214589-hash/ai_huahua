"""
主力识别API接口
提供主力活动、任务、K线标注和告警规则的CRUD操作
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import sqlite3
import json
import os
import uuid

router = APIRouter(prefix="/api/mainforce", tags=["主力识别"])

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'risk_management.db')


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM mainforce_activities WHERE 1=1"
    params = []
    
    if stock_code:
        sql += " AND stock_code = ?"
        params.append(stock_code)
    if activity_type:
        sql += " AND activity_type = ?"
        params.append(activity_type)
    if mainforce_type:
        sql += " AND mainforce_type = ?"
        params.append(mainforce_type)
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    if alert_status:
        sql += " AND alert_status = ?"
        params.append(alert_status)
    
    # 获取总数
    count_sql = sql.replace("SELECT *", "SELECT COUNT(*)")
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    
    # 分页
    offset = (page - 1) * page_size
    sql += " ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    conn.close()
    
    return [
        {
            **dict(row),
            'indicators': json.loads(row['indicators']) if row['indicators'] else None
        }
        for row in rows
    ]


@router.post("/activities")
async def create_activity(activity: MainForceActivity):
    """创建主力活动记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    activity_id = str(uuid.uuid4())
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
        INSERT INTO mainforce_activities 
        (id, date, stock_code, stock_name, activity_type, volume, amount, price, ratio, 
         mainforce_type, description, indicators, is_anomaly, alert_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        activity_id,
        activity.date,
        activity.stock_code,
        activity.stock_name,
        activity.activity_type,
        activity.volume,
        activity.amount,
        activity.price,
        activity.ratio,
        activity.mainforce_type,
        activity.description,
        json.dumps(activity.indicators) if activity.indicators else None,
        activity.is_anomaly,
        activity.alert_status,
        created_at,
        created_at
    ))
    
    conn.commit()
    conn.close()
    
    return {"id": activity_id, "message": "活动记录创建成功"}


@router.get("/activities/{activity_id}")
async def get_activity(activity_id: str):
    """获取单个主力活动"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM mainforce_activities WHERE id = ?", (activity_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="活动记录不存在")
    
    return dict(row)


# ============ 告警规则API ============

@router.get("/rules", response_model=List[dict])
async def get_rules(enabled: Optional[bool] = None):
    """获取告警规则列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM mainforce_alert_rules"
    params = []
    
    if enabled is not None:
        sql += " WHERE enabled = ?"
        params.append(1 if enabled else 0)
    
    sql += " ORDER BY priority DESC, created_at DESC"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    conn.close()
    
    return [
        {
            **dict(row),
            'enabled': bool(row['enabled']),
            'condition': json.loads(row['condition']) if row['condition'] else None
        }
        for row in rows
    ]


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, rule: MainForceRule):
    """更新告警规则"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查规则是否存在
    cursor.execute("SELECT id FROM mainforce_alert_rules WHERE id = ?", (rule_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="规则不存在")
    
    updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
        UPDATE mainforce_alert_rules
        SET name = ?, rule_type = ?, description = ?, enabled = ?, threshold = ?,
            threshold_unit = ?, condition = ?, action = ?, priority = ?,
            alert_template = ?, updated_at = ?
        WHERE id = ?
    """, (
        rule.name,
        rule.rule_type,
        rule.description,
        rule.enabled,
        rule.threshold,
        rule.threshold_unit,
        json.dumps(rule.condition) if rule.condition else None,
        rule.action,
        rule.priority,
        rule.alert_template,
        updated_at,
        rule_id
    ))
    
    conn.commit()
    conn.close()
    
    return {"message": "规则更新成功"}


@router.post("/rules/{rule_id}/trigger")
async def trigger_rule(rule_id: str, stock_code: str, stock_name: str, value: float):
    """触发规则检查"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM mainforce_alert_rules WHERE id = ? AND enabled = 1", (rule_id,))
    rule = cursor.fetchone()
    
    if not rule:
        conn.close()
        raise HTTPException(status_code=404, detail="规则不存在或未启用")
    
    triggered = False
    if value >= rule['threshold']:
        triggered = True
        cursor.execute("""
            UPDATE mainforce_alert_rules
            SET trigger_count = trigger_count + 1,
                last_trigger_time = ?,
                last_trigger_value = ?
            WHERE id = ?
        """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), value, rule_id))
        conn.commit()
    
    conn.close()
    
    return {
        "triggered": triggered,
        "rule_name": rule['name'],
        "threshold": rule['threshold'],
        "actual_value": value,
        "message": rule['alert_template'].format(
            stock_code=stock_code,
            stock_name=stock_name,
            amount=value,
            ratio=value / rule['threshold'] * 100 if rule['threshold'] > 0 else 0
        ) if triggered else None
    }


# ============ K线标注API ============

@router.get("/markers", response_model=List[dict])
async def get_markers(
    stock_code: Optional[str] = None,
    marker_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """获取K线标注列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM kline_markers WHERE is_visible = 1"
    params = []
    
    if stock_code:
        sql += " AND stock_code = ?"
        params.append(stock_code)
    if marker_type:
        sql += " AND marker_type = ?"
        params.append(marker_type)
    if start_date:
        sql += " AND marker_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND marker_date <= ?"
        params.append(end_date)
    
    sql += " ORDER BY marker_date DESC"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    conn.close()
    
    return [dict(row) for row in rows]


@router.post("/markers")
async def create_marker(marker: KlineMarker):
    """创建K线标注"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    marker_id = str(uuid.uuid4())
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
        INSERT INTO kline_markers
        (id, stock_code, stock_name, marker_date, marker_price, marker_type, 
         volume, amount, mainforce_type, source, activity_id, description, is_visible, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        marker_id,
        marker.stock_code,
        marker.stock_name,
        marker.marker_date,
        marker.marker_price,
        marker.marker_type,
        marker.volume,
        marker.amount,
        marker.mainforce_type,
        marker.source,
        marker.activity_id,
        marker.description,
        marker.is_visible,
        created_at,
        created_at
    ))
    
    conn.commit()
    conn.close()
    
    return {"id": marker_id, "message": "标注创建成功"}


# ============ 统计API ============

@router.get("/statistics")
async def get_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """获取主力识别统计"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM mainforce_statistics WHERE 1=1"
    params = []
    
    if start_date:
        sql += " AND stat_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND stat_date <= ?"
        params.append(end_date)
    
    sql += " ORDER BY stat_date DESC"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    conn.close()
    
    return [
        {
            **dict(row),
            'top_stocks': json.loads(row['top_stocks']) if row['top_stocks'] else []
        }
        for row in rows
    ]


@router.get("/summary")
async def get_summary():
    """获取总体统计摘要"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 今日统计
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN activity_type = 'BUY' THEN 1 ELSE 0 END) as buy_count,
            SUM(CASE WHEN activity_type = 'SELL' THEN 1 ELSE 0 END) as sell_count,
            SUM(CASE WHEN activity_type = 'BUY' THEN amount ELSE 0 END) as total_buy_amount,
            SUM(CASE WHEN activity_type = 'SELL' THEN amount ELSE 0 END) as total_sell_amount,
            SUM(CASE WHEN mainforce_type = 'institution' THEN 1 ELSE 0 END) as institution_count,
            SUM(CASE WHEN mainforce_type = 'hot_money' THEN 1 ELSE 0 END) as hot_money_count
        FROM mainforce_activities
        WHERE date = ?
    """, (today,))
    today_stats = cursor.fetchone()
    
    # 近7日统计
    cursor.execute("""
        SELECT 
            COUNT(*) as total_count,
            SUM(amount) as total_amount
        FROM mainforce_activities
        WHERE date >= date(?, '-7 days')
    """, (today,))
    week_stats = cursor.fetchone()
    
    # 活跃规则数
    cursor.execute("SELECT COUNT(*) FROM mainforce_alert_rules WHERE enabled = 1")
    active_rules = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "today": {
            "total_count": today_stats['total_count'] or 0,
            "buy_count": today_stats['buy_count'] or 0,
            "sell_count": today_stats['sell_count'] or 0,
            "total_buy_amount": today_stats['total_buy_amount'] or 0,
            "total_sell_amount": today_stats['total_sell_amount'] or 0,
            "net_flow": (today_stats['total_buy_amount'] or 0) - (today_stats['total_sell_amount'] or 0),
            "institution_count": today_stats['institution_count'] or 0,
            "hot_money_count": today_stats['hot_money_count'] or 0
        },
        "week": {
            "total_count": week_stats['total_count'] or 0,
            "total_amount": week_stats['total_amount'] or 0
        },
        "active_rules": active_rules
    }
