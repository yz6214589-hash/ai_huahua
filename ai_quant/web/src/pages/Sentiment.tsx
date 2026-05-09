import { fetchJson, postJson } from '@/api/client'
import type { MacroLatest, SentimentEvent, SentimentRun, StockSearchItem } from '@/api/types'
import { Badge } from '@/components/Badge'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Tabs } from '@/components/Tabs'
import { cn } from '@/lib/utils'
import { ExternalLink, PlayCircle, RefreshCcw, Search, Settings2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

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

export default function Sentiment() {
  const [tab, setTab] = useState<'watch' | 'macro'>('watch')

  const [schedule, setSchedule] = useState<{ enabled: boolean; cron: string; timezone: string } | null>(null)
  const [scheduleSaving, setScheduleSaving] = useState(false)

  const [manualStockQuery, setManualStockQuery] = useState('')
  const [manualStockResults, setManualStockResults] = useState<StockSearchItem[]>([])
  const [manualSelected, setManualSelected] = useState<StockSearchItem[]>([])
  const [manualDays, setManualDays] = useState(3)
  const [manualUseLlm, setManualUseLlm] = useState(false)
  const [manualStockSearching, setManualStockSearching] = useState(false)
  const [manualStockErr, setManualStockErr] = useState<string | null>(null)

  const [events, setEvents] = useState<SentimentEvent[]>([])
  const [runs, setRuns] = useState<SentimentRun[]>([])
  const [latestRun, setLatestRun] = useState<SentimentRun | null>(null)
  const [filterQ, setFilterQ] = useState('')
  const [filterEventType, setFilterEventType] = useState<'全部' | '利好' | '利空' | '政策'>('全部')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [macro, setMacro] = useState<MacroLatest | null>(null)
  const [macroLoading, setMacroLoading] = useState(false)

  const selectedCodes = useMemo(() => new Set(manualSelected.map((s) => s.code)), [manualSelected])

  const loadSchedule = async () => {
    const r = await fetchJson<{ enabled: boolean; cron: string; timezone: string }>('/api/sentiment/schedule')
    setSchedule(r)
  }

  const loadRuns = async () => {
    const r = await fetchJson<{ runs: SentimentRun[] }>('/api/sentiment/runs?limit=20')
    setRuns(r.runs || [])
    setLatestRun((r.runs || [])[0] || null)
  }

  const loadEvents = async (runId?: string) => {
    const params = new URLSearchParams()
    params.set('limit', '200')
    if (runId) params.set('run_id', runId)
    if (filterQ.trim()) params.set('q', filterQ.trim())
    if (filterEventType !== '全部') params.set('event_type', filterEventType)
    const r = await fetchJson<{ events: SentimentEvent[] }>(`/api/sentiment/events?${params.toString()}`)
    setEvents(r.events || [])
  }

  const refreshWatch = async () => {
    setLoading(true)
    setErr(null)
    try {
      await loadSchedule()
      await loadRuns()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshWatch()
  }, [])

  useEffect(() => {
    const t = window.setInterval(async () => {
      try {
        await loadRuns()
      } catch {}
    }, 2000)
    return () => window.clearInterval(t)
  }, [])

  useEffect(() => {
    loadEvents(latestRun?.run_id)
  }, [latestRun?.run_id, latestRun?.status, latestRun?.finished_at, filterQ, filterEventType])

  useEffect(() => {
    let alive = true
    const t = window.setTimeout(async () => {
      const v = manualStockQuery.trim()
      if (!v) {
        setManualStockResults([])
        setManualStockErr(null)
        return
      }
      const ctrl = new AbortController()
      const tt = window.setTimeout(() => ctrl.abort(), 5000)
      try {
        setManualStockSearching(true)
        setManualStockErr(null)
        const r = await fetchJson<{ items: StockSearchItem[] }>(`/api/stocks?q=${encodeURIComponent(v)}&limit=20`, { signal: ctrl.signal })
        if (!alive) return
        setManualStockResults(r.items || [])
      } catch {
        if (!alive) return
        setManualStockResults([])
        setManualStockErr('搜索超时或失败')
      } finally {
        window.clearTimeout(tt)
        if (alive) setManualStockSearching(false)
      }
    }, 200)
    return () => {
      alive = false
      window.clearTimeout(t)
    }
  }, [manualStockQuery])

  const toggleSchedule = async () => {
    if (!schedule) return
    setScheduleSaving(true)
    setErr(null)
    try {
      await fetchJson('/api/sentiment/schedule', { method: 'PUT', body: JSON.stringify({ enabled: !schedule.enabled }) })
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
      await postJson('/api/sentiment/runs', { days: 3, use_llm: false })
      await loadRuns()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const addManualStock = (it: StockSearchItem) => {
    if (selectedCodes.has(it.code)) return
    setManualSelected((prev) => [...prev, it])
  }

  const removeManualStock = (code: string) => {
    setManualSelected((prev) => prev.filter((x) => x.code !== code))
  }

  const clearManual = () => {
    setManualSelected([])
    setManualStockQuery('')
    setManualStockResults([])
  }

  const runManual = async () => {
    setErr(null)
    if (manualSelected.length === 0) {
      setErr('请先选择股票')
      return
    }
    try {
      await postJson('/api/sentiment/runs', {
        stock_codes: manualSelected.map((s) => s.code),
        days: manualDays,
        use_llm: manualUseLlm,
      })
      clearManual()
      await loadRuns()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const loadMacro = async () => {
    setMacroLoading(true)
    try {
      const r = await fetchJson<MacroLatest>('/api/macro/latest')
      setMacro(r)
    } finally {
      setMacroLoading(false)
    }
  }

  useEffect(() => {
    if (tab === 'macro' && !macro) loadMacro()
  }, [tab])

  const openPolymarket = (q: string) => {
    window.open(`https://polymarket.com/search?q=${encodeURIComponent(q)}`, '_blank', 'noreferrer')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Tabs
          value={tab}
          onChange={(v) => setTab(v as any)}
          items={[
            { key: 'watch', label: '自选股舆情' },
            { key: 'macro', label: '宏观风险' },
          ]}
        />
        {tab === 'watch' ? (
          <button
            onClick={refreshWatch}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
          >
            <RefreshCcw className="h-4 w-4" />
            刷新
          </button>
        ) : (
          <button
            onClick={loadMacro}
            disabled={macroLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
          >
            <RefreshCcw className="h-4 w-4" />
            刷新一次
          </button>
        )}
      </div>

      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

      {tab === 'watch' ? (
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
                <div className="mt-2 text-xs text-zinc-500">事件识别默认关键词，可在“手动分析股票”里开启 LLM 精检。</div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="手动分析股票"
                right={
                  <div className="flex items-center gap-2">
                    <button
                      onClick={clearManual}
                      className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
                    >
                      <X className="h-4 w-4" />
                      清空
                    </button>
                    <button
                      onClick={runManual}
                      className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white hover:bg-zinc-800"
                    >
                      <PlayCircle className="h-4 w-4" />
                      立即分析
                    </button>
                  </div>
                }
              />
              <CardBody>
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                  <input
                    value={manualStockQuery}
                    onChange={(e) => setManualStockQuery(e.target.value)}
                    placeholder="搜索股票代码/名称"
                    className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-3 text-sm outline-none transition focus:border-zinc-400"
                  />
                </div>

                {manualStockResults.length > 0 ? (
                  <div className="mt-2 space-y-2">
                    {manualStockResults.map((it) => (
                      <div key={it.code} className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-zinc-900">{it.code}</div>
                          <div className="truncate text-xs text-zinc-500">{it.name || '—'}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => addManualStock(it)}
                          disabled={selectedCodes.has(it.code)}
                          className={cn(
                            'inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50',
                            selectedCodes.has(it.code) ? 'opacity-60' : ''
                          )}
                        >
                          添加
                        </button>
                      </div>
                    ))}
                  </div>
                ) : manualStockSearching ? (
                  <div className="mt-2 text-xs text-zinc-500">搜索中…</div>
                ) : manualStockErr ? (
                  <div className="mt-2 text-xs text-red-600">{manualStockErr}</div>
                ) : null}

                {manualSelected.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {manualSelected.map((s) => (
                      <button
                        key={s.code}
                        type="button"
                        onClick={() => removeManualStock(s.code)}
                        className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                        title="点击移除"
                      >
                        <span className="font-semibold">{s.code}</span>
                        <span className="text-zinc-500">{s.name || '—'}</span>
                        <span className="text-zinc-400">×</span>
                      </button>
                    ))}
                  </div>
                ) : null}

                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
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
              <div className="flex flex-wrap items-end gap-3">
                <label className="block flex-1">
                  <div className="text-xs text-zinc-500">股票公司筛选</div>
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
                    onChange={(e) => setFilterEventType(e.target.value as any)}
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
                      <th className="px-3 py-2">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.length === 0 ? (
                      <tr>
                        <td className="px-3 py-6 text-sm text-zinc-500" colSpan={11}>
                          暂无舆情数据
                        </td>
                      </tr>
                    ) : (
                      events.map((e) => (
                        <tr key={e.id} className="border-t border-zinc-100">
                          <td className="px-3 py-2 text-sm text-zinc-900">
                            {e.stock_code} {e.stock_name || ''}
                          </td>
                          <td className="px-3 py-2">
                            <EventTypeBadge t={e.event_type} />
                          </td>
                          <td className="px-3 py-2 text-sm text-zinc-900">{e.event_category}</td>
                          <td className="px-3 py-2 text-sm text-zinc-900">{e.signal}</td>
                          <td className="px-3 py-2 text-sm text-zinc-700">{e.impact || e.signal_reason || '—'}</td>
                          <td className="px-3 py-2 text-sm text-zinc-900">{e.confidence || '—'}</td>
                          <td className="px-3 py-2 text-sm text-zinc-900">{e.urgency || '—'}</td>
                          <td className="px-3 py-2 text-sm text-zinc-900">{e.source_type === 'notice' ? '公告' : '新闻'}</td>
                          <td className="px-3 py-2">
                            {e.source_url ? (
                              <a
                                className="inline-flex items-center gap-2 text-sm text-blue-600 hover:underline"
                                href={e.source_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <ExternalLink className="h-4 w-4" />
                                打开
                              </a>
                            ) : (
                              <span className="text-zinc-400">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(e.published_at)}</td>
                          <td className="px-3 py-2">
                            <a
                              className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
                              href={`/sentiment/runs/${e.run_id}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                              查看详情
                            </a>
                          </td>
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
                          <td className="px-3 py-2">
                            <RunStatusBadge s={r.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </CardBody>
          </Card>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            {(macro?.indicators || []).map((it) => (
              <Card key={it.indicator}>
                <CardBody>
                  <div className="text-2xl font-bold text-zinc-900">{it.indicator === 'US10Y' && typeof it.value === 'number' ? `${(it.value * 100).toFixed(2)}%` : it.value ?? '—'}</div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {it.indicator} {it.name || ''} {it.date ? `· ${it.date}` : ''}
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader title="综合恐慌/贪婪指数" />
            <CardBody>
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-3xl font-extrabold text-zinc-900">{macro?.composite?.composite_fear_greed_index ?? '—'} / 100</div>
                  <div className="mt-1 text-sm text-zinc-600">
                    整体情绪：{macro?.composite?.overall_sentiment ?? '—'}；建议：{macro?.composite?.action_suggestion ?? '—'}
                  </div>
                </div>
                <div className="w-full max-w-[420px] rounded-lg border border-zinc-200 bg-white p-3">
                  <div className="text-xs text-zinc-500">更新时间</div>
                  <div className="mt-1 text-sm text-zinc-900">{macro?.composite?.timestamp ?? '—'}</div>
                </div>
              </div>

              <div className="mt-4 rounded-lg border border-zinc-200 bg-white p-3">
                <div className="text-sm font-semibold text-zinc-900">Polymarket 快捷入口</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {['war', 'ceasefire', 'tariff', 'China', 'Fed'].map((k) => (
                    <button
                      key={k}
                      onClick={() => openPolymarket(k)}
                      className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
                    >
                      {k}
                    </button>
                  ))}
                  <a
                    className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
                    href="https://polymarket.com/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink className="h-4 w-4" />
                    Polymarket
                  </a>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  )
}
