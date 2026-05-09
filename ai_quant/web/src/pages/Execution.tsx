import { Card, CardBody, CardHeader } from '@/components/Card'
import { cn } from '@/lib/utils'
import { useEffect, useState } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { RefreshCcw } from 'lucide-react'

type ExecutionStatus = {
  source: string
  status: string
  features: string[]
}

type ExecutionTask = {
  id: string
  symbol: string
  side: 'buy' | 'sell'
  total_qty: number
  num_steps: number
  strategy: 'twap' | 'vwap' | 'rl'
  status: 'draft' | 'running' | 'stopped' | 'finished' | 'failed'
  created_at: string
  error?: string | null
}

export default function Execution() {
  const [data, setData] = useState<ExecutionStatus | null>(null)
  const [items, setItems] = useState<ExecutionTask[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [totalQty, setTotalQty] = useState('1000')
  const [strategy, setStrategy] = useState<'twap' | 'vwap' | 'rl'>('twap')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    fetchJson<ExecutionStatus>('/api/execution/status')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  const loadTasks = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<{ items: ExecutionTask[] }>('/api/execution/tasks')
      setItems(r.items || [])
    } catch (e) {
      setItems([])
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTasks()
  }, [])

  const createTask = async () => {
    const sym = symbol.trim()
    if (!sym) {
      setErr('请填写股票代码')
      return
    }
    const qty = Number(totalQty || 0)
    if (!isFinite(qty) || qty < 100) {
      setErr('数量最少为 100')
      return
    }
    setCreating(true)
    setErr(null)
    try {
      await postJson('/api/execution/tasks', { symbol: sym, side, total_qty: qty, num_steps: 48, strategy })
      await loadTasks()
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
          <CardHeader title="执行监控" />
          <CardBody className="space-y-3 text-sm text-zinc-700">
            <div>模块来源：{data?.source || 'ethan'}</div>
            <div>状态：{data?.status || 'loading'}</div>
            <div>能力：{(data?.features || []).join(' / ') || '—'}</div>

            {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-sm font-semibold text-zinc-900">创建任务</div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block col-span-2">
                  <div className="text-xs text-zinc-500">股票代码</div>
                  <input
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="例如 600519.SH"
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">方向</div>
                  <select
                    value={side}
                    onChange={(e) => setSide(e.target.value as 'buy' | 'sell')}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  >
                    <option value="buy">buy</option>
                    <option value="sell">sell</option>
                  </select>
                </label>
                <label className="block">
                  <div className="text-xs text-zinc-500">策略</div>
                  <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value as 'twap' | 'vwap' | 'rl')}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  >
                    <option value="twap">twap</option>
                    <option value="vwap">vwap</option>
                    <option value="rl">rl</option>
                  </select>
                </label>
                <label className="block col-span-2">
                  <div className="text-xs text-zinc-500">数量（total_qty）</div>
                  <input
                    value={totalQty}
                    onChange={(e) => setTotalQty(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                  />
                </label>
              </div>

              <button
                type="button"
                disabled={creating}
                onClick={createTask}
                className={cn('mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60')}
              >
                <RefreshCcw className="h-4 w-4" />
                {creating ? '创建中...' : '创建任务'}
              </button>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader
            title="任务列表"
            right={
              <button
                onClick={loadTasks}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                刷新
              </button>
            }
          />
          <CardBody className="p-0">
            <div className="max-h-[620px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                    <th className="px-4 py-2">symbol</th>
                    <th className="px-4 py-2">side</th>
                    <th className="px-4 py-2">qty</th>
                    <th className="px-4 py-2">strategy</th>
                    <th className="px-4 py-2">status</th>
                    <th className="px-4 py-2">error</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-sm text-zinc-500" colSpan={6}>
                        {loading ? '加载中…' : '暂无任务'}
                      </td>
                    </tr>
                  ) : (
                    items.map((t) => (
                      <tr key={t.id} className="border-b border-zinc-50 align-top">
                        <td className="px-4 py-2 font-medium text-zinc-900">{t.symbol}</td>
                        <td className="px-4 py-2 text-zinc-700">{t.side}</td>
                        <td className="px-4 py-2 text-zinc-700">{t.total_qty}</td>
                        <td className="px-4 py-2 text-zinc-700">{t.strategy}</td>
                        <td className="px-4 py-2 text-zinc-700">{t.status}</td>
                        <td className="px-4 py-2 text-zinc-700">{t.error || '—'}</td>
                      </tr>
                    ))
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
