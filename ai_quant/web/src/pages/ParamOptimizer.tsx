import { useState, useEffect, useCallback } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Play, ChevronDown, ChevronUp } from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'

/* ---------- 数据类型 ---------- */

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
}

interface ParamCombination {
  params: Record<string, unknown>
  total_return: number
  annual_return?: number
  sharpe?: number
  max_drawdown?: number
  win_rate?: number
  num_trades?: number
}

interface ParamSearchResult {
  strategy_id: string
  stock_code: string
  total_combinations: number
  results: ParamCombination[]
  best_by_return: ParamCombination | null
  best_by_sharpe: ParamCombination | null
}

/* ---------- 指标标签映射 ---------- */

const METRIC_LABELS: Record<string, string> = {
  total_return: '总收益率',
  annual_return: '年化收益率',
  sharpe: '夏普比率',
  max_drawdown: '最大回撤',
  win_rate: '胜率',
  num_trades: '交易次数',
}

const METRICS = ['total_return', 'annual_return', 'sharpe', 'max_drawdown', 'win_rate', 'num_trades']

function isPctMetric(key: string) {
  return key !== 'sharpe' && key !== 'num_trades'
}

/* ---------- 参数影响曲线图组件 ---------- */

function ParamCurveChart({
  results,
  searchableParams,
}: {
  results: ParamCombination[]
  searchableParams: [string, { label: string }][]
}) {
  const [xParamKey, setXParamKey] = useState(searchableParams[0]?.[0] ?? '')
  const [yMetricKey, setYMetricKey] = useState('total_return')

  if (!xParamKey || results.length === 0) return null

  // 确定分组参数（X轴未选中的那个参数）
  const groupParamKeys = searchableParams
    .map(([key]) => key)
    .filter((key) => key !== xParamKey)

  // 获取X轴参数的所有唯一值，按数字排序
  const xValues = [...new Set(
    results.map((r) => Number(r.params[xParamKey]))
  )].sort((a, b) => a - b)

  if (xValues.length === 0) return null

  const xLabel = searchableParams.find(([k]) => k === xParamKey)?.[1]?.label || xParamKey
  const yLabel = METRIC_LABELS[yMetricKey] || yMetricKey
  const isPct = isPctMetric(yMetricKey)

  // 构建Series数据
  const colorPalette = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
  const series: any[] = []

  if (groupParamKeys.length === 0) {
    // 只有一个参数的情况：单条线
    const data = xValues.map((xVal) => {
      const match = results.find((r) => Number(r.params[xParamKey]) === xVal)
      return match ? (match as any)[yMetricKey] ?? null : null
    })
    series.push({
      name: xLabel,
      type: 'line',
      data,
      smooth: false,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2 },
    })
  } else {
    // 多个参数：按分组参数的值生成多条线
    const groupKey = groupParamKeys[0]
    const groupValues = [...new Set(
      results.map((r) => Number(r.params[groupKey]))
    )].sort((a, b) => a - b)

    const groupLabel = searchableParams.find(([k]) => k === groupKey)?.[1]?.label || groupKey

    groupValues.forEach((gVal, idx) => {
      const data = xValues.map((xVal) => {
        const match = results.find(
          (r) => Number(r.params[xParamKey]) === xVal && Number(r.params[groupKey]) === gVal
        )
        return match ? (match as any)[yMetricKey] ?? null : null
      })
      series.push({
        name: `${groupLabel}=${gVal}`,
        type: 'line',
        data,
        smooth: false,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        color: colorPalette[idx % colorPalette.length],
      })
    })
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        if (!params?.length) return ''
        const xVal = params[0].axisValue
        let html = `<div style="font-size:12px"><b>${xLabel}: ${xVal}</b></div>`
        params.forEach((p: any) => {
          if (p.value != null || p.value === 0) {
            const val = !isPct ? p.value : `${(p.value * 100).toFixed(2)}%`
            html += `<div style="color:${p.color}">${p.seriesName}: ${val}</div>`
          }
        })
        return html
      },
    },
    legend: { type: 'scroll', right: 10, top: 20, orient: 'vertical', itemWidth: 10, itemHeight: 10 },
    grid: { left: 65, right: 100, top: 50, bottom: 30 },
    xAxis: {
      type: 'category',
      data: xValues.map(String),
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameTextStyle: { fontSize: 11 },
      axisLabel: {
        fontSize: 11,
        formatter: isPct
          ? (v: number) => `${(v * 100).toFixed(1)}%`
          : (v: number) => v.toFixed(2),
      },
    },
    series,
  }

  return (
    <Card>
      <CardHeader title="参数影响曲线" />
      <CardBody>
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500">X轴:</span>
            <select
              value={xParamKey}
              onChange={(e) => setXParamKey(e.target.value)}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-zinc-400"
            >
              {searchableParams.map(([key, meta]) => (
                <option key={key} value={key}>{meta.label} ({key})</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500">Y轴:</span>
            <select
              value={yMetricKey}
              onChange={(e) => setYMetricKey(e.target.value)}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-zinc-400"
            >
              {METRICS.map((key) => (
                <option key={key} value={key}>{METRIC_LABELS[key]}</option>
              ))}
            </select>
          </div>
        </div>
        <ReactECharts option={option} style={{ height: 380 }} />
      </CardBody>
    </Card>
  )
}

/* ---------- 资金分配与收益展示组件 ---------- */

/** 查找所有股票中总收益率最高的公共参数组合 */
function findBestCommonCombination(stockResults: Map<string, ParamSearchResult>): {
  params: Record<string, unknown>
  stocks: Map<string, number>
  avgTotalReturn: number
} | null {
  const comboMap = new Map<string, { params: Record<string, unknown>; stocks: Map<string, number> }>()

  for (const [code, res] of stockResults) {
    for (const r of res.results) {
      const key = JSON.stringify(r.params)
      if (!comboMap.has(key)) {
        comboMap.set(key, { params: r.params, stocks: new Map() })
      }
      comboMap.get(key)!.stocks.set(code, r.total_return)
    }
  }

  let bestKey = ''
  let bestAvg = -Infinity
  for (const [key, combo] of comboMap) {
    if (combo.stocks.size === stockResults.size) {
      const total = Array.from(combo.stocks.values()).reduce((s, v) => s + v, 0)
      const avg = total / combo.stocks.size
      if (avg > bestAvg) {
        bestAvg = avg
        bestKey = key
      }
    }
  }

  if (!bestKey) return null
  const best = comboMap.get(bestKey)!
  return { params: best.params, stocks: best.stocks, avgTotalReturn: bestAvg }
}

function FundAllocationDisplay({
  selectedStocks,
  totalCash,
  stockResults,
  searchableParams,
}: {
  selectedStocks: StockSearchItem[]
  totalCash: number
  stockResults: Map<string, ParamSearchResult>
  searchableParams: [string, { label: string }][]
}) {
  const [expanded, setExpanded] = useState(false)
  const stockCount = selectedStocks.length
  if (stockCount === 0) return null

  const perStockCash = totalCash / stockCount
  const bestCombo = stockResults.size > 0 ? findBestCommonCombination(stockResults) : null

  const totalProfit = bestCombo
    ? Array.from(bestCombo.stocks.entries()).reduce((sum, [, ret]) => sum + perStockCash * ret, 0)
    : null

  return (
    <Card>
      <CardHeader
        title="资金分配与收益概览"
        right={
          <span className="text-xs text-zinc-400">
            总资金: {totalCash.toLocaleString()} 元 | {stockCount} 只股票
          </span>
        }
      />
      <CardBody>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 mb-4">
          <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
            <div className="text-xs text-zinc-500 mb-0.5">每只分配</div>
            <div className="text-lg font-bold text-zinc-900">{perStockCash.toLocaleString()}</div>
          </div>
          <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
            <div className="text-xs text-zinc-500 mb-0.5">选中股票</div>
            <div className="text-lg font-bold text-zinc-900">{stockCount}</div>
          </div>
          {totalProfit != null && (
            <>
              <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                <div className="text-xs text-zinc-500 mb-0.5">最高收益</div>
                <div className={`text-lg font-bold ${totalProfit >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {totalProfit >= 0 ? '+' : ''}{totalProfit.toFixed(2)}
                </div>
              </div>
              <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                <div className="text-xs text-zinc-500 mb-0.5">最高收益率</div>
                <div className={`text-lg font-bold ${totalProfit >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {totalProfit >= 0 ? '+' : ''}{((totalProfit / totalCash) * 100).toFixed(2)}%
                </div>
              </div>
            </>
          )}
        </div>

        {bestCombo && (
          <div className="mb-3 text-xs text-zinc-500">
            最优公共参数: {searchableParams.map(([key, meta]) => `${meta.label}(${key})=${String(bestCombo.params[key] ?? '')}`).join(', ')}
            （平均收益率 {bestCombo.stocks.size > 0 ? `${(bestCombo.avgTotalReturn * 100).toFixed(2)}%` : '—'}）
          </div>
        )}

        {bestCombo && (
          <>
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-700 mb-2"
            >
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              查看每只股票收益明细
            </button>

            {expanded && (
              <div className="max-h-60 overflow-auto rounded-lg border border-zinc-200">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs text-zinc-500 sticky top-0">
                    <tr>
                      <th className="px-3 py-1.5">股票</th>
                      <th className="px-3 py-1.5">分配资金</th>
                      <th className="px-3 py-1.5">收益率</th>
                      <th className="px-3 py-1.5">收益额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedStocks.map((s) => {
                      const ret = bestCombo.stocks.get(s.code) ?? null
                      const profit = ret != null ? perStockCash * ret : null
                      return (
                        <tr key={s.code} className="border-t border-zinc-100">
                          <td className="px-3 py-1.5 font-mono text-xs">{s.name || s.code}</td>
                          <td className="px-3 py-1.5">{perStockCash.toLocaleString()}</td>
                          <td className={`px-3 py-1.5 ${ret != null ? (ret >= 0 ? 'text-red-600' : 'text-green-600') : ''}`}>
                            {ret != null ? `${(ret * 100).toFixed(2)}%` : '—'}
                          </td>
                          <td className={`px-3 py-1.5 ${profit != null ? (profit >= 0 ? 'text-red-600' : 'text-green-600') : ''}`}>
                            {profit != null ? `${profit >= 0 ? '+' : ''}${profit.toFixed(2)}` : '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  )
}

/* ---------- 主组件 ---------- */

export default function ParamOptimizer() {
  const [strategies, setStrategies] = useState<StrategyDef[]>([])

  // 配置
  const [selectedStrategyId, setSelectedStrategyId] = useState('')
  const [selectedStocks, setSelectedStocks] = useState<StockSearchItem[]>([])
  const [totalCash, setTotalCash] = useState(100000)
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [paramGrid, setParamGrid] = useState<Record<string, string>>({})

  // 结果
  const [stockResults, setStockResults] = useState<Map<string, ParamSearchResult>>(new Map())
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState('')

  useEffect(() => {
    fetchJson<{ strategies: StrategyDef[] }>('/api/v1/analysis/strategies')
      .then((s) => {
        setStrategies(s.strategies || [])
        if (s.strategies?.length) setSelectedStrategyId(s.strategies[0].strategy_id)
      })
      .catch((e) => toast('error', e instanceof Error ? e.message : String(e)))
  }, [])

  const currentStrategy = strategies.find((s) => s.strategy_id === selectedStrategyId)

  useEffect(() => {
    if (currentStrategy) {
      const grid: Record<string, string> = {}
      for (const [k, v] of Object.entries(currentStrategy.default_params)) {
        grid[k] = String(v)
      }
      setParamGrid(grid)
    }
  }, [selectedStrategyId, currentStrategy])

  /** 运行参数搜索（逐只股票执行） */
  const runParamSearch = async () => {
    if (selectedStocks.length === 0) {
      toast('error', '请至少选择一只股票')
      return
    }
    if (!selectedStrategyId) {
      toast('error', '请选择策略')
      return
    }

    const grid: Record<string, unknown[]> = {}
    for (const [k, v] of Object.entries(paramGrid)) {
      const meta = currentStrategy?.params_schema?.[k]
      if (!meta) continue
      const parts = String(v).split(/[,，]/).map((s) => s.trim()).filter((s) => s)
      if (meta.type === 'int') {
        grid[k] = parts.map((s) => parseInt(s, 10))
      } else if (meta.type === 'float') {
        grid[k] = parts.map((s) => parseFloat(s))
      } else {
        grid[k] = parts
      }
    }

    setRunning(true)
    setStockResults(new Map())
    const allResults = new Map<string, ParamSearchResult>()

    for (let i = 0; i < selectedStocks.length; i++) {
      const stock = selectedStocks[i]
      setProgress(`正在搜索 ${stock.name || stock.code}（${i + 1}/${selectedStocks.length}）`)

      const traceLabel = `参数搜索-${stock.code}-${Date.now()}`
      console.time(traceLabel)
      console.log(`[参数搜索开始] 股票=${stock.code} 策略=${selectedStrategyId} 范围=${startDate}~${endDate}`)

      try {
        const res = await postJson<ParamSearchResult>('/api/v1/analysis/backtest/param-search', {
          stock_code: stock.code,
          start: startDate,
          end: endDate,
          strategy_id: selectedStrategyId,
          param_grid: grid,
        })
        allResults.set(stock.code, res)
        console.timeEnd(traceLabel)
        console.log(`[参数搜索完成] 股票=${stock.code} 共${res.total_combinations}种组合`)
      } catch (e) {
        console.timeEnd(traceLabel)
        const errorMsg = e instanceof Error ? e.message : String(e)
        console.error(`[参数搜索失败] 股票=${stock.code} ${errorMsg}`)
        toast('error', `${stock.name || stock.code} 参数搜索失败：${errorMsg}`)
      }
    }

    setStockResults(allResults)
    setProgress('')

    if (allResults.size > 0) {
      toast('success', `参数搜索完成，成功 ${allResults.size} 只，失败 ${selectedStocks.length - allResults.size} 只`)
    }
    setRunning(false)
  }

  /** 格式化百分比 */
  const fmtPct = (val: number | undefined | null) => {
    if (val == null) return '—'
    return `${(val * 100).toFixed(2)}%`
  }

  /** 收益率颜色（正红负绿） */
  const returnColor = (val: number | undefined | null) => {
    if (val == null) return 'text-zinc-900'
    return val > 0 ? 'text-red-600' : val < 0 ? 'text-green-600' : 'text-zinc-900'
  }

  /** 获取可搜索的参数 */
  const searchableParams = currentStrategy
    ? Object.entries(currentStrategy.params_schema).filter(
        ([, meta]) => meta.type === 'int' || meta.type === 'float' || meta.type === 'enum'
      )
    : []

  /** 获取股票的最佳参数（按收益率） */
  const getBestByReturn = (stockCode: string): ParamCombination | null => {
    return stockResults.get(stockCode)?.best_by_return || null
  }

  /** 聚合所有股票的参数组合结果（整体分析用） */
  const getAggregatedResults = useCallback(() => {
    if (stockResults.size === 0) return []
    const comboMap = new Map<string, {
      params: Record<string, unknown>
      total_return: number
      annual_return: number
      sharpe: number | null
      max_drawdown: number
      win_rate: number
      num_trades: number
      stockCount: number
    }>()

    for (const [, res] of stockResults) {
      for (const r of res.results) {
        const key = JSON.stringify(r.params)
        if (!comboMap.has(key)) {
          comboMap.set(key, {
            params: r.params,
            total_return: 0,
            annual_return: 0,
            sharpe: 0,
            max_drawdown: 0,
            win_rate: 0,
            num_trades: 0,
            stockCount: 0,
          })
        }
        const c = comboMap.get(key)!
        c.total_return += r.total_return
        c.annual_return += r.annual_return ?? 0
        if (r.sharpe != null) c.sharpe += r.sharpe
        c.max_drawdown = r.max_drawdown != null
          ? Math.min(c.max_drawdown, r.max_drawdown)
          : c.max_drawdown
        c.win_rate += r.win_rate ?? 0
        c.num_trades += r.num_trades ?? 0
        c.stockCount += 1
      }
    }

    const stockCount = stockResults.size
    const aggregated: ParamCombination[] = []
    for (const [, c] of comboMap) {
      if (c.stockCount >= stockCount) {
        aggregated.push({
          params: c.params,
          total_return: c.total_return / stockCount,
          annual_return: c.annual_return / stockCount,
          sharpe: c.sharpe / stockCount,
          max_drawdown: c.max_drawdown,
          win_rate: c.win_rate / stockCount,
          num_trades: c.num_trades,
        })
      }
    }

    aggregated.sort((a, b) => b.total_return - a.total_return)
    return aggregated
  }, [stockResults])

  /** 整体分析的状态 */
  const [overallExpanded, setOverallExpanded] = useState(true)
  const [heatmapExpanded, setHeatmapExpanded] = useState(true)
  const [heatmapMode, setHeatmapMode] = useState<'all' | 'single'>('all')
  const [heatmapStockCode, setHeatmapStockCode] = useState('')
  const [collapsedStocks, setCollapsedStocks] = useState<Set<string>>(new Set())

  const toggleStockCollapse = (code: string) => {
    setCollapsedStocks(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  /** 渲染单只股票的结果卡片 */
  const renderStockResult = (stock: StockSearchItem) => {
    const result = stockResults.get(stock.code)
    if (!result) return null

    const bestReturn = getBestByReturn(stock.code)
    const perStockCash = totalCash / selectedStocks.length
    const isCollapsed = collapsedStocks.has(stock.code)

    return (
      <Card key={stock.code}>
        <CardHeader
          title={`${stock.name || stock.code}（${stock.code}）`}
          right={
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400">分配资金: {perStockCash.toLocaleString()} 元</span>
              {bestReturn && (
                <Badge tone={bestReturn.total_return >= 0 ? 'red' : 'green'}>
                  {fmtPct(bestReturn.total_return)}
                </Badge>
              )}
              <button onClick={() => toggleStockCollapse(stock.code)} className="p-1 rounded hover:bg-zinc-100">
                {isCollapsed ? <ChevronDown className="h-4 w-4 text-zinc-400" /> : <ChevronUp className="h-4 w-4 text-zinc-400" />}
              </button>
            </div>
          }
        />
        {!isCollapsed && (
          <CardBody>
            {bestReturn && (() => {
              const worstReturn = result.results.length > 0 ? Math.min(...result.results.map(r => r.total_return)) : null
              const worstSharpe = result.results.some(r => r.sharpe != null) ? Math.min(...result.results.filter(r => r.sharpe != null).map(r => r.sharpe!)) : null
              const worstDrawdown = result.results.some(r => r.max_drawdown != null) ? Math.min(...result.results.filter(r => r.max_drawdown != null).map(r => r.max_drawdown!)) : null
              return (
                <div className="mb-4">
                  <div className="grid grid-cols-3 gap-3 mb-2">
                    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                      <div className={`text-lg font-bold ${returnColor(bestReturn.total_return)}`}>{fmtPct(bestReturn.total_return)}</div>
                      <div className="text-xs text-zinc-500">总收益率（最优）</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                      <div className="text-lg font-bold text-zinc-900">{bestReturn.sharpe?.toFixed(3) || '—'}</div>
                      <div className="text-xs text-zinc-500">夏普比率（最优）</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                      <div className="text-lg font-bold text-green-600">{fmtPct(bestReturn.max_drawdown)}</div>
                      <div className="text-xs text-zinc-500">最大回撤（最优）</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-1.5 text-center">
                      <div className={`text-sm font-medium ${returnColor(worstReturn)}`}>{worstReturn != null ? fmtPct(worstReturn) : '—'}</div>
                      <div className="text-xs text-zinc-400">总收益率（最差）</div>
                    </div>
                    <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-1.5 text-center">
                      <div className="text-sm font-medium text-zinc-900">{worstSharpe != null && worstSharpe !== Infinity ? worstSharpe.toFixed(3) : '—'}</div>
                      <div className="text-xs text-zinc-400">夏普比率（最差）</div>
                    </div>
                    <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-1.5 text-center">
                      <div className="text-sm font-medium text-green-600">{worstDrawdown != null && worstDrawdown !== Infinity ? fmtPct(worstDrawdown) : '—'}</div>
                      <div className="text-xs text-zinc-400">最大回撤（最差）</div>
                    </div>
                  </div>
                </div>
              )
            })()}

            <div className="mb-1 text-xs text-zinc-500">
              最佳参数: {bestReturn ? Object.entries(bestReturn.params).map(([k, v]) => `${k}=${v}`).join(', ') : '—'}
            </div>

            {/* 参数影响曲线图 */}
            {result.results.length > 0 && searchableParams.length > 0 && (
              <div className="mb-4">
                <ParamCurveChart results={result.results} searchableParams={searchableParams} />
              </div>
            )}

            <div className="max-h-[200px] overflow-auto rounded-lg border border-zinc-200">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500 sticky top-0">
                  <tr>
                    <th className="px-3 py-1.5">参数</th>
                    <th className="px-3 py-1.5">总收益率</th>
                    <th className="px-3 py-1.5">年化收益</th>
                    <th className="px-3 py-1.5">夏普比率</th>
                    <th className="px-3 py-1.5">最大回撤</th>
                    <th className="px-3 py-1.5">胜率</th>
                    <th className="px-3 py-1.5">交易次数</th>
                  </tr>
                </thead>
                <tbody>
                  {result.results.map((r, idx) => {
                    const returnTone = r.total_return > 0 ? 'text-red-600' : r.total_return < 0 ? 'text-green-600' : 'text-zinc-900'
                    return (
                      <tr key={idx} className="border-t border-zinc-100">
                        <td className="px-3 py-1.5 font-mono text-xs">
                          {searchableParams.map(([key]) => (
                            <span key={key} className="mr-1">{key}={String(r.params[key] ?? '—')}</span>
                          ))}
                        </td>
                        <td className={`px-3 py-1.5 font-medium ${returnTone}`}>{fmtPct(r.total_return)}</td>
                        <td className="px-3 py-1.5">{fmtPct(r.annual_return)}</td>
                        <td className="px-3 py-1.5">{r.sharpe?.toFixed(3) || '—'}</td>
                        <td className="px-3 py-1.5 text-green-600">{fmtPct(r.max_drawdown)}</td>
                        <td className="px-3 py-1.5">{fmtPct(r.win_rate)}</td>
                        <td className="px-3 py-1.5">{r.num_trades ?? '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardBody>
        )}
      </Card>
    )
  }

  /** 渲染综合收益热力图（支持全部/单股切换） */
  const renderCombinedHeatmap = () => {
    if (stockResults.size < 1) return null

    const multiValueParams = searchableParams.filter(([key]) => {
      const values = new Set<string>()
      stockResults.forEach((res) => {
        res.results.forEach((r) => values.add(String(r.params[key])))
      })
      return values.size > 1
    })

    if (multiValueParams.length < 2) return null

    const [paramX, paramY] = multiValueParams.slice(0, 2)
    const xKey = paramX[0]
    const yKey = paramY[0]

    // 根据模式选择数据源
    const isAllMode = heatmapMode === 'all'
    const activeStockCode = isAllMode ? null : heatmapStockCode

    // 收集参数组合数据
    const paramReturnMap = new Map<string, number>()
    const paramCountMap = new Map<string, number>()

    const processStock = (res: ParamSearchResult, code: string) => {
      res.results.forEach((r) => {
        const key = `${r.params[xKey]}-${r.params[yKey]}`
        const existing = paramReturnMap.get(key) ?? 0
        paramReturnMap.set(key, existing + (r.total_return || 0))
        paramCountMap.set(key, (paramCountMap.get(key) ?? 0) + 1)
      })
    }

    if (isAllMode) {
      stockResults.forEach((res) => processStock(res, ''))
    } else if (activeStockCode && stockResults.has(activeStockCode)) {
      processStock(stockResults.get(activeStockCode)!, activeStockCode)
    }

    // 计算平均值
    const avgReturns = new Map<string, number>()
    paramReturnMap.forEach((total, key) => {
      avgReturns.set(key, total / (paramCountMap.get(key) ?? 1))
    })

    const keysArr = Array.from(avgReturns.keys())
    const xValues = [...new Set(keysArr.map((k) => k.split('-')[0]))].sort()
    const yValues = [...new Set(keysArr.map((k) => k.split('-')[1]))].sort()

    const data = Array.from(avgReturns.entries()).map(([key, val]) => {
      const [x, y] = key.split('-')
      const xIdx = xValues.indexOf(x)
      const yIdx = yValues.indexOf(y)
      return [xIdx, yIdx, +((val || 0) * 100).toFixed(2)]
    })

    const maxAbs = Math.max(...data.map((d) => Math.abs(d[2])), 1)

    const metricLabel = isAllMode ? '平均收益率' : '收益率'

    const option = {
      tooltip: {
        formatter: (params: any) => {
          const xVal = xValues[params.data[0]]
          const yVal = yValues[params.data[1]]
          const val = params.data[2]
          return `${paramX[1].label}: ${xVal}<br/>${paramY[1].label}: ${yVal}<br/>${metricLabel}: ${val > 0 ? '+' : ''}${val.toFixed(2)}%`
        },
      },
      grid: { left: 80, right: 65, top: 10, bottom: 40 },
      xAxis: { type: 'category' as const, data: xValues, name: paramX[1].label, nameLocation: 'middle' as const, nameGap: 30, axisLabel: { fontSize: 10 } },
      yAxis: { type: 'category' as const, data: yValues, name: paramY[1].label, nameLocation: 'middle' as const, nameGap: 50, axisLabel: { fontSize: 10 } },
      visualMap: {
        min: -maxAbs, max: maxAbs, calculable: true, orient: 'vertical' as const, right: 10, bottom: 10,
        itemWidth: 12, itemHeight: 140,
        inRange: { color: ['#22c55e', '#f0fdf4', '#fef2f2', '#ef4444'] },
        textStyle: { fontSize: 10 },
        formatter: (val: number) => `${val.toFixed(1)}%`,
      },
      series: [{
        name: metricLabel, type: 'heatmap', data,
        label: { show: data.length < 50, fontSize: 9, formatter: (p: any) => { const v = p.data[2]; return v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1) } },
        itemStyle: { borderWidth: 1, borderColor: '#fff' },
      }],
    }

    return (
      <div>
        <ReactECharts option={option} style={{ height: 400 }} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 配置区 */}
      <Card>
        <CardHeader title="参数优化" />
        <CardBody>
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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

              <div>
                <div className="mb-1 text-xs text-zinc-500">总资金（元）</div>
                <input
                  type="number"
                  value={totalCash}
                  onChange={(e) => setTotalCash(Math.max(0, Number(e.target.value)))}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>

              <div>
                <div className="mb-1 text-xs text-zinc-500">开始日期</div>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>

              <div>
                <div className="mb-1 text-xs text-zinc-500">结束日期</div>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400" />
              </div>
            </div>

            {/* 多选股票组件（与回测页风格一致） */}
            <div>
              <div className="mb-1 text-xs text-zinc-500">股票列表（可搜索多选）</div>
              <StockPicker
                mode="multiple"
                value={selectedStocks}
                onChange={(val) => setSelectedStocks((val as StockSearchItem[]) || [])}
                placeholder="搜索股票代码或名称，多选添加"
              />
            </div>

            {/* 参数网格配置 */}
            {searchableParams.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-semibold text-zinc-900">参数网格（多个值用逗号分隔）</div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
                    {searchableParams.map(([key, meta]) => (
                      <div key={key}>
                        <div className="mb-1 text-xs text-zinc-500">{meta.label} <span className="text-zinc-400">({key})</span></div>
                        <input
                          value={paramGrid[key] ?? ''}
                          onChange={(e) => setParamGrid((p) => ({ ...p, [key]: e.target.value }))}
                          placeholder={`例如: ${meta.default}, 多值用逗号分隔`}
                          className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 font-mono"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={runParamSearch}
              disabled={running || selectedStocks.length === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              <Play className="h-4 w-4" />
              {running ? '搜索中...' : '开始参数搜索'}
            </button>

            {progress && (
              <div className="text-xs text-zinc-500 flex items-center gap-2">
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
                {progress}
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      {/* 资金分配与收益概览 */}
      {selectedStocks.length > 0 && (
        <FundAllocationDisplay
          selectedStocks={selectedStocks}
          totalCash={totalCash}
          stockResults={stockResults}
          searchableParams={searchableParams}
        />
      )}

      {/* 整体分析与各股票结果 */}
      {stockResults.size > 0 && (
        <>
          {/* 综合热力图（支持折叠，右上角模式切换） */}
          <div className="rounded-lg border border-zinc-200">
            <div className="flex items-center justify-between px-4 py-3">
              <button
                onClick={() => setHeatmapExpanded(!heatmapExpanded)}
                className="flex items-center gap-1 text-sm font-semibold text-zinc-900 hover:text-zinc-700"
              >
                {heatmapExpanded ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
                <span>综合参数热力图</span>
              </button>
              <div className="flex items-center gap-2">
                <select
                  value={heatmapMode === 'single' && heatmapStockCode ? heatmapStockCode : 'all'}
                  onChange={(e) => {
                    const v = e.target.value
                    if (v === 'all') {
                      setHeatmapMode('all')
                      setHeatmapStockCode('')
                    } else {
                      setHeatmapMode('single')
                      setHeatmapStockCode(v)
                    }
                  }}
                  className="rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs outline-none focus:border-zinc-400"
                >
                  <option value="all">全部（多股票平均）</option>
                  {selectedStocks.map((s) => (
                    <option key={s.code} value={s.code}>{s.name || s.code}</option>
                  ))}
                </select>
              </div>
            </div>
            {heatmapExpanded && <div className="px-4 pb-4">{renderCombinedHeatmap()}</div>}
          </div>

          {/* 整体分析（支持折叠） */}
          {(searchableParams.length > 0) && (
            <div className="rounded-lg border border-zinc-200">
              <button
                onClick={() => setOverallExpanded(!overallExpanded)}
                className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-50"
              >
                <span>整体分析（多股票聚合）</span>
                {overallExpanded ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
              </button>
              {overallExpanded && (
                <div className="px-4 pb-4 space-y-4">
                  {(() => {
                    const aggResults = getAggregatedResults()
                    if (aggResults.length === 0) return <div className="text-xs text-zinc-500 py-2">暂无聚合数据</div>
                    const best = aggResults[0]
                    return (
                      <>
                        {/* 最佳参数卡片 */}
                        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                          <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                            <div className={`text-xl font-bold ${returnColor(best.total_return)}`}>{fmtPct(best.total_return)}</div>
                            <div className="text-xs text-zinc-500">平均总收益率（最优）</div>
                          </div>
                          <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                            <div className="text-xl font-bold text-zinc-900">{best.sharpe?.toFixed(3) || '—'}</div>
                            <div className="text-xs text-zinc-500">平均夏普比率（最优）</div>
                          </div>
                          <div className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                            <div className="text-xl font-bold text-green-600">{fmtPct(best.max_drawdown)}</div>
                            <div className="text-xs text-zinc-500">最大回撤（最差）</div>
                          </div>
                        </div>

                        <div className="mb-1 text-xs text-zinc-500">
                          最优参数: {Object.entries(best.params).map(([k, v]) => `${k}=${v}`).join(', ')}
                        </div>

                        {/* 整体参数影响曲线图 */}
                        {aggResults.length > 0 && searchableParams.length > 0 && (
                          <div className="mb-4">
                            <ParamCurveChart results={aggResults} searchableParams={searchableParams} />
                          </div>
                        )}

                        {/* 整体参数组合表格 */}
                        <div className="max-h-[200px] overflow-auto rounded-lg border border-zinc-200">
                          <table className="w-full text-left text-sm">
                            <thead className="bg-zinc-50 text-xs text-zinc-500 sticky top-0">
                              <tr>
                                <th className="px-3 py-1.5">参数</th>
                                <th className="px-3 py-1.5">平均总收益率</th>
                                <th className="px-3 py-1.5">平均年化收益</th>
                                <th className="px-3 py-1.5">平均夏普比率</th>
                                <th className="px-3 py-1.5">最大回撤</th>
                                <th className="px-3 py-1.5">平均胜率</th>
                                <th className="px-3 py-1.5">总交易次数</th>
                              </tr>
                            </thead>
                            <tbody>
                              {aggResults.map((r, idx) => {
                                const returnTone = r.total_return > 0 ? 'text-red-600' : r.total_return < 0 ? 'text-green-600' : 'text-zinc-900'
                                return (
                                  <tr key={idx} className="border-t border-zinc-100">
                                    <td className="px-3 py-1.5 font-mono text-xs">
                                      {searchableParams.map(([key]) => (
                                        <span key={key} className="mr-1">{key}={String(r.params[key] ?? '—')}</span>
                                      ))}
                                    </td>
                                    <td className={`px-3 py-1.5 font-medium ${returnTone}`}>{fmtPct(r.total_return)}</td>
                                    <td className="px-3 py-1.5">{fmtPct(r.annual_return)}</td>
                                    <td className="px-3 py-1.5">{r.sharpe?.toFixed(3) || '—'}</td>
                                    <td className="px-3 py-1.5 text-green-600">{fmtPct(r.max_drawdown)}</td>
                                    <td className="px-3 py-1.5">{fmtPct(r.win_rate)}</td>
                                    <td className="px-3 py-1.5">{r.num_trades ?? '—'}</td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )
                  })()}
                </div>
              )}
            </div>
          )}

          {/* 各股票详细结果（每只股票独立折叠） */}
          <div>
            <div className="text-sm font-semibold text-zinc-900 mb-3">各股票详细结果</div>
            <div className="space-y-4">
              {selectedStocks.map((stock) => renderStockResult(stock))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
