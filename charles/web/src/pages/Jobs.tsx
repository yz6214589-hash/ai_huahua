import { useEffect, useMemo, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import type { JobDomain, JobRunResult, JobSchedule } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DataSourceBadge, JobStatusBadge } from '@/components/StatusBadge'
import { Play, RefreshCcw, Save, Settings, X } from 'lucide-react'

const JOBS: { domain: JobDomain; title: string; desc: string; defaultMode?: 'test' | 'full' }[] = [
  { domain: 'stock_daily', title: '行情日线', desc: 'OHLCV + 换手率（QMT 口径）', defaultMode: 'test' },
  { domain: 'stock_financial', title: '财务季度', desc: '三大报表 + 指标提取', defaultMode: 'test' },
  { domain: 'stock_news', title: '新闻事件', desc: 'AkShare 新闻 + LLM 摘要（可选）', defaultMode: 'test' },
  { domain: 'macro_indicator', title: '宏观指标', desc: 'CPI/PPI/PMI/M2/社融/LPR', defaultMode: 'full' },
  { domain: 'rate_daily', title: '利率日频', desc: '中美 10Y 国债收益率', defaultMode: 'full' },
  { domain: 'calendar', title: '财经日历', desc: '未来 30 天 + 过去 7 天事件', defaultMode: 'full' },
  { domain: 'report_consensus', title: '研报一致预期', desc: '东方财富评级 + 同花顺一致预期', defaultMode: 'test' },
  { domain: 'catalyst', title: '关键催化剂', desc: 'Qwen 联网搜索未来 6 个月催化剂', defaultMode: 'full' },
]

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

export default function Jobs() {
  const [runs, setRuns] = useState<JobRunResult[]>([])
  const [selectedDomain, setSelectedDomain] = useState<JobDomain>('stock_daily')
  const [selected, setSelected] = useState<JobRunResult | null>(null)
  const [history, setHistory] = useState<JobRunResult[]>([])
  const [schedules, setSchedules] = useState<Record<JobDomain, JobSchedule>>({} as Record<JobDomain, JobSchedule>)
  const [editingDomain, setEditingDomain] = useState<JobDomain | null>(null)
  const [editEnabled, setEditEnabled] = useState(true)
  const [editCron, setEditCron] = useState('')
  const [editTimezone, setEditTimezone] = useState('Asia/Shanghai')
  const [savingSchedule, setSavingSchedule] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ runs: JobRunResult[] }>('/api/jobs/runs?limit=50')
      setRuns(r.runs || [])
      const s = await fetchJson<{ schedules: JobSchedule[] }>('/api/jobs/schedules')
      const map = {} as Record<JobDomain, JobSchedule>
      for (const it of s.schedules || []) {
        map[it.domain] = it
      }
      setSchedules(map)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = window.setInterval(() => {
      load()
    }, 1500)
    return () => window.clearInterval(t)
  }, [])

  const loadHistory = async (domain: JobDomain) => {
    try {
      const r = await fetchJson<{ runs: JobRunResult[] }>(`/api/jobs/runs?domain=${encodeURIComponent(domain)}&limit=100`)
      setHistory(r.runs || [])
      const first = (r.runs || [])[0]
      setSelected(first || null)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    loadHistory(selectedDomain)
  }, [selectedDomain])

  const runJob = async (domain: JobDomain, mode?: string) => {
    setErr(null)
    try {
      const res = await postJson<{ result: JobRunResult }>('/api/jobs/run', { domain, mode, params: { test_stock: '600519.SH' } })
      setSelected(res.result)
      setSelectedDomain(domain)
      await loadHistory(domain)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const openScheduleEditor = (domain: JobDomain) => {
    const sch = schedules[domain]
    setEditingDomain(domain)
    setEditEnabled(sch?.enabled ?? true)
    setEditCron(sch?.cron ?? '')
    setEditTimezone(sch?.timezone ?? 'Asia/Shanghai')
  }

  const saveSchedule = async () => {
    if (!editingDomain) return
    setSavingSchedule(true)
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(`/api/jobs/schedules/${editingDomain}`, {
        method: 'PUT',
        body: JSON.stringify({ enabled: editEnabled, cron: editCron, timezone: editTimezone }),
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
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader
            title="任务列表"
            right={
              <button
                onClick={load}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                刷新
              </button>
            }
          />
          <CardBody>
            {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
            <div className="space-y-3">
              {JOBS.map((j) => {
                const last = runsByDomain.get(j.domain)
                const sch = schedules[j.domain]
                const isEditing = editingDomain === j.domain
                return (
                  <div key={j.domain} className="rounded-xl border border-zinc-200 bg-white p-3">
                    <div className="flex items-start justify-between gap-3">
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
                          className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-zinc-800"
                        >
                          <Play className="h-3.5 w-3.5" />
                          运行
                        </button>
                        <button
                          onClick={() => {
                            setSelectedDomain(j.domain)
                          }}
                          className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
                        >
                          查看
                        </button>
                        <button
                          onClick={() => openScheduleEditor(j.domain)}
                          className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 transition hover:bg-zinc-50"
                        >
                          <Settings className="h-3.5 w-3.5" />
                          调度
                        </button>
                      </div>
                    </div>

                    {isEditing ? (
                      <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                        <div className="flex items-center justify-between">
                          <div className="text-xs font-semibold text-zinc-900">修改采集周期 / 定时</div>
                          <button
                            type="button"
                            onClick={() => setEditingDomain(null)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                          <label className="block">
                            <div className="text-xs text-zinc-500">启用</div>
                            <select
                              value={editEnabled ? '1' : '0'}
                              onChange={(e) => setEditEnabled(e.target.value === '1')}
                              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                            >
                              <option value="1">启用</option>
                              <option value="0">停用</option>
                            </select>
                          </label>
                          <label className="block md:col-span-2">
                            <div className="text-xs text-zinc-500">cron（分 时 日 月 周）</div>
                            <input
                              value={editCron}
                              onChange={(e) => setEditCron(e.target.value)}
                              placeholder={sch?.cron || '0 18 * * 1-5'}
                              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                            />
                          </label>
                          <label className="block md:col-span-3">
                            <div className="text-xs text-zinc-500">时区</div>
                            <input
                              value={editTimezone}
                              onChange={(e) => setEditTimezone(e.target.value)}
                              className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                            />
                          </label>
                        </div>
                        <div className="mt-3 flex items-center justify-between">
                          <div className="text-xs text-zinc-500">示例：工作日 18:00 → 0 18 * * 1-5；每10分钟 → */10 * * * *</div>
                          <button
                            type="button"
                            disabled={savingSchedule}
                            onClick={saveSchedule}
                            className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
                          >
                            <Save className="h-3.5 w-3.5" />
                            保存
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader title="运行详情" />
          <CardBody>
            <div className="space-y-4">
              <div className="rounded-xl border border-zinc-200 bg-white">
                <div className="border-b border-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-900">历史运行记录</div>
                <div className="max-h-64 overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-white">
                      <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                        <th className="px-4 py-2">时间</th>
                        <th className="px-4 py-2">状态</th>
                        <th className="px-4 py-2">rows</th>
                        <th className="px-4 py-2">source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.length === 0 ? (
                        <tr>
                          <td className="px-4 py-6 text-sm text-zinc-500" colSpan={4}>
                            暂无运行记录
                          </td>
                        </tr>
                      ) : (
                        history.map((r) => (
                          <tr
                            key={r.runId}
                            onClick={() => setSelected(r)}
                            className="cursor-pointer border-b border-zinc-50 hover:bg-zinc-50"
                          >
                            <td className="px-4 py-2 text-xs text-zinc-700">{formatDate(r.startedAt)}</td>
                            <td className="px-4 py-2">
                              <JobStatusBadge status={r.status} />
                            </td>
                            <td className="px-4 py-2 text-zinc-700">{r.rowsWritten.toLocaleString()}</td>
                            <td className="px-4 py-2">
                              <DataSourceBadge source={r.dataSourceFinal} />
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {!selected ? (
                <div className="text-sm text-zinc-500">选择一条运行记录查看详情</div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">runId</div>
                      <div className="mt-1 break-all text-xs text-zinc-900">{selected.runId}</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">status</div>
                      <div className="mt-1">
                        <JobStatusBadge status={selected.status} />
                      </div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">dataSourceFinal</div>
                      <div className="mt-1">
                        <DataSourceBadge source={selected.dataSourceFinal} />
                      </div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                      <div className="text-xs text-zinc-500">fallbackChain</div>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {selected.fallbackChain.length === 0 ? <span className="text-xs text-zinc-500">—</span> : null}
                        {selected.fallbackChain.map((s, i) => (
                          <span key={`${s}-${i}`}>
                            <DataSourceBadge source={s} />
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-500">itemsProcessed</div>
                      <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.itemsProcessed.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-500">rowsWritten</div>
                      <div className="mt-1 text-sm font-semibold text-zinc-900">{selected.rowsWritten.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="text-xs text-zinc-500">time</div>
                      <div className="mt-1 text-xs text-zinc-700">
                        {formatDate(selected.startedAt)} → {formatDate(selected.finishedAt)}
                      </div>
                    </div>
                  </div>

                  {selected.message ? (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{selected.message}</div>
                  ) : null}

                  <div>
                    <div className="text-sm font-semibold text-zinc-900">failedItems</div>
                    <div className="mt-2 max-h-40 overflow-auto rounded-lg border border-zinc-200 bg-white p-3 text-xs text-zinc-700">
                      {selected.failedItems.length === 0 ? '—' : selected.failedItems.join('\n')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

