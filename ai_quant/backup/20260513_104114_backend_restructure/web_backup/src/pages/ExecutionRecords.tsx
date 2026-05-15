import { useState } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCcw } from 'lucide-react'

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
  remark?: string
}

const MOCK: TradeRecord[] = [
  { id: 'T001', timestamp: '2024-12-16 14:32:15', symbol: '600519.SH', name: '贵州茅台', side: 'buy', qty: 100, price: 1852.3, amount: 185230, strategy: 'TWAP', status: 'filled' },
  { id: 'T002', timestamp: '2024-12-16 14:28:05', symbol: '300750.SZ', name: '宁德时代', side: 'buy', qty: 200, price: 295.8, amount: 59160, strategy: 'VWAP', status: 'filled' },
  { id: 'T003', timestamp: '2024-12-16 11:05:42', symbol: '688256.SH', name: '寒武纪', side: 'buy', qty: 300, price: 128.5, amount: 38550, strategy: 'TWAP', status: 'filled' },
  { id: 'T004', timestamp: '2024-12-16 10:52:18', symbol: '002415.SZ', name: '海康威视', side: 'buy', qty: 500, price: 42.5, amount: 21250, strategy: 'RL', status: 'partial', remark: '部分成交，剩余 200 股' },
  { id: 'T005', timestamp: '2024-12-16 09:45:30', symbol: '000858.SZ', name: '五粮液', side: 'buy', qty: 150, price: 158.2, amount: 23730, strategy: 'TWAP', status: 'filled' },
  { id: 'T006', timestamp: '2024-12-15 15:10:05', symbol: '600036.SH', name: '招商银行', side: 'sell', qty: 1000, price: 38.2, amount: 38200, strategy: 'VWAP', status: 'filled' },
  { id: 'T007', timestamp: '2024-12-15 13:20:00', symbol: '002466.SZ', name: '天齐锂业', side: 'buy', qty: 200, price: 68.4, amount: 13680, strategy: 'TWAP', status: 'rejected', remark: '风控拒绝：超过单笔限额' },
  { id: 'T008', timestamp: '2024-12-15 10:30:15', symbol: '002475.SZ', name: '立讯精密', side: 'sell', qty: 300, price: 44.8, amount: 13440, strategy: 'RL', status: 'cancelled', remark: '用户取消' },
]

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
  const [filterSide, setFilterSide] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterCode, setFilterCode] = useState('')

  const filtered = MOCK.filter((r) => {
    if (filterSide !== 'all' && r.side !== filterSide) return false
    if (filterStatus !== 'all' && r.status !== filterStatus) return false
    if (filterCode && !r.symbol.includes(filterCode) && !r.name.includes(filterCode)) return false
    return true
  })

  const totalBuy = filtered.filter((r) => r.side === 'buy').reduce((s, r) => s + r.amount, 0)
  const totalSell = filtered.filter((r) => r.side === 'sell').reduce((s, r) => s + r.amount, 0)

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
        <input
          value={filterCode}
          onChange={(e) => setFilterCode(e.target.value)}
          placeholder="搜索股票代码或名称"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400"
        />
        <div className="ml-auto text-xs text-zinc-500">符合条件：{filtered.length} 笔</div>
      </div>

      <Card>
        <CardHeader title="交易明细" />
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2">时间</th>
                  <th className="px-4 py-2">股票</th>
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
                  <tr><td className="px-4 py-12 text-center text-zinc-500" colSpan={9}>暂无交易记录</td></tr>
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
