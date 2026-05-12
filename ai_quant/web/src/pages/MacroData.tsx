import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { MacroLatest } from '@/api/types'
import { cn } from '@/lib/utils'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { ExternalLink, RefreshCcw } from 'lucide-react'

const INDICATOR_LABELS: Record<string, string> = {
  CPI: 'CPI（居民消费价格指数）',
  PPI: 'PPI（生产价格指数）',
  PMI: 'PMI（采购经理指数）',
  LPR: 'LPR（贷款市场报价利率）',
  FearGreed: '恐惧贪婪指数',
  VIX: 'VIX（CBOE波动率指数）',
  OVX: 'OVX（原油波动率指数）',
  GVZ: 'GVZ（黄金波动率指数）',
  US10Y: '美国10年期国债收益率',
}

function IndicatorCard({ it }: { it: MacroLatest['indicators'][number] }) {
  const label = INDICATOR_LABELS[it.indicator] || it.indicator
  const raw = it.value
  const display = raw == null ? '—' : typeof raw === 'number' && it.indicator === 'US10Y' ? `${(raw * 100).toFixed(2)}%` : String(raw)
  return (
    <Card>
      <CardBody>
        <div className="text-2xl font-bold text-zinc-900">{display}</div>
        <div className="mt-1 text-xs text-zinc-500">{label}{it.date ? ` · ${it.date}` : ''}</div>
        {it.error ? <div className="mt-1 text-xs text-red-500">{it.error}</div> : null}
      </CardBody>
    </Card>
  )
}

export default function MacroData() {
  const [macro, setMacro] = useState<MacroLatest | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<MacroLatest>('/api/macro/latest')
      setMacro(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">实时宏观指标数据</div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          <RefreshCcw className={cn(loading ? 'animate-spin' : '', 'h-4 w-4')} />
          刷新
        </button>
      </div>
      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}
      {macro?.indicators && macro.indicators.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {macro.indicators.map((it) => (
            <IndicatorCard key={it.indicator} it={it} />
          ))}
        </div>
      ) : !loading ? (
        <div className="rounded-lg border border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500">暂无宏观数据</div>
      ) : null}

      {macro?.composite ? (
        <Card>
          <CardHeader title="综合恐慌/贪婪指数" />
          <CardBody>
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-xs text-zinc-500">恐慌/贪婪指数</div>
                <div className="mt-1 text-3xl font-extrabold text-zinc-900">
                  {macro.composite.composite_fear_greed_index ?? '—'} / 100
                </div>
                <div className="mt-1 text-sm text-zinc-600">
                  整体情绪：{macro.composite.overall_sentiment || '—'}；建议：{macro.composite.action_suggestion || '—'}
                </div>
              </div>
              <div className="w-full max-w-[320px] rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <div className="text-xs text-zinc-500">更新时间</div>
                <div className="mt-1 text-sm text-zinc-900">{macro.composite.timestamp || '—'}</div>
              </div>
            </div>
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Polymarket 快捷入口" />
        <CardBody>
          <div className="mt-1 flex flex-wrap gap-2">
            {['war', 'ceasefire', 'tariff', 'China', 'Fed'].map((k) => (
              <a
                key={k}
                href={`https://polymarket.com/markets?search=${k}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
              >
                {k} <ExternalLink className="h-3 w-3" />
              </a>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
