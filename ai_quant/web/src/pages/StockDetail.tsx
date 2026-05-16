import { fetchJson } from '@/api/client'
import type {
  StockFeedResponse,
  StockFundamentals,
  StockSnapshot,
  StockTechnicalLatest,
  StockTechnicalRow,
} from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Tabs } from '@/components/Tabs'
import { cn } from '@/lib/utils'
import type { EChartsOption } from 'echarts'
import ReactECharts from 'echarts-for-react'
import { ArrowLeft, ExternalLink, RefreshCcw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

function fmtNum(v: number | null | undefined, digits: number) {
  if (v === null || v === undefined || Number.isNaN(v)) return '--'
  return v.toFixed(digits)
}

function fmtSigned(v: number | null | undefined, digits: number) {
  if (v === null || v === undefined || Number.isNaN(v)) return '--'
  const s = v.toFixed(digits)
  return v > 0 ? `+${s}` : s
}

function fmtDateTime(v: string | null | undefined) {
  if (!v) return '—'
  return v.slice(0, 19).replace('T', ' ')
}

function todayISO() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

function shiftDaysISO(days: number) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

export default function StockDetail() {
  const { code = '' } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()

  const [tab, setTab] = useState<'fundamentals' | 'technical' | 'feed'>('fundamentals')

  const [snapshot, setSnapshot] = useState<StockSnapshot | null>(null)
  const [fund, setFund] = useState<StockFundamentals | null>(null)
  const [techLatest, setTechLatest] = useState<StockTechnicalLatest | null>(null)
  const [techRows, setTechRows] = useState<StockTechnicalRow[]>([])
  const [feedTab, setFeedTab] = useState<'news' | 'reports'>('news')
  const [feed, setFeed] = useState<StockFeedResponse | null>(null)

  const [loadingSnap, setLoadingSnap] = useState(false)
  const [loadingFund, setLoadingFund] = useState(false)
  const [loadingTech, setLoadingTech] = useState(false)
  const [loadingFeed, setLoadingFeed] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [techView, setTechView] = useState<'data' | 'chart'>('chart')
  const [start, setStart] = useState(params.get('start') || shiftDaysISO(180))
  const [end, setEnd] = useState(params.get('end') || todayISO())
  const [maPeriod, setMaPeriod] = useState(() => {
    const v = parseInt(params.get('ma') || '20', 10)
    return [5, 10, 20, 30, 60].includes(v) ? v : 20
  })
  const [macdShort, setMacdShort] = useState(() => {
    const v = parseInt(params.get('macdShort') || '12', 10)
    return Number.isFinite(v) && v > 0 ? v : 12
  })
  const [macdLong, setMacdLong] = useState(() => {
    const v = parseInt(params.get('macdLong') || '26', 10)
    return Number.isFinite(v) && v > 0 ? v : 26
  })
  const [macdSignal, setMacdSignal] = useState(() => {
    const v = parseInt(params.get('macdSignal') || '9', 10)
    return Number.isFinite(v) && v > 0 ? v : 9
  })
  const [rsiPeriod, setRsiPeriod] = useState(() => {
    const v = parseInt(params.get('rsi') || '14', 10)
    return Number.isFinite(v) && v > 0 ? v : 14
  })
  const [atrPeriod, setAtrPeriod] = useState(() => {
    const v = parseInt(params.get('atr') || '14', 10)
    return Number.isFinite(v) && v > 0 ? v : 14
  })

  const page = Number(params.get('page') || '1')

  const techQuery = useMemo(() => {
    const q = new URLSearchParams()
    q.set('maPeriod', String(maPeriod))
    q.set('macdShort', String(macdShort))
    q.set('macdLong', String(macdLong))
    q.set('macdSignal', String(macdSignal))
    q.set('rsiPeriod', String(rsiPeriod))
    q.set('atrPeriod', String(atrPeriod))
    return q.toString()
  }, [maPeriod, macdShort, macdLong, macdSignal, rsiPeriod, atrPeriod])

  const loadSnapshot = useCallback(async () => {
    setLoadingSnap(true)
    try {
      const r = await fetchJson<StockSnapshot>(`/api/stock/${encodeURIComponent(code)}/snapshot`)
      setSnapshot(r)
    } finally {
      setLoadingSnap(false)
    }
  }, [code])

  const loadFund = useCallback(async () => {
    setLoadingFund(true)
    try {
      const r = await fetchJson<StockFundamentals>(`/api/stock/${encodeURIComponent(code)}/fundamentals`)
      setFund(r)
    } finally {
      setLoadingFund(false)
    }
  }, [code])

  const loadTech = useCallback(async () => {
    setLoadingTech(true)
    try {
      const latest = await fetchJson<StockTechnicalLatest>(`/api/stock/${encodeURIComponent(code)}/technical/latest?${techQuery}`)
      setTechLatest(latest)
      const r = await fetchJson<{ stock_code: string; rows: StockTechnicalRow[] }>(
        `/api/stock/${encodeURIComponent(code)}/technical/series?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&${techQuery}`
      )
      setTechRows(r.rows || [])
    } finally {
      setLoadingTech(false)
    }
  }, [code, techQuery, start, end])

  const loadFeed = useCallback(async () => {
    setLoadingFeed(true)
    try {
      const r = await fetchJson<StockFeedResponse>(
        `/api/stock/${encodeURIComponent(code)}/feed?tab=${encodeURIComponent(feedTab)}&page=${page}&pageSize=5`
      )
      setFeed(r)
    } finally {
      setLoadingFeed(false)
    }
  }, [code, feedTab, page])

  const loadAll = useCallback(async () => {
    setErr(null)
    try {
      await Promise.all([loadSnapshot(), loadFund(), loadTech(), loadFeed()])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }, [loadSnapshot, loadFund, loadTech, loadFeed])

  useEffect(() => {
    loadAll()
  }, [code])

  useEffect(() => {
    setParams((p) => {
      p.set('start', start)
      p.set('end', end)
      p.set('ma', String(maPeriod))
      p.set('macdShort', String(macdShort))
      p.set('macdLong', String(macdLong))
      p.set('macdSignal', String(macdSignal))
      p.set('rsi', String(rsiPeriod))
      p.set('atr', String(atrPeriod))
      return p
    })
  }, [start, end, maPeriod, macdShort, macdLong, macdSignal, rsiPeriod, atrPeriod, setParams])

  useEffect(() => {
    loadTech().catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [start, end, techQuery])

  useEffect(() => {
    loadFeed().catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [feedTab, page])

  const header = (
    <div className="sticky top-0 z-10 border-b border-zinc-200 bg-white px-4 py-3 md:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="text-sm font-semibold text-zinc-900">
              {snapshot?.stock_name || '—'} <span className="text-zinc-500">{code}</span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-600">
              <span>现价 {fmtNum(snapshot?.price ?? null, 2)}</span>
              <span className={cn(snapshot?.change && snapshot.change > 0 ? 'text-red-600' : snapshot?.change && snapshot.change < 0 ? 'text-green-600' : '')}>
                {fmtSigned(snapshot?.change ?? null, 2)} ({fmtSigned(snapshot?.pctChange ?? null, 2)}%)
              </span>
              <span className="text-zinc-400">asOf {fmtDateTime(snapshot?.asOf)}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => loadAll()}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
          >
            <RefreshCcw className="h-4 w-4" />
            刷新
          </button>

        </div>
      </div>
    </div>
  )

  const fundGrid = (
    <Card>
      <CardHeader title="基本面" />
      <CardBody>
        {loadingFund ? <div className="text-sm text-zinc-500">加载中…</div> : null}
        {fund?.reportDate ? <div className="mb-3 text-xs text-zinc-500">最新财报期：{fund.reportDate}</div> : null}
        {!loadingFund && (!fund || fund.items.length === 0) ? <div className="text-sm text-zinc-500">暂无数据</div> : null}
        {fund && fund.items.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {fund.items.map((it) => (
              <div key={it.key} className="rounded-lg border border-zinc-200 bg-white px-3 py-2" title={it.tooltip}>
                <div className="text-xs text-zinc-500">{it.label}</div>
                <div className="mt-1 flex items-baseline justify-between gap-2">
                  <div className="text-sm font-semibold text-zinc-900">
                    {it.value === null ? '--' : `${fmtNum(it.value, 2)}${it.unit}`}
                  </div>
                  <div className="text-xs text-zinc-500">
                    {it.delta === null ? (
                      '—'
                    ) : (
                      <span className={cn(it.dir === 'up' ? 'text-red-600' : it.dir === 'down' ? 'text-green-600' : '')}>
                        {(() => {
                          const prev = it.value === null ? null : it.value - it.delta
                          const pct = prev && prev !== 0 ? (it.delta / prev) * 100 : null
                          return (
                            <>
                              {it.dir === 'up' ? '↑' : it.dir === 'down' ? '↓' : '→'} {pct === null ? '—' : `${fmtSigned(pct, 2)}%`}
                            </>
                          )
                        })()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </CardBody>
    </Card>
  )

  const technicalTable = (
    <div className="overflow-auto rounded-lg border border-zinc-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs text-zinc-500">
          <tr>
            <th className="px-3 py-2">指标</th>
            <th className="px-3 py-2">最新值</th>
          </tr>
        </thead>
        <tbody>
          {(
            [
              { key: 'ma_custom', label: `MA${maPeriod}` },
              { key: 'macd_dif_custom', label: `DIF(${macdShort},${macdLong},${macdSignal})` },
              { key: 'macd_dea_custom', label: `DEA(${macdShort},${macdLong},${macdSignal})` },
              { key: 'macd_hist_custom', label: `MACD(${macdShort},${macdLong},${macdSignal})` },
              { key: 'rsi_custom', label: `RSI(${rsiPeriod})` },
              { key: 'atr_custom', label: `ATR(${atrPeriod})` },
              { key: 'ma5', label: 'ma5' },
              { key: 'ma10', label: 'ma10' },
              { key: 'ma20', label: 'ma20' },
              { key: 'ma60', label: 'ma60' },
              { key: 'vol_ma5', label: 'vol_ma5' },
              { key: 'vol_ma20', label: 'vol_ma20' },
              { key: 'rsi14', label: 'rsi14' },
              { key: 'macd_dif', label: 'macd_dif' },
              { key: 'macd_dea', label: 'macd_dea' },
              { key: 'macd_hist', label: 'macd_hist' },
              { key: 'boll_upper', label: 'boll_upper' },
              { key: 'boll_mid', label: 'boll_mid' },
              { key: 'boll_lower', label: 'boll_lower' },
              { key: 'kdj_k', label: 'kdj_k' },
              { key: 'kdj_d', label: 'kdj_d' },
              { key: 'kdj_j', label: 'kdj_j' },
            ] as const
          ).map((it) => {
            const row = techLatest?.row as Record<string, unknown> | null | undefined
            const raw = row?.[it.key]
            const v = typeof raw === 'number' ? raw : null
            return (
              <tr key={it.key} className="border-t border-zinc-100">
                <td className="px-3 py-2 font-medium text-zinc-900">{it.label}</td>
                <td className="px-3 py-2 text-zinc-700">{v === null || v === undefined ? '--' : fmtNum(v, 3)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )

  const chartOption = useMemo<EChartsOption>(() => {
    const dates = techRows.map((r) => String(r.trade_date).slice(0, 10))
    const close = techRows.map((r) => r.close_price)
    const maLine = techRows.map((r) => r.ma_custom ?? null)
    const macdHist = techRows.map((r) => r.macd_hist_custom ?? null)
    const macdDif = techRows.map((r) => r.macd_dif_custom ?? null)
    const macdDea = techRows.map((r) => r.macd_dea_custom ?? null)
    const vol = techRows.map((r) => r.volume)
    const rsi = techRows.map((r) => r.rsi_custom ?? null)
    const atr = techRows.map((r) => r.atr_custom ?? null)

    const volColors = techRows.map((r, i) => {
      const cur = r.close_price
      const prev = i > 0 ? techRows[i - 1].close_price : null
      if (cur === null || cur === undefined || prev === null || prev === undefined) return '#94a3b8'
      return cur >= prev ? '#ef4444' : '#22c55e'
    })

    const volSeries = vol.map((v, i) => ({ value: v, itemStyle: { color: volColors[i] } }))

    return {
      animation: false,
      title: [
        { text: `MA 方向（MA${maPeriod}）`, left: 60, top: 10, textStyle: { fontSize: 12, fontWeight: 600, color: '#111827' } },
        { text: `MACD（${macdShort},${macdLong},${macdSignal}）快线DIF/慢线DEA`, left: 60, top: 190, textStyle: { fontSize: 12, fontWeight: 600, color: '#111827' } },
        { text: '成交量（燃料）', left: 60, top: 315, textStyle: { fontSize: 12, fontWeight: 600, color: '#111827' } },
        { text: `RSI 位置（${rsiPeriod}）`, left: 60, top: 410, textStyle: { fontSize: 12, fontWeight: 600, color: '#111827' } },
        { text: `ATR 风险（${atrPeriod}）`, left: 60, top: 505, textStyle: { fontSize: 12, fontWeight: 600, color: '#111827' } },
      ],
      legend: [
        {
          top: 12,
          right: 40,
          icon: 'roundRect',
          itemWidth: 10,
          itemHeight: 4,
          textStyle: { fontSize: 11, color: '#475569' },
          data: ['收盘价', `MA${maPeriod}`],
        },
        {
          top: 192,
          right: 40,
          icon: 'roundRect',
          itemWidth: 10,
          itemHeight: 4,
          textStyle: { fontSize: 11, color: '#475569' },
          data: ['DIF', 'DEA', 'MACD'],
        },
        {
          top: 317,
          right: 40,
          icon: 'roundRect',
          itemWidth: 10,
          itemHeight: 4,
          textStyle: { fontSize: 11, color: '#475569' },
          data: ['成交量'],
        },
        {
          top: 412,
          right: 40,
          icon: 'roundRect',
          itemWidth: 10,
          itemHeight: 4,
          textStyle: { fontSize: 11, color: '#475569' },
          data: [`RSI(${rsiPeriod})`],
        },
        {
          top: 507,
          right: 40,
          icon: 'roundRect',
          itemWidth: 10,
          itemHeight: 4,
          textStyle: { fontSize: 11, color: '#475569' },
          data: [`ATR(${atrPeriod})`],
        },
      ],
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      grid: [
        { left: 60, right: 40, top: 35, height: 140 },
        { left: 60, right: 40, top: 215, height: 95 },
        { left: 60, right: 40, top: 340, height: 70 },
        { left: 60, right: 40, top: 435, height: 70 },
        { left: 60, right: 40, top: 530, height: 70 },
      ],
      xAxis: [
        { type: 'category', data: dates, boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' },
        { type: 'category', gridIndex: 1, data: dates, boundaryGap: false, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
        { type: 'category', gridIndex: 2, data: dates, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
        { type: 'category', gridIndex: 3, data: dates, boundaryGap: false, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
        { type: 'category', gridIndex: 4, data: dates, boundaryGap: false, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      yAxis: [
        { scale: true, splitArea: { show: true } },
        { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
        { scale: true, gridIndex: 2, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
        { min: 0, max: 100, gridIndex: 3, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
        { scale: true, gridIndex: 4, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1, 2, 3, 4], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1, 2, 3, 4], top: 610, height: 18, start: 0, end: 100 },
      ],
      series: [
        { name: '收盘价', type: 'line', data: close, showSymbol: false, lineStyle: { width: 1.2, color: '#2563eb' } },
        { name: `MA${maPeriod}`, type: 'line', data: maLine, showSymbol: false, lineStyle: { width: 1.2, color: '#f59e0b' }, tooltip: { show: false } },
        { name: 'MACD', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: macdHist, itemStyle: { color: '#60a5fa' }, large: true },
        { name: 'DIF', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macdDif, showSymbol: false, lineStyle: { width: 1, color: '#ef4444' } },
        { name: 'DEA', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macdDea, showSymbol: false, lineStyle: { width: 1, color: '#22c55e' } },
        { name: '成交量', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: volSeries, large: true },
        {
          name: `RSI(${rsiPeriod})`,
          type: 'line',
          xAxisIndex: 3,
          yAxisIndex: 3,
          data: rsi,
          showSymbol: false,
          lineStyle: { width: 1.2, color: '#7c3aed' },
          markLine: {
            symbol: 'none',
            lineStyle: { color: '#94a3b8', type: 'dashed' },
            data: [{ yAxis: 80 }, { yAxis: 50 }, { yAxis: 20 }],
          },
        },
        { name: `ATR(${atrPeriod})`, type: 'line', xAxisIndex: 4, yAxisIndex: 4, data: atr, showSymbol: false, lineStyle: { width: 1.2, color: '#b45309' } },
      ],
    }
  }, [techRows, maPeriod, macdShort, macdLong, macdSignal, rsiPeriod, atrPeriod])

  const technicalBlock = (
    <Card>
      <CardHeader
        title="技术面"
        right={
          <div className="flex flex-wrap items-center gap-2">
            <Tabs
              value={techView}
              onChange={(v) => setTechView(v === 'data' ? 'data' : 'chart')}
              items={[
                { key: 'chart', label: '仪表盘' },
                { key: 'data', label: '数据' },
              ]}
            />
          </div>
        }
      />
      <CardBody>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs text-zinc-500">
            开始
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="ml-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="text-xs text-zinc-500">
            结束
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="ml-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <button
            type="button"
            onClick={() => {
              setStart(shiftDaysISO(180))
              setEnd(todayISO())
            }}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
          >
            近半年
          </button>
          <label className="text-xs text-zinc-500">
            MA
            <select
              value={String(maPeriod)}
              onChange={(e) => setMaPeriod(parseInt(e.target.value, 10))}
              className="ml-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            >
              <option value="5">MA5</option>
              <option value="10">MA10</option>
              <option value="20">MA20</option>
              <option value="30">MA30</option>
              <option value="60">MA60</option>
            </select>
          </label>
          <label className="text-xs text-zinc-500">
            MACD短
            <input
              inputMode="numeric"
              value={String(macdShort)}
              onChange={(e) => setMacdShort(Math.max(2, parseInt(e.target.value.replace(/\D/g, '') || '12', 10)))}
              className="ml-2 w-20 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="text-xs text-zinc-500">
            长
            <input
              inputMode="numeric"
              value={String(macdLong)}
              onChange={(e) => setMacdLong(Math.max(3, parseInt(e.target.value.replace(/\D/g, '') || '26', 10)))}
              className="ml-2 w-20 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="text-xs text-zinc-500">
            DEA
            <input
              inputMode="numeric"
              value={String(macdSignal)}
              onChange={(e) => setMacdSignal(Math.max(2, parseInt(e.target.value.replace(/\D/g, '') || '9', 10)))}
              className="ml-2 w-20 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="text-xs text-zinc-500">
            RSI
            <input
              inputMode="numeric"
              value={String(rsiPeriod)}
              onChange={(e) => setRsiPeriod(Math.max(2, parseInt(e.target.value.replace(/\D/g, '') || '14', 10)))}
              className="ml-2 w-20 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
          <label className="text-xs text-zinc-500">
            ATR
            <input
              inputMode="numeric"
              value={String(atrPeriod)}
              onChange={(e) => setAtrPeriod(Math.max(2, parseInt(e.target.value.replace(/\D/g, '') || '14', 10)))}
              className="ml-2 w-20 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
            />
          </label>
        </div>

        {loadingTech ? <div className="mt-3 text-sm text-zinc-500">加载中…</div> : null}
        {!loadingTech && techRows.length === 0 ? <div className="mt-3 text-sm text-zinc-500">暂无数据</div> : null}

        {!loadingTech && techView === 'data' ? <div className="mt-3">{technicalTable}</div> : null}

        {!loadingTech && techView === 'chart' && techRows.length > 0 ? (
          <div className="mt-3">
            <ReactECharts option={chartOption} style={{ height: 700, width: '100%' }} />
          </div>
        ) : null}
      </CardBody>
    </Card>
  )

  const feedBlock = (
    <Card>
      <CardHeader
        title="个股新闻 / 机构研报"
        right={
          <Tabs
            value={feedTab}
            onChange={(v) => {
              setFeedTab(v === 'reports' ? 'reports' : 'news')
              setParams((p) => {
                p.set('page', '1')
                return p
              })
            }}
            items={[
              { key: 'news', label: '新闻' },
              { key: 'reports', label: '研报' },
            ]}
          />
        }
      />
      <CardBody>
        {loadingFeed ? <div className="text-sm text-zinc-500">加载中…</div> : null}
        {!loadingFeed && (!feed || feed.items.length === 0) ? <div className="text-sm text-zinc-500">暂无数据</div> : null}
        {feed && feed.items.length > 0 ? (
          <div className="space-y-2">
            {feed.items.map((it, idx) => (
              <div key={`${it.title}-${idx}`} className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-zinc-900">{it.title}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                      <span>{it.source || '—'}</span>
                      <span>{fmtDateTime(it.publishedAt || null)}</span>
                    </div>
                  </div>
                  {it.url ? (
                    <a
                      href={it.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      打开
                    </a>
                  ) : (
                    <span className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs text-zinc-400" title="暂无链接">
                      暂无链接
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {feed ? (
          <div className="mt-3 flex items-center justify-between">
            <div className="text-xs text-zinc-500">
              total: {feed.total} · page {feed.page}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={feed.page <= 1}
                onClick={() =>
                  setParams((p) => {
                    p.set('page', String(Math.max(1, page - 1)))
                    return p
                  })
                }
                className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
              >
                上一页
              </button>
              <button
                type="button"
                disabled={feed.page * feed.pageSize >= feed.total}
                onClick={() =>
                  setParams((p) => {
                    p.set('page', String(page + 1))
                    return p
                  })
                }
                className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
              >
                下一页
              </button>
            </div>
          </div>
        ) : null}
      </CardBody>
    </Card>
  )

  return (
    <div className="-mx-4 -mt-6 md:-mx-6">
      {header}
      <div className="px-4 py-6 md:px-6">
        {err ? <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div> : null}

        <div className="mb-4">
          <Tabs
            value={tab}
            onChange={(v) => setTab(v === 'technical' ? 'technical' : v === 'feed' ? 'feed' : 'fundamentals')}
            items={[
              { key: 'fundamentals', label: '基本面' },
              { key: 'technical', label: '技术面' },
              { key: 'feed', label: '新闻/研报' },
            ]}
          />
        </div>

        <div className="space-y-4">
          {tab === 'fundamentals' ? fundGrid : null}
          {tab === 'technical' ? technicalBlock : null}
          {tab === 'feed' ? feedBlock : null}
        </div>

        {loadingSnap ? <div className="mt-3 text-xs text-zinc-500">加载快照中…</div> : null}
      </div>
    </div>
  )
}

