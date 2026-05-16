import { useState, useEffect } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Search, Clock, Database, TrendingUp } from 'lucide-react'

interface DataStatus {
  stock_daily: {
    latest_date: string | null
    stock_count: number
    data_count: number
  } | null
  stock_financial: {
    latest_date: string | null
    stock_count: number
    data_count: number
  } | null
  timestamp: string
}

interface FilterDef {
  key: string
  label: string
  type: 'range' | 'select' | 'multiselect' | 'number'
  min?: number
  max?: number
  step?: number
  options?: { value: string; label: string }[]
  defaultMin?: number
  defaultMax?: number
}

const FILTERS: FilterDef[] = [
  { key: 'pe', label: '市盈率（TTM）', type: 'range', min: 0, max: 200, defaultMin: 0, defaultMax: 30 },
  { key: 'pb', label: '市净率（MRQ）', type: 'range', min: 0, max: 20, defaultMin: 0, defaultMax: 10 },
  { key: 'roe', label: 'ROE（%）', type: 'range', min: -50, max: 100, defaultMin: 0, defaultMax: 100 },
  { key: 'gross_margin', label: '毛利率（%）', type: 'range', min: 0, max: 100, defaultMin: 0, defaultMax: 100 },
  { key: 'net_margin', label: '净利率（%）', type: 'range', min: -50, max: 100, defaultMin: 0, defaultMax: 100 },
  { key: 'industry', label: '行业板块', type: 'multiselect', options: [
    { value: 'bank', label: '银行' }, { value: 'insurance', label: '保险' },
    { value: 'securities', label: '证券' }, { value: ' liquor', label: '白酒' },
    { value: 'food', label: '食品饮料' }, { value: 'pharma', label: '医药生物' },
    { value: 'semiconductor', label: '半导体' }, { value: 'new_energy', label: '新能源' },
    { value: 'ai', label: '人工智能' }, { value: 'real_estate', label: '房地产' },
    { value: 'steel', label: '钢铁' }, { value: 'auto', label: '汽车' },
  ]},
  { key: 'market_cap', label: '总市值（亿）', type: 'range', min: 0, max: 50000, defaultMin: 0, defaultMax: 50000 },
  { key: 'rev_growth', label: '营收增速（%）', type: 'range', min: -100, max: 500, defaultMin: -100, defaultMax: 500 },
  { key: 'profit_growth', label: '利润增速（%）', type: 'range', min: -500, max: 1000, defaultMin: -500, defaultMax: 1000 },
  { key: 'debt_ratio', label: '资产负债率（%）', type: 'range', min: 0, max: 100, defaultMin: 0, defaultMax: 80 },
]

const MOCK_RESULTS = [
  { code: '600519.SH', name: '贵州茅台', pe: 28.5, pb: 8.2, roe: 45.2, gross: 91.8, net: 50.9, industry: '白酒', marketCap: 22000, revGrowth: 16.7, profitGrowth: 18.8, debtRatio: 14.2 },
  { code: '000858.SZ', name: '五粮液', pe: 18.2, pb: 4.1, roe: 28.4, gross: 75.4, net: 35.1, industry: '白酒', marketCap: 6800, revGrowth: 12.4, profitGrowth: 14.2, debtRatio: 22.8 },
  { code: '300750.SZ', name: '宁德时代', pe: 22.1, pb: 5.8, roe: 24.6, gross: 22.1, net: 10.9, industry: '新能源', marketCap: 10500, revGrowth: 78.1, profitGrowth: 92.5, debtRatio: 58.3 },
  { code: '601318.SH', name: '中国平安', pe: 8.5, pb: 0.9, roe: 11.2, gross: 0, net: 8.4, industry: '保险', marketCap: 8900, revGrowth: 4.2, profitGrowth: -5.1, debtRatio: 89.1 },
  { code: '000001.SZ', name: '平安银行', pe: 5.2, pb: 0.6, roe: 10.8, gross: 0, net: 28.4, industry: '银行', marketCap: 2400, revGrowth: 6.8, profitGrowth: 8.2, debtRatio: 92.4 },
  { code: '002475.SZ', name: '立讯精密', pe: 24.8, pb: 6.1, roe: 18.9, gross: 19.2, net: 8.1, industry: '消费电子', marketCap: 3200, revGrowth: 35.2, profitGrowth: 28.7, debtRatio: 45.6 },
  { code: '688041.SH', name: '寒武纪', pe: -45.2, pb: 8.4, roe: -12.3, gross: 62.1, net: -28.4, industry: '人工智能', marketCap: 1800, revGrowth: 45.8, profitGrowth: -15.2, debtRatio: 18.4 },
  { code: '600036.SH', name: '招商银行', pe: 7.8, pb: 1.2, roe: 16.8, gross: 0, net: 38.2, industry: '银行', marketCap: 11000, revGrowth: 8.1, profitGrowth: 11.4, debtRatio: 90.2 },
]

interface FilterValues {
  [key: string]: { min: number; max: number; selected: string[] }
}

const initValues = (): FilterValues => {
  const v: FilterValues = {}
  for (const f of FILTERS) {
    if (f.type === 'range') {
      v[f.key] = { min: f.defaultMin ?? f.min ?? 0, max: f.defaultMax ?? f.max ?? 100, selected: [] }
    } else {
      v[f.key] = { min: 0, max: 100, selected: [] }
    }
  }
  return v
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score))
  const cls = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-500' : 'bg-zinc-300'
  return (
    <div className="w-full">
      <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100">
        <div className={`h-full rounded-full transition-all ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-0.5 text-right text-xs text-zinc-500">{score.toFixed(1)}</div>
    </div>
  )
}

function ScoreTag({ score }: { score: number }) {
  const tone = score >= 70 ? 'green' : score >= 40 ? 'amber' : 'zinc'
  return <Badge tone={tone}>{score.toFixed(1)}</Badge>
}

function DataStatusBar({ dataStatus }: { dataStatus: DataStatus | null }) {
  if (!dataStatus) {
    return (
      <div className="mb-4 flex items-center gap-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-zinc-400" />
          <span className="text-sm text-zinc-500">正在加载数据状态...</span>
        </div>
      </div>
    )
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '暂无数据'
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2">
      <div className="flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-blue-500" />
        <span className="text-sm font-medium text-zinc-700">行情数据:</span>
        <span className="text-sm text-zinc-600">
          {formatDate(dataStatus.stock_daily?.latest_date)}
          <span className="ml-1 text-xs text-zinc-400">
            ({dataStatus.stock_daily?.stock_count ?? 0} 只股票)
          </span>
        </span>
      </div>

      <div className="h-4 w-px bg-zinc-300" />

      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-green-500" />
        <span className="text-sm font-medium text-zinc-700">财务数据:</span>
        <span className="text-sm text-zinc-600">
          {formatDate(dataStatus.stock_financial?.latest_date)}
          <span className="ml-1 text-xs text-zinc-400">
            ({dataStatus.stock_financial?.stock_count ?? 0} 只股票)
          </span>
        </span>
      </div>

      <div className="h-4 w-px bg-zinc-300" />

      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-zinc-400" />
        <span className="text-xs text-zinc-400">
          更新于 {dataStatus.timestamp ? new Date(dataStatus.timestamp).toLocaleTimeString('zh-CN') : ''}
        </span>
      </div>
    </div>
  )
}

export default function StockSelectFundamental() {
  const [values, setValues] = useState<FilterValues>(initValues)
  const [showFilters, setShowFilters] = useState(true)
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null)

  useEffect(() => {
    fetchDataStatus()
  }, [])

  const fetchDataStatus = async () => {
    try {
      const response = await fetch('/api/v1/data/status')
      if (response.ok) {
        const data = await response.json()
        setDataStatus(data)
      }
    } catch (error) {
      console.error('获取数据状态失败:', error)
    }
  }

  const toggleFilter = (key: string) => {
    setValues((prev) => {
      const next = { ...prev }
      if (next[key].selected.length > 0) {
        next[key] = { ...next[key], selected: [] }
      } else {
        next[key] = { ...next[key], selected: next[key].selected }
      }
      return next
    })
  }

  const matches = MOCK_RESULTS.filter((s) => {
    for (const f of FILTERS) {
      const v = values[f.key]
      if (f.type === 'range') {
        const val = (s as Record<string, unknown>)[f.key]
        const num = typeof val === 'number' ? val : 0
        if (num < v.min || num > v.max) return false
      } else if (f.type === 'multiselect') {
        if (v.selected.length === 0) continue
        const ind = s.industry
        if (!v.selected.includes(ind)) return false
      }
    }
    return true
  })

  return (
    <div className="space-y-4">
      <DataStatusBar dataStatus={dataStatus} />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-zinc-600">筛选条件</span>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="text-xs text-zinc-500 hover:text-zinc-900"
          >
            {showFilters ? '收起' : '展开'}
          </button>
        </div>
        <div className="text-sm text-zinc-500">符合条件：<span className="font-semibold text-zinc-900">{matches.length}</span> 只</div>
      </div>

      {showFilters && (
        <Card>
          <CardBody>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {FILTERS.map((f) => (
                <div key={f.key} className="rounded-lg border border-zinc-100 bg-zinc-50 p-3">
                  {f.type === 'range' ? (
                    <div>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-xs font-medium text-zinc-700">{f.label}</span>
                        <span className="text-xs text-zinc-500">
                          {values[f.key].min} ~ {values[f.key].max}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min={f.min}
                          max={f.max}
                          step={f.step || 1}
                          value={values[f.key].min}
                          onChange={(e) => setValues((v) => ({
                            ...v, [f.key]: { ...v[f.key], min: Number(e.target.value) }
                          }))}
                          className="flex-1 accent-zinc-900"
                        />
                        <input
                          type="range"
                          min={f.min}
                          max={f.max}
                          step={f.step || 1}
                          value={values[f.key].max}
                          onChange={(e) => setValues((v) => ({
                            ...v, [f.key]: { ...v[f.key], max: Number(e.target.value) }
                          }))}
                          className="flex-1 accent-zinc-900"
                        />
                      </div>
                    </div>
                  ) : f.type === 'multiselect' ? (
                    <div>
                      <div className="mb-2 text-xs font-medium text-zinc-700">{f.label}</div>
                      <div className="flex flex-wrap gap-1">
                        {f.options?.map((opt) => {
                          const sel = values[f.key].selected.includes(opt.value)
                          return (
                            <button
                              key={opt.value}
                              onClick={() => setValues((v) => {
                                const cur = v[f.key].selected
                                const next = sel ? cur.filter((x) => x !== opt.value) : [...cur, opt.value]
                                return { ...v, [f.key]: { ...v[f.key], selected: next } }
                              })}
                              className={`rounded-md border px-2 py-0.5 text-xs transition ${
                                sel ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-100'
                              }`}
                            >
                              {opt.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title={`选股结果（${matches.length} 只）`} />
        <CardBody className="p-0">
          {matches.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">暂无符合条件的股票</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">行业</th>
                    <th className="px-3 py-2 text-right">市盈率</th>
                    <th className="px-3 py-2 text-right">市净率</th>
                    <th className="px-3 py-2 text-right">ROE(%)</th>
                    <th className="px-3 py-2 text-right">毛利率(%)</th>
                    <th className="px-3 py-2 text-right">净利率(%)</th>
                    <th className="px-3 py-2 text-right">市值(亿)</th>
                    <th className="px-3 py-2 text-right">营收增(%)</th>
                    <th className="px-3 py-2 text-right">利润增(%)</th>
                    <th className="px-3 py-2 text-right">负债率(%)</th>
                    <th className="px-3 py-2 text-center">综合评分</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((s) => {
                    const peOk = s.pe > 0 && s.pe <= values['pe'].max
                    const roeOk = s.roe >= values['roe'].min
                    const profitOk = s.profitGrowth >= values['profit_growth'].min
                    const score = Math.round((peOk ? 20 : 0) + (roeOk ? 30 : 0) + (profitOk ? 25 : 0) + (s.gross / 100 * 15) + (s.net / 100 * 10))
                    return (
                      <tr key={s.code} className="border-t border-zinc-100 hover:bg-zinc-50">
                        <td className="px-3 py-2">
                          <div className="text-sm font-medium text-zinc-900">{s.code}</div>
                          <div className="text-xs text-zinc-500">{s.name}</div>
                        </td>
                        <td className="px-3 py-2"><Badge tone="blue">{s.industry}</Badge></td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.pe < 0 ? '亏损' : s.pe.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.pb.toFixed(2)}</td>
                        <td className={`px-3 py-2 text-right ${s.roe >= 15 ? 'text-red-600 font-medium' : 'text-zinc-700'}`}>{s.roe.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.gross.toFixed(1)}</td>
                        <td className={`px-3 py-2 text-right ${s.net >= 20 ? 'text-red-600 font-medium' : 'text-zinc-700'}`}>{s.net.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.marketCap.toLocaleString()}</td>
                        <td className={`px-3 py-2 text-right ${s.revGrowth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.revGrowth > 0 ? '+' : ''}{s.revGrowth.toFixed(1)}</td>
                        <td className={`px-3 py-2 text-right ${s.profitGrowth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.profitGrowth > 0 ? '+' : ''}{s.profitGrowth.toFixed(1)}</td>
                        <td className={`px-3 py-2 text-right ${s.debtRatio > 70 ? 'text-amber-600' : 'text-zinc-700'}`}>{s.debtRatio.toFixed(1)}</td>
                        <td className="px-3 py-2"><ScoreTag score={score} /></td>
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
