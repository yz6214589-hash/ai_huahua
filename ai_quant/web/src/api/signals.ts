import { fetchJson, postJson } from './client'

export interface SignalItem {
  id: string
  stock_code: string
  stock_name: string
  signal_type: string
  strength: number
  score: number
  macd?: number
  rsi?: number
  ma20?: number
  close: number
  reason: string
  trade_date: string
  created_at: string
}

export interface SignalRule {
  id: string
  name: string
  description?: string
  conditions?: any[]
  logic?: string
  enabled: boolean
  priority?: number
  created_at?: string
  updated_at?: string
}

export interface SignalListResponse {
  items: SignalItem[]
  total: number
  page: number
  page_size: number
}

export interface SignalGenerateRequest {
  stock_codes?: string[]
  start_date?: string
  end_date?: string
  use_rules?: boolean
}

export async function getSignals(params?: {
  signal_type?: string
  strength_min?: number
  keyword?: string
  stock_code?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}): Promise<SignalListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.signal_type) searchParams.set('signal_type', params.signal_type)
  if (params?.strength_min) searchParams.set('strength_min', String(params.strength_min))
  if (params?.keyword) searchParams.set('keyword', params.keyword)
  if (params?.stock_code) searchParams.set('stock_code', params.stock_code)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  const qs = searchParams.toString()
  return fetchJson<SignalListResponse>(`/api/v1/signals${qs ? '?' + qs : ''}`)
}

export async function getSignalRules(): Promise<SignalRule[]> {
  return fetchJson<SignalRule[]>('/api/v1/signals/rules')
}

export async function createSignalRule(rule: {
  name: string
  description?: string
  conditions?: any[]
  logic?: string
  enabled?: boolean
}): Promise<{ id: string }> {
  return postJson('/api/v1/signals/rules', rule)
}

export async function updateSignalRule(ruleId: string, rule: {
  name: string
  description?: string
  conditions?: any[]
  logic?: string
  enabled?: boolean
}): Promise<any> {
  return fetchJson(`/api/v1/signals/rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(rule),
  })
}

export async function deleteSignalRule(ruleId: string): Promise<any> {
  return fetchJson(`/api/v1/signals/rules/${ruleId}`, { method: 'DELETE' })
}

export async function generateSignals(request: SignalGenerateRequest): Promise<any> {
  return postJson('/api/v1/signals/generate', request)
}
