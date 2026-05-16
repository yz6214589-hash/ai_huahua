"""
审批流程API模块
提供审批流程模板管理、流程实例执行、审批操作等接口
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.approval_models import (
    FlowTemplate,
    FlowInstance,
    NodeInstance,
    ApprovalRecord,
    ApprovalFormData,
    ApprovalActionRequest,
    FlowStatus,
    NodeStatus,
    ApprovalAction,
    NodeType,
    FlowNode,
    FlowEdge,
)
from infra.storage.logging_service import get_logger

logger = get_logger("approval")

router = APIRouter(prefix="/api/v1/approval", tags=["approval"])

flow_templates: dict[str, FlowTemplate] = {}
flow_instances: dict[str, FlowInstance] = {}
node_instances: dict[str, NodeInstance] = {}
approval_records: list[ApprovalRecord] = []

_init_sample_templates()


def _init_sample_templates():
    """初始化示例流程模板"""
    sample_template = FlowTemplate(
        id="template_001",
        name="交易风控审批",
        description="股票交易风控审批流程",
        status=FlowStatus.ACTIVE,
        nodes=[
            FlowNode(id="node_start", type=NodeType.START, label="开始", x=100, y=200),
            FlowNode(id="node_approver_1", type=NodeType.APPROVER, label="风控经理审批", x=300, y=200,
                    approver_type="role", approver_id="risk_manager", approver_name="风控经理"),
            FlowNode(id="node_end", type=NodeType.END, label="结束", x=500, y=200),
        ],
        edges=[
            FlowEdge(id="edge_1", source="node_start", target="node_approver_1"),
            FlowEdge(id="edge_2", source="node_approver_1", target="node_end"),
        ]
    )
    flow_templates[sample_template.id] = sample_template


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
    templates = list(flow_templates.values())
    if status:
        templates = [t for t in templates if t.status.value == status]
    templates.sort(key=lambda x: x.updated_at, reverse=True)
    total = len(templates)
    start = (page - 1) * page_size
    end = start + page_size
    items = templates[start:end]
    return {
        "items": [t.model_dump() for t in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/templates/{template_id}")
def get_template(template_id: str) -> dict[str, Any]:
    """获取流程模板详情"""
    if template_id not in flow_templates:
        raise HTTPException(status_code=404, detail="模板不存在")
    return flow_templates[template_id].model_dump()


@router.post("/templates")
def create_template(request: FlowTemplateCreate) -> dict[str, Any]:
    """创建流程模板"""
    template_id = f"template_{uuid.uuid4().hex[:8]}"
    template = FlowTemplate(
        id=template_id,
        name=request.name,
        description=request.description,
        status=FlowStatus.DRAFT,
        nodes=[
            FlowNode(id="start", type=NodeType.START, label="开始", x=100, y=200),
            FlowNode(id="end", type=NodeType.END, label="结束", x=500, y=200),
        ],
        edges=[
            FlowEdge(id="start_to_end", source="start", target="end")
        ]
    )
    flow_templates[template_id] = template
    return {"id": template_id, "template": template.model_dump()}


@router.put("/templates/{template_id}")
def update_template(template_id: str, request: FlowTemplateUpdate) -> dict[str, Any]:
    """更新流程模板"""
    if template_id not in flow_templates:
        raise HTTPException(status_code=404, detail="模板不存在")
    template = flow_templates[template_id]
    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description
    if request.status is not None:
        template.status = FlowStatus(request.status)
    template.updated_at = datetime.now()
    return {"template": template.model_dump()}


@router.delete("/templates/{template_id}")
def delete_template(template_id: str) -> dict[str, Any]:
    """删除流程模板"""
    if template_id not in flow_templates:
        raise HTTPException(status_code=404, detail="模板不存在")
    del flow_templates[template_id]
    return {"message": "删除成功"}


@router.get("/instances")
def get_instances(
    status: Optional[str] = None,
    applicant_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取审批流程实例列表"""
    instances = list(flow_instances.values())
    if status:
        instances = [i for i in instances if i.status == status]
    if applicant_id:
        instances = [i for i in instances if i.applicant_id == applicant_id]
    instances.sort(key=lambda x: x.created_at, reverse=True)
    total = len(instances)
    start = (page - 1) * page_size
    end = start + page_size
    items = instances[start:end]
    return {
        "items": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str) -> dict[str, Any]:
    """获取流程实例详情"""
    if instance_id not in flow_instances:
        raise HTTPException(status_code=404, detail="实例不存在")
    instance = flow_instances[instance_id]
    nodes = get_instance_nodes(instance_id)
    return {
        "instance": instance.model_dump(),
        "nodes": nodes
    }


def get_instance_nodes(instance_id: str) -> list[dict]:
    """获取实例的节点列表"""
    nodes = [n for n in node_instances.values() if n.instance_id == instance_id]
    nodes.sort(key=lambda x: x.created_at)
    return [n.model_dump() for n in nodes]


@router.post("/instances")
def create_instance(request: ApprovalFormData) -> dict[str, Any]:
    """发起审批流程"""
    if request.template_id not in flow_templates:
        raise HTTPException(status_code=404, detail="模板不存在")
    template = flow_templates[request.template_id]
    if template.status != FlowStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="模板未启用")
    instance_id = f"instance_{uuid.uuid4().hex[:8]}"
    instance = FlowInstance(
        id=instance_id,
        template_id=template.id,
        template_name=template.name,
        title=request.title,
        applicant_id="current_user",
        applicant_name="当前用户",
        status="pending",
        form_data=request.form_data
    )
    flow_instances[instance_id] = instance
    return {"id": instance_id, "instance": instance.model_dump()}


@router.post("/instances/{instance_id}/approve")
def approve_instance(instance_id: str, request: ApprovalActionRequest) -> dict[str, Any]:
    """执行审批操作"""
    if instance_id not in flow_instances:
        raise HTTPException(status_code=404, detail="实例不存在")
    instance = flow_instances[instance_id]
    if instance.status not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail="流程已结束")
    if request.node_instance_id not in node_instances:
        raise HTTPException(status_code=404, detail="节点实例不存在")
    node_instance = node_instances[request.node_instance_id]
    record = ApprovalRecord(
        id=f"record_{uuid.uuid4().hex[:8]}",
        instance_id=instance_id,
        node_instance_id=request.node_instance_id,
        node_label=node_instance.node_label,
        approver_id="current_user",
        approver_name="当前用户",
        action=request.action,
        comment=request.comment,
        attachment_url=request.attachment_url
    )
    approval_records.append(record)
    if request.action == ApprovalAction.APPROVE:
        node_instance.status = NodeStatus.APPROVED
        instance.status = "approved"
    elif request.action == ApprovalAction.REJECT:
        node_instance.status = NodeStatus.REJECTED
        instance.status = "rejected"
    elif request.action == ApprovalAction.RETURN:
        node_instance.status = NodeStatus.RETURNED
        instance.status = "returned"
    node_instance.completed_at = datetime.now()
    instance.updated_at = datetime.now()
    return {
        "instance": instance.model_dump(),
        "node_instance": node_instance.model_dump(),
        "record": record.model_dump()
    }


@router.get("/records")
def get_records(
    instance_id: Optional[str] = None,
    approver_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取审批记录列表"""
    records = approval_records
    if instance_id:
        records = [r for r in records if r.instance_id == instance_id]
    if approver_id:
        records = [r for r in records if r.approver_id == approver_id]
    records.sort(key=lambda x: x.created_at, reverse=True)
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    items = records[start:end]
    return {
        "items": [r.model_dump() for r in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/pending")
def get_pending_approvals(
    assignee_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> dict[str, Any]:
    """获取待审批任务列表"""
    pending_nodes = [
        n for n in node_instances.values()
        if n.status == NodeStatus.PENDING
        and (assignee_id is None or n.assignee_id == assignee_id)
    ]
    pending_nodes.sort(key=lambda x: x.created_at, reverse=True)
    total = len(pending_nodes)
    start = (page - 1) * page_size
    end = start + page_size
    items = pending_nodes[start:end]
    result = []
    for node in items:
        instance = flow_instances.get(node.instance_id)
        if instance:
            result.append({
                "node_instance": node.model_dump(),
                "instance": instance.model_dump()
            })
    return {
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size
    }
