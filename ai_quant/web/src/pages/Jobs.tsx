import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchJson, postJson } from '@/api/client'
import type { JobDomain, JobDomainInfo, JobRunResult, JobSchedule } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { Play, RefreshCcw, Save, Settings, X } from 'lucide-react'

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
  const [stockDailyStart, setStockDailyStart] = useState('2023-01-01')
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
    setErr(null)
    try {
      const params: Record<string, unknown> = {}
      const mode0 = String(mode || 'test')
      if (domain === 'stock_daily' && stockDailyStart.trim()) params.data_start = stockDailyStart.trim()
      await postJson<{ result: JobRunResult }>('/api/v1/jobs/run', { domain, mode: mode0, params })
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
          </div>
          {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
          <div className="space-y-3">
            {domains.map((j) => {
              const last = runsByDomain.get(j.domain)
              const sch = schedules[j.domain]
              const isEditing = editingDomain === j.domain
              return (
                <div key={j.domain} className="rounded-xl border border-zinc-200 bg-white p-4">
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
                    </div>
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => runJob(j.domain, j.defaultMode)}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-zinc-800"
                      >
                        <Play className="h-3.5 w-3.5" />
                        运行
                      </button>
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
            })}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
