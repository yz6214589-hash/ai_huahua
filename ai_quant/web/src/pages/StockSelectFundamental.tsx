import { useState, useEffect, useCallback } from 'react'
import { fetchJson, postJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Search, Clock, Database, TrendingUp, RefreshCw } from 'lucide-react'

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

interface StockResult {
  code: string
  name: string
  sector_level1: string
  sector_level2: string
  pe: number
  pb: number
  roe: number
  gross_margin: number
  net_margin: number
  market_cap: number
  revenue_growth: number
  profit_growth: number
  debt_ratio: number
}

const SW_INDUSTRIES = [
  '农林牧渔', '基础化工', '钢铁', '有色金属', '电子', '家用电器',
  '食品饮料', '纺织服饰', '轻工制造', '医药生物', '公用事业',
  '交通运输', '房地产', '商贸零售', '社会服务', '银行',
  '非银金融', '综合', '建筑材料', '建筑装饰', '电力设备',
  '机械设备', '国防军工', '计算机', '传媒', '通信',
  '煤炭', '石油石化', '环保', '美容护理', '汽车',
]

const FILTER_CONFIG = [
  { key: 'pe_min', label: '市盈率下限', key2: 'pe_max', label2: '上限', unit: '' },
  { key: 'pb_min', label: '市净率下限', key2: 'pb_max', label2: '上限', unit: '' },
  { key: 'roe_min', label: 'ROE下限(%)', key2: 'roe_max', label2: '上限', unit: '%' },
  { key: 'gross_margin_min', label: '毛利率下限(%)', key2: 'gross_margin_max', label2: '上限', unit: '%' },
  { key: 'net_margin_min', label: '净利率下限(%)', key2: 'net_margin_max', label2: '上限', unit: '%' },
  { key: 'market_cap_min', label: '市值下限(亿)', key2: 'market_cap_max', label2: '上限', unit: '亿' },
  { key: 'revenue_growth_min', label: '营收增速下限(%)', key2: 'revenue_growth_max', label2: '上限', unit: '%' },
  { key: 'profit_growth_min', label: '利润增速下限(%)', key2: 'profit_growth_max', label2: '上限', unit: '%' },
  { key: 'debt_ratio_min', label: '负债率下限(%)', key2: 'debt_ratio_max', label2: '上限', unit: '%' },
]

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
  const tone: 'success' | 'warning' | 'default' = score >= 70 ? 'success' : score >= 40 ? 'warning' : 'default'
  return <Badge variant={tone}>{score.toFixed(1)}</Badge>
}

function calcScore(s: StockResult): number {
  let score = 0
  if (s.pe > 0 && s.pe <= 30) score += 20
  if (s.roe >= 15) score += 30
  else if (s.roe >= 10) score += 15
  if (s.profit_growth > 0) score += 25
  score += (s.gross_margin / 100) * 15
  score += (s.net_margin / 100) * 10
  return Math.min(100, Math.round(score))
}

export default function StockSelectFundamental() {
  const [results, setResults] = useState<StockResult[]>([])
  const [loading, setLoading] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null)
  const [showFilters, setShowFilters] = useState(true)

  const [selectedIndustries, setSelectedIndustries] = useState<string[]>([])
  const [filterValues, setFilterValues] = useState<Record<string, { min: string; max: string }>>({})

  useEffect(() => {
    fetchDataStatus()
    doQuery()
  }, [])

  const fetchDataStatus = async () => {
    try {
      const data = await fetchJson<DataStatus>('/api/v1/data/status')
      setDataStatus(data)
    } catch {
      //
    }
  }

  const doQuery = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = { page: 1, page_size: 200 }
      if (selectedIndustries.length > 0) {
        params.industries = selectedIndustries
      }
      for (const [key, val] of Object.entries(filterValues)) {
        if (val.min) params[key + '_min'] = Number(val.min)
        if (val.max) params[key + '_max'] = Number(val.max)
      }
      const data = await postJson<{ items: StockResult[]; total: number }>('/api/v1/stock-select/query', params)
      setResults(data.items || [])
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [selectedIndustries, filterValues])

  const handleUpdateData = async () => {
    setUpdating(true)
    try {
      await postJson('/api/v1/jobs/run', { domain: 'stock_daily', mode: 'full' })
      await postJson('/api/v1/jobs/run', { domain: 'stock_financial', mode: 'full' })
      await fetchDataStatus()
      await doQuery()
    } catch {
      //
    } finally {
      setUpdating(false)
    }
  }

  const toggleIndustry = (ind: string) => {
    setSelectedIndustries(prev =>
      prev.includes(ind) ? prev.filter(x => x !== ind) : [...prev, ind]
    )
  }

  const updateFilter = (key: string, field: 'min' | 'max', value: string) => {
    setFilterValues(prev => ({
      ...prev,
      [key]: { ...(prev[key] || { min: '', max: '' }), [field]: value },
    }))
  }

  const hasFilters = selectedIndustries.length > 0 || Object.values(filterValues).some(v => v.min || v.max)

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
    <div className="space-y-4">
      <div className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-blue-500" />
          <span className="text-sm font-medium text-zinc-700">行情数据:</span>
          <span className="text-sm text-zinc-600">
            {formatDate(dataStatus?.stock_daily?.latest_date)}
            <span className="ml-1 text-xs text-zinc-400">
              ({dataStatus?.stock_daily?.stock_count ?? 0} 只)
            </span>
          </span>
        </div>
        <div className="h-4 w-px bg-zinc-300" />
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium text-zinc-700">财务数据:</span>
          <span className="text-sm text-zinc-600">
            {formatDate(dataStatus?.stock_financial?.latest_date)}
            <span className="ml-1 text-xs text-zinc-400">
              ({dataStatus?.stock_financial?.stock_count ?? 0} 只)
            </span>
          </span>
        </div>
        <div className="h-4 w-px bg-zinc-300" />
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-zinc-400" />
          <span className="text-xs text-zinc-400">
            更新于 {dataStatus?.timestamp ? new Date(dataStatus.timestamp).toLocaleTimeString('zh-CN') : ''}
          </span>
        </div>
        <div className="ml-auto">
          <button
            onClick={handleUpdateData}
            disabled={updating}
            className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${updating ? 'animate-spin' : ''}`} />
            一键更新数据
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-zinc-600">筛选条件</span>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="text-xs text-zinc-500 hover:text-zinc-900"
          >
            {showFilters ? '收起' : '展开'}
          </button>
          {hasFilters && (
            <button
              onClick={() => { setSelectedIndustries([]); setFilterValues({}) }}
              className="text-xs text-red-500 hover:text-red-600"
            >
              清除筛选
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={doQuery}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50"
          >
            <Search className="h-3.5 w-3.5" />
            查询
          </button>
          <span className="text-sm text-zinc-500">结果：<span className="font-semibold text-zinc-900">{results.length}</span> 只</span>
        </div>
      </div>

      {showFilters && (
        <Card>
          <CardBody>
            <div className="mb-4">
              <div className="mb-2 text-xs font-medium text-zinc-700">申万一级行业</div>
              <div className="flex flex-wrap gap-1.5">
                {SW_INDUSTRIES.map(ind => {
                  const sel = selectedIndustries.includes(ind)
                  return (
                    <button
                      key={ind}
                      onClick={() => toggleIndustry(ind)}
                      className={`rounded-md border px-2.5 py-1 text-xs transition ${
                        sel
                          ? 'border-zinc-900 bg-zinc-900 text-white'
                          : 'border-zinc-200 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50'
                      }`}
                    >
                      {ind}
                    </button>
                  )
                })}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {FILTER_CONFIG.map(fc => (
                <div key={fc.key} className="rounded-lg border border-zinc-100 bg-zinc-50 p-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      placeholder={fc.label}
                      value={filterValues[fc.key]?.min ?? ''}
                      onChange={e => updateFilter(fc.key, 'min', e.target.value)}
                      className="w-full rounded border border-zinc-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900"
                    />
                    <span className="text-xs text-zinc-400">~</span>
                    <input
                      type="number"
                      placeholder={fc.label2}
                      value={filterValues[fc.key]?.max ?? ''}
                      onChange={e => updateFilter(fc.key, 'max', e.target.value)}
                      className="w-full rounded border border-zinc-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900"
                    />
                    <span className="text-xs text-zinc-500">{fc.unit}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">{fc.label} ~ {fc.label2}</div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">选股结果（{results.length} 只）</h3>
        </CardHeader>
        <CardBody className="p-0">
          {loading ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">加载中...</div>
          ) : results.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">暂无符合条件的股票，请调整筛选条件</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-3 py-2">股票</th>
                    <th className="px-3 py-2">一级行业</th>
                    <th className="px-3 py-2">二级行业</th>
                    <th className="px-3 py-2 text-right">市盈率</th>
                    <th className="px-3 py-2 text-right">市净率</th>
                    <th className="px-3 py-2 text-right">ROE(%)</th>
                    <th className="px-3 py-2 text-right">毛利率(%)</th>
                    <th className="px-3 py-2 text-right">净利率(%)</th>
                    <th className="px-3 py-2 text-right">市值(亿)</th>
                    <th className="px-3 py-2 text-right">营收增(%)</th>
                    <th className="px-3 py-2 text-right">利润增(%)</th>
                    <th className="px-3 py-2 text-right">负债率(%)</th>
                    <th className="px-3 py-2 text-center">评分</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((s, idx) => {
                    const score = calcScore(s)
                    return (
                      <tr key={`${s.code}-${idx}`} className="border-t border-zinc-100 hover:bg-zinc-50">
                        <td className="px-3 py-2">
                          <div className="text-sm font-medium text-zinc-900">{s.code}</div>
                          <div className="text-xs text-zinc-500">{s.name}</div>
                        </td>
                        <td className="px-3 py-2"><Badge variant="default">{s.sector_level1 || '--'}</Badge></td>
                        <td className="px-3 py-2"><span className="text-xs text-zinc-500">{s.sector_level2 || '--'}</span></td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.pe < 0 ? '亏损' : s.pe.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.pb.toFixed(2)}</td>
                        <td className={`px-3 py-2 text-right ${s.roe >= 15 ? 'text-green-600 font-medium' : 'text-zinc-700'}`}>{s.roe.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.gross_margin.toFixed(1)}</td>
                        <td className={`px-3 py-2 text-right ${s.net_margin >= 20 ? 'text-green-600 font-medium' : 'text-zinc-700'}`}>{s.net_margin.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right text-zinc-700">{s.market_cap.toLocaleString()}</td>
                        <td className={`px-3 py-2 text-right ${s.revenue_growth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.revenue_growth > 0 ? '+' : ''}{s.revenue_growth.toFixed(1)}</td>
                        <td className={`px-3 py-2 text-right ${s.profit_growth > 0 ? 'text-red-600' : 'text-green-600'}`}>{s.profit_growth > 0 ? '+' : ''}{s.profit_growth.toFixed(1)}</td>
                        <td className={`px-3 py-2 text-right ${s.debt_ratio > 70 ? 'text-amber-600' : 'text-zinc-700'}`}>{s.debt_ratio.toFixed(1)}</td>
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
