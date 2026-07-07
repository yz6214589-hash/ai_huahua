import { fetchJson, postJson } from '@/api/client'

export interface AdminResponse<T> {
  ok: boolean
  data?: T
  error?: string
}

// ===== 模型管理 =====

export interface ModelConfig {
  id: string
  name: string
  provider: string
  model_name: string
  api_key_ref: string
  base_url: string
  status: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ModelCreate {
  name: string
  provider: string
  model_name: string
  api_key_ref?: string
  base_url?: string
  sort_order?: number
}

// ===== 工具与技能 =====

export interface ToolItem {
  name: string
  category: string
  type?: string
  enabled: boolean
  description: string
  title?: string
  tags?: string[]
}

export interface ToolDetail extends ToolItem {
  config: Record<string, any>
  input_schema?: Record<string, any>
}

// ===== 提示词管理 =====

export interface PromptTemplate {
  id: string
  category: string
  name: string
  content: string
  version: number
  variables: string[]
  created_at: string
  updated_at: string
}

export interface PromptVersion {
  version: number
  content: string
  created_at: string
}

export interface PromptCreate {
  category: string
  name: string
  content: string
  variables?: string[]
}

export interface ApiKeyItem {
  id: string
  name: string
  provider: string
  key_type: string
  key_prefix: string
  status: string
  created_at: string
  updated_at: string
}

export interface ApiKeyCreate {
  name: string
  provider: string
  key_type: string
  plain_key: string
}

export interface ConversationStats {
  total: number
  feishu_private: number
  feishu_group: number
  system: number
}

export interface ConversationItem {
  id: string
  title: string
  source: string
  message_count: number
  last_message_time: string
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

const BASE = '/api/v1/admin'

export async function fetchApiKeys(): Promise<ApiKeyItem[]> {
  return fetchJson<ApiKeyItem[]>(`${BASE}/api-keys`)
}

export async function createApiKey(data: ApiKeyCreate): Promise<ApiKeyItem> {
  return postJson<ApiKeyItem>(`${BASE}/api-keys`, data)
}

export async function updateApiKey(id: string, data: Partial<ApiKeyCreate>): Promise<ApiKeyItem> {
  return fetchJson<ApiKeyItem>(`${BASE}/api-keys/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteApiKey(id: string): Promise<void> {
  await fetchJson<void>(`${BASE}/api-keys/${id}`, { method: 'DELETE' })
}

export async function testApiKey(id: string): Promise<{ ok: boolean; message: string }> {
  return postJson<{ ok: boolean; message: string }>(`${BASE}/api-keys/${id}/test`, {})
}

export async function testAllApiKeys(): Promise<{ ok: boolean; message: string }> {
  return postJson<{ ok: boolean; message: string }>(`${BASE}/api-keys/test-all`, {})
}

export async function fetchConversations(
  params?: { search?: string; source?: string; page?: number }
): Promise<PaginatedResponse<ConversationItem>> {
  const query = new URLSearchParams()
  if (params?.search) query.set('search', params.search)
  if (params?.source) query.set('source', params.source)
  if (params?.page) query.set('page', String(params.page))
  const qs = query.toString()
  const res = await fetchJson<AdminResponse<PaginatedResponse<ConversationItem>>>(`${BASE}/conversations${qs ? '?' + qs : ''}`)
  // 后端返回 {"ok": true, "data": {...}}，需要解包
  return res.data ?? (res as unknown as PaginatedResponse<ConversationItem>)
}

export async function fetchConversationStats(): Promise<ConversationStats> {
  const res = await fetchJson<AdminResponse<{ total_conversations: number; total_messages: number; feishu_private: number; feishu_group: number; system: number }>>(`${BASE}/conversations/stats`)
  // 后端返回 {"ok": true, "data": {"total_conversations": ..., ...}}，需要解包并映射字段
  const raw = res.data ?? (res as any)
  return {
    total: raw.total_conversations ?? raw.total ?? 0,
    feishu_private: raw.feishu_private ?? 0,
    feishu_group: raw.feishu_group ?? 0,
    system: raw.system ?? 0,
  }
}

export interface ConversationDetail {
  id: string
  title: string
  source: string
  created_at: string
  updated_at: string
  messages: {
    id: string
    role: string
    content: string
    metadata: Record<string, any>
    created_at: string
  }[]
  messages_total?: number
  messages_page?: number
  messages_page_size?: number
}

export async function fetchConversationDetail(
  convId: string,
  page: number = 1,
  pageSize: number = 50
): Promise<ConversationDetail> {
  const res = await fetchJson<AdminResponse<ConversationDetail>>(
    `${BASE}/conversations/${convId}?page=${page}&page_size=${pageSize}`
  )
  return res.data ?? (res as unknown as ConversationDetail)
}

export async function updateConversationTitle(convId: string, title: string): Promise<{id: string; title: string}> {
  const res = await fetchJson<AdminResponse<{id: string; title: string}>>(
    `${BASE}/conversations/${convId}/title`,
    {
      method: 'PUT',
      body: JSON.stringify({ title }),
    }
  )
  return res.data ?? (res as unknown as {id: string; title: string})
}

// ===== 模型管理 API =====

export async function fetchModels(): Promise<ModelConfig[]> {
  const res = await fetchJson<AdminResponse<ModelConfig[]>>(`${BASE}/models`)
  return res.data ?? (res as unknown as ModelConfig[])
}

export async function createModel(data: ModelCreate): Promise<ModelConfig> {
  return postJson<ModelConfig>(`${BASE}/models`, data)
}

export async function updateModel(id: string, data: Partial<ModelCreate>): Promise<ModelConfig> {
  return fetchJson<ModelConfig>(`${BASE}/models/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteModel(id: string): Promise<void> {
  await fetchJson<void>(`${BASE}/models/${id}`, { method: 'DELETE' })
}

export async function testModel(id: string): Promise<{ ok: boolean; message: string }> {
  return postJson<{ ok: boolean; message: string }>(`${BASE}/models/${id}/test`, {})
}

export async function toggleModelStatus(id: string, status: string): Promise<ModelConfig> {
  return fetchJson<ModelConfig>(`${BASE}/models/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  })
}

// ===== 工具与技能 API =====

export async function fetchTools(): Promise<ToolItem[]> {
  const res = await fetchJson<AdminResponse<ToolItem[]>>(`${BASE}/tools`)
  return res.data ?? (res as unknown as ToolItem[])
}

export async function toggleTool(name: string, enabled: boolean): Promise<void> {
  await fetchJson<void>(`${BASE}/tools/${name}`, {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export async function fetchToolDetail(name: string): Promise<ToolDetail> {
  return fetchJson<ToolDetail>(`${BASE}/tools/${name}`)
}

export async function updateToolConfig(name: string, config: Record<string, any>): Promise<void> {
  await fetchJson<void>(`${BASE}/tools/${name}/config`, {
    method: 'PUT',
    body: JSON.stringify({ config }),
  })
}

// ===== 提示词管理 API =====

export async function fetchPrompts(): Promise<PromptTemplate[]> {
  return fetchJson<PromptTemplate[]>(`${BASE}/prompts`)
}

export async function createPrompt(data: PromptCreate): Promise<PromptTemplate> {
  return postJson<PromptTemplate>(`${BASE}/prompts`, data)
}

export async function updatePrompt(id: string, data: Partial<PromptCreate>): Promise<PromptTemplate> {
  return fetchJson<PromptTemplate>(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function fetchPromptDetail(id: string): Promise<PromptTemplate> {
  return fetchJson<PromptTemplate>(`${BASE}/prompts/${id}`)
}

export async function fetchPromptVersions(id: string): Promise<PromptVersion[]> {
  return fetchJson<PromptVersion[]>(`${BASE}/prompts/${id}/versions`)
}

export async function rollbackPrompt(id: string, version: number): Promise<PromptTemplate> {
  return postJson<PromptTemplate>(`${BASE}/prompts/${id}/rollback`, { version })
}

// ===== 智能体配置 =====

export interface AgentConfig {
  id: string;
  role: string;
  name: string;
  description: string;
  model_id: string;
  model_name?: string;
  skills: string[];
  tools: string[];
  prompt_id: string;
  prompt_name?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  role: string;
  name: string;
  description: string;
  model_id?: string;
  skills?: string[];
  tools?: string[];
  prompt_id?: string;
}

export interface AgentDefault {
  role: string;
  name: string;
  description: string;
  color: string;
}

export async function fetchAgents(): Promise<AgentConfig[]> {
  const res = await fetchJson<AdminResponse<AgentConfig[]>>(`${BASE}/agents`)
  return res.data ?? (res as unknown as AgentConfig[])
}

export async function createAgent(data: AgentCreate): Promise<AgentConfig> {
  return postJson<AgentConfig>(`${BASE}/agents`, data)
}

export async function updateAgent(id: string, data: Partial<AgentCreate>): Promise<AgentConfig> {
  const res = await fetchJson<AdminResponse<AgentConfig>>(`${BASE}/agents/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
  return res.data ?? (res as unknown as AgentConfig)
}

export async function deleteAgent(id: string): Promise<void> {
  await fetchJson<void>(`${BASE}/agents/${id}`, { method: 'DELETE' })
}

export async function fetchAgentDefaults(): Promise<AgentDefault[]> {
  const res = await fetchJson<AdminResponse<AgentDefault[]>>(`${BASE}/agents/defaults`)
  return res.data ?? (res as unknown as AgentDefault[])
}

// ===== 飞书集成 =====

export interface FeishuConfig {
  app_id: string;
  app_secret_mask: string;
  ws_url: string;
  status: string;
}

export interface FeishuStatus {
  bot_status: string;
  today_messages: number;
  active_sessions: number;
  connection_duration: string;
  last_connect_time: string;
}

export async function fetchFeishuConfig(): Promise<FeishuConfig> {
  return fetchJson<FeishuConfig>(`${BASE}/feishu/config`)
}

export async function updateFeishuConfig(data: {app_id?: string; app_secret?: string; ws_url?: string}): Promise<FeishuConfig> {
  return fetchJson<FeishuConfig>(`${BASE}/feishu/config`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function fetchFeishuStatus(): Promise<FeishuStatus> {
  return fetchJson<FeishuStatus>(`${BASE}/feishu/status`)
}

export async function testFeishuConnection(): Promise<{ok: boolean; message: string}> {
  return postJson<{ok: boolean; message: string}>(`${BASE}/feishu/test`, {})
}

export async function reconnectFeishu(): Promise<{ok: boolean; message: string}> {
  return postJson<{ok: boolean; message: string}>(`${BASE}/feishu/reconnect`, {})
}

// ===== 系统配置 =====

export interface SystemSettings {
  app_name: string;
  log_dir: string;
  log_max_bytes: number;
  log_backup_count: number;
  task_timeout: number;
  llm_timeout: number;
  report_output_dir: string;
  checkpoint_dir: string;
  [key: string]: string | number;
}

export async function fetchSystemSettings(): Promise<SystemSettings> {
  return fetchJson<SystemSettings>(`${BASE}/settings`)
}

export async function updateSystemSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
  return fetchJson<SystemSettings>(`${BASE}/settings`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

// ===== 日志与监控 =====

export interface MonitorStatus {
  service_status: string;
  feishu_status: string;
  today_api_calls: number;
  today_messages: number;
}

export interface LogEntry {
  time: string;
  level: string;
  module: string;
  message: string;
}

export async function fetchMonitorStatus(): Promise<MonitorStatus> {
  return fetchJson<MonitorStatus>(`${BASE}/monitor/status`)
}

export async function fetchLogs(level?: string, page?: number): Promise<{items: LogEntry[], total: number}> {
  const query = new URLSearchParams()
  if (level) query.set('level', level)
  if (page) query.set('page', String(page))
  const qs = query.toString()
  return fetchJson<{items: LogEntry[], total: number}>(`${BASE}/monitor/logs${qs ? '?' + qs : ''}`)
}

// ===== 定时任务 =====

export interface ScheduledTask {
  id: string;
  name: string;
  task_type: string;
  cron_expr: string;
  enabled: boolean;
  last_run_time: string;
  last_run_status: string;
  created_at: string;
}

export interface TaskLog {
  id: string;
  task_id: string;
  status: string;
  started_at: string;
  finished_at: string;
  result: string;
  error_message: string;
}

export async function fetchScheduledTasks(): Promise<ScheduledTask[]> {
  return fetchJson<ScheduledTask[]>(`${BASE}/scheduled-tasks`)
}

export async function createScheduledTask(data: {name: string, task_type: string, cron_expr: string}): Promise<ScheduledTask> {
  return postJson<ScheduledTask>(`${BASE}/scheduled-tasks`, data)
}

export async function updateScheduledTask(id: string, data: Partial<ScheduledTask>): Promise<ScheduledTask> {
  return fetchJson<ScheduledTask>(`${BASE}/scheduled-tasks/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteScheduledTask(id: string): Promise<void> {
  await fetchJson<void>(`${BASE}/scheduled-tasks/${id}`, { method: 'DELETE' })
}

export async function runTaskNow(id: string): Promise<{ok: boolean, message: string}> {
  return postJson<{ok: boolean, message: string}>(`${BASE}/scheduled-tasks/${id}/run`, {})
}

export async function fetchTaskLogs(id: string): Promise<TaskLog[]> {
  return fetchJson<TaskLog[]>(`${BASE}/scheduled-tasks/${id}/logs`)
}
