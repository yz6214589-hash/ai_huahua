import { Loading } from '@/components/Loading'
import { useState, useEffect } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowUp, ArrowDown, RefreshCcw } from 'lucide-react'

interface Sector {
  name: string
  changePercent: number
  change3d: number
  mainFlow: number
  amount: number
  topStocks: { code: string; name: string; change: number }[]
  hotRank: number
}

interface SectorApiItem {
  name: string
  change_pct: number
  change_3d: number
  net_inflow: number
  turnover: number
  top_stocks: { code: string; name: string; change_pct: number }[]
  hot_rank: number
}

function HeatCell({ value }: { value: number }) {
  const abs = Math.abs(value)
  const opacity = Math.min(1, abs / 5)
  const bg = value > 0 ? `rgba(239,68,68,${opacity})` : `rgba(34,197,94,${opacity})`
  return (
    <div className="flex items-center justify-center">
      <div className="flex h-10 w-16 items-center justify-center rounded text-xs font-medium" style={{ backgroundColor: bg, color: abs > 2 ? 'white' : 'inherit' }}>
        {value > 0 ? '+' : ''}{value.toFixed(2)}%
      </div>
    </div>
  )
}

function SectorRow({ s }: { s: Sector }) {
  const [expanded, setExpanded] = useState(false)
  const up = s.changePercent > 0
  return (
    <>
      <tr
        className="cursor-pointer border-t border-zinc-100 hover:bg-zinc-50"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-100 text-xs font-bold text-zinc-500">
              {s.hotRank}
            </span>
            <Badge tone={up ? 'red' : 'green'}>{s.name}</Badge>
          </div>
        </td>
        <td className={`px-3 py-2 text-right font-semibold ${up ? 'text-red-600' : 'text-green-600'}`}>
          {up ? '+' : ''}{s.changePercent.toFixed(2)}%
        </td>
        <td className={`px-3 py-2 text-right ${s.change3d > 0 ? 'text-red-600' : 'text-green-600'}`}>
          {s.change3d > 0 ? '+' : ''}{s.change3d.toFixed(2)}%
        </td>
        <td className={`px-3 py-2 text-right font-medium ${s.mainFlow > 0 ? 'text-red-600' : 'text-green-600'}`}>
          {s.mainFlow > 0 ? '+' : ''}{s.mainFlow.toFixed(1)}亿
        </td>
        <td className="px-3 py-2 text-right text-zinc-700">
          {s.amount.toLocaleString()}亿
        </td>
        <td className="px-3 py-2">
          <div className="flex gap-1">
            {s.topStocks.slice(0, 2).map((st) => (
              <span key={st.code} className="rounded border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 text-xs text-zinc-600">
                {st.name}
                <span className={`ml-1 ${st.change > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {st.change > 0 ? '+' : ''}{st.change.toFixed(1)}%
                </span>
              </span>
            ))}
            {s.topStocks.length > 2 && (
              <span className="rounded border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 text-xs text-zinc-400">
                +{s.topStocks.length - 2}
              </span>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="border-t border-zinc-100 bg-zinc-50">
          <td colSpan={6} className="px-4 py-3">
            <div className="text-xs font-medium text-zinc-700">板块内股票</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {s.topStocks.map((st) => (
                <div key={st.code} className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5">
                  <span className="text-xs text-zinc-600">{st.code}</span>
                  <span className="text-xs font-medium text-zinc-900">{st.name}</span>
                  <span className={`text-xs font-medium ${st.change > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {st.change > 0 ? '+' : ''}{st.change.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function mapApiItem(item: SectorApiItem): Sector {
  return {
    name: item.name,
    changePercent: item.change_pct,
    change3d: item.change_3d,
    mainFlow: item.net_inflow,
    amount: item.turnover,
    topStocks: (item.top_stocks || []).map((st) => ({
      code: st.code,
      name: st.name,
      change: st.change_pct,
    })),
    hotRank: item.hot_rank,
  }
}

export default function OpportunitySector() {
  const [sectors, setSectors] = useState<Sector[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSectors = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetchJson<{ items: SectorApiItem[]; total: number }>('/api/v1/intraday/sectors')
      setSectors((r.items || []).map(mapApiItem))
    } catch (e) {
      setError(e instanceof Error ? e.message : '数据加载失败')
      setSectors([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSectors()
  }, [])

  const sorted = [...sectors].sort((a, b) => b.mainFlow - a.mainFlow)
  const totalUp = sectors.filter((s) => s.changePercent > 0).length
  const totalDown = sectors.length - totalUp

  if (loading && sectors.length === 0) {
    return <Loading className="py-12" />
  }

  if (error && sectors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
        <p className="text-sm text-zinc-500">{error}</p>
        <button
          onClick={loadSectors}
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-4 py-2 text-xs text-zinc-600 hover:bg-zinc-50"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          重新加载
        </button>
      </div>
    )
  }

  if (sectors.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-zinc-500">
        暂无板块数据
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-red-600">{totalUp}</div>
          <div className="mt-1 text-xs text-zinc-500">上涨板块</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{sectors.length}</div>
          <div className="mt-1 text-xs text-zinc-500">监测板块</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-green-600">{totalDown}</div>
          <div className="mt-1 text-xs text-zinc-500">下跌板块</div>
        </div>
      </div>

      <Card>
        <CardHeader
          title="板块轮动排名（按主力净流入排序）"
          right={
            <button
              onClick={loadSectors}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </button>
          }
        />
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2 text-left">板块</th>
                  <th className="px-3 py-2 text-right">今日涨跌</th>
                  <th className="px-3 py-2 text-right">3日涨跌</th>
                  <th className="px-3 py-2 text-right">主力净流入</th>
                  <th className="px-3 py-2 text-right">成交额</th>
                  <th className="px-3 py-2 text-left">领涨股</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((s) => <SectorRow key={s.name} s={s} />)}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}