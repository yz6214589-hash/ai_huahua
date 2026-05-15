import { fetchJson, postJson } from '@/api/client'
import type { SentimentEvent, SentimentRun, StockSearchItem } from '@/api/types'
import { Badge } from '@/components/Badge'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { StockPicker } from '@/components/StockPicker'
import { ExternalLink, PlayCircle, Settings2, X } from 'lucide-react'
import { useEffect, useState } from 'react'

function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function EventTypeBadge({ t }: { t: string }) {
  const tone = t === '利好' ? 'green' : t === '利空' ? 'red' : t === '政策' ? 'blue' : 'zinc'
  return <Badge tone={tone}>{t || '—'}</Badge>
}

function RunStatusBadge({ s }: { s: string }) {
  const tone = s === 'success' ? 'green' : s === 'failed' ? 'red' : s === 'running' ? 'amber' : 'zinc'
  const label = s === 'waiting' ? '等待' : s === 'running' ? '运行中' : s === 'success' ? '完成' : s === 'failed' ? '失败' : s
  return <Badge tone={tone}>{label}</Badge>
}

export default function WatchSentiment() {
  const [schedule, setSchedule] = useState<{ enabled: boolean; cron: string; timezone: string } | null>(null)
  const [scheduleSaving, setScheduleSaving] = useState(false)

  const [manualSelected, setManualSelected] = useState<StockSearchItem[]>([])
  const [manualDays, setManualDays] = useState(3)
  const [manualUseLlm, setManualUseLlm] = useState(false)

  const [events, setEvents] = useState<SentimentEvent[]>([])
  const [runs, setRuns] = useState<SentimentRun[]>([])
  const [latestRun, setLatestRun] = useState<SentimentRun | null>(null)
  const [filterQ, setFilterQ] = useState('')
  const [filterEventType, setFilterEventType] = useState<'全部' | '利好' | '利空' | '政策'>('全部')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const loadSchedule = async () => {
    const r = await fetchJson<{ enabled: boolean; cron: string; timezone: string }>('/api/v1/sentiment/schedule')
    setSchedule(r)
  }

  const loadRuns = async () => {
    const r = await fetchJson<{ runs: SentimentRun[] }>('/api/v1/sentiment/runs?limit=20')
    setRuns(r.runs || [])
    setLatestRun((r.runs || [])[0] || null)
  }

  const loadEvents = async (runId?: string) => {
    setLoading(true)
    setErr(null)
    try {
      const params = new URLSearchParams()
      if (runId) params.set('run_id', runId)
      params.set('limit', '100')
      const r = await fetchJson<{ events: SentimentEvent[] }>(`/api/v1/sentiment/events?${params.toString()}`)
      setEvents(r.events || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const toggleSchedule = async () => {
    if (!schedule) return
    setScheduleSaving(true)
    try {
      await fetchJson(`/api/v1/sentiment/schedule`, {
        method: 'PUT',
        body: JSON.stringify({ enabled: !schedule.enabled, cron: schedule.cron, timezone: schedule.timezone }),
      })
      await loadSchedule()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setScheduleSaving(false)
    }
  }

  const runWatchlistOnce = async () => {
    setErr(null)
    try {
      await postJson('/api/v1/sentiment/watchlist', {})
      await loadRuns()
      await loadEvents()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const runManual = async () => {
    if (manualSelected.length === 0) return
    setErr(null)
    try {
      await postJson('/api/v1/sentiment/analyze', {
        stock_codes: manualSelected.map((s) => s.code),
        days: manualDays,
        use_llm: manualUseLlm,
      })
      await loadRuns()
      await loadEvents()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const clearManual = () => setManualSelected([])

  useEffect(() => { loadSchedule(); loadRuns() }, [])
  useEffect(() => { loadEvents() }, [])
  useEffect(() => { loadEvents(latestRun?.run_id) }, [latestRun?.run_id])

  const filteredEvents = events.filter((e) => {
    if (filterQ && !(e.stock_code + (e.stock_name || '')).toLowerCase().includes(filterQ.toLowerCase())) return false
    if (filterEventType !== '全部' && e.event_type !== filterEventType) return false
    return true
  })

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="任务与调度" right={<RunStatusBadge s={schedule?.enabled ? 'success' : 'failed'} />} />
          <CardBody>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <div className="text-xs text-zinc-500">扫描频率</div>
                <div className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900">
                  每日收盘后（15:10）
                </div>
              </div>
              <div>
                <div className="text-xs text-zinc-500">最近一次运行</div>
                <div className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900">
                  {latestRun ? `${fmtDateTime(latestRun.created_at)}（${latestRun.status}）` : '—'}
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={toggleSchedule}
                disabled={scheduleSaving}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
              >
                <Settings2 className="h-4 w-4" />
                {schedule?.enabled ? '已启用（点击暂停）' : '已暂停（点击启用）'}
              </button>
              <button
                onClick={runWatchlistOnce}
                className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white hover:bg-zinc-800"
              >
                <PlayCircle className="h-4 w-4" />
                立即扫描自选股
              </button>
            </div>
            <div className="mt-2 text-xs text-zinc-500">事件识别默认关键词，可在「手动分析股票」里开启 LLM 精检。</div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="手动分析股票"
            right={
              <div className="flex items-center gap-2">
                <button onClick={clearManual} className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50">
                  <X className="h-4 w-4" />清空
                </button>
                <button
                  onClick={runManual}
                  disabled={manualSelected.length === 0}
                  className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white hover:bg-zinc-800 disabled:opacity-60"
                >
                  <PlayCircle className="h-4 w-4" />立即分析
                </button>
              </div>
            }
          />
          <CardBody>
            <StockPicker
              mode="multiple"
              value={manualSelected}
              onChange={(v) => setManualSelected((v as StockSearchItem[]) || [])}
              placeholder="搜索股票代码或名称"
            />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <label className="block">
                <div className="text-xs text-zinc-500">days</div>
                <select
                  value={manualDays}
                  onChange={(e) => setManualDays(parseInt(e.target.value, 10))}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                >
                  <option value={3}>3</option>
                  <option value={7}>7</option>
                  <option value={14}>14</option>
                </select>
              </label>
              <label className="block">
                <div className="text-xs text-zinc-500">LLM 精检</div>
                <select
                  value={manualUseLlm ? '1' : '0'}
                  onChange={(e) => setManualUseLlm(e.target.value === '1')}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                >
                  <option value="0">关闭（默认）</option>
                  <option value="1">开启</option>
                </select>
              </label>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="事件列表（最近一次 Run）" />
        <CardBody>
          {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}
          <div className="flex flex-wrap items-end gap-3">
            <label className="block flex-1">
              <div className="text-xs text-zinc-500">股票/公司筛选</div>
              <input
                value={filterQ}
                onChange={(e) => setFilterQ(e.target.value)}
                placeholder="例如：600519 或 贵州茅台"
                className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
              />
            </label>
            <label className="block w-[160px]">
              <div className="text-xs text-zinc-500">事件类型</div>
              <select
                value={filterEventType}
                onChange={(e) => setFilterEventType(e.target.value as typeof filterEventType)}
                className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
              >
                <option value="全部">全部</option>
                <option value="利好">利好</option>
                <option value="利空">利空</option>
                <option value="政策">政策</option>
              </select>
            </label>
          </div>
          <div className="mt-3 overflow-auto rounded-lg border border-zinc-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2">股票</th>
                  <th className="px-3 py-2">事件类型</th>
                  <th className="px-3 py-2">事件类别</th>
                  <th className="px-3 py-2">策略建议</th>
                  <th className="px-3 py-2">影响推断</th>
                  <th className="px-3 py-2">置信度</th>
                  <th className="px-3 py-2">紧急度</th>
                  <th className="px-3 py-2">来源</th>
                  <th className="px-3 py-2">原文链接</th>
                  <th className="px-3 py-2">触发时间</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td className="px-3 py-6 text-sm text-zinc-500" colSpan={10}>加载中…</td></tr>
                ) : filteredEvents.length === 0 ? (
                  <tr><td className="px-3 py-6 text-sm text-zinc-500" colSpan={10}>暂无舆情数据</td></tr>
                ) : (
                  filteredEvents.map((e) => (
                    <tr key={e.id} className="border-t border-zinc-100">
                      <td className="px-3 py-2 text-sm text-zinc-900">{e.stock_code} {e.stock_name || ''}</td>
                      <td className="px-3 py-2"><EventTypeBadge t={e.event_type} /></td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{e.event_category || '—'}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{e.signal || '—'}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{e.impact || '—'}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '—'}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{e.urgency || '—'}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{e.source_type || '—'}</td>
                      <td className="px-3 py-2">
                        {e.source_url ? (
                          <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-zinc-700 hover:text-zinc-900">
                            <ExternalLink className="h-3.5 w-3.5" />查看
                          </a>
                        ) : '—'}
                      </td>
                      <td className="px-3 py-2 text-xs text-zinc-500">{e.published_at ? fmtDateTime(e.published_at) : '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <details className="mt-3">
            <summary className="cursor-pointer text-sm text-zinc-500">任务运行记录（最近 20 次）</summary>
            <div className="mt-2 overflow-auto rounded-lg border border-zinc-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">RunID</th>
                    <th className="px-3 py-2">触发方式</th>
                    <th className="px-3 py-2">创建时间</th>
                    <th className="px-3 py-2">结束时间</th>
                    <th className="px-3 py-2">事件数</th>
                    <th className="px-3 py-2">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.run_id} className="border-t border-zinc-100">
                      <td className="px-3 py-2 text-xs text-zinc-900">{r.run_id}</td>
                      <td className="px-3 py-2 text-xs text-zinc-900">{r.trigger}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(r.created_at)}</td>
                      <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(r.finished_at)}</td>
                      <td className="px-3 py-2 text-xs text-zinc-900">{r.total_events ?? 0}</td>
                      <td className="px-3 py-2"><RunStatusBadge s={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </CardBody>
      </Card>
    </div>
  )
}
