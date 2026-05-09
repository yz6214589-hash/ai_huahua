import { fetchJson, fetchText, postJson } from '@/api/client'
import type { ReportModel, ReportTask, StockSearchItem } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { ChevronDown, ExternalLink, Plus, RefreshCcw, Search, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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

const RECENT_KEY = 'ai_quant_recent_report_stocks'

export default function Reports() {
  const [model, setModel] = useState<ReportModel>('qwen-max')
  const [useRag, setUseRag] = useState(true)
  const [q, setQ] = useState('')
  const [stockQuery, setStockQuery] = useState('')
  const [stockResults, setStockResults] = useState<StockSearchItem[]>([])
  const [stockSearching, setStockSearching] = useState(false)
  const [stockSearchErr, setStockSearchErr] = useState<string | null>(null)
  const [selectedStocks, setSelectedStocks] = useState<StockSearchItem[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [recentStocks, setRecentStocks] = useState<StockSearchItem[]>([])
  const [tasks, setTasks] = useState<ReportTask[]>([])
  const [createdStart, setCreatedStart] = useState('')
  const [createdEnd, setCreatedEnd] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [retrying, setRetrying] = useState<string | null>(null)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [viewerTask, setViewerTask] = useState<ReportTask | null>(null)
  const [viewerMd, setViewerMd] = useState('')
  const [viewerLoading, setViewerLoading] = useState(false)

  const pickerRef = useRef<HTMLDivElement | null>(null)
  const stockCacheRef = useRef<Map<string, StockSearchItem[]>>(new Map())

  const selectedCodes = useMemo(() => new Set(selectedStocks.map((s) => s.code)), [selectedStocks])

  const showToast = (msg: string) => {
    setToastMsg(msg)
    window.setTimeout(() => setToastMsg(null), 2200)
  }

  const loadTasks = async (opts?: { silent?: boolean }) => {
    setLoading(true)
    if (!opts?.silent) setErr(null)
    try {
      const params = new URLSearchParams()
      params.set('limit', '50')
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
    }, 3000)
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
      const cached = stockCacheRef.current.get(v)
      if (cached) {
        setStockResults(cached)
        setStockSearchErr(null)
        return
      }
      const ctrl = new AbortController()
      const tt = window.setTimeout(() => ctrl.abort(), 1200)
      try {
        setStockSearching(true)
        setStockSearchErr(null)
        const r = await fetchJson<{ items: StockSearchItem[] }>(`/api/stocks?q=${encodeURIComponent(v)}&limit=20`, { signal: ctrl.signal })
        if (!alive) return
        const items = (r.items || []).filter((x) => x && x.code)
        stockCacheRef.current.set(v, items)
        setStockResults(items)
      } catch {
        if (!alive) return
        setStockResults([])
        setStockSearchErr('搜索超时或失败')
      } finally {
        window.clearTimeout(tt)
        if (alive) setStockSearching(false)
      }
    }, 150)
    return () => {
      alive = false
      window.clearTimeout(t)
    }
  }, [stockQuery])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(RECENT_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const items = parsed.filter((x) => x && typeof x.code === 'string').slice(0, 20)
        setRecentStocks(items)
      }
    } catch {
      setRecentStocks([])
    }
  }, [])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const el = pickerRef.current
      if (!el) return
      if (e.target instanceof Node && !el.contains(e.target)) setPickerOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPickerOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  const rememberRecent = (it: StockSearchItem) => {
    const next = [it, ...recentStocks.filter((x) => x.code !== it.code)].slice(0, 20)
    setRecentStocks(next)
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(next))
    } catch {
      return
    }
  }

  const addStock = (it: StockSearchItem) => {
    if (selectedCodes.has(it.code)) return
    setSelectedStocks((prev) => [...prev, it])
    rememberRecent(it)
  }

  const removeStock = (code: string) => {
    setSelectedStocks((prev) => prev.filter((x) => x.code !== code))
  }

  const createTask = async () => {
    if (selectedStocks.length === 0) {
      setErr('请选择至少一只股票')
      return
    }
    setCreating(true)
    setErr(null)
    try {
      await postJson<{ task: ReportTask }>('/api/reports/tasks', {
        model,
        stock_codes: selectedStocks.map((s) => s.code),
        use_rag: useRag,
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

  const retryTask = async (taskId: string) => {
    setErr(null)
    setRetrying(taskId)
    try {
      await fetchJson<{ ok: boolean }>(`/api/reports/tasks/${encodeURIComponent(taskId)}/retry`, { method: 'POST' })
      await loadTasks()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setRetrying(null)
    }
  }

  const viewTask = async (t: ReportTask) => {
    if (t.status === 'failed') {
      showToast(`任务失败：${t.error_message || '未知错误'}`)
      return
    }
    if (t.status !== 'success') {
      showToast('任务仍在运行中，请稍后再试')
      return
    }

    setViewerTask(t)
    setViewerLoading(true)
    setViewerMd('')
    try {
      const md = await fetchText(`/api/reports/tasks/${encodeURIComponent(t.task_id)}/view`)
      setViewerMd(md || '')
    } catch (e) {
      showToast(e instanceof Error ? e.message : String(e))
      setViewerTask(null)
      setViewerMd('')
    } finally {
      setViewerLoading(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      {toastMsg ? (
        <div className="fixed left-1/2 top-4 z-50 -translate-x-1/2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow">
          {toastMsg}
        </div>
      ) : null}

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

            <label className="mt-3 inline-flex items-center gap-2 text-sm text-zinc-700">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-300"
              />
              启用 RAG
            </label>

            <div className="mt-3">
              <div className="text-xs text-zinc-500">选择股票（多选）</div>
              <div ref={pickerRef} className="relative mt-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
                <ChevronDown className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-zinc-400" />
                <input
                  value={stockQuery}
                  onChange={(e) => {
                    setStockQuery(e.target.value)
                    setPickerOpen(true)
                  }}
                  onFocus={() => setPickerOpen(true)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const first = stockResults[0]
                      if (first && first.code) {
                        addStock(first)
                        setStockQuery('')
                        setStockResults([])
                        setStockSearchErr(null)
                        setPickerOpen(false)
                      }
                    }
                  }}
                  placeholder="下拉选择 / 搜索股票代码或名称"
                  className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-9 text-sm outline-none transition focus:border-zinc-400"
                />

                {pickerOpen ? (
                  <div className="absolute z-50 mt-2 w-full rounded-lg border border-zinc-200 bg-white shadow-sm">
                    <div className="flex items-center justify-between gap-2 border-b border-zinc-100 px-3 py-2 text-xs text-zinc-500">
                      <div>{stockQuery.trim() ? '搜索结果' : '最近使用'}</div>
                      <button
                        type="button"
                        onClick={() => setPickerOpen(false)}
                        className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                      >
                        取消
                      </button>
                    </div>

                    {stockQuery.trim() ? (
                      <div className="max-h-72 overflow-auto p-2">
                        {stockResults.length > 0 ? (
                          <div className="space-y-2">
                            {stockResults.map((it) => (
                              <div key={it.code} className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold text-zinc-900">{it.code}</div>
                                  <div className="truncate text-xs text-zinc-500">{it.name || '—'}</div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    addStock(it)
                                    setStockQuery('')
                                    setStockResults([])
                                    setStockSearchErr(null)
                                    setPickerOpen(false)
                                  }}
                                  disabled={selectedCodes.has(it.code)}
                                  className={cn(
                                    'inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50',
                                    selectedCodes.has(it.code) ? 'opacity-60' : ''
                                  )}
                                >
                                  <Plus className="h-3.5 w-3.5" />
                                  选择
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : stockSearching ? (
                          <div className="px-1 py-2 text-xs text-zinc-500">搜索中…</div>
                        ) : stockSearchErr ? (
                          <div className="px-1 py-2 text-xs text-red-600">{stockSearchErr}</div>
                        ) : (
                          <div className="px-1 py-2 text-xs text-zinc-500">无匹配结果</div>
                        )}
                      </div>
                    ) : (
                      <div className="max-h-72 overflow-auto p-2">
                        {recentStocks.length === 0 ? (
                          <div className="px-1 py-2 text-xs text-zinc-500">请输入股票代码或名称进行搜索</div>
                        ) : (
                          <div className="space-y-2">
                            {recentStocks.map((it) => (
                              <div key={it.code} className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-semibold text-zinc-900">{it.code}</div>
                                  <div className="truncate text-xs text-zinc-500">{it.name || '—'}</div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    addStock(it)
                                    setPickerOpen(false)
                                  }}
                                  disabled={selectedCodes.has(it.code)}
                                  className={cn(
                                    'inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50',
                                    selectedCodes.has(it.code) ? 'opacity-60' : ''
                                  )}
                                >
                                  <Plus className="h-3.5 w-3.5" />
                                  选择
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : null}
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
                                onClick={() => viewTask(t)}
                                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                                查看
                              </button>
                              {t.status === 'failed' ? (
                                <button
                                  type="button"
                                  disabled={retrying === t.task_id}
                                  onClick={() => retryTask(t.task_id)}
                                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
                                >
                                  <RefreshCcw className="h-3.5 w-3.5" />
                                  {retrying === t.task_id ? '重试中...' : '重试'}
                                </button>
                              ) : null}
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

      {viewerTask ? (
        <div className="fixed inset-0 z-40 bg-black/30 p-4">
          <div className="mx-auto flex h-full max-w-5xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow">
            <div className="flex items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-zinc-900">研报查看</div>
                <div className="mt-0.5 truncate text-xs text-zinc-500">{(viewerTask.stock_codes || []).join('，')}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setViewerTask(null)
                  setViewerMd('')
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
              >
                <X className="h-3.5 w-3.5" />
                关闭
              </button>
            </div>
            <div className="flex-1 overflow-auto px-4 py-4">
              {viewerLoading ? (
                <div className="text-sm text-zinc-500">加载中...</div>
              ) : (
                <div className="prose prose-zinc max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{viewerMd || ''}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
