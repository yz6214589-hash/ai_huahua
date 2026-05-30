import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowUp, Flame, AlertTriangle, RefreshCcw } from 'lucide-react'

interface LimitUpStock {
  code: string
  name: string
  boardTime: string
  sealAmount: number
  sealAmountY: number
  consecutiveBoards: number
  floatCap: number
  sector: string
  status: 'limit_up' | 'limit_down' | 'break_limit_up' | 'break_limit_down'
  firstBoardTime: string
}

function fmtY(v: number) {
  if (v >= 10000) return `${(v / 10000).toFixed(1)}亿`
  if (v >= 1000) return `${(v / 1000).toFixed(1)}千万`
  return `${v.toFixed(0)}万`
}

function StatusBadge({ status }: { status: LimitUpStock['status'] }) {
  const map: Record<typeof status, { label: string; tone: 'green' | 'red' | 'amber' }> = {
    limit_up: { label: '涨停', tone: 'green' },
    limit_down: { label: '跌停', tone: 'red' },
    break_limit_up: { label: '炸板', tone: 'amber' },
    break_limit_down: { label: '开板（跌）', tone: 'amber' },
  }
  const { label, tone } = map[status]
  return <Badge tone={tone}>{label}</Badge>
}

function BoardTag({ n }: { n: number }) {
  if (n === 0) return <span className="text-xs text-zinc-400">—</span>
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-700">
      <Flame className="h-3 w-3" />
      {n}连板
    </span>
  )
}

export default function OpportunityLimitUp() {
  const [view, setView] = useState<'all' | 'limit_up' | 'break'>('all')
  const [stocks, setStocks] = useState<LimitUpStock[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchJson<LimitUpStock[] | { items: LimitUpStock[] }>('/api/v1/intraday/limit-up')
      if (Array.isArray(data)) {
        setStocks(data)
      } else if (data.items) {
        setStocks(data.items)
      } else {
        setStocks([])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setStocks([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const filtered = stocks.filter((s) => {
    if (view === 'limit_up') return s.status === 'limit_up' || s.status === 'limit_down'
    if (view === 'break') return s.status === 'break_limit_up' || s.status === 'break_limit_down'
    return true
  })

  const limitUps = filtered.filter((s) => s.status === 'limit_up' || s.status === 'limit_down')
  const breaks = filtered.filter((s) => s.status === 'break_limit_up' || s.status === 'break_limit_down')

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

  if (stocks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
        <AlertTriangle className="mb-3 h-10 w-10 text-zinc-300" />
        <p className="text-sm text-zinc-500">暂无涨停数据</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {(['all', 'limit_up', 'break'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setView(t)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              view === t
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'
            }`}
          >
            {t === 'all' ? '全部' : t === 'limit_up' ? '涨停/跌停' : '炸板'}
          </button>
        ))}
      </div>

      {limitUps.length > 0 && view !== 'break' && (
        <Card>
          <CardHeader
            title={`涨停板（${limitUps.filter((s) => s.status === 'limit_up').length} 只）`}
          />
          <CardBody className="p-0">
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">连板</th>
                    <th className="px-3 py-2">板块</th>
                    <th className="px-3 py-2 text-right">涨停时间</th>
                    <th className="px-3 py-2 text-right">封单量</th>
                    <th className="px-3 py-2 text-right">封单金额</th>
                    <th className="px-3 py-2 text-right">流通市值（亿）</th>
                  </tr>
                </thead>
                <tbody>
                  {limitUps.map((s) => (
                    <tr key={s.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <div className="text-sm font-medium text-zinc-900">{s.code}</div>
                        <div className="text-xs text-zinc-500">{s.name}</div>
                      </td>
                      <td className="px-3 py-2"><StatusBadge status={s.status} /></td>
                      <td className="px-3 py-2"><BoardTag n={s.consecutiveBoards} /></td>
                      <td className="px-3 py-2"><Badge tone="zinc">{s.sector}</Badge></td>
                      <td className="px-3 py-2 text-right text-zinc-700">{s.boardTime}</td>
                      <td className={`px-3 py-2 text-right font-medium ${s.sealAmount > 0 ? 'text-zinc-900' : 'text-zinc-400'}`}>
                        {s.sealAmount > 0 ? fmtY(s.sealAmount) : '—'}
                      </td>
                      <td className={`px-3 py-2 text-right font-medium ${s.sealAmountY > 0 ? 'text-red-600' : 'text-zinc-400'}`}>
                        {s.sealAmountY > 0 ? `${s.sealAmountY}千万` : '—'}
                      </td>
                      <td className="px-3 py-2 text-right text-zinc-700">{s.floatCap.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      {breaks.length > 0 && view !== 'limit_up' && (
        <Card>
          <CardHeader title={`炸板（${breaks.length} 只）`} />
          <CardBody className="p-0">
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">板块</th>
                    <th className="px-3 py-2 text-right">流通市值（亿）</th>
                  </tr>
                </thead>
                <tbody>
                  {breaks.map((s) => (
                    <tr key={s.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <div className="text-sm font-medium text-zinc-900">{s.code}</div>
                        <div className="text-xs text-zinc-500">{s.name}</div>
                      </td>
                      <td className="px-3 py-2"><StatusBadge status={s.status} /></td>
                      <td className="px-3 py-2"><Badge tone="zinc">{s.sector}</Badge></td>
                      <td className="px-3 py-2 text-right text-zinc-700">{s.floatCap.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}