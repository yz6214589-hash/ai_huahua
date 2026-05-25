/**
 * API 类型定义模块
 * 包含数据采集、研报生成、舆情监控、风险管理等功能的类型定义
 */

// 数据源类型枚举，标识数据采集时使用的数据源
export type DataSource = 'qmt' | 'tushare' | 'akshare' | 'qwen_search' | 'file' | 'unknown'

// 任务领域类型，定义不同的数据类型分类
export type JobDomain =
  | 'stock_daily'       // 股票日线数据
  | 'stock_financial'    // 股票财务数据
  | 'stock_news'         // 股票新闻资讯
  | 'macro_indicator'     // 宏观指标数据
  | 'rate_daily'         // 利率日线数据
  | 'report_consensus'   // 研报共识数据
  | 'calendar'           // 日历事件数据
  | 'catalyst'           // 催化剂事件数据

// 任务执行状态枚举
export type JobStatus = 'running' | 'success' | 'failed' | 'partial'

export interface JobDomainInfo {
  domain: JobDomain
  title: string
  desc: string
  defaultMode?: 'test' | 'full' | null
}

// 任务运行结果接口，记录一次数据采集任务的执行结果
export interface JobRunResult {
  runId: string              // 任务运行唯一标识
  domain: JobDomain          // 任务所属领域
  startedAt: string          // 任务开始时间（ISO 格式字符串）
  finishedAt?: string        // 任务结束时间
  status: JobStatus          // 任务最终状态
  dataSourceFinal: DataSource     // 最终使用的数据源
  fallbackChain: DataSource[]     // 数据源回退链
  rowsWritten: number        // 写入的数据行数
  itemsProcessed: number      // 处理的数据项总数
  failedItems: string[]      // 处理失败的数据项列表
  message?: string           // 任务执行消息
  userMessage?: string       // 给用户的提示消息
}

// 任务调度配置接口，定义定时任务的调度规则
export interface JobSchedule {
  domain: JobDomain          // 任务领域
  enabled: boolean           // 是否启用
  cron: string               // Cron 表达式，定义执行周期
  timezone: string           // 时区设置
  mode?: string | null       // 运行模式
  nextRunAt?: string | null   // 下次执行时间
  lastRunAt?: string | null  // 上次执行时间
  lastStatus?: JobStatus | null  // 上次执行状态
  updatedAt?: string | null  // 配置更新时间
}

// 数据集名称类型，定义系统中的各种数据集
export type DatasetName =
  | 'trade_stock_daily'        // 股票日线数据集
  | 'trade_stock_financial'    // 股票财务数据集
  | 'trade_stock_news'         // 股票新闻数据集
  | 'trade_macro_indicator'    // 宏观指标数据集
  | 'trade_rate_daily'         // 利率日线数据集
  | 'trade_report_consensus'   // 研报共识数据集
  | 'trade_calendar_event'     // 日历事件数据集

// 数据摘要项，包含最新更新时间戳和数据条数
export interface SummaryItem {
  latest: string | null       // 最新数据时间
  count: number                // 数据条数
}

// 数据摘要响应，键为数据集名称，值为对应的摘要信息
export type SummaryResponse = Record<DatasetName, SummaryItem>

// 分页数据接口，用于支持列表数据的分页查询
export interface PagedRows<T> {
  page: number                 // 当前页码
  pageSize: number             // 每页条数
  total: number               // 总条数
  rows: T[]                    // 当前页数据
}

// 股票搜索项，用于股票搜索和选择
export interface StockSearchItem {
  code: string                 // 股票代码
  name?: string | null         // 股票名称
}

// 自选股条目，包含股票信息和排序信息
export interface WatchlistItem {
  stock_code: string           // 股票代码
  stock_name?: string | null   // 股票名称
  pinned: boolean              // 是否置顶
  sort_order: number            // 排序顺序
  group_ids?: number[]         // 所属分组 ID 列表
}

// 自选股自定义分组
export interface WatchlistGroup {
  id: number
  name: string
  sort_order: number
}

// 自选股行情快照，用于自选股列表展示价格
export interface WatchlistSnapshot {
  stock_code: string
  stock_name?: string | null
  price?: number | null
  change?: number | null
  pctChange?: number | null
  trade_date?: string | null
  source: string
}

// 股票行情快照，包含实时价格和涨跌幅信息
export interface StockSnapshot {
  stock_code: string           // 股票代码
  stock_name?: string | null   // 股票名称
  price?: number | null        // 当前价格
  change?: number | null       // 价格变动
  pctChange?: number | null    // 涨跌幅百分比
  asOf: string                 // 数据时间点
  source: string               // 数据来源
}

// 指标方向枚举，表示指标的变化趋势
export type MetricDirection = 'up' | 'down' | 'flat' | null

// 基本面指标项，包含指标的详细信息和数值
export interface FundamentalsMetric {
  key: string                 // 指标键名
  label: string                // 指标显示标签
  unit: string                 // 计量单位
  tooltip: string              // 指标说明
  value: number | null         // 当前值
  delta: number | null         // 变化量
  dir: MetricDirection         // 变化方向
}

// 股票基本面数据，包含多个指标项
export interface StockFundamentals {
  stock_code: string           // 股票代码
  stock_name?: string | null   // 股票名称
  reportDate?: string | null   // 报告日期
  items: FundamentalsMetric[]   // 指标列表
}

// 股票技术指标行，包含 OHLCV 和各种技术指标
export interface StockTechnicalRow {
  trade_date: string           // 交易日期
  open_price: number | null    // 开盘价
  high_price: number | null   // 最高价
  low_price: number | null    // 最低价
  close_price: number | null  // 收盘价
  volume: number | null        // 成交量
  amount: number | null        // 成交额
  ma5: number | null           // 5日均线
  ma10: number | null          // 10日均线
  ma20: number | null          // 20日均线
  ma60: number | null          // 60日均线
  vol_ma5: number | null      // 成交量5日均线
  vol_ma20: number | null      // 成交量20日均线
  rsi14: number | null         // RSI 指标（14日）
  macd_dif: number | null      // MACD 差值线（DIF）
  macd_dea: number | null      // MACD 信号线（DEA）
  macd_hist: number | null     // MACD 柱状图
  boll_upper: number | null    // 布林带上轨
  boll_mid: number | null      // 布林带中轨
  boll_lower: number | null    // 布林带下轨
  kdj_k: number | null         // KDJ 的 K 值
  kdj_d: number | null         // KDJ 的 D 值
  kdj_j: number | null         // KDJ 的 J 值
  atr14?: number | null        // ATR 指标（14日）
  ma_custom?: number | null    // 自定义均线
  macd_dif_custom?: number | null   // 自定义 MACD 差值线
  macd_dea_custom?: number | null   // 自定义 MACD 信号线
  macd_hist_custom?: number | null  // 自定义 MACD 柱状图
  rsi_custom?: number | null        // 自定义 RSI
  atr_custom?: number | null        // 自定义 ATR
}

// 股票最新技术指标，简化版仅包含指标值不包含价格和成交量
export interface StockTechnicalLatest {
  stock_code: string           // 股票代码
  row?: Omit<StockTechnicalRow, 'open_price' | 'high_price' | 'low_price' | 'close_price' | 'volume' | 'amount'> | null
}

// 股票资讯条目，包含新闻或研报的基本信息
export interface StockFeedItem {
  title: string                // 标题
  source?: string | null       // 来源
  publishedAt?: string | null  // 发布时间
  url?: string | null          // 原文链接
  content?: string | null      // 新闻/研报原文内容
}

// 股票资讯响应，包含分页信息和资讯列表
export interface StockFeedResponse {
  tab: 'news' | 'reports'      // 标签类型：新闻或研报
  page: number                 // 当前页
  pageSize: number             // 每页条数
  total: number               // 总条数
  items: StockFeedItem[]      // 资讯列表
}

// 研报生成模型类型，支持通义千问和 DeepSeek
export type ReportModel = 'qwen-max' | 'deepseek'

// 研报任务状态枚举
export type ReportTaskStatus = 'waiting' | 'running' | 'success' | 'failed'

// 研报生成任务接口，记录一次研报生成任务的完整信息
export interface ReportTask {
  task_id: string              // 任务唯一标识
  model: ReportModel           // 使用的 AI 模型
  stock_codes: string[]        // 关联的股票代码列表
  stock_names: string[]        // 关联的股票名称列表
  use_rag?: boolean            // 是否启用 RAG（检索增强生成）
  status: ReportTaskStatus     // 任务状态
  created_at: string           // 创建时间
  started_at?: string | null   // 开始执行时间
  finished_at?: string | null // 完成时间
  error_message?: string | null    // 错误信息
  error_location?: string | null  // 错误位置
  report_path?: string | null   // 生成报告的文件路径
}

// 舆情运行记录，表示一次完整的舆情分析运行
export interface SentimentRun {
  run_id: string               // 运行唯一标识
  trigger: string              // 触发方式
  stock_codes: string[]        // 分析的股票代码
  stock_names: string[]        // 分析的股票名称
  days: number                 // 分析的历史天数
  use_llm: boolean             // 是否使用大语言模型
  status: string               // 运行状态
  total_events: number          // 发现的事件总数
  created_at: string | null    // 创建时间
  started_at?: string | null   // 开始时间
  finished_at?: string | null  // 结束时间
  error_message?: string | null // 错误信息
}

// 舆情事件条目，记录一个具体的舆情事件
export interface SentimentEvent {
  id: number                   // 事件唯一标识
  run_id: string               // 所属运行 ID
  stock_code: string          // 关联股票代码
  stock_name?: string | null   // 关联股票名称
  source_type: string          // 来源类型
  source_title?: string | null // 来源标题
  source_url?: string | null   // 来源链接
  published_at?: string | null // 发布时间
  event_type: string           // 事件类型
  event_category: string       // 事件分类
  signal: string               // 信号类型
  signal_reason?: string | null    // 信号原因
  impact?: string | null       // 影响描述
  confidence?: number | null   // 置信度
  urgency?: string | null      // 紧急程度
}

// 宏观指标数据项
export interface MacroIndicator {
  indicator: string            // 指标代码
  value: number | null         // 指标值
  date?: string | null         // 数据日期
  name?: string | null         // 指标名称
  source?: string | null       // 数据来源
  error?: string | null        // 错误信息
}

// 宏观情绪综合指标，包含恐惧贪婪指数等
export interface MacroComposite {
  composite_fear_greed_index: number   // 恐惧贪婪指数
  overall_sentiment: string             // 整体情绪
  action_suggestion: string             // 操作建议
  timestamp: string                     // 更新时间戳
}

// 最新宏观数据，包含指标列表和综合指标
export interface MacroLatest {
  indicators: MacroIndicator[]   // 宏观指标列表
  composite: MacroComposite      // 综合情绪指标
}

// 控制台概览数据，包含系统各模块的状态汇总
export interface ConsoleOverview {
  data_latest: SummaryResponse       // 数据最新状态
  recent_jobs: JobRunResult[]        // 最近运行的任务
  execution_status: {                // 执行模块状态
    source?: string
    status?: string
    features?: string[]
  }
  risk_status: {                     // 风控模块状态
    source?: string
    status?: string
    features?: string[]
    [key: string]: unknown
  }
  morning: {                         // 晨会模块状态
    last_run?: {                     // 最近一次运行
      run_id?: string
      input?: string
      route?: string
      created_at?: string
    } | null
    run_count?: number               // 运行次数
  }
}

// 交易信号类型，买入或卖出
export type TradeSignal = 'BUY' | 'SELL'

// 分析信号快照，记录生成信号时的关键指标值
export interface AnalysisSignalSnapshot {
  close: number | null          // 收盘价
  ma20: number | null           // 20日均线
  rsi14: number | null          // RSI(14)
  macd_hist: number | null      // MACD 柱状图
  boll_upper: number | null     // 布林带上轨
  boll_mid: number | null       // 布林带中轨
  boll_lower: number | null     // 布林带下轨
  [key: string]: unknown        // 允许添加其他指标
}

// 单个分析信号项，包含信号、评分和原因
export interface AnalysisSignalItem {
  trade_date: string                    // 交易日期
  signal: TradeSignal                   // 交易信号
  score: number                         // 信号评分
  reasons: string[]                     // 信号原因列表
  snapshot: AnalysisSignalSnapshot      // 指标快照
}

// 分析信号响应，包含股票代码和信号列表
export interface AnalysisSignalsResponse {
  stock_code: string
  signals: AnalysisSignalItem[]
}

// 分析股票样本响应，返回待分析的股票代码列表
export interface AnalysisStocksSampleResponse {
  codes: string[]
}

// 风险交易方向
export type RiskDirection = 'buy' | 'sell'

// 风险审批请求，包含订单信息、持仓信息和上下文
export interface RiskApproveRequest {
  order: {                      // 订单信息
    stock_code: string          // 股票代码
    direction: RiskDirection    // 交易方向
    amount: number              // 交易金额
    price: number               // 交易价格
    quantity: number            // 交易数量
  }
  portfolio: {                  // 持仓信息
    total_asset: number         // 总资产
    prices: Record<string, number>    // 各股票当前价格
    atr: Record<string, number>        // 各股票 ATR 值
  }
  context: {                    // 上下文信息
    news_text: string           // 相关新闻文本
  }
}

// 风控决策类型：通过、警告或拒绝
export type RiskDecision = 'APPROVE' | 'WARN' | 'REJECT'

// 单个风控检查项，记录每条规则的检查结果
export interface RiskCheckItem {
  decision: RiskDecision        // 检查决策
  reason: string                // 决策原因
  rule_name: string             // 规则名称
  max_position_pct: number      // 最大持仓比例
  timestamp: string             // 检查时间戳
}

// 风控审批响应，包含最终决策和建议
export interface RiskApproveResponse {
  decision: RiskDecision        // 最终决策
  reason: string                // 决策原因
  rule_name: string             // 触发的主要规则名
  max_position_pct: number      // 最大持仓比例
  timestamp: string             // 响应时间戳
  suggested_amount: number      // 建议交易金额
  suggested_quantity: number     // 建议交易数量
  checks: RiskCheckItem[]       // 所有检查项详情
}

// 风控审计条目，记录一次交易的风控审核历史
export interface RiskAuditItem {
  timestamp: string              // 审核时间
  stock_code: string             // 股票代码
  direction: string             // 交易方向
  amount: number                // 交易金额
  price: number                 // 交易价格
  quantity: number              // 交易数量
  decision: string              // 风控决策
  reason: string                // 决策原因
  rule_name: string             // 规则名称
  max_position_pct: number      // 最大持仓比例
}

// 风控审计响应，包含审核历史列表
export interface RiskAuditResponse {
  items: RiskAuditItem[]
}

// 晨会触发请求参数
export interface MorningTriggerRequest {
  industry_level?: 1 | 2        // 行业分类级别（1：一级，2：二级）
  top_n_industries?: number     // 选择的顶级行业数量
  top_n_stocks?: number         // 每个行业选择的股票数量
  lookback_days?: number        // 回看天数
  sample_stocks?: number        // 采样股票数量
  end_date?: string             // 截止日期
}

// 晨会触发响应，包含生成的报告内容
export interface MorningTriggerResponse {
  ok: boolean                   // 请求是否成功
  workflow: string               // 工作流名称
  result: {                     // 处理结果
    report_html: string         // HTML 格式报告
    report_md: string           // Markdown 格式报告
    messages: unknown[]         // 相关消息
    picked_stocks: unknown[]    // 选中的股票
    industry_rank: unknown[]    // 行业排名
  }
}
