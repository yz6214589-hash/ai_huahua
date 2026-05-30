import { Loading } from '@/components/Loading'
import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Search, RefreshCcw } from 'lucide-react'

interface Factor {
  key: string
  label: string
  weight: number
  direction: 'up' | 'down'
  desc: string
}

interface StockScore {
  code: string
  name: string
  factors: Record<string, number>
  total_score: number
  rank: number
}

const DEFAULT_FACTORS: Factor[] = [
  { key: 'pe', label: '市盈率（TTM）', weight: 15, direction: 'down', desc: '越低估值越合理' },
  { key: 'pb', label: '市净率（MRQ）', weight: 10, direction: 'down', desc: '越低资产质量越好' },
  { key: 'roe', label: 'ROE', weight: 20, direction: 'up', desc: '越高盈利能力越强' },
  { key: 'gross', label: '毛利率', weight: 10, direction: 'up', desc: '越高定价能力越强' },
  { key: 'rev_growth', label: '营收增速', weight: 15, direction: 'up', desc: '越高成长性越好' },
  { key: 'profit_growth', label: '利润增速', weight: 20, direction: 'up', desc: '越高盈利质量越好' },
  { key: 'debt_ratio', label: '资产负债率', weight: 5, direction: 'down', desc: '越低财务越健康' },
  { key: 'market_cap', label: '市值规模', weight: 5, direction: 'up', desc: '适中规模更具弹性' },
]

export default function StockSelectFactor() {
  const [factors, setFactors] = useState<Factor[]>([...DEFAULT_FACTORS])
  const [activeFactors, setActiveFactors] = useState<Set<string>>(new Set(DEFAULT_FACTORS.map((f) => f.key)))
  const [stocks, setStocks] = useState<StockScore[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggleFactor = (key: string) => {
    setActiveFactors((prev) => {
      const next = new Set(prev)
      if (next.has(key)) { if (next.size > 1) next.delete(key) }
      else next.add(key)
      return next
    })
  }

  const loadScores = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const activeFactorList = factors.filter((f) => activeFactors.has(f.key))
      const body = {
        factors: activeFactorList.map((f) => ({
          key: f.key,
          weight: f.weight,
          direction: f.direction,
        })),
      }
      const r = await postJson<{ items: StockScore[]; total: number }>('/api/v1/stock-select/score', body)
      setStocks((r.items || []).sort((a, b) => b.total_score - a.total_score))
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setStocks([])
    } finally {
      setLoading(false)
    }
  }, [factors, activeFactors])

  useEffect(() => {
    loadScores()
  }, [])

  const sorted = [...stocks].sort((a, b) => b.total_score - a.total_score)
  const topScore = sorted[0]?.total_score || 1

  const updateFactorWeight = (key: string, weight: number) => {
    setFactors((prev) => prev.map((f) => (f.key === key ? { ...f, weight: Math.max(1, Math.min(100, weight)) } : f)))
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="因子权重配置" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {factors.map((f) => {
              const active = activeFactors.has(f.key)
              const totalWeight = Array.from(activeFactors).reduce((sum, k) => sum + (factors.find((x) => x.key === k)?.weight || 0), 0)
              return (
                <div
                  key={f.key}
                  className={`rounded-lg border p-3 transition ${
                    active ? 'border-blue-300 bg-blue-50' : 'border-zinc-100 bg-zinc-50 opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between" onClick={() => toggleFactor(f.key)}>
                    <span className="text-sm font-medium text-zinc-900">{f.label}</span>
                    <span className={`cursor-pointer rounded-full px-2 py-0.5 text-xs font-medium ${
                      active ? 'bg-blue-200 text-blue-800' : 'bg-zinc-200 text-zinc-500'
                    }`}>
                      {active ? `×${f.weight}%` : '停用'}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {f.desc} · {f.direction === 'up' ? '↑ 越高越好' : '↓ 越低越好'}
                  </div>
                  {active && (
                    <div className="mt-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min="1"
                          max="50"
                          value={f.weight}
                          onChange={(e) => updateFactorWeight(f.key, Number(e.target.value))}
                          className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-blue-100 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500"
                        />
                        <span className="w-8 text-right text-xs text-zinc-500">{f.weight}%</span>
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{ width: `${(f.weight / Math.max(totalWeight, 1)) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="mt-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span>有效权重：{Array.from(activeFactors).reduce((s, k) => s + (factors.find((f) => f.key === k)?.weight || 0), 0)}%</span>
            </div>
            <button
              onClick={loadScores}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              重新评分
            </button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`多因子评分排名（${sorted.length} 只）`} />
        <CardBody className="p-0">
          {loading && sorted.length === 0 ? (
            <Loading className="py-8" />
          ) : error && sorted.length === 0 ? (
            <div className="flex flex-col items-center px-4 py-8">
              <p className="text-sm text-red-600">{error}</p>
              <button
                onClick={loadScores}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                <RefreshCcw className="h-3.5 w-3.5" />
                重新加载
              </button>
            </div>
          ) : sorted.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">暂无评分数据</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2 w-8">#</th>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2 text-center">综合评分</th>
                    {factors.filter((f) => activeFactors.has(f.key)).map((f) => (
                      <th key={f.key} className="px-3 py-2 text-right">{f.label}</th>
                    ))}
                    <th className="px-3 py-2">因子贡献</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((s, i) => {
                    const pct = topScore > 0 ? (s.total_score / topScore) * 100 : 0
                    const activeFactorKeys = factors.filter((f) => activeFactors.has(f.key)).map((f) => f.key)
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
                              <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: pct >= 80 ? '#4ade80' : pct >= 50 ? '#fbbf24' : '#d1d5db' }} />
                            </div>
                            <span className="text-sm font-bold text-zinc-900">{s.total_score.toFixed(1)}</span>
                          </div>
                        </td>
                        {activeFactorKeys.map((key) => {
                          const val = s.factors[key]
                          const factorDef = factors.find((f) => f.key === key)
                          const isUp = factorDef?.direction === 'up'
                          const displayVal = val !== undefined ? val : 0
                          return (
                            <td key={key} className={`px-3 py-2 text-right ${isUp && displayVal > 0 ? 'text-red-600 font-medium' : displayVal < 0 ? 'text-green-600' : 'text-zinc-700'}`}>
                              {typeof displayVal === 'number' ? displayVal.toFixed(1) : displayVal}
                            </td>
                          )
                        })}
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            {activeFactorKeys.map((key) => (
                              <span key={key} className="h-1.5 w-6 rounded-full bg-blue-400" />
                            ))}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}