/**
 * 绩效报告列表页
 * 复用回测历史页面的UI模式：搜索条件 + 列表（竖向滚动条） + 分页
 * 多选回测记录后生成绩效报告
 */

import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCw, FileText, Trash2, AlertTriangle, Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDate, formatPct } from '@/utils/performanceReport'

interface PerformanceReport {
  id: number
  report_id: string
  report_type: string
  account_id: number
  strategy_name?: string
  backtest_id?: string
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
  trading_days?: number
  avg_profit?: number
  avg_loss?: number
  status: string
  created_at?: string
}

interface StrategyOption {
  strategy_id: string
  name: string
  group: string
}

interface BacktestRecord {
  backtest_id: string
  strategy_id: string
  strategy_name?: string
  stock_code: string
  start_date: string
  end_date: string
  initial_cash: number
  total_return: number
  sharpe?: number
  max_drawdown?: number
  win_rate?: number
  created_at: string
}

const STRATEGY_GROUP_LABELS: Record<string, string> = {
  basic: '基础策略',
  optimized: '优化策略',
  combo: '组合策略',
}

const STRATEGY_NAMES: Record<string, string> = {
  ma_dual: 'MA双均线策略',
  macd_basic: 'MACD策略',
  rsi_basic: 'RSI策略',
  boll_basic: '布林带策略',
  bias: '乖离率策略',
  momentum: '动量策略',
  turtle_simple: '简单海龟交易法则',
  chan_third_buy: '经典缠论-基础三买',
  chan_trailing: '缠论-量价增强策略',
  chan_multi_tf: '缠论-多周期缠论策略',
  chan_ml: '缠论-ML增强缠论策略',
  grid_classic: '经典网格交易',
  chan_grid: '缠论中枢网络策略',
  chan_grid_trend: '中枢网格+趋势联动',
  rsi_cross_confirm: 'RSI增强-穿越确认',
  macd_vol_confirm: 'MACD增强-成交量确认',
  macd_profit_lock: 'MACD增强-利润锁定',
  boll_mid_stop: '布林带增强-中轨止损',
  macd_divergence: 'MACD底背离策略',
  turtle_full: '完整海龟交易法则',
  turtle_adx: 'ADX海龟策略',
  turtle_multi_tf: '多周期海龟策略',
  turtle_ml: 'ML增强海龟策略',
  adaptive: '综合增强-自适应策略',
  combo_custom: '自定义组合策略',
}

const PAGE_SIZE = 20

export default function PerformanceReport() {
  const navigate = useNavigate()
  const [reports, setReports] = useState<PerformanceReport[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

  // 搜索条件
  const [strategies, setStrategies] = useState<StrategyOption[]>([])
  const [filterStrategy, setFilterStrategy] = useState<string>('')
  const [filterStock, setFilterStock] = useState<string>('')

  // 搜索条件可选项
  const [stocks, setStocks] = useState<string[]>([])

  // 回测记录列表（带分页）
  const [records, setRecords] = useState<BacktestRecord[]>([])
  const [recordsTotal, setRecordsTotal] = useState(0)
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [page, setPage] = useState(1)

  // 多选
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchJson<{ items: PerformanceReport[]; total: number }>('/api/v1/performance/list')
      if (data.items?.length > 0) {
        const converted = data.items.map((item) => {
          const obj: Record<string, unknown> = { ...item }
          for (const key of ['total_return', 'annualized_return', 'max_drawdown', 'volatility', 'sharpe_ratio', 'calmar_ratio', 'win_rate', 'profit_factor', 'avg_profit', 'avg_loss', 'final_nav', 'initial_cash']) {
            if (typeof obj[key] === 'string') obj[key] = parseFloat(obj[key] as string)
          }
          return obj as unknown as PerformanceReport
        })
        setReports(converted)
      }
      else setReports([])
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setReports([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // 加载策略列表
  useEffect(() => {
    fetchJson<{ strategies: StrategyOption[] }>('/api/v1/analysis/strategies')
      .then(data => setStrategies(data.strategies || []))
      .catch(() => {})
  }, [])

  // 策略变更时加载股票列表
  useEffect(() => {
    if (!filterStrategy) {
      setStocks([])
      return
    }
    fetchJson<{ stocks: string[] }>(`/api/v1/analysis/backtest/stocks?strategy_id=${encodeURIComponent(filterStrategy)}`)
      .then(data => setStocks(data.stocks || []))
      .catch(() => setStocks([]))
  }, [filterStrategy])

  // 加载回测记录（带分页），支持空选择显示全部
  const loadRecords = useCallback(async (pg = 1) => {
    setRecordsLoading(true)
    try {
      const params = new URLSearchParams({
        page: String(pg),
        page_size: String(PAGE_SIZE),
      })
      if (filterStrategy) params.set('strategy_id', filterStrategy)
      if (filterStock) params.set('stock_code', filterStock)

      const data = await fetchJson<{ records: BacktestRecord[]; total: number }>(
        `/api/v1/analysis/backtest/records?${params.toString()}`
      )
      setRecords(data.records || [])
      setRecordsTotal(data.total || 0)
      setPage(pg)
    } catch {
      setRecords([])
      setRecordsTotal(0)
    } finally {
      setRecordsLoading(false)
    }
  }, [filterStrategy, filterStock])

  // 进入页面时默认加载全部回测记录
  useEffect(() => {
    loadRecords(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 执行搜索
  const handleSearch = () => {
    setSelectedIds([])
    loadRecords(1)
  }

  // 重置搜索
  const handleReset = () => {
    setFilterStrategy('')
    setFilterStock('')
    setStocks([])
    setRecords([])
    setRecordsTotal(0)
    setSelectedIds([])
    setPage(1)
  }

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === records.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(records.map(r => r.backtest_id))
    }
  }

  const handleGenerate = async () => {
    if (selectedIds.length === 0) return
    setGenerating(true)
    try {
      await postJson('/api/v1/performance/generate', {
        backtest_ids: selectedIds,
        report_type: 'common',
      })
      setSelectedIds([])
      await loadData()
    } catch {
      //
    } finally {
      setGenerating(false)
    }
  }

  const handleClickReport = useCallback((report: PerformanceReport) => {
    navigate('/strategy/performance/' + report.report_id)
  }, [navigate])

  const handleDelete = async (reportId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('确定要删除该绩效报告吗？此操作不可撤销，删除后数据将永久丢失。')) return
    try {
      await fetchJson(`/api/v1/performance/${reportId}`, { method: 'DELETE' })
      await loadData()
    } catch {
      alert('删除失败，请稍后重试')
    }
  }

  const groupedStrategies: Record<string, StrategyOption[]> = {}
  strategies.forEach(s => {
    const g = s.group || 'basic'
    if (!groupedStrategies[g]) groupedStrategies[g] = []
    groupedStrategies[g].push(s)
  })

  const totalPages = Math.max(1, Math.ceil(recordsTotal / PAGE_SIZE))

  if (loading && reports.length === 0) {
    return <Loading className="py-20" />
  }

  if (error && reports.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <AlertTriangle className="mb-3 h-10 w-10 text-zinc-300" />
        <p className="text-sm text-zinc-500">{error}</p>
        <button onClick={loadData} className="mt-3 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50">重新加载</button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">绩效报告</h1>
          <p className="text-sm text-zinc-500 mt-1">基于回测历史记录生成绩效报告</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={loadData} disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />刷新
          </button>
        </div>
      </div>

      {/* 生成绩效报告 - 复用回测历史页面结构 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">生成绩效报告</h3>
            <button
              onClick={handleGenerate}
              disabled={selectedIds.length === 0 || generating}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <FileText className="w-4 h-4" />
              {generating ? '生成中...' : `生成绩效报告${selectedIds.length > 0 ? ` (${selectedIds.length})` : ''}`}
            </button>
          </div>
        </CardHeader>
        <CardBody>
          {/* 搜索条件区域（复用回测历史筛选行风格） */}
          <div className="mb-4 flex flex-wrap items-end gap-3">
            <div className="w-48">
              <label className="block text-xs font-medium text-zinc-700 mb-1.5">选择策略</label>
              <select
                value={filterStrategy}
                onChange={e => setFilterStrategy(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white"
              >
                <option value="">全部策略</option>
                {Object.entries(groupedStrategies).map(([group, list]) => (
                  <optgroup key={group} label={STRATEGY_GROUP_LABELS[group] || group}>
                    {list.map(s => (
                      <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="w-40">
              <label className="block text-xs font-medium text-zinc-700 mb-1.5">选择股票</label>
              <select
                value={filterStock}
                onChange={e => setFilterStock(e.target.value)}
                disabled={stocks.length === 0}
                className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <option value="">全部股票</option>
                {stocks.map(code => (
                  <option key={code} value={code}>{code}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSearch}
                disabled={recordsLoading}
                className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <Search className="w-4 h-4" />
                查询
              </button>
              <button
                onClick={handleReset}
                className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-4 text-sm text-zinc-700 hover:bg-zinc-50 transition"
              >
                重置
              </button>
            </div>
          </div>

          {/* 列表区域（竖向滚动条，模仿回测历史表格） */}
          {records.length > 0 ? (
            <>
              <div className="overflow-y-auto max-h-[420px] rounded-lg border border-zinc-200">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 z-10 bg-zinc-50 text-xs text-zinc-500 shadow-[0_1px_0_0_rgba(0,0,0,0.05)]">
                    <tr>
                      <th className="w-10 px-3 py-2">
                        <input
                          type="checkbox"
                          checked={records.length > 0 && selectedIds.length === records.length}
                          ref={(el) => {
                            if (el) {
                              const allSelected = records.length > 0 && selectedIds.length === records.length
                              const someSelected = records.some(r => selectedIds.includes(r.backtest_id))
                              el.indeterminate = someSelected && !allSelected
                            }
                          }}
                          onChange={toggleSelectAll}
                          className="h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                        />
                      </th>
                      <th className="px-3 py-2">回测ID</th>
                      <th className="px-3 py-2">策略</th>
                      <th className="px-3 py-2">股票</th>
                      <th className="px-3 py-2">回测区间</th>
                      <th className="px-3 py-2 text-right">总收益率</th>
                      <th className="px-3 py-2 text-right">夏普</th>
                      <th className="px-3 py-2 text-right">最大回撤</th>
                      <th className="px-3 py-2 text-right">胜率</th>
                      <th className="px-3 py-2">创建时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map(r => {
                      const strategyName = STRATEGY_NAMES[r.strategy_id] || r.strategy_id
                      return (
                        <tr
                          key={r.backtest_id}
                          className="border-t border-zinc-100 hover:bg-zinc-50 cursor-pointer"
                          onClick={() => toggleSelect(r.backtest_id)}
                        >
                          <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={selectedIds.includes(r.backtest_id)}
                              onChange={() => toggleSelect(r.backtest_id)}
                              className="h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900"
                            />
                          </td>
                          <td className="px-3 py-2 font-mono text-xs text-zinc-600">{r.backtest_id.slice(0, 8)}...</td>
                          <td className="px-3 py-2">
                            <Badge variant="default">{strategyName}</Badge>
                          </td>
                          <td className="px-3 py-2 text-zinc-700">{r.stock_code}</td>
                          <td className="px-3 py-2 text-xs text-zinc-500">{r.start_date} ~ {r.end_date}</td>
                          <td className={`px-3 py-2 text-right font-medium ${(r.total_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatPct(r.total_return)}
                          </td>
                          <td className="px-3 py-2 text-right text-zinc-700">{r.sharpe?.toFixed(2) || '--'}</td>
                          <td className="px-3 py-2 text-right text-red-600">{r.max_drawdown ? formatPct(r.max_drawdown) : '--'}</td>
                          <td className="px-3 py-2 text-right text-zinc-700">{r.win_rate ? r.win_rate.toFixed(1) + '%' : '--'}</td>
                          <td className="px-3 py-2 text-xs text-zinc-400">{r.created_at ? r.created_at.slice(0, 10) : '--'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* 分页控件（复用回测历史页面的风格） */}
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-zinc-500">
                  第 {page} / {totalPages} 页（共 {recordsTotal} 条）
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => loadRecords(page - 1)}
                    disabled={page <= 1 || recordsLoading}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-zinc-200 text-zinc-600 hover:bg-zinc-50 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="px-2 text-xs text-zinc-600">
                    {page} / {totalPages}
                  </span>
                  <button
                    onClick={() => loadRecords(page + 1)}
                    disabled={page >= totalPages || recordsLoading}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-zinc-200 text-zinc-600 hover:bg-zinc-50 disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </>
          ) : recordsLoading ? (
            <div className="rounded-lg border border-zinc-200 py-12 text-center text-sm text-zinc-500">
              加载中...
            </div>
          ) : records.length === 0 && !filterStrategy && !filterStock ? (
            <div className="rounded-lg border border-zinc-200 py-12 text-center text-sm text-zinc-500">
              暂无可用的回测历史记录
            </div>
          ) : records.length === 0 ? (
            <div className="rounded-lg border border-zinc-200 py-12 text-center text-sm text-zinc-500">
              没有找到符合条件的回测记录，请调整筛选条件
            </div>
          ) : null}
        </CardBody>
      </Card>

      {/* 报告列表 */}
      <Card>
        <CardHeader><h3 className="text-lg font-semibold">报告列表</h3></CardHeader>
        <CardBody>
          <div className="space-y-3">
            {reports.map(report => (
              <div
                key={report.id}
                className="cursor-pointer rounded-lg border border-zinc-200 p-4 transition hover:border-zinc-400"
                onClick={() => handleClickReport(report)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-zinc-900">{report.strategy_name || '未命名策略'}</span>
                      <Badge variant={report.report_type === 'plus' ? 'success' : 'default'}>{report.report_type === 'plus' ? 'PLUS版' : '普通版'}</Badge>
                      <Badge variant={report.status === 'completed' ? 'success' : 'warning'}>{report.status === 'completed' ? '已完成' : report.status}</Badge>
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">{formatDate(report.start_date)} ~ {formatDate(report.end_date)}</div>
                  </div>
                  <button onClick={(e) => handleDelete(report.report_id, e)}
                    className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                </div>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <div><div className="text-xs text-zinc-500">总收益率</div>
                    <div className={`text-sm font-semibold ${(report.total_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>{formatPct(report.total_return)}</div></div>
                  <div><div className="text-xs text-zinc-500">年化收益率</div>
                    <div className={`text-sm font-semibold ${(report.annualized_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>{formatPct(report.annualized_return)}</div></div>
                  <div><div className="text-xs text-zinc-500">最大回撤</div><div className="text-sm font-semibold text-red-600">{formatPct(report.max_drawdown)}</div></div>
                  <div><div className="text-xs text-zinc-500">夏普比率</div><div className="text-sm font-semibold text-zinc-900">{report.sharpe_ratio?.toFixed(2) || '--'}</div></div>
                  <div><div className="text-xs text-zinc-500">胜率</div><div className="text-sm font-semibold text-zinc-900">{report.win_rate?.toFixed(1) || '--'}%</div></div>
                  <div><div className="text-xs text-zinc-500">盈亏比</div><div className="text-sm font-semibold text-zinc-900">{report.profit_factor?.toFixed(2) || '--'}</div></div>
                  <div><div className="text-xs text-zinc-500">交易次数</div><div className="text-sm font-semibold text-zinc-900">{report.total_trades || '--'}</div></div>
                  <div><div className="text-xs text-zinc-500">初始资金</div><div className="text-sm font-semibold text-zinc-900">{report.initial_cash?.toLocaleString() || '--'}</div></div>
                  <div><div className="text-xs text-zinc-500">创建时间</div><div className="text-sm font-semibold text-zinc-900">{report.created_at ? report.created_at.slice(0, 19).replace('T', ' ') : '--'}</div></div>
                  <div><div className="text-xs text-zinc-500">回测任务</div>
                    {report.backtest_id ? (
                      <button onClick={(e) => { e.stopPropagation(); navigate(`/strategy/backtest-history?backtest_id=${report.backtest_id}`) }}
                        className="text-sm font-semibold text-blue-600 hover:text-blue-800 hover:underline">{report.backtest_id.slice(0, 8)}...</button>
                    ) : <div className="text-sm font-semibold text-zinc-900">--</div>}</div>
                </div>
              </div>
            ))}
            {reports.length === 0 && <div className="py-8 text-center text-sm text-zinc-500">暂无绩效报告，请先选择策略和股票后生成</div>}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
