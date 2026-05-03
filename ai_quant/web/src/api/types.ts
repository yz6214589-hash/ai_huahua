export type DataSource = 'qmt' | 'tushare' | 'akshare' | 'qwen_search' | 'file' | 'unknown'

export type JobDomain =
  | 'stock_daily'
  | 'stock_financial'
  | 'stock_news'
  | 'macro_indicator'
  | 'rate_daily'
  | 'report_consensus'
  | 'calendar'
  | 'catalyst'

export type JobStatus = 'running' | 'success' | 'failed' | 'partial'

export interface JobRunResult {
  runId: string
  domain: JobDomain
  startedAt: string
  finishedAt?: string
  status: JobStatus
  dataSourceFinal: DataSource
  fallbackChain: DataSource[]
  rowsWritten: number
  itemsProcessed: number
  failedItems: string[]
  message?: string
}

export interface JobSchedule {
  domain: JobDomain
  enabled: boolean
  cron: string
  timezone: string
  mode?: string | null
  nextRunAt?: string | null
  lastRunAt?: string | null
  lastStatus?: JobStatus | null
  updatedAt?: string | null
}

export type DatasetName =
  | 'trade_stock_daily'
  | 'trade_stock_financial'
  | 'trade_stock_news'
  | 'trade_macro_indicator'
  | 'trade_rate_daily'
  | 'trade_report_consensus'
  | 'trade_calendar_event'

export interface SummaryItem {
  latest: string | null
  count: number
}

export type SummaryResponse = Record<DatasetName, SummaryItem>

export interface PagedRows<T> {
  page: number
  pageSize: number
  total: number
  rows: T[]
}

export interface StockSearchItem {
  code: string
  name?: string | null
}

export interface WatchlistItem {
  stock_code: string
  stock_name?: string | null
  pinned: boolean
  sortOrder: number
}

export interface StockSnapshot {
  stock_code: string
  stock_name?: string | null
  price?: number | null
  change?: number | null
  pctChange?: number | null
  asOf: string
  source: string
}

export type MetricDirection = 'up' | 'down' | 'flat' | null

export interface FundamentalsMetric {
  key: string
  label: string
  unit: string
  tooltip: string
  value: number | null
  delta: number | null
  dir: MetricDirection
}

export interface StockFundamentals {
  stock_code: string
  stock_name?: string | null
  reportDate?: string | null
  items: FundamentalsMetric[]
}

export interface StockTechnicalRow {
  trade_date: string
  open_price: number | null
  high_price: number | null
  low_price: number | null
  close_price: number | null
  volume: number | null
  amount: number | null
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  vol_ma5: number | null
  vol_ma20: number | null
  rsi14: number | null
  macd_dif: number | null
  macd_dea: number | null
  macd_hist: number | null
  boll_upper: number | null
  boll_mid: number | null
  boll_lower: number | null
  kdj_k: number | null
  kdj_d: number | null
  kdj_j: number | null
  atr14?: number | null
  ma_custom?: number | null
  macd_dif_custom?: number | null
  macd_dea_custom?: number | null
  macd_hist_custom?: number | null
  rsi_custom?: number | null
  atr_custom?: number | null
}

export interface StockTechnicalLatest {
  stock_code: string
  row?: Omit<StockTechnicalRow, 'open_price' | 'high_price' | 'low_price' | 'close_price' | 'volume' | 'amount'> | null
}

export interface StockFeedItem {
  title: string
  source?: string | null
  publishedAt?: string | null
  url?: string | null
}

export interface StockFeedResponse {
  tab: 'news' | 'reports'
  page: number
  pageSize: number
  total: number
  items: StockFeedItem[]
}

export type ReportModel = 'qwen-max' | 'deepseek'
export type ReportTaskStatus = 'waiting' | 'running' | 'success' | 'failed'

export interface ReportTask {
  task_id: string
  model: ReportModel
  stock_codes: string[]
  stock_names: string[]
  status: ReportTaskStatus
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
}

export interface SentimentRun {
  run_id: string
  trigger: string
  stock_codes: string[]
  stock_names: string[]
  days: number
  use_llm: boolean
  status: string
  total_events: number
  created_at: string | null
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
}

export interface SentimentEvent {
  id: number
  run_id: string
  stock_code: string
  stock_name?: string | null
  source_type: string
  source_title?: string | null
  source_url?: string | null
  published_at?: string | null
  event_type: string
  event_category: string
  signal: string
  signal_reason?: string | null
  impact?: string | null
  confidence?: number | null
  urgency?: string | null
}

export interface MacroIndicator {
  indicator: string
  value: number | null
  date?: string | null
  name?: string | null
  error?: string | null
}

export interface MacroComposite {
  composite_fear_greed_index: number
  overall_sentiment: string
  action_suggestion: string
  timestamp: string
}

export interface MacroLatest {
  indicators: MacroIndicator[]
  composite: MacroComposite
}

export interface ConsoleOverview {
  data_latest: SummaryResponse
  recent_jobs: JobRunResult[]
  execution_status: {
    source?: string
    status?: string
    features?: string[]
  }
  risk_status: {
    source?: string
    status?: string
    features?: string[]
    [key: string]: unknown
  }
  morning: {
    last_run?: {
      run_id?: string
      input?: string
      route?: string
      created_at?: string
    } | null
    run_count?: number
  }
}

