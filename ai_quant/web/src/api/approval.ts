// 审批流程 API 客户端

import {
  FlowTemplate,
  FlowInstance,
  ApprovalRecord,
  PendingTask,
  InstanceDetail,
  PaginatedResponse,
  CreateFlowTemplateRequest,
  UpdateFlowTemplateRequest,
  CreateApprovalRequest,
  ApprovalActionRequest,
} from '../types/approval';

const API_BASE = '/api/v1/approval';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

// 流程模板 API
export const flowTemplateApi = {
  // 获取模板列表
  async getTemplates(params?: {
    status?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<FlowTemplate>> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));

    const url = `${API_BASE}/templates${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
    const response = await fetch(url);
    return handleResponse<PaginatedResponse<FlowTemplate>>(response);
  },

  // 获取模板详情
  async getTemplate(templateId: string): Promise<FlowTemplate> {
    const response = await fetch(`${API_BASE}/templates/${templateId}`);
    return handleResponse<FlowTemplate>(response);
  },

  // 创建模板
  async createTemplate(data: CreateFlowTemplateRequest): Promise<{ id: string; template: FlowTemplate }> {
    const response = await fetch(`${API_BASE}/templates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  // 更新模板
  async updateTemplate(
    templateId: string,
    data: UpdateFlowTemplateRequest
  ): Promise<{ template: FlowTemplate }> {
    const response = await fetch(`${API_BASE}/templates/${templateId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  // 删除模板
  async deleteTemplate(templateId: string): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/templates/${templateId}`, {
      method: 'DELETE',
    });
    return handleResponse(response);
  },

  // 复制模板
  async copyTemplate(templateId: string): Promise<{ id: string; template: FlowTemplate }> {
    const response = await fetch(`${API_BASE}/templates/${templateId}/copy`, {
      method: 'POST',
    });
    return handleResponse(response);
  },
};

// 流程实例 API
export const flowInstanceApi = {
  // 获取实例列表
  async getInstances(params?: {
    status?: string;
    applicant_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<FlowInstance>> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.applicant_id) searchParams.set('applicant_id', params.applicant_id);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));

    const url = `${API_BASE}/instances${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
    const response = await fetch(url);
    return handleResponse<PaginatedResponse<FlowInstance>>(response);
  },

  // 获取实例详情
  async getInstance(instanceId: string): Promise<InstanceDetail> {
    const response = await fetch(`${API_BASE}/instances/${instanceId}`);
    return handleResponse<InstanceDetail>(response);
  },

  // 发起审批
  async createInstance(data: CreateApprovalRequest): Promise<{ id: string; instance: FlowInstance }> {
    const response = await fetch(`${API_BASE}/instances`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  // 执行审批操作
  async approveInstance(
    instanceId: string,
    data: ApprovalActionRequest
  ): Promise<{
    instance: FlowInstance;
    node_instance: any;
    record: ApprovalRecord;
  }> {
    const response = await fetch(`${API_BASE}/instances/${instanceId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },
};

// 审批记录 API
export const approvalRecordApi = {
  // 获取审批记录列表
  async getRecords(params?: {
    instance_id?: string;
    approver_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<ApprovalRecord>> {
    const searchParams = new URLSearchParams();
    if (params?.instance_id) searchParams.set('instance_id', params.instance_id);
    if (params?.approver_id) searchParams.set('approver_id', params.approver_id);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));

    const url = `${API_BASE}/records${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
    const response = await fetch(url);
    return handleResponse<PaginatedResponse<ApprovalRecord>>(response);
  },
};

// 待审批任务 API
export const pendingTaskApi = {
  // 获取待审批任务
  async getPendingTasks(params?: {
    assignee_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<PendingTask>> {
    const searchParams = new URLSearchParams();
    if (params?.assignee_id) searchParams.set('assignee_id', params.assignee_id);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));

    const url = `${API_BASE}/pending${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
    const response = await fetch(url);
    return handleResponse<PaginatedResponse<PendingTask>>(response);
  },
};
