// 审批流程相关类型定义

// 节点类型
export type NodeType = 'start' | 'end' | 'approver' | 'condition' | 'copy';

// 审批人类型
export type ApproverType = 'user' | 'role' | 'department_head' | 'manager';

// 审批模式
export type ApprovalMode = 'all' | 'any';

// 审批操作
export type ApprovalAction = 'approve' | 'reject' | 'return';

// 流程状态
export type FlowStatus = 'draft' | 'active' | 'inactive';

// 节点状态
export type NodeStatus = 'pending' | 'approved' | 'rejected' | 'returned' | 'skipped';

// 条件操作符
export type ConditionOperator = '>' | '>=' | '<' | '<=' | '==' | '!=';

// 审批流程节点
export interface FlowNode {
  id: string;
  type: NodeType;
  label: string;
  x: number;
  y: number;

  // 审批节点特有属性
  approver_type?: ApproverType;
  approver_id?: string;
  approver_name?: string;
  approval_mode?: ApprovalMode;
  timeout_hours?: number;
  require_comment?: boolean;
  require_attachment?: boolean;

  // 条件节点特有属性
  condition_field?: string;
  condition_operator?: ConditionOperator;
  condition_value?: string;
}

// 审批流程连线
export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string;
}

// 审批流程模板
export interface FlowTemplate {
  id: string;
  name: string;
  description?: string;
  status: FlowStatus;
  nodes: FlowNode[];
  edges: FlowEdge[];
  created_at: string;
  updated_at: string;
}

// 流程实例
export interface FlowInstance {
  id: string;
  template_id: string;
  template_name: string;
  title: string;
  applicant_id: string;
  applicant_name: string;
  status: string;
  current_node_id?: string;
  form_data: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// 节点实例
export interface NodeInstance {
  id: string;
  instance_id: string;
  node_id: string;
  node_label: string;
  node_type: NodeType;
  status: NodeStatus;
  assignee_id?: string;
  assignee_name?: string;
  created_at: string;
  completed_at?: string;
}

// 审批记录
export interface ApprovalRecord {
  id: string;
  instance_id: string;
  node_instance_id: string;
  node_label: string;
  approver_id: string;
  approver_name: string;
  action: ApprovalAction;
  comment?: string;
  attachment_url?: string;
  created_at: string;
}

// API 响应类型
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// 创建流程模板请求
export interface CreateFlowTemplateRequest {
  name: string;
  description?: string;
}

// 更新流程模板请求
export interface UpdateFlowTemplateRequest {
  name?: string;
  description?: string;
  status?: FlowStatus;
  nodes?: FlowNode[];
  edges?: FlowEdge[];
}

// 发起审批请求
export interface CreateApprovalRequest {
  template_id: string;
  title: string;
  form_data: Record<string, any>;
}

// 审批操作请求
export interface ApprovalActionRequest {
  instance_id: string;
  node_instance_id: string;
  action: ApprovalAction;
  comment?: string;
  attachment_url?: string;
}

// 待审批任务
export interface PendingTask {
  node_instance: NodeInstance;
  instance: FlowInstance;
}

// 流程实例详情
export interface InstanceDetail {
  instance: FlowInstance;
  nodes: NodeInstance[];
}

// 图表节点（用于可视化）
export interface ChartNode extends FlowNode {
  width?: number;
  height?: number;
}

// 图表边（用于可视化）
export interface ChartEdge extends FlowEdge {
  sourceX?: number;
  sourceY?: number;
  targetX?: number;
  targetY?: number;
}
