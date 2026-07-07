/**
 * 回测历史管理页面
 * 支持查看、筛选、删除回测记录，以及对比多条记录
 */
import { Loading } from '@/components/Loading'
import { useEffect, useState, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchJson } from '@/api/client'
import { toast } from '@/components/Toast'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Trash2, Eye, Search, XCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import BacktestCharts from '@/components/BacktestCharts'
import ReactECharts from 'echarts-for-react'

const METRIC_TOOLTIPS: Record<string, string> = {
  'Sortino': '只考虑下行风险的夏普比率改进版，衡量单位下行波动带来的超额收益，越高越好',
  'Calmar': '年化收益率与最大回撤的比值，衡量策略每承受1%回撤能换取多少年化收益，越高越好',
  '信息比率': '超额收益与跟踪误差的比值，衡量相对于基准的主动管理能力，越高越好',
  '盈亏比': '平均盈利与平均亏损的比值，>1 表示盈亏质量好',
  '平均盈亏': '每笔交易的平均盈亏金额，正数表示平均每笔盈利，负数表示平均每笔亏损',
  'Alpha': '超越市场基准的超额收益，衡量选股/择时能力，>0 表示跑赢市场',
  'Beta': '策略相对于市场基准的波动敏感度，β=1 同步波动，β>1 波动更大',
  '波动率': '收益率的年化标准差，衡量策略的整体风险水平，越低越稳定',
  '夏普比率': '单位总风险带来的超额收益，衡量风险调整后收益，>1 较好',
}

const STRATEGY_NAMES: Record<string, string> = {
  // 基础策略
  ma_dual: 'MA双均线策略',
  macd_basic: 'MACD策略',
  rsi_basic: 'RSI策略',
  boll_basic: '布林带策略',
  bias: '乖离率策略',
  momentum: '动量策略',
  turtle_simple: '简单海龟交易法则',
  // 缠论策略
  chan_third_buy: '经典缠论-基础三买',
  chan_trailing: '缠论-量价增强策略',
  chan_multi_tf: '缠论-多周期缠论策略',
  chan_ml: '缠论-ML增强缠论策略',
  // 网格策略
  grid_classic: '经典网格交易',
  chan_grid: '缠论中枢网络策略',
  chan_grid_trend: '中枢网格+趋势联动',
  // 优化策略
  rsi_cross_confirm: 'RSI增强-穿越确认',
  macd_vol_confirm: 'MACD增强-成交量确认',
  macd_profit_lock: 'MACD增强-利润锁定',
  boll_mid_stop: '布林带增强-中轨止损',
  macd_divergence: 'MACD底背离策略',
  turtle_full: '完整海龟交易法则',
  turtle_adx: 'ADX海龟策略',
  turtle_multi_tf: '多周期海龟策略',
  turtle_ml: 'ML增强海龟策略',
  // 组合策略
  adaptive: '综合增强-自适应策略',
  combo_custom: '自定义组合策略',
}

function MetricLabel({ label }: { label: string }) {
  const desc = METRIC_TOOLTIPS[label]
  return (
    <span className="inline-flex items-center gap-1">
      {label}
      {desc && (
        <span className="group relative inline-flex items-center">
          <span className="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full bg-zinc-200 text-[10px] font-bold text-zinc-500 hover:bg-zinc-300">?</span>
          <span className="invisible group-hover:visible absolute top-full left-1/2 -translate-x-1/2 mt-1.5 w-56 whitespace-normal rounded-md bg-zinc-800 px-2.5 py-1.5 text-xs text-white shadow-lg opacity-0 group-hover:opacity-100 transition-all z-50 pointer-events-none">
            {desc}
            <span className="absolute bottom-full left-1/2 -translate-x-1/2 border-4 border-transparent border-b-zinc-800" />
          </span>
        </span>
      )}
    </span>
  )
}

/* ---------- 数据类型 ---------- */

interface BacktestRecord {
  backtest_id: string
  strategy_id: string
  strategy_name?: string
  stock_code: string
  start_date: string
  end_date: string
  total_return: number
  annual_return?: number
  sharpe?: number
  max_drawdown?: number
  win_rate?: number
  created_at: string
  [key: string]: unknown
}

interface BacktestDetail {
  backtest_id: string
  strategy_id: string
  stock_code: string
  start_date: string
  end_date: string
  initial_cash: number
  commission_buy: number
  commission_sell: number
  slippage_pct: number
  slippage_fixed: number
  min_commission: number
  stamp_duty: number
  transfer_fee_buy: number
  transfer_fee_sell: number
  position_pct: number
  metrics: Record<string, unknown>
  trades: Array<{ date: string; action: string; price: number; qty: number; cost?: number; proceeds?: number; note?: string }>
  nav_log: Array<{ date: string; nav: number }>
  benchmark_nav_log?: Array<{ date: string; nav: number }>
  drawdown_log?: Array<{ date: string; nav: number; peak: number; drawdown: number }>
  monthly_returns?: Array<{ month: string; return: number }>
  kline?: Array<{ date: string; open: number; high: number; low: number; close: number; volume: number }>
  chan_vis?: {
    bi_list: Array<{
      start_date?: string
      end_date?: string
      start_idx?: number
      end_idx?: number
      start_price: number
      end_price: number
      direction: 'up' | 'down'
    }>
    seg_list: Array<{
      start_date?: string
      end_date?: string
      start_price?: number
      end_price?: number
      direction: 'up' | 'down'
    }>
    zs_list: Array<{
      ZG?: number
      ZD?: number
      zg?: number
      zd?: number
      start_date?: string
      end_date?: string
      start_idx?: number
      end_idx?: number
    }>
  }
  created_at: string
  [key: string]: unknown
}

/* ---------- 分页控件 ---------- */

function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const [jumpValue, setJumpValue] = useState('')

  if (total <= pageSize && page === 1) return null

  const pages: (number | '...')[] = []
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i)
  } else {
    pages.push(1)
    if (page > 3) pages.push('...')
    const start = Math.max(2, page - 1)
    const end = Math.min(totalPages - 1, page + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (page < totalPages - 2) pages.push('...')
    pages.push(totalPages)
  }

  const handleJump = () => {
    const n = parseInt(jumpValue, 10)
    if (n >= 1 && n <= totalPages) {
      onPageChange(n)
      setJumpValue('')
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 px-4 py-3">
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span>共 {total} 条记录</span>
        <span className="text-zinc-300">|</span>
        <span>第 {page}/{totalPages} 页</span>
        <span className="text-zinc-300">|</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded border border-zinc-200 bg-white px-2 py-1 text-xs outline-none focus:border-zinc-400"
        >
          <option value={10}>10条/页</option>
          <option value={20}>20条/页</option>
          <option value={50}>50条/页</option>
        </select>
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="inline-flex h-7 w-7 items-center justify-center rounded border border-zinc-200 bg-white text-zinc-600 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        {pages.map((p, idx) =>
          p === '...' ? (
            <span key={`ellipsis-${idx}`} className="px-1 text-xs text-zinc-400">...</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`inline-flex h-7 min-w-[28px] items-center justify-center rounded px-1.5 text-xs font-medium transition ${
                p === page
                  ? 'bg-zinc-900 text-white'
                  : 'border border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="inline-flex h-7 w-7 items-center justify-center rounded border border-zinc-200 bg-white text-zinc-600 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-30"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
        <div className="ml-2 flex items-center gap-1">
          <input
            value={jumpValue}
            onChange={(e) => setJumpValue(e.target.value.replace(/\D/g, ''))}
            onKeyDown={(e) => e.key === 'Enter' && handleJump()}
            placeholder="页码"
            className="w-14 rounded border border-zinc-200 px-2 py-1 text-xs outline-none focus:border-zinc-400"
          />
          <button
            onClick={handleJump}
            className="rounded border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50"
          >
            跳转
          </button>
        </div>
      </div>
    </div>
  )
}

/* ---------- 主组件 ---------- */

export default function BacktestHistory() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [records, setRecords] = useState<BacktestRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [filterStrategy, setFilterStrategy] = useState('')
  const [filterStock, setFilterStock] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)

  // 详情弹窗
  const [detailVisible, setDetailVisible] = useState(false)
  const [detailData, setDetailData] = useState<BacktestDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 选中状态（用于批量删除）
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  // 从 URL 读取 backtest_id 参数并自动展开详情
  const urlBacktestId = searchParams.get('backtest_id')
  const urlBacktestIdRef = useRef<string | null>(null)

  // 如果 URL 有 backtest_id 参数，自动展开详情
  useEffect(() => {
    if (!urlBacktestId || urlBacktestIdRef.current === urlBacktestId) return
    urlBacktestIdRef.current = urlBacktestId
    // 直接加载详情数据
    const loadDetail = async () => {
      setDetailLoading(true)
      setDetailVisible(true)
      try {
        const res = await fetchJson<BacktestDetail>(`/api/v1/analysis/backtest/${urlBacktestId}`)
        setDetailData(res)
      } catch (e) {
        toast('error', `加载详情失败：${e instanceof Error ? e.message : String(e)}`)
      } finally {
        setDetailLoading(false)
      }
    }
    loadDetail()
  }, [urlBacktestId])
  const loadRecords = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterStrategy) params.set('strategy_id', filterStrategy)
      if (filterStock) params.set('stock_code', filterStock)
      params.set('page', String(page))
      params.set('page_size', String(pageSize))
      const query = params.toString() ? `?${params.toString()}` : ''
      const res = await fetchJson<{ records: BacktestRecord[]; total: number }>(`/api/v1/analysis/backtest/records${query}`)
      setRecords(res.records || [])
      setTotal(res.total || 0)
    } catch (e) {
      toast('error', `加载记录失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRecords()
  }, [page, pageSize])

  // 使用 ref 保存最新的 loadRecords 引用，避免事件监听中的闭包陷阱
  const loadRecordsRef = useRef(loadRecords)
  loadRecordsRef.current = loadRecords

  // 监听回测完成事件，自动刷新记录列表
  useEffect(() => {
    const handleBacktestCompleted = () => {
      setPage(1)
      loadRecordsRef.current()
    }
    window.addEventListener('backtest-completed', handleBacktestCompleted)
    return () => window.removeEventListener('backtest-completed', handleBacktestCompleted)
  }, [])

  // 筛选时重置到第一页
  const handleFilter = () => {
    setPage(1)
    loadRecordsRef.current()
  }

  // 查看详情
  const viewDetail = async (id: string) => {
    setDetailLoading(true)
    setDetailVisible(true)
    try {
      const res = await fetchJson<BacktestDetail>(`/api/v1/analysis/backtest/records/${id}`)
      setDetailData(res)
    } catch (e) {
      toast('error', `加载详情失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setDetailLoading(false)
    }
  }

  // 删除记录
  const deleteRecord = async (id: string) => {
    if (!confirm('确定要删除这条回测记录吗？')) return
    try {
      await fetchJson(`/api/v1/analysis/backtest/records/${id}`, { method: 'DELETE' })
      toast('success', '删除成功')
      setRecords((prev) => prev.filter((r) => r.backtest_id !== id))
      setSelectedIds((prev) => prev.filter((sid) => sid !== id))
      loadRecords()
    } catch (e) {
      toast('error', `删除失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  // 切换选中
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      return [...prev, id]
    })
  }

  // 全选/取消全选
  const toggleSelectAll = () => {
    const allSelected = records.length > 0 && records.every((r) => selectedIds.includes(r.backtest_id))
    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !records.some((r) => r.backtest_id === id)))
    } else {
      const newIds = records.filter((r) => !selectedIds.includes(r.backtest_id)).map((r) => r.backtest_id)
      setSelectedIds([...selectedIds, ...newIds])
    }
  }

  // 批量删除
  const deleteSelected = async () => {
    if (selectedIds.length === 0) return
    if (!confirm(`确定要删除选中的 ${selectedIds.length} 条回测记录吗？`)) return
    try {
      await Promise.all(selectedIds.map((id) => fetchJson(`/api/v1/analysis/backtest/records/${id}`, { method: 'DELETE' })))
      toast('success', `成功删除 ${selectedIds.length} 条记录`)
      setSelectedIds([])
      loadRecords()
    } catch (e) {
      toast('error', `批量删除失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  // 格式化百分比
  const fmtPct = (val: number | undefined | null) => {
    if (val == null) return '—'
    return `${(val * 100).toFixed(2)}%`
  }

  return (
    <div className="space-y-4">
      {/* 页面导航头部 */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/strategy/backtest')}
          className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          返回回测
        </button>
        <h2 className="text-base font-semibold text-zinc-900">回测历史</h2>
      </div>

      {/* 筛选与表格卡片 */}
      <Card>
        <CardHeader title="" right={
          <button
            onClick={loadRecords}
            className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-700"
          >
            <Search className="h-3.5 w-3.5" />
            刷新
          </button>
        } />
        <CardBody>
          <div className="flex items-end gap-4 mb-4">
            <div>
              <div className="mb-1 text-xs text-zinc-500">策略</div>
              <input
                value={filterStrategy}
                onChange={(e) => setFilterStrategy(e.target.value)}
                placeholder="输入策略名筛选"
                className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 w-48"
              />
            </div>
            <div>
              <div className="mb-1 text-xs text-zinc-500">股票代码</div>
              <input
                value={filterStock}
                onChange={(e) => setFilterStock(e.target.value)}
                placeholder="输入股票代码筛选"
                className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400 w-48"
              />
            </div>
            <button
              onClick={handleFilter}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm text-white hover:bg-zinc-800"
            >
              筛选
            </button>
            <div className="flex-1" />
            {selectedIds.length > 0 && (
              <button
                onClick={deleteSelected}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 hover:bg-red-100 transition-colors"
                title="批量删除"
              >
                <Trash2 className="h-4 w-4" />
                删除 {selectedIds.length} 条
              </button>
            )}
          </div>

          {/* 记录表格 */}
          {loading ? (
            <Loading className="py-8" />
          ) : records.length === 0 ? (
            <div className="py-8 text-center text-sm text-zinc-500">暂无回测记录</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 w-10">
                    <input
                      type="checkbox"
                      checked={records.length > 0 && records.every((r) => selectedIds.includes(r.backtest_id))}
                      onChange={toggleSelectAll}
                      ref={(el) => {
                        if (el) {
                          const allSelected = records.length > 0 && records.every((r) => selectedIds.includes(r.backtest_id))
                          const someSelected = records.some((r) => selectedIds.includes(r.backtest_id))
                          el.indeterminate = someSelected && !allSelected
                        }
                      }}
                      className="h-4 w-4 accent-zinc-900"
                    />
                  </th>
                  <th className="px-4 py-2">回测ID</th>
                  <th className="px-4 py-2">策略</th>
                  <th className="px-4 py-2">股票</th>
                  <th className="px-4 py-2">时间范围</th>
                  <th className="px-4 py-2">收益率</th>
                  <th className="px-4 py-2">夏普比率</th>
                  <th className="px-4 py-2">创建时间</th>
                  <th className="px-4 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => {
                  const isSelected = selectedIds.includes(r.backtest_id)
                  const returnTone = r.total_return > 0 ? 'text-red-600' : r.total_return < 0 ? 'text-green-600' : 'text-zinc-900'
                  const strategyLabel = STRATEGY_NAMES[r.strategy_id] || r.strategy_name || r.strategy_id
                  return (
                    <tr key={r.backtest_id} className={`border-t border-zinc-100 ${isSelected ? 'bg-blue-50' : ''}`}>
                      <td className="px-4 py-2">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(r.backtest_id)}
                          className="h-4 w-4 accent-zinc-900"
                        />
                      </td>
                      <td className="px-4 py-2 text-xs font-mono text-zinc-500">{r.backtest_id.slice(0, 8)}...</td>
                      <td className="px-4 py-2 text-zinc-700">{strategyLabel}</td>
                      <td className="px-4 py-2 text-xs font-mono text-zinc-700">{r.stock_code}</td>
                      <td className="px-4 py-2 text-xs text-zinc-500">{r.start_date} ~ {r.end_date}</td>
                      <td className={`px-4 py-2 font-medium ${returnTone}`}>{fmtPct(r.total_return)}</td>
                      <td className="px-4 py-2 text-zinc-700">{r.sharpe != null ? r.sharpe.toFixed(3) : '—'}</td>
                      <td className="px-4 py-2 text-xs text-zinc-500">{r.created_at}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => viewDetail(r.backtest_id)}
                            className="text-zinc-500 hover:text-zinc-700"
                            title="查看详情"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => deleteRecord(r.backtest_id)}
                            className="text-zinc-500 hover:text-red-600"
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}

          {/* 分页控件 */}
          {!loading && records.length > 0 && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
            />
          )}
        </CardBody>
      </Card>

      {/* 详情弹窗 */}
      {detailVisible && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setDetailVisible(false)}>
          <div className="max-h-[80vh] w-[900px] overflow-auto rounded-lg bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <h3 className="text-lg font-semibold">回测详情</h3>
              <button onClick={() => setDetailVisible(false)} className="text-zinc-400 hover:text-zinc-600">
                <XCircle className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              {detailLoading ? (
                <Loading className="py-8" />
              ) : detailData ? (
                <>
                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div>
                      <div className="text-xs text-zinc-500">策略</div>
                      <div className="font-medium">{STRATEGY_NAMES[detailData.strategy_id] || detailData.strategy_id}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-500">股票</div>
                      <div className="font-medium font-mono">{detailData.stock_code}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-500">时间范围</div>
                      <div className="font-medium">{detailData.start_date} ~ {detailData.end_date}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-500">创建时间</div>
                      <div className="font-medium">{detailData.created_at}</div>
                    </div>
                  </div>

                  {/* 回测ID */}
                  <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2.5">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-500">回测ID</span>
                      <span className="font-mono text-sm font-medium text-zinc-800">{detailData.backtest_id}</span>
                    </div>
                  </div>

                  {/* 交易成本配置 */}
                  <div className="rounded-lg border border-zinc-200">
                    <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-2 text-xs font-medium text-zinc-600">
                      交易成本配置
                    </div>
                    <div className="grid grid-cols-4 gap-4 px-4 py-3 text-sm">
                      <div>
                        <div className="text-xs text-zinc-500">初始资金</div>
                        <div className="font-medium">{detailData.initial_cash?.toLocaleString() ?? '—'} 元</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">买入佣金率</div>
                        <div className="font-medium">{detailData.commission_buy != null ? `${(detailData.commission_buy * 100).toFixed(3)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">卖出佣金率</div>
                        <div className="font-medium">{detailData.commission_sell != null ? `${(detailData.commission_sell * 100).toFixed(3)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">最低手续费</div>
                        <div className="font-medium">{detailData.min_commission != null ? `${detailData.min_commission} 元` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">印花税（卖出）</div>
                        <div className="font-medium">{detailData.stamp_duty != null ? `${(detailData.stamp_duty * 100).toFixed(2)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">买入过户费</div>
                        <div className="font-medium">{detailData.transfer_fee_buy != null ? `${(detailData.transfer_fee_buy * 100).toFixed(3)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">卖出过户费</div>
                        <div className="font-medium">{detailData.transfer_fee_sell != null ? `${(detailData.transfer_fee_sell * 100).toFixed(3)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">仓位比例</div>
                        <div className="font-medium">{detailData.position_pct != null ? `${(detailData.position_pct * 100).toFixed(0)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">滑点（百分比）</div>
                        <div className="font-medium">{detailData.slippage_pct != null ? `${(detailData.slippage_pct * 100).toFixed(2)}%` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-500">滑点（固定值）</div>
                        <div className="font-medium">{detailData.slippage_fixed != null ? `${detailData.slippage_fixed} 元` : '—'}</div>
                      </div>
                    </div>
                  </div>

                  {/* K线图 + 缠论可视化 */}
                  {detailData.kline && detailData.kline.length > 0 && (() => {
                    const chartDates = detailData.kline!.map(k => k.date)
                    const legendData: string[] = ['收盘价', '买入', '卖出']
                    const hasChanVis = !!detailData.chan_vis
                    if (hasChanVis) {
                      if (detailData.chan_vis!.bi_list?.length) legendData.push('笔')
                      if (detailData.chan_vis!.seg_list?.length) legendData.push('线段')
                      if (detailData.chan_vis!.zs_list?.length) legendData.push('中枢')
                    }

                    const seriesList: any[] = []

                    // 收盘价折线
                    seriesList.push({
                      name: '收盘价',
                      type: 'line',
                      data: detailData.kline!.map(k => k.close),
                      xAxisIndex: 0,
                      yAxisIndex: 0,
                      smooth: true,
                      symbol: 'circle',
                      symbolSize: 3,
                      lineStyle: { color: '#3b82f6', width: 2 },
                      areaStyle: {
                        color: {
                          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                          colorStops: [
                            { offset: 0, color: 'rgba(59,130,246,0.2)' },
                            { offset: 1, color: 'rgba(59,130,246,0.02)' },
                          ],
                        },
                      },
                      z: 5,
                    })

                    // 买入/卖出标记点（从 trades 中提取）
                    const buyData = detailData.trades
                      ?.filter(t => t.action === 'buy')
                      .map(t => {
                        const idx = chartDates.indexOf(t.date)
                        return idx >= 0 ? [idx, t.price] : null
                      }).filter(Boolean) || []
                    const sellData = detailData.trades
                      ?.filter(t => t.action === 'sell')
                      .map(t => {
                        const idx = chartDates.indexOf(t.date)
                        return idx >= 0 ? [idx, t.price] : null
                      }).filter(Boolean) || []

                    if (buyData.length > 0) {
                      seriesList.push({
                        name: '买入',
                        type: 'scatter',
                        data: buyData,
                        xAxisIndex: 0,
                        yAxisIndex: 0,
                        symbol: 'triangle',
                        symbolSize: 10,
                        itemStyle: { color: '#ef4444' },
                        z: 10,
                      })
                    }
                    if (sellData.length > 0) {
                      seriesList.push({
                        name: '卖出',
                        type: 'scatter',
                        data: sellData,
                        xAxisIndex: 0,
                        yAxisIndex: 0,
                        symbol: 'triangle',
                        symbolSize: 10,
                        symbolRotate: 180,
                        itemStyle: { color: '#22c55e' },
                        z: 10,
                      })
                    }

                    // 缠论可视化：笔（bi_list）- markLine 统一渲染
                    if (detailData.chan_vis?.bi_list?.length) {
                      const biMarkData: any[] = []
                      detailData.chan_vis.bi_list.forEach((bi) => {
                        const startIdx = bi.start_date ? chartDates.indexOf(bi.start_date) : bi.start_idx
                        const endIdx = bi.end_date ? chartDates.indexOf(bi.end_date) : bi.end_idx
                        if (startIdx != null && endIdx != null && startIdx >= 0 && endIdx >= 0) {
                          biMarkData.push([
                            {
                              xAxis: chartDates[startIdx],
                              yAxis: bi.start_price,
                              lineStyle: {
                                color: bi.direction === 'up' ? '#ef4444' : '#22c55e',
                                width: 2,
                                type: 'solid' as const,
                              },
                            },
                            { xAxis: chartDates[endIdx], yAxis: bi.end_price },
                          ])
                        }
                      })
                      if (biMarkData.length > 0) {
                        seriesList.push({
                          name: '笔',
                          type: 'line',
                          data: [],
                          xAxisIndex: 0,
                          yAxisIndex: 0,
                          markLine: {
                            symbol: 'none',
                            animation: false,
                            label: { show: false },
                            data: biMarkData,
                          },
                          z: 4,
                        })
                      }
                    }

                    // 缠论可视化：线段（seg_list）- markLine 统一渲染
                    if (detailData.chan_vis?.seg_list?.length) {
                      const segMarkData: any[] = []
                      detailData.chan_vis.seg_list.forEach((seg) => {
                        const startIdx = seg.start_date ? chartDates.indexOf(seg.start_date) : -1
                        const endIdx = seg.end_date ? chartDates.indexOf(seg.end_date) : -1
                        if (startIdx >= 0 && endIdx >= 0) {
                          const startPrice = seg.start_price ?? detailData.kline![startIdx]?.close
                          const endPrice = seg.end_price ?? detailData.kline![endIdx]?.close
                          if (startPrice != null && endPrice != null) {
                            segMarkData.push([
                              {
                                xAxis: chartDates[startIdx],
                                yAxis: startPrice,
                                lineStyle: {
                                  color: seg.direction === 'up' ? '#dc2626' : '#16a34a',
                                  width: 3,
                                  type: 'dashed' as const,
                                },
                              },
                              { xAxis: chartDates[endIdx], yAxis: endPrice },
                            ])
                          }
                        }
                      })
                      if (segMarkData.length > 0) {
                        seriesList.push({
                          name: '线段',
                          type: 'line',
                          data: [],
                          xAxisIndex: 0,
                          yAxisIndex: 0,
                          markLine: {
                            symbol: 'none',
                            animation: false,
                            label: { show: false },
                            data: segMarkData,
                          },
                          z: 3,
                        })
                      }
                    }

                    // 缠论可视化：中枢（zs_list）- 独立 series + markArea
                    if (detailData.chan_vis?.zs_list?.length) {
                      const zsMarkData: any[] = []
                      detailData.chan_vis.zs_list.forEach((zs) => {
                        const startIdx = zs.start_date ? chartDates.indexOf(zs.start_date) : zs.start_idx
                        const endIdx = zs.end_date ? chartDates.indexOf(zs.end_date) : zs.end_idx
                        const zg = zs.ZG ?? zs.zg ?? 0
                        const zd = zs.ZD ?? zs.zd ?? 0
                        if (startIdx != null && endIdx != null && startIdx >= 0 && endIdx >= 0 && zg > 0 && zd > 0) {
                          zsMarkData.push([
                            { xAxis: chartDates[startIdx], yAxis: zd, itemStyle: { color: 'rgba(59,130,246,0.12)' } },
                            { xAxis: chartDates[endIdx], yAxis: zg },
                          ])
                        }
                      })
                      if (zsMarkData.length > 0) {
                        seriesList.push({
                          name: '中枢',
                          type: 'line',
                          data: [],
                          xAxisIndex: 0,
                          yAxisIndex: 0,
                          markArea: {
                            silent: true,
                            animation: false,
                            label: { show: false },
                            data: zsMarkData,
                          },
                          z: 2,
                        })
                      }
                    }

                    // 成交量柱状图
                    seriesList.push({
                      name: '成交量',
                      type: 'bar',
                      data: detailData.kline!.map(k => k.volume),
                      xAxisIndex: 1,
                      yAxisIndex: 1,
                      itemStyle: { color: 'rgba(161,161,170,0.3)' },
                      z: 1,
                    })

                    return (
                      <div>
                        <div className="mb-2 text-sm font-semibold text-zinc-900">
                          K线图{hasChanVis ? ' (含缠论分析)' : ''}
                        </div>
                        <ReactECharts
                          option={{
                            animation: false,
                            tooltip: {
                              trigger: 'axis',
                              axisPointer: { type: 'cross' },
                              backgroundColor: 'rgba(255,255,255,0.95)',
                              borderColor: '#e4e4e7',
                              textStyle: { color: '#27272a', fontSize: 12 },
                            },
                            legend: { data: legendData, top: 0, textStyle: { fontSize: 11 } },
                            grid: [
                              { left: '8%', right: '3%', top: '12%', height: '55%' },
                              { left: '8%', right: '3%', top: '72%', height: '18%' },
                            ],
                            xAxis: [
                              { type: 'category', data: chartDates, axisLabel: { fontSize: 10, rotate: 45 }, gridIndex: 0, boundaryGap: true, axisTick: { show: false } },
                              { type: 'category', data: chartDates, gridIndex: 1, boundaryGap: true, axisTick: { show: false }, axisLabel: { show: false } },
                            ],
                            yAxis: [
                              { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#f4f4f5' } } },
                              { scale: true, gridIndex: 1, splitLine: { show: false } },
                            ],
                            series: seriesList,
                          }}
                          style={{ height: '420px' }}
                          opts={{ renderer: 'canvas' }}
                        />
                      </div>
                    )
                  })()}

                  {detailData.metrics && (
                    <>
                      <div className="grid grid-cols-4 gap-3">
                        {[
                          { label: '总收益率', value: fmtPct(detailData.metrics.total_return as number), tone: (detailData.metrics.total_return as number) > 0 ? 'up' : 'down' },
                          { label: '年化收益', value: fmtPct(detailData.metrics.annual_return as number) },
                          { label: '最大回撤', value: fmtPct(detailData.metrics.max_drawdown as number), tone: 'down' },
                          { label: '夏普比率', value: (detailData.metrics.sharpe as number)?.toFixed(3) || '—' },
                          { label: '胜率', value: fmtPct(detailData.metrics.win_rate as number) },
                          { label: '交易次数', value: String(detailData.metrics.num_trades ?? detailData.metrics.total_trades ?? '—') },
                          { label: '初始资金', value: ((detailData.metrics.initial_nav as number) || 0).toLocaleString() },
                          { label: '最终资金', value: ((detailData.metrics.final_nav as number) || 0).toLocaleString() },
                        ].map((item, i) => {
                          const cls = item.tone === 'up' ? 'text-red-600' : item.tone === 'down' ? 'text-green-600' : 'text-zinc-900'
                          return (
                            <div key={i} className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                              <div className={`text-lg font-bold ${cls}`}>{item.value}</div>
                              <div className="text-xs text-zinc-500"><MetricLabel label={item.label} /></div>
                            </div>
                          )
                        })}
                      </div>
                      <div className="grid grid-cols-4 gap-3">
                        {[
                          { label: '波动率', value: fmtPct(detailData.metrics.volatility as number) },
                          { label: 'Sortino', value: (detailData.metrics.sortino as number)?.toFixed(3) || '—' },
                          { label: 'Calmar', value: (detailData.metrics.calmar as number)?.toFixed(3) || '—' },
                          { label: 'Alpha', value: fmtPct(detailData.metrics.alpha as number) },
                          { label: 'Beta', value: (detailData.metrics.beta as number)?.toFixed(3) || '—' },
                          { label: '信息比率', value: (detailData.metrics.information_ratio as number)?.toFixed(3) || '—' },
                          { label: '盈亏比', value: (detailData.metrics.profit_factor as number)?.toFixed(2) || '—' },
                          { label: '平均盈亏', value: (detailData.metrics.avg_profit_loss as number)?.toFixed(2) || '—' },
                        ].map((item, i) => {
                          return (
                            <div key={i + 8} className="rounded-lg border border-zinc-200 px-3 py-2 text-center">
                              <div className="text-lg font-bold text-zinc-900">{item.value}</div>
                              <div className="text-xs text-zinc-500"><MetricLabel label={item.label} /></div>
                            </div>
                          )
                        })}
                      </div>
                    </>
                  )}

                  <BacktestCharts
                    navLog={detailData.nav_log}
                    benchmarkNavLog={detailData.benchmark_nav_log}
                    drawdownLog={detailData.drawdown_log}
                    monthlyReturns={detailData.monthly_returns}
                  />

                  {/* 交易记录表 */}
                  {detailData.trades && detailData.trades.length > 0 && (
                    <div>
                      <div className="mb-2 text-sm font-semibold text-zinc-900">交易记录</div>
                      <div className="max-h-64 overflow-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-zinc-50 text-xs text-zinc-500 sticky top-0">
                            <tr>
                              <th className="px-3 py-2">日期</th>
                              <th className="px-3 py-2">方向</th>
                              <th className="px-3 py-2">价格</th>
                              <th className="px-3 py-2">数量</th>
                              <th className="px-3 py-2">金额</th>
                              <th className="px-3 py-2">备注</th>
                              <th className="px-3 py-2">费用</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detailData.trades.map((t: any, i: number) => {
                              const actionDisplay = t.action === 'buy' ? '买入' : t.action === 'pending_sell' ? '待卖' : '卖出'
                              const actionTone = t.action === 'buy' ? 'green' : t.action === 'pending_sell' ? 'amber' : 'red'
                              const amountDisplay = t.action === 'buy'
                                ? `-${t.cost != null ? t.cost.toLocaleString() : '—'}`
                                : t.action === 'pending_sell'
                                  ? `≈${t.proceeds != null ? t.proceeds.toLocaleString() : '—'}`
                                  : `+${t.proceeds != null ? t.proceeds.toLocaleString() : '—'}`
                              return (
                                <tr key={i} className="border-t border-zinc-100">
                                  <td className="px-3 py-1.5 text-xs text-zinc-700">{t.date}</td>
                                  <td className="px-3 py-1.5"><Badge tone={actionTone as any}>{actionDisplay}</Badge></td>
                                  <td className="px-3 py-1.5 text-zinc-900">{t.price}</td>
                                  <td className="px-3 py-1.5 text-zinc-700">{t.qty}</td>
                                  <td className="px-3 py-1.5 text-zinc-700">{amountDisplay}</td>
                                  <td className="px-3 py-1.5 text-xs text-zinc-400">{t.note || '—'}</td>
                                  <td className="px-3 py-1.5 text-xs text-zinc-500 max-w-[200px] break-all">{t.fee_detail || '—'}</td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* 绩效报告链接 */}
                  <div className="flex justify-end">
                    <button
                      onClick={() => navigate(`/strategy/performance?backtest_id=${detailData.backtest_id}`)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
                    >
                      查看绩效报告
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
