import { useState } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'

interface Factor {
  key: string
  label: string
  weight: number
  direction: 'up' | 'down'
  desc: string
}

const FACTORS: Factor[] = [
  { key: 'pe', label: '市盈率（TTM）', weight: 15, direction: 'down', desc: '越低估值越合理' },
  { key: 'pb', label: '市净率（MRQ）', weight: 10, direction: 'down', desc: '越低资产质量越好' },
  { key: 'roe', label: 'ROE', weight: 20, direction: 'up', desc: '越高盈利能力越强' },
  { key: 'gross', label: '毛利率', weight: 10, direction: 'up', desc: '越高定价能力越强' },
  { key: 'rev_growth', label: '营收增速', weight: 15, direction: 'up', desc: '越高成长性越好' },
  { key: 'profit_growth', label: '利润增速', weight: 20, direction: 'up', desc: '越高盈利质量越好' },
  { key: 'debt_ratio', label: '资产负债率', weight: 5, direction: 'down', desc: '越低财务越健康' },
  { key: 'market_cap', label: '市值规模', weight: 5, direction: 'up', desc: '适中规模更具弹性' },
]

const MOCK_STOCKS = [
  { code: '600519.SH', name: '贵州茅台', pe: 28.5, pb: 8.2, roe: 45.2, gross: 91.8, rev_growth: 16.7, profit_growth: 18.8, debt_ratio: 14.2, market_cap: 22000 },
  { code: '300750.SZ', name: '宁德时代', pe: 22.1, pb: 5.8, roe: 24.6, gross: 22.1, rev_growth: 78.1, profit_growth: 92.5, debt_ratio: 58.3, market_cap: 10500 },
  { code: '002594.SZ', name: '比亚迪', pe: 31.2, pb: 6.1, roe: 18.9, gross: 19.8, rev_growth: 42.1, profit_growth: 85.2, debt_ratio: 68.4, market_cap: 8500 },
  { code: '688041.SH', name: '寒武纪', pe: -45.2, pb: 8.4, roe: -12.3, gross: 62.1, rev_growth: 45.8, profit_growth: -15.2, debt_ratio: 18.4, market_cap: 1800 },
  { code: '600036.SH', name: '招商银行', pe: 7.8, pb: 1.2, roe: 16.8, gross: 0, rev_growth: 8.1, profit_growth: 11.4, debt_ratio: 90.2, market_cap: 11000 },
  { code: '000858.SZ', name: '五粮液', pe: 18.2, pb: 4.1, roe: 28.4, gross: 75.4, rev_growth: 12.4, profit_growth: 14.2, debt_ratio: 22.8, market_cap: 6800 },
]

function calcScore(stock: typeof MOCK_STOCKS[0], activeFactors: Set<string>): number {
  let total = 0
  let scored = 0
  for (const f of FACTORS) {
    if (!activeFactors.has(f.key)) continue
    const val = (stock as Record<string, unknown>)[f.key] as number
    if (typeof val !== 'number' || val === 0) continue
    scored += f.weight
    if (f.direction === 'up') total += f.weight
    else total += f.weight * 0.5
  }
  return scored > 0 ? (total / scored) * 100 : 0
}

export default function StockSelectFactor() {
  const [activeFactors, setActiveFactors] = useState<Set<string>>(new Set(FACTORS.map((f) => f.key)))

  const toggleFactor = (key: string) => {
    setActiveFactors((prev) => {
      const next = new Set(prev)
      if (next.has(key)) { if (next.size > 1) next.delete(key) }
      else next.add(key)
      return next
    })
  }

  const scored = MOCK_STOCKS
    .map((s) => ({ ...s, score: calcScore(s, activeFactors) }))
    .sort((a, b) => b.score - a.score)

  const topScore = scored[0]?.score || 1

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="因子权重配置" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {FACTORS.map((f) => {
              const active = activeFactors.has(f.key)
              const totalWeight = Array.from(activeFactors).reduce((sum, k) => sum + (FACTORS.find((x) => x.key === k)?.weight || 0), 0)
              return (
                <div
                  key={f.key}
                  onClick={() => toggleFactor(f.key)}
                  className={`cursor-pointer rounded-lg border p-3 transition ${
                    active ? 'border-blue-300 bg-blue-50' : 'border-zinc-100 bg-zinc-50 opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-zinc-900">{f.label}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      active ? 'bg-blue-200 text-blue-800' : 'bg-zinc-200 text-zinc-500'
                    }`}>
                      {active ? `×${f.weight}%` : '停用'}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {f.desc} · {f.direction === 'up' ? '↑ 越高越好' : '↓ 越低越好'}
                  </div>
                  {active && (
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
                      <div
                        className="h-full rounded-full bg-blue-500"
                        style={{ width: `${(f.weight / totalWeight) * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
            <span>有效权重：{Array.from(activeFactors).reduce((s, k) => s + (FACTORS.find((f) => f.key === k)?.weight || 0), 0)}%</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`多因子评分排名（${scored.length} 只）`} />
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2 w-8">#</th>
                  <th className="px-3 py-2">股票</th>
                  <th className="px-3 py-2 text-center">综合评分</th>
                  <th className="px-3 py-2 text-right">市盈率</th>
                  <th className="px-3 py-2 text-right">ROE(%)</th>
                  <th className="px-3 py-2 text-right">毛利率(%)</th>
                  <th className="px-3 py-2 text-right">营收增(%)</th>
                  <th className="px-3 py-2 text-right">利润增(%)</th>
                  <th className="px-3 py-2">因子贡献</th>
                </tr>
              </thead>
              <tbody>
                {scored.map((s, i) => {
                  const pct = topScore > 0 ? (s.score / topScore) * 100 : 0
                  const tone = pct >= 80 ? 'green' : pct >= 50 ? 'amber' : 'zinc'
                  return (
                    <tr key={s.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                      <td className="px-3 py-2 text-center text-zinc-400">{i + 1}</td>
                      <td className="px-3 py-2">
                        <div className="text-sm font-medium text-zinc-900">{s.code}</div>
                        <div className="text-xs text-zinc-500">{s.name}</div>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 overflow-hidden rounded-full bg-zinc-100">
                            <div className={`h-full rounded-full bg-${tone}-400`} style={{ width: `${pct}%`, backgroundColor: pct >= 80 ? '#4ade80' : pct >= 50 ? '#fbbf24' : '#d1d5db' }} />
                          </div>
                          <span className="text-sm font-bold text-zinc-900">{s.score.toFixed(1)}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right text-zinc-700">{s.pe < 0 ? '亏损' : s.pe.toFixed(1)}</td>
                      <td className={`px-3 py-2 text-right ${s.roe >= 15 ? 'text-red-600 font-medium' : 'text-zinc-700'}`}>{s.roe.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right text-zinc-700">{s.gross.toFixed(1)}</td>
                      <td className={`px-3 py-2 text-right ${s.rev_growth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.rev_growth > 0 ? '+' : ''}{s.rev_growth.toFixed(1)}</td>
                      <td className={`px-3 py-2 text-right ${s.profit_growth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.profit_growth > 0 ? '+' : ''}{s.profit_growth.toFixed(1)}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1">
                          {FACTORS.filter((f) => activeFactors.has(f.key)).map((f) => (
                            <span key={f.key} className="h-1.5 w-6 rounded-full bg-blue-400" />
                          ))}
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
  )
}
