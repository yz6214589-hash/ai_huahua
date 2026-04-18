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
import { ArrowLeft, ExternalLink, RefreshCcw, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
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

  const page = Number(params.get('page') || '1')

  const loadSnapshot = async () => {
    setLoadingSnap(true)
    try {
      const r = await fetchJson<StockSnapshot>(`/api/stock/${encodeURIComponent(code)}/snapshot`)
      setSnapshot(r)
    } finally {
      setLoadingSnap(false)
    }
  }

  const loadFund = async () => {
    setLoadingFund(true)
    try {
      const r = await fetchJson<StockFundamentals>(`/api/stock/${encodeURIComponent(code)}/fundamentals`)
      setFund(r)
    } finally {
      setLoadingFund(false)
    }
  }

  const loadTech = async () => {
    setLoadingTech(true)
    try {
      const latest = await fetchJson<StockTechnicalLatest>(`/api/stock/${encodeURIComponent(code)}/technical/latest`)
      setTechLatest(latest)
      const r = await fetchJson<{ stock_code: string; rows: StockTechnicalRow[] }>(
        `/api/stock/${encodeURIComponent(code)}/technical/series?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
      )
      setTechRows(r.rows || [])
    } finally {
      setLoadingTech(false)
    }
  }

  const loadFeed = async () => {
    setLoadingFeed(true)
    try {
      const r = await fetchJson<StockFeedResponse>(
        `/api/stock/${encodeURIComponent(code)}/feed?tab=${encodeURIComponent(feedTab)}&page=${page}&pageSize=5`
      )
      setFeed(r)
    } finally {
      setLoadingFeed(false)
    }
  }

  const loadAll = async () => {
    setErr(null)
    try {
      await Promise.all([loadSnapshot(), loadFund(), loadTech(), loadFeed()])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    loadAll()
  }, [code])

  useEffect(() => {
    setParams((p) => {
      p.set('start', start)
      p.set('end', end)
      return p
    })
  }, [start, end, setParams])

  useEffect(() => {
    loadTech().catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [start, end])

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
          <button
            type="button"
            onClick={() => navigate('/watchlist')}
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            <X className="h-4 w-4" />
            关闭
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
                        {it.dir === 'up' ? '↑' : it.dir === 'down' ? '↓' : '→'} {fmtSigned(it.delta, 2)}
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
          {[
            'ma5',
            'ma10',
            'ma20',
            'ma60',
            'vol_ma5',
            'vol_ma20',
            'rsi14',
            'macd_dif',
            'macd_dea',
            'macd_hist',
            'boll_upper',
            'boll_mid',
            'boll_lower',
            'kdj_k',
            'kdj_d',
            'kdj_j',
          ].map((k) => {
            const row = techLatest?.row as Record<string, unknown> | null | undefined
            const raw = row?.[k]
            const v = typeof raw === 'number' ? raw : null
            return (
              <tr key={k} className="border-t border-zinc-100">
                <td className="px-3 py-2 font-medium text-zinc-900">{k}</td>
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
    const ohlc = techRows.map((r) => [r.open_price, r.close_price, r.low_price, r.high_price])
    const vol = techRows.map((r) => r.volume)
    const macd = techRows.map((r) => r.macd_hist)
    const dif = techRows.map((r) => r.macd_dif)
    const dea = techRows.map((r) => r.macd_dea)
    const k = techRows.map((r) => r.kdj_k)
    const d = techRows.map((r) => r.kdj_d)
    const j = techRows.map((r) => r.kdj_j)
    const bollU = techRows.map((r) => r.boll_upper)
    const bollM = techRows.map((r) => r.boll_mid)
    const bollL = techRows.map((r) => r.boll_lower)

    return {
      animation: false,
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      grid: [
        { left: 60, right: 40, top: 20, height: 260 },
        { left: 60, right: 40, top: 300, height: 80 },
        { left: 60, right: 40, top: 400, height: 90 },
        { left: 60, right: 40, top: 510, height: 90 },
      ],
      xAxis: [
        { type: 'category', data: dates, boundaryGap: true, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' },
        { type: 'category', gridIndex: 1, data: dates, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
        { type: 'category', gridIndex: 2, data: dates, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
        { type: 'category', gridIndex: 3, data: dates, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      yAxis: [
        { scale: true, splitArea: { show: true } },
        { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
        { scale: true, gridIndex: 2, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
        { scale: true, gridIndex: 3, splitNumber: 2, axisLabel: { show: true }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1, 2, 3], top: 610, height: 20, start: 0, end: 100 },
      ],
      series: [
        { name: 'K', type: 'candlestick', data: ohlc, itemStyle: { color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' } },
        { name: 'BOLL上', type: 'line', data: bollU, showSymbol: false, lineStyle: { width: 1, opacity: 0.8 }, tooltip: { show: false } },
        { name: 'BOLL中', type: 'line', data: bollM, showSymbol: false, lineStyle: { width: 1, opacity: 0.6 }, tooltip: { show: false } },
        { name: 'BOLL下', type: 'line', data: bollL, showSymbol: false, lineStyle: { width: 1, opacity: 0.8 }, tooltip: { show: false } },
        { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: vol, itemStyle: { color: '#94a3b8' }, large: true },
        { name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: macd, itemStyle: { color: '#60a5fa' }, large: true },
        { name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: dif, showSymbol: false, lineStyle: { width: 1, color: '#ef4444' } },
        { name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: dea, showSymbol: false, lineStyle: { width: 1, color: '#22c55e' } },
        { name: 'K', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: k, showSymbol: false, lineStyle: { width: 1, color: '#ef4444' } },
        { name: 'D', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: d, showSymbol: false, lineStyle: { width: 1, color: '#22c55e' } },
        { name: 'J', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: j, showSymbol: false, lineStyle: { width: 1, color: '#60a5fa' } },
      ],
    }
  }, [techRows])

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
        </div>

        {loadingTech ? <div className="mt-3 text-sm text-zinc-500">加载中…</div> : null}
        {!loadingTech && techRows.length === 0 ? <div className="mt-3 text-sm text-zinc-500">暂无数据</div> : null}

        {!loadingTech && techView === 'data' ? <div className="mt-3">{technicalTable}</div> : null}

        {!loadingTech && techView === 'chart' && techRows.length > 0 ? (
          <div className="mt-3">
            <ReactECharts option={chartOption} style={{ height: 660, width: '100%' }} />
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

