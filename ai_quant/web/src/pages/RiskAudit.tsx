import { useEffect, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { RiskAuditResponse } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { RefreshCcw } from 'lucide-react'

function fmt(v: unknown) {
  if (!v) return '—'
  const s = String(v)
  return s.length > 19 ? s.slice(0, 19).replace('T', ' ') : s
}

const tone = (d: string) =>
  d === 'APPROVE' ? 'green' : d === 'WARN' ? 'amber' : d === 'REJECT' ? 'red' : 'zinc'

export default function RiskAudit() {
  const [data, setData] = useState<RiskAuditResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [filterDecision, setFilterDecision] = useState<string>('all')
  const [filterCode, setFilterCode] = useState('')

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetchJson<RiskAuditResponse>('/api/risk/audit?last_n=500')
      setData(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const items = data?.items || []
  const filtered = items.filter((it) => {
    if (filterDecision !== 'all' && it.decision !== filterDecision) return false
    if (filterCode && !(it.stock_code || '').includes(filterCode)) return false
    return true
  })

  const counts = {
    all: items.length,
    APPROVE: items.filter((it) => it.decision === 'APPROVE').length,
    WARN: items.filter((it) => it.decision === 'WARN').length,
    REJECT: items.filter((it) => it.decision === 'REJECT').length,
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        {(['all', 'APPROVE', 'WARN', 'REJECT'] as const).map((d) => (
          <button
            key={d}
            onClick={() => setFilterDecision(d)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              filterDecision === d
                ? 'border-zinc-900 bg-zinc-900 text-white'
                : 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50'
            }`}
          >
            {d === 'all' ? `全部（${counts.all}）` : d === 'APPROVE' ? `通过（${counts.APPROVE}）` : d === 'WARN' ? `警告（${counts.WARN}）` : `拒绝（${counts.REJECT}）`}
          </button>
        ))}
        <input
          value={filterCode}
          onChange={(e) => setFilterCode(e.target.value)}
          placeholder="搜索股票代码"
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400"
        />
        <button
          onClick={load}
          disabled={loading}
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50"
        >
          <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {err ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}

      <Card>
        <CardHeader title={`审批记录（${filtered.length} 条）`} />
        <CardBody className="p-0">
          {loading && !data ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">加载中…</div>
          ) : filtered.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">暂无审批记录</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-4 py-2">时间</th>
                    <th className="px-4 py-2">股票</th>
                    <th className="px-4 py-2">方向</th>
                    <th className="px-4 py-2">金额</th>
                    <th className="px-4 py-2">决策</th>
                    <th className="px-4 py-2">规则</th>
                    <th className="px-4 py-2">原因</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it, idx) => (
                    <tr key={idx} className="border-t border-zinc-100 hover:bg-zinc-50">
                      <td className="px-4 py-2 text-xs text-zinc-500">{fmt(it.timestamp)}</td>
                      <td className="px-4 py-2 text-sm font-medium text-zinc-900">{(it.stock_code || '—')}</td>
                      <td className="px-4 py-2 text-xs text-zinc-600">{it.direction || '—'}</td>
                      <td className="px-4 py-2 text-xs text-zinc-600">{it.amount != null ? it.amount.toLocaleString() : '—'}</td>
                      <td className="px-4 py-2"><Badge tone={tone(String(it.decision))}>{String(it.decision)}</Badge></td>
                      <td className="px-4 py-2 text-xs text-zinc-600">{it.rule_name || '—'}</td>
                      <td className="px-4 py-2 max-w-64 text-xs text-zinc-500">{it.reason || '—'}</td>
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
