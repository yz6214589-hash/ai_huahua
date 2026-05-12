import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { StockPicker } from '@/components/StockPicker'
import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { AnalysisSignalsResponse, AnalysisStocksSampleResponse, StockSearchItem } from '@/api/types'
import { RefreshCcw } from 'lucide-react'

type StrategyStatus = {
  source: string
  status: string
  features: string[]
}

export default function Strategy() {
  const [data, setData] = useState<StrategyStatus | null>(null)
  const [sampleCodes, setSampleCodes] = useState<string[]>([])
  const [selected, setSelected] = useState<StockSearchItem | null>(null)
  const [start, setStart] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 90)
    return d.toISOString().slice(0, 10)
  })
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10))
  const [signals, setSignals] = useState<AnalysisSignalsResponse | null>(null)
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetchJson<StrategyStatus>('/api/analysis/status')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  useEffect(() => {
    fetchJson<AnalysisStocksSampleResponse>('/api/analysis/stocks/sample?limit=50')
      .then((r) => setSampleCodes(r.codes || []))
      .catch(() => setSampleCodes([]))
  }, [])

  const loadSignals = async () => {
    const code = selected?.code?.trim()
    if (!code) {
      setErr('请先选择股票')
      return
    }
    if (!start || !end) {
      setErr('请选择开始/结束日期')
      return
    }
    setLoadingSignals(true)
    setErr(null)
    try {
      const qs = new URLSearchParams()
      qs.set('stock_code', code)
      qs.set('start', start)
      qs.set('end', end)
      const r = await fetchJson<AnalysisSignalsResponse>(`/api/analysis/signals?${qs.toString()}`)
      setSignals(r)
    } catch (e) {
      setSignals(null)
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoadingSignals(false)
    }
  }

  const toneOf = (s: string) => {
    if (s === 'BUY') return 'green'
    if (s === 'SELL') return 'red'
    return 'zinc'
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader title="策略分析（信号）" />
          <CardBody className="space-y-3 text-sm text-zinc-700">
            <div>模块来源：{data?.source || 'zoe'}</div>
            <div>状态：{data?.status || 'loading'}</div>
            <div>能力：{(data?.features || []).join(' / ') || '—'}</div>

            {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</div> : null}

            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">当前选择</div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <div className="min-w-0 truncate text-sm font-semibold text-zinc-900">
                  {selected ? `${selected.code}${selected.name ? ` ${selected.name}` : ''}` : '未选择'}
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="shrink-0 rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                >
                  清空
                </button>
              </div>
            </div>

            <div>
              <div className="text-xs text-zinc-500">选择股票</div>
              <StockPicker
                mode="single"
                value={selected}
                onChange={(v) => setSelected((v as StockSearchItem) || null)}
                placeholder="搜索股票代码或名称"
                className="mt-1"
              />
              {sampleCodes.length > 0 && !selected ? (
                <div className="mt-2 rounded-lg border border-zinc-200 bg-white p-3">
                  <div className="text-xs text-zinc-500">示例代码</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {sampleCodes.slice(0, 12).map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setSelected({ code: c })}
                        className="rounded-lg border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-50"
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <div className="text-xs text-zinc-500">开始日期</div>
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
              <label className="block">
                <div className="text-xs text-zinc-500">结束日期</div>
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-400"
                />
              </label>
            </div>

            <button
              type="button"
              disabled={loadingSignals}
              onClick={loadSignals}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
            >
              <RefreshCcw className="h-4 w-4" />
              {loadingSignals ? '生成中...' : '生成信号'}
            </button>
          </CardBody>
        </Card>
      </div>

      <div className="lg:col-span-3">
        <Card>
          <CardHeader title="信号结果" />
          <CardBody>
            {!signals ? (
              <div className="text-sm text-zinc-500">选择股票并生成信号后在此展示</div>
            ) : signals.signals.length === 0 ? (
              <div className="text-sm text-zinc-500">暂无信号数据，请先配置数据源</div>
            ) : (
              <div className="overflow-auto rounded-lg border border-zinc-200 bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs text-zinc-500">
                    <tr>
                      <th className="px-3 py-2">日期</th>
                      <th className="px-3 py-2">信号</th>
                      <th className="px-3 py-2">分数</th>
                      <th className="px-3 py-2">原因</th>
                      <th className="px-3 py-2">快照</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.signals.map((s) => (
                      <tr key={s.trade_date + s.signal} className="border-t border-zinc-100 align-top">
                        <td className="px-3 py-2 text-xs text-zinc-700">{s.trade_date}</td>
                        <td className="px-3 py-2">
                          <Badge tone={toneOf(s.signal)}>{s.signal}</Badge>
                        </td>
                        <td className="px-3 py-2 text-xs text-zinc-700">{Math.round(Number(s.score || 0))}</td>
                        <td className="px-3 py-2 text-xs text-zinc-700">{(s.reasons || []).join('；') || '—'}</td>
                        <td className="px-3 py-2 text-xs text-zinc-500">
                          close={String(s.snapshot?.close ?? '—')} ma20={String(s.snapshot?.ma20 ?? '—')} rsi14={String(s.snapshot?.rsi14 ?? '—')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
