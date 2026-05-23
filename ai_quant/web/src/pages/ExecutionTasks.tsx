import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { useEffect, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import { PlayCircle, RefreshCcw, StopCircle, Trash2, Edit3, CheckCircle } from 'lucide-react'

type ExecStatus = { source: string; status: string; features: string[] }
type Task = {
  id: string; symbol: string; side: 'buy' | 'sell'
  total_qty: number; num_steps: number
  strategy: 'twap' | 'vwap' | 'rl'
  status: 'draft' | 'running' | 'stopped' | 'finished' | 'failed'
  created_at: string; error?: string | null
  progress?: number
}

const STRAT_LABELS: Record<string, string> = { twap: 'TWAP', vwap: 'VWAP', rl: 'RL强化学习' }
const SIDE_LABELS = { buy: '买入', sell: '卖出' }
const STATUS_LABELS: Record<string, { label: string; tone: 'green' | 'amber' | 'red' | 'blue' | 'zinc' }> = {
  draft: { label: '草稿', tone: 'zinc' },
  running: { label: '执行中', tone: 'blue' },
  stopped: { label: '已停止', tone: 'amber' },
  finished: { label: '已完成', tone: 'green' },
  failed: { label: '失败', tone: 'red' },
}

function fmt(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 19 ? s.slice(0, 19).replace('T', ' ') : s
}

export default function ExecutionTasks() {
  const [status, setStatus] = useState<ExecStatus | null>(null)
  const [items, setItems] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [symbol, setSymbol] = useState('')
  const [execStock, setExecStock] = useState<StockSearchItem | null>(null)
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [totalQty, setTotalQty] = useState('1000')
  const [strategy, setStrategy] = useState<'twap' | 'vwap' | 'rl'>('twap')
  const [creating, setCreating] = useState(false)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editQty, setEditQty] = useState('')
  const [editStrategy, setEditStrategy] = useState<'twap' | 'vwap' | 'rl'>('twap')

  useEffect(() => {
    fetchJson<ExecStatus>('/api/v1/execution/status').then(setStatus).catch(() => null)
  }, [])

  const load = async () => {
    setLoading(true)

    setErr(null)
    try {
      const r = await fetchJson<{ items: Task[] }>('/api/v1/execution/tasks')
      setItems(r.items || [])
    } catch (e) {
      setItems([])
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const changeTaskStatus = async (id: string, newStatus: string) => {
    try {
      await fetchJson(`/api/v1/execution/tasks/${id}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status: newStatus }),
      })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const deleteTask = async (id: string) => {
    try {
      await fetchJson(`/api/v1/execution/tasks/${id}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const startEdit = (t: Task) => {
    setEditingId(t.id)
    setEditQty(String(t.total_qty))
    setEditStrategy(t.strategy)
  }

  const saveEdit = async (id: string) => {
    const qty = Number(editQty || 0)
    if (!isFinite(qty) || qty < 100) { setErr('数量最少为 100'); return }
    try {
      await fetchJson(`/api/v1/execution/tasks/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ total_qty: qty, strategy: editStrategy }),
      })
      setEditingId(null)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const cancelEdit = () => {
    setEditingId(null)
  }

  const createTask = async () => {
    const sym = symbol.trim()
    if (!sym) { setErr('请填写股票代码'); return }
    const qty = Number(totalQty || 0)
    if (!isFinite(qty) || qty < 100) { setErr('数量最少为 100'); return }
    setCreating(true)
    setErr(null)
    try {
      await postJson('/api/v1/execution/tasks', { symbol: sym, side, total_qty: qty, num_steps: 48, strategy })
      setSymbol('')
      setExecStock(null)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="执行终端" />
          <CardBody className="space-y-3 text-sm">
            <div className="flex items-center gap-4 text-xs text-zinc-500">
              <span>模块：{status?.source || '—'}</span>
              <span>状态：{status?.status || 'loading'}</span>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
              能力：{(status?.features || []).join(' / ') || '—'}
            </div>

            {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            <div className="space-y-3 rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">创建执行任务</div>
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <div className="mb-1 text-xs text-zinc-500">股票代码 *</div>
                  <StockPicker
                    value={execStock}
                    onChange={(v) => {
                      const item = v as StockSearchItem | null
                      setExecStock(item)
                      setSymbol(item?.code ?? '')
                    }}
                    mode="single"
                    placeholder="搜索股票代码或名称"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">方向</div>
                  <select
                    value={side}
                    onChange={(e) => setSide(e.target.value as 'buy' | 'sell')}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                </div>
                <div>
                  <div className="mb-1 text-xs text-zinc-500">策略</div>
                  <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value as 'twap' | 'vwap' | 'rl')}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  >
                    <option value="twap">TWAP</option>
                    <option value="vwap">VWAP</option>
                    <option value="rl">RL 强化学习</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <div className="mb-1 text-xs text-zinc-500">数量（股）</div>
                  <input
                    value={totalQty}
                    onChange={(e) => setTotalQty(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                </div>
              </div>
              <button
                type="button"
                disabled={creating}
                onClick={createTask}
                className={cn(
                  'mt-2 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition',
                  creating ? 'bg-zinc-400' : 'bg-zinc-900 hover:bg-zinc-800'
                )}
              >
                <PlayCircle className="h-4 w-4" />
                {creating ? '创建中…' : '创建任务'}
              </button>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader
            title="执行任务列表"
            right={
              <button
                onClick={load}
                disabled={loading}
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                刷新
              </button>
            }
          />
          <CardBody className="p-0">
            <div className="max-h-[520px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                    <th className="px-4 py-2">股票</th>
                    <th className="px-4 py-2">方向</th>
                    <th className="px-4 py-2">策略</th>
                    <th className="px-4 py-2">数量</th>
                    <th className="px-4 py-2">状态</th>
                    <th className="px-4 py-2">时间</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && items.length === 0 ? (
                    <tr><td className="px-4 py-12 text-center text-zinc-500" colSpan={7}>加载中…</td></tr>
                  ) : items.length === 0 ? (
                    <tr><td className="px-4 py-12 text-center text-zinc-500" colSpan={7}>暂无执行任务</td></tr>
                  ) : items.map((t) => {
                    const st = STATUS_LABELS[t.status] || { label: t.status, tone: 'zinc' as const }
                    const isEditing = editingId === t.id
                    return (
                      <tr key={t.id} className="border-b border-zinc-50">
                        <td className="px-4 py-2 font-medium text-zinc-900">{t.symbol}</td>
                        <td className="px-4 py-2">
                          <Badge tone={t.side === 'buy' ? 'green' : 'red'}>{SIDE_LABELS[t.side]}</Badge>
                        </td>
                        <td className="px-4 py-2 text-zinc-700">
                          {isEditing ? (
                            <select
                              value={editStrategy}
                              onChange={(e) => setEditStrategy(e.target.value as 'twap' | 'vwap' | 'rl')}
                              className="rounded border border-zinc-200 px-1 py-0.5 text-xs"
                            >
                              <option value="twap">TWAP</option>
                              <option value="vwap">VWAP</option>
                              <option value="rl">RL</option>
                            </select>
                          ) : (
                            STRAT_LABELS[t.strategy] || t.strategy
                          )}
                        </td>
                        <td className="px-4 py-2 text-zinc-700">
                          {isEditing ? (
                            <input
                              type="number"
                              value={editQty}
                              onChange={(e) => setEditQty(e.target.value)}
                              className="w-20 rounded border border-zinc-200 px-1 py-0.5 text-xs"
                            />
                          ) : (
                            t.total_qty.toLocaleString()
                          )}
                        </td>
                        <td className="px-4 py-2">
                          <Badge tone={st.tone}>{st.label}</Badge>
                        </td>
                        <td className="px-4 py-2 text-xs text-zinc-500">{fmt(t.created_at)}</td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-1">
                            {isEditing ? (
                              <>
                                <button
                                  onClick={() => saveEdit(t.id)}
                                  className="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-2 py-1 text-xs text-green-600 transition hover:bg-green-50"
                                >
                                  <CheckCircle className="h-3 w-3" />
                                  保存
                                </button>
                                <button
                                  onClick={cancelEdit}
                                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50"
                                >
                                  取消
                                </button>
                              </>
                            ) : (
                              <>
                                {t.status === 'draft' && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'running')}
                                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2 py-1 text-xs text-blue-600 transition hover:bg-blue-50"
                                  >
                                    <PlayCircle className="h-3 w-3" />
                                    运行
                                  </button>
                                )}
                                {t.status === 'running' && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'stopped')}
                                    className="inline-flex items-center gap-1 rounded-lg border border-amber-200 bg-white px-2 py-1 text-xs text-amber-600 transition hover:bg-amber-50"
                                  >
                                    <StopCircle className="h-3 w-3" />
                                    停止
                                  </button>
                                )}
                                {(t.status === 'stopped' || t.status === 'failed') && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'running')}
                                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2 py-1 text-xs text-blue-600 transition hover:bg-blue-50"
                                  >
                                    <PlayCircle className="h-3 w-3" />
                                    运行
                                  </button>
                                )}
                                {(t.status === 'draft' || t.status === 'stopped' || t.status === 'failed') && (
                                  <button
                                    onClick={() => startEdit(t)}
                                    className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50"
                                  >
                                    <Edit3 className="h-3 w-3" />
                                    编辑
                                  </button>
                                )}
                                {t.status !== 'running' && (
                                  <button
                                    onClick={() => deleteTask(t.id)}
                                    className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-2 py-1 text-xs text-red-600 transition hover:bg-red-50"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                    删除
                                  </button>
                                )}
                                {t.status === 'running' && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'finished')}
                                    className="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-2 py-1 text-xs text-green-600 transition hover:bg-green-50"
                                  >
                                    <CheckCircle className="h-3 w-3" />
                                    完成
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
