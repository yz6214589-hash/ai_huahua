import { useState } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowUp, ArrowDown } from 'lucide-react'

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

const MOCK: Position[] = [
  { code: '600519.SH', name: '贵州茅台', qty: 200, avgCost: 1680.5, currentPrice: 1852.3, marketValue: 370460, profitLoss: 34360, profitPct: 10.24, weight: 25.1, sector: '白酒', account: '实盘' },
  { code: '300750.SZ', name: '宁德时代', qty: 500, avgCost: 268.4, currentPrice: 295.8, marketValue: 147900, profitLoss: 13700, profitPct: 10.22, weight: 10.0, sector: '新能源', account: '实盘' },
  { code: '000858.SZ', name: '五粮液', qty: 300, avgCost: 142.8, currentPrice: 158.2, marketValue: 47460, profitLoss: 4620, profitPct: 10.79, weight: 3.2, sector: '白酒', account: '实盘' },
  { code: '688256.SH', name: '寒武纪', qty: 800, avgCost: 82.5, currentPrice: 128.5, marketValue: 102800, profitLoss: 36800, profitPct: 55.76, weight: 7.0, sector: 'AI芯片', account: '实盘' },
  { code: '600519.SH', name: '贵州茅台', qty: 100, avgCost: 1700.0, currentPrice: 1852.3, marketValue: 185230, profitLoss: 15230, profitPct: 8.96, weight: 12.5, sector: '白酒', account: '模拟盘' },
  { code: '002594.SZ', name: '比亚迪', qty: 500, avgCost: 198.0, currentPrice: 202.0, marketValue: 101000, profitLoss: 2000, profitPct: 2.02, weight: 6.8, sector: '新能源', account: '模拟盘' },
  { code: '002415.SZ', name: '海康威视', qty: 1200, avgCost: 38.6, currentPrice: 42.5, marketValue: 51000, profitLoss: 4680, profitPct: 10.1, weight: 3.5, sector: 'AI安防', account: '实盘' },
  { code: '600036.SH', name: '招商银行', qty: 2000, avgCost: 35.2, currentPrice: 38.2, marketValue: 76400, profitLoss: 6000, profitPct: 8.52, weight: 5.2, sector: '银行', account: '实盘' },
]

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

  const totalMarket = MOCK.reduce((s, p) => s + p.marketValue, 0)
  const totalPL = MOCK.reduce((s, p) => s + p.profitLoss, 0)
  const totalPLPct = (totalPL / (totalMarket - totalPL) * 100)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{MOCK.length}</div>
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
          <div className="text-2xl font-bold text-zinc-900">{MOCK.reduce((s, p) => s + p.qty * p.avgCost, 0).toLocaleString()}</div>
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
                {MOCK.map((p) => (
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
