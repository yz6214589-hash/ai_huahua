import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import type { JobDomain, JobDomainInfo, JobRunResult, JobSchedule } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { Play, RefreshCcw, Save, Settings, X, Eye, BarChart3, Square } from 'lucide-react'
import { Loading } from '@/components/Loading'
import StockScopeSelector from '@/components/StockScopeSelector'

function formatDate(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function formatCron(cron: string) {
  const parts = (cron || '').trim().split(/\s+/)
  if (parts.length !== 5) return cron
  const [min, hour, day, month, dow] = parts
  if (day === '*' && month === '*' && dow === '*') return `每天 ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  if (day === '*' && month === '*' && dow === '1-5') return `工作日 ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  if (day === '1' && month === '*' && dow === '*') return `每月1日 ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  if (dow === '0') return `周日 ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`
  if (min.startsWith('*/') && hour === '*' && day === '*' && month === '*' && dow === '*') return `每${min.slice(2)}分钟`
  return cron
}

type IntervalUnit = 'minute' | 'hour' | 'week' | 'month' | 'year'

function parseInterval(cron: string): { every: number; unit: IntervalUnit; startTime: string; advanced: boolean } {
  const parts = (cron || '').trim().split(/\s+/)
  if (parts.length !== 5 && parts.length !== 6) return { every: 1, unit: 'month', startTime: '18:00', advanced: true }
  const [min, hour, day, month, dow, year] = parts as [string, string, string, string, string, string | undefined]

  if (/^\*\/\d+$/.test(min) && hour === '*' && day === '*' && month === '*' && dow === '*' && !year) {
    return { every: Math.max(1, parseInt(min.slice(2), 10) || 1), unit: 'minute', startTime: '00:00', advanced: false }
  }
  if (/^\*\/\d+$/.test(hour) && day === '*' && month === '*' && dow === '*' && !year) {
    return { every: Math.max(1, parseInt(hour.slice(2), 10) || 1), unit: 'hour', startTime: `00:${String(min).padStart(2, '0')}`, advanced: false }
  }
  if (/^\*\/\d+$/.test(day) && month === '*' && dow === '*' && !year) {
    const nDays = Math.max(1, parseInt(day.slice(2), 10) || 1)
    if (nDays % 7 === 0) return { every: Math.max(1, nDays / 7), unit: 'week', startTime: `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`, advanced: false }
  }
  if (day === '1' && /^\*\/\d+$/.test(month) && dow === '*' && !year) {
    return { every: Math.max(1, parseInt(month.slice(2), 10) || 1), unit: 'month', startTime: `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`, advanced: false }
  }
  if (day === '1' && month === '1' && dow === '*' && year && (/^\*\/\d+$/.test(year) || year === '*')) {
    const n = year === '*' ? 1 : Math.max(1, parseInt(year.slice(2), 10) || 1)
    return { every: n, unit: 'year', startTime: `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`, advanced: false }
  }
  return { every: 1, unit: 'month', startTime: '18:00', advanced: true }
}

function buildCron(every: number, unit: IntervalUnit, startTime: string): string {
  const n = Math.max(1, Math.trunc(every || 1))
  const [hhRaw, mmRaw] = (startTime || '00:00').split(':', 2)
  const hh = Math.min(23, Math.max(0, parseInt(hhRaw || '0', 10) || 0))
  const mm = Math.min(59, Math.max(0, parseInt(mmRaw || '0', 10) || 0))
  if (unit === 'minute') return `*/${n} * * * *`
  if (unit === 'hour') return `${mm} */${n} * * *`
  if (unit === 'week') return `${mm} ${hh} */${7 * n} * *`
  if (unit === 'month') return `${mm} ${hh} 1 */${n} *`
  if (unit === 'year') return `${mm} ${hh} 1 1 * */${n}`
  throw new Error('单位不支持')
}

export default function Jobs() {
  const navigate = useNavigate()
  const [domains, setDomains] = useState<JobDomainInfo[]>([])
  const [runs, setRuns] = useState<JobRunResult[]>([])
  const [schedules, setSchedules] = useState<Record<JobDomain, JobSchedule>>({} as Record<JobDomain, JobSchedule>)
  const [stockDailyStart, setStockDailyStart] = useState(() => {
    const y = new Date().getFullYear()
    return `${y}-01-01`
  })
  const [stockFinancialWorkers, setStockFinancialWorkers] = useState(4)
  const [stockScopeMap, setStockScopeMap] = useState<Record<string, { scopeType: string; groupId: number }>>({
    stock_news: { scopeType: 'all', groupId: 0 },
    report_consensus: { scopeType: 'all', groupId: 0 },
    sentiment_monitor: { scopeType: 'all', groupId: 0 },
  })
  const [editingDomain, setEditingDomain] = useState<JobDomain | null>(null)
  const [editEnabled, setEditEnabled] = useState(true)
  const [editEvery, setEditEvery] = useState(1)
  const [editUnit, setEditUnit] = useState<IntervalUnit>('week')
  const [editStartTime, setEditStartTime] = useState('18:00')
  const [editTimezone, setEditTimezone] = useState('Asia/Shanghai')
  const [editHint, setEditHint] = useState<string | null>(null)
  const [savingSchedule, setSavingSchedule] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [previewDomain, setPreviewDomain] = useState<string | null>(null)
  const [previewCodes, setPreviewCodes] = useState<string[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewTotalCount, setPreviewTotalCount] = useState<number | null>(null)

  const load = async (opts?: { silent?: boolean }) => {
    setLoading(true)
    if (!opts?.silent) setErr(null)
    try {
      const d = await fetchJson<{ domains: JobDomainInfo[] }>('/api/v1/jobs/domains')
      setDomains(d.domains || [])
      const r = await fetchJson<{ runs: JobRunResult[] }>('/api/v1/jobs/runs?limit=50')
      setRuns(r.runs || [])
      const s = await fetchJson<{ schedules: JobSchedule[] }>('/api/v1/jobs/schedules')
      const map = {} as Record<JobDomain, JobSchedule>
      for (const it of s.schedules || []) map[it.domain] = it
      setSchedules(map)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = window.setInterval(() => { load({ silent: true }) }, 1500)
    return () => window.clearInterval(t)
  }, [])

  const runJob = async (domain: JobDomain, mode?: string) => {
    if (hasRunningTask) {
      setErr('已经有任务在进行中，请等待完成以后再开始新的任务')
      return
    }
    setErr(null)
    try {
      const params: Record<string, unknown> = {}
      const mode0 = String(mode || 'test')
      if (domain === 'stock_daily' && stockDailyStart.trim()) params.data_start = stockDailyStart.trim()
      if (domain === 'stock_daily') params.max_stocks = 0
      params.max_workers = stockFinancialWorkers
      if (['stock_news', 'report_consensus', 'sentiment_monitor'].includes(domain)) {
        const cfg = stockScopeMap[domain] || { scopeType: 'all', groupId: 0 }
        if (cfg.scopeType === 'group' && cfg.groupId > 0) {
          params.scope_type = 'group'
          params.group_id = cfg.groupId
        } else if (cfg.scopeType === 'watchlist') {
          params.scope_type = 'watchlist'
        }
      }
      await postJson<{ result: JobRunResult }>('/api/v1/jobs/run', { domain, mode: mode0, params })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const stopJob = async (domain: JobDomain) => {
    setErr(null)
    try {
      // 找到该 domain 正在运行的 run_id
      const running = runs.find((r) => r.domain === domain && r.status === 'running')
      if (!running || !running.runId) return
      await postJson(`/api/v1/jobs/runs/${running.runId}/stop`, {})
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const openScheduleEditor = (domain: JobDomain) => {
    const sch = schedules[domain]
    setEditingDomain(domain)
    setEditEnabled(sch?.enabled ?? true)
    const parsed = parseInterval(sch?.cron || '')
    setEditEvery(parsed.every || 1)
    setEditUnit(parsed.unit || 'week')
    setEditStartTime(parsed.startTime || '18:00')
    setEditTimezone(sch?.timezone ?? 'Asia/Shanghai')
    setEditHint(parsed.advanced ? '当前 cron 格式较复杂，已切换为默认参数。请按"间隔 + 开始时间"重新保存。' : null)
  }

  const saveSchedule = async () => {
    if (!editingDomain) return
    setSavingSchedule(true)
    setErr(null)
    try {
      const cron = buildCron(editEvery, editUnit, editStartTime)
      await fetchJson<{ ok: boolean }>(`/api/v1/jobs/schedules/${editingDomain}`, {
        method: 'PUT',
        body: JSON.stringify({ enabled: editEnabled, cron, timezone: editTimezone }),
      })
      setEditingDomain(null)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setSavingSchedule(false)
    }
  }

  const runsByDomain = useMemo(() => {
    const map = new Map<JobDomain, JobRunResult>()
    for (const r of runs) {
      if (!map.has(r.domain)) map.set(r.domain, r)
    }
    return map
  }, [runs])

  // 检测是否有任何任务正在运行中
  const hasRunningTask = useMemo(() => {
    return runs.some((r) => r.status === 'running')
  }, [runs])

  const domainOrder = ['stock_daily', 'stock_financial', 'stock_news', 'sentiment_monitor', 'report_consensus', 'calendar', 'catalyst', 'macro_indicator', 'rate_daily']

  const sortedDomains = useMemo(() => {
    const order = new Map(domainOrder.map((d, i) => [d, i]))
    return [...domains].sort((a, b) => {
      const ai = order.get(a.domain) ?? 999
      const bi = order.get(b.domain) ?? 999
      return ai - bi
    })
  }, [domains, domainOrder])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="任务列表"
          right={
            <button
              onClick={() => load()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              刷新
            </button>
          }
        />
        <CardBody>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className="text-xs text-zinc-500">日线起始</span>
            <input
              type="date"
              value={stockDailyStart}
              onChange={(e) => setStockDailyStart(e.target.value)}
              className="h-8 rounded-lg border border-zinc-200 bg-white px-2 text-xs text-zinc-900 outline-none focus:border-zinc-400"
            />
            <span className="ml-2 text-xs text-zinc-500">线程数</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setStockFinancialWorkers(Math.max(1, stockFinancialWorkers - 1))}
                className="flex h-8 w-7 items-center justify-center rounded-l-lg border border-zinc-200 bg-white text-xs text-zinc-600 transition hover:bg-zinc-50"
              >
                −
              </button>
              <input
                type="number"
                min={1}
                max={20}
                value={stockFinancialWorkers}
                onChange={(e) => setStockFinancialWorkers(Math.max(1, parseInt(e.target.value) || 1))}
                className="h-8 w-14 border-y border-zinc-200 bg-white px-1 text-center text-xs text-zinc-900 outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button
                onClick={() => setStockFinancialWorkers(Math.min(20, stockFinancialWorkers + 1))}
                className="flex h-8 w-7 items-center justify-center rounded-r-lg border border-zinc-200 bg-white text-xs text-zinc-600 transition hover:bg-zinc-50"
              >
                +
              </button>
            </div>
            <div className="ml-auto" />
            <button
              onClick={() => navigate('/info-access/stock-groups')}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
            >
              股票列表管理
            </button>
          </div>
          {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
          {hasRunningTask ? (
            <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
              已经有任务在进行中，请等待完成以后再开始新的任务
            </div>
          ) : null}
          <div className="space-y-3">
            {loading && domains.length === 0 ? (
              <Loading className="py-16" />
            ) : sortedDomains.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-400">暂无任务类型</div>
            ) : (
              sortedDomains.map((j) => {
              const last = runsByDomain.get(j.domain)
              const sch = schedules[j.domain]
              const isEditing = editingDomain === j.domain
              return (
                <div key={j.domain} data-testid="task-item" className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-zinc-900">{j.title}</div>
                      <div className="mt-1 text-xs text-zinc-500">{j.desc}</div>
                      <div className="mt-1 text-xs text-zinc-500">
                        周期：{sch?.cron ? formatCron(sch.cron) : '—'} {sch?.enabled === false ? '（已停用）' : ''}
                      </div>
                      <div className="mt-1 text-xs text-zinc-500">下次：{formatDate(sch?.nextRunAt)}</div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {last ? <JobStatusBadge status={last.status} /> : null}
                        {last ? <DataSourceBadge source={last.dataSourceFinal} /> : null}
                        {last ? <span className="text-xs text-zinc-500">上次：{formatDate(last.startedAt)}</span> : null}
                      </div>
                      {last && last.status === 'running' && last.itemsTotal ? (
                        <div className="mt-3 w-full max-w-sm space-y-2">
                          {/* 进度条 */}
                          <div className="flex items-center gap-1.5 text-xs text-zinc-600">
                            <BarChart3 className="h-3.5 w-3.5 flex-shrink-0 text-blue-400" />
                            <span className="font-medium tabular-nums">
                              {last.itemsProcessed.toLocaleString()}
                            </span>
                            <span className="text-zinc-300">/</span>
                            <span className="tabular-nums text-zinc-500">
                              {last.itemsTotal.toLocaleString()}
                            </span>
                            <span
                              className="ml-0.5 font-semibold"
                              style={{
                                color: last.itemsTotal > 0
                                  ? `hsl(${Math.round(Math.min(1, ((last.percentage ?? (last.itemsProcessed || 0) / last.itemsTotal * 100)) / 100) * 120)}, 65%, 40%)`
                                  : '#a1a1aa',
                              }}
                            >
                              （{last.percentage ?? Math.round(Math.min(100, ((last.itemsProcessed || 0) / last.itemsTotal) * 100))}%）
                            </span>
                          </div>
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100">
                            <div
                              className="h-full rounded-full transition-all duration-700 ease-out"
                              style={{
                                width: `${last.itemsTotal > 0 ? Math.min(100, Math.round((last.percentage ?? ((last.itemsProcessed || 0) / last.itemsTotal * 100)))) : 0}%`,
                                backgroundColor: last.itemsTotal > 0
                                  ? `hsl(${Math.round(Math.min(1, ((last.percentage ?? ((last.itemsProcessed || 0) / last.itemsTotal) * 100)) / 100) * 120)}, 55%, 45%)`
                                  : '#d4d4d8',
                              }}
                            />
                          </div>
                          {/* 增强信息：日期范围 + 剩余时间 */}
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
                            {last.dateRange ? (
                              <span className="flex items-center gap-1">
                                <span>日期范围:</span>
                                <span className="tabular-nums">{last.dateRange.replace('~', ' ~ ')}</span>
                              </span>
                            ) : null}
                            {last.etaSeconds != null && last.etaSeconds > 0 ? (
                              <span className="flex items-center gap-1">
                                <span>预计剩余:</span>
                                <span className="tabular-nums font-medium text-zinc-600">
                                  {last.etaSeconds >= 3600
                                    ? `${Math.floor(last.etaSeconds / 3600)}小时${Math.round((last.etaSeconds % 3600) / 60)}分`
                                    : last.etaSeconds >= 60
                                      ? `${Math.floor(last.etaSeconds / 60)}分${last.etaSeconds % 60}秒`
                                      : `${last.etaSeconds}秒`}
                                </span>
                              </span>
                            ) : last.etaSeconds === 0 ? (
                              <span className="text-zinc-400">计算中...</span>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </div>
                    <div className="flex flex-col gap-2">
                      {last && last.status === 'running' ? (
                        <button
                          onClick={() => stopJob(j.domain)}
                          className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-xs font-medium text-white transition hover:bg-red-700"
                        >
                          <Square className="h-3.5 w-3.5" />
                          停止
                        </button>
                      ) : (
                        <button
                          onClick={() => runJob(j.domain, j.defaultMode)}
                          disabled={hasRunningTask}
                          className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Play className="h-3.5 w-3.5" />
                          运行
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/info-access/data-collection/detail?domain=${encodeURIComponent(j.domain)}&name=${encodeURIComponent(j.title)}`)}
                        className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
                      >
                        查看详情
                      </button>
                      <button
                        onClick={() => openScheduleEditor(j.domain)}
                        className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
                      >
                        <Settings className="h-3.5 w-3.5" />
                        调度
                      </button>
                    </div>
                  </div>

                  {['stock_news', 'report_consensus', 'sentiment_monitor'].includes(j.domain) && (
                    <div className="mt-3">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-xs text-zinc-400">股票范围：</span>
                        <button
                          onClick={async () => {
                            const cfg = stockScopeMap[j.domain] || { scopeType: 'all', groupId: 0 }
                            setPreviewDomain(j.title)
                            setPreviewLoading(true)
                            setPreviewCodes([])
                            setPreviewTotalCount(null)
                            try {
                              if (cfg.scopeType === 'all') {
                                // 全市场模式：只获取总数，不获取具体列表
                                const resp = await fetchJson<{ ok: boolean; total: number }>('/api/v1/stock-groups/stock-count')
                                setPreviewTotalCount(resp.total || 0)
                                setPreviewCodes([])
                              } else if (cfg.scopeType === 'group' && cfg.groupId > 0) {
                                // 自定义分组：获取分组内的股票列表
                                const resp = await fetchJson<{ items: { stock_code: string }[] }>(`/api/v1/stock-groups/${cfg.groupId}/items`)
                                setPreviewCodes((resp.items || []).map(i => i.stock_code))
                              } else if (cfg.scopeType === 'watchlist') {
                                // 自选股：调用专用接口获取代码列表
                                const resp = await fetchJson<{ ok: boolean; codes: string[] }>('/api/v1/stock-groups/watchlist-codes')
                                setPreviewCodes(resp.codes || [])
                              }
                            } catch {
                              setPreviewCodes([])
                            }
                            setPreviewLoading(false)
                          }}
                          className="inline-flex items-center gap-1 text-xs text-zinc-400 transition hover:text-zinc-700"
                          title="预览股票列表"
                        >
                          <Eye className="h-3 w-3" />
                          预览
                        </button>
                      </div>
                      <StockScopeSelector
                        defaultValue={stockScopeMap[j.domain] || { scopeType: 'all', groupId: 0 }}
                        onChange={(v) => setStockScopeMap(prev => ({ ...prev, [j.domain]: v }))}
                      />
                    </div>
                  )}

                  {isEditing ? (
                    <div className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <div className="text-xs font-semibold text-zinc-900">修改采集周期 / 定时</div>
                        <button
                          type="button"
                          onClick={() => setEditingDomain(null)}
                          className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        <label className="block">
                          <div className="text-xs text-zinc-500">启用</div>
                          <select
                            value={editEnabled ? '1' : '0'}
                            onChange={(e) => setEditEnabled(e.target.value === '1')}
                            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          >
                            <option value="1">启用</option>
                            <option value="0">停用</option>
                          </select>
                        </label>
                        <label className="block">
                          <div className="text-xs text-zinc-500">采集时间间隔</div>
                          <div className="mt-1 flex items-center gap-2">
                            <input
                              inputMode="numeric"
                              value={String(editEvery)}
                              onChange={(e) => {
                                const v = e.target.value.replace(/\D/g, '')
                                setEditEvery(v ? Math.max(1, parseInt(v, 10)) : 1)
                              }}
                              className="w-20 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                            />
                            <select
                              value={editUnit}
                              onChange={(e) => setEditUnit(e.target.value as IntervalUnit)}
                              className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                            >
                              <option value="minute">分</option>
                              <option value="hour">小时</option>
                              <option value="week">周</option>
                              <option value="month">月</option>
                              <option value="year">年</option>
                            </select>
                          </div>
                        </label>
                        <label className="block">
                          <div className="text-xs text-zinc-500">开始时间</div>
                          <input
                            type="time"
                            value={editStartTime}
                            onChange={(e) => setEditStartTime(e.target.value)}
                            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          />
                        </label>
                        <label className="block md:col-span-3">
                          <div className="text-xs text-zinc-500">时区</div>
                          <input
                            value={editTimezone}
                            onChange={(e) => setEditTimezone(e.target.value)}
                            className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                          />
                        </label>
                      </div>
                      <div className="mt-3 flex items-center justify-between">
                        <div className="text-xs text-zinc-500">示例：10 分钟 → */10 * * * *；2 小时 + 08:30 → 30 */2 * * *</div>
                        <button
                          type="button"
                          disabled={savingSchedule}
                          onClick={saveSchedule}
                          className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
                        >
                          <Save className="h-3.5 w-3.5" />
                          保存
                        </button>
                      </div>
                      {editHint ? <div className="mt-2 text-xs text-amber-700">{editHint}</div> : null}
                    </div>
                  ) : null}
                </div>
              )
            }))}
          </div>
        </CardBody>
      </Card>

      {/* 股票预览弹窗 */}
      {previewDomain !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => { setPreviewDomain(null); setPreviewTotalCount(null) }}>
          <div className="w-[480px] max-h-[70vh] rounded-xl bg-white p-5 shadow-xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-semibold text-zinc-900">{previewDomain} - 股票预览</div>
              <button onClick={() => { setPreviewDomain(null); setPreviewTotalCount(null) }} className="text-zinc-400 hover:text-zinc-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            {previewLoading ? (
              <Loading className="py-8" size="sm" />
            ) : previewTotalCount !== null ? (
              <div className="py-8 text-center text-xs text-zinc-500">
                全市场模式已选中约 {previewTotalCount} 只股票
              </div>
            ) : previewCodes.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-400">暂无股票数据</div>
            ) : (
              <>
                <div className="mb-2 text-xs text-zinc-500">共 {previewCodes.length} 只股票</div>
                <div className="grid grid-cols-4 gap-1">
                  {previewCodes.map((c) => (
                    <span key={c} className="rounded bg-zinc-50 px-2 py-1 text-xs text-zinc-700">{c}</span>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
