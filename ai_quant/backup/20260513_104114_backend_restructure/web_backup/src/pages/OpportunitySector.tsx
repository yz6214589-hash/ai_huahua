import { useState } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowUp, ArrowDown } from 'lucide-react'

interface Sector {
  name: string
  changePercent: number
  change3d: number
  mainFlow: number
  amount: number
  topStocks: { code: string; name: string; change: number }[]
  hotRank: number
}

const MOCK_SECTORS: Sector[] = [
  { name: '人工智能', changePercent: 4.82, change3d: 12.5, mainFlow: 158.2, amount: 2850, topStocks: [
    { code: '688256.SH', name: '寒武纪', change: 15.82 },
    { code: '002415.SZ', name: '海康威视', change: 8.45 },
    { code: '688041.SH', name: '寒武纪', change: 15.82 },
  ], hotRank: 1 },
  { name: '新能源', changePercent: 3.21, change3d: 8.4, mainFlow: 92.5, amount: 1680, topStocks: [
    { code: '300750.SZ', name: '宁德时代', change: 5.41 },
    { code: '002466.SZ', name: '天齐锂业', change: 6.28 },
  ], hotRank: 2 },
  { name: '半导体', changePercent: 2.58, change3d: 6.2, mainFlow: 68.4, amount: 1240, topStocks: [
    { code: '688981.SH', name: '中芯国际', change: 4.12 },
  ], hotRank: 3 },
  { name: '白酒', changePercent: 1.85, change3d: 3.2, mainFlow: 28.6, amount: 620, topStocks: [
    { code: '600519.SH', name: '贵州茅台', change: 2.14 },
    { code: '000858.SZ', name: '五粮液', change: 1.42 },
  ], hotRank: 4 },
  { name: '房地产', changePercent: -2.14, change3d: -5.8, mainFlow: -45.2, amount: 480, topStocks: [
    { code: '000002.SZ', name: '万科A', change: -3.85 },
  ], hotRank: 5 },
  { name: '银行', changePercent: -0.85, change3d: -1.2, mainFlow: -18.5, amount: 320, topStocks: [
    { code: '600036.SH', name: '招商银行', change: -1.24 },
  ], hotRank: 6 },
]

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

export default function OpportunitySector() {
  const sorted = [...MOCK_SECTORS].sort((a, b) => b.mainFlow - a.mainFlow)
  const totalUp = MOCK_SECTORS.filter((s) => s.changePercent > 0).length
  const totalDown = MOCK_SECTORS.length - totalUp

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-red-600">{totalUp}</div>
          <div className="mt-1 text-xs text-zinc-500">上涨板块</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-zinc-900">{MOCK_SECTORS.length}</div>
          <div className="mt-1 text-xs text-zinc-500">监测板块</div>
        </div>
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
          <div className="text-2xl font-bold text-green-600">{totalDown}</div>
          <div className="mt-1 text-xs text-zinc-500">下跌板块</div>
        </div>
      </div>

      <Card>
        <CardHeader title="板块轮动排名（按主力净流入排序）" />
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
