"""
审批流程数据模型
定义审批流程、节点、执行记录等数据结构
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """审批节点类型"""
    START = "start"
    END = "end"
    APPROVER = "approver"
    CONDITION = "condition"
    COPY = "copy"


class ApproverType(str, Enum):
    """审批人类型"""
    USER = "user"
    ROLE = "role"
    DEPARTMENT_HEAD = "department_head"
    MANAGER = "manager"


class ApprovalMode(str, Enum):
    """审批模式"""
    ALL = "all"
    ANY = "any"


class ApprovalAction(str, Enum):
    """审批操作"""
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"


class FlowStatus(str, Enum):
    """流程状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class NodeStatus(str, Enum):
    """节点状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    SKIPPED = "skipped"


class ConditionOperator(str, Enum):
    """条件操作符"""
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NE = "!="


class FlowTemplate(BaseModel):
    """审批流程模板"""
    id: str = Field(..., description="模板ID")
    name: str = Field(..., description="流程名称")
    description: Optional[str] = Field(None, description="流程描述")
    status: FlowStatus = Field(FlowStatus.DRAFT, description="状态")
    nodes: list = Field(default_factory=list, description="节点列表")
    edges: list = Field(default_factory=list, description="连线列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class FlowNode(BaseModel):
    """审批流程节点"""
    id: str = Field(..., description="节点ID")
    type: NodeType = Field(..., description="节点类型")
    label: str = Field(..., description="节点标签")
    x: float = Field(0, description="X坐标")
    y: float = Field(0, description="Y坐标")
    approver_type: Optional[ApproverType] = Field(None, description="审批人类型")
    approver_id: Optional[str] = Field(None, description="审批人ID")
    approver_name: Optional[str] = Field(None, description="审批人名称")
    approval_mode: Optional[ApprovalMode] = Field(ApprovalMode.ALL, description="审批模式")
    timeout_hours: Optional[int] = Field(None, description="审批时限")
    require_comment: bool = Field(False, description="是否必填审批意见")
    require_attachment: bool = Field(False, description="是否要求上传附件")
    condition_field: Optional[str] = Field(None, description="条件字段")
    condition_operator: Optional[ConditionOperator] = Field(None, description="条件操作符")
    condition_value: Optional[str] = Field(None, description="条件值")


class FlowEdge(BaseModel):
    """审批流程连线"""
    id: str = Field(..., description="连线ID")
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    label: Optional[str] = Field(None, description="连线标签")
    condition: Optional[str] = Field(None, description="条件表达式")


class FlowInstance(BaseModel):
    """审批流程实例"""
    id: str = Field(..., description="实例ID")
    template_id: str = Field(..., description="模板ID")
    template_name: str = Field(..., description="模板名称")
    title: str = Field(..., description="审批标题")
    applicant_id: str = Field(..., description="申请人ID")
    applicant_name: str = Field(..., description="申请人名称")
    status: str = Field("pending", description="状态")
    current_node_id: Optional[str] = Field(None, description="当前节点ID")
    form_data: dict = Field(default_factory=dict, description="表单数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class NodeInstance(BaseModel):
    """节点实例"""
    id: str = Field(..., description="实例ID")
    instance_id: str = Field(..., description="流程实例ID")
    node_id: str = Field(..., description="节点ID")
    node_label: str = Field(..., description="节点名称")
    node_type: NodeType = Field(..., description="节点类型")
    status: NodeStatus = Field(NodeStatus.PENDING, description="节点状态")
    assignee_id: Optional[str] = Field(None, description="当前审批人ID")
    assignee_name: Optional[str] = Field(None, description="当前审批人名称")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class ApprovalRecord(BaseModel):
    """审批记录"""
    id: str = Field(..., description="记录ID")
    instance_id: str = Field(..., description="流程实例ID")
    node_instance_id: str = Field(..., description="节点实例ID")
    node_label: str = Field(..., description="节点名称")
    approver_id: str = Field(..., description="审批人ID")
    approver_name: str = Field(..., description="审批人名称")
    action: ApprovalAction = Field(..., description="审批操作")
    comment: Optional[str] = Field(None, description="审批意见")
    attachment_url: Optional[str] = Field(None, description="附件URL")
    created_at: datetime = Field(default_factory=datetime.now, description="审批时间")


class ApprovalFormData(BaseModel):
    """审批表单数据"""
    template_id: str = Field(..., description="模板ID")
    title: str = Field(..., description="审批标题")
    form_data: dict = Field(default_factory=dict, description="表单数据")


class ApprovalActionRequest(BaseModel):
    """审批操作请求"""
    instance_id: str = Field(..., description="流程实例ID")
    node_instance_id: str = Field(..., description="节点实例ID")
    action: ApprovalAction = Field(..., description="审批操作")
    comment: Optional[str] = Field(None, description="审批意见")
    attachment_url: Optional[str] = Field(None, description="附件URL")
