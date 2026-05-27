import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchJson } from '@/api/client'
import type { JobDomain, JobRunResult, DatasetName, PagedRows } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { GitBranch, History, RefreshCcw, Database, Play } from 'lucide-react'
import { cn } from '@/lib/utils'

const DATASETS: { value: DatasetName; label: string }[] = [
  { value: 'trade_stock_daily', label: '行情数据' },
  { value: 'trade_stock_financial', label: '财务数据' },
  { value: 'trade_stock_news', label: '新闻数据' },
  { value: 'trade_macro_indicator', label: '宏观指标' },
  { value: 'trade_rate_daily', label: '利率数据' },
  { value: 'trade_report_consensus', label: '研报一致预期' },
  { value: 'trade_calendar_event', label: '日历事件' },
]

type TabKey = 'dataset' | 'runs'

function formatDate(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function formatCellValue(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  const s = String(v)
  return s.length > 50 ? s.slice(0, 50) + '...' : s
}

export default function DataDelivery() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabKey>('dataset')
  const [history, setHistory] = useState<JobRunResult[]>([])
  const [selected, setSelected] = useState<JobRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [dataStatus, setDataStatus] = useState<{
    branch: string
    sync_status: string
    last_sync_time: string
  } | null>(null)

  useEffect(() => {
    fetchJson<{
      branch: string
      sync_status: string
      last_sync_time: string
    }>('/api/v1/data/status').then(setDataStatus).catch(() => {
      // 忽略
    })
  }, [])

  const DOMAIN_LABEL_MAP: Record<string, string> = {
    stock_daily: '行情日线（stock_daily）',
    stock_financial: '财务季度（stock_financial）',
    stock_news: '新闻事件（stock_news）',
    macro_indicator: '宏观指标（macro_indicator）',
    rate_daily: '利率日频（rate_daily）',
    report_consensus: '研报一致预期（report_consensus）',
    calendar: '财经日历（calendar）',
    catalyst: '关键催化剂（catalyst）',
    sentiment_monitor: '舆情监控（sentiment_monitor）',
  }

  const [datasetName, setDatasetName] = useState<DatasetName>('trade_stock_daily')
  const [datasetPage, setDatasetPage] = useState(1)
  const [datasetLoading, setDatasetLoading] = useState(false)
  const [datasetErr, setDatasetErr] = useState<string | null>(null)
  const [datasetData, setDatasetData] = useState<PagedRows<Record<string, unknown>> | null>(null)

  const PAGE_SIZE = 50
  const HISTORY_PAGE_SIZE = 10
  const [historyPage, setHistoryPage] = useState(1)

  const loadDataset = useCallback(async (dataset: DatasetName, page: number) => {
    setDatasetLoading(true)
    setDatasetErr(null)
    try {
      const r = await fetchJson<PagedRows<Record<string, unknown>>>(
        `/api/v1/data/${dataset}?page=${page}&page_size=${PAGE_SIZE}`
      )
      setDatasetData(r)
    } catch (e) {
      setDatasetErr(e instanceof Error ? e.message : String(e))
      setDatasetData(null)
    } finally {
      setDatasetLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDataset(datasetName, datasetPage)
  }, [datasetName, datasetPage, loadDataset])

  const handleDatasetChange = (value: DatasetName) => {
    setDatasetName(value)
    setDatasetPage(1)
    setDatasetData(null)
  }

  const loadHistory = async () => {
    setLoading(true)
    setErr(null)
    setHistoryPage(1)
    try {
      const r = await fetchJson<{ runs: JobRunResult[] }>('/api/v1/jobs/runs?limit=100')
      setHistory(r.runs || [])
      if (r.runs && r.runs.length > 0 && !selected) {
        setSelected(r.runs[0])
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
    const t = window.setInterval(() => { loadHistory() }, 5000)
    return () => window.clearInterval(t)
  }, [])

  const columns: string[] = datasetData && datasetData.rows && datasetData.rows.length > 0
    ? Object.keys(datasetData.rows[0])
    : []

  const totalPages = datasetData ? Math.ceil(datasetData.total / PAGE_SIZE) : 0

  const pagedHistory = history.slice((historyPage - 1) * HISTORY_PAGE_SIZE, historyPage * HISTORY_PAGE_SIZE)
  const historyTotalPages = Math.ceil(history.length / HISTORY_PAGE_SIZE)

  return (
    <div className="space-y-4">

      <div className="flex gap-1 rounded-lg border border-zinc-200 bg-zinc-50 p-1">
        <button
          onClick={() => setActiveTab('dataset')}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition',
            activeTab === 'dataset'
              ? 'bg-white text-zinc-900 shadow-sm'
              : 'text-zinc-500 hover:text-zinc-700'
          )}
        >
          <Database className="h-4 w-4" />
          数据集浏览
        </button>
        <button
          onClick={() => setActiveTab('runs')}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition',
            activeTab === 'runs'
              ? 'bg-white text-zinc-900 shadow-sm'
              : 'text-zinc-500 hover:text-zinc-700'
          )}
        >
          <Play className="h-4 w-4" />
          历史任务记录
        </button>
      </div>

      {dataStatus && (
        <div className="flex items-center gap-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-xs text-zinc-600">
          <span className="flex items-center gap-1.5">
            <GitBranch className="h-3.5 w-3.5 text-zinc-400" />
            分支: <span className="font-medium text-zinc-800">{dataStatus.branch}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <RefreshCcw className="h-3.5 w-3.5 text-zinc-400" />
            同步状态: <span className="font-medium text-zinc-800">{dataStatus.sync_status}</span>
          </span>
          <span className="text-zinc-400">|</span>
          <span className="text-zinc-400">上次同步: {dataStatus.last_sync_time || '—'}</span>
        </div>
      )}

      {activeTab === 'dataset' && (
        <Card>
          <CardHeader
            title="数据集浏览"
            right={
              <select
                value={datasetName}
                onChange={(e) => handleDatasetChange(e.target.value as DatasetName)}
                className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm text-zinc-700 outline-none focus:border-zinc-400"
              >
                {DATASETS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label} ({d.value})
                  </option>
                ))}
              </select>
            }
          />
          <CardBody className="p-0">
            {datasetLoading ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">加载中...</div>
            ) : datasetErr ? (
              <div className="px-4 py-8 text-center text-sm text-red-600">{datasetErr}</div>
            ) : !datasetData || datasetData.rows.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无数据</div>
            ) : (
              <>
                <div className="max-h-[420px] overflow-auto">
                  <table className="text-left text-sm" style={{ width: 'max-content' }}>
                    <thead className="sticky top-0 z-10 bg-white">
                      <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                        {columns.map((col) => (
                          <th key={col} className="whitespace-nowrap px-4 py-2 bg-white">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {datasetData.rows.map((row, idx) => (
                        <tr key={idx} className="border-b border-zinc-50 hover:bg-zinc-50">
                          {columns.map((col) => (
                            <td key={col} className="whitespace-nowrap px-4 py-2 text-xs text-zinc-700">
                              {formatCellValue(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
                  <div className="text-xs text-zinc-500">
                    共 {datasetData.total} 条，第 {datasetData.page}/{totalPages} 页
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setDatasetPage(1)}
                      disabled={datasetPage <= 1}
                      className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      首页
                    </button>
                    <button
                      onClick={() => setDatasetPage((p) => Math.max(1, p - 1))}
                      disabled={datasetPage <= 1}
                      className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      上一页
                    </button>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      const start = Math.max(1, Math.min(datasetPage - 2, totalPages - 4))
                      const page = start + i
                      if (page > totalPages) return null
                      return (
                        <button
                          key={page}
                          onClick={() => setDatasetPage(page)}
                          className={cn(
                            'min-w-[32px] rounded-lg border px-2 py-1.5 text-xs transition',
                            page === datasetPage
                              ? 'border-zinc-900 bg-zinc-900 text-white'
                              : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'
                          )}
                        >
                          {page}
                        </button>
                      )
                    })}
                    <button
                      onClick={() => setDatasetPage((p) => Math.min(totalPages, p + 1))}
                      disabled={datasetPage >= totalPages}
                      className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      下一页
                    </button>
                    <button
                      onClick={() => setDatasetPage(totalPages)}
                      disabled={datasetPage >= totalPages}
                      className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      末页
                    </button>
                  </div>
                </div>
              </>
            )}
          </CardBody>
        </Card>
      )}

      {activeTab === 'runs' && (
        <>
          <div className="grid grid-cols-1 gap-4">
            <Card>
              <CardHeader
                title="历史记录"
                right={
                  <button
                    onClick={() => loadHistory()}
                    disabled={loading}
                    className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
                  >
                    <RefreshCcw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
                    刷新
                  </button>
                }
              />
              <CardBody className="p-0">
                {loading && history.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-zinc-500">加载中...</div>
                ) : err ? (
                  <div className="px-4 py-8 text-center text-sm text-red-600">{err}</div>
                ) : history.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无运行记录</div>
                ) : (
                  <>
                  <div className="max-h-[295px] overflow-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="sticky top-0 bg-white">
                        <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                          <th className="px-4 py-2">时间</th>
                          <th className="px-4 py-2">任务</th>
                          <th className="px-4 py-2">状态</th>
                          <th className="px-4 py-2">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pagedHistory.map((r) => (
                          <tr
                            key={r.runId}
                            onClick={() => setSelected(r)}
                            className={cn(
                              'cursor-pointer border-b border-zinc-50 hover:bg-zinc-50',
                              selected?.runId === r.runId ? 'bg-zinc-50' : ''
                            )}
                          >
                            <td className="px-4 py-2 text-xs text-zinc-700">{formatDate(r.startedAt)}</td>
                            <td className="px-4 py-2 text-xs text-zinc-700">{DOMAIN_LABEL_MAP[r.domain] || r.domain}</td>
                            <td className="px-4 py-2"><JobStatusBadge status={r.status} /></td>
                            <td className="px-4 py-2">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  navigate(`/info-access/data-collection/detail?domain=${encodeURIComponent(r.domain)}&name=${encodeURIComponent(r.domain)}`)
                                }}
                                className="text-xs text-zinc-600 hover:text-zinc-900"
                              >
                                详情
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                  </table>
                </div>
                {historyTotalPages > 1 && (
                  <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
                    <div className="text-xs text-zinc-500">
                      共 {history.length} 条，第 {historyPage}/{historyTotalPages} 页
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setHistoryPage(1)}
                        disabled={historyPage <= 1}
                        className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        首页
                      </button>
                      <button
                        onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                        disabled={historyPage <= 1}
                        className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        上一页
                      </button>
                      {Array.from({ length: Math.min(5, historyTotalPages) }, (_, i) => {
                        const start = Math.max(1, Math.min(historyPage - 2, historyTotalPages - 4))
                        const page = start + i
                        if (page > historyTotalPages) return null
                        return (
                          <button
                            key={page}
                            onClick={() => setHistoryPage(page)}
                            className={cn(
                              'min-w-[32px] rounded-lg border px-2 py-1.5 text-xs transition',
                              page === historyPage
                                ? 'border-zinc-900 bg-zinc-900 text-white'
                                : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'
                            )}
                          >
                            {page}
                          </button>
                        )
                      })}
                      <button
                        onClick={() => setHistoryPage((p) => Math.min(historyTotalPages, p + 1))}
                        disabled={historyPage >= historyTotalPages}
                        className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        下一页
                      </button>
                      <button
                        onClick={() => setHistoryPage(historyTotalPages)}
                        disabled={historyPage >= historyTotalPages}
                        className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        末页
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
              </CardBody>
            </Card>
          </div>

          {selected && (
            <Card>
              <CardHeader title="选中记录详情" />
              <CardBody>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">runId</div>
                      <div className="mt-1 break-all text-xs text-zinc-900">{selected.runId}</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">状态</div>
                      <div className="mt-1"><JobStatusBadge status={selected.status} /></div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">数据源</div>
                      <div className="mt-1"><DataSourceBadge source={selected.dataSourceFinal} /></div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">写入行数</div>
                      <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.rowsWritten.toLocaleString()}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-500">处理条目</div>
                      <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.itemsProcessed.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-500">失败条目</div>
                      <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.failedItems.length}</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-500">耗时</div>
                      <div className="mt-1 text-xs text-zinc-700">{formatDate(selected.startedAt)}</div>
                    </div>
                  </div>
                  {selected.userMessage || selected.message ? (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                      {selected.userMessage || selected.message}
                    </div>
                  ) : null}
                </div>
              </CardBody>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
