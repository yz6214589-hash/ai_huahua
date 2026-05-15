import { useState } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { ArrowUp, ArrowDown } from 'lucide-react'

interface UnusualStock {
  code: string
  name: string
  changePercent: number
  volumeRatio: number
  turnoverRate: number
  amplitude: number
  change5d: number
  change20d: number
  reason: string
  sector: string
  alertType: 'volume' | 'amplitude' | 'turnover' | 'price'
}

const MOCK: UnusualStock[] = [
  { code: '000002.SZ', name: '万科A', changePercent: 9.82, volumeRatio: 4.2, turnoverRate: 8.5, amplitude: 12.4, change5d: 18.2, change20d: 32.1, reason: '房地产政策松动预期', sector: '房地产', alertType: 'volume' },
  { code: '300750.SZ', name: '宁德时代', changePercent: 5.41, volumeRatio: 3.1, turnoverRate: 4.2, amplitude: 7.8, change5d: 12.4, change20d: 25.6, reason: '新能源板块集体走强', sector: '新能源', alertType: 'amplitude' },
  { code: '002594.SZ', name: '比亚迪', changePercent: -3.28, volumeRatio: 3.8, turnoverRate: 6.1, amplitude: 9.2, change5d: -8.5, change20d: -15.2, reason: '汽车价格战担忧', sector: '汽车整车', alertType: 'volume' },
  { code: '688041.SH', name: '寒武纪', changePercent: 15.82, volumeRatio: 5.6, turnoverRate: 22.4, amplitude: 18.5, change5d: 45.2, change20d: 82.1, reason: 'AI算力需求持续爆发', sector: '人工智能', alertType: 'turnover' },
  { code: '600519.SH', name: '贵州茅台', changePercent: 2.14, volumeRatio: 1.8, turnoverRate: 0.5, amplitude: 3.2, change5d: 4.2, change20d: 8.5, reason: '消费板块估值修复', sector: '白酒', alertType: 'price' },
  { code: '601318.SH', name: '中国平安', changePercent: -1.85, volumeRatio: 2.4, turnoverRate: 1.2, amplitude: 4.1, change5d: -3.2, change20d: 2.1, reason: '保险行业保费增速放缓', sector: '保险', alertType: 'volume' },
  { code: '000001.SZ', name: '平安银行', changePercent: 4.52, volumeRatio: 3.5, turnoverRate: 3.8, amplitude: 6.2, change5d: 9.8, change20d: 15.4, reason: '银行板块估值洼地', sector: '银行', alertType: 'amplitude' },
  { code: '002475.SZ', name: '立讯精密', changePercent: 7.24, volumeRatio: 4.1, turnoverRate: 9.2, amplitude: 11.5, change5d: 22.8, change20d: 38.5, reason: '苹果产业链景气度提升', sector: '消费电子', alertType: 'turnover' },
]

const ALERT_LABELS: Record<UnusualStock['alertType'], string> = {
  volume: '量比异动', amplitude: '振幅异动', turnover: '换手率异动', price: '价格异动',
}

function ChangeCell({ v, unit = '%' }: { v: number; unit?: string }) {
  const up = v > 0
  const cls = up ? 'text-red-600' : 'text-green-600'
  return (
    <span className={`inline-flex items-center gap-0.5 font-medium ${cls}`}>
      {up ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
      {up ? '+' : ''}{v.toFixed(2)}{unit}
    </span>
  )
}

export default function OpportunityUnusual() {
  const [alertType, setAlertType] = useState<UnusualStock['alertType'] | 'all'>('all')
  const [sortKey, setSortKey] = useState<keyof UnusualStock>('volumeRatio')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const filtered = MOCK.filter((s) => alertType === 'all' || s.alertType === alertType)
  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey] as number
    const bv = b[sortKey] as number
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const handleSort = (key: keyof UnusualStock) => {
    if (sortKey === key) setSortDir((d) => d === 'desc' ? 'asc' : 'desc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const SortTh = ({ label, k }: { label: string; k: keyof UnusualStock }) => (
    <th
      className="cursor-pointer px-3 py-2 text-right hover:text-zinc-900"
      onClick={() => handleSort(k)}
    >
      {label} {sortKey === k ? (sortDir === 'desc' ? '↓' : '↑') : ''}
    </th>
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {(['all', 'volume', 'amplitude', 'turnover', 'price'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setAlertType(t)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              alertType === t
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'
            }`}
          >
            {t === 'all' ? '全部异动' : ALERT_LABELS[t as UnusualStock['alertType']]}
          </button>
        ))}
        <div className="ml-auto text-sm text-zinc-500">符合条件：<span className="font-semibold text-zinc-900">{sorted.length}</span> 只</div>
      </div>

      <Card>
        <CardHeader title="异动股票列表" />
        <CardBody className="p-0">
          {sorted.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">暂无异动数据</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">异动类型</th>
                    <th className="px-3 py-2">所属板块</th>
                    <SortTh label="今日涨跌%" k="changePercent" />
                    <SortTh label="量比" k="volumeRatio" />
                    <SortTh label="换手率%" k="turnoverRate" />
                    <SortTh label="振幅%" k="amplitude" />
                    <SortTh label="5日涨跌%" k="change5d" />
                    <SortTh label="20日涨跌%" k="change20d" />
                    <th className="px-3 py-2">异动原因</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((s) => (
                    <tr key={s.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                      <td className="px-3 py-2">
                        <div className="text-sm font-medium text-zinc-900">{s.code}</div>
                        <div className="text-xs text-zinc-500">{s.name}</div>
                      </td>
                      <td className="px-3 py-2">
                        <Badge tone={
                          s.alertType === 'volume' ? 'blue' :
                          s.alertType === 'amplitude' ? 'amber' :
                          s.alertType === 'turnover' ? 'red' : 'green'
                        }>{ALERT_LABELS[s.alertType]}</Badge>
                      </td>
                      <td className="px-3 py-2"><Badge tone="zinc">{s.sector}</Badge></td>
                      <td className="px-3 py-2 text-right"><ChangeCell v={s.changePercent} /></td>
                      <td className={`px-3 py-2 text-right font-medium ${s.volumeRatio > 3 ? 'text-red-600' : 'text-zinc-700'}`}>
                        {s.volumeRatio.toFixed(1)}x
                      </td>
                      <td className={`px-3 py-2 text-right ${s.turnoverRate > 10 ? 'text-red-600 font-medium' : 'text-zinc-700'}`}>
                        {s.turnoverRate.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right text-zinc-700">{s.amplitude.toFixed(2)}%</td>
                      <td className="px-3 py-2 text-right"><ChangeCell v={s.change5d} /></td>
                      <td className="px-3 py-2 text-right"><ChangeCell v={s.change20d} /></td>
                      <td className="px-3 py-2 max-w-48 text-xs text-zinc-600">{s.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
