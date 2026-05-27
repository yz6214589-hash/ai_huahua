import { useState, useEffect, useCallback } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowUp, ArrowDown, AlertTriangle, RefreshCcw } from 'lucide-react'

interface Position {
  code: string
  name: string
  qty: number
  avgCost: number
  currentPrice: number
  marketValue: number
  profitLoss: number
  profitPct: number
  weight: number
  sector: string
  account: string
}

function PlCell({ v, pct }: { v: number; pct: number }) {
  const up = v >= 0
  const cls = up ? 'text-red-600' : 'text-green-600'
  return (
    <div className="text-right">
      <div className={`flex items-center justify-end gap-0.5 font-semibold ${cls}`}>
        {up ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
        {up ? '+' : ''}{v.toLocaleString()}元
      </div>
      <div className={`text-xs ${cls}`}>
        {up ? '+' : ''}{pct.toFixed(2)}%
      </div>
    </div>
  )
}

export default function ExecutionPositions() {
  const [account, setAccount] = useState('all')
  const [positions, setPositions] = useState<Position[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchJson<{ positions: Position[]; total: number }>('/api/v1/execution/positions')
      setPositions(data.positions || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setPositions([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const totalMarket = positions.reduce((s, p) => s + p.marketValue, 0)
  const totalPL = positions.reduce((s, p) => s + p.profitLoss, 0)
  const totalPLPct = totalMarket - totalPL > 0 ? (totalPL / (totalMarket - totalPL) * 100) : 0
  const totalCost = positions.reduce((s, p) => s + p.qty * p.avgCost, 0)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-zinc-400">
        <RefreshCcw className="mr-2 h-5 w-5 animate-spin" />
        <span>加载中...</span>
      </div>
    )
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

  if (positions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <AlertTriangle className="mb-3 h-10 w-10 text-zinc-300" />
        <p className="text-sm text-zinc-500">暂无持仓数据</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{positions.length}</div>
          <div className="mt-1 text-xs text-zinc-500">持仓股票</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{totalMarket.toLocaleString()}</div>
          <div className="mt-1 text-xs text-zinc-500">总市值（元）</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className={`text-2xl font-bold ${totalPL >= 0 ? 'text-red-600' : 'text-green-600'}`}>
            {totalPL >= 0 ? '+' : ''}{totalPL.toLocaleString()}
          </div>
          <div className={`mt-1 text-xs ${totalPL >= 0 ? 'text-red-500' : 'text-green-500'}`}>
            浮动盈亏（{totalPLPct >= 0 ? '+' : ''}{totalPLPct.toFixed(2)}%）
          </div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{totalCost.toLocaleString()}</div>
          <div className="mt-1 text-xs text-zinc-500">成本（元）</div>
        </div>
      </div>

      <Card>
        <CardHeader><h3 className="text-lg font-semibold">持仓明细</h3></CardHeader>
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2">股票</th>
                  <th className="px-4 py-2">账户</th>
                  <th className="px-4 py-2 text-right">持仓量</th>
                  <th className="px-4 py-2 text-right">持仓市值</th>
                  <th className="px-4 py-2 text-right">持仓均价</th>
                  <th className="px-4 py-2 text-right">当前价</th>
                  <th className="px-4 py-2 text-right">浮动盈亏</th>
                  <th className="px-4 py-2 text-right">权重</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                    <td className="px-4 py-2">
                      <div className="text-sm font-medium text-zinc-900">{p.code}</div>
                      <div className="text-xs text-zinc-500">{p.name}</div>
                    </td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        p.account === '实盘' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                      }`}>
                        {p.account}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-zinc-700">{p.qty.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right font-medium text-zinc-900">{p.marketValue.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right text-zinc-700">{p.avgCost.toFixed(2)}</td>
                    <td className={`px-4 py-2 text-right font-semibold ${p.currentPrice >= p.avgCost ? 'text-red-600' : 'text-green-600'}`}>
                      {p.currentPrice.toFixed(2)}
                    </td>
                    <td className="px-4 py-2"><PlCell v={p.profitLoss} pct={p.profitPct} /></td>
                    <td className="px-4 py-2 text-right text-zinc-500">{p.weight.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}