import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Play, RefreshCcw, TrendingUp, TrendingDown, XCircle, CheckCircle2, ChevronDown, ChevronRight, History, BarChart3 } from 'lucide-react'
import BacktestCharts from '@/components/BacktestCharts'
import BacktestHistory from '@/pages/BacktestHistory'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'

interface StrategyDef {
  strategy_id: string
  name: string
  params_schema: Record<string, {
    type: 'int' | 'float' | 'bool' | 'enum' | 'object'
    label: string; help: string
    min?: number; max?: number; step?: number
    default?: number | string | boolean
    values?: string[]
  }>
  default_params: Record<string, unknown>
  requires_chan?: boolean
  requires_predictions?: boolean
}

interface StrategyInstance {
  instance_id: string
  strategy_id: string
  name: string
  params: Record<string, unknown>
}

interface StockGroup {
  id: number
  name: string
  description: string
  stock_count: number
}

/** 增强指标接口 */
interface EnhancedMetrics {
  initial_nav: number
  final_nav: number
  total_return: number
  num_trades: number
  win_rate: number
  annual_return?: number
  max_drawdown?: number
  // 增强指标
  volatility?: number
  sortino?: number
  calmar?: number
  alpha?: number
  beta?: number
  information_ratio?: number
  profit_factor?: number
  tracking_error?: number
  sharpe?: number
}

interface SingleBacktestResult {
  metrics: EnhancedMetrics
  trades: Array<{ date: string; action: string; price: number; qty: number; cost?: number; proceeds?: number; note?: string }>
  nav_log: Array<{ date: string; nav: number }>
  benchmark_nav_log?: Array<{ date: string; nav: number }>
  drawdown_log?: Array<{ date: string; nav: number; peak: number; drawdown: number }>
  monthly_returns?: Array<{ month: string; return: number }>
  strategy_id: string
  stock_code: string
  start_date: string
  end_date: string
  interval_results?: IntervalResult[]
}

interface IntervalResult {
  name: string
  start: string
  end: string
  error?: string
  result?: {
    metrics: EnhancedMetrics
    trades: Array<{ date: string; action: string; price: number; qty: number; cost?: number; proceeds?: number; note?: string }>
    nav_log: Array<{ date: string; nav: number }>
    benchmark_nav_log?: Array<{ date: string; nav: number }>
    drawdown_log?: Array<{ date: string; nav: number; peak: number; drawdown: number }>
    monthly_returns?: Array<{ month: string; return: number }>
  }
}

interface BatchBacktestResult {
  batch_id: string
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  aggregated: {
    avg_total_return: number
    avg_annual_return: number
    avg_max_drawdown: number
    avg_sharpe: number
    avg_win_rate: number
    total_trades: number
    win_stocks: number
    total_stocks: number
    best_stock?: { code: string; return: number }
    worst_stock?: { code: string; return: number }
  }
  results: Array<{
    task_id: string
    stock_code: string
    status: string
    error?: string
    metrics?: Record<string, unknown>
  }>
}

interface BacktestMode {
  type: 'single' | 'batch'
}

/* ---------- 指标卡片组件 ---------- */

function MetricCard({ label, value, unit = '', tone }: { label: string; value: string | number; unit?: string; tone?: 'up' | 'down' | 'neutral' }) {
  const cls = tone === 'up' ? 'text-red-600' : tone === 'down' ? 'text-green-600' : 'text-zinc-900'
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
      <div className={`text-2xl font-bold ${cls}`}>{value}{unit}</div>
      <div className="mt-1 text-xs text-zinc-500">{label}</div>
    </div>
  )
}

/* ---------- 增强指标展示组件 ---------- */

function MetricsDisplay({ metrics }: { metrics: EnhancedMetrics }) {
  const totalReturn = metrics.total_return ?? 0
  const returnTone = totalReturn > 0 ? 'up' : totalReturn < 0 ? 'down' : 'neutral'

  return (
    <div className="space-y-3">
      {/* 第一行：基础指标 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-7">
        <MetricCard label="初始资金" value={metrics.initial_nav.toLocaleString()} unit="元" />
        <MetricCard label="最终资金" value={metrics.final_nav.toLocaleString()} unit="元" />
        <MetricCard label="总收益率" value={`${totalReturn > 0 ? '+' : ''}${(totalReturn * 100).toFixed(2)}`} unit="%" tone={returnTone} />
        <MetricCard label="交易次数" value={metrics.num_trades} />
        <MetricCard label="胜率" value={`${(metrics.win_rate * 100).toFixed(1)}`} unit="%" />
        <MetricCard label="年化收益" value={`${((metrics.annual_return ?? 0) * 100).toFixed(2)}`} unit="%" tone={(metrics.annual_return ?? 0) > 0 ? 'up' : 'down'} />
        <MetricCard label="最大回撤" value={`${((metrics.max_drawdown ?? 0) * 100).toFixed(2)}`} unit="%" tone="down" />
      </div>
      {/* 第二行：增强指标 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-7">
        <MetricCard label="波动率" value={`${((metrics.volatility ?? 0) * 100).toFixed(2)}`} unit="%" />
        <MetricCard label="Sortino" value={(metrics.sortino ?? 0).toFixed(3)} />
        <MetricCard label="Calmar" value={(metrics.calmar ?? 0).toFixed(3)} />
        <MetricCard label="Alpha" value={`${((metrics.alpha ?? 0) * 100).toFixed(2)}`} unit="%" tone={(metrics.alpha ?? 0) > 0 ? 'up' : 'down'} />
        <MetricCard label="Beta" value={(metrics.beta ?? 0).toFixed(3)} />
        <MetricCard label="信息比率" value={(metrics.information_ratio ?? 0).toFixed(3)} />
        <MetricCard label="盈亏比" value={(metrics.profit_factor ?? 0).toFixed(2)} />
      </div>
    </div>
  )
}

/* ---------- 区间结果展示组件 ---------- */

function IntervalResultDisplay({ intervalResult }: { intervalResult: IntervalResult }) {
  const nameMap: Record<string, string> = { train: '训练集', val: '验证集', test: '测试集' }
  const label = nameMap[intervalResult.name] || intervalResult.name

  if ('error' in intervalResult) {
    return (
      <Card>
        <CardHeader title={`${label}（${intervalResult.start} ~ ${intervalResult.end}）`} />
        <CardBody>
          <div className="flex items-center gap-2 text-sm text-red-600">
            <XCircle className="h-4 w-4" />
            <span>回测失败：{(intervalResult as any).error}</span>
          </div>
        </CardBody>
      </Card>
    )
  }

  if (!intervalResult.result) return null

  return (
    <Card>
      <CardHeader title={`${label}（${intervalResult.start} ~ ${intervalResult.end}）`} />
      <CardBody className="space-y-4">
        <MetricsDisplay metrics={intervalResult.result.metrics} />
        <BacktestCharts
          navLog={intervalResult.result.nav_log}
          benchmarkNavLog={intervalResult.result.benchmark_nav_log}
          drawdownLog={intervalResult.result.drawdown_log}
          monthlyReturns={intervalResult.result.monthly_returns}
        />
      </CardBody>
    </Card>
  )
}

/* ---------- 错误详情展示组件（可折叠） ---------- */

interface ValidationError {
  field: string
  message: string
}

function ErrorDetailDisplay({ error, onClose }: { error: string; onClose: () => void }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-lg border border-red-200 bg-red-50">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 text-red-600" />
          <span className="text-sm font-medium text-red-800">回测执行失败</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center gap-1 text-xs text-red-700 hover:text-red-900"
          >
            {expanded ? (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                收起详情
              </>
            ) : (
              <>
                <ChevronRight className="h-3.5 w-3.5" />
                展开详情
              </>
            )}
          </button>
          <button
            onClick={onClose}
            className="rounded px-2 py-0.5 text-xs text-red-700 hover:bg-red-100"
          >
            关闭
          </button>
        </div>
      </div>

      <div className="px-4 pb-2 text-xs text-red-700">
        {error.length > 100 ? `${error.substring(0, 100)}...` : error}
      </div>

      {expanded && (
        <div className="border-t border-red-200 bg-white px-4 py-3">
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs font-mono text-red-800">
            {error}
          </pre>
        </div>
      )}
    </div>
  )
}

/** 参数校验错误提示组件 */
function ValidationErrors({ errors, onClose }: { errors: ValidationError[]; onClose: () => void }) {
  if (errors.length === 0) return null
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 text-amber-600" />
          <span className="text-sm font-medium text-amber-800">
            参数校验未通过（共 {errors.length} 项）
          </span>
        </div>
        <button onClick={onClose} className="rounded px-2 py-0.5 text-xs text-amber-700 hover:bg-amber-100">
          关闭
        </button>
      </div>
      <div className="border-t border-amber-200 px-4 py-3 space-y-1.5">
        {errors.map((e, i) => (
          <div key={i} className="flex items-start gap-2 text-xs text-amber-800">
            <span className="mt-0.5 shrink-0">•</span>
            <span><strong>{e.field}</strong>：{e.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---------- 主组件 ---------- */

export default function StrategyBacktest() {
  const [searchParams] = useSearchParams()
  const [strategies, setStrategies] = useState<StrategyDef[]>([])
  const [instances, setInstances] = useState<StrategyInstance[]>([])
  const [groups, setGroups] = useState<StockGroup[]>([])
  const [singleResult, setSingleResult] = useState<SingleBacktestResult | null>(null)
  const [batchResult, setBatchResult] = useState<BatchBacktestResult | null>(null)
  const [running, setRunning] = useState(false)
  // 回测错误信息（用于展示详细错误）
  const [backtestError, setBacktestError] = useState<string | null>(null)
  // 参数校验错误列表
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([])
  // 回测历史模态框可见性
  const [historyVisible, setHistoryVisible] = useState(false)
  // 页面数据是否已就绪（用于处理 URL 实例ID）
  const [pageReady, setPageReady] = useState(false)

  const [mode, setMode] = useState<'instance' | 'strategy'>('instance')
  const [selectedInstanceId, setSelectedInstanceId] = useState('')
  const [selectedStrategyId, setSelectedStrategyId] = useState('')
  const [overrideParams, setOverrideParams] = useState<Record<string, string>>({})
  const [stockCode, setStockCode] = useState<StockSearchItem>({ code: '' } as StockSearchItem)
  const [batchStockCodes, setBatchStockCodes] = useState<StockSearchItem[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [selectionType, setSelectionType] = useState<'list' | 'group'>('list')
  // 分组预览
  const [groupItems, setGroupItems] = useState<Array<{ id: number; stock_code: string; stock_name: string }>>([])
  const [groupPreviewVisible, setGroupPreviewVisible] = useState(false)
  const [groupAddVisible, setGroupAddVisible] = useState(false)
  const [groupAddStocks, setGroupAddStocks] = useState<StockSearchItem[]>([])
  const [backtestType, setBacktestType] = useState<'single' | 'batch'>('single')
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')

  // 区间模式配置
  const [intervalMode, setIntervalMode] = useState<'full' | 'train_val_test'>('full')
  const [trainRatio, setTrainRatio] = useState(0.7)
  const [valRatio, setValRatio] = useState(0.15)
  const [testRatio, setTestRatio] = useState(0.15)

  // 交易成本配置
  const [costExpanded, setCostExpanded] = useState(false)
  const [commissionBuy, setCommissionBuy] = useState(0.0003)
  const [commissionSell, setCommissionSell] = useState(0.0013)
  const [slippagePct, setSlippagePct] = useState(0)
  const [slippageFixed, setSlippageFixed] = useState(0)
  const [minCommission, setMinCommission] = useState(5)

  // 基准选择
  const [benchmarkCode, setBenchmarkCode] = useState('000300.SH')

  const navigate = useNavigate()

  /** 生成绩效报告并跳转到绩效报告页面 */
  const handlePerformanceAnalysis = async (stockCode: string, metrics: EnhancedMetrics) => {
    try {
      const strategyName = currentStrategy?.name || currentInstance?.name || selectedStrategyId
      const payload = {
        report_type: 'common',
        strategy_name: `${strategyName}_${stockCode}`,
        strategy_params: JSON.stringify(parseParams()),
        initial_cash: metrics.initial_nav,
        start_date: startDate,
        end_date: endDate,
      }
      await postJson('/api/v1/performance/generate', payload)
      toast('success', `绩效报告已生成：${stockCode}`)
      navigate('/strategy/performance')
    } catch (e) {
      toast('error', `生成绩效报告失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  useEffect(() => {
    Promise.all([
      fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies'),
      fetchJson<{ instances: StrategyInstance[] }>('/api/v1/analysis/strategy-instances'),
      fetchJson<{ ok: boolean; groups: StockGroup[] }>('/api/v1/stock-groups'),
    ]).then(([s, i, g]) => {
      setStrategies(s.strategies || [])
      setInstances(i.instances || [])
      setGroups(g.groups || [])
      if (s.strategies?.length) setSelectedStrategyId(s.strategies[0].strategy_id)
      // 处理 URL 中携带的 instance_id，自动选中对应的策略实例
      const urlInstanceId = searchParams.get('instance_id')
      if (urlInstanceId && i.instances?.find((x: StrategyInstance) => x.instance_id === urlInstanceId)) {
        setMode('instance')
        setSelectedInstanceId(urlInstanceId)
      }
      setPageReady(true)
    }).catch((e) => toast('error', e instanceof Error ? e.message : String(e)))
  }, [])

  const currentInstance = instances.find((x) => x.instance_id === selectedInstanceId)
  const currentStrategy = strategies.find((s) => s.strategy_id === (currentInstance?.strategy_id || selectedStrategyId))

  useEffect(() => {
    if (currentInstance) {
      const params: Record<string, string> = {}
      for (const [k, v] of Object.entries(currentInstance.params)) {
        params[k] = String(v)
      }
      setOverrideParams(params)
      setSelectedStrategyId(currentInstance.strategy_id)
    }
  }, [selectedInstanceId])

  useEffect(() => {
    if (!currentInstance && currentStrategy) {
      const params: Record<string, string> = {}
      for (const [k, v] of Object.entries(currentStrategy.default_params)) {
        params[k] = String(v)
      }
      setOverrideParams(params)
    }
  }, [selectedStrategyId, currentInstance])

  const parseParams = () => {
    const params: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(overrideParams)) {
      const meta = currentStrategy?.params_schema?.[k]
      if (!meta) continue
      if (meta.type === 'int') params[k] = parseInt(String(v), 10)
      else if (meta.type === 'float') params[k] = parseFloat(String(v))
      else if (meta.type === 'bool') params[k] = v === 'true'
      else if (meta.type === 'enum') params[k] = String(v)
      else if (meta.type === 'object') {
        try { params[k] = JSON.parse(String(v)) }
        catch { params[k] = {} }
      } else params[k] = v
    }
    return params
  }

  /** 综合参数校验：检查所有必填项、参数类型和取值范围 */
  const validateBacktestParams = (): ValidationError[] => {
    const errors: ValidationError[] = []

    // 1) 策略选择校验
    if (mode === 'instance') {
      if (!selectedInstanceId) {
        errors.push({ field: '策略实例', message: '请从下拉列表中选择一个策略实例，或切换到"直接选策略"模式' })
      }
      const inst = instances.find((x) => x.instance_id === selectedInstanceId)
      if (inst && !strategies.find((s) => s.strategy_id === inst.strategy_id)) {
        errors.push({ field: '策略实例', message: `实例 "${inst.name}" 对应的策略 "${inst.strategy_id}" 不存在，请重新选择` })
      }
    } else {
      if (!selectedStrategyId) {
        errors.push({ field: '策略', message: '请从下拉列表中选择一个策略' })
      }
    }

    // 2) 股票代码校验
    if (backtestType === 'single') {
      const code = stockCode?.code || ''
      if (!code) {
        errors.push({ field: '股票代码', message: '请在股票选择框中搜索并选择一只股票' })
      } else if (!/^\d{6}\.(SH|SZ|BJ)$/i.test(code)) {
        errors.push({ field: '股票代码', message: `"${code}" 格式不正确，应为 6位数字 + . + SH/SZ/BJ，如 600519.SH` })
      }
    } else {
      // 批量回测
      if (selectionType === 'list') {
        if (batchStockCodes.length === 0) {
          errors.push({ field: '股票列表', message: '请通过股票多选组件选择至少一只股票，或切换到"选择股票分组"模式' })
        } else {
          const invalidCodes = batchStockCodes.filter((c) => !/^\d{6}\.(SH|SZ|BJ)$/i.test(c.code))
          if (invalidCodes.length > 0) {
            errors.push({ field: '股票列表', message: `以下代码格式不正确：${invalidCodes.map((c) => c.code).join('、')}。应为 6位数字.SH/SZ/BJ 格式` })
          }
        }
      } else {
        if (!selectedGroupId) {
          errors.push({ field: '股票分组', message: '请选择一个股票分组，或切换到"输入股票列表"模式' })
        }
      }
    }

    // 3) 日期范围校验
    if (!startDate) {
      errors.push({ field: '开始日期', message: '开始日期不能为空' })
    }
    if (!endDate) {
      errors.push({ field: '结束日期', message: '结束日期不能为空' })
    }
    if (startDate && endDate && startDate >= endDate) {
      errors.push({ field: '日期范围', message: `结束日期 ${endDate} 必须晚于开始日期 ${startDate}` })
    }
    // 检查日期格式
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/
    if (startDate && !dateRegex.test(startDate)) {
      errors.push({ field: '开始日期', message: `"${startDate}" 格式不正确，应为 YYYY-MM-DD 格式` })
    }
    if (endDate && !dateRegex.test(endDate)) {
      errors.push({ field: '结束日期', message: `"${endDate}" 格式不正确，应为 YYYY-MM-DD 格式` })
    }

    // 4) 策略参数校验
    if (currentStrategy) {
      for (const [key, meta] of Object.entries(currentStrategy.params_schema)) {
        const value = overrideParams[key]
        if (meta.type === 'int') {
          const parsed = parseInt(String(value), 10)
          if (isNaN(parsed)) {
            errors.push({ field: `参数「${meta.label}」`, message: `"${value}" 不是有效的整数` })
          } else {
            if (meta.min !== undefined && parsed < meta.min) {
              errors.push({ field: `参数「${meta.label}」`, message: `最小值 ${meta.min}，当前值 ${parsed}` })
            }
            if (meta.max !== undefined && parsed > meta.max) {
              errors.push({ field: `参数「${meta.label}」`, message: `最大值 ${meta.max}，当前值 ${parsed}` })
            }
          }
        } else if (meta.type === 'float') {
          const parsed = parseFloat(String(value))
          if (isNaN(parsed)) {
            errors.push({ field: `参数「${meta.label}」`, message: `"${value}" 不是有效的浮点数` })
          } else {
            if (meta.min !== undefined && parsed < meta.min) {
              errors.push({ field: `参数「${meta.label}」`, message: `最小值 ${meta.min}，当前值 ${parsed}` })
            }
            if (meta.max !== undefined && parsed > meta.max) {
              errors.push({ field: `参数「${meta.label}」`, message: `最大值 ${meta.max}，当前值 ${parsed}` })
            }
          }
        }
      }
    }

    // 5) 区间模式比例校验
    if (intervalMode === 'train_val_test') {
      const total = Math.round((trainRatio + valRatio + testRatio) * 100)
      if (total !== 100) {
        errors.push({ field: '区间比例', message: `训练/验证/测试比例之和为 ${total}%，必须等于 100%（当前：训练 ${(trainRatio*100).toFixed(0)}%、验证 ${(valRatio*100).toFixed(0)}%、测试 ${(testRatio*100).toFixed(0)}%）` })
      }
    }

    return errors
  }

  /** 构建通用请求体（包含区间模式、交易成本、基准等增强参数） */
  const buildEnhancedPayload = () => {
    const params = parseParams()
    const payload: Record<string, unknown> = {
      start: startDate,
      end: endDate,
      strategy_id: currentInstance?.strategy_id || selectedStrategyId,
      params,
      interval_mode: intervalMode,
      benchmark_code: benchmarkCode,
    }

    // 区间模式参数
    if (intervalMode === 'train_val_test') {
      payload.train_ratio = trainRatio
      payload.val_ratio = valRatio
      payload.test_ratio = testRatio
    }

    // 交易成本参数
    payload.commission_buy = commissionBuy
    payload.commission_sell = commissionSell
    payload.slippage_pct = slippagePct
    payload.slippage_fixed = slippageFixed
    payload.min_commission = minCommission

    return payload
  }

  const runSingle = async () => {
    setBacktestError(null)
    setValidationErrors([])

    const errs = validateBacktestParams()
    if (errs.length > 0) {
      setValidationErrors(errs)
      toast('error', `参数校验未通过（共 ${errs.length} 项），请修正后重新提交`)
      return
    }

    setRunning(true)
    const payload = buildEnhancedPayload()
    payload.stock_code = stockCode?.code || ''

    const traceLabel = `回测-${payload.stock_code}-${Date.now()}`
    console.time(traceLabel)
    console.log(`[回测请求开始] 股票=${payload.stock_code} 策略=${payload.strategy_id} 区间=${payload.interval_mode} 基准=${payload.benchmark_code || '无'}`)
    console.log(`[回测请求参数] 开始=${payload.start} 结束=${payload.end} 参数=${JSON.stringify(payload.params)}`)

    try {
      const r = await postJson<SingleBacktestResult>('/api/v1/analysis/backtest/run', payload)
      console.timeEnd(traceLabel)
      const metrics = r.metrics
      if (metrics) {
        console.log(`[回测完成] 总收益率=${metrics.total_return} 夏普=${metrics.sharpe} 最大回撤=${metrics.max_drawdown} 交易次数=${r.trades?.length || 0}`)
      } else {
        console.log(`[回测完成] 区间模式结果 interval_results=${r.interval_results?.length || 0}`)
      }

      setSingleResult(r)
      setBatchResult(null)
      const responseAny = r as unknown as Record<string, unknown>
      if (responseAny.backtest_id) {
        toast('success', '回测完成，已保存到回测历史')
      } else {
        toast('success', '回测完成')
      }
      window.dispatchEvent(new Event('backtest-completed'))
    } catch (e) {
      console.timeEnd(traceLabel)
      const errorMsg = e instanceof Error ? e.message : String(e)
      console.error(`[回测失败] ${errorMsg}`)
      setBacktestError(errorMsg)
      toast('error', `回测失败：${errorMsg}`)
    } finally {
      setRunning(false)
    }
  }

  const runBatch = async () => {
    // 清空之前的错误
    setBacktestError(null)
    setValidationErrors([])

    // 1) 执行综合参数校验，校验未通过则阻止回测
    const errs = validateBacktestParams()
    if (errs.length > 0) {
      setValidationErrors(errs)
      toast('error', `参数校验未通过（共 ${errs.length} 项），请修正后重新提交`)
      return
    }

    setRunning(true)
    try {
      const payload = buildEnhancedPayload()
      payload.selection_type = selectionType
      payload.max_workers = 4

      if (selectionType === 'list') {
        payload.stock_codes = batchStockCodes.map((s) => s.code)
      } else {
        payload.group_id = selectedGroupId
      }

      const r = await postJson<BatchBacktestResult>('/api/v1/analysis/backtest/batch', payload)
      setBatchResult(r)
      setSingleResult(null)
      toast('success', `批量回测完成：成功 ${r.completed_tasks} 只，失败 ${r.failed_tasks} 只`)
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : String(e)
      setBacktestError(errorMsg)
      toast('error', `回测失败：${errorMsg}`)
    } finally {
      setRunning(false)
    }
  }

  /** 调整训练比例，自动调整测试比例保持总和为1 */
  const handleTrainRatioChange = (val: number) => {
    setTrainRatio(val)
    const remaining = 1 - val
    if (remaining < valRatio) {
      setValRatio(0)
      setTestRatio(remaining)
    } else {
      setTestRatio(+(remaining - valRatio).toFixed(4))
    }
  }

  /** 调整验证比例，自动调整测试比例保持总和为1 */
  const handleValRatioChange = (val: number) => {
    const remaining = 1 - trainRatio
    if (val > remaining) {
      val = remaining
    }
    setValRatio(val)
    setTestRatio(+(remaining - val).toFixed(4))
  }

  const stratName = currentStrategy?.name || selectedStrategyId

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="回测参数" right={
          <button
            onClick={() => setHistoryVisible(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
          >
            <History className="h-3.5 w-3.5" />
            回测历史
          </button>
        } />
        <CardBody>
          <div className="space-y-4">
            {/* 回测类型和模式选择 */}
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" checked={backtestType === 'single'} onChange={() => setBacktestType('single')} className="accent-zinc-900" />
                  单只股票回测
                </label>
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" checked={backtestType === 'batch'} onChange={() => setBacktestType('batch')} className="accent-zinc-900" />
                  批量多股票回测
                </label>
              </div>
              <div className="flex items-center gap-3 ml-auto">
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" checked={mode === 'instance'} onChange={() => { setMode('instance'); setSelectedInstanceId('') }} className="accent-zinc-900" />
                  从实例选择
                </label>
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" checked={mode === 'strategy'} onChange={() => { setMode('strategy'); setSelectedInstanceId('') }} className="accent-zinc-900" />
                  直接选策略
                </label>
              </div>
            </div>

            {/* 策略和股票选择 */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {mode === 'instance' ? (
                <div>
                  <div className="mb-1 text-xs text-zinc-500">策略实例</div>
                  <select
                    value={selectedInstanceId}
                    onChange={(e) => setSelectedInstanceId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    <option value="">— 请选择实例 —</option>
                    {instances.map((inst) => (
                      <option key={inst.instance_id} value={inst.instance_id}>
                        {inst.name}（{strategies.find((s) => s.strategy_id === inst.strategy_id)?.name || inst.strategy_id}）
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <div className="mb-1 text-xs text-zinc-500">策略</div>
                  <select
                    value={selectedStrategyId}
                    onChange={(e) => setSelectedStrategyId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    {strategies.map((s) => (
                      <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {backtestType === 'single' ? (
                <div>
                  <div className="mb-1 text-xs text-zinc-500">股票代码</div>
                  <StockPicker
                    mode="single"
                    value={stockCode}
                    onChange={(val) => {
                      if (val && !Array.isArray(val)) {
                        setStockCode(val as StockSearchItem)
                      }
                    }}
                    placeholder="搜索股票代码或名称"
                  />
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-1.5 text-sm">
                      <input type="radio" checked={selectionType === 'list'} onChange={() => setSelectionType('list')} className="accent-zinc-900" />
                      股票列表
                    </label>
                    <label className="flex items-center gap-1.5 text-sm">
                      <input type="radio" checked={selectionType === 'group'} onChange={() => setSelectionType('group')} className="accent-zinc-900" />
                      股票分组
                    </label>
                  </div>
                  {selectionType === 'list' ? (
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">股票列表（可搜索多选）</div>
                      <StockPicker
                        mode="multiple"
                        value={batchStockCodes}
                        onChange={(val) => setBatchStockCodes((val as StockSearchItem[]) || [])}
                        placeholder="搜索股票代码或名称，多选添加"
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <select
                          value={selectedGroupId ?? ''}
                          onChange={(e) => setSelectedGroupId(parseInt(e.target.value, 10) || null)}
                          className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                        >
                          <option value="">— 请选择分组 —</option>
                          {groups.map((g) => (
                            <option key={g.id} value={g.id}>
                              {g.name}（{g.stock_count} 只股票）
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={async () => {
                            if (!selectedGroupId) return
                            try {
                              const res = await fetchJson<{ ok: boolean; items: Array<{ id: number; stock_code: string; stock_name: string }> }>(`/api/v1/stock-groups/${selectedGroupId}/items`)
                              setGroupItems(res.items || [])
                              setGroupPreviewVisible(true)
                            } catch (e) {
                              toast('error', `加载分组股票失败：${e instanceof Error ? e.message : String(e)}`)
                            }
                          }}
                          disabled={!selectedGroupId}
                          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                        >
                          预览
                        </button>
                        <button
                          onClick={() => {
                            if (!selectedGroupId) return
                            setGroupAddStocks([])
                            setGroupAddVisible(true)
                          }}
                          disabled={!selectedGroupId}
                          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                        >
                          追加
                        </button>
                      </div>
                      {selectedGroupId && groupItems.length > 0 && !groupPreviewVisible && (
                        <div className="text-xs text-zinc-500">
                          已选分组共 {groupItems.length} 只股票
                        </div>
                      )}
                    </div>
                  )}

                  {/* 分组预览弹窗 */}
                  {groupPreviewVisible && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setGroupPreviewVisible(false)}>
                      <div className="w-[600px] max-h-[70vh] overflow-auto rounded-lg bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
                        <div className="sticky top-0 flex items-center justify-between border-b border-zinc-200 bg-white px-5 py-3">
                          <span className="text-sm font-semibold text-zinc-900">
                            分组股票预览（{groupItems.length} 只）
                          </span>
                          <button onClick={() => setGroupPreviewVisible(false)} className="text-xs text-zinc-500 hover:text-zinc-700">关闭</button>
                        </div>
                        <div className="p-4 space-y-1.5">
                          {groupItems.map((item) => (
                            <div key={item.id} className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2">
                              <div>
                                <span className="text-sm font-semibold text-zinc-900">{item.stock_code}</span>
                                {item.stock_name && <span className="ml-2 text-xs text-zinc-500">{item.stock_name}</span>}
                              </div>
                              <button
                                onClick={async () => {
                                  try {
                                    await fetchJson(`/api/v1/stock-groups/${selectedGroupId}/items/${item.id}`, { method: 'DELETE' })
                                    setGroupItems((prev) => prev.filter((x) => x.id !== item.id))
                                    setGroups((prev) => prev.map((g) => g.id === selectedGroupId ? { ...g, stock_count: Math.max(0, g.stock_count - 1) } : g))
                                    toast('success', `已删除 ${item.stock_code}`)
                                  } catch (e) {
                                    toast('error', `删除失败：${e instanceof Error ? e.message : String(e)}`)
                                  }
                                }}
                                className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                              >
                                删除
                              </button>
                            </div>
                          ))}
                          {groupItems.length === 0 && (
                            <div className="py-6 text-center text-xs text-zinc-500">分组中没有股票</div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* 追加股票弹窗 */}
                  {groupAddVisible && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setGroupAddVisible(false)}>
                      <div className="w-[500px] rounded-lg bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
                          <span className="text-sm font-semibold text-zinc-900">追加股票到分组</span>
                          <button onClick={() => setGroupAddVisible(false)} className="text-xs text-zinc-500 hover:text-zinc-700">关闭</button>
                        </div>
                        <div className="p-4 space-y-3">
                          <StockPicker
                            mode="multiple"
                            value={groupAddStocks}
                            onChange={(val) => setGroupAddStocks((val as StockSearchItem[]) || [])}
                            placeholder="搜索股票代码或名称"
                          />
                          <div className="flex justify-end gap-2">
                            <button onClick={() => setGroupAddVisible(false)} className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-xs text-zinc-700 hover:bg-zinc-50">
                              取消
                            </button>
                            <button
                              onClick={async () => {
                                if (!selectedGroupId || groupAddStocks.length === 0) return
                                try {
                                  const codes = groupAddStocks.map((s) => s.code)
                                  await postJson(`/api/v1/stock-groups/${selectedGroupId}/items`, { stock_codes: codes })
                                  toast('success', `已追加 ${codes.length} 只股票`)
                                  setGroupAddVisible(false)
                                  setGroupAddStocks([])
                                  // 刷新分组列表
                                  const g = await fetchJson<{ ok: boolean; groups: StockGroup[] }>('/api/v1/stock-groups')
                                  if (g.groups) setGroups(g.groups)
                                  // 刷新预览
                                  const res = await fetchJson<{ ok: boolean; items: Array<{ id: number; stock_code: string; stock_name: string }> }>(`/api/v1/stock-groups/${selectedGroupId}/items`)
                                  setGroupItems(res.items || [])
                                } catch (e) {
                                  toast('error', `追加失败：${e instanceof Error ? e.message : String(e)}`)
                                }
                              }}
                              disabled={groupAddStocks.length === 0}
                              className="rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
                            >
                              确认追加
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div>
                <div className="mb-1 text-xs text-zinc-500">开始日期</div>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>

              <div>
                <div className="mb-1 text-xs text-zinc-500">结束日期</div>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>
            </div>

            {/* 参数配置 */}
            {currentStrategy && Object.keys(currentStrategy.params_schema).length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-zinc-900">
                    {mode === 'instance' ? '实例参数（只读）' : '策略参数'}
                  </span>
                  {mode === 'instance' && (
                    <span className="text-xs text-zinc-400">参数来自实例，不可修改</span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {Object.entries(currentStrategy.params_schema).map(([key, meta]) => (
                    <div key={key}>
                      <div className="mb-1 text-xs text-zinc-500">{meta.label}</div>
                      {meta.type === 'bool' ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={overrideParams[key] === 'true'}
                            onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: String(e.target.checked) }))}
                            disabled={mode === 'instance'}
                            className="h-4 w-4 accent-zinc-900"
                          />
                          <span className={`text-xs ${mode === 'instance' ? 'text-zinc-400' : 'text-zinc-500'}`}>
                            {overrideParams[key] === 'true' ? '开启' : '关闭'}
                          </span>
                        </div>
                      ) : meta.type === 'enum' ? (
                        <select
                          value={overrideParams[key] ?? ''}
                          onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                          disabled={mode === 'instance'}
                          className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400"
                        >
                          {meta.values?.map((v) => (
                            <option key={v} value={v}>{v}</option>
                          ))}
                        </select>
                      ) : meta.type === 'object' ? (
                        <textarea
                          value={overrideParams[key] ?? '{}'}
                          onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                          disabled={mode === 'instance'}
                          rows={2}
                          className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-mono outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400"
                          placeholder='{"key": "value"}'
                        />
                      ) : (
                        <input
                          type="number"
                          value={overrideParams[key] ?? String(meta.default ?? '')}
                          onChange={(e) => setOverrideParams((p) => ({ ...p, [key]: e.target.value }))}
                          disabled={mode === 'instance'}
                          min={meta.min}
                          max={meta.max}
                          step={meta.step}
                          className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400"
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 区间模式配置 */}
            <div>
              <div className="mb-2 text-xs font-semibold text-zinc-900">区间模式</div>
              <div className="flex items-center gap-4 mb-2">
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" checked={intervalMode === 'full'} onChange={() => setIntervalMode('full')} className="accent-zinc-900" />
                  全区间回测
                </label>
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="radio" checked={intervalMode === 'train_val_test'} onChange={() => setIntervalMode('train_val_test')} className="accent-zinc-900" />
                  训练/验证/测试划分
                </label>
              </div>
              {intervalMode === 'train_val_test' && (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 space-y-3">
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">训练集比例</div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0.1}
                          max={0.9}
                          step={0.05}
                          value={trainRatio}
                          onChange={(e) => handleTrainRatioChange(parseFloat(e.target.value))}
                          className="flex-1 accent-zinc-900"
                        />
                        <span className="text-sm font-medium w-12 text-right">{(trainRatio * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">验证集比例</div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0}
                          max={0.8}
                          step={0.05}
                          value={valRatio}
                          onChange={(e) => handleValRatioChange(parseFloat(e.target.value))}
                          className="flex-1 accent-zinc-900"
                        />
                        <span className="text-sm font-medium w-12 text-right">{(valRatio * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">测试集比例</div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={0}
                          max={0.8}
                          step={0.05}
                          value={testRatio}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value)
                            const remaining = 1 - trainRatio
                            setTestRatio(val)
                            setValRatio(+(remaining - val).toFixed(4))
                          }}
                          className="flex-1 accent-zinc-900"
                        />
                        <span className="text-sm font-medium w-12 text-right">{(testRatio * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-zinc-400">
                    比例总和：{((trainRatio + valRatio + testRatio) * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>

            {/* 交易成本配置（折叠面板） */}
            <div>
              <button
                onClick={() => setCostExpanded(!costExpanded)}
                className="flex items-center gap-1.5 text-xs font-semibold text-zinc-900 hover:text-zinc-700"
              >
                {costExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                交易成本配置
              </button>
              {costExpanded && (
                <div className="mt-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">买入佣金率</div>
                      <input
                        type="number"
                        value={commissionBuy}
                        onChange={(e) => setCommissionBuy(parseFloat(e.target.value) || 0)}
                        step={0.0001}
                        className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">卖出佣金率（含印花税）</div>
                      <input
                        type="number"
                        value={commissionSell}
                        onChange={(e) => setCommissionSell(parseFloat(e.target.value) || 0)}
                        step={0.0001}
                        className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">滑点百分比</div>
                      <input
                        type="number"
                        value={slippagePct}
                        onChange={(e) => setSlippagePct(parseFloat(e.target.value) || 0)}
                        step={0.001}
                        className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">固定滑点</div>
                      <input
                        type="number"
                        value={slippageFixed}
                        onChange={(e) => setSlippageFixed(parseFloat(e.target.value) || 0)}
                        step={0.01}
                        className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-zinc-500">最低手续费</div>
                      <input
                        type="number"
                        value={minCommission}
                        onChange={(e) => setMinCommission(parseFloat(e.target.value) || 0)}
                        step={1}
                        className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 基准选择 */}
            <div>
              <div className="mb-2 text-xs font-semibold text-zinc-900">基准指数</div>
              <select
                value={benchmarkCode}
                onChange={(e) => setBenchmarkCode(e.target.value)}
                className="w-full max-w-xs rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
              >
                <option value="000300.SH">沪深300 (000300.SH)</option>
                <option value="000016.SH">上证50 (000016.SH)</option>
                <option value="000905.SH">中证500 (000905.SH)</option>
                <option value="">无基准</option>
              </select>
            </div>

            {currentStrategy?.requires_chan && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                此策略依赖缠论数据，当前环境暂不支持缠论策略回测
              </div>
            )}
            {currentStrategy?.requires_predictions && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                此策略依赖ML预测数据，需通过参数传入 predictions 字典
              </div>
            )}
            <button
              onClick={backtestType === 'single' ? runSingle : runBatch}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {running ? '回测中...' : backtestType === 'single' ? '开始回测' : '开始批量回测'}
            </button>
          </div>
        </CardBody>
      </Card>

      {/* 参数校验错误（优先显示，用户修正后自动消失） */}
      {validationErrors.length > 0 && (
        <ValidationErrors errors={validationErrors} onClose={() => setValidationErrors([])} />
      )}

      {/* 错误详情展示（可折叠） */}
      {backtestError && (
        <ErrorDetailDisplay error={backtestError} onClose={() => setBacktestError(null)} />
      )}

      {/* 单只股票回测结果 */}
      {singleResult && (
        <>
          {/* 指标展示（非区间模式或全区间模式有 metrics） */}
          {singleResult.metrics && (
            <>
              <MetricsDisplay metrics={singleResult.metrics} />

              {/* 绩效分析按钮 */}
              <div className="flex justify-end">
                <button
                  onClick={() => handlePerformanceAnalysis(singleResult.stock_code, singleResult.metrics!)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                >
                  <BarChart3 className="h-4 w-4" />
                  绩效分析
                </button>
              </div>

              {/* ECharts 图表区域 */}
              <BacktestCharts
                navLog={singleResult.nav_log}
                benchmarkNavLog={singleResult.benchmark_nav_log}
                drawdownLog={singleResult.drawdown_log}
                monthlyReturns={singleResult.monthly_returns}
              />
            </>
          )}

          {/* 区间模式结果展示 */}
          {singleResult.interval_results && singleResult.interval_results.length > 0 && (
            <>
              {!singleResult.metrics && (
                <div className="text-sm font-semibold text-zinc-900 mb-4">区间划分结果</div>
              )}
              {singleResult.metrics && (
                <div className="text-sm font-semibold text-zinc-900">区间划分结果</div>
              )}
              {singleResult.interval_results.map((ir, idx) => (
                <IntervalResultDisplay key={idx} intervalResult={ir} />
              ))}
            </>
          )}

          {/* 交易记录（仅在 metrics 存在且有交易时显示） */}
          {singleResult.metrics && (
            <Card>
              <CardHeader title={`交易记录（${singleResult.trades.length} 笔）`} />
              <CardBody className="p-0">
                {singleResult.trades.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-zinc-500">无交易记录</div>
                ) : (
                  <div className="max-h-80 overflow-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-zinc-50 text-xs text-zinc-500">
                        <tr>
                          <th className="px-4 py-2">日期</th>
                          <th className="px-4 py-2">方向</th>
                          <th className="px-4 py-2">价格</th>
                          <th className="px-4 py-2">数量</th>
                          <th className="px-4 py-2">金额</th>
                          <th className="px-4 py-2">备注</th>
                        </tr>
                      </thead>
                      <tbody>
                        {singleResult.trades.map((t, i) => (
                          <tr key={i} className="border-t border-zinc-100">
                            <td className="px-4 py-2 text-xs text-zinc-700">{t.date}</td>
                            <td className="px-4 py-2">
                              <Badge tone={t.action === 'buy' ? 'green' : 'red'}>
                                {t.action === 'buy' ? '买入' : '卖出'}
                              </Badge>
                            </td>
                            <td className="px-4 py-2 text-zinc-900">{t.price}</td>
                            <td className="px-4 py-2 text-zinc-700">{t.qty}</td>
                            <td className="px-4 py-2 text-zinc-700">
                              {t.action === 'buy' ? `-${
                                t.cost != null ? t.cost.toLocaleString() : '—'
                              }` : `+${
                                t.proceeds != null ? t.proceeds.toLocaleString() : '—'
                              }`}
                            </td>
                            <td className="px-4 py-2 text-xs text-zinc-400">{t.note || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </>
      )}

      {/* 批量回测结果 */}
      {batchResult && (
        <>
          <Card>
            <CardHeader title="批量回测汇总" />
            <CardBody>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4 mb-4">
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3">
                  <div className="text-2xl font-bold text-zinc-900">{batchResult.total_tasks}</div>
                  <div className="mt-1 text-xs text-zinc-500">总股票数</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3">
                  <div className="text-2xl font-bold text-green-600">{batchResult.completed_tasks}</div>
                  <div className="mt-1 text-xs text-zinc-500">成功数量</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3">
                  <div className="text-2xl font-bold text-red-600">{batchResult.failed_tasks}</div>
                  <div className="mt-1 text-xs text-zinc-500">失败数量</div>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3">
                  <div className="text-2xl font-bold text-zinc-900">{batchResult.aggregated.win_stocks}</div>
                  <div className="mt-1 text-xs text-zinc-500">正收益股票数</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <MetricCard label="平均收益率" value={`${(batchResult.aggregated.avg_total_return * 100).toFixed(2)}`} unit="%" tone={batchResult.aggregated.avg_total_return > 0 ? 'up' : 'down'} />
                <MetricCard label="平均年化" value={`${(batchResult.aggregated.avg_annual_return * 100).toFixed(2)}`} unit="%" tone={batchResult.aggregated.avg_annual_return > 0 ? 'up' : 'down'} />
                <MetricCard label="平均回撤" value={`${(batchResult.aggregated.avg_max_drawdown * 100).toFixed(2)}`} unit="%" tone="down" />
                <MetricCard label="平均夏普" value={batchResult.aggregated.avg_sharpe.toFixed(3)} />
                <MetricCard label="总交易次数" value={batchResult.aggregated.total_trades} />
              </div>

              {batchResult.aggregated.best_stock && (
                <div className="mt-4 flex items-center gap-2 text-sm">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                  <span className="text-zinc-500">最佳股票：</span>
                  <span className="font-medium text-zinc-900">{batchResult.aggregated.best_stock.code}</span>
                  <span className="text-green-600 font-medium">+{(batchResult.aggregated.best_stock.return * 100).toFixed(2)}%</span>
                </div>
              )}
              {batchResult.aggregated.worst_stock && (
                <div className="flex items-center gap-2 text-sm">
                  <TrendingDown className="h-4 w-4 text-red-600" />
                  <span className="text-zinc-500">最差股票：</span>
                  <span className="font-medium text-zinc-900">{batchResult.aggregated.worst_stock.code}</span>
                  <span className="text-red-600 font-medium">{(batchResult.aggregated.worst_stock.return * 100).toFixed(2)}%</span>
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="股票回测详情" />
            <CardBody className="p-0">
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs text-zinc-500 sticky top-0">
                    <tr>
                      <th className="px-4 py-2">股票代码</th>
                      <th className="px-4 py-2">状态</th>
                      <th className="px-4 py-2">总收益率</th>
                      <th className="px-4 py-2">年化收益率</th>
                      <th className="px-4 py-2">最大回撤</th>
                      <th className="px-4 py-2">交易次数</th>
                      <th className="px-4 py-2">胜率</th>
                      <th className="px-4 py-2">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchResult.results.map((r) => {
                      const tr = (r.metrics?.total_return as number) || 0
                      const tone = tr > 0 ? 'up' : tr < 0 ? 'down' : 'neutral'
                      const toneCls = tone === 'up' ? 'text-red-600' : tone === 'down' ? 'text-green-600' : 'text-zinc-900'
                      return (
                        <tr key={r.task_id} className="border-t border-zinc-100">
                          <td className="px-4 py-2 text-xs font-mono text-zinc-700">{r.stock_code}</td>
                          <td className="px-4 py-2">
                            {r.status === 'completed' ? (
                              <span className="inline-flex items-center gap-1 text-xs text-green-600">
                                <CheckCircle2 className="h-3 w-3" />
                                成功
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs text-red-600">
                                <XCircle className="h-3 w-3" />
                                {r.error || '失败'}
                              </span>
                            )}
                          </td>
                          <td className={`px-4 py-2 font-medium ${toneCls}`}>
                            {r.metrics ? `${tr > 0 ? '+' : ''}${(tr * 100).toFixed(2)}%` : '—'}
                          </td>
                          <td className="px-4 py-2 text-zinc-700">
                            {r.metrics ? (
                              (() => {
                                const ar = ((r.metrics.annual_return as number) || 0) * 100;
                                return `${ar > 0 ? '+' : ''}${ar.toFixed(2)}%`;
                              })()
                            ) : '—'}
                          </td>
                          <td className="px-4 py-2 text-green-600">
                            {r.metrics ? `${(((r.metrics.max_drawdown as number) || 0) * 100).toFixed(2)}%` : '—'}
                          </td>
                          <td className="px-4 py-2 text-zinc-700">
                            {r.metrics ? (r.metrics.total_trades as number) : '—'}
                          </td>
                          <td className="px-4 py-2 text-zinc-700">
                            {r.metrics ? `${(((r.metrics.win_rate as number) || 0) * 100).toFixed(1)}%` : '—'}
                          </td>
                          <td className="px-4 py-2">
                            {r.status === 'completed' && r.metrics && (
                              <button
                                onClick={() => handlePerformanceAnalysis(
                                  r.stock_code,
                                  r.metrics as unknown as EnhancedMetrics
                                )}
                                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700"
                              >
                                <BarChart3 className="h-3 w-3" />
                                绩效分析
                              </button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        </>
      )}

      {/* 回测历史模态框 */}
      {historyVisible && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-12" onClick={() => setHistoryVisible(false)}>
          <div className="w-[1000px] max-h-[85vh] overflow-auto rounded-lg bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4">
              <button
                onClick={() => setHistoryVisible(false)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
              >
                ← 返回
              </button>
              <h3 className="text-lg font-semibold text-zinc-900">回测历史</h3>
              <div className="w-20" />
            </div>
            <div className="p-6">
              <BacktestHistory />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
