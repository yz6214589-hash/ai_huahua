import { Loading } from '@/components/Loading'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { cn } from '@/lib/utils'
import { useEffect, useState, useCallback } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { StockPicker } from '@/components/StockPicker'
import type { StockSearchItem } from '@/api/types'
import { PlayCircle, RefreshCcw, StopCircle, Trash2, Edit3, CheckCircle, Link, ChevronUp, ChevronDown } from 'lucide-react'
import { useTrading } from './Execution'

type ExecStatus = { source: string; status: string; features: string[] }
type Task = {
  id: string; symbol: string; side: 'buy' | 'sell'
  total_qty: number
  status: 'draft' | 'running' | 'stopped' | 'finished' | 'failed'
  created_at: string; error?: string | null
  meta?: Record<string, unknown>
}

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

function floorToHundred(n: number): number {
  if (n <= 0) return 0
  return Math.floor(n / 100) * 100
}

function ceilToHundred(n: number): number {
  if (n <= 0) return 0
  return Math.ceil(n / 100) * 100
}

const STORAGE_KEY = 'execution_form_state_v2'

interface FormState {
  symbol: string
  stockCode: string
  side: 'buy' | 'sell'
  totalQty: string
  price: string
  remark: string
}

const DEFAULT_FORM: FormState = {
  symbol: '',
  stockCode: '',
  side: 'buy',
  totalQty: '1000',
  price: '',
  remark: '',
}

function loadFormState(): FormState {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      return { ...DEFAULT_FORM, ...parsed }
    }
  } catch { /* ignore */ }
  return DEFAULT_FORM
}

function saveFormState(state: FormState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch { /* ignore */ }
}

export default function ExecutionTasks() {
  const { connectedAccount, accountId } = useTrading()

  const [status, setStatus] = useState<ExecStatus | null>(null)
  const [items, setItems] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [savedForm] = useState(() => loadFormState())

  const [symbol, setSymbol] = useState(savedForm.symbol)
  const [execStock, setExecStock] = useState<StockSearchItem | null>(null)
  const [side, setSide] = useState<'buy' | 'sell'>(savedForm.side)
  const [totalQty, setTotalQty] = useState(savedForm.totalQty)
  const [price, setPrice] = useState(savedForm.price)
  const [remark, setRemark] = useState(savedForm.remark)
  const [creating, setCreating] = useState(false)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editQty, setEditQty] = useState('')

  const persistForm = useCallback(() => {
    saveFormState({ symbol, stockCode: execStock?.code ?? '', side, totalQty, price, remark })
  }, [symbol, execStock, side, totalQty, price, remark])

  useEffect(() => { persistForm() }, [persistForm])

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
    if (!connectedAccount) { setErr('请先连接账户'); return }
    try {
      const url = `/api/v1/execution/tasks/${id}/status?account_type=${encodeURIComponent(connectedAccount)}`
      await fetchJson(url, {
        method: 'PUT',
        body: JSON.stringify({ status: newStatus }),
      })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const deleteTask = async (id: string) => {
    if (!connectedAccount) { setErr('请先连接账户'); return }
    try {
      await fetchJson(`/api/v1/execution/tasks/${id}`, { method: 'DELETE' })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const startEdit = (t: Task) => {
    if (!connectedAccount) { setErr('请先连接账户'); return }
    setEditingId(t.id)
    setEditQty(String(t.total_qty))
  }

  const saveEdit = async (id: string) => {
    if (!connectedAccount) { setErr('请先连接账户'); return }
    const qty = floorToHundred(Number(editQty || 0))
    if (qty < 100) { setErr('数量最少为 100'); return }
    try {
      await fetchJson(`/api/v1/execution/tasks/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ total_qty: qty }),
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

  const adjustQty = (direction: 'up' | 'down') => {
    const current = Number(totalQty || 0)
    if (!isFinite(current) || current < 0) return
    let newQty: number
    if (direction === 'up') {
      newQty = current % 100 === 0 ? current + 100 : ceilToHundred(current)
    } else {
      if (current <= 0) return
      newQty = current % 100 === 0 ? Math.max(current - 100, 0) : floorToHundred(current)
    }
    setTotalQty(String(newQty))
  }

  const handleQtyBlur = () => {
    const qty = Number(totalQty || 0)
    if (!isFinite(qty) || qty <= 0) { setTotalQty(''); return }
    setTotalQty(String(Math.max(floorToHundred(qty), 100)))
  }

  const handleStockChange = async (v: unknown) => {
    const item = v as StockSearchItem | null
    setExecStock(item)
    const code = item?.code ?? ''
    setSymbol(code)
    if (code) {
      try {
        const snap = await fetchJson<{ price: number | null }>(`/api/v1/stock/${encodeURIComponent(code)}/snapshot`)
        if (snap && snap.price != null) {
          setPrice(String(snap.price))
          return
        }
      } catch {
        // 快照接口不可用时静默失败，价格留空让用户手动输入
      }
    }
    setPrice('')
  }

  const createOrder = async () => {
    if (!connectedAccount) { setErr('请先连接账户'); return }
    const sym = symbol.trim()
    if (!sym) { setErr('请填写股票代码'); return }
    const qty = floorToHundred(Number(totalQty || 0))
    if (qty < 100) { setErr('数量最少为 100'); return }
    const priceNum = price ? Number(price) : 0
    setCreating(true)
    setErr(null)
    try {
      const accountQuery = `account_type=${encodeURIComponent(connectedAccount)}`

      // 第一步：创建执行任务（自动将 account_type 存入 meta）
      const created = await postJson<{ task: Task }>(
        `/api/v1/execution/tasks?${accountQuery}`,
        {
          symbol: sym,
          side: side,
          total_qty: qty,
          meta: { price: priceNum, remark },
        },
      )
      const taskId = created?.task?.id
      if (!taskId) {
        setErr('创建执行任务失败，未返回任务ID')
        setCreating(false)
        return
      }

      // 第二步：触发任务执行（状态变更为 running -> 后端自动真实下单）
      const resultTask = await fetchJson<{ task: Task }>(
        `/api/v1/execution/tasks/${taskId}/status?${accountQuery}`,
        {
          method: 'PUT',
          body: JSON.stringify({ status: 'running' }),
        },
      )

      // 第三步：刷新任务列表
      await load()

      // 清空表单
      setSymbol('')
      setExecStock(null)
      setPrice('')
      setRemark('')
      setTotalQty('1000')
      setSide('buy')

      // 显示最终状态
      const finalStatus = resultTask?.task?.status
      if (finalStatus === 'finished') {
        setErr('下单成功')
      } else if (finalStatus === 'failed') {
        setErr(`下单失败: ${resultTask?.task?.error || '未知错误'}`)
      } else {
        setErr('下单成功')
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setCreating(false)
    }
  }

  if (!connectedAccount) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Link className="mb-3 h-8 w-8 text-zinc-300" />
        <p className="text-zinc-400">请先在上方连接账户</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="执行终端" />
          <CardBody className="space-y-3 text-sm">
            <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
              <span className="font-medium">当前使用账户：</span>
              <span>{connectedAccount}</span>
            </div>

            {err ? (
              <div className={cn(
                'rounded-lg border px-3 py-2 text-xs transition-all duration-300',
                err.includes('成功')
                  ? 'border-green-200 bg-green-50 text-green-700'
                  : 'border-red-200 bg-red-50 text-red-700'
              )}>
                {err}
              </div>
            ) : null}

            <div className="space-y-3 rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">快速下单</div>
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <div className="mb-1 text-xs text-zinc-500">股票代码 *</div>
                  <StockPicker
                    value={execStock}
                    onChange={handleStockChange}
                    mode="single"
                    placeholder="搜索股票代码或名称"
                  />
                </div>

                <div>
                  <div className="mb-1 text-xs text-zinc-500">方向</div>
                  <select
                    value={side}
                    onChange={(e) => setSide(e.target.value as 'buy' | 'sell')}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400 focus:ring-1 focus:ring-zinc-300"
                  >
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                </div>

                <div>
                  <div className="mb-1 text-xs text-zinc-500">数量（股）*</div>
                  <div className="flex">
                    <input
                      value={totalQty}
                      onChange={(e) => {
                        const val = e.target.value
                        if (val === '' || /^\d+$/.test(val)) { setTotalQty(val) }
                      }}
                      onBlur={handleQtyBlur}
                      type="text"
                      inputMode="numeric"
                      className="w-full rounded-l-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400 focus:ring-1 focus:ring-zinc-300"
                    />
                    <div className="flex flex-col border-y border-r border-zinc-200 rounded-r-lg overflow-hidden">
                      <button
                        type="button"
                        onClick={() => adjustQty('up')}
                        className="flex h-1/2 items-center justify-center px-2 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800 active:bg-zinc-200"
                        title="增加100股"
                      >
                        <ChevronUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => adjustQty('down')}
                        className="flex h-1/2 items-center justify-center border-t border-zinc-200 px-2 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-800 active:bg-zinc-200"
                        title="减少100股"
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-zinc-400">每次调整 ±100 股，失焦后自动取整</div>
                </div>

                <div>
                  <div className="mb-1 text-xs text-zinc-500">价格（留空为市价）</div>
                  <input
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    type="number"
                    step="0.01"
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400 focus:ring-1 focus:ring-zinc-300"
                  />
                </div>

                <div className="col-span-2">
                  <div className="mb-1 text-xs text-zinc-500">备注</div>
                  <input
                    value={remark}
                    onChange={(e) => setRemark(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400 focus:ring-1 focus:ring-zinc-300"
                  />
                </div>
              </div>

              <button
                type="button"
                disabled={creating || !connectedAccount}
                onClick={createOrder}
                className={cn(
                  'mt-2 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition',
                  creating || !connectedAccount
                    ? 'bg-zinc-400 cursor-not-allowed'
                    : 'bg-zinc-900 hover:bg-zinc-800 active:bg-zinc-700'
                )}
              >
                <PlayCircle className="h-4 w-4" />
                {!connectedAccount ? '请先连接账户' : creating ? '下单中...' : '下单'}
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
                disabled={loading || !connectedAccount}
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
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
                    <th className="px-4 py-2">数量</th>
                    <th className="px-4 py-2">状态</th>
                    <th className="px-4 py-2">时间</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && items.length === 0 ? (
                    <tr><td className="px-4 py-12 text-center" colSpan={6}><Loading size="sm" /></td></tr>
                  ) : items.length === 0 ? (
                    <tr><td className="px-4 py-12 text-center text-zinc-500" colSpan={6}>暂无执行任务</td></tr>
                  ) : items.map((t) => {
                    const st = STATUS_LABELS[t.status] || { label: t.status, tone: 'zinc' }
                    const isEditing = editingId === t.id
                    const disabled = !connectedAccount
                    return (
                      <tr key={t.id} className="border-b border-zinc-50 transition hover:bg-zinc-50/50">
                        <td className="px-4 py-2 font-medium text-zinc-900">{t.symbol}</td>
                        <td className="px-4 py-2">
                          <Badge tone={t.side === 'buy' ? 'green' : 'red'}>{SIDE_LABELS[t.side]}</Badge>
                        </td>
                        <td className="px-4 py-2 text-zinc-700">
                          {isEditing ? (
                            <input
                              type="text"
                              inputMode="numeric"
                              value={editQty}
                              onChange={(e) => {
                                const val = e.target.value
                                if (val === '' || /^\d+$/.test(val)) { setEditQty(val) }
                              }}
                              onBlur={() => {
                                const qty = floorToHundred(Number(editQty || 0))
                                setEditQty(String(Math.max(qty, 100)))
                              }}
                              disabled={disabled}
                              className="w-20 rounded border border-zinc-200 px-1 py-0.5 text-xs disabled:opacity-50"
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
                                  disabled={disabled}
                                  className="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-2 py-1 text-xs text-green-600 transition hover:bg-green-50 disabled:opacity-50"
                                >
                                  <CheckCircle className="h-3 w-3" />
                                  保存
                                </button>
                                <button
                                  onClick={cancelEdit}
                                  disabled={disabled}
                                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50 disabled:opacity-50"
                                >
                                  取消
                                </button>
                              </>
                            ) : (
                              <>
                                {t.status === 'draft' && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'running')}
                                    disabled={disabled}
                                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2 py-1 text-xs text-blue-600 transition hover:bg-blue-50 disabled:opacity-50"
                                    title="点击执行任务，将通过 QMT Gateway 真实下单"
                                  >
                                    <PlayCircle className="h-3 w-3" />
                                    执行
                                  </button>
                                )}
                                {t.status === 'running' && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'stopped')}
                                    disabled={disabled}
                                    className="inline-flex items-center gap-1 rounded-lg border border-amber-200 bg-white px-2 py-1 text-xs text-amber-600 transition hover:bg-amber-50 disabled:opacity-50"
                                  >
                                    <StopCircle className="h-3 w-3" />
                                    停止
                                  </button>
                                )}
                                {(t.status === 'stopped' || t.status === 'failed') && (
                                  <button
                                    onClick={() => changeTaskStatus(t.id, 'running')}
                                    disabled={disabled}
                                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2 py-1 text-xs text-blue-600 transition hover:bg-blue-50 disabled:opacity-50"
                                    title="重新执行任务"
                                  >
                                    <PlayCircle className="h-3 w-3" />
                                    重新执行
                                  </button>
                                )}
                                {(t.status === 'draft' || t.status === 'stopped' || t.status === 'failed') && (
                                  <button
                                    onClick={() => startEdit(t)}
                                    disabled={disabled}
                                    className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600 transition hover:bg-zinc-50 disabled:opacity-50"
                                  >
                                    <Edit3 className="h-3 w-3" />
                                    编辑
                                  </button>
                                )}
                                {(t.status === 'failed' || t.status === 'draft' || t.status === 'stopped') && (
                                  <button
                                    onClick={() => deleteTask(t.id)}
                                    disabled={disabled}
                                    className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-2 py-1 text-xs text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                    删除
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
            <div className="border-t border-zinc-100 px-4 py-2 text-xs text-zinc-400">
              点击"执行"按钮将通过 QMT Gateway 真实下单，执行后自动更新任务状态
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
