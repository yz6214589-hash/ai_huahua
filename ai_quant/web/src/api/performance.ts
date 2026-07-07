import { fetchJson, postJson } from './client'

export interface PerformanceReport {
  id: number
  report_id: string
  report_type: string
  account_id: number
  strategy_name?: string
  start_date?: string
  end_date?: string
  initial_cash: number
  final_nav?: number
  total_return?: number
  annualized_return?: number
  max_drawdown?: number
  volatility?: number
  sharpe_ratio?: number
  calmar_ratio?: number
  win_rate?: number
  profit_factor?: number
  total_trades?: number
  winning_trades?: number
  losing_trades?: number
  status: string
  created_at?: string
}

export interface ReportGenerateRequest {
  account_id?: number
  report_type?: string
  start_date?: string
  end_date?: string
  strategy_name?: string
  strategy_params?: string
  backtest_id?: string
  initial_cash?: number
  benchmark_code?: string
}

export interface ReportListResponse {
  items: PerformanceReport[]
  total: number
  page: number
  page_size: number
}

export async function getReportTypes(): Promise<{ value: string; label: string; description: string }[]> {
  return fetchJson('/api/v1/performance/types')
}

export async function generateReport(request: ReportGenerateRequest): Promise<any> {
  return postJson('/api/v1/performance/generate', request)
}

export async function getReportList(params?: {
  report_type?: string
  account_id?: number
  status?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}): Promise<ReportListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.report_type) searchParams.set('report_type', params.report_type)
  if (params?.account_id) searchParams.set('account_id', String(params.account_id))
  if (params?.status) searchParams.set('status', params.status)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  const qs = searchParams.toString()
  return fetchJson<ReportListResponse>(`/api/v1/performance/list${qs ? '?' + qs : ''}`)
}

export async function getReportDetail(reportId: string): Promise<PerformanceReport> {
  return fetchJson<PerformanceReport>(`/api/v1/performance/reports/${reportId}`)
}

export async function deleteReport(reportId: string): Promise<any> {
  return fetchJson(`/api/v1/performance/reports/${reportId}`, { method: 'DELETE' })
}

/** 获取 QuantStats HTML 报告路径 */
export async function getQuantStatsHtml(reportId: string): Promise<{ html_path: string; url: string }> {
  return fetchJson(`/api/v1/performance/quantstats-html/${reportId}`)
}

/** 生成 QuantStats 报告 */
export async function generateQuantStatsReport(data: {
  nav_log: Array<{ date: string; nav: number }>
  benchmark_nav_log?: Array<{ date: string; nav: number }>
}): Promise<any> {
  return postJson('/api/v1/performance/quantstats-generate', data)
}

/** 报告详情数据结构（从 /api/v1/performance/detail/{report_id} 返回） */
export interface ReportDetail {
  id: string
  report_type: string
  account_id: number | null
  strategy_name: string | null
  backtest_id?: string
  start_date: string
  end_date: string
  initial_cash: number
  final_nav: number
  status: string
  created_at: string | null
  metrics: {
    total_return: number
    annualized_return: number
    max_drawdown: number
    volatility: number
    sharpe_ratio: number
    calmar_ratio: number
    win_rate: number
    profit_factor: number
    total_trades: number
    winning_trades: number
    losing_trades: number
  }
  equity_curve: Array<{ date: string; nav: number }>
  drawdown_curve: Array<{ date: string; nav: number; peak: number; drawdown: number }>
  monthly_returns: Array<{ month: string; return: number }>
  trades: Array<Record<string, unknown>>
  // chart_data 中的额外 QuantStats 增强指标
  cagr?: number
  sortino?: number
  omega?: number
  var_95?: number
  cvar_95?: number
  gain_to_pain?: number
  skew?: number
  kurtosis?: number
  best_day?: number
  worst_day?: number
  consecutive_wins?: number
  consecutive_losses?: number
  alpha?: number
  beta?: number
  information_ratio?: number
  tracking_error?: number
}

/** 获取报告详情（含完整曲线数据和增强指标） */
export async function getReportDetailFull(reportId: string): Promise<ReportDetail> {
  return fetchJson<ReportDetail>(`/api/v1/performance/detail/${reportId}`)
}

/** SVD 市场状态诊断结果 */
export interface SVDResult {
  current_state: string
  current_f1_ratio: number
  advice: string
  rolling_data: Array<{ date: string; top1_var: number; top3_var: number; state: string }>
  stock_count: number
  data_days: number
}

/** 交易成本分析 */
export interface CostAnalysis {
  total_turnover: number
  commission: number
  stamp_tax: number
  transfer_fee: number
  total_cost: number
  cost_ratio: number
}

/** 个股盈亏 */
export interface StockPnL {
  stock_name: string
  stock_code: string
  buy_amount: number
  sell_amount: number
  unclosed: number
  realized_pnl: number
  total_cost: number
}

/** Plus 版报告详情数据结构 */
export interface ReportDetailPlus extends ReportDetail {
  svd_result?: SVDResult
  cost_analysis?: CostAnalysis
  stock_pnl?: StockPnL[]
}

/** 获取 Plus 版报告详情（含 SVD 诊断、成本分析、个股盈亏） */
export async function getReportDetailPlus(reportId: string): Promise<ReportDetailPlus> {
  return fetchJson<ReportDetailPlus>(`/api/v1/performance/detail-plus/${reportId}`)
}

/** SVD 市场状态诊断 */
export async function diagnoseMarketSVD(data: {
  stock_codes: string[]
  start_date: string
  end_date: string
  window?: number
  step?: number
}): Promise<SVDResult> {
  return postJson('/api/v1/performance/svd-diagnose', data)
}
