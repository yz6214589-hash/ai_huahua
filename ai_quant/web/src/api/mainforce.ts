/**
 * 主力识别API客户端
 */

import { fetchJson } from './client'

// 主力活动接口
export interface MainForceActivity {
  id?: string
  date: string
  stock_code: string
  stock_name: string
  activity_type: 'BUY' | 'SELL'
  volume: number
  amount: number
  price: number
  ratio: number
  mainforce_type: 'institution' | 'hot_money' | 'retail'
  description?: string
  indicators?: any
  is_anomaly?: number
  alert_status?: 'none' | 'pending' | 'triggered'
}

// 告警规则接口
export interface MainForceRule {
  id: string
  name: string
  rule_type: 'volume_anomaly' | 'large_order' | 'netflow' | 'position_change'
  description?: string
  enabled: boolean
  threshold: number
  threshold_unit?: string
  condition?: any
  action?: string
  priority?: number
  alert_template?: string
}

// K线标注接口
export interface KlineMarker {
  id?: string
  stock_code: string
  stock_name: string
  marker_date: string
  marker_price: number
  marker_type: 'BUY' | 'SELL'
  volume?: number
  amount?: number
  mainforce_type?: 'institution' | 'hot_money' | 'retail'
  source?: 'auto' | 'manual'
  activity_id?: string
  description?: string
  is_visible?: number
}

// 统计摘要接口
export interface MainForceSummary {
  today: {
    total_count: number
    buy_count: number
    sell_count: number
    total_buy_amount: number
    total_sell_amount: number
    net_flow: number
    institution_count: number
    hot_money_count: number
  }
  week: {
    total_count: number
    total_amount: number
  }
  active_rules: number
}

// 获取主力活动列表
export async function getMainForceActivities(params?: {
  stock_code?: string
  activity_type?: string
  mainforce_type?: string
  start_date?: string
  end_date?: string
  alert_status?: string
  page?: number
  page_size?: number
}): Promise<{ data: MainForceActivity[], total: number }> {
  const searchParams = new URLSearchParams()
  
  if (params?.stock_code) searchParams.append('stock_code', params.stock_code)
  if (params?.activity_type) searchParams.append('activity_type', params.activity_type)
  if (params?.mainforce_type) searchParams.append('mainforce_type', params.mainforce_type)
  if (params?.start_date) searchParams.append('start_date', params.start_date)
  if (params?.end_date) searchParams.append('end_date', params.end_date)
  if (params?.alert_status) searchParams.append('alert_status', params.alert_status)
  if (params?.page) searchParams.append('page', String(params.page))
  if (params?.page_size) searchParams.append('page_size', String(params.page_size))
  
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const data = await fetchJson<MainForceActivity[]>(`/api/mainforce/activities${query}`)
  
  return { data, total: data.length }
}

// 创建主力活动
export async function createMainForceActivity(activity: MainForceActivity): Promise<{ id: string }> {
  return fetchJson('/api/mainforce/activities', {
    method: 'POST',
    body: JSON.stringify(activity)
  })
}

// 获取单个主力活动
export async function getMainForceActivity(id: string): Promise<MainForceActivity> {
  return fetchJson<MainForceActivity>(`/api/mainforce/activities/${id}`)
}

// 获取告警规则列表
export async function getMainForceRules(enabled?: boolean): Promise<MainForceRule[]> {
  const query = enabled !== undefined ? `?enabled=${enabled}` : ''
  return fetchJson<MainForceRule[]>(`/api/mainforce/rules${query}`)
}

// 更新告警规则
export async function updateMainForceRule(
  ruleId: string, 
  rule: Partial<MainForceRule>
): Promise<{ message: string }> {
  return fetchJson(`/api/mainforce/rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(rule)
  })
}

// 触发规则检查
export async function triggerMainForceRule(
  ruleId: string,
  stockCode: string,
  stockName: string,
  value: number
): Promise<{
  triggered: boolean
  rule_name: string
  threshold: number
  actual_value: number
  message: string | null
}> {
  const params = new URLSearchParams({
    stock_code: stockCode,
    stock_name: stockName,
    value: String(value)
  })
  
  return fetchJson(`/api/mainforce/rules/${ruleId}/trigger?${params.toString()}`, {
    method: 'POST'
  })
}

// 获取K线标注列表
export async function getKlineMarkers(params?: {
  stock_code?: string
  marker_type?: string
  start_date?: string
  end_date?: string
}): Promise<KlineMarker[]> {
  const searchParams = new URLSearchParams()
  
  if (params?.stock_code) searchParams.append('stock_code', params.stock_code)
  if (params?.marker_type) searchParams.append('marker_type', params.marker_type)
  if (params?.start_date) searchParams.append('start_date', params.start_date)
  if (params?.end_date) searchParams.append('end_date', params.end_date)
  
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  return fetchJson<KlineMarker[]>(`/api/mainforce/markers${query}`)
}

// 创建K线标注
export async function createKlineMarker(marker: KlineMarker): Promise<{ id: string }> {
  return fetchJson('/api/mainforce/markers', {
    method: 'POST',
    body: JSON.stringify(marker)
  })
}

// 获取统计摘要
export async function getMainForceSummary(): Promise<MainForceSummary> {
  return fetchJson<MainForceSummary>('/api/mainforce/summary')
}

// 获取统计列表
export async function getMainForceStatistics(params?: {
  start_date?: string
  end_date?: string
}): Promise<any[]> {
  const searchParams = new URLSearchParams()
  
  if (params?.start_date) searchParams.append('start_date', params.start_date)
  if (params?.end_date) searchParams.append('end_date', params.end_date)
  
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  return fetchJson<any[]>(`/api/mainforce/statistics${query}`)
}
