/**
 * 主力识别API客户端
 */

import { postJson, fetchJson } from './client'

// 时间范围类型
export type TimeRange = 'today' | 'yesterday' | 'last_5_days'

// 单股主力行为分析结果接口
export interface MainForceAnalysis {
  stock_code: string
  stock_name: string
  analysis_date: string
  time_range: TimeRange
  time_range_label: string
  data_bars?: number
  actual_bars?: number
  expected_bars?: number
  data_complete?: boolean
  warning?: string
  features: Record<string, number>
  classification: {
    primary_type: 'institution' | 'hot_money' | 'retail'
    confidence: number
    type_scores: Record<string, number>
    direction: 'strong_buy' | 'weak_buy' | 'neutral' | 'weak_sell' | 'strong_sell'
    direction_score: number
    ofi_signed: number
    ofi_signed_recent: number
  }
  indicators: {
    volume_trend: string
    price_trend: string
    capital_flow: string
    activity_level: string
  }
  signals: Array<{
    date: string
    type: string
    strength: number
    description: string
  }>
  summary: string
  error?: string
}

// 触发单股主力行为分析
export async function analyzeMainForce(
  stockCode: string,
  timeRange: TimeRange = 'today'
): Promise<MainForceAnalysis> {
  return postJson<MainForceAnalysis>('/api/v1/mainforce/analyze', {
    stock_code: stockCode,
    time_range: timeRange,
  })
}

// 获取单股分析结果
export async function getMainForceAnalysis(
  stockCode: string,
  timeRange: TimeRange = 'today'
): Promise<MainForceAnalysis> {
  return fetchJson<MainForceAnalysis>(
    `/api/v1/mainforce/analysis/${encodeURIComponent(stockCode)}?time_range=${timeRange}`
  )
}

// 数据完整性检查
export function checkDataCompleteness(analysis: MainForceAnalysis): {
  complete: boolean
  warning: string | null
  actualVsExpected: string
} {
  const actual = analysis.actual_bars ?? analysis.data_bars ?? 0
  const expected = analysis.expected_bars ?? 0
  
  const ratio = expected > 0 ? (actual / expected) * 100 : 100
  const complete = ratio >= 90
  
  let warning: string | null = analysis.warning ?? null
  if (!complete && !warning) {
    warning = `数据缺失一部分（实际${actual}条/期望${expected}条），分析结果可能有误请谨慎对待`
  }
  
  return {
    complete,
    warning,
    actualVsExpected: `${actual}/${expected}`,
  }
}
