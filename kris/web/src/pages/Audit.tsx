import { useEffect, useMemo, useState } from 'react'
import { fetchJson } from '@/api/client'
import type { AuditItem, Decision } from '@/api/types'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { DecisionBadge } from '@/components/DecisionBadge'

export default function AuditPage() {
  const [items, setItems] = useState<AuditItem[]>([])
  const [filter, setFilter] = useState<Decision | ''>('')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const resp = await fetchJson<{ items: AuditItem[] }>('/api/kris/audit?last_n=200')
      setItems(resp.items || [])
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    if (!filter) return items
    return items.filter((x) => x.decision === filter)
  }, [items, filter])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-900">审计日志</div>
          <div className="mt-1 text-xs text-zinc-500">记录每笔审批：时间、订单、决策、规则、原因</div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as Decision | '')}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 outline-none focus:border-zinc-400"
          >
            <option value="">全部决策</option>
            <option value="approve">approve</option>
            <option value="warn">warn</option>
            <option value="reject">reject</option>
            <option value="halt">halt</option>
          </select>
          <button
            onClick={load}
            disabled={loading}
            className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
          >
            刷新
          </button>
        </div>
      </div>

      {err ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div> : null}

      <Card>
        <CardHeader title="最近审批记录" right={<div className="text-xs text-zinc-500">最多 200 条</div>} />
        <CardBody className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="border-b border-zinc-100 text-xs text-zinc-500">
                  <th className="px-4 py-3">时间</th>
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3">方向</th>
                  <th className="px-4 py-3">金额</th>
                  <th className="px-4 py-3">决策</th>
                  <th className="px-4 py-3">规则</th>
                  <th className="px-4 py-3">原因</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td className="px-4 py-10 text-center text-sm text-zinc-500" colSpan={7}>
                      暂无记录
                    </td>
                  </tr>
                ) : (
                  filtered.map((x, idx) => (
                    <tr key={idx} className="border-b border-zinc-50">
                      <td className="px-4 py-3 text-xs text-zinc-500">{x.time}</td>
                      <td className="px-4 py-3 font-medium text-zinc-900">{x.stock}</td>
                      <td className="px-4 py-3 text-zinc-700">{x.direction}</td>
                      <td className="px-4 py-3 text-zinc-700">{Number(x.amount).toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <DecisionBadge decision={x.decision} />
                      </td>
                      <td className="px-4 py-3 text-zinc-700">{x.rule}</td>
                      <td className="px-4 py-3 text-zinc-600">{x.reason}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
