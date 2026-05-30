import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { AlertTriangle, RefreshCcw, ArrowRight, TrendingUp } from 'lucide-react'

interface TradeRecord {
  id: string
  timestamp: string
  symbol: string
  name: string
  side: 'buy' | 'sell'
  qty: number
  price: number
  amount: number
  strategy: string
  status: 'filled' | 'partial' | 'cancelled' | 'rejected'
  account: '实盘' | '模拟盘'
  remark?: string
}

const STATUS_MAP: Record<string, { label: string; tone: 'green' | 'amber' | 'red' | 'blue' | 'zinc' }> = {
  filled: { label: '已成交', tone: 'green' },
  partial: { label: '部分成交', tone: 'amber' },
  cancelled: { label: '已取消', tone: 'zinc' },
  rejected: { label: '已拒绝', tone: 'red' },
}

function fmt(v: string) {
  if (!v) return '—'
  return v.length > 19 ? v.slice(0, 19).replace('T', ' ') : v
}

export default function ExecutionRecords() {
  const [records, setRecords] = useState<TradeRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterSide, setFilterSide] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterAccount, setFilterAccount] = useState<string>('all')
  const [filterCode, setFilterCode] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchJson<{ records: TradeRecord[]; total: number }>('/api/v1/execution/records')
      setRecords(data.records || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setRecords([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const filtered = records.filter((r) => {
    if (filterSide !== 'all' && r.side !== filterSide) return false
    if (filterStatus !== 'all' && r.status !== filterStatus) return false
    if (filterAccount !== 'all' && r.account !== filterAccount) return false
    if (filterCode && !r.symbol.includes(filterCode) && !r.name.includes(filterCode)) return false
    return true
  })

  const totalBuy = filtered.filter((r) => r.side === 'buy').reduce((s, r) => s + r.amount, 0)
  const totalSell = filtered.filter((r) => r.side === 'sell').reduce((s, r) => s + r.amount, 0)

  if (loading) {
    return <Loading className="py-20" />
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <AlertTriangle className="mb-3 h-10 w-10 text-zinc-300" />
        <p className="text-sm text-zinc-500">{error}</p>
        <button
          onClick={loadData}
          className="mt-3 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
        >
          重新加载
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{filtered.length}</div>
          <div className="mt-1 text-xs text-zinc-500">总交易笔数</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-red-600">{totalBuy.toLocaleString()}</div>
          <div className="mt-1 text-xs text-zinc-500">买入总额（元）</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-green-600">{totalSell.toLocaleString()}</div>
          <div className="mt-1 text-xs text-zinc-500">卖出总额（元）</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className={`text-2xl font-bold ${totalBuy - totalSell >= 0 ? 'text-red-600' : 'text-green-600'}`}>
            {totalBuy - totalSell >= 0 ? '+' : ''}{(totalBuy - totalSell).toLocaleString()}
          </div>
          <div className="mt-1 text-xs text-zinc-500">净买入（元）</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(['all', 'buy', 'sell'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilterSide(s)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              filterSide === s ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'
            }`}
          >
            {s === 'all' ? '全部方向' : s === 'buy' ? '仅买入' : '仅卖出'}
          </button>
        ))}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 outline-none focus:border-zinc-400"
        >
          <option value="all">全部状态</option>
          <option value="filled">已成交</option>
          <option value="partial">部分成交</option>
          <option value="cancelled">已取消</option>
          <option value="rejected">已拒绝</option>
        </select>
        <select
          value={filterAccount}
          onChange={(e) => setFilterAccount(e.target.value)}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 outline-none focus:border-zinc-400"
        >
          <option value="all">全部账户</option>
          <option value="实盘">实盘</option>
          <option value="模拟盘">模拟盘</option>
        </select>
        <input
          value={filterCode}
          onChange={(e) => setFilterCode(e.target.value)}
          placeholder="搜索股票代码或名称"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400"
        />
        <div className="ml-auto text-xs text-zinc-500">符合条件：{filtered.length} 笔</div>
      </div>

      <Card>
        <CardHeader><h3 className="text-lg font-semibold">交易明细</h3></CardHeader>
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2">时间</th>
                  <th className="px-4 py-2">股票</th>
                  <th className="px-4 py-2">账户</th>
                  <th className="px-4 py-2">方向</th>
                  <th className="px-4 py-2 text-right">数量</th>
                  <th className="px-4 py-2 text-right">价格</th>
                  <th className="px-4 py-2 text-right">金额</th>
                  <th className="px-4 py-2">策略</th>
                  <th className="px-4 py-2">状态</th>
                  <th className="px-4 py-2">备注</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td className="px-4 py-12 text-center text-zinc-500" colSpan={10}>暂无交易记录</td></tr>
                ) : filtered.map((r) => {
                  const st = STATUS_MAP[r.status] || { label: r.status, tone: 'zinc' as const }
                  return (
                    <tr key={r.id} className="border-t border-zinc-100 hover:bg-zinc-50">
                      <td className="px-4 py-2 text-xs text-zinc-500">{fmt(r.timestamp)}</td>
                      <td className="px-4 py-2">
                        <div className="text-sm font-medium text-zinc-900">{r.symbol}</div>
                        <div className="text-xs text-zinc-500">{r.name}</div>
                      </td>
                      <td className="px-4 py-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          r.account === '实盘' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                        }`}>
                          {r.account}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <Badge tone={r.side === 'buy' ? 'green' : 'red'}>{r.side === 'buy' ? '买入' : '卖出'}</Badge>
                      </td>
                      <td className="px-4 py-2 text-right text-zinc-700">{r.qty.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right text-zinc-700">{r.price.toFixed(2)}</td>
                      <td className={`px-4 py-2 text-right font-semibold ${r.side === 'buy' ? 'text-red-600' : 'text-green-600'}`}>
                        {r.side === 'buy' ? '-' : '+'}{r.amount.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-xs text-zinc-500">{r.strategy}</td>
                      <td className="px-4 py-2"><Badge tone={st.tone}>{st.label}</Badge></td>
                      <td className="px-4 py-2 max-w-48 text-xs text-zinc-500">{r.remark || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}