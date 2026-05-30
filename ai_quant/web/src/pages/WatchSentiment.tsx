import { Loading } from '@/components/Loading'
import { fetchJson, postJson } from '@/api/client'
import type { SentimentEvent, SentimentRun, StockSearchItem } from '@/api/types'
import { Badge } from '@/components/Badge'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { StockPicker } from '@/components/StockPicker'
import { cn } from '@/lib/utils'
import { ExternalLink, PlayCircle, Settings2, X, Plus, Trash2, RefreshCw, Bell } from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'

function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function RunStatusBadge({ s }: { s: string }) {
  const tone = (s === 'success' ? 'green' : s === 'failed' ? 'red' : s === 'running' ? 'amber' : 'default') as any
  const label = s === 'waiting' ? '等待' : s === 'running' ? '运行中' : s === 'success' ? '完成' : s === 'failed' ? '失败' : s
  return <Badge tone={tone}>{label}</Badge>
}

const MARKET_HOURS = ['9:30', '10:30', '11:30', '13:00', '14:00', '15:00']
const FREQ_OPTIONS = [
  { value: '1h', label: '每小时' },
  { value: '2h', label: '每2小时' },
  { value: '4h', label: '每4小时' },
  { value: 'daily', label: '每日固定时间' },
  { value: 'custom', label: '自定义Cron' },
]

export default function WatchSentiment() {
  const [schedule, setSchedule] = useState<{ enabled: boolean; cron: string; timezone: string; frequency: string; market_time: string; fixed_time: string } | null>(null)
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
  const [activeTab, setActiveTab] = useState<'events' | 'grouped' | 'history'>('events')

  const [watchlist, setWatchlist] = useState<{ code: string; name: string }[]>([])
  const [syncingLoading, setSyncingLoading] = useState(false)

  const [notifyEnabled, setNotifyEnabled] = useState(false)
  const [notifyThreshold, setNotifyThreshold] = useState(0.3)

  const [showScheduleEditor, setShowScheduleEditor] = useState(false)
  const [editFreq, setEditFreq] = useState('daily')
  const [editMarketTime, setEditMarketTime] = useState('14:00')
  const [editFixedTime, setEditFixedTime] = useState('15:10')
  const [editCustomCron, setEditCustomCron] = useState('0 10 15 * * ?')

  const loadSchedule = async () => {
    try {
      const r = await fetchJson<any>('/api/v1/sentiment/schedule')
      setSchedule(r)
      setEditFreq(r.frequency || 'daily')
      setEditMarketTime(r.market_time || '14:00')
      setEditFixedTime(r.fixed_time || '15:10')
      setEditCustomCron(r.cron || '0 10 15 * * ?')
    } catch {
      //
    }
  }

  const loadRuns = async () => {
    try {
      const r = await fetchJson<{ runs: SentimentRun[] }>('/api/v1/sentiment/runs?limit=20')
      setRuns(r.runs || [])
      setLatestRun((r.runs || [])[0] || null)
    } catch {
      //
    }
  }

  const loadEvents = async (runId?: string, eventType?: string) => {
    setLoading(true)
    setErr(null)
    try {
      const params = new URLSearchParams()
      if (runId) params.set('run_id', runId)
      // URLSearchParams.set 会自动对中文参数进行 URL 编码，确保中文字符正确传递
      if (eventType) params.set('event_type', eventType)
      params.set('limit', '200')
      const r = await fetchJson<{ events: SentimentEvent[] }>(`/api/v1/sentiment/events?${params.toString()}`)
      setEvents(r.events || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const loadWatchlist = async () => {
    try {
      const r = await fetchJson<{ items: { stock_code: string; stock_name: string; added_at: string }[] }>('/api/v1/sentiment/stock-list')
      const wl = (r.items || []).map(i => ({
        code: i.stock_code,
        name: i.stock_name || i.stock_code,
      }))
      setWatchlist(wl)
    } catch {
      //
    }
  }

  useEffect(() => { loadSchedule(); loadRuns(); loadWatchlist() }, [])
  useEffect(() => {
    // 当 filterEventType 变化时，将筛选条件传给后端 API（中文参数由 URLSearchParams 自动编码）
    const eventType = filterEventType !== '全部' ? filterEventType : undefined
    loadEvents(latestRun?.run_id, eventType)
  }, [latestRun?.run_id, filterEventType])

  const toggleSchedule = async () => {
    if (!schedule) return
    setScheduleSaving(true)
    try {
      await fetchJson('/api/v1/sentiment/schedule', {
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

  const saveScheduleConfig = async () => {
    setScheduleSaving(true)
    try {
      let cron = editCustomCron
      if (editFreq === 'daily') {
        const [h, m] = editFixedTime.split(':')
        cron = `0 ${m} ${h} * * ?`
      } else if (editFreq === '1h') {
        cron = '0 0 * * * ?'
      } else if (editFreq === '2h') {
        cron = '0 0 */2 * * ?'
      } else if (editFreq === '4h') {
        cron = '0 0 */4 * * ?'
      }
      await fetchJson('/api/v1/sentiment/schedule', {
        method: 'PUT',
        body: JSON.stringify({
          enabled: schedule?.enabled ?? true,
          cron,
          timezone: 'Asia/Shanghai',
          frequency: editFreq,
          market_time: editMarketTime,
          fixed_time: editFixedTime,
        }),
      })
      setShowScheduleEditor(false)
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
      // 修正API端点路径：使用 /api/v1/sentiment/runs
      await postJson('/api/v1/sentiment/runs', {})
      await loadRuns()
      // 重新加载事件时保留当前筛选条件
      const eventType = filterEventType !== '全部' ? filterEventType : undefined
      await loadEvents(latestRun?.run_id, eventType)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const runManual = async () => {
    if (manualSelected.length === 0) return
    setErr(null)
    try {
      // 修正API端点路径：使用 /api/v1/sentiment/runs
      await postJson('/api/v1/sentiment/runs', {
        stock_codes: manualSelected.map((s) => s.code),
        days: manualDays,
        use_llm: manualUseLlm,
      })
      await loadRuns()
      // 重新加载事件时保留当前筛选条件
      const eventType = filterEventType !== '全部' ? filterEventType : undefined
      await loadEvents(latestRun?.run_id, eventType)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const addCustomStock = (item: StockSearchItem) => {
    setWatchlist(prev => {
      if (prev.find(s => s.code === item.code)) return prev
      return [...prev, { code: item.code, name: item.name || item.code }]
    })
  }

  const removeCustomStock = async (code: string) => {
    try {
      await fetchJson(`/api/v1/sentiment/stock-list/${encodeURIComponent(code)}`, { method: 'DELETE' })
      setWatchlist(prev => prev.filter(s => s.code !== code))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const clearManual = () => setManualSelected([])

  const syncFromWatchlist = async () => {
    setSyncingLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ items: { stock_code: string; stock_name: string; added_at: string }[]; added_count: number; skipped_count: number }>('/api/v1/sentiment/stock-list/sync', {
        method: 'POST',
      })
      const wl = (r.items || []).map(i => ({
        code: i.stock_code,
        name: i.stock_name || i.stock_code,
      }))
      setWatchlist(wl)
      if (r.added_count > 0) {
        alert(`已从自选库同步 ${r.added_count} 只股票`)
      } else {
        alert(`自选库股票已全部存在，无需同步（跳过 ${r.skipped_count} 只）`)
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setSyncingLoading(false)
    }
  }

  const filteredEvents = events.filter((e) => {
    if (filterQ && !(e.stock_code + (e.stock_name || '')).toLowerCase().includes(filterQ.toLowerCase())) return false
    if (filterEventType !== '全部' && e.event_type !== filterEventType) return false
    return true
  })

  const groupedByStock = events.reduce<Record<string, { stock_name: string; events: SentimentEvent[]; positive: number; negative: number; neutral: number }>>((acc, e) => {
    const key = e.stock_code
    if (!acc[key]) {
      acc[key] = { stock_name: e.stock_name || e.stock_code, events: [], positive: 0, negative: 0, neutral: 0 }
    }
    acc[key].events.push(e)
    if (e.event_type === '利好') acc[key].positive++
    else if (e.event_type === '利空') acc[key].negative++
    else acc[key].neutral++
    return acc
  }, {})

  const sortedGroups = Object.entries(groupedByStock).sort(([, a], [, b]) => b.negative - a.negative)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">任务与调度</h3>
              <RunStatusBadge s={schedule?.enabled ? 'success' : 'failed'} />
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <div className="text-xs text-zinc-500">扫描频率</div>
                <div className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900">
                  {editFreq === 'daily' ? `每日 ${editFixedTime}` : editFreq === '1h' ? '每小时' : editFreq === '2h' ? '每2小时' : editFreq === '4h' ? '每4小时' : schedule?.cron || '每日收盘后(15:10)'}
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
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-60 transition-colors ${
                  schedule?.enabled
                    ? 'border-green-300 bg-green-50 text-green-700 hover:bg-green-100'
                    : 'border-zinc-300 bg-zinc-100 text-zinc-500 hover:bg-zinc-200'
                }`}
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
              <button
                onClick={() => setShowScheduleEditor(!showScheduleEditor)}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
              >
                <Settings2 className="h-4 w-4" />
                定时配置
              </button>
            </div>
            {showScheduleEditor && (
              <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 space-y-3">
                <div>
                  <label className="text-xs text-zinc-500">执行频率</label>
                  <select value={editFreq} onChange={e => setEditFreq(e.target.value)}
                    className="mt-1 w-full rounded border border-zinc-200 bg-white px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900">
                    {FREQ_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                {editFreq === 'daily' && (
                  <div>
                    <label className="text-xs text-zinc-500">每日执行时间</label>
                    <input type="time" value={editFixedTime} onChange={e => setEditFixedTime(e.target.value)}
                      className="mt-1 w-full rounded border border-zinc-200 bg-white px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  </div>
                )}
                {editFreq === 'custom' && (
                  <div>
                    <label className="text-xs text-zinc-500">Cron表达式</label>
                    <input type="text" value={editCustomCron} onChange={e => setEditCustomCron(e.target.value)}
                      className="mt-1 w-full rounded border border-zinc-200 bg-white px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900 font-mono" />
                  </div>
                )}
                <div>
                  <label className="text-xs text-zinc-500">开盘时段快捷设置</label>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {MARKET_HOURS.map(t => (
                      <button key={t} onClick={() => setEditFixedTime(t)}
                        className={`rounded px-2 py-1 text-xs transition ${editFixedTime === t ? 'bg-zinc-900 text-white' : 'border border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'}`}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <button onClick={() => setShowScheduleEditor(false)} className="rounded border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50">取消</button>
                  <button onClick={saveScheduleConfig} disabled={scheduleSaving}
                    className="rounded bg-zinc-900 px-3 py-1.5 text-xs text-white hover:bg-zinc-800 disabled:opacity-50">保存</button>
                </div>
              </div>
            )}
            <div className="mt-2 text-xs text-zinc-500">事件识别默认关键词，可在「手动分析股票」里开启 LLM 精检。</div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">手动分析股票</h3>
              <div className="flex items-center gap-2">
                <button onClick={clearManual} className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"><X className="h-3 w-3" />清空</button>
                <button onClick={runManual} disabled={manualSelected.length === 0}
                  className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-2.5 py-1.5 text-xs text-white hover:bg-zinc-800 disabled:opacity-60"><PlayCircle className="h-3 w-3" />立即分析</button>
              </div>
            </div>
          </CardHeader>
          <CardBody>
            <StockPicker mode="multiple" value={manualSelected} onChange={(v) => setManualSelected((v as StockSearchItem[]) || [])} placeholder="搜索股票代码或名称" />
            <div className="mt-3 grid grid-cols-3 gap-3">
              <label className="block">
                <div className="text-xs text-zinc-500">days</div>
                <select value={manualDays} onChange={e => setManualDays(parseInt(e.target.value, 10))}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none">
                  <option value={3}>3</option><option value={7}>7</option><option value={14}>14</option>
                </select>
              </label>
              <label className="block">
                <div className="text-xs text-zinc-500">LLM精检</div>
                <select value={manualUseLlm ? '1' : '0'} onChange={e => setManualUseLlm(e.target.value === '1')}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none">
                  <option value="0">关闭</option><option value="1">开启</option>
                </select>
              </label>
              <label className="block">
                <div className="text-xs text-zinc-500">通知阈值</div>
                <select value={notifyThreshold} onChange={e => setNotifyThreshold(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none">
                  <option value={0.3}>得分&lt;0.3</option><option value={0.5}>得分&lt;0.5</option><option value={0.7}>得分&lt;0.7</option>
                </select>
              </label>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">股票列表管理</h3>
              <span className="text-xs text-zinc-500">{watchlist.length}只</span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="mb-3 flex items-center gap-2">
              <StockPicker
                mode="single"
                placeholder="搜索股票代码或名称"
                onChange={(v) => { if (v) addCustomStock(v as StockSearchItem) }}
                className="flex-1"
              />
              <button
                onClick={syncFromWatchlist}
                disabled={syncingLoading}
                className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-2.5 py-1.5 text-xs text-white hover:bg-zinc-800 disabled:opacity-60 whitespace-nowrap"
              >
                <RefreshCw className={cn('h-3 w-3', syncingLoading ? 'animate-spin' : '')} />
                从自选股更新
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {watchlist.map(s => (
                <div key={s.code} className="flex items-center justify-between rounded bg-zinc-50 px-2.5 py-1.5">
                  <div><span className="text-xs font-medium text-zinc-900">{s.code}</span><span className="ml-1.5 text-xs text-zinc-500">{s.name}</span></div>
                  <button onClick={() => removeCustomStock(s.code)} className="rounded p-0.5 text-zinc-400 hover:text-red-500"><Trash2 className="h-3 w-3" /></button>
                </div>
              ))}
              {watchlist.length === 0 && <div className="py-4 text-center text-xs text-zinc-500">暂无自选股</div>}
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h3 className="text-sm font-semibold">监控结果</h3>
                <div className="flex gap-1">
                  {([
                    { key: 'events', label: '事件列表' },
                    { key: 'grouped', label: '按股票分组' },
                    { key: 'history', label: '运行历史' },
                  ] as const).map(tab => (
                    <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                      className={`rounded px-2 py-1 text-xs font-medium transition ${activeTab === tab.key ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'}`}>
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </CardHeader>
          <CardBody>
            {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            {activeTab === 'events' && (
              <div>
                <div className="mb-3 flex items-center gap-3">
                  <input value={filterQ} onChange={e => setFilterQ(e.target.value)} placeholder="搜索股票" className="flex-1 rounded border border-zinc-200 px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  <select value={filterEventType} onChange={e => setFilterEventType(e.target.value as any)}
                    className="rounded border border-zinc-200 px-2 py-1.5 text-xs focus:outline-none">
                    <option value="全部">全部</option><option value="利好">利好</option><option value="利空">利空</option><option value="政策">政策</option>
                  </select>
                  <span className="text-xs text-zinc-500">{filteredEvents.length}条</span>
                </div>
                <div className="overflow-auto max-h-80">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-500">
                      <tr>
                        <th className="px-2 py-1.5">股票</th>
                        <th className="px-2 py-1.5">类型</th>
                        <th className="px-2 py-1.5">类别</th>
                        <th className="px-2 py-1.5">建议</th>
                        <th className="px-2 py-1.5">置信度</th>
                        <th className="px-2 py-1.5">紧急度</th>
                        <th className="px-2 py-1.5">来源</th>
                        <th className="px-2 py-1.5">时间</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {loading ? (
                        <tr><td className="px-2 py-4 text-center" colSpan={8}><Loading className="mx-auto" size="sm" /></td></tr>
                      ) : filteredEvents.length === 0 ? (
                        <tr><td className="px-2 py-4 text-center text-zinc-500" colSpan={8}>暂无舆情数据</td></tr>
                      ) : filteredEvents.map(e => (
                        <tr key={e.id} className={`hover:bg-zinc-50 ${e.event_type === '利空' ? 'bg-red-50/50' : ''}`}>
                          <td className="px-2 py-1.5 text-zinc-900">{e.stock_code}<span className="ml-1 text-zinc-400">{e.stock_name}</span></td>
                          <td className="px-2 py-1.5">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              e.event_type === '利好' ? 'bg-green-100 text-green-700' : e.event_type === '利空' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                            }`}>{e.event_type || '—'}</span>
                          </td>
                          <td className="px-2 py-1.5 text-zinc-600">{e.event_category || '—'}</td>
                          <td className="px-2 py-1.5 text-zinc-600">{e.signal || '—'}</td>
                          <td className="px-2 py-1.5 text-zinc-600">{e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '—'}</td>
                          <td className="px-2 py-1.5 text-zinc-600">{e.urgency || '—'}</td>
                          <td className="px-2 py-1.5 text-zinc-600">{e.source_type || '—'}</td>
                          <td className="px-2 py-1.5 text-zinc-400">{e.published_at ? fmtDateTime(e.published_at) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'grouped' && (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {sortedGroups.map(([code, group]) => (
                  <div key={code} className={`rounded-lg border p-3 ${group.negative > 0 ? 'border-red-200 bg-red-50' : 'border-zinc-200'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-900">{group.stock_name}</span>
                        <span className="text-xs text-zinc-500">{code}</span>
                        {group.negative > 0 && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">{group.negative}条负面</span>}
                      </div>
                      <div className="flex gap-3 text-xs text-zinc-500">
                        <span className="text-green-600">正:{group.positive}</span>
                        <span className="text-red-600">负:{group.negative}</span>
                        <span>中:{group.neutral}</span>
                        <span>共:{group.events.length}</span>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {group.events.slice(0, 3).map(e => (
                        <span key={e.id} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${
                          e.event_type === '利好' ? 'bg-green-100 text-green-700' : e.event_type === '利空' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                        }`}>
                          {e.event_category || e.event_type}
                        </span>
                      ))}
                      {group.events.length > 3 && <span className="text-xs text-zinc-400">+{group.events.length - 3}更多</span>}
                    </div>
                  </div>
                ))}
                {sortedGroups.length === 0 && <div className="py-4 text-center text-xs text-zinc-500">暂无数据</div>}
              </div>
            )}

            {activeTab === 'history' && (
              <div className="overflow-auto max-h-80">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 text-zinc-500">
                    <tr>
                      <th className="px-2 py-1.5">RunID</th>
                      <th className="px-2 py-1.5">触发方式</th>
                      <th className="px-2 py-1.5">创建时间</th>
                      <th className="px-2 py-1.5">事件数</th>
                      <th className="px-2 py-1.5">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {runs.map(r => (
                      <tr key={r.run_id} className="hover:bg-zinc-50">
                        <td className="px-2 py-1.5 text-zinc-900 font-mono">{r.run_id}</td>
                        <td className="px-2 py-1.5 text-zinc-600">{r.trigger}</td>
                        <td className="px-2 py-1.5 text-zinc-500">{fmtDateTime(r.created_at)}</td>
                        <td className="px-2 py-1.5 text-zinc-900">{r.total_events ?? 0}</td>
                        <td className="px-2 py-1.5"><RunStatusBadge s={r.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {runs.length === 0 && <div className="py-4 text-center text-xs text-zinc-500">暂无运行记录</div>}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader><h3 className="text-sm font-semibold">通知设置</h3></CardHeader>
        <CardBody>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Bell className="h-4 w-4 text-zinc-400" />
              <div>
                <div className="text-sm font-medium text-zinc-900">负面舆情通知</div>
                <div className="text-xs text-zinc-500">当检测到重大负面舆情时发送系统通知</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <select value={notifyThreshold} onChange={e => setNotifyThreshold(Number(e.target.value))}
                className="rounded border border-zinc-200 px-2 py-1.5 text-xs focus:outline-none">
                <option value={0.3}>情感得分&lt;0.3触发</option>
                <option value={0.5}>情感得分&lt;0.5触发</option>
                <option value={0.7}>情感得分&lt;0.7触发</option>
              </select>
              <label className="relative inline-flex cursor-pointer items-center">
                <input type="checkbox" className="peer sr-only" checked={notifyEnabled} onChange={() => setNotifyEnabled(!notifyEnabled)} />
                <div className="h-5 w-9 rounded-full bg-zinc-200 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-zinc-900 peer-checked:after:translate-x-full" />
              </label>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
