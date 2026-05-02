import { fetchJson, postJson } from '@/api/client'
import type { ReportModel, ReportTask, StockSearchItem } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { ExternalLink, Plus, RefreshCcw, Search, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 10 ? s.slice(0, 19).replace('T', ' ') : s
}

function statusLabel(s: ReportTask['status']) {
  if (s === 'waiting') return '等待'
  if (s === 'running') return '运行中'
  if (s === 'success') return '完成'
  if (s === 'failed') return '失败'
  return s
}

function StatusBadge({ status }: { status: ReportTask['status'] }) {
  const tone = status === 'success' ? 'green' : status === 'failed' ? 'red' : status === 'running' ? 'amber' : 'zinc'
  return <Badge tone={tone}>{statusLabel(status)}</Badge>
}

export default function Reports() {
  const [model, setModel] = useState<ReportModel>('qwen-max')
  const [q, setQ] = useState('')
  const [stockQuery, setStockQuery] = useState('')
  const [stockResults, setStockResults] = useState<StockSearchItem[]>([])
  const [stockSearching, setStockSearching] = useState(false)
  const [stockSearchErr, setStockSearchErr] = useState<string | null>(null)
  const [selectedStocks, setSelectedStocks] = useState<StockSearchItem[]>([])
  const [tasks, setTasks] = useState<ReportTask[]>([])
  const [createdStart, setCreatedStart] = useState('')
  const [createdEnd, setCreatedEnd] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const selectedCodes = useMemo(() => new Set(selectedStocks.map((s) => s.code)), [selectedStocks])

  const loadTasks = async (opts?: { silent?: boolean }) => {
    setLoading(true)
    if (!opts?.silent) setErr(null)
    try {
      const params = new URLSearchParams()
      params.set('limit', '100')
      if (q.trim()) params.set('q', q.trim())
      if (createdStart) params.set('created_start', createdStart)
      if (createdEnd) params.set('created_end', createdEnd)
      const r = await fetchJson<{ tasks: ReportTask[] }>(`/api/reports/tasks?${params.toString()}`)
      setTasks(r.tasks || [])
    } catch (e) {
      if (!opts?.silent) setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTasks()
    const t = window.setInterval(() => {
      loadTasks({ silent: true })
    }, 1500)
    return () => window.clearInterval(t)
  }, [q, createdStart, createdEnd])

  useEffect(() => {
    let alive = true
    const t = window.setTimeout(async () => {
      const v = stockQuery.trim()
      if (!v) {
        setStockResults([])
        setStockSearchErr(null)
        return
      }
      const ctrl = new AbortController()
      const tt = window.setTimeout(() => ctrl.abort(), 5000)
      try {
        setStockSearching(true)
        setStockSearchErr(null)
        const r = await fetchJson<{ items: StockSearchItem[] }>(`/api/stocks?q=${encodeURIComponent(v)}&limit=20`, { signal: ctrl.signal })
        if (!alive) return
        setStockResults(r.items || [])
      } catch {
        if (!alive) return
        setStockResults([])
        setStockSearchErr('搜索超时或失败')
      } finally {
        window.clearTimeout(tt)
        if (alive) setStockSearching(false)
      }
    }, 200)
    return () => {
      alive = false
      window.clearTimeout(t)
    }
  }, [stockQuery])

  const addStock = (it: StockSearchItem) => {
    if (selectedCodes.has(it.code)) return
    setSelectedStocks((prev) => [...prev, it])
  }

  const removeStock = (code: string) => {
    setSelectedStocks((prev) => prev.filter((x) => x.code !== code))
  }

  const createTask = async () => {
    if (selectedStocks.length === 0) {
      setErr('请先选择股票')
      return
    }
    setCreating(true)
    setErr(null)
    try {
      await postJson<{ task: ReportTask }>('/api/reports/tasks', {
        model,
        stock_codes: selectedStocks.map((s) => s.code),
      })
      setSelectedStocks([])
      setStockQuery('')
      await loadTasks()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  const delTask = async (taskId: string) => {
    setErr(null)
    try {
      await fetchJson<{ ok: boolean }>(`/api/reports/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' })
      await loadTasks()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const viewTask = (taskId: string) => {
    window.open(`/api/reports/tasks/${encodeURIComponent(taskId)}/view`, '_blank', 'noreferrer')
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="智能研报" />
          <CardBody>
            {err ? <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            <label className="block">
              <div className="text-xs text-zinc-500">模型</div>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value as ReportModel)}
                className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
              >
                <option value="qwen-max">qwen-max</option>
                <option value="deepseek">deepseek</option>
              </select>
            </label>

            <div className="mt-3">
              <div className="text-xs text-zinc-500">选择股票（多选）</div>
              <div className="relative mt-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                <input
                  value={stockQuery}
                  onChange={(e) => setStockQuery(e.target.value)}
                  placeholder="搜索股票代码/名称"
                  className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-3 text-sm outline-none transition focus:border-zinc-400"
                />
              </div>

              {selectedStocks.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedStocks.map((s) => (
                    <button
                      key={s.code}
                      type="button"
                      onClick={() => removeStock(s.code)}
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

              {stockResults.length > 0 ? (
                <div className="mt-2 space-y-2">
                  {stockResults.map((it) => (
                    <div key={it.code} className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-zinc-900">{it.code}</div>
                        <div className="truncate text-xs text-zinc-500">{it.name || '—'}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => addStock(it)}
                        disabled={selectedCodes.has(it.code)}
                        className={cn(
                          'inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50',
                          selectedCodes.has(it.code) ? 'opacity-60' : ''
                        )}
                      >
                        <Plus className="h-3.5 w-3.5" />
                        添加
                      </button>
                    </div>
                  ))}
                </div>
              ) : stockSearching ? (
                <div className="mt-2 text-xs text-zinc-500">搜索中…</div>
              ) : stockSearchErr ? (
                <div className="mt-2 text-xs text-red-600">{stockSearchErr}</div>
              ) : null}
            </div>

            <button
              type="button"
              disabled={creating}
              onClick={createTask}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              创建研报任务
            </button>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader
            title="任务列表"
            right={
              <button
                onClick={() => loadTasks()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                刷新
              </button>
            }
          />
          <CardBody>
            <div className="flex flex-wrap items-end gap-3">
              <label className="block">
                <div className="text-xs text-zinc-500">创建开始</div>
                <input
                  type="date"
                  value={createdStart}
                  onChange={(e) => setCreatedStart(e.target.value)}
                  className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
              <label className="block">
                <div className="text-xs text-zinc-500">创建结束</div>
                <input
                  type="date"
                  value={createdEnd}
                  onChange={(e) => setCreatedEnd(e.target.value)}
                  className="mt-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
              <label className="block flex-1">
                <div className="text-xs text-zinc-500">股票公司</div>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="输入代码或公司名筛选"
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
            </div>

            <div className="mt-3 overflow-auto rounded-lg border border-zinc-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">创建时间</th>
                    <th className="px-3 py-2">生成时间</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.length === 0 ? (
                    <tr>
                      <td className="px-3 py-6 text-sm text-zinc-500" colSpan={5}>
                        暂无任务
                      </td>
                    </tr>
                  ) : (
                    tasks.map((t) => {
                      const pairs = t.stock_codes.map((c, i) => `${c} ${t.stock_names?.[i] || ''}`.trim())
                      return (
                        <tr key={t.task_id} className="border-t border-zinc-100">
                          <td className="px-3 py-2 text-sm text-zinc-900">{pairs.join('，')}</td>
                          <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(t.created_at)}</td>
                          <td className="px-3 py-2 text-xs text-zinc-700">{fmtDateTime(t.finished_at || null)}</td>
                          <td className="px-3 py-2">
                            <StatusBadge status={t.status} />
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => viewTask(t.task_id)}
                                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                                查看
                              </button>
                              <button
                                type="button"
                                onClick={() => delTask(t.task_id)}
                                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                删除
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
