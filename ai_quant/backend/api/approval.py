"""
审批流程API模块
提供审批流程模板管理、流程实例执行、审批操作等接口
数据存储使用MySQL数据库
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.approval_models import (
    ApprovalFormData,
    ApprovalActionRequest,
    ApprovalAction,
)
from core.db import connect, load_mysql_config, query_dict, execute
from infra.storage.logging_service import get_logger

logger = get_logger("approval")

router = APIRouter(prefix="/api/v1/approval", tags=["approval"])


def _get_conn():
    """获取数据库连接"""
    cfg = load_mysql_config()
    return connect(cfg)


def _ensure_default_template(conn):
    """确保默认审批模板存在"""
    existing = query_dict(conn, "SELECT id FROM trade_approval_template WHERE id = %s", ("template_001",))
    if not existing:
        nodes = [
            {"id": "node_start", "type": "start", "label": "开始", "x": 100, "y": 200},
            {"id": "node_approver_1", "type": "approver", "label": "风控经理审批", "x": 300, "y": 200,
             "approver_type": "role", "approver_id": "risk_manager", "approver_name": "风控经理"},
            {"id": "node_end", "type": "end", "label": "结束", "x": 500, "y": 200},
        ]
        edges = [
            {"id": "edge_1", "source": "node_start", "target": "node_approver_1"},
            {"id": "edge_2", "source": "node_approver_1", "target": "node_end"},
        ]
        execute(
            conn,
            """INSERT INTO trade_approval_template (id, name, description, status, nodes, edges)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ("template_001", "交易风控审批", "股票交易风控审批流程", "active",
             json.dumps(nodes, ensure_ascii=False), json.dumps(edges, ensure_ascii=False))
        )


class FlowTemplateCreate(BaseModel):
    """创建流程模板请求"""
    name: str
    description: Optional[str] = None


class FlowTemplateUpdate(BaseModel):
    """更新流程模板请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    nodes: Optional[list[dict]] = None
    edges: Optional[list[dict]] = None


@router.get("/templates")
def get_templates(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取审批流程模板列表"""
    conn = _get_conn()
    try:
        _ensure_default_template(conn)
        conditions = ["1=1"]
        params: list = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        where = " AND ".join(conditions)

        count_result = query_dict(
            conn,
            f"SELECT COUNT(*) as total FROM trade_approval_template WHERE {where}",
            tuple(params)
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = query_dict(
            conn,
            f"""SELECT * FROM trade_approval_template WHERE {where}
                ORDER BY updated_at DESC LIMIT %s OFFSET %s""",
            tuple(params + [page_size, offset])
        )

        items = []
        for row in rows:
            if row.get("nodes") and isinstance(row["nodes"], str):
                try:
                    row["nodes"] = json.loads(row["nodes"])
                except Exception:
                    row["nodes"] = []
            if row.get("edges") and isinstance(row["edges"], str):
                try:
                    row["edges"] = json.loads(row["edges"])
                except Exception:
                    row["edges"] = []
            for key in ("created_at", "updated_at"):
                if row.get(key):
                    row[key] = str(row[key])
            items.append(row)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error("获取审批流程模板列表失败", extra={"error": str(e)})
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()


@router.get("/templates/{template_id}")
def get_template(template_id: str) -> dict[str, Any]:
    """获取流程模板详情"""
    conn = _get_conn()
    try:
        rows = query_dict(conn, "SELECT * FROM trade_approval_template WHERE id = %s", (template_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="模板不存在")
        row = rows[0]
        if row.get("nodes") and isinstance(row["nodes"], str):
            try:
                row["nodes"] = json.loads(row["nodes"])
            except Exception:
                row["nodes"] = []
        if row.get("edges") and isinstance(row["edges"], str):
            try:
                row["edges"] = json.loads(row["edges"])
            except Exception:
                row["edges"] = []
        for key in ("created_at", "updated_at"):
            if row.get(key):
                row[key] = str(row[key])
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取流程模板详情失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取模板详情失败: {str(e)}")
    finally:
        conn.close()


@router.post("/templates")
def create_template(request: FlowTemplateCreate) -> dict[str, Any]:
    """创建流程模板"""
    conn = _get_conn()
    try:
        template_id = f"template_{uuid.uuid4().hex[:8]}"
        nodes = [
            {"id": "start", "type": "start", "label": "开始", "x": 100, "y": 200},
            {"id": "end", "type": "end", "label": "结束", "x": 500, "y": 200},
        ]
        edges = [
            {"id": "start_to_end", "source": "start", "target": "end"}
        ]
        execute(
            conn,
            """INSERT INTO trade_approval_template (id, name, description, status, nodes, edges)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (template_id, request.name, request.description, "draft",
             json.dumps(nodes, ensure_ascii=False), json.dumps(edges, ensure_ascii=False))
        )
        return {"id": template_id, "template": {
            "id": template_id, "name": request.name, "description": request.description,
            "status": "draft", "nodes": nodes, "edges": edges
        }}
    except Exception as e:
        logger.error("创建流程模板失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"创建模板失败: {str(e)}")
    finally:
        conn.close()


@router.put("/templates/{template_id}")
def update_template(template_id: str, request: FlowTemplateUpdate) -> dict[str, Any]:
    """更新流程模板"""
    conn = _get_conn()
    try:
        existing = query_dict(conn, "SELECT id FROM trade_approval_template WHERE id = %s", (template_id,))
        if not existing:
            raise HTTPException(status_code=404, detail="模板不存在")

        updates = []
        params: list = []
        if request.name is not None:
            updates.append("name = %s")
            params.append(request.name)
        if request.description is not None:
            updates.append("description = %s")
            params.append(request.description)
        if request.status is not None:
            updates.append("status = %s")
            params.append(request.status)
        if request.nodes is not None:
            updates.append("nodes = %s")
            params.append(json.dumps(request.nodes, ensure_ascii=False))
        if request.edges is not None:
            updates.append("edges = %s")
            params.append(json.dumps(request.edges, ensure_ascii=False))

        if updates:
            params.append(template_id)
            sql = f"UPDATE trade_approval_template SET {', '.join(updates)} WHERE id = %s"
            execute(conn, sql, tuple(params))

        return {"message": "更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新流程模板失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"更新模板失败: {str(e)}")
    finally:
        conn.close()


@router.delete("/templates/{template_id}")
def delete_template(template_id: str) -> dict[str, Any]:
    """删除流程模板"""
    conn = _get_conn()
    try:
        existing = query_dict(conn, "SELECT id FROM trade_approval_template WHERE id = %s", (template_id,))
        if not existing:
            raise HTTPException(status_code=404, detail="模板不存在")
        execute(conn, "DELETE FROM trade_approval_node_instance WHERE instance_id IN (SELECT id FROM trade_approval_instance WHERE template_id = %s)", (template_id,))
        execute(conn, "DELETE FROM trade_approval_record WHERE instance_id IN (SELECT id FROM trade_approval_instance WHERE template_id = %s)", (template_id,))
        execute(conn, "DELETE FROM trade_approval_instance WHERE template_id = %s", (template_id,))
        execute(conn, "DELETE FROM trade_approval_template WHERE id = %s", (template_id,))
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除流程模板失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"删除模板失败: {str(e)}")
    finally:
        conn.close()


@router.get("/instances")
def get_instances(
    status: Optional[str] = None,
    applicant_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取审批流程实例列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        if applicant_id:
            conditions.append("applicant_id = %s")
            params.append(applicant_id)
        where = " AND ".join(conditions)

        count_result = query_dict(
            conn,
            f"SELECT COUNT(*) as total FROM trade_approval_instance WHERE {where}",
            tuple(params)
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = query_dict(
            conn,
            f"""SELECT * FROM trade_approval_instance WHERE {where}
                ORDER BY created_at DESC LIMIT %s OFFSET %s""",
            tuple(params + [page_size, offset])
        )

        items = []
        for row in rows:
            if row.get("form_data") and isinstance(row["form_data"], str):
                try:
                    row["form_data"] = json.loads(row["form_data"])
                except Exception:
                    row["form_data"] = {}
            for key in ("created_at", "updated_at"):
                if row.get(key):
                    row[key] = str(row[key])
            items.append(row)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error("获取审批流程实例列表失败", extra={"error": str(e)})
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str) -> dict[str, Any]:
    """获取流程实例详情"""
    conn = _get_conn()
    try:
        instances = query_dict(conn, "SELECT * FROM trade_approval_instance WHERE id = %s", (instance_id,))
        if not instances:
            raise HTTPException(status_code=404, detail="实例不存在")
        instance = instances[0]
        if instance.get("form_data") and isinstance(instance["form_data"], str):
            try:
                instance["form_data"] = json.loads(instance["form_data"])
            except Exception:
                instance["form_data"] = {}
        for key in ("created_at", "updated_at"):
            if instance.get(key):
                instance[key] = str(instance[key])

        nodes = query_dict(
            conn,
            "SELECT * FROM trade_approval_node_instance WHERE instance_id = %s ORDER BY created_at",
            (instance_id,)
        )
        for node in nodes:
            for key in ("created_at", "completed_at"):
                if node.get(key):
                    node[key] = str(node[key])

        return {
            "instance": instance,
            "nodes": nodes
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取流程实例详情失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取实例详情失败: {str(e)}")
    finally:
        conn.close()


@router.post("/instances")
def create_instance(request: ApprovalFormData) -> dict[str, Any]:
    """发起审批流程"""
    conn = _get_conn()
    try:
        templates = query_dict(conn, "SELECT * FROM trade_approval_template WHERE id = %s", (request.template_id,))
        if not templates:
            raise HTTPException(status_code=404, detail="模板不存在")
        template = templates[0]
        if template.get("status") != "active":
            raise HTTPException(status_code=400, detail="模板未启用")

        instance_id = f"instance_{uuid.uuid4().hex[:8]}"
        form_data_json = json.dumps(request.form_data, ensure_ascii=False) if request.form_data else "{}"

        execute(
            conn,
            """INSERT INTO trade_approval_instance (id, template_id, template_name, title, applicant_id, applicant_name, status, form_data)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (instance_id, template["id"], template["name"], request.title,
             "current_user", "当前用户", "pending", form_data_json)
        )

        if template.get("nodes") and isinstance(template["nodes"], str):
            try:
                template_nodes = json.loads(template["nodes"])
            except Exception:
                template_nodes = []
        else:
            template_nodes = template.get("nodes", [])

        for node_def in template_nodes:
            if node_def.get("type") == "approver":
                node_instance_id = f"ni_{uuid.uuid4().hex[:8]}"
                execute(
                    conn,
                    """INSERT INTO trade_approval_node_instance
                       (id, instance_id, node_id, node_label, node_type, assignee_type, assignee_id, assignee_name, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (node_instance_id, instance_id, node_def.get("id", ""),
                     node_def.get("label", ""), node_def.get("type", "approver"),
                     node_def.get("approver_type"), node_def.get("approver_id"),
                     node_def.get("approver_name"), "pending")
                )

        return {"id": instance_id, "instance": {
            "id": instance_id, "template_id": template["id"],
            "template_name": template["name"], "title": request.title,
            "applicant_id": "current_user", "applicant_name": "当前用户",
            "status": "pending", "form_data": request.form_data
        }}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("发起审批流程失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"发起审批流程失败: {str(e)}")
    finally:
        conn.close()


@router.post("/instances/{instance_id}/approve")
def approve_instance(instance_id: str, request: ApprovalActionRequest) -> dict[str, Any]:
    """执行审批操作"""
    conn = _get_conn()
    try:
        instances = query_dict(conn, "SELECT * FROM trade_approval_instance WHERE id = %s", (instance_id,))
        if not instances:
            raise HTTPException(status_code=404, detail="实例不存在")
        instance = instances[0]
        if instance["status"] not in ("pending", "processing"):
            raise HTTPException(status_code=400, detail="流程已结束")

        nodes = query_dict(
            conn,
            "SELECT * FROM trade_approval_node_instance WHERE id = %s",
            (request.node_instance_id,)
        )
        if not nodes:
            raise HTTPException(status_code=404, detail="节点实例不存在")
        node_instance = nodes[0]

        record_id = f"record_{uuid.uuid4().hex[:8]}"
        execute(
            conn,
            """INSERT INTO trade_approval_record (record_id, instance_id, node_instance_id, node_label, approver_id, approver_name, action, comment, attachment_url)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (record_id, instance_id, request.node_instance_id, node_instance.get("node_label", ""),
             "current_user", "当前用户", request.action.value, request.comment, request.attachment_url)
        )

        if request.action == ApprovalAction.APPROVE:
            new_node_status = "approved"
            new_instance_status = "approved"
        elif request.action == ApprovalAction.REJECT:
            new_node_status = "rejected"
            new_instance_status = "rejected"
        elif request.action == ApprovalAction.RETURN:
            new_node_status = "returned"
            new_instance_status = "returned"
        else:
            new_node_status = "pending"
            new_instance_status = instance["status"]

        execute(
            conn,
            "UPDATE trade_approval_node_instance SET status = %s, completed_at = NOW() WHERE id = %s",
            (new_node_status, request.node_instance_id)
        )
        execute(
            conn,
            "UPDATE trade_approval_instance SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_instance_status, instance_id)
        )

        return {
            "instance": {"id": instance_id, "status": new_instance_status},
            "node_instance": {"id": request.node_instance_id, "status": new_node_status},
            "record": {"id": record_id, "action": request.action.value}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("执行审批操作失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"执行审批操作失败: {str(e)}")
    finally:
        conn.close()


@router.get("/records")
def get_records(
    instance_id: Optional[str] = None,
    approver_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取审批记录列表"""
    conn = _get_conn()
    try:
        conditions = ["1=1"]
        params: list = []
        if instance_id:
            conditions.append("instance_id = %s")
            params.append(instance_id)
        if approver_id:
            conditions.append("approver_id = %s")
            params.append(approver_id)
        where = " AND ".join(conditions)

        count_result = query_dict(
            conn,
            f"SELECT COUNT(*) as total FROM trade_approval_record WHERE {where}",
            tuple(params)
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        rows = query_dict(
            conn,
            f"""SELECT * FROM trade_approval_record WHERE {where}
                ORDER BY created_at DESC LIMIT %s OFFSET %s""",
            tuple(params + [page_size, offset])
        )

        items = []
        for row in rows:
            for key in ("created_at",):
                if row.get(key):
                    row[key] = str(row[key])
            items.append(row)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error("获取审批记录列表失败", extra={"error": str(e)})
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()


@router.get("/pending")
def get_pending_approvals(
    assignee_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取待审批任务列表"""
    conn = _get_conn()
    try:
        conditions = ["n.status = 'pending'"]
        params: list = []
        if assignee_id:
            conditions.append("n.assignee_id = %s")
            params.append(assignee_id)
        where = " AND ".join(conditions)

        count_result = query_dict(
            conn,
            f"""SELECT COUNT(*) as total FROM trade_approval_node_instance n WHERE {where}""",
            tuple(params)
        )
        total = count_result[0]["total"] if count_result else 0

        offset = (page - 1) * page_size
        node_rows = query_dict(
            conn,
            f"""SELECT n.* FROM trade_approval_node_instance n WHERE {where}
                ORDER BY n.created_at DESC LIMIT %s OFFSET %s""",
            tuple(params + [page_size, offset])
        )

        items = []
        for node in node_rows:
            for key in ("created_at", "completed_at"):
                if node.get(key):
                    node[key] = str(node[key])
            inst_id = node.get("instance_id")
            instance = None
            if inst_id:
                inst_rows = query_dict(conn, "SELECT * FROM trade_approval_instance WHERE id = %s", (inst_id,))
                if inst_rows:
                    instance = inst_rows[0]
                    if instance.get("form_data") and isinstance(instance["form_data"], str):
                        try:
                            instance["form_data"] = json.loads(instance["form_data"])
                        except Exception:
                            instance["form_data"] = {}
                    for key in ("created_at", "updated_at"):
                        if instance.get(key):
                            instance[key] = str(instance[key])
            items.append({
                "node_instance": node,
                "instance": instance
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        logger.error("获取待审批任务列表失败", extra={"error": str(e)})
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    finally:
        conn.close()


# ============ 审批流程默认配置 ============

@router.get("/config")
def get_approval_config() -> dict[str, Any]:
    """
    获取审批流程的默认配置模板。

    返回审批流程设计器的默认节点配置、条件字段、操作符
    和阈值设置等默认值。

    Returns:
        dict: 包含默认配置的字典
    """
    logger.info("审批流程默认配置查询")

    return {
        "default_nodes": [
            {
                "id": "node_start",
                "type": "start",
                "label": "开始",
                "x": 100,
                "y": 200,
            },
            {
                "id": "node_approver_1",
                "type": "approver",
                "label": "风控经理审批",
                "x": 300,
                "y": 200,
                "approver_type": "role",
                "approver_id": "risk_manager",
                "approver_name": "风控经理",
            },
            {
                "id": "node_end",
                "type": "end",
                "label": "结束",
                "x": 500,
                "y": 200,
            },
        ],
        "default_edges": [
            {"id": "edge_1", "source": "node_start", "target": "node_approver_1"},
            {"id": "edge_2", "source": "node_approver_1", "target": "node_end"},
        ],
        "condition_fields": [
            {"key": "amount", "label": "成交金额", "unit": "元", "type": "number"},
            {"key": "volume", "label": "成交量", "unit": "股", "type": "number"},
            {"key": "price", "label": "价格", "unit": "元", "type": "number"},
            {"key": "stock_code", "label": "股票代码", "type": "string"},
            {"key": "side", "label": "买卖方向", "type": "enum",
             "options": [{"value": "buy", "label": "买入"}, {"value": "sell", "label": "卖出"}]},
            {"key": "position_pct", "label": "持仓占比", "unit": "%", "type": "number"},
            {"key": "total_amount", "label": "累计成交额", "unit": "元", "type": "number"},
        ],
        "operators": [
            {"value": "gt", "label": "大于"},
            {"value": "gte", "label": "大于等于"},
            {"value": "lt", "label": "小于"},
            {"value": "lte", "label": "小于等于"},
            {"value": "eq", "label": "等于"},
            {"value": "neq", "label": "不等于"},
            {"value": "in", "label": "包含"},
            {"value": "not_in", "label": "不包含"},
        ],
        "default_thresholds": {
            "amount": 1000000,
            "volume": 10000,
            "price": 50,
            "position_pct": 10,
            "total_amount": 5000000,
        },
        "approver_roles": [
            {"id": "risk_manager", "name": "风控经理"},
            {"id": "ceo", "name": "总经理"},
            {"id": "trader", "name": "交易员"},
            {"id": "compliance", "name": "合规专员"},
        ],
        "flow_settings": {
            "max_nodes": 20,
            "max_edges": 30,
            "support_parallel": True,
            "support_condition": True,
            "default_logic": "AND",
        },
    }
