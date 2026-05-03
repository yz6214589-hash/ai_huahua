import { useEffect, useMemo, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { KirsStatus } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'

function fmtPct(v: number) {
  if (!Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(2)}%`
}

export default function DashboardPage() {
  const [status, setStatus] = useState<KirsStatus | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [startNav, setStartNav] = useState<string>('1000000')
  const [vix, setVix] = useState<string>('18.5')
  const [nav, setNav] = useState<string>('1000000')

  const parseNum = (s: string) => {
    const t = s.trim()
    if (t === '') return NaN
    const n = Number(t)
    return Number.isFinite(n) ? n : NaN
  }

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const s = await fetchJson<KirsStatus>('/api/kris/status')
      setStatus(s)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const kpis = useMemo(() => {
    if (!status) return []
    return [
      { label: '当日状态', value: status.circuit_breaker.is_halted ? '已熔断' : '未熔断', sub: status.circuit_breaker.halt_reason || '—' },
      { label: 'VIX', value: status.macro.vix == null ? '—' : String(status.macro.vix), sub: `风险等级：${status.macro.risk_level}` },
      { label: '仓位系数', value: fmtPct(status.macro.coefficient), sub: '宏观门控 max_position_pct' },
      { label: '当日盈亏', value: fmtPct(status.circuit_breaker.daily_pnl_pct), sub: `start_nav: ${status.circuit_breaker.daily_start_nav.toLocaleString()}` },
    ]
  }, [status])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-zinc-600">盘前重置 · 盘中宏观门控 · 成交后净值回传</div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
        >
          刷新
        </button>
      </div>

      {err ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.label}>
            <CardBody>
              <div className="text-xs text-zinc-500">{k.label}</div>
              <div className="mt-2 text-2xl font-semibold text-zinc-900">{k.value}</div>
              <div className="mt-1 text-xs text-zinc-500">{k.sub}</div>
            </CardBody>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="当日控制台" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs text-zinc-600">start_day(start_nav)</div>
                <input
                  value={startNav}
                  onChange={(e) => setStartNav(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={async () => {
                    try {
                      const n = parseNum(startNav)
                      if (!(n > 0)) throw new Error('请输入有效的 start_nav')
                      await fetchJson('/api/kris/start-day', { method: 'POST', body: JSON.stringify({ start_nav: n }) })
                      await load()
                    } catch (e) {
                      setErr(e instanceof Error ? e.message : String(e))
                    }
                  }}
                  className="w-full rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800"
                >
                  重置当日
                </button>
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-600">更新 VIX</div>
                <input
                  value={vix}
                  onChange={(e) => setVix(e.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={async () => {
                    try {
                      const n = parseNum(vix)
                      if (!Number.isFinite(n)) throw new Error('请输入有效的 VIX')
                      await fetchJson('/api/kris/update-macro', { method: 'POST', body: JSON.stringify({ vix: n }) })
                      await load()
                    } catch (e) {
                      setErr(e instanceof Error ? e.message : String(e))
                    }
                  }}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50"
                >
                  更新宏观
                </button>
              </div>

              <div className="space-y-1 md:col-span-2">
                <div className="text-xs text-zinc-600">on_trade_complete(nav)</div>
                <div className="flex gap-2">
                  <input
                    value={nav}
                    onChange={(e) => setNav(e.target.value)}
                    className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
                  />
                  <button
                    onClick={async () => {
                      try {
                        const n = parseNum(nav)
                        if (!(n > 0)) throw new Error('请输入有效的 nav')
                        await fetchJson('/api/kris/trade-complete', { method: 'POST', body: JSON.stringify({ nav: n }) })
                        await load()
                      } catch (e) {
                        setErr(e instanceof Error ? e.message : String(e))
                      }
                    }}
                    className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50"
                  >
                    回传
                  </button>
                </div>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="审批统计" />
          <CardBody className="space-y-3 text-sm text-zinc-700">
            <div>总审批：{status?.total ?? '—'}</div>
            <div>通过：{status?.approved ?? '—'}</div>
            <div>警告：{status?.warned ?? '—'}</div>
            <div>拒绝/熔断：{status?.rejected ?? '—'}</div>
            <div>拒绝率：{status ? fmtPct(status.rejection_rate) : '—'}</div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
